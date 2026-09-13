from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DailySaleViewSet, SaleStockView, SalesByEmployeeView

router = DefaultRouter()
router.register("sales", DailySaleViewSet, basename="daily-sale")

urlpatterns = [
    path("sales/stock/", SaleStockView.as_view(), name="sale-stock"),
    path("sales/by-employee/", SalesByEmployeeView.as_view(), name="sales-by-employee"),
    path("", include(router.urls)),
]
