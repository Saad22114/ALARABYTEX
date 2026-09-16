from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("accounts", views.AccountViewSet, basename="account")
router.register("journal", views.JournalEntryViewSet, basename="journal-entry")

urlpatterns = [
    path("reports/trial-balance/", views.TrialBalanceView.as_view()),
    path("reports/income-statement/", views.IncomeStatementView.as_view()),
    path("reports/balance-sheet/", views.BalanceSheetView.as_view()),
    path("reports/cash-flow/", views.CashFlowView.as_view()),
    path("reports/cashbox/", views.CashBoxView.as_view()),
    path("close-period/", views.ClosePeriodView.as_view()),
] + router.urls