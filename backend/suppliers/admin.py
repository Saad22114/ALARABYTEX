from django.contrib import admin
from .models import Fabric, LedgerEntry, PurchaseItem, Supplier


class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    fields = ["fabric", "quantity_yards", "rolls", "unit_price", "total"]
    extra = 0
    can_delete = False


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ["name", "company_name", "phone", "email", "city", "country", "is_active", "created_at"]
    search_fields = ["name", "company_name", "phone", "email", "city", "country"]
    list_filter = ["is_active", "city", "country"]
    ordering = ["name"]


@admin.register(Fabric)
class FabricAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "unit", "sale_price_yard", "is_active", "created_at"]
    search_fields = ["name", "code"]
    list_filter = ["unit", "is_active"]
    ordering = ["name"]


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ["supplier", "date", "entry_type", "amount"]
    list_filter = ["entry_type", "date", "supplier"]
    search_fields = ["supplier__name", "receipt_no"]
    list_select_related = ["supplier"]
    inlines = [PurchaseItemInline]