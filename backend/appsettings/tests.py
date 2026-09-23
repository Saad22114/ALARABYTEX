from datetime import date
import json
import struct
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from core.testsupport import AUTH_ADMIN_BRANCH_CODE, authenticate_admin

from branches.models import Branch
from expenses.models import Expense, ExpenseCategory
from sales.models import DailySale
from suppliers.models import Supplier

from .models import AppSettings


class SettingsAPITest(TestCase):
    def setUp(self):
        self.c = APIClient()
        authenticate_admin(self.c)

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
        self.assertEqual(r.data["receipt_show_tax"], True)
        self.assertEqual(r.data["receipt_show_phone"], False)

    def test_patch_invalid_control_fields_returns_400(self):
        for patch in (
            {"tax_rate": 150},
            {"currency_position": "inside"},
            {"previous_day_cutoff_hour": 30},
            {"discount_max_percent": 101},
            {"default_payment_method": "gold"},
            {"session_warn_hours": 0},
        ):
            r = self.c.patch("/api/settings/", patch, format="json")
            self.assertEqual(r.status_code, 400, patch)


class BackupEncryptionTest(TestCase):
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

    def test_password_hidden_from_api(self):
        r = self.c.patch("/api/settings/", {"backup_password": "s3cret"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertNotIn("backup_password", r.data)
        self.assertTrue(r.data["has_backup_password"])

        r = self.c.get("/api/settings/")
        self.assertNotIn("backup_password", r.data)
        self.assertTrue(r.data["has_backup_password"])

    def test_plain_backup_when_no_password(self):
        r = self.c.get("/api/settings/backup/")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data.get("version"), 2)
        self.assertIn("tables", data)
        self.assertNotIn("encrypted", data)

    def test_encrypted_backup_roundtrip(self):
        self.c.patch("/api/settings/", {"backup_password": "s3cret"}, format="json")
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
        self.c.patch("/api/settings/", {"backup_password": "s3cret"}, format="json")
        raw_text = self.c.get("/api/settings/backup/").content.decode("utf-8")

        self.c.patch("/api/settings/", {"backup_password": "other"}, format="json")
        r = self.c.post("/api/settings/restore/", {"content": raw_text}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("غير صحيحة", r.data["detail"])

    def test_restore_encrypted_without_password_fails(self):
        self.c.patch("/api/settings/", {"backup_password": "s3cret"}, format="json")
        raw_text = self.c.get("/api/settings/backup/").content.decode("utf-8")

        self.c.patch("/api/settings/", {"backup_password": ""}, format="json")
        r = self.c.post("/api/settings/restore/", {"content": raw_text}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_restore_legacy_plain_object(self):
        raw_text = self.c.get("/api/settings/backup/").content.decode("utf-8")
        data = json.loads(raw_text)
        self._clear_data()
        r = self.c.post("/api/settings/restore/", data, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(Branch.objects.exclude(code=AUTH_ADMIN_BRANCH_CODE).count(), 1)


class BackupRestoreTest(TestCase):
    def setUp(self):
        self.c = APIClient()
        authenticate_admin(self.c)
        self.today = date.today().isoformat()
        self.branch = Branch.objects.create(name="مركز مسقط", code="MHN")
        self.cat = ExpenseCategory.objects.create(name="تصنيف تجريبي", code="TESTCAT")

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
        data = r.json()
        for key in ("version", "tables"):
            self.assertIn(key, data)
        self.assertEqual(data["version"], 2)
        self.assertEqual(
            len([b for b in data["tables"]["branches.Branch"] if b["code"] != AUTH_ADMIN_BRANCH_CODE]), 1
        )
        self.assertEqual(len(data["tables"]["sales.DailySale"]), 1)
        self.assertEqual(len(data["tables"]["expenses.Expense"]), 1)

        self._clear_data()
        self.assertEqual(Branch.objects.exclude(code=AUTH_ADMIN_BRANCH_CODE).count(), 0)
        self.assertEqual(DailySale.objects.count(), 0)

        r = self.c.post("/api/settings/restore/", data, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Branch.objects.exclude(code=AUTH_ADMIN_BRANCH_CODE).count(), 1)
        self.assertTrue(Branch.objects.filter(code="MHN").exists())
        self.assertEqual(Supplier.objects.count(), 1)
        self.assertEqual(Supplier.objects.first().name, "مورد تجريبي")
        self.assertEqual(ExpenseCategory.objects.count(), 1)
        self.assertEqual(DailySale.objects.count(), 1)
        self.assertEqual(Expense.objects.count(), 1)
        self.assertEqual(str(Expense.objects.first().amount), "50.00")

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