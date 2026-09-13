from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    FabricRollViewSet,
    GoodsReceiptViewSet,
    StockAdjustmentViewSet,
    StockBalanceSetView,
    StockBalanceView,
    StockCountViewSet,
    StockMovementViewSet,
    StockOpeningViewSet,
    StockTransferViewSet,
    WarehouseViewSet,
)

router = DefaultRouter()
router.register("warehouses/rolls", FabricRollViewSet, basename="fabric-roll")
router.register("warehouses/receipts", GoodsReceiptViewSet, basename="goods-receipt")
router.register("warehouses/transfers", StockTransferViewSet, basename="stock-transfer")
router.register("warehouses/adjustments", StockAdjustmentViewSet, basename="stock-adjustment")
router.register("warehouses/counts", StockCountViewSet, basename="stock-count")
router.register("warehouses/openings", StockOpeningViewSet, basename="stock-opening")
router.register("warehouses/movements", StockMovementViewSet, basename="stock-movement")
router.register("warehouses", WarehouseViewSet, basename="warehouse")

urlpatterns = [
    path("warehouses/stock/set/", StockBalanceSetView.as_view(), name="stock-balance-set"),
    path("warehouses/stock/", StockBalanceView.as_view(), name="stock-balance"),
    path("", include(router.urls)),
]