"""اختبارات احتساب الحضور التلقائي من الورديات.

التغطية الأساسية: العدّ بدون تكرار لليوم الواحد، رفض الوردية غير المغلقة،
سقف الغياب عند الصفر، دقة الكسور، وعدم المساس بغير المُفعَّل لهم.
"""

from datetime import date, datetime, time
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from branches.models import Branch
from payroll.attendance import (
    DEFAULT_DAILY_HOURS,
    attendance_for,
    session_hours,
    untracked,
)
from payroll.models import SalaryStructure
from sale_sessions.models import Employee, SaleSession


def _backdate(session, opened_at):
    """يكتب ``opened_at`` على وردية بعد إنشائها.

    ``SaleSession.opened_at`` حقل ``auto_now_add``، فأي قيمة نمرّرها في
    ``create()`` يُتجاهلها Django وتُستبدل بلحظة «الآن» — وهذا ما كان يُفشل
    اختبارات المدة: كل المدد كانت تُحسب صفراً. المشروع يتعامل مع ذلك بنفس
    الطريقة في ``stamp_session_creation`` عبر ``update`` لتجاوز ``pre_save``.
    """
    SaleSession.objects.filter(pk=session.pk).update(opened_at=opened_at, created_at=opened_at)
    session.opened_at = opened_at
    session.created_at = opened_at
    return session


def _session(employee, day, branch, opened=time(9, 0), closed=None, status=SaleSession.Status.CLOSED):
    day_value = date(2026, 3, day)
    opened_at = timezone.make_aware(datetime.combine(day_value, opened))
    closed_at = (
        timezone.make_aware(datetime.combine(day_value, closed))
        if closed is not None
        else None
    )
    session = SaleSession.objects.create(
        employee=employee,
        branch=branch,
        status=status,
        closed_at=closed_at,
        session_date=day_value,
    )
    return _backdate(session, opened_at)


class SessionHoursTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name="الفرع", code="A1")

    def test_closed_session_duration_in_hours(self):
        employee = Employee.objects.create(name="موظف")
        session = _session(employee, 1, self.branch, opened=time(9, 0), closed=time(17, 30))
        self.assertEqual(session_hours(session), Decimal("8.50"))

    def test_open_session_is_zero(self):
        employee = Employee.objects.create(name="موظف")
        session = _session(employee, 2, self.branch, status=SaleSession.Status.OPEN)
        self.assertEqual(session_hours(session), Decimal("0.00"))

    def test_missing_close_time_is_zero(self):
        employee = Employee.objects.create(name="موظف")
        session = _session(employee, 3, self.branch, status=SaleSession.Status.CLOSED)
        session.closed_at = None
        self.assertEqual(session_hours(session), Decimal("0.00"))

    def test_inverted_duration_is_zero(self):
        employee = Employee.objects.create(name="موظف")
        session = _session(employee, 4, self.branch, opened=time(17, 0), closed=time(9, 0))
        self.assertEqual(session_hours(session), Decimal("0.00"))

    def test_overnight_session_counts_full_duration(self):
        employee = Employee.objects.create(name="موظف")
        session = SaleSession.objects.create(
            employee=employee,
            branch=self.branch,
            status=SaleSession.Status.CLOSED,
            closed_at=timezone.make_aware(datetime(2026, 3, 6, 4, 0)),
            session_date=date(2026, 3, 5),
        )
        _backdate(session, timezone.make_aware(datetime(2026, 3, 5, 20, 0)))
        self.assertEqual(session_hours(session), Decimal("8.00"))


class UntrackedTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name="الفرع", code="A1")

    def test_untracked_summary_is_all_zero(self):
        summary = untracked(7, Decimal("26"), Decimal("9"))
        self.assertFalse(summary.tracked)
        self.assertEqual(summary.absence_days, Decimal("0"))
        self.assertEqual(summary.overtime_hours, Decimal("0"))
        self.assertEqual(summary.sessions_count, 0)

    def test_employee_without_flag_is_not_queried(self):
        employee = Employee.objects.create(name="محاسب", attendance_tracked=False)
        _session(employee, 1, self.branch)
        summaries = attendance_for(
            [employee], date(2026, 3, 1), date(2026, 3, 31), lambda e: (Decimal("26"), Decimal("9"))
        )
        self.assertEqual(summaries, {})


class AttendanceComputationTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name="الفرع", code="A1")
        self.employee = Employee.objects.create(
            name="عامل", branch=self.branch, attendance_tracked=True
        )
        self.start, self.end = date(2026, 3, 1), date(2026, 3, 31)

    def _summarize(self, employee=None, working_days="26", daily_hours="9"):
        employee = employee or self.employee
        return attendance_for(
            [employee],
            self.start,
            self.end,
            lambda e: (Decimal(working_days), Decimal(daily_hours)),
        )[employee.id]

    def test_no_sessions_means_full_absence(self):
        summary = self._summarize()
        self.assertTrue(summary.tracked)
        self.assertEqual(summary.attended_days, Decimal("0.0"))
        self.assertEqual(summary.absence_days, Decimal("26.0"))

    def test_two_sessions_in_one_day_count_as_one_day(self):
        _session(self.employee, 5, self.branch, opened=time(9, 0), closed=time(13, 0))
        _session(self.employee, 5, self.branch, opened=time(16, 0), closed=time(20, 0))
        summary = self._summarize()
        self.assertEqual(summary.attended_days, Decimal("1.0"))
        self.assertEqual(summary.sessions_count, 1)
        self.assertEqual(summary.absence_days, Decimal("25.0"))

    def test_absent_days_rounded_to_half_day(self):
        _session(self.employee, 2, self.branch, opened=time(9, 0), closed=time(12, 0))
        summary = self._summarize()
        self.assertEqual(summary.attended_days, Decimal("1.0"))
        self.assertEqual(summary.absence_days, Decimal("25.0"))

    def test_full_attendance_yields_zero_absence(self):
        for day in range(1, 6):
            _session(self.employee, day, self.branch, opened=time(9, 0), closed=time(17, 0))
        summary = self._summarize(working_days="5")
        self.assertEqual(summary.attended_days, Decimal("5.0"))
        self.assertEqual(summary.absence_days, Decimal("0.0"))

    def test_absence_never_goes_negative(self):
        for day in range(1, 6):
            _session(self.employee, day, self.branch, opened=time(9, 0), closed=time(17, 0))
        summary = self._summarize(working_days="2")
        self.assertEqual(summary.absence_days, Decimal("0.0"))

    def test_overtime_only_beyond_daily_threshold(self):
        _session(self.employee, 7, self.branch, opened=time(8, 0), closed=time(20, 0))  # 12h -> +3
        _session(self.employee, 8, self.branch, opened=time(9, 0), closed=time(15, 0))  # 6h -> +0
        summary = self._summarize()
        self.assertEqual(summary.overtime_hours, Decimal("3.00"))

    def test_open_session_produces_no_overtime(self):
        _session(self.employee, 9, self.branch, opened=time(8, 0), status=SaleSession.Status.OPEN)
        summary = self._summarize()
        self.assertEqual(summary.overtime_hours, Decimal("0.00"))
        self.assertEqual(summary.attended_days, Decimal("1.0"))

    def test_open_session_counts_as_attendance_not_absence(self):
        """الوردية المفتوحة دليل حضور، فلا يُخصم اليوم غياباً.

        الموظف في وردية مفتوحة الآن يجب ألّا يُحتسب غائباً لمجرد أنه لم
        يُغلقها بعد — وهذا ما كان يحدث حين كان الاستعلام يقتصر على
        الورديات المغلقة.
        """
        _session(self.employee, 9, self.branch, opened=time(8, 0), status=SaleSession.Status.OPEN)
        summary = self._summarize(working_days="26")
        self.assertEqual(summary.absence_days, Decimal("25.0"))
        self.assertEqual(summary.sessions_count, 1)

    def test_open_and_closed_sessions_on_same_day_count_once(self):
        _session(self.employee, 9, self.branch, opened=time(8, 0), status=SaleSession.Status.OPEN)
        _session(self.employee, 9, self.branch, opened=time(16, 0), closed=time(20, 0))
        summary = self._summarize()
        self.assertEqual(summary.attended_days, Decimal("1.0"))
        self.assertEqual(summary.sessions_count, 1)
        # الإضافي من المغلقة وحدها: 4 ساعات أقل من 9 = لا إضافي
        self.assertEqual(summary.overtime_hours, Decimal("0.00"))

    def test_sessions_outside_month_are_ignored(self):
        _session(self.employee, 1, self.branch, opened=time(8, 0), closed=time(20, 0))
        summary = attendance_for(
            [self.employee], date(2026, 4, 1), date(2026, 4, 30), lambda e: (Decimal("26"), Decimal("9"))
        )[self.employee.id]
        self.assertEqual(summary.attended_days, Decimal("0.0"))
        self.assertEqual(summary.sessions_count, 0)

    def test_legacy_session_without_date_uses_opened_at(self):
        session = SaleSession.objects.create(
            employee=self.employee,
            branch=self.branch,
            status=SaleSession.Status.CLOSED,
            closed_at=timezone.make_aware(datetime(2026, 3, 11, 19, 0)),
        )
        _backdate(session, timezone.make_aware(datetime(2026, 3, 11, 9, 0)))
        self.assertIsNone(session.session_date)
        summary = self._summarize()
        self.assertEqual(summary.attended_days, Decimal("1.0"))
        self.assertEqual(summary.overtime_hours, Decimal("1.00"))

    def test_custom_daily_hours_threshold(self):
        _session(self.employee, 12, self.branch, opened=time(8, 0), closed=time(14, 0))  # 6h
        self.assertEqual(self._summarize(daily_hours="9").overtime_hours, Decimal("0.00"))
        self.assertEqual(self._summarize(daily_hours="4").overtime_hours, Decimal("2.00"))

    def test_zero_daily_hours_disables_overtime(self):
        _session(self.employee, 13, self.branch, opened=time(8, 0), closed=time(20, 0))
        self.assertEqual(self._summarize(daily_hours="0").overtime_hours, Decimal("0.00"))

    def test_summary_as_dict_is_json_safe(self):
        summary = self._summarize()
        payload = summary.as_dict()
        self.assertIsInstance(payload["absence_days"], float)
        self.assertIsInstance(payload["overtime_hours"], float)
        self.assertTrue(payload["tracked"])

    def test_multiple_employees_isolated(self):
        other = Employee.objects.create(
            name="عامل آخر", branch=self.branch, attendance_tracked=True
        )
        _session(self.employee, 15, self.branch, opened=time(9, 0), closed=time(13, 0))
        _session(other, 16, self.branch, opened=time(9, 0), closed=time(13, 0))
        _session(other, 17, self.branch, opened=time(9, 0), closed=time(13, 0))
        summaries = attendance_for(
            [self.employee, other],
            self.start,
            self.end,
            lambda e: (Decimal("26"), Decimal("9")),
        )
        self.assertEqual(summaries[self.employee.id].attended_days, Decimal("1.0"))
        self.assertEqual(summaries[other.id].attended_days, Decimal("2.0"))

    def test_mixed_tracked_and_untracked_batch(self):
        office = Employee.objects.create(name="إداري", branch=self.branch)
        _session(self.employee, 18, self.branch, opened=time(9, 0), closed=time(13, 0))
        summaries = attendance_for(
            [self.employee, office],
            self.start,
            self.end,
            lambda e: (Decimal("26"), Decimal("9")),
        )
        self.assertIn(self.employee.id, summaries)
        self.assertNotIn(office.id, summaries)

    def test_empty_batch_returns_empty(self):
        self.assertEqual(attendance_for([], self.start, self.end, lambda e: (Decimal("26"), Decimal("9"))), {})

    def test_garbage_terms_fall_back_to_defaults(self):
        summary = attendance_for(
            [self.employee], self.start, self.end, lambda e: (None, "غير رقم")
        )[self.employee.id]
        self.assertEqual(summary.working_days, Decimal("26"))
        self.assertEqual(summary.daily_work_hours, DEFAULT_DAILY_HOURS)

    def test_structure_daily_work_hours_used_as_threshold(self):
        SalaryStructure.objects.create(
            employee=self.employee,
            base_salary=Decimal("3000"),
            working_days=Decimal("26"),
            daily_work_hours=Decimal("5"),
        )
        _session(self.employee, 20, self.branch, opened=time(9, 0), closed=time(17, 0))  # 8h → +3
        summary = attendance_for(
            [self.employee],
            self.start,
            self.end,
            lambda e: (
                SalaryStructure.objects.filter(employee=e).first().working_days,
                SalaryStructure.objects.filter(employee=e).first().daily_work_hours,
            ),
        )[self.employee.id]
        self.assertEqual(summary.overtime_hours, Decimal("3.00"))
