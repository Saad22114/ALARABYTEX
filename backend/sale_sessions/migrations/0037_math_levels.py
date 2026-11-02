from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sale_sessions", "0036_add_seega_game"),
    ]

    operations = [
        migrations.AddField(
            model_name="gameresult",
            name="level",
            field=models.PositiveIntegerField(default=0, verbose_name="المستوى"),
        ),
        migrations.AlterField(
            model_name="gameresult",
            name="game",
            field=models.CharField(
                choices=[
                    ("tic_tac_toe", "إكس-أو"),
                    ("rock_paper_scissors", "حجر ورقة مقص"),
                    ("number_guess", "تحدي الرقم"),
                    ("memory_sequence", "تحدي الذاكرة"),
                    ("seega", "سيجا"),
                    ("math_levels", "تحدي الحساب"),
                ],
                max_length=30,
                verbose_name="اللعبة",
            ),
        ),
    ]
