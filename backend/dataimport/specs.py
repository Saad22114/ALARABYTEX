"""تعريف أعمدة الاستيراد لكل كيان: أسماء عربية وإنجليزية مقبولة، وأنواع التحويل.

الفصل بين "ما الأعمدة" و"كيف يُستورد" يجعل القالب المُنزَّل مطابقاً تماماً
للمُتحقَّق منه، ويجعل إضافة عمود جديد تغيّراً في مكان واحد.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

# Excel يعرض التواريخ كأيام منذ 1899-12-30
_EXCEL_EPOCH = date(1899, 12, 30)

TRUE_VALUES = {"نعم", "صح", "true", "yes", "1", "y", "x", "√", "مفعل", "مفعّل"}
FALSE_VALUES = {"لا", "خطأ", "false", "no", "0", "n", "✗", "غير مفعل", "معطل"}


@dataclass(frozen=True)
class FieldSpec:
    key: str
    label: str
    headers: tuple
    kind: str = "text"  # text | int | decimal | bool | choice | date
    required: bool = False
    choices: dict = field(default_factory=dict)  # value alias (lowercase) -> canonical
    default: object = None
    help: str = ""


@dataclass(frozen=True)
class EntitySpec:
    key: str
    label: str
    plural: str
    section: str
    model_label: str
    natural_key: tuple
    fields: tuple
    unique_by_name: bool = True

    @property
    def required_fields(self):
        return [f for f in self.fields if f.required]

    def header_map(self):
        """تريطة: ترويسة مُطبَّعة (lowercase, بلا تشكيل/تطويل) → FieldSpec."""
        mapping = {}
        for spec in self.fields:
            for header in (spec.label, *spec.headers):
                mapping[normalize_header(header)] = spec
        return mapping


def normalize_header(value):
    """يوحّد شكل الترويسة:-case، مسافات، وتطبيع عربي (أ/إ/آ→ا، ة→ه، ى→ي)."""
    if value is None:
        return ""
    text = str(value).strip().lower().replace("\u00a0", " ")
    text = text.replace("\ufeff", "")
    for src, dst in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ة", "ه"), ("ى", "ي"), ("\u064b", ""), ("\u064c", ""), ("\u064d", ""), ("\u064e", ""), ("\u064f", ""), ("\u0650", "")):
        text = text.replace(src, dst)
    return " ".join(text.split())


# ------------------------------------------------------------------ الموردون

SUPPLIER_FIELDS = (
    FieldSpec("name", "اسم المورد", ("name", "supplier", "supplier_name"), required=True),
    FieldSpec("company_name", "اسم الشركة", ("company", "company_name")),
    FieldSpec("phone", "الهاتف", ("phone", "mobile", "tel")),
    FieldSpec("email", "البريد الإلكتروني", ("email", "mail")),
    FieldSpec("city", "المدينة", ("city",)),
    FieldSpec("country", "الدولة", ("country",)),
    FieldSpec("tax_number", "الرقم الضريبي", ("tax_number", "tax_no", "vat")),
    FieldSpec("address", "العنوان", ("address",)),
    FieldSpec("notes", "ملاحظات", ("notes", "note", "comment")),
    FieldSpec("is_active", "نشط", ("active", "is_active"), kind="bool", default=True),
)

SUPPLIER = EntitySpec(
    key="suppliers",
    label="مورد",
    plural="الموردون",
    section="suppliers",
    model_label="مورد",
    natural_key=("name",),
    fields=SUPPLIER_FIELDS,
)

# ------------------------------------------------------------------ الأقمشة

FABRIC_FIELDS = (
    FieldSpec("name", "اسم القماش", ("name", "fabric", "fabric_name"), required=True),
    FieldSpec("code", "الرمز", ("code", "sku", "fabric_code")),
    FieldSpec("barcode", "الباركود", ("barcode", "upc", "ean")),
    FieldSpec(
        "unit",
        "وحدة البيع",
        ("unit",),
        kind="choice",
        choices={"yard": "yard", "ياردة": "yard", "ي": "yard", "roll": "roll", "لفة": "roll", "رول": "roll", "l": "roll"},
        default="yard",
    ),
    FieldSpec("fabric_type", "نوع القماش", ("fabric_type", "type")),
    FieldSpec("color", "اللون", ("color", "colour")),
    FieldSpec("composition", "التركيب", ("composition", "material")),
    FieldSpec("width_cm", "العرض سم", ("width", "width_cm"), kind="decimal"),
    FieldSpec("weight_gsm", "الوزن غ/م²", ("weight", "weight_gsm", "gsm"), kind="int"),
    FieldSpec("origin", "المنشأ", ("origin",)),
    FieldSpec("manufacturer", "المصنّع", ("manufacturer", "maker")),
    FieldSpec("supplier", "المورد", ("supplier", "supplier_name"), kind="reference"),
    FieldSpec("purchase_price", "سعر الشراء", ("purchase_price", "cost", "buy_price"), kind="decimal"),
    FieldSpec("sale_price_yard", "سعر البيع/ياردة", ("sale_price_yard", "price_yard", "price"), kind="decimal"),
    FieldSpec("sale_price_roll", "سعر البيع/لفة", ("sale_price_roll", "price_roll"), kind="decimal"),
    FieldSpec("piece_price", "سعر القطعة", ("piece_price",), kind="decimal"),
    FieldSpec("min_stock", "حد الطلب", ("min_stock", "minimum", "reorder"), kind="decimal"),
    FieldSpec("allow_roll_sale", "بيع باللفة", ("allow_roll_sale",), kind="bool"),
    FieldSpec("is_active", "نشط", ("active", "is_active"), kind="bool", default=True),
    FieldSpec("description", "الوصف", ("description", "notes")),
)

FABRIC = EntitySpec(
    key="fabrics",
    label="قماش",
    plural="الأقمشة",
    section="fabrics",
    model_label="قماش",
    natural_key=("code", "name"),
    fields=FABRIC_FIELDS,
)

# ------------------------------------------------------------------ الموظفون

EMPLOYEE_FIELDS = (
    FieldSpec("name", "اسم الموظف", ("name", "employee", "employee_name"), required=True),
    FieldSpec("employee_code", "الرقم الوظيفي", ("code", "employee_code", "emp_no")),
    FieldSpec("phone", "الهاتف", ("phone", "mobile")),
    FieldSpec("email", "البريد الإلكتروني", ("email", "mail")),
    FieldSpec("department", "القسم", ("department", "dept")),
    FieldSpec("position", "المسمى الوظيفي", ("position", "job", "title")),
    FieldSpec("branch", "الفرع", ("branch", "branch_name"), kind="reference"),
    FieldSpec(
        "role",
        "الدور",
        ("role",),
        kind="choice",
        choices={
            "admin": "admin", "مدير": "admin", "مدير النظام": "admin",
            "supervisor": "supervisor", "مشرف": "supervisor",
            "sales": "sales", "مبيعات": "sales", "مندوب مبيعات": "sales",
            "accountant": "accountant", "محاسب": "accountant",
            "viewer": "viewer", "مشاهد": "viewer",
            "custom": "custom", "مخصص": "custom",
        },
        default="custom",
    ),
    FieldSpec("base_salary", "الراتب الأساسي", ("base_salary", "salary"), kind="decimal"),
    FieldSpec("commission_percent", "نسبة العمولة %", ("commission_percent", "commission"), kind="decimal"),
    FieldSpec("commission_active", "عمولة فعّالة", ("commission_active",), kind="bool"),
    FieldSpec("hire_date", "تاريخ التعيين", ("hire_date", "joined"), kind="date"),
    FieldSpec("birth_date", "تاريخ الميلاد", ("birth_date", "birthday"), kind="date"),
    FieldSpec("civil_id", "الرقم الوطني", ("civil_id", "national_id", "id_number")),
    FieldSpec("address", "العنوان", ("address",)),
    FieldSpec("notes", "ملاحظات", ("notes", "note")),
    FieldSpec("is_active", "نشط", ("active", "is_active"), kind="bool", default=True),
)

EMPLOYEE = EntitySpec(
    key="employees",
    label="موظف",
    plural="الموظفون",
    section="employees",
    model_label="موظف",
    natural_key=("name",),
    fields=EMPLOYEE_FIELDS,
)

ENTITIES = {spec.key: spec for spec in (SUPPLIER, FABRIC, EMPLOYEE)}
ENTITY_KEYS = tuple(ENTITIES)


# ------------------------------------------------------------------ التحويل


class ValueError_(ValueError):
    """خطأ تحويل قيمة خلية إلى نوع حقلها."""


def parse_value(spec, raw):
    """يحوّل خلية Excel إلى قيمة صالحة لحقل، أو يرفع ``ValueError_`` برسالة عربية."""
    if raw is None:
        return None
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
    else:
        text = raw

    if spec.kind in ("text", "reference"):
        return str(text).strip()

    if spec.kind == "int":
        try:
            return int(Decimal(str(text).replace(",", "")))
        except (InvalidOperation, ValueError, TypeError):
            raise ValueError_(f"«{text}» ليس رقماً صحيحاً")

    if spec.kind == "decimal":
        try:
            return Decimal(str(text).replace(",", "").strip())
        except (InvalidOperation, ValueError, TypeError):
            raise ValueError_(f"«{text}» ليس رقماً")

    if spec.kind == "bool":
        lowered = str(text).strip().lower()
        if lowered in TRUE_VALUES:
            return True
        if lowered in FALSE_VALUES:
            return False
        raise ValueError_(f"«{text}» ليست قيمة صح/خطأ صحيحة")

    if spec.kind == "choice":
        key = str(text).strip().lower()
        if key in spec.choices:
            return spec.choices[key]
        options = "، ".join(sorted(set(spec.choices.values())))
        raise ValueError_(f"«{text}» غير مسموح — القيم المقبولة: {options}")

    if spec.kind == "date":
        if isinstance(text, datetime):
            return text.date()
        if isinstance(text, date):
            return text
        value = str(text).strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y", "%Y.%m.%d"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        # Excel قد يسلّم التاريخ كرقم تسلسلي
        try:
            serial = int(Decimal(value))
        except (InvalidOperation, ValueError):
            serial = None
        if serial is not None:
            try:
                return _EXCEL_EPOCH + timedelta(days=serial)
            except (OverflowError, ValueError):
                pass
        raise ValueError_(f"«{value}» ليس تاريخاً صالحاً (الصيغة المتوقعة: YYYY-MM-DD)")

    return str(text).strip()
