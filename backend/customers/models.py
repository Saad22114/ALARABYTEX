from django.db import models

from core.models import TimeStampedModel, ActiveModel


class Customer(TimeStampedModel, ActiveModel):
    name = models.CharField(max_length=150, verbose_name="اسم الزبون")
    phone = models.CharField(
        max_length=30,
        unique=True,
        blank=True,
        null=True,
        verbose_name="رقم الهاتف",
        help_text="رقم هاتف فريد للزبون",
    )
    email = models.EmailField(blank=True, verbose_name="البريد الإلكتروني")
    address = models.CharField(max_length=255, blank=True, verbose_name="العنوان")
    notes = models.TextField(blank=True, verbose_name="ملاحظات")
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customers",
        verbose_name="الفرع المسجل فيه",
    )

    class Meta:
        verbose_name = "زبون"
        verbose_name_plural = "الزبائن"
        ordering = ["name"]

    def __str__(self):
        return self.name