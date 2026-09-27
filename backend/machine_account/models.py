from django.conf import settings
from django.db import models
from django.db.models import Index

from core.models import TimeStampedModel


class MachineCollection(TimeStampedModel):
    """دفعة مستلمة من شركة الماكينة — «وصلني كذا».

    تُسجَّل كل دفعة تحويل/نقد تصل مقابل مبيعات البطاقة، ويُحسب الرصيد المتبقي
    في حساب الماكينة = إجمالي مبيعات البطاقة − مجموع هذه الدفعات.
    """

    class CollectionMethod(models.TextChoices):
        TRANSFER = "transfer", "تحويل بنكي"
        CASH = "cash", "نقدي"
        OTHER = "other", "أخرى"

    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="machine_collections",
        verbose_name="الفرع",
        help_text="فارغ = دفعة على الحساب الكلي",
    )
    date = models.DateField(verbose_name="تاريخ الاستلام")
    amount = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name="المبلغ المستلم"
    )
    method = models.CharField(
        max_length=10,
        choices=CollectionMethod.choices,
        default=CollectionMethod.TRANSFER,
        verbose_name="طريقة الاستلام",
    )
    reference = models.CharField(
        max_length=100, blank=True, verbose_name="مرجع التحويل / رقم العملية"
    )
    notes = models.CharField(max_length=255, blank=True, verbose_name="ملاحظات")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="machine_collections",
        verbose_name="سجّله",
    )

    class Meta:
        verbose_name = "دفعة ماكينة بطاقة"
        verbose_name_plural = "دفعات ماكينة البطاقة"
        ordering = ["-date", "-id"]
        indexes = [Index(fields=["branch", "date"])]

    def __str__(self):
        return f"{self.date} — {self.amount}"