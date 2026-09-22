from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db.models import Sum
from django.test import TestCase
from rest_framework.test import APIClient

from core.testsupport import authenticate_admin

from accounting.chart_of_accounts import ensure_seeded
from accounting.models import Account, JournalEntry
from branches.models import Branch
from expenses.models import Expense, ExpenseCategory
from partners.models import Partner
from sales.models import DailySale
from sale_sessions.models import Employee
from suppliers.models import Fabric, Supplier
from warehouses.models import FabricRoll, GoodsReceipt, StockMovement, Warehouse


class E2EBase(TestCase):
    def setUp(self):
        ensure_seeded()
        call_command("seed_categories", verbosity=0)
        self.c = APIClient()
        authenticate_admin(self.c)
        self.today = date.today().isoformat()

        r = self.c.post(
            "/api/branches/",
            {"name": "فرع اختبار E2E", "code": "E2E1", "monthly_sales_target": 100000},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)
        self.branch = r.data
        self.branch_obj = Branch.objects.get(pk=self.branch["id"])
        self.warehouse = Warehouse.objects.get(branch=self.branch_obj)

        self.supplier = Supplier.objects.create(name="مورد E2E")
        self.fabric = Fabric.objects.create(
            name="قماش E2E",
            code="E2E-F1",
            supplier=self.supplier,
            purchase_price=Decimal("3"),
            sale_price_yard=Decimal("5"),
            min_sale_yard=Decimal("4"),
            yards_per_roll=Decimal("50"),
        )
        self.emp = Employee.objects.create(name="موظف E2E", branch=self.branch_obj)
        self.emp2 = Employee.objects.create(name="موظف E2E 2", branch=self.branch_obj)

    def _purchase_to_branch(self, yards=100, rolls=2, unit_price=3):
        r = self.c.post(
            f"/api/suppliers/{self.supplier.id}/ledger/",
            {
                "entry_type": "purchase",
                "date": self.today,
                "branch": self.branch["id"],
                "items": [
                    {
                        "fabric": self.fabric.id,
                        "quantity_yards": yards,
                        "rolls": rolls,
                        "unit_price": unit_price,
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)
        return r.data

    def _branch_stock(self):
        return (
            FabricRoll.objects.filter(
                warehouse=self.warehouse, fabric=self.fabric, status="available"
            ).aggregate(total=Sum("remaining_yards"))["total"]
            or Decimal("0")
        )


class SectionsAndBasicsE2ETest(E2EBase):
    def test_sections_endpoint(self):
        r = self.c.get("/api/sections/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data["sections"])
        self.assertTrue(r.data["roles"])

    def test_branch_auto_creates_warehouse(self):
        self.assertTrue(self.warehouse.is_branch_stock)
        self.assertEqual(self.warehouse.code, "BR-E2E1")

    def test_settings_get_patch_and_backup(self):
        r = self.c.get("/api/settings/")
        self.assertEqual(r.status_code, 200, r.data)
        r = self.c.patch("/api/settings/", {"low_stock_threshold": 12}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["low_stock_threshold"], "12.00")
        r = self.c.get("/api/settings/backup/")
        self.assertEqual(r.status_code, 200)


class PurchaseAndSessionE2ETest(E2EBase):
    def test_full_purchase_then_session_close(self):
        purchase = self._purchase_to_branch(yards=100, rolls=2)
        self.assertEqual(purchase["destination_type"], "branch")
        gr = GoodsReceipt.objects.get(purchase_entry_id=purchase["id"])
        self.assertEqual(gr.status, "posted")
        self.assertEqual(self._branch_stock(), Decimal("100"))
        self.assertTrue(
            JournalEntry.objects.filter(source=JournalEntry.Source.PURCHASE).exists()
        )

        r = self.c.post("/api/sale-sessions/", {"employee": self.emp.id}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        sid = r.data["id"]
        self.assertEqual(r.data["branch"], self.branch["id"])

        r = self.c.post(
            f"/api/sale-sessions/{sid}/items/",
            {"fabric": self.fabric.id, "sale_type": "yard", "quantity": 10, "payment_method": "cash"},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Decimal(str(r.data["unit_price"])), Decimal("5"))

        r = self.c.post(
            f"/api/sale-sessions/{sid}/items/",
            {"fabric": self.fabric.id, "sale_type": "yard", "quantity": 5, "payment_method": "transfer"},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)

        r = self.c.post(f"/api/sale-sessions/{sid}/close/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["status"], "closed")

        self.assertEqual(self._branch_stock(), Decimal("85"))
        ds = DailySale.objects.get(branch=self.branch_obj)
        self.assertEqual(ds.total_sales, Decimal("75.00"))
        self.assertEqual(ds.cash_amount, Decimal("50.00"))
        self.assertEqual(ds.transfer_amount, Decimal("25.00"))
        self.assertTrue(
            JournalEntry.objects.filter(source=JournalEntry.Source.SESSION).exists()
        )

    def test_manual_session_accumulates_on_daily_sale(self):
        r = self.c.post(
            "/api/sale-sessions/manual/",
            {
                "employee": self.emp.id,
                "date": self.today,
                "cash": 30,
                "transfer": 20,
                "notes": "إدخال يدوي",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data["is_manual"])
        self.assertEqual(r.data["status"], "closed")

        r = self.c.post(
            "/api/sale-sessions/manual/",
            {"employee": self.emp.id, "date": self.today, "card": 10},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)

        ds = DailySale.objects.get(branch=self.branch_obj)
        self.assertEqual(ds.total_sales, Decimal("60.00"))
        self.assertEqual(ds.cash_amount, Decimal("30.00"))
        self.assertEqual(ds.card_amount, Decimal("10.00"))

    def test_manual_session_requires_amount(self):
        r = self.c.post(
            "/api/sale-sessions/manual/",
            {"employee": self.emp.id, "date": self.today},
            format="json",
        )
        self.assertEqual(r.status_code, 400, r.data)

    def test_daily_sale_direct(self):
        self._purchase_to_branch(yards=50, rolls=1)
        r = self.c.post(
            "/api/sales/",
            {
                "branch": self.branch["id"],
                "date": self.today,
                "total_sales": 20,
                "cash_amount": 20,
                "items": [{"fabric": self.fabric.id, "yards": 4, "unit_price": 5}],
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self._branch_stock(), Decimal("46"))

    def test_daily_sale_payment_mismatch_rejected(self):
        self._purchase_to_branch(yards=50, rolls=1)
        r = self.c.post(
            "/api/sales/",
            {
                "branch": self.branch["id"],
                "date": self.today,
                "total_sales": 20,
                "cash_amount": 10,
            },
            format="json",
        )
        self.assertEqual(r.status_code, 400, r.data)


class WarehouseE2ETest(E2EBase):
    def test_transfer_workflow(self):
        self._purchase_to_branch(yards=100, rolls=2)
        dst = Warehouse.objects.create(name="مخزن ثانوي E2E", code="E2E-W2")

        r = self.c.post(
            "/api/warehouses/transfers/",
            {
                "from_warehouse": self.warehouse.id,
                "to_warehouse": dst.id,
                "date": self.today,
                "requested_by": "مسؤول",
                "items": [{"fabric": self.fabric.id, "yards": 40, "rolls_count": 1}],
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)
        tid = r.data["id"]
        for action in ["request", "approve", "complete"]:
            body = {"approved_by": "مدير"} if action == "approve" else {}
            r = self.c.post(f"/api/warehouses/transfers/{tid}/{action}/", body, format="json")
            self.assertEqual(r.status_code, 200, (action, r.data))
        self.assertEqual(r.data["status"], "completed")
        self.assertEqual(self._branch_stock(), Decimal("60"))
        self.assertGreater(
            FabricRoll.objects.filter(warehouse=dst, fabric=self.fabric).aggregate(
                t=Sum("remaining_yards")
            )["t"],
            Decimal("0"),
        )

    def test_stock_adjustment_in(self):
        r = self.c.post(
            "/api/warehouses/adjustments/",
            {
                "warehouse": self.warehouse.id,
                "date": self.today,
                "direction": "in",
                "reason": "gain",
                "items": [{"fabric": self.fabric.id, "yards": 15, "rolls_count": 1}],
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self._branch_stock(), Decimal("15"))
        self.assertTrue(StockMovement.objects.filter(movement_type="adjustment_in").exists())

    def test_stock_count_snapshot_and_post(self):
        self._purchase_to_branch(yards=20, rolls=1)
        r = self.c.post(
            "/api/warehouses/counts/",
            {"warehouse": self.warehouse.id, "date": self.today},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)
        cid = r.data["id"]
        r = self.c.get(f"/api/warehouses/counts/{cid}/items/")
        self.assertEqual(r.status_code, 200, r.data)
        items = r.data if isinstance(r.data, list) else r.data.get("items", [])
        self.assertTrue(items)
        payload = {"items": [{"fabric": i["fabric"], "counted_yards": 18} for i in items]}
        r = self.c.put(f"/api/warehouses/counts/{cid}/items/", payload, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        r = self.c.post(f"/api/warehouses/counts/{cid}/post/")
        self.assertEqual(r.status_code, 200, r.data)

    def test_stock_opening(self):
        r = self.c.post(
            "/api/warehouses/openings/",
            {
                "warehouse": self.warehouse.id,
                "date": self.today,
                "items": [{"fabric": self.fabric.id, "yards": 30, "rolls_count": 1, "unit_price": 3}],
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self._branch_stock(), Decimal("30"))


class ExpensesPartnersCustomersE2ETest(E2EBase):
    def test_expense_and_budget(self):
        cat = ExpenseCategory.objects.create(name="إيجار E2E", code="E2E-RENT")
        r = self.c.post(
            "/api/expenses/",
            {
                "branch": self.branch["id"],
                "category": cat.id,
                "date": self.today,
                "amount": 75,
                "payment_method": "cash",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(Expense.objects.filter(branch=self.branch_obj).exists())
        self.assertTrue(
            JournalEntry.objects.filter(source=JournalEntry.Source.EXPENSE).exists()
        )
        r = self.c.post(
            "/api/expense-budgets/",
            {"branch": self.branch["id"], "category": cat.id, "month": self.today, "amount": 500},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)
        r = self.c.get(
            f"/api/reports/expenses-budget/?branch={self.branch['id']}&month={self.today[:7]}"
        )
        self.assertEqual(r.status_code, 200, r.data)

    def test_partner_operation_and_distribution(self):
        p = Partner.objects.create(name="شريك E2E", share_percent=Decimal("50"))
        r = self.c.post(
            "/api/partner-operations/",
            {
                "partner": p.id,
                "operation_type": "support",
                "amount": 1000,
                "date": self.today,
                "payment_method": "cash",
                "reason": "دعم",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(
            JournalEntry.objects.filter(source=JournalEntry.Source.PARTNER).exists()
        )
        r = self.c.get(f"/api/partners/{p.id}/movements/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertGreater(r.data["closing_balance"], 0)
        r = self.c.get("/api/partners/distribution/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data["items"])
        r = self.c.get("/api/partner-operations/summary/")
        self.assertEqual(r.status_code, 200, r.data)

    def test_customer_crud_and_lookup(self):
        r = self.c.post(
            "/api/customers/",
            {"name": "زبون E2E", "phone": "99990001", "branch": self.branch["id"]},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)
        r = self.c.get("/api/customers/lookup/?phone=99990001")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data["found"])
        r = self.c.post("/api/customers/", {"name": "مكرر", "phone": "99990001"}, format="json")
        self.assertEqual(r.status_code, 400, r.data)


class AccountingE2ETest(E2EBase):
    def test_manual_journal_reverse_and_reports(self):
        cash = Account.objects.get(source_key="CASH")
        revenue = Account.objects.get(source_key="SALE_REVENUE")
        r = self.c.post(
            "/api/journal/",
            {
                "date": self.today,
                "description": "قيد اختبار",
                "source": "manual",
                "lines": [
                    {"account": cash.id, "debit": 100, "credit": 0},
                    {"account": revenue.id, "debit": 0, "credit": 100},
                ],
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)
        jid = r.data["id"]

        r = self.c.get("/api/reports/trial-balance/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data["balanced"])

        for path in [
            "/api/reports/income-statement/",
            "/api/reports/balance-sheet/",
            "/api/reports/cash-flow/",
            "/api/reports/cashbox/",
        ]:
            r = self.c.get(path)
            self.assertEqual(r.status_code, 200, (path, r.data))

        r = self.c.post(f"/api/journal/{jid}/reverse/")
        self.assertEqual(r.status_code, 200, r.data)
        r = self.c.delete(f"/api/journal/{jid}/")
        self.assertEqual(r.status_code, 200, r.data)

    def test_close_period(self):
        cash = Account.objects.get(source_key="CASH")
        revenue = Account.objects.get(source_key="SALE_REVENUE")
        self.c.post(
            "/api/journal/",
            {
                "date": self.today,
                "description": "بيع",
                "lines": [
                    {"account": cash.id, "debit": 500, "credit": 0},
                    {"account": revenue.id, "debit": 0, "credit": 500},
                ],
            },
            format="json",
        )
        r = self.c.post(
            "/api/close-period/",
            {"period_end": self.today, "description": "إغلاق اختبار"},
            format="json",
        )
        self.assertIn(r.status_code, (200, 201), r.data)
        self.assertIn("net_profit", r.data)
        r = self.c.post(
            "/api/close-period/",
            {"period_end": self.today, "description": "مكرر"},
            format="json",
        )
        self.assertEqual(r.status_code, 400, r.data)


class ReportsDashboardMessagingE2ETest(E2EBase):
    def test_all_reports_and_dashboard(self):
        self._purchase_to_branch(yards=100, rolls=2)
        for path in [
            "/api/reports/sales/",
            "/api/reports/expenses/",
            "/api/reports/expenses-budget/",
            "/api/reports/net-daily/",
            "/api/reports/suppliers/",
            "/api/reports/branches/",
            "/api/reports/inventory/",
            "/api/reports/inventory-movements/",
            "/api/reports/cogs/",
            "/api/reports/profit-loss/",
            "/api/reports/commissions/",
            "/api/reports/journal/",
            f"/api/reports/trial-balance/",
        ]:
            r = self.c.get(path)
            self.assertEqual(r.status_code, 200, (path, getattr(r, "data", None)))
        for path in [
            "/api/dashboard/summary/",
            "/api/dashboard/alerts/",
            "/api/dashboard/activity/",
        ]:
            r = self.c.get(path)
            self.assertEqual(r.status_code, 200, (path, getattr(r, "data", None)))
        r = self.c.get("/api/sales/stock/", {"branch": self.branch["id"]})
        self.assertEqual(r.status_code, 200, r.data)
        r = self.c.get("/api/sales/stock/")
        self.assertEqual(r.status_code, 400, r.data)

    def test_messaging_flow(self):
        User = get_user_model()
        user_sender = User.objects.create_user(username="e2e_sender", password="x")
        user_receiver = User.objects.create_user(username="e2e_receiver", password="x")
        self.emp.user = user_sender
        self.emp.apply_role_preset(Employee.Role.ADMIN)
        self.emp.save()
        self.emp2.user = user_receiver
        self.emp2.apply_role_preset(Employee.Role.ADMIN)
        self.emp2.save()

        c_sender = APIClient()
        c_sender.force_authenticate(user=user_sender)
        c_receiver = APIClient()
        c_receiver.force_authenticate(user=user_receiver)

        r = c_sender.post(
            "/api/messaging/send/",
            {"receiver": self.emp2.id, "body": "مرحبا"},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)
        mid = r.data["id"]

        r = c_receiver.get("/api/messaging/unread/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["count"], 1)

        r = c_receiver.get("/api/messaging/conversations/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["unread_total"], 1)

        r = c_receiver.get(f"/api/messaging/messages/?partner={self.emp.id}")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(r.data["messages"]), 1)

        r = c_sender.post(
            f"/api/messaging/messages/{mid}/edit/",
            {"body": "مرحبا معدّل"},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.data)

        r = c_sender.post(f"/api/messaging/messages/{mid}/delete/", format="json")
        self.assertEqual(r.status_code, 200, r.data)
