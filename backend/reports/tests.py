from datetime import date, timedelta
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from core.testsupport import authenticate_admin

from branches.models import Branch
from expenses.models import Expense, ExpenseBudget, ExpenseCategory
from sale_sessions.models import Employee, SaleSession, SaleSessionItem
from sales.models import DailySale, DailySaleItem
from suppliers.models import Fabric, Supplier
from warehouses.models import GoodsReceipt, GoodsReceiptItem, StockMovement, Warehouse


class ReportsAPITest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        call_command("seed_categories", verbosity=0)

    def setUp(self):
        self.c = APIClient()
        authenticate_admin(self.c)
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

    def test_expenses_budget_report(self):
        month = self.today.replace(day=1)
        ExpenseBudget.objects.create(
            branch=self.branch, category=self.cat, month=month, amount=1000,
        )
        r = self.c.get("/api/reports/expenses-budget/", {
            "month": month.strftime("%Y-%m"),
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["items"]), 1)
        item = r.data["items"][0]
        self.assertEqual(item["budget"], 1000)
        self.assertEqual(item["spent"], 300)
        self.assertEqual(item["remaining"], 700)
        self.assertEqual(item["used_pct"], 30.0)
        self.assertEqual(r.data["totals"]["budget"], 1000)
        self.assertEqual(r.data["totals"]["spent"], 300)

    def test_expenses_budget_report_spent_without_budget(self):
        month = self.today.replace(day=1)
        r = self.c.get("/api/reports/expenses-budget/", {
            "month": month.strftime("%Y-%m"),
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["items"]), 1)
        self.assertEqual(r.data["items"][0]["budget"], 0)
        self.assertEqual(r.data["items"][0]["spent"], 300)

    def test_expenses_budget_report_xlsx(self):
        month = self.today.replace(day=1)
        ExpenseBudget.objects.create(
            branch=self.branch, category=self.cat, month=month, amount=1000,
        )
        r = self.c.get("/api/reports/expenses-budget/", {
            "month": month.strftime("%Y-%m"),
            "export": "xlsx",
        })
        self.assertEqual(r.status_code, 200)
        self.assertIn("spreadsheet", r["Content-Type"])

    def test_commissions_report(self):
        emp = Employee.objects.create(
            name="موظف", branch=self.branch, commission_active=True, commission_percent=5,
        )
        SaleSession.objects.create(
            employee=emp, branch=self.branch,
            status=SaleSession.Status.CLOSED,
            closed_at=timezone.now(),
            commission_amount=120,
        )
        r = self.c.get("/api/reports/commissions/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["items"]), 1)
        self.assertEqual(r.data["items"][0]["employee_name"], "موظف")
        self.assertEqual(r.data["items"][0]["total_commission"], 120)
        self.assertEqual(r.data["totals"]["commission"], 120)

    def test_commissions_report_xlsx(self):
        emp = Employee.objects.create(
            name="موظف", branch=self.branch, commission_active=True, commission_percent=5,
        )
        SaleSession.objects.create(
            employee=emp, branch=self.branch,
            status=SaleSession.Status.CLOSED,
            closed_at=timezone.now(),
            commission_amount=120,
        )
        r = self.c.get("/api/reports/commissions/", {"export": "xlsx"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("spreadsheet", r["Content-Type"])

    def _session_with_items(self, employee, **session_kwargs):
        session = SaleSession.objects.create(
            employee=employee,
            branch=self.branch,
            status=SaleSession.Status.CLOSED,
            closed_at=timezone.now(),
            **session_kwargs,
        )
        fabric, _ = Fabric.objects.get_or_create(
            code="Q-TEST-1",
            defaults={"name": "قماش", "purchase_price": Decimal("10")},
        )
        items = [
            SaleSessionItem(
                session=session, fabric=fabric, sale_date=self.today,
                sale_type=SaleSessionItem.SaleType.YARD,
                quantity=Decimal("70"), unit_price=Decimal("5"), total=Decimal("350"),
            ),
            SaleSessionItem(
                session=session, fabric=fabric, sale_date=self.today,
                sale_type=SaleSessionItem.SaleType.ROLL,
                quantity=Decimal("4"), unit_price=Decimal("100"), total=Decimal("400"),
            ),
        ]
        for item in items:
            item.save()
        return session, items

    def test_commissions_report_counts_pieces_per_employee(self):
        """الطلب: عدد القطع المباعة لكل موظف في توزيع المبيعات.

        القطعة طرد من 3.5 ياردة. فمن باع 70 ياردة باع 20 قطعة، لا 70؛
        ومن باع 4 طاقات باع 4 قطع لا 14. وجمع النوعين يعطي الرقم الذي
        يقابله المخزن.
        """
        emp = Employee.objects.create(
            name="بائع", branch=self.branch, commission_active=True, commission_percent=5,
        )
        self._session_with_items(emp)

        r = self.c.get("/api/reports/commissions/")
        self.assertEqual(r.status_code, 200)
        row = r.data["items"][0]
        self.assertEqual(row["total_yards"], 84.0)          # 70 + (4 × 3.5)
        self.assertEqual(row["total_pieces"], 24.0)        # 20 + 4
        self.assertEqual(r.data["totals"]["pieces"], 24.0)
        self.assertEqual(r.data["totals"]["yards"], 84.0)

    def test_commissions_report_excludes_returned_items(self):
        emp = Employee.objects.create(
            name="بائع", branch=self.branch, commission_active=True, commission_percent=5,
        )
        _, items = self._session_with_items(emp)
        returned = items[0]
        returned.is_returned = True
        returned.returned_at = timezone.now()
        returned.save()

        r = self.c.get("/api/reports/commissions/")
        row = r.data["items"][0]
        self.assertEqual(row["returned_items"], 1)
        # بقيت الطاقات وحدها: 4 قطع = 14 ياردة.
        self.assertEqual(row["total_pieces"], 4.0)
        self.assertEqual(row["total_yards"], 14.0)

    def test_commissions_report_lists_the_top_seller_first(self):
        quiet = Employee.objects.create(name="هادئ", branch=self.branch)
        loud = Employee.objects.create(name="نشيط", branch=self.branch)
        self._session_with_items(quiet)
        self._session_with_items(loud)

        r = self.c.get("/api/reports/commissions/")
        self.assertEqual(len(r.data["items"]), 2)
        self.assertEqual(r.data["items"][0]["employee_name"], "نشيط")

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
        authenticate_admin(self.c)
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

    def test_cogs_money_is_cents_even_when_cost_divides_oddly(self):
        """مئتان على سبعة: متوسطُ تكلفة لا ينتهي، فيُمَدُّ ذيلُه إن لم يُقرَّب."""
        receipt = GoodsReceipt.objects.create(number="GR-3", date=self.today, status="posted")
        fabric = Fabric.objects.create(
            name="كتان", code="FAB-7", unit="yard", sale_price_yard=Decimal("1.006"),
        )
        GoodsReceiptItem.objects.create(
            receipt=receipt, fabric=fabric, yards=Decimal("7"),
            unit_price=Decimal("28.571"), total=Decimal("200"),
        )
        sale = DailySale.objects.get(branch=self.branch, date=self.today)
        DailySaleItem.objects.create(sale=sale, fabric=fabric, yards=Decimal("7"))

        r = self.c.get("/api/reports/cogs/", {
            "date_from": self.today.isoformat(),
            "date_to": self.today.isoformat(),
        })
        self.assertEqual(r.status_code, 200)
        row = next(x for x in r.data["items"] if x["fabric_name"] == "كتان")
        self.assertEqual(row["revenue"], 7.04)
        self.assertEqual(row["cogs"], 200.0)
        self.assertEqual(row["profit"], -192.96)
        for value in (row["revenue"], row["cogs"], row["profit"]):
            self.assertEqual(value, round(value, 2), repr(value))
        for key in ("revenue", "cogs", "profit"):
            self.assertEqual(r.data["totals"][key], round(r.data["totals"][key], 2))

    def test_profit_loss_totals_are_cents(self):
        r = self.c.get("/api/reports/profit-loss/", {
            "date_from": self.today.isoformat(),
            "date_to": self.today.isoformat(),
        })
        self.assertEqual(r.status_code, 200)
        for key in ("total_sales", "cogs", "gross_profit", "salaries", "expenses", "net_profit"):
            value = r.data["totals"][key]
            self.assertIsInstance(value, float, key)
            self.assertEqual(value, round(value, 2), "%s = %r" % (key, value))
        for row in r.data["branches"]:
            for key in ("sales", "cogs", "salaries", "expenses", "net"):
                value = row[key]
                self.assertIsInstance(value, float, key)
                self.assertEqual(value, round(value, 2), "%s = %r" % (key, value))

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

    def test_profit_loss_includes_salaries(self):
        """صافي الربح = مبيعات - تكلفة - رواتب - مصاريف (الرواتب تدخل في التقرير)."""
        from datetime import datetime

        from django.utils import timezone as tz

        from payroll.models import PayrollRun, Payslip

        emp = Employee.objects.create(name="موظف الربح", branch=self.branch)
        run1 = PayrollRun.objects.create(
            month=date(2026, 3, 1), branch=self.branch,
            status=PayrollRun.Status.APPROVED,
        )
        Payslip.objects.create(run=run1, employee=emp, branch=self.branch, base_salary=500)
        run2 = PayrollRun.objects.create(
            month=date(2026, 3, 1), branch=None,
            status=PayrollRun.Status.PAID,
            paid_at=tz.make_aware(datetime(2026, 3, 15, 12, 0)),
        )
        Payslip.objects.create(run=run2, employee=emp, branch=self.branch, base_salary=300)

        r = self.c.get("/api/reports/profit-loss/", {
            "date_from": "2026-03-01",
            "date_to": "2026-03-31",
        })
        self.assertEqual(r.status_code, 200)
        t = r.data["totals"]
        # كل مسيّر غير ملغى يغطي شهراً داخل الفترة يُحسب في «الرواتب» المستحقة.
        self.assertEqual(t["salaries"], 800.0)
        # المدفوع فعلياً فقط حسب تاريخ الصرف.
        self.assertEqual(t["salaries_paid"], 300.0)
        self.assertEqual(t["net_profit"], t["gross_profit"] - t["salaries"] - t["expenses"])

        branch_row = next(
            b for b in r.data["branches"] if b["branch_name"] == self.branch.name
        )
        self.assertEqual(branch_row["salaries"], 800.0)
        self.assertIn("cogs", branch_row)

    def test_profit_loss_excludes_out_of_range_salary_month(self):
        """مسيّر شهر لا يتداخل مع الفترة لا يُحتسب في الرواتب."""
        from payroll.models import PayrollRun, Payslip

        emp = Employee.objects.create(name="خارج الفترة", branch=self.branch)
        run = PayrollRun.objects.create(
            month=date(2026, 5, 1), branch=self.branch,
            status=PayrollRun.Status.APPROVED,
        )
        Payslip.objects.create(run=run, employee=emp, branch=self.branch, base_salary=999)

        r = self.c.get("/api/reports/profit-loss/", {
            "date_from": "2026-03-01",
            "date_to": "2026-03-31",
        })
        self.assertEqual(r.data["totals"]["salaries"], 0.0)

    def test_profit_loss_xlsx_export(self):
        r = self.c.get("/api/reports/profit-loss/", {"export": "xlsx"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("spreadsheetml.sheet", r.headers["Content-Type"])

    def test_profit_loss_margins(self):
        """الهامشان يُحسبان من صافي المبيعات: مجمل 840/1000 وصافي 540/1000."""
        r = self.c.get("/api/reports/profit-loss/", {
            "date_from": self.today.isoformat(),
            "date_to": self.today.isoformat(),
        })
        t = r.data["totals"]
        self.assertEqual(t["gross_margin_pct"], 84.0)
        self.assertEqual(t["net_margin_pct"], 54.0)

    def test_profit_loss_margins_null_when_no_sales(self):
        r = self.c.get("/api/reports/profit-loss/", {
            "date_from": (self.today + timedelta(days=5)).isoformat(),
            "date_to": (self.today + timedelta(days=6)).isoformat(),
        })
        t = r.data["totals"]
        self.assertIsNone(t["gross_margin_pct"])
        self.assertIsNone(t["net_margin_pct"])

    def test_profit_loss_expense_breakdown(self):
        other = ExpenseCategory.objects.create(name="صيانة", code="maint")
        Expense.objects.create(
            branch=self.branch, category=other,
            date=self.today, amount=100,
        )
        r = self.c.get("/api/reports/profit-loss/", {
            "date_from": self.today.isoformat(),
            "date_to": self.today.isoformat(),
        })
        bd = r.data["expense_breakdown"]
        self.assertEqual(bd["total"], 400.0)
        # مرتّبة تنازلياً بالمبلغ، لذا المصروف (300) قبل الصيانة (100).
        self.assertEqual(bd["items"][0]["category_name"], "مصروف")
        self.assertEqual(bd["items"][0]["amount"], 300.0)
        self.assertEqual(bd["items"][0]["pct_of_total"], 75.0)
        self.assertEqual(bd["items"][1]["category_name"], "صيانة")
        self.assertEqual(bd["items"][1]["amount"], 100.0)
        self.assertEqual(bd["items"][1]["pct_of_total"], 25.0)

    def test_profit_loss_collection_breakdown(self):
        DailySale.objects.filter(branch=self.branch, date=self.today).update(
            cash_amount=600, transfer_amount=200, card_amount=150, other_amount=50,
        )
        r = self.c.get("/api/reports/profit-loss/", {
            "date_from": self.today.isoformat(),
            "date_to": self.today.isoformat(),
        })
        col = r.data["collection"]
        self.assertEqual(col["cash"], 600.0)
        self.assertEqual(col["transfer"], 200.0)
        self.assertEqual(col["card"], 150.0)
        self.assertEqual(col["other"], 50.0)
        self.assertEqual(col["collected"], 1000.0)
        self.assertEqual(col["collection_rate_pct"], 100.0)

    def test_profit_loss_collection_rate_below_100(self):
        """التحصيل الناقص (آجل/معلّق) يجب أن ينعكس كنسبة أقل من 100%."""
        DailySale.objects.filter(branch=self.branch, date=self.today).update(total_sales=1200)
        r = self.c.get("/api/reports/profit-loss/", {
            "date_from": self.today.isoformat(),
            "date_to": self.today.isoformat(),
        })
        col = r.data["collection"]
        self.assertEqual(col["sales"], 1200.0)
        self.assertEqual(col["collected"], 1000.0)
        self.assertEqual(col["collection_rate_pct"], 83.3)

    def test_profit_loss_daily_rows(self):
        """السطر اليومي: مبيعات 1000 − تكلفة 160 − مصاريف 300 = 540 صافي."""
        r = self.c.get("/api/reports/profit-loss/", {
            "date_from": self.today.isoformat(),
            "date_to": self.today.isoformat(),
        })
        daily = r.data["daily"]
        self.assertEqual(len(daily), 1)
        row = daily[0]
        self.assertEqual(row["date"], self.today.isoformat())
        self.assertEqual(row["sales"], 1000.0)
        self.assertEqual(row["cogs"], 160.0)
        self.assertEqual(row["gross_profit"], 840.0)
        self.assertEqual(row["expenses"], 300.0)
        self.assertEqual(row["net"], 540.0)
        self.assertEqual(row["net_margin_pct"], 54.0)

    def test_profit_loss_daily_rows_exclude_salaries(self):
        """الرواتب تخص شهراً كاملاً، فلا تُوزَّع على الأيام فيبقى صافي اليوم سالباً."""
        from payroll.models import Payslip, PayrollRun

        emp = Employee.objects.create(name="موظف", branch=self.branch)
        run = PayrollRun.objects.create(
            month=self.today.replace(day=1), branch=self.branch,
            status=PayrollRun.Status.APPROVED,
        )
        Payslip.objects.create(run=run, employee=emp, branch=self.branch, base_salary=900)
        r = self.c.get("/api/reports/profit-loss/", {
            "date_from": self.today.isoformat(),
            "date_to": self.today.isoformat(),
        })
        self.assertEqual(r.data["totals"]["net_profit"], 540.0 - 900.0)
        self.assertEqual(r.data["daily"][0]["net"], 540.0)

    def test_profit_loss_daily_spans_multiple_days(self):
        DailySale.objects.create(
            branch=self.branch, date=self.today + timedelta(days=1),
            total_sales=250, cash_amount=250,
        )
        r = self.c.get("/api/reports/profit-loss/", {
            "date_from": self.today.isoformat(),
            "date_to": (self.today + timedelta(days=1)).isoformat(),
        })
        days = [d["date"] for d in r.data["daily"]]
        self.assertEqual(days, sorted(days))
        self.assertEqual(len(days), 2)
        self.assertEqual(sum(d["sales"] for d in r.data["daily"]), 1250.0)
        # يوم بلا مصاريف يظهر بصفري لا يُحذف.
        tomorrow = next(d for d in r.data["daily"] if d["date"] == days[-1])
        self.assertEqual(tomorrow["expenses"], 0.0)
        self.assertEqual(tomorrow["sales"], 250.0)

    def test_profit_loss_comparison_no_previous_data(self):
        """بلا بيانات في الفترة السابقة، نسب التغيّر تكون None لا صفراً."""
        r = self.c.get("/api/reports/profit-loss/", {
            "date_from": self.today.isoformat(),
            "date_to": self.today.isoformat(),
        })
        cmp = r.data["comparison"]
        self.assertEqual(cmp["totals"]["total_sales"], 0.0)
        self.assertIsNone(cmp["change_pct"]["total_sales"])
        self.assertIsNone(cmp["change_pct"]["net_profit"])

    def test_profit_loss_comparison_change_pct(self):
        """مبيعات اليوم 1000 مقابل 500 في فترة سابقة بطول يوم واحد = +100%."""
        prev_day = self.today - timedelta(days=1)
        DailySale.objects.create(
            branch=self.branch, date=prev_day, total_sales=500, cash_amount=500,
        )
        r = self.c.get("/api/reports/profit-loss/", {
            "date_from": self.today.isoformat(),
            "date_to": self.today.isoformat(),
        })
        cmp = r.data["comparison"]
        # فترة يوم واحد، فالفترة السابقة هي اليوم السابق وحده.
        self.assertEqual(cmp["date_from"], (self.today - timedelta(days=1)).isoformat())
        self.assertEqual(cmp["date_to"], (self.today - timedelta(days=1)).isoformat())
        self.assertEqual(cmp["totals"]["total_sales"], 500.0)
        self.assertEqual(cmp["change_pct"]["total_sales"], 100.0)
        # المصاريف: 300 اليوم مقابل 0 سابقاً ⇒ بلا أساس ⇒ None.
        self.assertIsNone(cmp["change_pct"]["expenses"])

    def test_profit_loss_comparison_period_length_matches(self):
        """الفترة السابقة بنفس طول الفترة الحالية مهما كان الطول."""
        start = self.today - timedelta(days=4)
        end = self.today + timedelta(days=2)
        r = self.c.get("/api/reports/profit-loss/", {
            "date_from": start.isoformat(), "date_to": end.isoformat(),
        })
        cmp = r.data["comparison"]
        self.assertEqual(cmp["date_to"], (start - timedelta(days=1)).isoformat())
        self.assertEqual(cmp["date_from"], (start - timedelta(days=7)).isoformat())

    def test_profit_loss_branch_row_net_margin(self):
        r = self.c.get("/api/reports/profit-loss/", {
            "date_from": self.today.isoformat(),
            "date_to": self.today.isoformat(),
        })
        row = next(b for b in r.data["branches"] if b["branch_name"] == self.branch.name)
        self.assertEqual(row["sales"], 1000.0)
        self.assertEqual(row["cogs"], 160.0)
        self.assertEqual(row["net"], 540.0)
        self.assertEqual(row["net_margin_pct"], 54.0)

    def test_profit_loss_xlsx_has_all_sheets(self):
        import io

        r = self.c.get("/api/reports/profit-loss/", {"export": "xlsx"})
        self.assertEqual(r.status_code, 200)
        try:
            import openpyxl
        except ImportError:
            self.skipTest("openpyxl not installed")
        wb = openpyxl.load_workbook(io.BytesIO(r.content))
        for sheet in (
            "الربح والخسارة بعد كل شيء", "حسب الفرع",
            "تفصيل المصاريف", "تفصيل التحصيل", "التفصيل اليومي",
        ):
            self.assertIn(sheet, wb.sheetnames)

    def test_profit_loss_branch_filter_scopes_everything(self):
        """تصفية الفرع يجب أن تنعكس على كل الأقسام لا الإجماليات فقط."""
        other_branch = Branch.objects.create(name="C", code="C")
        cat2 = ExpenseCategory.objects.create(name="مصرفات", code="ops")
        DailySale.objects.create(
            branch=other_branch, date=self.today, total_sales=4000, cash_amount=4000,
        )
        Expense.objects.create(
            branch=other_branch, category=cat2, date=self.today, amount=250,
        )
        r = self.c.get("/api/reports/profit-loss/", {
            "date_from": self.today.isoformat(),
            "date_to": self.today.isoformat(),
            "branch": self.branch.id,
        })
        self.assertEqual(r.data["totals"]["total_sales"], 1000.0)
        self.assertEqual(r.data["expense_breakdown"]["total"], 300.0)
        self.assertEqual(r.data["collection"]["sales"], 1000.0)
        self.assertEqual(r.data["daily"][0]["sales"], 1000.0)
        self.assertEqual([b["branch_name"] for b in r.data["branches"]], [self.branch.name])
        # المقارنة تحترم نفس التصفية.
        self.assertEqual(r.data["comparison"]["totals"]["total_sales"], 0.0)

    def test_profit_loss_daily_cogs_across_multiple_branches(self):
        """تكلفة البضاعة المباعة اليومية تُجمع عبر الفروع بلا تكرار ولا نقصان."""
        other_branch = Branch.objects.create(name="C", code="C")
        # متوسط تكلفة f1 = 200 ÷ 100 = 2 للياردة.
        sale2 = DailySale.objects.create(
            branch=other_branch, date=self.today, total_sales=400, cash_amount=400,
        )
        DailySaleItem.objects.create(sale=sale2, fabric=self.f1, yards=40)
        r = self.c.get("/api/reports/profit-loss/", {
            "date_from": self.today.isoformat(),
            "date_to": self.today.isoformat(),
        })
        # 80 ياردة في الفرع B + 40 في الفرع C = 120 × 2 = 240.
        self.assertEqual(r.data["daily"][0]["cogs"], 240.0)
        self.assertEqual(r.data["totals"]["cogs"], 240.0)
        self.assertEqual(sum(b["cogs"] for b in r.data["branches"]), 240.0)

    def test_profit_loss_purchases(self):
        """تكلفة المشتريات = قيم الاستلامات المرحّلة داخل الفترة فقط."""
        r = self.c.get("/api/reports/profit-loss/", {
            "date_from": self.today.isoformat(),
            "date_to": self.today.isoformat(),
        })
        # السند GR-1 المرحّل: 100 ياردة × 2 = 200.
        self.assertEqual(r.data["stock"]["purchases"]["value"], 200.0)
        self.assertEqual(r.data["stock"]["purchases"]["yards"], 100.0)
        self.assertEqual(r.data["stock"]["purchases"]["avg_cost"], 2.0)

    def test_profit_loss_purchases_ignores_draft(self):
        """سند مسوّدة ليس مشتريات محقّقة."""
        draft = GoodsReceipt.objects.create(
            number="GR-DRAFT", date=self.today, status="draft",
        )
        GoodsReceiptItem.objects.create(
            receipt=draft, fabric=self.f1, rolls_count=1,
            yards=50, unit_price=9, total=450,
        )
        r = self.c.get("/api/reports/profit-loss/", {
            "date_from": self.today.isoformat(),
            "date_to": self.today.isoformat(),
        })
        self.assertEqual(r.data["stock"]["purchases"]["value"], 200.0)

    def test_profit_loss_purchases_outside_period(self):
        """استلام قبل الفترة لا يُحتسب كمشتريات الفترة."""
        r = self.c.get("/api/reports/profit-loss/", {
            "date_from": (self.today + timedelta(days=1)).isoformat(),
            "date_to": (self.today + timedelta(days=2)).isoformat(),
        })
        self.assertEqual(r.data["stock"]["purchases"]["value"], 0.0)
        self.assertIsNone(r.data["stock"]["purchases"]["avg_cost"])

    def test_profit_loss_purchases_unattributable_warehouse(self):
        """استلام في مخزن بلا فرع لا يُنسب لأي فرع عند التصفية."""
        # مخزن W في setUp بلا فرع.
        self.assertIsNone(Warehouse.objects.get(name="W").branch_id)
        r = self.c.get("/api/reports/profit-loss/", {
            "date_from": self.today.isoformat(),
            "date_to": self.today.isoformat(),
            "branch": self.branch.id,
        })
        self.assertEqual(r.data["stock"]["purchases"]["value"], 0.0)

    def test_profit_loss_purchases_respects_branch_filter(self):
        """تصفية الفرع لا تسرّب مشتريات فرع آخر عبر مخزنه."""
        # سند setUp أسند إلى مخزن بلا فرع، فنسنده للفرع ليجري الاختبار على أساس واضح.
        wh = Warehouse.objects.get(name="W")
        wh.branch = self.branch
        wh.save()
        other = Branch.objects.create(name="C", code="C")
        wh2 = Warehouse.objects.create(name="W2", code="W2", branch=other)
        r2 = GoodsReceipt.objects.create(
            number="GR-2", warehouse=wh2, date=self.today, status="posted",
        )
        GoodsReceiptItem.objects.create(
            receipt=r2, fabric=self.f1, rolls_count=1,
            yards=10, unit_price=5, total=50,
        )
        # بلا تصفية: المجموع 250.
        r = self.c.get("/api/reports/profit-loss/", {
            "date_from": self.today.isoformat(),
            "date_to": self.today.isoformat(),
        })
        self.assertEqual(r.data["stock"]["purchases"]["value"], 250.0)
        # مع تصفية: سند المستودع الأول فقط.
        r = self.c.get("/api/reports/profit-loss/", {
            "date_from": self.today.isoformat(),
            "date_to": self.today.isoformat(),
            "branch": self.branch.id,
        })
        self.assertEqual(r.data["stock"]["purchases"]["value"], 200.0)

    def test_profit_loss_closing_stock(self):
        """رصيد الإقفال = آخر رصيد مسجّل لكل (مخزن × قماش) عند نهاية الفترة."""
        wh = Warehouse.objects.get(name="W")
        wh.branch = self.branch
        wh.save()
        StockMovement.objects.create(
            warehouse=wh, fabric=self.f1,
            movement_type=StockMovement.Type.RECEIPT,
            quantity=100, balance_after=100, date=self.today,
        )
        StockMovement.objects.create(
            warehouse=wh, fabric=self.f1,
            movement_type=StockMovement.Type.SALE,
            quantity=-30, balance_after=70, date=self.today,
        )
        r = self.c.get("/api/reports/profit-loss/", {
            "date_from": self.today.isoformat(),
            "date_to": self.today.isoformat(),
        })
        closing = r.data["stock"]["closing"]
        # آخر حركة تركت 70 ياردة، ومتوسط التكلفة 2 للياردة.
        self.assertEqual(closing["yards"], 70.0)
        self.assertEqual(closing["value"], 140.0)

    def test_profit_loss_closing_stock_ignores_movements_after_period(self):
        """حركة بعد نهاية الفترة لا تؤثر على رصيد الإقفال."""
        wh = Warehouse.objects.get(name="W")
        wh.branch = self.branch
        wh.save()
        StockMovement.objects.create(
            warehouse=wh, fabric=self.f1,
            movement_type=StockMovement.Type.RECEIPT,
            quantity=100, balance_after=100, date=self.today,
        )
        later = self.today + timedelta(days=10)
        StockMovement.objects.create(
            warehouse=wh, fabric=self.f1,
            movement_type=StockMovement.Type.SALE,
            quantity=-40, balance_after=60, date=later,
        )
        r = self.c.get("/api/reports/profit-loss/", {
            "date_from": self.today.isoformat(),
            "date_to": self.today.isoformat(),
        })
        self.assertEqual(r.data["stock"]["closing"]["yards"], 100.0)
        self.assertEqual(r.data["stock"]["closing"]["value"], 200.0)

    def test_profit_loss_closing_stock_without_recorded_balance(self):
        """حركة بلا رصيد مسجّل لا تُحتسب، ونتيجة ذلك رصيد صفر لا خطأ."""
        wh = Warehouse.objects.get(name="W")
        wh.branch = self.branch
        wh.save()
        StockMovement.objects.create(
            warehouse=wh, fabric=self.f1,
            movement_type=StockMovement.Type.ADJUSTMENT_IN,
            quantity=50, balance_after=None, date=self.today,
        )
        r = self.c.get("/api/reports/profit-loss/", {
            "date_from": self.today.isoformat(),
            "date_to": self.today.isoformat(),
        })
        self.assertEqual(r.data["stock"]["closing"]["yards"], 0.0)
        self.assertEqual(r.data["stock"]["closing"]["value"], 0.0)

    def test_profit_loss_unsold_value(self):
        """قيمة البضاعة غير المباعة = قيمة مشتريات الفترة − تكلفة المباع.

        كان الحساب يقارن رصيد الإقفال (رصيد) بتكلفة المبيعات (تدفّق)، وهو
        ما جعل الرقم سالباً في أول شهر تشغيلي وفي كل شهر يُصفّي مخزوناً
        قديمة أكثر مما يشتري.
        """
        wh = Warehouse.objects.get(name="W")
        wh.branch = self.branch
        wh.save()
        StockMovement.objects.create(
            warehouse=wh, fabric=self.f1,
            movement_type=StockMovement.Type.RECEIPT,
            quantity=100, balance_after=100, date=self.today,
        )
        r = self.c.get("/api/reports/profit-loss/", {
            "date_from": self.today.isoformat(),
            "date_to": self.today.isoformat(),
        })
        # المخزون 100 ياردة × 2 = 200، وبُيع 80 ياردة بتكلفة 160.
        self.assertEqual(r.data["totals"]["cogs"], 160.0)
        self.assertEqual(r.data["stock"]["closing"]["value"], 200.0)
        self.assertEqual(r.data["stock"]["unsold_value"], 40.0)
        self.assertEqual(r.data["stock"]["unsold_margin_pct"], 20.0)

    def test_profit_loss_xlsx_has_stock_sheet(self):
        import io

        r = self.c.get("/api/reports/profit-loss/", {"export": "xlsx"})
        self.assertEqual(r.status_code, 200)
        try:
            import openpyxl
        except ImportError:
            self.skipTest("openpyxl not installed")
        wb = openpyxl.load_workbook(io.BytesIO(r.content))
        self.assertIn("المشتريات والمخزون", wb.sheetnames)

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


class AnalyticsReportsTests(TestCase):
    """تقارير Reports V2 — العقد الموحّد والمقارنة مع الفترة السابقة."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        call_command("seed_categories", verbosity=0)

    def setUp(self):
        self.c = APIClient()
        authenticate_admin(self.c)
        self.branch = Branch.objects.create(name="فرع التقارير", code="R2")
        self.supplier = Supplier.objects.create(name="مورد التقارير")
        self.cat = ExpenseCategory.objects.get(name="إيجار")
        self.today = date.today()
        self.fabric = Fabric.objects.create(
            name="قطن", code="R2-F1", unit="yard", sale_price_yard=20, min_stock=10
        )
        warehouse = Warehouse.objects.create(name="مخزن التقارير")
        receipt = GoodsReceipt.objects.create(
            number="GR-R2", warehouse=warehouse, date=self.today, status="posted"
        )
        GoodsReceiptItem.objects.create(
            receipt=receipt, fabric=self.fabric, rolls_count=1, yards=100,
            unit_price=16, total=1600,
        )
        sale = DailySale.objects.create(
            branch=self.branch, date=self.today, total_sales=1000,
            cash_amount=600, transfer_amount=200, card_amount=150, other_amount=50,
            employee=Employee.objects.create(name="مندعف", branch=self.branch),
        )
        DailySaleItem.objects.create(sale=sale, fabric=self.fabric, yards=10)
        Expense.objects.create(
            branch=self.branch, category=self.cat, date=self.today, amount=300
        )
        # مبيعات الفترة السابقة (اليوم الذي قبل) لاختبار المقارنة
        DailySale.objects.create(
            branch=self.branch, date=self.today - timedelta(days=1),
            total_sales=400, cash_amount=400,
        )

    def _params(self, **extra):
        params = {"date_from": self.today.isoformat(), "date_to": self.today.isoformat()}
        params.update(extra)
        return params

    def test_summary_kpis_compare_previous_period(self):
        r = self.c.get("/api/reports/summary/", self._params())
        self.assertEqual(r.status_code, 200, r.data)
        keys = [k["key"] for k in r.data["kpis"]]
        self.assertIn("sales", keys)
        self.assertIn("net", keys)
        self.assertIn("margin", keys)
        self.assertEqual(r.data["period"]["to"], self.today.isoformat())
        # الفترة السابقة = اليوم السابق (400)، فالمقارنة 1000 مقابل 400 = +150%
        sales = next(k for k in r.data["kpis"] if k["key"] == "sales")
        self.assertEqual(sales["value"], 1000.0)
        self.assertEqual(sales["previous"], 400.0)
        self.assertEqual(sales["change_pct"], 150.0)

    def test_sales_trend_buckets_and_series(self):
        r = self.c.get("/api/reports/sales-trend/", self._params(group_by="day"))
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["group_by"], "day")
        self.assertEqual(len(r.data["rows"]), 1)
        row = r.data["rows"][0]
        self.assertEqual(row["total_sales"], 1000.0)
        self.assertEqual(row["cash"], 600.0)
        self.assertEqual(row["avg_ticket"], 1000.0)
        self.assertEqual(r.data["series"]["current"], [1000.0])

    def test_sales_trend_auto_grouping(self):
        r = self.c.get("/api/reports/sales-trend/", self._params())
        self.assertEqual(r.data["group_by"], "day")
        r = self.c.get("/api/reports/sales-trend/", {
            "date_from": (self.today - timedelta(days=200)).isoformat(),
            "date_to": self.today.isoformat(),
        })
        self.assertEqual(r.data["group_by"], "month")

    def test_branch_performance(self):
        r = self.c.get("/api/reports/branch-performance/", self._params())
        self.assertEqual(r.status_code, 200, r.data)
        row = next(x for x in r.data["rows"] if x["branch_name"] == "فرع التقارير")
        self.assertEqual(row["sales"], 1000.0)
        self.assertEqual(row["expenses"], 300.0)
        self.assertEqual(row["net"], 700.0)
        self.assertEqual(row["share"], 100.0)

    def test_employee_performance(self):
        r = self.c.get("/api/reports/employee-performance/", self._params())
        self.assertEqual(r.status_code, 200, r.data)
        row = next(x for x in r.data["rows"] if x["employee_name"] == "مندعف")
        self.assertEqual(row["sales"], 1000.0)

    def test_fabric_profitability(self):
        r = self.c.get("/api/reports/fabric-profitability/", self._params())
        self.assertEqual(r.status_code, 200, r.data)
        row = next(x for x in r.data["rows"] if x["fabric_name"] == "قطن")
        self.assertEqual(row["yards"], 10.0)
        self.assertEqual(row["revenue"], 200.0)
        self.assertEqual(row["cogs"], 160.0)
        self.assertEqual(row["profit"], 40.0)
        self.assertEqual(row["margin"], 20.0)

    def test_inventory_slow_marks_unsold_fabric(self):
        from suppliers.models import Fabric as Fab
        from warehouses.models import FabricRoll, Warehouse

        idle = Fab.objects.create(name="راكد", code="R2-IDLE")
        warehouse = Warehouse.objects.get(name="مخزن التقارير")
        FabricRoll.objects.create(
            warehouse=warehouse, fabric=idle, code="ROLL-IDLE",
            yards=40, remaining_yards=40, status=FabricRoll.Status.AVAILABLE,
        )
        r = self.c.get("/api/reports/inventory-slow/", self._params(idle_days="1"))
        self.assertEqual(r.status_code, 200, r.data)
        row = next(x for x in r.data["rows"] if x["fabric_name"] == "راكد")
        self.assertEqual(row["status"], "لم يُبع")
        self.assertEqual(row["yards"], 40.0)

    def test_supplier_aging_buckets(self):
        from suppliers.models import LedgerEntry

        LedgerEntry.objects.create(
            supplier=self.supplier, date=self.today - timedelta(days=100),
            entry_type=LedgerEntry.EntryType.PURCHASE, amount=Decimal("500"),
        )
        LedgerEntry.objects.create(
            supplier=self.supplier, date=self.today - timedelta(days=5),
            entry_type=LedgerEntry.EntryType.PAYMENT, amount=Decimal("-200"),
        )
        r = self.c.get("/api/reports/supplier-aging/", self._params())
        self.assertEqual(r.status_code, 200, r.data)
        row = next(x for x in r.data["rows"] if x["party_name"] == "مورد التقارير")
        self.assertEqual(row["balance"], 300.0)
        self.assertEqual(row["over_90"], 300.0)
        self.assertEqual(row["oldest_days"], 100)

    def test_partner_aging_balance(self):
        from partners.models import Partner, PartnerMovement, PartnerOperation

        partner = Partner.objects.create(name="شريك اختبار", share_percent=Decimal("50"))
        support = PartnerOperation.objects.create(
            number="OP-1", partner=partner, date=self.today - timedelta(days=40),
            operation_type=PartnerOperation.OperationType.SUPPORT, amount=Decimal("1000"),
        )
        withdraw = PartnerOperation.objects.create(
            number="OP-2", partner=partner, date=self.today,
            operation_type=PartnerOperation.OperationType.WITHDRAW, amount=Decimal("400"),
        )
        # حركة لكل شريك عند كل عملية (كما ينشئها الـAPI)
        PartnerMovement.objects.create(
            operation=support, partner=partner,
            movement_type=PartnerMovement.MovementType.SUPPORT, amount=Decimal("1000"),
        )
        PartnerMovement.objects.create(
            operation=withdraw, partner=partner,
            movement_type=PartnerMovement.MovementType.WITHDRAW, amount=Decimal("400"),
        )
        r = self.c.get("/api/reports/partner-aging/", self._params())
        self.assertEqual(r.status_code, 200, r.data)
        row = next(x for x in r.data["rows"] if x["party_name"] == "شريك اختبار")
        self.assertEqual(row["balance"], 600.0)
        self.assertEqual(row["d31_60"], 600.0)
        self.assertEqual(row["withdraw"], 400.0)

    def test_cashflow_in_out(self):
        r = self.c.get("/api/reports/cashflow/", self._params())
        self.assertEqual(r.status_code, 200, r.data)
        row = r.data["rows"][0]
        self.assertEqual(row["inflow"], 600.0)
        self.assertEqual(row["outflow"], 300.0)
        self.assertEqual(row["net"], 300.0)

    def test_payroll_report_empty(self):
        r = self.c.get("/api/reports/payroll/", self._params())
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["rows"], [])
        self.assertEqual(r.data["totals"]["net"], 0.0)

    def test_xlsx_export_uses_columns(self):
        r = self.c.get("/api/reports/branch-performance/", self._params(export="xlsx"))
        self.assertEqual(r.status_code, 200)
        self.assertIn("spreadsheetml.sheet", r.headers["Content-Type"])

    def test_envelope_contract(self):
        r = self.c.get("/api/reports/fabric-profitability/", self._params())
        for field in ("key", "title", "columns", "rows", "totals", "kpis", "period", "previous"):
            self.assertIn(field, r.data)
        for col in r.data["columns"]:
            self.assertIn("key", col)
            self.assertIn("label", col)
            self.assertIn(col["type"], ("text", "money", "number", "percent", "date"))
