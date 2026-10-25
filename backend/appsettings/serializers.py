from rest_framework import serializers

from .crypto import password_problem
from .models import AppSettings


class AppSettingsSerializer(serializers.ModelSerializer):
    backup_password = serializers.CharField(
        max_length=128, required=False, allow_blank=True, write_only=True,
    )
    has_backup_password = serializers.SerializerMethodField()

    class Meta:
        model = AppSettings
        fields = [
            "pk", "business_name", "business_phone", "business_address", "tax_number",
            "trade_name", "commercial_registration",
            "business_email",
            "instagram_url", "snapchat_url", "tiktok_url", "facebook_url",
            "bank_transfer_url", "bank_transfer_phone",
            "instagram_qr_image", "snapchat_qr_image", "whatsapp_qr_image", "bank_transfer_qr_image",
            "currency_symbol", "currency_code", "decimal_places", "currency_position",
            "default_period", "default_page_size",
            "hidden_sections",
            "low_stock_threshold", "low_stock_alert_enabled",
            "date_format", "default_theme", "font_family", "receipt_footer",
            "invoice_notes",
            "invoice_prefix", "tax_rate",
            "previous_day_cutoff_hour",
            "session_warn_hours", "session_danger_hours",
            "session_auto_close_enabled", "session_auto_close_time",
            "default_payment_method", "discount_max_percent", "min_sale_percent",
            "min_piece_price_multiplier",
            "card_credit_fee_percent", "card_debit_fee_percent",
            "receipt_show_tax", "receipt_show_phone",
            "logo",
            "backup_password", "has_backup_password",
            "auto_backup_enabled", "auto_backup_time", "auto_backup_every_hours",
            "auto_backup_every_minutes",
            "last_auto_backup_at", "last_auto_backup_path",
            "created_at", "updated_at",
        ]
        read_only_fields = ["pk", "created_at", "updated_at"]

    def get_has_backup_password(self, obj):
        return bool(obj.backup_password)

    def validate_backup_password(self, value):
        """لا مجال لإلغاء التشفير.

        الحقل الفارغ كان يعني «امسح المفتاح» فتصبح النسخ بعدها نصاً مقروءاً —
        خيار بقي في الواجهة بعد أن صار التسريب محسوساً. صار الفراغ يعني
        «لم تُغيّر الكلمة»: نُبقي الحالية، وبلا كلمة أصلاً يبقى فارغاً
        فيرفض التصدير حتى تُضبط.
        """
        if value == "":
            return getattr(self.instance, "backup_password", "") or ""
        problem = password_problem(value)
        if problem:
            raise serializers.ValidationError(problem)
        return value

    def validate(self, attrs):
        enabled = attrs.get("auto_backup_enabled", getattr(self.instance, "auto_backup_enabled", False))
        password = attrs.get("backup_password", getattr(self.instance, "backup_password", ""))
        if enabled and not password:
            raise serializers.ValidationError({
                "auto_backup_enabled": "اضبط كلمة مرور النسخ الاحتياطي قبل تفعيل النسخ التلقائي.",
            })
        return attrs
