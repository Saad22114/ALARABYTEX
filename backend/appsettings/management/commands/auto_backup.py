from django.core.management.base import BaseCommand
from django.utils import timezone

from appsettings.backup import should_run_auto_backup, write_backup_file
from appsettings.models import AppSettings


class Command(BaseCommand):
    help = "ينشئ نسخة احتياطية تلقائية إذا كان موعدها قد حان (تُستدعى من المجدول: cron/systemd timer)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="إنشاء نسخة تلقائية الآن بغضّ النظر عن الجدولة",
        )

    def handle(self, *args, **options):
        s = AppSettings.load()
        if not options["force"] and not should_run_auto_backup(s):
            self.stdout.write("لا حاجة لنسخة تلقائية الآن (غير مفعّلة أو لم يحن موعدها).")
            return
        rel = write_backup_file(s)
        s.last_auto_backup_at = timezone.now()
        s.last_auto_backup_path = rel
        s.save(update_fields=["last_auto_backup_at", "last_auto_backup_path", "updated_at"])
        self.stdout.write(self.style.SUCCESS(f"تم إنشاء النسخة التلقائية: {rel}"))
        self.stdout.write("ملاحظة: جدول عندك تشغيل هذا الأمر دورياً (مثال كل ساعة عبر cron) ليتم التنفيذ.")
        self.stdout.write("  لمستخدمي Windows: أنشئ مهمة «Task Scheduler» تنفّذ هذا الأمر بشكل متكرر.")