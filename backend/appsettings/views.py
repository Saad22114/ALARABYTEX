import json
import mimetypes
import os
import uuid
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

from .backup import backup_file_abspath, backup_document, write_backup_file
from .crypto import (
    BackupCryptoError,
    BackupPasswordError,
    decrypt_backup,
    is_encrypted_envelope,
)
from .models import AppSettings
from .serializers import AppSettingsSerializer


class LogoUploadView(APIView):
    """رفع شعار الموقع وإعادته. لا يتطلب صلاحية «الإعدادات» — جزء من الثيمات والتحكم."""

    permission_section = "themes"

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


class DefaultPaymentMethodView(APIView):
    """Expose only the shared sale payment default to authenticated staff."""

    permission_section = "@identity"

    def get(self, request):
        return Response({"default_payment_method": AppSettings.load().default_payment_method})


class SalesLinksView(APIView):
    """Customer-facing contact and bank-transfer links for sales staff."""
    permission_section = "sales-links"

    def get(self, request):
        s = AppSettings.load()
        return Response({
            "business_name": s.business_name,
            "instagram_url": s.instagram_url,
            "snapchat_url": s.snapchat_url,
            "tiktok_url": s.tiktok_url,
            "facebook_url": s.facebook_url,
            "bank_transfer_url": s.bank_transfer_url,
            "bank_transfer_name": s.bank_transfer_name,
            "bank_transfer_phone": s.bank_transfer_phone,
            "bank_transfer_name_2": s.bank_transfer_name_2,
            "bank_transfer_phone_2": s.bank_transfer_phone_2,
            "qr_images": {
                "instagram": s.instagram_qr_image,
                "snapchat": s.snapchat_qr_image,
                "whatsapp": s.whatsapp_qr_image,
                "bank_transfer": s.bank_transfer_qr_image,
                "bank_transfer_2": s.bank_transfer_qr_image_2,
            },
        })


SALES_QR_FIELDS = {
    "instagram": "instagram_qr_image",
    "snapchat": "snapchat_qr_image",
    "whatsapp": "whatsapp_qr_image",
    "bank_transfer": "bank_transfer_qr_image",
    "bank_transfer_2": "bank_transfer_qr_image_2",
}


class SalesQrImageView(APIView):
    """Upload or remove a customer-facing QR image. Changing it requires settings permission."""
    permission_section = "settings"

    def _field(self, key):
        field = SALES_QR_FIELDS.get(key)
        if not field:
            from django.http import Http404
            raise Http404("رمز QR غير معروف")
        return field

    def post(self, request, key):
        from pathlib import Path

        field = self._field(key)
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "يرجى اختيار صورة"}, status=status.HTTP_400_BAD_REQUEST)
        ext = Path(file.name).suffix.lower()
        allowed = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
        if ext not in allowed or file.content_type not in (allowed[ext], "application/octet-stream"):
            return Response({"detail": "الصيغ المدعومة: PNG أو JPG أو WEBP"}, status=status.HTTP_400_BAD_REQUEST)
        if file.size > 5 * 1024 * 1024:
            return Response({"detail": "حجم الصورة يجب ألا يتجاوز 5 ميجابايت"}, status=status.HTTP_400_BAD_REQUEST)
        signature = file.read(12)
        file.seek(0)
        valid_signature = (
            (ext == ".png" and signature.startswith(b"\x89PNG\r\n\x1a\n")) or
            (ext in {".jpg", ".jpeg"} and signature.startswith(b"\xff\xd8\xff")) or
            (ext == ".webp" and signature.startswith(b"RIFF") and signature[8:12] == b"WEBP")
        )
        if not valid_signature:
            return Response({"detail": "محتوى الملف لا يطابق صيغة الصورة المحددة"}, status=status.HTTP_400_BAD_REQUEST)

        s = AppSettings.load()
        rel = f"sales_qr/{key}-{uuid.uuid4().hex}{ext}"
        path = Path(settings.MEDIA_ROOT) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as output:
            for chunk in file.chunks():
                output.write(chunk)
        old_rel = getattr(s, field)
        setattr(s, field, rel)
        s.save(update_fields=[field, "updated_at"])
        self._remove_old(old_rel, rel)
        return Response({"image": rel}, status=status.HTTP_200_OK)

    def delete(self, request, key):
        field = self._field(key)
        s = AppSettings.load()
        old_rel = getattr(s, field)
        setattr(s, field, "")
        s.save(update_fields=[field, "updated_at"])
        self._remove_old(old_rel, "")
        return Response({"detail": "تمت استعادة رمز QR الافتراضي"}, status=status.HTTP_200_OK)

    @staticmethod
    def _remove_old(rel, keep):
        from pathlib import Path

        if not rel or rel == keep:
            return
        base = (Path(settings.MEDIA_ROOT) / "sales_qr").resolve()
        candidate = (Path(settings.MEDIA_ROOT) / rel).resolve()
        if candidate.parent == base and candidate.is_file():
            candidate.unlink(missing_ok=True)


class SalesQrImageFileView(APIView):
    """Serve customer-facing QR images without requiring a browser auth header."""
    permission_classes = [AllowAny]

    def get(self, request, key):
        field = SALES_QR_FIELDS.get(key)
        if not field:
            raise Http404("رمز QR غير معروف")
        s = AppSettings.load()
        rel = getattr(s, field)
        if not rel:
            raise Http404("لا توجد صورة مخصصة لهذا الرمز")
        base = (Path(settings.MEDIA_ROOT) / "sales_qr").resolve()
        path = (Path(settings.MEDIA_ROOT) / rel).resolve()
        if path.parent != base or not path.is_file():
            raise Http404("الصورة غير موجودة")
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        return FileResponse(open(path, "rb"), content_type=content_type)


class AutoBackupView(APIView):
    """GET lists previously created auto-backups; POST runs one now."""
    permission_section = "settings"

    def get(self, request):
        from .backup import BACKUP_KEEP, list_backup_files

        files = list_backup_files()
        s = AppSettings.load()
        return Response(
            {
                "files": files,
                "keep": BACKUP_KEEP,
                "kept": len(files),
                "full": len(files) >= BACKUP_KEEP,
                "last_auto_backup_at": s.last_auto_backup_at,
                "last_auto_backup_path": s.last_auto_backup_path,
            }
        )

    def post(self, request):
        from django.utils import timezone

        from .backup import BACKUP_KEEP, list_backup_files, write_backup_file

        s = AppSettings.load()
        try:
            rel = write_backup_file(s)
        except BackupPasswordError as exc:
            # لا نسخة تلقائية بلا مفتاح: صامتُها تُوهم الجدولة أن البيانات محفوظة
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        s.last_auto_backup_at = timezone.now()
        s.last_auto_backup_path = rel
        s.save(update_fields=["last_auto_backup_at", "last_auto_backup_path", "updated_at"])
        return Response(
            {
                "detail": "تم إنشاء نسخة احتياطية الآن",
                "path": rel,
                "kept": len(list_backup_files()),
                "keep": BACKUP_KEEP,
            },
            status=status.HTTP_200_OK,
        )


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
        # أعد القراءة من قاعدة البيانات كي تكون استجابة الحفظ هي القيم
        # المثبتة فعلياً، لا قيم الذاكرة التي أُرسلت إلى serializer.
        s.refresh_from_db()
        return Response(ser.data)


class ThemesControlView(APIView):
    """إعدادات المظهر والطباعة، محمية بصلاحية قسم الثيمات والتحكم."""
    permission_section = "themes"
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
    """GET exports ALL data as a downloadable file — always encrypted (AES-256-GCM).

    لا نسخة غير مشفّرة: الملف الذي يخرج من هنا يحتاج كلمة مرور النسخة
    الاحتياطية ليُفتح، فلا يُقرأ بملف نصوص ولا على جهاز آخر.
    """
    permission_section = "settings"

    def get(self, request):
        settings_obj = AppSettings.load()
        try:
            # استخدم المسار نفسه للنسخ اليدوية والتلقائية: محتوى مشفّر واحد،
            # وتسمية موحّدة، وحلقة أسماء تمنع استبدال نسخة أُنشئت في الثانية نفسها.
            rel_path = write_backup_file(settings_obj, prefix="backup")
        except BackupPasswordError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        path = backup_file_abspath(Path(rel_path).name)
        if path is None:
            raise Http404("تعذر العثور على النسخة بعد إنشائها")
        return FileResponse(
            open(path, "rb"),
            as_attachment=True,
            filename=path.name,
            content_type="application/json; charset=utf-8",
        )


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

    Decryption takes the password the request supplies in ``backup_password``
    and falls back to the saved one. The supplied password matters: the saved
    one lives in the database this very restore is about to overwrite, so a
    machine that never held a backup (or one whose password was changed
    since) could not open the file otherwise — and the failure surfaced only
    at the worst moment, after the user had already chosen the file.

    A wrong password is rejected *before* ``restore_backup`` runs, so nothing
    is deleted on a failed attempt.
    """
    permission_section = "settings"

    def post(self, request):
        supplied = ""
        if isinstance(request.data, dict):
            supplied = str(request.data.get("backup_password") or "")

        payload = request.data
        if isinstance(payload, dict) and isinstance(payload.get("content"), str):
            try:
                payload = json.loads(payload["content"])
            except (ValueError, TypeError):
                return Response({"detail": "ملف النسخة الاحتياطية غير صالح"}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(payload, dict):
            return Response({"detail": "البيانات المرسلة غير صالحة"}, status=status.HTTP_400_BAD_REQUEST)
        if is_encrypted_envelope(payload):
            password = supplied or AppSettings.load().backup_password
            try:
                decrypted = decrypt_backup(payload, password)
                payload = json.loads(decrypted.decode("utf-8"))
            except BackupCryptoError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            except (ValueError, UnicodeDecodeError):
                return Response({"detail": "ملف النسخة الاحتياطية غير صالح"}, status=status.HTTP_400_BAD_REQUEST)
        # النسخ الأقدم من تشفير إلزامي كُتبت JSON مقروءاً، وتُستعاد كما هي
        # عمداً: رفضها يحبس نسخة المتجر الوحيدة خلف قاعدة لا يتبعها إلا ما
        # صدر بعد اليوم. القاعدة على التصدير لا على الاستيراد.
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
        from core.admin_secret import admin_password_ok

        return admin_password_ok(password)

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
