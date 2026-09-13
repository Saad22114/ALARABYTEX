from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from appsettings.models import AppSettings
from sales.models import DailySale, DailySaleItem
from warehouses.services import reverse_sale_consumption, sell_from_branch

from .models import SaleSession, SaleSessionItem


def effective_sale_date(now=None):
    """التاريخ الفعلي للبيع: حتى الساعة 2 صباحاً يُعامل البيع كأنه لليوم السابق."""
    now = now or timezone.localtime()
    if now.hour < 2:
        return now.date() - timedelta(days=1)
    return now.date()


def _item_yards(item):
    if item.sale_type == SaleSessionItem.SaleType.ROLL:
        return item.quantity * (item.fabric.yards_per_roll or Decimal("0"))
    return item.quantity


def close_session(session):
    """تحويل بنود الوردية إلى سندات مبيعات يومية مع خصم المخزون، ثم إغلاق الوردية."""
    if session.status == SaleSession.Status.CLOSED:
        raise ValueError("الوردية مغلقة بالفعل")
    rows = list(session.items.select_related("fabric"))

    with transaction.atomic():
        groups = defaultdict(list)
        for r in rows:
            groups[r.sale_date].append(r)

        for sale_date, group in groups.items():
            sale = DailySale.objects.filter(branch=session.branch, date=sale_date).first()
            totals = {m: Decimal("0") for m in SaleSessionItem.PaymentMethod.values}
            item_rows = []
            for r in group:
                totals[r.payment_method] += r.total
                item_rows.append((r.fabric_id, _item_yards(r)))
            total_all = sum(totals.values(), Decimal("0"))

            if sale is None:
                sale = DailySale.objects.create(
                    branch=session.branch,
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
                allow_negative = AppSettings.load().allow_negative_stock
                sell_from_branch(session.branch, sale, item_rows, allow_negative=allow_negative)

        session.status = SaleSession.Status.CLOSED
        session.closed_at = timezone.now()
        session.save(update_fields=["status", "closed_at"])
    return session


def _subtract_item(sale, item):
    payment_field = f"{item.payment_method}_amount"
    sale.total_sales -= item.total
    setattr(sale, payment_field, getattr(sale, payment_field) - item.total)
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
    sale.total_sales += item.total
    setattr(sale, payment_field, getattr(sale, payment_field) + item.total)
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


@transaction.atomic
def delete_session_item(session, item):
    allow_negative = AppSettings.load().allow_negative_stock
    if session.status == SaleSession.Status.CLOSED:
        sale = DailySale.objects.filter(branch=session.branch, date=item.sale_date).first()
        if sale:
            _subtract_item(sale, item)
            _cleanup_sale(sale, allow_negative)
    item.delete()


@transaction.atomic
def update_session_item(session, item, attrs):
    allow_negative = AppSettings.load().allow_negative_stock
    closed = session.status == SaleSession.Status.CLOSED
    if closed:
        current_sale = DailySale.objects.filter(branch=session.branch, date=item.sale_date).first()
        if current_sale:
            _subtract_item(current_sale, item)
    for field in ("fabric", "sale_type", "quantity", "unit_price", "payment_method"):
        if field in attrs:
            setattr(item, field, attrs[field])
    item.total = attrs.get("total", item.total)
    item.save()
    if closed:
        target_sale = DailySale.objects.filter(branch=session.branch, date=item.sale_date).first()
        if target_sale is None:
            target_sale = DailySale.objects.create(
                branch=session.branch,
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
    return item