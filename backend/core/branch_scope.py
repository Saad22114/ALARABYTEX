"""نطاق الفروع المسموح للموظف الحالي.

القاعدة:
- مدير النظام / المشرف / الموظف صاحب «دخول متعدد الفروع» يرون كل الفروع.
- عدا ذلك: يرى الموظف فرعه فقط (وإن لم يكن له فرع فلا يرى شيئاً).
"""

from django.db.models import Q

from .permissions import get_request_employee

MANAGER_ROLES = ("admin", "supervisor")


def employee_branch_scope(employee):
    """يرجع مجموعة معرّفات الفروع المسموحة، أو None للدلالة على عدم وجود تقييد."""
    if employee is None:
        return None
    if employee.role in MANAGER_ROLES:
        return None
    # قائمة الفروع المختارة (كثير-لكثير): الفرع الأساسي + الاختيارات الإضافية.
    if employee.allowed_branches.exists():
        allowed = set()
        if employee.branch_id:
            allowed.add(employee.branch_id)
        allowed.update(employee.allowed_branches.values_list("id", flat=True))
        return allowed or set()
    # سلوك قديم: «دخول متعدد الفروع» يعني كل الفروع؛ أو فرع واحد فقط؛ أو لا شيء.
    if employee.multi_branch_access:
        return None
    if not employee.branch_id:
        return set()
    return {employee.branch_id}


def allowed_branch_ids(request):
    return employee_branch_scope(get_request_employee(request))


def scope_queryset(request, queryset, branch_field="branch"):
    """يقصّ البيانات إلى الفروع المسموحة للموظف الحالي.

    branch_field: اسم حقل العلاقة إلى Branch (مثل "branch"، "warehouse__branch"
    بالنسبة للكائنات المرتبطة بمخزن مرتبط بفرع)، أو عمود جاهز مثل "id".
    """
    allowed = allowed_branch_ids(request)
    if allowed is None:
        return queryset
    if not allowed:
        return queryset.none()
    if branch_field == "id" or branch_field.endswith("_id"):
        lookup = f"{branch_field}__in"
    else:
        lookup = f"{branch_field}_id__in"
    return queryset.filter(**{lookup: allowed})


def scope_queryset_or(request, queryset, branch_fields):
    """مثل scope_queryset لكن يقصّ عبر أيّ من حقول فرعية متعددة (OR)."""
    allowed = allowed_branch_ids(request)
    if allowed is None:
        return queryset
    if not allowed:
        return queryset.none()
    q = Q()
    for field in branch_fields:
        if field == "id" or field.endswith("_id"):
            q |= Q(**{f"{field}__in": allowed})
        else:
            q |= Q(**{f"{field}_id__in": allowed})
    return queryset.filter(q)


def _branch_id_of(value):
    """يستخرج معرف الفرع من: فرع، مخزن، أو معرّف خام. None إن لم يُحدَّد."""
    if value is None:
        return None
    if isinstance(value, (int,)):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    if hasattr(value, "branch_id") and value.branch_id is not None:
        return value.branch_id
    if hasattr(value, "id"):
        return value.id
    return None


def write_scope_allowed(request, branches=(), warehouses=()):
    """هل يُسمح للموظف الحالي بالكتابة على هذه الفروع/المخازن؟

    - مدير/مشرف أو سياق بلا موظف: لا يوجد تقييد (True).
    - فرقّات فارغة (لا هدف للكتابة): يُسمح.
    - فرقّات محددة: كلها يجب أن تقع ضمن نطاق الفروع المسموح.
    """
    employee = get_request_employee(request)
    if employee is None:
        return True
    allowed = employee_branch_scope(employee)
    if allowed is None:
        return True
    if not allowed:
        return False
    ids = set()
    for b in branches:
        bid = _branch_id_of(b)
        if bid is not None:
            ids.add(bid)
    for w in warehouses:
        bid = _branch_id_of(w)
        if bid is not None:
            ids.add(bid)
    if not ids:
        return True
    return ids.issubset(allowed)


def assert_write_branch_allowed(request, branches=(), warehouses=(), message=None):
    """يمنع (403) الكتابة على فروع/مخازن خارج نطاق الموظف الحالي."""
    from rest_framework.exceptions import PermissionDenied

    if not write_scope_allowed(request, branches=branches, warehouses=warehouses):
        raise PermissionDenied(
            message or "لا يمكنك التعامل مع فرع خارج نطاق فروعك المسموحة"
        )