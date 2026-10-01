from decimal import Decimal

from django.db import transaction
from django.db.models import (
    Count,
    DecimalField,
    ExpressionWrapper,
    F,
    Q,
    Sum,
)
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import serializers

from sales.models import DailySale
from branches.models import Branch
from reports.cogs import fabric_average_costs
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
    # نقرّب نصّ اللفة مرّة واحدة ثم نعطي فائض التقريب لآخر لفة، وإلا ضاع نصف
    # قرش لكل لفة: 133.41 ياردة على لفتين كانتا تُسجَّلان 66.70 + 66.70 = 133.40
    # فينقص الاستلام عن السند، ويصير رصيد المخزن أقل من المستلم بدل أن يساويه.
    per_roll = (yards / Decimal(str(rolls_count))).quantize(Decimal("0.01"))
    created = []
    for i in range(rolls_count):
        y = per_roll if i < rolls_count - 1 else yards - per_roll * (rolls_count - 1)
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


def _create_receipt_for_destination(entry, wh_id, br_id, items, date=None):
    warehouse = Warehouse.objects.filter(pk=wh_id).first() if wh_id else None
    branch = Branch.objects.filter(pk=br_id).first() if br_id else None
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


def create_purchase_receipts(entry, date=None):
    """يُنشئ ويُرحّل سندات استلام حسب وجهة كل بند (مخزن/فرع اختيارياً لكل بند).

    البنود بدون وجهة تُستكمل إلى وجهة القيد إن وُجدت، وإلا لا تُورَّد.
    يُنشأ سند استلام مستقل لكل وجهة (عند توزيع البنود على أكثر من مخزن/فرع).
    """
    items = entry.items.select_related("fabric").filter(quantity_yards__gt=0)
    if not items.exists():
        return None
    fallback_wh = entry.warehouse_id
    fallback_br = entry.branch_id
    groups = {}
    for it in items:
        wh_id = it.warehouse_id or fallback_wh
        br_id = it.branch_id or fallback_br
        if wh_id is None and br_id is None:
            continue
        groups.setdefault((wh_id, br_id), []).append(it)
    if not groups:
        return None
    receipts = []
    with transaction.atomic():
        for (wh_id, br_id), group in groups.items():
            receipts.append(_create_receipt_for_destination(entry, wh_id, br_id, group, date=date))
    return receipts if len(receipts) > 1 else (receipts[0] if receipts else None)


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


#: أدنى فرقٍ يُحرّك حركة مخزون. تحته فرقُ قصّ وطحنٍ لا معنى لإثقال السجل
#: بحركاتٍ قيمتها صفر — لكنه يجب أن يكون رقماً واحداً معروفاً: العرض والنشر
#: يتّفقان عليه، وإلا عرض النظام سطراً «عليه فرق» ثم لم يتحرّك للمخزون
#: ياردةً واحدة عند النشر.
VARIANCE_EPSILON = Decimal("0.005")

def count_variance_expression():
    """تعبير SQL للفرق بين الرصيدين، للتصفية والتجميع معاً.

    ``counted_yards`` قد يكون ``NULL`` (صنفٌ لم يُعدّ)، وطرح ``NULL`` في SQL
    يُبتلع الصفّ كلّه فيحسبه غيرَ مرصود. فنستبدله بالرصيد الدفتري، فيصير
    الفرق صفراً — أي «لم يُعدّ بعد» لا «مطابق».
    """
    return ExpressionWrapper(
        Coalesce(F("counted_yards"), F("system_yards")) - F("system_yards"),
        output_field=DecimalField(max_digits=14, decimal_places=2),
    )


def count_summary(count, costs=None):
    """ملخّص الجلسة: كم رُصد، وكم بقي، وكم فروق، وبكم ياردة وبكم قيمة.

    ليس زينة: هذه الأرقام هي ما يقرّر مدير المخزن «هل انتهى الجرد» ومتى
    يُنشر. وتُحسب في استعلامٍ واحدٍ على قاعدة البيانات لا بعدّ الصفوف في
    بايثون، وتُقاس قيمة الفرق بخريطة التكلفة نفسها التي يستعملها
    ``post_count`` — فلو اختلفت لأظهر التقرير فرقاً غير ما في الشاشة.

    صنفٌ رُصد ولم يكن له رصيد دفتري — أي وُجد على الرفّ ولم يُسجّل — فرقُه
    قيمةٌ كاملة، ويُحسب هنا كغيره.
    """
    # الفرق يُحسب مرّةً واحدة كـ«تسمية» على الاستعلام، ثم يُجمَّع ويُصفّى
    # بتسمية لا بتعبير. خلطُ ``Sum(تعبير)`` مع ``Sum(عمود)`` في aggregate
    # واحد يربك Django: الاسم يُسجَّل كتعليق قبل أن يُحلّ، فيحسب العمود
    # تعليقاً على تعليق ويرفض الاستعلام كلّه.
    annotated = count.items.all().annotate(variance=count_variance_expression())
    stats = annotated.aggregate(
        items=Count("id"),
        counted=Count("counted_yards"),
        net=Sum("variance"),
    )
    # الصنف غيرُ المرصود فرقُه صفرٌ بالقيمة لا بالرصيد: هو «لم يُعدّ»، لا
    # «مطابق». وتصفيةُ الفروق على الصفر تطويباً تعبر المرصود فقط.
    discrepant = annotated.filter(
        Q(variance__gte=VARIANCE_EPSILON) | Q(variance__lte=-VARIANCE_EPSILON)
    )
    rows = list(discrepant.values_list("fabric_id", "variance"))
    if costs is None:
        costs = fabric_average_costs({fid for fid, _ in rows}) if rows else {}
    # فرقُ ياردتين بلا سعرٍ لا يُراجَع ولا يُسجَّل، فقيمة الفرق محلّها.
    value = sum(
        (Decimal(str(amount)) * (costs.get(fid) or Decimal("0")))
        for fid, amount in rows
    )
    total_items = stats["items"] or 0
    counted_items = stats["counted"] or 0
    return {
        "items": total_items,
        "counted": counted_items,
        "pending": total_items - counted_items,
        "variances": len(rows),
        "net_yards": float(stats["net"] or Decimal("0")),
        "value": float(value),
        "complete": total_items > 0 and counted_items == total_items,
    }


def public_summary(count):
    """الملخّص كما تُراه الشاشة، لا كما يُحسَب في الخدمة.

    الجرد المغلق يخفي الرصيد الدفتري سطراً سطراً، فلا يجوز أن يفصح عنه
    ملخّصٌ يجمعه: «فروقٌ في صنفين بـ‎-5‎ ياردة» هو الرصيدُ الدفتري
    نفسُه، مُجموعاً ومُقرَّباً. فالتقدّم (كم رُصد وكم بقي) يبقى ظاهراً —
    هو ما يحتاجه العدّاد ليرفع رأسه — أمّا الفروقُ فيُصفَّر حتى النشر.
    """
    summary = count_summary(count)
    if count.hides_system_balance:
        summary.update(variances=0, net_yards=0.0, value=0.0)
    return summary


def add_count_line(count, fabric):
    """يضيف قماشاً إلى الجلسة حتى لو لم يكن له رصيد دفتري.

    الجرد الفعلي يجد أقمشةً على الرفّ لا في الدفتر — وهذا أجمل ما يكتشفه
    الجرد وأخطره. فحصرُ الأصناف فيما رصيده موجب يجعل اكتشاف «قماش بلا
    دفتر» مستحيلاً بنيوياً، ويلغي أهمّ سببٍ لإتمام الجرد.
    """
    if count.status != StockCount.Status.OPEN:
        raise serializers.ValidationError("لا يمكن تعديل جلسة منشورة أو ملغاة")
    if count.items.filter(fabric=fabric).exists():
        raise serializers.ValidationError("القماش مرصود في هذه الجلسة مسبقاً")
    # رصيد الدفتر لهذا القماش في هذا المخزن لحظة الجرد، لا صفراً كسولاً:
    # القماش الذي أُدخل بلا رصيدٍ مُقاس يُعامل كرصيده الفعلي الجديد.
    system = (
        FabricRoll.objects.filter(
            warehouse=count.warehouse,
            fabric=fabric,
            status=FabricRoll.Status.AVAILABLE,
        ).aggregate(total=Sum("remaining_yards"))["total"]
        or Decimal("0")
    )
    return StockCountItem.objects.create(
        count=count, fabric=fabric, system_yards=system,
    )


def remove_count_line(count, item):
    """يحذف سطراً أُدخل بالخطأ — ما دامت الجلسة مفتوحة.

    ما بعد النشر ليس خطأً يُصحَّح بحذف سطر: هو فارق جردٍ موثَّق، وصحّتُه
    بتعديل حركة، لا بإخفاء سطرٍ كان قد وُثِق.
    """
    if count.status != StockCount.Status.OPEN:
        raise serializers.ValidationError("لا يمكن تعديل جلسة منشورة أو ملغاة")
    if item.count_id != count.pk:
        raise serializers.ValidationError("الصنف لا ينتمي إلى هذه الجلسة")
    item.delete()


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
    pending = count.items.filter(counted_yards__isnull=True).count()
    if pending:
        raise serializers.ValidationError(
            f"بقي {pending} صنفاً بلا رصد فعلي — أدخل الرصيد لكل صنف قبل النشر"
        )
    with transaction.atomic():
        item_list = list(count.items.select_related("fabric"))
        for item in item_list:
            diff = item.counted_yards - item.system_yards
            if abs(diff) < VARIANCE_EPSILON:
                continue
            if diff > 0:
                add_rolls(
                    count.warehouse, item.fabric, diff, movement_type=StockMovement.Type.COUNT,
                    reference=StockCount, reference_id=count.pk, reference_no=count.number,
                    date=count.date, notes=_variance_note(item, "زيادة"),
                    rolls_count=1,
                )
            else:
                consume_rolls(
                    count.warehouse, item.fabric, -diff, StockMovement.Type.COUNT,
                    reference=StockCount, reference_id=count.pk,
                    reference_no=count.number, date=count.date,
                    notes=_variance_note(item, "نقص"),
                )
        count.status = StockCount.Status.POSTED
        count.save(update_fields=["status"])
    return count


def _variance_note(item, direction):
    """حركة الجرد تحمل سبب الفرق المكتوب، لا كلمةً عامةً عن كل حركة.

    «فارق جرد (نقص) 12.5 ياردة» لا يقود قراراً. «فارق جرد (نقص) — هالك:
    قصاصة في المخزن» يفعل. فالسبب المُدخَل مع العدّ هو ما يجعل الفرق قابلاً
    للمعالجة بدل أن يكون مجهولاً في سطر حركة.
    """
    reason = (item.note or "").strip()
    base = f"فارق جرد ({direction})"
    return f"{base} — {reason}" if reason else base


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