"""خدمات الرواتب: هياكل الرواتب، السلف، مسيّرات الرواتب، وكشوف الحساب.

قواعد الاحتساب:
- الأساسي والبدلات من الهيكل الساري في تاريخ الشهر، وإن لم يوجد هيكل
  يُستخدم Employee.base_salary كأساسي بلا بدلات.
- العمولة تُؤخذ آلياً من ورديات الموظف المغلقة داخل الشهر.
- الغياب يُحتسب من الراتب الأساسي ÷ عدد أيام العمل الشهرية.
- خصم السلفة يُسجَّل سداداً (AdvanceInstallment) عند اعتماد المسيّر، فتنقص
  السلفة ولا تتكرر مع الشهري التالي.
"""

from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from .attendance import attendance_for, untracked
from .models import (
    AdvanceInstallment,
    Payslip,
    PayrollRun,
    SalaryAdvance,
    SalaryStructure,
)

ZERO = Decimal("0")
CENTS = Decimal("0.01")


def money(value):
    return Decimal(str(value if value is not None else 0)).quantize(CENTS)


def branch_id_of(value):
    """معرّف الفرع من: فرع، معرّف، أو نص — None عند عدم التحديد."""
    if value in (None, ""):
        return None
    return getattr(value, "id", value)


def normalize_month(value, fallback=None):
    """YYYY-MM أو تاريخ → أول يوم من الشهر."""
    if value in (None, ""):
        base = fallback or timezone.localdate()
        return base.replace(day=1)
    if isinstance(value, date):
        return value.replace(day=1)
    raw = str(value).strip()
    try:
        if len(raw) == 7:
            return date.fromisoformat(f"{raw}-01")
        return date.fromisoformat(raw).replace(day=1)
    except (TypeError, ValueError):
        base = fallback or timezone.localdate()
        return base.replace(day=1)


def month_bounds(month):
    month = normalize_month(month)
    last_day = monthrange(month.year, month.month)[1]
    return month, date(month.year, month.month, last_day)


def next_month(month):
    month = normalize_month(month)
    if month.month == 12:
        return date(month.year + 1, 1, 1)
    return date(month.year, month.month + 1, 1)


def previous_month(month):
    month = normalize_month(month)
    return date(month.year - 1, 12, 1) if month.month == 1 else date(month.year, month.month - 1, 1)


def active_structure(employee, on_date=None):
    """أحدث هيكل راتب ساري في التاريخ (أو بلا هيكل)."""
    on_date = on_date or timezone.localdate()
    qs = SalaryStructure.objects.filter(employee=employee).filter(
        Q(effective_from__lte=on_date) | Q(effective_from__isnull=True)
    )
    structure = None
    for candidate in qs.order_by("-effective_from", "-id"):
        if candidate.covers(on_date):
            structure = candidate
            break
    return structure


def salary_snapshot(employee, on_date=None):
    """(أساسي، بدل سكن، بدل نقل، بدلات أخرى، سعر ساعة إضافية، يومية) من الهيكل."""
    structure = active_structure(employee, on_date)
    if structure is not None:
        return {
            "base_salary": money(structure.base_salary),
            "housing_allowance": money(structure.housing_allowance),
            "transport_allowance": money(structure.transport_allowance),
            "other_allowance": money(structure.other_allowance),
            "overtime_hour_rate": money(structure.overtime_hour_rate),
            "working_days": structure.working_days or Decimal("26"),
            "daily_work_hours": structure.daily_work_hours or Decimal("9"),
            "daily_rate": money(structure.daily_rate),
            "has_structure": True,
            "structure_id": structure.id,
        }
    base = money(employee.base_salary or ZERO)
    days = Decimal("26")
    return {
        "base_salary": base,
        "housing_allowance": ZERO,
        "transport_allowance": ZERO,
        "other_allowance": ZERO,
        "overtime_hour_rate": ZERO,
        "working_days": days,
        "daily_work_hours": Decimal("9"),
        "daily_rate": money(base / days) if base else ZERO,
        "has_structure": False,
        "structure_id": None,
    }


def commissions_by_employee(start, end, branch=None):
    """مجموع عمولات الورديات المغلقة لكل موظف في الفترة."""
    from sale_sessions.models import SaleSession

    branch = branch_id_of(branch)
    qs = SaleSession.objects.filter(
        status=SaleSession.Status.CLOSED,
        closed_at__date__gte=start,
        closed_at__date__lte=end,
    )
    if branch:
        qs = qs.filter(branch_id=branch)
    qs = qs.values("employee_id").annotate(total=Sum("commission_amount"))
    return {row["employee_id"]: money(row["total"]) for row in qs}


def outstanding_advances(employee, upto=None):
    """السلف المعتمدة التي لم تُسدَّد بالكامل حتى تاريخ معيّن."""
    upto = upto or timezone.localdate()
    qs = SalaryAdvance.objects.filter(
        employee=employee,
        status=SalaryAdvance.Status.APPROVED,
        date__lte=upto,
    ).order_by("date", "id")
    return [a for a in qs if a.remaining_amount > 0]


def employee_advance_total(employee, upto=None):
    return money(sum((a.remaining_amount for a in outstanding_advances(employee, upto)), ZERO))


def payroll_employees(branch=None, include_inactive=False, employee_ids=None):
    """قائمة الموظفين المؤهلين للرواتب ضمن نطاق فرع."""
    from sale_sessions.models import Employee

    branch = branch_id_of(branch)
    qs = Employee.objects.all()
    if not include_inactive:
        qs = qs.filter(is_active=True)
    if employee_ids:
        qs = qs.filter(id__in=list(employee_ids))
    if branch:
        qs = qs.filter(Q(branch_id=branch) | Q(allowed_branches__id=branch)).distinct()
    return qs.order_by("name")


def build_preview(month, branch=None, employee_ids=None, include_inactive=False):
    """معاينة قسائم رواتب لشهر وفرع — بلا كتابة في قاعدة البيانات."""
    start, end = month_bounds(month)
    branch = branch_id_of(branch)
    employees = list(payroll_employees(branch, include_inactive, employee_ids))
    commissions = commissions_by_employee(start, end, branch)
    snapshots = {employee.id: salary_snapshot(employee, start) for employee in employees}
    attendance = attendance_for(
        employees,
        start,
        end,
        lambda employee: (
            snapshots[employee.id]["working_days"],
            snapshots[employee.id]["daily_work_hours"],
        ),
    )
    rows = []
    total_base = total_gross = total_commission = total_advances = ZERO
    total_overtime = total_absence = ZERO
    for employee in employees:
        snap = snapshots[employee.id]
        gross = snap["base_salary"] + snap["housing_allowance"] + snap["transport_allowance"] + snap["other_allowance"]
        advances = outstanding_advances(employee, end)
        advances_total = money(sum((a.remaining_amount for a in advances), ZERO))
        commission = money(commissions.get(employee.id, ZERO))
        mark = attendance.get(employee.id)
        overtime_hours = mark.overtime_hours if mark else ZERO
        overtime_amount = money(overtime_hours * snap["overtime_hour_rate"])
        absence_days = mark.absence_days if mark else ZERO
        absence_deduction = money(absence_days * snap["daily_rate"])
        total_base += snap["base_salary"]
        total_gross += gross
        total_commission += commission
        total_advances += advances_total
        total_overtime += overtime_amount
        total_absence += absence_deduction
        rows.append({
            "employee": employee.id,
            "employee_name": employee.name,
            "branch": employee.branch_id,
            "branch_name": employee.branch.name if employee.branch_id else "",
            "position": employee.position or "",
            "department": employee.department or "",
            "has_structure": snap["has_structure"],
            "working_days": float(snap.get("working_days") or Decimal("26")),
            "base_salary": float(snap["base_salary"]),
            "housing_allowance": float(snap["housing_allowance"]),
            "transport_allowance": float(snap["transport_allowance"]),
            "other_allowance": float(snap["other_allowance"]),
            "overtime_hour_rate": float(snap["overtime_hour_rate"]),
            "daily_rate": float(snap["daily_rate"]),
            "commission_amount": float(commission),
            "advances_total": float(advances_total),
            "advances_count": len(advances),
            "gross": float(money(gross)),
            "attendance": mark.as_dict() if mark else untracked(employee.id, snap["working_days"], snap["daily_work_hours"]).as_dict(),
            "overtime_hours": float(overtime_hours),
            "overtime_amount": float(overtime_amount),
            "absence_days": float(absence_days),
            "absence_deduction": float(absence_deduction),
            "net_estimate": float(money(gross + commission + overtime_amount - advances_total - absence_deduction)),
        })
    return {
        "month": start.isoformat(),
        "month_end": end.isoformat(),
        "rows": rows,
        "totals": {
            "employees": len(rows),
            "base_salary": money(total_base),
            "gross": money(total_gross),
            "commission": money(total_commission),
            "advances": money(total_advances),
            "overtime": money(total_overtime),
            "absence_deduction": money(total_absence),
        },
    }


@transaction.atomic
def generate_run(month, branch=None, created_by=None, employee_ids=None, include_commission=True):
    """ينشئ مسيّراً وقسائمه من المعاينة. القسائم الموجودة لنفس الموظف تُحدَّث."""
    start, end = month_bounds(month)
    branch = branch_id_of(branch)
    if PayrollRun.objects.filter(month=start, branch=branch).exists():
        raise ValueError("يوجد مسيّر رواتب لهذا الشهر والفرع بالفعل")

    from sale_sessions.models import Employee

    run = PayrollRun.objects.create(month=start, branch=branch, created_by=created_by)
    preview = build_preview(start, branch, employee_ids)
    commissions = commissions_by_employee(start, end, branch) if include_commission else {}

    for row in preview["rows"]:
        emp = Employee.objects.select_related("branch").get(id=row["employee"])
        snap = salary_snapshot(emp, start)
        advances = outstanding_advances(emp, end)
        advance_deduction = money(min(
            sum((a.remaining_amount for a in advances), ZERO),
            money(row["gross"]),
        ))
        Payslip.objects.create(
            run=run,
            employee=emp,
            branch=emp.branch,
            base_salary=Decimal(str(row["base_salary"])),
            housing_allowance=Decimal(str(row["housing_allowance"])),
            transport_allowance=Decimal(str(row["transport_allowance"])),
            other_allowance=Decimal(str(row["other_allowance"])),
            working_days=Decimal(str(row["working_days"])),
            daily_rate=snap["daily_rate"],
            overtime_hour_rate=snap["overtime_hour_rate"],
            overtime_hours=Decimal(str(row["overtime_hours"])),
            overtime_amount=Decimal(str(row["overtime_amount"])),
            absence_days=Decimal(str(row["absence_days"])),
            absence_deduction=Decimal(str(row["absence_deduction"])),
            commission_amount=commissions.get(emp.id, Decimal(str(row["commission_amount"]))),
            advance_deduction=advance_deduction,
            payment_method=run.payment_method or Payslip.PaymentMethod.CASH,
        )
    return run


@transaction.atomic
def apply_advance_settlement(payslip, amount=None):
    """يسجّل خصم السلفة كسداد على أقدم سلف، ويعيد حساب المتبقي."""
    amount = money(amount if amount is not None else payslip.advance_deduction)
    if amount <= 0:
        payslip.advance_installments.all().delete()
        return ZERO
    payslip.advance_installments.all().delete()
    remaining = amount
    touched = []
    # السلف المستحقة على الشهر كاملاً (نهاية الشهر لا أوله).
    month_end = month_bounds(payslip.run.month)[1]
    for advance in outstanding_advances(payslip.employee, month_end):
        take = money(min(advance.remaining_amount, remaining))
        if take <= 0:
            break
        AdvanceInstallment.objects.create(
            advance=advance,
            date=payslip.run.month,
            amount=take,
            method=AdvanceInstallment.Method.DEDUCTION,
            payslip=payslip,
            notes="خصم من الراتب",
        )
        remaining = money(remaining - take)
        touched.append(advance)
        if remaining <= 0:
            break
    for advance in touched:
        advance.refresh_from_db()
        if advance.is_settled and advance.status != SalaryAdvance.Status.SETTLED:
            advance.status = SalaryAdvance.Status.SETTLED
            advance.settled_at = timezone.now()
            advance.save(update_fields=["status", "settled_at", "updated_at"])
    return money(amount - remaining)


@transaction.atomic
def approve_run(run):
    if run.status != PayrollRun.Status.DRAFT:
        raise ValueError("لا يمكن اعتماد مسيّر ليس في حالة مسودة")
    for payslip in run.payslips.select_related("employee"):
        apply_advance_settlement(payslip)
    run.status = PayrollRun.Status.APPROVED
    run.approved_at = timezone.now()
    run.save(update_fields=["status", "approved_at", "updated_at"])
    return run


@transaction.atomic
def pay_run(run, payment_method=None, paid_at=None):
    if run.status not in (PayrollRun.Status.DRAFT, PayrollRun.Status.APPROVED):
        raise ValueError("لا يمكن صرف مسيّر بهذه الحالة")
    for payslip in run.payslips.select_related("employee"):
        apply_advance_settlement(payslip)
        payslip.is_paid = True
        payslip.paid_at = paid_at or timezone.now()
        if payment_method:
            payslip.payment_method = payment_method
        payslip.save(update_fields=["is_paid", "paid_at", "payment_method", "updated_at"])
    run.status = PayrollRun.Status.PAID
    run.paid_at = timezone.now()
    if payment_method:
        run.payment_method = payment_method
    run.save(update_fields=["status", "paid_at", "payment_method", "updated_at"])
    try:
        from accounting.services import post_payroll_run

        post_payroll_run(run)
    except Exception:  # pragma: no cover - لا نُسقط الصرف بسبب الترحيل
        import logging

        logging.getLogger("accounting").exception("فشل ترحيل قيد الرواتب (mسيّر=%s)", run.pk)
    return run


@transaction.atomic
def cancel_run(run):
    if run.status == PayrollRun.Status.PAID:
        raise ValueError("لا يمكن إلغاء مسيّر مصروف")
    touched = set()
    for payslip in run.payslips.all():
        touched.update(p.advance_id for p in payslip.advance_installments.all())
        payslip.advance_installments.all().delete()
    run.payslips.all().delete()
    # السلف التي سُدِّدت من هذا المسيّر تعود معتمدة بعد حذف سداداتها.
    for advance in SalaryAdvance.objects.filter(id__in=touched):
        advance.refresh_from_db()
        if advance.status == SalaryAdvance.Status.SETTLED and not advance.is_settled:
            advance.status = SalaryAdvance.Status.APPROVED
            advance.settled_at = None
            advance.save(update_fields=["status", "settled_at", "updated_at"])
    run.status = PayrollRun.Status.CANCELLED
    run.save(update_fields=["status", "updated_at"])
    return run


@transaction.atomic
def approve_advance(advance):
    if advance.status != SalaryAdvance.Status.PENDING:
        raise ValueError("السلفة ليست في حالة مسودة")
    advance.status = SalaryAdvance.Status.APPROVED
    advance.save(update_fields=["status", "updated_at"])
    try:
        from accounting.services import post_salary_advance

        post_salary_advance(advance)
    except Exception:  # pragma: no cover
        import logging

        logging.getLogger("accounting").exception("فشل ترحيل قيد السلفة (id=%s)", advance.pk)
    return advance


@transaction.atomic
def reject_advance(advance):
    if advance.status not in (SalaryAdvance.Status.PENDING, SalaryAdvance.Status.APPROVED):
        raise ValueError("لا يمكن رفض السلفة بهذه الحالة")
    if advance.status == SalaryAdvance.Status.APPROVED:
        _unpost_advance(advance)
    advance.status = SalaryAdvance.Status.REJECTED
    advance.save(update_fields=["status", "updated_at"])
    return advance


def _unpost_advance(advance):
    try:
        from accounting.services import unpost_source
        from accounting.models import JournalEntry

        unpost_source(JournalEntry.Source.SALARY_ADVANCE, advance.pk)
    except Exception:  # pragma: no cover
        import logging

        logging.getLogger("accounting").exception("فشل عكس قيد السلفة (id=%s)", advance.pk)


@transaction.atomic
def repay_advance(advance, amount, method=None, paid_on=None):
    """سداد (كامل أو جزئي) لسلفة — نقداً أو خصماً من الراتب."""
    remaining = advance.remaining_amount
    amount = money(min(money(amount), remaining))
    if amount <= 0:
        raise ValueError("لا يوجد مبلغ مستحق سداد على السلفة")
    installment = AdvanceInstallment.objects.create(
        advance=advance,
        date=paid_on or timezone.localdate(),
        amount=amount,
        method=method or AdvanceInstallment.Method.CASH,
    )
    advance.refresh_from_db()
    if advance.is_settled and advance.status != SalaryAdvance.Status.SETTLED:
        advance.status = SalaryAdvance.Status.SETTLED
        advance.settled_at = timezone.now()
        advance.save(update_fields=["status", "settled_at", "updated_at"])
    if installment.method in (AdvanceInstallment.Method.CASH, AdvanceInstallment.Method.TRANSFER):
        try:
            from accounting.services import post_advance_repayment

            post_advance_repayment(advance, installment)
        except Exception:  # pragma: no cover
            import logging

            logging.getLogger("accounting").exception("فشل ترحيل سداد السلفة (id=%s)", advance.pk)
    return installment


def statement_rows(employee, date_from=None, date_to=None):
    """كشف حساب موظف: الرواتب المصروفة والسلف الممنوحة والمسددة."""
    to = date_to or timezone.localdate()
    start = date_from or to.replace(day=1)
    rows = []

    payslips = Payslip.objects.filter(
        employee=employee, run__month__gte=start, run__month__lte=to, run__status=PayrollRun.Status.PAID
    ).select_related("run")
    for p in payslips:
        rows.append({
            "date": p.paid_at.date() if p.paid_at else p.run.month,
            "type": "payslip",
            "type_label": "راتب مصروف",
            "debit": float(p.gross),
            "credit": float(p.net_pay),
            "net": float(p.net_pay),
            "ref": f"مسيّر {p.run.month:%Y-%m}",
            "notes": p.notes or "",
        })

    advances = SalaryAdvance.objects.filter(
        employee=employee, date__gte=start, date__lte=to
    ).prefetch_related("installments")
    for a in advances:
        rows.append({
            "date": a.date,
            "type": "advance",
            "type_label": "سلفة ممنوحة",
            "debit": float(a.amount),
            "credit": float(a.recovered_amount),
            "net": float(a.remaining_amount),
            "ref": f"سلفة #{a.id}",
            "notes": a.reason or "",
        })

    rows.sort(key=lambda r: (r["date"], r["type"]))
    advances_total = sum((a.amount for a in advances), ZERO)
    recovered = sum((a.recovered_amount for a in advances), ZERO)
    net_paid = sum((p.net_pay for p in payslips), ZERO)
    return {
        "employee": employee.id,
        "employee_name": employee.name,
        "rows": rows,
        "totals": {
            "net_paid": money(net_paid),
            "advances": money(advances_total),
            "recovered": money(recovered),
            "outstanding": money(sum((a.remaining_amount for a in advances), ZERO)),
        },
    }
