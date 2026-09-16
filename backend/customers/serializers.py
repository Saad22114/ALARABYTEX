from rest_framework import serializers

from .models import Customer


class CustomerSerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(default=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True, default="")

    class Meta:
        model = Customer
        fields = [
            "id", "name", "phone", "email", "address", "notes",
            "branch", "branch_name", "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("اسم الزبون مطلوب")
        return value.strip()

    def validate_phone(self, value):
        if value is not None and not value.strip():
            return None
        if value is None:
            return value
        phone = value.strip()
        qs = Customer.objects.filter(phone=phone)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("رقم الهاتف مسجل مسبقاً لزبون آخر")
        return phone