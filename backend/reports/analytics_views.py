"""عروض Reports V2 — كل تقرير يتبع نفس العقد (period/previous/columns/rows/kpis).

تدعم جميعها:
- ?date_from=&date_to=  الفترة (افتراضياً 30 يوماً)
- ?group_by=day|week|month  للتقارير الزمنية
- ?export=xlsx            تصدير Excel بنفس أعمدة الجدول
"""

from core import excel
from rest_framework.response import Response
from rest_framework.views import APIView

from . import analytics as A


def _period_line(payload):
    """سطر يوضّح الفترة والمقارنة — الملف يحمل رقمين من فترتين."""
    parts = []
    period = payload.get("period") or {}
    if period:
        parts.append(f"الفترة: {period.get('from')} إلى {period.get('to')}")
    previous = payload.get("previous") or {}
    if previous:
        parts.append(f"مقارنةً بـ: {previous.get('from')} إلى {previous.get('to')}")
    return "  |  ".join(parts)


class AnalyticsReportView(APIView):
    """قاعدة Reports V2: نطاق الفروع + الفترة + تصدير موحّد."""

    permission_section = "reports"
    builder = None
    export_name = "تقرير"

    def build(self, request):
        date_from, date_to, prev_from, prev_to = A.period(request)
        return self.builder(request, date_from, date_to, prev_from, prev_to)

    def get(self, request):
        payload = self.build(request)
        if request.query_params.get("export") == "xlsx":
            return self.export(payload)
        return Response(payload)

    def export(self, payload):
        """تصدير بنفس عقد التقرير: نفس الأعمدة ونفس الأنواع ونفس الإجمالي.

        ``xlsx_rows`` كانت تُعيد كل شيء نصّياً أو بلا أنواع، فكان الملف
       outside shares الأنواع هنا: نمرّر الأعمدة كما هي، فيعرف الملف
        أيّ عمود نسبة وأيّها نقود.xl export يقرأ
        ``payload['totals']`` ويضعه صفَّ «الإجمالي» المعتَرَف به.
        """
        columns = [
            {"label": c.get("label") or c.get("key"), "type": c.get("type") or "text"}
            for c in (payload.get("columns") or [])
        ]
        rows = [
            [A.xlsx_value(c, row.get(c.get("key"))) for c in columns]
            for row in (payload.get("rows") or [])
        ]
        totals = payload.get("totals") or {}
        if totals:
            rows.append(
                ["الإجمالي"]
                + [
                    A.xlsx_value(c, totals.get(c.get("key"), 0)) if c.get("total") else ""
                    for c in columns[1:]
                ]
            )
        wb = excel.build_workbook([{
            "title": (payload.get("title") or self.export_name)[:31],
            "columns": columns,
            "rows": rows,
            "heading": payload.get("title") or self.export_name,
            "subtitle": _period_line(payload),
        }])
        if wb is None:
            return Response({"detail": "مكتبة openpyxl غير مثبتة"}, status=500)
        return excel.xlsx_response(wb, payload.get("key") or "report")


class SummaryReportView(AnalyticsReportView):
    builder = staticmethod(A.kpi_summary)
    export_name = "مؤشرات_الأداء"


class SalesTrendReportView(AnalyticsReportView):
    builder = staticmethod(A.sales_trend)
    export_name = "تطور_المبيعات"


class BranchPerformanceReportView(AnalyticsReportView):
    builder = staticmethod(A.branch_performance)
    export_name = "أداء_الفروع"


class EmployeePerformanceReportView(AnalyticsReportView):
    builder = staticmethod(A.employee_performance)
    export_name = "أداء_الموظفين"


class FabricProfitabilityReportView(AnalyticsReportView):
    builder = staticmethod(A.fabric_profitability)
    export_name = "ربحية_الأقمشة"


class InventorySlowReportView(AnalyticsReportView):
    builder = staticmethod(A.inventory_slow)
    export_name = "المخزون_الراكد"


class SupplierAgingReportView(AnalyticsReportView):
    builder = staticmethod(A.supplier_aging)
    export_name = "أعمار_الموردين"


class PartnerAgingReportView(AnalyticsReportView):
    builder = staticmethod(A.partner_aging)
    export_name = "أعمار_الشركاء"


class CashflowReportView(AnalyticsReportView):
    builder = staticmethod(A.cashflow)
    export_name = "حركة_الخزينة"


class PayrollReportView(AnalyticsReportView):
    builder = staticmethod(A.payroll_report)
    export_name = "تقرير_الرواتب"
