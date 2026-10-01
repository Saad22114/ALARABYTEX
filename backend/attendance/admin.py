# -*- coding: utf-8 -*-
from django.contrib import admin

from .models import AttendancePolicy, AttendanceRecord


@admin.register(AttendancePolicy)
class AttendancePolicyAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "enabled",
        "login_window_start",
        "login_window_end",
        "logout_window_start",
        "logout_window_end",
        "workday_minutes",
        "grace_minutes",
        "day_cutoff_hour",
    )


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = (
        "employee",
        "date",
        "login_at",
        "logout_at",
        "worked_minutes",
        "late_minutes",
        "early_leave_minutes",
        "overtime_minutes",
        "status",
        "excuse",
        "working_day",
        "source",
    )
    list_filter = ("status", "excuse", "working_day", "source", "date")
    search_fields = ("employee__name",)
    readonly_fields = (
        "worked_minutes",
        "late_minutes",
        "early_leave_minutes",
        "overtime_minutes",
        "status",
        "working_day",
    )
