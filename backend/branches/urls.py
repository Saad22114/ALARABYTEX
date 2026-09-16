from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BranchViewSet, FabricBranchPriceViewSet

router = DefaultRouter()
router.register("branches", BranchViewSet, basename="branch")
router.register("branch-prices", FabricBranchPriceViewSet, basename="branch-price")

urlpatterns = [
    path("", include(router.urls)),
]
