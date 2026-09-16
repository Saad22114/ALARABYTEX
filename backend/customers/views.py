from django.conf import settings
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Customer
from .serializers import CustomerSerializer


class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.select_related("branch").order_by("name")
    serializer_class = CustomerSerializer
    search_fields = ["name", "phone", "email", "address"]
    ordering_fields = ["name", "phone", "created_at", "is_active"]

    def get_queryset(self):
        qs = super().get_queryset()
        branch = self.request.query_params.get("branch")
        if branch:
            qs = qs.filter(branch_id=branch)
        is_active = self.request.query_params.get("is_active")
        if is_active in ("true", "1"):
            qs = qs.filter(is_active=True)
        elif is_active in ("false", "0"):
            qs = qs.filter(is_active=False)
        return qs

    @action(detail=False, methods=["get"], url_path="lookup")
    def lookup(self, request):
        phone = (request.query_params.get("phone") or "").strip()
        if not phone:
            return Response({"found": False, "customer": None})
        customer = Customer.objects.filter(phone=phone).first()
        if customer is None:
            return Response({"found": False, "customer": None})
        return Response({"found": True, "customer": CustomerSerializer(customer).data})

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(
            {"detail": settings.API_MESSAGES["deleted"]},
            status=status.HTTP_200_OK,
        )