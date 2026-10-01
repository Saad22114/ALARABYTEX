# -*- coding: utf-8 -*-
"""اختبارات نقطة النهاية: المسارات، والصلاحيات، وخطّافَي الدخول والخروج.

ما لا تغطّيه ``tests.py`` هو هذا: هناك نحاسب الأرقام، وهنا نتأكد أن
الطلب يصل أصلاً. أهمُّ ما هنا ثلاثة:

* **الدخول يفتح سطر حضور.** الخطّاف مكتوبٌ في نقطة الدخول نفسها، فإن سقطت
  أو أُزيلت بقي القسم كلّه فارغاً بلا أن يفشل اختبارٌ آخر.
* **خطأُ الحضور لا يُبطل الدخول.** الـ try/except حول الخطّاف موجود
  لسبب: من يصل بـ 500 عند الدخول بسبب ميزةٍ ثانوية هو نظامٌ متوقّف.
* **الحذف ممنوع.** سجلُّ الحضور هو الدليل؛ من محاه لا يستطيع أن
  يُثبت أنه كان هنا.
"""

from datetime import date, timedelta
import io
import unittest
from uuid import uuid4

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

try:
    import openpyxl
except ImportError:  # pragma: no cover - بيئة بلا openpyxl
    openpyxl = None

from attendance.models import AttendancePolicy, AttendanceRecord
from core.testsupport import authenticate_admin, make_admin_user
from sale_sessions.models import Employee


def first_column(response):
    """أسماءُ العمود الأول من ملف مُصدَّر: يُقرأ الملف كما سيراه المستخدم."""
    if openpyxl is None:  # pragma: no cover - بيئة بلا openpyxl
        raise unittest.SkipTest("openpyxl not installed")
    sheet = openpyxl.load_workbook(io.BytesIO(response.content)).active
    return [
        str(row[0].value)
        for row in sheet.iter_rows(min_col=1, max_col=1)
        if row[0].value
    ]


class AttendanceApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user, cls.employee = make_admin_user()
        cls.employee.role = Employee.Role.ADMIN
        cls.employee.save()

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.policy = AttendancePolicy.load()
        self.policy.enabled = True
        self.policy.save()

    def record(self, day=None, employee=None, **extra):
        return AttendanceRecord.objects.create(
            employee=employee or self.employee,
            date=day or date(2026, 9, 28),
            **extra,
        )

    # --- السياسة -----------------------------------------------------------
    def test_policy_is_readable(self):
        response = self.client.get("/api/attendance/policy/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("workday_minutes", response.data)

    def test_policy_update_recomputes_every_stored_row(self):
        # بلا هذا يبقى رقمُ تأخيرٍ محسوبٌ على نافذةٍ لم تعد موجودة،
        # ويقرأه أحدٌ ويظنّه حقيقة.
        from datetime import datetime, time

        from django.utils import timezone as dj_tz

        from attendance.services import recompute

        moment = dj_tz.make_aware(datetime(2026, 9, 28, 9, 30))
        record = self.record(login_at=moment)
        recompute(record, self.policy)
        self.assertEqual(record.late_minutes, 25)

        response = self.client.patch(
            "/api/attendance/policy/",
            {"login_window_end": "10:00:00", "grace_minutes": 5},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        record.refresh_from_db()
        self.assertEqual(record.late_minutes, 0)
        self.policy.login_window_end = time(9, 0)
        self.policy.save()

    # --- سجلات ------------------------------------------------------------
    def test_list_returns_the_records(self):
        self.record()
        response = self.client.get("/api/attendance/records/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

    def test_list_filters_by_date_range(self):
        self.record(date(2026, 9, 28))
        self.record(date(2026, 9, 10))
        response = self.client.get(
            "/api/attendance/records/?start=2026-09-20&end=2026-09-30"
        )
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["date"], "2026-09-28")

    def test_list_filters_by_status(self):
        from attendance.services import recompute

        record = self.record()
        recompute(record, self.policy)
        response = self.client.get("/api/attendance/records/?status=absent")
        self.assertEqual(response.data["count"], 1)

    def test_list_searches_by_employee_name_and_note(self):
        # سطران بالاسم وحده لا يكفيان: لو كان الفلترُ على الموظف وحده
        # لَما ظهر أثرُ الملاحظة في البحث.
        other = Employee.objects.create(name="منصور النجار")
        self.record(note="اتصال بمدير الفرع")
        self.record(employee=other)
        by_name = self.client.get("/api/attendance/records/?search=منصور")
        self.assertEqual(by_name.data["count"], 1)
        self.assertEqual(by_name.data["results"][0]["employee"]["name"], "منصور النجار")
        by_note = self.client.get("/api/attendance/records/?search=مدير")
        self.assertEqual(by_note.data["count"], 1)
        self.assertEqual(by_note.data["results"][0]["note"], "اتصال بمدير الفرع")
        empty = self.client.get("/api/attendance/records/?search=لا_يوجد")
        self.assertEqual(empty.data["count"], 0)

    def test_list_search_does_not_filter_out_everything_on_a_blank_needle(self):
        self.record()
        for needle in ("", "   "):
            response = self.client.get(f"/api/attendance/records/?search={needle}")
            self.assertEqual(response.data["count"], 1, needle)

    def test_status_cannot_be_written_by_hand(self):
        # ``status`` مُشتقّ. لو قُبل في الكتابة لأرسله كاتبٌ لا يعرف
        # النافذة، فصار الحقل يُكتب من طرفين.
        response = self.client.patch(
            f"/api/attendance/records/{self.record().pk}/",
            {"status": "present", "note": "ملاحظة"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.data["status"], "present")

    def test_writing_an_excuse_changes_the_derived_status(self):
        record = self.record()
        response = self.client.patch(
            f"/api/attendance/records/{record.pk}/",
            {"excuse": "sick"},
            format="json",
        )
        self.assertEqual(response.data["status"], AttendanceRecord.Status.EXCUSED)

    def test_writing_a_login_time_recomputes_the_row(self):
        from datetime import datetime

        from django.utils import timezone as dj_tz

        record = self.record()
        moment = dj_tz.make_aware(datetime(2026, 9, 28, 10, 0))
        response = self.client.patch(
            f"/api/attendance/records/{record.pk}/",
            {"login_at": moment.isoformat()},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["late_minutes"], 55)

    def test_creating_a_row_by_hand_is_allowed(self):
        # موظفٌ نسي النظامُ تسجيل دخوله: المدير يكتب السطر. هذا هو
        # الفرق بين «لا يُسجَّل» و«يُسجَّل».
        response = self.client.post(
            "/api/attendance/records/",
            {"employee": self.employee.pk, "date": "2026-09-28"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["source"], AttendanceRecord.Source.MANUAL)

    def test_creating_without_an_employee_is_refused(self):
        response = self.client.post(
            "/api/attendance/records/",
            {"date": "2026-09-28"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_deleting_a_record_is_refused(self):
        record = self.record()
        response = self.client.delete(f"/api/attendance/records/{record.pk}/")
        self.assertEqual(response.status_code, 405)
        self.assertTrue(AttendanceRecord.objects.filter(pk=record.pk).exists())

    # --- ورقة اليوم -------------------------------------------------------
    def test_sheet_has_one_row_per_active_employee(self):
        other = Employee.objects.create(name="موظف آخر", role="sales")
        response = self.client.get("/api/attendance/records/sheet/?date=2026-09-28")
        self.assertEqual(response.status_code, 200)
        names = {row["employee"]["name"] for row in response.data["rows"]}
        self.assertIn(self.employee.name, names)
        self.assertIn(other.name, names)

    def test_sheet_reports_whether_the_day_is_a_working_day(self):
        response = self.client.get("/api/attendance/records/sheet/?date=2026-09-25")
        self.assertFalse(response.data["working_day"])
        response = self.client.get("/api/attendance/records/sheet/?date=2026-09-28")
        self.assertTrue(response.data["working_day"])

    def test_sheet_ignores_an_unparsable_date_instead_of_lying(self):
        # تاريخٌ يُعرض خطأً في جدول حضور يُقرأ كحقيقة. السقوط إلى اليوم
        # الحالي مُعلنٌ في الحقل ``date``، فلا أحد يظنّ أنه طلب 31/2.
        response = self.client.get("/api/attendance/records/sheet/?date=2026-02-31")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["date"], timezone.localdate().isoformat()
        )

    def test_sheet_defaults_to_today(self):
        response = self.client.get("/api/attendance/records/sheet/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["date"], timezone.localdate().isoformat())

    def test_sheet_carries_a_summary(self):
        response = self.client.get("/api/attendance/records/sheet/?date=2026-09-28")
        self.assertIn("summary", response.data)
        self.assertIn("worked", response.data)

    # --- الملخص -----------------------------------------------------------
    def test_summary_defaults_to_the_last_thirty_days(self):
        response = self.client.get("/api/attendance/records/summary/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["end"], timezone.localdate().isoformat()
        )
        self.assertEqual(
            response.data["start"],
            (timezone.localdate() - timedelta(days=29)).isoformat(),
        )

    def test_summary_counts_only_the_requested_range(self):
        self.record(
            day=timezone.localdate() - timedelta(days=60), source="manual"
        )
        response = self.client.get("/api/attendance/records/summary/")
        self.assertEqual(response.data["summary"]["absent"], 0)

    # --- تصدير ------------------------------------------------------------
    def test_export_returns_an_xlsx_attachment(self):
        response = self.client.get("/api/attendance/records/export/?date=2026-09-28")
        self.assertEqual(response.status_code, 200)
        self.assertIn("spreadsheetml", response["Content-Type"])
        # رأس الترويسة ASCII خالص، فلا يتوقف Excel عن قراءة الاسم.
        disposition = response["Content-Disposition"]
        disposition.encode("ascii")  # يرفع UnicodeEncodeError إن تسرّب

    def test_export_over_a_range_builds_a_totals_row(self):
        self.record()
        response = self.client.get(
            "/api/attendance/records/export/?start=2026-09-01&end=2026-09-30"
        )
        self.assertEqual(response.status_code, 200)

    def test_export_of_an_empty_day_still_returns_a_file(self):
        # يومٌ بلا موظفين: الملف الفارغ أفضل من خطأ 500. القارئ يفهم
        # «لا أحد» من ورقةٍ فارغة، ولا يفهمه من رسالة.
        response = self.client.get("/api/attendance/records/export/?date=2026-01-01")
        self.assertEqual(response.status_code, 200)

    def test_day_export_carries_the_absent_and_the_range_export_does_not(self):
        """الورقة تُصدَّر «من الموظف»، والمدى يُصدَّر «من السجل».

        لولا هذا لخرج ملفُ اليوم بلا سطر الغائب — وهو الموظفُ الوحيد
        الذي فُتحت الورقة لأجله. والملفُ حينها صحيحٌ تقنياً وناقصٌ عملياً:
        يظهر الحاضرون ويخلو الغائب، فيُقرأ الملفُ «لم يتأخّر أحد» وفيه
        أربعة. أمّا تصديرُ المدى فحُكمُه غيرُ ذلك، ولهذا الفارقُ في
        الاختبار: ما لا يصلح في جدول السجلات يصلح في ورقة اليوم.
        """
        Employee.objects.create(name="عبد الله الغائب")
        self.record(day=date(2026, 9, 28))

        day_file = self.client.get(
            "/api/attendance/records/export/?date=2026-09-28"
        )
        self.assertEqual(day_file.status_code, 200)
        self.assertIn("عبد الله الغائب", first_column(day_file))
        self.assertIn(self.employee.name, first_column(day_file))

        range_file = self.client.get(
            "/api/attendance/records/export/?start=2026-09-28&end=2026-09-28"
        )
        self.assertEqual(range_file.status_code, 200)
        self.assertNotIn("عبد الله الغائب", first_column(range_file))

    # --- صلاحيات ----------------------------------------------------------
    def test_anonymous_access_is_refused(self):
        self.client.force_authenticate(None)
        for url in (
            "/api/attendance/records/",
            "/api/attendance/policy/",
            "/api/attendance/records/sheet/",
        ):
            self.assertIn(
                self.client.get(url).status_code, (401, 403), url
            )

    def employee_with(self, role, attendance=None):
        """موظفٌ بالدور المطلوب، وصلاحياتُ الحضور معدودة كما يريد الاختبار."""
        from django.contrib.auth.models import User

        user = User.objects.create_user(username=f"u_{uuid4().hex[:8]}")
        emp = Employee.objects.create(
            name=f"موظف {role}", user=user, is_active=True
        )
        emp.apply_role_preset(role)
        if attendance is not None:
            emp.permissions["attendance"] = attendance
        emp.save()
        return user

    def test_a_stranger_cannot_read_anything(self):
        # الموظفُ الذي لا يملك القسم أصلاً — دورُ «مخصص» بلا صلاحية
        # حضور: لا سجلّات، ولا سياسة، ولا ورقةُ يوم. لولا الحارس لقرأ
        # كلَّ حضورِ الشركة حسابٌ فارغُ الصلاحيات.
        self.client.force_authenticate(
            user=self.employee_with(Employee.Role.CUSTOM)
        )
        for url in (
            "/api/attendance/records/",
            "/api/attendance/policy/",
            "/api/attendance/records/sheet/",
            "/api/attendance/records/summary/",
        ):
            self.assertEqual(self.client.get(url).status_code, 403, url)

    def test_a_viewer_cannot_change_the_policy_or_the_records(self):
        # «يرى» ليست «يكتب»: النافذةُ بلا زرّ حفظ، لكنّ العنوان نفسه
        # مفتوحٌ لمن يكتب عنواناً في شريط المتصفح. الرفضُ هنا هو الفرق
        # بين واجهةٍ مرتّبةٍ وأمانٍ حقيقي.
        user = self.employee_with(
            Employee.Role.VIEWER,
            attendance={"view": True, "create": False, "edit": False, "delete": False},
        )
        self.client.force_authenticate(user=user)
        self.assertEqual(
            self.client.get("/api/attendance/records/").status_code, 200
        )
        self.assertEqual(
            self.client.patch(
                "/api/attendance/policy/", {"grace_minutes": 60}, format="json"
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.patch(
                f"/api/attendance/records/{self.record().pk}/",
                {"note": "تعديل"},
                format="json",
            ).status_code,
            403,
        )

    def test_edit_grants_the_patch_and_not_the_delete(self):
        # رفضان مختلفان لسببين: من لا يملك «حذف» يرفضه الحارسُ (403)، ومن يملكها
        # يرفضه القسمُ نفسُه (405). وكلاهما يعني السجلَّ باقياً — والفرقُ
        # بينهما في الطبقة لا في النتيجة، فلا يُبنى عليه سلوكٌ مختلف.
        user = self.employee_with(
            Employee.Role.ACCOUNTANT,
            attendance={"view": True, "create": True, "edit": True, "delete": False},
        )
        self.client.force_authenticate(user=user)
        record = self.record()
        patched = self.client.patch(
            f"/api/attendance/records/{record.pk}/",
            {"note": "تعديل مسجل"},
            format="json",
        )
        self.assertEqual(patched.status_code, 200)
        self.assertEqual(
            self.client.delete(
                f"/api/attendance/records/{record.pk}/"
            ).status_code,
            403,
        )


class LoginHookTests(TestCase):
    """خطّاف الدخول: يتأكد أن سطر الحضور يُفتح عند تسجيل الدخول."""

    @classmethod
    def setUpTestData(cls):
        cls.user, cls.employee = make_admin_user()
        cls.user.set_password("pass1234")
        cls.user.save()

    def setUp(self):
        self.client = APIClient()
        self.policy = AttendancePolicy.load()
        self.policy.enabled = True
        self.policy.save()
        AttendanceRecord.objects.all().delete()

    def login(self):
        response = self.client.post(
            "/api/auth/login/",
            {"username": self.user.username, "password": "pass1234"},
            format="json",
        )
        # The endpoint hands back a token; it does not log the test client in.
        # Without this every later logout is a 401 that looks like a broken
        # attendance hook.
        token = response.data.get("token")
        if token:
            self.client.credentials(HTTP_AUTHORIZATION="Token " + token)
        return response

    def test_a_successful_login_opens_an_attendance_row(self):
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(AttendanceRecord.objects.count(), 1)
        row = AttendanceRecord.objects.get()
        self.assertEqual(row.employee_id, self.employee.pk)
        self.assertIsNotNone(row.login_at)
        self.assertIsNone(row.logout_at)

    def test_a_failed_login_writes_nothing(self):
        response = self.client.post(
            "/api/auth/login/",
            {"username": self.user.username, "password": "خطأ"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(AttendanceRecord.objects.count(), 0)

    def test_a_disabled_policy_writes_nothing_but_login_succeeds(self):
        self.policy.enabled = False
        self.policy.save()
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(AttendanceRecord.objects.count(), 0)

    def test_a_second_login_the_same_day_does_not_duplicate_the_row(self):
        self.login()
        first = AttendanceRecord.objects.get().login_at
        self.client.post("/api/auth/logout/")
        self.login()
        self.assertEqual(AttendanceRecord.objects.count(), 1)
        self.assertEqual(AttendanceRecord.objects.get().login_at, first)

    def test_logout_closes_the_open_row(self):
        self.login()
        response = self.client.post("/api/auth/logout/")
        self.assertEqual(response.status_code, 200)
        row = AttendanceRecord.objects.get()
        self.assertIsNotNone(row.logout_at)
        self.assertIsNotNone(row.worked_minutes)

    def test_a_broken_attendance_hook_does_not_block_login(self):
        # من يصل بـ 500 عند الدخول بسبب قياس الحضور هو نظامٌ متوقّف.
        import attendance.services as services

        original = services.record_login
        services.record_login = lambda *a, **k: (_ for _ in ()).throw(
            RuntimeError("boom")
        )
        try:
            # assertLogs swallows the record instead of printing it: printing
            # writes the employee's Arabic name, and on a cp1252 console that
            # kills the whole parallel test runner, hiding every real failure
            # behind one. It also pins the failure as *logged*, so the silent
            # except cannot quietly regress into a swallow.
            with self.assertLogs("core.views", level="ERROR") as captured:
                response = self.login()
            self.assertEqual(response.status_code, 200)
            self.assertIn("token", response.data)
            self.assertTrue(
                any("attendance login hook failed" in line for line in captured.output)
            )
        finally:
            services.record_login = original

    def test_a_broken_logout_hook_does_not_block_logout(self):
        import attendance.services as services

        self.login()
        original = services.record_logout
        services.record_logout = lambda *a, **k: (_ for _ in ()).throw(
            RuntimeError("boom")
        )
        try:
            with self.assertLogs("core.views", level="ERROR") as captured:
                response = self.client.post("/api/auth/logout/")
            self.assertEqual(response.status_code, 200)
            self.assertTrue(
                any("attendance logout hook failed" in line for line in captured.output)
            )
        finally:
            services.record_logout = original


class ManualCheckInTests(TestCase):
    """تسجيلُ الحضور من داخل القسم: زرٌّ للمستخدم لنفسه."""

    @classmethod
    def setUpTestData(cls):
        cls.user, cls.employee = make_admin_user()

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.policy = AttendancePolicy.load()
        self.policy.enabled = True
        self.policy.save()

    def test_check_in_opens_the_users_own_row(self):
        response = self.client.post("/api/attendance/records/check_in/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            AttendanceRecord.objects.get().employee_id, self.employee.pk
        )

    def test_check_out_closes_it(self):
        self.client.post("/api/attendance/records/check_in/")
        response = self.client.post("/api/attendance/records/check_out/")
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(AttendanceRecord.objects.get().logout_at)

    def test_check_out_without_check_in_is_refused(self):
        response = self.client.post("/api/attendance/records/check_out/")
        self.assertEqual(response.status_code, 400)

    def test_check_in_is_refused_when_the_policy_is_disabled(self):
        self.policy.enabled = False
        self.policy.save()
        response = self.client.post("/api/attendance/records/check_in/")
        self.assertEqual(response.status_code, 400)


class OpenSessionsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user, cls.employee = make_admin_user()

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        AttendanceRecord.objects.all().delete()

    def test_open_sessions_lists_rows_without_a_logout(self):
        AttendanceRecord.objects.create(
            employee=self.employee, date=date(2026, 9, 28), login_at=timezone.now()
        )
        AttendanceRecord.objects.create(
            employee=self.employee,
            date=date(2026, 9, 27),
            login_at=timezone.now(),
            logout_at=timezone.now(),
        )
        response = self.client.get("/api/attendance/records/open_sessions/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["date"], "2026-09-28")
