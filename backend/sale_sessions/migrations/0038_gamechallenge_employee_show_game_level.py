from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("sale_sessions", "0037_math_levels"),
    ]

    operations = [
        migrations.AddField(
            model_name="employee",
            name="show_game_level",
            field=models.BooleanField(default=False, verbose_name="إظهار نقاط الفوز في الألعاب للموظفين"),
        ),
        migrations.CreateModel(
            name="GameChallenge",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")),
                ("game", models.CharField(choices=[("tic_tac_toe", "إكس-أو"), ("rock_paper_scissors", "حجر ورقة مقص"), ("number_guess", "تحدي الرقم"), ("memory_sequence", "تحدي الذاكرة"), ("seega", "سيجا"), ("math_levels", "تحدي الحساب")], max_length=30, verbose_name="اللعبة")),
                ("status", models.CharField(choices=[("pending", "بانتظار الرد"), ("accepted", "مقبول"), ("declined", "مرفوض")], default="pending", max_length=10, verbose_name="الحالة")),
                ("opponent", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="received_game_challenges", to="sale_sessions.employee", verbose_name="الموظف المدعو")),
                ("requester", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sent_game_challenges", to="sale_sessions.employee", verbose_name="مرسل الطلب")),
            ],
            options={"verbose_name": "طلب تحدي لعبة", "verbose_name_plural": "طلبات تحديات الألعاب", "ordering": ["-created_at", "-id"]},
        ),
    ]
