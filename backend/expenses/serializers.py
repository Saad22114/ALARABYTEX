from rest_framework import serializers
from django.conf import settings
from core.branch_scope import assert_write_branch_allowed
from .models import Expense, ExpenseBudget, ExpenseCategory


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
            "is_recurring", "recur_frequency", "next_run_date", "origin",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ExpenseWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = [
            "id", "branch", "category", "date", "amount", "payment_method",
            "description", "notes",
            "is_recurring", "recur_frequency", "next_run_date", "origin",
        ]
        read_only_fields = ["id", "origin"]

    def validate(self, attrs):
        request = self.context.get("request")
        if request is not None:
            branch = attrs.get("branch") or getattr(self.instance, "branch", None)
            assert_write_branch_allowed(request, branches=[branch])

        is_recurring = attrs.get("is_recurring")
        if self.instance is not None:
            is_recurring = attrs.get("is_recurring", self.instance.is_recurring)
        recur_frequency = attrs.get("recur_frequency")
        if self.instance is not None:
            recur_frequency = attrs.get("recur_frequency", self.instance.recur_frequency)

        if is_recurring:
            if not recur_frequency:
                raise serializers.ValidationError(
                    {"recur_frequency": "اختر دورة التكرار للمصروف المتكرر (أسبوعي أو شهري)"}
                )
        else:
            # عند تعطيل التكرار لا يبقى موعد قادم.
            attrs["next_run_date"] = None

        next_run_date = attrs.get("next_run_date")
        if is_recurring and not next_run_date:
            expense_date = attrs.get("date") or getattr(self.instance, "date", None)
            if expense_date:
                from .services import suggested_next_run_date

                attrs["next_run_date"] = suggested_next_run_date(expense_date, recur_frequency)
        return attrs


class ExpenseBudgetSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = ExpenseBudget
        fields = [
            "id", "branch", "branch_name", "category", "category_name",
            "month", "amount", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        request = self.context.get("request")
        if request is not None:
            branch = attrs.get("branch") or getattr(self.instance, "branch", None)
            assert_write_branch_allowed(request, branches=[branch])
        return attrs
