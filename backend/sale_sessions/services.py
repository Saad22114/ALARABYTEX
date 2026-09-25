from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
import logging

from django.db import transaction
from django.utils import timezone

from appsettings.models import AppSettings
from sales.models import DailySale, DailySaleItem
from warehouses.services import reverse_sale_consumption, sell_from_branch

from .models import SaleSession, SaleSessionItem

logger = logging.getLogger("accounting")


def _unpost_session(session):
    try:
        from accounting.models import JournalEntry
        from accounting.services import unpost_source
        unpost_source(JournalEntry.Source.SESSION, session.pk)
    except Exception:
        logger.exception("فشل إلغاء قيد الوردية (id=%s)", session.pk)


def _post_session(session):
    try:
        from accounting.services import post_session_close
        post_session_close(session)
    except Exception:
        logger.exception("فشل ترحيل قيد الوردية (id=%s)", session.pk)


def effective_sale_date(now=None):
    """التاريخ الفعلي للبيع: قبل ساعة بداية اليوم المحاسبي يُعتبر البيع لليوم السابق."""
    now = now or timezone.localtime()
    cutoff = AppSettings.load().previous_day_cutoff_hour
    if now.hour < cutoff:
        return now.date() - timedelta(days=1)
    return now.date()


def session_sale_date(session):
    """تاريخ تسجيل أصناف الوردية: تاريخ الوردية إن حُدِّد عند فتحها، وإلا التاريخ الفعلي الحالي."""
    if session is not None and getattr(session, "session_date", None):
        return session.session_date
    return effective_sale_date()


def _item_yards(item):
    if item.sale_type == SaleSessionItem.SaleType.ROLL:
        return item.quantity * (item.fabric.yards_per_roll or Decimal("0"))
    return item.quantity


def _manual_total(session):
    return (
        (session.manual_cash or Decimal("0"))
        + (session.manual_transfer or Decimal("0"))
        + (session.manual_card or Decimal("0"))
    )


def _apply_manual_to_daily(session, sign=1):
    """يضيف (أو يطرح) مبالغ الوردية اليدوية على السجل اليومي للفرع/التاريخ."""
    if session.manual_date is None:
        return
    cash = (session.manual_cash or Decimal("0")) * sign
    transfer = (session.manual_transfer or Decimal("0")) * sign
    card = (session.manual_card or Decimal("0")) * sign
    total = cash + transfer + card
    sale = DailySale.objects.filter(branch=session.branch, date=session.manual_date).first()
    if sale is None:
        if sign < 0 or total <= 0:
            return
        DailySale.objects.create(
            branch=session.branch,
            employee=session.employee,
            date=session.manual_date,
            total_sales=total,
            cash_amount=cash,
            transfer_amount=transfer,
            card_amount=card,
            other_amount=Decimal("0"),
            notes=f"وردية يدوية: {session.employee.name}",
        )
        return
    sale.total_sales += total
    sale.cash_amount += cash
    sale.transfer_amount += transfer
    sale.card_amount += card
    sale.save(update_fields=["total_sales", "cash_amount", "transfer_amount", "card_amount"])


def _reverse_manual_session(session):
    if session.manual_date is None:
        return
    allow_negative = False
    sale = DailySale.objects.filter(branch=session.branch, date=session.manual_date).first()
    if sale is None:
        return
    sale.total_sales -= _manual_total(session)
    sale.cash_amount -= session.manual_cash or Decimal("0")
    sale.transfer_amount -= session.manual_transfer or Decimal("0")
    sale.card_amount -= session.manual_card or Decimal("0")
    sale.save(update_fields=["total_sales", "cash_amount", "transfer_amount", "card_amount"])
    _cleanup_sale(sale, allow_negative)


@transaction.atomic
def create_manual_session(*, employee, branch, sale_date, cash, transfer, card, notes=""):
    """إنشاء وردية مغلقة كاملة كمجموع مالي بدون بنود ولا خصم مخزون."""
    total = cash + transfer + card
    session = SaleSession.objects.create(
        employee=employee,
        branch=branch,
        status=SaleSession.Status.CLOSED,
        closed_at=timezone.now(),
        is_manual=True,
        manual_date=sale_date,
        manual_cash=cash,
        manual_transfer=transfer,
        manual_card=card,
        notes=notes,
    )
    _apply_manual_to_daily(session, sign=1)
    if employee.commission_active:
        percent = Decimal(str(employee.commission_percent or "0"))
        session.commission_amount = (total * percent / Decimal("100")).quantize(Decimal("0.01"))
        session.save(update_fields=["commission_amount"])
    _post_session(session)
    return session


def recompute_commission(session):
    """إعادة حساب عمولة الموظف على إجمالي الوردية حسب نسبة عمولته."""
    total = sum(r.net_total for r in session.items.filter(is_returned=False))
    employee = session.employee
    if employee.commission_active:
        percent = Decimal(str(employee.commission_percent or "0"))
        session.commission_amount = (total * percent / Decimal("100")).quantize(Decimal("0.01"))
    else:
        session.commission_amount = Decimal("0")
    return session.commission_amount


def close_session(session):
    """تحويل بنود الوردية إلى سندات مبيعات يومية مع خصم المخزون، ثم إغلاق الوردية."""
    if session.status == SaleSession.Status.CLOSED:
        raise ValueError("الوردية مغلقة بالفعل")
    rows = list(session.items.select_related("fabric").filter(is_returned=False))

    with transaction.atomic():
        groups = defaultdict(list)
        for r in rows:
            groups[r.sale_date].append(r)

        for sale_date, group in groups.items():
            sale = DailySale.objects.filter(branch=session.branch, date=sale_date).first()
            totals = {m: Decimal("0") for m in SaleSessionItem.PaymentMethod.values}
            item_rows = []
            for r in group:
                totals[r.payment_method] += r.net_total
                item_rows.append((r.fabric_id, _item_yards(r)))
            total_all = sum(totals.values(), Decimal("0"))

            if sale is None:
                sale = DailySale.objects.create(
                    branch=session.branch,
                    employee=session.employee,
                    date=sale_date,
                    total_sales=total_all,
                    cash_amount=totals["cash"],
                    transfer_amount=totals["transfer"],
                    card_amount=totals["card"],
                    other_amount=Decimal("0"),
                    notes=f"وردية بيع: {session.employee.name}",
                )
            else:
                sale.total_sales += total_all
                sale.cash_amount += totals["cash"]
                sale.transfer_amount += totals["transfer"]
                sale.card_amount += totals["card"]
                sale.save(update_fields=["total_sales", "cash_amount", "transfer_amount", "card_amount"])

            existing = {it.fabric_id: it for it in sale.sale_items.all()}
            for fabric_id, yards in item_rows:
                if fabric_id in existing:
                    existing[fabric_id].yards += yards
                    existing[fabric_id].save(update_fields=["yards"])
                else:
                    existing[fabric_id] = DailySaleItem.objects.create(sale=sale, fabric_id=fabric_id, yards=yards)

            if item_rows:
                allow_negative = False
                sell_from_branch(session.branch, sale, item_rows, allow_negative=allow_negative)

        session.status = SaleSession.Status.CLOSED
        session.closed_at = timezone.now()
        recompute_commission(session)
        session.save(update_fields=["status", "closed_at", "commission_amount"])
        _post_session(session)
    return session


def _subtract_item(sale, item):
    payment_field = f"{item.payment_method}_amount"
    sale.total_sales -= item.net_total
    setattr(sale, payment_field, getattr(sale, payment_field) - item.net_total)
    sale.save(update_fields=["total_sales", payment_field])
    dsi = sale.sale_items.filter(fabric_id=item.fabric_id).first()
    if dsi:
        dsi.yards -= item.yards_effective
        if dsi.yards <= 0:
            dsi.delete()
        else:
            dsi.save(update_fields=["yards"])


def _add_item(sale, item):
    payment_field = f"{item.payment_method}_amount"
    sale.total_sales += item.net_total
    setattr(sale, payment_field, getattr(sale, payment_field) + item.net_total)
    sale.save(update_fields=["total_sales", payment_field])
    dsi = sale.sale_items.filter(fabric_id=item.fabric_id).first()
    if dsi:
        dsi.yards += item.yards_effective
        dsi.save(update_fields=["yards"])
    else:
        DailySaleItem.objects.create(
            sale=sale, fabric_id=item.fabric_id, yards=item.yards_effective
        )


def _rebuild_stock(sale, allow_negative):
    reverse_sale_consumption(sale)
    items = [(it.fabric, it.yards) for it in sale.sale_items.select_related("fabric").all()]
    if items:
        sell_from_branch(sale.branch, sale, items, allow_negative=allow_negative)


def _cleanup_sale(sale, allow_negative):
    if sale.total_sales <= 0 and sale.payment_total <= 0:
        reverse_sale_consumption(sale)
        sale.delete()
    else:
        _rebuild_stock(sale, allow_negative)


def _reverse_closed_items(session):
    """عكس استهلاك الوردية المغلق من السجلات اليومية والمخزون."""
    allow_negative = False
    rows = list(session.items.select_related("fabric").filter(is_returned=False))
    for item in rows:
        sale = DailySale.objects.filter(branch=session.branch, date=item.sale_date).first()
        if sale:
            _subtract_item(sale, item)
            _cleanup_sale(sale, allow_negative)


@transaction.atomic
def delete_session(session):
    """حذف وردية كاملة وإرجاع المخزون والسجلات اليومية للورديات المغلقة."""
    if session.status == SaleSession.Status.CLOSED:
        _unpost_session(session)
        if session.is_manual:
            _reverse_manual_session(session)
        else:
            _reverse_closed_items(session)
    session.items.all().delete()
    session.delete()


@transaction.atomic
def reopen_session(session):
    """إعادة فتح وردية مغلقة: عكس المبيعات اليومية والمخزون، ثم فتح الوردية."""
    if session.status != SaleSession.Status.CLOSED:
        raise ValueError("لا يمكن إعادة فتح وردية مفتوحة")
    if session.is_manual:
        raise ValueError("لا يمكن إعادة فتح وردية مُدخلة يدوياً — احذفها وأدخلها من جديد")
    _unpost_session(session)
    _reverse_closed_items(session)
    session.status = SaleSession.Status.OPEN
    session.closed_at = None
    session.commission_amount = Decimal("0")
    session.save(update_fields=["status", "closed_at", "commission_amount"])


@transaction.atomic
def move_session_item(source_session, item, target_session):
    """نقل بند من وردية مفتوحة إلى وردية مفتوحة أخرى مع إعادة التحقق من المتاح."""
    if item.is_returned:
        raise ValueError("البند مسترجع — لا يمكن نقل بند مُسترجع")
    if source_session.status != SaleSession.Status.OPEN or target_session.status != SaleSession.Status.OPEN:
        raise ValueError("يمكن نقل البنود بين ورديات مفتوحة فقط")
    if source_session.pk == target_session.pk:
        raise ValueError("لا يمكن نقل البند إلى نفس الوردية")
    if item.session_id != source_session.pk:
        raise ValueError("البند لا ينتمي إلى هذه الوردية")

    from .serializers import SaleSessionItemCreateSerializer

    check = SaleSessionItemCreateSerializer(
        data={
            "fabric": item.fabric_id,
            "sale_type": item.sale_type,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "discount_amount": item.discount_amount,
            "payment_method": item.payment_method,
            "card_type": item.card_type,
        },
        context={"session": target_session},
    )
    check.is_valid(raise_exception=True)
    item.session = target_session
    item.sale_date = session_sale_date(target_session)
    item.save(update_fields=["session", "sale_date"])
    return item


@transaction.atomic
def clear_session_items(session):
    """إفراغ كل بنود وردية مفتوحة دفعة واحدة."""
    if session.status == SaleSession.Status.CLOSED:
        raise ValueError("لا يمكن إفراغ وردية مغلقة")
    session.items.all().delete()


@transaction.atomic
def delete_session_item(session, item):
    if item.is_returned:
        raise ValueError("البند مسترجع — لا يمكن حذفه؛ يمكنك إلغاء الاسترجاع أو إعادة الوردية")
    allow_negative = False
    if session.status == SaleSession.Status.CLOSED:
        sale = DailySale.objects.filter(branch=session.branch, date=item.sale_date).first()
        if sale:
            _subtract_item(sale, item)
            _cleanup_sale(sale, allow_negative)
    item.delete()
    if session.status == SaleSession.Status.CLOSED:
        recompute_commission(session)
        session.save(update_fields=["commission_amount"])
        _post_session(session)


@transaction.atomic
def update_session_item(session, item, attrs):
    if item.is_returned:
        raise ValueError("البند مسترجع — لا يمكن تعديل بند مُسترجع؛ ألغِ الاسترجاع أولاً إذا كان خطاً")
    allow_negative = False
    closed = session.status == SaleSession.Status.CLOSED
    if closed:
        current_sale = DailySale.objects.filter(branch=session.branch, date=item.sale_date).first()
        if current_sale:
            _subtract_item(current_sale, item)
    for field in ("fabric", "sale_type", "quantity", "unit_price", "payment_method", "card_type", "card_fee_amount", "net_total", "discount_amount", "customer_name", "customer_phone"):
        if field in attrs:
            setattr(item, field, attrs[field])
    item.total = attrs.get("total", item.total)
    item.save()
    if closed:
        target_sale = DailySale.objects.filter(branch=session.branch, date=item.sale_date).first()
        if target_sale is None:
            target_sale = DailySale.objects.create(
                branch=session.branch,
                employee=session.employee,
                date=item.sale_date,
                total_sales=Decimal("0"),
                cash_amount=Decimal("0"),
                transfer_amount=Decimal("0"),
                card_amount=Decimal("0"),
                other_amount=Decimal("0"),
                notes=f"وردية بيع: {session.employee.name}",
            )
        _add_item(target_sale, item)
        if current_sale and current_sale.pk != target_sale.pk:
            _cleanup_sale(current_sale, allow_negative)
        if target_sale.pk:
            _rebuild_stock(target_sale, allow_negative)
        recompute_commission(session)
        session.save(update_fields=["commission_amount"])
        _post_session(session)
    return item


@transaction.atomic
def return_session_items(session, items, reason=""):
    """استرجاع بنود مبيعة: إبقاء السجل مع وسم «مسترجع» وترجيع الكمية إلى المخزون.

    للوردية المغلقة يُعكس البند من اليومي والمخزون (مثل الحذف) لكن يبقى البند
    مسجلاً بوسم مسترجع؛ وللوردية المفتوحة يُومَض ببساطة (تُستثنى من الإغلاق).
    """
    if session is None:
        raise ValueError("الوردية غير موجودة")
    closed = session.status == SaleSession.Status.CLOSED
    for item in items:
        if item.session_id != session.pk:
            raise ValueError("بعض البنود لا تنتمي إلى الوردية")
        if item.is_returned:
            raise ValueError("البند مسترجع مسبقاً")
    allow_negative = False
    for item in items:
        if closed:
            sale = DailySale.objects.filter(branch=session.branch, date=item.sale_date).first()
            if sale:
                _subtract_item(sale, item)
                _cleanup_sale(sale, allow_negative)
        item.is_returned = True
        item.returned_at = timezone.now()
        item.return_reason = (reason or "").strip()[:255]
        item.save(update_fields=["is_returned", "returned_at", "return_reason"])
    if closed:
        recompute_commission(session)
        session.save(update_fields=["commission_amount"])
        _post_session(session)
    return list(items)