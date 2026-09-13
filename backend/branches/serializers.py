from django.db import transaction
from rest_framework import serializers
from django.conf import settings
from warehouses.models import Warehouse
from .models import Branch


class BranchSerializer(serializers.ModelSerializer):
    sales_count = serializers.SerializerMethodField()
    expenses_count = serializers.SerializerMethodField()
    is_active = serializers.BooleanField(default=True)

    class Meta:
        model = Branch
        fields = [
            "id", "name", "code", "phone", "address", "city", "notes",
            "is_active", "sales_count", "expenses_count", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_sales_count(self, obj):
        return obj.daily_sales.count()

    def get_expenses_count(self, obj):
        return obj.expenses.count()

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
