"""تسجيل سجل التدقيق مع استخراج الفاعل تلقائياً من الطلب الحالي."""

from audit.models import AuditLog


def current_actor():
    from core.permissions import get_request_employee
    from core.request_state import get_current_request

    request = get_current_request()
    if request is None:
        return None, None
    return request, get_request_employee(request)


def log_audit(
    section,
    action,
    instance=None,
    changes=None,
    employee=None,
    request=None,
    model_name=None,
    object_id=None,
    object_repr=None,
    extra=None,
):
    if request is None or employee is None:
        active_request, actor = current_actor()
        request = request or active_request
        employee = employee or actor

    if instance is not None:
        model_name = model_name or instance._meta.label
        if object_id is None:
            object_id = getattr(instance, "pk", None)
        if object_repr is None:
            object_repr = str(instance)[:255]

    AuditLog.objects.create(
        employee=employee,
        section=section,
        action=action,
        model_name=model_name or "",
        object_id=object_id,
        object_repr=object_repr or "",
        changes=changes or {},
        ip=getattr(request, "META", {}).get("REMOTE_ADDR") if request else None,
        method=request.method if request else "",
        path=request.path if request else "",
    )
    return None


def log_audit_login(employee, request):
    log_audit(
        "auth",
        AuditLog.Action.LOGIN,
        employee=employee,
        request=request,
        model_name="sale_sessions.employee",
        object_id=employee.pk,
        object_repr=employee.name,
    )


def log_audit_logout(employee, request):
    log_audit(
        "auth",
        AuditLog.Action.LOGOUT,
        employee=employee,
        request=request,
        model_name="sale_sessions.employee",
        object_id=employee.pk,
        object_repr=employee.name,
    )