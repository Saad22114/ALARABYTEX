from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from core.models import TimeStampedModel


class AppSettings(TimeStampedModel):
    id = models.PositiveIntegerField(primary_key=True, default=1, editable=False)

    business_name = models.CharField(max_length=200, default="القماش العربي", verbose_name="اسم النشاط")
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

    class Meta:
        verbose_name = "إعدادات النظام"
        verbose_name_plural = "إعدادات النظام"

    def __str__(self):
        return "إعدادات النظام"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj