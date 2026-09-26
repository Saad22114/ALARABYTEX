"""مركز التنبيهات الذكية.

كل قاعدة دالة مستقلة تُرجع قائمة تنبيهات موحّدة الشكل:

``{key, title, severity, count, section, href, hint, items}``

- ``severity``: ``critical`` (يحتاج إجراءً فورياً) ثم ``warning`` ثم ``info``.
- ``section``: القسم الذي يجب أن يملك المستخدم صلاحية رؤيته ليظهر التنبيه.
- ``items``: عيّنة مختصرة (حتى 5 عناصر) تربط كل عنصر بالصفحة المسؤولة.

القواعد مكتوبة صراحةً لا عبر إعداد عام، لأن كل قاعدة تحتاج استعلامها
وشروطها الخاصة — والهدف وضوح السلوك أهم من التعميم.

ملاحظة: كل قاعدة مبنيّة لتكون رخيصة (استعلامات مُجمَّعة بلا تحميل كائنات)،
لأن هذه الدالة تُستدعى مع كل تحميل للوحة التحكم.
"""

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, F, Q, Sum
from django.utils import timezone

from accounting.models import JournalEntry
from core.branch_scope import scope_queryset, scope_queryset_or
from core.permissions import section_view_allowed
from payroll.models import AdvanceInstallment, PayrollRun, SalaryAdvance, SalaryStructure
from sale_sessions.models import Employee, SaleSession
from sales.models import DailySaleItem
from suppliers.models import LedgerEntry
from warehouses.models import FabricRoll, StockCount, StockTransfer

SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}
MAX_ITEMS = 5

STALE_STOCK_DAYS = 60
OVERDUE_ADVANCE_DAYS = 30


def _alert(key, title, severity, section, href, hint, items, total=None):
    items = list(items)[:MAX_ITEMS]
    return {
        "key": key,
        "title": title,
        "severity": severity,
        "section": section,
        "href": href,
        "hint": hint,
        "count": total if total is not None else len(items),
        "items": items,
    }


def _n(value):
    """رقم مختصر بدون كسور لا داعي لها."""
    return f"{float(value or 0):,.0f}"


# ------------------------------------------------------------------ المخزون


def _low_stock(request):
    from appsettings.models import AppSettings

    if not AppSettings.load().low_stock_alert_enabled:
        return []
    agg = (
        scope_queryset(
            request,
            FabricRoll.objects.filter(status=FabricRoll.Status.AVAILABLE),
            branch_field="warehouse__branch",
        )
        .values("fabric_id", "fabric__name", "fabric__min_stock", "fabric__unit")
        .annotate(total_yards=Sum("remaining_yards"))
    )
    out_of_stock, below_min = [], []
    for row in agg:
        total = row["total_yards"] or 0
        limit = row["fabric__min_stock"] or 0
        unit = row["fabric__unit"] or ""
        if total <= 0:
            out_of_stock.append(
                {"id": row["fabric_id"], "title": row["fabric__name"], "detail": "لا يوجد رصيد متاح"}
            )
        elif limit and total < limit:
            below_min.append(
                {
                    "id": row["fabric_id"],
                    "title": row["fabric__name"],
                    "detail": f"{float(total):g} من حد الطلب {float(limit):g} {unit}".strip(),
                }
            )

    alerts = []
    if out_of_stock:
        alerts.append(
            _alert(
                "stock_out",
                "أقمشة نفد رصيدها",
                "critical",
                "warehouses",
                "/warehouses",
                "رصيد صفر — يجب الشراء أو التحويل قبل أي بيع",
                out_of_stock,
                total=len(out_of_stock),
            )
        )
    if below_min:
        alerts.append(
            _alert(
                "stock_low",
                "أقمشة تحت حد الطلب",
                "warning",
                "warehouses",
                "/warehouses",
                "الرصيد الحالي أقل من الحد الأدنى المحدد في بطاقة القماش",
                below_min,
                total=len(below_min),
            )
        )
    return alerts


def _stale_stock(request):
    """أقمشة رصيدها قائم لكنها لم تُبَع منذ فترة — مال راكد."""
    since = timezone.localdate() - timedelta(days=STALE_STOCK_DAYS)
    sold_recently = set(
        scope_queryset(request, DailySaleItem.objects.filter(sale__date__gte=since)).values_list(
            "fabric_id", flat=True
        )
    )
    stock = (
        scope_queryset(
            request,
            FabricRoll.objects.filter(status=FabricRoll.Status.AVAILABLE),
            branch_field="warehouse__branch",
        )
        .exclude(remaining_yards__lte=0)
        .values("fabric_id", "fabric__name")
        .annotate(total_yards=Sum("remaining_yards"))
    )
    items = [
        {
            "id": row["fabric_id"],
            "title": row["fabric__name"],
            "detail": f"{float(row['total_yards'] or 0):g} يارد بلا حركة",
        }
        for row in stock
        if row["fabric_id"] not in sold_recently
    ]
    if not items:
        return []
    items.sort(key=lambda i: i["title"])
    return [
        _alert(
            "stock_stale",
            "مخزون راكد",
            "info",
            "warehouses",
            f"/reports?report=inventory-slow&days={STALE_STOCK_DAYS}",
            f"رصيد قائم بلا مبيعات خلال {STALE_STOCK_DAYS} يوماً",
            items,
            total=len(items),
        )
    ]


# ------------------------------------------------------- الورديات والمبيعات


def _open_sessions(request):
    cutoff = timezone.localdate() - timedelta(days=1)
    sessions = list(
        scope_queryset(
            request,
            SaleSession.objects.filter(status=SaleSession.Status.OPEN, opened_at__date__lt=cutoff),
        )
        .select_related("employee", "branch")
        .order_by("opened_at")
    )
    items = [
        {
            "id": s.id,
            "title": s.employee.name,
            "detail": f"{s.branch.name} — مفتوحة منذ {s.opened_at.date()}",
        }
        for s in sessions
    ]
    if not items:
        return []
    return [
        _alert(
            "sessions_open",
            "ورديات مفتوحة من أيام سابقة",
            "warning",
            "sessions",
            "/sessions?tab=open",
            "وردية لم تُغلق تُجمّد تقارير اليوم",
            items,
            total=len(items),
        )
    ]


def _unreceived_purchases(request):
    rows = list(
        scope_queryset_or(
            request,
            LedgerEntry.objects.filter(entry_type=LedgerEntry.EntryType.PURCHASE),
            ["branch", "warehouse__branch"],
        )
        .annotate(receipt_count=Count("goods_receipts"))
        .filter(receipt_count=0)
        .select_related("supplier")
        .order_by("date", "-id")[:50]
    )
    items = [
        {
            "id": e.id,
            "title": e.supplier.name,
            "detail": f"{e.receipt_no or 'بلا رقم'} — {e.date} — {_n(e.amount)}",
        }
        for e in rows
    ]
    if not items:
        return []
    return [
        _alert(
            "purchases_unreceived",
            "مشتريات لم تُستلَم بعد",
            "warning",
            "suppliers",
            "/suppliers?tab=purchases",
            "فاتورة شراء بلا سند استلام — المخزون غير محدَّث",
            items,
            total=len(items),
        )
    ]


# ------------------------------------------------------------------ المخازن


def _pending_transfers(request):
    rows = list(
        scope_queryset_or(
            request,
            StockTransfer.objects.filter(status=StockTransfer.Status.REQUESTED),
            ["from_warehouse__branch", "to_warehouse__branch", "to_branch"],
        )
        .select_related("from_warehouse")
        .order_by("date", "-id")[:50]
    )
    items = [
        {
            "id": t.id,
            "title": t.number,
            "detail": f"{t.from_warehouse.name if t.from_warehouse_id else '—'} — {t.date}",
        }
        for t in rows
    ]
    if not items:
        return []
    return [
        _alert(
            "transfers_pending",
            "تحويلات بانتظار الموافقة",
            "info",
            "warehouses",
            "/warehouses?tab=transfers&status=requested",
            "طلب تحويل لم يُعتمد بعد",
            items,
            total=len(items),
        )
    ]


def _open_counts(request):
    rows = list(
        scope_queryset_or(
            request,
            StockCount.objects.filter(status=StockCount.Status.OPEN),
            ["warehouse__branch"],
        )
        .select_related("warehouse")
        .order_by("-id")[:50]
    )
    items = [
        {
            "id": c.id,
            "title": c.number or f"جرد #{c.pk}",
            "detail": c.warehouse.name if c.warehouse_id else "—",
        }
        for c in rows
    ]
    if not items:
        return []
    return [
        _alert(
            "counts_open",
            "عمليات جرد غير منشورة",
            "info",
            "warehouses",
            "/warehouses?tab=counts&status=open",
            "جرد لم يُنشر بعد — لا يظهر أثره في المخزون الفعلي",
            items,
            total=len(items),
        )
    ]


# ------------------------------------------------------------------ الرواتب


def _payroll_drafts(request):
    rows = list(
        scope_queryset(request, PayrollRun.objects.filter(status=PayrollRun.Status.DRAFT))
        .select_related("branch")
        .order_by("month", "-id")
    )
    items = [
        {
            "id": r.id,
            "title": r.month.strftime("%Y-%m"),
            "detail": f"{r.branch.name if r.branch_id else 'كل الفروع'} — لم يُعتمد",
        }
        for r in rows
    ]
    if not items:
        return []
    return [
        _alert(
            "payroll_draft",
            "مسيّرات رواتب لم تُعتمد",
            "info",
            "payroll",
            "/payroll?tab=runs",
            "مسيّر في حالة مسودة — لم يُسجَّل صرفه بعد",
            items,
            total=len(items),
        )
    ]


def _pending_advances(request):
    rows = list(
        scope_queryset(request, SalaryAdvance.objects.filter(status=SalaryAdvance.Status.PENDING))
        .select_related("employee")
        .order_by("date", "-id")
    )
    items = [
        {"id": a.id, "title": a.employee.name, "detail": f"{_n(a.amount)} — {a.date}"} for a in rows
    ]
    if not items:
        return []
    return [
        _alert(
            "advances_pending",
            "سلف راتب بانتظار الاعتماد",
            "warning",
            "payroll",
            "/payroll?tab=advances&status=pending",
            "سلفة لم تُعتمد ولم تُسدد",
            items,
            total=len(items),
        )
    ]


def _overdue_advances(request):
    cutoff = timezone.localdate() - timedelta(days=OVERDUE_ADVANCE_DAYS)
    rows = list(
        scope_queryset(
            request,
            SalaryAdvance.objects.filter(status=SalaryAdvance.Status.APPROVED, date__lt=cutoff),
        ).select_related("employee")
    )
    if not rows:
        return []
    paid = defaultdict(lambda: Decimal("0"))
    for advance_id, amount in AdvanceInstallment.objects.filter(
        advance_id__in=[a.pk for a in rows]
    ).values_list("advance_id", "amount"):
        paid[advance_id] += amount

    items = []
    for advance in rows:
        remaining = (advance.amount or Decimal("0")) - paid[advance.pk]
        if remaining <= 0:
            continue
        days = (timezone.localdate() - advance.date).days
        items.append(
            {
                "id": advance.id,
                "title": advance.employee.name,
                "detail": f"متبقٍ {_n(remaining)} — مضى {days} يوماً",
            }
        )
    if not items:
        return []
    return [
        _alert(
            "advances_overdue",
            "سلف متأخرة السداد",
            "warning",
            "payroll",
            "/payroll?tab=advances&status=approved",
            f"سلفة معتمدة مضى على صرفها أكثر من {OVERDUE_ADVANCE_DAYS} يوماً وما زالت قائمة",
            items,
            total=len(items),
        )
    ]


def _employees_without_salary(request):
    rows = list(
        scope_queryset(request, Employee.objects.filter(is_active=True))
        .exclude(base_salary__gt=0)
        .exclude(pk__in=SalaryStructure.objects.values("employee_id"))
        .values("id", "name", "department", "phone")[:50]
    )
    items = [
        {
            "id": r["id"],
            "title": r["name"],
            "detail": r["department"] or r["phone"] or "بلا راتب أساسي ولا هيكل",
        }
        for r in rows
    ]
    if not items:
        return []
    return [
        _alert(
            "employees_no_salary",
            "موظفون بلا راتب محدَّد",
            "warning",
            "payroll",
            "/payroll?tab=structures",
            "لا هيكل راتب ولا راتب أساسي — ستُولَّد قسيمة بقيمة صفر",
            items,
            total=len(items),
        )
    ]


# ------------------------------------------------------------------ المحاسبة


def _unbalanced_entries(request):
    """قيود غير متوازنة — خطأ محاسبي يجب معالجته قبل الإقفال."""
    entries = (
        JournalEntry.objects.annotate(
            total_debit=Sum("lines__debit"), total_credit=Sum("lines__credit")
        )
        .filter(Q(total_debit__isnull=True) | ~Q(total_debit=F("total_credit")))
        .order_by("-date", "-id")[:50]
    )
    items = []
    for entry in entries:
        debit = entry.total_debit or Decimal("0")
        credit = entry.total_credit or Decimal("0")
        if debit == credit:
            # مدخل بلا سطور أو متوازن فعلياً — تحقّق إضافي على مستوى بايثون
            continue
        items.append(
            {
                "id": entry.id,
                "title": entry.number,
                "detail": f"{entry.date} — مدين {_n(debit)} / دائن {_n(credit)}",
            }
        )
    if not items:
        return []
    return [
        _alert(
            "journal_unbalanced",
            "قيود يومية غير متوازنة",
            "critical",
            "accounting",
            "/accounting?tab=journal",
            "المدين لا يساوي الدائن — القيد غير صحيح",
            items,
            total=len(items),
        )
    ]


RULES = (
    _low_stock,
    _unbalanced_entries,
    _open_sessions,
    _pending_advances,
    _overdue_advances,
    _employees_without_salary,
    _unreceived_purchases,
    _stale_stock,
    _pending_transfers,
    _open_counts,
    _payroll_drafts,
)


def build_alerts(request):
    """يبني كل التنبيهات مرتّبة بالخطورة، مع تصفية ما لا يملكه المستخدم صلاحيته."""
    alerts = []
    for rule in RULES:
        try:
            produced = rule(request) or []
        except Exception:
            # قاعدة معطوبة يجب ألّا تُسقط بقية التنبيهات
            produced = []
        alerts.extend(a for a in produced if section_view_allowed(request, a["section"]))

    alerts.sort(key=lambda a: (SEVERITY_ORDER.get(a["severity"], 9), a["title"]))
    return alerts


def alerts_summary(alerts):
    """رقم موجز: كم تنبيهاً لكل مستوى خطورة."""
    return {
        "total": len(alerts),
        "critical": sum(1 for a in alerts if a["severity"] == "critical"),
        "warning": sum(1 for a in alerts if a["severity"] == "warning"),
        "info": sum(1 for a in alerts if a["severity"] == "info"),
    }
