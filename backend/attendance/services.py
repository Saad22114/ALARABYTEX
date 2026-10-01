"""سجل الحضور والانصراف — ما يُكتب، وكيف يُشتقّ.

القاعدة التي يحكم هذا الملف كلّه: **لا يُكتب رقمٌ يشتقّ من غيره**.
التأخير والانصراف المبكر والساعات الإضافية تُحسب من لحظة الدخول
ولحظة الخروج لحظةَ الحساب، لا بتخزينها بجانبها. لو خُزّنت لتضطرب كلها مع
تعديل واحدٍ في الساعة المرجعية، ولأصبح 질문 «متى حُسب هذا؟» بلا جواب.

فالعملية كلها في دالّةٍ واحدة: ``recompute``.
"""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from .models import AttendancePolicy, AttendanceRecord

#: منطقة التوقيت التي تُحسب بها النوافذ.
#:
#: التوقيت ساعةٌ واحدة لا يفصلها، وهي بالضبط ما يجعل «نافذة الدخول
#: 09:00» تعني تسعاً أو ثمانياً حسب الخادم. فنحسب دائماً بالتوقيت
#: المحليّ، ونخزّن UTC كما يفعل Django، فلا يقع الحساب في نصف ساعة.
LOCAL_TZ = ZoneInfo("Asia/Muscat")

#: الجمعة في ترقيم ``date.weekday()``. ثابتٌ واحد لا يُكتب رقماً في
#: موضعين: Policy.load() يضعه افتراضياً، وis_working_day يفهمه.
FRIDAY = 4


def local_now():
    return timezone.now().astimezone(LOCAL_TZ)


def _as_local(moment):
    if moment is None:
        return None
    if timezone.is_naive(moment):
        return timezone.make_aware(moment, LOCAL_TZ)
    return moment.astimezone(LOCAL_TZ)


def business_date(moment, policy=None):
    """اليومُ الذي ينتمي إليه هذا الوقت.

    من يعمل ورديةً قبل فجر يومه هذا هو في يومه، لا في الغد: وردية تبدأ
    منتصف الليل نُنسبت لضبطتها ليجدها في تقرير يومها هي. عتبةُ الفجر هي
    الفرق، ولهذا هي إعدادٌ في السياسة لا ثابتٌ في الكود.
    """
    policy = policy or AttendancePolicy.load()
    local = _as_local(moment)
    if local.hour < policy.day_cutoff_hour:
        return local.date() - timedelta(days=1)
    return local.date()


def _minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def _day_minutes(moment: datetime) -> int:
    return moment.hour * 60 + moment.minute


def is_working_day(day, policy=None):
    """هل هذا اليومٌ من أيام العمل؟ عطلةُ الأسبوع ليست غياباً.

    ترقيم الأيام هنا هو ترتيب ``date.weekday()`` لا غير: الاثنين صفر
    والجمعة أربعة والأحد ستّة. أي ترقيمٍ آخر يجعل رقمة العطلة تقرأ يومَ
    عمل، فلا يظهر الغياب ولا يُحتسب — أسوأ من خطأٍ ظاهر.
    """
    policy = policy or AttendancePolicy.load()
    # لا بديل هنا لـ ``or [FRIDAY]``: القائمة الفارغة اختيارٌ مقصود
    # («لا عطلة أسبوعية»)، ولو عُوّضت هنا لأصبح كل من أراها فارغة —
    # أي من مسحها بالنقر — مقيَّداً بيومِ راحةٍ لم يطلبه.
    return day.weekday() not in (policy.weekend_days or [])


@transaction.atomic
def recompute(record, policy=None):
    """يُعيد اشتقاق كل ما يُشتقّ من دخول الموظف وخروجه.

    دالّةٌ واحدة تحسب كل شيء، وكل من يستدعيها يسألها بدل أن يحسب. لو
    تشعّبت الحساب على ثلاثة مواضع — الشاشة والتقرير والخدمة — لاختلفت
    في واحدٍ منها، وصار للتأخير رقمٌ بلا مصدر.

    القواعد، بالترتيب الذي يهمّ:

    - **التأخير** يُقاس على نهاية نافذة الدخول، لا على بدايتها. من جاء
      قبل الدوام لا يتأخّر، ومن جاء بعد نهايته يتأخّر ولو سبع دقائق.
    - **السماح** يُطرح من التأخير *و* الانصراف المبكر معاً: خمس دقائق
      متأخرة لا تستحقّ خصماً، ولا تستحقّ أن تُحاسَب عليها مرّتين.
    - **ساعات العمل** تُقاس بين اللحظتين، ولا تُحسب قبل الخروج: سطرٌ
      مفتوحٌ ساعتُه «مجهولة» لا «صفر»، وإلا بدا من لم يدخل كأنه غاب.
    - **الإضافي** ما زاد على طول يوم العمل، لا ما تأخّر به: من يعمل إلى
      الواحدة وأول نافذةِ خروجه الثانية يستحقّ ساعتين إضافيتين إن تأخّر
      ساعتين، وإلا صار التأخيرُ مكرماً.
    """
    policy = policy or AttendancePolicy.load()
    login_at = _as_local(record.login_at)
    logout_at = _as_local(record.logout_at)

    record.late_minutes = 0
    record.early_leave_minutes = 0
    record.overtime_minutes = 0
    record.worked_minutes = None

    if login_at is not None:
        late = _day_minutes(login_at) - _minutes(policy.login_window_end)
        record.late_minutes = max(0, late - policy.grace_minutes)

    if logout_at is not None:
        early = _minutes(policy.logout_window_start) - _day_minutes(logout_at)
        record.early_leave_minutes = max(0, early - policy.grace_minutes)

    if login_at is not None and logout_at is not None:
        minutes = int((logout_at - login_at).total_seconds() // 60)
        # الخروج قبل الدخول ليس «صفر دقيقة»، بل خطأٌ في الإدخال. نُصفّره
        # لأن الأرقام السالبة تنتشر في كل تقرير يُبنى عليها.
        record.worked_minutes = max(0, minutes)
        record.overtime_minutes = max(0, record.worked_minutes - policy.workday_minutes)

    if record.excuse != AttendanceRecord.Excuse.NONE:
        record.status = AttendanceRecord.Status.EXCUSED
    elif login_at is None:
        record.status = AttendanceRecord.Status.ABSENT
    elif logout_at is None:
        record.status = (
            AttendanceRecord.Status.LATE
            if record.late_minutes > 0
            else AttendanceRecord.Status.INSIDE
        )
    elif record.late_minutes > 0:
        record.status = AttendanceRecord.Status.LATE
    elif record.early_leave_minutes > 0:
        record.status = AttendanceRecord.Status.EARLY_LEAVE
    else:
        record.status = AttendanceRecord.Status.PRESENT

    record.save()
    return record


def _record_for(employee, day, policy=None):
    record, _created = AttendanceRecord.objects.get_or_create(
        employee=employee, date=day,
        defaults={"source": AttendanceRecord.Source.AUTO},
    )
    return record


@transaction.atomic
def record_login(employee, when=None, policy=None):
    """يفتح سطر اليوم عند دخول الموظف. يُستدعى من نقطة الدخول نفسها.

    الدخول الثاني في اليوم نفسه لا يطرد الأول: لو نُسي أن يخرج الموظف
    وعاد في المساء، فالأصحّ أن يبقى سطرُه مفتوحاً من أوّل دخول، لا أن
    يضيع عمله الأولى بين سجلّين.
    """
    policy = policy or AttendancePolicy.load()
    if not policy.enabled:
        return None
    moment = when or local_now()
    record = _record_for(employee, business_date(moment, policy), policy)
    if record.login_at is None:
        record.login_at = moment
    if record.source == AttendanceRecord.Source.MANUAL:
        # سطرٌ كتبه المدير يدوياً لا يُطمس بدخولٍ آلي.
        record.login_at = record.login_at or moment
    else:
        record.source = AttendanceRecord.Source.AUTO
    recompute(record, policy)
    return record


@transaction.atomic
def record_logout(employee, when=None, policy=None):
    """يغلق سطر اليوم عند خروج الموظف. يُستدعى من نقطة الخروج نفسها.

    الخروج بلا دخولٍ لا يُنشئ سطراً: سجلٌّ «خرج ولم يدخل» ليس انصرافاً،
    بل خطأٌ في بيانات الدخول، فلا نملأ الغياب استنتاجاً.
    """
    policy = policy or AttendancePolicy.load()
    if not policy.enabled:
        return None
    moment = when or local_now()
    record = AttendanceRecord.objects.filter(
        employee=employee, date=business_date(moment, policy),
    ).first()
    if record is None or record.login_at is None:
        return None
    if record.logout_at is None:
        record.logout_at = moment
    recompute(record, policy)
    return record


def open_sessions(employee=None):
    """من لم يخرج بعد: السطر المفتوح دليلُ حضورٍ لا دليلُ غياب."""
    qs = AttendanceRecord.objects.filter(
        login_at__isnull=False, logout_at__isnull=True,
    ).select_related("employee")
    if employee is not None:
        qs = qs.filter(employee=employee)
    return qs


#: تُحسب خارج الحقل عمداً: نسبةٌ من الدقائق تعطي رقماً كسرياً، والدقيقة
#: وحدةٌ لا تُقسَّم. ثلاثة عشر يوماً ونصف يومٍ لا غلطٌ حسابيّ بل وحدةٌ
#: خاطئة: تقرّبها الراتبُ إلى نصف يوم فتُحرّف الإجمالي.
def half_day_round(minutes: int) -> float:
    """تقرّب الساعات إلى أقرب نصف يوم — كما يفعل مسيّر الرواتب."""
    from decimal import Decimal

    day = Decimal(minutes) / Decimal(60 * 8)
    return float((day * 2).quantize(Decimal("1")) / 2)


def day_sheet(day, employees, policy=None):
    """ورقةُ اليوم: صفٌّ لكل موظف — حاضراً كان أو غائباً.

    الغياب حالةٌ لازمة في الجدول، لا سطرٌ ناقص. الورقة تُبنى
    من السجلات فقط إظهارُ الغياب مستحيل، لأن الغائب ليس له سطر. فمن
    يُقاس بالغياب يحتاج سطراً لكل موظف في كل يوم، حتى لو كان فارغاً.
    """
    policy = policy or AttendancePolicy.load()
    records = {
        record.employee_id: record
        for record in AttendanceRecord.objects.filter(date=day)
    }
    working = is_working_day(day, policy)
    rows = []
    for employee in employees:
        record = records.get(employee.pk)
        if record is None:
            status = (
                AttendanceRecord.Status.ABSENT.value
                if working
                else AttendanceRecord.Status.OFF.value
            )
            record = AttendanceRecord(
                employee=employee, date=day, status=status, working_day=working,
            )
        rows.append(record)
    return rows


def summarize(records, policy=None):
    """أرقامُ الشهر في سطر: أيام، ودقائق، وعدد مرّات."""
    policy = policy or AttendancePolicy.load()
    return {
        "days": len({r.date for r in records}),
        "present": sum(
            1 for r in records
            if r.status in (
                AttendanceRecord.Status.PRESENT,
                AttendanceRecord.Status.LATE,
                AttendanceRecord.Status.EARLY_LEAVE,
                AttendanceRecord.Status.INSIDE,
            )
        ),
        "absent": sum(1 for r in records if r.status == AttendanceRecord.Status.ABSENT),
        "excused": sum(1 for r in records if r.status == AttendanceRecord.Status.EXCUSED),
        "late_count": sum(1 for r in records if r.late_minutes > 0),
        "late_minutes": sum(r.late_minutes for r in records),
        "early_count": sum(1 for r in records if r.early_leave_minutes > 0),
        "early_minutes": sum(r.early_leave_minutes for r in records),
        "worked_minutes": sum(r.worked_minutes or 0 for r in records),
        "overtime_minutes": sum(r.overtime_minutes for r in records),
        "open_sessions": sum(
            1 for r in records if r.login_at is not None and r.logout_at is None
        ),
        "expected_minutes": policy.workday_minutes * len(
            [r for r in records if is_working_day(r.date, policy)]
        ),
    }