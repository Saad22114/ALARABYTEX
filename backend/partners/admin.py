from django.contrib import admin

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