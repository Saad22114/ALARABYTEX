"""عروض Reports V2 — كل تقرير يتبع نفس العقد (period/previous/columns/rows/kpis).

تدعم جميعها:
- ?date_from=&date_to=  الفترة (افتراضياً 30 يوماً)
- ?group_by=day|week|month  للتقارير الزمنية
- ?export=xlsx            تصدير Excel بنفس أعمدة الجدول
"""

from django.http import HttpResponse
from rest_framework.response import Response
from rest_framework.views import APIView

from . import analytics as A


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
        try:
            import openpyxl
        except ImportError:
            return Response({"detail": "مكتبة openpyxl غير مثبتة"}, status=500)
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = (payload.get("title") or self.export_name)[:31]
        for row in A.xlsx_rows(payload.get("columns") or [], payload.get("rows") or [], payload.get("totals")):
            ws.append(row)
        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{payload.get("key", "report")}.xlsx"'
        wb.save(response)
        return response


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
