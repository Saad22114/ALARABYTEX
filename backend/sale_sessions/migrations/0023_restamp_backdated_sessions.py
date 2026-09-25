"""نقل وقت الفتح والإغلاق ووقت الإنشاء إلى تاريخ الوردية المسجَّل.

الورديات التي فُتحت بتاريخ سابق كانت تُحفظ بأوقات فتحها الفعلية، فتظهر في
قائمة الورديات ضمن يوم الإنشاء بدل اليوم المسجَّل، وتُستبعد من فلاتر ذلك اليوم.
بعد ضبط الفتح والإغلاق، نُوحّد السجلات القائمة بنفس القاعدة مع الحفاظ على
الساعة والدقيقة والترتيب داخل اليوم.
"""

from datetime import timedelta

from django.db import migrations
from django.utils import timezone


def restamp_backdated_sessions(apps, schema_editor):
    SaleSession = apps.get_model("sale_sessions", "SaleSession")
    db_alias = schema_editor.connection.alias
    queryset = SaleSession.objects.using(db_alias).all().iterator()
    for session in queryset:
        target = session.session_date
        if target is None and session.is_manual:
            target = session.manual_date
        if target is None or not session.opened_at:
            continue
        delta = target - timezone.localtime(session.opened_at).date()
        if not delta:
            continue
        updates = {
            "opened_at": session.opened_at + delta,
            "created_at": session.created_at + delta,
        }
        if session.closed_at is not None:
            updates["closed_at"] = session.closed_at + delta
        SaleSession.objects.using(db_alias).filter(pk=session.pk).update(**updates)


class Migration(migrations.Migration):

    dependencies = [
        ("sale_sessions", "0022_salesession_session_date_and_card_type_labels"),
    ]

    operations = [
        # لا يمكن استرجاع أوقات الفتح الأصلية بعد النقل
        migrations.RunPython(restamp_backdated_sessions, migrations.RunPython.noop),
    ]
