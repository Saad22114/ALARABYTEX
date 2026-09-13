from decimal import Decimal

from django.conf import settings
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Employee, SaleSession, SaleSessionItem
from .serializers import (
    EmployeeSerializer,
    SaleSessionItemCreateSerializer,
    SaleSessionItemEditSerializer,
    SaleSessionItemSerializer,
    SaleSessionOpenSerializer,
    SaleSessionReadSerializer,
)
from .services import close_session, delete_session_item, update_session_item


class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.select_related("branch").all()
    serializer_class = EmployeeSerializer
    search_fields = ["name", "phone", "branch__name"]
    ordering_fields = ["name", "created_at"]

    def get_queryset(self):
        qs = super().get_queryset()
        branch = self.request.query_params.get("branch")
        if branch:
            qs = qs.filter(branch_id=branch)
        return qs

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.sessions.exists():
            return Response(
                {"detail": "لا يمكن حذف موظف لديه ورديات بيع"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        self.perform_destroy(instance)
        return Response({"detail": settings.API_MESSAGES["deleted"]}, status=status.HTTP_200_OK)


class SaleSessionViewSet(viewsets.ModelViewSet):
    queryset = SaleSession.objects.select_related("employee", "branch").all()
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def destroy(self, request, *args, **kwargs):
        return Response(
            {"detail": "لا يمكن حذف وردية بيع — أغلقها فقط"},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def get_serializer_class(self):
        if self.action == "create":
            return SaleSessionOpenSerializer
        return SaleSessionReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = serializer.save()
        return Response(
            SaleSessionReadSerializer(session).data,
            status=status.HTTP_201_CREATED,
            headers=self.get_success_headers(serializer.data),
        )

    def get_queryset(self):
        qs = super().get_queryset()
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
        return qs

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        qs = self.filter_queryset(self.get_queryset())
        sessions = list(qs)
        items = [it for s in sessions for it in s.items.select_related("fabric")]
        totals = {"cash": Decimal("0"), "transfer": Decimal("0"), "card": Decimal("0")}
        for it in items:
            totals[it.payment_method] += it.total
        total = sum(totals.values(), Decimal("0"))
        yards = sum(it.yards_effective for it in items)
        return Response(
            {
                "count": len(sessions),
                "open_count": sum(1 for s in sessions if s.status == SaleSession.Status.OPEN),
                "closed_count": sum(1 for s in sessions if s.status == SaleSession.Status.CLOSED),
                "items_count": len(items),
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