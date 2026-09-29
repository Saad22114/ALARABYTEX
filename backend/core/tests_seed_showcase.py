"""اختبارات أمر البيانات الشاملة ``seed_showcase``.

الغرض من هذا الملف ليس «الأمر لا يرمي استثناء» — بل أن يثبت ما وعد به الأمر:
أن كل شاشة لها بيانات تُفتح عليها، وأن الأرقام التي تعرضها التقارير متوافقة
مع الحركات والقيود التي صنعتها. اختبار يحفظ الموظف والفرع موجود، أو يثبت أن
صافي الربح موجب في كل شهر، أو أن ميزان المراجعة متوازن — هو الفارق بين
«بيانات تجريبية» و«بيانات تُختبر بها القواعد».
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db.models import Sum
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounting.models import JournalEntry, JournalLine
from branches.models import Branch
from core.testsupport import authenticate_admin
from customers.models import Customer
from expenses.models import Expense
from partners.models import Partner, PartnerOperation
from payroll.models import (
    AdvanceInstallment,
    PayrollRun,
    Payslip,
    SalaryAdvance,
    SalaryStructure,
)
from sale_sessions.models import Employee, SaleSession, SaleSessionItem
from sales.models import DailySale, DailySaleItem
from suppliers.models import Fabric, LedgerEntry, PurchaseItem, Supplier
from warehouses.models import (
    FabricRoll,
    GoodsReceipt,
    StockAdjustment,
    StockCount,
    StockMovement,
    StockOpening,
    StockTransfer,
    Warehouse,
)

User = get_user_model()


def month_start(value: date):
    return value.replace(day=1)


def add_months(value: date, months: int) -> date:
    index = value.year * 12 + (value.month - 1) + months
    return date(index // 12, index % 12 + 1, 1)


class SeedShowcaseBase(TestCase):
    """يشغّل الأمر مرّة واحدة لكل اختبار (وهي الحالة الوحيدة المهمة هنا)."""

    months = 2
    seed = 20260929

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # ما لا يجوز للأمر أن يمسّه: نتركه قبل التشغيل ونتأكد أنه باقٍ.
        cls.kept_branch = Branch.objects.create(name="فرع الاختبار", code="KEEP1")
        cls.kept_employee = Employee.objects.create(
            name="موظف محفوظ", branch=cls.kept_branch
        )
        cls.login_username = "account_to_keep"
        cls.login_user = User.objects.create_user(cls.login_username, password="pass1234")

        cls.ran_at = timezone.localdate()
        call_command(
            "seed_showcase", months=cls.months, verbosity=0, random_seed=cls.seed
        )

    def setUp(self):
        self.c = APIClient()
        authenticate_admin(self.c)


class SeedPreservesWhatItPromises(SeedShowcaseBase):
    def test_keeps_branches_and_employees(self):
        """الطلب الصريح: يمسح كل شيء **عدا** الموظفين والفروع."""
        self.assertTrue(Branch.objects.filter(pk=self.kept_branch.pk).exists())
        self.assertTrue(Employee.objects.filter(pk=self.kept_employee.pk).exists())
        self.assertEqual(Employee.objects.get(pk=self.kept_employee.pk).name, "موظف محفوظ")

    def test_links_every_login_account_to_an_employee(self):
        """حساب دخول بلا موظف يدخل الموقع فلا يرى شيئاً ولا يُسمح له.

        الصلاحيات تُقاس عبر ``Employee`` لا عبر ``auth.User``، فحساب بلا موظف
        يرى شاشة فارغة أو 403 في كل تقرير — وهو أسوأ ما يمكن أن يُترك لمن
        يفتح بيانات الاختبار.
        """
        self.assertTrue(User.objects.filter(username=self.login_username).exists())
        employee = Employee.objects.filter(user=self.login_user).first()
        self.assertIsNotNone(employee, "حساب الدخول لم يُربط بموظف")
        self.assertTrue(employee.is_active)
        self.assertIn(employee.role, dict(Employee.Role.choices))

        # وربطه يعمل فعلياً: يفتح تقرير الربح والخسارة بلا 403.
        res = self.c.get("/api/reports/profit-loss/")
        self.assertEqual(res.status_code, 200)

    def test_gives_every_branch_a_warehoused_staffed_employee(self):
        """بلا موظف في فرع لا يمكن فتح وردية بيع أصلاً، فيبقى الفرع بلا مبيعات."""
        for branch in Branch.objects.filter(is_active=True):
            self.assertTrue(
                Employee.objects.filter(branch=branch).exists(),
                f"الفرع {branch.code} بلا موظف",
            )
            self.assertIsNotNone(
                Warehouse.for_branch(branch), f"الفرع {branch.code} بلا مخزن"
            )

    def test_is_deterministic_for_a_fixed_seed(self):
        """نفس البذرة على قاعدة نظيفة تعطي نفس الأرقام.

        بدون هذا لا معنى لقول «البيانات متكرّرة»: تغيّر بذرة عشوائية يساوي
        تغيّر الأرقام، وهو ما يجعل كل خطأ في تقرير يبدو صحيحاً مرّة ويخطئ
        مرّة.
        """

        def totals():
            return (
                DailySale.objects.count(),
                DailySale.objects.aggregate(s=Sum("total_sales"))["s"],
            )

        first = totals()
        call_command(
            "seed_showcase", months=self.months, verbosity=0, random_seed=self.seed
        )
        self.assertEqual(
            totals(), first, "إعادة التشغيل ببذرة واحدة غيّرت الأرقام"
        )


class SeedPopulatesEveryScreen(SeedShowcaseBase):
    def test_supplies_fabrics_customers_partners_and_warehouses(self):
        self.assertGreaterEqual(Fabric.objects.count(), 8)
        self.assertGreaterEqual(Supplier.objects.count(), 4)
        self.assertGreaterEqual(Customer.objects.count(), 4)
        self.assertGreaterEqual(Partner.objects.count(), 2)
        self.assertGreaterEqual(Warehouse.objects.count(), 4)

    def test_builds_sales_through_the_real_session_flow(self):
        """المبيعات ورديات مغلقة، لا صفوفاً مُدخلة في جدول المبيعات مباشرة."""
        self.assertGreaterEqual(SaleSession.objects.count(), 40)
        self.assertEqual(
            SaleSession.objects.exclude(status=SaleSession.Status.CLOSED).count(),
            0,
            "بقيت وردية مفتوحة: شاشة الورديات تعتمد الإغلاق قبل التقرير",
        )
        self.assertGreaterEqual(DailySaleItem.objects.count(), 200)
        # كل بند في يومية وإلا كانت الأيامية بلا تفصيل يُعرض في شاشة اليوميات.
        self.assertEqual(
            DailySaleItem.objects.filter(sale__isnull=True).count(), 0
        )
        self.assertGreaterEqual(
            SaleSessionItem.objects.filter(session__status=SaleSession.Status.CLOSED)
            .values("session_id")
            .distinct()
            .count(),
            40,
            "ورديات بلا بنود: شاشة الوردية تفتح فارغة",
        )

    def test_sales_carry_customers_discounts_and_card_settlements(self):
        """شاشة اليوميات تعرض العميل والخصم ورسوم البطاقة؛ لا يكفي أن تُملأ."""
        self.assertTrue(
            SaleSessionItem.objects.filter(group_no__isnull=False).exists(),
            "لا رقم مجموعة في أي بند: تجميع بنود الوردية لا يعمل",
        )
        self.assertTrue(
            SaleSessionItem.objects.exclude(discount_amount=Decimal("0")).exists(),
            "لا خصم واحد في البيانات: تسمية «خصم» تبقى بلا رقم",
        )
        carded = SaleSessionItem.objects.filter(payment_method="card")
        self.assertTrue(carded.exists(), "لا بيعة بالبطاقة: تسوية الرسوم بلا رقم")
        self.assertTrue(
            any(i.card_fee_amount for i in carded), "رسوم بطاقة صفرية في كل العمليات"
        )
        methods = set(DailySale.objects.exclude(transfer_amount=0).values_list("id", flat=True))
        self.assertTrue(methods, "لا تحويل بنكي: تقرير التحصيل ناقص")
        self.assertTrue(
            SaleSessionItem.objects.exclude(customer_name="").exists(),
            "لا عميل مسجّل: حقل العميل في المبيعات فارغ دائماً",
        )

    def test_builds_purchases_supplier_balances_and_stock(self):
        self.assertGreaterEqual(GoodsReceipt.objects.count(), 10)
        self.assertEqual(
            GoodsReceipt.objects.exclude(status=GoodsReceipt.Status.POSTED).count(),
            0,
            "سند استلام مسوّدة: المخزون لا يتحرك قبل الترحيل",
        )
        self.assertGreaterEqual(PurchaseItem.objects.count(), 50)
        self.assertTrue(
            LedgerEntry.objects.filter(entry_type=LedgerEntry.EntryType.PAYMENT).exists(),
            "لا دفعة للمورد: كشف حساب المورد لا يُختبر",
        )
        self.assertTrue(StockOpening.objects.exists(), "لا رصيد افتتاحي للمخزن الرئيسي")
        self.assertTrue(StockTransfer.objects.exists(), "لا تحويل بين المخزن والفرع")

    def test_builds_expenses_across_categories_branches_and_months(self):
        self.assertGreaterEqual(Expense.objects.count(), 30)
        self.assertGreaterEqual(
            Expense.objects.values("category_id").distinct().count(), 4
        )
        self.assertGreaterEqual(
            Expense.objects.values("branch_id").distinct().count(), 2
        )
        self.assertEqual(
            Expense.objects.filter(amount__lte=0).count(), 0, "مصاريف بصفر أو أقل"
        )

    def test_expenses_never_repeat_the_payroll_line(self):
        """المصاريف لا تحمل فئة «رواتب»: الرواتب بند مستقل، وتكرارها يقرِب
        صافي الربح مرتين — وهو أسوأ خطأ في تقرير أرباح."""
        salaries_expenses = [
            e for e in Expense.objects.select_related("category")
            if "راتب" in (e.category.name or "")
        ]
        self.assertEqual(
            salaries_expenses, [], "مصاريف بفئة رواتب تكرّر خط الرواتب في صافي الربح"
        )

    def test_builds_payroll_with_paid_runs_and_structures(self):
        self.assertGreaterEqual(SalaryStructure.objects.count(), 3)
        runs = list(PayrollRun.objects.all())
        self.assertGreaterEqual(len(runs), 1)
        for run in runs:
            self.assertEqual(
                run.status, PayrollRun.Status.PAID, f"كشف {run.month} غير مصروف"
            )
            self.assertIsNotNone(run.paid_at)
            self.assertTrue(run.payslips.exists())
        self.assertTrue(
            [p for p in Payslip.objects.all() if p.gross > 0],
            "كل إجمالي الراتب صفر: تقرير الرواتب بلا أرقام",
        )
        self.assertTrue(
            [p for p in Payslip.objects.all() if p.net_pay > 0],
            "كل الصافي صفر: قسيمة الراتب فارغة",
        )
        # راتب شهر كامل فيه بدلات وعمولة، لا راتب أساسي وحده.
        self.assertTrue(
            Payslip.objects.exclude(commission_amount=Decimal("0")).exists(),
            "لا عمولة في أي قسيمة: تقرير العمولات فارغ",
        )

    def test_builds_advances_that_are_approved_and_repaid(self):
        advances = list(SalaryAdvance.objects.all())
        self.assertGreaterEqual(len(advances), 2)
        for advance in advances:
            self.assertNotEqual(
                advance.status,
                SalaryAdvance.Status.PENDING,
                "سلفة بانتظار الموافقة: حالتها الأولى لا تُختبر أبداً",
            )
            self.assertGreater(advance.amount, 0)
        self.assertTrue(
            AdvanceInstallment.objects.exists(), "لا قسط سلفة: السلفة بلا أثر مالي"
        )
        self.assertTrue(
            SalaryAdvance.objects.filter(
                status=SalaryAdvance.Status.SETTLED
            ).exists(),
            "لا سلفة مسدَّدة: شاشة السلف لا تُختبر على حالتها الأخيرة",
        )

    def test_builds_partner_operations(self):
        self.assertGreaterEqual(PartnerOperation.objects.count(), 2)
        self.assertTrue(
            PartnerOperation.objects.filter(amount__gt=0).exists()
        )

    def test_builds_stock_adjustments_and_counts(self):
        """شاشة الجرد والتسوية بلا بيانات فارغة لا تُفتح ولا تُختبر."""
        self.assertTrue(StockAdjustment.objects.exists(), "لا تسوية مخزون")
        counts = list(StockCount.objects.all())
        self.assertGreaterEqual(len(counts), 1)
        for count in counts:
            self.assertTrue(count.items.exists(), f"جرد بلا بنود: {count.pk}")

    def test_posts_journal_entries_for_every_operational_source(self):
        sources = set(JournalEntry.objects.values_list("source", flat=True))
        self.assertIn(JournalEntry.Source.EXPENSE, sources)
        self.assertIn(JournalEntry.Source.PURCHASE, sources)
        self.assertTrue(
            len(sources) >= 3, f"مصادر القيود قليلة: {sources}"
        )
        # كل قيد متوازن، وإلا اختلّ ميزان المراجعة.
        for entry in JournalEntry.objects.prefetch_related("lines")[:400]:
            lines = list(entry.lines.all())
            debit = sum(l.debit for l in lines)
            credit = sum(l.credit for l in lines)
            self.assertAlmostEqual(
                float(debit), float(credit), places=2,
                msg=f"قيد غير متوازن {entry.pk}",
            )

    def test_books_contain_nothing_future_dated(self):
        """لا بيعة بتاريخ لم يأتِ بعد: تقرير الشهر الجاري يفترض واقعية."""
        today = timezone.localdate()
        self.assertEqual(DailySale.objects.filter(date__gt=today).count(), 0)
        self.assertEqual(Expense.objects.filter(date__gt=today).count(), 0)
        self.assertEqual(
            LedgerEntry.objects.filter(date__gt=today, entry_type=LedgerEntry.EntryType.PURCHASE).count(),
            0,
        )


class SeedStockIsConsistent(SeedShowcaseBase):
    def test_no_roll_goes_negative(self):
        """رصيد سالب موتوق: إن حدث فالبيانات مُزوّرة لا محاكاة."""
        worst = FabricRoll.objects.filter(remaining_yards__lt=0).order_by("remaining_yards")
        self.assertEqual(
            [r.pk for r in worst[:5]], [], "لفات رصيدها سالب"
        )

    def test_no_sale_movement_was_overdrawn(self):
        self.assertEqual(
            StockMovement.objects.filter(quantity__lt=0, balance_after__lt=0).count(),
            0,
        )

    def test_rolls_hold_exactly_what_was_delivered(self):
        """مجموع لفات كل (مخزن × قماش) = مجموع حركاته.

        هذا هو الفحص الذي كشف أن تقسيم سند 133.41 ياردة على لفتين كان يسجّل
        133.40: الفارق نصف قرش، لكنه كان يرفض بيعات في منتصف البيانات.
        """
        balances = {}
        for wh_id, fabric_id, total in (
            FabricRoll.objects.values_list("warehouse_id", "fabric_id")
            .annotate(t=Sum("remaining_yards"))
        ):
            balances[(wh_id, fabric_id)] = total
        for key, total in balances.items():
            moves = sum(
                m.quantity for m in StockMovement.objects.filter(
                    warehouse_id=key[0], fabric_id=key[1]
                )
            )
            self.assertAlmostEqual(
                float(total), float(moves), places=2,
                msg=f"رصيد اللفات لا يطابق حركاته في {key}",
            )

    def test_every_branch_sells_under_its_own_warehouse(self):
        for branch in Branch.objects.filter(is_active=True):
            sold = DailySaleItem.objects.filter(
                sale__branch=branch
            ).aggregate(t=Sum("yards"))["t"] or Decimal("0")
            self.assertGreater(
                sold, 0, f"الفرع {branch.code} بلا مبيعات: تقرير أداء الفروع فارغ"
            )

    def test_closing_stock_is_left_for_the_next_month(self):
        """إن نفد المخزون تماماً فلا معنى لقسم «المخزون» في التقرير."""
        total = FabricRoll.objects.aggregate(t=Sum("remaining_yards"))["t"] or 0
        sold = DailySaleItem.objects.aggregate(t=Sum("yards"))["t"] or 0
        self.assertGreater(
            total, sold * Decimal("0.15"),
            "لا رصيد ختامي: تقرير الشهر التالي يبدأ بلا بضاعة",
        )


class SeedReportsWork(SeedShowcaseBase):
    """ثلاثة أشهر لا شهران: زرّ «الفترة السابقة» يحتاج شهراً كاملاً خلفه.

    بشهرين فقط، تُعيد مقارنة الفترة السابقة في تقرير الربح والخسارة أصفاراً،
    فلا يُختبر مسار المقارنة ولا سهم التغيّر ولا الفروق.
    """

    months = 3

    def _pl(self, first: date, last: date):
        res = self.c.get(
            "/api/reports/profit-loss/",
            {"date_from": first.isoformat(), "date_to": last.isoformat()},
        )
        self.assertEqual(res.status_code, 200, res.content[:400])
        return res.data

    def _month_bounds(self, offset):
        first = add_months(month_start(self.ran_at), offset)
        last = first.replace(day=1)
        nxt = add_months(first, 1)
        last = nxt - timedelta(days=1)
        return first, last

    def test_profit_loss_has_profit_in_every_month(self):
        for offset in (0, 1):
            first, last = self._month_bounds(-offset)
            data = self._pl(first, last)
            totals = data["totals"]
            self.assertGreater(
                totals["total_sales"], 0, f"لا مبيعات في {first:%Y-%m}"
            )
            self.assertGreater(
                totals["net_profit"], 0, f"خسارة في {first:%Y-%m}"
            )
            self.assertGreater(totals["gross_profit"], 0, f"مجمل سالب في {first:%Y-%m}")
            self.assertGreater(totals["cogs"], 0, "تكلفة مبيعات صفر: مخزون بلا حركة")
            self.assertGreater(totals["expenses"], 0, "لا مصاريف: تقرير المصاريف فارغ")
            self.assertGreater(totals["salaries"], 0, "لا رواتب: تقرير الرواتب فارغ")
            self.assertGreater(totals["gross_margin_pct"], 0)
            self.assertGreater(totals["net_margin_pct"], 0)

    def test_profit_loss_compares_with_the_previous_period(self):
        """زرّ «الشهر السابق» في التقرير يجب أن يجد شهراً كاملاً خلفه."""
        first, last = self._month_bounds(-1)
        data = self._pl(first, last)
        self.assertIsNotNone(data.get("comparison"), "لا مقارنة فترة سابقة")
        self.assertIsNotNone(data["comparison"]["totals"])
        self.assertGreater(data["comparison"]["totals"]["total_sales"], 0)
        for key, value in data["change_pct"].items():
            self.assertIsInstance(value, (int, float), key)

    def test_profit_loss_stock_section_is_meaningful(self):
        first, last = self._month_bounds(-1)
        stock = self._pl(first, last)["stock"]
        self.assertGreater(stock["purchases"]["value"], 0)
        self.assertGreater(stock["closing"]["yards"], 0)
        self.assertGreater(stock["closing"]["value"], 0)
        self.assertGreater(
            stock["unsold_value"], 0, "قيمة البضاعة غير المباعة صفر أو سالبة"
        )

    def test_profit_loss_collection_rate_is_plausible(self):
        first, last = self._month_bounds(-1)
        data = self._pl(first, last)
        collection = data["collection"]
        self.assertAlmostEqual(
            collection["collected"], data["totals"]["total_sales"], places=1
        )
        self.assertGreater(collection["cash"], 0)
        self.assertGreaterEqual(len(data["branches"]), 2)
        self.assertGreaterEqual(len(data["daily"]), 10)

    def test_profit_loss_exports_to_excel(self):
        first, last = self._month_bounds(-1)
        res = self.c.get(
            "/api/reports/profit-loss/",
            {
                "date_from": first.isoformat(),
                "date_to": last.isoformat(),
                "export": "xlsx",
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertGreater(len(res.content), 5000)

    def test_trial_balance_balances(self):
        res = self.c.get("/api/reports/trial-balance/")
        self.assertEqual(res.status_code, 200)
        totals = res.data["totals"]
        self.assertAlmostEqual(totals["debit"], totals["credit"], places=1)

    def test_balance_sheet_balances(self):
        """كان ينهار بـTypeError على أي شركة رابحة."""
        res = self.c.get("/api/reports/balance-sheet/")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["balanced"], f"الميزانية غير متوازنة: {res.data}")

    def test_income_statement_and_profit_loss_agree_on_direction(self):
        """رقمان مختلفان بمقياسين، لكن لا يجوز أن يتناقضا.

        قائمة الدخل المحاسبية تُقيس الربح التشغيلي على أساس الإقرار (المخزون
        أصل)، وتقرير الربح والخسارة يقيسه على أساس تكلفة المبيعات. فالفرق بينهما
        طبيعي — والتناقض بينهما لا.
        """
        first, last = self._month_bounds(-1)
        res = self.c.get(
            "/api/reports/income-statement/",
            {"date_from": first.isoformat(), "date_to": last.isoformat()},
        )
        self.assertEqual(res.status_code, 200)
        statement = res.data["net_profit"]
        report = self._pl(first, last)["totals"]["net_profit"]
        self.assertGreater(statement, 0)
        self.assertGreater(report, 0)
        # الفارق كله من المخزون: القائمة تُبقي المشتريات أصلاً.
        self.assertGreater(statement, report)

    def test_dashboard_opens_with_numbers(self):
        res = self.c.get("/api/dashboard/summary/")
        self.assertEqual(res.status_code, 200)
        self.assertGreater(res.data["total_sales"], 0)
        self.assertTrue(res.data["chart_data"])
        self.assertTrue(res.data["top_fabrics"])
        self.assertGreaterEqual(res.data["branches_count"], 2)


class SeedNoResetAddsInsteadOfDestroying(SeedShowcaseBase):
    def test_no_reset_keeps_previous_sales(self):
        before = DailySale.objects.count()
        marker = DailySale.objects.order_by("pk").first()

        call_command(
            "seed_showcase",
            months=1,
            verbosity=0,
            random_seed=4242,
            no_reset=True,
        )

        self.assertTrue(
            DailySale.objects.filter(pk=marker.pk).exists(),
            "--no-reset محا البيانات رغم أنه لا يفترض أن يفعل",
        )
        self.assertGreater(DailySale.objects.count(), before - 1)

    def test_end_option_shifts_the_whole_window(self):
        target = add_months(month_start(self.ran_at), -5)
        call_command(
            "seed_showcase",
            months=1,
            verbosity=0,
            random_seed=99,
            end=f"{target:%Y-%m}",
        )
        first = month_start(target)
        last = add_months(first, 1) - timedelta(days=1)
        self.assertTrue(
            DailySale.objects.filter(date__gte=first, date__lte=last).exists(),
            "--end لم ينقل نافذة البيانات",
        )
        self.assertFalse(
            DailySale.objects.filter(date__gt=last).exists(),
            "بيانات خارج النافذة المطلوبة",
        )
