from django.contrib import admin, messages

from .models import Partner, PartnerMovement, PartnerOperation


class PartnerMovementInline(admin.TabularInline):
    model = PartnerMovement
    extra = 0
    readonly_fields = ["partner", "amount"]
    can_delete = False


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ["name", "share_percent", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name"]


@admin.register(PartnerOperation)
class PartnerOperationAdmin(admin.ModelAdmin):
    list_display = ["number", "date", "operation_type", "amount"]
    list_filter = ["operation_type", "date"]
    search_fields = ["number", "notes"]
    inlines = [PartnerMovementInline]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        try:
            from accounting.services import post_partner_operation

            post_partner_operation(obj)
        except Exception:
            import logging

            logging.getLogger("accounting").exception(
                "فشل ترحيل عملية شريك من الإدارة (id=%s)", obj.pk
            )
            self.message_user(
                request,
                "تم حفظ العملية لكن فشل ترحيلها محاسبياً — راجع سجلات الأخطاء.",
                level=messages.ERROR,
            )

    def delete_model(self, request, obj):
        try:
            from accounting.models import JournalEntry
            from accounting.services import unpost_source

            unpost_source(JournalEntry.Source.PARTNER, obj.pk)
        except Exception:
            import logging

            logging.getLogger("accounting").exception(
                "فشل إلغاء قيد عملية شريك من الإدارة (id=%s)", obj.pk
            )
        super().delete_model(request, obj)