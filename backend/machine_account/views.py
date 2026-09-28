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

#: كل حساب تسوية وعمود المبيعات اليومية الذي يقابله.
#:
#: ``machine`` ← مبيعات البطاقة: شركة الماكينة تحوّلها لنا متأخرة.
#: ``bank``    ← مبيعات التحويل: يذهبها الزبون إلى حسابنا البنكي.
#:
#: Cash يستلم فوراً فلا حساب له، و`other` غير متتبَّع هنا.
ACCOUNTS = {
    MachineCollection.Account.MACHINE: {
        "label": MachineCollection.Account.MACHINE.label,
        "sales_field": "card_amount",
        "hint": "مبيعات البطاقة — تنتظر تحويل شركة الماكينة",
    },
    MachineCollection.Account.BANK: {
        "label": MachineCollection.Account.BANK.label,
        "sales_field": "transfer_amount",
        "hint": "مبيعات التحويل — تصل إلى حسابنا البنكي",
    },
}


def _sales_between(request, date_from, date_to, sales_field, branch=None):
    """مجموع عمود واحد من المبيعات اليومية للورديات المغلقة، ضمن نطاق الفروع."""
    qs = scope_queryset(
        request,
        DailySale.objects.filter(date__gte=date_from, date__lte=date_to),
    )
    if branch:
        qs = qs.filter(branch_id=branch)
    return qs.aggregate(t=Sum(sales_field))["t"] or ZERO


def _received_between(request, date_from, date_to, branch=None, account=None):
    qs = scope_queryset(
        request,
        MachineCollection.objects.filter(date__gte=date_from, date__lte=date_to),
        "branch",
    )
    if branch:
        qs = qs.filter(branch_id=branch)
    if account:
        qs = qs.filter(account=account)
    return qs.aggregate(t=Sum("amount"))["t"] or ZERO


def _account_figures(request, start, end, branch, account):
    """(مبيعات، مستلَم، رصيد) لحساب واحد في فترة."""
    field = ACCOUNTS[account]["sales_field"]
    sales = _sales_between(request, start, end, field, branch)
    received = _received_between(request, start, end, branch, account)
    return sales, received, sales - received


def _month_range(year, month):
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    return start, end


def _shift_month(value, delta):
    month = value.month - 1 + delta
    year = value.year + month // 12
    month = month % 12 + 1
    return date(year, month, 1)


class MachineAccountView(APIView):
    """حسابات التسوية: مبيعات كل قناة − الدفعات المستلمة لها = الرصيد المتبقي.

    قناتان تُتابَعان: حساب الماكينة (البطاقة) وحساب البنك (التحويل)،
    مع إجمالي مجمّع يجمعهما.

    GET /api/machine-account/?date_from=..&date_to=..&branch=..&account=..
    """

    permission_section = "machine_account"

    def get(self, request):
        today = timezone.localdate()
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        branch = request.query_params.get("branch")
        # `account` اختياري: بلاه نعيد الحسابين، ومعاه نقصر على حساب واحد.
        wanted = request.query_params.get("account") or ""
        if wanted and wanted not in ACCOUNTS:
            return Response(
                {"detail": f"حساب غير معروف: {wanted}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        keys = [wanted] if wanted else list(ACCOUNTS)

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

        # الفترة المختارة
        totals = {}
        for key in keys:
            sales, received, balance = _account_figures(request, start, end, branch, key)
            totals[key] = {
                "label": ACCOUNTS[key]["label"],
                "hint": ACCOUNTS[key]["hint"],
                "sales": float(sales),
                "received": float(received),
                "balance": float(balance),
            }

        # الشهر الحالي
        m_start = today.replace(day=1)
        month = {}
        for key in keys:
            sales, received, balance = _account_figures(request, m_start, today, branch, key)
            month[key] = {
                "sales": float(sales),
                "received": float(received),
                "balance": float(balance),
            }

        # الاتجاه الشهري: شهور الفترة (بحد أقصى 24 شهراً للعرض).
        months = []
        cursor = date(start.year, start.month, 1)
        guard = 0
        while cursor <= end and guard < 24:
            ms, me = _month_range(cursor.year, cursor.month)
            actual_start = max(ms, start)
            actual_end = min(me, end)
            row = {"month": f"{cursor.year:04d}-{cursor.month:02d}", "accounts": {}}
            for key in keys:
                s, r, b = _account_figures(request, actual_start, actual_end, branch, key)
                row["accounts"][key] = {
                    "sales": float(s),
                    "received": float(r),
                    "balance": float(b),
                }
            months.append(row)
            cursor = _shift_month(cursor, 1)
            guard += 1

        recent = scope_queryset(
            request, MachineCollection.objects.select_related("branch").order_by("-date", "-id"),
            "branch",
        )
        if branch:
            recent = recent.filter(branch_id=branch)
        if wanted:
            recent = recent.filter(account=wanted)
        recent = recent[:20]

        # إجمالي مجمّع عبر كل الحسابات المعروضة
        combined = {
            "sales": sum(totals[k]["sales"] for k in keys),
            "received": sum(totals[k]["received"] for k in keys),
            "balance": sum(totals[k]["balance"] for k in keys),
        }

        return Response({
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "accounts": totals,
            "combined": combined,
            "month": month,
            "months": months,
            "recent_collections": MachineCollectionSerializer(recent, many=True).data,
        })


class MachineCollectionViewSet(viewsets.ModelViewSet):
    """دفعات التسويات المستلمة — «وصلني كذا»."""

    permission_section = "machine_account"
    queryset = MachineCollection.objects.select_related("branch").all()
    serializer_class = MachineCollectionSerializer
    search_fields = ["reference", "notes", "branch__name"]
    ordering_fields = ["date", "amount", "created_at", "account"]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        qs = scope_queryset(self.request, qs, "branch")
        branch = self.request.query_params.get("branch")
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        account = self.request.query_params.get("account")
        if branch:
            qs = qs.filter(branch_id=branch)
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)
        if account in dict(ACCOUNTS):
            qs = qs.filter(account=account)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user if self.request.user.is_authenticated else None)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({"detail": "تم حذف الدفعة"}, status=status.HTTP_200_OK)