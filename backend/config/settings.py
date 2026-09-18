import os
import sys
from pathlib import Path

import dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
dotenv.load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-dev-change-me-0987fabric")

DEBUG = os.getenv("DEBUG", "True").lower() in ("1", "true", "yes")

ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "*").split(",") if h.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "corsheaders",
    "rest_framework",
    # Local apps
    "core",
    "appsettings",
    "branches",
    "suppliers",
    "sales",
    "expenses",
    "dashboard",
    "reports",
    "warehouses",
    "partners",
    "sale_sessions",
    "customers",
    "accounting",
    "messaging",
    "accounts",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Database - PostgreSQL
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "fabric_arabi"),
        "USER": os.getenv("DB_USER", "postgres"),
        "PASSWORD": os.getenv("DB_PASSWORD", "postgres"),
        "HOST": os.getenv("DB_HOST", "127.0.0.1"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "ar"
TIME_ZONE = "Asia/Muscat"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# CORS
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:9005",
    "http://127.0.0.1:9005",
    "http://localhost:9012",
    "http://127.0.0.1:9012",
]
_frontend = os.getenv("FRONTEND_URL")
if _frontend:
    CORS_ALLOWED_ORIGINS.append(_frontend)
CORS_ALLOW_CREDENTIALS = True

# Django REST Framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "accounts.authentication.EmployeeTokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PAGINATION_CLASS": "core.pagination.StandardPagination",
    "DEFAULT_FILTER_BACKENDS": [
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
}

# Arabic API messages shared across the whole API
API_MESSAGES = {
    "created": "تم إنشاء السجل بنجاح",
    "updated": "تم تحديث السجل بنجاح",
    "deleted": "تم حذف السجل بنجاح",
    "invalid_data": "يرجى التأكد من البيانات المدخلة",
    "not_found": "لم يتم العثور على السجل",
    "server_error": "حدث خطأ أثناء حفظ البيانات",
    "sales_mismatch": "إجمالي طرق الدفع لا يساوي إجمالي المبيعات",
    "branch_in_use": "لا يمكن حذف الفرع لأنه مرتبط بسجلات مبيعات أو مصاريف",
    "category_in_use": "لا يمكن حذف التصنيف لأنه مرتبط بمصاريف مسجلة",
    "system_category": "لا يمكن تعديل أو حذف تصنيف مصاريف أساسي من النظام",
}