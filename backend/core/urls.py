from django.urls import path

from . import views

urlpatterns = [
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    path("auth/me/", views.MeView.as_view(), name="me"),
    path("account/avatar/", views.AccountAvatarView.as_view(), name="account-avatar"),
    path("account/profile/", views.EmployeeProfileView.as_view(), name="account-profile"),
]