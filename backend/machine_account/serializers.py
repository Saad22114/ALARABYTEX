from decimal import Decimal

from rest_framework import serializers

from core.branch_scope import assert_write_branch_allowed

from .models import MachineCollection


class MachineCollectionSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source="branch.name", read_only=True, default="")
    method_label = serializers.CharField(source="get_method_display", read_only=True)
    account_label = serializers.CharField(source="get_account_display", read_only=True)
    amount = serializers.FloatField()

    class Meta:
        model = MachineCollection
        fields = [
            "id", "account", "account_label", "branch", "branch_name", "date", "amount",
            "method", "method_label", "reference", "notes", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_amount(self, value):
        if value <= Decimal("0"):
            raise serializers.ValidationError("المبلغ المستلم يجب أن يكون أكبر من صفر")
        return value

    def validate(self, attrs):
        request = self.context.get("request")
        if request is not None:
            branch = attrs.get("branch") or getattr(self.instance, "branch", None)
            assert_write_branch_allowed(request, branches=[branch])
        return attrs