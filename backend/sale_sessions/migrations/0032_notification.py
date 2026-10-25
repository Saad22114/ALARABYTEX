from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("sale_sessions", "0031_permissiontemplate")]

    operations = [
        migrations.CreateModel(
            name="Notification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")),
                ("kind", models.CharField(max_length=30, verbose_name="النوع")),
                ("title", models.CharField(max_length=180, verbose_name="العنوان")),
                ("body", models.CharField(blank=True, max_length=300, verbose_name="التفاصيل")),
                ("url", models.CharField(blank=True, max_length=300, verbose_name="الرابط")),
                ("read_at", models.DateTimeField(blank=True, null=True, verbose_name="وقت القراءة")),
                ("recipient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notifications", to="sale_sessions.employee", verbose_name="المستلم")),
            ],
            options={"verbose_name": "إشعار", "verbose_name_plural": "الإشعارات", "ordering": ["-created_at", "-id"]},
        ),
    ]
