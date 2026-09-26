"""فرض الصلاحيات على مستوى الخادم.

يعتمد على:
- موظف مرتبط بحساب Django (`request.user.employee`).
- قسم النظام (permission_section) المعرّف على كل View.
- خريطة الفعل من طريقة HTTP: GET/HEAD/OPTIONS → view، POST → create، PUT/PATCH → edit، DELETE → delete.
- إجراء من طيف (@…) لا يتطلب إذناً بقسم — يكتفي بموظف مصادق عليه (مثل الجلسة الحالية).
"""

from rest_framework.permissions import BasePermission, SAFE_METHODS

METHOD_TO_ACTION = {
    "GET": "view",
    "HEAD": "view",
    "OPTIONS": "view",
    "POST": "create",
    "PUT": "edit",
    "PATCH": "edit",
    "DELETE": "delete",
}

# أقسام تُعرض للموظف جزئي الصلاحية ضمن فرعه فقط (السور الحقيقي هو نطاق الفرع،
# لأن من له فرعٌ محدد لا يرى إلا فرعه — فحقه في رؤية قوائم الفروع/المبيعات/الورديات
# لا يفتح له أي فرع آخر، بل مجرد قيمةٍ وحيدة: فرعه).
SCOPE_VIEW_SECTIONS = {"branches", "sales", "sessions"}


def get_request_employee(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return None
    return getattr(user, "employee", None)


def section_view_allowed(request, section):
    """هل يُسمح للموظف بعرض هذا القسم؟

    نفس منطق ``SystemPermission`` لفعل ``view``، لكن متاح خارج صنف الإذن —
    تستخدمه الواجهات التي تعرض نتائج من عدة أقسام (مثل البحث الشامل) لتقصي
    ما لا يملك المستخدم صلاحية رؤيته بدل كشفه في نتائج البحث.
    """
    employee = get_request_employee(request)
    if employee is None or not employee.is_active:
        return False
    if not section or section.startswith("@"):
        return True
    if section in SCOPE_VIEW_SECTIONS and (employee.branch_id or employee.allowed_branches.exists()):
        return True
    return bool(employee.has_permission(section, "view"))


class SystemPermission(BasePermission):
    message = "لا تملك صلاحية تنفيذ هذا الإجراء"

    def has_permission(self, request, view):
        employee = get_request_employee(request)
        if employee is None:
            return False
        if not employee.is_active:
            return False
        section = getattr(view, "permission_section", None)
        if not section:
            return False
        if section.startswith("@"):
            return True
        action = METHOD_TO_ACTION.get(request.method.upper(), "view")
        if action == "view":
            return section_view_allowed(request, section)
        return bool(employee.has_permission(section, action))
