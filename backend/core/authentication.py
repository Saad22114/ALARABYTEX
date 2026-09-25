"""التحقق من التوكن مع تتبع «آخر ظهور» للموظف المُصادق عليه."""

import threading
import time

from django.utils import timezone
from rest_framework.authentication import TokenAuthentication

# لا نحدّث حقل آخر ظهور أكثر من مرة كل هذه الثواني لكل موظف
LAST_SEEN_THROTTLE_SECONDS = 10

_lock = threading.Lock()
_last_seen_written = {}


class PresenceTokenAuthentication(TokenAuthentication):
    """توكن كالمعتاد لكنه يحدّث «آخر ظهور» للموظف عند كل طلب مصادق."""

    #: المسارات التي تبقى متاحة لمن عليه تغيير كلمة المرور الإلزامي
    MUST_CHANGE_ALLOWED_PATHS = (
        "/api/auth/me/",
        "/api/auth/logout/",
        "/api/auth/change-password/",
        "/api/settings/public/",
    )

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None
        user, token = result
        employee = getattr(user, "employee", None)
        if employee is not None and employee.must_change_password:
            path = request.path or ""
            if not any(path.startswith(p) for p in self.MUST_CHANGE_ALLOWED_PATHS):
                from rest_framework.exceptions import PermissionDenied

                raise PermissionDenied(
                    {"detail": "يجب تغيير كلمة المرور قبل استخدام النظام", "code": "must_change_password"}
                )
        return result

    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)
        self._touch(user)
        return user, token

    @staticmethod
    def _touch(user):
        employee = getattr(user, "employee", None)
        if employee is None:
            return
        now_ts = time.time()
        with _lock:
            last = _last_seen_written.get(employee.pk)
            if last is not None and (now_ts - last) < LAST_SEEN_THROTTLE_SECONDS:
                return
            _last_seen_written[employee.pk] = now_ts
        from sale_sessions.models import Employee

        Employee.objects.filter(pk=employee.pk).update(last_seen_at=timezone.now())