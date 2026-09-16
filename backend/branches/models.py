from django.db import models
from core.models import TimeStampedModel, ActiveModel


class Branch(TimeStampedModel, ActiveModel):
    name = models.CharField(max_length=150, verbose_name="اسم الفرع")
    code = models.CharField(max_length=30, unique=True, verbose_name="كود الفرع")
    phone = models.CharField(max_length=30, blank=True, verbose_name="رقم الهاتف")
    address = models.CharField(max_length=255, blank=True, verbose_name="العنوان")
    city = models.CharField(max_length=100, blank=True, verbose_name="المدينة")
    notes = models.TextField(blank=True, verbose_name="ملاحظات")
    monthly_sales_target = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name="الهدف الشهري للمبيعات",
        help_text="صفر يعني بدون هدف",
    )

    class Meta:
        verbose_name = "فرع"
        verbose_name_plural = "الفروع"
        ordering = ["name"]

    def __str__(self):
        return self.name


class FabricBranchPrice(TimeStampedModel):
    branch = models.ForeignKey(
        Branch, on_delete=models.CASCADE, related_name="fabric_prices", verbose_name="الفرع"
    )
    fabric = models.ForeignKey(
        "suppliers.Fabric", on_delete=models.CASCADE, related_name="branch_prices", verbose_name="القماش"
    )
    sale_price_yard = models.DecimalField(
        max_digits=12, decimal_places=3, default=0, verbose_name="سعر بيع الياردة"
    )
    sale_price_roll = models.DecimalField(
        max_digits=12, decimal_places=3, blank=True, null=True, verbose_name="سعر بيع اللفة"
    )
    min_sale_yard = models.DecimalField(
        max_digits=12, decimal_places=3, default=0, verbose_name="الحد الأدنى لسعر بيع الياردة"
    )
    min_sale_roll = models.DecimalField(
        max_digits=12, decimal_places=3, blank=True, null=True, verbose_name="الحد الأدنى لسعر بيع اللفة"
    )

    class Meta:
        verbose_name = "سعر قماش في فرع"
        verbose_name_plural = "أسعار الأقمشة في الفروع"
        constraints = [
            models.UniqueConstraint(fields=["branch", "fabric"], name="unique_branch_fabric_price"),
        ]

    def __str__(self):
        return f"{self.branch.name} - {self.fabric.name}: {self.sale_price_yard}"
