import base64
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model

from core.request_state import suppress_audit


def _model(app_label, name):
    return apps.get_model(app_label, name)


#: (app_label, model_name) — order follows dependency (parents before children)
RESTORE_ORDER = [
    ("auth", "User"),
    ("branches", "Branch"),
    ("suppliers", "Supplier"),
    ("expenses", "ExpenseCategory"),
    ("suppliers", "Fabric"),
    ("warehouses", "Warehouse"),
    ("warehouses", "DocumentSequence"),
    ("sale_sessions", "Employee"),
    ("customers", "Customer"),
    ("suppliers", "LedgerEntry"),
    ("suppliers", "PurchaseItem"),
    ("warehouses", "FabricRoll"),
    ("branches", "FabricBranchPrice"),
    ("sales", "DailySale"),
    ("sales", "DailySaleItem"),
    ("expenses", "Expense"),
    ("expenses", "ExpenseBudget"),
    ("warehouses", "GoodsReceipt"),
    ("warehouses", "GoodsReceiptItem"),
    ("warehouses", "StockTransfer"),
    ("warehouses", "StockTransferItem"),
    ("warehouses", "StockAdjustment"),
    ("warehouses", "StockAdjustmentItem"),
    ("warehouses", "StockCount"),
    ("warehouses", "StockCountItem"),
    ("warehouses", "StockOpening"),
    ("warehouses", "StockOpeningItem"),
    ("warehouses", "StockMovement"),
    ("partners", "Partner"),
    ("partners", "PartnerOperation"),
    ("partners", "PartnerMovement"),
    ("sale_sessions", "SaleSession"),
    ("sale_sessions", "SaleSessionItem"),
    ("accounting", "Account"),
    ("accounting", "JournalEntry"),
    ("accounting", "JournalLine"),
    ("accounting", "ClosedPeriod"),
    ("messaging", "Message"),
]

#: self-referencing FKs that must be re-pointed after rows are created
SELF_FIELDS = {
    "accounting.Account": ["parent"],
    "expenses.Expense": ["origin"],
    "messaging.Message": ["reply_to"],
}


def _self_sorted(rows, self_fields):
    """Order rows so parent rows come before rows referencing them."""
    if not self_fields or not rows:
        return rows
    remaining = list(rows)
    ordered = []
    seen = set()
    while remaining:
        progress = False
        for row in list(remaining):
            deps = [row[f + "_id"] for f in self_fields if row.get(f + "_id")]
            if all(d is None or d in seen for d in deps):
                ordered.append(row)
                seen.add(row["id"])
                remaining.remove(row)
                progress = True
        if not progress:
            ordered.extend(remaining)
            break
    return ordered


def _dump_rows(app_label, name):
    rows = list(_model(app_label, name).objects.all().values())
    if app_label == "auth" and name == "User":
        rows = [r for r in rows]
    return rows


def export_backup(settings_obj):
    data = {"version": 2, "tables": {}}
    for app_label, name in RESTORE_ORDER:
        data["tables"][f"{app_label}.{name}"] = _dump_rows(app_label, name)
    data["tables"]["appsettings.AppSettings"] = [
        {f: getattr(settings_obj, f) for f in [x.name for x in settings_obj._meta.fields]}
    ]
    employee = _model("sale_sessions", "Employee")
    data["m2m_employee_allowed_branches"] = list(
        employee.allowed_branches.through.objects.values("id", "employee_id", "branch_id")
    )
    logo_meta = None
    if settings_obj.logo:
        p = Path(settings.MEDIA_ROOT) / settings_obj.logo
        if p.exists() and p.is_file():
            logo_meta = {
                "name": p.name,
                "content": base64.b64encode(p.read_bytes()).decode("ascii"),
            }
    data["logo_file"] = logo_meta
    return data


def should_run_auto_backup(s, now=None):
    """Determine whether an automatic backup is due based on the settings schedule.

    Rules:
    - disabled => never
    - first run (last_auto_backup_at is None) => run
    - interval mode (auto_backup_every_hours > 0) => run if elapsed >= hours
    - daily-time mode (auto_backup_time set) => run once the wall clock passes that time
    """
    if not s.auto_backup_enabled:
        return False
    if s.last_auto_backup_at is None:
        return True
    if now is None:
        from django.utils import timezone

        now = timezone.now()
    from django.utils import timezone

    elapsed_h = (now - s.last_auto_backup_at).total_seconds() / 3600.0
    candidates = []
    if s.auto_backup_every_hours and s.auto_backup_every_hours > 0:
        candidates.append(elapsed_h >= s.auto_backup_every_hours)
    if s.auto_backup_time is not None:
        local_now = timezone.localtime(now)
        local_last = timezone.localtime(s.last_auto_backup_at)
        crossed_today = local_now.time() >= s.auto_backup_time and local_last.date() < local_now.date()
        candidates.append(crossed_today)
    if not candidates:
        return False
    return any(candidates)


def write_backup_file(settings_obj, prefix="backup"):
    """Export all data to a timestamped file under MEDIA_ROOT/backups.
    Returns the relative path (e.g. backups/backup_20260922_101530.json).
    """
    from datetime import datetime

    content = json_dumps(export_backup(settings_obj))
    if settings_obj.backup_password:
        content = encrypt_content(content, settings_obj.backup_password)
    rel_dir = Path("backups")
    backdir = Path(settings.MEDIA_ROOT) / rel_dir
    backdir.mkdir(parents=True, exist_ok=True)
    filename = f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    rel = (rel_dir / filename).as_posix()
    (backdir / filename).write_bytes(content.encode("utf-8"))
    return rel


def json_dumps(data):
    import json

    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


def encrypt_content(content, password):
    from .crypto import encrypt_backup

    return encrypt_backup(content.encode("utf-8"), password).decode("utf-8")


def _backup_dir():
    d = Path(settings.MEDIA_ROOT) / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_backup_files():
    """Return metadata rows for stored backup files (newest first)."""
    from django.utils import timezone

    rows = []
    for p in sorted(_backup_dir().glob("*.json"), reverse=True):
        rows.append(
            {
                "name": p.name,
                "size": p.stat().st_size,
                "modified": timezone.make_aware(
                    timezone.datetime.fromtimestamp(p.stat().st_mtime)
                ).isoformat(),
            }
        )
    return rows


def backup_file_abspath(name):
    """Safely resolve a backup filename inside the backups dir (no path traversal)."""
    safe = Path(name).name
    p = _backup_dir() / safe
    if not p.exists() or not p.is_file():
        return None
    return p


def _create_rows(app_label, name, rows):
    """Re-create rows with explicit PKs to preserve relationships."""
    model = _model(app_label, name)
    self_fields = SELF_FIELDS.get(f"{app_label}.{name}", [])
    ordered = _self_sorted(rows, self_fields)
    created = []

    for row in ordered:
        data = dict(row)
        self_ids = {}
        for f in self_fields:
            key = f + "_id"
            self_ids[f] = data.pop(key, None)
        auto_stamps = {}
        for stamp in ("created_at", "updated_at"):
            if stamp in data:
                auto_stamps[stamp] = data.pop(stamp)
        obj = model(pk=row["id"], **data)
        obj.save()
        for f, fk_val in self_ids.items():
            if fk_val is not None:
                setattr(obj, f + "_id", fk_val)
                obj.save(update_fields=[f + "_id"])
        if auto_stamps:
            model.objects.filter(pk=obj.pk).update(**auto_stamps)
        created.append(obj)
    return created


def _delete_all():
    """Delete child-first, skipping auth.User (kept for login continuity)."""
    for app_label, name in reversed(RESTORE_ORDER):
        if app_label == "auth" and name == "User":
            continue
        try:
            _model(app_label, name).objects.all().delete()
        except Exception:
            pass


def restore_backup(payload):
    """Replace ALL data with the payload produced by :func:`export_backup`."""
    tables = payload.get("tables", {})
    User = get_user_model()

    with suppress_audit():
        # 1) delete everything except auth users (to keep the admin session alive)
        _delete_all()

        # 2) users: create missing accounts referenced by employees/journal
        backup_users = tables.get("auth.User", [])
        existing = set(User.objects.values_list("id", flat=True))
        for row in backup_users:
            if row["id"] in existing:
                continue
            data = dict(row)
            for stamp in ("created_at", "updated_at"):
                data.pop(stamp, None)
            uid = data.pop("id")
            User(pk=uid, **data).save()

        # 3) restore appsettings singleton (keep real PK=1)
        from .models import AppSettings

        real = AppSettings.load()
        settings_rows = tables.get("appsettings.AppSettings", [])
        if settings_rows:
            ser_data = settings_rows[0]
            for f in list(ser_data.keys()):
                if f in ("id", "created_at", "updated_at"):
                    continue
                setattr(real, f, ser_data[f])
            real.save()

        # 4) all other models in dependency order
        for app_label, name in RESTORE_ORDER:
            if (app_label, name) == ("auth", "User"):
                continue
            _create_rows(app_label, name, tables.get(f"{app_label}.{name}", []))

        # 5) restore employee.branches M2M
        through = _model("sale_sessions", "Employee").allowed_branches.through
        through.objects.all().delete()
        for row in payload.get("m2m_employee_allowed_branches", []):
            through.objects.create(**row)

        # 6) restore logo file
        logo_meta = payload.get("logo_file")
        if logo_meta and logo_meta.get("content"):
            rel = f"logos/{logo_meta['name']}"
            p = Path(settings.MEDIA_ROOT) / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(base64.b64decode(logo_meta["content"]))
            real.logo = rel
            real.save(update_fields=["logo", "updated_at"])
        elif logo_meta is None and real.logo:
            real.logo = ""
            real.save(update_fields=["logo", "updated_at"])