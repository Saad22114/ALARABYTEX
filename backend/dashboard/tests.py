from datetime import date, timedelta

from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from branches.models import Branch
from expenses.models import Expense, ExpenseCategory
from sales.models import DailySale
from suppliers.models import Fabric
from warehouses.models import FabricRoll, GoodsReceipt, Warehouse


class DashboardAPITest(TestCase):
    def setUp(self):
        call_command("seed_categories", verbosity=0)
        self.c = APIClient()
        self.branch = Branch.objects.create(name="B", code="B")
        self.cat = ExpenseCategory.objects.get(name="إيجار")
        self.today = date.today()

        DailySale.objects.create(
            branch=self.branch, date=self.today,
            total_sales=1000, cash_amount=600,
            transfer_amount=200, card_amount=150, other_amount=50,
        )
        DailySale.objects.create(
            branch=self.branch, date=self.today - timedelta(days=1),
            total_sales=500, cash_amount=500,
        )
        Expense.objects.create(
            branch=self.branch, category=self.cat, date=self.today, amount=200,
        )

    def test_summary_today(self):
        r = self.c.get("/api/dashboard/summary/", {"period": "today"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["total_sales"], 1000)
        self.assertEqual(r.data["total_expenses"], 200)
        self.assertEqual(r.data["net"], 800)

    def test_summary_week(self):
        r = self.c.get("/api/dashboard/summary/", {"period": "week"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["total_sales"], 1500)

    def test_summary_month(self):
        r = self.c.get("/api/dashboard/summary/", {"period": "month"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["total_sales"], 1500)

    def test_summary_custom_range(self):
        r = self.c.get("/api/dashboard/summary/", {
            "period": "custom",
            "date_from": (self.today - timedelta(days=1)).isoformat(),
            "date_to": self.today.isoformat(),
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["total_sales"], 1500)

    def test_chart_data(self):
        r = self.c.get("/api/dashboard/summary/", {"period": "week"})
        self.assertIsInstance(r.data["chart_data"], list)
        self.assertGreater(len(r.data["chart_data"]), 0)

    def test_branches_count(self):
        r = self.c.get("/api/dashboard/summary/", {"period": "today"})
        self.assertEqual(r.data["branches_count"], 1)

    def test_alerts_low_stock(self):
        wh = Warehouse.objects.create(name="W")
        f = Fabric.objects.create(name="قطن", code="FAB-1", unit="yard", min_stock=100, sale_price_yard=5)
        FabricRoll.objects.create(warehouse=wh, fabric=f, yards=50, remaining_yards=50)
        r = self.c.get("/api/dashboard/alerts/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["low_stock_count"], 1)
        self.assertEqual(r.data["low_stock"][0]["fabric_name"], "قطن")
        self.assertEqual(r.data["low_stock"][0]["total_yards"], 50.0)
        self.assertEqual(r.data["today"]["sales"], 1000.0)

    def test_alerts_no_low_stock(self):
        r = self.c.get("/api/dashboard/alerts/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["low_stock_count"], 0)
