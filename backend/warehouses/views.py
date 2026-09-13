from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Count, F, Max, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from suppliers.models import Fabric

from .models import (
    DocumentSequence,
    FabricRoll,
    GoodsReceipt,
    StockAdjustment,
    StockAdjustmentItem,
    StockCount,
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
    apply_adjustment,
    build_count_snapshot,
    complete_transfer,
    post_count,
    post_opening,
    post_receipt,
)


class WarehouseViewSet(viewsets.ModelViewSet):
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer
    search_fields = ["name", "code", "location", "manager_name"]
    ordering_fields = ["name", "code", "created_at"]

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
        if instance.rolls.exists() or instance.receipts.exists() or instance.transfers_out.exists():
            return Response(
                {"detail": "لا يمكن حذف المخزن لوجود لفات أو حركات مرتبطة به — يمكنك إيقافه بدلاً من ذلك"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        self.perform_destroy(instance)
        return Response({"detail": "تم حذف السجل بنجاح"}, status=status.HTTP_200_OK)


class FabricRollViewSet(viewsets.ModelViewSet):
    queryset = FabricRoll.objects.select_related("warehouse", "fabric")
    serializer_class = FabricRollSerializer
    search_fields = ["code", "fabric__name", "fabric__code"]
    ordering_fields = ["code", "created_at", "remaining_yards"]

    def get_queryset(self):
        qs = super().get_queryset()
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
    queryset = GoodsReceipt.objects.select_related("warehouse", "supplier").prefetch_related("items__fabric")
    search_fields = ["number", "supplier_receipt_no", "warehouse__name"]
    ordering_fields = ["date", "number", "created_at"]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return GoodsReceiptWriteSerializer
        return GoodsReceiptSerializer

    def get_queryset(self):
        return self.queryset

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
    queryset = StockTransfer.objects.select_related("from_warehouse", "to_warehouse", "to_branch").prefetch_related("items__fabric")
    search_fields = ["number", "from_warehouse__name", "to_warehouse__name", "to_branch__name"]
    ordering_fields = ["date", "number", "created_at"]

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
    queryset = StockAdjustment.objects.select_related("warehouse").prefetch_related("items__fabric")
    search_fields = ["number", "warehouse__name"]
    ordering_fields = ["date", "number", "created_at"]

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
    queryset = StockCount.objects.select_related("warehouse").prefetch_related("items__fabric")
    search_fields = ["number", "warehouse__name"]
    ordering_fields = ["date", "number", "created_at"]

    def get_serializer_class(self):
        if self.action == "create":
            return StockCountWriteSerializer
        if self.action == "items":
            return StockCountItemWriteSerializer
        return StockCountSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        build_count_snapshot(instance)
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
    def snapshot(self, request, pk=None):
        count = self.get_object()
        build_count_snapshot(count)
        return Response(StockCountSerializer(count).data)

    @action(detail=True, methods=["post"])
    def post(self, request, pk=None):
        count = self.get_object()
        post_count(count)
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


class StockMovementViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = StockMovement.objects.select_related("warehouse", "fabric", "roll")
    serializer_class = StockMovementSerializer
    search_fields = ["reference_no", "notes", "fabric__name"]
    ordering_fields = ["date", "quantity", "created_at"]

    def get_queryset(self):
        qs = super().get_queryset()
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
    queryset = StockOpening.objects.select_related("warehouse").prefetch_related("items__fabric")
    serializer_class = StockOpeningSerializer
    search_fields = ["number", "warehouse__name"]
    ordering_fields = ["date", "number", "created_at"]

    def get_queryset(self):
        qs = super().get_queryset()
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
        if search:
            rows = rows.filter(fabric__name__icontains=search)

        warehouses = {w.id: w for w in Warehouse.objects.filter(is_active=True)}

        agg = (
            rows.values("warehouse_id", "fabric_id")
            .annotate(total_yards=Sum("remaining_yards"), rolls_available=Count("id"))
            .order_by("fabric_id")
        )
        last_dates = dict(
            StockMovement.objects.filter(movement_type=StockMovement.Type.RECEIPT)
            .values("warehouse_id", "fabric_id")
            .annotate(last_date=Max("date"))
            .values_list("warehouse_id", "fabric_id", "last_date")
        )

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
            entry["warehouses"].sort(key=lambda w: w["warehouse_name"])
            result.append(entry)

        result.sort(key=lambda e: e["fabric_name"])
        total_yards = sum(e["total_yards"] for e in result)
        return Response({
            "items": result,
            "totals": {
                "total_yards": total_yards,
                "rolls_available": sum(e["rolls_available"] for e in result),
                "low_stock_count": sum(1 for e in result if e["low_stock"]),
                "warehouses": len([w for w in warehouses.values() if not w.is_branch_stock]),
            },
        })


class StockBalanceSetView(APIView):
    """يضبط رصيد قماش في مخزن (أو عدة مخازن) بقيمة جديدة عبر تسوية مخزون تلقائية.

    POST body: {"fabric": id, "date": "YYYY-MM-DD", "notes": "", "items": [{"warehouse": id, "yards": n}, ...]}
    لكل مخزن يخصم الفرق: زيادة -> تسوية إضافة، نقص -> تسوية خصم.
    """

    def post(self, request):
        fabric = get_object_or_404(Fabric, pk=request.data.get("fabric"))
        items_data = request.data.get("items") or []
        if not items_data:
            return Response({"detail": "أضف صنفاً واحداً على الأقل"}, status=status.HTTP_400_BAD_REQUEST)

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