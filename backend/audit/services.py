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


def _jsonable(value):
    """يحوّل القيم إلى أنواع قابلة للتسلسل في JSONField (Decimal/التاريخ/القواميس)."""
    from datetime import date, datetime, time
    from decimal import Decimal

    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (Decimal, date, datetime, time)):
        return str(value)
    return value


def log_activity(section, event, instance=None, employee=None, request=None, details=None):
    """يسجّل حدثاً تشغيلياً (اعتماد/صرف/توليد/إلغاء…) لا تلتقطه إشارات الحفظ.

    ``event`` نص قصير يظهر في واجهة سجل التدقيق، و``details`` خريطة قيم إضافية
    تُحفظ في حقل ``changes`` للبحث والتصفية لاحقاً.
    """
    from .models import AuditLog

    if request is None or employee is None:
        active_request, actor = current_actor()
        request = request or active_request
        employee = employee or actor

    changes = {"event": event}
    if details:
        changes["details"] = _jsonable(details)

    return log_audit(
        section,
        AuditLog.Action.OTHER,
        instance=instance,
        changes=changes,
        employee=employee,
        request=request,
        model_name=instance._meta.label if instance is not None else event,
        object_id=getattr(instance, "pk", None),
        object_repr=(f"{instance} — {event}" if instance is not None else event)[:255],
    )


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