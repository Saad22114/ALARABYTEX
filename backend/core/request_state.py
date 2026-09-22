"""حالة الطلب الحالي ضمن نفس الخيط — تُستخدم في تسجيل سجل التدقيق."""

import threading
from contextlib import contextmanager

_context = threading.local()


def set_current_request(request):
    _context.request = request
    _context.audit_suppressed = False


def get_current_request():
    return getattr(_context, "request", None)


def clear_current_request():
    if hasattr(_context, "request"):
        del _context.request
    if hasattr(_context, "audit_suppressed"):
        del _context.audit_suppressed


def audit_suppressed():
    return getattr(_context, "audit_suppressed", False)


@contextmanager
def suppress_audit():
    prev = getattr(_context, "audit_suppressed", False)
    _context.audit_suppressed = True
    try:
        yield
    finally:
        _context.audit_suppressed = prev