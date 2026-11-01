from django.db import migrations


WINDOW = "supplier-fabric-sales"
EXISTING_SALES_WINDOWS = ["sales", "sessions", "closed", "by_employee"]


def add_window(apps, schema_editor):
    Employee = apps.get_model("sale_sessions", "Employee")
    for employee in Employee.objects.all().iterator():
        permissions = employee.permissions if isinstance(employee.permissions, dict) else {}
        sales = permissions.get("sales")
        if not isinstance(sales, dict):
            continue
        windows = sales.get("windows")
        if not isinstance(windows, list):
            windows = EXISTING_SALES_WINDOWS.copy()
        windows = [key for key in windows if key != WINDOW]
        if employee.role in {"admin", "supervisor", "viewer"}:
            windows.append(WINDOW)
        if sales.get("windows") != windows:
            sales["windows"] = windows
            permissions["sales"] = sales
            employee.permissions = permissions
            employee.save(update_fields=["permissions"])


def remove_window(apps, schema_editor):
    Employee = apps.get_model("sale_sessions", "Employee")
    for employee in Employee.objects.all().iterator():
        permissions = employee.permissions if isinstance(employee.permissions, dict) else {}
        sales = permissions.get("sales")
        if isinstance(sales, dict) and isinstance(sales.get("windows"), list) and WINDOW in sales["windows"]:
            sales["windows"] = [key for key in sales["windows"] if key != WINDOW]
            employee.permissions = permissions
            employee.save(update_fields=["permissions"])


class Migration(migrations.Migration):
    dependencies = [("sale_sessions", "0032_notification")]
    operations = [migrations.RunPython(add_window, remove_window)]
