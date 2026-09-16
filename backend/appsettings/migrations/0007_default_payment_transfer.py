from django.db import migrations, models


def set_default_payment_transfer(apps, schema_editor):
    AppSettings = apps.get_model("appsettings", "AppSettings")
    AppSettings.objects.update(default_payment_method="transfer")


class Migration(migrations.Migration):

    dependencies = [
        ("appsettings", "0006_appsettings_logo"),
    ]

    operations = [
        migrations.AlterField(
            model_name="appsettings",
            name="default_payment_method",
            field=models.CharField(
                max_length=10,
                default="transfer",
                choices=[("cash", "كاش"), ("transfer", "تحويل"), ("card", "ماكينة")],
                verbose_name="طريقة الدفع الافتراضية",
                help_text="تُحدَّد تلقائياً عند إضافة بند جديد للوردية",
            ),
        ),
        migrations.RunPython(set_default_payment_transfer, migrations.RunPython.noop),
    ]