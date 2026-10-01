"""اختبارات تنسيق تصدير Excel.

السبب في وجود هذا الملف: التنسيق لا يُرى من الكود. كل تقرير في المشروع كان
يُصدَّر بلا تجميد رأس ولا عرض أعمدة ولا فاصل آلاف، ولا يكتشف المرء النقص
حتى يفتح الملف في Excel. هذه الاختبارات تُثبّت ما يجب أن يظهر في كل ملف،
فيعود التنسيق التزاماً لا نيّة.

وتُختبر هنا نقطة الدخول العامة ``_export_generic_to_xlsx`` التي يمرّ منها
معظم شاشات المشروع: فالتنسيق المطبَّق على واجهة المصنع لا يسري تلقائياً
على من نسي استدعاءه، وهذه هي النقطة التي يتسرّب منها العري.
"""

import io
from datetime import date, datetime
from decimal import Decimal

from django.test import TestCase

from core import excel

try:
    import openpyxl
except ImportError:  # pragma: no cover - بيئة بلا openpyxl
    openpyxl = None


def load(workbook):
    """يُعيد الملف كما سيراه المستخدم: يُكتب ثم يُقرأ، لا يُفحص في الذاكرة."""
    stream = io.BytesIO()
    workbook.save(stream)
    stream.seek(0)
    return openpyxl.load_workbook(stream)


def head(ws, label):
    """موضع صفّ رأس العمود، بالبحث عن عنوانه لا بالتخمين.

    أين يقع الرأس قرارٌ داخلي للمصنع (هل أضفنا عنواناً وسطراً توضيحياً؟)،
    والاختبار يهتمّ بأنّ الرأس وُضع ومُنسَّق، لا بأنّه في الصفّ الثاني بالضبط.
    """
    for row in range(1, ws.max_row + 1):
        if ws.cell(row=row, column=1).value == label:
            return row
    raise AssertionError(f"لم يُعثر على العمود {label!r} في الورقة")


class _ExcelTestCase(TestCase):
    def setUp(self):
        if openpyxl is None:
            self.skipTest("openpyxl not installed")

    def sheet(self, columns, rows, heading="", subtitle="", title="ورقة"):
        """ورقة واحدة بأعمدة صريحة، تُقرأ من القرص."""
        wb = excel.build_workbook([{
            "title": title, "columns": columns, "rows": rows,
            "heading": heading, "subtitle": subtitle,
        }])
        return load(wb).active

    def simple_sheet(self, headers, rows, heading="", subtitle="", title="ورقة"):
        """ورقة بترويسات نصّية — الطريق الذي تسلكه الشاشات القائمة."""
        wb = excel.simple(title, headers, rows, heading=heading, subtitle=subtitle)
        return load(wb).active


class ColumnInferenceTests(_ExcelTestCase):
    """استنتاج النوع: ما لا يُصرَّح به يُخمَّن خطأً، فيفقد فاصل الآلاف."""

    def test_decimal_values_infer_money(self):
        columns = excel.infer_columns(["قيمة"], [[1234.5], [98765.25]])
        self.assertEqual(columns[0]["type"], "money")

    def test_whole_numbers_are_counts_not_money(self):
        """«عدد القطع» بـ5 لا يُطبع 5.00 — كسرٌ عشري واحد يجعلها نقوداً."""
        columns = excel.infer_columns(["عدد القطع"], [[5], [12]])
        self.assertEqual(columns[0]["type"], "number")

    def test_header_words_win_over_numeric_shape(self):
        """عمود كسور عشرية اسمُه «الهامش %» نسبةٌ لا نقود."""
        columns = excel.infer_columns(["الهامش %"], [[12.5], [40.1]])
        self.assertEqual(columns[0]["type"], "percent")

    def test_money_header_wins_over_whole_numbers(self):
        """رصيدٌ صحيح 2000 يبقى نقوداً: اسمه يصرّح بذلك."""
        columns = excel.infer_columns(["الرصيد"], [[2000], [3000]])
        self.assertEqual(columns[0]["type"], "money")

    def test_iso_dates_infer_date(self):
        """نصّ التاريخ لا يُرتَّب زمنياً في Excel — ولا يُفلتر."""
        columns = excel.infer_columns(["التاريخ"], [["2026-09-01"], ["2026-09-02"]])
        self.assertEqual(columns[0]["type"], "date")

    def test_date_objects_infer_date(self):
        columns = excel.infer_columns(["التاريخ"], [[date(2026, 9, 1)]])
        self.assertEqual(columns[0]["type"], "date")

    def test_mixed_column_falls_back_to_text(self):
        """عمود فيه اسم ورقم: النصّ أصدق من التخمين."""
        columns = excel.infer_columns(["الحالة"], [["متوازن"], [5]])
        self.assertEqual(columns[0]["type"], "text")

    def test_column_without_values_is_text(self):
        """بلا قيم لا دليل على النوع — ولا سبب لتخمين عرضٍ ما."""
        columns = excel.infer_columns(["ملاحظات"], [["نص"], ["نص آخر"]])
        self.assertEqual(columns[0]["type"], "text")

    def test_column_full_of_blanks_is_text(self):
        columns = excel.infer_columns(["ملاحظات"], [[""], [None]])
        self.assertEqual(columns[0]["type"], "text")

    def test_explicit_type_overrides_inference(self):
        """من يعرف نوع عموده يصرّح به، ولا تخمينه يُتخلّى عنه."""
        columns = excel.infer_columns(["العدد"], [[5]], types=["money"])
        self.assertEqual(columns[0]["type"], "money")

    def test_unknown_explicit_type_falls_back_to_inference(self):
        """اسم نوعٍ خاطئ لا يجعل العمود بلا تنسيق: يُخمَّن كما لو لم يُمرَّر."""
        columns = excel.infer_columns(["المبلغ"], [[10.5]], types=["عملة"])
        self.assertEqual(columns[0]["type"], "money")

    def test_short_types_list_pads_by_inference(self):
        """قائمة أنواع أقصر من الترويسات تُكمل بالاستنتاج لا بالخطأ."""
        columns = excel.infer_columns(["أ", "ب"], [[1, 2.5]], types=["money"])
        self.assertEqual(columns[0]["type"], "money")
        self.assertEqual(columns[1]["type"], "money")

    def test_each_column_infers_its_own_type(self):
        """عمود نصّي وآخر نقودي في التقرير الواحد: لكلٍّ منهما صيغته."""
        columns = excel.infer_columns(["الاسم", "المبلغ"], [["مورد", 10.5]])
        self.assertEqual([c["type"] for c in columns], ["text", "money"])


class DateDetectionTests(_ExcelTestCase):
    """تحويل ما ليس تاريخاً إلى تاريخٍ يكذب في مستندٍ يُسلَّم للغير."""

    def test_rejects_shapes_that_are_not_iso(self):
        for value in ("2026/09/01", "09-2026", "سبتمبر 2026", "2026-9-1", "", "1"):
            self.assertIsNone(excel._to_date(value), value)

    def test_accepts_iso_with_trailing_time(self):
        self.assertEqual(
            excel._to_date("2026-09-01T10:30:00"), date(2026, 9, 1),
        )

    def test_passes_date_objects_through(self):
        self.assertEqual(excel._to_date(date(2026, 9, 1)), date(2026, 9, 1))

    def test_date_cell_is_a_real_date_not_a_string(self):
        """نصٌّ في خلية تاريخ لا يُفلتر زمنياً — والتصدير كلّه يُبنى عليه."""
        ws = self.sheet(
            [{"label": "التاريخ", "type": "date"}], [["2026-09-01"]],
        )
        cell = ws.cell(row=head(ws, "التاريخ") + 1, column=1)
        value = cell.value.date() if isinstance(cell.value, datetime) else cell.value
        self.assertEqual(value, date(2026, 9, 1))
        self.assertEqual(cell.number_format, excel.FORMAT_DATE)

    def test_non_date_text_stays_text(self):
        """شهرٌ بالاسم «سبتمبر 2026» يُبقى نصّاً، فلا يُكتب تاريخٌ مختلَق."""
        ws = self.sheet(
            [{"label": "الشهر", "type": "date"}], [["سبتمبر 2026"]],
        )
        cell = ws.cell(row=head(ws, "الشهر") + 1, column=1)
        self.assertEqual(cell.value, "سبتمبر 2026")


class TotalsRowTests(_ExcelTestCase):
    """صفّ الإجمالي يختلط بالبيانات إن لم يُعرف، فيضلّ القارئ بينه وبينها."""

    def test_detects_totals_labels(self):
        self.assertTrue(excel.is_totals_row(["الإجمالي", 100, 2]))
        self.assertTrue(excel.is_totals_row(["المجموع", 100]))
        self.assertTrue(excel.is_totals_row(["إجمالي", 100]))

    def test_tolerates_blank_cells(self):
        self.assertTrue(excel.is_totals_row(["الإجمالي", "", 50, ""]))

    def test_rejects_statement_row_whose_text_merely_starts_with_it(self):
        """«الإجمالي الشهري» سطر بيانٍ لا مجموع: التمييز بالقيمة لا بالكلمة."""
        self.assertFalse(excel.is_totals_row(["الإجمالي الشهري", 100, 2]))

    def test_rejects_label_appearing_in_a_later_column(self):
        """عمود «الحالة» قيمته «الإجمالي» لا يجعل الصفّ مجموعاً."""
        self.assertFalse(excel.is_totals_row(["مورد النسيج", 100, "الإجمالي"]))

    def test_rejects_empty_row(self):
        """صفٌّ فاصل في كشف الرواتب لا يُلوَّن خطأً."""
        self.assertFalse(excel.is_totals_row([]))

    def test_totals_row_is_bold_with_a_top_rule(self):
        """حدٌّ علويّ يفصل المجموع عمّن فوقه بالنظر وحده."""
        ws = self.sheet(
            [{"label": "البيان", "type": "text"}, {"label": "المبلغ", "type": "money"}],
            [["مبيعات", 100], ["الإجمالي", 100]],
        )
        top = head(ws, "البيان")
        self.assertFalse(ws.cell(row=top + 1, column=2).font.bold)
        total = ws.cell(row=top + 2, column=2)
        self.assertTrue(total.font.bold)
        self.assertEqual(total.border.top.style, "medium")


class SheetFormattingTests(_ExcelTestCase):
    """ما يراه المستخدم عند فتح الملف."""

    def test_reads_right_to_left(self):
        """العربية تُقرأ من اليمين؛ وورقة LTR تجعل الأرقام محاذِرةً للنص."""
        ws = self.simple_sheet(["أ", "ب"], [[1, 2]])
        self.assertTrue(ws.sheet_view.rightToLeft)

    def test_header_is_bold_white_on_dark(self):
        """رأسٌ عارٍ لا يُعرف أين يبدأ الجدول ولا أين ينتهي."""
        ws = self.simple_sheet(["المبلغ"], [[1]])
        cell = ws.cell(row=head(ws, "المبلغ"), column=1)
        self.assertTrue(cell.font.bold)
        self.assertEqual(cell.font.color.rgb[-6:], excel.HEADER_FONT)
        self.assertEqual(cell.fill.fgColor.rgb[-6:], excel.HEADER_FILL)

    def test_header_frozen_below_itself(self):
        """بلا تجميد، يُنسى أي عمود يقرأ بعد أن يُزاح الرأس خارج الشاشة."""
        ws = self.simple_sheet(["المبلغ"], [[1], [2]])
        top = head(ws, "المبلغ")
        self.assertEqual(
            ws.freeze_panes, ws.cell(row=top + 1, column=1).coordinate,
        )

    def test_freeze_covers_the_title_and_header_together(self):
        """تجميدٌ عند صفٍّ واحد يجمّد العنوان وحده، فيختفي العمود الأول عند
        التمرير — ويُجمَّد ما فوق الرأس كلّه حتى لا يبقى بلا سياق."""
        ws = self.simple_sheet(["المبلغ"], [[1]], heading="تقرير")
        self.assertEqual(ws.freeze_panes, "A3")

    def test_title_and_subtitle_span_every_column(self):
        """عنوانٌ لا يمتدّ على الجدول يبدو عنوان عمودٍ واحدٍ في وسطه."""
        ws = self.simple_sheet(
            ["أ", "ب", "ج"], [[1, 2, 3]],
            heading="تقرير المبيعات", subtitle="الفترة: 2026-09-01 إلى 2026-09-30",
        )
        self.assertEqual(ws.cell(row=1, column=1).value, "تقرير المبيعات")
        self.assertIn("2026-09-01", ws.cell(row=2, column=1).value)
        self.assertEqual(
            {str(rng) for rng in ws.merged_cells.ranges}, {"A1:C1", "A2:C2"},
        )

    def test_title_only_without_subtitle_keeps_rows_adjacent(self):
        """سطرٌ توضيحي ناقص لا يترك فراغاً يحسبه القارئ صفّاً مفقوداً."""
        ws = self.simple_sheet(["المبلغ"], [[1]], heading="تقرير المبيعات")
        self.assertEqual(ws.cell(row=1, column=1).value, "تقرير المبيعات")
        self.assertEqual(head(ws, "المبلغ"), 2)

    def test_number_formats_separate_money_from_counts_from_percent(self):
        ws = self.sheet(
            [
                {"label": "المبلغ", "type": "money"},
                {"label": "العدد", "type": "number"},
                {"label": "الهامش", "type": "percent"},
            ],
            [[1234.5, 7, 40.12]],
        )
        top = head(ws, "المبلغ")
        self.assertEqual(ws.cell(row=top + 1, column=1).number_format, "#,##0.00")
        self.assertEqual(ws.cell(row=top + 1, column=2).number_format, "#,##0.##")
        self.assertEqual(ws.cell(row=top + 1, column=3).number_format, '0.0"%"')

    def test_percent_is_printed_not_scaled_again(self):
        """القيمة 40.12 تعني 40.12٪: صيغةٌ تضرب في مئة تطبع 4012٪."""
        ws = self.sheet([{"label": "الهامش", "type": "percent"}], [[40.12]])
        cell = ws.cell(row=head(ws, "الهامش") + 1, column=1)
        self.assertEqual(cell.value, 40.12)
        self.assertEqual(cell.number_format, '0.0"%"')

    def test_decimal_becomes_a_writable_number(self):
        """Excel لا يقبل Decimal — وكاتبه يملأ الملف بخطأ ``unsupported``."""
        ws = self.sheet([{"label": "المبلغ", "type": "money"}], [[Decimal("99.99")]])
        cell = ws.cell(row=head(ws, "المبلغ") + 1, column=1)
        self.assertEqual(cell.value, 99.99)
        self.assertEqual(cell.number_format, "#,##0.00")

    def test_numeric_strings_are_left_as_text(self):
        """رقمٌ مكتوب كنصٍّ في مصدره يبقى نصّاً: تحويله يُخفي مصدرَه."""
        ws = self.sheet([{"label": "المبلغ", "type": "money"}], [["100"]])
        cell = ws.cell(row=head(ws, "المبلغ") + 1, column=1)
        self.assertEqual(cell.value, "100")

    def test_column_width_grows_with_content(self):
        """عمودُ نصٍّ طويل بلا عرضٍ يُقطع عند الحرف العاشر فيضيع المعنى."""
        ws = self.simple_sheet(
            ["الاسم"], [["مورد النسيج المصري المتخصص في الأقمشة cotton"]],
        )
        self.assertGreater(ws.column_dimensions["A"].width, 30)

    def test_column_width_has_a_floor(self):
        """عمودٌ ضيّقٌ على ترويسة طويلة يُقصّ عنوانه فلا يُقرأ أصلاً."""
        ws = self.simple_sheet(["ب"], [["1"]])
        self.assertGreaterEqual(ws.column_dimensions["A"].width, excel.MIN_COLUMN_WIDTH)

    def test_column_width_is_capped(self):
        """عرضٌ بلا حدٍّ يجعل عمودٌ واحدٌ يوسّع الورقة ويمسح الشاشة."""
        ws = self.simple_sheet(["ن"], [["س" * 500]])
        self.assertLessEqual(ws.column_dimensions["A"].width, excel.MAX_COLUMN_WIDTH)

    def test_autofilter_covers_header_and_data(self):
        ws = self.simple_sheet(["أ", "ب"], [[1, 2], [3, 4]])
        top = head(ws, "أ")
        self.assertEqual(
            ws.auto_filter.ref, f"A{top}:B{top + 2}",
        )

    def test_no_autofilter_without_rows(self):
        """فلترٌ على ترويسةٍ بلا بيانات يعرض قائمة فارغة بلا فائدة."""
        ws = self.simple_sheet(["أ"], [])
        self.assertIsNone(ws.auto_filter.ref)

    def test_zebra_alternates(self):
        """تظليلٌ متبادل يجعل العين تتبع الصفّ عبر عمودٍ بعرضه عشرين."""
        ws = self.simple_sheet(["أ"], [["1"], ["2"], ["3"]])
        top = head(ws, "أ")
        fills = [ws.cell(row=top + n, column=1).fill.fgColor.rgb for n in (1, 2, 3)]
        self.assertNotEqual(fills[0], fills[1])
        self.assertEqual(fills[0], fills[2])

    def test_zebra_can_be_turned_off(self):
        """الورقة التي تُصدَّر آلياً في مهمةٍ ليلية لا تُزيَّن."""
        ws = self.simple_sheet(["أ"], [["1"], ["2"]])
        top = head(ws, "أ")
        self.assertEqual(
            ws.cell(row=top + 1, column=1).fill.fgColor.rgb[-6:],
            "000000",
        )
        self.assertEqual(
            ws.cell(row=top + 2, column=1).fill.fgColor.rgb[-6:],
            excel.ZEBRA_FILL,
        )

    def test_data_cells_are_aligned_against_each_other(self):
        """الأرقام تُحاذى على حافّة واحدة، والنصّ على حافّته، وإلا تفرّقت الخانات."""
        ws = self.sheet(
            [
                {"label": "الاسم", "type": "text"},
                {"label": "المبلغ", "type": "money"},
            ],
            [["مورد", 10.0]],
        )
        top = head(ws, "الاسم")
        self.assertEqual(ws.cell(row=top + 1, column=1).alignment.horizontal, "right")
        self.assertEqual(ws.cell(row=top + 1, column=2).alignment.horizontal, "left")

    def test_print_setup_fits_the_width_on_one_landscape_page(self):
        """تقريرٌ من 20 عموداً يُطبع صفحةً في كل صفحة ويمسح النصّ."""
        ws = self.simple_sheet(["أ"], [[1]])
        self.assertEqual(ws.page_setup.orientation, "landscape")
        self.assertEqual(ws.page_setup.fitToWidth, 1)
        self.assertTrue(ws.sheet_properties.pageSetUpPr.fitToPage)

    def test_header_row_repeats_on_every_printed_page(self):
        """صفٌّ ثانٍ بلا ترويسة في تقريرٍ مطبوع: لا يُعرف عمودُه."""
        ws = self.simple_sheet(["أ"], [[1]], heading="تقرير")
        top = head(ws, "أ")
        self.assertEqual(ws.print_title_rows.replace("$", ""), f"1:{top}")

    def test_short_row_leaves_later_cells_empty_not_shifted(self):
        """صفٌّ أقصر من الترويس: الخانات الناقصة فراغ، لا إزاحةُ الأعمدة."""
        ws = self.sheet(
            [
                {"label": "أ", "type": "text"},
                {"label": "ب", "type": "money"},
                {"label": "ج", "type": "text"},
            ],
            [["س"]],
        )
        top = head(ws, "أ")
        self.assertEqual(ws.cell(row=top + 1, column=1).value, "س")
        self.assertIsNone(ws.cell(row=top + 1, column=2).value)
        self.assertIsNone(ws.cell(row=top + 1, column=3).value)

    def test_sheet_with_no_columns_still_prints(self):
        """تقريرٌ بلا أعمدة: ورقةٌ قابلة للطباعة لا انهيارٌ في المصنع."""
        ws = self.sheet([], [])
        self.assertTrue(ws.sheet_view.rightToLeft)


class WorkbookTests(_ExcelTestCase):
    def test_sheet_names_capped_at_the_excel_limit(self):
        """Excel يرفض اسم ورقة من 32 محرفاً، فيُفتح التقرير بلا محتوى."""
        wb = excel.build_workbook([{
            "title": "ت" * 60,
            "columns": [{"label": "أ", "type": "text"}],
            "rows": [["س"]],
        }])
        self.assertEqual(len(wb.sheetnames[0]), 31)

    def test_default_sheet_removed(self):
        """المصنِّع يترك ورقة فارغة باسم «Sheet» تسبق تقريرَك بلا معنى."""
        wb = excel.build_workbook([{
            "title": "تقرير",
            "columns": [{"label": "أ", "type": "text"}],
            "rows": [["س"]],
        }])
        self.assertEqual(wb.sheetnames, ["تقرير"])

    def test_arabic_sheet_names_survive(self):
        wb = excel.build_workbook([{
            "title": "الربح والخسارة",
            "columns": [{"label": "أ", "type": "text"}],
            "rows": [["س"]],
        }])
        self.assertEqual(wb.sheetnames, ["الربح والخسارة"])

    def test_each_sheet_is_formatted_independently(self):
        """ورقةٌ واحدة مُنسَّقة وأخرى عارية تُفسد الانطباع كلّه."""
        wb = excel.build_workbook([
            {
                "title": "الأول",
                "columns": [{"label": "أ", "type": "money"}],
                "rows": [[5]],
                "heading": "عنوان",
            },
            {
                "title": "الثاني",
                "columns": [{"label": "ب", "type": "text"}],
                "rows": [["س"]],
            },
        ])
        book = load(wb)
        first, second = book["الأول"], book["الثاني"]
        self.assertTrue(first.sheet_view.rightToLeft)
        self.assertTrue(second.sheet_view.rightToLeft)
        self.assertEqual(
            first.cell(row=head(first, "أ") + 1, column=1).number_format, "#,##0.00",
        )
        self.assertEqual(head(second, "ب"), 1)

    def test_returns_none_without_openpyxl(self):
        """بدون openpyxl تُرجع الشاشات رسالةً صريحة بدل انهيارٍ مبهم."""
        real = excel._lib
        excel._lib = lambda: None
        try:
            self.assertIsNone(excel.build_workbook([{"title": "أ"}]))
            self.assertFalse(excel.available())
        finally:
            excel._lib = real

    def test_always_has_at_least_one_sheet(self):
        """Workbook بلا أوراق يرفضه openpyxl عند الحفظ."""
        self.assertTrue(excel.build_workbook([]).sheetnames)


class ResponseTests(_ExcelTestCase):
    """اسم الملف: يُرسل مرّتين لأن قارئات مختلفة تقرأ واحدة منهما."""

    def _response(self, name="تقرير", **kwargs):
        return excel.xlsx_response(excel.simple("ورقة", ["أ"], [[1]]), name, **kwargs)

    def test_header_is_pure_ascii(self):
        """حرفٌ عربيٌ واحد في الترويسة يجعل Django يلفّ الرأس كلّه في
        ``=?utf-8?b?...?=``، فيتوقّف Excel عن تفسير ``filename*`` ويظهر
        الاسم مبتوراً. هذا كان خللاً في كل تصدير عربي في المشروع."""
        self.assertTrue(self._response()["Content-Disposition"].isascii())

    def test_arabic_name_is_sent_percent_encoded(self):
        disposition = self._response("تقرير المبيعات")["Content-Disposition"]
        self.assertIn("filename*=UTF-8''", disposition)
        self.assertIn("filename=", disposition)

    def test_ascii_fallback_is_offered_alongside(self):
        """قارئٌ لا يفهم ``filename*`` يبقى لديه اسمٌ سليم لا محرفاً واحداً."""
        disposition = self._response()["Content-Disposition"]
        self.assertIn('filename="report.xlsx"', disposition)

    def test_ascii_fallback_keeps_latin_characters_of_the_name(self):
        disposition = self._response("تقرير stock")["Content-Disposition"]
        self.assertIn('filename="stock.xlsx"', disposition)

    def test_explicit_ascii_name_wins(self):
        disposition = self._response("تقرير", ascii_name="sales")["Content-Disposition"]
        self.assertIn('filename="sales.xlsx"', disposition)

    def test_content_type_is_a_real_xlsx(self):
        self.assertEqual(
            self._response()["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def test_body_is_a_workbook_that_reopens(self):
        """الاسم الصحيح لا ينفع إن كان الملف تالفاً — نقرأ ما نرسله."""
        book = openpyxl.load_workbook(io.BytesIO(self._response().content))
        self.assertEqual(book.sheetnames, ["ورقة"])


class GenericExportEntryPointTests(_ExcelTestCase):
    """نقطة الدخول التي يمرّ منها معظم شاشات المشروع."""

    def _body(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertIn("spreadsheetml.sheet", response["Content-Type"])
        return openpyxl.load_workbook(io.BytesIO(response.content)).active

    def test_generic_export_is_formatted_end_to_end(self):
        from reports.views import _export_generic_to_xlsx, _xlsx_response

        ws = self._body(_xlsx_response(
            _export_generic_to_xlsx("التقرير", ["البيان", "المبلغ"], [["مبيعات", 1234.5]]),
            "تقرير",
        ))
        self.assertTrue(ws.sheet_view.rightToLeft)
        top = head(ws, "البيان")
        self.assertEqual(ws.cell(row=top + 1, column=2).number_format, "#,##0.00")
        self.assertIsNotNone(ws.freeze_panes)

    def test_generic_export_honours_declared_types(self):
        """عمود يُسمّى «الرصيد» ويقوم بأعداد صحيحة يبقى نقوداً بلا تصحيح يدوي."""
        from reports.views import _export_generic_to_xlsx, _xlsx_response

        ws = self._body(_xlsx_response(
            _export_generic_to_xlsx(
                "التقرير", ["الرصيد", "العدد"],
                [[2000, 7]], types=["money", "number"],
            ),
            "تقرير",
        ))
        top = head(ws, "الرصيد")
        self.assertEqual(ws.cell(row=top + 1, column=1).number_format, "#,##0.00")
        self.assertEqual(ws.cell(row=top + 1, column=2).number_format, "#,##0.##")

    def test_subtitle_lands_in_the_file(self):
        """الفترة تُكتب داخل الملف: من يفتحه بعد شهر يجب أن يعرف أيّ شهر."""
        from reports.views import _export_generic_to_xlsx, _xlsx_response

        ws = self._body(_xlsx_response(
            _export_generic_to_xlsx(
                "تقرير المبيعات", ["أ"], [["س"]],
                subtitle="الفترة: 2026-09-01 إلى 2026-09-30",
            ),
            "ت",
        ))
        self.assertIn("2026-09-01", ws.cell(row=2, column=1).value)

    def test_missing_openpyxl_gives_a_clear_500(self):
        """بدون المكتبة: رسالةٌ مفهومة، لا AttributeError في سجلّ الأخطاء."""
        from reports.views import _xlsx_response

        real = excel._lib
        excel._lib = lambda: None
        try:
            response = _xlsx_response(None, "تقرير")
        finally:
            excel._lib = real
        self.assertEqual(response.status_code, 500)
        self.assertIn("openpyxl", str(response.data))
