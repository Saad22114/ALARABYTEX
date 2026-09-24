from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from rest_framework import serializers
from django.conf import settings

from suppliers.models import Fabric
from warehouses.models import FabricRoll, Warehouse
from warehouses.services import reverse_sale_consumption, sell_from_branch

from .models import DailySale, DailySaleItem


class DailySaleItemSerializer(serializers.ModelSerializer):
    fabric_name = serializers.CharField(source="fabric.name", read_only=True)
    fabric_unit = serializers.CharField(source="fabric.unit", read_only=True)

    class Meta:
        model = DailySaleItem
        fields = ["id", "fabric", "fabric_name", "fabric_unit", "yards", "unit_price"]
        read_only_fields = ["id"]


class DailySaleReadSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    branch_code = serializers.CharField(source="branch.code", read_only=True)
    employee_name = serializers.CharField(source="employee.name", read_only=True, default=None)
    payment_total = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    mismatch = serializers.SerializerMethodField()
    items = DailySaleItemSerializer(many=True, read_only=True, source="sale_items")

    class Meta:
        model = DailySale
        fields = [
            "id", "branch", "branch_name", "branch_code", "employee", "employee_name", "date", "total_sales",
            "cash_amount", "transfer_amount", "card_amount", "other_amount",
            "payment_total", "mismatch", "notes", "items",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_mismatch(self, obj):
        return not obj.is_balanced


class DailySaleWriteSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.name", read_only=True, default=None)
    payment_total = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    mismatch = serializers.SerializerMethodField()
    items = serializers.ListField(
        child=serializers.DictField(), required=False, write_only=True, allow_empty=True
    )

    class Meta:
        model = DailySale
        fields = [
            "id", "branch", "employee", "employee_name", "date", "total_sales",
            "cash_amount", "transfer_amount", "card_amount", "other_amount",
            "payment_total", "mismatch", "notes", "items",
        ]
        read_only_fields = ["id", "payment_total", "mismatch"]

    def get_mismatch(self, obj):
        return not obj.is_balanced

    def validate(self, attrs):
        total_sales = attrs.get("total_sales", getattr(self.instance, "total_sales", Decimal("0")))
        cash = attrs.get("cash_amount", getattr(self.instance, "cash_amount", Decimal("0")))
        transfer = attrs.get("transfer_amount", getattr(self.instance, "transfer_amount", Decimal("0")))
        card = attrs.get("card_amount", getattr(self.instance, "card_amount", Decimal("0")))
        other = attrs.get("other_amount", getattr(self.instance, "other_amount", Decimal("0")))
        payment_total = cash + transfer + card + other
        if payment_total != total_sales:
            raise serializers.ValidationError(
                {"detail": settings.API_MESSAGES["sales_mismatch"]}
            )
        employee = attrs.get("employee") or getattr(self.instance, "employee", None)
        branch = attrs.get("branch") or getattr(self.instance, "branch", None)
        if employee and branch and employee.branch_id != branch.id:
            raise serializers.ValidationError(
                {"employee": "الموظف المحدد لا يتبع الفرع المختار"}
            )
        items = attrs.get("items")
        if items is not None:
            self.validate_stock_available(branch, items)
        return attrs

    def validate_stock_available(self, branch, rows):
        """يرفض البيع منذ البداية إذا كانت الكمية المطلوبة تتجاوز رصيد مخزون الفرع.

        عند التعديل يُحسب المتوفر مضافاً إليه ما يستهلكه البيع الحالي لأنه يُعكس أولاً.
        """
        if not rows or branch is None:
            return
        warehouse = Warehouse.objects.filter(branch=branch).first()
        if warehouse is None:
            return
        available = {
            r["fabric_id"]: r["total"]
            for r in FabricRoll.objects.filter(
                warehouse=warehouse,
                status=FabricRoll.Status.AVAILABLE,
                remaining_yards__gt=0,
            ).values("fabric_id").annotate(total=Sum("remaining_yards"))
        }
        needed = {}
        for fabric, yards, _unit_price in rows:
            needed[fabric] = needed.get(fabric, Decimal("0")) + yards
        used_by_instance = {}
        if self.instance is not None:
            for it in self.instance.sale_items.all():
                used_by_instance[it.fabric_id] = used_by_instance.get(it.fabric_id, Decimal("0")) + it.yards
        for fabric, yards in needed.items():
            total = available.get(fabric.pk, Decimal("0")) + used_by_instance.get(fabric.pk, Decimal("0"))
            if yards > total:
                raise serializers.ValidationError(
                    {
                        "detail": (
                            f"رصيد المخزن لا يكفي لقماش «{fabric.name}»: "
                            f"المتوفر {total} ياردة والمطلوب {yards}"
                        )
                    }
                )

    def validate_items(self, items):
        rows = []
        seen = set()
        for it in items:
            fabric = it.get("fabric")
            if isinstance(fabric, (int, str)):
                try:
                    fabric = Fabric.objects.get(pk=fabric)
                except Fabric.DoesNotExist:
                    raise serializers.ValidationError("قماش غير موجود")
            elif not isinstance(fabric, Fabric):
                raise serializers.ValidationError("قماش غير صالح")
            yards = Decimal(str(it.get("yards", "0") or "0"))
            if yards <= 0:
                raise serializers.ValidationError("ياردات المبيعات يجب أن تكون أكبر من صفر")
            unit_price = it.get("unit_price")
            if unit_price in (None, ""):
                unit_price = None
            else:
                unit_price = Decimal(str(unit_price))
                if unit_price < 0:
                    raise serializers.ValidationError("سعر الوحدة لا يمكن أن يكون سالباً")
            if fabric.pk in seen:
                raise serializers.ValidationError(f"القماش «{fabric.name}» مكرر في أصناف المبيعات")
            seen.add(fabric.pk)
            rows.append((fabric, yards, unit_price))
        return rows

    def create(self, validated_data):
        items = validated_data.pop("items", None)
        with transaction.atomic():
            sale = DailySale.objects.create(**validated_data)
            if items:
                sell_from_branch(sale.branch, sale, [(f, y) for f, y, _ in items], allow_negative=False)
                for fabric, yards, unit_price in items:
                    DailySaleItem.objects.create(sale=sale, fabric=fabric, yards=yards, unit_price=unit_price)
        return sale

    def update(self, instance, validated_data):
        if "items" not in validated_data:
            return super().update(instance, validated_data)

        with transaction.atomic():
            reverse_sale_consumption(instance)
            items = validated_data.pop("items") or []
            instance = super().update(instance, validated_data)
            instance.sale_items.all().delete()
            if items:
                sell_from_branch(instance.branch, instance, [(f, y) for f, y, _ in items], allow_negative=False)
                for fabric, yards, unit_price in items:
                    DailySaleItem.objects.create(
                        sale=instance, fabric=fabric, yards=yards, unit_price=unit_price,
                    )
        return instance