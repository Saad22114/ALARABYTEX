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


class RecurringExpenseTest(TestCase):
    """المصاريف الثابتة تترحّل تلقائياً للشهر التالي."""

    def setUp(self):
        self.c = APIClient()
        authenticate_admin(self.c)
        call_command("seed_categories", verbosity=0)
        self.branch = Branch.objects.create(name="B", code="B")
        self.cat = ExpenseCategory.objects.create(name="Test", code="TST")

    def _post(self, **overrides):
        payload = {
            "branch": self.branch.id,
            "category": self.cat.id,
            "date": "2026-01-15",
            "amount": 100,
        }
        payload.update(overrides)
        return self.c.post("/api/expenses/", payload, format="json")

    def test_create_monthly_recurring_computes_next_run_date(self):
        r = self._post(is_recurring=True, recur_frequency="monthly")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data["is_recurring"])
        self.assertEqual(r.data["recur_frequency"], "monthly")
        self.assertEqual(r.data["next_run_date"], "2026-02-15")

    def test_create_weekly_recurring_computes_next_run_date(self):
        r = self._post(is_recurring=True, recur_frequency="weekly")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["next_run_date"], "2026-01-22")

    def test_recurring_requires_frequency(self):
        r = self._post(is_recurring=True)
        self.assertEqual(r.status_code, 400)
        self.assertIn("recur_frequency", r.data)

    def test_disable_recurring_clears_next_run_date(self):
        r = self._post(is_recurring=True, recur_frequency="monthly")
        eid = r.data["id"]
        r2 = self.c.patch(f"/api/expenses/{eid}/", {
            "branch": self.branch.id,
            "category": self.cat.id,
            "date": "2026-01-15",
            "amount": 100,
            "is_recurring": False,
        }, format="json")
        self.assertEqual(r2.status_code, 200, r2.data)
        self.assertFalse(r2.data["is_recurring"])
        self.assertIsNone(r2.data["next_run_date"])

    def test_generate_due_creates_copies_and_advances(self):
        from expenses.models import Expense
        from expenses.services import generate_due_recurring_expenses

        original = Expense.objects.create(
            branch=self.branch, category=self.cat, date=date(2026, 1, 15),
            amount=100,
            is_recurring=True, recur_frequency=Expense.RecurringFrequency.MONTHLY,
            next_run_date=date(2026, 2, 15),
        )
        created = generate_due_recurring_expenses(date(2026, 3, 15))
        self.assertEqual(len(created), 2)
        dates = sorted(c.date for c in created)
        self.assertEqual(dates, [date(2026, 2, 15), date(2026, 3, 15)])
        for copy in created:
            self.assertFalse(copy.is_recurring)
            self.assertEqual(copy.origin_id, original.id)
        original.refresh_from_db()
        self.assertEqual(original.next_run_date, date(2026, 4, 15))

    def test_generate_due_is_idempotent(self):
        from expenses.models import Expense
        from expenses.services import generate_due_recurring_expenses

        original = Expense.objects.create(
            branch=self.branch, category=self.cat, date=date(2026, 1, 15),
            amount=100,
            is_recurring=True, recur_frequency=Expense.RecurringFrequency.MONTHLY,
            next_run_date=date(2026, 2, 15),
        )
        generate_due_recurring_expenses(date(2026, 3, 15))
        again = generate_due_recurring_expenses(date(2026, 4, 15))
        self.assertEqual(len(again), 1)  # فقط شهر نيسان الجديد — لا تكرار للشهور السابقة
        self.assertEqual(again[0].date, date(2026, 4, 15))

    def test_list_auto_generates_due_recurring(self):
        from expenses.models import Expense

        original = Expense.objects.create(
            branch=self.branch, category=self.cat, date=date(2026, 1, 15),
            amount=100,
            is_recurring=True, recur_frequency=Expense.RecurringFrequency.MONTHLY,
            next_run_date=date(2026, 2, 15),
        )
        r = self.c.get("/api/expenses/")
        self.assertEqual(r.status_code, 200)
        copies = Expense.objects.filter(origin=original)
        self.assertGreaterEqual(copies.count(), 1)
        self.assertTrue(copies.filter(date=date(2026, 2, 15)).exists())
        original.refresh_from_db()
        self.assertGreater(original.next_run_date, date(2026, 2, 15))

    def test_run_recurring_action(self):
        from expenses.models import Expense

        Expense.objects.create(
            branch=self.branch, category=self.cat, date=date(2026, 1, 15),
            amount=100,
            is_recurring=True, recur_frequency=Expense.RecurringFrequency.MONTHLY,
            next_run_date=date(2026, 2, 15),
        )
        r = self.c.post("/api/expenses/run-recurring/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertGreaterEqual(r.data["count"], 1)
