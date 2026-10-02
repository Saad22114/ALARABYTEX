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
from attendance.models import AttendancePolicy, AttendanceRecord
from attendance.services import is_working_day, recompute
from branches.models import Branch
from core.testsupport import authenticate_admin
from customers.models import Customer
from expenses.models import Expense
from machine_account.models import MachineCollection
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


def month_last_day(value: date) -> date:
    return add_months(value, 1) - timedelta(days=1)


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
        self._client = None

    @property
    def c(self) -> APIClient:
        """عميل بمدير، يُبنى عند أول طلب فقط.

        ``authenticate_admin`` ينشئ فرعاً معطّلاً، فلو بُني في ``setUp`` لأضاف
        فرعاً بعد تشغيل الأمر، فاشترط الاختبارات التي تعيد تشغيله أن تعيده على
        الحالة نفسها — وإلا اختلفت الأرقام لسبب لا علاقة له بالبذرة.
        """
        if self._client is None:
            self._client = APIClient()
            authenticate_admin(self._client)
        return self._client


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

    def test_gives_a_deactivated_branch_no_business(self):
        """فرع أوقفه صاحب النظام لا مبيعات له ولا مصاريف ولا مخزن.

        توليد بيانات لفرع مُعطَّل يجعل تقرير أداء الفروع يُظهر صفاً لفرع مغلق،
        وهو رقم يستدعي سؤالاً لا جواب له في البيانات.
        """
        dormant = Branch.objects.create(
            name="فرع متوقف", code="DORMANT", is_active=False
        )
        call_command(
            "seed_showcase", months=1, verbosity=0, random_seed=self.seed
        )

        self.assertTrue(Branch.objects.filter(pk=dormant.pk).exists(), "مسح الفرع")
        self.assertEqual(DailySale.objects.filter(branch=dormant).count(), 0)
        self.assertEqual(Expense.objects.filter(branch=dormant).count(), 0)
        self.assertEqual(SaleSession.objects.filter(branch=dormant).count(), 0)

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

    def test_settlement_accounts_get_collections_and_supplier_draws(self):
        """حسابا التسوية لا يُفتحان إلا ببيانات تُظهر الأمر كلّه.

        الطلب: من أي حساب خُصمت دفعة المورد. وهذا يُختبر من الجهتين:
        دفعة واردة تُنقص رصيد حساب الماكينة أو البنك، ودفعة مورد تخرج من
        أحدهما فيظهر المورد في **قسم** ذلك الحساب. والرصيد السالب خطأ
        مولِّد لا خطأ برنامج، ومع ذلك يُمنع.
        """
        self.assertGreaterEqual(
            MachineCollection.objects.count(),
            4,
            "لا دفعات تسوية واردة: شاشة حسابات التسوية تعرض مبيعات بلا وصول",
        )
        for account in ("machine", "bank"):
            self.assertTrue(
                MachineCollection.objects.filter(account=account).exists(),
                f"لا دفعة واردة على حساب {account}",
            )

        payments = LedgerEntry.objects.filter(
            entry_type=LedgerEntry.EntryType.PAYMENT
        )
        self.assertEqual(
            payments.filter(settlement_account="").count(),
            0,
            "دفعة بلا حساب خُصم منه: قيد يمرّ على الخادم بلا إجابة إلزامية",
        )
        drawn = payments.filter(
            settlement_account__in=LedgerEntry.SETTLEMENT_CHOICES
        )
        self.assertTrue(drawn.exists(), "لا دفعة مورد خُصمت من حساب تسوية")
        # كل دفعة خُصمت من حساب يجب أن تكون مرئية في قسم ذلك الحساب.
        for payment in drawn.select_related("settlement_movement"):
            self.assertIsNotNone(
                payment.settlement_movement,
                f"دفعة {payment.pk} بلا حركة تسوية: لا تظهر في القسم الذي خُصمت منها",
            )
            self.assertEqual(
                payment.settlement_movement.account, payment.settlement_account
            )
            # الحركة بقيمة موجبة: واردة من شركة البطاقة فتنقص رصيدها. لو
            # سُجّلت بالسالب — كما هي في دفتر المورد — لكان الرصيد قد زاد.
            self.assertEqual(
                payment.settlement_movement.amount, abs(payment.amount)
            )

        branches = list(Branch.objects.filter(is_active=True))
        for account in ("machine", "bank"):
            field = "card_amount" if account == "machine" else "transfer_amount"
            sales = DailySale.objects.filter(branch__in=branches).aggregate(
                t=Sum(field)
            )["t"] or Decimal("0")
            received = MachineCollection.objects.filter(
                account=account, branch__in=branches
            ).aggregate(t=Sum("amount"))["t"] or Decimal("0")
            # ``amount`` سالب في دفتر المورد، فنأخذ قيمته المطلقة عند طرحه من
            # المستلَم: الرصيد المتاح = ما باع − ما استقبل − ما أنفق منه.
            spent = abs(
                LedgerEntry.objects.filter(
                    entry_type=LedgerEntry.EntryType.PAYMENT,
                    settlement_account=account,
                ).aggregate(t=Sum("amount"))["t"]
                or Decimal("0")
            )
            self.assertGreaterEqual(
                sales - received - spent,
                Decimal("0"),
                f"رصيد حساب {account} سالب: أنفق منه المولِّد أكثر مما استقبل",
            )

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

    def test_builds_attendance_for_every_employee_on_every_working_day(self):
        """لكل موظفٍ في كل يومِ عملٍ سطر، والعطلةُ ليست يوماً ناقصاً.

        الفارقُ بين «بيانات حضور» و«موظفٍ له حضورُه»: سطرٌ لكل موظفٍ في
        كل يوم. ولو أُهمل الغائبُ بلا سطرٍ لَما عُدَّ في الملخّص أصلاً،
        لأنّ الملخّص يعدُّ السطور لا الناس.
        """
        policy = AttendancePolicy.load()
        self.assertTrue(policy.enabled, "سياسة الحضور معطّلة بعد البذرة")
        employees = list(Employee.objects.filter(is_active=True))
        self.assertTrue(employees, "لا موظفون نشطون")
        dates = set(AttendanceRecord.objects.values_list("date", flat=True))
        days = {day for day in dates if is_working_day(day, policy)}
        self.assertTrue(days, "لا سجلات حضور على الإطلاق")
        for employee in employees:
            for day in days:
                self.assertTrue(
                    AttendanceRecord.objects.filter(
                        employee=employee, date=day
                    ).exists(),
                    f"لا سطر حضور في {day}",
                )
        # الجمعة عطلةٌ في السياسة فلا سطر فيها: يومُ عملٍ بلا حضورٍ
        # يُحسب غياباً، والغيابُ في يومِ عطلة يُقرأ خطأً لا واقعة.
        fridays = sorted(
            {day for day in dates if day.weekday() == 4}
        )
        self.assertEqual(fridays, [], f"\u0633\u0637\u0631\u064f \u062d\u0636\u0648\u0631 \u0641\u064a \u064a\u0648\u0645\u0650 \u0639\u0637\u0644\u0629: {fridays}")

    def test_attendance_shows_every_status_the_table_can_hold(self):
        """لكل حالةٍ في اللائحة سطر: الجدولُ نصفُه ميت إن لم يُملأ.

        الانصرافُ المبكر والإضافي والتأخير والغياب والعذر: أيُّها غاب
        عن شهرين فلا تُختبر القاعدةُ التي تحسبه، وتبقى الشاشةُ تعرض
        دائماً صفراً دون أن يعلم أحد.
        """
        found = set(AttendanceRecord.objects.values_list("status", flat=True))
        for status in (
            AttendanceRecord.Status.ABSENT,
            AttendanceRecord.Status.EXCUSED,
            AttendanceRecord.Status.LATE,
        ):
            self.assertIn(status, found, f"لا سطر بحالة {status}")
        # «داخل الدوام» سطرٌ بلا خروج، ولا معنى للكلمة إلّا في يومه:
        # من لم يخرج منذ شهرين ليس داخل الدوام، والشاراةُ تكرّر الكذبة.
        if is_working_day(timezone.localdate(), AttendancePolicy.load()):
            self.assertIn(AttendanceRecord.Status.INSIDE, found)
        self.assertTrue(
            AttendanceRecord.objects.filter(
                early_leave_minutes__gt=0
            ).exists(),
            "لا انصراف مبكر",
        )
        self.assertTrue(
            AttendanceRecord.objects.filter(
                overtime_minutes__gt=0
            ).exists(),
            "لا ساعات إضافية",
        )
        self.assertTrue(
            AttendanceRecord.objects.exclude(note="").exists(),
            "لا ملاحظات على المبررات",
        )

    def test_attendance_never_writes_a_time_in_the_future(self):
        """لا خروجٌ بعد اللحظة الحالية.

        سطرٌ بخروجٍ في المستقبل لا يُقرأ كسجلِّ حضور، بل كدليلٍ على أنّ
        الأرقامَ زُروعت. والفرقُ بينهما لا يظهر في الجدول: كلتاهما نصٌّ
        ووقت، حتى يأتي من يستند عليه في خصمِ يومٍ أو إضافتِ ساعات.
        """
        now = timezone.now()
        for field in ("login_at", "logout_at"):
            self.assertEqual(
                AttendanceRecord.objects.filter(**{f"{field}__gt": now}).count(),
                0,
                f"{field} في المستقبل",
            )

    def test_attendance_numbers_are_derived_from_the_two_times(self):
        """أرقامُ السطر تُشتقّ من وقتيه، فلا تُنسخ من محضِ المصادفة.

        لو كُتبت جاهزةً لَما تأثّرت بتغيير السياسة: يموت اختبارُ
        الحساب في ``tests`` وحده، ويبقى ما يعرضه الجدول على حاله،
        ولا أحد يعلم أنّ الرقماً لم يعد يُشتقّ.
        """
        record = (
            AttendanceRecord.objects.filter(
                login_at__isnull=False,
                logout_at__isnull=False,
                late_minutes__gt=0,
            )
            .order_by("pk")
            .first()
        )
        self.assertIsNotNone(record, "لا سطر متأخّر بأرقامٍ محسوبة")
        policy = AttendancePolicy.load()
        policy.grace_minutes = 0
        before = record.late_minutes
        recompute(record, policy)
        self.assertGreaterEqual(record.late_minutes, before)
        self.assertTrue(
            AttendanceRecord.objects.filter(worked_minutes__gt=0).exists(),
            "لا ساعات عمل محسوبة",
        )

    def test_the_attendance_screens_answer_with_numbers(self):
        """الشاشةُ لا الجدول: الورقةُ والملخّص يجيبان بأرقامٍ لا بفراغ.

        الجدولُ ممتلئٌ وسطرُ الورقة فارغ: يحدث حين يُكتب الحضورُ بتاريخٍ
        آخر، أو حين يُجيب اليومُ بلا سطرٍ واحد. والاختبارُ يفتح
        المسارات كما تفتحها الشاشة.
        """
        self.assertEqual(
            self.c.get("/api/attendance/policy/").status_code, 200
        )
        busy_day = (
            AttendanceRecord.objects.filter(login_at__isnull=False)
            .order_by("-date")
            .values_list("date", flat=True)
            .first()
        )
        self.assertIsNotNone(busy_day, "لا يومَ مزروعٍ فيه دخول")
        # ورقةُ اليومُ تُجاب هي أيضاً: تفتحُها الشاشةُ في أيّ يومٍ من الأسبوع.
        self.assertEqual(
            self.c.get("/api/attendance/records/sheet/").status_code, 200
        )
        sheet = self.c.get(f"/api/attendance/records/sheet/?date={busy_day}")
        self.assertEqual(sheet.status_code, 200)
        self.assertTrue(sheet.data["rows"], "ورقة بلا سطور")
        self.assertTrue(
            any(row["login_at"] for row in sheet.data["rows"]),
            "ورقة بلا دخولٍ واحد",
        )
        summary = self.c.get("/api/attendance/records/summary/")
        self.assertEqual(summary.status_code, 200)
        counted = summary.data["summary"]
        self.assertGreater(
            counted["present"] + counted["absent"] + counted["excused"], 0
        )
        listed = self.c.get("/api/attendance/records/?limit=5")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(
            listed.data["count"], AttendanceRecord.objects.count()
        )

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
        # الراتبُ لا يسقط من القاعدة لئلا يُنسى: مسيّرٌ مصروفٌ بتاريخٍ
        # مستقبلي يُظهر في تقرير الشهر الجاري رواتبَ لم تُدفع، فيحسب
        # القارئ مصروفاً لم يقع. وهو أشدُّ خطأ في تقرير الأرباح لأن
        # الرقم فيه يبدو طبيعياً.
        self.assertEqual(
            [r for r in PayrollRun.objects.all() if r.paid_at and r.paid_at.date() > today],
            [],
            "مسيّر رواتب مصروفٌ بتاريخٍ لم يأتِ بعد",
        )
        self.assertFalse(
            PayrollRun.objects.filter(month__gt=today.replace(day=1)).exists(),
            "مسيّر رواتب لشهرٍ لم يبدأ",
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
        """كل شهرٍ كاملٍ رابح، والشهر الجاري يُفحص على أنه كذلك بلا أن يُطنَّش.

        الشهرُ الأخير قد يكون ناقصاً — نزرع ثلاثة أشهر فينتهي آخرها في
        منتصفه. وناقصاً لا تعني خاسراً: مصروفُ الشهر كاملٌ يُدفع في
        أوّله (إيجار، كهرباء) بينما مبيعاتُه ليومٍ واحد، فصافي ربحه
        بالسالب حتى لو كان ربحاً في شهره الكامل. والحكمُ على شهرٍ من
        أربعةِ أيامٍ كالحكم على شهرٍ كاملٍ لا يعني شيئاً — يُفحص على
        أنه بُني كما بُني غيره، لا على أنه ربح.
        """
        for offset in (0, 1):
            first, last = self._month_bounds(-offset)
            data = self._pl(first, last)
            totals = data["totals"]
            self.assertGreater(
                totals["total_sales"], 0, f"لا مبيعات في {first:%Y-%m}"
            )
            self.assertGreater(
                totals["gross_profit"], 0, f"مجمل سالب في {first:%Y-%m}"
            )
            self.assertGreater(totals["cogs"], 0, "تكلفة مبيعات صفر: مخزون بلا حركة")
            self.assertGreater(totals["gross_margin_pct"], 0)

            if month_last_day(first) > self.ran_at:
                # شهرٌ ما زال يجري: لا مسيّر رواتب له — الراتب مصروفُ
                # نهايةِ الشهر، فتسجيلُه الآن يعني رقماً بتاريخٍ لم يأتِ.
                self.assertEqual(
                    totals["salaries"], 0, "راتب شهرٍ لم ينتهِ: مسيّرٌ بتاريخٍ مستقبلي"
                )
                continue

            self.assertGreater(
                totals["net_profit"], 0, f"خسارة في شهرٍ كامل {first:%Y-%m}"
            )
            self.assertGreater(totals["expenses"], 0, "لا مصاريف: تقرير المصاريف فارغ")
            self.assertGreater(totals["salaries"], 0, "لا رواتب: تقرير الرواتب فارغ")
            self.assertGreater(totals["net_margin_pct"], 0)

    def test_profit_loss_compares_with_the_previous_period(self):
        """زرّ «الشهر السابق» في التقرير يجب أن يجد شهراً كاملاً خلفه."""
        first, last = self._month_bounds(-1)
        data = self._pl(first, last)
        self.assertIsNotNone(data.get("comparison"), "لا مقارنة فترة سابقة")
        self.assertIsNotNone(data["comparison"]["totals"])
        self.assertGreater(data["comparison"]["totals"]["total_sales"], 0)
        for key, value in data["comparison"]["change_pct"].items():
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
        """اللوحة تفتح بأرقام، ووقتها الافتراضي «اليوم».

        الافتراضي يومٌ واحد، والجمعة يوم راحة في هذه الشركة فلا مبيعات فيها.
        فلو اشترطنا رقماً في «اليوم» لسقط هذا الاختبار كل جمعة، ولو سقط
        أُصلح بأن نُفرغ اليوم من كل شيء — فصار مُصلَحاً على حساب معنى «اللوحة
        تحمل أرقاماً». فنثبّت الأرقام على شهرٍ مضمونٍ من أيام العمل، ونثبّت
        على «اليوم» وحده أن الشاشة تفتح ولا تنهار.
        """
        today = self.c.get("/api/dashboard/summary/")
        self.assertEqual(today.status_code, 200)
        self.assertIn("chart_data", today.data)

        res = self.c.get("/api/dashboard/summary/", {"period": "last_month"})
        self.assertEqual(res.status_code, 200)
        self.assertGreater(res.data["total_sales"], 0)
        self.assertTrue(res.data["chart_data"])
        self.assertTrue(res.data["top_fabrics"])
        self.assertGreaterEqual(res.data["branches_count"], 2)

    def test_the_weekly_holiday_carries_no_sales(self):
        """الجمعة يوم راحة: لا مبيعات فيها، واللقطة اليومية تُظهر صفراً لا خطأ.

        يوم الراحة ليس يوماً ناقص البيانات، بل يوم لا عمل فيه. فالموظف الذي
        يفتح اللوحة صباح الجمعة يجب أن يرى أصفاراً صحيّة، لا رقماً مفقوداً
        ولا خطأً يفزعه بأن حاسوبه خرب.
        """
        today = timezone.localdate()
        if today.weekday() != 4:
            self.skipTest("اليوم ليس الجمعة")
        self.assertFalse(DailySale.objects.filter(date=today).exists())
        res = self.c.get("/api/dashboard/summary/", {"period": "today"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["total_sales"], 0)
        row = next(
            (d for d in res.data["chart_data"] if d["date"] == today.isoformat()),
            None,
        )
        self.assertIsNotNone(row, "المصروفات اليومية تجعل اليوم سطراً في المنحنى")
        self.assertEqual(row["sales"], 0)


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

    def test_no_reset_does_not_duplicate_attendance(self):
        """\u0625\u0639\u0627\u062f\u0629\u064f \u0627\u0644\u062a\u0634\u063a\u064a\u0644 \u0644\u0627 \u062a\u064f\u0636\u0627\u0639\u0641 \u0633\u0637\u0648\u0631\u064e \u0627\u0644\u062d\u0636\u0648\u0631.

        \u0633\u0637\u0631\u064f \u0627\u0644\u062d\u0636\u0648\u0631 \u0648\u0627\u062d\u062f\u064c \u0644\u0643\u0644 \u0645\u0648\u0638\u0641\u064d \u0641\u064a \u0643\u0644 \u064a\u0648\u0645\u064d \u0628\u0642\u064a\u062f\u064d \u0641\u0631\u064a\u062f\u064c. \u0641\u0625\u0646 \u0643\u062a\u0628\u062a \u0627\u0644\u0628\u0630\u0631\u0629\u064f
        \u0633\u0637\u0631\u0627\u064b \u062c\u062f\u064a\u062f\u0627\u064b \u0641\u064a \u0643\u0644 \u062a\u0634\u063a\u064a\u0644\u060c \u0644\u0631\u0641\u0639 \u0627\u0644\u0642\u064a\u062f\u064f \u0641\u064a \u062b\u0627\u0646\u064a \u062a\u0634\u063a\u064a\u0644\u064d \u0644\u0640 ``--no-reset``\u060c
        \u0648\u0647\u0648 \u0641\u0634\u0644\u064c \u064a\u0642\u0639 \u0628\u0639\u062f \u0623\u0646 \u0637\u064f\u0644\u0628 \u0627\u0644\u0628\u064a\u0627\u0646\u0627\u062a \u0648\u0623\u064f\u062e\u0628\u0631\u062a \u0623\u0646\u0651\u0647\u0627 \u0623\u064f\u0636\u064a\u0641\u062a.
        """
        before = set(
            AttendanceRecord.objects.values_list("employee_id", "date")
        )
        self.assertTrue(before, "\u0644\u0627 \u0633\u0637\u0648\u0631 \u062d\u0636\u0648\u0631 \u0645\u0646 \u0627\u0644\u0623\u0635\u0644")

        call_command(
            "seed_showcase",
            months=self.months,
            verbosity=0,
            random_seed=4242,
            no_reset=True,
        )

        pairs = list(
            AttendanceRecord.objects.values_list("employee_id", "date")
        )
        self.assertTrue(
            before.issubset(pairs),
            "\u0633\u0637\u0631\u064f \u062d\u0636\u0648\u0631\u064d \u0627\u062e\u062a\u0641\u0649 \u0628\u0639\u062f \u0625\u0639\u0627\u062f\u0629 \u0627\u0644\u062a\u0634\u063a\u064a\u0644",
        )
        self.assertEqual(
            len(pairs), len(set(pairs)),
            "\u0633\u0637\u0648\u0631\u064d \u062d\u0636\u0648\u0631\u064d \u0645\u0643\u0631\u0651\u0631",
        )

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
