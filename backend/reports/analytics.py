"""مولّدات التقارير التحليلية (Reports V2).

كل تقرير يُرجع «مظروفاً» موحّداً:
{
  key, title, group_by, period, previous,
  columns: [{key, label, type, total?}],
  rows:    [{...}],
  totals:  {...},
  kpis:    [{key, label, value, previous, change_pct, type}],
  series:  {labels, current, previous}   # للرسم البياني
}

هذا يتيح للواجهة عرض أي تقرير بجدول ورسم واحد دون تكرار.
"""

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone

from core.branch_scope import allowed_branch_ids
from expenses.models import Expense
from partners.models import PartnerOperation
from sale_sessions.models import SaleSession
from sales.models import DailySale, DailySaleItem
from suppliers.models import Fabric, LedgerEntry
from warehouses.models import FabricRoll

from .cogs import fabric_average_costs

ZERO = Decimal("0")
MONEY = Decimal("0.01")
MAX_BUCKETS = 400

GROUPINGS = {
    "day": ("يومي", lambda d: d),
    "week": ("أسبوعي", lambda d: d - timedelta(days=d.weekday())),
    "month": ("شهري", lambda d: d.replace(day=1)),
}

AGING_BUCKETS = [
    ("not_due", "غير مستحق", 0, 0),
    ("d1_30", "منذ 1-30 يوم", 1, 30),
    ("d31_60", "منذ 31-60 يوم", 31, 60),
    ("d61_90", "منذ 61-90 يوم", 61, 90),
    ("over_90", "أكثر من 90 يوم", 91, None),
]


# ---------------------------------------------------------------------------
# أدوات عامة
# ---------------------------------------------------------------------------


def q2(value):
    return Decimal(str(value if value is not None else 0)).quantize(MONEY)


def pct(part, whole):
    """نسبة مئوية آمنة من القسمة على صفر."""
    if not whole:
        return 0.0
    return float((Decimal(str(part)) / Decimal(str(whole)) * 100).quantize(Decimal("0.1")))


def in_scope(queryset, request, field="branch_id"):
    """يقصّ الاستعلام على فروع الموظف (None = الكل، none() = لا شيء).

    يُطبَّق أيضاً `?branch=` من الواجهة، ولا يتجاوز أبداً نطاق المستخدم.
    """
    allowed = allowed_branch_ids(request)
    requested = (request.query_params.get("branch") or "").strip()
    if requested:
        try:
            wanted = int(requested)
        except ValueError:
            return queryset.none()
        if allowed is None:
            allowed = [wanted]
        else:
            allowed = [b for b in allowed if b == wanted]
    if allowed is None:
        return queryset
    if not allowed:
        return queryset.none()
    return queryset.filter(**{f"{field}__in": allowed})


def period(request, default_days=30):
    """(من، إلى، من السابق، إلى السابق) مع تصحيح الترتيب."""
    today = timezone.localdate()
    try:
        date_from = date.fromisoformat(request.query_params.get("date_from") or "")
    except ValueError:
        date_from = today - timedelta(days=default_days - 1)
    try:
        date_to = date.fromisoformat(request.query_params.get("date_to") or "")
    except ValueError:
        date_to = today
    if date_from > date_to:
        date_from, date_to = date_to, date_from
    span = (date_to - date_from).days + 1
    prev_to = date_from - timedelta(days=1)
    return date_from, date_to, prev_to - timedelta(days=span - 1), prev_to


def group_by(request, date_from, date_to):
    """يختار تجميعاً تلقائياً حسب طول الفترة إن لم يُحدَّد."""
    key = (request.query_params.get("group_by") or "").strip()
    if key not in GROUPINGS:
        span = (date_to - date_from).days + 1
        key = "day" if span <= 62 else ("week" if span <= 186 else "month")
    return key, GROUPINGS[key][0], GROUPINGS[key][1]


def bucket_start(value, grouper):
    return grouper(value)


def bucket_range(date_from, date_to, grouper):
    """كل بدايات الفترات بين تاريخين (مع ملء الفجوات)."""
    keys, current, guard = [], bucket_start(date_from, grouper), 0
    while current <= date_to and guard < MAX_BUCKETS:
        keys.append(current)
        nxt = (current + timedelta(days=7)) if current.weekday() == 6 else current + timedelta(days=1)
        current = bucket_start(nxt, grouper)
        guard += 1
    return keys


def bucket_label(value, key):
    if key == "month":
        return f"{value:%Y-%m}"
    if key == "week":
        return f"{value:%Y-%m-%d}"
    return value.isoformat()


def change_pct(current, previous):
    """نسبة التغيّر عن الفترة السابقة (النِّسب تُرجع 100 عند انعدام الأساس)."""
    cur, prev = q2(current), q2(previous)
    if prev == 0:
        return 100.0 if cur > 0 else 0.0
    return float(((cur - prev) / abs(prev) * 100).quantize(Decimal("0.1")))


def column(key, label, type_="money", total=False, width=None):
    col = {"key": key, "label": label, "type": type_, "total": total}
    if width:
        col["width"] = width
    return col


def kpi(key, label, value, previous=None, type_="money"):
    return {
        "key": key,
        "label": label,
        "type": type_,
        "value": float(q2(value)),
        "previous": float(q2(previous)) if previous is not None else None,
        "change_pct": change_pct(value, previous) if previous is not None else None,
    }


def envelope(
    key, title, columns, rows, totals=None, kpis=None,
    period_=None, previous=None, group=None, series=None, meta=None,
):
    payload = {
        "key": key,
        "title": title,
        "group_by": group or "",
        "columns": columns,
        "rows": rows,
        "totals": totals or {},
        "kpis": kpis or [],
        "series": series,
        "meta": meta or {},
    }
    if period_:
        payload["period"] = {"from": period_[0].isoformat(), "to": period_[1].isoformat()}
    if previous:
        payload["previous"] = {"from": previous[0].isoformat(), "to": previous[1].isoformat()}
    return payload


def xlsx_rows(columns, rows, totals=None):
    """يحوّل المظروف إلى صفوف جاهزة لـExcel."""
    def fmt(col, value):
        if col["type"] == "money":
            return float(q2(value))
        if col["type"] == "number":
            return float(value or 0)
        if col["type"] == "percent":
            return round(float(value or 0), 1)
        return value

    out = [[c["label"] for c in columns]]
    for row in rows:
        out.append([fmt(c, row.get(c["key"])) for c in columns])
    if totals:
        out.append(["الإجمالي"] + [
            fmt(col, totals.get(col["key"], 0)) if col.get("total") else ""
            for col in columns[1:]
        ])
    return out


# ---------------------------------------------------------------------------
# أعمار الديون (توزيع الدفعات على أقدم الالتزامات)
# ---------------------------------------------------------------------------


def empty_buckets():
    return {key: ZERO for key, _label, _lo, _hi in AGING_BUCKETS}


def bucket_of(days):
    for key, label, low, high in AGING_BUCKETS:
        if days >= low and (high is None or days <= high):
            return key, label
    return "over_90", "أكثر من 90 يوم"


def allocate(entries, today):
    """entries = [(تاريخ، مبلغ موجب=التزام، سالب=سداد)] → توزيع ما لم يُسدَّد."""
    buckets, open_items = empty_buckets(), []
    for when, amount in entries:
        amount = q2(amount)
        if amount > 0:
            open_items.append([when, amount])
        elif amount < 0:
            remaining = -amount
            for item in open_items:
                if remaining <= 0:
                    break
                take = min(item[1], remaining)
                item[1] -= take
                remaining -= take
            open_items = [i for i in open_items if i[1] > 0]
    oldest = None
    for when, amount in open_items:
        key, _label = bucket_of((today - when).days)
        buckets[key] += amount
        if oldest is None or when < oldest:
            oldest = when
    return buckets, oldest


# ---------------------------------------------------------------------------
# مبيعات وتكلفة البيع
# ---------------------------------------------------------------------------


def sales_totals(request, date_from, date_to, branch_id=None):
    qs = in_scope(DailySale.objects.all(), request)
    qs = qs.filter(date__gte=date_from, date__lte=date_to)
    if branch_id:
        qs = qs.filter(branch_id=branch_id)
    totals = defaultdict(lambda: ZERO)
    rows = 0
    for sale in qs:
        rows += 1
        totals["total"] += sale.total_sales
        totals["cash"] += sale.cash_amount
        totals["transfer"] += sale.transfer_amount
        totals["card"] += sale.card_amount
        totals["other"] += sale.other_amount
    totals["count"] = rows
    return totals


def expense_totals(request, date_from, date_to, branch_id=None):
    qs = in_scope(Expense.objects.all(), request)
    qs = qs.filter(date__gte=date_from, date__lte=date_to)
    if branch_id:
        qs = qs.filter(branch_id=branch_id)
    totals = defaultdict(lambda: ZERO)
    rows = 0
    for expense in qs:
        rows += 1
        totals["total"] += expense.amount
        if expense.payment_method == "cash":
            totals["cash"] += expense.amount
    totals["count"] = rows
    return totals


def sold_and_cogs(request, date_from, date_to, branch_id=None):
    """(ياردات مباعة، تكلفة مباعة) لكل قماش ضمن نطاق الفروع."""
    qs = DailySaleItem.objects.filter(
        sale__date__gte=date_from, sale__date__lte=date_to
    )
    qs = in_scope(qs, request, "sale__branch_id")
    if branch_id:
        qs = qs.filter(sale__branch_id=branch_id)
    sold = defaultdict(lambda: ZERO)
    for fid, yards in qs.values_list("fabric_id", "yards"):
        sold[fid] += yards
    costs = fabric_average_costs()
    cogs = {fid: q2((costs.get(fid) or ZERO) * yards) for fid, yards in sold.items()}
    return sold, cogs


def sessions_totals(request, date_from, date_to, branch_id=None):
    qs = in_scope(
        SaleSession.objects.filter(status=SaleSession.Status.CLOSED), request
    ).filter(closed_at__date__gte=date_from, closed_at__date__lte=date_to)
    if branch_id:
        qs = qs.filter(branch_id=branch_id)
    return {
        "count": qs.count(),
        "commission": q2(sum((s.commission_amount for s in qs), ZERO)),
    }


# ---------------------------------------------------------------------------
# 1) مؤشرات الأداء العامة
# ---------------------------------------------------------------------------


def kpi_summary(request, date_from, date_to, prev_from, prev_to):
    def snapshot(f, t):
        sales = sales_totals(request, f, t)
        expenses = expense_totals(request, f, t)
        sold, cogs_map = sold_and_cogs(request, f, t)
        cogs = sum(cogs_map.values(), ZERO)
        sessions = sessions_totals(request, f, t)
        return {
            "sales": sales["total"],
            "expenses": expenses["total"],
            "cogs": cogs,
            "net": sales["total"] - expenses["total"],
            "gross": sales["total"] - cogs,
            "sessions": sessions["count"],
            "yards": sum(sold.values(), ZERO),
        }

    cur, prev = snapshot(date_from, date_to), snapshot(prev_from, prev_to)
    margin = (cur["gross"] / cur["sales"] * 100) if cur["sales"] else ZERO
    prev_margin = (prev["gross"] / prev["sales"] * 100) if prev["sales"] else ZERO
    cards = [
        kpi("sales", "إجمالي المبيعات", cur["sales"], prev["sales"]),
        kpi("expenses", "المصاريف", cur["expenses"], prev["expenses"]),
        kpi("net", "صافي الفرق", cur["net"], prev["net"]),
        kpi("cogs", "تكلفة البضاعة المباعة", cur["cogs"], prev["cogs"]),
        kpi("gross", "مجمل الربح", cur["gross"], prev["gross"]),
        kpi("margin", "هامش الربح %", margin, prev_margin, type_="percent"),
        kpi("sessions", "الورديات المغلقة", cur["sessions"], prev["sessions"], type_="number"),
        kpi("yards", "الياردات المباعة", cur["yards"], prev["yards"], type_="number"),
    ]
    return envelope(
        "summary", "مؤشرات الأداء",
        columns=[], rows=[], kpis=cards,
        period_=(date_from, date_to), previous=(prev_from, prev_to),
    )


# ---------------------------------------------------------------------------
# 2) تطور المبيعات
# ---------------------------------------------------------------------------


def sales_trend(request, date_from, date_to, prev_from, prev_to):
    key, label, grouper = group_by(request, date_from, date_to)
    current_keys = bucket_range(date_from, date_to, grouper)
    span = len(current_keys)
    previous_keys = bucket_range(prev_from, prev_to, grouper)

    def collect(f, t, keys):
        qs = in_scope(DailySale.objects.all(), request).filter(date__gte=f, date__lte=t)
        acc = defaultdict(lambda: {"total": ZERO, "cash": ZERO, "transfer": ZERO, "card": ZERO, "other": ZERO, "count": 0})
        for sale in qs:
            slot = acc[bucket_start(sale.date, grouper)]
            slot["total"] += sale.total_sales
            slot["cash"] += sale.cash_amount
            slot["transfer"] += sale.transfer_amount
            slot["card"] += sale.card_amount
            slot["other"] += sale.other_amount
            slot["count"] += 1
        return acc, keys

    cur_acc, cur_keys = collect(date_from, date_to, current_keys)
    prev_acc, prev_keys = collect(prev_from, prev_to, previous_keys)

    def series_of(acc, keys, index=None):
        out = []
        for i, k in enumerate(keys):
            if index is not None and i >= index:
                out.append(0.0)
                continue
            out.append(float(q2(acc.get(k, {}).get("total", ZERO))))
        return out

    cur_series = series_of(cur_acc, cur_keys)
    prev_series = series_of(prev_acc, prev_keys, len(cur_keys))

    rows = []
    for i, k in enumerate(cur_keys):
        slot = cur_acc.get(k, {})
        total = q2(slot.get("total", ZERO))
        count = slot.get("count", 0)
        rows.append({
            "period": bucket_label(k, key),
            "total_sales": float(total),
            "cash": float(q2(slot.get("cash", ZERO))),
            "transfer": float(q2(slot.get("transfer", ZERO))),
            "card": float(q2(slot.get("card", ZERO))),
            "other": float(q2(slot.get("other", ZERO))),
            "invoices": count,
            "avg_ticket": float(q2(total / count)) if count else 0.0,
        })

    cur_total = sum((r["total_sales"] for r in rows), 0.0)
    prev_total = sum(prev_series, 0.0)
    invoices = sum(r["invoices"] for r in rows)
    columns = [
        column("period", "الفترة", "text"),
        column("total_sales", "إجمالي المبيعات", total=True),
        column("cash", "نقدي"),
        column("transfer", "تحويل"),
        column("card", "ماكينة"),
        column("other", "أخرى"),
        column("invoices", "عدد الأيام/الفواتير", "number"),
        column("avg_ticket", "متوسط الفاتورة"),
    ]
    return envelope(
        "sales-trend", f"تطور المبيعات ({label})",
        columns, rows,
        totals={"total_sales": q2(cur_total), "invoices": invoices,
                "avg_ticket": q2(cur_total / invoices) if invoices else ZERO},
        kpis=[
            kpi("total", "إجمالي المبيعات", cur_total, prev_total),
            kpi("avg", "متوسط الفاتورة", (cur_total / invoices) if invoices else 0,
                (prev_total / max(len([v for v in prev_series if v]), 1)) if prev_total else 0),
        ],
        period_=(date_from, date_to), previous=(prev_from, prev_to),
        group=key,
        series={"labels": [r["period"] for r in rows], "current": cur_series, "previous": prev_series},
    )


# ---------------------------------------------------------------------------
# 3) أداء الفروع
# ---------------------------------------------------------------------------


def branch_performance(request, date_from, date_to, prev_from, prev_to):
    from branches.models import Branch

    branches = {b.id: b for b in in_scope(Branch.objects.all(), request)}
    rows = []
    for bid, branch in branches.items():
        cur_sales = sales_totals(request, date_from, date_to, bid)
        prev_sales = sales_totals(request, prev_from, prev_to, bid)
        expenses = expense_totals(request, date_from, date_to, bid)
        _sold, cogs_map = sold_and_cogs(request, date_from, date_to, bid)
        cogs = sum(cogs_map.values(), ZERO)
        sessions = sessions_totals(request, date_from, date_to, bid)
        sales = cur_sales["total"]
        gross = sales - cogs
        net = sales - expenses["total"]
        rows.append({
            "branch": bid,
            "branch_name": branch.name,
            "sales": float(q2(sales)),
            "previous_sales": float(q2(prev_sales["total"])),
            "change_pct": change_pct(sales, prev_sales["total"]),
            "cogs": float(q2(cogs)),
            "gross": float(q2(gross)),
            "margin": pct(gross, sales),
            "expenses": float(q2(expenses["total"])),
            "net": float(q2(net)),
            "sessions": sessions["count"],
            "commission": float(sessions["commission"]),
        })
    rows.sort(key=lambda r: r["sales"], reverse=True)
    total_sales = sum(r["sales"] for r in rows)
    for row in rows:
        row["share"] = pct(row["sales"], total_sales)
    rows.sort(key=lambda r: r["sales"], reverse=True)
    columns = [
        column("branch_name", "الفرع", "text"),
        column("sales", "المبيعات", total=True),
        column("previous_sales", "السابقة"),
        column("change_pct", "التغيّر %", "percent"),
        column("share", "الحصة %", "percent"),
        column("cogs", "تكلفة البضاعة"),
        column("gross", "مجمل الربح", total=True),
        column("margin", "الهامش %", "percent"),
        column("expenses", "المصاريف"),
        column("net", "الصافي", total=True),
        column("sessions", "الورديات", "number"),
        column("commission", "العمولات"),
    ]
    return envelope(
        "branch-performance", "أداء الفروع",
        columns, rows,
        totals={
            "sales": q2(total_sales),
            "gross": q2(sum(r["gross"] for r in rows)),
            "expenses": q2(sum(r["expenses"] for r in rows)),
            "net": q2(sum(r["net"] for r in rows)),
        },
        kpis=[
            kpi("sales", "مبيعات الفروع", total_sales, sum(r["previous_sales"] for r in rows)),
            kpi("branches", "عدد الفروع النشطة", len(rows), type_="number"),
        ],
        period_=(date_from, date_to), previous=(prev_from, prev_to),
    )


# ---------------------------------------------------------------------------
# 4) أداء الموظفين
# ---------------------------------------------------------------------------


def employee_performance(request, date_from, date_to, prev_from, prev_to):
    sales_acc, session_acc, commission_acc = defaultdict(lambda: ZERO), defaultdict(int), defaultdict(lambda: ZERO)
    yards_acc = defaultdict(lambda: ZERO)

    for session in in_scope(
        SaleSession.objects.filter(status=SaleSession.Status.CLOSED), request
    ).filter(closed_at__date__gte=date_from, closed_at__date__lte=date_to):
        session_acc[session.employee_id] += 1
        commission_acc[session.employee_id] += session.commission_amount

    prev_commission = defaultdict(lambda: ZERO)
    for session in in_scope(
        SaleSession.objects.filter(status=SaleSession.Status.CLOSED), request
    ).filter(closed_at__date__gte=prev_from, closed_at__date__lte=prev_to):
        prev_commission[session.employee_id] += session.commission_amount

    for sale in in_scope(DailySale.objects.select_related("employee"), request).filter(
        date__gte=date_from, date__lte=date_to
    ):
        if sale.employee_id:
            sales_acc[sale.employee_id] += sale.total_sales
    for item in in_scope(
        DailySaleItem.objects.select_related("sale__employee"), request, "sale__branch_id"
    ).filter(sale__date__gte=date_from, sale__date__lte=date_to):
        if item.sale.employee_id:
            yards_acc[item.sale.employee_id] += item.yards

    from sale_sessions.models import Employee

    employees = {
        e.id: e for e in Employee.objects.filter(id__in=set(sales_acc) | set(session_acc))
    }
    rows = []
    for eid, employee in employees.items():
        sales = sales_acc.get(eid, ZERO)
        sessions = session_acc.get(eid, 0)
        rows.append({
            "employee": eid,
            "employee_name": employee.name,
            "branch_name": employee.branch.name if employee.branch_id else "",
            "sales": float(q2(sales)),
            "sessions": sessions,
            "yards": float(q2(yards_acc.get(eid, ZERO))),
            "commission": float(q2(commission_acc.get(eid, ZERO))),
            "previous_commission": float(q2(prev_commission.get(eid, ZERO))),
            "avg_ticket": float(q2(sales / sessions)) if sessions else 0.0,
        })
    rows.sort(key=lambda r: r["sales"], reverse=True)
    total_sales = sum(r["sales"] for r in rows)
    total_commission = sum(r["commission"] for r in rows)
    columns = [
        column("employee_name", "الموظف", "text"),
        column("branch_name", "الفرع", "text"),
        column("sales", "المبيعات", total=True),
        column("sessions", "الورديات", "number"),
        column("yards", "الياردات", "number"),
        column("avg_ticket", "متوسط الوردية"),
        column("commission", "العمولة", total=True),
        column("previous_commission", "عمولة سابقة"),
    ]
    return envelope(
        "employee-performance", "أداء الموظفين",
        columns, rows,
        totals={
            "sales": q2(total_sales),
            "commission": q2(total_commission),
            "sessions": sum(r["sessions"] for r in rows),
        },
        kpis=[
            kpi("sales", "مبيعات الموظفين", total_sales),
            kpi("commission", "إجمالي العمولات", total_commission, sum(r["previous_commission"] for r in rows)),
            kpi("employees", "عدد الموظفين النشطين", len(rows), type_="number"),
        ],
        period_=(date_from, date_to), previous=(prev_from, prev_to),
    )


# ---------------------------------------------------------------------------
# 5) ربحية الأقمشة
# ---------------------------------------------------------------------------


def fabric_profitability(request, date_from, date_to, prev_from, prev_to):
    sold, cogs = sold_and_cogs(request, date_from, date_to)
    prev_sold, _prev_cogs = sold_and_cogs(request, prev_from, prev_to)
    if not sold:
        return envelope(
            "fabric-profitability", "ربحية الأقمشة",
            [
                column("fabric_name", "القماش", "text"),
                column("yards", "الياردات", "number", total=True),
                column("revenue", "الإيراد", total=True),
                column("cogs", "التكلفة", total=True),
                column("profit", "الربح", total=True),
                column("margin", "الهامش %", "percent"),
            ], [],
        )
    fabrics = {f.id: f for f in Fabric.objects.filter(id__in=set(sold))}
    rows = []
    for fid, yards in sold.items():
        fabric = fabrics.get(fid)
        if not fabric:
            continue
        revenue = q2((fabric.sale_price_yard or ZERO) * yards)
        cost = cogs.get(fid, ZERO)
        profit = revenue - cost
        rows.append({
            "fabric": fid,
            "fabric_name": fabric.name,
            "fabric_code": fabric.code,
            "unit": fabric.unit,
            "yards": float(q2(yards)),
            "previous_yards": float(q2(prev_sold.get(fid, ZERO))),
            "revenue": float(revenue),
            "cogs": float(cost),
            "profit": float(q2(profit)),
            "margin": pct(profit, revenue),
        })
    rows.sort(key=lambda r: r["profit"], reverse=True)
    total_revenue = sum(r["revenue"] for r in rows)
    for row in rows:
        row["share"] = pct(row["revenue"], total_revenue)
    columns = [
        column("fabric_name", "القماش", "text"),
        column("fabric_code", "الكود", "text"),
        column("yards", "الياردات", "number", total=True),
        column("previous_yards", "ياردات سابقة", "number"),
        column("revenue", "الإيراد", total=True),
        column("cogs", "التكلفة", total=True),
        column("profit", "الربح", total=True),
        column("margin", "الهامش %", "percent"),
        column("share", "الحصة %", "percent"),
    ]
    return envelope(
        "fabric-profitability", "ربحية الأقمشة",
        columns, rows,
        totals={
            "yards": q2(sum(r["yards"] for r in rows)),
            "revenue": q2(total_revenue),
            "cogs": q2(sum(r["cogs"] for r in rows)),
            "profit": q2(sum(r["profit"] for r in rows)),
        },
        kpis=[
            kpi("revenue", "إيراد الأقمشة", total_revenue),
            kpi("profit", "مجمل ربح الأقمشة", sum(r["profit"] for r in rows)),
            kpi("fabrics", "عدد الأقمشة المباعة", len(rows), type_="number"),
        ],
        period_=(date_from, date_to), previous=(prev_from, prev_to),
    )


# ---------------------------------------------------------------------------
# 6) المخزون الراكد
# ---------------------------------------------------------------------------


def inventory_slow(request, date_from, date_to, prev_from, prev_to):
    try:
        idle_days = max(int(request.query_params.get("idle_days") or 30), 1)
    except (TypeError, ValueError):
        idle_days = 30

    rolls = in_scope(
        FabricRoll.objects.filter(status=FabricRoll.Status.AVAILABLE), request, "warehouse__branch_id"
    )
    stock = defaultdict(lambda: {"yards": ZERO, "rolls": 0})
    for fabric_id, yards, in rolls.values_list("fabric_id", "remaining_yards"):
        stock[fabric_id]["yards"] += yards or ZERO
        stock[fabric_id]["rolls"] += 1
    if not stock:
        return envelope(
            "inventory-slow", "المخزون الراكد",
            [
                column("fabric_name", "القماش", "text"),
                column("yards", "الرصيد", "number", total=True),
                column("idle_days", "أيام الركود", "number"),
                column("idle_value", "قيمة الركود", total=True),
            ], [],
        )

    sold, _cogs = sold_and_cogs(request, date_from, date_to)
    last_sale = {}
    for item_id, sale_date in in_scope(
        DailySaleItem.objects.select_related("sale"), request, "sale__branch_id"
    ).filter(sale__date__lte=date_to).values_list("fabric_id", "sale__date"):
        current = last_sale.get(item_id)
        if current is None or sale_date > current:
            last_sale[item_id] = sale_date

    today = date_to
    costs = fabric_average_costs()
    fabrics = {f.id: f for f in Fabric.objects.filter(id__in=set(stock))}
    rows = []
    for fid, entry in stock.items():
        fabric = fabrics.get(fid)
        if not fabric:
            continue
        sold_yards = sold.get(fid, ZERO)
        seen = last_sale.get(fid)
        idle = (today - seen).days if seen else (today - date_from).days
        idle_value = q2((costs.get(fid) or ZERO) * entry["yards"])
        rows.append({
            "fabric": fid,
            "fabric_name": fabric.name,
            "fabric_code": fabric.code,
            "unit": fabric.unit,
            "yards": float(q2(entry["yards"])),
            "rolls": entry["rolls"],
            "sold_yards": float(q2(sold_yards)),
            "last_sale": seen.isoformat() if seen else "",
            "idle_days": idle,
            "idle_value": float(idle_value),
            "status": "لم يُبع" if not sold_yards else ("راكد" if idle >= idle_days else "نشط"),
        })
    rows.sort(key=lambda r: (r["idle_value"], r["yards"]), reverse=True)
    idle_rows = [r for r in rows if r["status"] != "نشط"]
    columns = [
        column("fabric_name", "القماش", "text"),
        column("fabric_code", "الكود", "text"),
        column("yards", "الرصيد", "number", total=True),
        column("rolls", "اللفات", "number"),
        column("sold_yards", "مبيع الفترة", "number"),
        column("last_sale", "آخر بيع", "text"),
        column("idle_days", "أيام الركود", "number"),
        column("idle_value", "قيمة الركود", total=True),
        column("status", "الحالة", "text"),
    ]
    return envelope(
        "inventory-slow", f"المخزون الراكد (أكثر من {idle_days} يوم بلا حركة)",
        columns, rows,
        totals={
            "yards": q2(sum(r["yards"] for r in rows)),
            "idle_value": q2(sum(r["idle_value"] for r in idle_rows)),
            "rolls": sum(r["rolls"] for r in rows),
        },
        kpis=[
            kpi("idle_value", "قيمة المخزون الراكد", sum(r["idle_value"] for r in idle_rows)),
            kpi("idle_count", "عدد الأقمشة الراكدة", len(idle_rows), type_="number"),
            kpi("stock_value", "قيمة كامل المخزون", sum(r["idle_value"] for r in rows)),
        ],
        period_=(date_from, date_to), previous=(prev_from, prev_to),
        meta={"idle_days": idle_days},
    )


# ---------------------------------------------------------------------------
# 7) أعمار ديون الموردين
# ---------------------------------------------------------------------------


def supplier_aging(request, date_from, date_to, prev_from, prev_to):
    from suppliers.models import Supplier

    today = date_to
    entries = defaultdict(list)
    for supplier_id, when, amount in LedgerEntry.objects.values_list(
        "supplier_id", "date", "amount"
    ).order_by("date", "id"):
        entries[supplier_id].append((when, amount))
    period_moves = defaultdict(lambda: {"purchases": ZERO, "payments": ZERO})
    for supplier_id, entry_type, amount in LedgerEntry.objects.filter(
        date__gte=date_from, date__lte=date_to
    ).values_list("supplier_id", "entry_type", "amount"):
        if entry_type == LedgerEntry.EntryType.PURCHASE:
            period_moves[supplier_id]["purchases"] += amount
        elif entry_type == LedgerEntry.EntryType.PAYMENT:
            period_moves[supplier_id]["payments"] += amount

    supplier_ids = set(entries)
    if not supplier_ids:
        return _empty_aging("supplier-aging", "أعمار ديون الموردين", "supplier", "المورد")
    suppliers = {s.id: s for s in Supplier.objects.filter(id__in=supplier_ids)}
    rows = []
    for sid, supplier in suppliers.items():
        buckets, oldest = allocate(entries[sid], today)
        balance = sum(buckets.values(), ZERO)
        moves = period_moves.get(sid)
        if balance == 0 and not moves:
            continue
        rows.append({
            "party": sid,
            "party_name": supplier.name,
            "balance": float(q2(balance)),
            **{key: float(q2(value)) for key, value in buckets.items()},
            "purchases": float(q2(moves["purchases"])) if moves else 0.0,
            "payments": float(q2(moves["payments"])) if moves else 0.0,
            "oldest_days": (today - oldest).days if oldest else 0,
            "oldest_date": oldest.isoformat() if oldest else "",
        })
    rows.sort(key=lambda r: r["balance"], reverse=True)
    total_balance = sum(r["balance"] for r in rows)
    columns = [
        column("party_name", "المورد", "text"),
        column("balance", "الرصيد المستحق", total=True),
        column("purchases", "مشتريات الفترة", total=True),
        column("payments", "سدادات الفترة", total=True),
        column("not_due", "غير مستحق"),
        column("d1_30", "1-30 يوم"),
        column("d31_60", "31-60 يوم"),
        column("d61_90", "61-90 يوم"),
        column("over_90", "أكثر من 90 يوم"),
        column("oldest_days", "أقدم يوم", "number"),
    ]
    return envelope(
        "supplier-aging", "أعمار ديون الموردين",
        columns, rows,
        totals={
            "balance": q2(total_balance),
            "over_90": q2(sum(r["over_90"] for r in rows)),
            "purchases": q2(sum(r["purchases"] for r in rows)),
            "payments": q2(sum(r["payments"] for r in rows)),
        },
        kpis=[
            kpi("balance", "إجمالي المستحق للموردين", total_balance),
            kpi("over_90", "متأخر أكثر من 90 يوم", sum(r["over_90"] for r in rows)),
            kpi("suppliers", "عدد الموردين", len(rows), type_="number"),
        ],
        period_=(date_from, date_to), previous=(prev_from, prev_to),
    )


# ---------------------------------------------------------------------------
# 8) أعمار حسابات الشركاء
# ---------------------------------------------------------------------------


def partner_aging(request, date_from, date_to, prev_from, prev_to):
    from partners.models import Partner
    from partners.models import PartnerMovement

    # حركات كل شريك (عملية واحدة تُنتج حركة لكل شريك) — تُعالَج مجتمعةً بالترتيب الزمني.
    entries = defaultdict(list)
    for partner_id, when, kind, amount in PartnerMovement.objects.values_list(
        "partner_id", "operation__date", "movement_type", "amount"
    ).order_by("operation__date", "id"):
        value = amount if kind == PartnerMovement.MovementType.SUPPORT else -amount
        entries[partner_id].append((when, value))

    moves = defaultdict(lambda: {"support": ZERO, "withdraw": ZERO})
    for partner_id, kind, amount in PartnerMovement.objects.filter(
        operation__date__gte=date_from, operation__date__lte=date_to
    ).values_list("partner_id", "movement_type", "amount"):
        if kind == PartnerMovement.MovementType.SUPPORT:
            moves[partner_id]["support"] += amount
        else:
            moves[partner_id]["withdraw"] += amount

    rows = []
    for partner_id, party_entries in entries.items():
        buckets, oldest = allocate(party_entries, date_to)
        balance = sum(buckets.values(), ZERO)
        partner = Partner.objects.filter(id=partner_id).first()
        if partner is None:
            continue
        move = moves.get(partner_id, {"support": ZERO, "withdraw": ZERO})
        rows.append({
            "party": partner.id,
            "party_name": partner.name,
            "share_percent": float(partner.share_percent or 0),
            "balance": float(q2(balance)),
            **{key: float(q2(value)) for key, value in buckets.items()},
            "support": float(q2(move["support"])),
            "withdraw": float(q2(move["withdraw"])),
            "oldest_days": (date_to - oldest).days if oldest else 0,
        })
    rows.sort(key=lambda r: r["balance"], reverse=True)
    total_balance = sum(r["balance"] for r in rows)
    columns = [
        column("party_name", "الشريك", "text"),
        column("share_percent", "نسبة الملكية %", "percent"),
        column("balance", "الرصيد", total=True),
        column("support", "دعم الفترة", total=True),
        column("withdraw", "سحب الفترة", total=True),
        column("not_due", "غير مستحق"),
        column("d1_30", "1-30 يوم"),
        column("d31_60", "31-60 يوم"),
        column("d61_90", "61-90 يوم"),
        column("over_90", "أكثر من 90 يوم"),
    ]
    return envelope(
        "partner-aging", "أعمار حسابات الشركاء",
        columns, rows,
        totals={
            "balance": q2(total_balance),
            "support": q2(sum(r["support"] for r in rows)),
            "withdraw": q2(sum(r["withdraw"] for r in rows)),
        },
        kpis=[
            kpi("balance", "صافي رصيد الشركاء", total_balance),
            kpi("support", "دعم الفترة", sum(r["support"] for r in rows)),
            kpi("withdraw", "سحب الفترة", sum(r["withdraw"] for r in rows)),
        ],
        period_=(date_from, date_to), previous=(prev_from, prev_to),
    )


def _empty_aging(key, title, column_key, column_label):
    columns = [column(column_key, column_label, "text"), column("balance", "الرصيد", total=True)]
    for bucket_key, label, _lo, _hi in AGING_BUCKETS:
        columns.append(column(bucket_key, label))
    return envelope(key, title, columns, [], totals={"balance": ZERO})


# ---------------------------------------------------------------------------
# 9) حركة الخزينة
# ---------------------------------------------------------------------------


def cashflow(request, date_from, date_to, prev_from, prev_to):
    key, label, grouper = group_by(request, date_from, date_to)
    keys = bucket_range(date_from, date_to, grouper)
    prev_keys = bucket_range(prev_from, prev_to, grouper)
    inflow = defaultdict(lambda: ZERO)
    outflow = defaultdict(lambda: ZERO)
    breakdown = defaultdict(lambda: defaultdict(lambda: ZERO))

    for sale in in_scope(DailySale.objects.all(), request).filter(date__gte=date_from, date__lte=date_to):
        slot = bucket_start(sale.date, grouper)
        inflow[slot] += sale.cash_amount
        if sale.transfer_amount:
            breakdown[slot]["تحويل"] += sale.transfer_amount
        if sale.card_amount:
            breakdown[slot]["ماكينة"] += sale.card_amount

    for expense in in_scope(Expense.objects.select_related("category"), request).filter(
        date__gte=date_from, date__lte=date_to
    ):
        slot = bucket_start(expense.date, grouper)
        name = expense.category.name if expense.category_id else "أخرى"
        breakdown[slot][f"مصروف: {name}"] += expense.amount
        if expense.payment_method == "cash":
            outflow[slot] += expense.amount

    for entry in LedgerEntry.objects.filter(
        date__gte=date_from, date__lte=date_to, entry_type=LedgerEntry.EntryType.PAYMENT
    ).select_related("supplier"):
        if entry.payment_method == LedgerEntry.PaymentMethod.CASH:
            slot = bucket_start(entry.date, grouper)
            outflow[slot] += abs(entry.amount)
            breakdown[slot][f"سداد مورد: {entry.supplier.name}"] += abs(entry.amount)

    for operation in PartnerOperation.objects.filter(
        date__gte=date_from, date__lte=date_to,
        operation_type=PartnerOperation.OperationType.WITHDRAW,
        payment_method=PartnerOperation.PaymentMethod.CASH,
    ):
        slot = bucket_start(operation.date, grouper)
        outflow[slot] += operation.amount
        breakdown[slot]["سحب شريك"] += operation.amount

    prev_net = defaultdict(lambda: ZERO)
    for sale in in_scope(DailySale.objects.all(), request).filter(date__gte=prev_from, date__lte=prev_to):
        prev_net[bucket_start(sale.date, grouper)] += sale.cash_amount
    for expense in in_scope(Expense.objects.all(), request).filter(
        date__gte=prev_from, date__lte=prev_to, payment_method="cash"
    ):
        prev_net[bucket_start(expense.date, grouper)] -= expense.amount
    for entry in LedgerEntry.objects.filter(
        date__gte=prev_from, date__lte=prev_to,
        entry_type=LedgerEntry.EntryType.PAYMENT,
        payment_method=LedgerEntry.PaymentMethod.CASH,
    ):
        prev_net[bucket_start(entry.date, grouper)] -= abs(entry.amount)
    for operation in PartnerOperation.objects.filter(
        date__gte=prev_from, date__lte=prev_to,
        operation_type=PartnerOperation.OperationType.WITHDRAW,
        payment_method=PartnerOperation.PaymentMethod.CASH,
    ):
        prev_net[bucket_start(operation.date, grouper)] -= operation.amount

    all_breakdowns = sorted({name for slot in breakdown for name in breakdown[slot]})
    rows = []
    for slot in keys:
        net = inflow.get(slot, ZERO) - outflow.get(slot, ZERO)
        row = {
            "period": bucket_label(slot, key),
            "inflow": float(q2(inflow.get(slot, ZERO))),
            "outflow": float(q2(outflow.get(slot, ZERO))),
            "net": float(q2(net)),
        }
        for name in all_breakdowns:
            row[f"bd_{name}"] = float(q2(breakdown.get(slot, {}).get(name, ZERO)))
        rows.append(row)

    columns = [
        column("period", "الفترة", "text"),
        column("inflow", "وارد (نقدي)", total=True),
        column("outflow", "منصرف (نقدي)", total=True),
        column("net", "صافي الحركة", total=True),
    ] + [column(f"bd_{name}", name) for name in all_breakdowns]
    total_in = sum(r["inflow"] for r in rows)
    total_out = sum(r["outflow"] for r in rows)
    previous_net = sum(prev_net.values(), ZERO)
    return envelope(
        "cashflow", f"حركة الخزينة ({label})",
        columns, rows,
        totals={"inflow": q2(total_in), "outflow": q2(total_out), "net": q2(total_in - total_out)},
        kpis=[
            kpi("inflow", "إجمالي الوارد", total_in),
            kpi("outflow", "إجمالي المنصرف", total_out),
            kpi("net", "صافي حركة الخزينة", total_in - total_out, previous_net),
        ],
        period_=(date_from, date_to), previous=(prev_from, prev_to),
        group=key,
        series={
            "labels": [r["period"] for r in rows],
            "current": [r["net"] for r in rows],
            "previous": [
                float(q2(prev_net.get(pk, ZERO))) for pk in prev_keys[:len(rows)]
            ] + [0.0] * max(0, len(rows) - len(prev_keys)),
        },
    )


# ---------------------------------------------------------------------------
# 10) تقرير الرواتب
# ---------------------------------------------------------------------------


def payroll_report(request, date_from, date_to, prev_from, prev_to):
    from payroll.models import Payslip, PayrollRun, SalaryAdvance

    runs = in_scope(
        PayrollRun.objects.filter(month__gte=date_from.replace(day=1), month__lte=date_to),
        request,
    ).exclude(status=PayrollRun.Status.CANCELLED)
    payslips = Payslip.objects.filter(run__in=runs).select_related("employee", "branch")
    acc = defaultdict(lambda: {
        "runs": 0, "employees": 0, "gross": ZERO, "deductions": ZERO, "net": ZERO, "advances": ZERO,
    })
    for payslip in payslips:
        slot = acc[payslip.run.month]
        slot["gross"] += payslip.gross
        slot["deductions"] += payslip.total_deductions
        slot["net"] += payslip.net_pay
        slot["advances"] += payslip.advance_deduction
        slot["employees"] += 1
    for run in runs:
        acc[run.month]["runs"] += 1

    advances = in_scope(SalaryAdvance.objects.all(), request, "employee__branch_id").filter(
        date__gte=date_from, date__lte=date_to
    )
    advances_total = sum((a.amount for a in advances), ZERO)
    outstanding = sum((a.remaining_amount for a in advances), ZERO)

    rows = []
    for month in sorted(acc):
        slot = acc[month]
        rows.append({
            "month": f"{month:%Y-%m}",
            "runs": slot["runs"],
            "employees": slot["employees"],
            "gross": float(q2(slot["gross"])),
            "deductions": float(q2(slot["deductions"])),
            "net": float(q2(slot["net"])),
            "advances": float(q2(slot["advances"])),
        })
    columns = [
        column("month", "الشهر", "text"),
        column("runs", "المسيّرات", "number"),
        column("employees", "عدد القسائم", "number", total=True),
        column("gross", "الإجمالي", total=True),
        column("deductions", "الخصومات", total=True),
        column("net", "الصافي", total=True),
        column("advances", "خصم سلف", total=True),
    ]
    return envelope(
        "payroll", "تقرير الرواتب",
        columns, rows,
        totals={
            "gross": q2(sum(r["gross"] for r in rows)),
            "deductions": q2(sum(r["deductions"] for r in rows)),
            "net": q2(sum(r["net"] for r in rows)),
            "advances": q2(sum(r["advances"] for r in rows)),
        },
        kpis=[
            kpi("net", "صافي الرواتب", sum(r["net"] for r in rows)),
            kpi("gross", "إجمالي الرواتب", sum(r["gross"] for r in rows)),
            kpi("advances", "سلف الفترة", advances_total),
            kpi("outstanding", "سلف مستحقة", outstanding),
        ],
        period_=(date_from, date_to), previous=(prev_from, prev_to),
    )
