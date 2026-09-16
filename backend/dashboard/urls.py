from django.urls import path
from .views import DashboardActivityView, DashboardAlertsView, DashboardSummaryView

urlpatterns = [
    path("summary/", DashboardSummaryView.as_view(), name="dashboard-summary"),
    path("alerts/", DashboardAlertsView.as_view(), name="dashboard-alerts"),
    path("activity/", DashboardActivityView.as_view(), name="dashboard-activity"),
]