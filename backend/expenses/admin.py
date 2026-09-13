from django.contrib import admin
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
