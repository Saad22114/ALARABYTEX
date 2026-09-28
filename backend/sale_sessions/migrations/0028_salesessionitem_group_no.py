from django.db import migrations, models
from django.db.models import Max


def backfill_group_no(apps, schema_editor):
    """ترقيم البيعات الموجودة مسبقا داخل كل وردية.

    كل بنود البيعة الواحدة تشترك في `sale_group`، فيحصل أقدم معرّف على 1
    وتُرقَّم كل بنوده بالرقم نفسه. البند بلا معرّف يعود لمرحلة سبقت فكرة
    تجميع البيعات، فكل بند منها بيعة قائمة بحد ذات.
    البيانات القائمة لا تحمل تاريخ محذوفات، فالترقيم المتصل صحيح ولا يفقد
    أي رقم.
    """
    item_model = apps.get_model("sale_sessions", "SaleSessionItem")
    db_alias = schema_editor.connection.alias

    session_ids = (
        item_model.objects.using(db_alias)
        .values_list("session_id", flat=True)
        .distinct()
    )
    for session_id in session_ids.iterator():
        items = list(
            item_model.objects.using(db_alias)
            .filter(session_id=session_id)
            .order_by("id")
            .values_list("id", "sale_group")
        )
        number_by_group = {}
        ids_by_number = {}
        for item_id, sale_group in items:
            key = sale_group or f"single-{item_id}"
            if key not in number_by_group:
                number_by_group[key] = len(number_by_group) + 1
            ids_by_number.setdefault(number_by_group[key], []).append(item_id)
        # تحديث واحد لكل رقم بدل تحديث لكل بند
        for number, ids in ids_by_number.items():
            item_model.objects.using(db_alias).filter(id__in=ids).update(group_no=number)


def set_session_counters(apps, schema_editor):
    """ضبط عدّاد كل وردية ليبدأ بعد أكبر رقم مرقّم فيها."""
    session_model = apps.get_model("sale_sessions", "SaleSession")
    item_model = apps.get_model("sale_sessions", "SaleSessionItem")
    db_alias = schema_editor.connection.alias

    for session in session_model.objects.using(db_alias).all().iterator():
        top = (
            item_model.objects.using(db_alias)
            .filter(session_id=session.id)
            .exclude(group_no=None)
            .aggregate(top=Max("group_no"))["top"]
        )
        session_model.objects.using(db_alias).filter(id=session.id).update(
            next_group_no=(top or 0) + 1
        )


def noop(apps, schema_editor):
    """التراجع يحذف الحقول، فلا بيانات يُعكس ترحيلها."""


class Migration(migrations.Migration):

    dependencies = [
        ("sale_sessions", "0027_machine_account_section_permissions"),
    ]

    operations = [
        migrations.AddField(
            model_name="salesessionitem",
            name="group_no",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="ترتيب البيعة داخل الوردية (الأقدم = 1). يُثبَّت عند الحفظ فلا يعيد الحذف ترقيم ما بعده",
                null=True,
                verbose_name="رقم البيعة",
            ),
        ),
        migrations.AddField(
            model_name="salesession",
            name="next_group_no",
            field=models.PositiveIntegerField(
                default=1,
                help_text="عدّاد ترقيم البيّعات داخل الوردية؛ يزيد فقط فلا تُعاد أرقام بيعات محذوفة",
                verbose_name="رقم البيعة التالي",
            ),
        ),
        migrations.RunPython(backfill_group_no, noop),
        migrations.RunPython(set_session_counters, noop),
    ]
