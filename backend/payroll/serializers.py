from decimal import Decimal

from rest_framework import serializers

from .models import (
    AdvanceInstallment,
    Payslip,
    PayrollRun,
    SalaryAdvance,
    SalaryStructure,
)
from .services import money, normalize_month

ZERO = Decimal("0")


class SalaryStructureSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.name", read_only=True)
    branch_name = serializers.CharField(source="employee.branch.name", read_only=True, default="")
    total_allowances = serializers.FloatField(read_only=True)
    gross = serializers.FloatField(read_only=True)
    daily_rate = serializers.FloatField(read_only=True)

    class Meta:
        model = SalaryStructure
        fields = [
            "id", "employee", "employee_name", "branch_name",
            "base_salary", "housing_allowance", "transport_allowance", "other_allowance",
            "overtime_hour_rate", "working_days", "effective_from", "effective_to",
            "notes", "is_active", "total_allowances", "gross", "daily_rate",
            "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate_employee(self, value):
        if not value.is_active:
            raise serializers.ValidationError("لا يمكن إنشاء هيكل لموظف غير نشط")
        return value

    def validate(self, attrs):
        employee = attrs.get("employee") or getattr(self.instance, "employee", None)
        effective_from = attrs.get("effective_from") or getattr(self.instance, "effective_from", None)
        if employee and effective_from and SalaryStructure.objects.filter(
            employee=employee, effective_from=effective_from
        ).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError("يوجد هيكل راتب لنفس الموظف بنفس تاريخ السريان")
        return attrs


class AdvanceInstallmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdvanceInstallment
        fields = ["id", "advance", "date", "amount", "method", "payslip", "notes", "created_at"]
        read_only_fields = ["created_at"]


class SalaryAdvanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.name", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True, default="")
    recovered_amount = serializers.FloatField(read_only=True)
    remaining_amount = serializers.FloatField(read_only=True)
    is_settled = serializers.BooleanField(read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    installments = AdvanceInstallmentSerializer(many=True, read_only=True)

    class Meta:
        model = SalaryAdvance
        fields = [
            "id", "employee", "employee_name", "branch", "branch_name",
            "amount", "date", "method", "status", "status_label", "reason", "notes",
            "settled_at", "recovered_amount", "remaining_amount", "is_settled",
            "installments", "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["settled_at", "created_at", "updated_at"]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("مبلغ السلفة يجب أن يكون أكبر من صفر")
        return value

    def validate(self, attrs):
        if self.instance and "status" in attrs and attrs["status"] != self.instance.status:
            raise serializers.ValidationError(
                {"status": "الحالة تُدار عبر إجراءات الاعتماد والرفض"}
            )
        status = attrs.get("status") or getattr(self.instance, "status", None)
        if status == SalaryAdvance.Status.APPROVED and self.instance:
            if self.instance.recovered_amount > 0:
                raise serializers.ValidationError("لا يمكن اعتماد سلفة لها سدادات مسجلة")
        return attrs


class PayslipSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.name", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True, default="")
    month = serializers.DateField(source="run.month", read_only=True)
    run_status = serializers.CharField(source="run.status", read_only=True)
    total_allowances = serializers.FloatField(read_only=True)
    gross = serializers.FloatField(read_only=True)
    total_deductions = serializers.FloatField(read_only=True)
    net_pay = serializers.FloatField(read_only=True)

    class Meta:
        model = Payslip
        fields = [
            "id", "run", "month", "run_status", "employee", "employee_name",
            "branch", "branch_name",
            "base_salary", "housing_allowance", "transport_allowance", "other_allowance",
            "working_days", "daily_rate", "overtime_hour_rate",
            "overtime_hours", "overtime_amount", "bonus", "commission_amount",
            "absence_days", "absence_deduction", "late_deduction", "other_deduction",
            "advance_deduction", "total_allowances", "gross", "total_deductions", "net_pay",
            "is_paid", "paid_at", "payment_method", "notes", "created_at", "updated_at",
        ]
        read_only_fields = [
            "is_paid", "paid_at", "created_at", "updated_at",
        ]

    def validate(self, attrs):
        if self.instance and self.instance.run.status not in (PayrollRun.Status.DRAFT,):
            raise serializers.ValidationError("القسيمة مثبتة في مسيّر مُعتمد أو مصروف")
        for field in (
            "overtime_hours", "absence_days", "overtime_amount", "bonus",
            "commission_amount", "absence_deduction", "late_deduction",
            "other_deduction", "advance_deduction",
        ):
            value = attrs.get(field)
            if value is not None and value < 0:
                raise serializers.ValidationError({field: "القيمة لا يمكن أن تكون سالبة"})
        return attrs


class PayrollRunSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source="branch.name", read_only=True, default="")
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    month = serializers.DateField(required=False)
    totals = serializers.SerializerMethodField()
    payslips = PayslipSerializer(many=True, read_only=True)

    class Meta:
        model = PayrollRun
        fields = [
            "id", "month", "branch", "branch_name", "status", "status_label",
            "payment_method", "paid_at", "approved_at", "notes", "totals", "payslips",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "status", "paid_at", "approved_at", "created_at", "updated_at",
        ]

    def get_totals(self, obj):
        totals = obj.totals
        return {k: float(v) for k, v in totals.items()}

    def validate_month(self, value):
        return normalize_month(value)

    def validate(self, attrs):
        month = attrs.get("month") or getattr(self.instance, "month", None)
        branch = attrs.get("branch", getattr(self.instance, "branch", None))
        if month and PayrollRun.objects.filter(month=month, branch=branch).exclude(
            pk=self.instance.pk if self.instance else None
        ).exists():
            raise serializers.ValidationError("يوجد مسيّر رواتب لهذا الشهر والفرع بالفعل")
        return attrs


class PayrollRunListSerializer(PayrollRunSerializer):
    class Meta(PayrollRunSerializer.Meta):
        fields = [f for f in PayrollRunSerializer.Meta.fields if f != "payslips"]


class PayrollSummarySerializer(serializers.Serializer):
    """ملخص الرواتب لشهر — يُبنى في العرض."""

    month = serializers.CharField()
    employees = serializers.IntegerField()
    gross = serializers.FloatField()
    deductions = serializers.FloatField()
    net = serializers.FloatField()
    advances = serializers.FloatField()
    outstanding_advances = serializers.FloatField()
    paid_runs = serializers.IntegerField()
    pending_runs = serializers.IntegerField()


def payslip_row_to_dict(payslip):
    return {
        "id": payslip.id,
        "employee": payslip.employee_id,
        "employee_name": payslip.employee.name,
        "branch": payslip.branch_id,
        "branch_name": payslip.branch.name if payslip.branch_id else "",
        "base_salary": float(money(payslip.base_salary)),
        "total_allowances": float(money(payslip.total_allowances)),
        "overtime_amount": float(money(payslip.overtime_amount)),
        "bonus": float(money(payslip.bonus)),
        "commission_amount": float(money(payslip.commission_amount)),
        "gross": float(money(payslip.gross)),
        "absence_deduction": float(money(payslip.absence_deduction)),
        "late_deduction": float(money(payslip.late_deduction)),
        "other_deduction": float(money(payslip.other_deduction)),
        "advance_deduction": float(money(payslip.advance_deduction)),
        "total_deductions": float(money(payslip.total_deductions)),
        "net_pay": float(money(payslip.net_pay)),
        "is_paid": payslip.is_paid,
        "notes": payslip.notes or "",
    }
