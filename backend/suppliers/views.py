from decimal import Decimal

from django.conf import settings
from django.db.models import Count, F, Q, Sum, Window
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from warehouses.models import FabricRoll
from warehouses.services import create_purchase_receipts

from .models import Fabric, LedgerEntry, Supplier
from .serializers import (
    FabricSerializer,
    LedgerEntryCreateSerializer,
    LedgerEntrySerializer,
    SupplierSerializer,
)


class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.annotate(
        current_balance=Coalesce(Sum("ledger_entries__amount"), Decimal("0"))
    ).order_by("name")
    serializer_class = SupplierSerializer
    search_fields = ["name", "company_name", "city", "country", "phone", "email"]
    ordering_fields = ["name", "company_name", "city", "created_at"]

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        qs = self.get_queryset()
        total_suppliers = qs.count()
        active_count = qs.filter(is_active=True).count()

        entries = LedgerEntry.objects
        ledger_agg = entries.aggregate(
            purchases=Sum("amount", filter=Q(entry_type=LedgerEntry.EntryType.PURCHASE)),
            payments=Sum("amount", filter=Q(entry_type=LedgerEntry.EntryType.PAYMENT)),
            returns=Sum("amount", filter=Q(entry_type=LedgerEntry.EntryType.RETURN)),
        )
        counts = {
            r["entry_type"]: r["n"]
            for r in entries.values("entry_type").annotate(n=Count("id"))
        }

        owing = list(qs.filter(current_balance__gt=0).order_by("-current_balance"))
        outstanding = sum((s.current_balance or Decimal("0")) for s in owing)

        top = [
            {
                "id": s.id,
                "name": s.name,
                "company_name": s.company_name,
                "balance": float(s.current_balance or 0),
            }
            for s in owing[:5]
        ]

        return Response({
            "total_suppliers": total_suppliers,
            "active_count": active_count,
            "total_purchases": abs(float(ledger_agg["purchases"] or 0)),
            "purchases_count": counts.get(LedgerEntry.EntryType.PURCHASE, 0),
            "total_payments": abs(float(ledger_agg["payments"] or 0)),
            "payments_count": counts.get(LedgerEntry.EntryType.PAYMENT, 0),
            "total_returns": abs(float(ledger_agg["returns"] or 0)),
            "returns_count": counts.get(LedgerEntry.EntryType.RETURN, 0),
            "outstanding_debit": float(outstanding),
            "owing_count": len(owing),
            "top_suppliers": top,
        })

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(
            {"detail": settings.API_MESSAGES["deleted"]},
            status=status.HTTP_200_OK,
        )


class FabricViewSet(viewsets.ModelViewSet):
    serializer_class = FabricSerializer
    search_fields = ["name", "code", "barcode", "fabric_type", "color", "origin"]
    ordering_fields = ["name", "code", "sale_price_yard", "created_at"]

    def get_queryset(self):
        available = Q(rolls__status=FabricRoll.Status.AVAILABLE)
        return (
            Fabric.objects.all()
            .select_related("supplier")
            .annotate(
                total_rolls=Count("rolls", filter=available),
                stock_yards=Coalesce(
                    Sum("rolls__remaining_yards", filter=available), Decimal("0")
                ),
                stock_cost_value=Coalesce(
                    Sum(
                        F("rolls__remaining_yards") * F("rolls__unit_cost"),
                        filter=available,
                    ),
                    Decimal("0"),
                ),
            )
            .order_by("name")
        )

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        qs = self.get_queryset()
        agg = qs.aggregate(
            total_rolls=Count(
                "rolls", filter=Q(rolls__status=FabricRoll.Status.AVAILABLE)
            ),
            stock_yards=Coalesce(
                Sum(
                    "rolls__remaining_yards",
                    filter=Q(rolls__status=FabricRoll.Status.AVAILABLE),
                ),
                Decimal("0"),
            ),
        )
        retail_value = sum(
            (it.stock_yards or Decimal("0")) * (it.sale_price_yard or Decimal("0"))
            for it in qs
        )
        cost_value = sum(it.stock_cost_value or Decimal("0") for it in qs)
        low_stock_count = 0
        for it in qs:
            min_stock = it.min_stock or Decimal("0")
            if min_stock > 0 and (it.stock_yards or Decimal("0")) < min_stock:
                low_stock_count += 1
        return Response({
            "fabric_count": qs.count(),
            "active_count": qs.filter(is_active=True).count(),
            "low_stock_count": low_stock_count,
            "total_rolls": agg["total_rolls"],
            "total_stock_yards": float(agg["stock_yards"]),
            "inventory_cost_value": float(cost_value),
            "inventory_retail_value": float(retail_value),
        })

    def list(self, request, *args, **kwargs):
        export = request.query_params.get("export") == "xlsx"
        if export:
            qs = self.filter_queryset(self.get_queryset())
            headers = [
                "اسم القماش", "الكود", "الباركود", "النوع", "اللون", "الوحدة",
                "تكلفة الشراء", "سعر بيع الياردة", "سعر بيع اللفة",
                "حد أدنى ياردة", "حد أدنى لفة", "المورد",
                "لفات متاحة", "ياردات متاحة", "قيمة التكلفة", "الحد الأدنى للمخزون",
                "الحالة",
            ]
            rows = [
                [
                    f.name,
                    f.code,
                    f.barcode,
                    f.fabric_type,
                    f.color,
                    f.get_unit_display() if hasattr(f, "get_unit_display") else f.unit,
                    float(f.purchase_price or 0),
                    float(f.sale_price_yard or 0),
                    float(f.sale_price_roll) if f.sale_price_roll is not None else float((f.sale_price_yard or 0) * (f.yards_per_roll or 0)),
                    float(f.min_sale_yard or 0),
                    float(f.min_sale_roll) if f.min_sale_roll is not None else float((f.min_sale_yard or 0) * (f.yards_per_roll or 0)),
                    f.supplier.name if f.supplier else "",
                    f.total_rolls if hasattr(f, "total_rolls") else 0,
                    float(f.stock_yards or 0),
                    float(f.stock_cost_value or 0),
                    float(f.min_stock or 0),
                    "نشط" if f.is_active else "غير نشط",
                ]
                for f in qs
            ]
            from reports.views import _export_generic_to_xlsx, _xlsx_response

            wb = _export_generic_to_xlsx("الأقمشة", headers, rows)
            if wb is not None:
                return _xlsx_response(wb, "الأقمشة")
        return super().list(request, *args, **kwargs)

    @action(detail=True, methods=["get"], url_path="stock")
    def stock(self, request, pk=None):
        fabric = self.get_object()
        rows = (
            FabricRoll.objects.filter(
                fabric=fabric, status=FabricRoll.Status.AVAILABLE
            )
            .values("warehouse_id", "warehouse__name")
            .annotate(
                rolls=Count("id"),
                yards=Coalesce(Sum("remaining_yards"), Decimal("0")),
                cost_value=Coalesce(
                    Sum(F("remaining_yards") * F("unit_cost")), Decimal("0")
                ),
            )
            .order_by("warehouse__name")
        )
        items = [
            {
                "warehouse": r["warehouse_id"],
                "warehouse_name": r["warehouse__name"],
                "rolls": r["rolls"],
                "yards": r["yards"],
                "cost_value": r["cost_value"],
            }
            for r in rows
        ]
        return Response({
            "fabric": {
                "id": fabric.id,
                "name": fabric.name,
                "code": fabric.code,
                "unit": fabric.unit,
            },
            "items": items,
            "totals": {
                "rolls": sum(r["rolls"] for r in rows),
                "yards": float(sum(r["yards"] for r in rows)),
                "cost_value": float(sum(r["cost_value"] for r in rows)),
            },
        })

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(
            {"detail": settings.API_MESSAGES["deleted"]},
            status=status.HTTP_200_OK,
        )


class SupplierLedgerViewSet(viewsets.GenericViewSet):
    def _annotated_ledger(self, supplier):
        return (
            LedgerEntry.objects.filter(supplier=supplier)
            .select_related("supplier", "warehouse", "branch")
            .prefetch_related("items__fabric", "goods_receipts")
            .annotate(
                running_balance=Window(
                    expression=Sum("amount"),
                    order_by=[F("date"), F("created_at")],
                )
            )
            .order_by("date", "created_at")
        )

    def list(self, request, pk=None):
        supplier = get_object_or_404(Supplier, pk=pk)
        qs = self._annotated_ledger(supplier)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = LedgerEntrySerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = LedgerEntrySerializer(qs, many=True)
        return Response(serializer.data)

    def summary(self, request, pk=None):
        supplier = get_object_or_404(Supplier, pk=pk)
        qs = LedgerEntry.objects.filter(supplier=supplier)
        agg = qs.aggregate(
            opening_balance=Sum(
                "amount", filter=Q(entry_type=LedgerEntry.EntryType.OPENING)
            ),
            total_purchases=Sum(
                "amount", filter=Q(entry_type=LedgerEntry.EntryType.PURCHASE)
            ),
            total_payments=Sum(
                "amount", filter=Q(entry_type=LedgerEntry.EntryType.PAYMENT)
            ),
            total_returns=Sum(
                "amount", filter=Q(entry_type=LedgerEntry.EntryType.RETURN)
            ),
            balance=Sum("amount"),
        )
        counts = {
            r["entry_type"]: r["n"]
            for r in qs.values("entry_type").annotate(n=Count("id"))
        }
        return Response({
            "opening_balance": float(agg["opening_balance"] or 0),
            "total_purchases": float(agg["total_purchases"] or 0),
            "total_payments": abs(float(agg["total_payments"] or 0)),
            "total_returns": abs(float(agg["total_returns"] or 0)),
            "balance": float(agg["balance"] or 0),
            "purchases_count": counts.get(LedgerEntry.EntryType.PURCHASE, 0),
            "payments_count": counts.get(LedgerEntry.EntryType.PAYMENT, 0),
            "returns_count": counts.get(LedgerEntry.EntryType.RETURN, 0),
        })

    def create(self, request, pk=None):
        supplier = get_object_or_404(Supplier, pk=pk)
        serializer = LedgerEntryCreateSerializer(
            data=request.data, context={"supplier": supplier}
        )
        serializer.is_valid(raise_exception=True)
        created = serializer.save()
        try:
            from accounting.services import post_supplier_entry
            post_supplier_entry(created)
            if (
                created.entry_type == LedgerEntry.EntryType.PURCHASE
                and created.receipt_no
                and request.data.get("payment_amount")
            ):
                payment = (
                    LedgerEntry.objects.filter(
                        supplier=supplier,
                        entry_type=LedgerEntry.EntryType.PAYMENT,
                        receipt_no=created.receipt_no,
                        date=created.date,
                    )
                    .order_by("-created_at")
                    .first()
                )
                if payment:
                    post_supplier_entry(payment)
        except Exception:
            pass
        entry = next(
            (row for row in self._annotated_ledger(supplier) if row.pk == created.pk),
            created,
        )
        return Response(
            LedgerEntrySerializer(entry).data,
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request, pk=None, entry_pk=None):
        supplier = get_object_or_404(Supplier, pk=pk)
        entry = get_object_or_404(LedgerEntry, pk=entry_pk, supplier=supplier)
        try:
            from accounting.models import JournalEntry
            from accounting.services import unpost_source

            unpost_source(JournalEntry.Source.PURCHASE, entry.pk)
            if (
                entry.entry_type == LedgerEntry.EntryType.PURCHASE
                and entry.receipt_no
            ):
                payment = LedgerEntry.objects.filter(
                    supplier=supplier,
                    entry_type=LedgerEntry.EntryType.PAYMENT,
                    receipt_no=entry.receipt_no,
                    date=entry.date,
                ).first()
                if payment:
                    unpost_source(JournalEntry.Source.PURCHASE, payment.pk)
        except Exception:
            pass
        entry.delete()
        return Response(
            {"detail": settings.API_MESSAGES["deleted"]},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"])
    def receive(self, request, pk=None, entry_pk=None):
        supplier = get_object_or_404(Supplier, pk=pk)
        entry = get_object_or_404(
            LedgerEntry,
            pk=entry_pk,
            supplier=supplier,
            entry_type=LedgerEntry.EntryType.PURCHASE,
        )
        entry_dest = entry.warehouse_id or entry.branch_id
        item_dest = entry.items.filter(
            Q(warehouse_id__isnull=False) | Q(branch_id__isnull=False)
        ).exists()
        if not entry_dest and not item_dest:
            return Response(
                {"detail": "حدد وجهة التوريد (مخزن أو فرع) لقيد الشراء أولاً"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if entry.goods_receipts.exists():
            return Response(
                {"detail": "بضاعة قيد الشراء مُستلمة بالفعل"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            create_purchase_receipts(entry, date=entry.date)
        except serializers.ValidationError as exc:
            return Response({"detail": str(exc.detail)}, status=status.HTTP_400_BAD_REQUEST)
        entry_row = next(
            (row for row in self._annotated_ledger(supplier) if row.pk == entry.pk),
            entry,
        )
        return Response(LedgerEntrySerializer(entry_row).data)