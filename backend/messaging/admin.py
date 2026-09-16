from django.contrib import admin

from .models import Message


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("sender", "receiver", "body", "read_at", "created_at")
    list_filter = ("sender", "receiver")
    search_fields = ("sender__name", "receiver__name", "body")