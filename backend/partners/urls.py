from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import PartnerOperationViewSet, PartnerViewSet

router = DefaultRouter()
router.register("partners", PartnerViewSet, basename="partner")
router.register("partner-operations", PartnerOperationViewSet, basename="partner-operation")

urlpatterns = [
    path("", include(router.urls)),
]