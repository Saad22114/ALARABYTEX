from datetime import date, timedelta

from django.db.models import Sum
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from branches.models import Branch
from expenses.models import Expense
from partners.models import PartnerOperation
from sales.models import DailySale
from suppliers.models import Supplier
from warehouses.models import FabricRoll


class DashboardAlertsView(APIView):
    """تنبيهات لوحة التحكم: نقص المخزون + ملخص اليوم."""

    def get(self, request):
        today = timezone.localdate()

        agg = (
            FabricRoll.objects.filter(status=FabricRoll.Status.AVAILABLE)
            .values("fabric_id", "fabric__name", "fabric__code", "fabric__min_stock", "fabric__unit")
            .annotate(total_yards=Sum("remaining_yards"))
        )
        low_stock = []
        for r in agg:
            total = r["total_yards"] or 0
            if total < r["fabric__min_stock"]:
                low_stock.append({
                    "fabric": r["fabric_id"],
                    "fabric_name": r["fabric__name"],
                    "fabric_code": r["fabric__code"],
                    "unit": r["fabric__unit"],
                    "total_yards": float(total),
                    "min_stock": float(r["fabric__min_stock"]),
                })
        low_stock.sort(key=lambda x: x["fabric_name"])

        sales = DailySale.objects.filter(date=today).aggregate(t=Sum("total_sales"))["t"] or 0
        expenses = Expense.objects.filter(date=today).aggregate(t=Sum("amount"))["t"] or 0
        support = PartnerOperation.objects.filter(date=today, operation_type=PartnerOperation.OperationType.SUPPORT).aggregate(t=Sum("amount"))["t"] or 0
        withdraw = PartnerOperation.objects.filter(date=today, operation_type=PartnerOperation.OperationType.WITHDRAW).aggregate(t=Sum("amount"))["t"] or 0

        return Response({
            "date": today.isoformat(),
            "low_stock": low_stock,
            "low_stock_count": len(low_stock),
            "today": {
                "sales": float(sales),
                "expenses": float(expenses),
                "support": float(support),
                "withdraw": float(withdraw),
                "net": float(sales + support - expenses - withdraw),
            },
        })


class DashboardSummaryView(APIView):
    def get(self, request):
        today = timezone.localdate()
        period = request.query_params.get("period", "today")
        branch_id = request.query_params.get("branch")

        if period == "today":
            start_date = today
            end_date = today
        elif period == "week":
            start_date = today - timedelta(days=today.weekday())
            end_date = today
        elif period == "month":
            start_date = today.replace(day=1)
            end_date = today
        elif period == "custom":
            start_date = request.query_params.get("date_from", today)
            end_date = request.query_params.get("date_to", today)
            if isinstance(start_date, str):
                start_date = date.fromisoformat(start_date)
            if isinstance(end_date, str):
                end_date = date.fromisoformat(end_date)
        else:
            start_date = today
            end_date = today

        sales_qs = DailySale.objects.filter(date__gte=start_date, date__lte=end_date)
        expense_qs = Expense.objects.filter(date__gte=start_date, date__lte=end_date)

        if branch_id:
            sales_qs = sales_qs.filter(branch_id=branch_id)
            expense_qs = expense_qs.filter(branch_id=branch_id)

        total_sales = sales_qs.aggregate(total=Sum("total_sales"))["total"] or 0
        total_expenses = expense_qs.aggregate(total=Sum("amount"))["total"] or 0
        branches_count = Branch.objects.filter(is_active=True).count()
        suppliers_count = Supplier.objects.filter(is_active=True).count()

        chart_data = []
        current = start_date
        while current <= end_date:
            day_sales = DailySale.objects.filter(date=current)
            day_expenses = Expense.objects.filter(date=current)
            if branch_id:
                day_sales = day_sales.filter(branch_id=branch_id)
                day_expenses = day_expenses.filter(branch_id=branch_id)
            ds = day_sales.aggregate(total=Sum("total_sales"))["total"] or 0
            de = day_expenses.aggregate(total=Sum("amount"))["total"] or 0
            chart_data.append({
                "date": current.isoformat(),
                "sales": float(ds),
                "expenses": float(de),
                "net": float(ds - de),
            })
            current += timedelta(days=1)

        return Response({
            "total_sales": float(total_sales),
            "total_expenses": float(total_expenses),
            "net": float(total_sales - total_expenses),
            "branches_count": branches_count,
            "suppliers_count": suppliers_count,
            "chart_data": chart_data,
            "period": period,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        })
