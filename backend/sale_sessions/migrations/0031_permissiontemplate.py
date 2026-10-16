from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sale_sessions", "0030_salesession_is_backdated"),
    ]

    operations = [
        migrations.CreateModel(
            name="PermissionTemplate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")),
                ("name", models.CharField(max_length=100, unique=True, verbose_name="اسم القالب")),
                ("role", models.CharField(choices=[("admin", "مدير النظام"), ("supervisor", "مشرف"), ("sales", "مندوب مبيعات"), ("accountant", "محاسب"), ("viewer", "مشاهد"), ("custom", "مخصص")], default="custom", max_length=20)),
                ("permissions", models.JSONField(blank=True, default=dict)),
                ("hidden_sections", models.JSONField(blank=True, default=list)),
                ("allowed_branches", models.JSONField(blank=True, default=list)),
            ],
            options={
                "verbose_name": "قالب صلاحيات",
                "verbose_name_plural": "قوالب الصلاحيات",
                "ordering": ["name"],
            },
        ),
    ]
