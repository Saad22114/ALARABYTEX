from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
import logging

from django.db import transaction
from django.utils import timezone

from appsettings.models import AppSettings
from sales.models import DailySale, DailySaleItem
from warehouses.models import FabricRoll, StockMovement, Warehouse
from warehouses.services import consume_rolls

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
    """تاريخ تسجيل أصناف الوردية: يوم فتحها دائماً، لا يوم إغلاقها.

    الوردية تُقاس بيومها وتُقفل عليه: كل بند فيها يقع على اليوم الذي فُتحت فيه، ولو أُضيف
    بندٌ بعد منتصف الليل، ولو بلغ وقتها ما بعد بداية اليوم المحاسبي.

    والعبارة السابقة كانت تُعيد `effective_sale_date` لكل بند على حدة، فتعتتمد على لحظة
    إضافة البند لا على لحظة فتح الوردية. والنتيجة أن وردية فُتحت الساعة العاشرة قد تُقسَّم
    بيومين: بنودُ العاشرة على يومها، وبنودُ الواحدة بعد منتصف الليل على اليوم التالي إذا بلغ
    وقتُ الإضافة ساعة بداية اليوم المحاسبي. وهي فجوة في حساب اليوم لا في العدّاد وحده.
    """
    if session is None:
        return effective_sale_date()
    return session_business_date(session)


def session_business_date(session):
    """تاريخ الوردية الفعلي: التاريخ المختار عند الفتح، أو تاريخ الفتح لورديات قديمة بلا تاريخ صريح."""
    if session is None:
        return timezone.localdate()
    if session.session_date:
        return session.session_date
    if session.opened_at:
        return timezone.localtime(session.opened_at).date()
    return timezone.localdate()


def now_on(target_date, *, floor=None):
    """الوقت الحالي منقولاً إلى اليوم المطلوب بنفس الساعة والدقيقة.

    يُستخدم لتسجيل الوردية بتاريخها المختار: يبقى ترتيب الورديات داخل نفس اليوم
    مطابقاً لتسلسل الإنشاء الحقيقي، وتبقى المدة محسوبة بالدقائق لا بالأيام.
    """
    now = timezone.localtime()
    shifted = datetime.combine(target_date, now.timetz())
    if floor is not None and shifted < floor:
        return floor
    return shifted


def stamp_session_creation(session, target_date, *, stamp=None):
    """نقل وقت الفتح ووقت الإنشاء إلى اليوم المختار.

    الحقول auto_now_add لا تُقبل في create، لذا تُكتب عبر update لتجاوز pre_save.
    """
    stamp = stamp or now_on(target_date)
    SaleSession.objects.filter(pk=session.pk).update(opened_at=stamp, created_at=stamp)
    session.opened_at = stamp
    session.created_at = stamp
    return stamp


def elapsed_minutes(session, now=None):
    """مدة الوردية المفتوحة بالدقائق: الوقت الحالي منقوص من وقت فتحها.

    كان المرجع السابق يأخذ الساعة الحالية على يوم الوردية، حتى لا تظهر المدة بالأيام
    للورديات المؤرخة سابقاً. لكن الوردية المفتوحة من البارح إلى صباح اليوم ليست يوماً
    سابقاً صُدف، بل وردية نسيها صاحبها، فصار عمرها الحقيقي يُقاس على يومها بساعتها
    الحالية: وردية مفتوحة منذ أربع وعشرين ساعة تُعرض بثلاث عشرة دقيقة، والوردية التي
    امتدت فوق منتصف الليل تُعرض صفراً حتى تبلغ منتصف الليل.

    عدّادُ الوردية وظيفته أن يُظهر أنها ما زالت مفتوحة. فإذا قِسناه بساعةٍ من يومٍ آخر
    لتقدّمه صفراً، أخفى بالضبط ما وُجد ليُظهره. والمدة الصحيحة هي الوقت الحالي ناقصَ
    وقت الفتح، بلا نظرٍ إلى تاريخ الوردية.
    """
    if session is None or not session.opened_at:
        return 0
    opened = timezone.localtime(session.opened_at)
    return max(0, int(((now or timezone.localtime()) - opened).total_seconds() // 60))


def business_timezone():
    """نطاق العمل المحلي، ليُثبَّت وقت معلوم على تاريخه وإلا ساعته محلية."""
    return timezone.get_current_timezone()


def auto_close_moment(session, close_time):
    """أوّل موعدٍ لهذا الوقت يقع بعد فتح الوردية.

    الموعد يتكرّر يومياً بعد يوم الفتح: وردية فُتحت بعد موعد الإغلاق فيومها تنتقل إلى
    موعد الغد، فلا تُغلق في يوم فتحها ولا تُترك مفتوحة بلا سبب.
    """
    business = session_business_date(session)
    stamp = datetime.combine(business, close_time, tzinfo=business_timezone())
    if session.opened_at:
        opened = timezone.localtime(session.opened_at)
        if stamp < opened:
            days = int((opened - stamp).total_seconds() // 86400) + 1
            stamp += timedelta(days=days)
    return stamp


AUTO_CLOSE_NOTE = "أُغلقت تلقائياً: بلغ موعد إغلاق الورديات المنسية ولم تُغلق يدوياً"


def auto_close_stale_sessions(now=None):
    """تغلق النظام الورديات المنسية وتُعيد مبيعاتها على يوم فتحها.

    لا يجدول النظام شيئاً في الخلفية، فلم يكن هناك ما يغلق وردية نسيها صاحبها: لم تكن
    تُغلق إلا حين يفتح أحد الصفحة. وأول من يذهب ليرى وردية منسية هو من يغلقها له.

    تُغلق على موعد الإغلاق نفسه لا على لحظة الاكتشاف، حتى لا يتغير يومها المحاسبي بتغير
    ساعة الدخول، ويبقى سبب الإغلاق مكتوباً في ملاحظاتها. الورديات التي أُنشئت
    عمداً بتاريخ محاسبي سابق تُترك للإغلاق اليدوي حتى لا تُغلق عند أول تحديث للقائمة.
    """
    now = now or timezone.localtime()
    conf = AppSettings.load()
    if not conf.session_auto_close_enabled:
        return []
    due = []
    rows = SaleSession.objects.filter(
        status=SaleSession.Status.OPEN, is_manual=False, is_backdated=False
    ).only("id", "opened_at", "session_date", "notes")
    for session in rows:
        if now < auto_close_moment(session, conf.session_auto_close_time):
            continue
        try:
            close_session(session, auto=True)
        except Exception:
            logger.exception(
                "فشل إغلاق الوردية تلقائياً (id=%s)", session.pk
            )
            continue
        due.append(session.pk)
    if due:
        logger.info(
            "أغلق النظام %s وردية منسية تلقائياً: %s", len(due), due
        )
    return due


def _item_yards(item):
    if item.sale_type == SaleSessionItem.SaleType.ROLL:
        return item.quantity * (item.fabric.yards_per_roll or Decimal("0"))
    return item.quantity


def item_pieces(item):
    """
    يحسب القطع المكافئ لبند وردية، بنسق التعريف في كل شاشات المشروع.

    «القطعة» طرد من 3.5 ياردة، فالبند نوعان: الطاقة كميتها قطعة، والياردات
    كميتها ياردة فتُقسم على 3.5، والجمع بلا هذا التمييز كان سيعطي رقماً لا
    يقابله شيء في المخزن: من باع 70 ياردة باطلاقات استحق 20 قطعة، لا 70.

    اختصر التعريف في دالة واحدة لأن لقطعتين في المشروع تذكران «القطع» —
    توزيع المبيعات على الموظفين وتقرير العمولات — ولو اختلفتاه لقابل الموظف
    رقمين مختلفين لنفس البيع.
    """
    from suppliers.serializers import PIECE_YARDS

    if item.sale_type == SaleSessionItem.SaleType.ROLL:
        return item.quantity
    return item.quantity / PIECE_YARDS


def next_sale_group_no(session, sale_group=""):
    """يأخذ رقم البيعة التالي داخل وردية، بدءا من 1 للبيعة الأقدم.

    الرقم محفوظ على بنود البيعة نفسها (`group_no`) فيثبت عند الحفظ، ويقرأ
    من عدّاد الوردية `next_group_no` الذي يزيد فقط ولا ينقص. لذلك حذف
    بيعة — حتى لو كانت الأحدث — يترك فجوة ولا يُعاد استخدام رقمها.

    إن كانت `sale_group` مرفقة ببنود محفوظة في هذه الوردية، يُعاد الرقم
    نفسه، فتتشترك كل بنود الدفعة الواحدة في رقم واحد.
    """
    if sale_group:
        existing = (
            SaleSessionItem.objects.filter(session=session, sale_group=sale_group)
            .exclude(group_no=None)
            .values_list("group_no", flat=True)
            .first()
        )
        if existing is not None:
            return existing
    # يُقفل صف الوردية أثناء القراءة والزيادة، فلا تأخذ دفعةان متزامنتان
    # الرقم نفسه.
    locked = SaleSession.objects.select_for_update().get(pk=session.pk)
    number = locked.next_group_no or 1
    SaleSession.objects.filter(pk=locked.pk).update(next_group_no=number + 1)
    return number


def deduct_item_stock(item):
    """يخصم كمية البند فورياً من مخزن فرع الوردية عند حفظ البيعة."""
    if item is None or item.is_returned:
        return
    warehouse = Warehouse.for_branch(item.session.branch)
    if warehouse is None:
        return
    yards = _item_yards(item)
    if yards <= 0:
        return
    consume_rolls(
        warehouse, item.fabric, yards, StockMovement.Type.SALE,
        reference=SaleSessionItem, reference_id=item.pk,
        reference_no=f"SI-{item.pk:05d}", date=item.sale_date,
        notes=f"بيعة #SI-{item.pk:05d} — {item.session.employee.name}",
    )


def restock_item(item):
    """يعيد كمية البند إلى مخزن الفرع الذي خُصم منه (عند الحذف/الاسترجاع/التعديل/الإفراغ)."""
    movements = list(
        StockMovement.objects.filter(
            movement_type=StockMovement.Type.SALE,
            reference_type="SaleSessionItem",
            reference_id=item.pk,
        ).select_related("roll")
    )
    if not movements:
        return
    roll_ids = {m.roll_id for m in movements if m.roll_id}
    rolls = {r.pk: r for r in FabricRoll.objects.filter(pk__in=roll_ids)}
    for m in movements:
        if m.roll_id and m.roll_id in rolls:
            roll = rolls[m.roll_id]
            roll.remaining_yards = roll.remaining_yards + abs(m.quantity)
            if roll.remaining_yards > 0 and roll.status == FabricRoll.Status.CONSUMED:
                roll.status = FabricRoll.Status.AVAILABLE
            roll.save(update_fields=["remaining_yards", "status"])
    StockMovement.objects.filter(
        movement_type=StockMovement.Type.SALE,
        reference_type="SaleSessionItem",
        reference_id=item.pk,
    ).delete()


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
    sale = DailySale.objects.filter(branch=session.branch, date=session.manual_date).first()
    if sale is None:
        return
    sale.total_sales -= _manual_total(session)
    sale.cash_amount -= session.manual_cash or Decimal("0")
    sale.transfer_amount -= session.manual_transfer or Decimal("0")
    sale.card_amount -= session.manual_card or Decimal("0")
    sale.save(update_fields=["total_sales", "cash_amount", "transfer_amount", "card_amount"])
    if sale.total_sales <= 0 and sale.payment_total <= 0:
        sale.delete()


@transaction.atomic
def create_manual_session(*, employee, branch, sale_date, cash, transfer, card, notes=""):
    """إنشاء وردية مغلقة كاملة كمجموع مالي بدون بنود ولا خصم مخزون."""
    total = cash + transfer + card
    stamp = now_on(sale_date)
    session = SaleSession.objects.create(
        employee=employee,
        branch=branch,
        status=SaleSession.Status.CLOSED,
        closed_at=stamp,
        is_manual=True,
        manual_date=sale_date,
        manual_cash=cash,
        manual_transfer=transfer,
        manual_card=card,
        notes=notes,
    )
    stamp_session_creation(session, sale_date, stamp=stamp)
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


def close_session(session, *, auto=False):
    """تحويل بنود الوردية إلى سندات مبيعات يومية مع خصم المخزون، ثم إغلاق الوردية.

    وكلاهما يُبقي مبيعات الوردية على يوم فتحها؛ والفرق في وقت الإغلاق نفسه: الإغلاق
    اليدوي يُختم بساعة اللحظة على يوم الوردية، والإغلاق التلقائي بموعد الإغلاق المضبوط
    بعده — فترتفع ساعة الوردية الليلية إلى صباح الغد بدل أن تُقطع عند منتصف الليل.
    """
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

        session.status = SaleSession.Status.CLOSED
        if auto:
            stamp = auto_close_moment(session, AppSettings.load().session_auto_close_time)
            note = AUTO_CLOSE_NOTE
        else:
            # وقت الإغلاق اليدوي يُسجَّل على تاريخ الوردية بنفس الساعة ليبقى التسلسل متسقاً
            stamp = now_on(session_business_date(session), floor=session.opened_at)
            note = ""
        session.closed_at = stamp
        recompute_commission(session)
        fields = ["status", "closed_at", "commission_amount"]
        if note and note not in (session.notes or ""):
            session.notes = f"{(session.notes or '').strip()}\n{note}".strip()
            fields.append("notes")
        session.save(update_fields=fields)
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


def _remove_from_daily(sale, item):
    """يزيل بنداً من السجل اليومي ويحذف السجل إن أصبح فارغاً (المخزون لا يتأثر هنا)."""
    _subtract_item(sale, item)
    if sale.total_sales <= 0 and sale.payment_total <= 0:
        sale.delete()


def _reverse_closed_items(session):
    """عكس بنود الوردية المغلقة من السجلات اليومية فقط — المخزون يبقى مخصوماً (الخصم فوري عند الإضافة)."""
    rows = list(session.items.select_related("fabric").filter(is_returned=False))
    for item in rows:
        sale = DailySale.objects.filter(branch=session.branch, date=item.sale_date).first()
        if sale:
            _remove_from_daily(sale, item)


@transaction.atomic
def delete_session(session):
    """حذف وردية كاملة وإرجاع المخزون المخصوم لكل بند وإلغاء السجلات اليومية."""
    if session.status == SaleSession.Status.CLOSED:
        _unpost_session(session)
        if session.is_manual:
            _reverse_manual_session(session)
        else:
            _reverse_closed_items(session)
    for item in session.items.select_related("fabric").all():
        if not item.is_returned:
            restock_item(item)
    session.items.all().delete()
    session.delete()


@transaction.atomic
def reopen_session(session):
    """إعادة فتح وردية مغلقة: إلغاء السجلات اليومية ثم فتح الوردية — المخزون يبقى مخصوماً."""
    if session.status != SaleSession.Status.CLOSED:
        raise ValueError("لا يمكن إعادة فتح وردية مفتوحة")
    if session.is_manual:
        raise ValueError("لا يمكن إعادة فتح وردية مُدخلة يدوياً — احذفها وأدخلها من جديد")
    _unpost_session(session)
    _reverse_closed_items(session)
    session.status = SaleSession.Status.OPEN
    session.is_backdated = bool(session.session_date and session.session_date < timezone.localdate())
    session.closed_at = None
    session.commission_amount = Decimal("0")
    session.save(update_fields=["status", "closed_at", "commission_amount", "is_backdated"])


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
    restock_item(item)  # إرجاع الخصم الفوري لمخزن الفرع المصدر
    item.session = target_session
    item.sale_date = session_sale_date(target_session)
    # الترقيم يتبع الوردية لا البند: البيعة الواردة لوردية لم تكن فيها
    # تأخذ رقمها التالي هناك، أما إن كانت مجموعة بيعة قائمة فيها فيبقى
    # رقمها كما هو.
    item.group_no = next_sale_group_no(target_session, item.sale_group)
    item.save(update_fields=["session", "sale_date", "group_no"])
    deduct_item_stock(item)  # خصم فوري من مخزن الفرع الهدف
    return item


@transaction.atomic
def clear_session_items(session):
    """إفراغ كل بنود وردية مفتوحة دفعة واحدة مع إرجاع الخصم الفوري لكل بند."""
    if session.status == SaleSession.Status.CLOSED:
        raise ValueError("لا يمكن إفراغ وردية مغلقة")
    for item in session.items.select_related("fabric").all():
        if not item.is_returned:
            restock_item(item)
    session.items.all().delete()


@transaction.atomic
def delete_session_item(session, item):
    if item.is_returned:
        raise ValueError("البند مسترجع — لا يمكن حذفه؛ يمكنك إلغاء الاسترجاع أو إعادة الوردية")
    if session.status == SaleSession.Status.CLOSED:
        sale = DailySale.objects.filter(branch=session.branch, date=item.sale_date).first()
        if sale:
            _remove_from_daily(sale, item)
    restock_item(item)
    item.delete()
    if session.status == SaleSession.Status.CLOSED:
        recompute_commission(session)
        session.save(update_fields=["commission_amount"])
        _post_session(session)


@transaction.atomic
def update_session_item(session, item, attrs):
    if item.is_returned:
        raise ValueError("البند مسترجع — لا يمكن تعديل بند مُسترجع؛ ألغِ الاسترجاع أولاً إذا كان خطاً")
    closed = session.status == SaleSession.Status.CLOSED
    if closed:
        current_sale = DailySale.objects.filter(branch=session.branch, date=item.sale_date).first()
        if current_sale:
            _remove_from_daily(current_sale, item)
    restock_item(item)  # إرجاع الخصم الفوري للكمية القديمة (للوردية المفتوحة والمغلقة)
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
        recompute_commission(session)
        session.save(update_fields=["commission_amount"])
        _post_session(session)
    deduct_item_stock(item)  # خصم فوري للكمية الجديدة
    return item


@transaction.atomic
def return_session_items(session, items, reason=""):
    """استرجاع بنود مبيعة: إبقاء السجل مع وسم «مسترجع» وترجيع الكمية إلى المخزون.

    يُرجَع الخصم الفوري للبند من المخزن في كل الحالات، وللوردية المغلقة يُعكس
    البند من السجل اليومي أيضاً لكن يبقى البند مسجلاً بوسم مسترجع.
    """
    if session is None:
        raise ValueError("الوردية غير موجودة")
    closed = session.status == SaleSession.Status.CLOSED
    for item in items:
        if item.session_id != session.pk:
            raise ValueError("بعض البنود لا تنتمي إلى الوردية")
        if item.is_returned:
            raise ValueError("البند مسترجع مسبقاً")
    for item in items:
        if closed:
            sale = DailySale.objects.filter(branch=session.branch, date=item.sale_date).first()
            if sale:
                _remove_from_daily(sale, item)
        restock_item(item)  # إرجاع الخصم الفوري (للوردية المفتوحة والمغلقة)
        item.is_returned = True
        item.returned_at = timezone.now()
        item.return_reason = (reason or "").strip()[:255]
        item.save(update_fields=["is_returned", "returned_at", "return_reason"])
    if closed:
        recompute_commission(session)
        session.save(update_fields=["commission_amount"])
        _post_session(session)
    return list(items)
