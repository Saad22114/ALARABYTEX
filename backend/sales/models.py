from decimal import Decimal
from django.db import models
from django.db.models import UniqueConstraint, Index
from core.models import TimeStampedModel


class DailySale(TimeStampedModel):
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.PROTECT,
        related_name="daily_sales",
        verbose_name="الفرع",
    )
    date = models.DateField(verbose_name="التاريخ")
    employee = models.ForeignKey(
        "sale_sessions.Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_sales",
        verbose_name="الموظف",
    )
    total_sales = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="إجمالي المبيعات")
    cash_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="المبيعات النقدية")
    transfer_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="مبيعات التحويل")
    card_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="مبيعات البطاقة")
    other_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="مبيعات أخرى")
    notes = models.TextField(blank=True, verbose_name="ملاحظات")

    class Meta:
        verbose_name = "مبيعات يومية"
        verbose_name_plural = "المبيعات اليومية"
        ordering = ["-date", "-created_at"]
        constraints = [
            UniqueConstraint(fields=["branch", "date"], name="unique_branch_date_sale"),
        ]
        indexes = [
            Index(fields=["branch", "date"]),
            Index(fields=["date"]),
        ]

    @property
    def payment_total(self):
        return self.cash_amount + self.transfer_amount + self.card_amount + self.other_amount

    @property
    def is_balanced(self):
        return abs(self.payment_total - self.total_sales) < Decimal("0.01")

    def __str__(self):
        return f"{self.branch.name} - {self.date} - {self.total_sales}"


class DailySaleItem(TimeStampedModel):
    sale = models.ForeignKey(
        DailySale, on_delete=models.CASCADE, related_name="sale_items", verbose_name="البيع"
    )
    fabric = models.ForeignKey(
        "suppliers.Fabric", on_delete=models.PROTECT, related_name="sale_items", verbose_name="القماش"
    )
    yards = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="ياردات المبيعات")
    unit_price = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True,
        verbose_name="سعر الوحدة", help_text="سعر الياردة عند البيع (اختياري)",
    )

    class Meta:
        verbose_name = "صنف مبيعات"
        verbose_name_plural = "أصناف المبيعات"
        ordering = ["id"]
