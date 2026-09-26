"""أساس مشترك لأوامر الإدارة يضمن سلامة الإخراج العربي على أي طرفية."""

from django.core.management.base import BaseCommand


class ArabicSafeCommand(BaseCommand):
    """BaseCommand يكتب الرسائل العربية دون أن ينهار إذا كان ترميز الطرفية غير UTF-8.

    على ويندوز يكون إخراج العربية إلى ملف أو أنبوب (pipe) بترميز cp1252،
    فيرمي `UnicodeEncodeError` ويُسقط الأمر — وكان يُسقط معه الاختبارات كلها
    لأن `call_command` داخل `setUpClass` يفشل.
    """

    def write_line(self, message, style=None, ending="\n"):
        text = style(message) if style else message
        try:
            self.stdout.write(text, ending=ending)
        except UnicodeEncodeError:
            stream = getattr(self.stdout, "_out", None) or self.stdout
            encoding = getattr(stream, "encoding", None) or "ascii"
            fallback = text.encode(encoding, "replace").decode(encoding, "replace")
            self.stdout.write(fallback, ending=ending)
