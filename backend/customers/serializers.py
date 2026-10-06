from rest_framework import serializers
from django.utils import timezone

from core.phones import find_by_phone

from .models import Customer


class CustomerSerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(default=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True, default="")

    class Meta:
        model = Customer
        fields = [
            "id", "name", "phone", "email", "address", "notes",
            "branch", "branch_name", "is_active",
            "whatsapp_opt_in", "whatsapp_opt_in_at", "whatsapp_opt_out_at",
            "whatsapp_welcome_status", "whatsapp_welcome_sent_at", "whatsapp_welcome_message_id",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "whatsapp_opt_in_at", "whatsapp_opt_out_at", "whatsapp_welcome_status",
            "whatsapp_welcome_sent_at", "whatsapp_welcome_message_id", "created_at", "updated_at",
        ]

    def validate(self, attrs):
        opted_in = attrs.get("whatsapp_opt_in", getattr(self.instance, "whatsapp_opt_in", False))
        phone = attrs.get("phone", getattr(self.instance, "phone", None))
        if opted_in and not phone:
            raise serializers.ValidationError({"whatsapp_opt_in": "أدخل رقم الهاتف قبل طلب إرسال رسالة واتساب"})
        return attrs

    def create(self, validated_data):
        if validated_data.get("whatsapp_opt_in"):
            validated_data["whatsapp_opt_in_at"] = timezone.now()
        return super().create(validated_data)

    def update(self, instance, validated_data):
        opted_in = validated_data.get("whatsapp_opt_in", instance.whatsapp_opt_in)
        if opted_in and not instance.whatsapp_opt_in:
            validated_data["whatsapp_opt_in_at"] = timezone.now()
            validated_data["whatsapp_opt_out_at"] = None
        elif not opted_in and instance.whatsapp_opt_in:
            validated_data["whatsapp_opt_out_at"] = timezone.now()
        return super().update(instance, validated_data)

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
        # التطابقُ على الأرقام لا على الرسم. «0565-555-555» و«0565555555» و«0565 555 555»
        # ثلاثةُ أسطرٍ في قاعدة البيانات، ورقمٌ واحدٌ عند الناس — فالسؤالُ هنا
        # «هل واحدٌ مرّتين؟» لا «هل أعرفه؟». ولهذا لا يُشترط عددُ الأرقام الأدنى
        # المعتاد في البحث (سبعة): هنا الغايةُ كشفُ التكرار لا اليقين، والرقمُ
        # القصيرُ نفسُه أرجحُ خطأً منه رقماً صحيحاً.
        qs = Customer.objects.all()
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        twin = find_by_phone(qs, phone, min_digits=1).first()
        if twin is not None:
            raise serializers.ValidationError(
                f"رقم الهاتف مسجل مسبقاً للزبون «{twin.name}» — "
                "أدخله كما هو أو اختر رقماً آخر"
            )
        return phone
