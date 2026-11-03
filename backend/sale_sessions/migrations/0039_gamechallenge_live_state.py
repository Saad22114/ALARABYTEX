from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sale_sessions", "0038_gamechallenge_employee_show_game_level"),
    ]

    operations = [
        migrations.AddField(
            model_name="gamechallenge",
            name="game_state",
            field=models.JSONField(blank=True, default=dict, verbose_name="حالة المباراة"),
        ),
        migrations.AlterField(
            model_name="gamechallenge",
            name="status",
            field=models.CharField(choices=[("pending", "بانتظار الرد"), ("accepted", "مقبول"), ("declined", "مرفوض"), ("completed", "انتهت المباراة")], default="pending", max_length=10, verbose_name="الحالة"),
        ),
    ]
