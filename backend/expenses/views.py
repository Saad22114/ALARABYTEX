from rest_framework import viewsets, status
from rest_framework.response import Response
from django.conf import settings
from datetime import date
from core.branch_scope import scope_queryset
from .models import Expense, ExpenseBudget, ExpenseCategory
from .serializers import (
    ExpenseBudgetSerializer,
    ExpenseCategorySerializer,
    ExpenseReadSerializer,
    ExpenseWriteSerializer,
)


class ExpenseCategoryViewSet(viewsets.ModelViewSet):
    permission_section = "@themes"
    queryset = ExpenseCategory.objects.all()
    serializer_class = ExpenseCategorySerializer
    search_fields = ["name", "code"]
    ordering_fields = ["name", "created_at"]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_system:
            return Response(
                {"detail": settings.API_MESSAGES["system_category"]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if instance.expenses.exists():
            return Response(
                {"detail": settings.API_MESSAGES["category_in_use"]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        self.perform_destroy(instance)
        return Response(
            {"detail": settings.API_MESSAGES["deleted"]},
            status=status.HTTP_200_OK,
        )


class ExpenseViewSet(viewsets.ModelViewSet):
    permission_section = "expenses"
    queryset = Expense.objects.select_related("branch", "category").all()
    search_fields = ["branch__name", "category__name", "description", "notes"]
    ordering_fields = ["date", "amount", "created_at"]

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return ExpenseReadSerializer
        return ExpenseWriteSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        qs = scope_queryset(self.request, qs)
        branch = self.request.query_params.get("branch")
        category = self.request.query_params.get("category")
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        if branch:
            qs = qs.filter(branch_id=branch)
        if category:
            qs = qs.filter(category_id=category)
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)
        return qs

    def perform_create(self, serializer):
        expense = serializer.save()
        try:
            from accounting.services import post_expense
            post_expense(expense)
        except Exception:
            pass

    def perform_update(self, serializer):
        expense = serializer.save()
        try:
            from accounting.services import post_expense
            post_expense(expense)
        except Exception:
            pass

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            from accounting.models import JournalEntry
            from accounting.services import unpost_source
            unpost_source(JournalEntry.Source.EXPENSE, instance.pk)
        except Exception:
            pass
        self.perform_destroy(instance)
        return Response(
            {"detail": settings.API_MESSAGES["deleted"]},
            status=status.HTTP_200_OK,
        )


def _normalize_month(value):
    """تحويل YYYY-MM أو تاريخ كامل إلى أول يوم من الشهر."""
    try:
        if len(str(value)) == 7:
            return date.fromisoformat(f"{value}-01")
        return date.fromisoformat(str(value)).replace(day=1)
    except ValueError:
        return None


class ExpenseBudgetViewSet(viewsets.ModelViewSet):
    permission_section = "expenses"
    queryset = ExpenseBudget.objects.select_related("branch", "category").all()
    serializer_class = ExpenseBudgetSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        qs = scope_queryset(self.request, qs)
        branch = self.request.query_params.get("branch")
        category = self.request.query_params.get("category")
        month = self.request.query_params.get("month")
        if branch:
            qs = qs.filter(branch_id=branch)
        if category:
            qs = qs.filter(category_id=category)
        normalized = _normalize_month(month) if month else None
        if normalized:
            qs = qs.filter(month=normalized)
        return qs

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(
            {"detail": settings.API_MESSAGES["deleted"]},
            status=status.HTTP_200_OK,
        )
