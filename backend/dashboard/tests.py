from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db.models import Sum
from django.test import TestCase
from rest_framework.test import APIClient
from core.testsupport import authenticate_admin

from branches.models import Branch
from expenses.models import Expense, ExpenseCategory
from sale_sessions.models import Employee, SaleSession
from sales.models import DailySale
from suppliers.models import Fabric, LedgerEntry, Supplier
from warehouses.models import FabricRoll, GoodsReceipt, Warehouse


class DashboardAPITest(TestCase):
    def setUp(self):
        call_command("seed_categories", verbosity=0)
        self.c = APIClient()
        authenticate_admin(self.c)
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
        from core.daterange import resolve_range

        start, end, _ = resolve_range({"period": "week"})
        expected = (
            DailySale.objects.filter(date__gte=start, date__lte=end)
            .aggregate(total=Sum("total_sales"))["total"]
            or 0
        )
        r = self.c.get("/api/dashboard/summary/", {"period": "week"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["total_sales"], expected)

    def test_summary_month(self):
        from core.daterange import resolve_range

        start, end, _ = resolve_range({"period": "month"})
        expected = (
            DailySale.objects.filter(date__gte=start, date__lte=end)
            .aggregate(total=Sum("total_sales"))["total"]
            or 0
        )
        r = self.c.get("/api/dashboard/summary/", {"period": "month"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["total_sales"], expected)

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

    def test_summary_for_scoped_employee(self):
        User = get_user_model()
        user = User.objects.create_user(username="sales_scope", password="x")
        emp = Employee(name="مندوب", branch=self.branch, user=user, is_active=True)
        emp.apply_role_preset(Employee.Role.SALES)
        emp.save()
        client = APIClient()
        client.force_authenticate(user=user)
        r = client.get("/api/dashboard/summary/", {"period": "today"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["branches_count"], 1)

    def test_summary_for_scoped_employee_without_branch(self):
        User = get_user_model()
        user = User.objects.create_user(username="sales_nobranch", password="x")
        emp = Employee(name="مندوب بلا فرع", user=user, is_active=True)
        emp.apply_role_preset(Employee.Role.SALES)
        emp.save()
        client = APIClient()
        client.force_authenticate(user=user)
        r = client.get("/api/dashboard/summary/", {"period": "today"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["branches_count"], 0)

    def test_profit_fields(self):
        r = self.c.get("/api/dashboard/summary/", {"period": "today"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["gross_profit"], 1000.0)
        self.assertEqual(r.data["margin_pct"], 100.0)
        self.assertIn("cogs", r.data["chart_data"][0])
        self.assertIn("gross_profit", r.data["chart_data"][0])
        self.assertIsInstance(r.data["top_fabrics"], list)

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

    def test_alerts_low_stock_disabled_by_setting(self):
        from appsettings.models import AppSettings

        settings = AppSettings.load()
        settings.low_stock_alert_enabled = False
        settings.save(update_fields=["low_stock_alert_enabled"])
        wh = Warehouse.objects.create(name="W")
        f = Fabric.objects.create(name="قطن", code="FAB-1", unit="yard", min_stock=100, sale_price_yard=5)
        FabricRoll.objects.create(warehouse=wh, fabric=f, yards=50, remaining_yards=50)
        r = self.c.get("/api/dashboard/alerts/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["low_stock_count"], 0)
        self.assertEqual(r.data["low_stock"], [])

    def test_alerts_no_low_stock(self):
        r = self.c.get("/api/dashboard/alerts/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["low_stock_count"], 0)

    def test_alerts_open_sessions(self):
        employee = Employee.objects.create(name="emp1", branch=self.branch)
        session = SaleSession.objects.create(employee=employee, branch=self.branch)
        session.opened_at = self.today - timedelta(days=2)
        session.save(update_fields=["opened_at"])
        r = self.c.get("/api/dashboard/alerts/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["open_sessions_count"], 1)
        self.assertEqual(r.data["open_sessions"][0]["employee_name"], "emp1")

    def test_alerts_pending_receipts(self):
        supplier = Supplier.objects.create(name="S1")
        e1 = LedgerEntry.objects.create(
            supplier=supplier, date=self.today,
            entry_type=LedgerEntry.EntryType.PURCHASE, amount=-500,
        )
        wh = Warehouse.objects.create(name="W")
        GoodsReceipt.objects.create(warehouse=wh, supplier=supplier, purchase_entry=e1)
        e2 = LedgerEntry.objects.create(
            supplier=supplier, date=self.today,
            entry_type=LedgerEntry.EntryType.PURCHASE, amount=-300,
        )
        r = self.c.get("/api/dashboard/alerts/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["pending_receipts_count"], 1)
        self.assertEqual(r.data["pending_receipts"][0]["id"], e2.id)

    def test_summary_previous_period(self):
        r = self.c.get("/api/dashboard/summary/", {"period": "today"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["previous_sales"], 500.0)
        self.assertEqual(r.data["sales_delta_pct"], 100.0)
        self.assertIn("chart_previous", r.data)

    def test_activity(self):
        supplier = Supplier.objects.create(name="S1")
        LedgerEntry.objects.create(
            supplier=supplier, date=self.today,
            entry_type=LedgerEntry.EntryType.PURCHASE, amount=-500,
        )
        LedgerEntry.objects.create(
            supplier=supplier, date=self.today,
            entry_type=LedgerEntry.EntryType.PAYMENT, amount=200,
        )
        r = self.c.get("/api/dashboard/activity/")
        self.assertEqual(r.status_code, 200)
        types = [a["type"] for a in r.data["activities"]]
        self.assertIn("sale", types)
        self.assertIn("expense", types)
        self.assertIn("purchase", types)
        self.assertIn("payment", types)
