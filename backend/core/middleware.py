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


def _check_auto_backup():
    """Run the auto backup if it is due — throttled in-process to at most once a minute.

    الاستدعاء من طلبات الويب بديل عملي عن cron: على منصات مثل Render (بدون cron بالطبقة
    المجانية) يتحقق التطبيق دورياً كلما مرّ طلب، ويُنشئ النسخة التلقائية عند موعدها.
    """
    global _last_auto_backup_check
    with _auto_backup_lock:
        now = time.time()
        if now - _last_auto_backup_check < _AUTO_BACKUP_MIN_INTERVAL_SECONDS:
            return
        _last_auto_backup_check = now
    try:
        from appsettings.backup import run_auto_backup_if_due

        run_auto_backup_if_due()
    except Exception:
        # لا يجب أن يوقف النسخ الاحتياطي حياة الطلب أبداً
        import logging

        logging.getLogger("appsettings").exception("استدعاء النسخة الاحتياطية التلقائية فشل")


class AutoBackupMiddleware:
    """يشغّل النسخة الاحتياطية التلقائية عند استحقاقها كجزء من معالجة الطلبات."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        _check_auto_backup()
        return response