from django.db import transaction
from django.db.models import Sum
from rest_framework import serializers
from core.daterange import resolve_range
from suppliers.models import Fabric
from warehouses.models import Warehouse
from .models import Branch, FabricBranchPrice


class BranchSerializer(serializers.ModelSerializer):
    sales_count = serializers.SerializerMethodField()
    expenses_count = serializers.SerializerMethodField()
    monthly_sales = serializers.SerializerMethodField()
    monthly_expenses = serializers.SerializerMethodField()
    target_progress_pct = serializers.SerializerMethodField()
    is_active = serializers.BooleanField(default=True)

    class Meta:
        model = Branch
        fields = [
            "id", "name", "code", "phone", "address", "city", "notes",
            "is_active", "sales_count", "expenses_count",
            "monthly_sales_target", "monthly_sales", "monthly_expenses", "target_progress_pct",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_sales_count(self, obj):
        return obj.daily_sales.count()

    def get_expenses_count(self, obj):
        return obj.expenses.count()

    def _range(self):
        request = self.context.get("request")
        params = request.query_params if request is not None else {}
        return resolve_range(params, default_period="month")[:2]

    def get_monthly_sales(self, obj):
        start_date, end_date = self._range()
        total = (
            obj.daily_sales.filter(date__gte=start_date, date__lte=end_date)
            .aggregate(total=Sum("total_sales"))["total"]
        )
        return float(total or 0)

    def get_monthly_expenses(self, obj):
        start_date, end_date = self._range()
        total = (
            obj.expenses.filter(date__gte=start_date, date__lte=end_date)
            .aggregate(total=Sum("amount"))["total"]
        )
        return float(total or 0)

    def get_target_progress_pct(self, obj):
        target = obj.monthly_sales_target
        if not target:
            return None
        progress = (self.get_monthly_sales(obj) / float(target)) * 100
        return round(progress, 1)

    def validate_code(self, value):
        if value:
            qs = Branch.objects.filter(code__iexact=value)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError("كود الفرع موجود مسبقاً")
        return value

    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("اسم الفرع مطلوب")
        return value

    def create(self, validated_data):
        with transaction.atomic():
            branch = super().create(validated_data)
            Warehouse.for_branch(branch)
        return branch


class FabricBranchPriceSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    fabric_name = serializers.CharField(source="fabric.name", read_only=True)
    fabric_code = serializers.CharField(source="fabric.code", read_only=True)
    fabric_unit = serializers.CharField(source="fabric.unit", read_only=True)
    yards_per_roll = serializers.DecimalField(
        source="fabric.yards_per_roll", max_digits=8, decimal_places=2, read_only=True, allow_null=True
    )
    global_sale_price_yard = serializers.DecimalField(
        source="fabric.sale_price_yard", max_digits=12, decimal_places=3, read_only=True
    )
    global_sale_price_roll = serializers.DecimalField(
        source="fabric.sale_price_roll", max_digits=12, decimal_places=3, read_only=True, allow_null=True
    )

    class Meta:
        model = FabricBranchPrice
        fields = [
            "id", "branch", "branch_name", "fabric", "fabric_name", "fabric_code",
            "fabric_unit", "yards_per_roll", "global_sale_price_yard", "global_sale_price_roll",
            "sale_price_yard", "sale_price_roll", "min_sale_yard", "min_sale_roll",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        fabric = attrs.get("fabric")
        branch = attrs.get("branch")
        if fabric and fabric.unit == Fabric.Unit.ROLL and not fabric.yards_per_roll:
            raise serializers.ValidationError(
                {"sale_price_roll": "لا يمكن تحديد سعر لفة قبل ضبط ياردات اللفة الواحدة للقماش"}
            )
        return attrs