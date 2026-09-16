from datetime import date

from django.conf import settings
from django.db.models import Count
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Account, JournalEntry
from .serializers import (
    AccountSerializer,
    JournalEntrySerializer,
    ClosedPeriodSerializer,
)
from .services import (
    balance_sheet,
    cash_box,
    cash_flow,
    close_period,
    income_statement,
    trial_balance,
)
from .models import ClosedPeriod


class AccountViewSet(viewsets.ModelViewSet):
    queryset = Account.objects.select_related("parent").all()
    serializer_class = AccountSerializer
    search_fields = ["code", "name"]
    ordering_fields = ["code", "name", "created_at"]

    def get_queryset(self):
        qs = super().get_queryset()
        active = self.request.query_params.get("active")
        if active is not None:
            qs = qs.filter(is_active=active.lower() in ("1", "true"))
        return qs.annotate(children_count=Count("children")).order_by("code")

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.journal_lines.exists():
            return Response(
                {"detail": "لا يمكن حذف حساب عليه حركات محاسبية"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if instance.children.exists():
            return Response(
                {"detail": "لا يمكن حذف حساب له حسابات فرعية"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if instance.is_system:
            return Response(
                {"detail": "لا يمكن حذف حساب نظامي"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        self.perform_destroy(instance)
        return Response({"detail": settings.API_MESSAGES["deleted"]}, status=status.HTTP_200_OK)


class JournalEntryViewSet(viewsets.ModelViewSet):
    queryset = JournalEntry.objects.select_related("created_by").prefetch_related("lines__account").all()
    serializer_class = JournalEntrySerializer
    http_method_names = ["get", "post", "delete", "head", "options"]
    ordering_fields = ["date", "number", "created_at"]

    def get_queryset(self):
        qs = super().get_queryset()
        source = self.request.query_params.get("source")
        if source:
            qs = qs.filter(source=source)
        date_from = self.request.query_params.get("from")
        if date_from:
            qs = qs.filter(date__gte=date_from)
        date_to = self.request.query_params.get("to")
        if date_to:
            qs = qs.filter(date__lte=date_to)
        account = self.request.query_params.get("account")
        if account:
            qs = qs.filter(lines__account_id=account).distinct()
        return qs

    def create(self, request, *args, **kwargs):
        data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
        if not data.get("source"):
            data["source"] = JournalEntry.Source.MANUAL
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.source != JournalEntry.Source.MANUAL:
            return Response(
                {"detail": "القيد تلقائي المصدر — يُلغى من مصدره الأصلي"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        self.perform_destroy(instance)
        return Response({"detail": settings.API_MESSAGES["deleted"]}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="reverse")
    def reverse(self, request, pk=None):
        instance = self.get_object()
        if instance.source != JournalEntry.Source.MANUAL:
            return Response(
                {"detail": "لا يمكن عكس قيد تلقائي المصدر"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from django.utils import timezone
        instance.reversed_at = timezone.now()
        instance.save(update_fields=["reversed_at"])
        return Response({"detail": "تم عكس القيد", "id": instance.pk}, status=status.HTTP_200_OK)


class ClosePeriodView(APIView):
    """إغلاق الفترة: تحويل نتائج الدخل إلى الأرباح المحتجزة."""

    def get(self, request):
        periods = ClosedPeriod.objects.all()
        return Response(ClosedPeriodSerializer(periods, many=True).data)

    def post(self, request):
        period_end = request.data.get("period_end")
        description = request.data.get("description", "")
        try:
            result = close_period(
                date.fromisoformat(str(period_end)),
                description=description,
            )
        except (ValueError, KeyError) as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(result, status=status.HTTP_201_CREATED)


class TrialBalanceView(APIView):
    def get(self, request):
        date_to = request.query_params.get("to") or request.query_params.get("date")
        show_zero = request.query_params.get("show_zero") in ("1", "true")
        if date_to:
            date_to = date.fromisoformat(str(date_to))
        return Response(trial_balance(date_to, show_zero=show_zero))


class IncomeStatementView(APIView):
    def get(self, request):
        df = request.query_params.get("from")
        dt = request.query_params.get("to")
        return Response(
            income_statement(
                date.fromisoformat(str(df)) if df else None,
                date.fromisoformat(str(dt)) if dt else None,
            )
        )


class BalanceSheetView(APIView):
    def get(self, request):
        dt = request.query_params.get("to") or request.query_params.get("date")
        return Response(balance_sheet(date.fromisoformat(str(dt)) if dt else None))


class CashFlowView(APIView):
    def get(self, request):
        df = request.query_params.get("from")
        dt = request.query_params.get("to")
        return Response(
            cash_flow(
                date.fromisoformat(str(df)) if df else None,
                date.fromisoformat(str(dt)) if dt else None,
            )
        )


class CashBoxView(APIView):
    def get(self, request):
        d = request.query_params.get("date")
        return Response(cash_box(date.fromisoformat(str(d)) if d else None))