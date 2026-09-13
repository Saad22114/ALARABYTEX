from django.contrib import admin

from .models import Employee, SaleSession, SaleSessionItem


class SaleSessionItemInline(admin.TabularInline):
    model = SaleSessionItem
    extra = 0
    readonly_fields = ["fabric", "sale_type", "quantity", "unit_price", "payment_method", "total", "sale_date"]


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ["name", "phone", "branch", "is_active", "created_at"]
    list_filter = ["branch", "is_active"]
    search_fields = ["name", "phone"]


@admin.register(SaleSession)
class SaleSessionAdmin(admin.ModelAdmin):
    list_display = ["employee", "branch", "status", "opened_at", "closed_at"]
    list_filter = ["status", "branch"]
    inlines = [SaleSessionItemInline]


@admin.register(SaleSessionItem)
class SaleSessionItemAdmin(admin.ModelAdmin):
    list_display = ["session", "fabric", "sale_type", "quantity", "unit_price", "payment_method", "total", "sale_date"]
    list_filter = ["sale_type", "payment_method"]