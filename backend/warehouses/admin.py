from django.contrib import admin

from .models import (
    DocumentSequence,
    FabricRoll,
    GoodsReceipt,
    GoodsReceiptItem,
    StockAdjustment,
    StockAdjustmentItem,
    StockCount,
    StockCountItem,
    StockMovement,
    StockTransfer,
    StockTransferItem,
    Warehouse,
)


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "location", "manager_name", "is_active")
    search_fields = ("name", "code", "location")


@admin.register(FabricRoll)
class FabricRollAdmin(admin.ModelAdmin):
    list_display = ("code", "warehouse", "fabric", "remaining_yards", "status")
    search_fields = ("code", "fabric__name")
    list_filter = ("warehouse", "status")


class GoodsReceiptItemInline(admin.TabularInline):
    model = GoodsReceiptItem
    extra = 0


@admin.register(GoodsReceipt)
class GoodsReceiptAdmin(admin.ModelAdmin):
    list_display = ("number", "warehouse", "supplier", "date", "status")
    search_fields = ("number", "supplier_receipt_no")
    list_filter = ("status", "warehouse")
    inlines = [GoodsReceiptItemInline]


class StockTransferItemInline(admin.TabularInline):
    model = StockTransferItem
    extra = 0


@admin.register(StockTransfer)
class StockTransferAdmin(admin.ModelAdmin):
    list_display = ("number", "from_warehouse", "to_warehouse", "date", "status")
    search_fields = ("number",)
    list_filter = ("status", "from_warehouse", "to_warehouse")
    inlines = [StockTransferItemInline]


class StockAdjustmentItemInline(admin.TabularInline):
    model = StockAdjustmentItem
    extra = 0


@admin.register(StockAdjustment)
class StockAdjustmentAdmin(admin.ModelAdmin):
    list_display = ("number", "warehouse", "date", "direction", "reason")
    search_fields = ("number",)
    list_filter = ("direction", "reason", "warehouse")
    inlines = [StockAdjustmentItemInline]


class StockCountItemInline(admin.TabularInline):
    model = StockCountItem
    extra = 0


@admin.register(StockCount)
class StockCountAdmin(admin.ModelAdmin):
    list_display = ("number", "warehouse", "date", "status")
    search_fields = ("number",)
    list_filter = ("status", "warehouse")
    inlines = [StockCountItemInline]


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("date", "warehouse", "fabric", "movement_type", "quantity", "reference_no")
    search_fields = ("fabric__name", "reference_no")
    list_filter = ("movement_type", "warehouse")


@admin.register(DocumentSequence)
class DocumentSequenceAdmin(admin.ModelAdmin):
    list_display = ("key", "value")