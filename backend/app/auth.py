"""JWT auth: Argon2 password hashing + short-lived access tokens and
rotating, revocable refresh tokens (blueprint §11).

- Access token: 15 minutes, claim type="access".
- Refresh token: opaque random string, 7 days, SHA-256 hash stored in
  refresh_tokens. Refresh rotates (old token revoked, new one issued).
- Logout revokes one token; logout-all revokes every token of the user.
- Password hashes are Argon2id. Old bcrypt hashes are NOT migratable:
  accounts created before this change must re-register (dev DB only).
JWTs use PyJWT (python-jose removed 2026-11-27: GHSA-3qf3-8w2g-rqmx).
"""
import hashlib
import secrets
from datetime import datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy.orm import Session

from .config import (
    ACCESS_EXPIRE_MINUTES,
    JWT_ALGORITHM,
    REFRESH_EXPIRE_DAYS,
    SECRET_KEY,
)
from .db import get_db
from .models import RefreshToken, User

bearer = HTTPBearer(auto_error=False)
_ph = PasswordHasher()

# A fixed Argon2 hash of a password nobody knows: verified when the
# login email does not exist, so a wrong-email login costs the same
# time as a wrong-password login (audit F7 — no timing oracle).
_DUMMY_HASH = _ph.hash("no-such-password-" + secrets.token_hex(16))


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bool(_ph.verify(password_hash, password))
    except (VerifyMismatchError, Exception):
        return False


def verify_password_dummy(password: str) -> bool:
    """Burns the same Argon2 time as a real check; always False."""
    return verify_password(password, _DUMMY_HASH)


def create_access_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": str(user_id), "type": "access", "exp": expire},
        SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_totp_pending_token(user_id: int) -> str:
    """Short-lived token for the 2FA second step: proves the password
    was just accepted, but grants nothing by itself. 5 minutes."""
    expire = datetime.utcnow() + timedelta(minutes=5)
    return jwt.encode(
        {"sub": str(user_id), "type": "totp_pending", "exp": expire},
        SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_totp_pending_token(raw: str) -> int | None:
    """Returns the user id if the token is a live totp_pending token."""
    try:
        payload = jwt.decode(raw, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "totp_pending":
            return None
        return int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        return None


def _new_refresh_token(db: Session, user_id: int) -> str:
    """Creates a refresh token row and returns the raw token (shown once)."""
    raw = secrets.token_urlsafe(32)
    db.add(RefreshToken(
        user_id=user_id,
        token_hash=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        expires_at=datetime.utcnow() + timedelta(days=REFRESH_EXPIRE_DAYS),
    ))
    db.commit()
    return raw


def issue_tokens(db: Session, user_id: int) -> dict:
    return {
        "access_token": create_access_token(user_id),
        "refresh_token": _new_refresh_token(db, user_id),
        "token_type": "bearer",
    }


def _find_refresh_token(db: Session, raw: str) -> RefreshToken | None:
    token_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return db.query(RefreshToken).filter_by(token_hash=token_hash).first()


def refresh_tokens(db: Session, raw: str) -> tuple[dict, int] | None:
    """Validates a refresh token and rotates it.
    Returns (new tokens, user_id) or None.

    Batch 1 / audit F4 — reuse detection: the rotation is one atomic
    UPDATE ... WHERE revoked_at IS NULL, so two concurrent refreshes
    with the same token cannot both succeed. Presenting a token that
    was already rotated (revoked, not yet expired) is treated as theft:
    the whole token family is revoked, so the attacker's rotated copy
    dies too, and the user must log in again."""
    token_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    now = datetime.utcnow()
    rotated = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash,
        RefreshToken.revoked_at.is_(None),
        RefreshToken.expires_at > now,
    ).update({"revoked_at": now}, synchronize_session=False)
    db.commit()
    if rotated:
        row = db.query(RefreshToken).filter_by(token_hash=token_hash).first()
        return issue_tokens(db, row.user_id), row.user_id
    # No live token matched. If the token exists and was revoked while
    # still unexpired, it was replayed after rotation -> revoke family.
    row = db.query(RefreshToken).filter_by(token_hash=token_hash).first()
    if row is not None and row.revoked_at is not None and row.expires_at > now:
        revoke_all_refresh_tokens(db, row.user_id)
    return None


def revoke_refresh_token(db: Session, raw: str) -> bool:
    row = _find_refresh_token(db, raw)
    if row is None or row.revoked_at is not None:
        return False
    row.revoked_at = datetime.utcnow()
    db.commit()
    return True


def revoke_all_refresh_tokens(db: Session, user_id: int) -> int:
    rows = db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id,
        RefreshToken.revoked_at.is_(None)).all()
    now = datetime.utcnow()
    for row in rows:
        row.revoked_at = now
    db.commit()
    return len(rows)


def decode_access_token_query(token: str | None) -> int:
    """Decodes a JWT access token passed as a ?token= query param
    (EventSource cannot send an Authorization header, so the SSE stream
    uses this). Same checks as get_current_user: type == "access",
    signature, expiry. Returns the user id; 401 otherwise."""
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing token")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
        return int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")


def get_current_user_query(
    token: str | None = Query(None),
    db: Session = Depends(get_db),
) -> User:
    """Same as get_current_user, but the token comes from ?token=."""
    user_id = decode_access_token_query(token)
    user = db.query(User).get(user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing token")
    try:
        payload = jwt.decode(creds.credentials, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    user = db.query(User).get(user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user
