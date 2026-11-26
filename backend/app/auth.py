"""JWT auth: Argon2 password hashing + short-lived access tokens and
rotating, revocable refresh tokens (blueprint §11).

- Access token: 15 minutes, claim type="access".
- Refresh token: opaque random string, 7 days, SHA-256 hash stored in
  refresh_tokens. Refresh rotates (old token revoked, new one issued).
- Logout revokes one token; logout-all revokes every token of the user.
- Password hashes are Argon2id. Old bcrypt hashes are NOT migratable:
  accounts created before this change must re-register (dev DB only).
"""
import hashlib
import secrets
from datetime import datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
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


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bool(_ph.verify(password_hash, password))
    except (VerifyMismatchError, Exception):
        return False


def create_access_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": str(user_id), "type": "access", "exp": expire},
        SECRET_KEY, algorithm=JWT_ALGORITHM)


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
    Returns (new tokens, user_id) or None."""
    row = _find_refresh_token(db, raw)
    if row is None or row.revoked_at is not None:
        return None
    if row.expires_at < datetime.utcnow():
        return None
    user_id = row.user_id
    row.revoked_at = datetime.utcnow()  # rotation: old token dies here
    db.commit()
    return issue_tokens(db, user_id), user_id


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
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    user = db.query(User).get(user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user
