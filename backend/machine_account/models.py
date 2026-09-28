from django.conf import settings
from django.db import models
from django.db.models import Index

from core.models import TimeStampedModel


class MachineCollection(TimeStampedModel):
    """دفعة مستلمة من جهة تسوية — «وصلني كذا».

    لكل قناة بيع بالأجل حساب يُقاس عليه: ``machine`` حساب شركة الماكينة
    (مبيعات البطاقة)، و``bank`` حساب البنك (مبيعات التحويل). الرصيد المتبقي
    في كل حساب = مبيعات تلك القناة − الدفعات المستلمة لها.

    ``method`` يصف **كيف** وصلت الدفعة (نقداً/تحويلاً)، و``account`` يصف
    **أي حساب** سدّدته — البُعدان مستقلان: دفعة بنكية قد تسدّد حساب الماكينة.
    """

    class Account(models.TextChoices):
        MACHINE = "machine", "حساب الماكينة"
        BANK = "bank", "حساب البنك"

    class CollectionMethod(models.TextChoices):
        TRANSFER = "transfer", "تحويل بنكي"
        CASH = "cash", "نقدي"
        OTHER = "other", "أخرى"

    account = models.CharField(
        max_length=10,
        choices=Account.choices,
        default=Account.MACHINE,
        verbose_name="الحساب",
        help_text="الحساب الذي سدّدته هذه الدفعة",
    )
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
        verbose_name = "دفعة تسوية"
        verbose_name_plural = "دفعات التسويات"
        ordering = ["-date", "-id"]
        indexes = [Index(fields=["account", "branch", "date"])]

    def __str__(self):
        return f"{self.get_account_display()} — {self.date} — {self.amount}"