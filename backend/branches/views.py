from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.conf import settings
from decimal import Decimal
from suppliers.models import Fabric
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

    def list(self, request, *args, **kwargs):
        """القائمة تعرض الفروع النشطة فقط؛ يُمرَّر ``include_inactive=1`` لعرض الموقوفة (صفحة الإدارة)."""
        queryset = self.filter_queryset(self.get_queryset())
        if not request.query_params.get("include_inactive"):
            queryset = queryset.filter(is_active=True)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

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

    @action(detail=False, methods=["post"], url_path="bulk")
    def bulk_upsert(self, request):
        fabric_id = request.data.get("fabric")
        prices = request.data.get("prices", [])
        fabric = get_object_or_404(Fabric, id=fabric_id)
        created = updated = 0
        errors = []

        with transaction.atomic():
            for item in prices:
                branch_id = item.get("branch")
                branch = get_object_or_404(Branch, id=branch_id)
                sale_yard = item.get("sale_price_yard")
                piece_price = item.get("piece_price")
                if (sale_yard in (None, "", 0)) and piece_price not in (None, "", 0):
                    # سعر القطعة يحدّد سعر بيع الياردة تلقائياً (قطعة ÷ 3.5)
                    sale_yard = (
                        Decimal(str(piece_price)) / Decimal("3.5")
                    ).quantize(Decimal("0.001"))
                obj, was_created = FabricBranchPrice.objects.update_or_create(
                    branch=branch, fabric=fabric,
                    defaults={
                        "sale_price_yard": sale_yard or 0,
                        "sale_price_roll": item.get("sale_price_roll"),
                        "min_sale_yard": item.get("min_sale_yard", 0),
                        "min_sale_roll": item.get("min_sale_roll"),
                        "piece_price": piece_price,
                    },
                )
                if was_created:
                    created += 1
                else:
                    updated += 1
        return Response({"created": created, "updated": updated, "errors": errors})
