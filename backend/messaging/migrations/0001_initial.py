import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("sale_sessions", "__first__"),
    ]

    operations = [
        migrations.CreateModel(
            name="Message",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")),
                ("body", models.TextField(verbose_name="النص")),
                ("read_at", models.DateTimeField(blank=True, null=True, verbose_name="وقت القراءة")),
                (
                    "sender",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sent_messages",
                        to="sale_sessions.employee",
                        verbose_name="المرسل",
                    ),
                ),
                (
                    "receiver",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="received_messages",
                        to="sale_sessions.employee",
                        verbose_name="المستلم",
                    ),
                ),
            ],
            options={
                "verbose_name": "رسالة",
                "verbose_name_plural": "الرسائل",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["sender", "receiver"], name="messaging_m_sender__ca4e27_idx"),
                    models.Index(fields=["receiver", "read_at"], name="messaging_m_receive_f45464_idx"),
                ],
            },
        ),
    ]