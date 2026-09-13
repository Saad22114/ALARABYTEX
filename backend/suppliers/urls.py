from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FabricViewSet, SupplierLedgerViewSet, SupplierViewSet

router = DefaultRouter()
router.register("suppliers", SupplierViewSet, basename="supplier")
router.register("fabrics", FabricViewSet, basename="fabric")

urlpatterns = [
    path("", include(router.urls)),
    path(
        "suppliers/<int:pk>/summary/",
        SupplierLedgerViewSet.as_view({"get": "summary"}),
        name="supplier-ledger-summary",
    ),
    path(
        "suppliers/<int:pk>/ledger/",
        SupplierLedgerViewSet.as_view({"get": "list", "post": "create"}),
        name="supplier-ledger",
    ),
    path(
        "suppliers/<int:pk>/ledger/<int:entry_pk>/",
        SupplierLedgerViewSet.as_view({"delete": "destroy"}),
        name="supplier-ledger-entry",
    ),
    path(
        "suppliers/<int:pk>/ledger/<int:entry_pk>/receive/",
        SupplierLedgerViewSet.as_view({"post": "receive"}),
        name="supplier-ledger-receive",
    ),
]