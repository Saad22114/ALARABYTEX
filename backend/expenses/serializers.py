from rest_framework import serializers
from django.conf import settings
from .models import Expense, ExpenseCategory


class ExpenseCategorySerializer(serializers.ModelSerializer):
    expense_count = serializers.SerializerMethodField()
    is_active = serializers.BooleanField(default=True)

    class Meta:
        model = ExpenseCategory
        fields = [
            "id", "name", "code", "is_system", "notes", "expense_count",
            "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_expense_count(self, obj):
        return obj.expenses.count()

    def validate(self, attrs):
        instance = self.instance
        if instance and instance.is_system:
            raise serializers.ValidationError(
                {"detail": settings.API_MESSAGES["system_category"]}
            )
        return attrs


class ExpenseReadSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Expense
        fields = [
            "id", "branch", "branch_name", "category", "category_name",
            "date", "amount", "payment_method", "description", "notes",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ExpenseWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = [
            "id", "branch", "category", "date", "amount", "payment_method",
            "description", "notes",
        ]
        read_only_fields = ["id"]
