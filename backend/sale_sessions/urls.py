from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import EmployeeViewSet, SaleSessionViewSet, SectionsView

router = DefaultRouter()
router.register("employees", EmployeeViewSet, basename="employee")
router.register("sale-sessions", SaleSessionViewSet, basename="sale-session")

urlpatterns = [
    path("sections/", SectionsView.as_view(), name="sections"),
] + router.urls