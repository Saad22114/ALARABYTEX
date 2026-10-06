from django.db import models

from core.models import TimeStampedModel, ActiveModel


class Customer(TimeStampedModel, ActiveModel):
    class WhatsAppWelcomeStatus(models.TextChoices):
        NOT_REQUESTED = "not_requested", "لم يُطلب الإرسال"
        NOT_CONFIGURED = "not_configured", "التكامل غير مهيأ"
        SENT = "sent", "أُرسل إلى واتساب"
        FAILED = "failed", "تعذر الإرسال"

    name = models.CharField(max_length=150, verbose_name="اسم الزبون")
    phone = models.CharField(
        max_length=30,
        unique=True,
        blank=True,
        null=True,
        verbose_name="رقم الهاتف",
        help_text="رقم هاتف فريد للزبون",
    )
    email = models.EmailField(blank=True, verbose_name="البريد الإلكتروني")
    address = models.CharField(max_length=255, blank=True, verbose_name="العنوان")
    notes = models.TextField(blank=True, verbose_name="ملاحظات")
    whatsapp_opt_in = models.BooleanField(default=False, verbose_name="موافقة رسائل واتساب")
    whatsapp_opt_in_at = models.DateTimeField(null=True, blank=True, verbose_name="وقت موافقة واتساب")
    whatsapp_opt_out_at = models.DateTimeField(null=True, blank=True, verbose_name="وقت إلغاء موافقة واتساب")
    whatsapp_welcome_status = models.CharField(
        max_length=20,
        choices=WhatsAppWelcomeStatus.choices,
        default=WhatsAppWelcomeStatus.NOT_REQUESTED,
        verbose_name="حالة رسالة الترحيب عبر واتساب",
    )
    whatsapp_welcome_sent_at = models.DateTimeField(null=True, blank=True, verbose_name="وقت إرسال رسالة الترحيب")
    whatsapp_welcome_message_id = models.CharField(max_length=150, blank=True, verbose_name="معرف رسالة واتساب")
    whatsapp_welcome_error = models.CharField(max_length=500, blank=True, verbose_name="خطأ إرسال رسالة واتساب")
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customers",
        verbose_name="الفرع المسجل فيه",
    )

    class Meta:
        verbose_name = "زبون"
        verbose_name_plural = "الزبائن"
        ordering = ["name"]

    def __str__(self):
        return self.name
