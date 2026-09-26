from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.services import log_activity

from .services import ImportError_, build_rows, build_template, commit_rows, read_sheet
from .specs import ENTITIES

ALLOWED_SUFFIXES = (".xlsx", ".xlsm")
MAX_UPLOAD_BYTES = 8 * 1024 * 1024


class EntityImportView(APIView):
    """أساس نقاط الاستيراد: يحوّل الكيان في المسار إلى قسم صلاحيات.

    ``permission_section`` مُعرَّف على الـView class، وغيّرُه داخل
    ``check_permissions`` (قبل فرض الإذن) هو ما يجعل فحص الصلاحيات
    ``SystemPermission`` يطبَّق على القسم الصحيح لكل كيان على حدة.
    """

    parser_classes = [MultiPartParser, FormParser]
    required_action = "create"

    def check_permissions(self, request):
        spec = ENTITIES.get(self.kwargs.get("entity"))
        if spec is None:
            raise NotFound(f"كيان غير مدعوم: {self.kwargs.get('entity')}")
        self.entity_spec = spec
        self.permission_section = spec.section
        if self.required_action:
            from core.permissions import get_request_employee

            employee = get_request_employee(request)
            if employee is None or not employee.has_permission(spec.section, self.required_action):
                self.permission_denied(
                    request, message="لا تملك صلاحية تنفيذ هذا الإجراء"
                )
            return
        super().check_permissions(request)

    def _read(self, request):
        uploaded = request.FILES.get("file")
        if uploaded is None:
            return None, "أرفق ملف Excel"
        name = (getattr(uploaded, "name", "") or "").lower()
        if not name.endswith(ALLOWED_SUFFIXES):
            return None, "صيغة غير مدعومة — ارفع ملف ‎.xlsx"
        if getattr(uploaded, "size", 0) > MAX_UPLOAD_BYTES:
            return None, "حجم الملف يتجاوز 8 ميجابايت"
        try:
            return read_sheet(uploaded), None
        except ImportError_ as exc:
            return None, str(exc)


def _row_payload(row):
    return {
        "index": row.index,
        "label": row.label,
        "action": row.action,
        "errors": row.errors,
        "data": {
            key: (value if isinstance(value, (int, float, bool, str, type(None))) else str(value))
            for key, value in row.data.items()
        },
    }


class ImportSchemaView(EntityImportView):
    """أعمدة الكيان كما يتوقّعها المحرّك — تبني النموذج في الواجهة."""

    required_action = None

    def get(self, request, entity):
        spec = self.entity_spec
        return Response(
            {
                "entity": spec.key,
                "label": spec.label,
                "plural": spec.plural,
                "columns": [
                    {
                        "key": f.key,
                        "label": f.label,
                        "required": f.required,
                        "kind": f.kind,
                        "default": f.default if isinstance(f.default, (int, float, bool, str, type(None))) else None,
                    }
                    for f in spec.fields
                ],
            }
        )


class ImportPreviewView(EntityImportView):
    """معاينة الملف: تتحقّق من كل صف وتُرجع الأخطاء، دون أي كتابة."""

    def post(self, request, entity):
        spec = self.entity_spec
        parsed, problem = self._read(request)
        if problem:
            return Response({"detail": problem}, status=status.HTTP_400_BAD_REQUEST)

        headers, body = parsed
        rows, columns, unknown = build_rows(spec.key, headers, body)
        return Response(
            {
                "entity": spec.key,
                "label": spec.label,
                "plural": spec.plural,
                "headers": headers,
                "unknown_headers": unknown,
                "matched_columns": [f.label for f in columns if f],
                "summary": {
                    "total": len(rows),
                    "valid": sum(1 for r in rows if r.valid),
                    "invalid": sum(1 for r in rows if not r.valid),
                    "create": sum(1 for r in rows if r.action == "create" and r.valid),
                    "update": sum(1 for r in rows if r.action == "update" and r.valid),
                },
                "rows": [_row_payload(r) for r in rows],
            }
        )


class ImportCommitView(EntityImportView):
    """تنفيذ الاستيراد: يطبّق الصفوف الصحيحة فقط، ويسجّل ما تعذّر."""

    def post(self, request, entity):
        spec = self.entity_spec
        parsed, problem = self._read(request)
        if problem:
            return Response({"detail": problem}, status=status.HTTP_400_BAD_REQUEST)

        headers, body = parsed
        rows, _columns, unknown = build_rows(spec.key, headers, body)
        applicable = [r for r in rows if r.valid]
        if not applicable:
            return Response(
                {
                    "detail": "لا توجد صفوف صالحة للتنفيذ",
                    "summary": {"total": len(rows), "created": 0, "updated": 0, "failed": len(rows)},
                    "rows": [_row_payload(r) for r in rows],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        results = commit_rows(spec.key, applicable)
        created = sum(1 for r, i in results if i is not None and r.action == "create")
        updated = sum(1 for r, i in results if i is not None and r.action == "update")
        failed = [r for r, i in results if r.errors]
        skipped = [r for r in rows if r.errors]

        log_activity(
            spec.section,
            f"استيراد {spec.plural} من Excel",
            details={
                "created": created,
                "updated": updated,
                "failed": len(failed),
                "skipped": len(skipped),
                "file": request.FILES["file"].name,
            },
        )

        return Response(
            {
                "entity": spec.key,
                "summary": {
                    "total": len(rows),
                    "created": created,
                    "updated": updated,
                    "failed": len(failed),
                    "skipped": len(skipped),
                },
                "unknown_headers": unknown,
                "rows": [_row_payload(r) for r in rows],
                "message": f"تم إنشاء {created} وتحديث {updated}، وتعذّر {len(failed)}.",
                "imported_at": timezone.now().isoformat(),
            }
        )


class ImportTemplateView(EntityImportView):
    """تحميل قالب Excel إرشادي للكيان — يتطلّب عرض القسم فقط."""

    required_action = "view"

    def get(self, request, entity):
        spec = self.entity_spec
        workbook = build_template(spec.key)
        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = f'attachment; filename="{spec.key}-template.xlsx"'
        workbook.save(response)
        return response
