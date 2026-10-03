"""Middleware لحفظ الطلب الحالي في حالة الخيط — يُغذّي سجل التدقيق بالـ employee والعنوان."""

import threading
import time

from .request_state import clear_current_request, set_current_request


class CurrentRequestMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        set_current_request(request)
        try:
            return self.get_response(request)
        finally:
            clear_current_request()


#: حدّ أدنى بين فحوصات النسخة التلقائية (من داخل الطلبات) لتقليل الضغط على قاعدة البيانات
_AUTO_BACKUP_MIN_INTERVAL_SECONDS = 60
_auto_backup_lock = threading.Lock()
_last_auto_backup_check = 0.0


def _database_is_throwaway() -> bool:
    """True when the default connection points at a database built to be discarded.

    Test runs are not something you should be billed for; they are
    something that must never charge you. Every request that gets past
    the throttle serialises the whole database into ``MEDIA_ROOT/backups``,
    and that directory keeps only ``BACKUP_KEEP`` files, the oldest going
    first. So one test run that reaches this middleware spends a real
    backup slot on test data and pushes out a real backup: the last copy
    of yesterday's books, deleted by a change to a serializer.

    The test is the database name, not the process. Asking "is this a test?"
    means guessing from argv and environment, and a guess that is wrong in
    the direction of "yes" is how a real backup gets thrown away. The name
    is the thing that is actually true about the data. A production
    database genuinely called ``test_something`` would lose its
    auto-backup -- a deliberate trade, and cheaper than the other direction.
    """
    from django.db import connections

    name = connections["default"].settings_dict.get("NAME") or ""
    return str(name).startswith("test_")


def _check_auto_backup():
    """Run the auto backup if it is due — throttled in-process to at most once a minute.

    الاستدعاء من طلبات الويب بديل عملي عن cron: على منصات مثل Render (بدون cron بالطبقة
    المجانية) يتحقق التطبيق دورياً كلما مرّ طلب، ويُنشئ النسخة التلقائية عند موعدها.
    """
    global _last_auto_backup_check
    if _database_is_throwaway():
        return
    with _auto_backup_lock:
        now = time.time()
        if now - _last_auto_backup_check < _AUTO_BACKUP_MIN_INTERVAL_SECONDS:
            return
        _last_auto_backup_check = now
    try:
        from appsettings.backup import run_auto_backup_if_due

        run_auto_backup_if_due()
    except Exception as exc:
        # لا يجب أن يوقف النسخ الاحتياطي حياة الطلب أبداً
        import logging

        log = logging.getLogger("appsettings")
        # غياب مفتاح التشفير خطأ إعداد متوقّع لا عطل: يُسجَّل سطراً واحداً
        # بدل أثر استدعاء كامل يتكرّر كل دقيقة على كل طلب.
        from appsettings.crypto import BackupPasswordError

        if isinstance(exc, BackupPasswordError):
            log.warning("النسخ الاحتياطية التلقائية متوقفة: %s", exc)
        else:
            log.exception("استدعاء النسخة الاحتياطية التلقائية فشل")


class AutoBackupMiddleware:
    """يشغّل النسخة الاحتياطية التلقائية عند استحقاقها كجزء من معالجة الطلبات."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        _check_auto_backup()
        return response