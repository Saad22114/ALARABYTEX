from django.contrib import admin

from .models import AdvanceInstallment, Payslip, PayrollRun, SalaryAdvance, SalaryStructure


@admin.register(SalaryStructure)
class SalaryStructureAdmin(admin.ModelAdmin):
    list_display = ("employee", "base_salary", "housing_allowance", "transport_allowance", "effective_from", "is_active")
    list_filter = ("is_active",)
    search_fields = ("employee__name",)


@admin.register(SalaryAdvance)
class SalaryAdvanceAdmin(admin.ModelAdmin):
    list_display = ("employee", "amount", "date", "method", "status", "branch")
    list_filter = ("status", "method")
    search_fields = ("employee__name", "reason")


@admin.register(AdvanceInstallment)
class AdvanceInstallmentAdmin(admin.ModelAdmin):
    list_display = ("advance", "amount", "date", "method")
    list_filter = ("method",)


@admin.register(PayrollRun)
class PayrollRunAdmin(admin.ModelAdmin):
    list_display = ("month", "branch", "status", "paid_at")
    list_filter = ("status",)


@admin.register(Payslip)
class PayslipAdmin(admin.ModelAdmin):
    list_display = ("employee", "run", "gross", "net_pay", "is_paid")
    list_filter = ("is_paid", "payment_method")
    search_fields = ("employee__name",)
