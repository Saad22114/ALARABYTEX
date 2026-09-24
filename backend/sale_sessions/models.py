from decimal import Decimal

from django.conf import settings
from django.db import models

from core.models import TimeStampedModel, ActiveModel

from .sections import ROLE_CHOICES, PERMISSION_ACTIONS


class Employee(TimeStampedModel, ActiveModel):
    class Role(models.TextChoices):
        ADMIN = "admin", "مدير النظام"
        SUPERVISOR = "supervisor", "مشرف"
        SALES = "sales", "مندوب مبيعات"
        ACCOUNTANT = "accountant", "محاسب"
        VIEWER = "viewer", "مشاهد"
        CUSTOM = "custom", "مخصص"

    name = models.CharField(max_length=150, unique=True, verbose_name="اسم الموظف")
    avatar = models.CharField(max_length=8, blank=True, default="", verbose_name="الأفاتار")
    avatar_image = models.TextField(
        blank=True,
        default="",
        verbose_name="الصورة الشخصية",
        help_text="صورة مرفوعة من الجهاز كـ data:image/...;base64 — تُعرض بدل الأفاتار عندما تكون موجودة. تقبّلها فقط AccountAvatarView بحجم محدود ومُتحقَّق.",
    )
    last_seen_at = models.DateTimeField(
        null=True, blank=True, verbose_name="آخر ظهور",
        help_text="يُحدَّث عند أي طلب؛ المتصل من ظهر خلال آخر دقيقتين",
    )
    phone = models.CharField(max_length=30, blank=True, verbose_name="رقم الهاتف")
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees",
        verbose_name="الفرع",
        help_text="اختياري للمدير والمشرف",
    )
    allowed_branches = models.ManyToManyField(
        "branches.Branch",
        blank=True,
        related_name="employees_allowed",
        verbose_name="الفروع المسموحة",
        help_text="فروع إضافية يرى الموظف بياناتها بجانب فرعه الأساسي",
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="employee",
        verbose_name="حساب المستخدم",
    )
    notes = models.TextField(blank=True, verbose_name="ملاحظات")
    role = models.CharField(
        max_length=20, choices=Role.choices, default=Role.ADMIN, verbose_name="الدور"
    )
    permissions = models.JSONField(default=dict, blank=True, verbose_name="الصلاحيات")
    hidden_sections = models.JSONField(default=list, blank=True, verbose_name="الأقسام المخفية")
    commission_active = models.BooleanField(default=False, verbose_name="تفعيل العمولة")
    commission_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0"),
        verbose_name="نسبة العمولة (%)",
    )
    department = models.CharField(max_length=100, blank=True, default="", verbose_name="القسم")
    position = models.CharField(max_length=100, blank=True, default="", verbose_name="المسمى الوظيفي")
    email = models.EmailField(blank=True, default="", verbose_name="البريد الإلكتروني")
    birth_date = models.DateField(null=True, blank=True, verbose_name="تاريخ الميلاد")
    civil_id = models.CharField(max_length=50, blank=True, default="", verbose_name="الرقم المدني / الهوية")
    address = models.CharField(max_length=255, blank=True, default="", verbose_name="العنوان")
    hire_date = models.DateField(null=True, blank=True, verbose_name="تاريخ التوظيف")
    base_salary = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="الراتب الأساسي"
    )
    employee_code = models.CharField(
        max_length=50, blank=True, null=True, default=None, verbose_name="رقم الموظف"
    )
    multi_branch_access = models.BooleanField(default=False, verbose_name="دخول متعدد الفروع")
    must_change_password = models.BooleanField(default=False, verbose_name="تغيير كلمة المرور عند أول دخول")

    class Meta:
        verbose_name = "موظف"
        verbose_name_plural = "الموظفون"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def apply_role_preset(self, role):
        """يعيد بناء الصلاحيات حسب الدور."""

        from .sections import ROLE_PRESETS

        preset = ROLE_PRESETS.get(role, ROLE_PRESETS["custom"])
        self.role = role
        self.permissions = preset["permissions"]
        self.hidden_sections = preset["hidden_sections"]

    def has_permission(self, section_key, action="view"):
        try:
            return bool(self.permissions[section_key].get(action))
        except (KeyError, AttributeError, TypeError):
            return False

    def has_window(self, section_key, window_key):
        """يعيد هل يملك الموظف نافذةً داخل قسم — غياب قائمة النوافذ يعني عدم التقييد."""
        perms = self.permissions.get(section_key, {}) if isinstance(self.permissions, dict) else {}
        windows = perms.get("windows") if isinstance(perms, dict) else None
        if windows is None:
            return True
        if isinstance(windows, list):
            return window_key in windows
        if isinstance(windows, dict):
            return bool(windows.get(window_key))
        return True

    def section_is_hidden(self, section_key):
        return section_key in (self.hidden_sections or [])


class SaleSession(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "مفتوحة"
        CLOSED = "closed", "مغلقة"

    employee = models.ForeignKey(
        Employee, on_delete=models.PROTECT, related_name="sessions", verbose_name="الموظف"
    )
    branch = models.ForeignKey(
        "branches.Branch", on_delete=models.PROTECT, related_name="sale_sessions", verbose_name="الفرع"
    )
    opened_at = models.DateTimeField(auto_now_add=True, verbose_name="وقت الفتح")
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name="وقت الإغلاق")
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.OPEN, verbose_name="الحالة"
    )
    commission_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0"),
        verbose_name="قيمة العمولة",
    )
    is_manual = models.BooleanField(default=False, verbose_name="وردية مُدخلة يدوياً")
    manual_date = models.DateField(null=True, blank=True, verbose_name="تاريخ البيعة اليدوية")
    manual_cash = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0"), verbose_name="النقدي (يدوي)"
    )
    manual_transfer = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0"), verbose_name="التحويل (يدوي)"
    )
    manual_card = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0"), verbose_name="الماكينة (يدوي)"
    )
    notes = models.TextField(blank=True, verbose_name="ملاحظات")

    class Meta:
        verbose_name = "وردية بيع"
        verbose_name_plural = "ورديات البيع"
        ordering = ["-opened_at"]

    def __str__(self):
        return f"{self.employee.name} - {self.branch.name} - {self.opened_at:%Y-%m-%d %H:%M}"


class SaleSessionItem(TimeStampedModel):
    class SaleType(models.TextChoices):
        YARD = "yard", "ياردات"
        ROLL = "roll", "طاقات"

    class PaymentMethod(models.TextChoices):
        CASH = "cash", "كاش"
        TRANSFER = "transfer", "تحويل"
        CARD = "card", "ماكينة"

    class CardType(models.TextChoices):
        CREDIT = "credit", "إئتماني"
        DEBIT = "debit", "خصم مباشر"

    session = models.ForeignKey(
        SaleSession, on_delete=models.CASCADE, related_name="items", verbose_name="الوردية"
    )
    fabric = models.ForeignKey(
        "suppliers.Fabric", on_delete=models.PROTECT, related_name="session_items", verbose_name="القماش"
    )
    sale_type = models.CharField(
        max_length=10,
        choices=SaleType.choices,
        default=SaleType.YARD,
        verbose_name="نوع البيع",
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="الكمية")
    unit_price = models.DecimalField(max_digits=12, decimal_places=3, verbose_name="سعر الوحدة")
    discount_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0"), verbose_name="قيمة الخصم"
    )
    payment_method = models.CharField(
        max_length=10,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
        verbose_name="طريقة الدفع",
    )
    card_type = models.CharField(
        max_length=10,
        choices=CardType.choices,
        blank=True,
        default="",
        verbose_name="نوع البطاقة",
        help_text="نوع الماكينة عند الدفع بها: إئتماني أو خصم مباشر (كل نوع بنسبة عمولة مستقلة)",
    )
    card_fee_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0"),
        verbose_name="رسوم الماكينة",
        help_text="مبلغ عمولة الماكينة المخصوم (يُحسب تلقائياً من إعدادات النظام)",
    )
    net_total = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0"),
        verbose_name="صافي البند",
        help_text="إجمالي البند بعد خصم رسوم الماكينة (يساوي الإجمالي عند الدفع نقداً أو تحويلاً)",
    )
    total = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="الإجمالي")
    sale_date = models.DateField(verbose_name="تاريخ البيع")
    customer_name = models.CharField(max_length=150, blank=True, verbose_name="اسم الزبون")
    customer_phone = models.CharField(max_length=30, blank=True, verbose_name="رقم هاتف الزبون")
    sale_group = models.CharField(max_length=36, blank=True, verbose_name="معرّف البيعة")
    is_returned = models.BooleanField(default=False, verbose_name="مسترجع")
    returned_at = models.DateTimeField(null=True, blank=True, verbose_name="وقت الاسترجاع")
    return_reason = models.CharField(max_length=255, blank=True, verbose_name="سبب الاسترجاع")

    class Meta:
        verbose_name = "بند وردية"
        verbose_name_plural = "بنود الوردية"
        ordering = ["-id"]

    @property
    def yards_effective(self):
        if self.sale_type == SaleSessionItem.SaleType.ROLL:
            return self.quantity * (self.fabric.yards_per_roll or Decimal("0"))
        return self.quantity

    def __str__(self):
        return f"{self.fabric.name} x {self.quantity}"