from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db.models import Sum
from django.test import TestCase
from rest_framework.test import APIClient
from core.testsupport import authenticate_admin

from branches.models import Branch
from expenses.models import Expense, ExpenseCategory
from sale_sessions.models import Employee, SaleSession
from sales.models import DailySale, DailySaleItem
from suppliers.models import Fabric, LedgerEntry, Supplier
from warehouses.models import FabricRoll, GoodsReceipt, GoodsReceiptItem, Warehouse

from core.money import money, unit_price


class DashboardMoneyTest(TestCase):
    def test_money_rounds_to_cents(self):
        self.assertEqual(money(Decimal("1.006")), 1.01)
        self.assertEqual(money(Decimal("0.1") + Decimal("0.2")), 0.3)
        self.assertEqual(money(Decimal(1) / Decimal(3) * 3), 1.0)

    def test_money_accepts_none_and_numbers(self):
        self.assertEqual(money(None), 0.0)
        self.assertEqual(money(5), 5.0)
        self.assertEqual(money(2.5), 2.5)

    def test_money_stays_a_json_number(self):
        self.assertIsInstance(money(Decimal("1.006")), float)
        self.assertIsInstance(money(None), float)

    def test_unit_price_keeps_three_places(self):
        self.assertEqual(unit_price(Decimal("0.6666")), 0.667)
        self.assertEqual(unit_price(Decimal("2")), 2.0)
        self.assertEqual(unit_price(None), 0.0)


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

    def test_net_includes_cost_of_goods_sold_expenses_and_salaries(self):
        from payroll.models import Payslip, PayrollRun

        sold_fabric = Fabric.objects.create(name="مباع", code="SOLD", unit="yard")
        unsold_fabric = Fabric.objects.create(name="غير مباع", code="UNSOLD", unit="yard")
        receipt = GoodsReceipt.objects.create(
            number="DASH-COGS-1", date=self.today, status="posted",
        )
        GoodsReceiptItem.objects.create(
            receipt=receipt, fabric=sold_fabric, rolls_count=1,
            yards=100, unit_price=2, total=200,
        )
        GoodsReceiptItem.objects.create(
            receipt=receipt, fabric=unsold_fabric, rolls_count=1,
            yards=100, unit_price=90, total=9000,
        )
        sale = DailySale.objects.get(branch=self.branch, date=self.today)
        DailySaleItem.objects.create(sale=sale, fabric=sold_fabric, yards=10)

        employee = Employee.objects.create(name="موظف الراتب", branch=self.branch)
        run = PayrollRun.objects.create(
            month=self.today.replace(day=1), branch=self.branch,
            status=PayrollRun.Status.APPROVED,
        )
        Payslip.objects.create(
            run=run, employee=employee, branch=self.branch, base_salary=100,
        )

        response = self.c.get("/api/dashboard/summary/", {"period": "today"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_cogs"], 20.0)
        self.assertEqual(response.data["gross_profit"], 980.0)
        self.assertEqual(response.data["total_expenses"], 200.0)
        self.assertEqual(response.data["total_salaries"], 100.0)
        self.assertEqual(response.data["net"], 680.0)

    def _sell_a_yard_at_a_three_decimal_price(self):
        """قماشٌ سعرُ ياردته 1.006 — ثلاثةُ خانات، والمبلغُ خانتان."""
        fabric = Fabric.objects.create(
            name="حرير", code="FAB-3", unit="yard", sale_price_yard=Decimal("1.006"),
        )
        sale = DailySale.objects.get(branch=self.branch, date=self.today)
        DailySaleItem.objects.create(sale=sale, fabric=fabric, yards=1)
        return fabric

    def test_top_fabrics_revenue_is_a_cents_amount(self):
        fabric = self._sell_a_yard_at_a_three_decimal_price()
        r = self.c.get("/api/dashboard/summary/", {"period": "today"})
        self.assertEqual(r.status_code, 200)
        row = next(x for x in r.data["top_fabrics"] if x["fabric"] == fabric.id)
        self.assertEqual(row["revenue"], 1.01)
        self.assertEqual(row["cogs"], 0.0)
        self.assertEqual(row["profit"], 1.01)

    def test_no_money_field_carries_a_third_decimal(self):
        self._sell_a_yard_at_a_three_decimal_price()
        r = self.c.get("/api/dashboard/summary/", {"period": "week"})
        self.assertEqual(r.status_code, 200)

        def check(value, where):
            self.assertIsInstance(value, float, where)
            self.assertEqual(value, round(value, 2), "%s = %r" % (where, value))

        for key in (
            "total_sales", "total_expenses", "net", "gross_profit",
            "previous_sales", "previous_expenses", "previous_net",
        ):
            check(r.data[key], key)
        for chart in ("chart_data", "chart_previous"):
            for row in r.data[chart]:
                for key in ("sales", "expenses", "net", "cogs", "gross_profit"):
                    check(row[key], "%s/%s" % (chart, key))
        for row in r.data["top_fabrics"]:
            for key in ("revenue", "cogs", "profit"):
                check(row[key], "top_fabrics/%s" % key)

    def test_alert_amounts_are_cents(self):
        self._sell_a_yard_at_a_three_decimal_price()
        r = self.c.get("/api/dashboard/alerts/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(round(r.data["today"]["net"], 2), r.data["today"]["net"])

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
