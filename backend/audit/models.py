from django.db import models


class AuditLog(models.Model):
    class Action(models.TextChoices):
        CREATE = "create", "إنشاء"
        UPDATE = "update", "تعديل"
        DELETE = "delete", "حذف"
        LOGIN = "login", "تسجيل دخول"
        LOGOUT = "logout", "تسجيل خروج"
        OTHER = "other", "أخرى"

    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="الوقت")
    employee = models.ForeignKey(
        "sale_sessions.Employee",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
        verbose_name="الموظف",
    )
    section = models.CharField(max_length=50, blank=True, default="", verbose_name="القسم")
    action = models.CharField(
        max_length=20, choices=Action.choices, default=Action.OTHER, verbose_name="الإجراء"
    )
    model_name = models.CharField(max_length=120, blank=True, default="", verbose_name="النموذج")
    object_id = models.PositiveBigIntegerField(null=True, blank=True, verbose_name="معرّف السجل")
    object_repr = models.CharField(max_length=255, blank=True, default="", verbose_name="وصف السجل")
    changes = models.JSONField(default=dict, blank=True, verbose_name="التغييرات")
    ip = models.GenericIPAddressField(null=True, blank=True, verbose_name="العنوان")
    method = models.CharField(max_length=10, blank=True, default="", verbose_name="الطريقة")
    path = models.CharField(max_length=500, blank=True, default="", verbose_name="المسار")

    class Meta:
        verbose_name = "سجل تدقيق"
        verbose_name_plural = "سجلات التدقيق"
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["employee", "timestamp"]),
            models.Index(fields=["section", "timestamp"]),
        ]

    def __str__(self):
        return f"{self.timestamp:%Y-%m-%d %H:%M} — {self.get_action_display()}"