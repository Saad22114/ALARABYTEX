"""Check that every riyal on the home screen can be traced back to a line item.

There was a report that the dashboard figures "look like a million riyals".
Nothing in the formatting multiplied anything and nothing in the database was
over seven thousand, so the arithmetic was audited by hand and came back clean.
Hand audits go stale the moment a sale is entered, so this is the audit as a
command: run it whenever a number on the screen looks wrong, and it either
prints "clean" or names the exact row that disagrees.

    python manage.py audit_money
    python manage.py audit_money --branch 33
    python manage.py audit_money --limit 20

Four checks, from the bottom of the pile upwards:

1. every sale line equals quantity * unit_price - discount
2. every card line nets off its card fee
3. every payment split on a daily row adds up to that row's total
4. every daily row equals its own lines plus the manual sessions for that day

Check 4 is the one that matters for the dashboard, because DailySale is what
the summary endpoint sums. A day whose lines were edited after the daily row
was written would show a stale total on the home screen with no warning
anywhere, and this is the only place that would notice.
"""
from collections import defaultdict
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Sum

from expenses.models import Expense
from machine_account.models import MachineCollection
from sale_sessions.models import SaleSession, SaleSessionItem
from sales.models import DailySale

TOLERANCE = Decimal("0.05")
ZERO = Decimal("0")


def dec(value) -> Decimal:
    """Decimal from anything, including a float that has already drifted."""
    return Decimal(str(value if value is not None else 0))


class Command(BaseCommand):
    help = "Trace every dashboard figure back to the sale lines behind it."

    def add_arguments(self, parser):
        parser.add_argument("--branch", type=int, default=None,
                            help="only audit this branch id")
        parser.add_argument("--limit", type=int, default=10,
                            help="how many offending rows to print per check")

    def handle(self, *args, **options):
        branch = options["branch"]
        limit = options["limit"]
        failures = 0

        def report(title, problems, describe):
            nonlocal failures
            if problems:
                failures += 1
                self.stdout.write(self.style.ERROR(f"FAIL  {title}"))
                for row in problems[:limit]:
                    self.stdout.write("      " + describe(row))
                if len(problems) > limit:
                    self.stdout.write(f"      ... and {len(problems) - limit} more")
            else:
                self.stdout.write(self.style.SUCCESS(f"ok    {title}"))

        # --- 1 and 2, in one pass ----------------------------------------
        # Both checks read the same row, so the row is fetched once. Asking for
        # fewer fields than the checks read would be worse, not better: a
        # deferred attribute is a query, and this loop is over every line the
        # shop has ever sold.
        lines = SaleSessionItem.objects.select_related("session")
        if branch:
            lines = lines.filter(session__branch_id=branch)

        wanted = ("id", "quantity", "unit_price", "discount_amount", "total",
                  "net_total", "card_fee_amount", "payment_method", "sale_date",
                  "session__branch_id")
        rows = list(lines.only(*wanted))

        bad_lines = []
        bad_cards = []
        card_count = 0
        for i in rows:
            expected = dec(i.quantity) * dec(i.unit_price) - dec(i.discount_amount)
            if abs(expected - dec(i.total)) > TOLERANCE:
                bad_lines.append((i, expected))
            if i.payment_method == SaleSessionItem.PaymentMethod.CARD:
                card_count += 1
                if abs(dec(i.total) - dec(i.card_fee_amount) - dec(i.net_total)) > TOLERANCE:
                    bad_cards.append(i)

        report(
            f"sale lines: quantity x price - discount = total ({len(rows)} lines)",
            bad_lines,
            lambda row: (f"line {row[0].id} on {row[0].sale_date} "
                         f"branch {row[0].session.branch_id}: "
                         f"{row[0].quantity} x {row[0].unit_price} "
                         f"- {row[0].discount_amount} = {row[1]}, "
                         f"stored {row[0].total}"),
        )

        report(f"card lines: total - fee = net ({card_count} lines)",
               bad_cards,
               lambda i: (f"line {i.id} on {i.sale_date}: {i.total} - {i.card_fee_amount} "
                          f"!= {i.net_total}"))

        # --- 3. the payment split on the daily row ------------------------
        days = DailySale.objects.all()
        if branch:
            days = days.filter(branch_id=branch)
        bad_splits = [d for d in days
                      if abs(d.payment_total - dec(d.total_sales)) > TOLERANCE]
        report(f"daily rows: cash + transfer + card + other = total ({days.count()} rows)",
               bad_splits,
               lambda d: (f"{d.date} branch {d.branch_id}: split {d.payment_total} "
                          f"!= total {d.total_sales}"))

        # --- 4. the daily row against its own lines and manual sessions ---
        net_by_day = defaultdict(lambda: ZERO)
        for i in rows:
            net_by_day[(i.session.branch_id, i.sale_date)] += dec(i.net_total)

        manual_by_day = defaultdict(lambda: ZERO)
        manual = SaleSession.objects.filter(is_manual=True)
        if branch:
            manual = manual.filter(branch_id=branch)
        for s in manual.only("branch_id", "session_date", "manual_date",
                             "manual_cash", "manual_transfer", "manual_card"):
            when = s.session_date or s.manual_date
            if when is None:
                continue
            manual_by_day[(s.branch_id, when)] += (
                dec(s.manual_cash) + dec(s.manual_transfer) + dec(s.manual_card))

        bad_days = []
        for d in days.only("id", "branch_id", "date", "total_sales"):
            key = (d.branch_id, d.date)
            expected = net_by_day.get(key, ZERO) + manual_by_day.get(key, ZERO)
            if abs(expected - dec(d.total_sales)) > TOLERANCE:
                bad_days.append((d, net_by_day.get(key, ZERO),
                                 manual_by_day.get(key, ZERO), expected))

        report("daily rows: lines + manual sessions = total", bad_days,
               lambda row: (f"{row[0].date} branch {row[0].branch_id}: lines {row[1]} "
                            f"+ manual {row[2]} = {row[3]}, stored {row[0].total_sales}"))

        # --- what the dashboard actually reads ----------------------------
        sales = days.aggregate(t=Sum("total_sales"))["t"] or ZERO
        biggest = days.order_by("-total_sales").first()
        # From `rows`, not from a fresh query: `rows` is already scoped to
        # --branch, and a headline that ignores the filter would answer a
        # different question than the one the operator asked.
        biggest_line = max(rows, key=lambda i: dec(i.total), default=None)
        self.stdout.write("")
        self.stdout.write(f"all-time sales     : {sales}")
        self.stdout.write(f"largest day        : {biggest.total_sales if biggest else ZERO}"
                          f"  ({biggest.date if biggest else '-'})")
        self.stdout.write(f"largest sale line  : {biggest_line.total if biggest_line else ZERO}"
                          f"  ({biggest_line.sale_date if biggest_line else '-'})")
        over = days.filter(total_sales__gt=1000000).count()
        self.stdout.write(f"days over a million: {over}")

        # --- the other two streams the dashboard sums ----------------------
        expenses = Expense.objects.all()
        collections = MachineCollection.objects.all()
        if branch:
            expenses = expenses.filter(branch_id=branch)
            collections = collections.filter(branch_id=branch)
        e_total = expenses.aggregate(t=Sum("amount"))["t"] or ZERO
        c_total = collections.aggregate(t=Sum("amount"))["t"] or ZERO
        self.stdout.write(f"all-time expenses  : {e_total}")
        self.stdout.write(f"all-time collections: {c_total}")

        if failures:
            self.stdout.write(self.style.ERROR(
                f"\n{failures} check(s) disagree. The dashboard sums DailySale.total_sales,"))
            self.stdout.write(self.style.ERROR(
                "so check 4 is the one that moves the numbers on the home screen."))
        else:
            self.stdout.write(self.style.SUCCESS("\nEvery figure traces back to its lines."))
