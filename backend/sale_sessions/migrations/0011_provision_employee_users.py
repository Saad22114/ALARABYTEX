import os
import re

from django.conf import settings
from django.db import migrations

DEFAULT_PASSWORD = os.getenv("DEFAULT_EMPLOYEE_PASSWORD", "Qomash@123")

AUTH_APP, AUTH_MODEL = settings.AUTH_USER_MODEL.split(".")


def _unique_username(base, User):
    username = base or "employee"
    n = 1
    while User.objects.filter(username=username).exists():
        username = f"{base}{n}"
        n += 1
    return username


def provision_users(apps, schema_editor):
    Employee = apps.get_model("sale_sessions", "Employee")
    User = apps.get_model(AUTH_APP, AUTH_MODEL)
    for emp in Employee.objects.order_by("id"):
        if getattr(emp, "user_id", None):
            continue
        base = re.sub(r"\s+", "", emp.phone or "")
        if not base:
            base = re.sub(r"\s+", "", emp.name or f"employee-{emp.id}")
        username = _unique_username(base, User)
        user = User.objects.create_user(username=username, password=DEFAULT_PASSWORD)
        emp.user = user
        emp.save(update_fields=["user"])


def unprovision(apps, schema_editor):
    Employee = apps.get_model("sale_sessions", "Employee")
    User = apps.get_model(AUTH_APP, AUTH_MODEL)
    for emp in Employee.objects.exclude(user__isnull=True):
        user = emp.user
        emp.user = None
        emp.save(update_fields=["user"])
        user.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("sale_sessions", "0010_employee_user"),
    ]

    operations = [
        migrations.RunPython(provision_users, unprovision),
    ]