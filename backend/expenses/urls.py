from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ExpenseBudgetViewSet, ExpenseViewSet, ExpenseCategoryViewSet

router = DefaultRouter()
router.register("expenses", ExpenseViewSet, basename="expense")
router.register("expense-categories", ExpenseCategoryViewSet, basename="expense-category")
router.register("expense-budgets", ExpenseBudgetViewSet, basename="expense-budget")

urlpatterns = [
    path("", include(router.urls)),
]
