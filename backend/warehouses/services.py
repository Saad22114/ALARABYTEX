from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework import serializers

from sales.models import DailySale
from suppliers.models import Fabric

from .models import (
    DocumentSequence,
    FabricRoll,
    GoodsReceipt,
    GoodsReceiptItem,
    StockAdjustment,
    StockCount,
    StockCountItem,
    StockMovement,
    StockOpening,
    StockTransfer,
    StockTransferItem,
    Warehouse,
)


def log_movement(warehouse, fabric, movement_type, quantity, roll=None,
                 reference=None, reference_id=None, reference_no="", date=None, notes="",
                 balance_before=None, balance_after=None):
    """يسجّل حركة مخزون موثقة مع مرجع الوثيقة ورصيد القماش قبل/بعد الحركة."""
    if balance_before is None or balance_after is None:
        after = (
            FabricRoll.objects.filter(
                warehouse=warehouse, fabric=fabric, status=FabricRoll.Status.AVAILABLE
            ).aggregate(total=Sum("remaining_yards"))["total"] or Decimal("0")
        )
        balance_after = after
        balance_before = after - quantity
    return StockMovement.objects.create(
        warehouse=warehouse,
        fabric=fabric,
        roll=roll,
        movement_type=movement_type,
        quantity=quantity,
        balance_before=balance_before,
        balance_after=balance_after,
        reference_type=reference.__name__ if reference else "",
        reference_id=reference_id,
        reference_no=reference_no,
        date=date or timezone.localdate(),
        notes=notes,
    )


def add_rolls(warehouse, fabric, yards, unit_cost=Decimal("0"),
              movement_type=StockMovement.Type.RECEIPT, reference=None,
              reference_id=None, reference_no="", date=None, notes="",
              rolls_count=1):
    """ينشئ لفات ويوزّع الياردات بالتساوي مع تسجيل حركة لكل لفة."""
    if yards <= 0:
        raise serializers.ValidationError("الكمية يجب أن تكون أكبر من صفر")
    if rolls_count < 1:
        raise serializers.ValidationError("عدد اللفات يجب أن يكون 1 على الأقل")
    per_roll = yards / Decimal(str(rolls_count))
    created = []
    for i in range(rolls_count):
        y = (per_roll if i < rolls_count - 1 else yards - per_roll * (rolls_count - 1)).quantize(Decimal("0.01"))
        roll = FabricRoll.objects.create(
            warehouse=warehouse, fabric=fabric, yards=y, remaining_yards=y,
            unit_cost=unit_cost, received_date=date, notes=notes,
        )
        created.append(roll)
        log_movement(warehouse, fabric, movement_type, y, roll=roll,
                     reference=reference, reference_id=reference_id,
                     reference_no=reference_no, date=date, notes=notes)
    return created


def consume_rolls(warehouse, fabric, yards, movement_type,
                  reference=None, reference_id=None, reference_no="", date=None, notes="",
                  allow_negative=False):
    """يخصم كمية من المخزن بأسلوب FIFO ويسجّل حركة لكل لفة.

    عند تفعيل allow_negative يتم السماح بخصم يتجاوز الرصيد المتاح ويُسجّل
    المبلغ الناقص كرصيد سالب في السجل المحاسبي.
    """
    if yards <= 0:
        raise serializers.ValidationError("الكمية يجب أن تكون أكبر من صفر")
    rolls = list(
        FabricRoll.objects.select_for_update()
        .filter(warehouse=warehouse, fabric=fabric, status=FabricRoll.Status.AVAILABLE, remaining_yards__gt=0)
        .order_by("created_at", "id")
    )
    available = sum(r.remaining_yards for r in rolls)
    if available < yards and not allow_negative:
        raise serializers.ValidationError(
            f"رصيد المخزن لا يكفي لقماش «{fabric.name}»: المتوفر {available} ياردة والمطلوب {yards}"
        )
    remaining = yards
    for roll in rolls:
        if remaining <= 0:
            break
        take = min(roll.remaining_yards, remaining)
        remaining -= take
        roll.remaining_yards -= take
        if roll.remaining_yards <= 0:
            roll.status = FabricRoll.Status.CONSUMED
            roll.remaining_yards = Decimal("0")
        roll.save(update_fields=["remaining_yards", "status"])
        log_movement(warehouse, fabric, movement_type, -take, roll=roll,
                     reference=reference, reference_id=reference_id,
                     reference_no=reference_no, date=date, notes=notes)
    if remaining > 0:
        if not allow_negative:
            raise serializers.ValidationError(
                f"رصيد المخزن لا يكفي لقماش «{fabric.name}»: المتبقي المطلوب {remaining} ياردة"
            )
        after = available - yards
        log_movement(warehouse, fabric, movement_type, -remaining, roll=None,
                     reference=reference, reference_id=reference_id,
                     reference_no=reference_no, date=date,
                     notes=f"{notes} (بيع برصيد سالب اللحظة)".rstrip(" ") if notes else "رصيد سالب",
                     balance_before=after + remaining, balance_after=after)
    return yards


def move_to_warehouse(source, dest, fabric, yards, transfer, source_rolls=None):
    """يخصم من المصدر بأسلوب FIFO ويضيف اللفات الناتجة للمخزن الهدف."""
    rolls = source_rolls or list(
        FabricRoll.objects.select_for_update()
        .filter(warehouse=source, fabric=fabric, status=FabricRoll.Status.AVAILABLE, remaining_yards__gt=0)
        .order_by("created_at", "id")
    )
    available = sum(r.remaining_yards for r in rolls)
    if available < yards:
        raise serializers.ValidationError(
            f"رصيد المخزن لا يكفي لقماش «{fabric.name}»: المتوفر {available} ياردة والمطلوب {yards}"
        )
    remaining = yards
    for roll in rolls:
        if remaining <= 0:
            break
        if roll.remaining_yards >= remaining:
            take = remaining
            remaining = Decimal("0")
            roll.remaining_yards -= take
            if roll.remaining_yards <= 0:
                roll.status = FabricRoll.Status.CONSUMED
                roll.remaining_yards = Decimal("0")
            roll.save(update_fields=["remaining_yards", "status"])
        else:
            take = roll.remaining_yards
            remaining -= take
            roll.status = FabricRoll.Status.CONSUMED
            roll.remaining_yards = Decimal("0")
            roll.save(update_fields=["remaining_yards", "status"])
        note = f"من {roll.code} - {transfer.number}"
        add_rolls(dest, fabric, take, unit_cost=roll.unit_cost,
                  movement_type=StockMovement.Type.TRANSFER_IN,
                  reference=transfer.__class__, reference_id=transfer.pk,
                  reference_no=transfer.number, date=transfer.date, notes=note, rolls_count=1)
        log_movement(source, fabric, StockMovement.Type.TRANSFER_OUT, -take, roll=roll,
                     reference=transfer.__class__, reference_id=transfer.pk,
                     reference_no=transfer.number, date=transfer.date, notes=note)
    return yards


def move_rolls_to_warehouse(source, dest, fabric, rolls_count, transfer):
    """ينقل عدداً محدداً من اللفات كاملة (أقدم اللفات أولاً) مع الحفاظ على كل لفة مستقلة."""
    if rolls_count <= 0:
        raise serializers.ValidationError("عدد اللفات يجب أن يكون 1 على الأقل")
    rolls = list(
        FabricRoll.objects.select_for_update()
        .filter(warehouse=source, fabric=fabric, status=FabricRoll.Status.AVAILABLE, remaining_yards__gt=0)
        .order_by("created_at", "id")
    )
    if len(rolls) < rolls_count:
        raise serializers.ValidationError(
            f"عدد اللفات المتوفر لقماش «{fabric.name}» في المخزن {len(rolls)} لفة والمطلوب {rolls_count}"
        )
    moved = Decimal("0")
    for roll in rolls[:rolls_count]:
        take = roll.remaining_yards
        roll.status = FabricRoll.Status.CONSUMED
        roll.remaining_yards = Decimal("0")
        roll.save(update_fields=["remaining_yards", "status"])
        note = f"من {roll.code} - {transfer.number}"
        add_rolls(dest, fabric, take, unit_cost=roll.unit_cost,
                  movement_type=StockMovement.Type.TRANSFER_IN,
                  reference=transfer.__class__, reference_id=transfer.pk,
                  reference_no=transfer.number, date=transfer.date, notes=note, rolls_count=1)
        log_movement(source, fabric, StockMovement.Type.TRANSFER_OUT, -take, roll=roll,
                     reference=transfer.__class__, reference_id=transfer.pk,
                     reference_no=transfer.number, date=transfer.date, notes=note)
        moved += take
    return moved


def resolve_receipt_destination(receipt: GoodsReceipt):
    """يرجع مخزن وجهة الاستلام: المخزن مباشرة أو مخزِن الفرع (مع إنشائه تلقائياً)."""
    if receipt.warehouse_id:
        return receipt.warehouse
    if receipt.branch_id:
        return Warehouse.for_branch(receipt.branch)
    raise serializers.ValidationError("حدد وجهة الاستلام: مخزن أو فرع")


def post_receipt(receipt: GoodsReceipt):
    """يُنشئ اللفات في وجهة الاستلام (مخزن أو فرع) ثم يُرحّل سند الاستلام."""
    if receipt.status == GoodsReceipt.Status.POSTED:
        raise serializers.ValidationError("سند الاستلام مُرحّل مسبقاً")
    with transaction.atomic():
        if not receipt.items.exists():
            raise serializers.ValidationError("سند الاستلام فارغ — أضف أصنافاً أولاً")
        destination = resolve_receipt_destination(receipt)
        for item in receipt.items.select_related("fabric"):
            if item.yards <= 0:
                raise serializers.ValidationError(f"ياردات قماش «{item.fabric.name}» يجب أن تكون أكبر من صفر")
            item.total = (item.yards * item.unit_price).quantize(Decimal("0.01"))
            item.save(update_fields=["total"])
            add_rolls(
                warehouse=destination, fabric=item.fabric, yards=item.yards,
                unit_cost=item.unit_price, movement_type=StockMovement.Type.RECEIPT,
                reference=GoodsReceipt, reference_id=receipt.pk,
                reference_no=receipt.number, date=receipt.date,
                rolls_count=item.rolls_count,
            )
        receipt.status = GoodsReceipt.Status.POSTED
        receipt.save(update_fields=["status"])
    return receipt


def create_receipt_from_purchase(entry, warehouse=None, branch=None, date=None):
    """يُنشئ ويُرحّل سند استلام تلقائياً لأصناف قيد الشراء في الوجهة المحددة."""
    items = entry.items.select_related("fabric").filter(quantity_yards__gt=0)
    if not items.exists():
        return None
    with transaction.atomic():
        receipt = GoodsReceipt.objects.create(
            number=DocumentSequence.next_number("GR"),
            warehouse=warehouse,
            branch=branch,
            purchase_entry=entry,
            supplier=entry.supplier,
            date=date or (entry.date or timezone.localdate()),
            supplier_receipt_no=entry.receipt_no,
            notes=f"توريد بضاعة قيد الشراء {entry.receipt_no or ''}",
        )
        for it in items:
            rolls = int(it.rolls or 1)
            if rolls < 1:
                rolls = 1
            GoodsReceiptItem.objects.create(
                receipt=receipt, fabric=it.fabric, rolls_count=rolls,
                yards=it.quantity_yards, unit_price=it.unit_price,
                total=(it.quantity_yards * it.unit_price).quantize(Decimal("0.01")),
            )
        if not receipt.items.exists():
            raise serializers.ValidationError("لا توجد أصناف شراء قابلة للتوريد")
        post_receipt(receipt)
    return receipt


def resolve_transfer_destination(transfer):
    """يرجع مخزن الوجهة: إما المخزن المُستقبِل أو مُخزِن الفرع (مع إنشائه تلقائياً)."""
    if transfer.to_warehouse_id:
        return transfer.to_warehouse
    if transfer.to_branch_id:
        return Warehouse.for_branch(transfer.to_branch)
    raise serializers.ValidationError("حدد وجهة التحويل: مخزن أو فرع")


def complete_transfer(transfer):
    """ينفّذ التحويل: خصم من المُرسِل (FIFO حسب الياردات أو اللفات) وإضافة للوجهة."""
    if transfer.from_warehouse_id == transfer.to_warehouse_id:
        raise serializers.ValidationError("لا يمكن التحويل إلى نفس المخزن")
    if transfer.status == StockTransfer.Status.COMPLETED:
        raise serializers.ValidationError("التحويل منفّذ مسبقاً")
    if not transfer.items.exists():
        raise serializers.ValidationError("سند التحويل فارغ — أضف أصنافاً أولاً")
    with transaction.atomic():
        destination = resolve_transfer_destination(transfer)
        transfer_items = list(transfer.items.select_related("fabric"))
        for item in transfer_items:
            if item.quantity_mode == StockTransferItem.QuantityMode.ROLL:
                moved = move_rolls_to_warehouse(
                    transfer.from_warehouse, destination, item.fabric, item.rolls_count, transfer
                )
                if item.yards != moved:
                    item.yards = moved
                    item.save(update_fields=["yards"])
            else:
                move_to_warehouse(transfer.from_warehouse, destination, item.fabric, item.yards, transfer)
        transfer.status = StockTransfer.Status.COMPLETED
        transfer.completed_at = timezone.now()
        transfer.save(update_fields=["status", "completed_at"])
    return transfer


def apply_adjustment(adjustment: StockAdjustment):
    """يطبّق تسوية مخزون (إضافة أو خصم) مع تسجيل الحركات."""
    if adjustment.items.filter(yards__lte=0).exists():
        raise serializers.ValidationError("الكميات يجب أن تكون أكبر من صفر")
    if not adjustment.items.exists():
        raise serializers.ValidationError("سند التسوية فارغ — أضف أصنافاً أولاً")
    with transaction.atomic():
        movement_type = (
            StockMovement.Type.ADJUSTMENT_IN
            if adjustment.direction == StockAdjustment.Direction.IN
            else StockMovement.Type.ADJUSTMENT_OUT
        )
        references = []
        for item in adjustment.items.select_related("fabric"):
            references.append(item)
        for item in references:
            if adjustment.direction == StockAdjustment.Direction.IN:
                add_rolls(
                    adjustment.warehouse, item.fabric, item.yards,
                    movement_type=movement_type, reference=StockAdjustment,
                    reference_id=adjustment.pk, reference_no=adjustment.number,
                    date=adjustment.date, notes=adjustment.get_reason_display(),
                    rolls_count=item.rolls_count or 1,
                )
            else:
                consume_rolls(
                    adjustment.warehouse, item.fabric, item.yards, movement_type,
                    reference=StockAdjustment, reference_id=adjustment.pk,
                    reference_no=adjustment.number, date=adjustment.date,
                    notes=adjustment.get_reason_display(),
                )
    return adjustment


def build_count_snapshot(count: StockCount):
    """يرصد الأرصدة الدفترية لكل قماش بفروع الجلسة قبل الجرد."""
    if count.status in (StockCount.Status.POSTED, StockCount.Status.CANCELLED):
        raise serializers.ValidationError("لا يمكن تعديل جلسة منشورة أو ملغاة")
    rows = (
        FabricRoll.objects.filter(warehouse=count.warehouse, status=FabricRoll.Status.AVAILABLE)
        .values("fabric_id")
        .annotate(total=Sum("remaining_yards"))
    )
    with transaction.atomic():
        count.items.all().delete()
        StockCountItem.objects.bulk_create(
            StockCountItem(count=count, fabric_id=row["fabric_id"], system_yards=row["total"])
            for row in rows
        )
    return count


def post_count(count: StockCount):
    """ينشر الجرد: يعالج فروق الجرد كحركات موثقة."""
    if count.status == StockCount.Status.POSTED:
        raise serializers.ValidationError("الجلسة منشورة مسبقاً")
    if not count.items.exists():
        raise serializers.ValidationError("جلسة الجرد فارغة")
    with transaction.atomic():
        item_list = list(count.items.select_related("fabric"))
        for item in item_list:
            if item.counted_yards is None:
                raise serializers.ValidationError(
                    f"أدخل الرصيد الفعلي لجميع الأصناف قبل النشر (قماش «{item.fabric.name}»)"
                )
            diff = item.counted_yards - item.system_yards
            if abs(diff) < Decimal("0.005"):
                continue
            if diff > 0:
                add_rolls(
                    count.warehouse, item.fabric, diff, movement_type=StockMovement.Type.COUNT,
                    reference=StockCount, reference_id=count.pk, reference_no=count.number,
                    date=count.date, notes="فارق جرد (زيادة)", rolls_count=1,
                )
            else:
                consume_rolls(
                    count.warehouse, item.fabric, -diff, StockMovement.Type.COUNT,
                    reference=StockCount, reference_id=count.pk,
                    reference_no=count.number, date=count.date, notes="فارق جرد (نقص)",
                )
        count.status = StockCount.Status.POSTED
        count.save(update_fields=["status"])
    return count


def post_opening(opening):
    """يسجّل الرصيد الافتتاحي للأقمشة في المخزن (مرة واحدة لكل قماش)."""
    if not opening.items.exists():
        raise serializers.ValidationError("سند الرصيد الافتتاحي فارغ — أضف أصنافاً أولاً")
    if opening.items.filter(yards__lte=0).exists():
        raise serializers.ValidationError("الكميات يجب أن تكون أكبر من صفر")
    with transaction.atomic():
        opened = set(
            StockMovement.objects.filter(
                warehouse=opening.warehouse, movement_type=StockMovement.Type.OPENING
            ).values_list("fabric_id", flat=True)
        )
        duplicates = [f"«{it.fabric.name}»" for it in opening.items.select_related("fabric") if it.fabric_id in opened]
        if duplicates:
            raise serializers.ValidationError(
                f"الرصيد الافتتاحي للقماش {(' و '.join(duplicates))} مسجّل مسبقاً في هذا المخزن"
            )
        for item in opening.items.select_related("fabric"):
            add_rolls(
                opening.warehouse, item.fabric, item.yards, unit_cost=item.unit_price,
                movement_type=StockMovement.Type.OPENING,
                reference=StockOpening, reference_id=opening.pk,
                reference_no=opening.number, date=opening.date,
                rolls_count=item.rolls_count or 1,
            )
    return opening


def reverse_sale_consumption(sale):
    """يعكس خصم المخزون الذي تم لبيع: يعيد الياردات للفات ويمحو حركات البيع المسجلة."""
    movements = list(
        StockMovement.objects.filter(
            movement_type=StockMovement.Type.SALE,
            reference_type="DailySale",
            reference_id=sale.pk,
        ).select_related("roll")
    )
    roll_ids = {m.roll_id for m in movements if m.roll_id}
    rolls = {r.pk: r for r in FabricRoll.objects.filter(pk__in=roll_ids)}
    for m in movements:
        if m.roll_id:
            roll = rolls[m.roll_id]
            roll.remaining_yards = roll.remaining_yards + abs(m.quantity)
            if roll.remaining_yards > 0 and roll.status == FabricRoll.Status.CONSUMED:
                roll.status = FabricRoll.Status.AVAILABLE
            roll.save(update_fields=["remaining_yards", "status"])
    StockMovement.objects.filter(
        movement_type=StockMovement.Type.SALE,
        reference_type="DailySale",
        reference_id=sale.pk,
    ).delete()


def sell_from_branch(branch, sale, items, allow_negative=False):
    """يخصم أصناف المبيعات من مخزون الفرع بأسلوب FIFO ويسجّل حركات مبيعات."""
    if not items:
        return
    with transaction.atomic():
        warehouse = Warehouse.for_branch(branch)
        for fabric, item_yards in items:
            if isinstance(fabric, int):
                fabric = Fabric.objects.get(pk=fabric)
            consume_rolls(
                warehouse, fabric, item_yards, StockMovement.Type.SALE,
                reference=DailySale, reference_id=sale.pk,
                reference_no=f"DS-{sale.pk:05d}", date=sale.date,
                notes=f"مبيعات فرع «{branch.name}»", allow_negative=allow_negative,
            )