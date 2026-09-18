from rest_framework import authentication, exceptions

from .models import EmployeeAuthToken


class EmployeeTokenAuthentication(authentication.BaseAuthentication):
    """مصادقة عبر الرمز في ترويسة Authorization: Token <key>."""

    keyword = "Token"

    def authenticate(self, request):
        header = request.META.get("HTTP_AUTHORIZATION", "")
        if not header.startswith(self.keyword + " "):
            return None
        key = header[len(self.keyword) + 1:].strip()
        if not key:
            return None
        try:
            token = EmployeeAuthToken.objects.select_related("employee").get(key=key)
        except EmployeeAuthToken.DoesNotExist:
            raise exceptions.AuthenticationFailed("رمز الدخول غير صالح أو منتهي")
        employee = token.employee
        if not employee.is_active:
            raise exceptions.AuthenticationFailed("هذا الموظف موقوف من النظام")
        return (employee, token)

    def authenticate_header(self, request):
        return self.keyword