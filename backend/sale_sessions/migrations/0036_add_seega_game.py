from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sale_sessions", "0035_expand_game_choices"),
    ]

    operations = [
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
                ],
                max_length=30,
                verbose_name="اللعبة",
            ),
        ),
    ]
