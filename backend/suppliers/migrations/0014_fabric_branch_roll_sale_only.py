from django.db import migrations, models


def copy_global_setting_to_branches(apps, schema_editor):
    Fabric = apps.get_model("suppliers", "Fabric")
    Branch = apps.get_model("branches", "Branch")
    branch_ids = list(Branch.objects.using(schema_editor.connection.alias).values_list("pk", flat=True))
    fabrics = Fabric.objects.using(schema_editor.connection.alias).all()
    for fabric in fabrics.iterator():
        overrides = dict(fabric.roll_sale_overrides or {})
        for branch_id in branch_ids:
            overrides.setdefault(str(branch_id), bool(fabric.allow_roll_sale))
        Fabric.objects.using(schema_editor.connection.alias).filter(pk=fabric.pk).update(
            roll_sale_overrides=overrides
        )


class Migration(migrations.Migration):
    dependencies = [
        ("branches", "0003_fabricbranchprice_piece_price"),
        ("suppliers", "0013_ledgerentry_settlement_account"),
    ]

    operations = [
        migrations.RunPython(copy_global_setting_to_branches, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="fabric",
            name="allow_roll_sale",
        ),
        migrations.AlterField(
            model_name="fabric",
            name="roll_sale_overrides",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="خريطة رقم الفرع → (true/false) لتحديد السماح ببيع الطاقة لكل فرع على حدة",
                verbose_name="البيع بالطاقة حسب الفرع",
            ),
        ),
    ]
