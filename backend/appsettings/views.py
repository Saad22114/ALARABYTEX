import json
import mimetypes
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.files.storage import default_storage
from django.db import transaction
from django.http import FileResponse, HttpResponse, Http404
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from branches.models import Branch
from expenses.models import Expense, ExpenseCategory
from sale_sessions.models import Employee, SaleSession, SaleSessionItem
from sales.models import DailySale
from suppliers.models import Supplier

from .backup import export_backup
from .crypto import (
    BackupCryptoError,
    decrypt_backup,
    encrypt_backup,
    is_encrypted_envelope,
)
from .models import AppSettings
from .serializers import AppSettingsSerializer


class LogoUploadView(APIView):
    """رفع شعار الموقع وإعادته. لا يتطلب صلاحية «الإعدادات» — جزء من الثيمات والتحكم."""

    permission_section = "@themes"

    def _save_logo(self, file):
        ext = os.path.splitext(file.name)[1].lower() or ".png"
        if ext not in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"):
            ext = ".png"
        rel = f"logos/logo{ext}"
        abs_path = Path(settings.MEDIA_ROOT) / rel
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        with abs_path.open("wb") as fh:
            for chunk in file.chunks():
                fh.write(chunk)
        s = AppSettings.load()
        s.logo = rel
        s.save(update_fields=["logo", "updated_at"])
        return rel

    def post(self, request):
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "يرجى إرفاق ملف الصورة (الحقل: file)"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            rel = self._save_logo(file)
        except Exception as exc:
            return Response({"detail": f"تعذر حفظ الشعار: {exc}"}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "تم حفظ الشعار بنجاح", "logo": rel}, status=status.HTTP_200_OK)

    def delete(self, request):
        s = AppSettings.load()
        if s.logo:
            try:
                p = Path(settings.MEDIA_ROOT) / s.logo
                if p.exists():
                    p.unlink()
            except OSError:
                pass
        s.logo = ""
        s.save(update_fields=["logo", "updated_at"])
        return Response({"detail": "تم حذف الشعار بنجاح"}, status=status.HTTP_200_OK)


class LogoFileView(APIView):
    """يُقدّم ملف اللوجو مباشرةً من الباكند حتى يعمل أون لاين (حيث لا تُخدم media بمع DEBUG).

    عام (AllowAny) ليعمل في صفحة تسجيل الدخول ودون تسجيل دخول أصلاً.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        s = AppSettings.load()
        if not s.logo:
            raise Http404("لا يوجد شعار")
        path = Path(settings.MEDIA_ROOT) / s.logo
        if not path.exists() or not path.is_file():
            raise Http404("ملف الشعار غير موجود")
        content_type = mimetypes.guess_type(path.name)[0] or "image/png"
        return FileResponse(open(path, "rb"), content_type=content_type)


class AppSettingsPublicView(APIView):
    """بيانات عامة (اسم النشاط + الشعار + التذييل) لعرضها في صفحة تسجيل الدخول ودون auth."""

    permission_classes = [AllowAny]

    def get(self, request):
        s = AppSettings.load()
        return Response(
            {
                "business_name": s.business_name,
                "logo": s.logo,
                "receipt_footer": s.receipt_footer,
            }
        )


class AutoBackupView(APIView):
    """GET lists previously created auto-backups; POST runs one now."""
    permission_section = "settings"

    def get(self, request):
        from .backup import list_backup_files

        files = list_backup_files()
        return Response(
            {
                "files": files,
                "last_auto_backup_at": AppSettings.load().last_auto_backup_at,
                "last_auto_backup_path": AppSettings.load().last_auto_backup_path,
            }
        )

    def post(self, request):
        from django.utils import timezone

        from .backup import write_backup_file

        s = AppSettings.load()
        rel = write_backup_file(s)
        s.last_auto_backup_at = timezone.now()
        s.last_auto_backup_path = rel
        s.save(update_fields=["last_auto_backup_at", "last_auto_backup_path", "updated_at"])
        return Response({"detail": "تم إنشاء نسخة احتياطية الآن", "path": rel}, status=status.HTTP_200_OK)


class AutoBackupDownloadView(APIView):
    """GET downloads a stored auto-backup file by name; DELETE removes it."""
    permission_section = "settings"

    def get(self, request, name):
        from django.http import FileResponse

        from .backup import backup_file_abspath

        path = backup_file_abspath(name)
        if not path or not path.exists():
            raise Http404("الملف غير موجود")
        return FileResponse(open(path, "rb"), as_attachment=True, filename=path.name)

    def delete(self, request, name):
        from django.utils import timezone

        from .backup import delete_backup_file

        if not delete_backup_file(name):
            raise Http404("الملف غير موجود")
        s = AppSettings.load()
        if s.last_auto_backup_path and Path(s.last_auto_backup_path).name == Path(name).name:
            s.last_auto_backup_at = None
            s.last_auto_backup_path = ""
            s.save(update_fields=["last_auto_backup_at", "last_auto_backup_path", "updated_at"])
        return Response({"detail": "تم حذف النسخة الاحتياطية", "name": name}, status=status.HTTP_200_OK)


class AppSettingsView(APIView):
    """GET returns the singleton settings; PATCH partially updates them."""
    permission_section = "settings"

    def get(self, request):
        s = AppSettings.load()
        return Response(AppSettingsSerializer(s).data)

    def patch(self, request):
        s = AppSettings.load()
        ser = AppSettingsSerializer(s, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)


class ThemesControlView(APIView):
    """قسم «الثيمات والتحكم»: مفتوح لكل الموظفين المصادق عليهم.

    يُعرض ويُحدّث فقط حقول المظهر (default_theme) والطباعة (الفوترة) —
    بدون أي صلاحية قسم، لأن هذا القسم مخصص للجميع حتى لو أُغلقت الإعدادات.
    """
    permission_section = "@themes"
    fields = [
        "logo",
        "default_theme",
        "font_family",
        "receipt_footer",
        "invoice_notes",
        "receipt_show_tax",
        "receipt_show_phone",
        "tax_rate",
    ]
    writable = [
        "default_theme",
        "font_family",
        "receipt_footer",
        "invoice_notes",
        "receipt_show_tax",
        "receipt_show_phone",
    ]

    def get(self, request):
        s = AppSettings.load()
        data = {}
        for field in self.fields:
            value = getattr(s, field)
            data[field] = float(value) if isinstance(value, Decimal) else value
        return Response(data)

    def patch(self, request):
        s = AppSettings.load()
        allowed = {k: v for k, v in request.data.items() if k in self.writable}
        ser = AppSettingsSerializer(s, data=allowed, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(
            {f: (float(getattr(ser.instance, f)) if isinstance(getattr(ser.instance, f), Decimal) else getattr(ser.instance, f)) for f in self.fields}
        )


class BackupView(APIView):
    """GET exports ALL data as a downloadable file; encrypted when a password is set."""
    permission_section = "settings"

    def get(self, request):
        settings_obj = AppSettings.load()
        data = export_backup(settings_obj)
        content = json.dumps(data, ensure_ascii=False, indent=2, default=str)
        if settings_obj.backup_password:
            content = encrypt_backup(content.encode("utf-8"), settings_obj.backup_password).decode("utf-8")
        response = HttpResponse(content, content_type="application/json; charset=utf-8")
        filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


def _coerce_v1(payload):
    """Convert an old v1 backup to the v2 tables format (so old files still restore)."""
    if payload.get("version") == 1 and "tables" not in payload:
        tables = {}
        tables["branches.Branch"] = payload.get("branches", [])
        tables["suppliers.Supplier"] = payload.get("suppliers", [])
        tables["expenses.ExpenseCategory"] = payload.get("expense_categories", [])
        tables["sales.DailySale"] = payload.get("sales", [])
        tables["expenses.Expense"] = payload.get("expenses", [])
        payload["tables"] = tables
    return payload


class RestoreView(APIView):
    """POST replaces ALL data with the uploaded backup.

    Accepts either the parsed backup object or {"content": "<raw file text>"}.
    Encrypted backups are decrypted using the saved backup password.
    """
    permission_section = "settings"

    def post(self, request):
        payload = request.data
        if isinstance(payload, dict) and isinstance(payload.get("content"), str):
            try:
                payload = json.loads(payload["content"])
            except (ValueError, TypeError):
                return Response({"detail": "ملف النسخة الاحتياطية غير صالح"}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(payload, dict):
            return Response({"detail": "البيانات المرسلة غير صالحة"}, status=status.HTTP_400_BAD_REQUEST)
        if is_encrypted_envelope(payload):
            settings_obj = AppSettings.load()
            try:
                decrypted = decrypt_backup(payload, settings_obj.backup_password)
                payload = json.loads(decrypted.decode("utf-8"))
            except BackupCryptoError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            except (ValueError, UnicodeDecodeError):
                return Response({"detail": "ملف النسخة الاحتياطية غير صالح"}, status=status.HTTP_400_BAD_REQUEST)
        if payload.get("version") not in (1, 2):
            return Response({"detail": "إصدار النسخة الاحتياطية غير مدعوم"}, status=status.HTTP_400_BAD_REQUEST)
        payload = _coerce_v1(payload)

        from .backup import restore_backup

        try:
            restore_backup(payload)
        except Exception as exc:
            return Response(
                {"detail": f"تعذرت الاستعادة: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({"detail": "تمت استعادة النسخة الاحتياطية بنجاح"}, status=status.HTTP_200_OK)


class ResetView(APIView):
    """POST resets data. Body: {"confirm": true, "scope": "transactions"|"all", "admin_password": "..."}."""
    permission_section = "settings"

    def _admin_password_ok(self, password):
        from django.contrib.auth import get_user_model

        from sale_sessions.models import Employee

        User = get_user_model()
        admins = User.objects.filter(
            employee__role=Employee.Role.ADMIN,
            employee__is_active=True,
            is_active=True,
        )
        return any(u.check_password(password) for u in admins)

    def post(self, request):
        if request.data.get("confirm") is not True:
            return Response({"detail": "يرجى التأكيد بإرسال confirm: true"}, status=status.HTTP_400_BAD_REQUEST)
        admin_password = request.data.get("admin_password")
        if not admin_password:
            return Response({"detail": "الرقم السري لمدير النظام مطلوب للتأكيد"}, status=status.HTTP_400_BAD_REQUEST)
        if not self._admin_password_ok(str(admin_password)):
            return Response({"detail": "الرقم السري لمدير النظام غير صحيح"}, status=status.HTTP_403_FORBIDDEN)
        scope = request.data.get("scope", "transactions")
        if scope not in ("transactions", "all"):
            return Response({"detail": "scope غير صالح"}, status=status.HTTP_400_BAD_REQUEST)

        deleted = {}
        from core.request_state import suppress_audit

        with suppress_audit():
            with transaction.atomic():
                deleted["expenses"] = Expense.objects.all().delete()[0]
                deleted["sales"] = DailySale.objects.all().delete()[0]
                if scope == "all":
                    deleted["suppliers"] = Supplier.objects.all().delete()[0]
                    deleted["session_items"] = SaleSessionItem.objects.all().delete()[0]
                    deleted["sessions"] = SaleSession.objects.all().delete()[0]
                    deleted["employees"] = Employee.objects.all().delete()[0]
                    deleted["branches"] = Branch.objects.all().delete()[0]
                    deleted["categories"] = ExpenseCategory.objects.all().delete()[0]

        return Response(
            {"detail": "تم إعادة الضبط بنجاح", "deleted": deleted},
            status=status.HTTP_200_OK,
        )