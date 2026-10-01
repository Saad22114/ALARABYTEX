"""ربط دفعة المورد بحساب التسوية الذي خُصم منه.

عند تسجيل دفعة لمورد يختار المستخدم **من أي حساب خرجت**: حساب الماكينة،
أو الحساب البنكي، أو لا خصم منهما. الخيار الأول والثاني ليسا تسمية تُحفظ:
هما حركة في حساب التسوية، فيجب أن **تنقص** رصيد ذلك الحساب وأن **تظهر في
قسمه** في شاشة «حسابات التسوية» — وإلا كان اختيارُ الحساب كلاماً لا أثر،
ورصيد التسوية يخالف ما في دفتر المورد.

فنُنشئ ``MachineCollection`` مرتبطاً بالقيد عبر
``MachineCollection.supplier_payment``، ونعيد إنشاء الحركة عند تكرار الترحيل
بدل تكديسها، ونحذفها بحذف القيد حتى لا يبقى في التسوية ما ليس في الدفتر.
"""

from decimal import Decimal

from django.db import transaction

from machine_account.models import MachineCollection

from .models import LedgerEntry

ZERO = Decimal("0")


def _collection_method(payment_method):
    """كيف وصلت النقلة إلى المورد: هذا بُعد مستقل عن الحساب الذي حمّلها."""
    if payment_method == LedgerEntry.PaymentMethod.CASH:
        return MachineCollection.CollectionMethod.CASH
    if payment_method == LedgerEntry.PaymentMethod.BANK:
        return MachineCollection.CollectionMethod.TRANSFER
    return MachineCollection.CollectionMethod.OTHER


def sync_settlement(entry, user=None):
    """يوائم حركة التسوية مع قيد المورد، ويعيد ``True`` إن كان لها حركة.

    الدفعة المسجَّلة بقيمة سالبة في دفتر المورد، وحركة التسوية تُقاس بقيمتها
    المطلقة؛ فتسجيلها بالسالب كان سيجعل رصيد التسوية **يزيد** بدل أن ينقص،
    وهذا عكس ما يريده من اختار «حساب الماكينة».
    """
    account = entry.settlement_account
    if (
        entry.entry_type != LedgerEntry.EntryType.PAYMENT
        or account not in LedgerEntry.SETTLEMENT_CHOICES
    ):
        drop_settlement(entry)
        return False

    amount = abs(entry.amount)
    if amount <= ZERO:
        drop_settlement(entry)
        return False

    reference = (
        entry.bank_reference
        or (f"مورد: {entry.supplier.name}" if entry.supplier_id else "")
    )[:100]

    with transaction.atomic():
        # ``update_or_create`` على الربط نفسه: إعادة الترحيل تحدّث الحركة ولا
        # تكدّس حركةً ثانية، فيبقى «ما استُلم» مساوياً لما سُدِّد للموردين.
        MachineCollection.objects.update_or_create(
            supplier_payment=entry,
            defaults={
                "account": account,
                "branch": entry.branch,
                "date": entry.date,
                "amount": amount,
                "method": _collection_method(entry.payment_method),
                "reference": reference,
                "notes": (entry.notes or entry.description or "")[:255],
                "created_by": user if getattr(user, "is_authenticated", False) else None,
            },
        )
    return True


def drop_settlement(entry):
    """يحذف حركة التسوية المرتبطة، فلا يبقى في شاشة التسوية ما ليس بالدفتر."""
    collection = MachineCollection.objects.filter(supplier_payment=entry).first()
    if collection is None:
        return False
    collection.delete()
    return True
