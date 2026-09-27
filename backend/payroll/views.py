from datetime import date
from decimal import Decimal

from django.db.models import (
    DecimalField,
    ExpressionWrapper,
    F,
    Q,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.services import log_activity
from core.branch_scope import scope_queryset
from sale_sessions.models import Employee

from .models import (
    AdvanceInstallment,
    Payslip,
    PayrollRun,
    SalaryAdvance,
    SalaryStructure,
)
from .serializers import (
    AdvanceInstallmentSerializer,
    PayslipSerializer,
    PayrollRunListSerializer,
    PayrollRunSerializer,
    SalaryAdvanceSerializer,
    SalaryStructureSerializer,
    payslip_row_to_dict,
)
from .services import (
    approve_advance,
    approve_run,
    build_preview,
    cancel_run,
    employee_advance_total,
    month_bounds,
    money,
    normalize_month,
    outstanding_advances,
    pay_run,
    reject_advance,
    repay_advance,
    salary_snapshot,
    statement_rows,
)

ZERO = Decimal("0")


# ---------------------------------------------------------------------------
# تصدير Excel
# ---------------------------------------------------------------------------


def _xlsx_response(workbook, filename):
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}.xlsx"'
    workbook.save(response)
    return response


def _workbook_or_error(sheet_title, headers, rows, filename):
    try:
        import openpyxl
    except ImportError:
        return Response({"detail": "مكتبة openpyxl غير مثبتة"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_title
    ws.append(headers)
    for row in rows:
        ws.append(row)
    return _xlsx_response(wb, filename)


def _month_label(value):
    return f"{normalize_month(value):%Y-%m}"


def advance_queryset(request):
    """استعلام السلف مع تطبيق نطاق الفروع والفلاتر (يُستخدم في القائمة والتصدير)."""
    qs = SalaryAdvance.objects.select_related("employee", "employee__branch", "branch").prefetch_related(
        "installments"
    )
    qs = scope_queryset(request, qs, "employee__branch")
    params = request.query_params
    if params.get("employee"):
        qs = qs.filter(employee_id=params["employee"])
    if params.get("branch"):
        qs = qs.filter(Q(branch_id=params["branch"]) | Q(employee__branch_id=params["branch"]))
    if params.get("status"):
        qs = qs.filter(status=params["status"])
    if params.get("date_from"):
        qs = qs.filter(date__gte=params["date_from"])
    if params.get("date_to"):
        qs = qs.filter(date__lte=params["date_to"])
    ordered = qs.order_by("-date", "-id")
    if params.get("outstanding") in ("1", "true", "True"):
        money_field = DecimalField(max_digits=14, decimal_places=2)
        ordered = ordered.annotate(
            recovered_total=Coalesce(Sum("installments__amount"), Value(ZERO), output_field=money_field),
        ).annotate(
            remaining_total=ExpressionWrapper(
                F("amount") - F("recovered_total"), output_field=money_field
            ),
        ).exclude(status=SalaryAdvance.Status.REJECTED).filter(remaining_total__gt=0)
    return ordered


# ---------------------------------------------------------------------------
# هياكل الرواتب
# ---------------------------------------------------------------------------


class SalaryStructureViewSet(viewsets.ModelViewSet):
    permission_section = "payroll"
    serializer_class = SalaryStructureSerializer
    search_fields = ["employee__name", "notes"]

    def get_queryset(self):
        qs = SalaryStructure.objects.select_related("employee", "employee__branch")
        qs = scope_queryset(self.request, qs, "employee__branch")
        employee = self.request.query_params.get("employee")
        if employee:
            qs = qs.filter(employee_id=employee)
        branch = self.request.query_params.get("branch")
        if branch:
            qs = qs.filter(employee__branch_id=branch)
        if self.request.query_params.get("active") in ("1", "true", "True"):
            qs = qs.filter(is_active=True)
        return qs


# ---------------------------------------------------------------------------
# السلف
# ---------------------------------------------------------------------------


class SalaryAdvanceViewSet(viewsets.ModelViewSet):
    permission_section = "payroll"
    serializer_class = SalaryAdvanceSerializer
    search_fields = ["employee__name", "reason", "notes"]
    ordering_fields = ["date", "amount", "employee__name", "created_at"]

    def get_queryset(self):
        return advance_queryset(self.request)

    def perform_create(self, serializer):
        instance = serializer.save()
        if self.request.data.get("approve") in (True, "true", "1"):
            approve_advance(instance)
            instance.refresh_from_db()
        self._sync_branch(instance)

    def _sync_branch(self, advance):
        if not advance.branch_id and advance.employee_id:
            employee = Employee.objects.filter(id=advance.employee_id).first()
            if employee and employee.branch_id:
                advance.branch_id = employee.branch_id
                advance.save(update_fields=["branch", "updated_at"])

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        advance = self.get_object()
        if advance.status != SalaryAdvance.Status.PENDING:
            return Response({"detail": "السلفة ليست في حالة مسودة"}, status=status.HTTP_400_BAD_REQUEST)
        self._sync_branch(advance)
        approve_advance(advance)
        log_activity("payroll", "اعتماد سلفة راتب", advance)
        return Response(self.get_serializer(advance).data)

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        advance = self.get_object()
        try:
            reject_advance(advance)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        log_activity("payroll", "رفض سلفة راتب", advance)
        return Response(self.get_serializer(advance).data)

    @action(detail=True, methods=["post"], url_path="repay")
    def repay(self, request, pk=None):
        advance = self.get_object()
        amount = request.data.get("amount")
        if amount in (None, ""):
            return Response({"detail": "أدخل مبلغ السداد"}, status=status.HTTP_400_BAD_REQUEST)
        method = request.data.get("method") or AdvanceInstallment.Method.CASH
        paid_on = request.data.get("date")
        try:
            installment = repay_advance(advance, Decimal(str(amount)), method, paid_on)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        advance.refresh_from_db()
        log_activity(
            "payroll",
            "سداد سلفة راتب",
            advance,
            details={"amount": str(installment.amount), "method": installment.method},
        )
        return Response(
            {
                "installment": AdvanceInstallmentSerializer(installment).data,
                "advance": SalaryAdvanceSerializer(advance).data,
            }
        )

    def destroy(self, request, *args, **kwargs):
        advance = self.get_object()
        if advance.recovered_amount > 0:
            return Response(
                {"detail": "لا يمكن حذف سلفة لها سدادات مسجلة"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            from accounting.services import unpost_source
            from accounting.models import JournalEntry

            unpost_source(JournalEntry.Source.SALARY_ADVANCE, advance.pk)
        except Exception:
            pass
        self.perform_destroy(advance)
        return Response({"detail": "تم الحذف"}, status=status.HTTP_200_OK)


class AdvanceInstallmentViewSet(viewsets.ReadOnlyModelViewSet):
    permission_section = "payroll"
    serializer_class = AdvanceInstallmentSerializer
    search_fields = ["advance__employee__name"]

    def get_queryset(self):
        qs = AdvanceInstallment.objects.select_related("advance", "advance__employee")
        qs = scope_queryset(self.request, qs, "advance__employee__branch")
        if self.request.query_params.get("advance"):
            qs = qs.filter(advance_id=self.request.query_params["advance"])
        if self.request.query_params.get("employee"):
            qs = qs.filter(advance__employee_id=self.request.query_params["employee"])
        return qs.order_by("-date", "-id")


# ---------------------------------------------------------------------------
# المسيّرات والقسائم
# ---------------------------------------------------------------------------


class PayrollRunViewSet(viewsets.ModelViewSet):
    permission_section = "payroll"

    def get_serializer_class(self):
        if self.action in ("list",):
            return PayrollRunListSerializer
        return PayrollRunSerializer

    def get_queryset(self):
        qs = PayrollRun.objects.select_related("branch").prefetch_related(
            "payslips__employee", "payslips__branch"
        )
        qs = scope_queryset(self.request, qs)
        params = self.request.query_params
        if params.get("month"):
            qs = qs.filter(month=normalize_month(params["month"]))
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        if params.get("branch"):
            qs = qs.filter(branch_id=params["branch"])
        return qs.order_by("-month", "-id")

    def perform_create(self, serializer):
        month = normalize_month(serializer.validated_data.get("month"))
        branch = serializer.validated_data.get("branch")
        from .services import generate_run

        try:
            run = generate_run(month, branch, created_by=self.request.user if self.request.user.is_authenticated else None)
        except ValueError as exc:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"detail": str(exc)})
        notes = serializer.validated_data.get("notes")
        if notes:
            run.notes = notes
            run.save(update_fields=["notes", "updated_at"])
        log_activity(
            "payroll",
            "توليد مسيّر رواتب",
            run,
            details={"month": month.isoformat(), "payslips": run.payslips.count()},
        )
        serializer.instance = run

    def perform_update(self, serializer):
        run = serializer.instance
        if run.status != PayrollRun.Status.DRAFT:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"detail": "لا يمكن تعديل مسيّر مُعتمد أو مصروف"})
        serializer.save()

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        run = self.get_object()
        try:
            approve_run(run)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        log_activity("payroll", "اعتماد مسيّر رواتب", run, details=run.totals)
        return Response(PayrollRunSerializer(run).data)

    @action(detail=True, methods=["post"])
    def pay(self, request, pk=None):
        run = self.get_object()
        method = request.data.get("payment_method")
        try:
            pay_run(run, method)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        run.refresh_from_db()
        log_activity(
            "payroll",
            "صرف مسيّر رواتب",
            run,
            details={"method": run.payment_method, **run.totals},
        )
        return Response(PayrollRunSerializer(run).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        run = self.get_object()
        try:
            cancel_run(run)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        try:
            from accounting.services import unpost_payroll_run

            unpost_payroll_run(run)
        except Exception:
            pass
        log_activity("payroll", "إلغاء مسيّر رواتب", run, details=run.totals)
        return Response(PayrollRunSerializer(run).data)

    @action(detail=True, methods=["get"], url_path="export")
    def export(self, request, pk=None):
        run = self.get_object()
        rows = []
        for p in run.payslips.select_related("employee", "branch").order_by("employee__name"):
            rows.append([
                p.employee.name,
                p.branch.name if p.branch_id else "",
                float(money(p.base_salary)),
                float(money(p.total_allowances)),
                float(money(p.overtime_amount)),
                float(money(p.bonus)),
                float(money(p.commission_amount)),
                float(money(p.gross)),
                float(money(p.absence_deduction)),
                float(money(p.late_deduction)),
                float(money(p.other_deduction)),
                float(money(p.advance_deduction)),
                float(money(p.net_pay)),
                "نعم" if p.is_paid else "لا",
            ])
        totals = run.totals
        rows.append([])
        rows.append([
            "الإجمالي", "", "", "", "", "", "",
            float(money(totals["gross"])), "", "", "",
            float(money(totals["advances"])), float(money(totals["net"])), "",
        ])
        return _workbook_or_error(
            f"رواتب {_month_label(run.month)}",
            [
                "الموظف", "الفرع", "الأساسي", "البدلات", "عمل إضافي", "مكافأة", "عمولة",
                "الإجمالي", "غياب", "تأخير", "خصومات أخرى", "خصم سلفة", "الصافي", "مصروف",
            ],
            rows,
            f"كشف_رواتب_{_month_label(run.month)}",
        )

    def destroy(self, request, *args, **kwargs):
        run = self.get_object()
        if run.status == PayrollRun.Status.PAID:
            return Response(
                {"detail": "لا يمكن حذف مسيّر مصروف"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        cancel_run(run)
        run.delete()
        return Response({"detail": "تم الحذف"}, status=status.HTTP_200_OK)


class PayslipViewSet(viewsets.ModelViewSet):
    permission_section = "payroll"
    serializer_class = PayslipSerializer
    search_fields = ["employee__name", "notes"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        qs = Payslip.objects.select_related("run", "employee", "branch", "employee__branch")
        qs = scope_queryset(self.request, qs)
        params = self.request.query_params
        if params.get("run"):
            qs = qs.filter(run_id=params["run"])
        if params.get("employee"):
            qs = qs.filter(employee_id=params["employee"])
        if params.get("paid") in ("1", "true", "True"):
            qs = qs.filter(is_paid=True)
        if params.get("unpaid") in ("1", "true", "True"):
            qs = qs.filter(is_paid=False)
        if params.get("month"):
            qs = qs.filter(run__month=normalize_month(params["month"]))
        return qs.order_by("-run__month", "employee__name")

    def perform_create(self, serializer):
        run = serializer.validated_data["run"]
        if run.status != PayrollRun.Status.DRAFT:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"detail": "لا يمكن إضافة قسيمة لمسيّر مُعتمد أو مصروف"})
        employee = serializer.validated_data.get("employee")
        if employee and not employee.branch_id:
            serializer.save(branch=run.branch)
        else:
            serializer.save(branch=employee.branch if employee else run.branch)


def _scoped_employee(request, employee_id):
    """موظف ضمن نطاق فروع المستخدم الحالي، أو None."""
    return scope_queryset(
        request, Employee.objects.select_related("branch"), "branch"
    ).filter(id=employee_id).first()


# ---------------------------------------------------------------------------
# معاينات وملخصات
# ---------------------------------------------------------------------------


class PayrollPreviewView(APIView):
    """معاينة رواتب شهر قبل إنشاء المسيّر."""

    permission_section = "payroll"

    def get(self, request):
        month = normalize_month(request.query_params.get("month"))
        branch = request.query_params.get("branch") or None
        employees = None
        raw_ids = request.query_params.get("employees")
        if raw_ids:
            employees = [p for p in str(raw_ids).split(",") if p.strip()]
        data = build_preview(month, branch, employees)
        return Response(data)


class PayrollSummaryView(APIView):
    """ملخص الرواتب والسلف لشهر."""

    permission_section = "payroll"

    def get(self, request):
        start, end = month_bounds(request.query_params.get("month"))
        branch = request.query_params.get("branch") or None
        runs_qs = scope_queryset(request, PayrollRun.objects.filter(month=start), "branch")
        if branch:
            runs_qs = runs_qs.filter(branch_id=branch)
        runs = list(runs_qs.prefetch_related("payslips"))
        active_runs = [r for r in runs if r.status != PayrollRun.Status.CANCELLED]
        payslips = [p for r in active_runs for p in r.payslips.all()]

        advances_qs = scope_queryset(
            request,
            SalaryAdvance.objects.filter(date__gte=start, date__lte=end),
            "employee__branch",
        )
        if branch:
            advances_qs = advances_qs.filter(Q(branch_id=branch) | Q(employee__branch_id=branch))
        advances = list(advances_qs.prefetch_related("installments"))
        approved = [a for a in advances if a.status != SalaryAdvance.Status.REJECTED]
        outstanding = [a for a in approved if a.remaining_amount > 0]

        return Response({
            "month": start.isoformat(),
            "employees": len({p.employee_id for p in payslips}),
            "gross": float(money(sum((p.gross for p in payslips), ZERO))),
            "deductions": float(money(sum((p.total_deductions for p in payslips), ZERO))),
            "net": float(money(sum((p.net_pay for p in payslips), ZERO))),
            "advances": float(money(sum((a.amount for a in approved), ZERO))),
            "recovered": float(money(sum((a.recovered_amount for a in approved), ZERO))),
            "outstanding_advances": float(money(sum((a.remaining_amount for a in outstanding), ZERO))),
            "runs": len(active_runs),
            "paid_runs": len([r for r in active_runs if r.status == PayrollRun.Status.PAID]),
            "pending_runs": len([r for r in active_runs if r.status == PayrollRun.Status.DRAFT]),
            "approved_runs": len([r for r in active_runs if r.status == PayrollRun.Status.APPROVED]),
            "missing_structures": [
                p.employee_id for p in payslips if not SalaryStructure.objects.filter(employee_id=p.employee_id).exists()
            ],
        })


class PayrollEmployeesView(APIView):
    """قائمة موظفي الرواتب مع لقطة الراتب والسلف المستحقة."""

    permission_section = "payroll"

    def get(self, request):
        from .services import payroll_employees

        month = normalize_month(request.query_params.get("month"))
        end = month_bounds(month)[1]
        branch = request.query_params.get("branch") or None
        rows = []
        for employee in payroll_employees(branch):
            snap = salary_snapshot(employee, end)
            advances = outstanding_advances(employee, end)
            rows.append({
                "employee": employee.id,
                "employee_name": employee.name,
                "branch": employee.branch_id,
                "branch_name": employee.branch.name if employee.branch_id else "",
                "position": employee.position or "",
                "department": employee.department or "",
                "phone": employee.phone or "",
                "base_salary": float(snap["base_salary"]),
                "housing_allowance": float(snap["housing_allowance"]),
                "transport_allowance": float(snap["transport_allowance"]),
                "other_allowance": float(snap["other_allowance"]),
                "overtime_hour_rate": float(snap["overtime_hour_rate"]),
                "daily_rate": float(snap["daily_rate"]),
                "gross": float(money(
                    snap["base_salary"] + snap["housing_allowance"]
                    + snap["transport_allowance"] + snap["other_allowance"]
                )),
                "has_structure": snap["has_structure"],
                "advances_total": float(employee_advance_total(employee, end)),
                "advances_count": len(advances),
            })
        return Response({"month": month.isoformat(), "rows": rows, "count": len(rows)})


class EmployeeStatementView(APIView):
    """كشف حساب موظف: الرواتب والسلف."""

    permission_section = "payroll"

    def get(self, request, employee_id):
        employee = _scoped_employee(request, employee_id)
        if employee is None:
            return Response({"detail": "الموظف غير موجود أو خارج نطاقك"}, status=status.HTTP_404_NOT_FOUND)
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        data = statement_rows(
            employee,
            date.fromisoformat(date_from) if date_from else None,
            date.fromisoformat(date_to) if date_to else None,
        )
        return Response(data)


# ---------------------------------------------------------------------------
# تصديرات عامة
# ---------------------------------------------------------------------------


class AdvanceExportView(APIView):
    permission_section = "payroll"

    def get(self, request):
        rows = []
        for a in advance_queryset(request):
            rows.append([
                a.employee.name,
                a.branch.name if a.branch_id else (a.employee.branch.name if a.employee.branch_id else ""),
                str(a.date),
                float(money(a.amount)),
                a.get_method_display(),
                a.get_status_display(),
                float(money(a.recovered_amount)),
                float(money(a.remaining_amount)),
                a.reason or "",
            ])
        return _workbook_or_error(
            "سلف الرواتب",
            ["الموظف", "الفرع", "التاريخ", "المبلغ", "طريقة الصرف", "الحالة", "المسدد", "المتبقي", "السبب"],
            rows,
            "سلف_الرواتب",
        )


class RunListExportView(APIView):
    permission_section = "payroll"

    def get(self, request):
        runs = scope_queryset(request, PayrollRun.objects.select_related("branch"), "branch")
        month = request.query_params.get("month")
        if month:
            runs = runs.filter(month=normalize_month(month))
        rows = []
        for r in runs.order_by("-month"):
            totals = r.totals
            rows.append([
                f"{r.month:%Y-%m}",
                r.branch.name if r.branch_id else "كل الفروع",
                r.get_status_display(),
                totals["employees"],
                float(money(totals["gross"])),
                float(money(totals["deductions"])),
                float(money(totals["net"])),
                float(money(totals["advances"])),
            ])
        return _workbook_or_error(
            "مسيّرات الرواتب",
            ["الشهر", "الفرع", "الحالة", "الموظفون", "الإجمالي", "الخصومات", "الصافي", "خصم سلفة"],
            rows,
            "مسيّرات_الرواتب",
        )


class StatementExportView(APIView):
    permission_section = "payroll"

    def get(self, request, employee_id):
        employee = _scoped_employee(request, employee_id)
        if employee is None:
            return Response({"detail": "الموظف غير موجود أو خارج نطاقك"}, status=status.HTTP_404_NOT_FOUND)
        data = statement_rows(employee)
        rows = [
            [str(r["date"]), r["type_label"], r["ref"], float(r["debit"]), float(r["credit"]), r["notes"]]
            for r in data["rows"]
        ]
        return _workbook_or_error(
            f"كشف {employee.name}",
            ["التاريخ", "النوع", "المرجع", "مدين", "دائن", "ملاحظات"],
            rows,
            f"كشف_حساب_{employee.name}",
        )


class PayrollDatesView(APIView):
    """مرجع سريع: الشهر الحالي والسابق ونهاية الشهر."""

    permission_section = "@payroll"

    def get(self, request):
        today = timezone.localdate()
        current = today.replace(day=1)
        previous = date(current.year - 1, 12, 1) if current.month == 1 else date(current.year, current.month - 1, 1)
        start, end = month_bounds(current)
        return Response({
            "today": today.isoformat(),
            "month": current.isoformat(),
            "month_end": end.isoformat(),
            "previous_month": previous.isoformat(),
        })


class MyPayrollView(APIView):
    """راتبي: صيانة ذاتية — كل موظف يرى راتبه وسلفه وقسائمه هو فقط.

    الصلاحية من «الطيف @» أي موظف مصادق عليه، والبيانات تُقصّ برمجياً على
    الموظف الحالي من الطلب حصراً (لا معرّف خارجي).
    """

    permission_section = "@payroll"

    def get(self, request):
        from core.permissions import get_request_employee

        employee = get_request_employee(request)
        if employee is None:
            return Response(
                {"detail": "لا يوجد موظف مرتبط بحسابك"},
                status=status.HTTP_404_NOT_FOUND,
            )
        today = timezone.localdate()

        structure = salary_snapshot(employee, today)
        payslips_qs = (
            Payslip.objects.filter(employee=employee)
            .select_related("run", "branch")
            .order_by("-run__month", "-id")
        )
        advances_qs = (
            SalaryAdvance.objects.filter(employee=employee)
            .select_related("branch")
            .order_by("-date", "-id")
        )

        payslips = PayslipSerializer(payslips_qs, many=True).data
        advances = SalaryAdvanceSerializer(advances_qs, many=True).data

        active_qs = payslips_qs.exclude(run__status=PayrollRun.Status.CANCELLED)
        paid_qs = active_qs.filter(is_paid=True)
        approved_advances = [
            a for a in advances_qs if a.status == SalaryAdvance.Status.APPROVED
        ]
        outstanding = float(
            sum((a.remaining_amount for a in approved_advances if not a.is_settled), ZERO)
        )
        summary = {
            "gross_total": float(sum((p.gross for p in active_qs), ZERO)),
            "net_total": float(sum((p.net_pay for p in active_qs), ZERO)),
            "paid_net": float(sum((p.net_pay for p in paid_qs), ZERO)),
            "payslip_count": active_qs.count(),
            "structure_exists": bool(structure["has_structure"]),
            "outstanding_advances": outstanding,
        }

        return Response({
            "employee": {
                "id": employee.id,
                "name": employee.name,
                "avatar": employee.avatar,
                "avatar_image": employee.avatar_image,
                "phone": employee.phone,
                "position": employee.position,
                "department": employee.department,
                "branch_id": employee.branch_id,
                "branch_name": employee.branch.name if employee.branch_id else "",
                "hire_date": employee.hire_date.isoformat() if employee.hire_date else None,
            },
            "structure": structure,
            "payslips": payslips,
            "advances": advances,
            "statement": statement_rows(employee, None, None),
            "summary": summary,
        })
