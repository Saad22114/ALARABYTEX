from django.contrib import admin, messages
from .models import Expense, ExpenseCategory


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "is_system", "is_active", "created_at"]
    search_fields = ["name", "code"]
    list_filter = ["is_system", "is_active"]
    ordering = ["name"]


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = [
        "branch", "category", "date", "amount", "payment_method", "created_at",
    ]
    search_fields = ["branch__name", "category__name", "description", "notes"]
    list_filter = ["branch", "category", "payment_method", "date"]
    ordering = ["-date", "-created_at"]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        try:
            from accounting.services import post_expense

            post_expense(obj)
        except Exception:
            import logging

            logging.getLogger("accounting").exception(
                "فشل ترحيل قيد المصروف من الإدارة (id=%s)", obj.pk
            )
            self.message_user(
                request,
                "تم حفظ المصروف لكن فشل ترحيل القيد المحاسبي — راجع سجلات الأخطاء.",
                level=messages.ERROR,
            )

    def delete_model(self, request, obj):
        try:
            from accounting.models import JournalEntry
            from accounting.services import unpost_source

            unpost_source(JournalEntry.Source.EXPENSE, obj.pk)
        except Exception:
            import logging

            logging.getLogger("accounting").exception(
                "فشل إلغاء قيد المصروف من الإدارة (id=%s)", obj.pk
            )
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        try:
            from accounting.models import JournalEntry
            from accounting.services import unpost_source

            for obj in queryset:
                unpost_source(JournalEntry.Source.EXPENSE, obj.pk)
        except Exception:
            import logging

            logging.getLogger("accounting").exception("فشل إلغاء قيود المصروفات المجمعة")
        super().delete_queryset(request, queryset)
