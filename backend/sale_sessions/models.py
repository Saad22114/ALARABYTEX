from decimal import Decimal

from django.db import models

from core.models import TimeStampedModel, ActiveModel


class Employee(TimeStampedModel, ActiveModel):
    name = models.CharField(max_length=150, unique=True, verbose_name="اسم الموظف")
    phone = models.CharField(max_length=30, blank=True, verbose_name="رقم الهاتف")
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.PROTECT,
        related_name="employees",
        verbose_name="الفرع",
    )
    notes = models.TextField(blank=True, verbose_name="ملاحظات")

    class Meta:
        verbose_name = "موظف"
        verbose_name_plural = "الموظفون"
        ordering = ["name"]

    def __str__(self):
        return self.name


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
        ROLL = "roll", "لفات"

    class PaymentMethod(models.TextChoices):
        CASH = "cash", "كاش"
        TRANSFER = "transfer", "تحويل"
        CARD = "card", "ماكينة"

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
    payment_method = models.CharField(
        max_length=10,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
        verbose_name="طريقة الدفع",
    )
    total = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="الإجمالي")
    sale_date = models.DateField(verbose_name="تاريخ البيع")

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