"""خدمة الترحيل المحاسبي: إنشاء القيود من المصادر تلقائياً، وعكسها، وبناء التقارير.

كل قيد يُنشأ مرتبطاً بمصدر (source + source_id) فتصبح العملية غير قابلة للتكرار
عند الترحيل المتكرر، وعكس العملية يحذف القيد المرتبط بها بالكامل.
"""

from collections import defaultdict
from datetime import date as _date, timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from .chart_of_accounts import ensure_seeded
from .models import Account, ClosedPeriod, JournalEntry, JournalLine

_HALF = Decimal("0.005")


def account_by_key(key):
    ensure_seeded()
    return Account.objects.filter(source_key=key).first()


def cash_account():
    return account_by_key("CASH")


def bank_account():
    return account_by_key("BANK")


def payable_account():
    return account_by_key("SUPPLIER_PAYABLE")


def partner_equity_account():
    return account_by_key("PARTNER_EQUITY")


def revenue_account():
    return account_by_key("SALE_REVENUE")


def cogs_account():
    return account_by_key("COGS")


def inventory_account():
    return account_by_key("INVENTORY")


def opening_offset_account():
    return account_by_key("OPENING_OFFSET")


def retained_account():
    return account_by_key("RETAINED_EARNINGS")


def payment_account(payment_method):
    """نقد -> حساب الخزنة، أي طريقة أخرى -> البنك."""
    if payment_method == "cash":
        return cash_account()
    return bank_account()


def ensure_expense_account(category):
    """حساب مصروف خاص بكل تصنيف يُنشأ تحت جذر المصاريف تلقائياً."""
    key = f"expense_cat:{category.id}"
    acc = Account.objects.filter(source_key=key).first()
    if acc:
        return acc
    parent = account_by_key("EXPENSE_ROOT")
    code = f"52-{category.id:04d}"
    i = category.id
    while Account.objects.filter(code=code).exists():
        i += 1
        code = f"52-{i:04d}"
    try:
        with transaction.atomic():
            return Account.objects.create(
                code=code,
                name=category.name or f"مصروف {category.id}",
                type=Account.Type.EXPENSE,
                parent=parent,
                source_key=key,
                is_system=False,
            )
    except IntegrityError:
        return Account.objects.get(source_key=key)


def next_entry_number(date):
    prefix = f"JV-{date:%Y%m%d}-"
    count = JournalEntry.objects.filter(number__startswith=prefix).count()
    number = f"{prefix}{count + 1}"
    guard = 0
    while JournalEntry.objects.filter(number=number).exists() and guard < 50:
        guard += 1
        number = f"{prefix}{count + 1 + guard}"
    return number


@transaction.atomic
def create_entry(date, description, source, source_id, lines, created_by=None):
    """lines: قائمة (account, debit, credit, description)."""
    ensure_seeded()
    if isinstance(date, str):
        from datetime import date as _dt
        date = _dt.fromisoformat(str(date))
    entry = JournalEntry.objects.create(
        number=next_entry_number(date),
        date=date,
        description=description,
        source=source,
        source_id=source_id,
        created_by=created_by,
    )
    for account, debit, credit, line_desc in lines:
        JournalLine.objects.create(
            entry=entry,
            account=account,
            debit=debit,
            credit=credit,
            description=line_desc or "",
        )
    return entry


def unpost_source(source, source_id):
    JournalEntry.objects.filter(source=source, source_id=source_id).delete()


def _round2(value):
    return (value or Decimal("0")).quantize(Decimal("0.01"))


# ---------------------------------------------------------------------------
# الترحيل التلقائي من المصادر
# ---------------------------------------------------------------------------


def post_session_close(session):
    """قيد إغلاق الوردية: نقد/بنك مقابل مبيعات + تكلفة البضاعة مقابل المخزون."""
    unpost_source(JournalEntry.Source.SESSION, session.pk)
    from sale_sessions.models import SaleSessionItem

    if getattr(session, "is_manual", False):
        totals = {
            "cash": _round2(session.manual_cash),
            "transfer": _round2(session.manual_transfer),
            "card": _round2(session.manual_card),
        }
        cogs = Decimal("0")
    else:
        rows = list(session.items.select_related("fabric"))
        if not rows:
            return
        totals = {m: Decimal("0") for m in SaleSessionItem.PaymentMethod.values}
        cogs = Decimal("0")
        for r in rows:
            totals[r.payment_method] += _round2(r.net_total)
            cogs += _round2((r.fabric.purchase_price or Decimal("0")) * r.yards_effective)
    total = sum(totals.values(), Decimal("0"))

    lines = []
    if total > 0:
        for method, amount in totals.items():
            if amount <= 0:
                continue
            acc = payment_account(method)
            lines.append((acc, amount, Decimal("0"), ""))
        lines.append((revenue_account(), Decimal("0"), total, ""))
    if cogs > 0:
        lines.append((cogs_account(), cogs, Decimal("0"), ""))
        lines.append((inventory_account(), Decimal("0"), cogs, ""))

    if not lines:
        return
    closed = session.closed_at or timezone.now()
    create_entry(
        closed.date(),
        f"إغلاق وردية بيع #{session.pk} — {session.employee.name} ({session.branch.name})",
        JournalEntry.Source.SESSION,
        session.pk,
        lines,
    )


def post_supplier_entry(entry):
    """قيد من دفتر الموردين: شراء / دفعة / مرتجع / رصيد افتتاحي."""
    unpost_source(JournalEntry.Source.PURCHASE, entry.pk)
    if not entry.amount:
        return
    from suppliers.models import LedgerEntry

    payable = payable_account()
    amount = entry.amount
    abs_amount = abs(amount)
    entry_type = entry.entry_type

    if entry_type == LedgerEntry.EntryType.PAYMENT:
        lines = [
            (payable, abs_amount, Decimal("0"), ""),
            (payment_account(entry.payment_method), Decimal("0"), abs_amount, ""),
        ]
    elif entry_type == LedgerEntry.EntryType.RETURN:
        lines = [
            (payable, abs_amount, Decimal("0"), ""),
            (inventory_account(), Decimal("0"), abs_amount, ""),
        ]
    elif entry_type == LedgerEntry.EntryType.OPENING:
        if amount > 0:
            lines = [
                (opening_offset_account(), abs_amount, Decimal("0"), "رصيد افتتاحي"),
                (payable, Decimal("0"), abs_amount, ""),
            ]
        else:
            lines = [
                (payable, abs_amount, Decimal("0"), ""),
                (opening_offset_account(), Decimal("0"), abs_amount, "رصيد افتتاحي"),
            ]
    else:  # PURCHASE
        if amount > 0:
            lines = [
                (inventory_account(), abs_amount, Decimal("0"), ""),
                (payable, Decimal("0"), abs_amount, ""),
            ]
        else:
            lines = [
                (payable, abs_amount, Decimal("0"), ""),
                (inventory_account(), Decimal("0"), abs_amount, ""),
            ]

    create_entry(
        entry.date,
        f"عمليات الموردين — {entry.supplier.name} ({entry.get_entry_type_display()}) {entry.receipt_no or ''}".strip(),
        JournalEntry.Source.PURCHASE,
        entry.pk,
        lines,
    )


def post_expense(expense):
    """قيد مصروف: حساب التصنيف مقابل نقد/بنك."""
    unpost_source(JournalEntry.Source.EXPENSE, expense.pk)
    if expense.amount <= 0:
        return
    exp_acc = ensure_expense_account(expense.category)
    amount = _round2(expense.amount)
    lines = [
        (exp_acc, amount, Decimal("0"), ""),
        (payment_account(expense.payment_method), Decimal("0"), amount, ""),
    ]
    create_entry(
        expense.date,
        f"مصروف — {expense.category.name} — {expense.description or ''} ({expense.branch.name})",
        JournalEntry.Source.EXPENSE,
        expense.pk,
        lines,
    )


def post_partner_operation(operation):
    """قيد عملية شريك: نقد/بنك مقابل حساب الشركاء."""
    unpost_source(JournalEntry.Source.PARTNER, operation.pk)
    if not operation.amount:
        return
    from partners.models import PartnerOperation

    amount = _round2(operation.amount)
    equity = partner_equity_account()
    pmt = payment_account(operation.payment_method)
    if operation.operation_type == PartnerOperation.OperationType.SUPPORT:
        lines = [
            (pmt, amount, Decimal("0"), ""),
            (equity, Decimal("0"), amount, ""),
        ]
    else:
        lines = [
            (equity, amount, Decimal("0"), ""),
            (pmt, Decimal("0"), amount, ""),
        ]
    create_entry(
        operation.date,
        f"عملية شريك — {operation.number} — {operation.get_operation_type_display()}",
        JournalEntry.Source.PARTNER,
        operation.pk,
        lines,
    )


@transaction.atomic
def close_period(date_to, description="", created_by=None):
    """قيد إقفال دوري: نقل أرصدة حسابات الدخل والمصاريف إلى الأرباح المحتجزة."""
    if ClosedPeriod.objects.filter(period_end=date_to).exists():
        raise ValueError("هذه الفترة مقفلة بالفعل")
    lines = JournalLine.objects.filter(entry__date__lte=date_to).select_related("account")
    totals = defaultdict(lambda: [Decimal("0"), Decimal("0")])
    for ln in lines:
        if ln.account.type in (Account.Type.INCOME, Account.Type.EXPENSE):
            totals[ln.account_id][0] += ln.debit
            totals[ln.account_id][1] += ln.credit
    accounts = {
        a.id: a
        for a in Account.objects.filter(
            type__in=(Account.Type.INCOME, Account.Type.EXPENSE)
        )
    }
    debit_rows = []  # (account, amount) مدين
    credit_rows = []  # (account, amount) دائن
    income_total = Decimal("0")
    expense_total = Decimal("0")
    for acc_id, (dr, cr) in totals.items():
        acc = accounts.get(acc_id)
        if not acc:
            continue
        net = cr - dr
        if acc.type == Account.Type.INCOME:
            if net > 0:
                income_total += net
                debit_rows.append((acc, net))
        else:
            if net > 0:
                expense_total += net
                credit_rows.append((acc, net))

    net_profit = income_total - expense_total
    retained = retained_account()
    closing_lines = [(a, amt, Decimal("0"), "") for a, amt in debit_rows]
    closing_lines += [(a, Decimal("0"), amt, "") for a, amt in credit_rows]
    if net_profit > 0:
        closing_lines.append((retained, Decimal("0"), _round2(net_profit), "صافي أرباح الفترة"))
    elif net_profit < 0:
        closing_lines.append((retained, _round2(-net_profit), Decimal("0"), "خسائر الفترة"))

    if not closing_lines:
        raise ValueError("لا توجد حركات للإقفال في هذه الفترة")

    create_entry(
        date_to,
        description or f"قيد إقفال دوري حتى {date_to}",
        JournalEntry.Source.CLOSING,
        None,
        closing_lines,
        created_by=created_by,
    )
    ClosedPeriod.objects.create(period_end=date_to, description=description, net_profit=_round2(net_profit))
    return {"net_profit": float(_round2(net_profit)), "entries": len(closing_lines)}


# ---------------------------------------------------------------------------
# التقارير المحاسبية
# ---------------------------------------------------------------------------


def _movements(date_from=None, date_to=None):
    """حركات السطور بين تاريخين (حركة الفترة). العودة كقائمة."""
    qs = JournalLine.objects.select_related("account", "entry").all()
    if date_from:
        qs = qs.filter(entry__date__gte=date_from)
    if date_to:
        qs = qs.filter(entry__date__lte=date_to)
    return list(qs)


def _balances(date_to=None):
    """أرصدة تراكمية حتى تاريخ (شاملة). العودة dict account_id -> (debit, credit)."""
    qs = JournalLine.objects.select_related("account").all()
    if date_to:
        qs = qs.filter(entry__date__lte=date_to)
    totals = defaultdict(lambda: [Decimal("0"), Decimal("0")])
    for ln in qs:
        totals[ln.account_id][0] += ln.debit
        totals[ln.account_id][1] += ln.credit
    return totals


def _float(value):
    return float(value)


def trial_balance(date_to=None, show_zero=False):
    """ميزان المراجعة: أرصدة لكل حساب حتى تاريخ."""
    balances = _balances(date_to)
    accounts = Account.objects.all()
    rows = []
    for acc in accounts:
        dr, cr = balances.get(acc.id, [Decimal("0"), Decimal("0")])
        if not show_zero and dr == cr == Decimal("0"):
            continue
        rows.append({
            "id": acc.id,
            "code": acc.code,
            "name": acc.name,
            "type": acc.type,
            "type_label": acc.get_type_display(),
            "parent_id": acc.parent_id,
            "debit": _float(dr),
            "credit": _float(cr),
        })
    total_dr = sum((r["debit"] for r in rows), 0.0)
    total_cr = sum((r["credit"] for r in rows), 0.0)
    return {
        "date_to": date_to,
        "rows": rows,
        "totals": {"debit": total_dr, "credit": total_cr},
        "balanced": abs(total_dr - total_cr) < 0.005,
    }


def income_statement(date_from=None, date_to=None):
    """قائمة الدخل: إيرادات ومصاريف الفترة وصافي الربح."""
    account_ids = set()
    for acc in Account.objects.filter(type__in=(Account.Type.INCOME, Account.Type.EXPENSE)):
        account_ids.add(acc.id)
    balances = _movements(date_from, date_to)
    totals = defaultdict(lambda: [Decimal("0"), Decimal("0")])
    for ln in balances:
        if ln.account_id in account_ids:
            totals[ln.account_id][0] += ln.debit
            totals[ln.account_id][1] += ln.credit
    accounts = {a.id: a for a in Account.objects.filter(type__in=(Account.Type.INCOME, Account.Type.EXPENSE))}
    income_rows = []
    expense_rows = []
    income_total = Decimal("0")
    expense_total = Decimal("0")
    for acc_id, (dr, cr) in sorted(totals.items()):
        acc = accounts.get(acc_id)
        if not acc:
            continue
        if acc.type == Account.Type.INCOME:
            net = cr - dr
            if net > 0:
                income_total += net
                income_rows.append({"code": acc.code, "name": acc.name, "amount": _float(net)})
        else:
            net = dr - cr
            if net > 0:
                expense_total += net
                expense_rows.append({"code": acc.code, "name": acc.name, "amount": _float(net)})
    return {
        "date_from": date_from,
        "date_to": date_to,
        "income_rows": sorted(income_rows, key=lambda r: r["code"]),
        "expense_rows": sorted(expense_rows, key=lambda r: r["code"]),
        "total_income": _float(income_total),
        "total_expenses": _float(expense_total),
        "net_profit": _float(income_total - expense_total),
    }


def balance_sheet(date_to=None):
    """المركز المالي (الميزانية العمومية): أصول / التزامات / حقوق ملكية + أرباح الفترة."""
    balances = _balances(date_to)
    accounts = {a.id: a for a in Account.objects.all()}

    asset_rows = []
    liability_rows = []
    equity_rows = []
    for acc_id, (dr, cr) in balances.items():
        acc = accounts.get(acc_id)
        if not acc:
            continue
        if acc.type == Account.Type.ASSET:
            net = dr - cr
            if net:
                asset_rows.append({"code": acc.code, "name": acc.name, "amount": _float(net)})
        elif acc.type == Account.Type.LIABILITY:
            net = cr - dr
            if net:
                liability_rows.append({"code": acc.code, "name": acc.name, "amount": _float(net)})
        elif acc.type == Account.Type.EQUITY:
            net = cr - dr
            if net:
                equity_rows.append({"code": acc.code, "name": acc.name, "amount": _float(net)})

    def _sort(rows):
        return sorted(rows, key=lambda r: r["code"])

    total_assets = sum(r["amount"] for r in asset_rows)
    total_liabilities = sum(r["amount"] for r in liability_rows)
    total_equity = sum(r["amount"] for r in equity_rows)

    # صافي أرباح الفترة غير المغلقة يُضاف لحقوق الملكية
    pl = income_statement(None, date_to)
    period_profit = Decimal(str(pl["net_profit"]))
    if period_profit:
        equity_rows.append({
            "code": "99",
            "name": "أرباح الفترة الحالية (غير مقتلة)",
            "amount": _float(period_profit),
        })
        total_equity += period_profit

    difference = Decimal(str(total_assets)) - (Decimal(str(total_liabilities)) + total_equity)
    return {
        "date_to": date_to,
        "asset_rows": _sort(asset_rows),
        "liability_rows": _sort(liability_rows),
        "equity_rows": _sort(equity_rows),
        "total_assets": _float(total_assets),
        "total_liabilities": _float(total_liabilities),
        "total_equity": _float(total_equity),
        "difference": _float(difference),
        "balanced": abs(difference) < 0.005,
    }


def _cash_account_ids():
    return list(
        Account.objects.filter(source_key__in=("CASH", "BANK")).values_list("id", flat=True)
    )


_CASH_SOURCE_LABELS = {
    "session": "مبيعات الورديات",
    "purchase": "مدفوعات الموردين",
    "expense": "المصاريف",
    "partner": "عمليات الشركاء",
    "manual": "قيود يدوية",
    "closing": "قيد الإقفال",
}


def cash_flow(date_from=None, date_to=None):
    """حركة النقد والبنك مصنفة حسب مصدر القيد."""
    cash_ids = set(_cash_account_ids())
    in_total = Decimal("0")
    out_total = Decimal("0")
    by_source = defaultdict(lambda: [Decimal("0"), Decimal("0")])
    for ln in _movements(date_from, date_to):
        if ln.account_id not in cash_ids:
            continue
        entry = ln.entry
        if ln.debit > 0:
            by_source[entry.source][0] += ln.debit
            in_total += ln.debit
        elif ln.credit > 0:
            by_source[entry.source][1] += ln.credit
            out_total += ln.credit

    rows = []
    for source, (in_amt, out_amt) in sorted(by_source.items()):
        rows.append({
            "source": source,
            "label": _CASH_SOURCE_LABELS.get(source, source),
            "in": _float(in_amt),
            "out": _float(out_amt),
            "net": _float(in_amt - out_amt),
        })
    return {
        "date_from": date_from,
        "date_to": date_to,
        "rows": rows,
        "totals": {
            "in": _float(in_total),
            "out": _float(out_total),
            "net": _float(in_total - out_total),
        },
    }


def cash_box(date=None):
    """خزنة اليوم: الرصيد الافتتاحي، التحريكات الواردة والصادرة، والرصيد الختامي."""
    date = date or timezone.localdate()
    cash_ids = set(
        Account.objects.filter(source_key="CASH").values_list("id", flat=True)
    )
    opening = Decimal("0")
    for ln in JournalLine.objects.filter(
        account_id__in=cash_ids, entry__date__lt=date
    ):
        opening += ln.debit - ln.credit

    day_lines = list(
        JournalLine.objects.filter(
            account_id__in=cash_ids, entry__date=date
        ).select_related("entry")
    )
    in_total = sum((ln.debit for ln in day_lines), Decimal("0"))
    out_total = sum((ln.credit for ln in day_lines), Decimal("0"))
    by_source = defaultdict(lambda: [Decimal("0"), Decimal("0")])
    for ln in day_lines:
        if ln.debit > 0:
            by_source[ln.entry.source][0] += ln.debit
        else:
            by_source[ln.entry.source][1] += ln.credit
    rows = []
    for source, (in_amt, out_amt) in sorted(by_source.items()):
        rows.append({
            "source": source,
            "label": _CASH_SOURCE_LABELS.get(source, source),
            "in": _float(in_amt),
            "out": _float(out_amt),
        })
    closing = opening + in_total - out_total
    return {
        "date": str(date),
        "opening": _float(opening),
        "rows": rows,
        "totals": {"in": _float(in_total), "out": _float(out_total)},
        "closing": _float(closing),
    }