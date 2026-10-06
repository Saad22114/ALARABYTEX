import base64
import uuid
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction

from core.request_state import suppress_audit

from .crypto import BackupPasswordError, password_problem

#: عدد النسخ المحفوظة على القرص؛ ما قبلها يُحذف عند كل نسخة جديدة.
#: يُضبط بمتغيّر البيئة BACKUP_KEEP دون حاجة لهجرة قاعدة بيانات.
BACKUP_KEEP = getattr(settings, "BACKUP_KEEP", 20)

#: تطبيقات لا تُصدَّر. جداول إطار العمل تُبنى من الترحيلات وتُشتق من الكود،
#: فنسخُها في ملف لا ينفع، ومسحُها عند الاستعادة يكسر الصلاحيات والجلسات.
EXCLUDED_APPS = frozenset(
    {"django", "contenttypes", "sessions", "admin", "authtoken", "rest_framework"}
)

#: جداول داخل تطبيقات مصدَّرة لكنها مشتقّة من الكود: ``auth.Permission`` مربوطة
#: بـ``contenttypes.ContentType`` وتُعاد بناؤها من كل ترحيل، فنسخُها يجمّد
#: الصلاحيات عند نسخة قديمة ثم يمنع إضافة صلاحية جديدة.
EXCLUDED_MODELS = frozenset({"auth.Permission"})

#: جداول لها منطق خاص: صفّ واحد يُستبدل بصفّ الإعدادات الحيّ، لا يُحذف ويُعاد.
SPECIAL_TABLES = frozenset({"appsettings.AppSettings"})


def _model(label):
    """النموذج من تسميته الكاملة ``app_label.ModelName``.

    لا نبني التسمية من ``app_label`` و``model_name``: الأخيرة صغيرة الحروف
    بحكم Django، فتنتج مفاتيح ``branches.branch`` لا ``branches.Branch``،
    فلا يطابقها الاستعادة ولا ملف قديم فيسقط الجدول كلّه.
    """
    return apps.get_model(label)


def _is_exported(opts):
    if opts.app_label in EXCLUDED_APPS:
        return False
    if opts.label in EXCLUDED_MODELS or opts.label in SPECIAL_TABLES:
        return False
    return not opts.proxy and opts.managed


def _exported_labels():
    """تسميات كل جداول المشروع التي تذهب في النسخة."""
    return sorted(
        m._meta.label for m in apps.get_models() if _is_exported(m._meta)
    )


def _self_fields(model):
    """أسماء الحقول التي تشير إلى الجدول نفسه (مرجع ذاتي).

    تُشتق من النموذج بدل قائمة مكتوبة يدوياً، فكل مرجع ذاتي جديد يُغطّى
    تلقائياً عند الاستعادة ولا يُسقط.
    """
    return [
        f.name
        for f in model._meta.concrete_fields
        if f.is_relation and not f.auto_created and f.related_model is model
    ]


def _dependency_labels(model):
    """النماذج التي يجب إنشاؤها قبل هذا النموذج (FK عادية)."""
    deps = set()
    for f in model._meta.concrete_fields:
        if not f.is_relation or f.auto_created:
            continue
        target = f.related_model
        if target is None or target is model:
            continue  # المرجع الذاتي يُرتَّب داخل الجدول لا بين الجداول
        if _is_exported(target._meta):
            deps.add(target._meta.label)
    return deps


def _m2m_through_labels(exported_labels):
    """جداول الربط ``ManyToMany`` التي طرفاها مُصدَّران معاً.

    تصدير طرفٍ دون الآخر يبقى صفوفاً تشير إلى غائب: لو صدّرنا
    ``Group_permissions`` دون ``auth.Permission`` لأشارت الصفوف إلى
    صلاحيات غير موجودة. أما الربط داخل النطاق المصدَّر — الربط بين
    الموظفين والفروع، والمستخدمين والمجموعات — فيشمله الشرط.
    """
    out = []
    for model in apps.get_models():
        if not _is_exported(model._meta):
            continue
        for f in model._meta.many_to_many:
            through = f.remote_field.through
            if not through._meta.auto_created:
                continue  # جدول ربط مُعرَّف يدوياً — يُصدَّر كنموذج إن كان مُداراً
            if {f.model._meta.label, f.related_model._meta.label} <= exported_labels:
                out.append(through._meta.label)
    return sorted(set(out))


def _topological_order(labels):
    """ترتيب الجداول بحيث يسبق كلُّ أصلٍ كلَّ فرعٍ يعتمد عليه."""
    remaining = list(labels)
    deps = {label: _dependency_labels(_model(label)) for label in remaining}
    ordered = []
    placed = set()
    while remaining:
        ready = [label for label in remaining if deps[label] <= placed]
        if not ready:
            # دورة حقيقية في المخطّط: نضع البقية بترتيبها بدل الدوران بلا نهاية
            ordered.extend(sorted(remaining))
            break
        for label in sorted(ready):
            ordered.append(label)
            placed.add(label)
        remaining = [label for label in remaining if label not in placed]
    return ordered


def _model_labels():
    """جداول النماذج وحدها، مرتّبة بحيث يسبق الأصلُ الفرعَ."""
    return _topological_order(_exported_labels())


def _through_labels():
    """جداول الربط المستقلة (تُمسح قبل أصلها وتُعاد بعد إنشائه)."""
    return _m2m_through_labels(set(_exported_labels()))


def _order():
    """ترتيب الاستعادة الكامل: النماذج ثم جداول الربط في النهاية.

    يُشتق من مخطّط المفاتيح الأجنبية في كل استدعاء بدل قائمة مكتوبة يدوياً.
    القائمة القديمة أسقطت 11 جدولاً بأكملها — منها كل جداول الرواتب ودفعات
    التسويات — لأن أحداً لم يذكرها، فكانت تُمسح عند الاستعادة ولا تعود.
    """
    return _model_labels() + _through_labels()


def self_fields_for(label):
    """حقول المرجع الذاتي لنموذج معيّن."""
    return _self_fields(_model(label))


def _auto_stamp_fields(model):
    """الحقول التي يفرض Django قيمتها عند الحفظ ولا يقبل المُرمِّز تمريرها.

    ``auto_now_add`` / ``auto_now`` تتجاوز أي قيمة ترد من النموذج، فلا بدّ من
    كتابة القيمة الأصلية بعد الحفظ عبر ``.update()`` الذي يتجاوز ``pre_save``.

    تُشتق من النموذج لا من قائمة ``("created_at", "updated_at")``: الحقلان
    ليسا الوحيدين — ``SaleSession.opened_at`` و``AuditLog.timestamp`` كذلك
    أي حقل تلقائي خارجها كان يعيد تاريخ كل وردية وسجل تدقيق إلى لحظة الاستعادة.
    """
    return [
        f.name
        for f in model._meta.fields
        if getattr(f, "auto_now_add", False) or getattr(f, "auto_now", False)
    ]


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


def _dump_rows(label):
    rows = list(_model(label).objects.all().values())
    if label == "auth.User":
        # لا نصدّر هاش كلمات المرور أبداً: الحسابات المستعادة تُنشأ بدون كلمة
        # مرور (غير قابلة للدخول) فتُصفَّر من المدير بعد الاستعادة.
        for row in rows:
            row.pop("password", None)
    return rows


def export_backup(settings_obj):
    data = {"version": 2, "tables": {}, "m2m": {}}
    for label in _model_labels():
        data["tables"][label] = _dump_rows(label)
    data["tables"]["appsettings.AppSettings"] = [
        {
            f: getattr(settings_obj, f)
            # لا تُصدَّر كلمة مرور النسخ الاحتياطي نفسها داخل الملف أبداً
            for f in [x.name for x in settings_obj._meta.fields]
            if f != "backup_password"
        }
    ]
    # جداول الربط في خانة مستقلّة: تُمسح وتُعاد بعد طرفَيها، لا مع الجداول
    for label in _through_labels():
        data["m2m"][label] = list(_model(label).objects.all().values())
    # مفتاح قديم محفوظ لتوافق النسخ السابقة مع القارئات القديمة
    legacy = data["m2m"].get("sale_sessions.Employee_allowed_branches")
    if legacy is not None:
        data["m2m_employee_allowed_branches"] = legacy
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


def backup_document(settings_obj):
    """نص النسخة الاحتياطية كاملاً، **مشفّراً دائماً**.

    التشفير ليس خياراً يُختار: النسخة غير المشفّرة تفتح بأي محرر نصوص على أي
    جهاز، فتسريب الملف يعني تسريب كل بيانات النظام — الفروع والرواتب والزبائن
    والأرباح. ومن يفتح الملف يملك كل شيء.

    دالة واحدة يبني منها التنزيل والكتابة على القرص، لأن المسارين كانا يقرّران
    التشفير كلٌّ منهما مستقلاً — فأمكن أن يُصدَّر ملف من أحدهما بلا تشفير
    بينما الآخر مشفّر، ولا يظهر الخلل إلا حين يفشل الاسترجاع في أسوأ لحظة.
    """
    problem = password_problem(settings_obj.backup_password)
    if problem:
        raise BackupPasswordError(problem)
    plaintext = json_dumps(export_backup(settings_obj))
    return encrypt_content(plaintext, settings_obj.backup_password)


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
        # Enabled but neither time nor interval is set → default to every 24h
        candidates.append(elapsed_h >= 24)
    return any(candidates)


def run_auto_backup_if_due(now=None):
    """Create the automatic backup now if one is due. Returns relative path or None.

    Uses a row lock (select_for_update) on the AppSettings singleton so that in
    multi-worker environments only one process creates the backup at a time.
    """
    from django.utils import timezone

    from .models import AppSettings

    s = AppSettings.load()
    if not should_run_auto_backup(s, now):
        return None
    with transaction.atomic():
        locked = AppSettings.objects.select_for_update().get(pk=s.pk)
        if not should_run_auto_backup(locked, now):
            return None
        rel = write_backup_file(locked)
        # ``last_auto_backup_at`` يُحدَّث فقط بعد نجاح الكتابة: تخطّاؤه عند
        # الفشل يجعل الجدولة تعيد المحاولة في الطلب التالي بدل انتظار
        # الفاصل الزمني كاملاً.
        locked.last_auto_backup_at = timezone.now()
        locked.last_auto_backup_path = rel
        locked.save(update_fields=["last_auto_backup_at", "last_auto_backup_path", "updated_at"])
        return rel


def _unique_backup_path(backdir, stem):
    """مسار نسخة باسم لا وجود له، فلا تبتلع نسخةٌ أختها في الثانية نفسها.

    التسمية بدقة الثانية: نسختان في الثانية نفسها تأخذان الاسم نفسه، فتكتب
    الثانية فوق الأولى وضيّعتها بصمت — وتكرارُ الضغط على «إنشاء نسخة الآن»
    يجعل ذلك مألوفاً لا نادراً.
    """
    candidate = backdir / f"{stem}.json"
    if not candidate.exists():
        return candidate
    for n in range(2, 1000):
        candidate = backdir / f"{stem}-{n}.json"
        if not candidate.exists():
            return candidate
    return backdir / f"{stem}-{uuid.uuid4().hex[:8]}.json"


def write_backup_file(settings_obj, prefix="backup"):
    """Export all data to a timestamped file under MEDIA_ROOT/backups.
    Returns the relative path (e.g. backups/backup_20260922_101530.json).

    يُقصى ما تجاوز ``BACKUP_KEEP`` نسخةً فوراً بعد الكتابة، فلا تتراكم
    النسخ على القرص بلا سقف. المحتوى مشفّر دائماً — انظر ``backup_document``.
    """
    from datetime import datetime

    content = backup_document(settings_obj)
    rel_dir = Path("backups")
    backdir = Path(settings.MEDIA_ROOT) / rel_dir
    backdir.mkdir(parents=True, exist_ok=True)
    stem = f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    path = _unique_backup_path(backdir, stem)
    path.write_bytes(content.encode("utf-8"))
    _keep_last_n(keep_current=path)
    return (rel_dir / path.name).as_posix()


def _sorted_backup_paths():
    """ملفات النسخ مرتّبة من الأحدث إلى الأقدم.

    الترتيب بمعدّل التعديل لا بالاسم: ملفان بنفس الثانية (نسخة تلقائية
    ونسخة يدوية) لا يصلح بينهما الحسم بالاسم، فيبقى أحدهما معرّضاً للحذف
    لمجرّد اعتباط التسمية. ويُتخطّى الملف الذي يختفي بين ``glob`` و``stat``،
    وإلا سقطت القائمة كلها بسبب ملف يحذفه المجدول في اللحظة نفسها.
    """
    paths = []
    for p in _backup_dir().glob("*.json"):
        try:
            paths.append((p.stat().st_mtime, p.name, p))
        except OSError:
            continue
    paths.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item[2] for item in paths]


def _keep_last_n(keep=BACKUP_KEEP, keep_current=None):
    """يحتفظ بآخر ``keep`` نسخة ويحذف ما قبلها. يعيد أسماء ما حُذف.

    ``keep_current`` اسم ملف يجب ألا يُحذف حتى لو كان خارج العشرين — نسخة
    ``last_auto_backup_path`` تُكتب قبل القصّ، وقد يقع ترتيبها خارجه في
    نظام ملفات تقريبي.
    """
    paths = _sorted_backup_paths()
    protected = keep_current.name if keep_current is not None else None
    removed = []
    for index, path in enumerate(paths):
        if index < keep:
            continue
        if protected is not None and path.name == protected:
            continue
        try:
            path.unlink()
            removed.append(path.name)
        except OSError:
            # نسخة مفتوحة على جهاز آخر أو مقفلة: نتخطاها ولا نُفشل العملية
            continue
    return removed


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
    """Return metadata rows for stored backup files (newest first).

    نفس ترتيب ``_sorted_backup_paths`` الذي يقصّ به النظام: فما تراه الواجهة
    هو ما سيُحذف فعلاً، لا ترتيباً آخر بالاسم.
    """
    from django.utils import timezone

    rows = []
    for p in _sorted_backup_paths():
        try:
            stat = p.stat()
        except OSError:
            continue
        rows.append(
            {
                "name": p.name,
                "size": stat.st_size,
                "modified": timezone.make_aware(
                    timezone.datetime.fromtimestamp(stat.st_mtime)
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


def delete_backup_file(name):
    """Delete a stored backup file; returns True if a file was removed."""
    safe = Path(name).name
    p = _backup_dir() / safe
    if not p.exists() or not p.is_file():
        return False
    p.unlink()
    return True


def _create_rows(label, rows):
    """Re-create rows with explicit PKs to preserve relationships."""
    model = _model(label)
    self_fields = self_fields_for(label)
    stamp_fields = _auto_stamp_fields(model)
    ordered = _self_sorted(rows, self_fields)
    created = []

    for row in ordered:
        data = dict(row)
        self_ids = {}
        for f in self_fields:
            key = f + "_id"
            self_ids[f] = data.pop(key, None)
        auto_stamps = {}
        for stamp in stamp_fields:
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


def _remap_user_references(tables, m2m, user_id_map):
    """Replace backup user IDs with matching accounts already on this device.

    Local and online databases often assign different primary keys to the
    same username.  Since restore deliberately preserves local auth users,
    imported rows must point at the preserved account ID as well.
    """
    if not user_id_map:
        return
    User = get_user_model()
    for collection in (tables, m2m):
        for label, rows in collection.items():
            try:
                model = _model(label)
            except LookupError:
                continue
            user_fk_keys = [
                field.attname
                for field in model._meta.concrete_fields
                if field.is_relation and field.related_model is User
            ]
            for row in rows:
                for key in user_fk_keys:
                    if row.get(key) in user_id_map:
                        row[key] = user_id_map[row[key]]


def _delete_all():
    """مسح كل شيء عدا ``auth.User`` (يُبقي جلسة الدخول حيّة).

    جداول الربط تُمسح **أولاً**: صفُّ ``Employee_allowed_branches`` يمنع حذف
    الموظف الذي يشير إليه بـ``PROTECT``، وكان ``except: pass`` يبتلع الخطأ
    فيبقى الموظف وتُحاول الاستعادة إنشاء نفس المعرّف فتفشل.
    """
    for label in _through_labels():
        try:
            _model(label).objects.all().delete()
        except Exception:
            pass
    for label in reversed(_order()):
        if label == "auth.User":
            continue
        try:
            _model(label).objects.all().delete()
        except Exception:
            pass


def restore_backup(payload):
    """Replace ALL data with the payload produced by :func:`export_backup`."""
    tables = payload.get("tables", {})
    User = get_user_model()

    with suppress_audit():
        with transaction.atomic():
            # 1) delete everything except auth users (to keep the admin session alive)
            _delete_all()

            # 2) users: create missing accounts referenced by employees/journal
            #    — كلمة المرور لا تُستعاد أبداً (حتى من نسخ قديمة): الحساب يُنشأ
            #    بدون كلمة مرور ويديره المدير بصفّها بعد الاستعادة.
            backup_users = tables.get("auth.User", [])
            existing = set(User.objects.values_list("id", flat=True))
            existing_by_username = dict(
                User.objects.values_list("username", "id")
            )
            user_id_map = {}
            for row in backup_users:
                backup_id = row["id"]
                local_id = existing_by_username.get(row.get("username"))
                if local_id is not None:
                    user_id_map[backup_id] = local_id
                    continue
                data = dict(row)
                data.pop("password", None)
                for stamp in ("created_at", "updated_at"):
                    data.pop(stamp, None)
                data.pop("id", None)
                # Keep the backup PK where free. If this local database has
                # assigned it to another username, let the DB allocate a safe
                # ID and rewrite every imported FK below.
                uid = backup_id if backup_id not in existing else None
                user = User(pk=uid, **data)
                user.save()
                existing.add(user.pk)
                user_id_map[backup_id] = user.pk

            # Remap references before restoring Employee and other records.
            m2m = dict(payload.get("m2m") or {})
            legacy_rows = payload.get("m2m_employee_allowed_branches")
            if legacy_rows is not None:
                m2m.setdefault("sale_sessions.Employee_allowed_branches", legacy_rows)
            _remap_user_references(tables, m2m, user_id_map)

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
            for label in _model_labels():
                if label == "auth.User":
                    continue
                _create_rows(label, tables.get(label, []))

            # 5) جداول الربط، بعد إنشاء طرفَيها. المفتاح القديم مقروء أيضاً
            #    حتى تُستعاد نسخٌ أُنشئت قبل تعميم الصيغة.
            for label in _through_labels():
                through = _model(label)
                rows = m2m.get(label, [])
                through.objects.all().delete()
                for row in rows:
                    data = {k: v for k, v in row.items() if k != "id"}
                    through.objects.create(**data)

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
