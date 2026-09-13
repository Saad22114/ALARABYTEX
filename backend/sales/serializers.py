from decimal import Decimal

from django.db import transaction
from rest_framework import serializers
from django.conf import settings

from appsettings.models import AppSettings
from suppliers.models import Fabric
from warehouses.services import reverse_sale_consumption, sell_from_branch

from .models import DailySale, DailySaleItem


class DailySaleItemSerializer(serializers.ModelSerializer):
    fabric_name = serializers.CharField(source="fabric.name", read_only=True)
    fabric_unit = serializers.CharField(source="fabric.unit", read_only=True)

    class Meta:
        model = DailySaleItem
        fields = ["id", "fabric", "fabric_name", "fabric_unit", "yards"]
        read_only_fields = ["id"]


class DailySaleReadSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    employee_name = serializers.CharField(source="employee.name", read_only=True, default=None)
    payment_total = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    mismatch = serializers.SerializerMethodField()
    items = DailySaleItemSerializer(many=True, read_only=True, source="sale_items")

    class Meta:
        model = DailySale
        fields = [
            "id", "branch", "branch_name", "employee", "employee_name", "date", "total_sales",
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
        return attrs

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
            if fabric.pk in seen:
                raise serializers.ValidationError(f"القماش «{fabric.name}» مكرر في أصناف المبيعات")
            seen.add(fabric.pk)
            rows.append((fabric, yards))
        return rows

    def create(self, validated_data):
        items = validated_data.pop("items", None)
        allow_negative = AppSettings.load().allow_negative_stock
        with transaction.atomic():
            sale = DailySale.objects.create(**validated_data)
            if items:
                sell_from_branch(sale.branch, sale, items, allow_negative=allow_negative)
                for fabric, yards in items:
                    DailySaleItem.objects.create(sale=sale, fabric=fabric, yards=yards)
        return sale

    def update(self, instance, validated_data):
        if "items" not in validated_data:
            return super().update(instance, validated_data)

        allow_negative = AppSettings.load().allow_negative_stock
        with transaction.atomic():
            reverse_sale_consumption(instance)
            items = validated_data.pop("items") or []
            instance = super().update(instance, validated_data)
            instance.sale_items.all().delete()
            if items:
                sell_from_branch(instance.branch, instance, items, allow_negative=allow_negative)
                for fabric, yards in items:
                    DailySaleItem.objects.create(sale=instance, fabric=fabric, yards=yards)
        return instance