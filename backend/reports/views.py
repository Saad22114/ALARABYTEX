from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from branches.models import Branch
from core.branch_scope import allowed_branch_ids, scope_queryset, scope_queryset_or
from expenses.models import Expense, ExpenseBudget, ExpenseCategory
from partners.models import PartnerOperation
from sales.models import DailySale
from suppliers.models import Fabric, Supplier
from sale_sessions.models import SaleSession, SaleSessionItem
from sale_sessions.services import item_pieces
from suppliers.serializers import PIECE_YARDS
from warehouses.models import (
    FabricRoll,
    GoodsReceiptItem,
    StockMovement,
    Warehouse,
)

from core import excel
from core.money import money, unit_price
from .cogs import (
    cogs_by_day_branch,
    cogs_by_fabric,
    fabric_average_costs,
    sold_by_fabric,
)


def _period_label(request, default=""):
    """سطر يوضّح الفترة المصدَّرة — وإلا خرج الملف بلا تاريخ يُرجَع إليه.

    تاريخٌ واحد بلا counterpart يجعل القارئ يسأل: «أي شهر هذا؟» — وتلك
    أغلى ثانية في قراءة أي تقرير.
    """
    start = request.query_params.get("date_from") or ""
    end = request.query_params.get("date_to") or ""
    parts = []
    if start or end:
        parts.append(f"الفترة: {start or '—'} إلى {end or '—'}")
    branch = request.query_params.get("branch")
    if branch:
        parts.append(f"الفرع: {branch}")
    if not parts:
        return default
    return "  |  ".join(parts)


def _export_sales_to_xlsx(sales_data, subtitle=""):
    headers = [
        "الفرع", "التاريخ", "إجمالي المبيعات", "نقدي", "تحويل", "بطاقة", "أخرى",
        "إجمالي الدفع", "ملاحظات",
    ]
    rows = [
        [
            s["branch_name"],
            str(s["date"]),
            s["total_sales"],
            s["cash_amount"],
            s["transfer_amount"],
            s["card_amount"],
            s["other_amount"],
            s["payment_total"],
            s.get("notes", ""),
        ]
        for s in sales_data
    ]
    return excel.build_workbook([{
        "title": "المبيعات",
        "columns": excel.infer_columns(headers, rows),
        "rows": rows,
        "heading": "تقرير المبيعات",
        "subtitle": subtitle,
    }])


def _export_expenses_to_xlsx(expenses_data, subtitle=""):
    headers = [
        "الفرع", "التصنيف", "التاريخ", "المبلغ", "طريقة الدفع", "الوصف", "ملاحظات",
    ]
    rows = [
        [
            e["branch_name"],
            e["category_name"],
            str(e["date"]),
            e["amount"],
            e["payment_method"],
            e.get("description", ""),
            e.get("notes", ""),
        ]
        for e in expenses_data
    ]
    return excel.build_workbook([{
        "title": "المصاريف",
        "columns": excel.infer_columns(headers, rows),
        "rows": rows,
        "heading": "تقرير المصاريف",
        "subtitle": subtitle,
    }])


def _export_generic_to_xlsx(sheet_title, headers, rows, types=None, subtitle=""):
    """ورقة واحدة مُنسَّقة — الطريق الموحّد لكل الشاشات البسيطة.

    يُرجع ``None`` إن لم يكن ``openpyxl`` مثبَّتاً، فيردّ كل موضع رسالة
    500 صريحة بدل انهيارٍ obscures سببه.
    """
    return excel.build_workbook([{
        "title": sheet_title,
        "columns": excel.infer_columns(headers, rows, types),
        "rows": rows,
        "heading": sheet_title,
        "subtitle": subtitle,
    }])


def _xlsx_response(workbook, filename):
    if workbook is None:
        return Response(
            {"detail": "مكتبة openpyxl غير مثبتة"}, status=500
        )
    return excel.xlsx_response(workbook, filename)


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
            wb = _export_sales_to_xlsx(sales_data, _period_label(request))
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
            wb = _export_expenses_to_xlsx(
                expenses_data,
                _period_label(request, f"عدد السجلات: {len(expenses_data)}"),
            )
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
            # صفّ الإجمالي: يُجمع في Excel بضغطة، لكن من يكتب التقرير لا
            # يعرف أيّ خانة خاطئة أفسدته — والمجموع المكتوب يبيّنها.
            rows.append([
                "الإجمالي",
                round(sum(d["sales"] for d in chart_data), 2),
                round(sum(d["expenses"] for d in chart_data), 2),
                round(sum(d["net"] for d in chart_data), 2),
            ])
            wb = _export_generic_to_xlsx(
                "صافي يومي", headers, rows,
                subtitle=f"الفترة: {date_from.isoformat()} إلى {date_to.isoformat()}",
            )
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
            wb = _export_generic_to_xlsx(
                "الموردون", headers, rows,
                subtitle=f"عدد الموردين: {len(data)}",
            )
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
            rows.append([
                "الإجمالي", "", "", "",
                sum(d["sales_count"] for d in data),
                sum(d["expenses_count"] for d in data),
            ])
            wb = _export_generic_to_xlsx(
                "الفروع", headers, rows,
                subtitle=f"عدد الفروع: {len(data)}",
            )
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
            rows_x.append([
                "الإجمالي", "",
                round(sum(float(d["total_yards"]) for d in data), 2),
                round(sum(float(d["min_stock"]) for d in data), 2),
                "",
            ])
            low = sum(1 for d in data if d["low_stock"])
            wb = _export_generic_to_xlsx(
                "المخزون", headers, rows_x,
                types=["text", "text", "number", "number", "text"],
                subtitle=f"عدد الأقمشة: {len(data)}  |  تحت الحد الأدنى: {low}",
            )
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
            rows_x.append([
                "الإجمالي", "", "", f"وارد: {float(totals['in'])} / منصرف: {float(totals['out'])}",
                "", "", "", f"{len(data)} حركة",
            ])
            wb = _export_generic_to_xlsx(
                "حركات المخزون", headers, rows_x,
                types=["date", "text", "text", "text", "number", "number", "number", "text"],
                subtitle=_period_label(request, f"عدد الحركات: {len(data)}"),
            )
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


def _scoped_branch_ids(request, branch=None):
    """معرّفات الفروع التي يسري عليها الاستعلام.

    تُرجع ``[None]`` للدلالة على «كل الفروع» (لا تقييد)، و``[]`` إذا لم يُسمح
    بأي فرع. عند تمرير branch يتقدّم الفهرس على نطاق الموظف (الخارج يُرجع []).
    """
    if branch:
        try:
            return [int(branch)]
        except (TypeError, ValueError):
            return []
    allowed = allowed_branch_ids(request)
    if allowed is None:
        return [None]
    return sorted(allowed)


def _scoped_cogs(request, date_from, date_to, branch=None, costs=None):
    """تكلفة البضاعة المباعة الإجمالية في الفترة لنطاق فرع الموظف إن كان مقيداً."""
    total = Decimal("0")
    for bid in _scoped_branch_ids(request, branch):
        total += sum(
            cogs_by_fabric(date_from, date_to, bid, costs).values(), Decimal("0")
        )
    return total


def _scoped_sold(request, date_from, date_to, fabric_id=None):
    """الياردات المباعة لكل قماش في الفترة لنطاق فرع الموظف إن كان مقيداً."""
    sold = {}
    for bid in _scoped_branch_ids(request):
        sold.update(sold_by_fabric(date_from, date_to, bid))
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
                "avg_cost": unit_price(avg_cost),
                "revenue": money(revenue),
                "cogs": money(cogs),
                "profit": money(revenue - cogs),
            })
        data.sort(key=lambda d: d["fabric_name"])

        totals = {
            "yards_sold": float(sum(d["yards_sold"] for d in data)),
            "revenue": money(sum(d["revenue"] for d in data)),
            "cogs": money(sum(d["cogs"] for d in data)),
            "profit": money(sum(d["profit"] for d in data)),
        }

        if request.query_params.get("export") == "xlsx":
            headers = ["القماش", "الكود", "المباع", "متوسط التكلفة", "الإيراد (تقريبي)", "التكلفة", "الربح"]
            rows_x = [[d["fabric_name"], d["fabric_code"], d["yards_sold"],
                       d["avg_cost"], d["revenue"], d["cogs"], d["profit"]] for d in data]
            rows_x.append([
                "الإجمالي", "",
                round(totals["yards_sold"], 2), "",
                round(totals["revenue"], 2),
                round(totals["cogs"], 2),
                round(totals["profit"], 2),
            ])
            wb = _export_generic_to_xlsx(
                "تكلفة البضاعة المباعة", headers, rows_x,
                types=["text", "text", "number", "money", "money", "money", "money"],
                subtitle=(
                    f"الفترة: {date_from.isoformat()} إلى {date_to.isoformat()}"
                    f"  |  عدد الأقمشة: {len(data)}"
                ),
            )
            if wb is None:
                return Response({"detail": "مكتبة openpyxl غير مثبتة"}, status=500)
            return _xlsx_response(wb, "تقرير_تكلفة_البضاعة")

        return Response({
            "items": data,
            "totals": totals,
            "start_date": date_from.isoformat(),
            "end_date": date_to.isoformat(),
        })


def _last_of_month(value):
    if value.month == 12:
        return date(value.year + 1, 1, 1) - timedelta(days=1)
    return date(value.year, value.month + 1, 1) - timedelta(days=1)


def _pct(numerator, denominator):
    """نسبة مئوية من base، أو None إذا كان الأساس صفراً."""
    if not denominator:
        return None
    return round(float(numerator) / float(denominator) * 100, 1)


def _ratio(numerator, denominator):
    """نسبة عددية (لا مئوية) — كمتوسط تكلفة الياردة."""
    if not denominator:
        return None
    return round(float(numerator) / float(denominator), 3)


def _change_pct(current, previous):
    """نسبة التغيّر عن الفترة السابقة، أو None إذا كانت الفترة السابقة صفراً."""
    if not previous:
        return None
    return round((float(current) - float(previous)) / abs(float(previous)) * 100, 1)


def _period_before(date_from, date_to):
    """الفترة السابقة المطابقة في الطول مباشرة قبل الفترة الحالية."""
    span = (date_to - date_from).days + 1
    prev_to = date_from - timedelta(days=1)
    prev_from = prev_to - timedelta(days=span - 1)
    return prev_from, prev_to


def _last_balance_per_series(qs, date_to, branch_ids=None):
    """آخر رصيد (balance_after) لكل سلسلة (مخزن × قماش) عند تاريخ معيّن.

    ``balance_after`` هو رصيد السلسلة بعد الحركة، فأخذ آخر حركة لكل سلسلة
    عند end-of-date يعطي رصيد الإقفال الصحيح. الحركات بلا رصيد مسجّل تُتجاهل
    لأنها لا يحملLastSnapshot لقيمته.
    """
    ids = set(qs.values_list("id", flat=True))
    if not ids:
        return {}
    last = {}
    # الترتيب تنازلي بالتاريخ ثم المعرّف: آخر حركة لكل سلسلة هي أول ما نراه.
    for mv_id, warehouse_id, fabric_id, balance in (
        qs.filter(date__lte=date_to, balance_after__isnull=False)
        .order_by("warehouse_id", "fabric_id", "-date", "-id")
        .values_list("id", "warehouse_id", "fabric_id", "balance_after")
    ):
        key = (warehouse_id, fabric_id)
        if key not in last:
            last[key] = balance
    return last


def _purchases(request, date_from, date_to, branch=None):
    """تكلفة المشتريات الفعلية في الفترة: قيم الاستلامات المرحّلة."""
    items_qs = scope_queryset_or(
        request,
        GoodsReceiptItem.objects.filter(
            receipt__status="posted",
            receipt__date__gte=date_from,
            receipt__date__lte=date_to,
        ),
        ["receipt__branch", "receipt__warehouse__branch"],
    )
    if branch:
        items_qs = items_qs.filter(
            Q(receipt__branch_id=branch) | Q(receipt__warehouse__branch_id=branch)
        )
    agg = items_qs.aggregate(value=Sum("total"), yards=Sum("yards"))
    return {
        "value": float(agg["value"] or 0),
        "yards": float(agg["yards"] or 0),
        "avg_cost": _ratio(agg["value"], agg["yards"]),
    }


def _closing_stock(request, date_to, branch=None, costs=None):
    """رصيد الإقفال بالياردة وقيمته عند نهاية الفترة.

    القيمة بمتوسط التكلفة المرجّح نفسه المستخدم في تكلفة البضاعة المباعة،
    حتى لا تختلط معاملات في نفس التقرير، ولو كان الرصيد غير مسجّل لأحد
    الأقسام تُحسب تكلفة صفراً (وهو ما تفعله تكلفة البضاعة المباعة أيضاً).
    """
    qs = scope_queryset(
        request,
        StockMovement.objects.filter(date__lte=date_to, balance_after__isnull=False),
        branch_field="warehouse__branch",
    )
    if branch:
        qs = qs.filter(warehouse__branch_id=branch)
    if costs is None:
        costs = fabric_average_costs()

    balances = _last_balance_per_series(qs, date_to)
    if not balances:
        return {"yards": 0.0, "value": 0.0}

    yards = 0.0
    value = 0.0
    for (_warehouse_id, fabric_id), balance in balances.items():
        b = float(balance or 0)
        if b <= 0:
            continue
        yards += b
        value += b * float(costs.get(fabric_id) or 0)
    return {"yards": round(yards, 2), "value": round(value, 2)}


class ProfitLossReportView(APIView):
    """الربح والخسارة بعد كل شيء: مبيعات - تكلفة البضاعة المباعة - رواتب - مصاريف.

    مع تفصيل لكل فرع (مبيعات / تكلفة / رواتب / مصاريف / صافي) للمقارنة بين الفروع.
    """
    permission_section = "reports"

    # ---------- بناء أرقام فترة واحدة ----------

    def _totals(self, request, date_from, date_to, branch=None, costs=None):
        sales_qs = scope_queryset(
            request, DailySale.objects.filter(
                date__gte=date_from, date__lte=date_to
            )
        )
        expense_qs = scope_queryset(
            request, Expense.objects.filter(
                date__gte=date_from, date__lte=date_to
            )
        )
        if branch:
            sales_qs = sales_qs.filter(branch_id=branch)
            expense_qs = expense_qs.filter(branch_id=branch)

        total_sales = sales_qs.aggregate(t=Sum("total_sales"))["t"] or 0
        total_expenses = expense_qs.aggregate(t=Sum("amount"))["t"] or 0
        cogs = _scoped_cogs(request, date_from, date_to, branch, costs)
        gross_profit = total_sales - cogs
        salaries, salaries_paid, _ = self._salaries(request, date_from, date_to, branch)
        net_profit = gross_profit - salaries - total_expenses

        return {
            "total_sales": money(total_sales),
            "cogs": money(cogs),
            "gross_profit": money(gross_profit),
            "salaries": money(salaries),
            "salaries_paid": money(salaries_paid),
            "expenses": money(total_expenses),
            "net_profit": money(net_profit),
            "gross_margin_pct": _pct(gross_profit, total_sales),
            "net_margin_pct": _pct(net_profit, total_sales),
        }

    def _salaries(self, request, date_from, date_to, branch=None):
        """الرواتب المستحقة (تكلفة المسيّرات المتداخلة مع الفترة) والمدفوعة فعلياً.

        المسيّر يغطي شهراً كاملاً، لذا نطابق تداخل الفواصل لا التطابق التام.
        """
        from payroll.models import Payslip, PayrollRun

        run_qs = scope_queryset(
            request,
            PayrollRun.objects.filter(month__lte=date_to)
            .exclude(status=PayrollRun.Status.CANCELLED),
            "branch",
        )
        if branch:
            run_qs = run_qs.filter(branch_id=branch)
        candidates = list(run_qs)
        run_ids = [r.id for r in candidates if _last_of_month(r.month) >= date_from]
        payslips_qs = Payslip.objects.filter(run_id__in=run_ids) if run_ids else Payslip.objects.none()
        if branch:
            payslips_qs = payslips_qs.filter(branch_id=branch)
        salaries = sum((p.net_pay for p in payslips_qs), Decimal("0"))

        # المدفوع فعلياً داخل الفترة (حسب تاريخ الصرف) — للمقارنة فقط.
        paid_run_ids = [
            r.id for r in candidates
            if (r.status == PayrollRun.Status.PAID and r.paid_at
                and date_from <= r.paid_at.date() <= date_to)
        ]
        paid_qs = Payslip.objects.filter(run_id__in=paid_run_ids) if paid_run_ids else Payslip.objects.none()
        if branch:
            paid_qs = paid_qs.filter(branch_id=branch)
        salaries_paid = sum((p.net_pay for p in paid_qs), Decimal("0"))
        return salaries, salaries_paid, payslips_qs

    def _collection(self, request, date_from, date_to, branch=None):
        """تفصيل المبيعات حسب طريقة التحصيل ونسبة التحصيل من إجمالي المبيعات."""
        qs = scope_queryset(
            request, DailySale.objects.filter(
                date__gte=date_from, date__lte=date_to
            )
        )
        if branch:
            qs = qs.filter(branch_id=branch)
        agg = qs.aggregate(
            total=Sum("total_sales"),
            cash=Sum("cash_amount"),
            transfer=Sum("transfer_amount"),
            card=Sum("card_amount"),
            other=Sum("other_amount"),
        )
        values = {k: float(agg[k] or 0) for k in ("cash", "transfer", "card", "other")}
        total = sum(values.values())
        sales = float(agg["total"] or 0)
        return {
            "cash": values["cash"],
            "transfer": values["transfer"],
            "card": values["card"],
            "other": values["other"],
            "collected": total,
            "sales": sales,
            "collection_rate_pct": _pct(total, sales),
        }

    def _expense_breakdown(self, request, date_from, date_to, branch=None):
        """المصاريف مجمّعة حسب التصنيف مع نسبة كل تصنيف من الإجمالي."""
        qs = scope_queryset(
            request, Expense.objects.filter(
                date__gte=date_from, date__lte=date_to
            )
        )
        if branch:
            qs = qs.filter(branch_id=branch)
        rows = (
            qs.values("category_id", "category__name")
            .annotate(amount=Sum("amount"))
            .order_by("-amount")
        )
        total = float(sum((r["amount"] or 0) for r in rows))
        items = [
            {
                "category_id": r["category_id"],
                "category_name": r["category__name"] or "غير مصنّف",
                "amount": float(r["amount"] or 0),
                "pct_of_total": _pct(r["amount"] or 0, total),
            }
            for r in rows
        ]
        return {"items": items, "total": total}

    def _branch_rows(self, request, date_from, date_to, branch=None, costs=None):
        """صافي كل فرع: مبيعات - تكلفة - رواتب - مصاريف.

        كل المجاميع محسوبة باستعلامات مجمّعة (GROUP BY) لا استعلام لكل فرع.
        """
        from payroll.models import Payslip

        row_branches = scope_queryset(request, Branch.objects.filter(is_active=True))
        if branch:
            row_branches = row_branches.filter(id=branch)
        row_branches = list(row_branches.order_by("name"))
        if not row_branches:
            return []
        ids = [b.id for b in row_branches]

        sales_by_branch = {
            r["branch_id"]: r["t"] or 0
            for r in DailySale.objects.filter(
                branch_id__in=ids, date__gte=date_from, date__lte=date_to
            ).values("branch_id").annotate(t=Sum("total_sales"))
        }
        expenses_by_branch = {
            r["branch_id"]: r["t"] or 0
            for r in Expense.objects.filter(
                branch_id__in=ids, date__gte=date_from, date__lte=date_to
            ).values("branch_id").annotate(t=Sum("amount"))
        }
        # branch_ids هنا قائمة صريحة، فنمرّرها كما هي إلى cogs_by_day_branch.
        cogs_by_branch = defaultdict(Decimal)
        for (_day, bid), value in cogs_by_day_branch(date_from, date_to, ids, costs).items():
            cogs_by_branch[bid] += value

        _, _, payslips_qs = self._salaries(request, date_from, date_to, branch)
        salaries_by_branch = {
            r["branch_id"]: r["t"] or 0
            for r in payslips_qs.values("branch_id").annotate(
                t=Sum(Payslip.net_pay_expression())
            )
        }

        rows = []
        for b in row_branches:
            bs = sales_by_branch.get(b.id, 0)
            bcogs = cogs_by_branch.get(b.id, Decimal("0"))
            bsal = salaries_by_branch.get(b.id, 0)
            be = expenses_by_branch.get(b.id, 0)
            net = bs - bcogs - bsal - be
            rows.append({
                "branch": b.id,
                "branch_name": b.name,
                "sales": money(bs),
                "cogs": money(bcogs),
                "salaries": money(bsal),
                "expenses": money(be),
                "net": money(net),
                "net_margin_pct": _pct(net, bs),
            })
        return rows

    def _daily_rows(self, request, date_from, date_to, branch=None, costs=None):
        """صافي كل يوم: مبيعات - تكلفة البضاعة المباعة - مصاريف.

        الرواتب لا تُوزَّع على الأيام لأنها تخص شهراً كاملاً، فتبقى في البنود العامة.
        """
        sale_qs = scope_queryset(
            request, DailySale.objects.filter(
                date__gte=date_from, date__lte=date_to
            )
        )
        exp_qs = scope_queryset(
            request, Expense.objects.filter(
                date__gte=date_from, date__lte=date_to
            )
        )
        if branch:
            sale_qs = sale_qs.filter(branch_id=branch)
            exp_qs = exp_qs.filter(branch_id=branch)

        sales_by_day = defaultdict(float)
        for day, value in sale_qs.values_list("date", "total_sales"):
            sales_by_day[day] += float(value or 0)
        exp_by_day = defaultdict(float)
        for day, value in exp_qs.values_list("date", "amount"):
            exp_by_day[day] += float(value or 0)

        cogs_by_day = defaultdict(float)
        allowed = _scoped_branch_ids(request, branch)
        # [None] تعني «كل الفروع» و cogs_by_day_branch تتوقع None أو قائمة معرّفات.
        branch_ids = None if allowed == [None] else [b for b in allowed if b is not None]
        for (day, _bid), value in cogs_by_day_branch(
            date_from, date_to, branch_ids, costs
        ).items():
            cogs_by_day[day] += float(value)

        rows = []
        for day in sorted(set(sales_by_day) | set(exp_by_day) | set(cogs_by_day)):
            s = sales_by_day[day]
            c = cogs_by_day[day]
            e = exp_by_day[day]
            rows.append({
                "date": day.isoformat(),
                "sales": round(s, 2),
                "cogs": round(c, 2),
                "gross_profit": round(s - c, 2),
                "expenses": round(e, 2),
                "net": round(s - c - e, 2),
                "net_margin_pct": _pct(s - c - e, s),
            })
        return rows

    # ---------- الاستجابة ----------

    def get(self, request):
        date_from, date_to = _report_dates(request)
        branch = request.query_params.get("branch")

        # خريطة متوسطات التكلفة تُحسب مرة واحدة وتُعاد لكل الأقسام:
        # fabric_average_costs تمسح كل الاستلامات والأرصدة الافتتاحية، فاستدعاؤها
        # لكل فرع/يوم/فترة سابقة يحوّل التقرير إلى استعلامات مربّعة.
        costs = fabric_average_costs()

        totals = self._totals(request, date_from, date_to, branch, costs)
        collection = self._collection(request, date_from, date_to, branch)
        expenses = self._expense_breakdown(request, date_from, date_to, branch)
        branch_rows = self._branch_rows(request, date_from, date_to, branch, costs)
        daily = self._daily_rows(request, date_from, date_to, branch, costs)

        # مقارنة مع الفترة السابقة المطابقة في الطول.
        prev_from, prev_to = _period_before(date_from, date_to)
        prev = self._totals(request, prev_from, prev_to, branch, costs)
        comparison = {
            "date_from": prev_from.isoformat(),
            "date_to": prev_to.isoformat(),
            "totals": prev,
            "change_pct": {
                key: _change_pct(totals[key], prev[key])
                for key in (
                    "total_sales", "cogs", "gross_profit",
                    "salaries", "expenses", "net_profit",
                )
            },
        }

        purchases = _purchases(request, date_from, date_to, branch)
        closing = _closing_stock(request, date_to, branch, costs)
        # بضاعة لم تُبَع بعد: ما اشتريناه في الفترة ناقص ما خرج بالبيع منها.
        # كان الحساب يقارن رصيداً (قيمة المخزون آخر الشهر) بتدفّق (تكلفة المبيعات)،
        # فينتج رقم لا معنى له ويصبح سالباً في أول شهر تشغيلي أو في أي شهر يبيع
        # مخزوناً قديمة أكثر مما يشتري. والسالب هنا له معنى: المخزون نقص.
        unsold_value = purchases["value"] - totals["cogs"]
        stock = {
            "purchases": purchases,
            "closing": closing,
            "unsold_value": round(unsold_value, 2),
            "unsold_margin_pct": _pct(unsold_value, purchases["value"]),
        }

        if request.query_params.get("export") == "xlsx":
            return self._export_xlsx(
                totals, comparison, collection, expenses, branch_rows, daily, stock,
                date_from, date_to,
            )

        return Response({
            "start_date": date_from.isoformat(),
            "end_date": date_to.isoformat(),
            "totals": totals,
            "comparison": comparison,
            "collection": collection,
            "expense_breakdown": expenses,
            "stock": stock,
            "branches": branch_rows,
            "daily": daily,
        })

    def _export_xlsx(
        self, totals, comparison, collection, expenses, branch_rows, daily, stock,
        date_from=None, date_to=None,
    ):
        change = comparison["change_pct"]

        def _line(label, key):
            pct = change.get(key)
            return [
                label,
                round(totals[key], 2),
                round(comparison["totals"][key], 2),
                f"{pct:+.1f}%" if pct is not None else "—",
            ]

        # السطر التوضيحي يحمل الفترة والمقارنة: الملف يحمل رقمين من فترتين
        # مختلفتين، ولا يعرف من يفتحه لاحقاً أيّهما الحالي.
        period = ""
        if date_from and date_to:
            period = (
                f"الفترة: {date_from.isoformat()} إلى {date_to.isoformat()}"
                f"  |  الفترة السابقة للمقارنة"
            )

        headers = ["البيان", "الفترة الحالية", "الفترة السابقة", "نسبة التغيّر"]
        rows_x = [
            _line("إجمالي المبيعات", "total_sales"),
            _line("تكلفة البضاعة المباعة", "cogs"),
            _line("مجمل الربح", "gross_profit"),
            _line("الرواتب (شهر الفترة)", "salaries"),
            _line("المصاريف", "expenses"),
            _line("صافي الربح بعد كل شيء", "net_profit"),
            ["الرواتب المدفوعة فعلياً", round(totals["salaries_paid"], 2), "", ""],
            ["هامش مجمل الربح %", totals["gross_margin_pct"] or 0, "", ""],
            ["هامش صافي الربح %", totals["net_margin_pct"] or 0, "", ""],
        ]
        # بنود المخزون تُكتب في ورقة منفصلة: هي معلومات عن رأس المال لا عن
        # نتيجة الفترة، وخلطها في قائمة الدخل يربك القراءة.
        stock_rows = [
            ["تكلفة المشتريات (استلامات مرحّلة)", round(stock["purchases"]["value"], 2)],
            ["الياردات المشتراة", round(stock["purchases"]["yards"], 2)],
            ["متوسط تكلفة الياردة المشتراة", stock["purchases"]["avg_cost"] or 0],
            ["رصيد الإقفال بالياردة", round(stock["closing"]["yards"], 2)],
            ["قيمة رصيد الإقفال", round(stock["closing"]["value"], 2)],
            ["قيمة البضاعة غير المباعة", round(stock["unsold_value"], 2)],
        ]

        branch_rows_x = [
            [r["branch_name"], round(r["sales"], 2), round(r["cogs"], 2),
             round(r["salaries"], 2), round(r["expenses"], 2),
             round(r["net"], 2), r["net_margin_pct"]] for r in branch_rows
        ]
        if branch_rows_x:
            branch_rows_x.append([
                "الإجمالي",
                round(sum(r["sales"] for r in branch_rows), 2),
                round(sum(r["cogs"] for r in branch_rows), 2),
                round(sum(r["salaries"] for r in branch_rows), 2),
                round(sum(r["expenses"] for r in branch_rows), 2),
                round(sum(r["net"] for r in branch_rows), 2),
                "",
            ])

        expense_rows_x = [
            [r["category_name"], round(r["amount"], 2), r["pct_of_total"]]
            for r in expenses["items"]
        ]
        if expense_rows_x:
            expense_rows_x.append([
                "الإجمالي",
                round(sum(r["amount"] for r in expenses["items"]), 2),
                100.0,
            ])

        collection_rows = [
            ["نقدي", round(collection["cash"], 2), _pct(collection["cash"], collection["sales"])],
            ["تحويل", round(collection["transfer"], 2), _pct(collection["transfer"], collection["sales"])],
            ["بطاقة", round(collection["card"], 2), _pct(collection["card"], collection["sales"])],
            ["أخرى", round(collection["other"], 2), _pct(collection["other"], collection["sales"])],
            ["إجمالي المحصّل", round(collection["collected"], 2), collection["collection_rate_pct"] or 0],
        ]

        daily_rows_x = [
            [r["date"], r["sales"], r["cogs"], r["gross_profit"], r["expenses"],
             r["net"], r["net_margin_pct"]] for r in daily
        ]
        if daily_rows_x:
            daily_rows_x.append([
                "الإجمالي",
                round(sum(r["sales"] for r in daily), 2),
                round(sum(r["cogs"] for r in daily), 2),
                round(sum(r["gross_profit"] for r in daily), 2),
                round(sum(r["expenses"] for r in daily), 2),
                round(sum(r["net"] for r in daily), 2),
                "",
            ])

        wb = excel.build_workbook([
            {
                "title": "الربح والخسارة بعد كل شيء",
                "columns": [
                    {"label": "البيان", "type": "text"},
                    {"label": "الفترة الحالية", "type": "money"},
                    {"label": "الفترة السابقة", "type": "money"},
                    {"label": "نسبة التغيّر", "type": "text"},
                ],
                "rows": rows_x,
                "heading": "تقرير الربح والخسارة",
                "subtitle": period,
            },
            {
                "title": "حسب الفرع",
                "columns": [
                    {"label": "الفرع", "type": "text"},
                    {"label": "المبيعات", "type": "money"},
                    {"label": "التكلفة", "type": "money"},
                    {"label": "الرواتب", "type": "money"},
                    {"label": "المصاريف", "type": "money"},
                    {"label": "الصافي", "type": "money"},
                    {"label": "هامش الصافي %", "type": "percent"},
                ],
                "rows": branch_rows_x,
                "subtitle": period,
            },
            {
                "title": "تفصيل المصاريف",
                "columns": [
                    {"label": "التصنيف", "type": "text"},
                    {"label": "المبلغ", "type": "money"},
                    {"label": "النسبة %", "type": "percent"},
                ],
                "rows": expense_rows_x,
                "subtitle": period,
            },
            {
                "title": "تفصيل التحصيل",
                "columns": [
                    {"label": "طريقة التحصيل", "type": "text"},
                    {"label": "المبلغ", "type": "money"},
                    {"label": "النسبة من المبيعات %", "type": "percent"},
                ],
                "rows": collection_rows,
                "subtitle": period,
            },
            {
                "title": "التفصيل اليومي",
                "columns": [
                    {"label": "التاريخ", "type": "date"},
                    {"label": "المبيعات", "type": "money"},
                    {"label": "تكلفة البضاعة المباعة", "type": "money"},
                    {"label": "مجمل الربح", "type": "money"},
                    {"label": "المصاريف", "type": "money"},
                    {"label": "الصافي", "type": "money"},
                    {"label": "هامش الصافي %", "type": "percent"},
                ],
                "rows": daily_rows_x,
                "subtitle": period,
            },
            {
                "title": "المشتريات والمخزون",
                "columns": [
                    {"label": "البيان", "type": "text"},
                    {"label": "القيمة", "type": "money"},
                ],
                "rows": stock_rows,
                "subtitle": period,
            },
        ])
        return _xlsx_response(wb, "تقرير_الربح_والخسارة")


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
                "total_yards": Decimal("0"),
                "total_pieces": Decimal("0"),
                "returned_items": 0,
            })
            entry["sessions_count"] += 1
            entry["total_sales"] += sum(r.total for r in s.items.all())
            entry["total_commission"] += s.commission_amount or Decimal("0")
            # التعريف في `sale_sessions.services.item_pieces` وحده: لقطعتان في
            # المشروع تذكران «القطع» — هذا التقرير وتوزيع المبيعات على الموظفين —
            # ولو اختلفتاه لقابل الموظف رقمين مختلفين لنفس البيع.
            for item in s.items.all():
                if item.is_returned:
                    entry["returned_items"] += 1
                    continue
                entry["total_yards"] += (
                    item.quantity * PIECE_YARDS
                    if item.sale_type == SaleSessionItem.SaleType.ROLL
                    else item.quantity
                )
                entry["total_pieces"] += item_pieces(item)

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
                "total_yards": float(entry["total_yards"]),
                "total_pieces": float(entry["total_pieces"]),
                "returned_items": entry["returned_items"],
            })
        # الأعلى مبيعاً أولاً: جدول التوزيع يُقرأ من أول سطر لا من وسطه.
        data.sort(key=lambda d: (-d["total_sales"], d["employee_name"]))


        totals = {
            "sessions": sum(d["sessions_count"] for d in data),
            "sales": float(sum(d["total_sales"] for d in data)),
            "commission": float(sum(d["total_commission"] for d in data)),
            "pieces": float(sum(d["total_pieces"] for d in data)),
            "yards": float(sum(d["total_yards"] for d in data)),
            "employees": len(data),
        }

        if request.query_params.get("export") == "xlsx":
            headers = [
                "الموظف", "الفرع", "عدد الورديات", "عدد القطع", "عدد الياردات",
                "إجمالي المبيعات", "العمولة",
            ]
            rows_x = [[
                d["employee_name"], d["branch_name"], d["sessions_count"],
                round(d["total_pieces"], 2), round(d["total_yards"], 2),
                d["total_sales"], d["total_commission"],
            ] for d in data]
            rows_x.append([
                "الإجمالي", "", totals["sessions"], round(totals["pieces"], 2),
                round(totals["yards"], 2), totals["sales"], totals["commission"],
            ])
            wb = _export_generic_to_xlsx(
                "عمولات المبيعات", headers, rows_x,
                types=["text", "text", "number", "number", "number", "money", "money"],
                subtitle=(
                    f"الفترة: {month_start.isoformat()} إلى {month_end.isoformat()}"
                    f"  |  عدد الموظفين: {totals['employees']}"
                ),
            )
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
            # مجموع العمود «الصافي» لا يساوي الرصيد التراكمي الأخير إلا إذا
            # بدأ الرصيد من صفر — وهذا بالضبط ما يُراجَع به السجل.
            rows_x.append([
                "الإجمالي", totals["sales"], totals["purchases"], totals["expenses"],
                totals["support"], totals["withdraw"], totals["net"], "",
            ])
            wb = _export_generic_to_xlsx(
                "القيود اليومية", headers, rows_x,
                types=["date"] + ["money"] * 7,
                subtitle=(
                    f"الفترة: {date_from.isoformat()} إلى {date_to.isoformat()}"
                    f"  |  عدد الأيام: {len(journal)}"
                ),
            )
            if wb is None:
                return Response({"detail": "مكتبة openpyxl غير مثبتة"}, status=500)
            return _xlsx_response(wb, "تقرير_القيود_اليومية")

        return Response({
            "journal": journal,
            "totals": totals,
            "start_date": date_from.isoformat(),
            "end_date": date_to.isoformat(),
        })
