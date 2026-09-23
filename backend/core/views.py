"""نقاط تسجيل الدخول والخروج والجلسة الحالية + الحصول على الأقسام والأدوار."""

from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from sale_sessions.avatars import AVATAR_EMOJI
from sale_sessions.models import Employee
from sale_sessions.sections import ROLE_PRESETS, SECTIONS


def employee_payload(emp):
    return {
        "id": emp.id,
        "name": emp.name,
        "avatar": emp.avatar,
        "phone": emp.phone,
        "branch": emp.branch_id,
        "branch_name": emp.branch.name if emp.branch_id else None,
        "role": emp.role,
        "role_label": emp.get_role_display(),
        "permissions": emp.permissions,
        "hidden_sections": emp.hidden_sections,
        "allowed_branches": list(
            emp.allowed_branches.values_list("id", flat=True)
        ),
        "allowed_branches_names": list(
            emp.allowed_branches.order_by("name").values_list("name", flat=True)
        ),
        "is_active": emp.is_active,
        "username": emp.user.username if emp.user_id else None,
        "commission_active": emp.commission_active,
        "birth_date": emp.birth_date,
        "civil_id": emp.civil_id,
        "address": emp.address,
        "hire_date": emp.hire_date,
        "base_salary": str(emp.base_salary),
    }


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        username = (request.data.get("username") or "").strip()
        password = request.data.get("password") or ""
        if not username or not password:
            return Response(
                {"detail": "اسم المستخدم وكلمة المرور مطلوبان"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response(
                {"detail": "اسم المستخدم أو كلمة المرور غير صحيحة"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        employee = getattr(user, "employee", None)
        if employee is None:
            return Response(
                {"detail": "هذا الحساب ليس حساب موظف في النظام"},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not employee.is_active or not user.is_active:
            return Response(
                {"detail": "الحساب غير مفعّل — تواصل مع مدير النظام"},
                status=status.HTTP_403_FORBIDDEN,
            )
        token, _ = Token.objects.get_or_create(user=user)
        from audit.models import AuditLog
        last_login = (
            AuditLog.objects.filter(
                employee=employee, action=AuditLog.Action.LOGIN
            )
            .order_by("-timestamp", "-id")
            .first()
        )
        from django.utils import timezone as dj_timezone
        user.last_login = dj_timezone.now()
        user.save(update_fields=["last_login"])
        from audit.services import log_audit_login
        log_audit_login(employee, request)
        return Response(
            {
                "token": token.key,
                "employee": employee_payload(employee),
                "sections": SECTIONS,
                "roles": ROLE_PRESETS,
                "last_login": last_login.timestamp.isoformat() if last_login else None,
            }
        )


class LogoutView(APIView):
    permission_section = "@identity"

    def post(self, request):
        from audit.services import log_audit_logout
        employee = request.user.employee
        log_audit_logout(employee, request)
        Token.objects.filter(user=request.user).delete()
        return Response({"detail": "تم تسجيل الخروج بنجاح"})


class MeView(APIView):
    permission_section = "@identity"

    def get(self, request):
        employee = request.user.employee
        return Response(
            {
                "employee": employee_payload(employee),
                "sections": SECTIONS,
                "roles": ROLE_PRESETS,
            }
        )


class AccountAvatarView(APIView):
    """تحديث أفاتار الموظف الحالي — من الرموز الجاهزة فقط."""

    permission_section = "@identity"

    def patch(self, request):
        employee = request.user.employee
        avatar = (request.data.get("avatar") or "").strip()
        if avatar not in AVATAR_EMOJI:
            return Response(
                {"detail": "أفاتار غير صالح — اختر من المجموعة الجاهزة"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        Employee.objects.filter(pk=employee.pk).update(avatar=avatar)
        employee.avatar = avatar
        return Response({"employee": employee_payload(employee)})


class EmployeeProfileView(APIView):
    """بطاقة معلومات موظف — بيانات عامة آمنة لأي موظف مصادق عليه."""

    permission_section = "@identity"

    def get(self, request):
        employee_id = request.query_params.get("employee_id")
        if not employee_id:
            return Response({"detail": "حدّد employee_id"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            emp = Employee.objects.select_related("branch", "user").get(pk=employee_id)
        except Employee.DoesNotExist:
            return Response({"detail": "الموظف غير موجود"}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            "id": emp.pk,
            "name": emp.name,
            "avatar": emp.avatar,
            "role": emp.role,
            "role_label": emp.get_role_display(),
            "branch": emp.branch_id,
            "branch_name": emp.branch.name if emp.branch_id else "",
            "phone": emp.phone,
            "email": emp.email,
            "department": emp.department,
            "position": emp.position,
            "employee_code": emp.employee_code or "",
            "hire_date": emp.hire_date,
            "is_active": emp.is_active,
        })