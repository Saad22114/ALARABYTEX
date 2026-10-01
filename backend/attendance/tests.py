# -*- coding: utf-8 -*-
"""اختبارات الحضور والانصراف.

المرساة في كل اختبار: **الحدّ**. لا يكفي أن يعمل الحساب في منتصف المسار؛
السؤال هو ماذا يحدث *عند* الحدّ بالضبط، لأن الخطأ كله يسكن هناك:

* دقيقةٌ واحدة بعد نهاية نافذة الدخول + دقيقة سماح = صفر تأخير.
* دقيقةٌ واحدة بعدها = تأخير.
* خروجٌ قبل بداية نافذة الخروج = انصراف مبكر... إلّا إذا كان داخل السماح.
* يومٌ عملٍ بعدّادٍ أكبر منه = عملٌ إضافي، ولو كان قد تأخّر ساعتين.
"""

from datetime import date, datetime, time, timedelta

from django.test import TestCase
from django.utils import timezone

from attendance.models import AttendancePolicy, AttendanceRecord
from attendance.services import (
    FRIDAY,
    business_date,
    day_sheet,
    half_day_round,
    is_working_day,
    record_login,
    record_logout,
    recompute,
    summarize,
)
from sale_sessions.models import Employee


def at(day, hour, minute=0, tz=None):
    """لحظةٌ محلية في يومٍ بعينه، بتوقيت المشروع."""
    return timezone.make_aware(
        datetime.combine(day, time(hour=hour, minute=minute)),
        tz or timezone.get_current_timezone(),
    )


class PolicyFixture(TestCase):
    """سياسة معروفة الأرقام: كل حدٍّ في هذا الملف مشتقٌّ منها."""

    @classmethod
    def setUpTestData(cls):
        cls.employee = Employee.objects.create(name="حسام", role="sales")

    def setUp(self):
        self.policy = AttendancePolicy.load()
        self.policy.workday_minutes = 480      # 8 ساعات
        self.policy.grace_minutes = 5
        self.policy.login_window_start = time(7, 0)
        self.policy.login_window_end = time(9, 0)
        self.policy.logout_window_start = time(16, 0)
        self.policy.logout_window_end = time(18, 0)
        self.policy.day_cutoff_hour = 3
        self.policy.weekend_days = [FRIDAY]    # الجمعة عطلة
        self.policy.enabled = True
        self.policy.save()

    def make(self, day, login=None, logout=None, **extra):
        record = AttendanceRecord.objects.create(
            employee=self.employee,
            date=day,
            login_at=login,
            logout_at=logout,
            **extra,
        )
        return recompute(record, self.policy)


class BusinessDateTests(TestCase):
    def setUp(self):
        self.policy = AttendancePolicy.load()
        self.policy.day_cutoff_hour = 3
        self.policy.save()

    def test_after_cutoff_belongs_to_the_same_day(self):
        day = date(2026, 9, 28)
        self.assertEqual(
            business_date(at(day, 3, 0), self.policy), day
        )

    def test_one_minute_before_cutoff_belongs_to_the_previous_day(self):
        # 02:59 يوم الاثنين هو فيوردية الأحد: من ينهي ليلاً ليس غائباً
        # عن يومٍ بدأ قبل أن يولد.
        self.assertEqual(
            business_date(at(date(2026, 9, 28), 2, 59), self.policy),
            date(2026, 9, 27),
        )

    def test_midnight_is_the_previous_day(self):
        self.assertEqual(
            business_date(at(date(2026, 9, 28), 0, 0), self.policy),
            date(2026, 9, 27),
        )

    def test_cutoff_is_configurable(self):
        self.policy.day_cutoff_hour = 0
        self.policy.save()
        self.assertEqual(
            business_date(at(date(2026, 9, 28), 0, 0), self.policy),
            date(2026, 9, 28),
        )


class WorkingDayTests(TestCase):
    def setUp(self):
        self.policy = AttendancePolicy.load()
        self.policy.weekend_days = [FRIDAY]
        self.policy.save()

    def test_friday_is_off(self):
        # 2026-09-25 جمعة، وترقيمها في date.weekday() هو 4.
        self.assertEqual(date(2026, 9, 25).weekday(), FRIDAY)
        self.assertFalse(is_working_day(date(2026, 9, 25), self.policy))

    def test_thursday_is_a_working_day(self):
        self.assertTrue(is_working_day(date(2026, 9, 24), self.policy))

    def test_empty_weekend_means_every_day_works(self):
        # قائمة فارغة تعني «لا عطلة أسبوعية»، لا «كل الأيام عطلة».
        self.policy.weekend_days = []
        self.policy.save()
        self.assertTrue(is_working_day(date(2026, 9, 25), self.policy))


class LatenessBoundaryTests(PolicyFixture):
    def test_arriving_at_the_end_of_the_window_is_not_late(self):
        record = self.make(date(2026, 9, 28), login=at(date(2026, 9, 28), 9, 0))
        self.assertEqual(record.late_minutes, 0)
        self.assertEqual(record.status, AttendanceRecord.Status.INSIDE)

    def test_arriving_one_minute_late_is_swallowed_by_grace(self):
        # 09:01 متأخّر دقيقة، والسماح خمس: صفر.
        record = self.make(date(2026, 9, 28), login=at(date(2026, 9, 28), 9, 1))
        self.assertEqual(record.late_minutes, 0)

    def test_arriving_one_minute_past_grace_is_late_by_one_minute(self):
        # 09:06 = ست دقائق بعد النهاية، ناقص السماح = دقيقة واحدة.
        record = self.make(date(2026, 9, 28), login=at(date(2026, 9, 28), 9, 6))
        self.assertEqual(record.late_minutes, 1)
        self.assertEqual(record.status, AttendanceRecord.Status.LATE)

    def test_arriving_exactly_at_grace_is_not_late(self):
        # 09:05 = خمس دقائق = السماح كلّه. الحدّ مُغلق من جهة اللطف.
        record = self.make(date(2026, 9, 28), login=at(date(2026, 9, 28), 9, 5))
        self.assertEqual(record.late_minutes, 0)

    def test_arriving_early_is_never_late(self):
        # من جاء قبل الدوام لم يتأخّر ولو بُدئت المحاسبة من بداية النافذة.
        record = self.make(date(2026, 9, 28), login=at(date(2026, 9, 28), 5, 0))
        self.assertEqual(record.late_minutes, 0)

    def test_zero_grace_makes_the_boundary_strict(self):
        self.policy.grace_minutes = 0
        self.policy.save()
        record = self.make(date(2026, 9, 28), login=at(date(2026, 9, 28), 9, 1))
        self.assertEqual(record.late_minutes, 1)


class EarlyLeaveBoundaryTests(PolicyFixture):
    def test_leaving_at_the_start_of_the_window_is_not_early(self):
        record = self.make(
            date(2026, 9, 28),
            login=at(date(2026, 9, 28), 8, 0),
            logout=at(date(2026, 9, 28), 16, 0),
        )
        self.assertEqual(record.early_leave_minutes, 0)
        self.assertEqual(record.status, AttendanceRecord.Status.PRESENT)

    def test_leaving_one_minute_early_is_swallowed_by_grace(self):
        record = self.make(
            date(2026, 9, 28),
            login=at(date(2026, 9, 28), 8, 0),
            logout=at(date(2026, 9, 28), 15, 59),
        )
        self.assertEqual(record.early_leave_minutes, 0)

    def test_leaving_one_minute_past_grace_is_early_by_one_minute(self):
        # 15:54 = ست دقائق قبل النافذة، ناقص السماح = دقيقة.
        record = self.make(
            date(2026, 9, 28),
            login=at(date(2026, 9, 28), 8, 0),
            logout=at(date(2026, 9, 28), 15, 54),
        )
        self.assertEqual(record.early_leave_minutes, 1)
        self.assertEqual(record.status, AttendanceRecord.Status.EARLY_LEAVE)

    def test_leaving_after_the_window_is_not_early(self):
        record = self.make(
            date(2026, 9, 28),
            login=at(date(2026, 9, 28), 8, 0),
            logout=at(date(2026, 9, 28), 23, 0),
        )
        self.assertEqual(record.early_leave_minutes, 0)


class WorkedMinutesTests(PolicyFixture):
    def test_worked_minutes_is_the_gap_between_the_two_moments(self):
        record = self.make(
            date(2026, 9, 28),
            login=at(date(2026, 9, 28), 8, 0),
            logout=at(date(2026, 9, 28), 17, 30),
        )
        self.assertEqual(record.worked_minutes, 570)

    def test_worked_minutes_stays_empty_while_the_row_is_open(self):
        # «داخل الدوام» ساعتُه مجهولة لا صفر: لو صُفّر لبدا من لم يدخل
        # كأنه حاضر بلا عمل.
        record = self.make(date(2026, 9, 28), login=at(date(2026, 9, 28), 8, 0))
        self.assertIsNone(record.worked_minutes)
        self.assertEqual(record.status, AttendanceRecord.Status.INSIDE)

    def test_seconds_are_dropped_not_rounded_up(self):
        # 08:00:00 -> 08:00:59 تسع وخمسون دقيقة، لا ستّين. التقريب للأعلى
        # يجعل كل يومٍ فيه ثوانٍ يُحسَب ساعةً زائدة.
        login = at(date(2026, 9, 28), 8, 0) + timedelta(seconds=0)
        logout = at(date(2026, 9, 28), 8, 59) + timedelta(seconds=59)
        record = self.make(date(2026, 9, 28), login=login, logout=logout)
        self.assertEqual(record.worked_minutes, 59)

    def test_logout_before_login_is_zero_not_negative(self):
        record = self.make(
            date(2026, 9, 28),
            login=at(date(2026, 9, 28), 17, 0),
            logout=at(date(2026, 9, 28), 9, 0),
        )
        # رقمٌ سالبٌ في حقل_duration ينتشر في كل تقريرٍ يُبنى عليه.
        self.assertEqual(record.worked_minutes, 0)

    def test_a_shift_crossing_midnight_is_measured_by_duration(self):
        record = self.make(
            date(2026, 9, 28),
            login=at(date(2026, 9, 28), 20, 0),
            logout=at(date(2026, 9, 29), 4, 0),
        )
        self.assertEqual(record.worked_minutes, 480)


class OvertimeTests(PolicyFixture):
    def test_exactly_the_workday_length_is_no_overtime(self):
        record = self.make(
            date(2026, 9, 28),
            login=at(date(2026, 9, 28), 8, 0),
            logout=at(date(2026, 9, 28), 16, 0),
        )
        self.assertEqual(record.overtime_minutes, 0)

    def test_one_minute_past_the_workday_is_one_minute_of_overtime(self):
        record = self.make(
            date(2026, 9, 28),
            login=at(date(2026, 9, 28), 8, 0),
            logout=at(date(2026, 9, 28), 16, 1),
        )
        self.assertEqual(record.overtime_minutes, 1)

    def test_a_short_day_is_never_negative_overtime(self):
        record = self.make(
            date(2026, 9, 28),
            login=at(date(2026, 9, 28), 12, 0),
            logout=at(date(2026, 9, 28), 13, 0),
        )
        self.assertEqual(record.overtime_minutes, 0)

    def test_overtime_measures_work_not_lateness(self):
        # تأخّر ساعتين وعمل حتى الواحدة: ساعتان إضافيَّتان. لو حُسب
        # الإضافي من لحظة الدوام صار صفراً، وهو ما يحوّل التأخير إلى مكرم.
        record = self.make(
            date(2026, 9, 28),
            login=at(date(2026, 9, 28), 11, 0),
            logout=at(date(2026, 9, 29), 1, 0),
        )
        self.assertEqual(record.late_minutes, 115)
        self.assertEqual(record.worked_minutes, 840)
        self.assertEqual(record.overtime_minutes, 360)

    def test_workday_length_is_configurable(self):
        self.policy.workday_minutes = 240
        self.policy.save()
        record = self.make(
            date(2026, 9, 28),
            login=at(date(2026, 9, 28), 8, 0),
            logout=at(date(2026, 9, 28), 13, 0),
        )
        self.assertEqual(record.overtime_minutes, 60)


class StatusTests(PolicyFixture):
    def test_no_login_is_absent(self):
        record = self.make(date(2026, 9, 28))
        self.assertEqual(record.status, AttendanceRecord.Status.ABSENT)
        self.assertIsNone(record.worked_minutes)

    def test_late_beats_early_leave_when_both_apply(self):
        # الحالةُ واحدة. لو رُتّبت الحقول وحدها لبقي أحدهما مخفياً،
        # فيظهر الموظف منصرِفاً مبكراً وهو متأخّر ساعة.
        record = self.make(
            date(2026, 9, 28),
            login=at(date(2026, 9, 28), 10, 0),
            logout=at(date(2026, 9, 28), 15, 0),
        )
        self.assertEqual(record.status, AttendanceRecord.Status.LATE)
        self.assertEqual(record.late_minutes, 55)
        self.assertEqual(record.early_leave_minutes, 55)

    def test_an_excuse_overrides_the_derived_status(self):
        record = self.make(
            date(2026, 9, 28),
            login=at(date(2026, 9, 28), 12, 0),
            excuse=AttendanceRecord.Excuse.SICK,
        )
        # الدقائق تبقى كما هي: المبرّر لا يمحو الواقع، بل يشرحه.
        self.assertEqual(record.status, AttendanceRecord.Status.EXCUSED)
        self.assertEqual(record.late_minutes, 175)

    def test_a_late_arrival_with_no_logout_is_late_not_inside(self):
        record = self.make(date(2026, 9, 28), login=at(date(2026, 9, 28), 10, 0))
        self.assertEqual(record.status, AttendanceRecord.Status.LATE)

    def test_an_on_time_arrival_with_no_logout_is_inside(self):
        record = self.make(date(2026, 9, 28), login=at(date(2026, 9, 28), 8, 0))
        self.assertEqual(record.status, AttendanceRecord.Status.INSIDE)


class RecomputeTests(PolicyFixture):
    def test_recompute_is_pure_with_respect_to_the_clock(self):
        # إعادة الحساب بلا تغييرٍ في المدخلات لا تُحرّك الأرقام: لو
        # كانت تعتمد على «الآن» لتغيّرت كلّما استُدعيت، فاختلّ التقارير.
        record = self.make(
            date(2026, 9, 28),
            login=at(date(2026, 9, 28), 9, 30),
            logout=at(date(2026, 9, 28), 16, 30),
        )
        before = (record.late_minutes, record.worked_minutes, record.status)
        for _ in range(3):
            recompute(record, self.policy)
            record.refresh_from_db()
            self.assertEqual(
                (record.late_minutes, record.worked_minutes, record.status), before
            )

    def test_widening_the_window_clears_stored_lateness(self):
        record = self.make(date(2026, 9, 28), login=at(date(2026, 9, 28), 9, 30))
        self.assertEqual(record.late_minutes, 25)
        self.policy.login_window_end = time(10, 0)
        self.policy.save()
        recompute(record, self.policy)
        record.refresh_from_db()
        self.assertEqual(record.late_minutes, 0)

    def test_recompute_saves_so_the_database_agrees_with_the_object(self):
        record = self.make(date(2026, 9, 28), login=at(date(2026, 9, 28), 10, 0))
        AttendanceRecord.objects.filter(pk=record.pk).update(late_minutes=999)
        recompute(record, self.policy)
        record.refresh_from_db()
        self.assertEqual(record.late_minutes, 55)


class LoginLogoutTests(PolicyFixture):
    def test_login_opens_a_row_for_today(self):
        moment = at(date(2026, 9, 28), 8, 0)
        record = record_login(self.employee, when=moment, policy=self.policy)
        self.assertIsNotNone(record.login_at)
        self.assertIsNone(record.logout_at)
        self.assertEqual(record.status, AttendanceRecord.Status.INSIDE)

    def test_a_second_login_keeps_the_first_moment(self):
        # نسي الموظف أن يخرج وعاد في المساء: ساعةُ العمل الأولى لا
        # تضيع بين سجلّين.
        first = at(date(2026, 9, 28), 8, 0)
        record_login(self.employee, when=first, policy=self.policy)
        again = at(date(2026, 9, 28), 14, 0)
        record = record_login(self.employee, when=again, policy=self.policy)
        self.assertEqual(record.login_at, first)

    def test_logout_closes_the_open_row_and_measures_the_gap(self):
        record_login(self.employee, when=at(date(2026, 9, 28), 8, 0), policy=self.policy)
        record = record_logout(
            self.employee, when=at(date(2026, 9, 28), 17, 0), policy=self.policy
        )
        self.assertIsNotNone(record.logout_at)
        self.assertEqual(record.worked_minutes, 540)

    def test_logout_without_login_creates_nothing(self):
        # «خرج ولم يدخل» ليس انصرافاً، بل خطأٌ في بيانات الدخول. لو
        # أنشأناه لظهر الغائب سطراً من عنده لا سطراً من عند الدليل.
        self.assertIsNone(
            record_logout(self.employee, when=at(date(2026, 9, 28), 17, 0),
                          policy=self.policy)
        )
        self.assertEqual(AttendanceRecord.objects.count(), 0)

    def test_a_disabled_policy_writes_nothing(self):
        self.policy.enabled = False
        self.policy.save()
        self.assertIsNone(
            record_login(self.employee, when=at(date(2026, 9, 28), 8, 0),
                         policy=self.policy)
        )
        self.assertEqual(AttendanceRecord.objects.count(), 0)

    def test_a_second_logout_keeps_the_first_moment(self):
        record_login(self.employee, when=at(date(2026, 9, 28), 8, 0), policy=self.policy)
        first = at(date(2026, 9, 28), 17, 0)
        record_logout(self.employee, when=first, policy=self.policy)
        record = record_logout(
            self.employee, when=at(date(2026, 9, 28), 19, 0), policy=self.policy
        )
        self.assertEqual(record.logout_at, first)

    def test_a_login_after_midnight_belongs_to_the_previous_day(self):
        record_login(self.employee, when=at(date(2026, 9, 29), 1, 0), policy=self.policy)
        self.assertTrue(
            AttendanceRecord.objects.filter(date=date(2026, 9, 28)).exists()
        )

    def test_only_one_row_per_employee_per_day(self):
        for hour in range(8, 18):
            record_login(
                self.employee, when=at(date(2026, 9, 28), hour, 0), policy=self.policy
            )
        self.assertEqual(AttendanceRecord.objects.count(), 1)

    def test_unique_together_blocks_a_second_row_for_the_same_day(self):
        from django.db import IntegrityError, transaction

        record_login(self.employee, when=at(date(2026, 9, 28), 8, 0), policy=self.policy)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AttendanceRecord.objects.create(
                    employee=self.employee, date=date(2026, 9, 28)
                )


class DaySheetTests(PolicyFixture):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.absent_employee = Employee.objects.create(name="غائب", role="sales")
        cls.present_employee = Employee.objects.create(name="حاضر", role="sales")

    def test_every_employee_gets_a_row_even_with_no_record(self):
        # الغياب حالةٌ لازمة في الجدول: يُبنى من الموظفين، لا من السجلات.
        employees = [self.employee, self.absent_employee, self.present_employee]
        rows = day_sheet(date(2026, 9, 28), employees, self.policy)
        self.assertEqual(len(rows), 3)
        by_id = {r.employee_id: r for r in rows}
        self.assertEqual(
            by_id[self.absent_employee.pk].status, AttendanceRecord.Status.ABSENT
        )

    def test_absence_is_not_charged_on_a_friday(self):
        # عطلةُ الأسبوع ليست غياباً: خصمٌ من راتبٍ مقابل يومٍ لم يُفتح
        # أبوابه أصلاً.
        rows = day_sheet(date(2026, 9, 25), [self.absent_employee], self.policy)
        self.assertEqual(rows[0].status, AttendanceRecord.Status.OFF)
        self.assertFalse(rows[0].working_day)

    def test_absence_is_charged_on_a_working_day(self):
        rows = day_sheet(date(2026, 9, 28), [self.absent_employee], self.policy)
        self.assertEqual(rows[0].status, AttendanceRecord.Status.ABSENT)
        self.assertTrue(rows[0].working_day)

    def test_the_sheet_does_not_write_to_the_database(self):
        day_sheet(date(2026, 9, 28), [self.absent_employee], self.policy)
        self.assertEqual(AttendanceRecord.objects.count(), 0)

    def test_an_existing_record_keeps_its_own_status(self):
        record_login(
            self.present_employee,
            when=at(date(2026, 9, 28), 8, 0),
            policy=self.policy,
        )
        rows = day_sheet(date(2026, 9, 28), [self.present_employee], self.policy)
        self.assertEqual(rows[0].status, AttendanceRecord.Status.INSIDE)
        self.assertEqual(rows[0].pk, AttendanceRecord.objects.get().pk)


class SummarizeTests(PolicyFixture):
    def test_summary_of_an_empty_range_is_all_zero(self):
        # ملخّصُ مدىٍ بلا سجلات أرقامُه أصفار، لا انهيار: الشاشة تفتح
        # على شهرٍ لم يُسجَّل فيه بعد.
        summary = summarize([], self.policy)
        self.assertEqual(summary["present"], 0)
        self.assertEqual(summary["worked_minutes"], 0)
        self.assertEqual(summary["expected_minutes"], 0)

    def test_summary_counts_each_kind_once(self):
        # ثلاثة موظفين لا ثلاثة سجلات لنفس الموظف: سطرٌ واحد لكل موظف
        # في اليوم، فمحاولةُ عدّ حالاتٍ ثلاثٍ بموظفٍ واحد تكسر القيد.
        day = date(2026, 9, 28)
        late_employee = Employee.objects.create(name="متأخر", role="sales")
        early_employee = Employee.objects.create(name="مبكر", role="sales")

        def build(employee, login, logout):
            record = AttendanceRecord.objects.create(
                employee=employee,
                date=day,
                login_at=at(day, login[0], login[1]),
                logout_at=at(day, logout[0], logout[1]),
            )
            return recompute(record, self.policy)

        late = build(late_employee, (10, 0), (17, 0))
        early = build(early_employee, (8, 0), (15, 0))
        good = self.make(day, login=at(day, 8, 0), logout=at(day, 16, 0))
        summary = summarize([late, early, good], self.policy)
        self.assertEqual(summary["days"], 1)
        self.assertEqual(summary["present"], 3)
        self.assertEqual(summary["late_count"], 1)
        self.assertEqual(summary["early_count"], 1)
        # 10:00->17:00 = 420، و8:00->15:00 = 420، و8:00->16:00 = 480.
        self.assertEqual(summary["worked_minutes"], (420 + 420 + 480))

    def test_expected_minutes_ignores_non_working_days(self):
        # الرقمُ ليس «طولَ المدى»: هو ما كان على الموظف أن يعمله فعلاً،
        # فإلاّ صار كل يومِ عطلة نقصاً في كسبه.
        day = date(2026, 9, 28)
        self.make(day, login=at(day, 8, 0), logout=at(day, 16, 0))
        summary = summarize(list(AttendanceRecord.objects.all()), self.policy)
        self.assertEqual(summary["expected_minutes"], 480)

    def test_open_rows_are_counted_separately(self):
        day = date(2026, 9, 28)
        self.make(day, login=at(day, 8, 0))
        summary = summarize(list(AttendanceRecord.objects.all()), self.policy)
        self.assertEqual(summary["open_sessions"], 1)
        self.assertEqual(summary["worked_minutes"], 0)


class HalfDayRoundTests(TestCase):
    def test_a_full_day_rounds_to_one(self):
        self.assertEqual(half_day_round(480), 1.0)

    def test_four_hours_is_half_a_day(self):
        self.assertEqual(half_day_round(240), 0.5)

    def test_a_quarter_day_is_still_half(self):
        # التقريب إلى أقرب نصف: ثلاث ساعات تساوي نصف يوم، لا ثلث يوم.
        self.assertEqual(half_day_round(180), 0.5)

    def test_an_exact_half_is_half(self):
        self.assertEqual(half_day_round(241), 0.5)

    def test_a_minute_over_half_rounds_up(self):
        # الحدّ عند ثلاثة أرباع اليوم لا عند نصفه: نصفُ اليوم 240 دقيقة،
        # لكنّ ما بعده يقع في النصف الثاني، فلا يُقرَّب إلا إن تجاوز
        # ثلاثةَ أرباع اليوم (360 دقيقة) بواحدة.
        self.assertEqual(half_day_round(359), 0.5)
        self.assertEqual(half_day_round(361), 1.0)

    def test_exactly_three_quarters_of_a_day_is_one(self):
        self.assertEqual(half_day_round(360), 1.0)


class PolicySingletonTests(TestCase):
    def test_load_creates_the_row_with_friday_as_the_weekend(self):
        AttendancePolicy.objects.all().delete()
        policy = AttendancePolicy.load()
        self.assertEqual(policy.pk, 1)
        self.assertEqual(policy.weekend_days, [FRIDAY])

    def test_load_is_idempotent(self):
        first = AttendancePolicy.load()
        first.grace_minutes = 11
        first.save()
        self.assertEqual(AttendancePolicy.load().grace_minutes, 11)
        self.assertEqual(AttendancePolicy.objects.count(), 1)

    def test_the_default_windows_do_not_overlap(self):
        policy = AttendancePolicy.load()
        # نافذتان متداخلتان تعني أن «بداية الخروج» بعد «نهاية الدخول»
        # بساعتين: يبدو معقولاً، ويحسب تأخيراً لمن لم يتأخر.
        self.assertLess(policy.login_window_end, policy.logout_window_start)
