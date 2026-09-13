from django.contrib import admin
from .models import DailySale


@admin.register(DailySale)
class DailySaleAdmin(admin.ModelAdmin):
    list_display = [
        "branch", "date", "total_sales", "cash_amount", "transfer_amount",
        "card_amount", "other_amount", "created_at",
    ]
    search_fields = ["branch__name", "notes"]
    list_filter = ["branch", "date"]
    ordering = ["-date", "-created_at"]
