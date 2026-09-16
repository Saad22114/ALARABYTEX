from django.db import models

from core.models import TimeStampedModel


class Message(TimeStampedModel):
    """رسالة مباشرة بين موظفين — نمط واتساب."""

    sender = models.ForeignKey(
        "sale_sessions.Employee",
        on_delete=models.CASCADE,
        related_name="sent_messages",
        verbose_name="المرسل",
    )
    receiver = models.ForeignKey(
        "sale_sessions.Employee",
        on_delete=models.CASCADE,
        related_name="received_messages",
        verbose_name="المستلم",
    )
    body = models.TextField(verbose_name="النص")
    read_at = models.DateTimeField(null=True, blank=True, verbose_name="وقت القراءة")
    edited_at = models.DateTimeField(null=True, blank=True, verbose_name="وقت التعديل")
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name="وقت الحذف")
    reply_to = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replies",
        verbose_name="الرد على",
    )
    reply_to_body = models.TextField(blank=True, verbose_name="نص الرسالة المُركّبة عليها")

    class Meta:
        verbose_name = "رسالة"
        verbose_name_plural = "الرسائل"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["sender", "receiver"]),
            models.Index(fields=["receiver", "read_at"]),
        ]

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    def __str__(self):
        return f"{self.sender.name} → {self.receiver.name}: {self.body[:40]}"