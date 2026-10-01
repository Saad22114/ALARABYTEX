"""بناء ملفات Excel مُنسَّقة: كل تصدير في المشروع يمرّ من هنا.

لولا هذا الملف كان لكل تقرير مصنعه: صفُّ ترويسة عارٍ بلا ألوان ولا تجميد ولا
عرض أعمدة، وأرقام تُقرأ `1234.5` بينما ورقتها لا تفصل الآلاف، وتاريخ
`2026-09-01` **نصٌّ** لا تاريخ — فلا تُرتَّب الأعمدة ولا يُفلتر عليها. كل
مستخدم يصدّر تقريره ليقرأه في Excel يصطدم بذلك في كل مرة.

المبادئ التي يلتزم بها هذا الملف:

* **من اليمين**: الورقة تُقرأ من اليمين، لا ترجمة، بل اتجاه تفرضه اللغة.
* **ترتيب وعرض**: تجميد الرأس، وعرض أعمدة محسوب من المحتوى، وصفوف متبادلة
  التظليل، وفلتر تلقائي على الرأس.
* **أرقام قابلة للقراءة**: فاصل آلاف، ومنزلتان عشريتان للمال، وعلامة النسبة.
* **تواريخ حقيقية**: `2026-09-01` نصٌّ في Excel لا تاريخ، فلا يُرتَّب ولا
  يُفلتر زمنياً. فنحوّله إلى تاريخ فعلي.
* **صفّ الإجمالي** يُعرف بأن أول خلية فيه «الإجمالي» أو «المجموع»، فيُبرز
  بسطرٍ عريض وحدٍ علويّ — لا أن يختلط بالبيانات.

الدوال كلها تأخذ الأعمدة كـ ``[{"label": ..., "type": ...}]``، وتوافق من
يرسل ترويسات نصّية فقط. النوع يُستنتج عند غيابه (انظر :func:`infer_columns`)
فتستفيد كل الشاشات القائمة من التنسيق الجديد بلا أن تُعدَّل واحدة منها.
"""

from datetime import date, datetime
from decimal import Decimal

#: الورقة تُقرأ من اليمين.
RTL = True

#: العنوان ثم السطر التوضيحي ثم فراغ، قبل رأس الأعمدة.
TITLE_ROW = 1
SUBTITLE_ROW = 2

#: عرض الورقة: من اليمين لليسار.
#: ألوان الترويسة: التعبئة، ثم لون الخطّ (‎FFFFFF‎ أبيض).
HEADER_FILL = "1F3A5F"
HEADER_FONT = "FFFFFF"

#: تظليل الصفوف الفردية — خفيف عمداً: يوجّه العين ولا يصرخ.
ZEBRA_FILL = "F4F6F9"

#: تظليل صفّ الإجمالي.
TOTAL_FILL = "E8EDF4"

#: لون النصّ الثانوي (السطر التوضيحي).
MUTED_FONT = "5A6B7D"

#: حدود العرض التحوّلي — دون هذا يضيق نصٌّ عربي طويل، وفوقه يبقى عمودٌ بلا
#: معنى يوسّع الورقة ويمسح الشاشة.
MIN_COLUMN_WIDTH = 10
MAX_COLUMN_WIDTH = 44

# ---------------------------------------------------------------------------
# أنواع الأعمدة
# ---------------------------------------------------------------------------

TYPES = ("text", "money", "number", "percent", "date")

#: صيغة كل نوع في Excel.
#:
#: النسبة مخزَّنة عندنا كعدد كامل (``85.0`` بمعنى 85٪) لا كعدد عشري
#: (``0.85``)، فالصيغة ``0.0"%"`` تطبع الرقم كما هو مضافاً إليه علامة
#: النسبة. ضربه في مئة كان سيطبع ‎8500٪‎.
FORMAT_MONEY = "#,##0.00"
FORMAT_NUMBER = "#,##0.##"
FORMAT_PERCENT = '0.0"%"'
FORMAT_DATE = "dd-mm-yyyy"

NUMBER_FORMATS = {
    "money": FORMAT_MONEY,
    "number": FORMAT_NUMBER,
    "percent": FORMAT_PERCENT,
    "date": FORMAT_DATE,
}

#: كلمات تدلّ على عمود نقود — لاستنتاج النوع حين لا يُمرَّر.
MONEY_WORDS = (
    "مبلغ", "إجمالي", "رصيد", "قيمه", "قيمة", "تكلفه", "تكلفة",
    "دفعه", "دفعة", "سعر", "خصم", "ايراد", "إيراد", "مصروف", "مصاريف",
    "راتب", "اجور", "أجور", "مستحق", "متوسط", "مبيعات", "مشتريات",
)

#: وكلمات النسبة.
PERCENT_WORDS = ("%", "نسبه", "نسبة", "هامش", "تغير", "تغيّر", "حصة")


def _is_number(value):
    return isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)


def _to_date(value):
    """يحوّل نصّاً أو كائناً إلى تاريخ، أو ``None`` إن لم يكن تاريخاً.

    ``datetime.strptime`` لا يقبل إلا ``YYYY-MM-DD`` — وهو شكل تاريخنا
    الوحيد في هذه التقارير. الأشكال الأخرى (``2026/09/01``، ``سبتمبر
    2026``، ``09-2026``) تبقى نصّاً: تحويلها تخمينٌ يكتب تاريخاً خاطئاً في
    مستندٍ يُسلَّم للمحل.
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if len(text) < 10 or text[4] != "-" or text[7] != "-":
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _display(value, type_):
    """ما سيُكتب في الخلية، محوَّلاً إلى نوع يفهمه Excel."""
    if type_ == "date":
        return _to_date(value) or value
    if _is_number(value):
        # Excel لا يقبل ``Decimal``، بل float وint.
        return float(value)
    return value


def infer_columns(headers, rows, types=None):
    """يبني أعمدةً مُنسَّقة من ترويسات وصفوف، مستنتجاً النوع حيث أمكن.

    ``types`` اختياري: قائمة بنفس طول ``headers``. وتمرير نوعٍ يخالف محتوى
    العمود يجعل الملف يُظهر رقماً بمقاس غير مقصود، فمن يُمرّره مسؤول عنه.
    """
    out = []
    for index, label in enumerate(headers):
        if types and index < len(types) and types[index] in TYPES:
            type_ = types[index]
        else:
            type_ = _infer_one(label, [r[index] for r in rows if index < len(r)])
        out.append({"label": label, "type": type_})
    return out


def _infer_one(label, values):
    """نوع العمود من اسمه ومن محتواه."""
    present = [v for v in values if v not in (None, "")]
    if not present:
        return "text"
    # كل تاريخ؟ تاريخٌ حقيقي حتى لو جاء نصّاً.
    if all(_to_date(v) is not None for v in present):
        return "date"
    if not all(_is_number(v) for v in present):
        return "text"
    text = str(label or "")
    if any(word in text for word in PERCENT_WORDS):
        return "percent"
    if any(word in text for word in MONEY_WORDS):
        return "money"
    # أعداد صحيحة فقط: عدّاد لا مبلغ. ووجود كسرٍ عشري واحد يجعلها نقوداً.
    if all(float(v) == int(float(v)) for v in present):
        return "number"
    return "money"


#: عبارات صفّ الإجمالي في التقارير.
TOTAL_LABELS = ("الإجمالي", "المجموع", "إجمالي", "المجموع الكلي")


def is_totals_row(row):
    """هل هذا صفّ الإجمالي؟

    أول خلية فيه إحدى عبارات الإجمالي، وبقية خلاياه أرقام أو فراغات. وهذا
    يكفي: لو سمحنا بأي نصٍّ في الصفّ لصار كل سطر بيانٍ «إجمالياً».
    """
    if not row:
        return False
    head = str(row[0] or "").strip()
    if head not in TOTAL_LABELS:
        return False
    return all(v in ("", None) or _is_number(v) for v in row[1:])


# ---------------------------------------------------------------------------
# الكتابة
# ---------------------------------------------------------------------------


def _lib():
    try:
        import openpyxl
    except ImportError:
        return None
    return openpyxl


def available():
    """هل ``openpyxl`` مثبَّت؟ تُرجع الشاشات 500 برسالة صريحة إن لم يكن."""
    return _lib() is not None


def write_sheet(ws, columns, rows, title="", subtitle="", zebra=True):
    """يكتب جدولاً مُنسَّقاً كاملاً في ورقة، ويُرجع رقمَ صفّ الرأس.

    ``rows`` صفوف بيانات خام؛ صفّ الإجمالي يُكتشف ويُبرز تلقائياً.
    """
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    last_col = max(1, len(columns))

    # عنوان التقرير: سطر واحد يملأ الورقة، فيعرف القارئ ما ينظر إليه قبل
    # أن يقرأ أول رقم.
    header_row = TITLE_ROW
    if title:
        ws.cell(row=TITLE_ROW, column=1, value=title)
        ws.merge_cells(
            start_row=TITLE_ROW, start_column=1, end_row=TITLE_ROW, end_column=last_col
        )
        cell = ws.cell(row=TITLE_ROW, column=1)
        cell.font = Font(bold=True, size=14, color=HEADER_FONT)
        cell.fill = PatternFill("solid", fgColor=HEADER_FILL)
        cell.alignment = Alignment(horizontal="right", vertical="center")
        ws.row_dimensions[TITLE_ROW].height = 26
        header_row = SUBTITLE_ROW
    if subtitle:
        ws.cell(row=SUBTITLE_ROW, column=1, value=subtitle)
        ws.merge_cells(
            start_row=SUBTITLE_ROW, start_column=1,
            end_row=SUBTITLE_ROW, end_column=last_col,
        )
        cell = ws.cell(row=SUBTITLE_ROW, column=1)
        cell.font = Font(size=10, color=MUTED_FONT)
        cell.alignment = Alignment(horizontal="right", vertical="center")
        header_row = SUBTITLE_ROW + 1

    header_fill = PatternFill("solid", fgColor=HEADER_FILL)
    for index, column in enumerate(columns, start=1):
        cell = ws.cell(row=header_row, column=index, value=column["label"])
        cell.fill = header_fill
        cell.font = Font(bold=True, color=HEADER_FONT, size=11)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[header_row].height = 24

    zebra_fill = PatternFill("solid", fgColor=ZEBRA_FILL)
    total_fill = PatternFill("solid", fgColor=TOTAL_FILL)
    thin = Side(style="thin", color="C7D0DA")
    total_border = Border(top=Side(style="medium", color=HEADER_FILL))

    row_number = header_row
    for offset, row in enumerate(rows):
        row_number += 1
        totals = is_totals_row(row)
        for index, column in enumerate(columns, start=1):
            raw = row[index - 1] if index - 1 < len(row) else None
            cell = ws.cell(row=row_number, column=index, value=_display(raw, column["type"]))
            if column["type"] in NUMBER_FORMATS:
                cell.number_format = NUMBER_FORMATS[column["type"]]
                cell.alignment = Alignment(horizontal="left", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="right", vertical="center")
            if totals:
                cell.font = Font(bold=True)
                cell.fill = total_fill
                cell.border = total_border
            elif zebra:
                cell.border = Border(bottom=thin)
                if offset % 2 == 1:
                    cell.fill = zebra_fill

    # تجميد الرأس: لا بدّ أن يبقى أول ما يُرى عند التمرير، وإلا نسي القارئ
    # أي عمود يقرأ.
    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)
    if rows:
        ws.auto_filter.ref = (
            f"A{header_row}:"
            f"{ws.cell(row=header_row, column=last_col).column_letter}"
            f"{row_number}"
        )

    fit_columns(ws, columns, rows, header_row)
    _print_setup(ws, title or (columns[0]["label"] if columns else ""), header_row)
    ws.sheet_view.rightToLeft = RTL
    return header_row


def fit_columns(ws, columns, rows, header_row):
    """عرض كل عمدة من أعرض محتواه، ضمن حدَّين."""
    widths = []
    for index, column in enumerate(columns, start=1):
        longest = len(str(column["label"] or ""))
        for row in rows:
            if index - 1 >= len(row):
                continue
            value = _display(row[index - 1], column["type"])
            if value is None or value == "":
                continue
            if column["type"] == "date":
                text = "00-00-0000"
            elif _is_number(value):
                text = (
                    f"{value:,.2f}"
                    if column["type"] in ("money", "percent")
                    else f"{value:,.0f}"
                )
            else:
                text = str(value)
            longest = max(longest, len(text))
        widths.append(min(MAX_COLUMN_WIDTH, max(MIN_COLUMN_WIDTH, longest + 3)))

    for index, width in enumerate(widths, start=1):
        letter = ws.cell(row=header_row, column=index).column_letter
        ws.column_dimensions[letter].width = width
    return widths


def _print_setup(ws, title, header_row):
    """إعداد الطباعة: عرضي، يتّسع في صفحة واحدة، والرأس يتكرّر بكل صفحة."""
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    if title:
        ws.print_title_rows = f"1:{header_row}"
    ws.print_options.horizontalCentered = True


def build_workbook(sheets):
    """مصنع مصطلح: قائمة أوراق، كل ورقة قاموس::

        {"title", "heading", "subtitle", "columns", "rows"}

    ``title`` اسم الورقة (حدّه Excel بـ31 محرفاً)، و``heading`` سطر العنوان
    المعروض داخلها. يُرجع ``Workbook`` أو ``None`` إن لم يكن ``openpyxl``
    مثبَّتاً.
    """
    openpyxl = _lib()
    if openpyxl is None:
        return None
    wb = openpyxl.Workbook()
    # المصنِّع يولّد ورقة أولى فارغة؛ إمّا نكتب فيها وإلّا حذفناها.
    wb.remove(wb.active)
    for spec in sheets:
        ws = wb.create_sheet(title=(spec.get("title") or "ورقة")[:31])
        write_sheet(
            ws,
            spec.get("columns") or [],
            spec.get("rows") or [],
            title=spec.get("heading") or "",
            subtitle=spec.get("subtitle") or "",
        )
    if not wb.sheetnames:
        wb.create_sheet(title="ورقة")
    return wb


def _ascii_fallback(filename, default="report"):
    """اسم ASCII بديل لاسم عربي، لِما لا يقرأ ترميز RFC 5987."""
    cleaned = "".join(
        ch for ch in filename
        if ch.isascii() and (ch.isalnum() or ch in "-_ ")
    ).strip().replace(" ", "_")
    return cleaned or default


def xlsx_response(workbook, filename, ascii_name=None):
    """يردّ الملف مصمَّماً اسماً عربياً يُفتح في Excel دون كسر الاسم.

    ``filename*=UTF-8''...`` هو ما يقرأه Excel للعربية، وهو ASCII خالص لأن
    البايتات مُرمَّزة بنسبة. لكنّ رأس ``Content-Disposition`` لا يحتمل حرفاً
    عربياً واحداً: Django يلفّ الرأس كلّه في encoded-word
    (``=?utf-8?b?...?=``)، فيتوقّف كل قارئ — بما فيه Excel — عن تفسير
    ``filename*`` ويظهر الاسم مبتوراً. فاسم الـ ASCII ضروري لا تجميلي.
    """
    from urllib.parse import quote

    from django.http import HttpResponse

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    safe = filename.replace('"', "")
    response["Content-Disposition"] = (
        f'attachment; filename="{ascii_name or _ascii_fallback(safe)}.xlsx"; '
        f"filename*=UTF-8''{quote(f'{safe}.xlsx')}"
    )
    workbook.save(response)
    return response


def simple(title, headers, rows, types=None, heading="", subtitle=""):
    """الطريق المختصر للشاشات التي تمرّر ترويسات وصفوفاً بلا أنواع.

    يستنتج الأنواع، فيستفيد كل تقرير قائم من التنسيق الجديد بلا تعديل.
    """
    return build_workbook([
        {
            "title": title,
            "columns": infer_columns(headers, rows, types),
            "rows": rows,
            "heading": heading or title,
            "subtitle": subtitle,
        },
    ])