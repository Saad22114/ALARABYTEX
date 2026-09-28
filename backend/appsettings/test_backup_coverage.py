"""اختبار تغطية النسخ الاحتياطي: كل جدول داخل الملف، وأحدث 20 نسخة فقط.

هذان شرطان صامتان كانا مكسورين: جداول الرواتب ودفعات التسويات لم تكن في
القائمة اليدوية أصلاً فكانت تُمسح عند الاستعادة ولا تعود، ولا سقف لعدد
النسخ على القرص.
"""

import os
import shutil
import tempfile
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from django.apps import apps
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from branches.models import Branch
from core.testsupport import authenticate_admin
from machine_account.models import MachineCollection
from payroll.models import SalaryStructure
from sale_sessions.models import Employee

from . import backup as bk
from .models import AppSettings


#: جداول مستثناة قصداً: مشتقّة من الكود والترحيلات، أو لها مسار استعادة خاص.
EXPECTED_EXCLUDED = {
    "appsettings.AppSettings",   # صفّ واحد يُستبدل بصفّ الإعدادات الحيّ
    "contenttypes.ContentType",
    "auth.Permission",
}


class BackupCoverageTest(TestCase):
    """كل جدول في المشروع يجب أن يكون داخل ملف النسخة بلا استثناء."""

    def test_every_project_table_is_in_the_export(self):
        order = bk._order()
        covered = set(order) | set(bk._through_labels())

        skip_prefixes = ("django.", "rest_framework", "authtoken", "sessions.", "admin.")
        project_tables = {
            m._meta.label
            for m in apps.get_models()
            if not m._meta.label.startswith(skip_prefixes)
        }

        missing = project_tables - covered - EXPECTED_EXCLUDED
        self.assertEqual(
            missing, set(), f"جداول تسقط من النسخة الاحتياطية: {sorted(missing)}"
        )

    def test_export_contains_the_tables_that_used_to_be_dropped(self):
        """الجداول التي أسقطتها القائمة اليدوية — انحدار صامت."""
        data = bk.export_backup(AppSettings.load())
        tables = data["tables"]
        for label in (
            "payroll.SalaryStructure",
            "payroll.PayrollRun",
            "payroll.Payslip",
            "payroll.SalaryAdvance",
            "payroll.AdvanceInstallment",
            "machine_account.MachineCollection",
            "audit.AuditLog",
        ):
            self.assertIn(label, tables, f"{label} غير موجود في ملف النسخة")

    def test_table_keys_keep_their_original_casing(self):
        """``model_name`` صغيرة الحروف بحكم Django — بناؤها منقط، فتنهار المطابقة."""
        tables = bk.export_backup(AppSettings.load())["tables"]
        self.assertIn("branches.Branch", tables)
        self.assertNotIn("branches.branch", tables)

    def test_excluded_framework_tables_are_not_exported(self):
        tables = bk.export_backup(AppSettings.load())["tables"]
        self.assertNotIn("auth.Permission", tables)
        self.assertNotIn("contenttypes.ContentType", tables)

    def test_m2m_through_tables_are_exported_separately(self):
        data = bk.export_backup(AppSettings.load())
        self.assertIn("sale_sessions.Employee_allowed_branches", data["m2m"])
        self.assertIn("auth.User_groups", data["m2m"])
        # لا تختلط بالنماذج: تُمسح وتُعاد بترتيبها الخاص
        self.assertNotIn("sale_sessions.Employee_allowed_branches", data["tables"])

    def test_m2m_only_covers_pairs_inside_the_export(self):
        """``User_user_permissions`` طرفُه الثاني ``auth.Permission`` غير مُصدَّر."""
        labels = set(bk._through_labels())
        self.assertNotIn("auth.User_user_permissions", labels)
        self.assertNotIn("auth.Group_permissions", labels)

    def test_every_parent_precedes_its_children(self):
        order = bk._order()
        pos = {label: i for i, label in enumerate(order)}
        for label in order:
            for dep in bk._dependency_labels(bk._model(label)):
                self.assertLess(pos[dep], pos[label], f"{dep} يجب أن يسبق {label}")

    def test_through_tables_come_after_both_ends(self):
        order = bk._order()
        pos = {label: i for i, label in enumerate(order)}
        for label in bk._through_labels():
            self.assertGreater(pos[label], pos["sale_sessions.Employee"])
            self.assertGreater(pos[label], pos["branches.Branch"])

    def test_self_referencing_fields_are_derived(self):
        """المراجع الذاتية مشتقّةٌ من النموذج، لا من قائمة قد تنسى واحداً."""
        self.assertEqual(bk.self_fields_for("accounting.Account"), ["parent"])
        self.assertEqual(bk.self_fields_for("expenses.Expense"), ["origin"])
        self.assertEqual(bk.self_fields_for("messaging.Message"), ["reply_to"])
        self.assertEqual(bk.self_fields_for("branches.Branch"), [])


class BackupRestoreFullCoverageTest(TestCase):
    """استعادة فعلية لجداول كانت تسقط: الرواتب ودفعات التسويات."""

    def setUp(self):
        self.c = APIClient()
        authenticate_admin(self.c)
        self.branch = Branch.objects.create(name="فرع", code="FULL")

    def test_payroll_and_settlement_survive_a_restore(self):
        emp = Employee.objects.create(name="موظف", branch=self.branch)
        structure = SalaryStructure.objects.create(
            employee=emp, base_salary=Decimal("300.00"), daily_work_hours=Decimal("9")
        )
        collection = MachineCollection.objects.create(
            branch=self.branch,
            date=date(2026, 3, 5),
            amount=Decimal("250.00"),
            method="transfer",
            account="bank",
        )

        payload = bk.export_backup(AppSettings.load())
        # محو كامل كما تفعل الاستعادة
        SalaryStructure.objects.all().delete()
        MachineCollection.objects.all().delete()
        self.assertEqual(SalaryStructure.objects.count(), 0)
        self.assertEqual(MachineCollection.objects.count(), 0)

        bk.restore_backup(payload)

        self.assertTrue(SalaryStructure.objects.filter(pk=structure.pk).exists())
        self.assertEqual(
            str(SalaryStructure.objects.get(pk=structure.pk).base_salary), "300.00"
        )
        restored = MachineCollection.objects.get(pk=collection.pk)
        self.assertEqual(str(restored.amount), "250.00")
        self.assertEqual(restored.account, "bank")

    def test_employee_branch_links_survive_a_restore(self):
        """صفّ الربط يُمسح قبل الموظف وإلا منع حذفه عبر PROTECT."""
        emp = Employee.objects.create(name="موظف", branch=self.branch)
        other = Branch.objects.create(name="ثان", code="SEC")
        emp.allowed_branches.set([self.branch, other])

        payload = bk.export_backup(AppSettings.load())
        through = Employee.allowed_branches.through
        self.assertEqual(
            through.objects.filter(employee=emp).count(), 2
        )

        bk.restore_backup(payload)

        self.assertEqual(
            set(Employee.objects.get(pk=emp.pk).allowed_branches.values_list("id", flat=True)),
            {self.branch.id, other.id},
        )


class BackupAutoStampTest(TestCase):
    """الحقول التلقائية تُعاد بقيمتها الأصلية، لا بلحظة الاستعادة.

    ``auto_now_add`` يتجاوز أي قيمة ترد من النموذج، فبلا ``.update()`` لاحق
    ترجع كل وردية وسجل تدقيق بتاريخ «الآن» — فتنهار فترات الحضور والرواتب.
    """

    def setUp(self):
        self.branch = Branch.objects.create(name="فرع", code="STAMP")
        self.emp = Employee.objects.create(name="موظف", branch=self.branch)

    def test_auto_stamp_fields_are_derived_from_the_model(self):
        session_fields = bk._auto_stamp_fields(bk._model("sale_sessions.SaleSession"))
        # opened_at خارج القائمة القديمة (created_at/updated_at) فكان يُنسى
        self.assertIn("opened_at", session_fields)
        self.assertIn("created_at", session_fields)
        self.assertIn("updated_at", session_fields)
        self.assertIn("timestamp", bk._auto_stamp_fields(bk._model("audit.AuditLog")))

    def test_session_opened_at_keeps_its_original_value(self):
        from sale_sessions.models import SaleSession

        opened = timezone.now() - timedelta(days=40)
        session = SaleSession.objects.create(branch=self.branch, employee=self.emp)
        # opened_at تلقائي، فنكتب قيمته عبر update كما يفعل المشروع
        SaleSession.objects.filter(pk=session.pk).update(opened_at=opened)
        original = SaleSession.objects.get(pk=session.pk).opened_at

        payload = bk.export_backup(AppSettings.load())
        SaleSession.objects.all().delete()
        bk.restore_backup(payload)

        self.assertEqual(
            SaleSession.objects.get(pk=session.pk).opened_at, original
        )
        self.assertNotEqual(
            SaleSession.objects.get(pk=session.pk).opened_at, timezone.now()
        )

    def test_audit_timestamp_keeps_its_original_value(self):
        from audit.models import AuditLog

        log = AuditLog.objects.create(employee=self.emp, section="sales", action="create")
        original = log.timestamp

        payload = bk.export_backup(AppSettings.load())
        AuditLog.objects.all().delete()
        bk.restore_backup(payload)

        self.assertEqual(AuditLog.objects.get(pk=log.pk).timestamp, original)


class BackupRetentionTest(TestCase):
    """أحدث 20 نسخة فقط، وما قبلها يُحذف فوراً."""

    def setUp(self):
        self.c = APIClient()
        authenticate_admin(self.c)
        self.tmp = Path(tempfile.mkdtemp(prefix="backup-keep-"))
        self.override = override_settings(MEDIA_ROOT=self.tmp)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.s = AppSettings.load()

    def _make(self, count, mtime_step=10):
        """ينشئ ``count`` ملف نسخة بتعديلات زمنية متزايدة."""
        made = []
        base = 1_700_000_000
        for i in range(count):
            p = self.tmp / "backups" / f"backup_2026010{i}_000000.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("{}", encoding="utf-8")
            os.utime(p, (base + i * mtime_step, base + i * mtime_step))
            made.append(p)
        return made

    def test_prunes_down_to_the_limit(self):
        self._make(25)
        self.assertEqual(len(list((self.tmp / "backups").glob("*.json"))), 25)

        removed = bk._keep_last_n(keep=20)

        self.assertEqual(len(removed), 5)
        self.assertEqual(len(bk.list_backup_files()), 20)

    def test_keeps_the_newest_twenty(self):
        made = self._make(25)
        bk._keep_last_n(keep=20)

        remaining = {p.name for p in (self.tmp / "backups").glob("*.json")}
        newest_20 = {p.name for p in made[-20:]}
        self.assertEqual(remaining, newest_20)

    def test_below_the_limit_nothing_is_deleted(self):
        self._make(7)
        self.assertEqual(bk._keep_last_n(keep=20), [])
        self.assertEqual(len(bk.list_backup_files()), 7)

    def test_write_prunes_automatically(self):
        """الكتابة نفسها تحذف ما تجاوز السقف، فلا تتراكم النسخ على القرص."""
        self._make(23)
        rel = bk.write_backup_file(self.s)
        self.assertTrue((self.tmp / rel).exists())
        self.assertEqual(len(bk.list_backup_files()), 20)

    def test_never_deletes_the_file_it_just_wrote(self):
        """النسخة الحيّة محميّة حتى يقع ترتيبها خارج العشرين في نظام تقريبي."""
        self._make(25, mtime_step=0)  # كل الملفات بنفس التوقيت
        rel = bk.write_backup_file(self.s)
        self.assertTrue((self.tmp / rel).exists(), "حُذفت النسخة التي كُتبت للتوّ")

    def test_listing_order_matches_what_the_pruner_keeps(self):
        """ما يعرضه الجدول هو ما يبقى فعلاً، الأحدث أولاً."""
        made = self._make(25)
        bk._keep_last_n(keep=20)

        files = bk.list_backup_files()
        listed = [f["name"] for f in files]
        stamps = [f["modified"] for f in files]

        self.assertEqual(len(listed), 20)
        self.assertEqual(stamps, sorted(stamps, reverse=True))
        # الأحدثُ timestamps هي الباقية، والأقدم اختفى
        self.assertEqual(set(listed), {p.name for p in made[-20:]})

    def test_same_second_files_are_still_ordered_and_capped(self):
        """نسختان في الثانية نفسها: بالاسم وحده لا يُحسم الترتيب."""
        self._make(25, mtime_step=0)
        bk._keep_last_n(keep=20)
        self.assertEqual(len(bk.list_backup_files()), 20)

    def test_two_backups_in_the_same_second_both_survive(self):
        """التسمية بدقة الثانية — نسختان في الثانية تتبتلع إحداهما الأخرى."""
        first = bk.write_backup_file(self.s)
        second = bk.write_backup_file(self.s)

        self.assertNotEqual(first, second)
        self.assertTrue((self.tmp / first).exists(), "النسخة الأولى ضاعت")
        self.assertTrue((self.tmp / second).exists(), "النسخة الثانية ضاعت")
        self.assertEqual(len(bk.list_backup_files()), 2)

    def test_twenty_five_rapid_backups_are_capped_at_twenty(self):
        """ضغط متتالٍ: 25 طلباً ⇒ 20 ملفاً على القرص لا 25 ولا أقل."""
        for _ in range(25):
            bk.write_backup_file(self.s)
        self.assertEqual(len(bk.list_backup_files()), 20)

    def test_limit_is_twenty_by_default(self):
        self.assertEqual(bk.BACKUP_KEEP, 20)

    def test_listing_reports_the_cap(self):
        r = self.c.get("/api/settings/auto-backup/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["keep"], 20)
        self.assertIn("kept", r.data)
        self.assertIn("full", r.data)

    def test_running_now_reports_what_was_kept(self):
        r = self.c.post("/api/settings/auto-backup/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["keep"], 20)
        self.assertEqual(r.data["kept"], 1)
