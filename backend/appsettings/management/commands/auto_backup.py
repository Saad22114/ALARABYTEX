from core.management.base import ArabicSafeCommand

from appsettings.backup import run_auto_backup_if_due, write_backup_file
from appsettings.models import AppSettings


class Command(ArabicSafeCommand):
    help = "ينشئ نسخة احتياطية تلقائية إذا كان موعدها قد حان (تُستدعى من المجدول: cron/systemd timer)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="إنشاء نسخة تلقائية الآن بغضّ النظر عن الجدولة",
        )

    def handle(self, *args, **options):
        from appsettings.crypto import BackupPasswordError

        if options["force"]:
            s = AppSettings.load()
            try:
                rel = write_backup_file(s)
            except BackupPasswordError as exc:
                # بلا مفتاح لا نسخة. exit_code=1 يمنع الجدول من اعتبار
                # «النجاح» صامتاً بينما لم يُكتب ملف واحد.
                self.stderr.write(str(exc))
                raise SystemExit(1)
            from django.utils import timezone

            s.last_auto_backup_at = timezone.now()
            s.last_auto_backup_path = rel
            s.save(update_fields=["last_auto_backup_at", "last_auto_backup_path", "updated_at"])
            self.write_line(f"تم إنشاء النسخة التلقائية: {rel}", self.style.SUCCESS)
            return
        try:
            rel = run_auto_backup_if_due()
        except BackupPasswordError as exc:
            self.stderr.write(str(exc))
            raise SystemExit(1)
        if not rel:
            self.write_line("لا حاجة لنسخة تلقائية الآن (غير مفعّلة أو لم يحن موعدها).")
            return
        self.write_line(f"تم إنشاء النسخة التلقائية: {rel}", self.style.SUCCESS)
        self.write_line("ملاحظة: جدول عندك تشغيل هذا الأمر دورياً (مثال كل ساعة عبر cron) ليتم التنفيذ.")
        self.write_line("  لمستخدمي Windows: أنشئ مهمة «Task Scheduler» تنفّذ هذا الأمر بشكل متكرر.")