from decimal import Decimal

from django.db import transaction as txn
from django.utils import timezone

from warehouses.models import DocumentSequence

from .models import Partner, PartnerOperation, PartnerMovement


class PartnerOperationError(Exception):
    pass


def signed_movement_amount(movement: PartnerMovement) -> Decimal:
    """المبلغ بعلامته حسب نوع الحركة: دعم موجب، سحب سالب."""
    return (
        movement.amount
        if movement.movement_type == PartnerOperation.OperationType.SUPPORT
        else -movement.amount
    )


def create_partner_operation(*, partner, date, operation_type, amount, payment_method="cash", reason="", notes=""):
    if amount <= 0:
        raise PartnerOperationError("المبلغ يجب أن أكبر من صفر")
    if not partner.is_active:
        raise PartnerOperationError("الشريك المحدد غير نشط")
    with txn.atomic():
        operation = PartnerOperation.objects.create(
            number=DocumentSequence.next_number("TRP"),
            date=date or timezone.localdate(),
            partner=partner,
            operation_type=operation_type,
            payment_method=payment_method,
            amount=amount,
            reason=reason,
            notes=notes,
        )
        refresh_partner_movement(operation)
    return operation


def refresh_partner_movement(operation: PartnerOperation) -> PartnerMovement:
    """أعد إنشاء حركة الشريك للعملية وفق نوعها ومبلغها — تُستعمل بعد تعديل العملية.

    تحذف الحركات القديمة المرتبطة بالعملية ثم تُنشئ حركة واحدة للشريك
    المدرج على العملية بنفس منطق الإنشاء في ``create_partner_operation``.
    """
    movement_type = (
        PartnerMovement.MovementType.WITHDRAW
        if operation.operation_type == PartnerOperation.OperationType.WITHDRAW
        else PartnerMovement.MovementType.SUPPORT
    )
    PartnerMovement.objects.filter(operation=operation).delete()
    return PartnerMovement.objects.create(
        operation=operation,
        partner=operation.partner,
        movement_type=movement_type,
        amount=operation.amount,
    )