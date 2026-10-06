from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from rest_framework import serializers

from suppliers.models import Fabric, Supplier
from sale_sessions.models import Employee
from branches.models import Branch
from core.branch_scope import assert_write_branch_allowed
from core.permissions import get_request_employee

from .models import (
    DocumentSequence,
    FabricRoll,
    GoodsReceipt,
    GoodsReceiptItem,
    StockAdjustment,
    StockAdjustmentItem,
    StockCount,
    StockCountItem,
    StockMovement,
    StockOpening,
    StockOpeningItem,
    StockTransfer,
    StockTransferItem,
    Warehouse,
)
from .services import public_summary


class WarehouseSerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(default=True)
    total_rolls = serializers.IntegerField(read_only=True)
    total_yards = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True, default="")
    is_branch_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Warehouse
        fields = [
            "id", "name", "code", "location", "phone", "manager_name", "notes",
            "branch", "branch_name", "is_branch_stock",
            "is_active", "total_rolls", "total_yards", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "branch", "created_at", "updated_at"]

    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("اسم المخزن مطلوب")
        return value


class FabricRollSerializer(serializers.ModelSerializer):
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    fabric_name = serializers.CharField(source="fabric.name", read_only=True)
    fabric_unit = serializers.CharField(source="fabric.unit", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = FabricRoll
        fields = [
            "id", "code", "warehouse", "warehouse_name", "fabric", "fabric_name",
            "fabric_unit", "yards", "remaining_yards", "unit_cost", "status",
            "status_label", "received_date", "notes", "created_at",
        ]
        read_only_fields = ["id", "code", "remaining_yards", "created_at"]

    def validate(self, attrs):
        request = self.context.get("request")
        if request is not None:
            assert_write_branch_allowed(
                request,
                warehouses=[attrs.get("warehouse") or getattr(self.instance, "warehouse", None)],
            )
        return attrs


class StockMovementSerializer(serializers.ModelSerializer):
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    fabric_name = serializers.CharField(source="fabric.name", read_only=True)
    movement_type_label = serializers.CharField(source="get_movement_type_display", read_only=True)
    roll_code = serializers.CharField(source="roll.code", read_only=True, default="")

    class Meta:
        model = StockMovement
        fields = [
            "id", "date", "warehouse", "warehouse_name", "fabric", "fabric_name",
            "roll", "roll_code", "movement_type", "movement_type_label",
            "quantity", "balance_before", "balance_after",
            "reference_type", "reference_id", "reference_no",
            "notes", "created_at",
        ]
        read_only_fields = fields


def _item_tuples(items_data, support_mode=False):
    """يحوّل إدخالات العناصر إلى قيم مشتركة مع التحقق."""
    rows = []
    for it in items_data:
        mode = it.get("quantity_mode", "yard") if support_mode else "yard"
        if mode not in ("yard", "roll"):
            raise serializers.ValidationError("طريقة الكمية غير صالحة")
        if mode == "roll":
            rolls_count = int(it.get("rolls_count", 0) or 0)
            if rolls_count < 1:
                raise serializers.ValidationError("عدد اللفات يجب أن يكون 1 على الأقل")
            yards = Decimal("0")
        else:
            rolls_count = int(it.get("rolls_count", 0) or 0)
            yards = Decimal(str(it.get("yards", "0")))
            if yards <= 0:
                raise serializers.ValidationError("الياردات يجب أن تكون أكبر من صفر")
        fabric = it.get("fabric")
        if isinstance(fabric, (int, str)):
            try:
                fabric = Fabric.objects.get(pk=fabric)
            except Fabric.DoesNotExist:
                raise serializers.ValidationError("قماش غير موجود")
        rows.append({
            "fabric": fabric,
            "yards": yards,
            "rolls_count": rolls_count,
            "unit_price": Decimal(str(it.get("unit_price", "0") or "0")),
            "quantity_mode": mode,
        })
    return rows


def _validate_transfer_stock(source_warehouse, items):
    """تحقق من رصيد المصدر قبل إنشاء الطلب، مع محاكاة البنود حسب ترتيب تنفيذها."""
    stock_by_fabric = {}
    errors = []
    for item in items:
        fabric = item["fabric"]
        if fabric.pk not in stock_by_fabric:
            stock_by_fabric[fabric.pk] = list(
                FabricRoll.objects.filter(
                    warehouse=source_warehouse,
                    fabric=fabric,
                    status=FabricRoll.Status.AVAILABLE,
                    remaining_yards__gt=0,
                )
                .order_by("created_at", "id")
                .values_list("remaining_yards", flat=True)
            )
        rolls = stock_by_fabric[fabric.pk]
        if item["quantity_mode"] == StockTransferItem.QuantityMode.ROLL:
            requested = item["rolls_count"]
            if len(rolls) < requested:
                errors.append(
                    f"قماش «{fabric.name}»: المتوفر {len(rolls)} لفة والمطلوب {requested}"
                )
            else:
                del rolls[:requested]
            continue

        requested_yards = item["yards"]
        available_yards = sum(rolls, Decimal("0"))
        if available_yards < requested_yards:
            errors.append(
                f"قماش «{fabric.name}»: المتوفر {available_yards} ياردة والمطلوب {requested_yards}"
            )
        remaining = requested_yards
        while rolls and remaining > 0:
            taken = min(rolls[0], remaining)
            rolls[0] -= taken
            remaining -= taken
            if rolls[0] <= 0:
                rolls.pop(0)

    if errors:
        raise serializers.ValidationError({"items": errors})


class GoodsReceiptItemSerializer(serializers.ModelSerializer):
    fabric_name = serializers.CharField(source="fabric.name", read_only=True)

    class Meta:
        model = GoodsReceiptItem
        fields = ["id", "fabric", "fabric_name", "rolls_count", "yards", "unit_price", "total"]
        read_only_fields = ["id"]


class GoodsReceiptSerializer(serializers.ModelSerializer):
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True, default="")
    branch_name = serializers.CharField(source="branch.name", read_only=True, default="")
    dest_type = serializers.SerializerMethodField()
    dest_name = serializers.SerializerMethodField()
    supplier_name = serializers.CharField(source="supplier.name", read_only=True, default="")
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    items = GoodsReceiptItemSerializer(many=True, read_only=True)
    total_yards = serializers.SerializerMethodField()
    total_value = serializers.SerializerMethodField()
    purchase_entry_number = serializers.CharField(source="purchase_entry.receipt_no", read_only=True, default="")

    class Meta:
        model = GoodsReceipt
        fields = [
            "id", "number", "warehouse", "warehouse_name", "branch", "branch_name",
            "dest_type", "dest_name", "supplier", "supplier_name",
            "purchase_entry", "purchase_entry_number",
            "date", "supplier_receipt_no", "status", "status_label", "notes",
            "items", "total_yards", "total_value", "created_at",
        ]
        read_only_fields = ["id", "number", "status", "created_at"]

    def get_dest_type(self, obj):
        return "branch" if obj.branch_id else "warehouse"

    def get_dest_name(self, obj):
        return obj.branch.name if obj.branch_id else (obj.warehouse.name if obj.warehouse_id else "")

    def get_total_yards(self, obj):
        return sum((i.yards for i in obj.items.all()), Decimal("0"))

    def get_total_value(self, obj):
        return sum((i.total for i in obj.items.all()), Decimal("0"))


class GoodsReceiptWriteSerializer(serializers.Serializer):
    warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all(), required=False, allow_null=True)
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all(), required=False, allow_null=True)
    supplier = serializers.PrimaryKeyRelatedField(queryset=Supplier.objects.all(), required=False, allow_null=True)
    date = serializers.DateField()
    supplier_receipt_no = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    items = serializers.ListField(child=serializers.DictField(), required=False)

    def validate(self, attrs):
        warehouse = attrs.get("warehouse")
        branch = attrs.get("branch")
        if bool(warehouse) == bool(branch):
            raise serializers.ValidationError("حدد وجهة واحدة للاستلام: إمّا مخزن أَو فرع")
        request = self.context.get("request")
        if request is not None:
            assert_write_branch_allowed(
                request,
                branches=[branch if branch is not None else (warehouse.branch if warehouse else None)],
            )
        return attrs

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError("أضف صنفاً واحداً على الأقل")
        return _item_tuples(items)

    def create(self, validated_data):
        with transaction.atomic():
            receipt = GoodsReceipt.objects.create(
                number=DocumentSequence.next_number("GR"),
                warehouse=validated_data.get("warehouse"),
                branch=validated_data.get("branch"),
                supplier=validated_data.get("supplier"),
                date=validated_data["date"],
                supplier_receipt_no=validated_data.get("supplier_receipt_no", ""),
                notes=validated_data.get("notes", ""),
            )
            for it in validated_data["items"]:
                GoodsReceiptItem.objects.create(
                    receipt=receipt, fabric=it["fabric"], rolls_count=it["rolls_count"],
                    yards=it["yards"], unit_price=it["unit_price"],
                    total=(it["yards"] * it["unit_price"]).quantize(Decimal("0.01")),
                )
        return receipt

    def update(self, instance, validated_data):
        if instance.status != GoodsReceipt.Status.DRAFT:
            raise serializers.ValidationError("لا يمكن تعديل سند استلام مُرحّل")
        with transaction.atomic():
            instance.warehouse = validated_data.get("warehouse", instance.warehouse)
            instance.branch = validated_data.get("branch", instance.branch)
            instance.supplier = validated_data.get("supplier", instance.supplier)
            instance.date = validated_data.get("date", instance.date)
            instance.supplier_receipt_no = validated_data.get("supplier_receipt_no", instance.supplier_receipt_no)
            instance.notes = validated_data.get("notes", instance.notes)
            instance.save()
            if "items" in validated_data:
                instance.items.all().delete()
                for it in validated_data["items"]:
                    GoodsReceiptItem.objects.create(
                        receipt=instance, fabric=it["fabric"], rolls_count=it["rolls_count"],
                        yards=it["yards"], unit_price=it["unit_price"],
                        total=(it["yards"] * it["unit_price"]).quantize(Decimal("0.01")),
                    )
        return instance


class StockTransferItemSerializer(serializers.ModelSerializer):
    fabric_name = serializers.CharField(source="fabric.name", read_only=True)
    quantity_mode_label = serializers.CharField(source="get_quantity_mode_display", read_only=True)

    class Meta:
        model = StockTransferItem
        fields = ["id", "fabric", "fabric_name", "yards", "rolls_count", "quantity_mode", "quantity_mode_label"]
        read_only_fields = ["id"]


class StockTransferSerializer(serializers.ModelSerializer):
    from_warehouse_name = serializers.CharField(source="from_warehouse.name", read_only=True)
    from_branch_name = serializers.CharField(source="from_branch.name", read_only=True, default="")
    source_type = serializers.SerializerMethodField()
    source_name = serializers.SerializerMethodField()
    to_warehouse_name = serializers.CharField(source="to_warehouse.name", read_only=True, default="")
    to_branch_name = serializers.CharField(source="to_branch.name", read_only=True, default="")
    dest_type = serializers.SerializerMethodField()
    dest_name = serializers.SerializerMethodField()
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    items = StockTransferItemSerializer(many=True, read_only=True)
    total_yards = serializers.SerializerMethodField()

    class Meta:
        model = StockTransfer
        fields = [
            "id", "number", "from_warehouse", "from_warehouse_name",
            "from_branch", "from_branch_name", "source_type", "source_name",
            "to_warehouse", "to_warehouse_name", "to_branch", "to_branch_name",
            "dest_type", "dest_name", "date", "status", "status_label",
            "requested_by", "approved_by", "requested_at", "approved_at", "completed_at",
            "rejection_reason", "rejected_by", "rejected_at",
            "cancellation_reason", "cancelled_by", "cancelled_at",
            "reversal_reason", "reversed_by", "reversed_at",
            "notes", "items", "total_yards", "created_at",
        ]
        read_only_fields = ["id", "number", "status", "requested_at", "approved_at", "completed_at", "created_at"]

    def get_dest_type(self, obj):
        return "branch" if obj.to_branch_id else "warehouse"

    def get_source_type(self, obj):
        return "branch" if obj.from_branch_id else "warehouse"

    def get_source_name(self, obj):
        return obj.from_branch.name if obj.from_branch_id else obj.from_warehouse.name

    def get_dest_name(self, obj):
        return obj.to_branch.name if obj.to_branch_id else (obj.to_warehouse.name if obj.to_warehouse_id else "")

    def get_total_yards(self, obj):
        return StockTransferItem.objects.filter(transfer=obj).aggregate(t=Sum("yards"))["t"] or Decimal("0")


class StockTransferWriteSerializer(serializers.Serializer):
    from_warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all(), required=False, allow_null=True)
    from_branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all(), required=False, allow_null=True)
    to_warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all(), required=False, allow_null=True)
    to_branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all(), required=False, allow_null=True)
    date = serializers.DateField()
    requested_by = serializers.CharField(read_only=True)
    requested_by_employee = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.filter(is_active=True), required=False, write_only=True,
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    items = serializers.ListField(child=serializers.DictField(), required=False)

    def validate(self, attrs):
        partial_update = bool(self.instance and self.partial)
        to_warehouse = attrs.get("to_warehouse", self.instance.to_warehouse if partial_update else None)
        to_branch = attrs.get("to_branch", self.instance.to_branch if partial_update else None)
        if self.instance and "from_warehouse" not in attrs and "from_branch" not in attrs:
            source_warehouse, source_branch = self.instance.from_warehouse, self.instance.from_branch
        else:
            source_warehouse = attrs.get("from_warehouse")
            source_branch = attrs.get("from_branch")
        if not source_warehouse and not source_branch:
            raise serializers.ValidationError({"from_warehouse": "حدد المخزن أو الفرع المُرسِل"})
        if source_warehouse and source_branch and source_warehouse.branch_id != source_branch.pk:
            raise serializers.ValidationError({"from_warehouse": "مخزن المصدر لا يتبع الفرع المحدد"})
        if source_warehouse and not source_branch and source_warehouse.branch_id:
            source_branch = source_warehouse.branch
            attrs["from_branch"] = source_branch
        if bool(to_warehouse) == bool(to_branch):
            raise serializers.ValidationError("حدد وجهة واحدة للتحويل: إمّا مخزن أَو فرع")
        if source_warehouse and to_warehouse and source_warehouse.pk == to_warehouse.pk:
            raise serializers.ValidationError("لا يمكن التحويل من مخزن إلى نفسه")
        if source_branch and (
            (to_branch and source_branch.pk == to_branch.pk)
            or (to_warehouse and to_warehouse.branch_id == source_branch.pk)
        ):
            raise serializers.ValidationError("لا يمكن التحويل إلى مخزن أو فرع المصدر نفسه")
        request = self.context.get("request")
        if request is not None:
            actor = get_request_employee(request)
            requested_employee = attrs.get("requested_by_employee")
            can_choose_requester = actor and actor.role in (Employee.Role.ADMIN, Employee.Role.SUPERVISOR)
            if actor and not can_choose_requester and requested_employee and requested_employee.pk != actor.pk:
                raise serializers.ValidationError({"requested_by_employee": "يمكنك تسجيل الطلب باسمك فقط"})
            assert_write_branch_allowed(
                request,
                branches=[source_branch, to_branch],
                warehouses=[source_warehouse, to_warehouse],
            )
        if not attrs.get("items") and not (self.instance and self.instance.items.exists()):
            raise serializers.ValidationError("أضف صنفاً واحداً على الأقل")
        if "items" in attrs:
            attrs["items"] = _item_tuples(attrs["items"], support_mode=True)
        if self.instance is None:
            stock_warehouse = source_warehouse
            if source_branch and stock_warehouse is None:
                stock_warehouse = (
                    Warehouse.objects.filter(branch=source_branch).first()
                    or Warehouse.objects.filter(code=f"BR-{source_branch.code}").first()
                )
            if stock_warehouse is not None:
                _validate_transfer_stock(stock_warehouse, attrs["items"])
        return attrs

    def create(self, validated_data):
        with transaction.atomic():
            request = self.context.get("request")
            actor = get_request_employee(request) if request is not None else None
            requested_employee = validated_data.pop("requested_by_employee", None)
            can_choose_requester = actor and actor.role in (Employee.Role.ADMIN, Employee.Role.SUPERVISOR)
            requester = requested_employee if can_choose_requester and requested_employee else actor
            source_branch = validated_data.get("from_branch")
            source_warehouse = validated_data.get("from_warehouse")
            if source_branch:
                source_warehouse = source_warehouse or Warehouse.for_branch(source_branch)
            transfer = StockTransfer.objects.create(
                number=DocumentSequence.next_number("TR"),
                from_warehouse=source_warehouse,
                from_branch=source_branch,
                to_warehouse=validated_data.get("to_warehouse"),
                to_branch=validated_data.get("to_branch"),
                date=validated_data["date"],
                requested_by=requester.name if requester else "",
                notes=validated_data.get("notes", ""),
            )
            for it in validated_data["items"]:
                StockTransferItem.objects.create(
                    transfer=transfer, fabric=it["fabric"], yards=it["yards"],
                    rolls_count=it["rolls_count"], quantity_mode=it["quantity_mode"],
                )
        return transfer

    def update(self, instance, validated_data):
        if instance.status not in (StockTransfer.Status.DRAFT, StockTransfer.Status.REJECTED):
            raise serializers.ValidationError("لا يمكن تعديل التحويل في هذه الحالة")
        with transaction.atomic():
            request = self.context.get("request")
            actor = get_request_employee(request) if request is not None else None
            requested_employee = validated_data.pop("requested_by_employee", None)
            if requested_employee and actor and actor.role in (Employee.Role.ADMIN, Employee.Role.SUPERVISOR):
                instance.requested_by = requested_employee.name
            elif actor:
                instance.requested_by = actor.name
            if "from_branch" in validated_data:
                instance.from_branch = validated_data["from_branch"]
                if instance.from_branch:
                    instance.from_warehouse = Warehouse.for_branch(instance.from_branch)
                else:
                    instance.from_warehouse = validated_data.get("from_warehouse", instance.from_warehouse)
            elif "from_warehouse" in validated_data:
                instance.from_warehouse = validated_data["from_warehouse"]
                instance.from_branch = None
            instance.to_warehouse = validated_data.get("to_warehouse", instance.to_warehouse)
            instance.to_branch = validated_data.get("to_branch", instance.to_branch)
            instance.date = validated_data.get("date", instance.date)
            instance.notes = validated_data.get("notes", instance.notes)
            instance.save()
            if "items" in validated_data:
                instance.items.all().delete()
                for it in validated_data["items"]:
                    StockTransferItem.objects.create(
                        transfer=instance, fabric=it["fabric"], yards=it["yards"],
                        rolls_count=it["rolls_count"], quantity_mode=it["quantity_mode"],
                    )
        return instance


class StockAdjustmentItemSerializer(serializers.ModelSerializer):
    fabric_name = serializers.CharField(source="fabric.name", read_only=True)

    class Meta:
        model = StockAdjustmentItem
        fields = ["id", "fabric", "fabric_name", "yards", "rolls_count"]
        read_only_fields = ["id"]


class StockAdjustmentSerializer(serializers.ModelSerializer):
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    reason_label = serializers.CharField(source="get_reason_display", read_only=True, default="")
    direction_label = serializers.CharField(source="get_direction_display", read_only=True)
    items = StockAdjustmentItemSerializer(many=True, read_only=True)

    class Meta:
        model = StockAdjustment
        fields = [
            "id", "number", "warehouse", "warehouse_name", "date", "reason",
            "reason_label", "direction", "direction_label", "notes",
            "items", "created_at",
        ]
        read_only_fields = ["id", "number", "created_at"]


class StockAdjustmentWriteSerializer(serializers.Serializer):
    warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all())
    date = serializers.DateField()
    reason = serializers.ChoiceField(choices=StockAdjustment.Reason.choices, required=False, allow_blank=True)
    direction = serializers.ChoiceField(choices=StockAdjustment.Direction.choices)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    items = serializers.ListField(child=serializers.DictField(), required=False)

    def validate(self, attrs):
        request = self.context.get("request")
        if request is not None:
            assert_write_branch_allowed(request, warehouses=[attrs.get("warehouse")])
        return attrs

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError("أضف صنفاً واحداً على الأقل")
        return _item_tuples(items)

    def create(self, validated_data):
        with transaction.atomic():
            adjustment = StockAdjustment.objects.create(
                number=DocumentSequence.next_number("ADJ"),
                warehouse=validated_data["warehouse"],
                date=validated_data["date"],
                reason=validated_data.get("reason", ""),
                direction=validated_data["direction"],
                notes=validated_data.get("notes", ""),
            )
            for it in validated_data["items"]:
                StockAdjustmentItem.objects.create(
                    adjustment=adjustment, fabric=it["fabric"], yards=it["yards"],
                    rolls_count=it["rolls_count"],
                )
        return adjustment


class StockCountItemSerializer(serializers.ModelSerializer):
    """سطر جرد واحد.

    ``reveal_system=False`` يُسقط الرصيد الدفتري والفرق من الردّ: في الجرد
    المغلق هما ما يفسد العدّ، ورؤيةُ رقمٍ يقارَن به العدّادُ تجعل الجرد
   قياسًا لا مطابقةً. لا نحذف الحقول من الواجهة بل نخفيها، فتبقى
    الشاشةُ تطلب الرصيدَ بلا أن يعرضه، ويفهم المطوّرُ أن الحقل محجوب لا
    مُهمَل.
    """

    fabric_name = serializers.CharField(source="fabric.name", read_only=True)
    fabric_code = serializers.CharField(source="fabric.code", read_only=True)
    # السعران يُقرآن من القماش لحظة العرض، لا من سطر الجرد: سطر الجرد
    # لا يحمل سعراً، ولو حمله لتقادما مع تغيّر سعر القماش. والأسعار
    # بياناتٌ ثابتة لا إجابةُ الجرد، فبقاءُها ظاهراً في الجرد المغلق
    # لا يُفسد سرّيةَ العدّ.
    purchase_price = serializers.DecimalField(
        source="fabric.purchase_price",
        max_digits=12,
        decimal_places=3,
        read_only=True,
    )
    sale_price = serializers.DecimalField(
        source="fabric.sale_price_yard",
        max_digits=12,
        decimal_places=3,
        read_only=True,
    )
    difference = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    is_variance = serializers.BooleanField(read_only=True)
    counted = serializers.SerializerMethodField()

    def __init__(self, *args, **kwargs):
        # The default is disclosure: this serializer is reused outside the
        # blind count, so a missing key there would be a bug, not a policy.
        self._reveal_system = kwargs.pop("reveal_system", True)
        super().__init__(*args, **kwargs)

    def get_counted(self, obj):
        return obj.counted_yards is not None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self._reveal_system:
            for field in ("system_yards", "difference", "is_variance"):
                data.pop(field, None)
        return data

    class Meta:
        model = StockCountItem
        fields = [
            "id", "fabric", "fabric_name", "fabric_code", "purchase_price",
            "sale_price", "system_yards", "counted_yards", "difference",
            "is_variance", "counted", "note",
        ]
        read_only_fields = ["id", "system_yards"]


class StockCountSummarySerializer(serializers.Serializer):
    """ما يقرّر مدير المخزن «هل انتهى الجرد»."""

    items = serializers.IntegerField()
    counted = serializers.IntegerField()
    pending = serializers.IntegerField()
    variances = serializers.IntegerField()
    net_yards = serializers.FloatField()
    value = serializers.FloatField()
    complete = serializers.BooleanField()


class StockCountSerializer(serializers.ModelSerializer):
    """جلسة الجرد كاملة: أصنافها وملخّصها.

    الأصناف تُمرّر عبر دالّة لا كحقلٍ عادي، لأن إخفاء الجرد المغلق
    يحتاج حالة الجلسة (الوقت والحالة) ليقرر ما يُخفى، وهي لا تصل إلى
    المسلسل السطريّ.
    """

    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    counted_by_name = serializers.CharField(
        source="counted_by.name", read_only=True, allow_null=True, default="",
    )
    hides_system = serializers.BooleanField(source="hides_system_balance", read_only=True)
    items = serializers.SerializerMethodField()
    summary = serializers.SerializerMethodField()

    def get_items(self, obj):
        return StockCountItemSerializer(
            obj.items.select_related("fabric").all(),
            many=True,
            reveal_system=not obj.hides_system_balance,
        ).data

    def get_summary(self, obj):
        return public_summary(obj)

    class Meta:
        model = StockCount
        fields = [
            "id", "number", "warehouse", "warehouse_name", "date", "status",
            "status_label", "notes", "blind", "hides_system", "counted_by",
            "counted_by_name", "items", "summary", "created_at",
        ]
        read_only_fields = ["id", "number", "status", "created_at"]


class StockCountListSerializer(serializers.ModelSerializer):
    """صفٌّ واحد في قائمة الجلسات — بلا أصناف.

    القائمة كانت تُحمّل أصناف كل جلسة: عشرون جلسة بأربعين صنفاً = ثمانمئة
    سطر في طلبٍ واحد، لعرض خمسة أعمدة. والملخّص وحده يجيب «كم رُصد وكم
    فروق» بلا أن يمرّ سطرٌ واحدٍ من الأصناف عبر الشبكة.
    """

    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    counted_by_name = serializers.CharField(
        source="counted_by.name", read_only=True, allow_null=True, default="",
    )
    hides_system = serializers.BooleanField(source="hides_system_balance", read_only=True)
    summary = serializers.SerializerMethodField()

    def get_summary(self, obj):
        return public_summary(obj)

    class Meta:
        model = StockCount
        fields = [
            "id", "number", "warehouse", "warehouse_name", "date", "status",
            "status_label", "notes", "blind", "hides_system", "counted_by",
            "counted_by_name", "summary", "created_at",
        ]
        read_only_fields = ["id", "number", "status", "created_at"]


class StockCountWriteSerializer(serializers.Serializer):
    warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all())
    date = serializers.DateField()
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    # `blind` mirrors the model default on purpose. A missing field must not
    # change the shape of the response: an absent key read as True would hide
    # the book balance from a caller that never asked for a blind count, and
    # the screen sends the flag explicitly anyway.
    blind = serializers.BooleanField(required=False, default=False)
    counted_by = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(), required=False, allow_null=True,
    )
    # نطاق الجرد: غائبٌ أو فارغ = كل قماش المخزن، ومعه = المخزوم منه.
    # والحقلُ يمرّ إلى `build_count_snapshot` ولا يُخزَّن: سطورُ الجلسة هي
    # ما يثبّت النطاق، فلا يحتاج الأمرُ إلى أثرٍ ثانٍ يجرّ معه.
    fabrics = serializers.PrimaryKeyRelatedField(
        queryset=Fabric.objects.all(), many=True, required=False,
    )

    def validate(self, attrs):
        request = self.context.get("request")
        if request is not None:
            assert_write_branch_allowed(request, warehouses=[attrs.get("warehouse")])
        return attrs

    def create(self, validated_data):
        return StockCount.objects.create(
            number=DocumentSequence.next_number("CNT"),
            warehouse=validated_data["warehouse"],
            date=validated_data["date"],
            notes=validated_data.get("notes", ""),
            blind=validated_data.get("blind", False),
            counted_by=validated_data.get("counted_by"),
        )


#: يقبل القيم النصية الفارغة كـ«لم يُرصد» لا كرقمٍ صفر.
#: «صفر» و«لم أعدّه» حالتان مختلفتان: الأولى فارقٌ معدوم، والثانية جردٌ ناقص.
_YARDS = serializers.DecimalField(max_digits=12, decimal_places=2)


class StockCountItemWriteSerializer(serializers.Serializer):
    items = serializers.ListField(child=serializers.DictField(), required=True)

    def update(self, instance, validated_data):
        if instance.status != StockCount.Status.OPEN:
            raise serializers.ValidationError("لا يمكن تعديل جلسة مغلقة")
        with transaction.atomic():
            for raw in validated_data["items"]:
                counted = raw.get("counted_yards")
                item = instance.items.filter(fabric_id=raw.get("fabric")).first()
                if not item:
                    raise serializers.ValidationError("يوجد صنف غير مرصود في الجلسة")
                if counted is None or counted == "":
                    counted = None
                else:
                    try:
                        counted = _YARDS.to_internal_value(counted)
                    except serializers.ValidationError:
                        raise serializers.ValidationError(
                            f"قيمة غير صحيحة لـ«{item.fabric.name}»"
                        )
                # السبب يُحفظ مع الرصيد: يُترجم بعد ذلك إلى ملاحظة الحركة.
                note = raw.get("note", None)
                if note is not None:
                    item.note = str(note).strip()
                item.counted_yards = counted
                item.save(update_fields=["counted_yards", "note"])
        return instance


class StockOpeningItemSerializer(serializers.ModelSerializer):
    fabric_name = serializers.CharField(source="fabric.name", read_only=True)

    class Meta:
        model = StockOpeningItem
        fields = ["id", "fabric", "fabric_name", "yards", "rolls_count", "unit_price"]
        read_only_fields = ["id"]


class StockOpeningSerializer(serializers.ModelSerializer):
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    items = StockOpeningItemSerializer(many=True, read_only=True)
    total_yards = serializers.SerializerMethodField()

    class Meta:
        model = StockOpening
        fields = [
            "id", "number", "warehouse", "warehouse_name", "date",
            "notes", "items", "total_yards", "created_at",
        ]
        read_only_fields = ["id", "number", "created_at"]

    def get_total_yards(self, obj):
        return sum((i.yards for i in obj.items.all()), Decimal("0"))


class StockOpeningWriteSerializer(serializers.Serializer):
    warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all())
    date = serializers.DateField()
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    items = serializers.ListField(child=serializers.DictField(), required=False)

    def validate(self, attrs):
        request = self.context.get("request")
        if request is not None:
            assert_write_branch_allowed(request, warehouses=[attrs.get("warehouse")])
        return attrs

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError("أضف صنفاً واحداً على الأقل")
        return _item_tuples(items)

    def create(self, validated_data):
        items = validated_data.get("items") or []
        if not items:
            raise serializers.ValidationError("أضف صنفاً واحداً على الأقل")
        with transaction.atomic():
            opening = StockOpening.objects.create(
                number=DocumentSequence.next_number("OPN"),
                warehouse=validated_data["warehouse"],
                date=validated_data["date"],
                notes=validated_data.get("notes", ""),
            )
            for it in items:
                StockOpeningItem.objects.create(
                    opening=opening, fabric=it["fabric"], yards=it["yards"],
                    rolls_count=it["rolls_count"], unit_price=it["unit_price"],
                )
        return opening
