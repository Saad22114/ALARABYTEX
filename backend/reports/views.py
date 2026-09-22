from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from branches.models import Branch
from core.branch_scope import allowed_branch_ids, scope_queryset, scope_queryset_or
from expenses.models import Expense, ExpenseBudget, ExpenseCategory
from partners.models import PartnerOperation
from sales.models import DailySale
from suppliers.models import Fabric, Supplier
from sale_sessions.models import SaleSession
from warehouses.models import (
    FabricRoll,
    GoodsReceiptItem,
    StockMovement,
    Warehouse,
)

from .cogs import cogs_by_fabric, fabric_average_costs, sold_by_fabric


def _generate_excel(workbook, sheet_name, headers, rows):
    ws = workbook.create_sheet(title=sheet_name)
    ws.append(headers)
    for row in rows:
        ws.append(row)
    return ws


def _export_sales_to_xlsx(sales_data):
    try:
        import openpyxl
    except ImportError:
        return None
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "المبيعات"
    headers = [
        "الفرع", "التاريخ", "إجمالي المبيعات", "نقدي", "تحويل", "بطاقة", "أخرى",
        "إجمالي الدفع", "ملاحظات",
    ]
    ws.append(headers)
    for s in sales_data:
        ws.append([
            s["branch_name"],
            str(s["date"]),
            float(s["total_sales"]),
            float(s["cash_amount"]),
            float(s["transfer_amount"]),
            float(s["card_amount"]),
            float(s["other_amount"]),
            float(s["payment_total"]),
            s.get("notes", ""),
        ])
    return wb


def _export_expenses_to_xlsx(expenses_data):
    try:
        import openpyxl
    except ImportError:
        return None
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "المصاريف"
    headers = [
        "الفرع", "التصنيف", "التاريخ", "المبلغ", "طريقة الدفع", "الوصف", "ملاحظات",
    ]
    ws.append(headers)
    for e in expenses_data:
        ws.append([
            e["branch_name"],
            e["category_name"],
            str(e["date"]),
            float(e["amount"]),
            e["payment_method"],
            e.get("description", ""),
            e.get("notes", ""),
        ])
    return wb


def _export_generic_to_xlsx(sheet_title, headers, rows):
    try:
        import openpyxl
    except ImportError:
        return None
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_title
    ws.append(headers)
    for row in rows:
        ws.append(row)
    return wb


def _xlsx_response(workbook, filename):
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}.xlsx"'
    workbook.save(response)
    return response


class SalesReportView(APIView):
    permission_section = "reports"
    def get(self, request):
        qs = scope_queryset(
            self.request, DailySale.objects.select_related("branch")
        )
        branch = request.query_params.get("branch")
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        if branch:
            qs = qs.filter(branch_id=branch)
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)
        qs = qs.order_by("-date", "-created_at")

        sales_data = []
        for s in qs:
            sales_data.append({
                "branch_name": s.branch.name,
                "date": s.date,
                "total_sales": s.total_sales,
                "cash_amount": s.cash_amount,
                "transfer_amount": s.transfer_amount,
                "card_amount": s.card_amount,
                "other_amount": s.other_amount,
                "payment_total": s.payment_total,
                "notes": s.notes,
            })

        totals = qs.aggregate(
            total_sales=Sum("total_sales"),
            cash=Sum("cash_amount"),
            transfer=Sum("transfer_amount"),
            card=Sum("card_amount"),
            other=Sum("other_amount"),
        )

        if request.query_params.get("export") == "xlsx":
            wb = _export_sales_to_xlsx(sales_data)
            if wb is None:
                return Response(
                    {"detail": "مكتبة openpyxl غير مثبتة"},
                    status=500,
                )
            return _xlsx_response(wb, "تقرير_المبيعات")

        return Response({
            "sales": sales_data,
            "totals": {
                "total_sales": float(totals["total_sales"] or 0),
                "cash": float(totals["cash"] or 0),
                "transfer": float(totals["transfer"] or 0),
                "card": float(totals["card"] or 0),
                "other": float(totals["other"] or 0),
            },
            "count": qs.count(),
        })


class ExpensesReportView(APIView):
    permission_section = "reports"
    def get(self, request):
        qs = scope_queryset(
            self.request, Expense.objects.select_related("branch", "category")
        )
        branch = request.query_params.get("branch")
        category = request.query_params.get("category")
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        if branch:
            qs = qs.filter(branch_id=branch)
        if category:
            qs = qs.filter(category_id=category)
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)
        qs = qs.order_by("-date", "-created_at")

        expenses_data = []
        for e in qs:
            expenses_data.append({
                "branch_name": e.branch.name,
                "category_name": e.category.name,
                "date": e.date,
                "amount": e.amount,
                "payment_method": e.get_payment_method_display(),
                "description": e.description,
                "notes": e.notes,
            })

        totals = qs.aggregate(total_amount=Sum("amount"))

        if request.query_params.get("export") == "xlsx":
            wb = _export_expenses_to_xlsx(expenses_data)
            if wb is None:
                return Response(
                    {"detail": "مكتبة openpyxl غير مثبتة"},
                    status=500,
                )
            return _xlsx_response(wb, "تقرير_المصاريف")

        return Response({
            "expenses": expenses_data,
            "totals": {
                "total_amount": float(totals["total_amount"] or 0),
            },
            "count": qs.count(),
        })


def _month_start(value, fallback):
    """تحويل YYYY-MM أو تاريخ إلى أول يوم من الشهر."""
    try:
        if len(str(value)) == 7:
            return date.fromisoformat(f"{value}-01")
        return date.fromisoformat(str(value)).replace(day=1)
    except (TypeError, ValueError):
        return fallback


class ExpensesBudgetReportView(APIView):
    """مصاريف كل فرع/تصنيف مقابل الميزانية الشهرية المحددة له."""
    permission_section = "reports"

    def get(self, request):
        today = timezone.localdate()
        month_start = _month_start(
            request.query_params.get("month"), today.replace(day=1)
        )
        month_end = month_start.replace(day=28) + timedelta(days=4)
        month_end = month_end.replace(day=1) - timedelta(days=1)

        branch = request.query_params.get("branch")
        category = request.query_params.get("category")

        budget_qs = scope_queryset(
            self.request, ExpenseBudget.objects.filter(month=month_start)
        )
        expense_qs = scope_queryset(
            self.request,
            Expense.objects.filter(date__gte=month_start, date__lte=month_end),
        )
        if branch:
            budget_qs = budget_qs.filter(branch_id=branch)
            expense_qs = expense_qs.filter(branch_id=branch)
        if category:
            budget_qs = budget_qs.filter(category_id=category)
            expense_qs = expense_qs.filter(category_id=category)

        budgets = {}
        for b in budget_qs.select_related("branch", "category"):
            budgets[(b.branch_id, b.category_id)] = Decimal(b.amount)

        spent = {}
        agg = (
            expense_qs.values("branch_id", "branch__name", "category_id", "category__name")
            .annotate(total=Sum("amount"))
        )
        for row in agg:
            spent[(row["branch_id"], row["category_id"])] = {
                "total": row["total"] or Decimal("0"),
                "branch_name": row["branch__name"],
                "category_name": row["category__name"],
            }

        data = []
        keys = set(budgets.keys()) | set(spent.keys())
        for key in keys:
            branch_id, category_id = key
            budget_row = budget_qs.filter(branch_id=branch_id, category_id=category_id).first()
            spent_row = spent.get(key)
            budget_amount = budgets.get(key, Decimal("0"))
            spent_amount = spent_row["total"] if spent_row else Decimal("0")
            remaining = budget_amount - spent_amount
            used_pct = float(spent_amount * Decimal("100") / budget_amount) if budget_amount else 0.0
            data.append({
                "branch": branch_id,
                "branch_name": budget_row.branch.name if budget_row else spent_row["branch_name"],
                "category": category_id,
                "category_name": budget_row.category.name if budget_row else spent_row["category_name"],
                "budget": float(budget_amount),
                "spent": float(spent_amount),
                "remaining": float(remaining),
                "used_pct": round(used_pct, 1),
            })
        data.sort(key=lambda d: (d["branch_name"], d["category_name"]))

        totals = {
            "budget": float(sum(d["budget"] for d in data)),
            "spent": float(sum(d["spent"] for d in data)),
            "remaining": float(sum(d["remaining"] for d in data)),
            "rows": len(data),
        }

        if request.query_params.get("export") == "xlsx":
            headers = ["الفرع", "التصنيف", "الميزانية", "المنصرف", "المتبقي", "نسبة الاستهلاك %"]
            rows_x = [[d["branch_name"], d["category_name"], d["budget"], d["spent"],
                       d["remaining"], d["used_pct"]] for d in data]
            wb = _export_generic_to_xlsx("المصاريف مقابل الميزانية", headers, rows_x)
            if wb is None:
                return Response({"detail": "مكتبة openpyxl غير مثبتة"}, status=500)
            return _xlsx_response(wb, "تقرير_الميزانية")

        return Response({
            "items": data,
            "totals": totals,
            "month": month_start.isoformat(),
        })


class NetDailyReportView(APIView):
    permission_section = "reports"
    def get(self, request):
        today = timezone.localdate()
        date_from = request.query_params.get("date_from", today - timedelta(days=30))
        date_to = request.query_params.get("date_to", today)
        branch = request.query_params.get("branch")

        if isinstance(date_from, str):
            date_from = date.fromisoformat(date_from)
        if isinstance(date_to, str):
            date_to = date.fromisoformat(date_to)

        current = date_from
        chart_data = []
        while current <= date_to:
            sales_qs = scope_queryset(
                self.request, DailySale.objects.filter(date=current)
            )
            expense_qs = scope_queryset(
                self.request, Expense.objects.filter(date=current)
            )
            if branch:
                sales_qs = sales_qs.filter(branch_id=branch)
                expense_qs = expense_qs.filter(branch_id=branch)
            ds = sales_qs.aggregate(total=Sum("total_sales"))["total"] or 0
            de = expense_qs.aggregate(total=Sum("amount"))["total"] or 0
            chart_data.append({
                "date": current.isoformat(),
                "sales": float(ds),
                "expenses": float(de),
                "net": float(ds - de),
            })
            current += timedelta(days=1)

        if request.query_params.get("export") == "xlsx":
            headers = ["التاريخ", "المبيعات", "المصاريف", "صافي"]
            rows = [[d["date"], d["sales"], d["expenses"], d["net"]] for d in chart_data]
            wb = _export_generic_to_xlsx("صافي يومي", headers, rows)
            if wb is None:
                return Response(
                    {"detail": "مكتبة openpyxl غير مثبتة"},
                    status=500,
                )
            return _xlsx_response(wb, "تقرير_صافي_يومي")

        return Response({
            "chart_data": chart_data,
            "start_date": date_from.isoformat(),
            "end_date": date_to.isoformat(),
        })


class SupplierReportView(APIView):
    permission_section = "reports"
    def get(self, request):
        suppliers = Supplier.objects.filter(is_active=True).order_by("name")
        data = []
        for s in suppliers:
            data.append({
                "id": s.id,
                "name": s.name,
                "company_name": s.company_name,
                "phone": s.phone,
                "email": s.email,
                "city": s.city,
                "country": s.country,
            })

        if request.query_params.get("export") == "xlsx":
            headers = ["الاسم", "الشركة", "الهاتف", "البريد", "المدينة", "الدولة"]
            rows = [[d["name"], d["company_name"], d["phone"], d["email"], d["city"], d["country"]] for d in data]
            wb = _export_generic_to_xlsx("الموردون", headers, rows)
            if wb is None:
                return Response(
                    {"detail": "مكتبة openpyxl غير مثبتة"},
                    status=500,
                )
            return _xlsx_response(wb, "تقرير_الموردين")

        return Response({"suppliers": data, "count": len(data)})


class BranchReportView(APIView):
    permission_section = "reports"
    def get(self, request):
        branches = scope_queryset(
            self.request, Branch.objects.filter(is_active=True)
        ).order_by("name")
        data = []
        for b in branches:
            data.append({
                "id": b.id,
                "name": b.name,
                "code": b.code,
                "phone": b.phone,
                "city": b.city,
                "sales_count": b.daily_sales.count(),
                "expenses_count": b.expenses.count(),
            })

        if request.query_params.get("export") == "xlsx":
            headers = ["الاسم", "الكود", "الهاتف", "المدينة", "عدد المبيعات", "عدد المصاريف"]
            rows = [[d["name"], d["code"], d["phone"], d["city"], d["sales_count"], d["expenses_count"]] for d in data]
            wb = _export_generic_to_xlsx("الفروع", headers, rows)
            if wb is None:
                return Response(
                    {"detail": "مكتبة openpyxl غير مثبتة"},
                    status=500,
                )
            return _xlsx_response(wb, "تقرير_الفروع")

        return Response({"branches": data, "count": len(data)})


class InventoryReportView(APIView):
    """تقرير الأرصدة الحالية لكل قماش في كل مخزن مع تنبيهات الحد الأدنى."""
    permission_section = "reports"

    def get(self, request):
        filters = {}
        warehouse_id = request.query_params.get("warehouse")
        if warehouse_id:
            filters["warehouse_id"] = warehouse_id
        fabric_id = request.query_params.get("fabric")
        if fabric_id:
            filters["fabric_id"] = fabric_id
        search = request.query_params.get("search", "").strip()

        rows = FabricRoll.objects.filter(status=FabricRoll.Status.AVAILABLE, **filters)
        rows = scope_queryset(self.request, rows, branch_field="warehouse__branch")
        if search:
            rows = rows.filter(fabric__name__icontains=search)

        agg = (
            rows.values("warehouse_id", "warehouse__name", "fabric_id", "fabric__name", "fabric__code", "fabric__min_stock", "fabric__unit")
            .annotate(total_yards=Sum("remaining_yards"), rolls_available=Count("id"))
            .order_by("fabric__name")
        )

        by_fabric = {}
        warehouses = {
            w.id: w.name
            for w in scope_queryset(self.request, Warehouse.objects.all())
        }
        for r in agg:
            key = r["fabric_id"]
            entry = by_fabric.setdefault(key, {
                "fabric": key,
                "fabric_code": r["fabric__code"],
                "fabric_name": r["fabric__name"],
                "min_stock": r["fabric__min_stock"],
                "unit": r["fabric__unit"],
                "total_yards": Decimal("0"),
                "rolls_available": 0,
                "rows": [],
            })
            total = r["total_yards"] or Decimal("0")
            # عدد اللفات يُحتسب من تجميع منفصل لأن annotate لا يضيف Count تلقائياً
            entry["total_yards"] += total
            entry["rows"].append({
                "warehouse": r["warehouse_id"],
                "warehouse_name": r["warehouse__name"],
                "total_yards": total,
                "rolls_available": r["rolls_available"] or 0,
            })

        data = []
        for key, entry in by_fabric.items():
            entry["low_stock"] = entry["total_yards"] < entry["min_stock"]
            entry["rows"].sort(key=lambda x: x["warehouse_name"])
            data.append(entry)
        data.sort(key=lambda e: e["fabric_name"])

        if request.query_params.get("export") == "xlsx":
            headers = ["القماش", "الكود", "الرصيد الكلي", "الحد الأدنى", "الحالة"]
            rows_x = [[d["fabric_name"], d["fabric_code"], float(d["total_yards"]), float(d["min_stock"]),
                       "نقص" if d["low_stock"] else "مناسب"] for d in data]
            wb = _export_generic_to_xlsx("المخزون", headers, rows_x)
            if wb is None:
                return Response({"detail": "مكتبة openpyxl غير مثبتة"}, status=500)
            return _xlsx_response(wb, "تقرير_المخزون")

        return Response({
            "items": data,
            "totals": {
                "total_yards": float(sum(e["total_yards"] for e in data)),
                "rolls_available": sum(r["rolls_available"] for e in data for r in e["rows"]),
                "low_stock_count": sum(1 for e in data if e["low_stock"]),
                "fabrics": len(data),
            },
        })


class InventoryMovementsReportView(APIView):
    """تقرير حركات المخزون المفصلة مع الرصيد قبل/بعد كل حركة."""
    permission_section = "reports"

    def get(self, request):
        qs = scope_queryset(
            self.request,
            StockMovement.objects.select_related("warehouse", "fabric"),
            branch_field="warehouse__branch",
        ).order_by("date", "id")
        warehouse = request.query_params.get("warehouse")
        fabric = request.query_params.get("fabric")
        movement_type = request.query_params.get("movement_type")
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        if warehouse:
            qs = qs.filter(warehouse_id=warehouse)
        if fabric:
            qs = qs.filter(fabric_id=fabric)
        if movement_type:
            qs = qs.filter(movement_type=movement_type)
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)

        data = []
        for m in qs:
            data.append({
                "date": m.date,
                "warehouse_name": m.warehouse.name,
                "fabric_name": m.fabric.name,
                "movement_type": m.movement_type,
                "movement_type_label": m.get_movement_type_display(),
                "quantity": m.quantity,
                "balance_before": m.balance_before,
                "balance_after": m.balance_after,
                "reference_no": m.reference_no,
            })

        totals = {"in": Decimal("0"), "out": Decimal("0")}
        for d in data:
            if d["quantity"] > 0:
                totals["in"] += d["quantity"]
            else:
                totals["out"] += -d["quantity"]

        if request.query_params.get("export") == "xlsx":
            headers = ["التاريخ", "المخزن", "القماش", "الحركة", "الكمية", "الرصيد قبل", "الرصيد بعد", "المرجع"]
            rows_x = [[str(d["date"]), d["warehouse_name"], d["fabric_name"], d["movement_type_label"],
                       float(d["quantity"]),
                       float(d["balance_before"]) if d["balance_before"] is not None else "",
                       float(d["balance_after"]) if d["balance_after"] is not None else "",
                       d["reference_no"]] for d in data]
            wb = _export_generic_to_xlsx("حركات المخزون", headers, rows_x)
            if wb is None:
                return Response({"detail": "مكتبة openpyxl غير مثبتة"}, status=500)
            return _xlsx_response(wb, "تقرير_حركات_المخزون")

        return Response({
            "movements": data,
            "totals": {
                "in": float(totals["in"]),
                "out": float(totals["out"]),
                "count": len(data),
            },
        })


# ---------- تكلفة البضاعة المباعة / الربح والخسارة / القيود اليومية ----------


def _report_dates(request):
    today = timezone.localdate()
    date_from = request.query_params.get("date_from") or (today - timedelta(days=30)).isoformat()
    date_to = request.query_params.get("date_to") or today.isoformat()
    return date.fromisoformat(date_from), date.fromisoformat(date_to)


def _scoped_cogs(request, date_from, date_to):
    """تكلفة البضاعة المباعة الإجمالية في الفترة لنطاق فرع الموظف إن كان مقيداً."""
    allowed = allowed_branch_ids(request)
    if allowed is not None:
        if not allowed:
            return Decimal("0")
        branch_id = next(iter(allowed))
    else:
        branch_id = None
    cogs = cogs_by_fabric(date_from, date_to, branch_id)
    return sum(cogs.values(), Decimal("0"))


def _scoped_sold(request, date_from, date_to, fabric_id=None):
    """الياردات المباعة لكل قماش في الفترة لنطاق فرع الموظف إن كان مقيداً."""
    allowed = allowed_branch_ids(request)
    if allowed is not None:
        if not allowed:
            return {}
        branch_id = next(iter(allowed))
    else:
        branch_id = None
    sold = sold_by_fabric(date_from, date_to, branch_id)
    if fabric_id:
        try:
            sold = {k: v for k, v in sold.items() if k == int(fabric_id)}
        except (TypeError, ValueError):
            sold = {}
    return sold


class CogsReportView(APIView):
    """تكلفة البضاعة المباعة وربحية كل قماش في الفترة."""
    permission_section = "reports"

    def get(self, request):
        date_from, date_to = _report_dates(request)
        fabric_id = request.query_params.get("fabric")
        sold = _scoped_sold(request, date_from, date_to, fabric_id)
        costs = fabric_average_costs()
        fabrics = {f.id: f for f in Fabric.objects.filter(id__in=list(sold.keys()))}

        data = []
        for fid, yards in sold.items():
            f = fabrics.get(fid)
            if not f:
                continue
            unit_cost = costs.get(fid) or Decimal("0")
            avg_cost = Decimal(unit_cost)
            revenue = Decimal(str(f.sale_price_yard or 0)) * yards
            cogs = avg_cost * yards
            data.append({
                "fabric": fid,
                "fabric_code": f.code,
                "fabric_name": f.name,
                "unit": f.unit,
                "yards_sold": float(yards),
                "avg_cost": float(avg_cost),
                "revenue": float(revenue),
                "cogs": float(cogs),
                "profit": float(revenue - cogs),
            })
        data.sort(key=lambda d: d["fabric_name"])

        totals = {
            "yards_sold": float(sum(d["yards_sold"] for d in data)),
            "revenue": float(sum(d["revenue"] for d in data)),
            "cogs": float(sum(d["cogs"] for d in data)),
            "profit": float(sum(d["profit"] for d in data)),
        }

        if request.query_params.get("export") == "xlsx":
            headers = ["القماش", "الكود", "المباع", "متوسط التكلفة", "الإيراد (تقريبي)", "التكلفة", "الربح"]
            rows_x = [[d["fabric_name"], d["fabric_code"], d["yards_sold"],
                       d["avg_cost"], d["revenue"], d["cogs"], d["profit"]] for d in data]
            wb = _export_generic_to_xlsx("تكلفة البضاعة المباعة", headers, rows_x)
            if wb is None:
                return Response({"detail": "مكتبة openpyxl غير مثبتة"}, status=500)
            return _xlsx_response(wb, "تقرير_تكلفة_البضاعة")

        return Response({
            "items": data,
            "totals": totals,
            "start_date": date_from.isoformat(),
            "end_date": date_to.isoformat(),
        })


class ProfitLossReportView(APIView):
    """الربح والخسارة: مبيعات - تكلفة البضاعة المباعة - مصاريف."""
    permission_section = "reports"

    def get(self, request):
        date_from, date_to = _report_dates(request)
        branch = request.query_params.get("branch")

        sales_qs = scope_queryset(
            self.request, DailySale.objects.filter(
                date__gte=date_from, date__lte=date_to
            )
        )
        expense_qs = scope_queryset(
            self.request, Expense.objects.filter(
                date__gte=date_from, date__lte=date_to
            )
        )
        if branch:
            sales_qs = sales_qs.filter(branch_id=branch)
            expense_qs = expense_qs.filter(branch_id=branch)

        total_sales = sales_qs.aggregate(t=Sum("total_sales"))["t"] or 0
        total_expenses = expense_qs.aggregate(t=Sum("amount"))["t"] or 0
        cogs = _scoped_cogs(request, date_from, date_to)
        gross_profit = total_sales - cogs
        net_profit = gross_profit - total_expenses

        row_branches = scope_queryset(
            self.request, Branch.objects.filter(is_active=True)
        )
        if branch:
            row_branches = row_branches.filter(id=branch)
        rows = []
        for b in row_branches.order_by("name"):
            bs = DailySale.objects.filter(branch=b, date__gte=date_from, date__lte=date_to).aggregate(t=Sum("total_sales"))["t"] or 0
            be = Expense.objects.filter(branch=b, date__gte=date_from, date__lte=date_to).aggregate(t=Sum("amount"))["t"] or 0
            rows.append({
                "branch_name": b.name,
                "sales": float(bs),
                "expenses": float(be),
                "net": float(bs - be),
            })

        if request.query_params.get("export") == "xlsx":
            headers = ["البيان", "المبلغ"]
            rows_x = [
                ["إجمالي المبيعات", float(total_sales)],
                ["تكلفة البضاعة المباعة", float(cogs)],
                ["مجمل الربح", float(gross_profit)],
                ["المصاريف", float(total_expenses)],
                ["صافي الربح", float(net_profit)],
            ]
            for r in rows:
                rows_x.append(["ربح فرع " + r["branch_name"], r["net"]])
            wb = _export_generic_to_xlsx("الربح والخسارة", headers, rows_x)
            if wb is None:
                return Response({"detail": "مكتبة openpyxl غير مثبتة"}, status=500)
            return _xlsx_response(wb, "تقرير_الربح_والخسارة")

        return Response({
            "totals": {
                "total_sales": float(total_sales),
                "cogs": float(cogs),
                "gross_profit": float(gross_profit),
                "expenses": float(total_expenses),
                "net_profit": float(net_profit),
            },
            "branches": rows,
        })


class CommissionsReportView(APIView):
    """عمولات المبيعات لكل موظف في الفترة حسب إغلاق الورديات."""
    permission_section = "reports"

    def get(self, request):
        today = timezone.localdate()
        month_start = _month_start(
            request.query_params.get("month") or today.strftime("%Y-%m"),
            today.replace(day=1),
        )
        month_end = month_start.replace(day=28) + timedelta(days=4)
        month_end = month_end.replace(day=1) - timedelta(days=1)

        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        if date_from:
            try:
                month_start = date.fromisoformat(date_from)
            except ValueError:
                pass
        if date_to:
            try:
                month_end = date.fromisoformat(date_to)
            except ValueError:
                pass

        qs = scope_queryset(
            self.request,
            SaleSession.objects.filter(
                status=SaleSession.Status.CLOSED,
                closed_at__date__gte=month_start,
                closed_at__date__lte=month_end,
            ),
        ).select_related("employee", "employee__branch", "branch").prefetch_related("items")

        employee = request.query_params.get("employee")
        branch = request.query_params.get("branch")
        if employee:
            qs = qs.filter(employee_id=employee)
        if branch:
            qs = qs.filter(branch_id=branch)

        rows = {}
        for s in qs:
            key = (s.employee_id, s.branch_id)
            entry = rows.setdefault(key, {
                "employee": s.employee_id,
                "employee_name": s.employee.name,
                "branch": s.branch_id,
                "branch_name": s.branch.name,
                "sessions_count": 0,
                "total_sales": Decimal("0"),
                "total_commission": Decimal("0"),
            })
            entry["sessions_count"] += 1
            entry["total_sales"] += sum(r.total for r in s.items.all())
            entry["total_commission"] += s.commission_amount or Decimal("0")

        data = []
        for entry in rows.values():
            data.append({
                "employee": entry["employee"],
                "employee_name": entry["employee_name"],
                "branch": entry["branch"],
                "branch_name": entry["branch_name"],
                "sessions_count": entry["sessions_count"],
                "total_sales": float(entry["total_sales"]),
                "total_commission": float(entry["total_commission"]),
            })
        data.sort(key=lambda d: (d["employee_name"], d["branch_name"]))

        totals = {
            "sessions": sum(d["sessions_count"] for d in data),
            "sales": float(sum(d["total_sales"] for d in data)),
            "commission": float(sum(d["total_commission"] for d in data)),
            "employees": len(data),
        }

        if request.query_params.get("export") == "xlsx":
            headers = ["الموظف", "الفرع", "عدد الورديات", "إجمالي المبيعات", "العمولة"]
            rows_x = [[d["employee_name"], d["branch_name"], d["sessions_count"],
                       d["total_sales"], d["total_commission"]] for d in data]
            wb = _export_generic_to_xlsx("عمولات المبيعات", headers, rows_x)
            if wb is None:
                return Response({"detail": "مكتبة openpyxl غير مثبتة"}, status=500)
            return _xlsx_response(wb, "تقرير_عمولات_المبيعات")

        return Response({
            "items": data,
            "totals": totals,
            "start_date": month_start.isoformat(),
            "end_date": month_end.isoformat(),
        })


class JournalReportView(APIView):
    """سجل القيود اليومية: مبيعات، مشتريات، مصاريف، دعم وسحب الشركاء مع رصيد تراكمي."""
    permission_section = "reports"

    def get(self, request):
        date_from, date_to = _report_dates(request)
        branch = request.query_params.get("branch")

        journal = []
        current = date_from
        while current <= date_to:
            sales_qs = scope_queryset(
                self.request, DailySale.objects.filter(date=current)
            )
            expense_qs = scope_queryset(
                self.request, Expense.objects.filter(date=current)
            )
            purchase_qs = scope_queryset_or(
                self.request,
                GoodsReceiptItem.objects.filter(
                    receipt__status="posted", receipt__date=current
                ),
                ["receipt__branch", "receipt__warehouse__branch"],
            )
            if branch:
                sales_qs = sales_qs.filter(branch_id=branch)
                expense_qs = expense_qs.filter(branch_id=branch)
                purchase_qs = purchase_qs.filter(receipt__branch_id=branch)
            sales = sales_qs.aggregate(t=Sum("total_sales"))["t"] or 0
            expenses = expense_qs.aggregate(t=Sum("amount"))["t"] or 0
            purchases = purchase_qs.aggregate(t=Sum("total"))["t"] or 0
            support = PartnerOperation.objects.filter(date=current, operation_type=PartnerOperation.OperationType.SUPPORT).aggregate(t=Sum("amount"))["t"] or 0
            withdraw = PartnerOperation.objects.filter(date=current, operation_type=PartnerOperation.OperationType.WITHDRAW).aggregate(t=Sum("amount"))["t"] or 0
            net = sales + support - purchases - expenses - withdraw
            journal.append({
                "date": current.isoformat(),
                "sales": float(sales),
                "purchases": float(purchases),
                "expenses": float(expenses),
                "support": float(support),
                "withdraw": float(withdraw),
                "net": float(net),
                "running_balance": Decimal("0"),
            })
            current += timedelta(days=1)

        running = Decimal("0")
        for row in journal:
            running += Decimal(str(row["net"]))
            row["running_balance"] = float(running)

        totals = {
            "sales": float(sum(r["sales"] for r in journal)),
            "purchases": float(sum(r["purchases"] for r in journal)),
            "expenses": float(sum(r["expenses"] for r in journal)),
            "support": float(sum(r["support"] for r in journal)),
            "withdraw": float(sum(r["withdraw"] for r in journal)),
            "net": float(running),
        }

        if request.query_params.get("export") == "xlsx":
            headers = ["التاريخ", "المبيعات", "المشتريات", "المصاريف", "دعم الشركاء", "سحب الشركاء", "الصافي", "الرصيد التراكمي"]
            rows_x = [[r["date"], r["sales"], r["purchases"], r["expenses"], r["support"],
                       r["withdraw"], r["net"], r["running_balance"]] for r in journal]
            wb = _export_generic_to_xlsx("القيود اليومية", headers, rows_x)
            if wb is None:
                return Response({"detail": "مكتبة openpyxl غير مثبتة"}, status=500)
            return _xlsx_response(wb, "تقرير_القيود_اليومية")

        return Response({
            "journal": journal,
            "totals": totals,
            "start_date": date_from.isoformat(),
            "end_date": date_to.isoformat(),
        })
