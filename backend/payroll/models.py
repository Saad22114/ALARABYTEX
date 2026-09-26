from datetime import date
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Index

from core.models import TimeStampedModel, ActiveModel
from sale_sessions.models import Employee

ZERO = Decimal("0")


def _q2(value):
    return value.quantize(Decimal("0.01"))


class SalaryStructure(TimeStampedModel, ActiveModel):
    """هيكل راتب موظف: الأساسي والبدلات وسعر ساعة العمل الإضافي.

    يُحفظ كتاريخ متسلسل (effective_from) فيمكن تعديل راتب لاحقاً دون المساس
    بقسائم شهر سابق. إن لم يوجد هيكل، يُستخدم Employee.base_salary.
    """

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="salary_structures",
        verbose_name="الموظف",
    )
    base_salary = models.DecimalField(
        max_digits=12, decimal_places=2, default=ZERO, verbose_name="الراتب الأساسي"
    )
    housing_allowance = models.DecimalField(
        max_digits=12, decimal_places=2, default=ZERO, verbose_name="بدل السكن"
    )
    transport_allowance = models.DecimalField(
        max_digits=12, decimal_places=2, default=ZERO, verbose_name="بدل النقل"
    )
    other_allowance = models.DecimalField(
        max_digits=12, decimal_places=2, default=ZERO, verbose_name="بدلات أخرى"
    )
    overtime_hour_rate = models.DecimalField(
        max_digits=10, decimal_places=2, default=ZERO, verbose_name="سعر ساعة العمل الإضافي"
    )
    working_days = models.DecimalField(
        max_digits=5, decimal_places=1, default=Decimal("26"),
        verbose_name="عدد أيام العمل الشهرية",
        help_text="يُستخدم في احتساب خصم الغياب (يوم = الراتب الأساسي ÷ الأيام)",
    )
    daily_work_hours = models.DecimalField(
        max_digits=4, decimal_places=1, default=Decimal("9"),
        verbose_name="ساعات العمل اليومية",
        help_text="ما زاد على هذا الحد في الوردية يُحتسب عملاً إضافياً (للموظفين المُفعَّل لهم الحضور التلقائي)",
    )
    effective_from = models.DateField(
        default=date.today, verbose_name="سري من تاريخ"
    )
    effective_to = models.DateField(
        null=True, blank=True, verbose_name="سري حتى تاريخ"
    )
    notes = models.TextField(blank=True, verbose_name="ملاحظات")

    class Meta:
        verbose_name = "هيكل راتب"
        verbose_name_plural = "هياكل الرواتب"
        ordering = ["-effective_from", "-id"]
        indexes = [Index(fields=["employee", "effective_from"])]

    def __str__(self):
        return f"{self.employee.name} — {self.gross}"

    @property
    def total_allowances(self):
        return (self.housing_allowance or ZERO) + (self.transport_allowance or ZERO) + (self.other_allowance or ZERO)

    @property
    def gross(self):
        return (self.base_salary or ZERO) + self.total_allowances

    @property
    def daily_rate(self):
        days = self.working_days or Decimal("26")
        if days <= 0:
            return ZERO
        return ((self.base_salary or ZERO) / days).quantize(Decimal("0.01"))

    def covers(self, on_date):
        if self.effective_from and on_date < self.effective_from:
            return False
        if self.effective_to and on_date > self.effective_to:
            return False
        return True


class SalaryAdvance(TimeStampedModel, ActiveModel):
    """سلفة راتب: مبلغ يُمنح للموظف ويُسدد من رواتبه أو نقداً."""

    class Status(models.TextChoices):
        PENDING = "pending", "مسودة"
        APPROVED = "approved", "معتمدة"
        REJECTED = "rejected", "مرفوضة"
        SETTLED = "settled", "مسددة"

    class Method(models.TextChoices):
        CASH = "cash", "نقدي"
        TRANSFER = "transfer", "تحويل"

    employee = models.ForeignKey(
        Employee, on_delete=models.PROTECT, related_name="salary_advances",
        verbose_name="الموظف",
    )
    branch = models.ForeignKey(
        "branches.Branch", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="salary_advances", verbose_name="الفرع",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="مبلغ السلفة")
    date = models.DateField(default=date.today, verbose_name="تاريخ السلفة")
    method = models.CharField(
        max_length=10, choices=Method.choices, default=Method.CASH, verbose_name="طريقة الصرف"
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING, verbose_name="الحالة"
    )
    reason = models.CharField(max_length=255, blank=True, verbose_name="السبب")
    notes = models.TextField(blank=True, verbose_name="ملاحظات")
    settled_at = models.DateTimeField(null=True, blank=True, verbose_name="تاريخ السداد الكامل")

    class Meta:
        verbose_name = "سلفة راتب"
        verbose_name_plural = "سلف الرواتب"
        ordering = ["-date", "-id"]
        indexes = [
            Index(fields=["employee", "date"]),
            Index(fields=["status", "date"]),
        ]

    def __str__(self):
        return f"{self.employee.name} — {self.amount}"

    @property
    def recovered_amount(self):
        total = sum(
            (i.amount or ZERO for i in self.installments.all()), ZERO
        )
        return total.quantize(Decimal("0.01"))

    @property
    def remaining_amount(self):
        value = (self.amount or ZERO) - self.recovered_amount
        return value if value > 0 else Decimal("0.00")

    @property
    def is_settled(self):
        return self.recovered_amount >= (self.amount or ZERO)


class AdvanceInstallment(TimeStampedModel):
    """قسط/سداد لسلفة — نقدي أو خصم من راتب."""

    class Method(models.TextChoices):
        CASH = "cash", "نقدي"
        TRANSFER = "transfer", "تحويل"
        DEDUCTION = "deduction", "خصم من الراتب"

    advance = models.ForeignKey(
        SalaryAdvance, on_delete=models.CASCADE, related_name="installments",
        verbose_name="السلفة",
    )
    date = models.DateField(default=date.today, verbose_name="تاريخ السداد")
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="المبلغ المسدد")
    method = models.CharField(
        max_length=10, choices=Method.choices, default=Method.DEDUCTION,
        verbose_name="طريقة السداد",
    )
    payslip = models.ForeignKey(
        "payroll.Payslip", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="advance_installments", verbose_name="قسيمة الراتب",
    )
    notes = models.CharField(max_length=255, blank=True, verbose_name="ملاحظات")

    class Meta:
        verbose_name = "سداد سلفة"
        verbose_name_plural = "سدادات السلف"
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.advance.employee.name} — {self.amount}"


class PayrollRun(TimeStampedModel):
    """مسيّر رواتب لشهر وفرع (فراغي = كل الفروع)."""

    class Status(models.TextChoices):
        DRAFT = "draft", "مسودة"
        APPROVED = "approved", "معتمد"
        PAID = "paid", "مدفوع"
        CANCELLED = "cancelled", "ملغى"

    month = models.DateField(verbose_name="الشهر", help_text="أول يوم من الشهر")
    branch = models.ForeignKey(
        "branches.Branch", on_delete=models.PROTECT, null=True, blank=True,
        related_name="payroll_runs", verbose_name="الفرع",
        help_text="فارغ = مسيّر لكل الفروع",
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.DRAFT, verbose_name="الحالة"
    )
    payment_method = models.CharField(
        max_length=10, blank=True, default="", verbose_name="طريقة الصرف"
    )
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name="تاريخ الصرف")
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name="تاريخ الاعتماد")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="payroll_runs", verbose_name="أنشأه",
    )
    notes = models.TextField(blank=True, verbose_name="ملاحظات")

    class Meta:
        verbose_name = "مسيّر رواتب"
        verbose_name_plural = "مسيّرات الرواتب"
        ordering = ["-month", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["month", "branch"],
                condition=models.Q(branch__isnull=False),
                name="uniq_payroll_run_month_branch",
            )
        ]
        indexes = [Index(fields=["month", "status"])]

    def __str__(self):
        month = self.month
        label = month.strftime("%Y-%m") if hasattr(month, "strftime") else str(month)
        return f"{label} — {self.branch.name if self.branch_id else 'كل الفروع'}"

    @property
    def totals(self):
        payslips = list(self.payslips.all())
        return {
            "employees": len(payslips),
            "gross": sum((p.gross for p in payslips), ZERO),
            "deductions": sum((p.total_deductions for p in payslips), ZERO),
            "net": sum((p.net_pay for p in payslips), ZERO),
            "advances": sum((p.advance_deduction for p in payslips), ZERO),
            "paid": sum((p.net_pay for p in payslips if p.is_paid), ZERO),
        }


class Payslip(TimeStampedModel):
    """قسيمة راتب موظف داخل مسيّر — لقطة ثابتة عند التوليد."""

    class PaymentMethod(models.TextChoices):
        CASH = "cash", "نقدي"
        TRANSFER = "transfer", "تحويل"

    run = models.ForeignKey(
        PayrollRun, on_delete=models.CASCADE, related_name="payslips", verbose_name="المسيّر"
    )
    employee = models.ForeignKey(
        Employee, on_delete=models.PROTECT, related_name="payslips", verbose_name="الموظف"
    )
    branch = models.ForeignKey(
        "branches.Branch", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="payslips", verbose_name="الفرع",
    )
    base_salary = models.DecimalField(
        max_digits=12, decimal_places=2, default=ZERO, verbose_name="الراتب الأساسي"
    )
    housing_allowance = models.DecimalField(
        max_digits=12, decimal_places=2, default=ZERO, verbose_name="بدل السكن"
    )
    transport_allowance = models.DecimalField(
        max_digits=12, decimal_places=2, default=ZERO, verbose_name="بدل النقل"
    )
    other_allowance = models.DecimalField(
        max_digits=12, decimal_places=2, default=ZERO, verbose_name="بدلات أخرى"
    )
    working_days = models.DecimalField(
        max_digits=5, decimal_places=1, default=Decimal("26"),
        verbose_name="عدد أيام العمل الشهرية", help_text="لقطة من الهيكل وقت التوليد",
    )
    daily_rate = models.DecimalField(
        max_digits=10, decimal_places=2, default=ZERO, verbose_name="قيمة اليوم"
    )
    overtime_hour_rate = models.DecimalField(
        max_digits=10, decimal_places=2, default=ZERO, verbose_name="سعر ساعة العمل الإضافي"
    )
    overtime_hours = models.DecimalField(
        max_digits=7, decimal_places=2, default=ZERO, verbose_name="ساعات إضافية"
    )
    overtime_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=ZERO, verbose_name="قيمة العمل الإضافي"
    )
    bonus = models.DecimalField(
        max_digits=12, decimal_places=2, default=ZERO, verbose_name="مكافأة"
    )
    commission_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=ZERO, verbose_name="عمولة المبيعات"
    )
    absence_days = models.DecimalField(
        max_digits=6, decimal_places=1, default=ZERO, verbose_name="أيام الغياب"
    )
    absence_deduction = models.DecimalField(
        max_digits=12, decimal_places=2, default=ZERO, verbose_name="خصم الغياب"
    )
    late_deduction = models.DecimalField(
        max_digits=12, decimal_places=2, default=ZERO, verbose_name="خصم التأخير"
    )
    other_deduction = models.DecimalField(
        max_digits=12, decimal_places=2, default=ZERO, verbose_name="خصومات أخرى"
    )
    advance_deduction = models.DecimalField(
        max_digits=12, decimal_places=2, default=ZERO,
        verbose_name="خصم سلفة", help_text="يُسجَّل سداداً للسلفة تلقائياً عند الاعتماد",
    )
    is_paid = models.BooleanField(default=False, verbose_name="مصروف")
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name="تاريخ الصرف")
    payment_method = models.CharField(
        max_length=10, choices=PaymentMethod.choices, default=PaymentMethod.CASH,
        verbose_name="طريقة الصرف",
    )
    notes = models.TextField(blank=True, verbose_name="ملاحظات")

    class Meta:
        verbose_name = "قسيمة راتب"
        verbose_name_plural = "قسائم الرواتب"
        ordering = ["-run__month", "employee__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "employee"], name="uniq_payslip_run_employee"
            )
        ]
        indexes = [Index(fields=["employee", "-created_at"])]

    def __str__(self):
        return f"{self.employee.name} — {self.net_pay}"

    def save(self, *args, **kwargs):
        """يحسب العمل الإضافي وخصم الغياب تلقائياً من اللقطة إن لم يُحدَّدا يدوياً."""
        auto = []
        if self.overtime_hours and not self.overtime_amount and (self.overtime_hour_rate or ZERO) > 0:
            self.overtime_amount = _q2(Decimal(str(self.overtime_hours)) * Decimal(str(self.overtime_hour_rate)))
            auto.append("overtime_amount")
        if self.absence_days and not self.absence_deduction and (self.daily_rate or ZERO) > 0:
            self.absence_deduction = _q2(Decimal(str(self.absence_days)) * Decimal(str(self.daily_rate)))
            auto.append("absence_deduction")
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and auto:
            kwargs["update_fields"] = list({*update_fields, *auto})
        super().save(*args, **kwargs)

    @property
    def total_allowances(self):
        return (
            (self.housing_allowance or ZERO)
            + (self.transport_allowance or ZERO)
            + (self.other_allowance or ZERO)
        )

    @property
    def gross(self):
        return (
            (self.base_salary or ZERO)
            + self.total_allowances
            + (self.overtime_amount or ZERO)
            + (self.bonus or ZERO)
            + (self.commission_amount or ZERO)
        )

    @property
    def total_deductions(self):
        return (
            (self.absence_deduction or ZERO)
            + (self.late_deduction or ZERO)
            + (self.other_deduction or ZERO)
            + (self.advance_deduction or ZERO)
        )

    @property
    def net_pay(self):
        return self.gross - self.total_deductions
