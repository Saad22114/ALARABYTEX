from django.urls import path

from .views import (
    AppSettingsPublicView,
    AppSettingsView,
    AutoBackupDownloadView,
    AutoBackupView,
    BackupView,
    LogoFileView,
    LogoUploadView,
    RestoreView,
    ResetView,
    ThemesControlView,
)

urlpatterns = [
    path("", AppSettingsView.as_view(), name="app-settings"),
    path("public/", AppSettingsPublicView.as_view(), name="app-settings-public"),
    path("themes-control/", ThemesControlView.as_view(), name="app-settings-themes-control"),
    path("logo/", LogoUploadView.as_view(), name="app-settings-logo"),
    path("logo-file/", LogoFileView.as_view(), name="app-settings-logo-file"),
    path("backup/", BackupView.as_view(), name="app-settings-backup"),
    path("auto-backup/", AutoBackupView.as_view(), name="app-settings-auto-backup"),
    path("auto-backup/<str:name>/", AutoBackupDownloadView.as_view(), name="app-settings-auto-backup-download"),
    path("restore/", RestoreView.as_view(), name="app-settings-restore"),
    path("reset/", ResetView.as_view(), name="app-settings-reset"),
]