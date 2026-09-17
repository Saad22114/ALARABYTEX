from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from core.models import TimeStampedModel


class AppSettings(TimeStampedModel):
    id = models.PositiveIntegerField(primary_key=True, default=1, editable=False)

    business_name = models.CharField(max_length=200, default="القماش العربي", verbose_name="اسم النشاط")
    trade_name = models.CharField(max_length=200, blank=True, verbose_name="الاسم التجاري",
                                  help_text="الاسم التجاري المسجّل (اسم السجل التجاري) كما يظهر في الفواتير")
    commercial_registration = models.CharField(max_length=50, blank=True, verbose_name="رقم السجل التجاري")
    business_phone = models.CharField(max_length=30, blank=True, verbose_name="رقم الهاتف")
    business_address = models.CharField(max_length=255, blank=True, verbose_name="العنوان")
    tax_number = models.CharField(max_length=50, blank=True, verbose_name="الرقم الضريبي")

    currency_symbol = models.CharField(max_length=10, default="ر.ع", verbose_name="رمز العملة")
    currency_code = models.CharField(max_length=10, default="OMR", verbose_name="كود العملة")
    decimal_places = models.PositiveSmallIntegerField(
        default=2,
        validators=[MinValueValidator(0), MaxValueValidator(4)],
        verbose_name="منازل الفاصلة العشرية",
    )

    default_period = models.CharField(
        max_length=20,
        default="today",
        choices=[("today", "اليوم"), ("week", "هذا الأسبوع"), ("month", "هذا الشهر")],
        verbose_name="الفترة الافتراضية للوحة التحكم",
    )
    default_page_size = models.PositiveSmallIntegerField(
        default=10,
        validators=[MinValueValidator(5), MaxValueValidator(50)],
        verbose_name="عدد الصفوف في الجداول",
    )
    allow_negative_stock = models.BooleanField(
        default=False,
        verbose_name="السماح بالمبيعات برصيد سالب",
        help_text="عند التفعيل يُسمح بتسجيل مبيعات تتجاوز رصيد المخزون المتاح",
    )
    hidden_sections = models.JSONField(default=list, blank=True, verbose_name="الأقسام المخفية")

    business_email = models.EmailField(blank=True, verbose_name="البريد الإلكتروني")
    low_stock_threshold = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=50,
        verbose_name="حد تنبيه المخزون المنخفض",
        help_text="تنبيه عند وصول رصيد القماش إلى هذا الحد أو أقل",
    )
    date_format = models.CharField(
        max_length=20,
        default="YYYY-MM-DD",
        choices=[
            ("YYYY-MM-DD", "2026-09-13"),
            ("DD-MM-YYYY", "13-09-2026"),
            ("DD/MM/YYYY", "13/09/2026"),
            ("MM-DD-YYYY", "09-13-2026"),
        ],
        verbose_name="صيغة التاريخ",
    )
    default_theme = models.CharField(
        max_length=20,
        default="green",
        choices=[
            ("green", "أخضر"),
            ("blue", "أزرق"),
            ("violet", "بنفسجي"),
            ("rose", "وردي"),
            ("amber", "ذهبي"),
            ("cyan", "سماوي"),
            ("orange", "برتقالي"),
            ("red", "أحمر"),
            ("pink", "زهري"),
            ("indigo", "نيلي"),
            ("teal", "أخضر مائي"),
            ("fuchsia", "فوشيا"),
            ("lime", "ليموني"),
            ("slate", "رمادي أردوازي"),
            ("maroon", "نبيذي"),
            ("burgundy", "برغندي"),
            ("lilac", "ليلكي"),
            ("forest", "أخضر غابة"),
            ("plum", "خوخي داكن"),
            ("navy", "كحلي"),
        ],
        verbose_name="المظهر الافتراضي",
    )
    receipt_footer = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="تذييل الفواتير والطباعة",
        help_text="نص يظهر أسفل الفواتير المطبوعة",
    )
    invoice_notes = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="ملاحظات الفاتورة",
        help_text="نص اختياري يظهر أعلى خانتي التوقيع في الفاتورة",
    )

    invoice_prefix = models.CharField(
        max_length=30, blank=True, default="", verbose_name="برفكس أرقام الإيصالات",
        help_text="حروف تُسبَق لرقم الإيصال المطبوع (مثال: INV-)",
    )
    tax_rate = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
        verbose_name="نسبة الضريبة المضافة (%)",
        help_text="تُحسب على إجمالي الإيصال المطبوع عند تفعيل إظهار الضريبة",
    )
    currency_position = models.CharField(
        max_length=10,
        default="after",
        choices=[("after", "بعد المبلغ"), ("before", "قبل المبلغ")],
        verbose_name="موضع رمز العملة",
    )
    previous_day_cutoff_hour = models.PositiveSmallIntegerField(
        default=2,
        validators=[MinValueValidator(0), MaxValueValidator(23)],
        verbose_name="ساعة بداية اليوم المحاسبي",
        help_text="البيوع المسجلة قبل هذه الساعة تُعدّ لليوم السابق (افتراضياً 2 صباحاً)",
    )
    low_stock_alert_enabled = models.BooleanField(
        default=True,
        verbose_name="تفعيل تنبيهات المخزون المنخفض",
        help_text="إظهار تنبيهات الأقمشة التي وصل رصيدها إلى حد التنبيه",
    )
    session_warn_hours = models.PositiveSmallIntegerField(
        default=2,
        validators=[MinValueValidator(1), MaxValueValidator(24)],
        verbose_name="تنبيه مدة الوردية (ساعات)",
        help_text="بعد هذه المدة تظهر شارة تحذير على الوردية المفتوحة",
    )
    session_danger_hours = models.PositiveSmallIntegerField(
        default=4,
        validators=[MinValueValidator(1), MaxValueValidator(72)],
        verbose_name="تحذير الوردية الطويلة (ساعات)",
        help_text="بعد هذه المدة تظهر شارة تحذير حمراء للوردية المفتوحة",
    )
    default_payment_method = models.CharField(
        max_length=10,
        default="transfer",
        choices=[("cash", "كاش"), ("transfer", "تحويل"), ("card", "ماكينة")],
        verbose_name="طريقة الدفع الافتراضية",
        help_text="تُحدَّد تلقائياً عند إضافة بند جديد للوردية",
    )
    discount_max_percent = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("100"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
        verbose_name="أقصى خصم مسموح (%)",
        help_text="الحد الأقصى لخصم البند كنسبة من إجماليه (100 تعني بدون حد)",
    )
    receipt_show_tax = models.BooleanField(
        default=False,
        verbose_name="إظهار الضريبة في الإيصال المطبوع",
    )
    receipt_show_phone = models.BooleanField(
        default=True,
        verbose_name="إظهار رقم الهاتف في الإيصال المطبوع",
    )
    logo = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="شعار الموقع",
        help_text="مسار ملف صورة الشعار (PNG) داخل مجلد الوسائط",
    )
    backup_password = models.CharField(
        max_length=128,
        blank=True,
        default="",
        verbose_name="كلمة مرور النسخ الاحتياطي",
        help_text="عند ضبطها تُشفَّر النسخ الاحتياطية وتتطلب كلمة المرور نفسها للاستعادة",
    )

    class Meta:
        verbose_name = "إعدادات النظام"
        verbose_name_plural = "إعدادات النظام"

    def __str__(self):
        return "إعدادات النظام"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj