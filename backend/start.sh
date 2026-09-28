#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

export PYTHONUNBUFFERED=1

echo "==> Applying migrations"
python manage.py migrate --noinput

# لا قيمة افتراضية لاسم المستخدم: كان `Saad22114` مثبّتاً هنا، فكل نشر
# جديد كان ينشئ حساب مدير بالاسم نفسه. كما أن كلمة المرور لم تكن تعيد
# تعيين الحساب إلا إذا مُرّرت صراحةً — وهذه كلمة مرور معروفة للجميع.
: "${ADMIN_USERNAME:?ADMIN_USERNAME مطلوب (اسم المستخدم لحساب المدير)}"

echo "==> Ensuring admin account (${ADMIN_USERNAME})"
if [ -n "${ADMIN_PASSWORD:-}" ]; then
    # كلمة المرور من المُشغّل: إعادة تعيين الحساب عند كل نشر.
    python manage.py create_admin --username "${ADMIN_USERNAME}" --password "${ADMIN_PASSWORD}" --name "${ADMIN_NAME:-مدير النظام}" --force-name
else
    # بدون ADMIN_PASSWORD: نمرّر الإدارة بلا --password فتولّد الكلمة عشوائياً
    # وتُطبع مرة واحدة في سجل النشر. إعادة التشغيل التالي يولّد كلمة أخرى،
    # فاحفظها قبل النشر التالي أو مرّر ADMIN_PASSWORD ثابتاً لإدارة وصول النفاذ.
    python manage.py create_admin --username "${ADMIN_USERNAME}" --name "${ADMIN_NAME:-مدير النظام}" --force-name
fi

echo "==> Starting gunicorn on 0.0.0.0:${PORT:-8000}"
exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers "${WEB_CONCURRENCY:-3}" --timeout 120