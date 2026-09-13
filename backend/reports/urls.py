from django.urls import path
from .views import (
    BranchReportView,
    CogsReportView,
    ExpensesReportView,
    InventoryMovementsReportView,
    InventoryReportView,
    JournalReportView,
    NetDailyReportView,
    ProfitLossReportView,
    SalesReportView,
    SupplierReportView,
)

urlpatterns = [
    path("sales/", SalesReportView.as_view(), name="report-sales"),
    path("expenses/", ExpensesReportView.as_view(), name="report-expenses"),
    path("net-daily/", NetDailyReportView.as_view(), name="report-net-daily"),
    path("suppliers/", SupplierReportView.as_view(), name="report-suppliers"),
    path("branches/", BranchReportView.as_view(), name="report-branches"),
    path("inventory/", InventoryReportView.as_view(), name="report-inventory"),
    path("inventory-movements/", InventoryMovementsReportView.as_view(), name="report-inventory-movements"),
    path("cogs/", CogsReportView.as_view(), name="report-cogs"),
    path("profit-loss/", ProfitLossReportView.as_view(), name="report-profit-loss"),
    path("journal/", JournalReportView.as_view(), name="report-journal"),
]