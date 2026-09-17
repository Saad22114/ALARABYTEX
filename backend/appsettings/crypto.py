import base64
import json
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ENVELOPE_FORMAT = "qomash-backup"
ENVELOPE_VERSION = 1
KDF_ITERATIONS = 200_000
SALT_SIZE = 16
NONCE_SIZE = 12
KEY_SIZE = 32


class BackupCryptoError(Exception):
    """Raised when a backup cannot be decrypted."""


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
    if not password:
        raise BackupCryptoError("كلمة المرور غير محددة")
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
        raise BackupCryptoError("هذه النسخة مشفّرة، اضبط كلمة مرور النسخ الاحتياطي أولاً")
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
