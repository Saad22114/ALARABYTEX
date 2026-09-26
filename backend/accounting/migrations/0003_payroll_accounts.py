"""حسابات الرواتب والسلف لنظام قائم (شجرة حسابات أُنشئت قبل إضافة الرواتب)."""

from django.db import migrations

EXTRA = [
    ("1105", "سلف الموظفين", "asset", "11", "ADVANCE_RECEIVABLE"),
    ("5501", "مصروف الرواتب", "expense", "5", "SALARY_EXPENSE"),
]


def add_accounts(apps, schema_editor):
    Account = apps.get_model("accounting", "Account")
    if not Account.objects.exists():
        return
    for code, name, type_, parent_code, source_key in EXTRA:
        if Account.objects.filter(source_key=source_key).exists():
            continue
        parent = Account.objects.filter(code=parent_code).first() if parent_code else None
        final_code = code
        guard = 0
        while Account.objects.filter(code=final_code).exists() and guard < 50:
            guard += 1
            final_code = f"{code}{guard}"
        Account.objects.create(
            code=final_code,
            name=name,
            type=type_,
            parent=parent,
            source_key=source_key,
            is_system=True,
        )


def remove_accounts(apps, schema_editor):
    Account = apps.get_model("accounting", "Account")
    for _, _, _, _, source_key in EXTRA:
        Account.objects.filter(source_key=source_key).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounting", "0002_alter_journalentry_source"),
    ]

    operations = [
        migrations.RunPython(add_accounts, remove_accounts),
    ]
