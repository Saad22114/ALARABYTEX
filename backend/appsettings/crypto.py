import base64
import json
import os
import secrets
import string

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ENVELOPE_FORMAT = "qomash-backup"
ENVELOPE_VERSION = 1
KDF_ITERATIONS = 200_000
SALT_SIZE = 16
NONCE_SIZE = 12
KEY_SIZE = 32

#: أقل طول لكلمة مرور النسخ الاحتياطية. أقل من ثمانية أحرف يجعل المفتاح
#: قابلاً للتخمين بالقوة الغاشمة رغم الـPBKDF2، وأطول دون سبب يُنسى.
MIN_PASSWORD_LENGTH = 8

_PASSWORD_ALPHABET = string.ascii_letters + string.digits


class BackupCryptoError(Exception):
    """Raised when a backup cannot be decrypted."""


class BackupPasswordError(BackupCryptoError):
    """Raised when the backup password is missing or too weak to export with."""


def password_problem(password: str) -> str | None:
    """سبب رفض كلمة المرور بالعربية، أو ``None`` إن كانت صالحة.

    دالة واحدة تحكم صالحتها في موضعين: عند الحفظ في الإعدادات، وعند التصدير.
    تفرّق بينهما فتصير نسخة بلا مفتاح وقتُه يُكتشف متأخراً بعد تصديرها.
    """
    if not password:
        return "كلمة مرور النسخة الاحتياطية مطلوبة — لا تُصدَّر نسخ غير مشفّرة"
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"كلمة مرور النسخة الاحتياطية قصيرة — {MIN_PASSWORD_LENGTH} أحرف على الأقل"
    return None


def _b64encode(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.b64decode(value.encode("ascii"))


def _derive_key(password: str, salt: bytes, iterations: int) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=salt,
        iterations=iterations,
    )
    return kdf.derive(password.encode("utf-8"))


def is_encrypted_envelope(payload: dict) -> bool:
    return bool(
        isinstance(payload, dict)
        and payload.get("format") == ENVELOPE_FORMAT
        and payload.get("encrypted") is True
    )


def encrypt_backup(plaintext: bytes, password: str) -> bytes:
    problem = password_problem(password)
    if problem:
        raise BackupPasswordError(problem)
    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    key = _derive_key(password, salt, KDF_ITERATIONS)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
    envelope = {
        "format": ENVELOPE_FORMAT,
        "encrypted": True,
        "version": ENVELOPE_VERSION,
        "kdf": "pbkdf2-sha256",
        "iterations": KDF_ITERATIONS,
        "cipher": "aes-256-gcm",
        "salt": _b64encode(salt),
        "nonce": _b64encode(nonce),
        "data": _b64encode(ciphertext),
    }
    return json.dumps(envelope, ensure_ascii=False, indent=2).encode("utf-8")


def decrypt_backup(payload: dict, password: str) -> bytes:
    if not password:
        raise BackupCryptoError("هذه النسخة مشفّرة — أدخل كلمة مرور النسخة الاحتياطية")
    try:
        salt = _b64decode(payload["salt"])
        nonce = _b64decode(payload["nonce"])
        ciphertext = _b64decode(payload["data"])
        iterations = int(payload.get("iterations", KDF_ITERATIONS))
    except (KeyError, ValueError, TypeError) as exc:
        raise BackupCryptoError("ملف النسخة الاحتياطية غير صالح") from exc
    key = _derive_key(password, salt, iterations)
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, None)
    except Exception as exc:
        raise BackupCryptoError("كلمة مرور النسخة الاحتياطية غير صحيحة") from exc
