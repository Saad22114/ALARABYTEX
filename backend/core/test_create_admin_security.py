"""حارس أمني لأمر ``create_admin``.

الهدف: منع عودة أي حساب مدير بكلمة مرور افتراضية معروفة إلى المستودع.
كان الأمر يحمل ``--password`` بقيمة ثابتة، فأي شخص يقرأ الكود كان يستطيع
الدخول كمدير على أي خادم جديد لم يغيّر كلمة المرور.
"""

from io import StringIO
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from sale_sessions.models import Employee

User = get_user_model()


class CreateAdminCommandSecurityTests(TestCase):
    def _call(self, **kwargs):
        out = StringIO()
        opts = {
            "username": f"sec_{uuid4().hex[:8]}",
            "name": "مدير تجريبي",
            "force_name": True,
            "stdout": out,
        }
        opts.update(kwargs)
        call_command("create_admin", **opts)
        return out.getvalue()

    def test_username_is_required(self):
        """بلا ``--username`` يجب أن يفشل الأمر، لا أن يختار اسماً افتراضياً."""
        with self.assertRaises(CommandError):
            call_command("create_admin", name="بلا اسم", stdout=StringIO())

    def test_generates_strong_password_when_omitted(self):
        """بلا ``--password``: تُولَّد كلمة عشوائية وتُطبع مرة واحدة."""
        output = self._call()
        user = User.objects.get(username__startswith="sec_")
        self.assertTrue(user.check_password(self._printed_password(output)))
        # الكلمة المُولَّدة ليست ثابتة معروفة
        self.assertNotIn("Saad22114", output)

    def test_rejects_short_password(self):
        """كلمة المرور القصيرة مرفوضة صراحةً بدل القبول الصامت."""
        with self.assertRaises(CommandError):
            self._call(password="123")

    def test_explicit_password_is_hashed_not_stored_plain(self):
        self._call(password="a-very-long-password-1")
        user = User.objects.get(username__startswith="sec_")
        self.assertTrue(user.check_password("a-very-long-password-1"))
        self.assertNotEqual(user.password, "a-very-long-password-1")

    def test_creates_active_admin_employee(self):
        output = self._call()
        username = self._printed_username(output)
        employee = Employee.objects.get(user__username=username)
        self.assertTrue(employee.is_active)
        self.assertEqual(employee.role, Employee.Role.ADMIN)

    # ---------- مساعدات ----------

    @staticmethod
    def _printed_password(output: str) -> str:
        for line in output.splitlines():
            if "المُولَّدة" in line:
                return line.split(":", 1)[1].strip()
        raise AssertionError(f"لم تُطبع كلمة المرور في المخرجات: {output!r}")

    @staticmethod
    def _printed_username(output: str) -> str:
        for line in output.splitlines():
            if "«" in line and "»" in line and "id=" in line:
                return line.split("«", 2)[2].split("»", 1)[0]
        raise AssertionError(f"لم يُطبع اسم المستخدم في المخرجات: {output!r}")


class NoHardcodedAdminCredentialsTests(TestCase):
    """فحص ساكن: لا سرّ مكتوب في أي ملف من الأوامر أو سكربتات النشر."""

    def test_repository_has_no_hardcoded_admin_password(self):
        from pathlib import Path

        backend = Path(__file__).resolve().parent.parent
        # نتجاهل هذا الملف نفسه: هو الذي يحتفظ بالأنماط التي نبحث عنها،
        # وإلا اشتكى من كل سطر فيه.
        self_name = Path(__file__).name
        needles = ("Saad22114", "0987fabric")
        offenders = []
        for path in backend.rglob("*"):
            if not path.is_file() or path.suffix not in {".py", ".sh", ".env", ".example"}:
                continue
            if path.name == self_name:
                continue
            if ".venv" in path.parts or "__pycache__" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for needle in needles:
                # نتجاهل التعليقات التي تشرح أن السرّ كان موجوداً وأُزيل
                if needle in text:
                    for line in text.splitlines():
                        if needle in line and not line.lstrip().startswith("#"):
                            offenders.append(f"{path.name}: {line.strip()}")
        self.assertEqual(offenders, [], f"أسرار مكتوبة في الكود: {offenders}")
