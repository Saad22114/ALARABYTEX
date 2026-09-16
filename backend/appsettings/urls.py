from django.urls import path

from .views import AppSettingsView, BackupView, LogoUploadView, RestoreView, ResetView

urlpatterns = [
    path("", AppSettingsView.as_view(), name="app-settings"),
    path("logo/", LogoUploadView.as_view(), name="app-settings-logo"),
    path("backup/", BackupView.as_view(), name="app-settings-backup"),
    path("restore/", RestoreView.as_view(), name="app-settings-restore"),
    path("reset/", ResetView.as_view(), name="app-settings-reset"),
]