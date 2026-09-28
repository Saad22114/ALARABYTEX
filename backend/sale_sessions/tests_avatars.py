"""اختبارات التحقّق من الصورة الشخصية — `validate_avatar_image` في sale_sessions.avatars."""

import base64

from django.test import SimpleTestCase

from .avatars import (
    ALLOWED_AVATAR_IMAGE_TYPES,
    MAX_AVATAR_IMAGE_BYTES,
    MAX_AVATAR_IMAGE_CHARS,
    validate_avatar_image,
)

# صور صالحة 1×1 لكل نوع مدعوم
PNG_1PX = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
GIF_1PX = "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
# JPEG مُنتَج فعلياً (SOI ثم بايتات) — للتحقّق من التوقيع
JPEG_FAKE = "\xff\xd8\xff\xe0" + "\x00" * 32

# WebP = RIFF + حجم + WEBP
WEBP_1PX = base64.b64encode(
    b"RIFF" + (8).to_bytes(4, "little") + b"WEBP" + b"\x00" * 8
).decode()


def data_url(mime: str, raw_b64: str) -> str:
    return f"data:{mime};base64,{raw_b64}"


class ValidateAvatarImageTest(SimpleTestCase):
    def test_accepts_png(self):
        value, error = validate_avatar_image(data_url("image/png", PNG_1PX))
        self.assertEqual(error, "")
        self.assertTrue(value.startswith("data:image/png;base64,"))

    def test_accepts_gif_bytes_rejected_as_unsupported_type(self):
        # GIF غير في الأنواع المسموحة — حتى لو كان ملفاً حقيقياً
        _, error = validate_avatar_image(data_url("image/gif", GIF_1PX))
        self.assertIn("غير مدعومة", error)

    def test_accepts_jpeg_magic(self):
        raw = base64.b64encode(JPEG_FAKE.encode("latin-1")).decode()
        _, error = validate_avatar_image(data_url("image/jpeg", raw))
        self.assertEqual(error, "")

    def test_accepts_webp_magic(self):
        _, error = validate_avatar_image(data_url("image/webp", WEBP_1PX))
        self.assertEqual(error, "")

    def test_rejects_non_image_mime(self):
        _, error = validate_avatar_image(data_url("text/html", "PHNjcmlwdD4="))
        self.assertIn("غير مدعومة", error)

    def test_rejects_svg_mime(self):
        _, error = validate_avatar_image(
            data_url("image/svg+xml", "PHN2Zy8+")
        )
        self.assertIn("غير مدعومة", error)

    def test_rejects_plain_url(self):
        _, error = validate_avatar_image("https://example.com/a.png")
        self.assertIn("غير مدعومة", error)

    def test_rejects_non_data_url(self):
        _, error = validate_avatar_image("data:image/png,notbase64")
        self.assertIn("غير مدعومة", error)

    def test_rejects_empty_string(self):
        _, error = validate_avatar_image("")
        self.assertTrue(error)

    def test_rejects_whitespace_only(self):
        _, error = validate_avatar_image("   ")
        self.assertTrue(error)

    def test_rejects_none(self):
        _, error = validate_avatar_image(None)
        self.assertIn("غير مدعومة", error)

    def test_rejects_non_string(self):
        _, error = validate_avatar_image(12345)
        self.assertIn("غير مدعومة", error)

    def test_rejects_oversized_payload(self):
        payload = data_url("image/png", "A" * (MAX_AVATAR_IMAGE_CHARS + 10))
        _, error = validate_avatar_image(payload)
        self.assertIn("كبير", error)

    def test_rejects_decoded_size_over_limit(self):
        # نص ضمن حدّ الأرقام لكن فك الترميز يتجاوز حدّ البايتات
        # (نقرب لأعلى مضاعف 4 حتى يمرّ فك base64 ولا يُرفض كبيانات تالفة)
        decoded = MAX_AVATAR_IMAGE_BYTES + 1024
        raw = "A" * (((decoded + 2) // 3) * 4)
        self.assertEqual(len(raw) % 4, 0)
        _, error = validate_avatar_image(data_url("image/png", raw))
        self.assertIn("كبير", error)

    def test_rejects_magic_mismatch_png_declared_but_html_content(self):
        raw = base64.b64encode(b"<script>alert(1)</script>").decode()
        _, error = validate_avatar_image(data_url("image/png", raw))
        self.assertIn("تالف", error)

    def test_rejects_magic_mismatch_jpeg_declared_but_png_content(self):
        _, error = validate_avatar_image(data_url("image/jpeg", PNG_1PX))
        self.assertIn("تالف", error)

    def test_rejects_webp_with_wrong_signature(self):
        raw = base64.b64encode(b"RIFF" + b"\x00" * 4 + b"XXXX" + b"\x00" * 8).decode()
        _, error = validate_avatar_image(data_url("image/webp", raw))
        self.assertIn("تالف", error)

    def test_rejects_invalid_base64(self):
        _, error = validate_avatar_image("data:image/png;base64,!!!nope!!!")
        self.assertTrue(error)

    def test_rejects_base64_bad_length(self):
        _, error = validate_avatar_image("data:image/png;base64,QUJD Q")
        self.assertTrue(error)

    def test_tolerates_whitespace_and_newlines_in_base64(self):
        wrapped = "\n".join(
            [PNG_1PX[i : i + 20] for i in range(0, len(PNG_1PX), 20)]
        )
        _, error = validate_avatar_image(data_url("image/png", wrapped))
        self.assertEqual(error, "")

    def test_tolerates_surrounding_whitespace(self):
        _, error = validate_avatar_image(f"  {data_url('image/png', PNG_1PX)}\n")
        self.assertEqual(error, "")

    def test_rejects_uppercase_mime(self):
        # الأنماط المسموحة في الخادم lowercase — لا نقبل أحرفاً كبيرة
        _, error = validate_avatar_image(f"data:image/PNG;base64,{PNG_1PX}")
        self.assertTrue(error)

    def test_all_allowed_types_are_reachable(self):
        self.assertEqual(
            set(ALLOWED_AVATAR_IMAGE_TYPES),
            {"image/jpeg", "image/png", "image/webp"},
        )
