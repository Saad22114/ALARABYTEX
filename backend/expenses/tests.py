import io
from datetime import date

from django.core.management import call_command
from django.core.management.base import OutputWrapper
from django.test import TestCase
from rest_framework.test import APIClient
from core.management.base import ArabicSafeCommand
from core.testsupport import authenticate_admin

from branches.models import Branch
from expenses.models import ExpenseCategory


class ExpenseAPITest(TestCase):
    def setUp(self):
        self.c = APIClient()
        authenticate_admin(self.c)
        call_command("seed_categories", verbosity=0)
        self.branch = Branch.objects.create(name="B", code="B")
        self.cat = ExpenseCategory.objects.create(name="Test", code="TST")
        self.sys_cat = ExpenseCategory.objects.get(name="إيجار")
        self.today = date.today().isoformat()

    def test_create_expense(self):
        r = self.c.post("/api/expenses/", {
            "branch": self.branch.id,
            "category": self.cat.id,
            "date": self.today,
            "amount": 50,
        })
        self.assertEqual(r.status_code, 201)
        self.assertIn("id", r.data)

    def test_list_expenses(self):
        self.c.post("/api/expenses/", {
            "branch": self.branch.id,
            "category": self.cat.id,
            "date": self.today,
            "amount": 50,
        })
        r = self.c.get("/api/expenses/")
        self.assertEqual(r.data["count"], 1)

    def test_filter_by_category(self):
        self.c.post("/api/expenses/", {
            "branch": self.branch.id,
            "category": self.cat.id,
            "date": self.today,
            "amount": 50,
        })
        self.c.post("/api/expenses/", {
            "branch": self.branch.id,
            "category": self.sys_cat.id,
            "date": self.today,
            "amount": 100,
        })
        r = self.c.get("/api/expenses/", {"category": self.cat.id})
        self.assertEqual(r.data["count"], 1)

    def test_delete_expense(self):
        r = self.c.post("/api/expenses/", {
            "branch": self.branch.id,
            "category": self.cat.id,
            "date": self.today,
            "amount": 50,
        })
        eid = r.data["id"]
        r = self.c.delete(f"/api/expenses/{eid}/")
        self.assertEqual(r.status_code, 200)

    def test_system_category_delete_blocked(self):
        r = self.c.delete(f"/api/expense-categories/{self.sys_cat.id}/")
        self.assertEqual(r.status_code, 400)

    def test_category_list(self):
        r = self.c.get("/api/expense-categories/")
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(r.data["count"], 9)

    def test_create_custom_category(self):
        r = self.c.post("/api/expense-categories/", {"name": "Custom", "code": "CST"})
        self.assertEqual(r.status_code, 201)
        self.assertFalse(r.data["is_system"])


class ExpenseBudgetAPITest(TestCase):
    def setUp(self):
        self.c = APIClient()
        authenticate_admin(self.c)
        self.branch = Branch.objects.create(name="B", code="B")
        self.cat = ExpenseCategory.objects.create(name="Test", code="TST")
        self.month = date.today().replace(day=1)

    def test_create_budget(self):
        r = self.c.post("/api/expense-budgets/", {
            "branch": self.branch.id,
            "category": self.cat.id,
            "month": self.month.isoformat(),
            "amount": 500,
        })
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["branch_name"], "B")

    def test_budget_unique_per_branch_category_month(self):
        payload = {
            "branch": self.branch.id,
            "category": self.cat.id,
            "month": self.month.isoformat(),
            "amount": 500,
        }
        self.assertEqual(self.c.post("/api/expense-budgets/", payload).status_code, 201)
        r = self.c.post("/api/expense-budgets/", payload)
        self.assertEqual(r.status_code, 400)

    def test_budget_month_filter_yyyy_mm(self):
        self.c.post("/api/expense-budgets/", {
            "branch": self.branch.id,
            "category": self.cat.id,
            "month": self.month.isoformat(),
            "amount": 500,
        })
        r = self.c.get("/api/expense-budgets/", {"month": self.month.strftime("%Y-%m")})
        self.assertEqual(r.data["count"], 1)

    def test_delete_budget(self):
        r = self.c.post("/api/expense-budgets/", {
            "branch": self.branch.id,
            "category": self.cat.id,
            "month": self.month.isoformat(),
            "amount": 500,
        })
        eid = r.data["id"]
        r = self.c.delete(f"/api/expense-budgets/{eid}/")
        self.assertEqual(r.status_code, 200)


class SeedCategoriesCommandTest(TestCase):
    """حارس ضد انهيار الإخراج العربي على ترميز الطرفية غير UTF-8 (cp1252 في ويندوز)."""

    def test_verbosity_zero_writes_nothing(self):
        stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", line_buffering=True)
        call_command("seed_categories", stdout=stream, verbosity=0)
        self.assertEqual(stream.buffer.tell(), 0)
        self.assertEqual(ExpenseCategory.objects.count(), 9)

    def test_arabic_output_does_not_crash_on_cp1252(self):
        stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", line_buffering=True)
        call_command("seed_categories", stdout=stream, verbosity=1)
        self.assertEqual(ExpenseCategory.objects.count(), 9)
        stream.seek(0)
        self.assertTrue(stream.read())

    def test_write_line_falls_back_when_stream_cannot_encode(self):
        command = ArabicSafeCommand()
        command.stdout = OutputWrapper(
            io.TextIOWrapper(io.BytesIO(), encoding="cp1252", line_buffering=True)
        )
        command.write_line("تمت إضافة 9 تصنيف مصروف أساسي")
        command.stdout.flush()
        self.assertTrue(command.stdout._out.buffer.getvalue().decode("cp1252"))

    def test_write_line_keeps_arabic_on_utf8(self):
        command = ArabicSafeCommand()
        command.stdout = OutputWrapper(
            io.TextIOWrapper(io.BytesIO(), encoding="utf-8", line_buffering=True)
        )
        command.write_line("تمت إضافة 9 تصنيف مصروف أساسي")
        command.stdout.flush()
        text = command.stdout._out.buffer.getvalue().decode("utf-8")
        self.assertIn("تمت إضافة", text)
