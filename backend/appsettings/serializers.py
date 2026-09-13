from rest_framework import serializers

from .models import AppSettings


class AppSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppSettings
        fields = [
            "pk", "business_name", "business_phone", "business_address", "tax_number",
            "currency_symbol", "currency_code", "decimal_places",
            "default_period", "default_page_size",
            "allow_negative_stock", "hidden_sections",
            "created_at", "updated_at",
        ]
        read_only_fields = ["pk", "created_at", "updated_at"]