from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("sale_sessions", "0033_supplier_fabric_sales_window"),
    ]

    operations = [
        migrations.CreateModel(
            name="GameResult",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")),
                ("employee_name", models.CharField(max_length=150, verbose_name="اسم الموظف")),
                ("game", models.CharField(choices=[("tic_tac_toe", "إكس-أو"), ("rock_paper_scissors", "حجر ورقة مقص")], max_length=30, verbose_name="اللعبة")),
                ("outcome", models.CharField(choices=[("win", "فوز"), ("loss", "خسارة"), ("draw", "تعادل")], max_length=10, verbose_name="النتيجة")),
                ("difficulty", models.CharField(choices=[("easy", "سهل"), ("medium", "متوسط"), ("hard", "صعب")], max_length=10, verbose_name="الصعوبة")),
                ("employee", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="game_results", to="sale_sessions.employee", verbose_name="الموظف")),
            ],
            options={
                "verbose_name": "نتيجة لعبة",
                "verbose_name_plural": "نتائج الألعاب",
                "ordering": ["-created_at", "-id"],
            },
        ),
    ]

