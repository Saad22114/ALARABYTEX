from django.urls import path

from .alerts_views import AlertsCenterView
from .views import DashboardActivityView, DashboardAlertsView, DashboardSummaryView

urlpatterns = [
    path("summary/", DashboardSummaryView.as_view(), name="dashboard-summary"),
    path("alerts/", DashboardAlertsView.as_view(), name="dashboard-alerts"),
    path("alerts-center/", AlertsCenterView.as_view(), name="alerts-center"),
    path("activity/", DashboardActivityView.as_view(), name="dashboard-activity"),
]
