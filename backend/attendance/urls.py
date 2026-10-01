# -*- coding: utf-8 -*-
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AttendancePolicyView, AttendanceRecordViewSet

router = DefaultRouter()
router.register(r"records", AttendanceRecordViewSet, basename="attendance-record")

urlpatterns = [
    # قبل الراوتر: عنوانُ السياسة سادسٌ مستقلّ، و ``records/`` لا تحجبه.
    path("policy/", AttendancePolicyView.as_view(), name="attendance-policy"),
    path("", include(router.urls)),
]
