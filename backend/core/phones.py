"""أرقامُ الهاتف: هويّتُها أرقامُها، وما سواها رسمٌ لا يُقارَن به."""

import re

from django.db.models import Q

#: فواصلٌ تُكتب بين الأرقام ولا تغيّر صاحب الرقم.
_SEPARATORS = re.compile(r"[\s\-_()]+")

#: أقصرُ ما يُقارَن به عند السؤال عن زبون. أربعةُ أرقامٍ تطابق آلافَ
#: السجلّات، والجوابُ عندئذٍ ليس «غيرُ موجود» بل «لا أعرف» — وهو أسوأُ من
#: الصمت. وكشفُ التكرار لا يحتجب إلى هذا القصر؛ فالطبق فيه عند الرسم واقع، والمطلوب أشد.
MIN_MATCH_DIGITS = 7


def normalize_phone(value):
    """تجريد ما ليس يرقماً: «0565 555-555» و«0565555555» رقمٌ واحد."""
    return _SEPARATORS.sub("", value or "")


def phone_regex(phone, min_digits=MIN_MATCH_DIGITS):
    """نمطٌ يطابق الرقمَ مكتوباً بأرقامه، بأية فواصلٍ بينهما، أو لا شيء.

    ذيلُ الرقم المخزَّن ليس ذيلَه: «0565-555-555» تنتهي «555» لا «5555».
    فالسؤالُ عن أربعةِ أرقامٍ من آخره سؤالٌ خاطئٌ لا اختبارُ أضيق. أمّا
    النمطُ فيكتب الرقمَ كاملاً ويُجيز لكلِّ ما ليس رقماً أن يقف بين رقمين،
    وهو شرطُ التجريد نفسُه لا تقريبٌ عليه.

    والقصْرُ على `min_digits` ليس شرطَ صحّةٍ بل قصرُ امتناع: النمطُ لا يخطئ
    ولا يطابق إلا الرقمَ نفسَه، لكنه قد يجيبُ عن سؤالٍ لم يُسأل كاملاً.
    فمن يبحث عن زبونٍ بأربعةِ أرقامٍ لم يُرِد إلا «لا أعرف»، ومن يكشف
    التكرار يريد الجوابَ كاملاً فيرفع القصرَ عنه.
    """
    digits = normalize_phone(phone)
    if len(digits) < min_digits or not digits.isdigit():
        return None
    return r"^\D*" + r"\D*".join(digits) + r"\D*$"


def find_by_phone(qs, phone, field="phone", min_digits=MIN_MATCH_DIGITS):
    """يُصفّي `qs` على الرقم: كما كُتب أوّلاً، ثم بأرقامه إن أخطأ الرسم.

    المطابقةُ التامةُ أوّلاً لأنها المفهرسة والأدقّ. فإن لم تصب — والكاتبُ
    يكتب الرقمَ كما يذكره لا كما حُفظ — بقي النمطُ، فيجد الزبونَ برقمٍ
    كُتبت فواصلُه أو خُففت. انظر `phone_regex` لسبب القصر وحدوده.
    """
    if not phone:
        return qs.none()
    exact = qs.filter(**{field: phone})
    if exact.exists():
        return exact
    pattern = phone_regex(phone, min_digits=min_digits)
    if pattern is None:
        return qs.none()
    return qs.filter(Q(**{f"{field}__isnull": False, f"{field}__regex": pattern}))
