from django.core.management.base import BaseCommand

from expenses.models import ExpenseCategory

DEFAULT_CATEGORIES = [
    ("إيجار", "RENT"),
    ("كهرباء", "ELECTRICITY"),
    ("ماء", "WATER"),
    ("رواتب", "SALARIES"),
    ("نقل", "TRANSPORT"),
    ("صيانة", "MAINTENANCE"),
    ("مشتريات أخرى", "OTHER_PURCHASES"),
    ("مصاريف تشغيلية", "OPERATIONAL"),
    ("أخرى", "OTHER"),
]


class Command(BaseCommand):
    help = "إنشاء تصنيفات المصاريف الأساسية"

    def handle(self, *args, **options):
        created = 0
        for name, code in DEFAULT_CATEGORIES:
            _, was_created = ExpenseCategory.objects.get_or_create(
                code=code, defaults={"name": name, "is_system": True}
            )
            if was_created:
                created += 1
        self.stdout.write(self.style.SUCCESS(f"تمت إضافة {created} تصنيف مصروف أساسي"))
        if created == 0:
            self.stdout.write("جميع التصنيفات الأساسية موجودة بالفعل")