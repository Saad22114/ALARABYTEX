import secrets

from django.db import models

from sale_sessions.models import Employee


class EmployeeAuthToken(models.Model):
    """رمز الدخول الخاص بالموظف (نظام تسجيل الدخول بدل مستخدم Django)."""

    key = models.CharField(max_length=64, primary_key=True, verbose_name="المفتاح")
    employee = models.OneToOneField(
        Employee, on_delete=models.CASCADE, related_name="auth_token", verbose_name="الموظف"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")

    class Meta:
        verbose_name = "رمز دخول"
        verbose_name_plural = "رموز الدخول"

    def __str__(self):
        return f"رمز {self.employee.name}"

    @classmethod
    def generate_key(cls):
        return secrets.token_hex(32)