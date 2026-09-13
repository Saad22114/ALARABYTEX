from django.conf import settings
from django.db.models import Count, F, Sum
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from warehouses.models import FabricRoll, Warehouse

from .models import DailySale
from .serializers import DailySaleReadSerializer, DailySaleWriteSerializer


class DailySaleViewSet(viewsets.ModelViewSet):
    queryset = DailySale.objects.select_related("branch", "employee").prefetch_related("sale_items__fabric").all()
    search_fields = ["branch__name", "notes", "employee__name"]
    ordering_fields = ["date", "total_sales", "created_at"]

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return DailySaleReadSerializer
        return DailySaleWriteSerializer

    def list(self, request, *args, **kwargs):
        export = request.query_params.get("export") == "xlsx"
        if export:
            qs = self.filter_queryset(self.get_queryset())
            headers = [
                "التاريخ", "الفرع", "الموظف", "الأصناف",
                "إجمالي المبيعات", "النقدي", "التحويل", "البطاقة", "أخرى",
                "إجمالي الدفع", "الحالة",
            ]
            rows = []
            for s in qs:
                items_txt = " | ".join(
                    f"{it.fabric.name}: {it.yards}" for it in s.sale_items.all()
                )
                rows.append([
                    str(s.date),
                    s.branch.name,
                    s.employee.name if s.employee_id else "",
                    items_txt,
                    float(s.total_sales),
                    float(s.cash_amount),
                    float(s.transfer_amount),
                    float(s.card_amount),
                    float(s.other_amount),
                    float(s.payment_total),
                    "متوازن" if s.is_balanced else "غير متوازن",
                ])
            from reports.views import _export_generic_to_xlsx, _xlsx_response
            wb = _export_generic_to_xlsx("المبيعات", headers, rows)
            if wb is not None:
                return _xlsx_response(wb, "المبيعات")
        return super().list(request, *args, **kwargs)

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        qs = self.filter_queryset(self.get_queryset())
        agg = qs.aggregate(
            total=Sum("total_sales"),
            cash=Sum("cash_amount"),
            transfer=Sum("transfer_amount"),
            card=Sum("card_amount"),
            other=Sum("other_amount"),
            sales_count=Count("id"),
            days_count=Count("date", distinct=True),
        )
        return Response({
            "total_sales": float(agg["total"] or 0),
            "cash": float(agg["cash"] or 0),
            "transfer": float(agg["transfer"] or 0),
            "card": float(agg["card"] or 0),
            "other": float(agg["other"] or 0),
            "sales_count": agg["sales_count"] or 0,
            "days_count": agg["days_count"] or 0,
        })

    def get_queryset(self):
        qs = super().get_queryset()
        branch = self.request.query_params.get("branch")
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        employee = self.request.query_params.get("employee")
        if branch:
            qs = qs.filter(branch_id=branch)
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)
        if employee:
            qs = qs.filter(employee_id=employee)
        return qs

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(
            {"detail": settings.API_MESSAGES["deleted"]},
            status=status.HTTP_200_OK,
        )


class SalesByEmployeeView(APIView):
    """تجميع المبيعات حسب الموظف للفرع والفترة."""

    def get(self, request):
        branch = request.query_params.get("branch")
        employee = request.query_params.get("employee")
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        qs = DailySale.objects.select_related("employee").filter(employee__isnull=False)
        if branch:
            qs = qs.filter(branch_id=branch)
        if employee:
            qs = qs.filter(employee_id=employee)
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)

        rows = (
            qs.values("employee_id", "employee__name")
            .annotate(
                total_sales=Sum("total_sales"),
                cash_total=Sum("cash_amount"),
                transfer_total=Sum("transfer_amount"),
                card_total=Sum("card_amount"),
                other_total=Sum("other_amount"),
                sales_count=Count("id"),
            )
            .order_by("-total_sales")
        )

        items = [
            {
                "employee": r["employee_id"],
                "employee_name": r["employee__name"],
                "total_sales": float(r["total_sales"] or 0),
                "cash_total": float(r["cash_total"] or 0),
                "transfer_total": float(r["transfer_total"] or 0),
                "card_total": float(r["card_total"] or 0),
                "other_total": float(r["other_total"] or 0),
                "sales_count": r["sales_count"],
            }
            for r in rows
        ]

        unassigned = DailySale.objects.filter(employee__isnull=True)
        if branch:
            unassigned = unassigned.filter(branch_id=branch)
        if date_from:
            unassigned = unassigned.filter(date__gte=date_from)
        if date_to:
            unassigned = unassigned.filter(date__lte=date_to)
        unassigned_total = unassigned.aggregate(total=Sum("total_sales"))["total"] or 0

        return Response({
            "items": items,
            "unassigned_total": float(unassigned_total),
            "grand_total": float(sum(i["total_sales"] for i in items) + float(unassigned_total)),
        })


class SaleStockView(APIView):
    """الأرصدة المتاحة لأصناف المبيعات في مخزون الفرع."""

    def get(self, request):
        branch = request.query_params.get("branch")
        if not branch:
            return Response({"detail": "معلم branch مطلوب"}, status=status.HTTP_400_BAD_REQUEST)
        warehouse = Warehouse.objects.filter(branch_id=branch).first()
        if warehouse is None:
            return Response({"warehouse": None, "warehouse_name": "", "items": []})
        rows = (
            FabricRoll.objects.filter(warehouse=warehouse, status=FabricRoll.Status.AVAILABLE)
            .values("fabric_id", fabric_name=F("fabric__name"))
            .annotate(total=Sum("remaining_yards"))
            .order_by("fabric_name")
        )
        items = [
            {"fabric": r["fabric_id"], "fabric_name": r["fabric_name"], "yards": r["total"]}
            for r in rows
        ]
        return Response({
            "warehouse": warehouse.pk,
            "warehouse_name": warehouse.name,
            "items": items,
        })
