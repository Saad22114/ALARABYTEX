# -*- coding: utf-8 -*-
"""نماذج الحضور والانصراف، وسياسة الضبط التي يُقاس عليها."""

from datetime import time

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from core.models import ActiveModel, TimeStampedModel


class AttendancePolicy(TimeStampedModel):
    """سياسة الحضور: متى يُسمح بالدخول، ومتى يجب أن يخرج، وكم يوم العمل.

    ساعةٌ واحدة لا تفصلها. لماذا هذا سجلٌّ منفصل عن إعدادات النظام: لو
    وُضعت في ``AppSettings`` لاختلطت بمئتي حقلٍ آخر، ولأمكن تعطيلها بتغيير
    غير مقصود من نموذج الإعدادات العام. هنا صفٌّ واحد، سببُ كل حقلٍ
    مكتوبٌ بجواره، ولا يُلمس إلا من قسم الحضور نفسه.
    """

    id = models.PositiveIntegerField(primary_key=True, default=1, editable=False)

    enabled = models.BooleanField(
        default=True,
        verbose_name="تفعيل تسجيل الحضور",
        help_text="عند التفعيل يُفتح سجل الحضور تلقائياً مع كل دخول ويغلق مع كل خروج",
    )
    #: قيمٌ من نوع ``time`` لا نصوص: الحقل يعيد النصّ كما هو على
    #: كائنٍ جديد، فلا يُقرأ منه ``.hour`` إلا بعد رحلةٍ إلى قاعدة
    #: البيانات — وأولُ استخدامٍ للسياسة يقع بالضبط قبل تلك الرحلة.
    login_window_start = models.TimeField(
        default=time(7, 0),
        verbose_name="بداية نافذة الدخول",
        help_text="قبل هذه الساعة يُعدّ الدخول مبكراً (قبل الدوام)",
    )
    login_window_end = models.TimeField(
        default=time(9, 0),
        verbose_name="نهاية نافذة الدخول",
        help_text="بعد هذه الساعة يُحتسب دخولٌ متأخّر",
    )
    logout_window_start = models.TimeField(
        default=time(16, 0),
        verbose_name="بداية نافذة الخروج",
        help_text="قبل هذه الساعة يُحتسب خروجٌ مبكر",
    )
    logout_window_end = models.TimeField(
        default=time(18, 0),
        verbose_name="نهاية نافذة الخروج",
        help_text="بعد هذه الساعة يُحتسب العمل إضافياً من لحظة بداية نافذة الخروج",
    )
    workday_minutes = models.PositiveIntegerField(
        default=480,
        validators=[MinValueValidator(1), MaxValueValidator(1440)],
        verbose_name="طول يوم العمل (دقائق)",
        help_text="ما بعده من دقائق اليوم يُحتسب عملاً إضافياً (افتراضياً 480 دقيقة = 8 ساعات)",
    )
    grace_minutes = models.PositiveIntegerField(
        default=5,
        validators=[MaxValueValidator(120)],
        verbose_name="سماح التأخير (دقائق)",
        help_text="لا يُحتسب تأخيرٌ حتى يتجاوز هذا العدد من الدقائق",
    )
    day_cutoff_hour = models.PositiveSmallIntegerField(
        default=3,
        validators=[MinValueValidator(0), MaxValueValidator(12)],
        verbose_name="ساعة بداية اليوم",
        help_text="دخولٌ بعد منتصف الليل قبل هذه الساعة يُنسب لليوم السابق (افتراضياً 3 صباحاً)",
    )
    weekend_days = models.JSONField(
        default=list,
        blank=True,
        verbose_name="أيام العطلة الأسبوعية",
        help_text="أرقام الأيام بترتيب date.weekday(): 0 الاثنين .. 4 الجمعة .. 6 الأحد. الافتراضي الجمعة",
    )
    notes = models.TextField(blank=True, default="", verbose_name="ملاحظات")

    class Meta:
        verbose_name = "سياسة الحضور"
        verbose_name_plural = "سياسات الحضور"

    def __str__(self):
        return "سياسة الحضور"

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        if created and not obj.weekend_days:
            # الجمعة في ترقيم date.weekday(): الرقم 4 لا 6.
            obj.weekend_days = [4]
            obj.save(update_fields=["weekend_days"])
        return obj


class AttendanceRecord(TimeStampedModel, ActiveModel):
    """سجل الحضور والانصراف ليومٍ واحدٍ لكل موظف.

    لا يُخزَّن هنا رقمٌ يشتقّ من غيره: ما يُشتقّ يُحسب دائماً من
    ``login_at`` و``logout_at`` عند الطلب، بواسطة ``recompute``.
    """

    class Status(models.TextChoices):
        PRESENT = "present", "حاضر"
        LATE = "late", "متأخر"
        EARLY_LEAVE = "early_leave", "انصراف مبكر"
        ABSENT = "absent", "غائب"
        EXCUSED = "excused", "مبرر"
        INSIDE = "inside", "داخل الدوام"
        OFF = "off", "عطلة"

    class Excuse(models.TextChoices):
        NONE = "none", "لا شيء"
        SICK = "sick", "مريض"
        LEAVE = "leave", "إجازة"
        OFFICIAL = "official", "مهمة رسمية"
        OTHER = "other", "أخرى"

    class Source(models.TextChoices):
        AUTO = "auto", "آلي"
        MANUAL = "manual", "يدوي"

    employee = models.ForeignKey(
        "sale_sessions.Employee",
        on_delete=models.CASCADE,
        related_name="attendance_records",
        verbose_name="الموظف",
    )
    date = models.DateField(verbose_name="التاريخ")
    login_at = models.DateTimeField(null=True, blank=True, verbose_name="وقت الدخول")
    logout_at = models.DateTimeField(null=True, blank=True, verbose_name="وقت الخروج")

    # حقول مُشتقّة: تُحسب فقط عند الحفظ والقراءة، ولا تُدخَل يدوياً.
    # worked_minutes يبقى فارغاً ما دام السطر مفتوحاً، لا صفراً: من لم
    # يخرج بعد لا عمل له، ومن لم يدخل أصلاً لا صفَّ له.
    worked_minutes = models.IntegerField(
        null=True, blank=True, verbose_name="ساعات العمل (دقائق)"
    )
    late_minutes = models.IntegerField(default=0, verbose_name="التأخير (دقائق)")
    early_leave_minutes = models.IntegerField(
        default=0, verbose_name="الانصراف المبكر (دقائق)"
    )
    overtime_minutes = models.IntegerField(default=0, verbose_name="الإضافي (دقائق)")

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ABSENT,
        verbose_name="الحالة",
    )
    excuse = models.CharField(
        max_length=20,
        choices=Excuse.choices,
        default=Excuse.NONE,
        verbose_name="المبرر",
    )
    working_day = models.BooleanField(default=True, verbose_name="يوم عمل")
    source = models.CharField(
        max_length=10,
        choices=Source.choices,
        default=Source.AUTO,
        verbose_name="مصدر السجل",
    )
    note = models.TextField(blank=True, default="", verbose_name="ملاحظات")

    class Meta:
        verbose_name = "سجل الحضور"
        verbose_name_plural = "سجلات الحضور"
        unique_together = (("employee", "date"),)
        ordering = ("-date", "employee__name")

    def __str__(self):
        return f"{self.employee} - {self.date} - {self.get_status_display()}"
