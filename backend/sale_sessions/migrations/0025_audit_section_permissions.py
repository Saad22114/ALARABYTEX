"""مزامنة صلاحيات الموظفين مع قسم سجل التدقيق الجديد.

قسم ``audit`` كان في السابق موروثاً من صلاحية ``settings`` على مستوى الخادم؛
يُمنح الآن قسماً مستقلاً بنفس مستوى الوصول تماماً (المدير/المشرف/المشاهد).
"""

from django.db import migrations

NEW_SECTION_KEYS = ["audit"]


def _preset_for(role):
    from sale_sessions.sections import ROLE_PRESETS

    return ROLE_PRESETS.get(role, ROLE_PRESETS["custom"])


def _section_entry(section, preset):
    entry = {a: bool(preset["permissions"].get(section["key"], {}).get(a)) for a in section["actions"]}
    windows = preset["permissions"].get(section["key"], {}).get("windows")
    if section.get("windows"):
        entry["windows"] = list(windows) if isinstance(windows, list) else [w["key"] for w in section["windows"]]
    return entry


def sync_sections(apps, schema_editor):
    from sale_sessions.sections import SECTIONS

    Employee = apps.get_model("sale_sessions", "Employee")
    by_key = {s["key"]: s for s in SECTIONS}
    for employee in Employee.objects.all().iterator():
        perms = employee.permissions if isinstance(employee.permissions, dict) else {}
        preset = _preset_for(employee.role)
        changed = False
        for key in NEW_SECTION_KEYS:
            if key not in perms:
                section = by_key.get(key)
                if section:
                    perms[key] = _section_entry(section, preset)
                    changed = True
        if changed:
            employee.permissions = perms
            employee.save(update_fields=["permissions"])


def unsync_sections(apps, schema_editor):
    Employee = apps.get_model("sale_sessions", "Employee")
    for employee in Employee.objects.all().iterator():
        perms = employee.permissions if isinstance(employee.permissions, dict) else {}
        changed = False
        for key in NEW_SECTION_KEYS:
            if key in perms:
                perms.pop(key, None)
                changed = True
        if changed:
            employee.permissions = perms
            employee.save(update_fields=["permissions"])


class Migration(migrations.Migration):

    dependencies = [
        ("sale_sessions", "0024_payroll_section_permissions"),
    ]

    operations = [
        migrations.RunPython(sync_sections, unsync_sections),
    ]
