from django.contrib import admin

from .models import MachineCollection


@admin.register(MachineCollection)
class MachineCollectionAdmin(admin.ModelAdmin):
    list_display = ("date", "amount", "method", "branch", "reference", "created_by")
    list_filter = ("method", "branch", "date")
    search_fields = ("reference", "notes")