"""بيانات اختبار شاملة: تمسح كل المدخلات وتبني شهوراً كاملة من الحسابات.

الأمر يُبقي **الموظفين والفروع** (وحسابات الدخول والإعدادات والدليل المحاسبي)
ويمسح كل ما عداه، ثم يبني البيانات عبر **الخدمات الفعلية للنظام** لا بالإدراج
المباشر: `close_session` و`post_receipt` و`generate_run` و`create_partner_operation`.
بيانات الاختبار التي تمرّ هي التي تُختبِر المسار الحقيقي — ولو مرّت فالقواعد كلّها
(سقوط المخزون، سقف الخصم، الحد الأدنى لسعر البيع، ترحيل القيود) تعمل. الإدراج
المباشر لـ`DailySale` كان سيملأ الشاشة بأرقام لا تتفق مع حركات المخزون ولا
بالقيود: أرقام تعمل في التقارير وتسقط في العمليات.

الأشهر: ``--months`` شهراً متتالياً **ينتهي بالشهر الحالي**، والشهر الأخير يُولَّد
حتى اليوم فقط. فالأول شهر كامل برواتبه المدفوعة وصافيه، والثاني شهر كامل أيضاً
فتعمل مقارنة الفترة السابقة في تقرير الربح والخسارة، والأخير شهر جارٍ يُدخَل.
"""

import random
from calendar import monthrange
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.apps import apps
from django.core.management import call_command, CommandError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from core.management.base import ArabicSafeCommand
from core.request_state import suppress_audit

ZERO = Decimal("0")
CENTS = Decimal("0.01")

#: الجداول التي لا تُمسح أبداً: الموظفون والفروع (طلب المستخدم)، إضافةً إلى ما
#: بدونه ينهار النظام — حسابات الدخول ومجموعاتها وربطها، وإعدادات النظام، والدليل
#: المحاسبي (مبناه من الكود لا من البيانات، ومفتاح كل حساب يشتق من كوده).
KEEP_LABELS = frozenset(
    {
        "auth.User",
        "auth.Group",
        "sale_sessions.Employee",
        "branches.Branch",
        "appsettings.AppSettings",
        "accounting.Account",
    }
)

#: الجمعة عطلة في عُمان والسبت يوم عمل — ستة أيام أسبوعياً تعطي نحو 26 يوم عمل
#: شهرياً وهو نفسه ``working_days`` في هيكل الراتب، فيتّفق الحضور مع الرواتب.
FRIDAY = 4

#: أيام الشراء داخل الشهر؛ كل دفعة تغطي الطلب حتى الدفعة التالية (أو آخر الشهر).
PURCHASE_DAYS = (1, 11, 21)

DEMO_BRANCHES = [
    {"code": "MNH", "name": "الفرع الرئيسي", "city": "مسقط", "phone": "24123456"},
    {"code": "SIB", "name": "فرع السيب", "city": "السيب", "phone": "25567890"},
    {"code": "BWR", "name": "فرع بوشر", "city": "بوشر", "phone": "24561234"},
]

DEMO_EMPLOYEES = [
    {"name": "خالد بن سالم", "role": "ADMIN", "position": "مدير النظام", "base": 900, "commission": False},
    {"name": "سالم الحسني", "role": "SUPERVISOR", "position": "مشرف فرع", "base": 650, "commission": True},
    {"name": "مبارك الراشدي", "role": "SALES", "position": "مندوب مبيعات", "base": 320, "commission": True},
    {"name": "نوري عبد الله", "role": "SALES", "position": "مندوب مبيعات", "base": 300, "commission": True},
    {"name": "هند العامرية", "role": "ACCOUNTANT", "position": "محاسب", "base": 450, "commission": False},
    {"name": "سلمى المقبالية", "role": "VIEWER", "position": "أمين مخزن", "base": 280, "commission": False},
]

DEMO_SUPPLIERS = [
    {"name": "مؤسسة النسيج الحديث", "city": "مسقط", "phone": "97651122"},
    {"name": "شركة الشامل للأقمشة", "city": "السيب", "phone": "99654321"},
    {"name": "مصنع النور للنسج", "city": "صنعاء", "phone": "98001122"},
    {"name": "تجارة الأمل", "city": "بوشر", "phone": "99224455"},
    {"name": "مؤسسة الروضة للتجارة", "city": "نزوى", "phone": "99887766"},
    {"name": "شركة الأناقة للأقمشة", "city": "مسقط", "phone": "97331144"},
]

#: (الاسم، الكود، سعر الشراء بالريال، النوع، اللون)
DEMO_FABRICS = [
    ("قطن مطبوع", "F-101", "3.200", "قطن", "أزرق سماوي"),
    ("قطن سادة", "F-102", "2.850", "قطن", "أبيض"),
    ("قطن مبطن", "F-103", "4.100", "قطن", "رمادي"),
    ("حرير صناعي", "F-201", "7.400", "حرير", "أسود"),
    ("شيفون", "F-202", "5.600", "شيفون", "بيج"),
    ("ساتان", "F-203", "6.250", "ساتان", "أحمر"),
    ("جينز", "F-301", "5.900", "جينز", "دنيم"),
    ("كريب", "F-302", "4.750", "كريب", "زيتوني"),
    ("بوليستر", "F-303", "3.950", "بوليستر", "أخضر"),
    ("مودال", "F-304", "4.350", "مودال", "بنفسجي"),
    ("كانفاس", "F-401", "6.800", "كانفاس", "بيج"),
    ("بطانة داخلية", "F-402", "2.950", "بطانة", "كريمي"),
]

DEMO_CUSTOMERS = [
    ("سالم الرواحي", "98110001"),
    ("خالد المعشني", "98110002"),
    ("سعاد الحارثية", "98110003"),
    ("راشد الجابري", "98110004"),
    ("منى البادية", "98110005"),
    ("يوسف العبري", "98110006"),
    ("فاطمة الزدجالية", "98110007"),
    ("حمد الكندي", "98110008"),
    ("أمل السيابي", "98110009"),
    ("ناصر الفارسي", "98110010"),
    ("بدر الخروصي", "98110011"),
    ("رقية المهنائية", "98110012"),
    ("ماجد البلوشي", "98110013"),
    ("عائشة الشحي", "98110014"),
    ("طارق المقبالي", "98110015"),
]

DEMO_PARTNERS = [
    {"name": "سالم بن خميس", "share": 60},
    {"name": "ريم بنت سعيد", "share": 40},
]

#: (كود التصنيف، نص الوصف، أقل مبلغ، أعلى مبلغ، عدد المصروفات في الشهر).
#: تصنيف «رواتب» مستبعَد عمداً: الرواتب تُسجَّل في مسيّر الرواتب، ولو دُوّن
#: مصروفاً في هذا التصنيف لاحتُسبت الرواتب مرتين في صافي الربح.
EXPENSE_TEMPLATES = [
    ("RENT", "إيجار المحل — {month}", 280, 420, 1),
    ("ELECTRICITY", "فاتورة كهرباء", 45, 130, 1),
    ("WATER", "فاتورة ماء", 12, 38, 1),
    ("TRANSPORT", "نقل بضاعة", 8, 45, 4),
    ("MAINTENANCE", "صيانة ماكينة أو خياطة", 15, 90, 2),
    ("OPERATIONAL", "مصاريف تشغيلية", 10, 70, 5),
    ("OTHER_PURCHASES", "مشتريات متفرقة", 20, 110, 2),
    ("OTHER", "مصاريف أخرى", 5, 35, 3),
]

ADVANCE_REASONS = ["سلفة طارئة", "تجهيز", "دفعة أولى", "ظرف عائلي"]


def q2(value):
    return (value or ZERO).quantize(CENTS)


def money(value):
    return Decimal(str(value)).quantize(CENTS)


def add_months(value: date, months: int) -> date:
    total = value.year * 12 + (value.month - 1) + months
    return date(total // 12, total % 12 + 1, 1)


def month_last_day(value: date) -> date:
    return date(value.year, value.month, monthrange(value.year, value.month)[1])


def working_days(start: date, last: date):
    """أيام العمل من ``start`` إلى ``last`` شاملة، بلا جمعة."""
    out = []
    day = start
    while day <= last:
        if day.weekday() != FRIDAY:
            out.append(day)
        day += timedelta(days=1)
    return out


class Command(ArabicSafeCommand):
    help = (
        "يمسح كل المدخلات عدا الموظفين والفروع، ثم يبني بيانات اختبار كاملة: "
        "مبيعات ومخازن ومشتريات ومصاريف ورواتب وسلف وشركاء وحسابات شهر كامل وصافي أرباح"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--months",
            type=int,
            default=3,
            help="عدد الأشهر المتتالية المنتهية بالشهر الحالي (افتراضي 3)",
        )
        parser.add_argument(
            "--end",
            default="",
            help="آخر شهر تُولَّد بياناته بصيغة YYYY-MM (افتراضي: الشهر الحالي)",
        )
        parser.add_argument(
            "--no-reset",
            action="store_true",
            help="لا يمسح البيانات الحالية، بل يضيف الجديدة فقط",
        )
        parser.add_argument(
            "--random-seed",
            type=int,
            default=20260929,
            help="بذرة العشوائية، لتكرار النتيجة نفسها",
        )

    # ------------------------------------------------------------------
    # المسح
    # ------------------------------------------------------------------
    def _wipe(self, verbosity):
        from accounting.models import Account
        from appsettings.backup import _order, _through_labels

        removed = 0
        keep_models = {apps.get_model(label) for label in KEEP_LABELS}
        failed = {}
        with transaction.atomic():
            # جداول الربط أولاً: صفّ Employee_allowed_branches يمنع حذف الموظف
            # بـPROTECT، وترتيبه بعد النماذج يبتلعه ``except: pass`` فيبقى
            # الموظف وتُحاول إعادة إنشائه بالمعرّف نفسه.
            for label in _through_labels():
                through = apps.get_model(label)
                targets = {
                    f.related_model
                    for f in through._meta.concrete_fields
                    if f.is_relation and not f.auto_created
                }
                if targets and targets <= keep_models:
                    continue
                removed += through.objects.all().delete()[0]

            for label in reversed(_order()):
                if label in KEEP_LABELS:
                    continue
                try:
                    removed += apps.get_model(label).objects.all().delete()[0]
                except Exception as exc:  # جدول تحميه علاقة أو قيد
                    failed[label] = exc
                    continue

            # حساب المصروف يُبنى آلياً لكل تصنيف ومفتاح مصدره يحمل معرّف
            # التصنيف. إبقاؤه بعد حذف التصنيفات يترك حسابات يتيمة لا يشير إليها
            # شيء، ويتراكم مع كل تشغيل.
            removed += Account.objects.filter(source_key__startswith="expense_cat:").delete()[0]

            # المسح الجزئي أخطر من عدم المسح: يُعلِن الأمر أنه مسح، ثم يترك
            # صفوفاً من التشغيل السابق تختلط بالجديد، فتصير كل الأرقام 이후ها
            # غير قابلة للنسبة إلى أي شهر. فنتأكد أن كل جدول غير محفوظ صار
            # خالياً، وإن بقي شيء نوقف الأمر بدل أن نُكمل ونُخفي.
            leftovers = {}
            for label in reversed(_order()):
                if label in KEEP_LABELS:
                    continue
                model = apps.get_model(label)
                left = model.objects.count()
                if left:
                    leftovers[label] = left

        if leftovers:
            reasons = "\n".join(
                f"  - {label}: {left} صفاً"
                + (f" (السبب: {type(failed[label]).__name__})" if label in failed else "")
                for label, left in sorted(leftovers.items())
            )
            raise CommandError(
                "توقّف الأمر: المسح لم يكتمل، وبقيت بيانات من تشغيل سابق.\n"
                f"{reasons}\n"
                "إعادة التشغيل على قاعدة فيها بيانات محمية تُنتج أرقاماً مختلطة "
                "لا يمكن الاعتماد عليها. احذف السجلات المتبقية يدوياً أو شغّل "
                "الأمر على قاعدة نظيفة."
            )

        if verbosity >= 1:
            self.write_line(
                f"مُسح {removed} سجلاً — أُبقي الموظفون والفروع وحسابات الدخول والإعدادات والدليل المحاسبي",
                self.style.SUCCESS,
            )
        return removed

    # ------------------------------------------------------------------
    # البيانات المرجعية
    # ------------------------------------------------------------------
    def _ensure_branches(self):
        """يعيد الفروع النشطة وينشئ الناقص منها.

        الفروع من بيانات لا يمسّها الأمر إطلاقاً. لكن إن كانت القائمة اثنتين
        فقط، فبيانات اختبار على فرعين لا تُظهر تقرير أداء الفروع ولا مقارنة
        الفروع عمّا يفعلهما. فنضيف الناقص من الفروع التجريبية ولا نلمس القائم.

        ويعيد **النشطة فقط**: فرع أوقفه صاحب النظام لا يبيع ولا يُصرف عليه،
        وتوليد مبيعات له يعني ان/reviews تقرير أداء الفروع رقماً لفرع مغلق،
        ومخزناً له بلا حركة، وردية بيع في مكان لا تُفتح فيه ال��رضيات.
        """
        from branches.models import Branch

        created = []
        for row in DEMO_BRANCHES:
            _, made = Branch.objects.get_or_create(code=row["code"], defaults=row)
            if made:
                created.append(row["code"])
        if created:
            self.write_line(
                f"أضفنا الفروع الناقصة لبيانات الاختبار: {'، '.join(created)}",
                self.style.SUCCESS,
            )
        return list(Branch.objects.filter(is_active=True))

    def _ensure_employees(self, branches):
        """يعيد الموظفين وينشئهم إن لم يوجدوا، ويضمن أن لكل فرع موظفاً.

        تعديل الموظفين القائمين محدود ومقصود: من لا فرع له يُربط بفرع بالتناوب،
        وفرع بلا موظف يُربط بموظف قائم. بلا ذلك لا يمكن فتح وردية بيع في ذلك
        الفرع أصلاً، فيبقى بلا مبيعات ولا تُختبر تقاريره.
        """
        from sale_sessions.models import Employee

        employees = list(Employee.objects.all())
        known_names = {e.name for e in employees}
        made = []
        for row in DEMO_EMPLOYEES:
            # الموظفون بيانات تُحفظ، فلا نمسّ القائم منها ولا نغيّر هويته؛
            # ونضيف من نقص فقط، فالموظف الواحد في المنشأة يُنتج تقرير أداء
            # موظفين بصفٍّ واحد لا معنى له.
            if row["name"] in known_names:
                continue
            employee = Employee.objects.create(
                name=row["name"],
                role=row["role"],
                position=row["position"],
                base_salary=Decimal(str(row["base"])),
                commission_active=bool(row["commission"]),
                commission_percent=Decimal("2.50") if row["commission"] else ZERO,
                department="المبيعات" if row["role"] == "SALES" else "الإدارة",
                hire_date=date(2023, 1, 15),
            )
            employee.apply_role_preset(row["role"])
            employee.save(update_fields=["permissions", "hidden_sections", "updated_at"])
            employees.append(employee)
            made.append(employee)
        if made:
            self.write_line(
                f"أضفنا {len(made)} موظفاً لبيانات الاختبار "
                f"(الموظفون القائمون لم يُمسّوا)",
                self.style.SUCCESS,
            )

        employees.extend(self._ensure_login_employees(Employee, branches))

        for index, employee in enumerate(employees):
            if employee.branch_id is None and branches:
                employee.branch = branches[index % len(branches)]
                employee.save(update_fields=["branch", "updated_at"])

        for branch in branches:
            if any(e.branch_id == branch.pk for e in employees):
                continue
            employees[0].branch = branch
            employees[0].save(update_fields=["branch", "updated_at"])
            self.write_line(
                f"تنبيه: ربطنا الموظف «{employees[0].name}» بفرع «{branch.name}» لأن الفرع كان بلا موظف",
                self.style.WARNING,
            )

        # كل موظف يرى كل الفروع: وإلا رأى كلٌّ فرعه وحده، فلم يظهر في التقارير
        # إلا جزء من البيانات، وطُنّ أن الباقي مفقود.
        for employee in employees:
            employee.allowed_branches.set(branches)
        return employees

    def _ensure_login_employees(self, Employee, branches):
        """يربط كل حساب دخول بموظف، ويمنع «تسجيل الدخول ثم لا شيء».

        النظام يقيس الصلاحيات عبر ``Employee`` لا عبر ``auth.User``، فحساب
        بلا موظف يدخل الموقع ويرى شاشة فارغة أو خطأ 403 في كل تقرير — وهو
        أسوأ ما يمكن أن会遇到ه من يفتح بيانات اختبار.
        """
        from django.contrib.auth import get_user_model

        made = []
        for user in get_user_model().objects.filter(is_active=True).order_by("id"):
            if Employee.objects.filter(user=user).exists():
                continue
            employee = Employee(
                name=(user.get_full_name() or user.get_username())[:150],
                branch=branches[0] if branches else None,
                user=user,
                role=Employee.Role.ADMIN,
                is_active=True,
                position="مدير النظام",
                department="الإدارة",
                hire_date=date(2023, 1, 15),
            )
            employee.apply_role_preset(Employee.Role.ADMIN)
            employee.save()
            made.append(employee)
            self.write_line(
                f"ربطنا حساب الدخول «{user.get_username()}» بموظف بصلاحية مدير "
                f"كيتمكّن من تصفّح البيانات",
                self.style.SUCCESS,
            )
        return made

    def _staff_by_branch(self, branches, employees):
        out = {branch.pk: [e for e in employees if e.branch_id == branch.pk] for branch in branches}
        for branch in branches:
            if not out[branch.pk]:
                out[branch.pk] = list(employees)
        return out

    def _ensure_salary_structures(self, employees, start):
        from payroll.models import SalaryStructure

        made = 0
        for employee in employees:
            if SalaryStructure.objects.filter(employee=employee).exists():
                continue
            base = employee.base_salary or Decimal("300")
            SalaryStructure.objects.create(
                employee=employee,
                base_salary=base,
                housing_allowance=Decimal("50") if base >= 400 else ZERO,
                transport_allowance=Decimal("30") if base >= 300 else ZERO,
                other_allowance=ZERO,
                overtime_hour_rate=q2(base / Decimal("26") / Decimal("8")),
                working_days=Decimal("26"),
                daily_work_hours=Decimal("9"),
                effective_from=start,
                notes="هيكل راتب تجريبي",
            )
            made += 1
        return made

    def _ensure_suppliers(self):
        from suppliers.models import Supplier

        for row in DEMO_SUPPLIERS:
            defaults = {k: v for k, v in row.items() if k != "name"}
            defaults["country"] = "عمان"
            Supplier.objects.get_or_create(name=row["name"], defaults=defaults)
        return list(Supplier.objects.all())

    def _ensure_fabrics(self, suppliers):
        from suppliers.models import Fabric

        for index, (name, code, cost, kind, color) in enumerate(DEMO_FABRICS):
            purchase = Decimal(cost)
            Fabric.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "supplier": suppliers[index % len(suppliers)] if suppliers else None,
                    "fabric_type": kind,
                    "color": color,
                    "unit": Fabric.Unit.YARD,
                    "composition": f"{kind} 100%",
                    "width_cm": Decimal("150"),
                    "weight_gsm": Decimal("180") if kind == "قطن" else Decimal("140"),
                    "origin": "عمان" if index % 2 else "الهند",
                    "purchase_price": purchase,
                    "sale_price_yard": q2(purchase * Decimal("1.35")),
                    "piece_price": q2(purchase * Decimal("3.5")),
                    "min_sale_yard": q2(purchase * Decimal("1.10")),
                    "yards_per_roll": Decimal("50"),
                    "min_stock": Decimal("120"),
                    "description": f"{name} — {color}",
                },
            )
        return list(Fabric.objects.all())

    def _ensure_branch_prices(self, branches, fabrics):
        """سعر بيع لكل قماش في كل فرع — بعضها أعلى وبعضها أدنى.

        وجود سعر في الفروع يجعل التقارير تُظهر فروقاً حقيقية بدل سعر واحد مكرر،
        وهو ما تفعله محلات الأقمشة فعلاً.
        """
        from branches.models import FabricBranchPrice

        rng = random.Random(7)
        for branch in branches:
            for fabric in fabrics:
                factor = Decimal(str(round(rng.uniform(0.97, 1.06), 4)))
                price = q2(fabric.sale_price_yard * factor)
                FabricBranchPrice.objects.update_or_create(
                    branch=branch,
                    fabric=fabric,
                    defaults={
                        "sale_price_yard": price,
                        "min_sale_yard": q2(price * Decimal("0.92")),
                        "piece_price": q2(price * Decimal("3.5")),
                    },
                )

    def _ensure_warehouses(self, branches):
        from warehouses.models import Warehouse

        main, _ = Warehouse.objects.get_or_create(
            code="WH-MAIN",
            defaults={
                "name": "المخزن الرئيسي",
                "location": "المنطقة الصناعية — مسقط",
                "manager_name": "سلمى المقبالية",
                "phone": "24110000",
            },
        )
        return main, {branch.pk: Warehouse.for_branch(branch) for branch in branches}

    def _ensure_customers(self, branches):
        from customers.models import Customer

        for index, (name, phone) in enumerate(DEMO_CUSTOMERS):
            Customer.objects.get_or_create(
                phone=phone,
                defaults={
                    "name": name,
                    "branch": branches[index % len(branches)] if branches else None,
                    "address": "مسقط",
                },
            )
        return list(Customer.objects.all())

    def _ensure_partners(self):
        from partners.models import Partner

        for row in DEMO_PARTNERS:
            Partner.objects.get_or_create(
                name=row["name"],
                defaults={"share_percent": Decimal(str(row["share"]))},
            )
        return list(Partner.objects.all())

    def _ensure_settings(self):
        """يملأ الإعدادات الصفرية بقيمة واقعية، ولا يمسّ ما ضبطه صاحب النظام.

        رسوم البطاقة ونسبة الحد الأدنى للبيع وأقصى خصم أهم ما في هذه الشاشة:
        المنشأة الجديدة تجدها كلها صفراً. ومعها صفر، لا تُحسب رسوم بطاقة ولا
        يُختبر سقف الخصم ولا يُرفض بيع تحت الحد الأدنى — أي أن أهم قواعد البيع
        تبقى غير مجرّبة في بيانات الاختبار. فنضبط الصفر فقط ونقول ما ضبطناه.
        """
        from appsettings.models import AppSettings

        conf = AppSettings.load()
        wanted = {
            "card_credit_fee_percent": Decimal("1.800"),
            "card_debit_fee_percent": Decimal("0.500"),
            "min_sale_percent": Decimal("15.00"),
        }
        changed = []
        for field, value in wanted.items():
            if getattr(conf, field) in (None, ZERO):
                setattr(conf, field, value)
                changed.append(f"{conf._meta.get_field(field).verbose_name}={value}")
        if changed:
            conf.save()
            self.write_line(
                f"ضبطنا إعدادات كانت صفراً لبيانات الاختبار: {'، '.join(changed)}",
                self.style.SUCCESS,
            )
        return conf

    # ------------------------------------------------------------------
    # التخطيط قبل الكتابة
    # ------------------------------------------------------------------
    def _plan_month(self, rng, month_start, last_day, branches, staff, fabrics, customers):
        """يخطّط ورديات الشهر كاملاً قبل إنشائها.

        التخطيط المسبق ليس ترفاً: مشتريات الشهر تُحسب من **الاحتياج المخطط**،
        فلا تصل بيعة إلى فرع رصيد قماشه صفر — وهو ما كان يعنيell's
        ``رصيد المخزن لا يكفي`` في منتصف البيانات التجريبية بدل نهايتها.
        """
        plan = {}
        for branch in branches:
            pool = staff.get(branch.pk) or list(staff.values())[0]
            for day in working_days(month_start, last_day):
                if rng.random() < 0.06:
                    continue  # يوم عطلة أو إجازة
                sessions = []
                for _ in range(1 if rng.random() < 0.75 else 2):
                    items = [
                        {
                            "fabric": rng.choice(fabrics),
                            "yards": Decimal(str(round(rng.uniform(8, 70), 2))),
                        }
                        for _ in range(rng.randint(3, 7))
                    ]
                    sessions.append(
                        {
                            "employee": rng.choice(pool),
                            "items": items,
                            "customer": rng.choice(customers) if rng.random() < 0.5 else None,
                        }
                    )
                manual = None
                if rng.random() < 0.12:
                    total = money(rng.uniform(120, 600))
                    cash = q2(total * Decimal("0.6"))
                    transfer = q2(total * Decimal("0.25"))
                    manual = {
                        "cash": cash,
                        "transfer": transfer,
                        "card": q2(total - cash - transfer),
                    }
                plan.setdefault(day, []).append(
                    {"branch": branch, "sessions": sessions, "manual": manual}
                )
        return plan

    @staticmethod
    def _demand_curve(plan):
        """[(فرع, قماش)] -> [(تاريخ, ياردات مطلوبة حتى ذلك التاريخ)] تصاعدية.

        منها يُشتق حجم كل دفعة شراء: ما لم يُشترَ قبل تاريخ الدفعة يجب أن
        يساوي الطلب المتراكم حتى تاريخ الدفعة التالية — أو آخر الشهر.
        """
        buckets = {}
        for day, entries in sorted(plan.items()):
            for entry in entries:
                for session in entry["sessions"]:
                    for item in session["items"]:
                        key = (entry["branch"].pk, item["fabric"].pk)
                        buckets.setdefault(key, []).append((day, item["yards"]))
        curves = {}
        for key, pairs in buckets.items():
            pairs.sort(key=lambda pair: pair[0])
            total = ZERO
            curve = []
            for day, yards in pairs:
                total += yards
                curve.append((day, total))
            curves[key] = curve
        return curves

    # ------------------------------------------------------------------
    # الكتابة: المشتريات
    # ------------------------------------------------------------------
    def _post_purchase(self, rng, day, branch, needs, fabrics_by_id, suppliers, owed):
        """سند شراء لمورّد، ثم سند استلام يورّد الكميات إلى مخزن الفرع.

        ``create_purchase_receipts`` هو نفسه المستدعى من شاشة الموردين، فيُبنى
        الرصيد الحقيقي (لفات وحركات مخزون) ويُرحَّل السند — لا أرقام مصطنعة.
        """
        from accounting.services import post_supplier_entry
        from suppliers.models import LedgerEntry, PurchaseItem
        from warehouses.services import create_purchase_receipts

        wanted = [
            fabrics_by_id[fid]
            for (branch_id, fid), yards in needs.items()
            if branch_id == branch.pk and yards > 0
        ]
        if not wanted:
            return 0
        made = 0
        pool = rng.sample(list(suppliers), min(len(suppliers), rng.randint(2, 3)))
        for index, supplier in enumerate(pool):
            # الفاتورة تغطّي عدة أقمشة: نقسم القائمة على الموردين كما في الواقع
            chunk = wanted[index :: len(pool)]
            rows = []
            total = ZERO
            for fabric in chunk:
                yards = needs[(branch.pk, fabric.pk)]
                if yards <= 0:
                    continue
                jitter = Decimal(str(round(rng.uniform(0.97, 1.05), 4)))
                unit_price = q2((fabric.purchase_price or Decimal("3")) * jitter)
                line_total = q2(yards * unit_price)
                rolls = int(yards / (fabric.yards_per_roll or Decimal("50"))) or 1
                rows.append((fabric, yards, rolls, unit_price, line_total))
                total += line_total
            if not rows:
                continue
            entry = LedgerEntry.objects.create(
                supplier=supplier,
                date=day,
                entry_type=LedgerEntry.EntryType.PURCHASE,
                amount=total,
                description=f"شراء قماش — {branch.name}",
                receipt_no=f"INV-{day:%Y%m%d}-{branch.code}-{supplier.pk:02d}",
                branch=branch,
            )
            for fabric, yards, rolls, unit_price, line_total in rows:
                PurchaseItem.objects.create(
                    entry=entry,
                    fabric=fabric,
                    quantity_yards=yards,
                    rolls=Decimal(rolls),
                    unit_price=unit_price,
                    total=line_total,
                    branch=branch,
                )
            create_purchase_receipts(entry, date=day)
            post_supplier_entry(entry)
            owed[supplier.pk] = owed.get(supplier.pk, ZERO) + total
            made += 1
        return made

    def _pay_suppliers(self, rng, day, suppliers, owed):
        from accounting.services import post_supplier_entry
        from suppliers.models import LedgerEntry

        made = 0
        for supplier in suppliers:
            balance = owed.get(supplier.pk, ZERO)
            if balance <= ZERO or rng.random() < 0.25:
                continue
            pay = q2(balance * Decimal(str(round(rng.uniform(0.5, 0.95), 3))))
            method = rng.choice(
                [LedgerEntry.PaymentMethod.CASH, LedgerEntry.PaymentMethod.BANK]
            )
            entry = LedgerEntry.objects.create(
                supplier=supplier,
                date=day,
                entry_type=LedgerEntry.EntryType.PAYMENT,
                amount=-pay,
                description="دفعة للمورد",
                receipt_no=f"RC-{day:%Y%m%d}-{supplier.pk:02d}",
                payment_method=method,
                bank_reference=(
                    f"TR{rng.randint(100000, 999999)}"
                    if method == LedgerEntry.PaymentMethod.BANK
                    else ""
                ),
                receiver_name=(
                    "أمين الصندوق" if method == LedgerEntry.PaymentMethod.CASH else ""
                ),
            )
            post_supplier_entry(entry)
            owed[supplier.pk] = balance - pay
            made += 1
        return made

    # ------------------------------------------------------------------
    # الكتابة: المخزون
    # ------------------------------------------------------------------
    def _open_main_warehouse(self, rng, when, main_warehouse, fabrics):
        from warehouses.models import DocumentSequence, StockOpening, StockOpeningItem
        from warehouses.services import post_opening

        # ``post_opening`` يرفض رصيداً افتتاحياً مكرّراً للقماش نفسه في المخزن
        # نفسه، فيسقط أي تشغيل ثانٍ بـ--no-reset. 그래서 الرصيد الافتتاحي
        # يُكتب مرّة واحدة لكل مخزن: هو لقطة بداية، لا حركة متكرّرة.
        already = StockOpeningItem.objects.filter(
            opening__warehouse=main_warehouse
        ).values_list("fabric_id", flat=True)
        pending = [f for f in fabrics if f.pk not in set(already)]
        if not pending:
            self.write_line(
                "المخزن الرئيسي له رصيد افتتاحي سابق: لم نكرّره",
                self.style.WARNING,
            )
            return None

        opening = StockOpening.objects.create(
            number=DocumentSequence.next_number("OP"),
            warehouse=main_warehouse,
            date=when,
            notes="رصيد افتتاحي للمخزن الرئيسي",
        )
        for fabric in pending:
            yards = Decimal(str(round(rng.uniform(150, 400), 2)))
            StockOpeningItem.objects.create(
                opening=opening,
                fabric=fabric,
                yards=yards,
                rolls_count=max(1, int(yards / (fabric.yards_per_roll or Decimal("50")))),
                unit_price=fabric.purchase_price,
            )
        post_opening(opening)
        return opening

    def _transfer_to_branch(self, rng, day, main_warehouse, branch_warehouse, fabrics):
        from warehouses.models import DocumentSequence, StockTransfer, StockTransferItem
        from warehouses.services import complete_transfer

        transfer = StockTransfer.objects.create(
            number=DocumentSequence.next_number("TR"),
            from_warehouse=main_warehouse,
            to_warehouse=branch_warehouse,
            date=day,
            status=StockTransfer.Status.APPROVED,
            requested_by="أمين المخزن الرئيسي",
            approved_by="المدير",
            notes="توريد من المخزن الرئيسي إلى الفرع",
        )
        for fabric in rng.sample(list(fabrics), 3):
            StockTransferItem.objects.create(
                transfer=transfer,
                fabric=fabric,
                yards=Decimal(str(round(rng.uniform(60, 150), 2))),
                rolls_count=1,
                quantity_mode=StockTransferItem.QuantityMode.YARD,
            )
        try:
            complete_transfer(transfer)
        except Exception:
            # القماش المختار قد يكون مستنفداً؛ التحويل مكمل اختياري في بيانات
            # الاختبار، وفشله لا يعني أن مسار التحويل معطوب.
            return None
        return transfer

    def _stock_adjustment(self, rng, day, warehouse, fabrics):
        from warehouses.models import DocumentSequence, StockAdjustment, StockAdjustmentItem
        from warehouses.services import apply_adjustment

        adjustment = StockAdjustment.objects.create(
            number=DocumentSequence.next_number("ADJ"),
            warehouse=warehouse,
            date=day,
            reason=StockAdjustment.Reason.DAMAGE,
            direction=StockAdjustment.Direction.OUT,
            notes="تلف أثناء القص",
        )
        for fabric in rng.sample(list(fabrics), 2):
            StockAdjustmentItem.objects.create(
                adjustment=adjustment,
                fabric=fabric,
                yards=Decimal(str(round(rng.uniform(2, 9), 2))),
                rolls_count=1,
            )
        try:
            apply_adjustment(adjustment)
            return adjustment
        except Exception:
            return None

    def _stock_count(self, rng, day, warehouse):
        """جرد دوري: لقطة للرصيد الدفتري، عدّ فعلي بفروق صغيرة، ثم نشر."""
        from warehouses.models import DocumentSequence, StockCount
        from warehouses.services import build_count_snapshot, post_count

        count = StockCount.objects.create(
            number=DocumentSequence.next_number("CNT"),
            warehouse=warehouse,
            date=day,
            notes="جرد دوري",
        )
        build_count_snapshot(count)
        for item in count.items.all():
            if item.system_yards <= 0:
                continue
            # الفرق صغير وناقص غالباً، كما في جرد حقيقي
            drift = Decimal(str(round(rng.uniform(-0.03, 0.0), 4)))
            item.counted_yards = q2(item.system_yards * (Decimal("1") + drift))
            item.save(update_fields=["counted_yards", "updated_at"])
        post_count(count)
        return count

    # ------------------------------------------------------------------
    # الكتابة: المبيعات
    # ------------------------------------------------------------------
    def _run_day_sales(self, rng, day, entries, staff):
        from sale_sessions.models import SaleSession
        from sale_sessions.serializers import SaleSessionItemCreateSerializer
        from sale_sessions.services import (
            close_session,
            create_manual_session,
            stamp_session_creation,
        )

        made = 0
        for entry in entries:
            branch = entry["branch"]
            if entry["manual"]:
                create_manual_session(
                    employee=rng.choice(staff.get(branch.pk) or list(staff.values())[0]),
                    branch=branch,
                    sale_date=day,
                    cash=entry["manual"]["cash"],
                    transfer=entry["manual"]["transfer"],
                    card=entry["manual"]["card"],
                    notes="وردية يومية مُدخلة يدوياً",
                )
                made += 1

            for spec in entry["sessions"]:
                # ``next_sale_group_no`` يطلب قفل الصف بـ``select_for_update``،
                # فيلزم معاملة — تماماً كما تفعل شاشة البيع.
                with transaction.atomic():
                    session = SaleSession.objects.create(
                        employee=spec["employee"],
                        branch=branch,
                        session_date=day,
                        status=SaleSession.Status.OPEN,
                    )
                    stamp_session_creation(session, day)
                    customer = spec["customer"]
                    for item in spec["items"]:
                        fabric = item["fabric"]
                        payment = rng.choices(
                            ["cash", "transfer", "card"], weights=[55, 25, 20]
                        )[0]
                        payload = {
                            "fabric": fabric.pk,
                            "sale_type": "yard",
                            "quantity": item["yards"],
                            "payment_method": payment,
                        }
                        if payment == "card":
                            payload["card_type"] = rng.choice(["credit", "debit"])
                        if customer is not None:
                            payload["customer_name"] = customer.name
                            payload["customer_phone"] = customer.phone or ""
                        discount = self._discount(rng, branch, fabric, item["yards"])
                        if discount > ZERO:
                            payload["discount_amount"] = discount
                        serializer = SaleSessionItemCreateSerializer(
                            data=payload, context={"session": session}
                        )
                        if not serializer.is_valid():
                            # رفض المُسلسل يعني أن قاعدة بيع في الإعدادات تمنع
                            # هذه البيعة. البند يُتخطّى ويُعلَن، ولا يُسقط الأمر.
                            self.write_line(
                                f"تخطّينا بند {fabric.name} بتاريخ {day}: "
                                f"{serializer.errors}",
                                self.style.WARNING,
                            )
                            continue
                        serializer.save()
                    close_session(session)
                made += 1
        return made

    def _discount(self, rng, branch, fabric, yards):
        """خصم واقعي لا يخالف سقف النسبة ولا حدّ أدنى سعر القطعة.

        الخصم هنا ليس تجميلَ بيانات: لو تجاوز سقف ``discount_max_percent`` أو
        أنزل سعرَ القطعة تحت تكلفة الشراء × المضاعف، رفضه مُسلسل البيع،
        ونترك بنداً بلا بيع وسط أرقام لا تفحصها يد. فنحسب الخصم داخل الحدّين
        ونستعمل قيمة عشوائية تحته.
        """
        from appsettings.models import AppSettings

        if rng.random() >= 0.18:
            return ZERO
        conf = AppSettings.load()
        unit_price = self._sale_price(branch, fabric)
        line = q2(yards * unit_price)
        if line <= ZERO:
            return ZERO

        cap = line * conf.discount_max_percent / Decimal("100")
        multiplier = conf.min_piece_price_multiplier
        purchase = fabric.purchase_price or ZERO
        if multiplier > ZERO and purchase > ZERO:
            # أقل سعر ياردة يمرّ: لا بدّ أن يبقى فوق التكلفة × المضاعف.
            floor = q2(yards * purchase * multiplier)
            cap = min(cap, line - floor)
        if cap <= ZERO:
            return ZERO
        return q2(cap * Decimal(str(round(rng.uniform(0, 1), 3))))

    @staticmethod
    def _sale_price(branch, fabric):
        from branches.models import FabricBranchPrice

        row = FabricBranchPrice.objects.filter(branch=branch, fabric=fabric).first()
        return row.sale_price_yard if row else fabric.sale_price_yard

    # ------------------------------------------------------------------
    # الكتابة: المصاريف والشركاء والسلف والرواتب
    # ------------------------------------------------------------------
    def _make_expenses(self, rng, month_start, last_day, branches, categories):
        from accounting.services import post_expense
        from expenses.models import Expense, ExpenseBudget

        made = budgets = 0
        month_label = f"{month_start:%B %Y}"
        span = (last_day - month_start).days
        for branch in branches:
            for code, template, low, high, per_month in EXPENSE_TEMPLATES:
                category = categories.get(code)
                if category is None:
                    continue
                total = ZERO
                for _ in range(per_month):
                    expense = Expense.objects.create(
                        branch=branch,
                        category=category,
                        date=month_start + timedelta(days=rng.randrange(0, span + 1)),
                        amount=money(rng.uniform(low, high)),
                        payment_method=rng.choices(
                            ["cash", "transfer", "card"], weights=[50, 40, 10]
                        )[0],
                        description=template.format(month=month_label),
                        notes="مصروف تجريبي",
                    )
                    post_expense(expense)
                    total += expense.amount
                    made += 1
                # ميزانية أعلى من الفعلي قليلاً، فيظهر الفارق في شاشة الميزانيات
                ExpenseBudget.objects.get_or_create(
                    branch=branch,
                    category=category,
                    month=month_start,
                    defaults={"amount": q2(total * Decimal("1.15"))},
                )
                budgets += 1
        return made, budgets

    def _make_advances(self, rng, day, employees):
        from payroll.models import AdvanceInstallment, SalaryAdvance
        from payroll.services import approve_advance, repay_advance

        made = 0
        for employee in rng.sample(employees, min(len(employees), rng.randint(1, 2))):
            approve_advance(
                SalaryAdvance.objects.create(
                    employee=employee,
                    branch=employee.branch,
                    amount=money(rng.uniform(60, 250)),
                    date=day,
                    method=rng.choice(
                        [SalaryAdvance.Method.CASH, SalaryAdvance.Method.TRANSFER]
                    ),
                    status=SalaryAdvance.Status.PENDING,
                    reason=rng.choice(ADVANCE_REASONS),
                    notes="سلفة تجريبية",
                )
            )
            made += 1
        for advance in SalaryAdvance.objects.filter(
            status=SalaryAdvance.Status.APPROVED
        )[:2]:
            if advance.remaining_amount <= 0 or rng.random() < 0.5:
                continue
            repay_advance(
                advance,
                q2(advance.remaining_amount * Decimal("0.5")),
                method=AdvanceInstallment.Method.CASH,
                paid_on=day,
            )
            made += 1
        return made

    def _make_payroll(self, month_start, last_day_of_month):
        """مسيّر رواتب الشهر الكامل: إنشاء ثم اعتماد ثم صرف."""
        from payroll.models import PayrollRun
        from payroll.services import approve_run, generate_run, pay_run

        if PayrollRun.objects.filter(month=month_start).exists():
            return None
        run = generate_run(month_start)
        if not run.payslips.exists():
            run.delete()
            return None
        approve_run(run)
        pay_run(
            run,
            payment_method="cash",
            paid_at=timezone.make_aware(
                datetime.combine(last_day_of_month, datetime.min.time()).replace(hour=18)
            ),
        )
        return run

    def _make_partner_ops(self, rng, day, partners):
        from accounting.services import post_partner_operation
        from partners.models import PartnerOperation
        from partners.services import create_partner_operation

        made = 0
        for partner in partners:
            if rng.random() < 0.5:
                continue
            operation = create_partner_operation(
                partner=partner,
                date=day,
                operation_type=rng.choice(
                    [
                        PartnerOperation.OperationType.SUPPORT,
                        PartnerOperation.OperationType.WITHDRAW,
                    ]
                ),
                amount=money(rng.uniform(100, 400)),
                payment_method=rng.choice(["cash", "transfer"]),
                reason=rng.choice(["دفعة شريك", "سحب شريك", "تمويل إضافي"]),
                notes="عملية شريك تجريبية",
            )
            post_partner_operation(operation)
            made += 1
        return made

    # ------------------------------------------------------------------
    # التشغيل
    # ------------------------------------------------------------------
    def handle(self, *args, **options):
        verbosity = options.get("verbosity", 1)
        months_count = max(1, int(options.get("months") or 3))
        rng = random.Random(int(options.get("random_seed") or 0))

        from accounting.chart_of_accounts import ensure_seeded

        ensure_seeded()

        with suppress_audit():
            if not options.get("no_reset"):
                self._wipe(verbosity)
                ensure_seeded()
            call_command("seed_categories", verbosity=0)

            branches = self._ensure_branches()
            employees = self._ensure_employees(branches)
            staff = self._staff_by_branch(branches, employees)
            suppliers = self._ensure_suppliers()
            fabrics = self._ensure_fabrics(suppliers)
            self._ensure_branch_prices(branches, fabrics)
            main_warehouse, branch_warehouses = self._ensure_warehouses(branches)
            customers = self._ensure_customers(branches)
            partners = self._ensure_partners()
            self._ensure_settings()

            today = timezone.localdate()
            end_month = self._parse_end(options.get("end"), today)
            month_starts = [
                add_months(end_month, offset) for offset in range(-(months_count - 1), 1)
            ]
            first_month = month_starts[0]
            ranges = [
                (start, min(month_last_day(start), today)) for start in month_starts
            ]

            self._ensure_salary_structures(employees, first_month)
            self._open_main_warehouse(
                rng, first_month - timedelta(days=1), main_warehouse, fabrics
            )
            for index, branch in enumerate(branches):
                self._transfer_to_branch(
                    rng,
                    first_month + timedelta(days=1 + index),
                    main_warehouse,
                    branch_warehouses[branch.pk],
                    fabrics,
                )

            from expenses.models import ExpenseCategory

            categories = {c.code: c for c in ExpenseCategory.objects.all() if c.code}

            owed = {}
            totals = {
                "sessions": 0,
                "purchases": 0,
                "expenses": 0,
                "advances": 0,
                "runs": 0,
            }

            for month_start, last_day in ranges:
                month_final = month_last_day(month_start)
                is_partial = last_day < month_final
                plan = self._plan_month(
                    rng, month_start, last_day, branches, staff, fabrics, customers
                )
                curves = self._demand_curve(plan)
                bought = {}

                # نمرّ على الأيام بترتيبها الزمني: الشراء قبل البيع في نفس اليوم،
                # فالرصيد الجاري في سجل حركات المخزون يبقى صحيحاً. وقائمة الأيام
                # تشمل أيام الشراء حتى لو لم يكن فيها بيع (يوم عطلة).
                purchase_days = {
                    month_start + timedelta(days=n - 1) for n in PURCHASE_DAYS
                }
                days = sorted(set(plan) | purchase_days)
                for day in days:
                    if day > last_day:
                        continue
                    if day in purchase_days:
                        horizon = self._horizon_for(
                            month_start, last_day, (day - month_start).days + 1
                        )
                        needs = {}
                        for key, curve in curves.items():
                            needs.update(
                                self._shortfall(
                                    bought, key, self._cumulative_at(curve, horizon)
                                )
                            )
                        for branch in branches:
                            totals["purchases"] += self._post_purchase(
                                rng,
                                day,
                                branch,
                                needs,
                                {f.pk: f for f in fabrics},
                                suppliers,
                                owed,
                            )
                        for key, yards in needs.items():
                            bought[key] = bought.get(key, ZERO) + yards

                    if day in plan:
                        totals["sessions"] += self._run_day_sales(rng, day, plan[day], staff)

                # دفعة ختامية في آخر الشهر تترك رصيداً افتتاحياً للشهر التالي،
                # فيظهر في قسم «المشتريات والمخزون» من تقرير الربح والخسارة
                # قيمة البضاعة غير المباعة — وهي من أرقام التقارير. المعامل 1.25
                # يُبقي المخزون قريباً من حجم شهر واحد؛ رفعه يُضخّم المخزون شهراً
                # بعد شهر حتى تصير قيمة البضاعة غير المباعة سخيفة.
                needs = {}
                for key, curve in curves.items():
                    needs.update(
                        self._shortfall(
                            bought, key, q2((curve[-1][1] if curve else ZERO) * Decimal("1.25"))
                        )
                    )
                for branch in branches:
                    totals["purchases"] += self._post_purchase(
                        rng,
                        last_day,
                        branch,
                        needs,
                        {f.pk: f for f in fabrics},
                        suppliers,
                        owed,
                    )
                for key, yards in needs.items():
                    bought[key] = bought.get(key, ZERO) + yards

                expenses, budgets = self._make_expenses(
                    rng, month_start, last_day, branches, categories
                )
                totals["expenses"] += expenses
                if verbosity >= 2:
                    self.write_line(
                        f"  {month_start:%Y-%m}: {expenses} مصروف، {budgets} ميزانية"
                    )

                # تاريخ السلفة داخل الشهر: نقصره على آخر يوم مُولَّد حتى لا
                # تقع سلفة شهرٍ ناقص في يوم لم تُبنَ بياناته بعد.
                advance_day = min(month_start + timedelta(days=5), last_day)
                totals["advances"] += self._make_advances(rng, advance_day, employees)
                totals["runs"] += bool(self._make_payroll(month_start, month_final))
                if month_start == first_month:
                    # أول شهر فقط: التسوية والجرد مرّة واحدة يكفيان لفتح الشاشتين،
                    # وتكرارهما كل شهر بلا داعٍ يُضخّم سجل الحركات بلا فائدة.
                    self._stock_adjustment(
                        rng,
                        min(month_start + timedelta(days=12), last_day),
                        branch_warehouses[branches[0].pk],
                        fabrics,
                    )
                if partners:
                    self._make_partner_ops(
                        rng,
                        min(month_start + timedelta(days=8), last_day),
                        partners,
                    )
                if is_partial:
                    self._stock_count(
                        rng,
                        max(month_start, last_day - timedelta(days=3)),
                        main_warehouse,
                    )

            self._pay_suppliers(rng, ranges[-1][1] + timedelta(days=1), suppliers, owed)
            self._print_report(verbosity, totals, ranges)

    # ------------------------------------------------------------------
    def _parse_end(self, raw, today):
        if not raw:
            return today.replace(day=1)
        try:
            return date.fromisoformat(str(raw).strip()).replace(day=1)
        except ValueError:
            self.write_line(
                f"تجاهلنا قيمة --end غير الصالحة «{raw}» واستعملنا الشهر الحالي", self.style.WARNING
            )
            return today.replace(day=1)

    @staticmethod
    def _horizon_for(month_start, last_day, day_number):
        """آخر يوم يجب أن تغطيه دفعة شراء اليوم: اليوم السابق للدفعة التالية."""
        following = [d for d in PURCHASE_DAYS if d > day_number]
        if following:
            return month_start + timedelta(days=min(following) - 1)
        return last_day

    @staticmethod
    def _cumulative_at(curve, horizon):
        total = ZERO
        for day, value in curve:
            if day <= horizon:
                total = value
            else:
                break
        return total

    @staticmethod
    def _shortfall(bought, key, target):
        """كمية يجب شراؤها رفعاً للمخزون إلى ``target``، مع هامش أمان.

        الهامش ليس ترفاً: تقسيم السند على اللفات يقرّب، والمُسلسل يرفض البيعة
        إن نقص رصيد الفرع عن المطلوب، فالشراء بالضبط يحوّل فرقاً قدره نصف قرش
        إلى رسالة «الكمية غير متوفرة» في منتصف بيانات الاختبار.
        """
        padded = q2(target * Decimal("1.02")) + Decimal("0.5")
        already = bought.get(key, ZERO)
        if padded <= already:
            return {}
        return {key: q2(padded - already)}

    def _print_report(self, verbosity, totals, ranges):
        """يطبع ملخّصاً بالأرقام الحقيقية المحسوبة من البيانات المُنشأة.

        الأرقام تُقرأ من جداول النظام ومن ``reports.cogs`` نفسها التي يقرأ بها
        تقرير الربح والخسارة — فالملخّص لا يمكن أن يخالف التقرير، وهو سبب
        وجوده: التحقق بعين المستخدم دون فتح عشر شاشات.
        """
        from accounting.models import JournalEntry, JournalLine
        from expenses.models import Expense
        from payroll.models import Payslip
        from reports.cogs import cogs_by_fabric
        from sales.models import DailySale

        if verbosity < 1:
            return

        self.write_line("")
        self.write_line("===== ملخّص البيانات المُنشأة =====", self.style.SUCCESS)
        self.write_line(
            f"ورديات البيع: {totals['sessions']}  |  سندات الشراء: {totals['purchases']}  |  "
            f"المصاريف: {totals['expenses']}  |  سلف: {totals['advances']}  |  "
            f"مسيّرات رواتب: {totals['runs']}"
        )
        self.write_line(
            f"قيود اليومية: {JournalEntry.objects.count()}  |  "
            f"سطور القيود: {JournalLine.objects.count()}"
        )
        self.write_line("")
        self.write_line("الشهر      |      المبيعات | تكلفة البضاعة |     المصاريف |      الرواتب |   صافي الربح")
        self.write_line("-" * 78)
        for month_start, last_day in ranges:
            is_partial = last_day < month_last_day(month_start)
            revenue = (
                DailySale.objects.filter(date__gte=month_start, date__lte=last_day).aggregate(
                    t=Sum("total_sales")
                )["t"]
                or ZERO
            )
            cogs = sum(cogs_by_fabric(month_start, last_day).values(), ZERO)
            expenses = (
                Expense.objects.filter(date__gte=month_start, date__lte=last_day).aggregate(
                    t=Sum("amount")
                )["t"]
                or ZERO
            )
            payroll = (
                Payslip.objects.filter(run__month=month_start).aggregate(
                    t=Sum(Payslip.net_pay_expression())
                )["t"]
                or ZERO
            )
            net = revenue - cogs - expenses - payroll
            label = f"{month_start:%Y-%m}" + ("*" if is_partial else " ")
            self.write_line(
                f"{label} | {revenue:>15,.2f} | {cogs:>14,.2f} | {expenses:>13,.2f} "
                f"| {payroll:>13,.2f} | {net:>13,.2f}"
            )
        self.write_line(
            "* شهر جارٍ: أرقامه حتى تاريخ التشغيل فقط، وهذا هو سبب وجوده — "
            "حتى يعمل الانتقال إلى الشهر التالي."
        )
        self.write_line("")
        self.write_line(
            "افتح الآن: تقرير الربح والخسارة (فيه مقارنة مع الشهر السابق)، المخازن "
            "والجرد، دفتر الموردين، مسيّرات الرواتب، كشف حساب الموظف، وميزان المراجعة.",
            self.style.SUCCESS,
        )
