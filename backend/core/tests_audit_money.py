"""A command that always says "ok" proves nothing, so plant the disagreement.

`audit_money` was written after someone reported that the home screen figures
looked like a million riyals. The arithmetic was clean by hand, so the audit
became a command -- and a command nobody has ever seen fail is not evidence.
These tests break each check on purpose and insist the command names the row.
"""

from datetime import date
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from branches.models import Branch
from sale_sessions.models import Employee, SaleSession, SaleSessionItem
from sales.models import DailySale
from suppliers.models import Fabric

SALE_DAY = date(2026, 9, 15)


class AuditMoneyTest(TestCase):
    """Each test writes one clean fixture, breaks exactly one thing, and reads
    the command's own output."""

    def setUp(self):
        self.branch = Branch.objects.create(name="فرع التدقيق", code="AUD")
        self.employee = Employee.objects.create(name="بائع", branch=self.branch)
        self.fabric = Fabric.objects.create(name="قماش التدقيق", code="AUD-F")
        self.session = SaleSession.objects.create(
            employee=self.employee, branch=self.branch, session_date=SALE_DAY,
        )
        self.item = SaleSessionItem.objects.create(
            session=self.session,
            fabric=self.fabric,
            quantity=Decimal("10"),
            unit_price=Decimal("20"),
            discount_amount=Decimal("0"),
            payment_method=SaleSessionItem.PaymentMethod.CASH,
            net_total=Decimal("200"),
            total=Decimal("200"),
            sale_date=SALE_DAY,
        )
        self.daily = DailySale.objects.create(
            branch=self.branch,
            date=SALE_DAY,
            total_sales=Decimal("200"),
            cash_amount=Decimal("200"),
        )

    def run_audit(self, **kwargs):
        out = StringIO()
        call_command("audit_money", stdout=out, stderr=out, **kwargs)
        return out.getvalue()

    # --- the clean case ----------------------------------------------------
    def test_clean_fixture_reports_every_check_ok(self):
        text = self.run_audit()
        self.assertNotIn("FAIL", text)
        self.assertIn("lines + manual sessions = total", text)
        self.assertIn("Every figure traces back to its lines.", text)

    # --- check 1: the line's own arithmetic --------------------------------
    def test_a_line_that_does_not_multiply_out_is_named(self):
        self.item.total = Decimal("250")
        self.item.save(update_fields=["total"])
        text = self.run_audit()
        self.assertIn("FAIL", text)
        self.assertIn(f"line {self.item.id}", text)

    # --- check 2: the card fee --------------------------------------------
    def test_a_card_line_that_ignores_its_fee_is_named(self):
        self.item.payment_method = SaleSessionItem.PaymentMethod.CARD
        self.item.card_fee_amount = Decimal("5")
        self.item.total = Decimal("200")
        self.item.net_total = Decimal("200")  # should have been 195
        self.item.save(update_fields=["payment_method", "card_fee_amount",
                                      "total", "net_total"])
        self.daily.card_amount = Decimal("200")
        self.daily.cash_amount = Decimal("0")
        self.daily.save(update_fields=["card_amount", "cash_amount"])
        text = self.run_audit()
        self.assertIn("FAIL", text)
        self.assertIn("card lines", text)

    # --- check 3: the payment split ----------------------------------------
    def test_a_daily_row_whose_split_does_not_add_up_is_named(self):
        self.daily.cash_amount = Decimal("150")
        self.daily.save(update_fields=["cash_amount"])
        text = self.run_audit()
        self.assertIn("FAIL", text)
        self.assertIn("cash + transfer + card + other", text)

    # --- check 4: the one that moves the dashboard -------------------------
    def test_a_daily_row_that_forgot_its_lines_is_named(self):
        # The shape a stale aggregate takes: the lines are still there, the
        # daily row was never updated. This is what the home screen would show
        # and it would show it with no warning anywhere else.
        self.daily.total_sales = Decimal("999999")
        self.daily.cash_amount = Decimal("999999")
        self.daily.save(update_fields=["total_sales", "cash_amount"])
        text = self.run_audit()
        self.assertIn("FAIL", text)
        self.assertIn("lines + manual sessions", text)
        self.assertIn("stored 999999", text.replace(",", ""))

    def test_an_edited_line_that_leaves_the_daily_row_stale_is_named(self):
        self.item.quantity = Decimal("1000")
        self.item.total = Decimal("20000")
        self.item.net_total = Decimal("20000")
        self.item.save(update_fields=["quantity", "total", "net_total"])
        text = self.run_audit()
        self.assertIn("FAIL", text)
        self.assertIn("lines + manual sessions", text)

    # --- manual sessions are money too ------------------------------------
    def test_manual_money_counts_towards_the_daily_row(self):
        manual = SaleSession.objects.create(
            employee=self.employee, branch=self.branch,
            is_manual=True, manual_date=SALE_DAY,
            manual_cash=Decimal("50"),
        )
        self.daily.total_sales = Decimal("250")
        self.daily.cash_amount = Decimal("250")
        self.daily.save(update_fields=["total_sales", "cash_amount"])
        text = self.run_audit()
        self.assertIn("lines + manual sessions", text)
        self.assertNotIn("FAIL", text)
        manual.delete()

    # --- the branch filter -------------------------------------------------
    def test_branch_filter_ignores_other_branches(self):
        # The amount is deliberately distinctive. Asserting on row ids would be
        # a trap: "2" is a substring of "200 lines", so a scoping test written
        # that way passes or fails by accident.
        stash = Decimal("7654321.25")
        other = Branch.objects.create(name="فرع آخر", code="AUD2")
        SaleSessionItem.objects.create(
            session=SaleSession.objects.create(
                employee=self.employee, branch=other, session_date=SALE_DAY),
            fabric=self.fabric,
            quantity=Decimal("3"),
            unit_price=Decimal("7"),
            discount_amount=Decimal("0"),
            net_total=Decimal("21"),
            total=Decimal("21"),
            sale_date=SALE_DAY,
        )
        DailySale.objects.create(
            branch=other, date=SALE_DAY, total_sales=stash,
            cash_amount=stash,
        )

        broken = self.run_audit()
        self.assertIn("FAIL", broken)
        self.assertIn("7654321.25", broken)

        scoped = self.run_audit(branch=self.branch.id)
        self.assertNotIn("7654321.25", scoped)
        self.assertNotIn("FAIL", scoped)

    # --- the headline figures ---------------------------------------------
    def test_it_reports_the_largest_day_and_how_many_days_pass_a_million(self):
        text = self.run_audit()
        self.assertIn("largest day", text)
        self.assertIn("days over a million: 0", text)
