"""سجل تدقيق تلقائي عبر إشارات Django على النماذج الحساسة في النظام."""

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from accounting.models import Account, JournalEntry, JournalLine
from appsettings.models import AppSettings
from branches.models import Branch, FabricBranchPrice
from core.request_state import audit_suppressed
from customers.models import Customer
from expenses.models import Expense, ExpenseBudget, ExpenseCategory
from messaging.models import Message
from partners.models import Partner, PartnerMovement, PartnerOperation
from sale_sessions.models import Employee, SaleSession, SaleSessionItem
from sales.models import DailySale, DailySaleItem
from suppliers.models import Fabric, LedgerEntry, PurchaseItem, Supplier
from warehouses.models import (
    FabricRoll,
    GoodsReceipt,
    GoodsReceiptItem,
    StockAdjustment,
    StockAdjustmentItem,
    StockCount,
    StockCountItem,
    StockMovement,
    StockOpening,
    StockTransfer,
    StockTransferItem,
    Warehouse,
)

from .models import AuditLog
from .services import log_audit

# نموذج ← قسم النظام
AUDIT_MODELS = {
    Branch: "branches",
    FabricBranchPrice: "branches",
    Supplier: "suppliers",
    Fabric: "fabrics",
    LedgerEntry: "suppliers",
    PurchaseItem: "suppliers",
    Customer: "customers",
    Partner: "partners",
    PartnerOperation: "partners",
    PartnerMovement: "partners",
    Employee: "employees",
    SaleSession: "sessions",
    SaleSessionItem: "sessions",
    DailySale: "sales",
    DailySaleItem: "sales",
    Warehouse: "warehouses",
    FabricRoll: "warehouses",
    GoodsReceipt: "warehouses",
    GoodsReceiptItem: "warehouses",
    StockTransfer: "warehouses",
    StockTransferItem: "warehouses",
    StockAdjustment: "warehouses",
    StockAdjustmentItem: "warehouses",
    StockCount: "warehouses",
    StockCountItem: "warehouses",
    StockMovement: "warehouses",
    StockOpening: "warehouses",
    Expense: "expenses",
    ExpenseCategory: "expenses",
    ExpenseBudget: "expenses",
    Account: "accounting",
    JournalEntry: "accounting",
    JournalLine: "accounting",
    AppSettings: "settings",
    Message: "messages",
}

_OLD_ATTR = "_qomash_old_state"


def _clean(value):
    from decimal import Decimal

    from datetime import date, datetime, time

    if isinstance(value, (Decimal, date, datetime, time)):
        return str(value)
    return value


def _snapshot(instance):
    state = {}
    for field in instance._meta.fields:
        name = field.name
        if name in ("id",):
            continue
        state[field.attname] = _clean(getattr(instance, field.attname, None))
    return state


def _diff(old, new):
    changes = {}
    for key in old.keys() | new.keys():
        old_val = old.get(key)
        new_val = new.get(key)
        if old_val != new_val:
            changes[key] = {"old": old_val, "new": new_val}
    return {k: v for k, v in changes.items() if not (v["old"] is None and v["new"] in (None, "", False, 0))}


@receiver(pre_save)
def _track_old_state(sender, instance, **kwargs):
    if sender not in AUDIT_MODELS:
        return
    if instance.pk is None:
        return
    try:
        old = sender.objects.filter(pk=instance.pk).values()
        setattr(
            instance,
            _OLD_ATTR,
            {r["id"]: {k: _clean(v) for k, v in r.items()} for r in old},
        )
    except Exception:
        pass


@receiver(post_save)
def _log_create_update(sender, instance, created, **kwargs):
    if sender not in AUDIT_MODELS or audit_suppressed():
        return
    if created:
        log_audit(
            AUDIT_MODELS[sender],
            AuditLog.Action.CREATE,
            instance=instance,
        )
        return
    old_map = getattr(instance, _OLD_ATTR, None)
    if not old_map:
        return
    old = old_map.get(instance.pk, {})
    if not old:
        return
    new = _snapshot(instance)
    changes = _diff(old, new)
    if changes:
        log_audit(
            AUDIT_MODELS[sender],
            AuditLog.Action.UPDATE,
            instance=instance,
            changes=changes,
        )


@receiver(post_delete)
def _log_delete(sender, instance, **kwargs):
    if sender not in AUDIT_MODELS or audit_suppressed():
        return
    log_audit(
        AUDIT_MODELS[sender],
        AuditLog.Action.DELETE,
        instance=instance,
    )