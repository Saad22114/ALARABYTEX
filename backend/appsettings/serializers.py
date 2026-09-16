from rest_framework import serializers

from .models import AppSettings


class AppSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppSettings
        fields = [
            "pk", "business_name", "business_phone", "business_address", "tax_number",
            "trade_name", "commercial_registration",
            "business_email",
            "currency_symbol", "currency_code", "decimal_places", "currency_position",
            "default_period", "default_page_size",
            "allow_negative_stock", "hidden_sections",
            "low_stock_threshold", "low_stock_alert_enabled",
            "date_format", "default_theme", "receipt_footer",
            "invoice_notes",
            "invoice_prefix", "tax_rate",
            "previous_day_cutoff_hour",
            "session_warn_hours", "session_danger_hours",
            "default_payment_method", "discount_max_percent",
            "receipt_show_tax", "receipt_show_phone",
            "logo",
            "created_at", "updated_at",
        ]
        read_only_fields = ["pk", "created_at", "updated_at"]