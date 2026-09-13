from datetime import date

from django.db import models

from core.models import TimeStampedModel, ActiveModel


class Partner(TimeStampedModel, ActiveModel):
    name = models.CharField(max_length=150, unique=True, verbose_name="اسم الشريك")
    share_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=50, verbose_name="نسبة المشاركة %"
    )
    notes = models.TextField(blank=True, verbose_name="ملاحظات")

    class Meta:
        verbose_name = "شريك"
        verbose_name_plural = "الشركاء"
        ordering = ["name"]

    def __str__(self):
        return self.name


class PartnerOperation(TimeStampedModel):
    """عملية شريك واحدة تمثل حركتين متطابقتين (واحدة لكل شريك بذات المبلغ)."""

    class OperationType(models.TextChoices):
        SUPPORT = "support", "دعم"
        WITHDRAW = "withdraw", "سحب"

    class PaymentMethod(models.TextChoices):
        CASH = "cash", "كاش"
        TRANSFER = "transfer", "تحويل بنكي"

    number = models.CharField(max_length=40, unique=True, verbose_name="رقم العملية")
    date = models.DateField(default=date.today, verbose_name="التاريخ")
    partner = models.ForeignKey(
        "partners.Partner",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="operations",
        verbose_name="الشريك المسجل عليه العملية",
    )
    operation_type = models.CharField(
        max_length=10,
        choices=OperationType.choices,
        verbose_name="نوع العملية",
    )
    payment_method = models.CharField(
        max_length=10,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
        verbose_name="طريقة الدفع",
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="المبلغ")
    reason = models.CharField(max_length=255, blank=True, verbose_name="السبب")
    notes = models.TextField(blank=True, verbose_name="ملاحظات")

    class Meta:
        verbose_name = "عملية شريك"
        verbose_name_plural = "عمليات الشركاء"
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.number} - {self.get_operation_type_display()} - {self.amount}"


class PartnerMovement(TimeStampedModel):
    """حركة منفردة لشريك — تُنشأ تلقائياً لكل شريك عند تسجيل أي عملية."""

    class MovementType(models.TextChoices):
        SUPPORT = "support", "دعم"
        WITHDRAW = "withdraw", "سحب"

    operation = models.ForeignKey(
        PartnerOperation,
        on_delete=models.CASCADE,
        related_name="movements",
        verbose_name="العملية",
    )
    partner = models.ForeignKey(
        Partner,
        on_delete=models.PROTECT,
        related_name="movements",
        verbose_name="الشريك",
    )
    movement_type = models.CharField(
        max_length=10,
        choices=MovementType.choices,
        default=MovementType.SUPPORT,
        verbose_name="نوع الحركة",
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="المبلغ")

    class Meta:
        verbose_name = "حركة شريك"
        verbose_name_plural = "حركات الشركاء"
        constraints = [
            models.UniqueConstraint(
                fields=["operation", "partner"], name="unique_movement_per_operation_partner"
            )
        ]

    def __str__(self):
        return f"{self.operation.number} - {self.partner.name} - {self.amount}"