from django.urls import path
from .views import DashboardAlertsView, DashboardSummaryView

urlpatterns = [
    path("summary/", DashboardSummaryView.as_view(), name="dashboard-summary"),
    path("alerts/", DashboardAlertsView.as_view(), name="dashboard-alerts"),
]