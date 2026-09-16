from django.contrib import admin

from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "email", "branch", "is_active", "created_at")
    list_filter = ("is_active", "branch")
    search_fields = ("name", "phone", "email")
    list_select_related = ("branch",)