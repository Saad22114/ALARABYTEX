"""Middleware لحفظ الطلب الحالي في حالة الخيط — يُغذّي سجل التدقيق بالـ employee والعنوان."""

from .request_state import clear_current_request, set_current_request


class CurrentRequestMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        set_current_request(request)
        try:
            return self.get_response(request)
        finally:
            clear_current_request()