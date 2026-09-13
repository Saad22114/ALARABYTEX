from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone
from rest_framework import serializers

from suppliers.models import Fabric
from warehouses.models import FabricRoll, Warehouse

from .models import Employee, SaleSession, SaleSessionItem
from .services import effective_sale_date

PAYMENT_METHODS = {m for m, _ in SaleSessionItem.PaymentMethod.choices}


class EmployeeSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source="branch.name", read_only=True)

    class Meta:
        model = Employee
        fields = [
            "id", "name", "phone", "branch", "branch_name",
            "notes", "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SaleSessionItemSerializer(serializers.ModelSerializer):
    fabric_name = serializers.CharField(source="fabric.name", read_only=True)
    fabric_code = serializers.CharField(source="fabric.code", read_only=True)
    fabric_unit = serializers.CharField(source="fabric.unit", read_only=True)
    sale_type_label = serializers.CharField(source="get_sale_type_display", read_only=True)
    payment_method_label = serializers.CharField(source="get_payment_method_display", read_only=True)
    yards_effective = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = SaleSessionItem
        fields = [
            "id", "fabric", "fabric_name", "fabric_code", "fabric_unit",
            "sale_type", "sale_type_label",
            "quantity", "unit_price", "payment_method", "payment_method_label",
            "total", "sale_date", "yards_effective",
        ]


class SaleSessionReadSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.name", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    elapsed_minutes = serializers.SerializerMethodField()
    items = serializers.SerializerMethodField()
    totals = serializers.SerializerMethodField()

    class Meta:
        model = SaleSession
        fields = [
            "id", "employee", "employee_name", "branch", "branch_name",
            "status", "status_label", "opened_at", "closed_at", "notes",
            "elapsed_minutes", "items", "totals",
        ]

    def get_elapsed_minutes(self, obj):
        if obj.status == SaleSession.Status.CLOSED:
            return None
        if not obj.opened_at:
            return 0
        return max(0, int((timezone.now() - obj.opened_at).total_seconds() // 60))

    def get_items(self, obj):
        return SaleSessionItemSerializer(obj.items.all(), many=True).data

    def get_totals(self, obj):
        agg = {m: Decimal("0") for m in PAYMENT_METHODS}
        yards = Decimal("0")
        for it in obj.items.all():
            agg[it.payment_method] += it.total
            yards += it.yards_effective
        return {
            "cash": float(agg["cash"]),
            "transfer": float(agg["transfer"]),
            "card": float(agg["card"]),
            "total": float(agg["cash"] + agg["transfer"] + agg["card"]),
            "yards": float(yards),
        }


class SaleSessionOpenSerializer(serializers.Serializer):
    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all())

    def validate_employee(self, employee):
        if SaleSession.objects.filter(
            employee=employee, status=SaleSession.Status.OPEN
        ).exists():
            raise serializers.ValidationError("لهذا الموظف وردية مفتوحة بالفعل")
        return employee

    def create(self, validated_data):
        employee = validated_data["employee"]
        return SaleSession.objects.create(employee=employee, branch=employee.branch)


class SaleSessionItemCreateSerializer(serializers.Serializer):
    fabric = serializers.PrimaryKeyRelatedField(queryset=Fabric.objects.all())
    sale_type = serializers.ChoiceField(
        choices=SaleSessionItem.SaleType.choices, default=SaleSessionItem.SaleType.YARD
    )
    quantity = serializers.DecimalField(max_digits=12, decimal_places=2)
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=3, required=False)
    payment_method = serializers.ChoiceField(
        choices=SaleSessionItem.PaymentMethod.choices,
        default=SaleSessionItem.PaymentMethod.CASH,
    )

    def validate(self, attrs):
        fabric = attrs["fabric"]
        sale_type = attrs.get("sale_type", SaleSessionItem.SaleType.YARD)
        quantity = attrs["quantity"]
        if quantity <= 0:
            raise serializers.ValidationError({"quantity": "الكمية يجب أن تكون أكبر من صفر"})
        if sale_type == SaleSessionItem.SaleType.ROLL and not fabric.yards_per_roll:
            raise serializers.ValidationError(
                {"detail": f"القماش «{fabric.name}» لا توجد له ياردات اللفة — حدّدها في ملف القماش قبل البيع باللفة"}
            )

        auto = Decimal(str(fabric.sale_price_yard if fabric.sale_price_yard is not None else 0))
        if sale_type == SaleSessionItem.SaleType.ROLL:
            auto = (
                Decimal(str(fabric.sale_price_roll))
                if fabric.sale_price_roll is not None
                else auto * Decimal(str(fabric.yards_per_roll))
            )
        if "unit_price" not in attrs or attrs.get("unit_price") is None:
            attrs["unit_price"] = auto
        unit_price = Decimal(str(attrs["unit_price"]))
        if unit_price < 0:
            raise serializers.ValidationError({"unit_price": "سعر الوحدة لا يمكن أن يكون سالباً"})

        min_price = None
        if sale_type == SaleSessionItem.SaleType.ROLL:
            min_price = (
                fabric.min_sale_roll
                if fabric.min_sale_roll is not None
                else (
                    (Decimal(str(fabric.min_sale_yard or 0)) * Decimal(str(fabric.yards_per_roll)))
                    if fabric.min_sale_yard and fabric.yards_per_roll
                    else None
                )
            )
        elif fabric.min_sale_yard:
            min_price = Decimal(str(fabric.min_sale_yard))
        if (
            min_price
            and min_price > 0
            and unit_price < min_price
            and self.context["session"].status != SaleSession.Status.CLOSED
        ):
            raise serializers.ValidationError(
                {
                    "unit_price": (
                        f"السعر أقل من الحد الأدنى للبيع ({min_price}) — حدّده في ملف القماش"
                    )
                }
            )

        warehouse = Warehouse.for_branch(self.context["session"].branch)
        available = Decimal("0")
        if warehouse is not None:
            available = (
                FabricRoll.objects.filter(
                    warehouse=warehouse,
                    fabric=fabric,
                    status=FabricRoll.Status.AVAILABLE,
                    remaining_yards__gt=0,
                ).aggregate(total=Sum("remaining_yards"))["total"]
                or Decimal("0")
            )
        if sale_type == SaleSessionItem.SaleType.ROLL:
            yards_need = quantity * (fabric.yards_per_roll or Decimal("0"))
        else:
            yards_need = quantity
        if self.context["session"].status != SaleSession.Status.CLOSED and available < yards_need:
            raise serializers.ValidationError(
                {
                    "detail": (
                        f"الكمية غير متوفرة في فرع الوردية — القماش «{fabric.name}» "
                        f"متوفر {available.normalize()} ياردة فقط"
                    )
                }
            )

        attrs["total"] = Decimal(str(quantity)) * unit_price
        attrs["sale_date"] = effective_sale_date()
        return attrs

    def create(self, validated_data):
        validated_data["session"] = self.context["session"]
        return SaleSessionItem.objects.create(**validated_data)


class SaleSessionItemEditSerializer(SaleSessionItemCreateSerializer):
    def validate(self, attrs):
        item = self.instance
        if "fabric" not in attrs:
            attrs["fabric"] = item.fabric
        if "sale_type" not in attrs:
            attrs["sale_type"] = item.sale_type
        if "quantity" not in attrs:
            attrs["quantity"] = item.quantity
        if "unit_price" not in attrs:
            attrs["unit_price"] = item.unit_price
        if "payment_method" not in attrs:
            attrs["payment_method"] = item.payment_method
        attrs = super().validate(attrs)
        attrs.pop("sale_date", None)
        return attrs

    def update(self, instance, validated_data):
        raise NotImplementedError  # done via update_session_item service

    def create(self, validated_data):  # pragma: no cover - edit path never calls create
        raise NotImplementedError