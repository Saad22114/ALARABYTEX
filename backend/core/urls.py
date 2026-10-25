from django.urls import path

from . import views
from sale_sessions.notification_views import NotificationReadView, NotificationsView

urlpatterns = [
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    path("auth/me/", views.MeView.as_view(), name="me"),
    path("auth/change-password/", views.ChangePasswordView.as_view(), name="change-password"),
    path("account/avatar/", views.AccountAvatarView.as_view(), name="account-avatar"),
    path("account/profile/", views.EmployeeProfileView.as_view(), name="account-profile"),
    path("notifications/", NotificationsView.as_view(), name="notifications"),
    path("notifications/read-all/", NotificationReadView.as_view(), name="notifications-read-all"),
    path("notifications/<int:pk>/read/", NotificationReadView.as_view(), name="notification-read"),
]
