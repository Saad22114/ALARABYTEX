from rest_framework.routers import DefaultRouter

from .views import EmployeeViewSet, SaleSessionViewSet

router = DefaultRouter()
router.register("employees", EmployeeViewSet, basename="employee")
router.register("sale-sessions", SaleSessionViewSet, basename="sale-session")

urlpatterns = router.urls