"""مساعدات الاختبار: موظف مدير مرتبط بمستخدم Django حقيقي للتحقق من الصلاحيات."""

from uuid import uuid4

from django.contrib.auth import get_user_model

from branches.models import Branch
from sale_sessions.models import Employee

User = get_user_model()

AUTH_ADMIN_BRANCH_CODE = "AUTHADM"


def admin_branch():
    branch, _ = Branch.objects.get_or_create(
        name="فرع الاختبار", code=AUTH_ADMIN_BRANCH_CODE, defaults={"is_active": False}
    )
    if branch.is_active:
        branch.is_active = False
        branch.save(update_fields=["is_active"])
    return branch


def make_admin_user(username=None, name="مدير الاختبار", branch=None):
    branch = branch or admin_branch()
    user = User.objects.create_user(
        username=username or f"auth_{uuid4().hex[:8]}",
        password="pass1234",
    )
    employee = Employee(
        name=name,
        branch=branch,
        user=user,
        is_active=True,
    )
    employee.apply_role_preset(Employee.Role.ADMIN)
    employee.save()
    return user, employee


def authenticate_admin(client, user=None, employee=None):
    """يربط client بمستخدم مدير (إما جديد أو مُمرَّر) ويوثّق طلباته."""
    if user is None:
        user, employee = make_admin_user()
    elif employee is None:
        employee = user.employee
    client.force_authenticate(user=user)
    return user, employee