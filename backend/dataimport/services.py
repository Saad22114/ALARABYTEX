"""محرك الاستيراد من Excel: قراءة، تحقّق، معاينة، ثم تنفيذ.

المبادئ:
- **معاينة بلا كتابة**: ``preview_rows`` لا تلمس قاعدة البيانات إطلاقاً، فتستطيع
  الواجهة عرض الأخطاء وتصحيح الملف قبل الحفظ.
- **مفتاح طبيعي لا صفّ مكرر**: التكرار يعني "تحديث" لا "إنشاء ثانٍ"، فلا يتضاعف
  المورد ولا يتكرر الموظف في كشف الرواتب.
- **صفّ خاطئ لا يوقف الملف**: كل صف يُنفَّذ داخل نقطة حفظ، فيُحفظ الناجح ويُسجَّل
  الفاشل مع سببه، ويُعاد ملخّص صريح.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from branches.models import Branch
from sale_sessions.models import Employee
from suppliers.models import Fabric, Supplier

from .specs import ENTITIES, FieldSpec, ValueError_, normalize_header, parse_value

MAX_ROWS = 2000
HEADER_SCAN_ROWS = 5


class ImportError_(Exception):
    """خطأ بنيوي في الملف (لا ترويسة، نوع غير مدعوم…)."""


@dataclass
class RowResult:
    index: int
    data: dict
    action: str  # create | update | skip
    errors: list = field(default_factory=list)
    label: str = ""

    @property
    def valid(self):
        return not self.errors and self.action != "skip"


@dataclass
class ImportReport:
    entity: str
    rows: list
    headers: list
    unknown_headers: list
    total_rows: int = 0

    @property
    def summary(self):
        counts = {"total": self.total_rows, "create": 0, "update": 0, "skip": 0, "invalid": 0}
        for row in self.rows:
            if row.errors:
                counts["invalid"] += 1
            else:
                counts[row.action] += 1
        counts["valid"] = counts["create"] + counts["update"]
        return counts


# ------------------------------------------------------------------ قراءة الملف


def read_sheet(uploaded_file):
    """يقرأ أول ورقة ويعيد (العناوين، صفوف القيم) مع تخطّي الأسطر الفارغة."""
    try:
        workbook = load_workbook(uploaded_file, data_only=True, read_only=True)
    except Exception as exc:  # openpyxl يرمي استثناءات متعدّدة حسب تلف الملف
        raise ImportError_(f"تعذّرت قراءة الملف: {exc}") from exc

    sheet = workbook.active
    if sheet is None:
        raise ImportError_("الملف لا يحتوي على أي ورقة")

    raw_rows = []
    for row in sheet.iter_rows(values_only=True):
        if row is None or all(cell is None or str(cell).strip() == "" for cell in row):
            continue
        raw_rows.append(list(row))
        if len(raw_rows) > MAX_ROWS + HEADER_SCAN_ROWS:
            break

    if not raw_rows:
        raise ImportError_("الملف فارغ")

    header_index = _find_header_row(raw_rows)
    headers = [str(c).strip() if c is not None else "" for c in raw_rows[header_index]]
    body = raw_rows[header_index + 1 :]
    workbook.close()
    return headers, body


def _find_header_row(rows):
    """الملفات المُصدَّرة قد تبدأ بصفوف عنوان/شعار — نختار صفّ العناوين الأعلى كثافة."""
    best_index, best_score = 0, -1
    for index, row in enumerate(rows[:HEADER_SCAN_ROWS]):
        filled = sum(1 for cell in row if cell is not None and str(cell).strip())
        if filled > best_score:
            best_index, best_score = index, filled
    return best_index


# ------------------------------------------------------------------ التحقّق


def _cell(row, position):
    return row[position] if position < len(row) else None


def _lookup_references(value, model, label_field="name"):
    """يحوّل اسماً نصياً (اسم مورد/فرع) إلى كائن، أو يرفع خطأ واضحاً."""
    if value is None or str(value).strip() == "":
        return None
    if isinstance(value, (Branch, Supplier)):
        return value
    text = str(value).strip()
    obj = model.objects.filter(**{f"{label_field}__iexact": text}).first()
    if obj is None:
        obj = model.objects.filter(name__iexact=text).first()
    if obj is None:
        raise ValueError_(f"لا يوجد {label_field} باسم «{text}»")
    return obj


def build_rows(entity_key, headers, body):
    """يحوّل صفوف Excel إلى ``RowResult`` مع أخطاء لكل صف (بلا كتابة)."""
    spec = ENTITIES[entity_key]
    header_map = spec.header_map()

    columns = []
    unknown = []
    for position, header in enumerate(headers):
        field_spec = header_map.get(normalize_header(header))
        if field_spec is None:
            if header:
                unknown.append(header)
            columns.append(None)
        else:
            columns.append(field_spec)

    rows = []
    for offset, raw in enumerate(body[:MAX_ROWS]):
        index = offset + 2  # رقم الصف في Excel (العنوان = 1)
        values = {}
        errors = []
        for position, field_spec in enumerate(columns):
            if field_spec is None:
                continue
            cell = _cell(raw, position)
            try:
                value = parse_value(field_spec, cell)
            except ValueError_ as exc:
                errors.append(f"{field_spec.label}: {exc}")
                continue
            if value is not None:
                values[field_spec.key] = value

        for field_spec in spec.required_fields:
            if values.get(field_spec.key) in (None, ""):
                errors.append(f"{field_spec.label}: حقل مطلوب")

        values, ref_errors = _resolve_references(spec, values)
        errors.extend(ref_errors)

        label = str(values.get("name") or values.get("code") or f"صف {index}")
        if errors:
            rows.append(RowResult(index=index, data=values, action="skip", errors=errors, label=label))
            continue

        if spec.key == "employees":
            if not Employee.objects.filter(name__iexact=values["name"]).exists():
                action = "create"
            else:
                action = "update"
        elif spec.key == "fabrics":
            code = values.get("code")
            if code and Fabric.objects.filter(code__iexact=code).exists():
                action = "update"
            elif Fabric.objects.filter(name__iexact=values["name"]).exists():
                action = "update"
            else:
                action = "create"
        else:
            action = "update" if Supplier.objects.filter(name__iexact=values["name"]).exists() else "create"

        rows.append(RowResult(index=index, data=values, action=action, label=label))

    return rows, columns, unknown


def _resolve_references(spec, values):
    """يحلّ حقول ``kind=reference`` (المورد/الفرع) إلى كائنات، مع رص الأخطاء."""
    errors = []
    resolved = dict(values)
    for field_spec in spec.fields:
        if field_spec.kind != "reference" or field_spec.key not in resolved:
            continue
        if field_spec.key == "supplier":
            try:
                resolved[field_spec.key] = _lookup_references(resolved[field_spec.key], Supplier)
            except ValueError_ as exc:
                errors.append(f"{field_spec.label}: {exc}")
                resolved.pop(field_spec.key, None)
        elif field_spec.key == "branch":
            try:
                resolved[field_spec.key] = _lookup_references(resolved[field_spec.key], Branch)
            except ValueError_ as exc:
                errors.append(f"{field_spec.label}: {exc}")
                resolved.pop(field_spec.key, None)
    return resolved, errors


# ------------------------------------------------------------------ التنفيذ


def _existing(spec, values):
    if spec.key == "employees":
        return Employee.objects.filter(name__iexact=values["name"]).first()
    if spec.key == "fabrics":
        code = values.get("code")
        if code:
            found = Fabric.objects.filter(code__iexact=code).first()
            if found:
                return found
        return Fabric.objects.filter(name__iexact=values["name"]).first()
    return Supplier.objects.filter(name__iexact=values["name"]).first()


MODEL_FOR = {"suppliers": Supplier, "fabrics": Fabric, "employees": Employee}


def _apply_row(spec, values):
    """ينشئ الصف أو يحدّث القائم منه، ويعيد (كائن، action)."""
    model = MODEL_FOR[spec.key]
    instance = _existing(spec, values)
    if instance is not None:
        for key, value in values.items():
            setattr(instance, key, value)
        instance.save()
        return instance, "update"

    instance = model(**values)
    if spec.key == "employees" and "permissions" not in values:
        role = values.get("role") or Employee.Role.CUSTOM
        instance.role = role
        instance.apply_role_preset(role)
    instance.save()
    return instance, "create"


def commit_rows(entity_key, rows):
    """ينفّذ الصفوف الصالحة فقط، ويعيد قائمة بالنتائج مع الأخطاء الحاصلة أثناء الحفظ.

    كل صف داخل ``atomic`` مستقل (حفظ نقطة) حتى لا يُبطل خطأُ صفٍّ واحدٌ ما
    حُفظ من الصفوف السابقة — وهو سلوك مقصود: صفٌّ فاسد يجب ألّا يُسقط الملف.
    """
    from django.db import transaction

    spec = ENTITIES[entity_key]
    results = []
    for row in rows:
        if row.errors:
            results.append((row, None))
            continue
        try:
            with transaction.atomic():
                instance, action = _apply_row(spec, row.data)
            row.action = action
            results.append((row, instance))
        except Exception as exc:
            row.errors.append(f"فشل الحفظ: {exc}")
            results.append((row, None))
    return results


# ------------------------------------------------------------------ القالب


HEADER_FILL = PatternFill("solid", fgColor="1F2937")
REQUIRED_FILL = PatternFill("solid", fgColor="B91C1C")


def build_template(entity_key):
    """ورقة إرشادية: ترويسة بالأسماء العربية + صف مثال + ملاحظات."""
    spec = ENTITIES[entity_key]
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = spec.plural[:31]

    for column, field_spec in enumerate(spec.fields, start=1):
        cell = sheet.cell(row=1, column=column, value=field_spec.label)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = REQUIRED_FILL if field_spec.required else HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        sheet.column_dimensions[get_column_letter(column)].width = max(14, len(field_spec.label) + 4)
    sheet.row_dimensions[1].height = 26

    example = []
    for field_spec in spec.fields:
        example.append(_example_value(spec, field_spec))
    for column, value in enumerate(example, start=1):
        cell = sheet.cell(row=2, column=column, value=value)
        cell.font = Font(italic=True, color="6B7280")

    # القالب يُملأ لا يُقرأ: تجميد الرأس يبقى أسماء الأعمدة أمام العين
    # عند التمرير في ملفٍ فيه مئة صفّ، والفلتر يتيح النظر في عمودٍ واحد.
    # الورقة تُقرأ من اليمين كبقية مصدّرات المشروع.
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:{get_column_letter(len(spec.fields))}1"
    sheet.sheet_view.rightToLeft = True
    sheet.page_setup.orientation = "landscape"
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.page_setup.fitToWidth = 1

    # التعليمات في ورقة منفصلة: لو كُتبت في ورقة البيانات لقرأها المحرّك
    # كصفوف استيراد وأفسدت الملف.
    notes_sheet = workbook.create_sheet("تعليمات")
    notes_sheet.column_dimensions["A"].width = 90
    notes_sheet.sheet_view.rightToLeft = True
    title = notes_sheet.cell(row=1, column=1, value=f"قالب استيراد {spec.plural}")
    title.font = Font(bold=True, size=14)
    row = 3
    for line in _template_notes(spec):
        cell = notes_sheet.cell(row=row, column=1, value=f"• {line}")
        cell.font = Font(color="4B5563")
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        row += 1
    return workbook


def _example_value(spec, field_spec):
    samples = {
        "suppliers": {"name": "مورد النسيج", "company_name": "شركة النسيج", "phone": "0555000111", "email": "info@example.com", "city": "دمشق", "is_active": "نعم"},
        "fabrics": {"name": "قطن مصري", "code": "CT-001", "unit": "ياردة", "color": "أبيض", "purchase_price": 12.5, "sale_price_yard": 18, "min_stock": 100, "supplier": "مورد النسيج", "is_active": "نعم"},
        "employees": {"name": "أحمد محمد", "employee_code": "E-001", "phone": "0555000222", "department": "المبيعات", "role": "مبيعات", "base_salary": 500000, "hire_date": "2026-01-15", "is_active": "نعم"},
    }
    return samples[spec.key].get(field_spec.key)


def _template_notes(spec):
    notes = [
        f"احذف صف المثال (الصف الثاني) قبل الرفع.",
        f"التسلسل هو: {'، '.join(f.label for f in spec.required_fields)}.",
        "التكرار يقوم بالتحديث: الصف الذي يحمل نفس الاسم يُحدَّث ولا يُنشأ من جديد.",
        "الصف الفارغ يتجاهَل، والصف الذي فيه خطأ لا يوقف بقية الصفوف.",
    ]
    if spec.key == "fabrics":
        notes.append("«الرمز» هو مفتاح التطابق الأول؛ فإن كان فارغاً يُطابَق بالاسم.")
        notes.append("وحدة البيع: ياردة أو لفة.")
        notes.append("«المورد» يُكتب باسمه كما هو مسجَّل في قائمة الموردين.")
    if spec.key == "employees":
        notes.append("«الدور»: مدير، مشرف، مبيعات، محاسب، مشاهد، مخصص — يحدّد صلاحيات الموظف.")
        notes.append("«الفرع» يُكتب باسم الفرع كما هو مسجَّل.")
        notes.append("إن كان «الدور» فارغاً يُعامل كمخصص بصلاحيات فارغة.")
    if spec.key == "suppliers":
        notes.append("«نشط»: نعم أو لا.")
    return notes
