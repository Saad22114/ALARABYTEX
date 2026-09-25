from django.db import models
from core.models import TimeStampedModel, ActiveModel


class Supplier(TimeStampedModel, ActiveModel):
    name = models.CharField(max_length=150, verbose_name="اسم المورد")
    company_name = models.CharField(max_length=200, blank=True, verbose_name="اسم الشركة")
    phone = models.CharField(max_length=30, blank=True, verbose_name="رقم الهاتف")
    email = models.EmailField(blank=True, verbose_name="البريد الإلكتروني")
    address = models.CharField(max_length=255, blank=True, verbose_name="العنوان")
    city = models.CharField(max_length=100, blank=True, verbose_name="المدينة")
    country = models.CharField(max_length=100, blank=True, verbose_name="الدولة")
    tax_number = models.CharField(max_length=50, blank=True, verbose_name="الرقم الضريبي")
    notes = models.TextField(blank=True, verbose_name="ملاحظات")

    class Meta:
        verbose_name = "مورد"
        verbose_name_plural = "الموردون"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Fabric(TimeStampedModel, ActiveModel):
    class Unit(models.TextChoices):
        YARD = "yard", "ياردة"
        ROLL = "roll", "طاقة"

    name = models.CharField(max_length=200, verbose_name="اسم القماش")
    code = models.CharField(max_length=30, unique=True, blank=True, verbose_name="كود القماش")
    barcode = models.CharField(max_length=64, blank=True, verbose_name="الباركود")
    unit = models.CharField(
        max_length=10,
        choices=Unit.choices,
        default=Unit.YARD,
        verbose_name="الوحدة الأساسية",
    )
    fabric_type = models.CharField(max_length=100, blank=True, verbose_name="نوع القماش")
    color = models.CharField(max_length=60, blank=True, verbose_name="اللون")
    composition = models.CharField(
        max_length=150, blank=True, verbose_name="التركيبة"
    )
    width_cm = models.DecimalField(
        max_digits=6, decimal_places=1, blank=True, null=True, verbose_name="العرض (سم)"
    )
    weight_gsm = models.DecimalField(
        max_digits=6, decimal_places=0, blank=True, null=True, verbose_name="الوزن (جم/م²)"
    )
    origin = models.CharField(max_length=100, blank=True, verbose_name="بلد المنشأ")
    manufacturer = models.CharField(max_length=150, blank=True, verbose_name="الشركة المصنعة")
    supplier = models.ForeignKey(
        "suppliers.Supplier",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fabrics",
        verbose_name="المورد الأساسي",
    )
    allow_roll_sale = models.BooleanField(
        default=True,
        verbose_name="السماح بالبيع بالطاقة",
        help_text="أطفئه لمنع بيع هذا القماش بالطاقة (اللفة) في ورديات البيع",
    )
    roll_sale_overrides = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="البيع بالطاقة حسب الفرع",
        help_text="خريطة رقم الفرع → (true/false) للتحكم في بيع الطاقة لكل فرع على حدة؛ الفرع غير المذكور يتبع الإعداد العام",
    )
    piece_price = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        blank=True,
        null=True,
        verbose_name="سعر القطعة",
        help_text="سعر الطرد/القطعة كاملة؛ يُقسَم على 3.5 ليُحتسب سعر بيع الياردة تلقائياً",
    )
    sale_price_yard = models.DecimalField(
        max_digits=12, decimal_places=3, default=0, verbose_name="سعر بيع الياردة"
    )
    sale_price_roll = models.DecimalField(
        max_digits=12, decimal_places=3, blank=True, null=True, verbose_name="سعر بيع اللفة"
    )
    purchase_price = models.DecimalField(
        max_digits=12, decimal_places=3, default=0, verbose_name="تكلفة الشراء (ياردة)"
    )
    min_sale_yard = models.DecimalField(
        max_digits=12, decimal_places=3, default=0, verbose_name="الحد الأدنى لسعر بيع الياردة"
    )
    min_sale_roll = models.DecimalField(
        max_digits=12, decimal_places=3, blank=True, null=True, verbose_name="الحد الأدنى لسعر بيع اللفة"
    )
    yards_per_roll = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name="ياردات اللفة الواحدة",
        help_text="نسبة التحويل بين اللفات والياردات لضمان اتساق الكميات",
    )
    min_stock = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="حد التنبيه الأدنى",
        help_text="عندما ينخفض رصيد القماش عن هذا الحد يظهر تنبيه نقص في المخزون",
    )
    description = models.TextField(blank=True, verbose_name="التفاصيل")

    class Meta:
        verbose_name = "قماش"
        verbose_name_plural = "الأقمشة"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def roll_sale_allowed_in(self, branch_id=None):
        """هل يُسمح ببيع هذا القماش بالطاقة في فرعٍ معيّن؟

        الفرع غير المذكور في roll_sale_overrides يتبع الإعداد العام allow_roll_sale؛
        والفرع المذكور صراحةً (true/false) يُحتكم إليه مهما كان الإعداد العام.
        """
        key = str(branch_id) if branch_id is not None else None
        overrides = self.roll_sale_overrides or {}
        if key is not None and key in overrides:
            return bool(overrides[key])
        if key is not None and branch_id in overrides:  # للتسامح مع إرسال المعرّف رقماً
            return bool(overrides[branch_id])
        return bool(self.allow_roll_sale)


class LedgerEntry(TimeStampedModel):
    class EntryType(models.TextChoices):
        OPENING = "opening", "رصيد افتتاحي"
        PURCHASE = "purchase", "شراء"
        PAYMENT = "payment", "دفعة"
        RETURN = "return", "مرتجع"
        ADJUSTMENT = "adjustment", "تسوية"

    class PaymentMethod(models.TextChoices):
        CASH = "cash", "كاش"
        BANK = "bank_transfer", "تحويل بنكي"

    supplier = models.ForeignKey(
        "suppliers.Supplier",
        on_delete=models.CASCADE,
        related_name="ledger_entries",
        verbose_name="المورد",
    )
    date = models.DateField(verbose_name="التاريخ")
    entry_type = models.CharField(max_length=12, choices=EntryType.choices, verbose_name="نوع القيد")
    amount = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name="المبلغ (موقّع)"
    )
    description = models.CharField(max_length=255, blank=True, verbose_name="البيان")
    receipt_no = models.CharField(max_length=50, blank=True, verbose_name="رقم السند/الفاتورة")
    payment_method = models.CharField(
        max_length=15,
        choices=PaymentMethod.choices,
        blank=True,
        null=True,
        verbose_name="طريقة الدفع",
    )
    bank_reference = models.CharField(max_length=100, blank=True, verbose_name="رقم الحوالة/المرجع البنكي")
    receiver_name = models.CharField(max_length=150, blank=True, verbose_name="اسم المستلم")
    notes = models.TextField(blank=True, verbose_name="ملاحظات")
    warehouse = models.ForeignKey(
        "warehouses.Warehouse",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_entries",
        verbose_name="مخزن التوريد",
    )
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_entries",
        verbose_name="فرع التوريد",
    )

    @property
    def destination_type(self):
        if self.branch_id:
            return "branch"
        if self.warehouse_id:
            return "warehouse"
        return ""

    @property
    def destination_name(self):
        if self.branch_id:
            return self.branch.name
        if self.warehouse_id:
            return self.warehouse.name
        return ""

    class Meta:
        verbose_name = "قيد دفتر مورد"
        verbose_name_plural = "قيد دفتر الموردين"
        ordering = ["date", "created_at"]
        indexes = [
            models.Index(fields=["supplier", "date"]),
        ]

    def __str__(self):
        return f"{self.supplier.name} - {self.date} - {self.amount}"


class PurchaseItem(TimeStampedModel):
    entry = models.ForeignKey(
        LedgerEntry,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="القيد",
    )
    fabric = models.ForeignKey(
        Fabric,
        on_delete=models.PROTECT,
        related_name="purchase_items",
        verbose_name="القماش",
    )
    quantity_yards = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name="الكمية (ياردة)"
    )
    rolls = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="عدد اللفات"
    )
    unit_price = models.DecimalField(max_digits=12, decimal_places=3, verbose_name="سعر الياردة")
    total = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="الإجمالي")
    warehouse = models.ForeignKey(
        "warehouses.Warehouse",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_items",
        verbose_name="مخزن توريد البند",
    )
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_items",
        verbose_name="فرع توريد البند",
    )

    @property
    def destination_type(self):
        if self.branch_id:
            return "branch"
        if self.warehouse_id:
            return "warehouse"
        return ""

    @property
    def destination_name(self):
        if self.branch_id:
            return self.branch.name
        if self.warehouse_id:
            return self.warehouse.name
        return ""

    class Meta:
        verbose_name = "صنف شراء"
        verbose_name_plural = "أصناف الشراء"
        ordering = ["id"]

    def __str__(self):
        return f"{self.fabric.name} - {self.quantity_yards}"
