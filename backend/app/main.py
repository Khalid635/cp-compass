"""CP Compass API — FastAPI. JWT auth on everything except /api/v1/health
and the read-only demo routes.

API version: /api/v1 (the old unversioned /api was removed in the
blueprint pass — the frontend is the only client and it was updated).
Sync runs in the DB-backed worker loop (app.sync), not BackgroundTasks.
Schema is managed by Alembic; migrations run automatically at startup.

Batch 1 security (audit 2026-11-27): handle verification by profile
token (F1), login rate limiting + lockout and 8-char minimum password
(F2), fail-fast SECRET_KEY (F3, in config), refresh-token reuse
detection (F4, in auth), ML retrain cooldown (F5), email verification
at signup + optional TOTP 2FA (F6), generic auth errors (F7), security
headers (F8), scoped ml/status (F9), request body size limits (F10).
"""
import asyncio
import hashlib
import hmac
import secrets
import threading
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import mailer, ml, ratelimit, seed, services, sync as sync_engine, totp
from .auth import (
    create_totp_pending_token,
    decode_totp_pending_token,
    get_current_user,
    hash_password,
    issue_tokens,
    refresh_tokens,
    revoke_all_refresh_tokens,
    revoke_refresh_token,
    verify_password,
    verify_password_dummy,
)
from .cf import CFError, cf
from .config import (
    CORS_ORIGINS,
    EMAIL_CODE_EXPIRE_MINUTES,
    EMAIL_CODE_MAX_ATTEMPTS,
    MAX_BODY_BYTES,
    MIN_PASSWORD_LENGTH,
    RESEND_API_KEY,
    RETRAIN_COOLDOWN_S,
    RETRAIN_GLOBAL_MIN_GAP_S,
)
from .db import SessionLocal, get_db
from .models import (
    BackupCode, CfAccount, DailyStat, EmailVerification, HandleVerification,
    Problem, ProblemNote, ProblemPreference, RatingHistory, RefreshToken,
    Revision, Submission, SyncJob, TotpSecret, User, WeeklyReport,
)

V1 = "/api/v1"


def _run_migrations() -> None:
    """Applies Alembic migrations at startup so `uvicorn` just works.
    Failures are logged, not fatal — the endpoints will fail loudly
    instead of the process dying silently at import time."""
    try:
        import os

        from alembic import command
        from alembic.config import Config

        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cfg = Config(os.path.join(backend_dir, "alembic.ini"))
        cfg.set_main_option("script_location", os.path.join(backend_dir, "alembic"))
        command.upgrade(cfg, "head")
    except Exception as exc:  # noqa: BLE001 — startup must not crash here
        print(f"[startup] alembic upgrade failed: {exc}")


def _train_model_at_startup() -> None:
    """Trains the ML model in the background on first boot (only if no
    artifact exists yet). Never blocks or fails startup — until it
    finishes, prediction endpoints honestly report "not trained yet"
    instead of training synchronously (audit F5)."""
    if ml.artifact_exists():
        return
    db = SessionLocal()
    try:
        ml.train_model(db)
    except Exception as exc:  # noqa: BLE001
        print(f"[startup] ml training failed: {exc}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _run_migrations()
    db = SessionLocal()
    try:
        recovered = sync_engine.recover_stale_jobs(db)
        if recovered:
            print(f"[startup] recovered {recovered} stale sync job(s)")
    finally:
        db.close()
    worker_task = asyncio.create_task(sync_engine.worker_loop())
    threading.Thread(target=_train_model_at_startup, daemon=True).start()
    yield
    worker_task.cancel()


app = FastAPI(title="CP Compass API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)


# ---------- Batch 1: security headers (F8) + body size limit (F10) --------
@app.middleware("http")
async def _security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"  # no clickjacking
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=()")
    return response


@app.middleware("http")
async def _body_size_limit(request: Request, call_next):
    length = request.headers.get("content-length")
    try:
        size = int(length) if length is not None else 0
    except ValueError:
        size = 0
    if size > MAX_BODY_BYTES:
        return JSONResponse({"detail": "Request body too large"},
                            status_code=413)
    return await call_next(request)


# ---------- schemas ----------
# Batch 1 (F10): every string input is length-bounded so no endpoint
# accepts an unbounded body. EmailStr already validates the format.
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class HandleIn(BaseModel):
    handle: str = Field(min_length=1, max_length=64)


class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=128)


class VerifyEmailIn(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class ResendCodeIn(BaseModel):
    email: EmailStr


class TotpVerifyIn(BaseModel):
    pre_token: str = Field(min_length=1, max_length=512)
    # 6-digit authenticator code, or an 8-char backup code (dashes ok).
    code: str = Field(min_length=6, max_length=9)


class TotpEnableIn(BaseModel):
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class PasswordIn(BaseModel):
    password: str = Field(min_length=1, max_length=128)


class FeedbackIn(BaseModel):
    contest_id: int
    index: str = Field(min_length=1, max_length=10)
    action: str = Field(min_length=1, max_length=20)  # later | dismissed | interested


class ReviewIn(BaseModel):
    revision_id: int
    result: str = Field(min_length=1, max_length=10)  # again | hard | good | easy


class GoalIn(BaseModel):
    target: int  # problems per week, 1..50


class NoteIn(BaseModel):
    body: str = Field(max_length=10000)


class AuthOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    email: str
    cf_handle: str | None


# ---------- helpers ----------
_rating_cache: dict[str, tuple[float, list]] = {}


async def _rating_history(handle: str) -> list[dict]:
    now = time.monotonic()
    if handle in _rating_cache and now - _rating_cache[handle][0] < 300:
        return _rating_cache[handle][1]
    try:
        rows = await cf.user_rating(handle)
        hist = [{"contest": r["contestName"], "rating": r["newRating"],
                 "old_rating": r.get("oldRating"),
                 "date": datetime.utcfromtimestamp(r["ratingUpdateTimeSeconds"]).isoformat()}
                for r in rows]
    except CFError:
        hist = []
    _rating_cache[handle] = (now, hist)
    return hist


def _problem_json(p) -> dict:
    return {"contest_id": p.contest_id, "index": p.index, "name": p.name,
            "rating": p.rating, "tags": p.tags or []}


def _cf_handle(db: Session, user: User) -> str | None:
    account = services.get_cf_account(db, user.id)
    return account.handle if account else None


# ---------- health / auth ----------
@app.get(f"{V1}/health")
def health():
    return {"status": "ok", "service": "cp-compass", "demo": True}


_REGISTER_MESSAGE = ("If this email is new, check your inbox for the "
                     "verification code.")


def _client_ip(request: Request) -> str:
    """Best-effort client IP (X-Forwarded-For on Render, else the peer)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _issue_email_code(db: Session, user: User) -> bool:
    """Creates a fresh 6-digit code (any old one is deleted), emails it
    via the pluggable mailer. Returns True if it was sent — the dev
    outbox counts as sent."""
    db.query(EmailVerification).filter_by(user_id=user.id).delete()
    code = "".join(secrets.choice("0123456789") for _ in range(6))
    db.add(EmailVerification(
        user_id=user.id, email=user.email, code_hash=_hash_code(code),
        expires_at=datetime.utcnow() + timedelta(minutes=EMAIL_CODE_EXPIRE_MINUTES),
    ))
    db.commit()
    return mailer.send_verification_code(user.email, code)


@app.post(f"{V1}/auth/register", status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    """Creates an UNVERIFIED account and emails a 6-digit code. The
    response is identical whether the email is new, already registered
    and unverified (a fresh code is sent), or already registered and
    verified — no account enumeration (audit F7). No tokens are issued
    until the code is verified."""
    existing = db.query(User).filter_by(email=body.email).first()
    if existing is not None:
        if not existing.email_verified:
            _issue_email_code(db, existing)
        return {"email": body.email, "verification_required": True,
                "message": _REGISTER_MESSAGE}
    user = User(email=body.email, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    sent = _issue_email_code(db, user)
    if not sent and RESEND_API_KEY:
        # Production mailer failed: the account exists but the user has
        # no code — say so plainly instead of stranding them.
        raise HTTPException(
            503, "Could not send the verification email — try again")
    return {"email": body.email, "verification_required": True,
            "message": _REGISTER_MESSAGE}


@app.post(f"{V1}/auth/verify-email", response_model=AuthOut)
def verify_email(body: VerifyEmailIn, db: Session = Depends(get_db)):
    """Checks the 6-digit signup code. Wrong codes, expired codes and
    unknown emails all give the same generic 400 (audit F7)."""
    user = db.query(User).filter_by(email=body.email).first()
    if user is None:
        raise HTTPException(400, "Invalid or expired code")
    row = (db.query(EmailVerification)
           .filter_by(user_id=user.id, used_at=None)
           .order_by(EmailVerification.created_at.desc()).first())
    if row is None or row.expires_at < datetime.utcnow():
        raise HTTPException(400, "Invalid or expired code")
    if row.attempts >= EMAIL_CODE_MAX_ATTEMPTS:
        row.used_at = datetime.utcnow()
        db.commit()
        raise HTTPException(400, "Too many wrong attempts — request a new code")
    if not hmac.compare_digest(row.code_hash, _hash_code(body.code)):
        row.attempts += 1
        db.commit()
        raise HTTPException(400, "Invalid or expired code")
    row.used_at = datetime.utcnow()
    user.email_verified = True
    db.commit()
    tokens = issue_tokens(db, user.id)
    return AuthOut(**tokens, email=user.email, cf_handle=None)


@app.post(f"{V1}/auth/resend-code")
def resend_code(body: ResendCodeIn, db: Session = Depends(get_db)):
    """Re-sends the signup code. The response and the rate limit are
    the same for existing and unknown emails — no enumeration."""
    ratelimit.check_resend_allowed(body.email)
    user = db.query(User).filter_by(email=body.email).first()
    if user is not None and not user.email_verified:
        _issue_email_code(db, user)
    ratelimit.record_resend(body.email)
    return {"ok": True, "message": _REGISTER_MESSAGE}


@app.post(f"{V1}/auth/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    """Password step. Returns AuthOut — or {totp_required, pre_token}
    when 2FA is on, or 403 when the signup code was never verified.
    Wrong email and wrong password give the same 401 after the same
    Argon2 work (audit F7); 5 failures in 15 minutes lock the account
    for 15 minutes (audit F2)."""
    ip = _client_ip(request)
    ratelimit.check_login_allowed(ip, body.email)
    user = db.query(User).filter_by(email=body.email).first()
    if user is None or not verify_password(body.password, user.password_hash):
        if user is None:
            verify_password_dummy(body.password)  # same cost, no oracle
        ratelimit.record_login_failure(ip, body.email)
        raise HTTPException(401, "Wrong email or password")
    ratelimit.record_login_success(body.email)
    if not user.email_verified:
        raise HTTPException(
            403, "Email not verified — enter the code sent to your inbox")
    if user.totp_enabled:
        return {"totp_required": True,
                "pre_token": create_totp_pending_token(user.id),
                "email": user.email}
    tokens = issue_tokens(db, user.id)
    return AuthOut(**tokens, email=user.email, cf_handle=_cf_handle(db, user))


@app.post(f"{V1}/auth/2fa/verify", response_model=AuthOut)
def totp_verify(body: TotpVerifyIn, db: Session = Depends(get_db)):
    """Second login step (audit F6): exchanges the 5-minute pre-auth
    token + a 6-digit authenticator code — or a single-use backup code
    — for real tokens. 5 wrong codes in 15 minutes -> 429."""
    user_id = decode_totp_pending_token(body.pre_token)
    if user_id is None:
        raise HTTPException(401, "Invalid or expired login session — log in again")
    user = db.query(User).get(user_id)
    if user is None or not user.totp_enabled:
        raise HTTPException(401, "Invalid or expired login session — log in again")
    ratelimit.check_totp_allowed(user.id)
    code = body.code.strip().replace(" ", "").replace("-", "")
    for row in db.query(BackupCode).filter_by(user_id=user.id, used_at=None).all():
        if totp.backup_code_matches(code, row.code_hash):
            row.used_at = datetime.utcnow()
            db.commit()
            ratelimit.record_totp_success(user.id)
            tokens = issue_tokens(db, user.id)
            return AuthOut(**tokens, email=user.email, cf_handle=_cf_handle(db, user))
    secret_row = db.query(TotpSecret).filter_by(user_id=user.id).first()
    secret = totp.decrypt_secret(secret_row.secret_encrypted) if secret_row else None
    if secret is None or not totp.verify_code(secret, code):
        ratelimit.record_totp_failure(user.id)
        raise HTTPException(401, "Wrong code")
    ratelimit.record_totp_success(user.id)
    tokens = issue_tokens(db, user.id)
    return AuthOut(**tokens, email=user.email, cf_handle=_cf_handle(db, user))


@app.post(f"{V1}/auth/refresh", response_model=AuthOut)
def refresh(body: RefreshIn, db: Session = Depends(get_db)):
    result = refresh_tokens(db, body.refresh_token)
    if result is None:
        raise HTTPException(401, "Invalid or expired refresh token")
    tokens, user_id = result
    user = db.query(User).get(user_id)
    return AuthOut(**tokens, email=user.email if user else "",
                    cf_handle=_cf_handle(db, user) if user else None)


@app.post(f"{V1}/auth/logout")
def logout(body: RefreshIn, db: Session = Depends(get_db)):
    if not revoke_refresh_token(db, body.refresh_token):
        raise HTTPException(401, "Invalid refresh token")
    return {"ok": True}


@app.post(f"{V1}/auth/logout-all")
def logout_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"ok": True, "revoked": revoke_all_refresh_tokens(db, user.id)}


@app.get(f"{V1}/auth/2fa/status")
def totp_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    remaining = db.query(BackupCode).filter_by(user_id=user.id, used_at=None).count()
    return {"enabled": bool(user.totp_enabled),
            "backup_codes_remaining": remaining}


@app.post(f"{V1}/auth/2fa/setup")
def totp_setup(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Step 1 of enabling 2FA: creates a fresh TOTP secret (encrypted
    at rest) and returns it with the otpauth:// URI — the frontend
    renders it as a QR code and shows the secret for manual entry."""
    if user.totp_enabled:
        raise HTTPException(400, "Two-factor authentication is already enabled")
    secret = totp.generate_secret()
    row = db.query(TotpSecret).filter_by(user_id=user.id).first()
    if row is None:
        db.add(TotpSecret(user_id=user.id,
                          secret_encrypted=totp.encrypt_secret(secret)))
    else:
        row.secret_encrypted = totp.encrypt_secret(secret)
    db.commit()
    return {"secret": secret,
            "otpauth_uri": totp.provisioning_uri(secret, user.email)}


@app.post(f"{V1}/auth/2fa/enable")
def totp_enable(body: TotpEnableIn, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    """Step 2: confirms the authenticator code, then enables 2FA and
    issues 10 single-use backup codes — shown once, never again."""
    if user.totp_enabled:
        raise HTTPException(400, "Two-factor authentication is already enabled")
    row = db.query(TotpSecret).filter_by(user_id=user.id).first()
    secret = totp.decrypt_secret(row.secret_encrypted) if row else None
    if secret is None or not totp.verify_code(secret, body.code):
        raise HTTPException(400, "Wrong code — check the authenticator app")
    codes = totp.new_backup_codes()
    db.query(BackupCode).filter_by(user_id=user.id).delete()
    for code in codes:
        db.add(BackupCode(user_id=user.id, code_hash=totp.hash_backup_code(code)))
    user.totp_enabled = True
    db.commit()
    return {"ok": True, "backup_codes": codes}


@app.post(f"{V1}/auth/2fa/disable")
def totp_disable(body: PasswordIn, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    """Disables 2FA. Needs the password — a stolen access token alone
    must not be able to strip the second factor."""
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Wrong password")
    user.totp_enabled = False
    db.query(TotpSecret).filter_by(user_id=user.id).delete()
    db.query(BackupCode).filter_by(user_id=user.id).delete()
    db.commit()
    return {"ok": True}


@app.post(f"{V1}/auth/2fa/backup-codes")
def totp_regenerate_codes(body: PasswordIn, user: User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    """Replaces all backup codes with a fresh set of 10. Needs the
    password; the old codes die immediately."""
    if not user.totp_enabled:
        raise HTTPException(400, "Two-factor authentication is not enabled")
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Wrong password")
    codes = totp.new_backup_codes()
    db.query(BackupCode).filter_by(user_id=user.id).delete()
    for code in codes:
        db.add(BackupCode(user_id=user.id, code_hash=totp.hash_backup_code(code)))
    db.commit()
    return {"ok": True, "backup_codes": codes}


@app.get(f"{V1}/auth/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"email": user.email, "cf_handle": _cf_handle(db, user),
            "current_rating": user.current_rating}


# Codeforces user.info has no "about" field — the only editable
# free-text fields are first name, last name, city and organization.
_HANDLE_PROFILE_FIELDS = ("firstName", "lastName", "city", "organization")
_HANDLE_MAX_ATTEMPTS = 5


def _link_handle(db: Session, user: User, handle: str, info: dict) -> dict:
    """Links the (already ownership-proven) handle to the account."""
    account = services.get_cf_account(db, user.id)
    if account is None:
        account = CfAccount(user_id=user.id, handle=handle,
                            handle_norm=handle.lower(), rank=info.get("rank"))
        db.add(account)
    else:
        account.handle = handle
        account.handle_norm = handle.lower()
        account.rank = info.get("rank")
    user.current_rating = info.get("rating")
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, "This handle is already connected to another account")
    return {"cf_handle": handle, "current_rating": user.current_rating,
            "rank": info.get("rank")}


@app.post(f"{V1}/auth/handle/start")
async def handle_start(body: HandleIn, user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    """Step 1 of handle verification (audit F1): checks the handle
    exists on Codeforces, then issues a one-time profile token. The
    user puts the token in an editable profile field and confirms in
    step 2. The token is shown once — starting again issues a new one."""
    handle = body.handle.strip()
    if not handle:
        raise HTTPException(400, "Handle is empty")
    try:
        await cf.verify_handle(handle)
    except CFError as exc:
        raise HTTPException(400, f"Codeforces could not verify this handle: {exc}")
    taken = (db.query(CfAccount)
             .filter(CfAccount.handle_norm == handle.lower(),
                     CfAccount.user_id != user.id).first())
    if taken is not None:
        raise HTTPException(400, "This handle is already connected to another account")
    db.query(HandleVerification).filter_by(user_id=user.id).delete()
    token = totp.generate_handle_token()
    db.add(HandleVerification(
        user_id=user.id, handle=handle, handle_norm=handle.lower(),
        token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
        expires_at=datetime.utcnow() + timedelta(minutes=60),
    ))
    db.commit()
    return {"handle": handle, "token": token, "expires_in_minutes": 60,
            "fields": list(_HANDLE_PROFILE_FIELDS),
            "message": ("Put this token in your Codeforces profile — first "
                        "name, last name, city or organization — save it, "
                        "then press Verify. You can remove it right after, "
                        "and restore your name.")}


@app.get(f"{V1}/auth/handle/pending")
def handle_pending(user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    """The pending verification (if any): handle + expiry + attempts
    left. The token itself is NOT returned — it was shown once at
    start; starting again issues a new one."""
    row = (db.query(HandleVerification).filter_by(user_id=user.id)
           .order_by(HandleVerification.created_at.desc()).first())
    if row is None or row.expires_at < datetime.utcnow():
        return {"pending": None}
    return {"pending": {"handle": row.handle,
                        "expires_at": row.expires_at.isoformat(),
                        "attempts_left": max(0, _HANDLE_MAX_ATTEMPTS - row.attempts)}}


@app.post(f"{V1}/auth/handle/confirm")
async def handle_confirm(body: HandleIn, user: User = Depends(get_current_user),
                         db: Session = Depends(get_db)):
    """Step 2: reads the public Codeforces profile and links the handle
    ONLY if the step-1 token is present in it. A second account cannot
    claim a handle it does not own — it cannot edit the victim's
    Codeforces profile."""
    handle = body.handle.strip()
    row = (db.query(HandleVerification)
           .filter_by(user_id=user.id, handle_norm=handle.lower())
           .order_by(HandleVerification.created_at.desc()).first())
    if row is None or row.expires_at < datetime.utcnow():
        raise HTTPException(400, "No pending verification for this handle — start again")
    if row.attempts >= _HANDLE_MAX_ATTEMPTS:
        db.delete(row)
        db.commit()
        raise HTTPException(400, "Too many attempts — start the verification again")
    try:
        info = await cf.verify_handle(handle)
    except CFError as exc:
        raise HTTPException(400, f"Codeforces could not verify this handle: {exc}")
    found = None
    for field in _HANDLE_PROFILE_FIELDS:
        for word in str(info.get(field) or "").split():
            word = word.strip(".,;:!?()[]{}")
            if word.startswith("CP-") and len(word) == 9:
                found = word
                break
        if found:
            break
    if found is None or not hmac.compare_digest(
            row.token_hash, hashlib.sha256(found.encode("utf-8")).hexdigest()):
        row.attempts += 1
        db.commit()
        raise HTTPException(
            400, "Token not found in the Codeforces profile yet — check the "
                 "token is saved in your profile and try again")
    db.delete(row)
    return _link_handle(db, user, handle, info)


@app.post(f"{V1}/auth/handle")
async def set_handle_legacy(body: HandleIn, user: User = Depends(get_current_user),
                            db: Session = Depends(get_db)):
    """The old direct-link endpoint is CLOSED: handles are linked only
    through the verification flow (start -> confirm)."""
    raise HTTPException(
        400, "Handle linking now needs verification — use "
             "/auth/handle/start then /auth/handle/confirm")


# ---------- sync ----------
@app.post(f"{V1}/sync", status_code=status.HTTP_202_ACCEPTED)
def start_sync(user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    if _cf_handle(db, user) is None:
        raise HTTPException(400, "Connect your Codeforces handle first")
    job = sync_engine.enqueue_sync(db, user.id)
    if job is None:
        raise HTTPException(409, "A sync is already running")
    return {"job_id": job.id, "status": "pending"}


@app.get(f"{V1}/sync/status")
def sync_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = sync_engine.latest_job(db, user.id)
    if not job:
        return {"status": "never", "total_synced": 0}
    return {"status": job.status, "total_synced": job.total_synced,
            "last_synced_at": job.last_synced_at.isoformat() if job.last_synced_at else None,
            "error": job.error}


# ---------- dashboard ----------
@app.get(f"{V1}/dashboard")
async def dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    handle = _cf_handle(db, user)
    if not handle:
        return {"has_handle": False, "synced": False, "user": {"handle": None},
                "stats": None, "rating_history": [], "today_plan": {"problems": [], "revisions": []},
                "tag_strengths": [], "heatmap": [], "recent": [],
                "cumulative": [], "recent_total": 0}
    solved = len(services.solved_problem_ids(db, user.id))
    due = services.revision_list(db, user.id, "due")
    recs = []
    try:
        problems = await cf.problemset()
        recs = services.recommend(db, user, problems, limit=3)
    except CFError:
        recs = []
    return {
        "has_handle": True,
        "synced": db.query(Submission).filter_by(user_id=user.id).first() is not None,
        "user": {"handle": handle, "rating": user.current_rating},
        "stats": {"rating": user.current_rating, "solved": solved,
                  "streak": services.current_streak(db, user.id),
                  "revisions_due": len(due)},
        "rating_history": await _rating_history(handle),
        "today_plan": {"problems": recs, "revisions": due[:2]},
        "tag_strengths": services.tag_stats(db, user.id),
        "heatmap": services.heatmap(db, user.id, weeks=None),
        "recent": services.recent_submissions(db, user.id),
        "cumulative": services.cumulative_solved(db, user.id),
        "recent_total": db.query(Submission).filter_by(user_id=user.id).count(),
    }


# ---------- recommendations ----------
@app.get(f"{V1}/recommendations")
async def recommendations(
        user: User = Depends(get_current_user), db: Session = Depends(get_db),
        tag: str | None = None, min_rating: int | None = None,
        max_rating: int | None = None, hide_solved: bool = True):
    if _cf_handle(db, user) is None:
        raise HTTPException(400, "Connect your Codeforces handle first")
    try:
        problems = await cf.problemset()
    except CFError as exc:
        raise HTTPException(502, f"Codeforces didn't respond: {exc}")
    return services.recommend(db, user, problems, limit=24, tag=tag,
                              min_rating=min_rating, max_rating=max_rating,
                              hide_solved=hide_solved)


@app.post(f"{V1}/recommendations/action")
def recommendation_action(body: FeedbackIn, user: User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    action = body.action
    if action == "not_interested":  # legacy frontend name
        action = "dismissed"
    if action not in ("later", "dismissed", "interested"):
        raise HTTPException(400, "Unknown action")
    services.set_preference(db, user.id, body.contest_id, body.index, action)
    return {"ok": True}


@app.get(f"{V1}/practice/preferences")
def practice_preferences(user: User = Depends(get_current_user),
                         db: Session = Depends(get_db)):
    return services.list_preferences(db, user.id)


# ---------- Phase 3: ML solvability prediction ----------
# Global retrain gap (audit F5): even across users, two retrains must be
# at least RETRAIN_GLOBAL_MIN_GAP_S apart — training is the one
# CPU-heavy endpoint, and a per-user limit alone still allows N users
# to hammer it in turn.
_last_retrain_finished_at: float | None = None


def _scoped_ml_payload(payload: dict, handle: str | None) -> dict:
    """Audit F9: ml payloads must not leak every user's handle. The
    response keeps aggregate counts; per-user sources show only the
    requesting user's own handle (or nothing for the demo)."""
    sources = payload.get("sources")
    if isinstance(sources, dict):
        payload = dict(payload)
        payload["sources"] = ({handle: sources[handle]}
                              if handle and handle in sources else {})
    return payload


@app.get(f"{V1}/ml/status")
def ml_status(user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    """Model status + evaluation. Trains only at startup or via
    /ml/retrain — never lazily on a read (audit F5)."""
    return _scoped_ml_payload(ml.model_status(db, _cf_handle(db, user)),
                              _cf_handle(db, user))


@app.post(f"{V1}/ml/retrain")
def ml_retrain(user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    """Retrains the model on all current data (demo + your submissions).
    Returns the evaluation report. Cooldown (audit F5): max 1 retrain
    per user per hour, plus a global minimum gap, so retraining cannot
    be used for CPU exhaustion."""
    global _last_retrain_finished_at
    now = datetime.utcnow()
    if user.last_retrain_at is not None:
        elapsed = (now - user.last_retrain_at).total_seconds()
        if elapsed < RETRAIN_COOLDOWN_S:
            retry = int(RETRAIN_COOLDOWN_S - elapsed) + 1
            raise HTTPException(
                429, "Retrain is limited to once per hour — "
                     f"try again in {retry} seconds",
                headers={"Retry-After": str(retry)})
    if ml.training_running():
        raise HTTPException(409, "Training is already running")
    if _last_retrain_finished_at is not None:
        gap = time.monotonic() - _last_retrain_finished_at
        if gap < RETRAIN_GLOBAL_MIN_GAP_S:
            retry = int(RETRAIN_GLOBAL_MIN_GAP_S - gap) + 1
            raise HTTPException(
                429, "Another retrain just finished — "
                     f"try again in {retry} seconds",
                headers={"Retry-After": str(retry)})
    user.last_retrain_at = now
    db.commit()
    result = ml.train_model(db)
    _last_retrain_finished_at = time.monotonic()
    return _scoped_ml_payload(result, _cf_handle(db, user))


@app.get(f"{V1}/ml/predictions")
async def ml_predictions(
        user: User = Depends(get_current_user), db: Session = Depends(get_db),
        limit: int = Query(24, ge=1, le=50)):
    """Recommendations with a solvability probability each. The model
    trains lazily on first call (demo + your data)."""
    if _cf_handle(db, user) is None:
        raise HTTPException(400, "Connect your Codeforces handle first")
    try:
        problems = await cf.problemset()
    except CFError as exc:
        raise HTTPException(502, f"Codeforces didn't respond: {exc}")
    recs = services.recommend(db, user, problems, limit=limit)
    result = ml.predict_for_user(db, user, recs, handle=_cf_handle(db, user))
    by_key = {(p["contest_id"], p["index"]): p["probability"]
              for p in result["predictions"]}
    out = []
    for rec in recs:
        rec = dict(rec)
        rec["solvability"] = by_key.get((rec["contest_id"], rec["index"]))
        out.append(rec)
    return {"recommendations": out, "model": result["model"]}


# ---------- revisions ----------
@app.get(f"{V1}/revisions")
def revisions(tab: str = Query("due", pattern="^(due|upcoming|done)$"),
              user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return services.revision_list(db, user.id, tab)


@app.post(f"{V1}/revisions/review")
def review(body: ReviewIn, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    rev = services.review_revision(db, user.id, body.revision_id, body.result)
    if rev is None:
        raise HTTPException(404, "Revision not found")
    return {"ok": True, "next_due": rev.due_date.isoformat(),
            "interval_days": rev.interval_days}


@app.get(f"{V1}/revisions/counts")
def revision_counts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {tab: len(services.revision_list(db, user.id, tab))
            for tab in ("due", "upcoming", "done")}


# ---------- Phase 2: analytics / calendar / weekly report ----------
@app.get(f"{V1}/analytics")
def analytics(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if _cf_handle(db, user) is None:
        raise HTTPException(400, "Connect your Codeforces handle first")
    return services.analytics(db, user.id)


@app.get(f"{V1}/analytics/failures")
def analytics_failures(user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    """Batch 2: where the user's solutions fail — verdict breakdown,
    test-stage distribution, per-topic and per-problem patterns, from
    their own synced submissions."""
    if _cf_handle(db, user) is None:
        raise HTTPException(400, "Connect your Codeforces handle first")
    return services.failure_patterns(db, user.id)


@app.get(f"{V1}/calendar")
def calendar(year: int = Query(...), month: int = Query(...),
             user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if month < 1 or month > 12:
        raise HTTPException(400, "Month must be 1..12")
    if year < 2000 or year > 2100:
        raise HTTPException(400, "Year must be 2000..2100")
    return services.calendar_month(db, user.id, year, month)


@app.get(f"{V1}/calendar/day")
def calendar_day(day: str = Query(...),
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        d = date.fromisoformat(day)
    except ValueError:
        raise HTTPException(400, "Day must be YYYY-MM-DD")
    return {"date": d.isoformat(), "submissions": services.day_submissions(db, user.id, d)}


@app.get(f"{V1}/reports/weekly")
def weekly_report(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if _cf_handle(db, user) is None:
        raise HTTPException(400, "Connect your Codeforces handle first")
    return services.weekly_report(db, user.id)


# ---------- Phase 2: problem detail + notes ----------
@app.get(f"{V1}/problems/{{contest_id}}/{{index}}")
async def problem_detail(contest_id: int, index: str,
                         user: User = Depends(get_current_user),
                         db: Session = Depends(get_db)):
    detail = services.problem_detail(db, user.id, contest_id, index)
    if detail is not None:
        return detail
    # Not in the local catalog yet — look it up in the public problemset
    # so any Codeforces problem has a detail page (with empty user data).
    try:
        problems = await cf.problemset()
    except CFError as exc:
        raise HTTPException(502, f"Codeforces didn't respond: {exc}")
    for p in problems:
        if p.get("contestId") == contest_id and p.get("index") == index:
            return {
                "problem": {"contest_id": contest_id, "index": index,
                            "name": p.get("name", ""), "rating": p.get("rating"),
                            "tags": p.get("tags", [])},
                "attempts": 0, "wrong_attempts": 0, "solved": False, "first_attempt": None,
                "last_attempt": None, "submissions": [], "revision": None,
                "note": {"body": "", "updated_at": None}, "preference": None,
            }
    raise HTTPException(404, "Problem not found on Codeforces")


@app.get(f"{V1}/problems/{{contest_id}}/{{index}}/notes")
def get_note(contest_id: int, index: str,
             user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    detail = services.problem_detail(db, user.id, contest_id, index)
    if detail is None:
        raise HTTPException(404, "Problem not found")
    return detail["note"]


@app.put(f"{V1}/problems/{{contest_id}}/{{index}}/notes")
def put_note(contest_id: int, index: str, body: NoteIn,
             user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    note = services.save_note(db, user.id, contest_id, index, body.body)
    if note is None:
        raise HTTPException(404, "Problem not found")
    return note


# ---------- Phase 2: settings ----------
@app.get(f"{V1}/settings")
def settings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return services.settings_data(db, user)


@app.post(f"{V1}/settings/goal")
def set_goal(body: GoalIn, user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    if body.target < 1 or body.target > 50:
        raise HTTPException(400, "Weekly goal must be 1..50 problems")
    user.weekly_goal = body.target
    db.commit()
    return services.settings_data(db, user)


@app.delete(f"{V1}/settings/handle")
def disconnect_handle(user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    """Disconnects the Codeforces handle. Submissions and stats stay —
    reconnecting the same handle links them back."""
    account = services.get_cf_account(db, user.id)
    if account is None:
        raise HTTPException(400, "No handle connected")
    db.delete(account)
    db.commit()
    return {"ok": True}


@app.delete(f"{V1}/auth/account")
def delete_account(body: PasswordIn, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    """Deletes the account and everything attached to it. Child rows are
    deleted explicitly — SQLite does not enforce ON DELETE CASCADE unless
    foreign_keys is on, so never rely on it here. Requires the password:
    a stolen access token alone must not be able to wipe the account."""
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Wrong password")
    revoke_all_refresh_tokens(db, user.id)
    db.query(RefreshToken).filter_by(user_id=user.id).delete()
    db.query(SyncJob).filter_by(user_id=user.id).delete()
    db.query(WeeklyReport).filter_by(user_id=user.id).delete()
    db.query(DailyStat).filter_by(user_id=user.id).delete()
    db.query(ProblemNote).filter_by(user_id=user.id).delete()
    db.query(ProblemPreference).filter_by(user_id=user.id).delete()
    db.query(Revision).filter_by(user_id=user.id).delete()
    db.query(RatingHistory).filter_by(user_id=user.id).delete()
    db.query(Submission).filter_by(user_id=user.id).delete()
    db.query(CfAccount).filter_by(user_id=user.id).delete()
    db.query(EmailVerification).filter_by(user_id=user.id).delete()
    db.query(TotpSecret).filter_by(user_id=user.id).delete()
    db.query(BackupCode).filter_by(user_id=user.id).delete()
    db.query(HandleVerification).filter_by(user_id=user.id).delete()
    db.delete(user)
    db.commit()
    return {"ok": True}


# ---------- export ----------
@app.get(f"{V1}/export")
def export_data(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    subs = db.query(Submission).filter_by(user_id=user.id).all()
    return {
        "handle": _cf_handle(db, user), "email": user.email,
        "exported_at": datetime.utcnow().isoformat(),
        "submissions": [
            {"cf_id": s.cf_submission_id, "verdict": s.verdict,
             "submitted_at": s.submitted_at.isoformat()} for s in subs],
        "tag_stats": services.tag_stats(db, user.id),
        "revisions": services.revision_list(db, user.id, "due")
        + services.revision_list(db, user.id, "upcoming")
        + services.revision_list(db, user.id, "done"),
        "rating_history": [
            {"contest_id": r.contest_id, "contest_name": r.contest_name,
             "old_rating": r.old_rating, "new_rating": r.rating,
             "date": r.rated_at.date().isoformat()}
            for r in db.query(RatingHistory).filter_by(user_id=user.id)
            .order_by(RatingHistory.rated_at.asc()).all()],
        "preferences": services.list_preferences(db, user.id),
        "notes": [
            {"contest_id": p.contest_id, "index": p.index, "body": n.body,
             "updated_at": n.updated_at.isoformat()}
            for n, p in db.query(ProblemNote, Problem)
            .join(Problem, ProblemNote.problem_id == Problem.id)
            .filter(ProblemNote.user_id == user.id).all()],
        "daily_stats": [
            {"date": r.day.isoformat(), "solved": r.solved, "attempted": r.attempted}
            for r in db.query(DailyStat).filter_by(user_id=user.id)
            .order_by(DailyStat.day.asc()).all()],
        "weekly_reports": [
            {"week_start": r.week_start.isoformat(), "solved": r.solved,
             "attempted": r.attempted, "tag_acceptance": r.tag_acceptance or {}}
            for r in db.query(WeeklyReport).filter_by(user_id=user.id)
            .order_by(WeeklyReport.week_start.asc()).all()],
    }


# ---------- demo (no auth, read-only, honestly labelled) ----------
@app.get(f"{V1}/demo/dashboard")
def demo_dashboard():
    return seed.dashboard_payload()


@app.get(f"{V1}/demo/recommendations")
def demo_recommendations():
    return seed.RECOMMENDATIONS


@app.get(f"{V1}/demo/ml/status")
def demo_ml_status():
    # Demo: aggregate counts only, no per-user sources (audit F9).
    return _scoped_ml_payload(ml.model_status(None), None)


@app.get(f"{V1}/demo/ml/predictions")
def demo_ml_predictions(limit: int = Query(24, ge=1, le=50)):
    """Demo recommendations with a solvability probability each."""
    recs = seed.RECOMMENDATIONS[:limit]
    result = ml.predict_for_demo(recs)
    by_key = {(p["contest_id"], p["index"]): p["probability"]
              for p in result["predictions"]}
    out = []
    for rec in recs:
        rec = dict(rec)
        rec["solvability"] = by_key.get((rec["contest_id"], rec["index"]))
        out.append(rec)
    return {"recommendations": out, "model": result["model"]}


@app.get(f"{V1}/demo/revisions")
def demo_revisions():
    return seed.REVISIONS


@app.get(f"{V1}/demo/analytics")
def demo_analytics():
    return seed.analytics_payload()


@app.get(f"{V1}/demo/analytics/failures")
def demo_analytics_failures():
    return seed.failure_patterns_payload()


@app.get(f"{V1}/demo/calendar")
def demo_calendar(year: int = Query(...), month: int = Query(...)):
    if month < 1 or month > 12:
        raise HTTPException(400, "Month must be 1..12")
    if year < 2000 or year > 2100:
        raise HTTPException(400, "Year must be 2000..2100")
    return seed.calendar_payload(year, month)


@app.get(f"{V1}/demo/calendar/day")
def demo_calendar_day(day: str = Query(...)):
    try:
        d = date.fromisoformat(day)
    except ValueError:
        raise HTTPException(400, "Day must be YYYY-MM-DD")
    return {"date": d.isoformat(), "submissions": seed.day_submissions(d)}


@app.get(f"{V1}/demo/reports/weekly")
def demo_weekly_report():
    return seed.weekly_report_payload()


@app.get(f"{V1}/demo/problems/{{contest_id}}/{{index}}")
def demo_problem_detail(contest_id: int, index: str):
    detail = seed.problem_detail_payload(contest_id, index)
    if detail is None:
        raise HTTPException(404, "Problem not found")
    return detail


@app.get(f"{V1}/demo/settings")
def demo_settings():
    return seed.settings_payload()


@app.get(f"{V1}/demo/export")
def demo_export():
    return seed.export_payload()
