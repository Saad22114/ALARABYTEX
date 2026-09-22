from decimal import Decimal

from django.db import models, transaction
from django.db.models import Sum
from django.utils import timezone

from core.models import TimeStampedModel, ActiveModel


class DocumentSequence(TimeStampedModel):
    """عدّاد آمن للأرقام التسلسلية للوثائق (استلام، تحويل، تسوية، جرد)."""

    key = models.CharField(max_length=30, unique=True, verbose_name="المفتاح")
    value = models.PositiveIntegerField(default=0, verbose_name="آخر رقم")

    class Meta:
        verbose_name = "تسلسل وثيقة"
        verbose_name_plural = "تسلسلات الوثائق"

    @classmethod
    def next_number(cls, prefix: str) -> str:
        year = timezone.now().year
        key = f"{prefix}-{year}"
        with transaction.atomic():
            seq, created = cls.objects.select_for_update().get_or_create(key=key)
            if created:
                seq.value = 0
            seq.value += 1
            seq.save(update_fields=["value"])
        return f"{prefix}-{year}-{seq.value:04d}"


class Warehouse(TimeStampedModel, ActiveModel):
    name = models.CharField(max_length=150, verbose_name="اسم المخزن")
    code = models.CharField(max_length=30, unique=True, verbose_name="كود المخزن")
    location = models.CharField(max_length=255, blank=True, verbose_name="الموقع")
    phone = models.CharField(max_length=30, blank=True, verbose_name="الهاتف")
    manager_name = models.CharField(max_length=150, blank=True, verbose_name="أمين المخزن")
    notes = models.TextField(blank=True, verbose_name="ملاحظات")
    branch = models.OneToOneField(
        "branches.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="warehouse",
        verbose_name="الفرع المرتبط",
    )

    class Meta:
        verbose_name = "مخزن"
        verbose_name_plural = "المخازن"
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def is_branch_stock(self):
        return self.branch_id is not None

    @classmethod
    def for_branch(cls, branch):
        """يرجع مخزن المرتبط بالفرع وينشئه أو يربطه إن وُجد باسمه المعتاد."""
        wh = cls.objects.filter(branch=branch).first()
        if wh:
            return wh
        wh = cls.objects.filter(code=f"BR-{branch.code}").first()
        if wh:
            wh.branch = branch
            wh.save(update_fields=["branch"])
            return wh
        wh = cls(name=f"فرع: {branch.name}", code=f"BR-{branch.code}",
                 location=branch.address or branch.city or "", branch=branch)
        wh.save()
        return wh

    @property
    def total_rolls(self):
        return self.rolls.exclude(status=FabricRoll.Status.CONSUMED).count()

    @property
    def total_yards(self):
        return self.rolls.aggregate(t=Sum("remaining_yards"))["t"] or Decimal("0")


class FabricRoll(TimeStampedModel):
    class Status(models.TextChoices):
        AVAILABLE = "available", "متاحة"
        CONSUMED = "consumed", "مستنفدة"
        DAMAGED = "damaged", "تالفة"

    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="rolls", verbose_name="المخزن"
    )
    fabric = models.ForeignKey(
        "suppliers.Fabric", on_delete=models.PROTECT, related_name="rolls", verbose_name="القماش"
    )
    code = models.CharField(max_length=40, unique=True, verbose_name="كود اللفة")
    yards = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="الياردات الأصلية")
    remaining_yards = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="الياردات المتبقية")
    unit_cost = models.DecimalField(max_digits=12, decimal_places=3, default=0, verbose_name="تكلفة الياردة")
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.AVAILABLE, verbose_name="الحالة"
    )
    received_date = models.DateField(null=True, blank=True, verbose_name="تاريخ الاستلام")
    notes = models.TextField(blank=True, verbose_name="ملاحظات")

    class Meta:
        verbose_name = "لفة قماش"
        verbose_name_plural = "لفات القماش"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["warehouse", "fabric"])]

    def __str__(self):
        return f"{self.code} - {self.fabric.name} ({self.remaining_yards} ياردة)"

    def save(self, *args, **kwargs):
        if not self.code:
            seq, _ = DocumentSequence.objects.get_or_create(key="ROLL")
            if _:
                seq.value = 0
            with transaction.atomic():
                seq.value += 1
                seq.save(update_fields=["value"])
                self.code = f"RL-{timezone.now().year}-{seq.value:05d}"
        if self.remaining_yards is None:
            self.remaining_yards = self.yards
        if self.status == FabricRoll.Status.CONSUMED:
            self.remaining_yards = Decimal("0")
        super().save(*args, **kwargs)


class GoodsReceipt(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "مسودة"
        POSTED = "posted", "مُرحّل"

    number = models.CharField(max_length=40, unique=True, verbose_name="رقم سند الاستلام")
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="receipts",
        null=True, blank=True, verbose_name="المخزن المستلم",
    )
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="goods_receipts",
        verbose_name="الفرع المستلم",
    )
    purchase_entry = models.ForeignKey(
        "suppliers.LedgerEntry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="goods_receipts",
        verbose_name="قيد الشراء المرتبط",
    )
    supplier = models.ForeignKey(
        "suppliers.Supplier",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="goods_receipts",
        verbose_name="المورد",
    )
    date = models.DateField(verbose_name="تاريخ الاستلام", default=timezone.localdate)
    supplier_receipt_no = models.CharField(max_length=50, blank=True, verbose_name="رقم فاتورة المورد")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT, verbose_name="الحالة")
    notes = models.TextField(blank=True, verbose_name="ملاحظات")

    @property
    def is_branch_receipt(self):
        return bool(self.branch_id)

    class Meta:
        verbose_name = "استلام بضاعة من مورد"
        verbose_name_plural = "استلام البضاعة من الموردين"
        ordering = ["-date", "-id"]

    def __str__(self):
        dest = self.warehouse or self.branch
        return f"{self.number} - {dest.name if dest else 'بدون وجهة'}"


class GoodsReceiptItem(TimeStampedModel):
    receipt = models.ForeignKey(GoodsReceipt, on_delete=models.CASCADE, related_name="items", verbose_name="السند")
    fabric = models.ForeignKey("suppliers.Fabric", on_delete=models.PROTECT, verbose_name="القماش")
    rolls_count = models.PositiveIntegerField(default=1, verbose_name="عدد اللفات")
    yards = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="إجمالي الياردات")
    unit_price = models.DecimalField(max_digits=12, decimal_places=3, default=0, verbose_name="سعر الياردة")
    total = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="الإجمالي")

    class Meta:
        verbose_name = "صنف استلام"
        verbose_name_plural = "أصناف الاستلام"
        ordering = ["id"]


class StockTransfer(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "مسودة"
        REQUESTED = "requested", "بانتظار الموافقة"
        APPROVED = "approved", "معتمد"
        REJECTED = "rejected", "مرفوض"
        COMPLETED = "completed", "منفّذ"
        CANCELLED = "cancelled", "ملغى"

    number = models.CharField(max_length=40, unique=True, verbose_name="رقم سند التحويل")
    from_warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="transfers_out", verbose_name="المخزن المُرسِل"
    )
    to_warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="transfers_in",
        verbose_name="المخزن المُستقبِل",
    )
    to_branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="stock_transfers",
        verbose_name="الفرع المستلم",
    )
    date = models.DateField(verbose_name="تاريخ التحويل", default=timezone.localdate)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT, verbose_name="الحالة")
    requested_by = models.CharField(max_length=150, blank=True, verbose_name="مقدّم الطلب")
    approved_by = models.CharField(max_length=150, blank=True, verbose_name="الموافِق")
    requested_at = models.DateTimeField(null=True, blank=True, verbose_name="وقت الطلب")
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name="وقت الموافقة")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="وقت التنفيذ")
    notes = models.TextField(blank=True, verbose_name="ملاحظات")

    class Meta:
        verbose_name = "تحويل بين المخازن"
        verbose_name_plural = "التحويلات بين المخازن"
        ordering = ["-date", "-id"]

    def __str__(self):
        to = self.to_warehouse or self.to_branch
        return f"{self.number} - {self.from_warehouse.name} إلى {to.name if to else 'بدون وجهة'}"

    @property
    def total_yards(self):
        return self.items.aggregate(t=Sum("yards"))["t"] or Decimal("0")


class StockTransferItem(TimeStampedModel):
    class QuantityMode(models.TextChoices):
        YARD = "yard", "ياردات"
        ROLL = "roll", "طاقات"

    transfer = models.ForeignKey(StockTransfer, on_delete=models.CASCADE, related_name="items", verbose_name="التحويل")
    fabric = models.ForeignKey("suppliers.Fabric", on_delete=models.PROTECT, verbose_name="القماش")
    yards = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="الياردات")
    rolls_count = models.PositiveIntegerField(default=0, verbose_name="عدد اللفات")
    quantity_mode = models.CharField(
        max_length=10, choices=QuantityMode.choices, default=QuantityMode.YARD, verbose_name="طريقة الكمية"
    )

    class Meta:
        verbose_name = "صنف تحويل"
        verbose_name_plural = "أصناف التحويل"
        ordering = ["id"]


class StockAdjustment(TimeStampedModel):
    class Reason(models.TextChoices):
        DAMAGE = "damage", "تلف"
        LOSS = "loss", "فقد/نقص"
        GAIN = "gain", "زيادة"
        CORRECTION = "correction", "تصحيح جرد"

    class Direction(models.TextChoices):
        IN = "in", "إضافة للمخزون"
        OUT = "out", "خصم من المخزون"

    number = models.CharField(max_length=40, unique=True, verbose_name="رقم سند التسوية")
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="adjustments", verbose_name="المخزن"
    )
    date = models.DateField(verbose_name="تاريخ التسوية", default=timezone.localdate)
    reason = models.CharField(max_length=20, choices=Reason.choices, blank=True, verbose_name="سبب التسوية")
    direction = models.CharField(max_length=5, choices=Direction.choices, verbose_name="نوع التسوية")
    notes = models.TextField(blank=True, verbose_name="ملاحظات")

    class Meta:
        verbose_name = "تسوية مخزون"
        verbose_name_plural = "تسويات المخزون"
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.number} - {self.warehouse.name}"


class StockAdjustmentItem(TimeStampedModel):
    adjustment = models.ForeignKey(
        StockAdjustment, on_delete=models.CASCADE, related_name="items", verbose_name="التسوية"
    )
    fabric = models.ForeignKey("suppliers.Fabric", on_delete=models.PROTECT, verbose_name="القماش")
    yards = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="الياردات")
    rolls_count = models.PositiveIntegerField(default=0, verbose_name="عدد اللفات التقريبي")

    class Meta:
        verbose_name = "صنف تسوية"
        verbose_name_plural = "أصناف التسوية"
        ordering = ["id"]


class StockCount(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "غير منشور"
        POSTED = "posted", "منشور"
        CANCELLED = "cancelled", "ملغى"

    number = models.CharField(max_length=40, unique=True, verbose_name="رقم جلسة الجرد")
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="counts", verbose_name="المخزن"
    )
    date = models.DateField(verbose_name="تاريخ الجرد", default=timezone.localdate)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN, verbose_name="الحالة")
    notes = models.TextField(blank=True, verbose_name="ملاحظات")

    class Meta:
        verbose_name = "جلسة جرد"
        verbose_name_plural = "جلسات الجرد"
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.number} - {self.warehouse.name}"


class StockCountItem(TimeStampedModel):
    count = models.ForeignKey(StockCount, on_delete=models.CASCADE, related_name="items", verbose_name="الجلسة")
    fabric = models.ForeignKey("suppliers.Fabric", on_delete=models.PROTECT, verbose_name="القماش")
    system_yards = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="الرصيد الدفتري")
    counted_yards = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="الرصيد الفعلي")

    class Meta:
        verbose_name = "صنف جرد"
        verbose_name_plural = "أصناف الجرد"
        ordering = ["id"]

    @property
    def difference(self):
        if self.counted_yards is None:
            return Decimal("0")
        return self.counted_yards - self.system_yards


class StockOpening(TimeStampedModel):
    number = models.CharField(max_length=40, unique=True, verbose_name="رقم سند الرصيد الافتتاحي")
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="openings", verbose_name="المخزن"
    )
    date = models.DateField(verbose_name="تاريخ الرصيد الافتتاحي", default=timezone.localdate)
    notes = models.TextField(blank=True, verbose_name="ملاحظات")

    class Meta:
        verbose_name = "رصيد افتتاحي"
        verbose_name_plural = "الأرصدة الافتتاحية"
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.number} - {self.warehouse.name}"


class StockOpeningItem(TimeStampedModel):
    opening = models.ForeignKey(StockOpening, on_delete=models.CASCADE, related_name="items", verbose_name="السند")
    fabric = models.ForeignKey("suppliers.Fabric", on_delete=models.PROTECT, verbose_name="القماش")
    yards = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="الياردات")
    rolls_count = models.PositiveIntegerField(default=1, verbose_name="عدد اللفات")
    unit_price = models.DecimalField(max_digits=12, decimal_places=3, default=0, verbose_name="تكلفة الياردة")

    class Meta:
        verbose_name = "صنف رصيد افتتاحي"
        verbose_name_plural = "أصناف الأرصدة الافتتاحية"
        ordering = ["id"]


class StockMovement(TimeStampedModel):
    class Type(models.TextChoices):
        RECEIPT = "receipt", "استلام من مورد"
        TRANSFER_OUT = "transfer_out", "تحويل صادر"
        TRANSFER_IN = "transfer_in", "تحويل ياردةد"
        ADJUSTMENT_IN = "adjustment_in", "تسوية إضافة"
        ADJUSTMENT_OUT = "adjustment_out", "تسوية خصم"
        COUNT = "count", "تسوية جرد"
        SALE = "sale", "مبيعات"
        OPENING = "opening", "رصيد افتتاحي"

    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="movements", verbose_name="المخزن")
    fabric = models.ForeignKey("suppliers.Fabric", on_delete=models.PROTECT, verbose_name="القماش")
    roll = models.ForeignKey(
        FabricRoll, on_delete=models.SET_NULL, null=True, blank=True, related_name="movements", verbose_name="اللفة"
    )
    movement_type = models.CharField(max_length=20, choices=Type.choices, verbose_name="نوع الحركة")
    quantity = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="الكمية (موقّعة)")
    balance_before = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="الرصيد قبل الحركة"
    )
    balance_after = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="الرصيد بعد الحركة"
    )
    reference_type = models.CharField(max_length=30, blank=True, verbose_name="المرجع")
    reference_id = models.PositiveIntegerField(null=True, blank=True, verbose_name="رقم المرجع")
    reference_no = models.CharField(max_length=40, blank=True, verbose_name="رقم الوثيقة")
    date = models.DateField(verbose_name="التاريخ", default=timezone.localdate)
    notes = models.TextField(blank=True, verbose_name="ملاحظات")

    class Meta:
        verbose_name = "حركة مخزون"
        verbose_name_plural = "حركات المخزون"
        ordering = ["-date", "-id"]
        indexes = [models.Index(fields=["warehouse", "date"])]

    def __str__(self):
        return f"{self.movement_type} {self.quantity} - {self.warehouse.name}"