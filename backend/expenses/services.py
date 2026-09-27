"""خدمات المصاريف المتكررة: ترحيل تلقائي للمصاريف الثابتة إلى المواعيد القادمة.

القاعدة:
- المصروف «الأصل» يحمل is_recurring=True ويُحفظ عليه next_run_date (موعد النسخة القادمة).
- عند حلول الموعد تُنشأ نسخة بتاريخ الموعد (is_recurring=False، origin=الأصل)
  وتُرحَّل محاسبياً كأي مصروف، ثم يتقدم next_run_date للأصل حسب دورة التكرار.
- النسخ سريعة ثابتة: تعديلها أو حذفها لا يؤثر على الدورة، والدورة الأصل فقط هي محرك النسخ.
"""

import logging
from datetime import date, timedelta

from django.utils import timezone

from .models import Expense

logger = logging.getLogger(__name__)


def add_months(value: date, months: int) -> date:
    """نفس اليوم من الشهر الذي يليه/يسبقه مع تثبيت نهاية الشهر (31/30 → آخر يوم)."""
    idx = value.month - 1 + months
    year = value.year + idx // 12
    month = idx % 12 + 1
    day = min(value.day, _days_in_month(year, month))
    return date(year, month, day)


def _days_in_month(year, month):
    if month == 12:
        next_first = date(year + 1, 1, 1)
    else:
        next_first = date(year, month + 1, 1)
    return (next_first - timedelta(days=1)).day


def advance_run_date(value: date, frequency: str) -> date:
    """الموعد التالي بعد value حسب دورة التكرار."""
    if frequency == Expense.RecurringFrequency.WEEKLY:
        return value + timedelta(days=7)
    return add_months(value, 1)


def suggested_next_run_date(expense_date: date, frequency: str) -> date:
    """أول موعد قادم يُنشأ بعده — يُقترح عند إنشاء مصروف متكرر بلا موعد محدد."""
    if frequency == Expense.RecurringFrequency.WEEKLY:
        return expense_date + timedelta(days=7)
    return add_months(expense_date, 1)


def generate_due_recurring_expenses(through_date: date | None = None):
    """ينشئ نسخ المصاريف المتكررة المستحقة حتى through_date ويعيد النسخ الجديدة.

    يُستدعى تلقائياً عند فتح صفحة المصاريف، ويدوياً من زر «ترحيل المتكررة».
    العملية آمنة للتكرار: لا تُنشأ نسخة بتاريخ موجود مسبقاً لنفس الأصل.
    """
    through = through_date or timezone.localdate()
    originals = Expense.objects.filter(
        is_recurring=True,
        next_run_date__isnull=False,
        next_run_date__lte=through,
    ).select_related("branch", "category")

    created = []
    for original in originals:
        run_date = original.next_run_date
        advanced = False
        while run_date <= through:
            if not Expense.objects.filter(origin_id=original.id, date=run_date).exists():
                copy = Expense.objects.create(
                    branch=original.branch,
                    category=original.category,
                    date=run_date,
                    amount=original.amount,
                    payment_method=original.payment_method,
                    description=original.description,
                    notes=original.notes,
                    is_recurring=False,
                    recur_frequency=original.recur_frequency,
                    next_run_date=None,
                    origin=original,
                )
                created.append(copy)
                try:
                    from accounting.services import post_expense

                    post_expense(copy)
                except Exception:
                    logger.exception("فشل ترحيل قيد مصروف متكرر (id=%s)", copy.pk)
            run_date = advance_run_date(run_date, original.recur_frequency)
            advanced = True
        if advanced and run_date != original.next_run_date:
            original.next_run_date = run_date
            original.save(update_fields=["next_run_date", "updated_at"])
    return created