from django.contrib import admin, messages
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

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        try:
            from accounting.services import post_supplier_entry

            post_supplier_entry(obj)
        except Exception:
            import logging

            logging.getLogger("accounting").exception(
                "فشل ترحيل قيد مورد من الإدارة (id=%s)", obj.pk
            )
            self.message_user(
                request,
                "تم حفظ القيد لكن فشل ترحيله محاسبياً — راجع سجلات الأخطاء.",
                level=messages.ERROR,
            )

    def delete_model(self, request, obj):
        payment = None
        if (
            obj.entry_type == LedgerEntry.EntryType.PURCHASE
            and obj.receipt_no
        ):
            payment = LedgerEntry.objects.filter(
                supplier=obj.supplier,
                entry_type=LedgerEntry.EntryType.PAYMENT,
                receipt_no=obj.receipt_no,
                date=obj.date,
                description__startswith="سداد فوري",
            ).first()
        try:
            from accounting.models import JournalEntry
            from accounting.services import unpost_source

            unpost_source(JournalEntry.Source.PURCHASE, obj.pk)
            if payment is not None:
                unpost_source(JournalEntry.Source.PURCHASE, payment.pk)
        except Exception:
            import logging

            logging.getLogger("accounting").exception(
                "فشل إلغاء قيد مورد من الإدارة (id=%s)", obj.pk
            )
        super().delete_model(request, obj)
        if payment is not None:
            payment.delete()