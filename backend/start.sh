#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

export PYTHONUNBUFFERED=1

echo "==> Applying migrations"
python manage.py migrate --noinput

echo "==> Ensuring admin account (Saad22114)"
python manage.py create_admin --username "${ADMIN_USERNAME:-Saad22114}" --password "${ADMIN_PASSWORD:-Saad22114@#}" --name "${ADMIN_NAME:-مدير النظام}" --force-name

echo "==> Starting gunicorn on 0.0.0.0:${PORT:-8000}"
exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers "${WEB_CONCURRENCY:-3}" --timeout 120