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