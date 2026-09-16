from django.core.exceptions import ValidationError
from django.db import models
from django.conf import settings

from core.models import TimeStampedModel


class Account(TimeStampedModel):
    """حساب في شجرة الحسابات (الدليل المحاسبي)."""

    class Type(models.TextChoices):
        ASSET = "asset", "أصل"
        LIABILITY = "liability", "التزام"
        EQUITY = "equity", "حقوق ملكية"
        INCOME = "income", "إيراد"
        EXPENSE = "expense", "مصروف"

    code = models.CharField(max_length=20, unique=True, verbose_name="الكود")
    name = models.CharField(max_length=150, verbose_name="اسم الحساب")
    type = models.CharField(max_length=10, choices=Type.choices, verbose_name="النوع")
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
        verbose_name="الحساب الأب",
    )
    source_key = models.CharField(
        max_length=80,
        unique=True,
        null=True,
        blank=True,
        verbose_name="مفتاح المصدر",
        help_text="يربط الحساب تلقائياً بمصدر خارجي (تصنيف مصروف، طريقة دفع...)",
    )
    is_active = models.BooleanField(default=True, verbose_name="نشط")
    is_system = models.BooleanField(default=False, verbose_name="حساب نظامي")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="الترتيب")

    class Meta:
        verbose_name = "حساب"
        verbose_name_plural = "الحسابات"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} — {self.name}"

    def clean(self):
        if self.parent_id and self.pk and self.parent_id == self.pk:
            raise ValidationError("لا يمكن جعل الحساب أباً لنفسه")


class JournalEntry(TimeStampedModel):
    """قيد يومية — الوحدة الأساسية في الدفتر المحاسبي."""

    class Source(models.TextChoices):
        MANUAL = "manual", "قيد يدوي"
        SESSION = "session", "إغلاق وردية بيع"
        PURCHASE = "purchase", "عمليات الموردين"
        EXPENSE = "expense", "مصروف"
        PARTNER = "partner", "عملية شريك"
        CLOSING = "closing", "قيد إقفال دوري"

    number = models.CharField(max_length=30, unique=True, verbose_name="رقم القيد")
    date = models.DateField(verbose_name="التاريخ")
    description = models.CharField(max_length=255, blank=True, verbose_name="البيان")
    source = models.CharField(
        max_length=15, choices=Source.choices, default=Source.MANUAL, verbose_name="المصدر"
    )
    source_id = models.PositiveIntegerField(null=True, blank=True, verbose_name="معرف المصدر")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="journal_entries",
        verbose_name="أنشأه",
    )
    reversed_at = models.DateTimeField(null=True, blank=True, verbose_name="تاريخ الإلغاء")

    class Meta:
        verbose_name = "قيد يومية"
        verbose_name_plural = "القيود اليومية"
        ordering = ["-date", "-created_at"]
        indexes = [
            models.Index(fields=["source", "source_id"]),
            models.Index(fields=["date"]),
        ]

    def __str__(self):
        return f"{self.number} — {self.description}"


class JournalLine(TimeStampedModel):
    """سطر داخل قيد اليومية (مدين/دائن على حساب محدد)."""

    entry = models.ForeignKey(
        JournalEntry, on_delete=models.CASCADE, related_name="lines", verbose_name="القيد"
    )
    account = models.ForeignKey(
        Account, on_delete=models.PROTECT, related_name="journal_lines", verbose_name="الحساب"
    )
    debit = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="مدين")
    credit = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="دائن")
    description = models.CharField(max_length=255, blank=True, verbose_name="البيان")

    class Meta:
        verbose_name = "سطر قيد"
        verbose_name_plural = "أسطر القيد"
        ordering = ["id"]

    def __str__(self):
        return f"{self.account.name}: {self.debit or self.credit}"


class ClosedPeriod(TimeStampedModel):
    """سجل عمليات الإقفال الدوري (تحويل نتائج الدخل إلى أرباح محتجزة)."""

    period_end = models.DateField(unique=True, verbose_name="أخر يوم في الفترة المغلقة")
    description = models.CharField(max_length=255, blank=True, verbose_name="الوصف")
    net_profit = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, verbose_name="صافي أرباح الفترة"
    )

    class Meta:
        verbose_name = "فترة مقفلة"
        verbose_name_plural = "الفترات المغلقة"
        ordering = ["-period_end"]

    def __str__(self):
        return f"إقفال حتى {self.period_end} — صافي {self.net_profit}"