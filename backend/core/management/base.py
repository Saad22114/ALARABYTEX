"""أساس مشترك لأوامر الإدارة يضمن سلامة الإخراج العربي على أي طرفية."""

from django.core.management.base import BaseCommand


class ArabicSafeCommand(BaseCommand):
    """BaseCommand يكتب الرسائل العربية دون أن ينهار إذا كان ترميز الطرفية غير UTF-8.

    على ويندوز يكون إخراج العربية إلى ملف أو أنبوب (pipe) بترميز cp1252،
    فيرمي `UnicodeEncodeError` ويُسقط الأمر — وكان يُسقط معه الاختبارات كلها
    لأن `call_command` داخل `setUpClass` يفشل.
    """

    #: أدنى مستوى من `--verbosity` يمرّر إلى ``write_line``.
    minimum_level = 1

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # المستوى المطلوب للمستخدم. لا يضعه Django في مكان واحد يصلح للقراءة
        # من ``write_line``، فنحتفظ به بأنفسنا ونحدّثه عند التنفيذ.
        self.output_level = 1

    def execute(self, *args, **options):
        try:
            self.output_level = int(options.get("verbosity", 1))
        except (TypeError, ValueError):
            self.output_level = 1
        return super().execute(*args, **options)

    def write_line(self, message, style=None, ending="\n", level=None):
        """رسالة واحدة، ولا تُكتب أصلاً إن كان المستوى أدنى من المطلوب.

        ``OutputWrapper`` لا يفحص المستوى بنفسه — الفحص عادةً عند المُنادي
        بـ``if verbosity >= 1``. ونسيان الفحص يُخرج رسائل الأمر حتى مع
        ``verbosity=0``، فيختلط صوتُ الاختبارات بنسخٍ من تقرير البذرة العربية
        في كل تشغيل، وتضيع رسالة الخطأ الحقيقية بينها.
        """
        if (self.minimum_level if level is None else level) > self.output_level:
            return
        text = style(message) if style else message
        try:
            self.stdout.write(text, ending=ending)
        except UnicodeEncodeError:
            stream = getattr(self.stdout, "_out", None) or self.stdout
            encoding = getattr(stream, "encoding", None) or "ascii"
            fallback = text.encode(encoding, "replace").decode(encoding, "replace")
            self.stdout.write(fallback, ending=ending)
