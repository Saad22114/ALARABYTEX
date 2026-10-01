# -*- coding: utf-8 -*-
from rest_framework import serializers

from sale_sessions.serializers import EmployeeSerializer

from .models import AttendancePolicy, AttendanceRecord


class AttendancePolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendancePolicy
        fields = (
            "enabled",
            "login_window_start",
            "login_window_end",
            "logout_window_start",
            "logout_window_end",
            "workday_minutes",
            "grace_minutes",
            "day_cutoff_hour",
            "weekend_days",
            "notes",
        )


class AttendanceRecordSerializer(serializers.ModelSerializer):
    employee = EmployeeSerializer(read_only=True)

    class Meta:
        model = AttendanceRecord
        fields = (
            "id",
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
            "note",
        )


class AttendanceRecordWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceRecord
        fields = ("date", "login_at", "logout_at", "excuse", "note")
