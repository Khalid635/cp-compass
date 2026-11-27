"""TOTP 2FA helpers (Batch 1 / audit F6): authenticator-app codes +
single-use backup codes. No SMS (costs money per message).

The TOTP secret is stored encrypted with Fernet, keyed by a SHA-256
derivation of SECRET_KEY — a database leak alone does not hand over the
secrets. Backup codes are SHA-256 hashed, like refresh tokens.
"""
import base64
import hashlib
import hmac
import secrets

import pyotp
from cryptography.fernet import Fernet, InvalidToken

from .config import BACKUP_CODE_COUNT, SECRET_KEY, TOTP_ISSUER, TOTP_VALID_WINDOW

_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I confusion


def _fernet() -> Fernet:
    key = hashlib.sha256(b"cp-compass-totp:" + SECRET_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def generate_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(secret: str, email: str) -> str:
    """otpauth:// URI — the frontend renders it as a QR code, and also
    shows the secret for manual entry into the authenticator app."""
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=TOTP_ISSUER)


def verify_code(secret: str, code: str) -> bool:
    code = code.strip().replace(" ", "").replace("-", "")
    if not code.isdigit() or len(code) != 6:
        return False
    try:
        return bool(pyotp.TOTP(secret).verify(code, valid_window=TOTP_VALID_WINDOW))
    except Exception:  # noqa: BLE001 — bad secret/code must not crash
        return False


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode("utf-8")).decode("utf-8")


def decrypt_secret(blob: str) -> str | None:
    try:
        return _fernet().decrypt(blob.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError, Exception):  # noqa: BLE001
        return None


def new_backup_codes(count: int = BACKUP_CODE_COUNT) -> list[str]:
    """8 hex characters each, shown grouped as XXXX-XXXX in the UI."""
    return [secrets.token_hex(4) for _ in range(count)]


def hash_backup_code(code: str) -> str:
    code = code.strip().replace(" ", "").replace("-", "").lower()
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def backup_code_matches(code: str, code_hash: str) -> bool:
    return hmac.compare_digest(hash_backup_code(code), code_hash)


def generate_handle_token() -> str:
    """Profile token for handle verification (audit F1): 6 unambiguous
    characters, e.g. CP-K7Q2XA. The user pastes it into an editable
    Codeforces profile field; the backend checks it via user.info."""
    return "CP-" + "".join(secrets.choice(_ALPHABET) for _ in range(6))
