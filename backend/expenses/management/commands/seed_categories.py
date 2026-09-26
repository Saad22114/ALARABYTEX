from core.management.base import ArabicSafeCommand
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


class Command(ArabicSafeCommand):
    help = "إنشاء تصنيفات المصاريف الأساسية"

    def handle(self, *args, **options):
        created = 0
        for name, code in DEFAULT_CATEGORIES:
            _, was_created = ExpenseCategory.objects.get_or_create(
                code=code, defaults={"name": name, "is_system": True}
            )
            if was_created:
                created += 1
        # الاحترام الصريح للـ verbosity: الاستدعاءات الداخلية (الاختبارات والبيانات
        # التجريبية) تمرر verbosity=0 فلا يُكتب شيء على الطرفية إطلاقاً.
        if options.get("verbosity", 1) >= 1:
            self.write_line(
                f"تمت إضافة {created} تصنيف مصروف أساسي", self.style.SUCCESS
            )
            if created == 0:
                self.write_line("جميع التصنيفات الأساسية موجودة بالفعل")