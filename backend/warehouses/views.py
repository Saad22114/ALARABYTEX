from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Count, F, Max, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from suppliers.models import Fabric
from core.admin_secret import require_admin_password
from core.branch_scope import allowed_branch_ids, scope_queryset, scope_queryset_or
from reports.cogs import fabric_average_costs

from .models import (
    DocumentSequence,
    FabricRoll,
    GoodsReceipt,
    StockAdjustment,
    StockAdjustmentItem,
    StockCount,
    StockCountItem,
    StockMovement,
    StockOpening,
    StockTransfer,
    Warehouse,
)
from .serializers import (
    FabricRollSerializer,
    GoodsReceiptSerializer,
    GoodsReceiptWriteSerializer,
    StockAdjustmentSerializer,
    StockAdjustmentWriteSerializer,
    StockCountItemWriteSerializer,
    StockCountListSerializer,
    StockCountSerializer,
    StockCountWriteSerializer,
    StockMovementSerializer,
    StockOpeningSerializer,
    StockOpeningWriteSerializer,
    StockTransferSerializer,
    StockTransferWriteSerializer,
    WarehouseSerializer,
)
from .services import (
    add_count_line,
    apply_adjustment,
    build_count_snapshot,
    complete_transfer,
    post_count,
    post_opening,
    post_receipt,
    public_summary,
    remove_count_line,
)


def _message(exc):
    """نصّ خطأ واحد يُعرض في سطر، لا كائن JSON داخل حقل detail.

    خطأ التحقّق قد يكون قائمةً أو قاموساً؛ والواجهة تعرض ``detail`` نصّاً،
    فترى المستخدم ``["نص"]`` و``{"x": "نص"}`` بدل الجملة. نجمله هنا.
    """
    detail = getattr(exc, "detail", str(exc))
    if isinstance(detail, dict):
        detail = "; ".join(str(v) for v in detail.values())
    elif isinstance(detail, (list, tuple)):
        detail = "; ".join(str(v) for v in detail)
    return str(detail)


def _count_subtitle(count, summary):
    """سطر يوضيحي في ملف الجرد: من عدّ، وأين، ومتى، وكم بقي."""
    counter = count.counted_by.name if count.counted_by else "غير محدّد"
    parts = [
        f"المخزن: {count.warehouse.name}",
        f"التاريخ: {count.date}",
        f"العدّاد: {counter}",
        "جرد مغلق" if count.blind else "جرد مفتوح",
        f"مُرصد {summary['counted']} من {summary['items']}",
    ]
    if summary["pending"]:
        parts.append(f"بقي {summary['pending']}")
    if summary["variances"]:
        parts.append(
            f"فروق: {summary['variances']} صنف / "
            f"{summary['net_yards']:.2f} ياردة / {summary['value']:.2f} قيمة"
        )
    return "  |  ".join(parts)


class WarehouseViewSet(viewsets.ModelViewSet):
    permission_section = "warehouses"
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer
    search_fields = ["name", "code", "location", "manager_name"]
    ordering_fields = ["name", "code", "created_at"]

    def get_queryset(self):
        return scope_queryset(self.request, super().get_queryset())

    @action(detail=True, methods=["get"])
    def summary(self, request, pk=None):
        warehouse = self.get_object()
        rows = (
            FabricRoll.objects.filter(warehouse=warehouse, status=FabricRoll.Status.AVAILABLE)
            .values("fabric_id", fabric_name=F("fabric__name"))
            .annotate(
                total_yards=Sum("remaining_yards"),
                rolls_available=Count("id"),
            )
            .order_by("fabric__name")
        )
        data = [
            {
                "fabric": r["fabric_id"],
                "fabric_name": r["fabric_name"],
                "total_yards": r["total_yards"],
                "rolls_available": r["rolls_available"],
            }
            for r in rows
        ]
        return Response(data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        error = require_admin_password(request)
        if error is not None:
            return error
        if instance.rolls.exists() or instance.receipts.exists() or instance.transfers_out.exists():
            return Response(
                {"detail": "لا يمكن حذف المخزن لوجود لفات أو حركات مرتبطة به — يمكنك إيقافه بدلاً من ذلك"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        self.perform_destroy(instance)
        return Response({"detail": "تم حذف السجل بنجاح"}, status=status.HTTP_200_OK)


class FabricRollViewSet(viewsets.ModelViewSet):
    permission_section = "warehouses"
    queryset = FabricRoll.objects.select_related("warehouse", "fabric")
    serializer_class = FabricRollSerializer
    search_fields = ["code", "fabric__name", "fabric__code"]
    ordering_fields = ["code", "created_at", "remaining_yards"]

    def get_queryset(self):
        qs = super().get_queryset()
        qs = scope_queryset(self.request, qs, branch_field="warehouse__branch")
        warehouse = self.request.query_params.get("warehouse")
        fabric = self.request.query_params.get("fabric")
        status_filter = self.request.query_params.get("status")
        if warehouse:
            qs = qs.filter(warehouse_id=warehouse)
        if fabric:
            qs = qs.filter(fabric_id=fabric)
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.movements.exists():
            return Response(
                {"detail": "لا يمكن حذف لفة مسجلة في حركات المخزون"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        self.perform_destroy(instance)
        return Response({"detail": "تم حذف السجل بنجاح"}, status=status.HTTP_200_OK)


class GoodsReceiptViewSet(viewsets.ModelViewSet):
    permission_section = "warehouses"
    queryset = GoodsReceipt.objects.select_related("warehouse", "supplier").prefetch_related("items__fabric")
    search_fields = ["number", "supplier_receipt_no", "warehouse__name"]
    ordering_fields = ["date", "number", "created_at"]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return GoodsReceiptWriteSerializer
        return GoodsReceiptSerializer

    def get_queryset(self):
        return scope_queryset_or(
            self.request, self.queryset, ["warehouse__branch", "branch"]
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response(GoodsReceiptSerializer(instance).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response(GoodsReceiptSerializer(instance).data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status == GoodsReceipt.Status.POSTED:
            return Response(
                {"detail": "لا يمكن حذف سند مُرحّل — أنشئ سنداً عكسياً بدلاً من ذلك"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        self.perform_destroy(instance)
        return Response({"detail": "تم حذف السجل بنجاح"}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def post(self, request, pk=None):
        receipt = self.get_object()
        post_receipt(receipt)
        return Response(GoodsReceiptSerializer(receipt).data)


class StockTransferViewSet(viewsets.ModelViewSet):
    permission_section = "warehouses"
    queryset = StockTransfer.objects.select_related("from_warehouse", "to_warehouse", "to_branch").prefetch_related("items__fabric")
    search_fields = ["number", "from_warehouse__name", "to_warehouse__name", "to_branch__name"]
    ordering_fields = ["date", "number", "created_at"]

    def get_queryset(self):
        return scope_queryset_or(
            self.request,
            self.queryset,
            ["from_warehouse__branch", "to_warehouse__branch", "to_branch"],
        )

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return StockTransferWriteSerializer
        return StockTransferSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response(StockTransferSerializer(instance).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response(StockTransferSerializer(instance).data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status in (StockTransfer.Status.REQUESTED, StockTransfer.Status.APPROVED):
            return Response(
                {"detail": "لا يمكن حذف تحويل قيد التنفيذ — ارفضه أو ألغِه أولاً"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if instance.status == StockTransfer.Status.COMPLETED:
            return Response(
                {"detail": "لا يمكن حذف تحويل منفّذ"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        self.perform_destroy(instance)
        return Response({"detail": "تم حذف السجل بنجاح"}, status=status.HTTP_200_OK)

    def _emit(self, instance):
        return StockTransferSerializer(instance).data

    @action(detail=True, methods=["post"])
    def request(self, request, pk=None):
        transfer = self.get_object()
        if transfer.status not in (StockTransfer.Status.DRAFT, StockTransfer.Status.REJECTED):
            return Response({"detail": "التحويل يجب أن يكون مسودة أو مرفوضاً لتقديم الطلب"},
                            status=status.HTTP_400_BAD_REQUEST)
        transfer.status = StockTransfer.Status.REQUESTED
        transfer.requested_at = timezone.now()
        transfer.requested_by = request.data.get("requested_by", "") or transfer.requested_by
        transfer.save(update_fields=["status", "requested_at", "requested_by"])
        return Response(self._emit(transfer))

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        transfer = self.get_object()
        if transfer.status != StockTransfer.Status.REQUESTED:
            return Response({"detail": "التحويل يجب أن يكون بانتظار الموافقة"},
                            status=status.HTTP_400_BAD_REQUEST)
        transfer.status = StockTransfer.Status.APPROVED
        transfer.approved_at = timezone.now()
        transfer.approved_by = request.data.get("approved_by", "") or transfer.approved_by
        transfer.save(update_fields=["status", "approved_at", "approved_by"])
        return Response(self._emit(transfer))

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        transfer = self.get_object()
        if transfer.status != StockTransfer.Status.REQUESTED:
            return Response({"detail": "التحويل يجب أن يكون بانتظار الموافقة"},
                            status=status.HTTP_400_BAD_REQUEST)
        transfer.status = StockTransfer.Status.REJECTED
        transfer.save(update_fields=["status"])
        return Response(self._emit(transfer))

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        transfer = self.get_object()
        if transfer.status != StockTransfer.Status.APPROVED:
            return Response({"detail": "التحويل يجب أن يكون موافقاً عليه للتنفيذ"},
                            status=status.HTTP_400_BAD_REQUEST)
        complete_transfer(transfer)
        # إبطال كاش التحميل المسبق كي تُقرأ عناصر محيّثة بعد التنفيذ
        transfer._prefetched_objects_cache = {}
        return Response(self._emit(transfer))

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        transfer = self.get_object()
        if transfer.status == StockTransfer.Status.COMPLETED:
            return Response({"detail": "لا يمكن إلغاء تحويل منفّذ"},
                            status=status.HTTP_400_BAD_REQUEST)
        transfer.status = StockTransfer.Status.CANCELLED
        transfer.save(update_fields=["status"])
        return Response(self._emit(transfer))


class StockAdjustmentViewSet(viewsets.ModelViewSet):
    permission_section = "warehouses"
    queryset = StockAdjustment.objects.select_related("warehouse").prefetch_related("items__fabric")
    search_fields = ["number", "warehouse__name"]
    ordering_fields = ["date", "number", "created_at"]

    def get_queryset(self):
        return scope_queryset(self.request, self.queryset, branch_field="warehouse__branch")

    def get_serializer_class(self):
        if self.action == "create":
            return StockAdjustmentWriteSerializer
        return StockAdjustmentSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        apply_adjustment(instance)
        return Response(StockAdjustmentSerializer(instance).data, status=status.HTTP_201_CREATED)


class StockCountViewSet(viewsets.ModelViewSet):
    permission_section = "warehouses"
    queryset = StockCount.objects.select_related("warehouse", "counted_by")
    search_fields = ["number", "warehouse__name", "counted_by__name"]
    ordering_fields = ["date", "number", "created_at"]

    def get_queryset(self):
        return scope_queryset(self.request, self.queryset, branch_field="warehouse__branch")

    def get_serializer_class(self):
        if self.action == "create":
            return StockCountWriteSerializer
        if self.action == "items":
            return StockCountItemWriteSerializer
        # القائمة لا تحتاج أصناف كل جلسة: الملخّص وحده يجيب «كم رُصد وكم
        # فروق». تحميلُ صنفٍ لكل سطرٍ في القائمة كان
        # الصفوف لعرض خمسة أعمدة.
        if self.action == "list":
            return StockCountListSerializer
        return StockCountSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        build_count_snapshot(instance, serializer.validated_data.get("fabrics"))
        return Response(StockCountSerializer(instance).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get", "put", "patch"])
    def items(self, request, pk=None):
        count = self.get_object()
        if request.method == "GET":
            return Response(StockCountSerializer(count).data["items"])
        serializer = StockCountItemWriteSerializer(count, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(StockCountSerializer(count).data["items"])

    @action(detail=True, methods=["post"])
    def add_fabric(self, request, pk=None):
        """يضيف قماشاً وُجد على الرفّ وليس له سطرٌ في الجرد.

        هذا هو الشقّ الذي كان مفقوداً: الجرد محصورٌ فيما رصيده الدفتري
        موجب، فيستحيل عليه أن يُبلّغ عن قماشٍ وُجد بلا دفتر — وهو أشيع
        الفروق في المخازن وأخطرها على الكمية.
        """
        count = self.get_object()
        fabric = get_object_or_404(Fabric, pk=request.data.get("fabric"))
        try:
            add_count_line(count, fabric)
        except serializers.ValidationError as exc:
            return Response(
                {"detail": _message(exc)}, status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(StockCountSerializer(count).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="items/(?P<item_id>[0-9]+)/remove")
    def remove_item(self, request, pk=None, item_id=None):
        count = self.get_object()
        item = get_object_or_404(StockCountItem, pk=item_id, count=count)
        try:
            remove_count_line(count, item)
        except serializers.ValidationError as exc:
            return Response(
                {"detail": _message(exc)}, status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(StockCountSerializer(count).data)

    @action(detail=True, methods=["post"])
    def snapshot(self, request, pk=None):
        count = self.get_object()
        build_count_snapshot(count)
        return Response(StockCountSerializer(count).data)

    @action(detail=True, methods=["post"])
    def post(self, request, pk=None):
        count = self.get_object()
        try:
            post_count(count)
        except serializers.ValidationError as exc:
            return Response(
                {"detail": _message(exc)}, status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(StockCountSerializer(count).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        count = self.get_object()
        if count.status != StockCount.Status.OPEN:
            return Response({"detail": "لا يمكن إلغاء جلسة غير مفتوحة"},
                            status=status.HTTP_400_BAD_REQUEST)
        count.status = StockCount.Status.CANCELLED
        count.save(update_fields=["status"])
        return Response(StockCountSerializer(count).data)

    @action(detail=True, methods=["get"])
    def export(self, request, pk=None):
        """كشف الجرد إلى Excel: ورقةُ رصدٍ تُملأ بيد، وورقةُ فروقٍ تُقرأ بالعين.

        في الجرد المغلق تُخفي ورقةُ الرصدُ الرصيد الدفتري، وإلا صار الملف
        المطبوع ورقةَ مطابقةٍ لا ورقةَ جرد. أمّا ورقةُ الفروق فتعنى فقط ما بعد
        النشر — لا معنى لفروقٍ لا يحتاج مشاهدة بعدها.

        ومع كل سطر سعرا قماشه: سعرُ الشراء وسعرُ البيع لليارد، فتصير
        الورقة تُقرأ بمالها لا بالمتر وحده — المراجع يعرف قيمة ما عدّ
        وقيمة ما نقص، لا مقدار النقص وحده.
        """
        count = self.get_object()
        hide = count.hides_system_balance
        # نفس قاعدة الشاشة: الملخّص لا يفصح عن الفروق ما دامت الجلسة مغلقة.
        summary = public_summary(count)
        costs = fabric_average_costs(
            list(count.items.values_list("fabric_id", flat=True).distinct())
        )
        rows = []
        for item in count.items.select_related("fabric").all():
            rows.append([
                item.fabric.name,
                item.fabric.code or "",
                None if hide else float(item.system_yards),
                float(item.counted_yards) if item.counted_yards is not None else None,
                None if hide else float(item.difference),
                "مطابق" if (item.counted_yards is not None and not item.is_variance)
                else ("فروق" if item.counted_yards is not None else "لم يُرصد"),
                float(costs.get(item.fabric_id) or 0),
                float(item.fabric.purchase_price or 0),
                float(item.fabric.sale_price_yard or 0),
                item.note or "",
            ])
        counted_rows = [
            r for r in rows if r[3] is not None
        ]
        if counted_rows and not hide:
            rows.append([
                "الإجمالي", "",
                round(sum(r[2] or 0 for r in counted_rows), 2),
                round(sum(r[3] or 0 for r in counted_rows), 2),
                round(sum(r[4] or 0 for r in counted_rows), 2),
                f"{summary['variances']} صنف عليه فرق", "", "", "", "",
            ])
        columns = [
            {"label": "القماش", "type": "text"},
            {"label": "الكود", "type": "text"},
            {"label": "الرصيد الدفتري", "type": "money"},
            {"label": "الرصيد المرصود", "type": "money"},
            {"label": "الفرق", "type": "money"},
            {"label": "الحالة", "type": "text"},
            {"label": "متوسط التكلفة", "type": "money"},
            {"label": "سعر الشراء", "type": "money"},
            {"label": "سعر البيع", "type": "money"},
            {"label": "سبب الفرق", "type": "text"},
        ]
        from core import excel

        sheets = [{
            "title": "جرد",
            "heading": f"جلسة جرد {count.number}",
            "subtitle": _count_subtitle(count, summary),
            "columns": columns,
            "rows": rows,
        }]
        variance_rows = [r for r in rows if r[5] == "فروق"]
        # ورقةُ فروقٍ فارغةٌ لا تقرأ شيئاً: إمّا فيها فروقٌ تستحق الصفحة،
        # وإمّا فالمطابقةُ كلُّها فلا داعيَ لورقةٍ ثانية.
        if variance_rows and count.status != StockCount.Status.OPEN:
            sheets.append({
                "title": "فروق",
                "heading": f"فروق جرد {count.number}",
                "subtitle": _count_subtitle(count, summary),
                "columns": columns,
                "rows": variance_rows,
            })
        workbook = excel.build_workbook(sheets)
        if workbook is None:
            return Response(
                {"detail": "مكتبة openpyxl غير مثبّتة على الخادم."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return excel.xlsx_response(workbook, f"جرد-{count.number}", ascii_name="stock-count")


class StockMovementViewSet(viewsets.ReadOnlyModelViewSet):
    permission_section = "warehouses"
    queryset = StockMovement.objects.select_related("warehouse", "fabric", "roll")
    serializer_class = StockMovementSerializer
    search_fields = ["reference_no", "notes", "fabric__name"]
    ordering_fields = ["date", "quantity", "created_at"]

    def get_queryset(self):
        qs = super().get_queryset()
        qs = scope_queryset(self.request, qs, branch_field="warehouse__branch")
        params = self.request.query_params
        if params.get("warehouse"):
            qs = qs.filter(warehouse_id=params["warehouse"])
        if params.get("fabric"):
            qs = qs.filter(fabric_id=params["fabric"])
        if params.get("movement_type"):
            qs = qs.filter(movement_type=params["movement_type"])
        if params.get("date_from"):
            qs = qs.filter(date__gte=params["date_from"])
        if params.get("date_to"):
            qs = qs.filter(date__lte=params["date_to"])
        return qs


class StockOpeningViewSet(viewsets.ReadOnlyModelViewSet):
    permission_section = "warehouses"
    queryset = StockOpening.objects.select_related("warehouse").prefetch_related("items__fabric")
    serializer_class = StockOpeningSerializer
    search_fields = ["number", "warehouse__name"]
    ordering_fields = ["date", "number", "created_at"]

    def get_queryset(self):
        qs = super().get_queryset()
        qs = scope_queryset(self.request, qs, branch_field="warehouse__branch")
        warehouse = self.request.query_params.get("warehouse")
        if warehouse:
            qs = qs.filter(warehouse_id=warehouse)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = StockOpeningWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        opening = serializer.save()
        post_opening(opening)
        return Response(StockOpeningSerializer(opening).data, status=status.HTTP_201_CREATED)

    def get_serializer_class(self):
        return StockOpeningSerializer


class StockBalanceView(APIView):
    """الرصيد الكلي لكل قماش في كل المخازن مع تنبيهات الحد الأدنى."""
    permission_section = "warehouses"

    def get(self, request):
        filters = {}
        warehouse_id = request.query_params.get("warehouse")
        if warehouse_id:
            filters["warehouse_id"] = warehouse_id
        search = request.query_params.get("search", "").strip()
        fabric_id = request.query_params.get("fabric")
        if fabric_id:
            filters["fabric_id"] = fabric_id

        rows = FabricRoll.objects.filter(status=FabricRoll.Status.AVAILABLE, **filters)
        rows = scope_queryset(self.request, rows, branch_field="warehouse__branch")
        if search:
            rows = rows.filter(fabric__name__icontains=search)

        warehouses = {
            w.id: w
            for w in scope_queryset(self.request, Warehouse.objects.filter(is_active=True))
        }

        agg = (
            rows.values("warehouse_id", "fabric_id")
            .annotate(total_yards=Sum("remaining_yards"), rolls_available=Count("id"))
            .order_by("fabric_id")
        )
        last_dates = {
            (row["warehouse_id"], row["fabric_id"]): row["last_date"]
            for row in (
                StockMovement.objects.filter(movement_type=StockMovement.Type.RECEIPT)
                .values("warehouse_id", "fabric_id")
                .annotate(last_date=Max("date"))
            )
        }

        near_rows = (
            rows.filter(remaining_yards__lte=10)
            .values("fabric_id")
            .annotate(near_count=Count("id"))
        )
        near_by_fabric = {r["fabric_id"]: r["near_count"] for r in near_rows}

        by_fabric = {}
        for r in agg:
            key = r["fabric_id"]
            entry = by_fabric.setdefault(key, {
                "fabric": key,
                "fabric_name": "",
                "fabric_code": "",
                "min_stock": 0,
                "unit": "yard",
                "total_yards": Decimal("0"),
                "rolls_available": 0,
                "near_depletion_rolls": 0,
                "warehouses": [],
            })
            entry["total_yards"] += r["total_yards"]
            entry["rolls_available"] += r["rolls_available"]
            wh = warehouses.get(r["warehouse_id"])
            if wh is None:
                continue
            entry["warehouses"].append({
                "warehouse": r["warehouse_id"],
                "warehouse_name": wh.name,
                "is_branch_stock": wh.is_branch_stock,
                "total_yards": r["total_yards"],
                "rolls_available": r["rolls_available"],
                "last_receipt_date": last_dates.get((r["warehouse_id"], r["fabric_id"])) or None,
            })

        fabrics = {f.id: f for f in Fabric.objects.filter(id__in=by_fabric.keys())}
        result = []
        for fid, entry in by_fabric.items():
            f = fabrics.get(fid)
            if f is None:
                continue
            entry["fabric_name"] = f.name
            entry["fabric_code"] = f.code
            entry["min_stock"] = f.min_stock
            entry["unit"] = f.unit
            entry["low_stock"] = entry["total_yards"] < f.min_stock
            entry["near_depletion_rolls"] = near_by_fabric.get(fid, 0)
            entry["warehouses"].sort(key=lambda w: w["warehouse_name"])
            result.append(entry)

        result.sort(key=lambda e: e["fabric_name"])
        low_stock_only = request.query_params.get("low_stock")
        if low_stock_only and str(low_stock_only).strip().lower() in ("true", "1", "yes", "on"):
            result = [e for e in result if e["low_stock"]]

        if request.query_params.get("export") == "xlsx":
            from reports.views import _export_generic_to_xlsx, _xlsx_response

            headers = [
                "القماش", "الكود", "الحد الأدنى", "الكمية المتاحة",
                "الطاقات المتاحة", "طاقات قاربت النفاد", "الحالة",
            ]
            rows_x = [
                [
                    e["fabric_name"], e["fabric_code"], e["min_stock"],
                    float(e["total_yards"]), e["rolls_available"],
                    e["near_depletion_rolls"],
                    "منخفض" if e["low_stock"] else "مناسب",
                ]
                for e in result
            ]
            rows_x.append([
                "الإجمالي", "",
                round(sum(float(e["min_stock"]) for e in result), 2),
                round(sum(float(e["total_yards"]) for e in result), 2),
                sum(e["rolls_available"] for e in result),
                sum(e["near_depletion_rolls"] for e in result),
                "",
            ])
            wb = _export_generic_to_xlsx(
                "المخزون الموحد", headers, rows_x,
                types=["text", "text", "number", "number", "number", "number", "text"],
                subtitle=(
                    f"عدد الأقمشة: {len(result)}"
                    f"  |  منخفض: {sum(1 for e in result if e['low_stock'])}"
                ),
            )
            if wb is None:
                return Response({"detail": "مكتبة openpyxl غير مثبتة"}, status=500)
            return _xlsx_response(wb, "المخزون_الموحد")

        total_yards = sum(e["total_yards"] for e in result)
        return Response({
            "items": result,
            "totals": {
                "total_yards": total_yards,
                "rolls_available": sum(e["rolls_available"] for e in result),
                "low_stock_count": sum(1 for e in result if e["low_stock"]),
                "near_depletion_rolls": sum(e["near_depletion_rolls"] for e in result),
                "warehouses": len([w for w in warehouses.values() if not w.is_branch_stock]),
            },
        })


class StockBalanceSetView(APIView):
    """يضبط رصيد قماش في مخزن (أو عدة مخازن) بقيمة جديدة عبر تسوية مخزون تلقائية.

    POST body: {"fabric": id, "date": "YYYY-MM-DD", "notes": "", "items": [{"warehouse": id, "yards": n}, ...]}
    لكل مخزن يخصم الفرق: زيادة -> تسوية إضافة، نقص -> تسوية خصم.
    """
    permission_section = "warehouses"

    def post(self, request):
        fabric = get_object_or_404(Fabric, pk=request.data.get("fabric"))
        items_data = request.data.get("items") or []
        if not items_data:
            return Response({"detail": "أضف صنفاً واحداً على الأقل"}, status=status.HTTP_400_BAD_REQUEST)

        allowed = allowed_branch_ids(request)

        lines = []
        seen_warehouses = set()
        for it in items_data:
            warehouse_id = it.get("warehouse")
            if not warehouse_id:
                return Response({"detail": "حدد المخزن لكل صنف"}, status=status.HTTP_400_BAD_REQUEST)
            if warehouse_id in seen_warehouses:
                return Response({"detail": "المخزن مكرر في الأصناف"}, status=status.HTTP_400_BAD_REQUEST)
            seen_warehouses.add(warehouse_id)
            try:
                target = Decimal(str(it.get("yards", "0")))
            except (TypeError, ValueError, InvalidOperation):
                return Response({"detail": "الكمية غير صالحة"}, status=status.HTTP_400_BAD_REQUEST)
            if target < 0:
                return Response({"detail": "الكمية لا يمكن أن تكون سالبة"}, status=status.HTTP_400_BAD_REQUEST)
            lines.append((warehouse_id, target))

        with transaction.atomic():
            for warehouse_id, target in lines:
                warehouse = get_object_or_404(Warehouse, pk=warehouse_id)
                if allowed is not None and warehouse.branch_id not in allowed:
                    return Response(
                        {"detail": "لا يمكنك تعديل رصيد مخزن خارج فرعك"},
                        status=status.HTTP_403_FORBIDDEN,
                    )
                current = (
                    FabricRoll.objects.filter(
                        warehouse=warehouse, fabric=fabric, status=FabricRoll.Status.AVAILABLE
                    ).aggregate(total=Sum("remaining_yards"))["total"] or Decimal("0")
                )
                diff = (target - current).quantize(Decimal("0.01"))
                if abs(diff) < Decimal("0.005"):
                    continue
                direction = (
                    StockAdjustment.Direction.IN if diff > 0 else StockAdjustment.Direction.OUT
                )
                adjustment = StockAdjustment.objects.create(
                    number=DocumentSequence.next_number("ADJ"),
                    warehouse=warehouse,
                    date=request.data.get("date") or timezone.localdate(),
                    reason=StockAdjustment.Reason.CORRECTION,
                    direction=direction,
                    notes=request.data.get("notes", "") or "تعديل رصيد من صفحة المخزون",
                )
                StockAdjustmentItem.objects.create(
                    adjustment=adjustment,
                    fabric=fabric,
                    yards=abs(diff).quantize(Decimal("0.01")),
                    rolls_count=1,
                )
                apply_adjustment(adjustment)
        return Response({"detail": "تم تعديل رصيد المخزون بنجاح"}, status=status.HTTP_200_OK)