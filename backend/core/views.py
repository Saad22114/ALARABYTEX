"""نقاط تسجيل الدخول والخروج والجلسة الحالية + الحصول على الأقسام والأدوار."""

import logging

from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from appsettings.models import AppSettings
from core.permissions import get_request_employee
from sale_sessions.avatars import (
    AVATAR_EMOJI,
    MAX_AVATAR_REQUEST_BYTES,
    validate_avatar_image,
)
from sale_sessions.models import Employee
from sale_sessions.sections import ROLE_PRESETS, SECTIONS

logger = logging.getLogger(__name__)


def employee_payload(emp):
    return {
        "id": emp.id,
        "name": emp.name,
        "avatar": emp.avatar,
        "avatar_image": emp.avatar_image,
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
        "must_change_password": emp.must_change_password,
        "username": emp.user.username if emp.user_id else None,
        "commission_active": emp.commission_active,
        "birth_date": emp.birth_date,
        "civil_id": emp.civil_id,
        "address": emp.address,
        "hire_date": emp.hire_date,
        "base_salary": str(emp.base_salary),
        "theme": emp.theme or "",
        "last_seen_at": emp.last_seen_at.isoformat() if emp.last_seen_at else None,
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

        # حضور الموظف يُفتح مع دخوله. مغطّى بـ try/except لأن فشل قياس
        # الحضور لا يجوز أن يُبطل دخولاً صحيحاً: المستخدم لو مُنع من الدخول
        # بسبب خطأ في سجلّ الحضور، يكون النظام قد أوقف الناس عن عملهم
        # بسبب ميزةٍ ثانوية.
        try:
            from attendance.services import record_login

            record_login(employee, when=dj_timezone.now())
        except Exception:
            logger.exception("attendance login hook failed for %s", employee)

        return Response(
            {
                "token": token.key,
                "employee": employee_payload(employee),
                "sections": SECTIONS,
                "roles": ROLE_PRESETS,
                "last_login": last_login.timestamp.isoformat() if last_login else None,
                # «آخر ظهور» قبل هذا الدخول. نقطة الدخول بلا مصادقة توكن،
                # فلا يمرّ عبر PresenceTokenAuthentication ولم يُحدَّث الحقل بعد —
                # فالقيمة هنا هي آخر نشاط سابق لا اللحظة الحالية.
                "last_seen_at": (
                    employee.last_seen_at.isoformat() if employee.last_seen_at else None
                ),
            }
        )


class LogoutView(APIView):
    permission_section = "@identity"

    def post(self, request):
        from audit.services import log_audit_logout
        employee = request.user.employee
        log_audit_logout(employee, request)

        # حضور الموظف يُغلق قبل حذف التوكن: بعد الحذف لا يصل الطلب إلى هنا
        # مرةً ثانية، فترتيب السطرين ليس تفصيلاً.
        try:
            from attendance.services import record_logout

            record_logout(employee)
        except Exception:
            logger.exception("attendance logout hook failed for %s", employee)

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


class ChangePasswordView(APIView):
    """تغيير كلمة مرور الموظف الحالي — مطلوب في أول دخول عند تفعيل must_change_password."""

    permission_section = "@identity"

    def post(self, request):
        employee = request.user.employee
        current = request.data.get("current_password") or ""
        new = request.data.get("new_password") or ""
        confirm = request.data.get("confirm_password") or ""
        if not new:
            return Response(
                {"detail": "كلمة المرور الجديدة مطلوبة"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not current:
            return Response(
                {"detail": "كلمة المرور الحالية مطلوبة"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if new != confirm:
            return Response(
                {"detail": "تأكيد كلمة المرور غير متطابق"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(new) < 6:
            return Response(
                {"detail": "كلمة المرور يجب أن تكون 6 أحرف على الأقل"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not request.user.check_password(current):
            return Response(
                {"detail": "كلمة المرور الحالية غير صحيحة"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if new == current:
            return Response(
                {"detail": "كلمة المرور الجديدة يجب أن تختلف عن الحالية"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        request.user.set_password(new)
        request.user.save(update_fields=["password"])
        Employee.objects.filter(pk=employee.pk).update(must_change_password=False)
        employee.must_change_password = False

        from audit.services import log_audit
        log_audit(
            "auth",
            "update",
            employee=employee,
            request=request,
            model_name="sale_sessions.employee",
            object_id=employee.pk,
            object_repr=employee.name,
            changes={"field": "password", "must_change_password": False},
        )
        return Response(
            {
                "detail": "تم تغيير كلمة المرور بنجاح",
                "employee": employee_payload(employee),
                "sections": SECTIONS,
                "roles": ROLE_PRESETS,
            }
        )


class AccountAvatarView(APIView):
    """تحديث صورة الموظف الشخصية.

    يقبل أحدين (أو كليهما معاً):
    - ``avatar``: رمز من الرموز الجاهزة في `AVATAR_EMOJI`. أي رمز خارجها يُرفض.
    - ``avatar_image``: صورة شخصية كـ data URL من جهاز المستخدم (JPEG/PNG/WebP).
    - ``clear_avatar_image: true``: حذف الصورة الشخصية والعودة للأفاتار.
    """

    permission_section = "@identity"

    def patch(self, request):
        employee = request.user.employee

        # حدّ حجم الطلب: data URL صغيرة فقط — يمنع استنزاف الذاكرة بطلب ضخم
        if len(request.body or b"") > MAX_AVATAR_REQUEST_BYTES:
            return Response(
                {"detail": "حجم الطلب كبير جداً"},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

        updates = {}

        if "avatar_image" in request.data:
            value, error = validate_avatar_image(request.data.get("avatar_image"))
            if error:
                return Response(
                    {"detail": error},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            updates["avatar_image"] = value
        elif request.data.get("clear_avatar_image"):
            updates["avatar_image"] = ""

        if "avatar" in request.data:
            avatar = (request.data.get("avatar") or "").strip()
            if avatar not in AVATAR_EMOJI:
                return Response(
                    {"detail": "أفاتار غير صالح — اختر من المجموعة الجاهزة"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            updates["avatar"] = avatar

        if not updates:
            return Response(
                {"detail": "لا يوجد تغيير — أرسل avatar أو avatar_image"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        Employee.objects.filter(pk=employee.pk).update(**updates)
        for field, value in updates.items():
            setattr(employee, field, value)
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
            "avatar_image": emp.avatar_image,
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
            "theme": emp.theme or "",
        })

    def patch(self, request):
        emp_id = request.query_params.get("employee_id")
        if emp_id and emp_id != "me":
            try:
                emp = Employee.objects.select_related("branch", "user").get(pk=emp_id)
            except Employee.DoesNotExist:
                return Response({"detail": "الموظف غير موجود"}, status=status.HTTP_404_NOT_FOUND)
        else:
            emp = get_request_employee(request)
            if emp is None:
                return Response({"detail": "تعذّر تحديد الموظف"}, status=status.HTTP_400_BAD_REQUEST)
        requester = get_request_employee(request)
        if requester is not None and requester.pk != emp.pk and requester.role not in ("admin", "supervisor"):
            return Response({"detail": "لا يمكنك تعديل بيانات موظف آخر"}, status=status.HTTP_403_FORBIDDEN)
        valid_themes = {c[0] for c in AppSettings._meta.get_field("default_theme").choices}
        theme = request.data.get("theme", "").strip()
        if theme and theme not in valid_themes:
            return Response({"theme": "ثيم غير صالح"}, status=status.HTTP_400_BAD_REQUEST)
        emp.theme = theme
        emp.save(update_fields=["theme"])
        return Response({"theme": emp.theme or ""})