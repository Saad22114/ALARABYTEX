from django.conf import settings
import re
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.daterange import resolve_range
from core.branch_scope import scope_queryset

from sale_sessions.models import SaleSessionItem

from .models import Customer
from .serializers import CustomerSerializer


class CustomerViewSet(viewsets.ModelViewSet):
    permission_section = "customers"
    queryset = Customer.objects.select_related("branch").order_by("name")
    serializer_class = CustomerSerializer
    search_fields = ["name", "phone", "email", "address"]
    ordering_fields = ["name", "phone", "created_at", "is_active"]

    def get_queryset(self):
        qs = super().get_queryset()
        qs = scope_queryset(self.request, qs)
        params = self.request.query_params
        branch = params.get("branch")
        if branch:
            qs = qs.filter(branch_id=branch)
        is_active = params.get("is_active")
        if is_active in ("true", "1"):
            qs = qs.filter(is_active=True)
        elif is_active in ("false", "0"):
            qs = qs.filter(is_active=False)
        date_from = params.get("date_from")
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        date_to = params.get("date_to")
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)
        return qs

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        qs = self.get_queryset()
        start_date, end_date, _ = resolve_range(request.query_params, default_period="month")
        return Response({
            "total_customers": qs.count(),
            "active_count": qs.filter(is_active=True).count(),
            "new_count": qs.filter(
                created_at__date__gte=start_date, created_at__date__lte=end_date
            ).count(),
            "with_phone_count": qs.exclude(phone__isnull=True).exclude(phone="").count(),
        })

    @action(detail=False, methods=["get"], url_path="lookup")
    def lookup(self, request):
        phone = (request.query_params.get("phone") or "").strip()
        if not phone:
            return Response({"found": False, "customer": None})
        customer = (
            scope_queryset(self.request, Customer.objects.all())
            .filter(phone=phone)
            .first()
        )
        if customer is None:
            return Response({"found": False, "customer": None})
        data = CustomerSerializer(customer).data
        data["last_purchase_date"] = self._last_purchase_date(request, phone)
        return Response({"found": True, "customer": data})

    @staticmethod
    def _last_purchase_date(request, phone):
        phones = {phone, re.sub(r"\s", "", phone)} if phone else {phone}
        return (
            scope_queryset(
                request,
                SaleSessionItem.objects.filter(customer_phone__in=phones),
                branch_field="session__branch",
            )
            .order_by("-sale_date")
            .values_list("sale_date", flat=True)
            .first()
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(
            {"detail": settings.API_MESSAGES["deleted"]},
            status=status.HTTP_200_OK,
        )