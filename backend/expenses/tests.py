from datetime import date

from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from branches.models import Branch
from expenses.models import ExpenseCategory


class ExpenseAPITest(TestCase):
    def setUp(self):
        self.c = APIClient()
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
