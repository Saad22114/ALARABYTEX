from decimal import Decimal

from rest_framework import serializers

from .models import Partner, PartnerMovement, PartnerOperation
from .services import PartnerOperationError, create_partner_operation


class PartnerSerializer(serializers.ModelSerializer):
    total_support = serializers.SerializerMethodField()
    total_withdraw = serializers.SerializerMethodField()
    net_balance = serializers.SerializerMethodField()

    class Meta:
        model = Partner
        fields = [
            "id",
            "name",
            "share_percent",
            "notes",
            "is_active",
            "total_support",
            "total_withdraw",
            "net_balance",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_total_support(self, obj):
        value = obj.support if hasattr(obj, "support") and obj.support else Decimal("0")
        return float(value)

    def get_total_withdraw(self, obj):
        value = obj.withdraw if hasattr(obj, "withdraw") and obj.withdraw else Decimal("0")
        return float(value)

    def get_net_balance(self, obj):
        return self.get_total_support(obj) - self.get_total_withdraw(obj)

    def validate_share_percent(self, value):
        if value <= 0 or value > 100:
            raise serializers.ValidationError("نسبة المشاركة يجب أن تكون بين 1 و 100")
        return value


class PartnerBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Partner
        fields = ["id", "name", "share_percent", "is_active"]


class PartnerMovementSerializer(serializers.ModelSerializer):
    partner_name = serializers.CharField(source="partner.name", read_only=True)
    partner_share = serializers.DecimalField(
        source="partner.share_percent", max_digits=5, decimal_places=2, read_only=True
    )
    movement_type_label = serializers.CharField(source="get_movement_type_display", read_only=True)

    class Meta:
        model = PartnerMovement
        fields = [
            "id",
            "partner",
            "partner_name",
            "partner_share",
            "movement_type",
            "movement_type_label",
            "amount",
        ]


class PartnerOperationReadSerializer(serializers.ModelSerializer):
    operation_type_label = serializers.CharField(source="get_operation_type_display", read_only=True)
    payment_method_label = serializers.CharField(source="get_payment_method_display", read_only=True)
    partner_name = serializers.CharField(source="partner.name", read_only=True)
    movements = PartnerMovementSerializer(many=True, read_only=True)

    class Meta:
        model = PartnerOperation
        fields = [
            "id",
            "number",
            "date",
            "partner",
            "partner_name",
            "operation_type",
            "operation_type_label",
            "payment_method",
            "payment_method_label",
            "amount",
            "reason",
            "notes",
            "movements",
            "created_at",
        ]


class PartnerOperationWriteSerializer(serializers.ModelSerializer):
    partner = serializers.PrimaryKeyRelatedField(
        queryset=Partner.objects.all(),
        required=True,
        error_messages={"does_not_exist": "الشريك المحدد غير موجود", "required": "يرجى اختيار الشريك"},
    )

    class Meta:
        model = PartnerOperation
        fields = ["partner", "date", "operation_type", "payment_method", "amount", "reason", "notes"]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("المبلغ يجب أن أكبر من صفر")
        return value

    def validate(self, attrs):
        partner = attrs.get("partner", getattr(self.instance, "partner", None))
        if partner is not None and not partner.is_active:
            raise serializers.ValidationError({"partner": "الشريك المحدد غير نشط"})
        return attrs

    def create(self, validated_data):
        try:
            return create_partner_operation(
                partner=validated_data["partner"],
                date=validated_data.get("date"),
                operation_type=validated_data["operation_type"],
                payment_method=validated_data.get("payment_method", "cash"),
                amount=validated_data["amount"],
                reason=validated_data.get("reason", ""),
                notes=validated_data.get("notes", ""),
            )
        except PartnerOperationError as exc:
            raise serializers.ValidationError(str(exc))

    def update(self, instance, validated_data):
        instance.partner = validated_data.get("partner", instance.partner)
        instance.date = validated_data.get("date", instance.date)
        instance.operation_type = validated_data.get("operation_type", instance.operation_type)
        instance.payment_method = validated_data.get("payment_method", instance.payment_method)
        instance.amount = validated_data.get("amount", instance.amount)
        instance.reason = validated_data.get("reason", instance.reason)
        instance.notes = validated_data.get("notes", instance.notes)
        instance.save()
        return instance


class PartnerMovementReportSerializer(serializers.ModelSerializer):
    operation_id = serializers.IntegerField(source="operation.id", read_only=True)
    date = serializers.DateField(source="operation.date")
    number = serializers.CharField(source="operation.number")
    movement_type_label = serializers.CharField(source="get_movement_type_display")
    payment_method = serializers.CharField(source="operation.payment_method")
    payment_method_label = serializers.CharField(source="operation.get_payment_method_display")
    reason = serializers.CharField(source="operation.reason")
    notes = serializers.CharField(source="operation.notes")
    running_balance = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)

    class Meta:
        model = PartnerMovement
        fields = [
            "id",
            "operation_id",
            "date",
            "number",
            "movement_type",
            "movement_type_label",
            "payment_method",
            "payment_method_label",
            "amount",
            "reason",
            "notes",
            "running_balance",
        ]