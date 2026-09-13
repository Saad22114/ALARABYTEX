from rest_framework import viewsets, status
from rest_framework.response import Response
from django.conf import settings
from .models import Expense, ExpenseCategory
from .serializers import (
    ExpenseCategorySerializer,
    ExpenseReadSerializer,
    ExpenseWriteSerializer,
)


class ExpenseCategoryViewSet(viewsets.ModelViewSet):
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
    queryset = Expense.objects.select_related("branch", "category").all()
    search_fields = ["branch__name", "category__name", "description", "notes"]
    ordering_fields = ["date", "amount", "created_at"]

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return ExpenseReadSerializer
        return ExpenseWriteSerializer

    def get_queryset(self):
        qs = super().get_queryset()
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

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(
            {"detail": settings.API_MESSAGES["deleted"]},
            status=status.HTTP_200_OK,
        )
