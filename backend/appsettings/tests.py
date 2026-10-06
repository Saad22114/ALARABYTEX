from datetime import date
import json
import shutil
import struct
import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from core.testsupport import AUTH_ADMIN_BRANCH_CODE, authenticate_admin

from branches.models import Branch
from expenses.models import Expense, ExpenseCategory
from sale_sessions.models import Employee
from sales.models import DailySale
from suppliers.models import Supplier

from .backup import export_backup as bk_export, restore_backup
from .models import AppSettings


class SettingsAPITest(TestCase):
    def setUp(self):
        self.c = APIClient()
        self.admin_user, _ = authenticate_admin(self.c)

    def test_get_settings_returns_defaults(self):
        r = self.c.get("/api/settings/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["business_name"], "القماش العربي")
        self.assertEqual(r.data["currency_symbol"], "ر.ع")
        self.assertEqual(r.data["currency_code"], "OMR")
        self.assertEqual(r.data["decimal_places"], 2)
        self.assertEqual(r.data["trade_name"], "")
        self.assertEqual(r.data["commercial_registration"], "")
        self.assertEqual(r.data["invoice_notes"], "")
        self.assertEqual(r.data["min_sale_percent"], "15.00")
        self.assertEqual(r.data["min_piece_price_multiplier"], "1.00")

    def test_patch_invoice_registration_fields(self):
        r = self.c.patch("/api/settings/", {
            "trade_name": "مؤسسة الأقمشة العربية",
            "commercial_registration": "100987654",
            "invoice_notes": "تُسلم البضاعة حسب المواصفات المتفق عليها",
        }, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["trade_name"], "مؤسسة الأقمشة العربية")
        self.assertEqual(r.data["commercial_registration"], "100987654")
        self.assertEqual(r.data["invoice_notes"], "تُسلم البضاعة حسب المواصفات المتفق عليها")

    def test_patch_updates_business_name_and_decimal_places(self):
        r = self.c.patch("/api/settings/", {
            "business_name": "القماش العربي الجديد",
            "decimal_places": 3,
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["business_name"], "القماش العربي الجديد")
        self.assertEqual(r.data["decimal_places"], 3)

        r = self.c.get("/api/settings/")
        self.assertEqual(r.data["business_name"], "القماش العربي الجديد")
        self.assertEqual(r.data["decimal_places"], 3)

    def test_patch_invalid_decimal_places_returns_400(self):
        r = self.c.patch("/api/settings/", {"decimal_places": 99}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_get_settings_returns_professional_defaults(self):
        r = self.c.get("/api/settings/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["default_theme"], "green")
        self.assertEqual(r.data["date_format"], "YYYY-MM-DD")
        self.assertEqual(r.data["low_stock_threshold"], "50.00")
        self.assertEqual(r.data.get("business_email"), "")
        self.assertEqual(r.data.get("receipt_footer"), "")

    def test_patch_new_professional_fields(self):
        r = self.c.patch("/api/settings/", {
            "business_email": "info@example.com",
            "low_stock_threshold": 100,
            "date_format": "DD/MM/YYYY",
            "default_theme": "amber",
            "receipt_footer": "شكراً لتعاملكم معنا",
        }, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["business_email"], "info@example.com")
        self.assertEqual(r.data["low_stock_threshold"], "100.00")
        self.assertEqual(r.data["date_format"], "DD/MM/YYYY")
        self.assertEqual(r.data["default_theme"], "amber")
        self.assertEqual(r.data["receipt_footer"], "شكراً لتعاملكم معنا")

    def test_patch_invalid_email_returns_400(self):
        r = self.c.patch("/api/settings/", {"business_email": "not-an-email"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_patch_control_fields(self):
        r = self.c.patch("/api/settings/", {
            "invoice_prefix": "INV-",
            "tax_rate": 5,
            "currency_position": "before",
            "previous_day_cutoff_hour": 5,
            "low_stock_alert_enabled": False,
            "session_warn_hours": 3,
            "session_danger_hours": 8,
            "default_payment_method": "card",
            "discount_max_percent": 50,
            "min_sale_percent": 30,
            "min_piece_price_multiplier": 2.5,
            "receipt_show_tax": True,
            "receipt_show_phone": False,
        }, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["invoice_prefix"], "INV-")
        self.assertEqual(r.data["tax_rate"], "5.000")
        self.assertEqual(r.data["currency_position"], "before")
        self.assertEqual(r.data["previous_day_cutoff_hour"], 5)
        self.assertEqual(r.data["low_stock_alert_enabled"], False)
        self.assertEqual(r.data["session_warn_hours"], 3)
        self.assertEqual(r.data["session_danger_hours"], 8)
        self.assertEqual(r.data["default_payment_method"], "card")
        self.assertEqual(r.data["discount_max_percent"], "50.00")
        self.assertEqual(r.data["min_sale_percent"], "30.00")
        self.assertEqual(r.data["min_piece_price_multiplier"], "2.50")
        self.assertEqual(r.data["receipt_show_tax"], True)
        self.assertEqual(r.data["receipt_show_phone"], False)

    def test_patch_invalid_control_fields_returns_400(self):
        for patch in (
            {"tax_rate": 150},
            {"currency_position": "inside"},
            {"previous_day_cutoff_hour": 30},
            {"discount_max_percent": 101},
            {"min_sale_percent": 101},
            {"min_piece_price_multiplier": 101},
            {"default_payment_method": "gold"},
            {"session_warn_hours": 0},
        ):
            r = self.c.patch("/api/settings/", patch, format="json")
            self.assertEqual(r.status_code, 400, patch)


class BackupEncryptionTest(TestCase):
    #: كلمة المرور تُطال إلى ثمانية أحرف فأكثر، فالسابقة كانت تُرفض الآن.
    PASSWORD = "s3cret-passphrase"

    def setUp(self):
        self.c = APIClient()
        authenticate_admin(self.c)
        self.today = date.today().isoformat()
        self.branch = Branch.objects.create(name="مركز مسقط", code="MHN")

    def _clear_data(self):
        Expense.objects.all().delete()
        DailySale.objects.all().delete()
        ExpenseCategory.objects.all().delete()
        Supplier.objects.all().delete()
        Branch.objects.exclude(code=AUTH_ADMIN_BRANCH_CODE).delete()

    def _set_password(self, value):
        r = self.c.patch("/api/settings/", {"backup_password": value}, format="json")
        self.assertEqual(r.status_code, 200, r.data)

    def test_password_hidden_from_api(self):
        self._set_password(self.PASSWORD)
        self.assertNotIn("backup_password", self.c.get("/api/settings/").data)

    def test_plain_backup_when_no_password(self):
        """بلا مفتاح لا نسخة أصلاً — لا يُنتَج ملف يفتحه أي محرر نصوص."""
        r = self.c.get("/api/settings/backup/")
        self.assertEqual(r.status_code, 400)
        self.assertNotIn("version", r.data)
        self.assertNotIn("tables", r.data)

    def test_backup_refused_when_password_too_short(self):
        s = AppSettings.load()
        s.backup_password = "abc"
        s.save(update_fields=["backup_password", "updated_at"])
        self.assertEqual(self.c.get("/api/settings/backup/").status_code, 400)

    def test_short_password_rejected_on_save(self):
        r = self.c.patch("/api/settings/", {"backup_password": "abc"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(AppSettings.load().backup_password)

    def test_blank_password_cannot_disable_encryption(self):
        """الفراغ يعني «لم تُغيّر» — لا باب لإلغاء التشفير بعد ضبطه."""
        self._set_password(self.PASSWORD)
        self._set_password("")
        self.assertEqual(AppSettings.load().backup_password, self.PASSWORD)
        self.assertEqual(self.c.get("/api/settings/backup/").status_code, 200)

    def test_downloaded_file_is_opaque_without_the_password(self):
        """الملف المُنزَّل لا يحمل بيانات مقروءة، ولا الجداول تظهر نصاً."""
        self._set_password(self.PASSWORD)
        DailySale.objects.create(
            branch=self.branch, date=self.today, total_sales=100, cash_amount=100,
        )
        raw = self.c.get("/api/settings/backup/").content.decode("utf-8")
        self.assertNotIn("مركز مسقط", raw)
        self.assertNotIn("tables", raw)
        envelope = json.loads(raw)
        self.assertEqual(envelope["format"], "qomash-backup")
        self.assertEqual(envelope["cipher"], "aes-256-gcm")

    def test_supplied_password_restores_on_a_fresh_install(self):
        """جهاز جديد بلا كلمة محفوظة: الكلمة المرسلة مع الطلب تفتح النسخة."""
        self._set_password(self.PASSWORD)
        DailySale.objects.create(
            branch=self.branch, date=self.today, total_sales=100, cash_amount=100,
        )
        raw = self.c.get("/api/settings/backup/").content.decode("utf-8")

        # محاكاة تثبيت جديد: لا كلمة محفوظة في القاعدة إطلاقاً.
        s = AppSettings.load()
        s.backup_password = ""
        s.save(update_fields=["backup_password", "updated_at"])

        r = self.c.post(
            "/api/settings/restore/",
            {"content": raw, "backup_password": self.PASSWORD},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(DailySale.objects.count(), 1)
        self.assertEqual(Branch.objects.exclude(code=AUTH_ADMIN_BRANCH_CODE).count(), 1)

    def test_wrong_supplied_password_is_rejected(self):
        self._set_password(self.PASSWORD)
        raw = self.c.get("/api/settings/backup/").content.decode("utf-8")
        s = AppSettings.load()
        s.backup_password = ""
        s.save(update_fields=["backup_password", "updated_at"])

        r = self.c.post(
            "/api/settings/restore/",
            {"content": raw, "backup_password": "totally-wrong"},
            format="json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("غير صحيحة", r.data["detail"])

    def test_wrong_password_deletes_nothing(self):
        """الرفض قبل الاستعادة: البيانات سليمة بعد كلمة مرور خاطئة."""
        self._set_password(self.PASSWORD)
        DailySale.objects.create(
            branch=self.branch, date=self.today, total_sales=100, cash_amount=100,
        )
        raw = self.c.get("/api/settings/backup/").content.decode("utf-8")
        self.c.patch("/api/settings/", {"backup_password": "another-pass"}, format="json")

        r = self.c.post("/api/settings/restore/", {"content": raw}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(DailySale.objects.count(), 1)
        self.assertEqual(Branch.objects.exclude(code=AUTH_ADMIN_BRANCH_CODE).count(), 1)

    def test_encrypted_backup_roundtrip(self):
        self._set_password(self.PASSWORD)
        DailySale.objects.create(
            branch=self.branch, date=self.today, total_sales=100, cash_amount=100,
        )

        r = self.c.get("/api/settings/backup/")
        self.assertEqual(r.status_code, 200)
        envelope = r.json()
        self.assertTrue(envelope["encrypted"])
        self.assertEqual(envelope["format"], "qomash-backup")
        raw_text = r.content.decode("utf-8")

        self._clear_data()
        self.assertEqual(DailySale.objects.count(), 0)

        r = self.c.post("/api/settings/restore/", {"content": raw_text}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(Branch.objects.exclude(code=AUTH_ADMIN_BRANCH_CODE).count(), 1)
        self.assertEqual(DailySale.objects.count(), 1)

    def test_restore_encrypted_with_wrong_password_fails(self):
        self._set_password(self.PASSWORD)
        raw_text = self.c.get("/api/settings/backup/").content.decode("utf-8")

        self._set_password("another-passphrase")
        r = self.c.post("/api/settings/restore/", {"content": raw_text}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("غير صحيحة", r.data["detail"])

    def test_restore_encrypted_without_password_fails(self):
        self._set_password(self.PASSWORD)
        raw_text = self.c.get("/api/settings/backup/").content.decode("utf-8")

        s = AppSettings.load()
        s.backup_password = ""
        s.save(update_fields=["backup_password", "updated_at"])
        r = self.c.post("/api/settings/restore/", {"content": raw_text}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_restore_legacy_plain_object(self):
        """نسخة قديمة JSON مقروءة تُستعاد — القاعدة على التصدير لا الاستيراد."""
        s = AppSettings.load()
        s.backup_password = self.PASSWORD
        s.save(update_fields=["backup_password", "updated_at"])
        data = bk_export(AppSettings.load())
        self._clear_data()
        r = self.c.post("/api/settings/restore/", data, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(Branch.objects.exclude(code=AUTH_ADMIN_BRANCH_CODE).count(), 1)


class BackupRestoreTest(TestCase):
    PASSWORD = "restore-test-password"

    def setUp(self):
        self.c = APIClient()
        self.admin_user, _ = authenticate_admin(self.c)
        self.today = date.today().isoformat()
        self.branch = Branch.objects.create(name="مركز مسقط", code="MHN")
        self.cat = ExpenseCategory.objects.create(name="تصنيف تجريبي", code="TESTCAT")
        s = AppSettings.load()
        s.backup_password = self.PASSWORD
        s.save(update_fields=["backup_password", "updated_at"])

    def _clear_data(self):
        Expense.objects.all().delete()
        DailySale.objects.all().delete()
        ExpenseCategory.objects.all().delete()
        Supplier.objects.all().delete()
        Branch.objects.exclude(code=AUTH_ADMIN_BRANCH_CODE).delete()

    def test_backup_restore_roundtrip(self):
        Supplier.objects.create(name="مورد تجريبي")
        DailySale.objects.create(
            branch=self.branch,
            date=self.today,
            total_sales=100,
            cash_amount=100,
        )
        Expense.objects.create(
            branch=self.branch,
            category=self.cat,
            date=self.today,
            amount=50,
        )

        r = self.c.get("/api/settings/backup/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Content-Disposition", r.headers)
        # التنزيل مُشفّر، فالمحتوى مُغلَّف لا جداول مقروءة.
        envelope = r.json()
        self.assertTrue(envelope["encrypted"])
        from appsettings.crypto import decrypt_backup

        plaintext = json.loads(decrypt_backup(envelope, self.PASSWORD).decode("utf-8"))
        for key in ("version", "tables"):
            self.assertIn(key, plaintext)
        self.assertEqual(plaintext["version"], 2)
        self.assertEqual(
            len([b for b in plaintext["tables"]["branches.Branch"] if b["code"] != AUTH_ADMIN_BRANCH_CODE]), 1
        )
        self.assertEqual(len(plaintext["tables"]["sales.DailySale"]), 1)
        self.assertEqual(len(plaintext["tables"]["expenses.Expense"]), 1)

        self._clear_data()
        self.assertEqual(Branch.objects.exclude(code=AUTH_ADMIN_BRANCH_CODE).count(), 0)
        self.assertEqual(DailySale.objects.count(), 0)

        r = self.c.post("/api/settings/restore/", {"content": r.content.decode("utf-8")}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Branch.objects.exclude(code=AUTH_ADMIN_BRANCH_CODE).count(), 1)
        self.assertTrue(Branch.objects.filter(code="MHN").exists())
        self.assertEqual(Supplier.objects.count(), 1)
        self.assertEqual(Supplier.objects.first().name, "مورد تجريبي")
        self.assertEqual(ExpenseCategory.objects.count(), 1)
        self.assertEqual(DailySale.objects.count(), 1)
        self.assertEqual(Expense.objects.count(), 1)
        self.assertEqual(str(Expense.objects.first().amount), "50.00")

    def test_restore_maps_duplicate_username_to_local_user_id(self):
        User = get_user_model()
        local_admin = self.admin_user
        payload = bk_export(AppSettings.load())
        backup_admin = next(
            row for row in payload["tables"]["auth.User"]
            if row["username"] == local_admin.username
        )
        old_id = backup_admin["id"]
        backup_admin["id"] = max(User.objects.values_list("id", flat=True)) + 10000
        imported_id = backup_admin["id"]

        # Simulate another database where the same account has a different PK.
        for collection in (payload["tables"], payload["m2m"]):
            for label, rows in collection.items():
                if label == "auth.User":
                    continue
                for row in rows:
                    for key, value in list(row.items()):
                        if key.endswith("_id") and value == old_id:
                            row[key] = imported_id

        restore_backup(payload)

        self.assertTrue(User.objects.filter(pk=local_admin.pk, username=local_admin.username).exists())
        employee = Employee.objects.filter(user_id=local_admin.pk).first()
        self.assertIsNotNone(employee)
        self.assertFalse(Employee.objects.filter(user_id=imported_id).exists())

    def test_restore_rejects_bad_version(self):
        r = self.c.post("/api/settings/restore/", {"version": 3}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_reset_requires_admin_password(self):
        Supplier.objects.create(name="مورد تجريبي")
        DailySale.objects.create(
            branch=self.branch,
            date=self.today,
            total_sales=100,
            cash_amount=100,
        )

        r = self.c.post("/api/settings/reset/", {"confirm": True, "scope": "transactions"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(DailySale.objects.count(), 1)

        r = self.c.post("/api/settings/reset/", {
            "confirm": True,
            "scope": "transactions",
            "admin_password": "wrong-pass",
        }, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(DailySale.objects.count(), 1)

    def test_reset_transactions(self):
        Supplier.objects.create(name="مورد تجريبي")
        DailySale.objects.create(
            branch=self.branch,
            date=self.today,
            total_sales=100,
            cash_amount=100,
        )
        Expense.objects.create(
            branch=self.branch,
            category=self.cat,
            date=self.today,
            amount=50,
        )

        r = self.c.post("/api/settings/reset/", {}, format="json")
        self.assertEqual(r.status_code, 400)

        r = self.c.post("/api/settings/reset/", {"scope": "bad"}, format="json")
        self.assertEqual(r.status_code, 400)

        r = self.c.post("/api/settings/reset/", {
            "confirm": True,
            "scope": "transactions",
            "admin_password": "pass1234",
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(DailySale.objects.count(), 0)
        self.assertEqual(Expense.objects.count(), 0)
        self.assertEqual(Branch.objects.exclude(code=AUTH_ADMIN_BRANCH_CODE).count(), 1)
        self.assertEqual(Supplier.objects.count(), 1)
        self.assertEqual(ExpenseCategory.objects.count(), 1)

    def test_reset_all(self):
        Supplier.objects.create(name="مورد تجريبي")
        DailySale.objects.create(
            branch=self.branch,
            date=self.today,
            total_sales=100,
            cash_amount=100,
        )

        r = self.c.post("/api/settings/reset/", {
            "confirm": True,
            "scope": "all",
            "admin_password": "pass1234",
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(DailySale.objects.count(), 0)
        self.assertEqual(Branch.objects.count(), 0)
        self.assertEqual(Supplier.objects.count(), 0)
        self.assertEqual(ExpenseCategory.objects.count(), 0)


class LargeBackupRestoreTest(TestCase):
    """نسخة تتجاوز حدّ Django الافتراضي تُرفض عند الاستعادة.

    التشفير يكبّر الملف ~33% لأن base64 يمدّ النص 4/3، فنسخة كانت 2MB
    صارت 2.7MB — وحدّ الطلب في Django 2.5MB. النتيجة أن الاستعادة تُرفض
    بكلمة مرور صحيحة، وهو أسوأ شكل للخطأ: المستخدم يتهمّ مفتاحه السليم.
    """

    PASSWORD = "large-backup-pass"
    #: أكبر من 2621440 بايت (حد Django الافتراضي).
    FILLER_BYTES = 3_000_000

    def setUp(self):
        self.c = APIClient()
        authenticate_admin(self.c)
        s = AppSettings.load()
        s.backup_password = self.PASSWORD
        s.save(update_fields=["backup_password", "updated_at"])

    def test_backup_larger_than_the_request_limit_restores(self):
        real_export = bk_export

        def padded(settings_obj):
            data = real_export(settings_obj)
            # حشو بلا معنى دلالي: يختبر حجم الطلب فقط.
            data["_padding"] = "x" * self.FILLER_BYTES
            return data

        with mock.patch("appsettings.backup.export_backup", padded):
            r = self.c.get("/api/settings/backup/")
            # استجابة التنزيل HttpResponse عادية، لا Response بـ.data
            self.assertEqual(r.status_code, 200)
            raw = r.content.decode("utf-8")
        self.assertGreater(len(raw.encode("utf-8")), 2621440, "الاختبار بلا معنى بلا تجاوز الحد")

        r = self.c.post(
            "/api/settings/restore/",
            {"content": raw, "backup_password": self.PASSWORD},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.data)


class ScheduledBackupEncryptionTest(TestCase):
    """النسخة التلقائية مشفّرة، وغياب المفتاح يُعلن فشلاً لا نجاحاً صامتاً.

    الجدولة (cron/Task Scheduler) تقرأ رمز الخروج لا مخرجات الشاشة: صفر يعني
    «احتفظت ببياناتك». لو ابتلع الأمرُ غيابَ المفتاح صامتاً لتوفّر في صمت
    المفتاح، وبقي المستخدم شهوراً بلا نسخة دون أن يعرف.
    """

    PASSWORD = "cron-backup-pass"

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="backup-cron-"))
        self.override = override_settings(MEDIA_ROOT=self.tmp)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _run(self, *args):
        out = StringIO()
        err = StringIO()
        call_command("auto_backup", *args, stdout=out, stderr=err)
        return out.getvalue(), err.getvalue()

    def test_force_without_password_exits_nonzero(self):
        out = StringIO()
        err = StringIO()
        with self.assertRaises(SystemExit) as cm:
            call_command("auto_backup", "--force", stdout=out, stderr=err)
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("مطلوبة", err.getvalue())
        self.assertEqual(list((self.tmp / "backups").glob("*.json")), [])
        self.assertEqual(AppSettings.load().last_auto_backup_at, None)

    def test_force_with_password_writes_an_encrypted_file(self):
        s = AppSettings.load()
        s.backup_password = self.PASSWORD
        s.save(update_fields=["backup_password", "updated_at"])

        out, _ = self._run("--force")

        files = list((self.tmp / "backups").glob("*.json"))
        self.assertEqual(len(files), 1, out)
        raw = files[0].read_text(encoding="utf-8")
        envelope = json.loads(raw)
        self.assertTrue(envelope["encrypted"])
        self.assertEqual(envelope["cipher"], "aes-256-gcm")
        # الملف على القرص لا يحمل بيانات مقروءة.
        self.assertNotIn("tables", raw)
        self.assertEqual(AppSettings.load().last_auto_backup_path, f"backups/{files[0].name}")

    def test_scheduled_run_without_password_exits_nonzero(self):
        s = AppSettings.load()
        s.auto_backup_enabled = True
        s.auto_backup_every_hours = 1
        s.save(update_fields=["auto_backup_enabled", "auto_backup_every_hours", "updated_at"])

        out = StringIO()
        err = StringIO()
        with self.assertRaises(SystemExit) as cm:
            call_command("auto_backup", stdout=out, stderr=err)
        self.assertEqual(cm.exception.code, 1)
        self.assertEqual(list((self.tmp / "backups").glob("*.json")), [])


def _png_bytes(width=64, height=64):
    def _chunk(tag, payload):
        return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", 0)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", b"") + _chunk(b"IEND", b"")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class LogoUploadAPITest(TestCase):
    def setUp(self):
        self.c = APIClient()
        authenticate_admin(self.c)

    def _png(self):
        return SimpleUploadedFile("site.png", _png_bytes(), content_type="image/png")

    def test_upload_logo_success(self):
        r = self.c.post("/api/settings/logo/", {"file": self._png()}, format="multipart")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["logo"], "logos/logo.png")

    def test_upload_requires_file_field(self):
        r = self.c.post("/api/settings/logo/", {}, format="multipart")
        self.assertEqual(r.status_code, 400)

    def test_delete_logo_success(self):
        s = AppSettings.load()
        s.logo = "logos/logo.png"
        s.save(update_fields=["logo"])
        r = self.c.delete("/api/settings/logo/")
        self.assertEqual(r.status_code, 200, r.data)
        s.refresh_from_db()
        self.assertEqual(s.logo, "")

    def test_logo_upload_replaces_previous(self):
        s = AppSettings.load()
        s.logo = "media/logos/logo_keep.png"
        s.save(update_fields=["logo"])
        self.c.post("/api/settings/logo/", {"file": self._png()}, format="multipart")
        s.refresh_from_db()
        self.assertEqual(s.logo, "logos/logo.png")

    def test_logo_field_in_settings_payload(self):
        r = self.c.get("/api/settings/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("logo", r.data)
