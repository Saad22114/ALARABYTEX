from django.contrib import admin

from .models import Account, ClosedPeriod, JournalEntry, JournalLine


class JournalLineInline(admin.TabularInline):
    model = JournalLine
    extra = 0
    readonly_fields = ["account", "debit", "credit", "description"]


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "type", "parent", "is_active", "is_system"]
    list_filter = ["type", "is_active", "is_system"]
    search_fields = ["code", "name"]


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ["number", "date", "description", "source", "created_by", "reversed_at"]
    list_filter = ["source", "date"]
    search_fields = ["number", "description"]
    inlines = [JournalLineInline]


@admin.register(ClosedPeriod)
class ClosedPeriodAdmin(admin.ModelAdmin):
    list_display = ["period_end", "net_profit", "description", "created_at"]