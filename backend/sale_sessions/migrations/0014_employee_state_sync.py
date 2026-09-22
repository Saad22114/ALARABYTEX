from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sale_sessions", "0013_employee_address_employee_base_salary_and_more"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE sale_sessions_employee "
                        "ADD COLUMN IF NOT EXISTS address varchar(255) NOT NULL DEFAULT ''"
                    ),
                    reverse_sql=(
                        "ALTER TABLE sale_sessions_employee "
                        "DROP COLUMN IF EXISTS address"
                    ),
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="employee",
                    name="address",
                    field=models.CharField(
                        blank=True, default="", max_length=255, verbose_name="العنوان"
                    ),
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE sale_sessions_employee "
                        "ADD COLUMN IF NOT EXISTS hire_date date NULL"
                    ),
                    reverse_sql=(
                        "ALTER TABLE sale_sessions_employee "
                        "DROP COLUMN IF EXISTS hire_date"
                    ),
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="employee",
                    name="hire_date",
                    field=models.DateField(
                        blank=True, null=True, verbose_name="تاريخ التوظيف"
                    ),
                ),
            ],
        ),
    ]