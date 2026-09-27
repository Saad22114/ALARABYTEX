from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AdvanceExportView,
    AdvanceInstallmentViewSet,
    EmployeeStatementView,
    MyPayrollView,
    PayrollDatesView,
    PayrollEmployeesView,
    PayrollPreviewView,
    PayrollRunViewSet,
    PayrollSummaryView,
    PayslipViewSet,
    RunListExportView,
    SalaryAdvanceViewSet,
    SalaryStructureViewSet,
    StatementExportView,
)

router = DefaultRouter()
router.register("salary-structures", SalaryStructureViewSet, basename="salary-structure")
router.register("advances", SalaryAdvanceViewSet, basename="salary-advance")
router.register("advance-installments", AdvanceInstallmentViewSet, basename="advance-installment")
router.register("runs", PayrollRunViewSet, basename="payroll-run")
router.register("payslips", PayslipViewSet, basename="payslip")

urlpatterns = [
    path("", include(router.urls)),
    path("preview/", PayrollPreviewView.as_view(), name="payroll-preview"),
    path("summary/", PayrollSummaryView.as_view(), name="payroll-summary"),
    path("dates/", PayrollDatesView.as_view(), name="payroll-dates"),
    path("employees/", PayrollEmployeesView.as_view(), name="payroll-employees"),
    path("employees/<int:employee_id>/statement/", EmployeeStatementView.as_view(), name="payroll-statement"),
    path("my/", MyPayrollView.as_view(), name="payroll-my"),
    path("export/advances/", AdvanceExportView.as_view(), name="payroll-export-advances"),
    path("export/runs/", RunListExportView.as_view(), name="payroll-export-runs"),
    path("export/statement/<int:employee_id>/", StatementExportView.as_view(), name="payroll-export-statement"),
]
