from django.urls import path

from .views import AppSettingsView, BackupView, RestoreView, ResetView

urlpatterns = [
    path("", AppSettingsView.as_view(), name="app-settings"),
    path("backup/", BackupView.as_view(), name="app-settings-backup"),
    path("restore/", RestoreView.as_view(), name="app-settings-restore"),
    path("reset/", ResetView.as_view(), name="app-settings-reset"),
]