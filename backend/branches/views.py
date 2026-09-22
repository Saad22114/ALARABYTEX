from rest_framework import viewsets, status
from rest_framework.response import Response
from django.conf import settings
from core.branch_scope import scope_queryset
from .models import Branch, FabricBranchPrice
from .serializers import BranchSerializer, FabricBranchPriceSerializer


class BranchViewSet(viewsets.ModelViewSet):
    permission_section = "branches"
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    search_fields = ["name", "code", "city", "phone"]
    ordering_fields = ["name", "code", "created_at"]

    def get_queryset(self):
        return scope_queryset(self.request, super().get_queryset(), branch_field="id")

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.daily_sales.exists() or instance.expenses.exists():
            return Response(
                {"detail": settings.API_MESSAGES["branch_in_use"]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        self.perform_destroy(instance)
        return Response(
            {"detail": settings.API_MESSAGES["deleted"]},
            status=status.HTTP_200_OK,
        )


class FabricBranchPriceViewSet(viewsets.ModelViewSet):
    permission_section = "branches"
    serializer_class = FabricBranchPriceSerializer
    ordering_fields = ["fabric__name", "sale_price_yard", "created_at"]
    ordering = ["fabric__name"]

    def get_queryset(self):
        qs = FabricBranchPrice.objects.select_related("branch", "fabric").all()
        qs = scope_queryset(self.request, qs)
        branch = self.request.query_params.get("branch")
        fabric = self.request.query_params.get("fabric")
        if branch:
            qs = qs.filter(branch_id=branch)
        if fabric:
            qs = qs.filter(fabric_id=fabric)
        return qs
