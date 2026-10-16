from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("accounting", "0003_payroll_accounts")]

    operations = [
        migrations.AlterField(
            model_name="journalentry",
            name="source",
            field=models.CharField(
                choices=[
                    ("manual", "قيد يدوي"),
                    ("session", "إغلاق وردية بيع"),
                    ("purchase", "عمليات الموردين"),
                    ("expense", "مصروف"),
                    ("partner", "عملية شريك"),
                    ("closing", "قيد إقفال دوري"),
                    ("payroll", "مسيّر رواتب"),
                    ("salary_advance", "سلفة راتب"),
                    ("settlement", "دفعة تسوية مالية"),
                ],
                default="manual",
                max_length=15,
                verbose_name="المصدر",
            ),
        )
    ]
