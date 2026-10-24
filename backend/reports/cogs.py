from collections import defaultdict
from decimal import Decimal

from sales.models import DailySaleItem
from suppliers.models import Fabric
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


def fabric_purchase_prices(fabric_ids=None):
    """سعر الشراء الحالي للياردة لكل قماش، كما هو مسجل في بطاقة القماش."""
    fabrics = Fabric.objects.all()
    if fabric_ids is not None:
        requested_ids = set(fabric_ids)
        if not requested_ids:
            return {}
        fabrics = fabrics.filter(id__in=requested_ids)
    return {
        fabric_id: purchase_price or Decimal("0")
        for fabric_id, purchase_price in fabrics.values_list("id", "purchase_price")
    }


def fabric_average_costs(fabric_ids=None):
    """متوسط تكلفة الياردة لكل قماش:
    (قيمة الاستلامات المرحّلة + قيمة الأرصدة الافتتاحية) ÷ مجموع الياردات.

    تنبيه أداء: هذا يمسح كل أصناف الاستلام والأرصدة الافتتاحية في بايثون،
    فهو غالٍ. من يحتاج أكثر من استدعاء في الطلب نفسه (مثل تقرير الربح والخسارة)
    عليه حسابه مرة واحدة وتمريره عبر ``costs=`` في بقية دوال هذا الملف.

    تكلفة القماش المسجلة في ملفه هي قيمة احتياطية عندما لا توجد تكلفة تاريخية،
    أو عندما أُدخل الرصيد الافتتاحي دون تكلفة (صفر).
    """
    requested_ids = set(fabric_ids) if fabric_ids is not None else None
    if requested_ids is not None and not requested_ids:
        return {}

    buckets = defaultdict(lambda: [Decimal("0"), Decimal("0")])
    receipts = GoodsReceiptItem.objects.filter(receipt__status="posted")
    openings = StockOpeningItem.objects.select_related("fabric")
    if requested_ids is not None:
        receipts = receipts.filter(fabric_id__in=requested_ids)
        openings = openings.filter(fabric_id__in=requested_ids)
    for item in receipts:
        buckets[item.fabric_id][0] += item.total
        buckets[item.fabric_id][1] += item.yards
    for item in openings:
        unit_cost = item.unit_price or Decimal("0")
        if unit_cost <= 0:
            unit_cost = item.fabric.purchase_price or Decimal("0")
        buckets[item.fabric_id][0] += unit_cost * item.yards
        buckets[item.fabric_id][1] += item.yards

    costs = {
        fid: value / yards
        for fid, (value, yards) in buckets.items()
        if yards > 0
    }
    fabrics = Fabric.objects.all()
    if requested_ids is not None:
        fabrics = fabrics.filter(id__in=requested_ids)
    for fabric_id, purchase_price in fabrics.values_list("id", "purchase_price"):
        if costs.get(fabric_id, Decimal("0")) <= 0 and purchase_price and purchase_price > 0:
            costs[fabric_id] = purchase_price
    return costs


def cogs_by_fabric(date_from, date_to, branch_id=None, costs=None):
    """تكلفة البضاعة المباعة لكل قماش في الفترة.

    costs: خريطة متوسطات جاهزة من ``fabric_average_costs`` لتفادي إعادة الحساب.
    """
    sold = sold_by_fabric(date_from, date_to, branch_id)
    if not sold:
        return {}
    if costs is None:
        costs = fabric_average_costs()
    return {fid: (costs.get(fid) or Decimal("0")) * yards for fid, yards in sold.items()}


def cogs_by_day_branch(date_from, date_to, branch_ids=None, costs=None):
    """{(يوم, معرّف الفرع): تكلفة البضاعة المباعة} في الفترة.

    استعلام واحد لكل الفترة مع خريطة تكلفة واحدة، فيصير أرخص بكثير من
    استدعاء ``cogs_by_fabric`` لكل يوم/فرع على حدة.

    branch_ids: قائمة معرّفات فروع للتقييد، أو None يعني كل الفروع،
    وقائمة فارغة تعني لا فروع.
    costs: خريطة متوسطات جاهزة من ``fabric_average_costs`` لتفادي إعادة الحساب.
    """
    qs = DailySaleItem.objects.filter(
        sale__date__gte=date_from, sale__date__lte=date_to
    )
    if branch_ids is not None:
        if not branch_ids:
            return {}
        qs = qs.filter(sale__branch_id__in=branch_ids)
    sold = defaultdict(lambda: Decimal("0"))
    for day, branch_id, fid, yards in qs.values_list(
        "sale__date", "sale__branch_id", "fabric_id", "yards"
    ):
        sold[(day, branch_id, fid)] += yards
    if not sold:
        return {}
    if costs is None:
        costs = fabric_average_costs({fid for (_, _, fid) in sold})
    out = defaultdict(lambda: Decimal("0"))
    for (day, branch_id, fid), yards in sold.items():
        out[(day, branch_id)] += (costs.get(fid) or Decimal("0")) * yards
    return dict(out)
