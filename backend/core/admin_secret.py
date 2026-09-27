"""التحقق من الرقم السري لمدير النظام قبل العمليات الحساسة (حذف فرع/مخزن/إعادة ضبط)."""

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.response import Response


def admin_password_ok(password) -> bool:
    """True إذا كان الرقم السري صحيحاً لأحد مستخدمي المدير (ADMIN) النشطين."""
    if not password:
        return False
    from sale_sessions.models import Employee

    User = get_user_model()
    admins = User.objects.filter(
        employee__role=Employee.Role.ADMIN,
        employee__is_active=True,
        is_active=True,
    )
    return any(u.check_password(str(password)) for u in admins)


def require_admin_password(request):
    """يتحقق من ``admin_password`` في جسم الطلب قبل عملية حساسة.

    يرجع ``None`` عند النجاح، أو ``Response`` جاهزاً للإرجاع في حال الخطأ
    (400 عند غياب الرقم السري، 403 عند عدم صحته).
    """
    password = request.data.get("admin_password")
    if not password:
        return Response(
            {"detail": "الرقم السري لمدير النظام مطلوب للتأكيد"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not admin_password_ok(password):
        return Response(
            {"detail": "الرقم السري لمدير النظام غير صحيح"},
            status=status.HTTP_403_FORBIDDEN,
        )
    return None