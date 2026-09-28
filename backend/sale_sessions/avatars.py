"""الأفاتارات الجاهزة للموظفين — رموز تعبيرية تظهر داخل دوائر ملونة.

القاعدة المهمة:
- أول 16 رمزاً**محجوزة** (ترتيباً ومحتوى) — لا تغيّرها: تعتمد عليها اختباراتٌ قائمة.
- إجمالي القائمة = **30 رمزاً** متنوّعاً (حيوانات، طيور، بحر، وجوه، قلوب، طبيعة/فضاء).
- أي قيمة خارج هذه القائمة تُرفض من الخادم (`AccountAvatarView`).
- لكن الحقل `avatar_image` (صورة من جهاز المستخدم) يُقبل عبر نفس الـ endpoint
  بمفتاح `avatar_image` منفصل — راجع `validate_avatar_image`.

بالإضافة إلى الرموز، يدعم النظام **الصورة الشخصية**: صورة يرفعها الموظف من جهازه
تُخزَّن كـ data URL في `Employee.avatar_image` وتُعرض بدل الأفاتار. تتحقّق منها
`validate_avatar_image` هنا (نوع صورة حقيقي + حجم محدود) قبل أي حفظ.
"""

import base64
import binascii
import re

AVATAR_EMOJI = [
    # ——— المجموعة الأصلية المحجوزة (16) ———
    "🦁", "🐯", "🐻", "🐼",
    "🐨", "🐸", "🐙", "🦊",
    "🐺", "🦄", "🐧", "🦉",
    "🐵", "🐳", "🦋", "🐢",
    # ——— المجموعة الجديدة (14) — ميكس بين كل الأنواع ———
    # طيور
    "🦅", "🦚", "🦩",
    # بحر
    "🦈", "🐠", "🦑",
    # وجوه
    "😺", "🤓", "😎", "🥳",
    # قلوب
    "❤️", "💙",
    # طبيعة / فضاء
    "🍀", "🪐",
]

# ——— الصورة الشخصية (مرفوعة من جهاز الموظف) ———
ALLOWED_AVATAR_IMAGE_TYPES = ("image/jpeg", "image/png", "image/webp")
# 64 كيلوبايت بعد فك ترميز base64 — تكفي لصورة مربّعة 256px مضغوطة بجودة جيدة.
MAX_AVATAR_IMAGE_BYTES = 64 * 1024
# حدّ على طول النص قبل فك الترميز (base64 يتمدّد ~4/3 + بادئة data URL).
MAX_AVATAR_IMAGE_CHARS = 120_000
# حدّ أعلى لحجم جسم الطلب الوارد — أكبر من الصورة المسموحة بهامش يكفي لـ JSON.
MAX_AVATAR_REQUEST_BYTES = MAX_AVATAR_IMAGE_CHARS + 8192

_DATA_URL_RE = re.compile(
    r"^data:(?P<mime>image/[a-z0-9.+-]+);base64,(?P<data>[A-Za-z0-9+/=\s]+)$"
)

# الترويسات السحرية (magic numbers) لكل نوع مدعوم.
_MAGIC_NUMBERS = {
    "image/jpeg": (b"\xff\xd8\xff", b""),
    "image/png": (b"\x89PNG\r\n\x1a\n", b""),
    # البايتات 8-11 في ملف WebP يجب أن تحمل التوقيع WEBP
    "image/webp": (b"RIFF", b"WEBP"),
}

_BAD_TYPE = "صيغة الصورة غير مدعومة — ارفع صورة JPEG أو PNG أو WebP"
_BAD_DATA = "ملف الصورة تالف أو ليس صورة صالحة"
_TOO_BIG = "حجم الصورة كبير جداً — اختر صورة أص"


def _matches_magic(blob: bytes, mime: str) -> bool:
    """هل يطابق محتوى الملف فعلياً النوع المعلن في data URL؟"""
    signature = _MAGIC_NUMBERS.get(mime)
    if not signature or not blob.startswith(signature[0]):
        return False
    if signature[1] and blob[8:12] != signature[1]:
        return False
    return True


def validate_avatar_image(value):
    """التحقّق من صورة شخصية مرفوعة كـ data URL.

    يرجع ``(value, "")`` عند الصلاحية، أو ``(None, رسالة_الخطأ)`` عند الرفض.
    لا يُقبل إلا JPEG/PNG/WebP بحجم محدود، ويجب أن يطابق محتوى الملف نوعه
    المعلن حتى لا يُخزَّن ملف تنفيذي على هيئة صورة.
    """
    if not isinstance(value, str):
        return None, _BAD_TYPE
    value = value.strip()
    if not value:
        return None, _BAD_DATA
    if len(value) > MAX_AVATAR_IMAGE_CHARS:
        return None, _TOO_BIG

    match = _DATA_URL_RE.match(value)
    if not match:
        return None, _BAD_TYPE

    mime = match.group("mime").lower()
    if mime not in ALLOWED_AVATAR_IMAGE_TYPES:
        return None, _BAD_TYPE

    raw = re.sub(r"\s+", "", match.group("data"))
    if not raw or len(raw) % 4:
        return None, _BAD_DATA
    try:
        blob = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError):
        return None, _BAD_DATA

    if not blob or len(blob) > MAX_AVATAR_IMAGE_BYTES:
        return None, _TOO_BIG
    if not _matches_magic(blob, mime):
        return None, _BAD_DATA

    return value, ""
