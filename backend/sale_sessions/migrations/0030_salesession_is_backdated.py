from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sale_sessions", "0029_employee_theme"),
    ]

    operations = [
        migrations.AddField(
            model_name="salesession",
            name="is_backdated",
            field=models.BooleanField(
                default=False,
                help_text="تبقى مفتوحة حتى الإغلاق اليدوي ولا تُغلق فوراً ضمن إغلاق الورديات المنسية",
                verbose_name="وردية بتاريخ سابق أُنشئت يدوياً",
            ),
        ),
    ]
