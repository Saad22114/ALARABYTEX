"""إعدادات الاختبارات.

تُستخدم الاختبارات القديمة القائمة بدون مصادقة، لذا تُبقى الأذونات
الافتراضية AllowAny هنا. اختبارات الدخول الجديدة تستخدم override_settings
مع REST_FRAMEWORK الحقيقي من config.settings للتحقق من التطبيق الفعلي.
"""

from .settings import *  # noqa: F403

REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"] = [  # noqa: F405
    "rest_framework.permissions.AllowAny"
]