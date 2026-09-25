import uuid
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from core.branch_scope import scope_queryset
from .models import Employee, SaleSession, SaleSessionItem
from .sections import ROLE_PRESETS, SECTIONS
from .serializers import (
    EmployeeSerializer,
    SaleSessionItemCreateSerializer,
    SaleSessionItemEditSerializer,
    SaleSessionItemSerializer,
    SaleSessionManualCreateSerializer,
    SaleSessionOpenSerializer,
    SaleSessionReadSerializer,
    SaleSessionUpdateSerializer,
)
from .services import (
    close_session,
    clear_session_items,
    delete_session,
    delete_session_item,
    move_session_item,
    reopen_session,
    update_session_item,
)


class SectionsView(APIView):
    """يعيد قائمة أقسام النظام والصلاحيات المتاحة وأدياردة العملاء الجاهزة."""
    permission_section = "@identity"

    def get(self, request):
        return Response(
            {
                "sections": SECTIONS,
                "roles": ROLE_PRESETS,
            }
        )


class EmployeeViewSet(viewsets.ModelViewSet):
    permission_section = "employees"
    queryset = Employee.objects.select_related("branch").prefetch_related("allowed_branches").all()
    serializer_class = EmployeeSerializer
    search_fields = ["name", "phone", "branch__name"]
    ordering_fields = ["name", "created_at"]

    def get_queryset(self):
        qs = super().get_queryset()
        qs = scope_queryset(self.request, qs)
        branch = self.request.query_params.get("branch")
        if branch:
            qs = qs.filter(branch_id=branch)
        return qs

    def update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.sessions.exists():
            return Response(
                {"detail": "لا يمكن حذف موظف لديه ورديات بيع"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from django.contrib.auth.models import User
        user = instance.user
        self.perform_destroy(instance)
        if user is not None:
            User.objects.filter(pk=user.pk).delete()
        return Response({"detail": settings.API_MESSAGES["deleted"]}, status=status.HTTP_200_OK)


class SaleSessionViewSet(viewsets.ModelViewSet):
    permission_section = "sessions"
    queryset = SaleSession.objects.select_related("employee", "branch").all()
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def destroy(self, request, *args, **kwargs):
        session = self.get_object()
        try:
            delete_session(session)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": settings.API_MESSAGES["deleted"]}, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response(SaleSessionReadSerializer(instance).data)

    def get_serializer_class(self):
        if self.action == "create":
            return SaleSessionOpenSerializer
        if self.action in ("update", "partial_update"):
            return SaleSessionUpdateSerializer
        return SaleSessionReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = serializer.save()
        data = SaleSessionReadSerializer(session).data
        if getattr(session, "_reopened", False):
            data["reopened"] = True
        return Response(
            data,
            status=status.HTTP_201_CREATED,
            headers=self.get_success_headers(serializer.data),
        )

    def get_queryset(self):
        qs = super().get_queryset()
        qs = scope_queryset(self.request, qs)
        status_ = self.request.query_params.get("status")
        if status_:
            qs = qs.filter(status=status_)
        branch = self.request.query_params.get("branch")
        if branch:
            qs = qs.filter(branch_id=branch)
        employee = self.request.query_params.get("employee")
        if employee:
            qs = qs.filter(employee_id=employee)
        opened_from = self.request.query_params.get("opened_from")
        if opened_from:
            qs = qs.filter(opened_at__date__gte=opened_from)
        opened_to = self.request.query_params.get("opened_to")
        if opened_to:
            qs = qs.filter(opened_at__date__lte=opened_to)
        closed_from = self.request.query_params.get("closed_from")
        closed_to = self.request.query_params.get("closed_to")
        if closed_from or closed_to:
            normal = Q(is_manual=False)
            manual = Q(is_manual=True)
            if closed_from:
                normal &= Q(closed_at__date__gte=closed_from)
                manual &= Q(manual_date__gte=closed_from)
            if closed_to:
                normal &= Q(closed_at__date__lte=closed_to)
                manual &= Q(manual_date__lte=closed_to)
            qs = qs.filter(normal | manual)
        return qs

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        qs = self.filter_queryset(self.get_queryset())
        sessions = list(qs)
        items = [
            it
            for s in sessions
            for it in s.items.select_related("fabric").filter(is_returned=False)
        ]
        totals = {"cash": Decimal("0"), "transfer": Decimal("0"), "card": Decimal("0")}
        for it in items:
            totals[it.payment_method] += it.net_total
        total = sum(totals.values(), Decimal("0"))
        yards = sum(it.yards_effective for it in items)
        returned_count = sum(
            s.items.filter(is_returned=True).count() for s in sessions
        )
        return Response(
            {
                # تاريخ اليوم بحسب ساعة الخادم — مرجع الواجهة بدل ساعة الجهاز التي قد تكون غير مضبوطة
                "today": timezone.localdate().isoformat(),
                "count": len(sessions),
                "open_count": sum(1 for s in sessions if s.status == SaleSession.Status.OPEN),
                "closed_count": sum(1 for s in sessions if s.status == SaleSession.Status.CLOSED),
                "items_count": len(items),
                "returned_items_count": returned_count,
                "yards": float(yards),
                "total": float(total),
                "cash": float(totals["cash"]),
                "transfer": float(totals["transfer"]),
                "card": float(totals["card"]),
            }
        )

    @action(detail=True, methods=["post"], url_path="items")
    def add_item(self, request, pk=None):
        session = self.get_object()
        if session.status == SaleSession.Status.CLOSED:
            return Response({"detail": "الوردية مغلقة — لا يمكن إضافة بنود"}, status=status.HTTP_400_BAD_REQUEST)
        serializer = SaleSessionItemCreateSerializer(
            data=request.data, context={"session": session}
        )
        serializer.is_valid(raise_exception=True)
        item = serializer.save()
        return Response(SaleSessionItemSerializer(item).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="items/bulk")
    def add_items(self, request, pk=None):
        session = self.get_object()
        if session.status == SaleSession.Status.CLOSED:
            return Response({"detail": "الوردية مغلقة — لا يمكن إضافة بنود"}, status=status.HTTP_400_BAD_REQUEST)
        items = request.data.get("items")
        if not isinstance(items, list) or not items:
            return Response(
                {"detail": "أرسل قائمة بنود (items) لإضافتها معاً"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        sale_group = str(uuid.uuid4())
        # تُتحقق البنود واحدة تلو الأخرى داخل معاملة واحدة: كل بند يُراجع على بنود الوردية
        # المعلّقة (بما فيها الأصناف المضافة للتو في نفس الدفعة) — أي تجاوز للرصيد يُرفض
        # ويُلغى كامل الدفعة (كل أو لا شيء).
        with transaction.atomic():
            created = []
            for data in items:
                s = SaleSessionItemCreateSerializer(
                    data=data, context={"session": session, "sale_group": sale_group}
                )
                s.is_valid(raise_exception=True)
                created.append(s.save())
        return Response(
            SaleSessionItemSerializer(created, many=True).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["put", "patch", "delete"], url_path="items/(?P<item_id>[0-9]+)")
    def edit_item(self, request, pk=None, item_id=None):
        session = self.get_object()
        if request.method == "DELETE":
            try:
                item = session.items.select_related("fabric").get(pk=item_id)
            except SaleSessionItem.DoesNotExist:
                return Response({"detail": "البند غير موجود"}, status=status.HTTP_404_NOT_FOUND)
            try:
                delete_session_item(session, item)
            except (ValueError, serializers.ValidationError) as e:
                detail = getattr(e, "detail", str(e))
                if isinstance(detail, (list, tuple, dict)):
                    detail = "; ".join(str(x) for x in (detail.values() if isinstance(detail, dict) else detail))
                return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
            return Response({"detail": settings.API_MESSAGES["deleted"]}, status=status.HTTP_200_OK)
        try:
            item = session.items.select_related("fabric").get(pk=item_id)
        except SaleSessionItem.DoesNotExist:
            return Response({"detail": "البند غير موجود"}, status=status.HTTP_404_NOT_FOUND)
        serializer = SaleSessionItemEditSerializer(
            data=request.data,
            instance=item,
            context={"session": session},
            partial=request.method == "PATCH",
        )
        serializer.is_valid(raise_exception=True)
        try:
            item = update_session_item(session, item, serializer.validated_data)
        except (ValueError, serializers.ValidationError) as e:
            detail = getattr(e, "detail", str(e))
            if isinstance(detail, (list, tuple, dict)):
                detail = "; ".join(str(x) for x in (detail.values() if isinstance(detail, dict) else detail))
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
        return Response(SaleSessionItemSerializer(item).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="close")
    def close(self, request, pk=None):
        session = self.get_object()
        try:
            close_session(session)
        except (ValueError, serializers.ValidationError) as e:
            detail = getattr(e, "detail", str(e))
            if isinstance(detail, (list, tuple, dict)):
                detail = "; ".join(str(x) for x in (detail.values() if isinstance(detail, dict) else detail))
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
        return Response(SaleSessionReadSerializer(session).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="clear")
    def clear(self, request, pk=None):
        session = self.get_object()
        try:
            clear_session_items(session)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(SaleSessionReadSerializer(session).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="manual")
    def manual(self, request):
        serializer = SaleSessionManualCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        session = serializer.save()
        return Response(
            SaleSessionReadSerializer(session).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="move-item/(?P<item_id>[0-9]+)")
    def move_item(self, request, pk=None, item_id=None):
        session = self.get_object()
        try:
            item = session.items.select_related("fabric").get(pk=item_id)
        except SaleSessionItem.DoesNotExist:
            return Response({"detail": "البند غير موجود"}, status=status.HTTP_404_NOT_FOUND)
        target_id = request.data.get("target_session")
        if not target_id:
            return Response({"detail": "حدّد الوردية الهدف"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            target = scope_queryset(
                self.request, SaleSession.objects.select_related("branch")
            ).get(pk=int(target_id))
        except (ValueError, SaleSession.DoesNotExist):
            return Response({"detail": "الوردية الهدف غير موجودة"}, status=status.HTTP_404_NOT_FOUND)
        try:
            item = move_session_item(session, item, target)
        except (ValueError, serializers.ValidationError) as e:
            detail = getattr(e, "detail", str(e))
            if isinstance(detail, (list, tuple, dict)):
                detail = "; ".join(str(x) for x in (detail.values() if isinstance(detail, dict) else detail))
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
        return Response(SaleSessionItemSerializer(item).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="reopen")
    def reopen(self, request, pk=None):
        session = self.get_object()
        try:
            reopen_session(session)
        except (ValueError, serializers.ValidationError) as e:
            detail = getattr(e, "detail", str(e))
            if isinstance(detail, (list, tuple, dict)):
                detail = "; ".join(str(x) for x in (detail.values() if isinstance(detail, dict) else detail))
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
        return Response(SaleSessionReadSerializer(session).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="customer-sales")
    def customer_sales(self, request):
        """يُعيد كل بيعات زبونٍ بهاتفه عبر الورديات (المفتوحة والمغلقة) ضمن فروع المستخدم."""
        phone = (request.query_params.get("phone") or "").strip()
        if not phone:
            return Response(
                {"detail": "أدخل رقم هاتف الزبون"}, status=status.HTTP_400_BAD_REQUEST
            )
        items = (
            SaleSessionItem.objects.select_related(
                "fabric", "session__employee", "session__branch"
            )
            .filter(customer_phone=phone)
            .order_by("-sale_date", "-id")
        )
        items = scope_queryset(request, items, branch_field="session__branch")
        from .serializers import SaleSessionItemSerializer as _ItemSer
        rows = []
        for it in items:
            data = _ItemSer(it).data
            data["session_id"] = it.session_id
            data["session_status"] = it.session.status
            data["session_status_label"] = it.session.get_status_display()
            data["session_closed"] = it.session.status == SaleSession.Status.CLOSED
            rows.append(data)
        total = sum(Decimal(str(r["total"])) for r in rows if not r["is_returned"])
        yards = sum(Decimal(str(r["yards_effective"])) for r in rows if not r["is_returned"])
        return Response(
            {
                "phone": phone,
                "items": rows,
                "totals": {
                    "count": len(rows),
                    "returned_count": sum(1 for r in rows if r["is_returned"]),
                    "total": float(total),
                    "yards": float(yards),
                },
            }
        )

    @action(detail=False, methods=["post"], url_path="return-items")
    def return_items(self, request):
        """استرجاع بنود مبيعة لزبون: إبقاء السجل بوسم «مسترجع» وترجيع القماش للمخزون."""
        item_ids = request.data.get("item_ids")
        reason = request.data.get("reason", "")
        if not isinstance(item_ids, list) or not item_ids:
            return Response(
                {"detail": "أرسل قائمة البنود (item_ids)"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(item_ids) > 50:
            return Response(
                {"detail": "حد أقصى 50 بنداً في العملية الواحدة"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        session_ids = set(
            SaleSessionItem.objects.filter(pk__in=item_ids).values_list(
                "session_id", flat=True
            )
        )
        if len(session_ids) != 1:
            return Response(
                {"detail": "ارسل بنوداً من وردية واحدة فقط في كل عملية استرجاع"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from .services import return_session_items as do_return
        try:
            session = scope_queryset(
                request, SaleSession.objects.select_related("branch")
            ).get(pk=session_ids.pop())
        except SaleSession.DoesNotExist:
            return Response(
                {"detail": "الوردية غير موجودة ضمن فروعك المسموحة"},
                status=status.HTTP_404_NOT_FOUND,
            )
        items = list(session.items.select_related("fabric").filter(pk__in=item_ids))
        if len(items) != len(item_ids):
            return Response(
                {"detail": "بعض البنود غير موجودة في الوردية"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            do_return(session, items, reason=reason)
        except (ValueError, serializers.ValidationError) as e:
            detail = getattr(e, "detail", str(e))
            if isinstance(detail, (list, tuple, dict)):
                detail = "; ".join(str(x) for x in (detail.values() if isinstance(detail, dict) else detail))
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
        from .serializers import SaleSessionItemSerializer as _ItemSer
        return Response(
            {"items": _ItemSer(items, many=True).data},
            status=status.HTTP_200_OK,
        )