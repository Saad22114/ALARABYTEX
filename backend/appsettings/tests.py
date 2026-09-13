from datetime import date

from django.test import TestCase
from rest_framework.test import APIClient

from branches.models import Branch
from expenses.models import Expense, ExpenseCategory
from sales.models import DailySale
from suppliers.models import Supplier


class SettingsAPITest(TestCase):
    def setUp(self):
        self.c = APIClient()

    def test_get_settings_returns_defaults(self):
        r = self.c.get("/api/settings/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["business_name"], "القماش العربي")
        self.assertEqual(r.data["currency_symbol"], "ر.ع")
        self.assertEqual(r.data["currency_code"], "OMR")
        self.assertEqual(r.data["decimal_places"], 2)

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


class BackupRestoreTest(TestCase):
    def setUp(self):
        self.c = APIClient()
        self.today = date.today().isoformat()
        self.branch = Branch.objects.create(name="مركز مسقط", code="MHN")
        self.cat = ExpenseCategory.objects.create(name="تصنيف تجريبي", code="TESTCAT")

    def _clear_data(self):
        Expense.objects.all().delete()
        DailySale.objects.all().delete()
        ExpenseCategory.objects.all().delete()
        Supplier.objects.all().delete()
        Branch.objects.all().delete()

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
        for key in ("version", "branches", "sales", "expenses", "settings"):
            self.assertIn(key, data)
        self.assertEqual(data["version"], 1)
        self.assertEqual(len(data["branches"]), 1)
        self.assertEqual(len(data["sales"]), 1)
        self.assertEqual(len(data["expenses"]), 1)

        self._clear_data()
        self.assertEqual(Branch.objects.count(), 0)
        self.assertEqual(DailySale.objects.count(), 0)

        r = self.c.post("/api/settings/restore/", data, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Branch.objects.count(), 1)
        self.assertEqual(Branch.objects.first().code, "MHN")
        self.assertEqual(Supplier.objects.count(), 1)
        self.assertEqual(Supplier.objects.first().name, "مورد تجريبي")
        self.assertEqual(ExpenseCategory.objects.count(), 1)
        self.assertEqual(DailySale.objects.count(), 1)
        self.assertEqual(Expense.objects.count(), 1)
        self.assertEqual(str(Expense.objects.first().amount), "50.00")

    def test_restore_rejects_bad_version(self):
        r = self.c.post("/api/settings/restore/", {"version": 2}, format="json")
        self.assertEqual(r.status_code, 400)

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
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(DailySale.objects.count(), 0)
        self.assertEqual(Expense.objects.count(), 0)
        self.assertEqual(Branch.objects.count(), 1)
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
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(DailySale.objects.count(), 0)
        self.assertEqual(Branch.objects.count(), 0)
        self.assertEqual(Supplier.objects.count(), 0)
        self.assertEqual(ExpenseCategory.objects.count(), 0)