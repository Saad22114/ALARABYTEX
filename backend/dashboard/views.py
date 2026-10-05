from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from appsettings.models import AppSettings
from branches.models import Branch
from core.branch_scope import allowed_branch_ids, scope_queryset, scope_queryset_or
from core.daterange import resolve_range
from core.money import money, unit_price
from expenses.models import Expense
from partners.models import PartnerOperation
from sale_sessions.models import SaleSession
from sales.models import DailySale, DailySaleItem
from suppliers.models import Fabric, LedgerEntry, Supplier
from warehouses.models import FabricRoll

from reports.cogs import fabric_average_costs, sold_by_fabric


def _last_day_of_month(value):
    if value.month == 12:
        return date(value.year + 1, 1, 1) - timedelta(days=1)
    return date(value.year, value.month + 1, 1) - timedelta(days=1)


def _salary_cost(request, date_from, date_to, branch_id=None):
    """راتب الفترة المستحق من مسيّرات الرواتب غير الملغاة المتداخلة معها."""
    from payroll.models import Payslip, PayrollRun

    runs = scope_queryset(
        request,
        PayrollRun.objects.filter(month__lte=date_to).exclude(
            status=PayrollRun.Status.CANCELLED
        ),
        "branch",
    )
    if branch_id:
        runs = runs.filter(branch_id=branch_id)
    run_ids = [run.id for run in runs if _last_day_of_month(run.month) >= date_from]
    payslips = Payslip.objects.filter(run_id__in=run_ids) if run_ids else Payslip.objects.none()
    if branch_id:
        payslips = payslips.filter(branch_id=branch_id)
    return sum((slip.net_pay for slip in payslips), Decimal("0"))


class DashboardAlertsView(APIView):
    """تنبيهات لوحة التحكم: نقص المخزون + ورديات مفتوحة + مشتريات غير مستلمة + ملخص اليوم."""
    permission_section = "dashboard"

    def get(self, request):
        today = timezone.localdate()

        low_stock = []
        if AppSettings.load().low_stock_alert_enabled:
            agg = (
                scope_queryset(
                    self.request,
                    FabricRoll.objects.filter(status=FabricRoll.Status.AVAILABLE),
                    branch_field="warehouse__branch",
                )
                .values("fabric_id", "fabric__name", "fabric__code", "fabric__min_stock", "fabric__unit")
                .annotate(total_yards=Sum("remaining_yards"))
            )
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

        open_sessions = list(
            scope_queryset(
                self.request,
                SaleSession.objects.filter(
                    status=SaleSession.Status.OPEN, opened_at__date__lt=today
                ),
            )
            .select_related("employee", "branch")
            .order_by("opened_at")[:10]
        )
        open_sessions_data = [
            {
                "id": s.id,
                "employee_name": s.employee.name,
                "branch_name": s.branch.name,
                "opened_at": s.opened_at.isoformat(),
            }
            for s in open_sessions
        ]

        pending_purchases = (
            scope_queryset_or(
                self.request,
                LedgerEntry.objects.filter(
                    entry_type=LedgerEntry.EntryType.PURCHASE
                ),
                ["branch", "warehouse__branch"],
            )
            .annotate(receipt_count=Count("goods_receipts"))
            .filter(receipt_count=0)
            .select_related("supplier")
            .order_by("-date", "-created_at")[:10]
        )
        pending_receipts_data = [
            {
                "id": e.id,
                "supplier": e.supplier_id,
                "supplier_name": e.supplier.name,
                "receipt_no": e.receipt_no,
                "date": e.date.isoformat(),
                "amount": money(e.amount),
                "destination": e.destination_name,
            }
            for e in pending_purchases
        ]

        sales = scope_queryset(
            self.request, DailySale.objects.filter(date=today)
        ).aggregate(t=Sum("total_sales"))["t"] or 0
        expenses = scope_queryset(
            self.request, Expense.objects.filter(date=today)
        ).aggregate(t=Sum("amount"))["t"] or 0
        support = PartnerOperation.objects.filter(date=today, operation_type=PartnerOperation.OperationType.SUPPORT).aggregate(t=Sum("amount"))["t"] or 0
        withdraw = PartnerOperation.objects.filter(date=today, operation_type=PartnerOperation.OperationType.WITHDRAW).aggregate(t=Sum("amount"))["t"] or 0

        return Response({
            "date": today.isoformat(),
            "low_stock": low_stock,
            "low_stock_count": len(low_stock),
            "open_sessions": open_sessions_data,
            "open_sessions_count": len(open_sessions_data),
            "pending_receipts": pending_receipts_data,
            "pending_receipts_count": len(pending_receipts_data),
            "today": {
                "sales": money(sales),
                "expenses": money(expenses),
                "support": money(support),
                "withdraw": money(withdraw),
                "net": money(sales + support - expenses - withdraw),
            },
        })


class DashboardSummaryView(APIView):
    permission_section = "dashboard"
    def get(self, request):
        start_date, end_date, period = resolve_range(request.query_params)
        branch_id = request.query_params.get("branch")

        allowed = allowed_branch_ids(request)
        restricted = allowed is not None
        if restricted:
            if not branch_id and len(allowed) == 1:
                branch_id = str(next(iter(allowed)))
            elif branch_id and branch_id not in {str(b) for b in allowed}:
                branch_id = None

        sales_qs = scope_queryset(
            request,
            DailySale.objects.filter(date__gte=start_date, date__lte=end_date),
        )
        expense_qs = scope_queryset(
            request,
            Expense.objects.filter(date__gte=start_date, date__lte=end_date),
        )

        if branch_id:
            sales_qs = sales_qs.filter(branch_id=branch_id)
            expense_qs = expense_qs.filter(branch_id=branch_id)
        branch_pk = int(branch_id) if branch_id else None
        if restricted and branch_pk is None:
            branch_pk = -1

        total_sales = sales_qs.aggregate(total=Sum("total_sales"))["total"] or 0
        total_expenses = expense_qs.aggregate(total=Sum("amount"))["total"] or 0
        branches_count = scope_queryset(
            request, Branch.objects.filter(is_active=True), branch_field="id"
        ).count()
        suppliers_count = Supplier.objects.filter(is_active=True).count()

        sold = sold_by_fabric(start_date, end_date, branch_pk)
        costs = fabric_average_costs(sold.keys())
        cogs_map = {fid: (costs.get(fid) or Decimal("0")) * yards for fid, yards in sold.items()}
        total_cogs = sum(cogs_map.values(), Decimal("0"))
        gross_profit = Decimal(total_sales) - total_cogs
        total_salaries = _salary_cost(request, start_date, end_date, branch_pk)
        margin = (gross_profit / Decimal(total_sales) * 100) if total_sales else Decimal("0")

        sales_by_day = {
            row["date"]: row["total"]
            for row in sales_qs.values("date").annotate(total=Sum("total_sales"))
        }
        expense_by_day = {
            row["date"]: row["total"]
            for row in expense_qs.values("date").annotate(total=Sum("amount"))
        }
        daily_sold_qs = scope_queryset(
            request,
            DailySaleItem.objects.filter(
                sale__date__gte=start_date, sale__date__lte=end_date
            ),
            branch_field="sale__branch",
        )
        if branch_id:
            daily_sold_qs = daily_sold_qs.filter(sale__branch_id=branch_id)
        daily_sold = {}
        for row in daily_sold_qs.values("sale__date", "fabric_id").annotate(total_yards=Sum("yards")):
            daily_sold.setdefault(row["sale__date"], {})[row["fabric_id"]] = row["total_yards"]

        chart_data = []
        current = start_date
        while current <= end_date:
            ds = sales_by_day.get(current) or 0
            de = expense_by_day.get(current) or 0
            day_sold = daily_sold.get(current) or {}
            day_cogs = sum(
                (costs.get(fid) or Decimal("0")) * yards
                for fid, yards in day_sold.items()
            )
            day_profit = Decimal(ds) - day_cogs
            chart_data.append({
                "date": current.isoformat(),
                "sales": money(ds),
                "expenses": money(de),
                "net": money(ds - de),
                "cogs": money(day_cogs),
                "gross_profit": money(day_profit),
            })
            current += timedelta(days=1)

        duration = (end_date - start_date).days
        prev_end = start_date - timedelta(days=1)
        prev_start = prev_end - timedelta(days=duration)

        prev_sales_qs = scope_queryset(
            request, DailySale.objects.filter(date__gte=prev_start, date__lte=prev_end)
        )
        prev_expense_qs = scope_queryset(
            request, Expense.objects.filter(date__gte=prev_start, date__lte=prev_end)
        )
        if branch_id:
            prev_sales_qs = prev_sales_qs.filter(branch_id=branch_id)
            prev_expense_qs = prev_expense_qs.filter(branch_id=branch_id)
        previous_sales = prev_sales_qs.aggregate(total=Sum("total_sales"))["total"] or 0
        previous_expenses = prev_expense_qs.aggregate(total=Sum("amount"))["total"] or 0
        previous_sold = sold_by_fabric(prev_start, prev_end, branch_pk)
        previous_costs = fabric_average_costs(previous_sold.keys())
        previous_cogs = sum(
            ((previous_costs.get(fid) or Decimal("0")) * yards for fid, yards in previous_sold.items()),
            Decimal("0"),
        )
        previous_salaries = _salary_cost(request, prev_start, prev_end, branch_pk)
        previous_gross_profit = Decimal(previous_sales) - previous_cogs
        previous_net = previous_gross_profit - Decimal(previous_expenses) - previous_salaries
        current_net = gross_profit - Decimal(total_expenses) - total_salaries

        def _delta(current_value, previous_value):
            if previous_value:
                return round((float(current_value) - float(previous_value)) / float(previous_value) * 100, 1)
            return None

        prev_sales_by_day = {
            row["date"]: row["total"]
            for row in prev_sales_qs.values("date").annotate(total=Sum("total_sales"))
        }
        prev_expense_by_day = {
            row["date"]: row["total"]
            for row in prev_expense_qs.values("date").annotate(total=Sum("amount"))
        }
        chart_previous = []
        current = prev_start
        while current <= prev_end:
            ds = prev_sales_by_day.get(current) or 0
            de = prev_expense_by_day.get(current) or 0
            chart_previous.append({
                "date": current.isoformat(),
                "sales": money(ds),
                "expenses": money(de),
                "net": money(ds - de),
                "cogs": 0.0,
                "gross_profit": 0.0,
            })
            current += timedelta(days=1)

        fabrics = {f.id: f for f in Fabric.objects.filter(id__in=list(sold.keys()))}
        top = []
        for fid, yards in sold.items():
            f = fabrics.get(fid)
            unit_cost = costs.get(fid) or Decimal("0")
            revenue_f = (Decimal(str(f.sale_price_yard or 0)) if f else Decimal("0")) * yards
            cogs_f = cogs_map.get(fid) or Decimal("0")
            top.append({
                "fabric": fid,
                "fabric_name": f.name if f else "",
                "fabric_code": f.code if f else "",
                "yards_sold": float(yards),
                "unit_cost": unit_price(unit_cost),
                "revenue": money(revenue_f),
                "cogs": money(cogs_f),
                "profit": money(revenue_f - cogs_f),
            })
        top.sort(key=lambda d: d["profit"], reverse=True)

        return Response({
            "total_sales": money(total_sales),
            "total_cogs": money(total_cogs),
            "total_expenses": money(total_expenses),
            "total_salaries": money(total_salaries),
            "net": money(current_net),
            "gross_profit": money(gross_profit),
            "margin_pct": round(float(margin), 1),
            "branches_count": branches_count,
            "suppliers_count": suppliers_count,
            "chart_data": chart_data,
            "chart_previous": chart_previous,
            "previous_sales": money(previous_sales),
            "previous_expenses": money(previous_expenses),
            "previous_salaries": money(previous_salaries),
            "previous_net": money(previous_net),
            "sales_delta_pct": _delta(total_sales, previous_sales),
            "expenses_delta_pct": _delta(total_expenses, previous_expenses),
            "net_delta_pct": _delta(current_net, previous_net),
            "top_fabrics": top[:5],
            "period": period,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        })


class DashboardActivityView(APIView):
    """آخر العمليات: بيع، شراء، دفعة، مصروف."""
    permission_section = "dashboard"

    def get(self, request):
        activities = []

        sales = scope_queryset(
            self.request,
            DailySale.objects.select_related("branch"),
        ).order_by("-date", "-created_at")[:5]
        for s in sales:
            activities.append({
                "type": "sale",
                "id": s.id,
                "title": f"بيعة - {s.branch.name}",
                "amount": money(s.total_sales),
                "date": s.date.isoformat(),
                "created_at": s.created_at.isoformat(),
                "link": "/sales",
            })

        purchase_qs = (
            scope_queryset_or(
                self.request,
                LedgerEntry.objects.filter(
                    entry_type=LedgerEntry.EntryType.PURCHASE
                ),
                ["branch", "warehouse__branch"],
            )
            .select_related("supplier")
            .order_by("-date", "-created_at")[:5]
        )
        for e in purchase_qs:
            activities.append({
                "type": "purchase",
                "id": e.id,
                "title": f"شراء من {e.supplier.name}",
                "amount": money(abs(e.amount)),
                "date": e.date.isoformat(),
                "created_at": e.created_at.isoformat(),
                "link": f"/suppliers/{e.supplier_id}",
            })

        payment_qs = (
            scope_queryset_or(
                self.request,
                LedgerEntry.objects.filter(
                    entry_type=LedgerEntry.EntryType.PAYMENT
                ),
                ["branch", "warehouse__branch"],
            )
            .select_related("supplier")
            .order_by("-date", "-created_at")[:5]
        )
        for e in payment_qs:
            activities.append({
                "type": "payment",
                "id": e.id,
                "title": f"دفعة لـ {e.supplier.name}",
                "amount": money(abs(e.amount)),
                "date": e.date.isoformat(),
                "created_at": e.created_at.isoformat(),
                "link": f"/suppliers/{e.supplier_id}",
            })

        expense_qs = scope_queryset(
            self.request,
            Expense.objects.select_related("category", "branch"),
        ).order_by("-date", "-created_at")[:5]
        for e in expense_qs:
            activities.append({
                "type": "expense",
                "id": e.id,
                "title": f"مصروف: {e.category.name}",
                "amount": money(e.amount),
                "date": e.date.isoformat(),
                "created_at": e.created_at.isoformat(),
                "link": "/expenses",
            })

        activities.sort(key=lambda a: (a["date"], a["created_at"]), reverse=True)
        return Response({"activities": activities[:10]})
