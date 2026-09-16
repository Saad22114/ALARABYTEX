from decimal import Decimal

from django.db import transaction
from rest_framework import serializers
from branches.models import Branch
from warehouses.models import Warehouse
from warehouses.services import create_purchase_receipts

from .models import Fabric, LedgerEntry, PurchaseItem, Supplier


class SupplierSerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(default=True)
    current_balance = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True
    )

    class Meta:
        model = Supplier
        fields = [
            "id", "name", "company_name", "phone", "email", "address",
            "city", "country", "tax_number", "notes",
            "is_active", "created_at", "updated_at", "current_balance",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("اسم المورد مطلوب")
        return value


class FabricSerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(default=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True, default="")
    total_rolls = serializers.SerializerMethodField()
    stock_yards = serializers.SerializerMethodField()
    stock_cost_value = serializers.SerializerMethodField()
    low_stock = serializers.SerializerMethodField()
    sale_price_roll_display = serializers.DecimalField(
        max_digits=12, decimal_places=3, read_only=True
    )
    min_sale_roll_display = serializers.DecimalField(
        max_digits=12, decimal_places=3, read_only=True
    )
    profit_yard = serializers.DecimalField(max_digits=12, decimal_places=3, read_only=True)
    profit_margin_pct = serializers.SerializerMethodField()

    class Meta:
        model = Fabric
        fields = [
            "id", "name", "code", "barcode", "unit",
            "fabric_type", "color", "composition",
            "width_cm", "weight_gsm", "origin", "manufacturer",
            "supplier", "supplier_name",
            "sale_price_yard", "sale_price_roll", "purchase_price",
            "min_sale_yard", "min_sale_roll",
            "sale_price_roll_display", "min_sale_roll_display",
            "profit_yard", "profit_margin_pct",
            "total_rolls", "stock_yards", "stock_cost_value", "low_stock",
            "yards_per_roll", "min_stock", "description", "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("اسم القماش مطلوب")
        return value

    def _display_roll(self, override, yards_per_roll, base):
        if override is not None:
            return override
        if yards_per_roll:
            return (base or 0) * yards_per_roll
        return None

    def validate(self, attrs):
        sale_yard = attrs.get("sale_price_yard")
        min_yard = attrs.get("min_sale_yard")
        if min_yard and sale_yard is not None and min_yard > sale_yard:
            raise serializers.ValidationError(
                {"min_sale_yard": "الحد الأدنى لسعر بيع الياردة لا يمكن أن يتجاوز سعر البيع"}
            )
        sale_roll = attrs.get("sale_price_roll")
        min_roll = attrs.get("min_sale_roll")
        if min_roll and sale_roll is not None and min_roll > sale_roll:
            raise serializers.ValidationError(
                {"min_sale_roll": "الحد الأدنى لسعر بيع اللفة لا يمكن أن يتجاوز سعر البيع"}
            )
        return attrs

    def get_total_rolls(self, obj):
        return obj.total_rolls if hasattr(obj, "total_rolls") else 0

    def get_stock_yards(self, obj):
        return obj.stock_yards if hasattr(obj, "stock_yards") else 0

    def get_stock_cost_value(self, obj):
        return obj.stock_cost_value if hasattr(obj, "stock_cost_value") else 0

    def get_low_stock(self, obj):
        min_stock = obj.min_stock or Decimal("0")
        if min_stock <= 0:
            return False
        yards = obj.stock_yards if hasattr(obj, "stock_yards") else 0
        return (yards or 0) < min_stock

    def get_profit_margin_pct(self, obj):
        cost = obj.purchase_price or Decimal("0")
        sale = obj.sale_price_yard or Decimal("0")
        if sale <= 0:
            return 0
        return float(((sale - cost) / sale) * 100)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        yards_per_roll = instance.yards_per_roll
        sale_roll = self._display_roll(
            instance.sale_price_roll, yards_per_roll, instance.sale_price_yard
        )
        min_roll = self._display_roll(
            instance.min_sale_roll, yards_per_roll, instance.min_sale_yard
        )
        data["sale_price_roll_display"] = sale_roll
        data["min_sale_roll_display"] = min_roll
        data["profit_yard"] = (instance.sale_price_yard or 0) - (instance.purchase_price or 0)
        return data


class PurchaseItemSerializer(serializers.ModelSerializer):
    fabric_name = serializers.CharField(source="fabric.name", read_only=True)
    fabric_unit = serializers.CharField(source="fabric.unit", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True, default="")
    branch_name = serializers.CharField(source="branch.name", read_only=True, default="")

    class Meta:
        model = PurchaseItem
        fields = [
            "id", "fabric", "fabric_name", "fabric_unit",
            "quantity_yards", "rolls", "unit_price", "total",
            "warehouse", "warehouse_name", "branch", "branch_name",
            "destination_type", "destination_name",
        ]
        read_only_fields = ["id", "destination_type", "destination_name"]


class LedgerEntrySerializer(serializers.ModelSerializer):
    entry_type_label = serializers.CharField(source="get_entry_type_display", read_only=True)
    payment_method_label = serializers.SerializerMethodField()
    debit = serializers.SerializerMethodField()
    credit = serializers.SerializerMethodField()
    running_balance = serializers.SerializerMethodField()
    items = PurchaseItemSerializer(many=True, read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True, default="")
    branch_name = serializers.CharField(source="branch.name", read_only=True, default="")
    destination_name = serializers.SerializerMethodField()
    destination_type = serializers.SerializerMethodField()
    goods_receipt_number = serializers.SerializerMethodField()
    goods_receipt_status = serializers.SerializerMethodField()

    class Meta:
        model = LedgerEntry
        fields = [
            "id", "date", "entry_type", "entry_type_label",
            "amount", "debit", "credit", "running_balance",
            "description", "receipt_no", "payment_method",
            "payment_method_label", "bank_reference", "receiver_name", "notes",
            "items", "created_at",
            "warehouse", "warehouse_name", "branch", "branch_name",
            "destination_type", "destination_name",
            "goods_receipt_number", "goods_receipt_status",
        ]
        read_only_fields = ["id", "created_at"]

    def get_debit(self, obj):
        return obj.amount if obj.amount > 0 else Decimal("0")

    def get_credit(self, obj):
        return -obj.amount if obj.amount < 0 else Decimal("0")

    def get_payment_method_label(self, obj):
        if obj.payment_method:
            return obj.get_payment_method_display()
        return None

    def get_running_balance(self, obj):
        return getattr(obj, "running_balance", None)

    def _item_destinations(self, obj):
        return obj.items.select_related("warehouse", "branch").all()

    def get_destination_name(self, obj):
        if obj.warehouse_id:
            return obj.warehouse.name
        if obj.branch_id:
            return obj.branch.name
        seen = set()
        names = []
        for it in self._item_destinations(obj):
            name = it.destination_name
            if name and name not in seen:
                seen.add(name)
                names.append(name)
        return "، ".join(names)

    def get_destination_type(self, obj):
        if obj.warehouse_id:
            return "warehouse"
        if obj.branch_id:
            return "branch"
        types = set()
        for it in self._item_destinations(obj):
            if it.destination_type:
                types.add(it.destination_type)
        if len(types) == 1:
            return types.pop()
        return "mixed" if types else ""

    def get_goods_receipt_number(self, obj):
        numbers = [gr.number for gr in obj.goods_receipts.all()]
        return "، ".join(numbers)

    def get_goods_receipt_status(self, obj):
        grs = list(obj.goods_receipts.all())
        if not grs:
            return ""
        if all(gr.status == "posted" for gr in grs):
            return "posted"
        return grs[0].status


class PurchaseItemInputSerializer(serializers.Serializer):
    fabric = serializers.PrimaryKeyRelatedField(queryset=Fabric.objects.all())
    quantity_yards = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, default=Decimal("0")
    )
    rolls = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, default=Decimal("0")
    )
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=3, required=False)
    total = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)
    warehouse = serializers.PrimaryKeyRelatedField(
        queryset=Warehouse.objects.filter(is_active=True), required=False, allow_null=True
    )
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all(), required=False, allow_null=True)


class LedgerEntryCreateSerializer(serializers.Serializer):
    entry_type = serializers.ChoiceField(choices=LedgerEntry.EntryType.choices)
    date = serializers.DateField()
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)
    description = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    receipt_no = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")
    payment_method = serializers.ChoiceField(
        choices=LedgerEntry.PaymentMethod.choices, required=False
    )
    bank_reference = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    receiver_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    payment_amount = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)
    total = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)
    items = PurchaseItemInputSerializer(many=True, required=False)
    warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.filter(is_active=True), required=False, allow_null=True)
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all(), required=False, allow_null=True)

    def _item_total(self, item):
        explicit_total = item.get("total")
        if explicit_total is not None:
            return explicit_total
        quantity = item.get("quantity_yards") or Decimal("0")
        unit_price = item.get("unit_price")
        if unit_price is None:
            unit_price = item["fabric"].purchase_price
        return quantity * unit_price

    def validate(self, attrs):
        data = dict(attrs)
        entry_type = data["entry_type"]
        amount = data.get("amount")
        items = data.get("items") or []
        total_override = data.get("total")
        payment_amount = data.get("payment_amount")
        warehouse = data.get("warehouse")
        branch = data.get("branch")
        has_wh = warehouse is not None
        has_br = branch is not None
        if has_wh and has_br:
            raise serializers.ValidationError("حدد وجهة توريد واحدة فقط: إمّا مخزن أَو فرع")

        immediate_payment = None

        if entry_type == LedgerEntry.EntryType.PURCHASE:
            for item in items:
                if item.get("warehouse") is not None and item.get("branch") is not None:
                    raise serializers.ValidationError(
                        "حدد وجهة واحدة لكل بند: مخزن أو فرع — ولا يمكن تحديدهما معاً"
                    )
            if total_override is not None:
                total = total_override
            elif items:
                total = sum(self._item_total(item) for item in items)
            else:
                raise serializers.ValidationError("مطلوب إجمالي الشراء أو الأصناف")
            if total <= 0:
                raise serializers.ValidationError("إجمالي الشراء يجب أن يكون أكبر من صفر")
            computed_amount = total
            if payment_amount is not None and payment_amount > 0:
                if not data.get("payment_method"):
                    raise serializers.ValidationError("طريقة الدفع مطلوبة لسداد فوري")
                if payment_amount > total:
                    raise serializers.ValidationError("مبلغ السداد الفوري أكبر من إجمالي الشراء")
                immediate_payment = payment_amount
        elif entry_type == LedgerEntry.EntryType.PAYMENT:
            if amount is None or amount <= 0:
                raise serializers.ValidationError("مبلغ الدفع يجب أن يكون أكبر من صفر")
            if not data.get("payment_method"):
                raise serializers.ValidationError("طريقة الدفع مطلوبة")
            computed_amount = -amount
        elif entry_type == LedgerEntry.EntryType.RETURN:
            if items:
                total = sum(self._item_total(item) for item in items)
            else:
                total = amount or Decimal("0")
            if total <= 0:
                raise serializers.ValidationError("مبلغ المرتجع يجب أن يكون أكبر من صفر")
            computed_amount = -total
        else:
            if amount is None:
                raise serializers.ValidationError("المبلغ مطلوب")
            computed_amount = amount

        data["amount"] = computed_amount
        data.pop("total", None)
        data.pop("payment_amount", None)
        data.pop("items", None)
        data["_items"] = items
        data["_payment_amount"] = immediate_payment
        return data

    def create(self, validated_data):
        with transaction.atomic():
            supplier = self.context["supplier"]
            items = validated_data.pop("_items", [])
            payment_amount = validated_data.pop("_payment_amount", None)
            receipt_no = validated_data.get("receipt_no", "")
            entry_type = validated_data["entry_type"]
            warehouse = validated_data.pop("warehouse", None)
            branch = validated_data.pop("branch", None)
            # الوجهة خاصة بقيد الشراء فقط
            if entry_type != LedgerEntry.EntryType.PURCHASE:
                warehouse = None
                branch = None

            entry = LedgerEntry.objects.create(
                supplier=supplier, warehouse=warehouse, branch=branch, **validated_data
            )

            for item in items:
                fabric = item["fabric"]
                quantity_yards = item.get("quantity_yards", Decimal("0"))
                rolls = item.get("rolls", Decimal("0"))
                unit_price = item.get("unit_price")
                if unit_price is None:
                    unit_price = fabric.purchase_price
                total = item.get("total")
                if total is None:
                    total = quantity_yards * unit_price
                item_warehouse = item.get("warehouse")
                item_branch = item.get("branch")
                if entry_type != LedgerEntry.EntryType.PURCHASE:
                    item_warehouse = None
                    item_branch = None
                PurchaseItem.objects.create(
                    entry=entry,
                    fabric=fabric,
                    quantity_yards=quantity_yards,
                    rolls=rolls,
                    unit_price=unit_price,
                    total=total,
                    warehouse=item_warehouse,
                    branch=item_branch,
                )
                if unit_price > 0 and fabric.purchase_price != unit_price:
                    fabric.purchase_price = unit_price
                    fabric.save(update_fields=["purchase_price"])

            if payment_amount:
                LedgerEntry.objects.create(
                    supplier=supplier,
                    date=validated_data["date"],
                    entry_type=LedgerEntry.EntryType.PAYMENT,
                    amount=-payment_amount,
                    receipt_no=receipt_no,
                    description=f"سداد فوري - {receipt_no or ''}",
                    payment_method=validated_data["payment_method"],
                    bank_reference=validated_data.get("bank_reference", ""),
                    receiver_name=validated_data.get("receiver_name", ""),
                )

            # توريد البضاعة المشتراة تلقائياً إلى وجهة كل بند (مخزن أو فرع) وإنشاء اللفات
            if entry_type == LedgerEntry.EntryType.PURCHASE:
                try:
                    create_purchase_receipts(entry, date=entry.date)
                except Exception as exc:
                    raise serializers.ValidationError(f"تعذر توريد البضاعة: {exc}")

            return entry