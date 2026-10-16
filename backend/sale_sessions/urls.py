from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import EmployeeViewSet, PermissionTemplateViewSet, SaleSessionViewSet, SectionsView

router = DefaultRouter()
router.register("employees", EmployeeViewSet, basename="employee")
router.register("permission-templates", PermissionTemplateViewSet, basename="permission-template")
router.register("sale-sessions", SaleSessionViewSet, basename="sale-session")

urlpatterns = [
    path("sections/", SectionsView.as_view(), name="sections"),
] + router.urls
