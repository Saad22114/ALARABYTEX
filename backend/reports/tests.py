from datetime import date, timedelta

from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from branches.models import Branch
from expenses.models import Expense, ExpenseCategory
from sales.models import DailySale, DailySaleItem
from suppliers.models import Fabric, Supplier
from warehouses.models import GoodsReceipt, GoodsReceiptItem, Warehouse


class ReportsAPITest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        call_command("seed_categories", verbosity=0)

    def setUp(self):
        self.c = APIClient()
        self.branch = Branch.objects.create(name="B", code="B")
        self.supplier = Supplier.objects.create(name="S")
        self.cat = ExpenseCategory.objects.get(name="إيجار")
        self.today = date.today()

        DailySale.objects.create(
            branch=self.branch, date=self.today,
            total_sales=1000, cash_amount=600,
            transfer_amount=200, card_amount=150, other_amount=50,
        )
        Expense.objects.create(
            branch=self.branch, category=self.cat,
            date=self.today, amount=300,
        )

    def test_sales_report(self):
        r = self.c.get("/api/reports/sales/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("sales", r.data)
        self.assertEqual(len(r.data["sales"]), 1)
        self.assertEqual(r.data["totals"]["total_sales"], 1000)
        self.assertEqual(r.data["count"], 1)

    def test_sales_report_with_filter(self):
        r = self.c.get("/api/reports/sales/", {
            "date_from": (self.today + timedelta(days=1)).isoformat(),
        })
        self.assertEqual(r.data["count"], 0)

    def test_expenses_report(self):
        r = self.c.get("/api/reports/expenses/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("expenses", r.data)
        self.assertEqual(r.data["count"], 1)

    def test_net_daily_report(self):
        r = self.c.get("/api/reports/net-daily/", {
            "date_from": self.today.isoformat(),
            "date_to": self.today.isoformat(),
        })
        self.assertEqual(r.status_code, 200)
        self.assertIn("chart_data", r.data)
        self.assertEqual(len(r.data["chart_data"]), 1)
        pt = r.data["chart_data"][0]
        self.assertEqual(pt["sales"], 1000)
        self.assertEqual(pt["expenses"], 300)
        self.assertEqual(pt["net"], 700)

    def test_suppliers_report(self):
        r = self.c.get("/api/reports/suppliers/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("suppliers", r.data)
        self.assertEqual(len(r.data["suppliers"]), 1)

    def test_branches_report(self):
        r = self.c.get("/api/reports/branches/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("branches", r.data)
        self.assertEqual(len(r.data["branches"]), 1)
        self.assertEqual(r.data["branches"][0]["sales_count"], 1)
        self.assertEqual(r.data["branches"][0]["expenses_count"], 1)

    def test_sales_xlsx_export(self):
        r = self.c.get("/api/reports/sales/", {"export": "xlsx"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("spreadsheetml.sheet", r.headers["Content-Type"])

    def test_expenses_xlsx_export(self):
        r = self.c.get("/api/reports/expenses/", {"export": "xlsx"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("spreadsheetml.sheet", r.headers["Content-Type"])

    def test_net_daily_xlsx_export(self):
        r = self.c.get("/api/reports/net-daily/", {
            "date_from": self.today.isoformat(),
            "date_to": self.today.isoformat(),
            "export": "xlsx",
        })
        self.assertEqual(r.status_code, 200)
        self.assertIn("spreadsheetml.sheet", r.headers["Content-Type"])

    def test_suppliers_xlsx_export(self):
        r = self.c.get("/api/reports/suppliers/", {"export": "xlsx"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("spreadsheetml.sheet", r.headers["Content-Type"])

    def test_branches_xlsx_export(self):
        r = self.c.get("/api/reports/branches/", {"export": "xlsx"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("spreadsheetml.sheet", r.headers["Content-Type"])


class AdvancedReportsAPITest(TestCase):
    def setUp(self):
        self.c = APIClient()
        self.branch = Branch.objects.create(name="B", code="B")
        self.cat = ExpenseCategory.objects.create(name="مصروف")
        self.today = date.today()
        self.f1 = Fabric.objects.create(name="قطن", code="FAB-1", unit="yard", sale_price_yard=5)
        self.f2 = Fabric.objects.create(name="حرير", code="FAB-2", unit="yard", sale_price_yard=4)
        wh = Warehouse.objects.create(name="W")
        self.receipt = GoodsReceipt.objects.create(
            number="GR-1", warehouse=wh, date=self.today, status="posted"
        )
        GoodsReceiptItem.objects.create(
            receipt=self.receipt, fabric=self.f1, rolls_count=1, yards=100, unit_price=2, total=200
        )
        sale = DailySale.objects.create(
            branch=self.branch, date=self.today, total_sales=1000, cash_amount=1000
        )
        DailySaleItem.objects.create(sale=sale, fabric=self.f1, yards=80)
        DailySaleItem.objects.create(sale=sale, fabric=self.f2, yards=50)
        Expense.objects.create(branch=self.branch, category=self.cat, date=self.today, amount=300)

    def test_cogs_report(self):
        r = self.c.get("/api/reports/cogs/", {
            "date_from": self.today.isoformat(),
            "date_to": self.today.isoformat(),
        })
        self.assertEqual(r.status_code, 200)
        by_name = {x["fabric_name"]: x for x in r.data["items"]}
        q = by_name["قطن"]
        self.assertEqual(q["yards_sold"], 80)
        self.assertEqual(q["avg_cost"], 2.0)
        self.assertEqual(q["revenue"], 400.0)
        self.assertEqual(q["cogs"], 160.0)
        self.assertEqual(q["profit"], 240.0)
        h = by_name["حرير"]
        self.assertEqual(h["avg_cost"], 0.0)
        self.assertEqual(h["revenue"], 200.0)
        self.assertEqual(h["cogs"], 0.0)

    def test_cogs_excludes_draft_receipts(self):
        GoodsReceipt.objects.create(number="GR-2", date=self.today, status="draft")
        r = self.c.get("/api/reports/cogs/")
        q = next(x for x in r.data["items"] if x["fabric_name"] == "قطن")
        self.assertEqual(q["avg_cost"], 2.0)

    def test_cogs_xlsx_export(self):
        r = self.c.get("/api/reports/cogs/", {"export": "xlsx"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("spreadsheetml.sheet", r.headers["Content-Type"])

    def test_profit_loss(self):
        r = self.c.get("/api/reports/profit-loss/", {
            "date_from": self.today.isoformat(),
            "date_to": self.today.isoformat(),
        })
        self.assertEqual(r.status_code, 200)
        t = r.data["totals"]
        self.assertEqual(t["total_sales"], 1000.0)
        self.assertEqual(t["cogs"], 160.0)
        self.assertEqual(t["gross_profit"], 840.0)
        self.assertEqual(t["expenses"], 300.0)
        self.assertEqual(t["net_profit"], 540.0)

    def test_profit_loss_empty_period(self):
        r = self.c.get("/api/reports/profit-loss/", {
            "date_from": (self.today + timedelta(days=10)).isoformat(),
            "date_to": (self.today + timedelta(days=11)).isoformat(),
        })
        self.assertEqual(r.data["totals"]["total_sales"], 0.0)
        self.assertEqual(r.data["totals"]["cogs"], 0.0)
        self.assertEqual(r.data["totals"]["net_profit"], 0.0)

    def test_profit_loss_xlsx_export(self):
        r = self.c.get("/api/reports/profit-loss/", {"export": "xlsx"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("spreadsheetml.sheet", r.headers["Content-Type"])

    def test_journal(self):
        r = self.c.get("/api/reports/journal/", {
            "date_from": self.today.isoformat(),
            "date_to": self.today.isoformat(),
        })
        self.assertEqual(r.status_code, 200)
        row = r.data["journal"][0]
        self.assertEqual(row["sales"], 1000.0)
        self.assertEqual(row["purchases"], 200.0)
        self.assertEqual(row["expenses"], 300.0)
        self.assertEqual(row["support"], 0.0)
        self.assertEqual(row["withdraw"], 0.0)
        self.assertEqual(row["net"], 500.0)
        self.assertEqual(row["running_balance"], 500.0)

    def test_journal_xlsx_export(self):
        r = self.c.get("/api/reports/journal/", {"export": "xlsx"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("spreadsheetml.sheet", r.headers["Content-Type"])
