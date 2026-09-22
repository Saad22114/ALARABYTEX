from decimal import Decimal
from datetime import date
import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from branches.models import Branch
from expenses.models import Expense, ExpenseCategory
from partners.models import Partner, PartnerOperation
from sale_sessions.models import Employee
from suppliers.models import Fabric, LedgerEntry, Supplier
from warehouses.models import FabricRoll, Warehouse

from .models import Account, ClosedPeriod, JournalEntry, JournalLine
from .services import (
    balance_sheet,
    cash_flow,
    cash_box,
    close_period,
    create_entry,
    income_statement,
    post_expense,
    post_partner_operation,
    post_session_close,
    post_supplier_entry,
    trial_balance,
    unpost_source,
)
from .chart_of_accounts import ensure_seeded

User = get_user_model()


class AccountingSetup(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_seeded()
        cls.user = User.objects.create_user("admin", password="pass1234")
        cls.branch = Branch.objects.create(name="فرع 1", code="BR1")
        cls.employee = Employee(
            name="محاسب الاختبار",
            branch=cls.branch,
            user=cls.user,
        )
        cls.employee.apply_role_preset(Employee.Role.ADMIN)
        cls.employee.save()
        cls.supplier = Supplier.objects.create(name="مورد 1")
        cls.fabric = Fabric.objects.create(
            name="قماش",
            code="F001",
            supplier=cls.supplier,
            purchase_price=Decimal("10"),
            sale_price_yard=Decimal("20"),
            yards_per_roll=100,
        )
        cls.expense_cat = ExpenseCategory.objects.create(name="إيجار", code="EXP-RENT")
        cls.partner = Partner.objects.create(name="شريك 1")
        cls.warehouse = Warehouse.objects.create(name="مخزن 1", code="WH1", branch=cls.branch)
        FabricRoll.objects.create(
            fabric=cls.fabric,
            warehouse=cls.warehouse,
            code="ROLL-001",
            yards=Decimal("100"),
            remaining_yards=Decimal("100"),
            unit_cost=cls.fabric.purchase_price,
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)


class AccountTests(AccountingSetup):
    def test_list(self):
        res = self.client.get("/api/accounts/")
        self.assertEqual(res.status_code, 200)
        self.assertGreater(len(res.json()["results"]), 0)

    def test_create(self):
        res = self.client.post(
            "/api/accounts/",
            {"code": "9901", "name": "حساب اختبار", "type": "asset"},
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(Account.objects.get(pk=res.json()["id"]).code, "9901")

    def test_update(self):
        acc = Account.objects.filter(type=Account.Type.ASSET, is_system=False).first()
        res = self.client.patch(
            f"/api/accounts/{acc.pk}/",
            json.dumps({"name": "تعديل"}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(Account.objects.get(pk=acc.pk).name, "تعديل")

    def test_delete_guard_system(self):
        acc = Account.objects.filter(is_system=True).first()
        res = self.client.delete(f"/api/accounts/{acc.pk}/")
        self.assertEqual(res.status_code, 400)
        self.assertIn("نظامي", res.json()["detail"])

    def test_delete_guard_lines(self):
        acc = Account.objects.get(source_key="CASH")
        create_entry(date(2025, 1, 1), "t", JournalEntry.Source.MANUAL, None, [(acc, 100, 100, "")])
        res = self.client.delete(f"/api/accounts/{acc.pk}/")
        self.assertEqual(res.status_code, 400)


class JournalEntryTests(AccountingSetup):
    def test_create_manual(self):
        cash = Account.objects.get(source_key="CASH")
        rev = Account.objects.get(source_key="SALE_REVENUE")
        res = self.client.post(
            "/api/journal/",
            json.dumps({
                "date": "2025-06-01",
                "description": "بيع",
                "source": "manual",
                "lines": [
                    {"account": cash.pk, "debit": 100, "credit": 0},
                    {"account": rev.pk, "debit": 0, "credit": 100},
                ],
            }),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 201, res.data)
        entry = JournalEntry.objects.get(pk=res.json()["id"])
        self.assertEqual(entry.source, JournalEntry.Source.MANUAL)
        self.assertEqual(entry.lines.count(), 2)

    def test_reject_unbalanced(self):
        cash = Account.objects.get(source_key="CASH")
        rev = Account.objects.get(source_key="SALE_REVENUE")
        res = self.client.post(
            "/api/journal/",
            json.dumps({
                "date": "2025-06-01",
                "source": "manual",
                "lines": [
                    {"account": cash.pk, "debit": 100, "credit": 0},
                    {"account": rev.pk, "debit": 0, "credit": 80},
                ],
            }),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("غير متوازن", str(res.json()))

    def test_reverse_manual(self):
        cash = Account.objects.get(source_key="CASH")
        rev = Account.objects.get(source_key="SALE_REVENUE")
        entry = create_entry(date(2025, 1, 1), "t", JournalEntry.Source.MANUAL, None, [(cash, 100, 0, ""), (rev, 0, 100, "")])
        res = self.client.post(f"/api/journal/{entry.pk}/reverse/")
        self.assertEqual(res.status_code, 200)
        entry.refresh_from_db()
        self.assertIsNotNone(entry.reversed_at)

    def test_reject_delete_auto(self):
        entry = create_entry(date(2025, 1, 1), "t", JournalEntry.Source.SESSION, 999, [])
        res = self.client.delete(f"/api/journal/{entry.pk}/")
        self.assertEqual(res.status_code, 400)

    def test_filter_source(self):
        e1 = create_entry(date(2025, 1, 1), "a", JournalEntry.Source.MANUAL, None, [])
        e2 = create_entry(date(2025, 1, 1), "b", JournalEntry.Source.SESSION, 999, [])
        res = self.client.get("/api/journal/?source=manual")
        ids = [e["id"] for e in res.json()["results"]]
        self.assertIn(e1.pk, ids)
        self.assertNotIn(e2.pk, ids)


class AutoPostTests(AccountingSetup):
    def test_post_session_creates_entry(self):
        from sale_sessions.models import Employee, SaleSession, SaleSessionItem
        from sale_sessions.services import close_session

        emp = Employee.objects.create(name="مندوب", branch=self.branch)
        session = SaleSession.objects.create(employee=emp, branch=self.branch)
        SaleSessionItem.objects.create(
            session=session,
            fabric=self.fabric,
            sale_type=SaleSessionItem.SaleType.YARD,
            quantity=Decimal("10"),
            unit_price=Decimal("20"),
            total=Decimal("200"),
            sale_date=date.today(),
            payment_method=SaleSessionItem.PaymentMethod.CASH,
        )
        close_session(session)
        entry = JournalEntry.objects.filter(source=JournalEntry.Source.SESSION, source_id=session.pk).first()
        self.assertIsNotNone(entry)
        self.assertGreaterEqual(entry.lines.count(), 2)

    def test_post_expense(self):
        exp = Expense.objects.create(
            branch=self.branch,
            category=self.expense_cat,
            date=date(2025, 6, 1),
            amount=Decimal("50"),
            payment_method=Expense.PaymentMethod.CASH,
            description="叮",
        )
        post_expense(exp)
        entry = JournalEntry.objects.filter(source=JournalEntry.Source.EXPENSE, source_id=exp.pk).first()
        self.assertIsNotNone(entry)
        self.assertEqual(entry.lines.count(), 2)

    def test_unpost_on_delete_expense(self):
        exp = Expense.objects.create(
            branch=self.branch,
            category=self.expense_cat,
            date=date(2025, 6, 1),
            amount=Decimal("50"),
            payment_method=Expense.PaymentMethod.CASH,
            description="叮",
        )
        post_expense(exp)
        self.assertTrue(JournalEntry.objects.filter(source=JournalEntry.Source.EXPENSE, source_id=exp.pk).exists())
        unpost_source(JournalEntry.Source.EXPENSE, exp.pk)
        self.assertFalse(JournalEntry.objects.filter(source=JournalEntry.Source.EXPENSE, source_id=exp.pk).exists())

    def test_post_partner(self):
        op = PartnerOperation.objects.create(
            partner=self.partner,
            operation_type=PartnerOperation.OperationType.SUPPORT,
            date=date(2025, 6, 1),
            amount=Decimal("1000"),
            payment_method="cash",
            reason="دعم",
        )
        post_partner_operation(op)
        entry = JournalEntry.objects.filter(source=JournalEntry.Source.PARTNER, source_id=op.pk).first()
        self.assertIsNotNone(entry)

    def test_post_supplier_opening(self):
        entry = LedgerEntry.objects.create(
            supplier=self.supplier,
            entry_type=LedgerEntry.EntryType.OPENING,
            date=date(2025, 1, 1),
            amount=Decimal("5000"),
        )
        post_supplier_entry(entry)
        je = JournalEntry.objects.filter(source=JournalEntry.Source.PURCHASE, source_id=entry.pk).first()
        self.assertIsNotNone(je)


class ReportsTests(AccountingSetup):
    def test_trial_balance(self):
        result = trial_balance()
        self.assertIn("totals", result)
        self.assertAlmostEqual(result["totals"]["debit"], result["totals"]["credit"], places=2)

    def test_income_statement(self):
        result = income_statement(date(2025, 1, 1), date(2025, 12, 31))
        self.assertIn("net_profit", result)

    def test_balance_sheet(self):
        result = balance_sheet()
        self.assertTrue(result["balanced"])

    def test_cash_flow(self):
        result = cash_flow()
        self.assertIn("totals", result)

    def test_cashbox(self):
        result = cash_box()
        self.assertIn("opening", result)

    def test_close_period(self):
        cash = Account.objects.get(source_key="CASH")
        rev = Account.objects.get(source_key="SALE_REVENUE")
        create_entry(date(2025, 6, 1), "بيع", JournalEntry.Source.MANUAL, None, [(cash, 1000, 0, ""), (rev, 0, 1000, "")])
        result = close_period(date(2025, 12, 31), description="سنوي")
        self.assertIn("net_profit", result)
        self.assertEqual(ClosedPeriod.objects.filter(period_end=date(2025, 12, 31)).count(), 1)

    def test_close_period_duplicate(self):
        cash = Account.objects.get(source_key="CASH")
        rev = Account.objects.get(source_key="SALE_REVENUE")
        create_entry(date(2025, 6, 1), "بيع", JournalEntry.Source.MANUAL, None, [(cash, 1000, 0, ""), (rev, 0, 1000, "")])
        close_period(date(2025, 12, 31), description="سنوي")
        with self.assertRaises(ValueError):
            close_period(date(2025, 12, 31), description="مكرر")


class AccountingAPITests(AccountingSetup):
    def test_reports_trial_balance(self):
        res = self.client.get("/api/reports/trial-balance/")
        self.assertEqual(res.status_code, 200)

    def test_reports_income_statement(self):
        res = self.client.get("/api/reports/income-statement/?from=2025-01-01&to=2025-12-31")
        self.assertEqual(res.status_code, 200)

    def test_reports_balance_sheet(self):
        res = self.client.get("/api/reports/balance-sheet/")
        self.assertEqual(res.status_code, 200)

    def test_reports_cash_flow(self):
        res = self.client.get("/api/reports/cash-flow/")
        self.assertEqual(res.status_code, 200)

    def test_reports_cashbox(self):
        res = self.client.get("/api/reports/cashbox/")
        self.assertEqual(res.status_code, 200)

    def test_close_period_api(self):
        cash = Account.objects.get(source_key="CASH")
        rev = Account.objects.get(source_key="SALE_REVENUE")
        create_entry(date(2025, 6, 1), "بيع", JournalEntry.Source.MANUAL, None, [(cash, 1000, 0, ""), (rev, 0, 1000, "")])
        res = self.client.post(
            "/api/close-period/",
            {"period_end": "2025-12-31", "description": "سنوي"},
            format="json",
        )
        self.assertEqual(res.status_code, 201)