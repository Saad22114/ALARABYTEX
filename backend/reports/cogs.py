from collections import defaultdict
from decimal import Decimal

from sales.models import DailySaleItem
from warehouses.models import GoodsReceiptItem, StockOpeningItem


def sold_by_fabric(date_from, date_to, branch_id=None):
    qs = DailySaleItem.objects.filter(
        sale__date__gte=date_from, sale__date__lte=date_to
    )
    if branch_id:
        qs = qs.filter(sale__branch_id=branch_id)
    sold = defaultdict(lambda: Decimal("0"))
    for fid, yards in qs.values_list("fabric_id", "yards"):
        sold[fid] += yards
    return dict(sold)


def fabric_average_costs(fabric_ids=None):
    """متوسط تكلفة الياردة لكل قماش:
    (قيمة الاستلامات المرحّلة + قيمة الأرصدة الافتتاحية) ÷ مجموع الياردات."""
    buckets = defaultdict(lambda: [Decimal("0"), Decimal("0")])
    receipts = GoodsReceiptItem.objects.filter(receipt__status="posted")
    openings = StockOpeningItem.objects.all()
    if fabric_ids:
        receipts = receipts.filter(fabric_id__in=fabric_ids)
        openings = openings.filter(fabric_id__in=fabric_ids)
    for item in receipts:
        buckets[item.fabric_id][0] += item.total
        buckets[item.fabric_id][1] += item.yards
    for item in openings:
        buckets[item.fabric_id][0] += (item.unit_price or 0) * item.yards
        buckets[item.fabric_id][1] += item.yards
    return {fid: value / yards for fid, (value, yards) in buckets.items() if yards > 0}


def cogs_by_fabric(date_from, date_to, branch_id=None):
    """تكلفة البضاعة المباعة لكل قماش في الفترة."""
    sold = sold_by_fabric(date_from, date_to, branch_id)
    if not sold:
        return {}
    costs = fabric_average_costs()
    return {fid: (costs.get(fid) or Decimal("0")) * yards for fid, yards in sold.items()}