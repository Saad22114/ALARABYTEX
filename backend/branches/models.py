from django.db import models
from core.models import TimeStampedModel, ActiveModel


class Branch(TimeStampedModel, ActiveModel):
    name = models.CharField(max_length=150, verbose_name="اسم الفرع")
    code = models.CharField(max_length=30, unique=True, verbose_name="كود الفرع")
    phone = models.CharField(max_length=30, blank=True, verbose_name="رقم الهاتف")
    address = models.CharField(max_length=255, blank=True, verbose_name="العنوان")
    city = models.CharField(max_length=100, blank=True, verbose_name="المدينة")
    notes = models.TextField(blank=True, verbose_name="ملاحظات")

    class Meta:
        verbose_name = "فرع"
        verbose_name_plural = "الفروع"
        ordering = ["name"]

    def __str__(self):
        return self.name
