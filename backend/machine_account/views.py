from decimal import Decimal
from datetime import date, timedelta

from django.db.models import Sum
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from core.branch_scope import scope_queryset
from sales.models import DailySale

from .models import MachineCollection
from .serializers import MachineCollectionSerializer

ZERO = Decimal("0")


def _card_sales_between(request, date_from, date_to, branch=None):
    """مبيعات البطاقة (المبيعات اليومية للورديات المغلقة) في الفترة ضمن نطاق الفروع."""
    qs = scope_queryset(
        request,
        DailySale.objects.filter(date__gte=date_from, date__lte=date_to),
    )
    if branch:
        qs = qs.filter(branch_id=branch)
    return qs.aggregate(t=Sum("card_amount"))["t"] or ZERO


def _received_between(request, date_from, date_to, branch=None):
    qs = scope_queryset(
        request,
        MachineCollection.objects.filter(date__gte=date_from, date__lte=date_to),
        "branch",
    )
    if branch:
        qs = qs.filter(branch_id=branch)
    return qs.aggregate(t=Sum("amount"))["t"] or ZERO


def _month_range(year, month):
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    return start, end


class MachineAccountView(APIView):
    """حساب الماكينة: مبيعات البطاقة − الدفعات المستلمة = الرصيد المتبقي.

    GET /api/machine-account/?date_from=..&date_to=..&branch=..
    """

    permission_section = "machine_account"

    def get(self, request):
        today = timezone.localdate()
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        branch = request.query_params.get("branch")

        try:
            start = date.fromisoformat(date_from) if date_from else None
        except ValueError:
            start = None
        try:
            end = date.fromisoformat(date_to) if date_to else None
        except ValueError:
            end = None
        if start is None:
            start = today.replace(day=1)
        if end is None:
            end = today
        if end < start:
            end = start

        card_total = _card_sales_between(request, start, end, branch)
        received_total = _received_between(request, start, end, branch)
        balance = card_total - received_total

        # الشهر الحالي
        m_start = today.replace(day=1)
        month_card = _card_sales_between(request, m_start, today, branch)
        month_received = _received_between(request, m_start, today, branch)

        # الاتجاه الشهري: شهور الفترة (بحد أقصى 24 شهراً للعرض).
        months = []
        cursor = date(start.year, start.month, 1)
        guard = 0
        while cursor <= end and guard < 24:
            ms, me = _month_range(cursor.year, cursor.month)
            actual_start = max(ms, start)
            actual_end = min(me, end)
            mc = _card_sales_between(request, actual_start, actual_end, branch)
            mr = _received_between(request, actual_start, actual_end, branch)
            months.append({
                "month": f"{cursor.year:04d}-{cursor.month:02d}",
                "card_sales": float(mc),
                "received": float(mr),
                "balance": float(mc - mr),
            })
            cursor = _shift_month(cursor, 1)
            guard += 1

        recent = scope_queryset(
            request, MachineCollection.objects.select_related("branch").order_by("-date", "-id"),
            "branch",
        )
        if branch:
            recent = recent.filter(branch_id=branch)
        recent = recent[:20]

        return Response({
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "totals": {
                "card_sales": float(card_total),
                "received": float(received_total),
                "balance": float(balance),
            },
            "month": {
                "card_sales": float(month_card),
                "received": float(month_received),
                "balance": float(month_card - month_received),
            },
            "months": months,
            "recent_collections": MachineCollectionSerializer(recent, many=True).data,
        })


def _shift_month(value, delta):
    month = value.month - 1 + delta
    year = value.year + month // 12
    month = month % 12 + 1
    return date(year, month, 1)


class MachineCollectionViewSet(viewsets.ModelViewSet):
    """دفعات الماكينة المستلمة — «وصلني كذا»."""

    permission_section = "machine_account"
    queryset = MachineCollection.objects.select_related("branch").all()
    serializer_class = MachineCollectionSerializer
    search_fields = ["reference", "notes", "branch__name"]
    ordering_fields = ["date", "amount", "created_at"]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        qs = scope_queryset(self.request, qs, "branch")
        branch = self.request.query_params.get("branch")
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        if branch:
            qs = qs.filter(branch_id=branch)
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user if self.request.user.is_authenticated else None)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({"detail": "تم حذف الدفعة"}, status=status.HTTP_200_OK)