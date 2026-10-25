from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import get_request_employee

from .models import Notification


def notification_data(item):
    return {
        "id": item.id,
        "kind": item.kind,
        "title": item.title,
        "body": item.body,
        "url": item.url,
        "created_at": item.created_at,
        "read_at": item.read_at,
    }


class NotificationsView(APIView):
    permission_section = "@notifications"

    def get(self, request):
        employee = get_request_employee(request)
        if employee is None:
            return Response({"results": [], "unread_count": 0})
        qs = Notification.objects.filter(recipient=employee).order_by("-created_at", "-id")
        return Response({
            "results": [notification_data(item) for item in qs[:40]],
            "unread_count": qs.filter(read_at__isnull=True).count(),
        })


class NotificationReadView(APIView):
    permission_section = "@notifications"

    def post(self, request, pk=None):
        employee = get_request_employee(request)
        if employee is None:
            return Response({"detail": "الموظف غير موجود"}, status=status.HTTP_403_FORBIDDEN)
        qs = Notification.objects.filter(recipient=employee, read_at__isnull=True)
        if pk is None:
            qs.update(read_at=timezone.now())
        else:
            qs.filter(pk=pk).update(read_at=timezone.now())
        return Response({"detail": "تم تحديث الإشعارات"})
