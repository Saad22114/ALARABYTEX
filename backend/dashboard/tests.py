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


class PreviousPeriodWindowTest(TestCase):
    """The card says "compared with the previous period". If that window is
    off by one day the number stays plausible, the percentage changes, and
    nobody can see why. So the window is pinned at its edges by dates, not
    by totals: a total alone can hide a one-day error.

    This is the defect that reached the home screen once already - sound
    arithmetic beside a figure from the wrong period.
    """

    def setUp(self):
        call_command("seed_categories", verbosity=0)
        self.c = APIClient()
        authenticate_admin(self.c)
        self.branch = Branch.objects.create(name="B", code="B")
        self.cat = ExpenseCategory.objects.get(name="\u0625\u064a\u062c\u0627\u0631")
        self.today = date.today()

    def sale(self, days_ago, amount):
        DailySale.objects.create(
            branch=self.branch, date=self.today - timedelta(days=days_ago),
            total_sales=amount, cash_amount=amount,
        )

    def spend(self, days_ago, amount):
        Expense.objects.create(
            branch=self.branch, category=self.cat,
            date=self.today - timedelta(days=days_ago), amount=amount,
        )

    def summary(self, days_from_today, days_to_today):
        r = self.c.get("/api/dashboard/summary/", {
            "date_from": (self.today - timedelta(days=days_from_today)).isoformat(),
            "date_to": (self.today - timedelta(days=days_to_today)).isoformat(),
        })
        self.assertEqual(r.status_code, 200)
        return r.data

    def test_seven_day_range_compares_against_the_seven_days_before_it(self):
        # Window [-13..-7]. Both edges and the day just past each edge.
        self.sale(13, 100)
        self.sale(8, 200)
        self.sale(7, 300)
        self.sale(14, 9999)   # one day too far back
        self.sale(6, 5000)    # the first day of the range itself
        data = self.summary(6, 0)
        self.assertEqual(data["previous_sales"], 600)
        self.assertEqual(data["total_sales"], 5000)

    def test_three_day_range_compares_against_the_three_days_before_it(self):
        # Window [-5..-3].
        self.sale(5, 200)
        self.sale(4, 250)
        self.sale(3, 300)
        self.sale(6, 9999)
        self.sale(2, 1000)
        data = self.summary(2, 0)
        self.assertEqual(data["previous_sales"], 750)
        self.assertEqual(data["total_sales"], 1000)

    def test_one_day_range_compares_against_that_single_day(self):
        # duration collapses to zero here, so the formula yields one day
        # rather than an empty span. Correct by accident, which is why it
        # needs pinning too.
        self.sale(1, 400)
        self.sale(2, 7000)
        self.sale(0, 900)
        data = self.summary(0, 0)
        self.assertEqual(data["previous_sales"], 400)
        self.assertEqual(data["total_sales"], 900)

    def test_expenses_are_measured_over_the_same_window_as_sales(self):
        # Two baselines under one word would put unrelated numbers side by
        # side, which is the whole fault being guarded here.
        self.sale(0, 1000)
        self.sale(1, 1000)
        self.spend(0, 40)
        self.spend(1, 25)
        self.spend(2, 7000)
        data = self.summary(0, 0)
        self.assertEqual(data["total_expenses"], 40)
        self.assertEqual(data["previous_expenses"], 25)

    def test_narrowing_the_range_moves_the_baseline_with_it(self):
        for d in (0, 1, 2):
            self.sale(d, 1000)
        self.sale(3, 100)
        self.sale(4, 100)
        # [-2..0] compares against [-5..-3]: the 100 at -3 only.
        self.assertEqual(self.summary(2, 0)["previous_sales"], 200)
        # [-1..0] compares against [-3..-2]: the 100 at -3 and the 1000.
        self.assertEqual(self.summary(1, 0)["previous_sales"], 1100)

    def test_the_percentage_is_measured_against_that_baseline(self):
        self.sale(0, 1000)
        self.sale(1, 1000)
        self.sale(3, 250)
        self.sale(4, 50)
        data = self.summary(1, 0)
        self.assertEqual(data["previous_sales"], 250)
        self.assertEqual(data["sales_delta_pct"], 700.0)
