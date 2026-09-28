"""احتساب الحضور التلقائي من الورديات.

الوردية هي المصدر الوحيد للحقيقة في هذا النظام، فدقّة أرقام الرواتب تتوقّف على
مدى دقّة قراءتها. القواعد:

- **يوم حضور**: كل يوم فيه وردية واحدة على الأقل خلال الشهر، مفتوحةً كانت أو
  مغلقة. أكثر من وردية في اليوم نفسه لا تُحتسب أكثر من يوم حضور.
- **غياب**: ``أيام العمل الشهرية − أيام الحضور``، ولا ينزل تحت الصفر أبداً.
- **عمل إضافي**: لكل وردية *مغلقة*، ما زاد مدتها على ``ساعات العمل اليومية``
  في الهيكل. الوردية المفتوحة أو بلا وقت إغلاق لا تُحتسب — لا يمكن الجزم بمدتها،
  وأحتسابها قد يُضخّم الراتب على غير يقين.

الاحتساب **اختياري** لكل موظف عبر ``Employee.attendance_tracked``: موظف بلا
ورديات (محاسب، إداري) لا معنى لخصم غيابه من راتبه.

الاحتساب لدفعة موظفين واحدة باستعلام واحد لكل الجلسات، لا استعلاماً لكل موظف.
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from sale_sessions.models import SaleSession
from sale_sessions.services import session_business_date

HOURS_QUANTUM = Decimal("0.01")
HALF_DAY = Decimal("0.5")
DEFAULT_WORKING_DAYS = Decimal("26")
DEFAULT_DAILY_HOURS = Decimal("9")
ZERO = Decimal("0")


@dataclass
class AttendanceSummary:
    employee_id: int
    tracked: bool
    working_days: Decimal
    daily_work_hours: Decimal
    attended_days: Decimal
    absence_days: Decimal
    overtime_hours: Decimal
    sessions_count: int

    def as_dict(self):
        return {
            "tracked": self.tracked,
            "working_days": float(self.working_days),
            "daily_work_hours": float(self.daily_work_hours),
            "attended_days": float(self.attended_days),
            "absence_days": float(self.absence_days),
            "overtime_hours": float(self.overtime_hours),
            "sessions_count": self.sessions_count,
        }


def _to_decimal(value, fallback):
    if value in (None, ""):
        return fallback
    try:
        return Decimal(str(value))
    except Exception:
        return fallback


def _quantize_half_day(value):
    """يقرّب أيام الحضور/الغياب إلى أقرب نصف يوم — فالوردية القصيرة نصف حضور."""
    units = (Decimal(value) / HALF_DAY).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return units * HALF_DAY


def _quantize_hours(value):
    return Decimal(value).quantize(HOURS_QUANTUM, rounding=ROUND_HALF_UP)


def session_hours(session):
    """مدة الوردية بالساعات، أو صفر إن لم تُغلق أو كانت المدة غير منطقية."""
    if not session.closed_at or not session.opened_at:
        return ZERO
    seconds = (session.closed_at - session.opened_at).total_seconds()
    if seconds <= 0:
        return ZERO
    return _quantize_hours(Decimal(str(seconds)) / Decimal("3600"))


def untracked(employee_id, working_days, daily_work_hours):
    """ملخّص صفري لموظف غير مُفعَّل له الحضور التلقائي."""
    return AttendanceSummary(
        employee_id=employee_id,
        tracked=False,
        working_days=working_days,
        daily_work_hours=daily_work_hours,
        attended_days=ZERO,
        absence_days=ZERO,
        overtime_hours=ZERO,
        sessions_count=0,
    )


def attendance_for(employees, start, end, terms_for):
    """يحسب الحضور لمجموعة موظفين.

    ``terms_for(employee)`` تُرجع ``(working_days, daily_work_hours)`` من هيكل
    الراتب الساري، فيبقى المصدر الوحيد لأرقام workday.
    """
    employees = list(employees)
    terms = {}
    for employee in employees:
        working_days, daily_hours = terms_for(employee)
        terms[employee.id] = (
            _to_decimal(working_days, DEFAULT_WORKING_DAYS),
            _to_decimal(daily_hours, DEFAULT_DAILY_HOURS),
        )

    tracked_ids = [e.id for e in employees if getattr(e, "attendance_tracked", False)]
    if not tracked_ids:
        return {}

    by_employee = {employee_id: [] for employee_id in tracked_ids}
    # نجلب الورديات المفتوحة والمغلقة معاً: يوم الحضور يُعدّ من «كل يوم فيه
    # وردية واحدة على الأقل» دون شرط الإغلاق. كان الاستعلام يقتصر على
    # المغلقة، فيُخصم من الموظف يومُه وهو في وردية مفتوحة الآن — عقوبة على
    # الحضور لا على الغياب. الإغلاق شرطُ العمل الإضافي وحده، لأن مدّة
    # الوردية المفتوحة غير معلومة.
    sessions = SaleSession.objects.filter(employee_id__in=tracked_ids).only(
        "employee_id", "opened_at", "closed_at", "session_date", "status"
    )
    for session in sessions:
        business = session_business_date(session)
        if start <= business <= end:
            by_employee[session.employee_id].append(session)

    summaries = {}
    for employee in employees:
        if employee.id not in by_employee:
            continue
        working_days, daily_hours = terms[employee.id]
        own = by_employee[employee.id]
        attended = _quantize_half_day(Decimal(len({session_business_date(s) for s in own})))
        overtime = ZERO
        for session in own:
            if session.status != SaleSession.Status.CLOSED:
                continue
            hours = session_hours(session)
            if daily_hours > 0 and hours > daily_hours:
                overtime += hours - daily_hours
        absence = max(ZERO, working_days - attended)
        summaries[employee.id] = AttendanceSummary(
            employee_id=employee.id,
            tracked=True,
            working_days=working_days,
            daily_work_hours=daily_hours,
            attended_days=attended,
            absence_days=_quantize_half_day(absence),
            overtime_hours=_quantize_hours(overtime),
            sessions_count=len({session_business_date(s) for s in own}),
        )
    return summaries
