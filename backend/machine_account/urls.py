from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import MachineAccountView, MachineCollectionViewSet

router = DefaultRouter()
router.register("collections", MachineCollectionViewSet, basename="machine-collection")

urlpatterns = [
    path("", MachineAccountView.as_view(), name="machine-account"),
    path("", include(router.urls)),
]