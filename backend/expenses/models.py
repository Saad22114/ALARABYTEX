from django.db import models
from django.db.models import Index
from core.models import TimeStampedModel, ActiveModel


class ExpenseCategory(TimeStampedModel, ActiveModel):
    name = models.CharField(max_length=120, verbose_name="اسم التصنيف")
    code = models.CharField(max_length=30, unique=True, blank=True, verbose_name="كود التصنيف")
    is_system = models.BooleanField(default=False, verbose_name="تصنيف أساسي")
    notes = models.CharField(max_length=255, blank=True, verbose_name="ملاحظات")

    class Meta:
        verbose_name = "تصنيف مصروف"
        verbose_name_plural = "تصنيفات المصاريف"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Expense(TimeStampedModel):
    class PaymentMethod(models.TextChoices):
        CASH = "cash", "نقدي"
        TRANSFER = "transfer", "تحويل"
        CARD = "card", "بطاقة"
        OTHER = "other", "أخرى"

    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.PROTECT,
        related_name="expenses",
        verbose_name="الفرع",
    )
    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.PROTECT,
        related_name="expenses",
        verbose_name="نوع المصروف",
    )
    date = models.DateField(verbose_name="التاريخ")
    amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="المبلغ")
    payment_method = models.CharField(
        max_length=10,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
        verbose_name="طريقة الدفع",
    )
    description = models.CharField(max_length=255, blank=True, verbose_name="الوصف")
    notes = models.TextField(blank=True, verbose_name="ملاحظات")

    class Meta:
        verbose_name = "مصروف"
        verbose_name_plural = "المصاريف"
        ordering = ["-date", "-created_at"]
        indexes = [
            Index(fields=["branch", "date"]),
            Index(fields=["category", "date"]),
        ]

    def __str__(self):
        return f"{self.category.name} - {self.date} - {self.amount}"


class ExpenseBudget(TimeStampedModel):
    """ميزانية شهرية لمصروف فرع/تصنيف للمقارنة مع المصروف الفعلي."""

    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.CASCADE,
        related_name="expense_budgets",
        verbose_name="الفرع",
    )
    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.CASCADE,
        related_name="budgets",
        verbose_name="التصنيف",
    )
    month = models.DateField(verbose_name="الشهر", help_text="أول يوم من الشهر")
    amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="قيمة الميزانية")

    class Meta:
        verbose_name = "ميزانية شهرية"
        verbose_name_plural = "الميزانيات الشهرية"
        ordering = ["-month", "branch__name", "category__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["branch", "category", "month"],
                name="uniq_expense_budget_branch_category_month",
            )
        ]
        indexes = [
            Index(fields=["branch", "month"]),
            Index(fields=["category", "month"]),
        ]

    def __str__(self):
        return f"{self.branch.name} - {self.category.name} - {self.month} - {self.amount}"
