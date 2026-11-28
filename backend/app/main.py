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
import json
import hashlib
import hmac
import secrets
import threading
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import audit, google_oauth, hints, mailer, ml, postmortem_ai, ratelimit, seed, services, sync as sync_engine, totp
from .auth import (
    CSRF_COOKIE,
    REFRESH_COOKIE,
    clear_auth_cookies,
    create_totp_pending_token,
    decode_totp_pending_token,
    get_current_user,
    hash_password,
    issue_tokens,
    new_csrf_token,
    refresh_tokens,
    revoke_all_refresh_tokens,
    revoke_refresh_token,
    set_auth_cookies,
    set_csrf_cookie,
    verify_password,
    verify_password_dummy,
)
from .cf import CFError, cf
from .config import (
    CORS_ORIGINS,
    DATABASE_URL,
    EMAIL_CODE_EXPIRE_MINUTES,
    EMAIL_CODE_MAX_ATTEMPTS,
    ENV,
    FRONTEND_URL,
    IS_PROD,
    HINT_DAILY_LIMIT,
    MAX_BODY_BYTES,
    MIN_PASSWORD_LENGTH,
    POSTMORTEM_DAILY_LIMIT,
    RESEND_API_KEY,
    RESET_TOKEN_EXPIRE_MINUTES,
    RETRAIN_COOLDOWN_S,
    RETRAIN_GLOBAL_MIN_GAP_S,
)
from .db import SessionLocal, get_db, set_rls_user
from .models import (
    BackupCode, CfAccount, DailyStat, EmailVerification, HandleVerification,
    PasswordResetToken, Problem, ProblemNote, ProblemPreference, RatingHistory, RefreshToken,
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


# Reel check #12 (2026-11-27): interactive API docs are public by
# default. Disable them outside local dev so the full API surface is
# not advertised; local dev keeps docs for debugging. Production is
# detected in config.py (IS_PROD: ENV == "production" OR a non-SQLite
# DATABASE_URL — Render does not set ENV, so an ENV-only check would
# have left docs on live).
_docs_kwargs = {} if not IS_PROD else {
    "docs_url": None, "redoc_url": None, "openapi_url": None}
app = FastAPI(title="CP Compass API", version="1.0.0", lifespan=lifespan,
              **_docs_kwargs)
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
    # Hardening H5: HSTS (Render serves HTTPS only; browsers ignore this
    # on plain-HTTP dev) and CSP frame-ancestors (the API returns JSON, so
    # no broader CSP is needed — this just forbids framing).
    response.headers["Strict-Transport-Security"] = (
        "max-age=63072000; includeSubDomains")
    response.headers["Content-Security-Policy"] = "frame-ancestors 'none'"
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


# ---------- Batch 6, N4: CSRF protection (arena winner a005 + a003) -------
# A middleware (not a per-endpoint dependency) covers every mutation
# automatically — including the N2 endpoints built in the same batch —
# and a future mutation cannot forget the check. It only reads headers
# + cookies (never the body), and returns a JSONResponse 403 directly:
# an http middleware cannot raise HTTPException into a response.
def _csrf_failure(request: Request) -> str | None:
    """Returns a 403 detail string if the mutation fails CSRF, else
    None. One detail for every failure (a001's supplement) so a probe
    learns nothing about which gate tripped."""
    # (1) Double-submit: X-CSRF-Token must equal the cp_csrf cookie.
    header = request.headers.get("x-csrf-token")
    cookie = request.cookies.get(CSRF_COOKIE)
    if not header or not cookie or not hmac.compare_digest(header, cookie):
        return "csrf_check_failed"
    # (2) Origin: the Origin header (or Referer if Origin is absent)
    # must be in the exact CORS allowlist; both absent -> reject.
    # Browsers always send Origin on a fetch POST; page JS cannot
    # spoof it (forbidden header). SameSite is NOT a layer here: prod
    # cookies are SameSite=None, which by definition sends them
    # cross-site.
    origin = request.headers.get("origin")
    if origin is None:
        referer = request.headers.get("referer")
        if referer and "://" in referer:
            origin = referer.split("://", 1)[0] + "://" + \
                referer.split("://", 1)[1].split("/")[0]
    if origin is None or origin not in CORS_ORIGINS:
        return "csrf_check_failed"
    return None


@app.middleware("http")
async def _csrf_protect(request: Request, call_next):
    if (request.method in ("POST", "PUT", "PATCH", "DELETE")
            and request.url.path.startswith("/api/v1")):
        detail = _csrf_failure(request)
        if detail is not None:
            return JSONResponse({"detail": detail}, status_code=403)
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


class GoogleCallbackIn(BaseModel):
    code: str = Field(min_length=1, max_length=2048)
    state: str = Field(min_length=1, max_length=2048)


class HandleIn(BaseModel):
    handle: str = Field(min_length=1, max_length=64)



class VerifyEmailIn(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class ResendCodeIn(BaseModel):
    email: EmailStr


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=128)


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


class PublicProfileIn(BaseModel):
    public: bool


class NoteIn(BaseModel):
    body: str = Field(max_length=10000)


class AuthOut(BaseModel):
    email: str
    cf_handle: str | None
    csrf_token: str | None = None


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
    """Best-effort client IP (Batch 6, hacker review N3).

    Render terminates TLS at its edge and APPENDS the connecting IP
    as the LAST X-Forwarded-For entry — earlier entries are
    client-controlled and must never be trusted (an attacker can put
    any IP first and dodge a per-IP bucket). So in production
    (behind Render) the last entry is the client; in local dev there
    is no proxy, so XFF is ignored entirely and the direct peer is
    the client.
    """
    peer = request.client.host if request.client else "unknown"
    if IS_PROD:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[-1].strip()
    return peer


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _issue_email_code(db: Session, user: User) -> bool:
    """Creates a fresh 6-digit code and emails it via the pluggable
    mailer. Returns True if it was sent — the dev outbox counts as
    sent.

    Batch 6, N1: the old code stays valid until the new one is
    actually sent. The old code is only deleted AFTER a successful
    send; if the send fails, the new row is deleted instead and the
    old code keeps working (a re-register used to kill the victim's
    pending code first, then strand them when the mail failed).
    """
    # Batch 7 (RLS): registration / resend run pre-auth -- scope the
    # session to this user first, so the INSERT and the post-send
    # old-row delete are visible to the policy.
    set_rls_user(db, user.id)
    code = "".join(secrets.choice("0123456789") for _ in range(6))
    row = EmailVerification(
        user_id=user.id, email=user.email, code_hash=_hash_code(code),
        expires_at=datetime.utcnow() + timedelta(minutes=EMAIL_CODE_EXPIRE_MINUTES),
    )
    db.add(row)
    db.commit()
    sent = mailer.send_verification_code(user.email, code)
    if sent:
        db.query(EmailVerification).filter(
            EmailVerification.user_id == user.id,
            EmailVerification.id != row.id).delete()
    else:
        db.delete(row)
    db.commit()
    return sent


def _auth_out(response: Response, db: Session, user: User) -> AuthOut:
    """Issues fresh tokens, sets the auth cookies, and returns AuthOut
    — no token fields (Batch 6, N4). The CSRF token is rotated on auth
    transitions (login, verify-email, totp-verify, Google callback)
    and echoed in the JSON body (a004's pattern) so the frontend can
    update its in-memory copy; refresh does NOT rotate (see refresh)."""
    tokens = issue_tokens(db, user.id)
    csrf = new_csrf_token()
    set_auth_cookies(response, tokens["access_token"], tokens["refresh_token"], csrf)
    return AuthOut(email=user.email, cf_handle=_cf_handle(db, user), csrf_token=csrf)


@app.get(f"{V1}/auth/csrf")
def get_csrf(request: Request, response: Response):
    """Issues the CSRF token (Batch 6, N4 — a005). Idempotent: if a
    cp_csrf cookie is already present, its value is returned (no
    rotation — any site could otherwise rotate the victim's token at
    will); else a new token is minted, set as the cookie, and
    returned. The JSON body is load-bearing: JS on the Vercel origin
    cannot read a cookie set for the Render origin via document.cookie.
    Cache-Control: no-store. No rate limit (a003): minting a random
    token is harmless — no DB, no auth."""
    token = request.cookies.get(CSRF_COOKIE) or new_csrf_token()
    set_csrf_cookie(response, token)
    response.headers["Cache-Control"] = "no-store"
    return {"csrf_token": token}


@app.get(f"{V1}/auth/cookie-probe")
def cookie_probe(request: Request, response: Response):
    """Confirms whether the browser is blocking third-party cookies
    (Batch 6, N4 — a002's supplement). First call sets a throwaway
    cookie and answers cookies_ok False; the frontend calls again and
    checks whether it came back."""
    if request.cookies.get("cp_probe") == "1":
        return {"cookies_ok": True}
    response.set_cookie("cp_probe", "1", max_age=60, httponly=True,
                        secure=IS_PROD, samesite="none" if IS_PROD else "lax",
                        path="/")
    return {"cookies_ok": False}


@app.post(f"{V1}/auth/register", status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    """Creates an UNVERIFIED account and emails a 6-digit code. The
    response is identical whether the email is new, already registered
    and unverified (a fresh code is sent), or already registered and
    verified — no account enumeration (audit F7). No tokens are issued
    until the code is verified. Rate-limited per email (1/min, 5/hour,
    shared with resend-code — Batch 6, N1)."""
    # Batch 6, N1: checked before the DB lookup, recorded on every
    # call that passes — exactly like resend-code, so no enumeration
    # oracle is introduced.
    ratelimit.check_resend_allowed(body.email)
    ratelimit.record_resend(body.email)
    existing = db.query(User).filter_by(email=body.email).first()
    if existing is not None:
        if not existing.email_verified:
            _issue_email_code(db, existing)
        return {"email": body.email, "verification_required": True,
                "message": _REGISTER_MESSAGE}
    user = User(email=body.email, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    # Batch 7 (RLS): scope to the new user before issuing the code
    # (pre-auth request, no context yet; _issue_email_code sets it
    # again -- idempotent).
    set_rls_user(db, user.id)
    sent = _issue_email_code(db, user)
    if not sent and RESEND_API_KEY:
        # Production mailer failed: the account exists but the user has
        # no code — say so plainly instead of stranding them.
        raise HTTPException(
            503, "Could not send the verification email — try again")
    return {"email": body.email, "verification_required": True,
            "message": _REGISTER_MESSAGE}


@app.post(f"{V1}/auth/verify-email", response_model=AuthOut)
def verify_email(body: VerifyEmailIn, response: Response, db: Session = Depends(get_db)):
    """Checks the 6-digit signup code. Wrong codes, expired codes and
    unknown emails all give the same generic 400 (audit F7)."""
    user = db.query(User).filter_by(email=body.email).first()
    if user is None:
        raise HTTPException(400, "Invalid or expired code")
    # Batch 7 (RLS): the code proves this email -- scope the session
    # to the user before reading or mutating their verification rows.
    set_rls_user(db, user.id)
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
    return _auth_out(response, db, user)


@app.post(f"{V1}/auth/resend-code")
def resend_code(body: ResendCodeIn, db: Session = Depends(get_db)):
    """Re-sends the signup code. The response and the rate limit are
    the same for existing and unknown emails — no enumeration."""
    ratelimit.check_resend_allowed(body.email)
    user = db.query(User).filter_by(email=body.email).first()
    if user is not None and not user.email_verified:
        # Batch 7 (RLS): scope to the user before issuing a new code.
        set_rls_user(db, user.id)
        _issue_email_code(db, user)
    ratelimit.record_resend(body.email)
    return {"ok": True, "message": _REGISTER_MESSAGE}


def _issue_reset_token(db: Session, user: User) -> bool:
    """Creates a single-use reset token row and mails the link.
    Returns True if it was sent — the dev outbox counts as sent.

    Batch 6, N2: like _issue_email_code, the old token stays valid
    until the new one is actually sent. The old rows are only deleted
    AFTER a successful send; if the send fails, the new row is
    deleted instead and the old token keeps working.
    """
    # Batch 7 (RLS): forgot-password runs pre-auth -- scope first.
    set_rls_user(db, user.id)
    raw = secrets.token_urlsafe(32)
    row = PasswordResetToken(
        user_id=user.id, token_hash=_hash_code(raw),
        expires_at=datetime.utcnow() + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES),
    )
    db.add(row)
    db.commit()
    reset_url = f"{FRONTEND_URL}/auth/reset?token={raw}"
    sent = mailer.send_password_reset(user.email, reset_url)
    if sent:
        # Batch 7 (RLS): a commit sits between the INSERT and this
        # delete -- the hook re-applies the context, this call is
        # belt-and-braces so the delete never silently drops to 0 rows.
        set_rls_user(db, user.id)
        db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.id != row.id,
            PasswordResetToken.used_at.is_(None)).delete()
    else:
        db.delete(row)
    db.commit()
    return sent


@app.post(f"{V1}/auth/forgot-password")
def forgot_password(body: ForgotPasswordIn, db: Session = Depends(get_db)):
    """Starts a password reset (Batch 6, N2). The response is identical
    whether the email exists or not — no account enumeration.
    Rate-limited per email (1/min, 5/hour). The reset link is
    single-use, 30 minutes. Note the Resend test-domain limit: until
    a custom domain is live, the mail only delivers to the account
    owner's own address."""
    ratelimit.check_forgot_allowed(body.email)
    ratelimit.record_forgot(body.email)
    user = db.query(User).filter_by(email=body.email).first()
    if user is not None:
        # Batch 7 (RLS): scope to the user before issuing a reset token.
        set_rls_user(db, user.id)
        _issue_reset_token(db, user)
    return {"ok": True,
            "message": "If an account exists for this email, a reset link was sent."}


@app.post(f"{V1}/auth/reset-password")
def reset_password(body: ResetPasswordIn, request: Request, db: Session = Depends(get_db)):
    """Completes a password reset (Batch 6, N2). Every failure is the
    same generic 400 — the token is never confirmed to exist. On
    success the token is consumed and ALL refresh tokens are revoked,
    so every other session is signed out."""
    ip = _client_ip(request)
    ratelimit.check_reset_attempt_allowed(ip)
    ratelimit.record_reset_attempt(ip)
    row = db.query(PasswordResetToken).filter_by(token_hash=_hash_code(body.token)).first()
    if row is None or row.used_at is not None or row.expires_at < datetime.utcnow():
        raise HTTPException(400, "Invalid or expired reset link")
    user = db.query(User).get(row.user_id)
    if user is None:
        raise HTTPException(400, "Invalid or expired reset link")
    # Batch 7 (RLS): the token proves this account -- scope the session
    # to the user before mutating the token or the password.
    set_rls_user(db, user.id)
    row.used_at = datetime.utcnow()
    user.password_hash = hash_password(body.new_password)
    db.commit()
    revoke_all_refresh_tokens(db, user.id)
    return {"ok": True, "message": "Password reset — sign in with your new password"}


@app.post(f"{V1}/auth/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
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
    return _auth_out(response, db, user)


@app.get(f"{V1}/auth/google")
def google_auth_url():
    """Returns the Google authorization URL the frontend redirects to.
    503 until the OAuth client is configured (client ID/secret in env).
    """
    if not google_oauth.is_configured():
        raise HTTPException(503, "Google sign-in is not configured yet")
    return {"auth_url": google_oauth.build_auth_url(google_oauth.build_state())}


@app.post(f"{V1}/auth/google/callback")
def google_callback(body: GoogleCallbackIn, response: Response, db: Session = Depends(get_db)):
    """Exchanges Google's authorization code for CP Compass tokens.

    Finds the user by google_id, else by email (linking the Google
    account to an existing email+password account — never a duplicate
    row). New users are created with email_verified=True: Google
    already verified the email, so no Resend code is needed. A
    TOTP-enabled user gets the second-step response, exactly like
    password login — Google does not skip 2FA.
    """
    if not google_oauth.is_configured():
        raise HTTPException(503, "Google sign-in is not configured yet")
    if not google_oauth.verify_state(body.state):
        raise HTTPException(
            400, "Invalid or expired sign-in session — please try again")
    try:
        tokens = google_oauth.exchange_code(body.code)
        claims = google_oauth.fetch_userinfo(tokens["access_token"])
    except google_oauth.GoogleOAuthError:
        raise HTTPException(502, "Google sign-in failed — please try again")
    email = (claims.get("email") or "").strip().lower()
    sub = claims.get("sub")
    if not email or not sub or not claims.get("email_verified"):
        raise HTTPException(400, "Google did not return a verified email")
    user = db.query(User).filter_by(google_id=sub).first()
    if user is None:
        # Case-insensitive email match: Google treats the whole address
        # case-insensitively, but password signup stores it as typed.
        user = db.query(User).filter(func.lower(User.email) == email).first()
        if user is not None:
            if user.google_id is not None and user.google_id != sub:
                raise HTTPException(
                    400, "This email is already linked to a different Google account")
            user.google_id = sub
            user.email_verified = True
            # Batch 7 (RLS): scope before the link UPDATE commits --
            # the users UPDATE policy needs a context.
            set_rls_user(db, user.id)
        else:
            user = User(email=email, password_hash=None, google_id=sub,
                        email_verified=True)
            db.add(user)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                400, "This Google account is already linked to another account")
    # Batch 7 (RLS): the create path has no id until the commit --
    # scope now (idempotent on the link path, already set above).
    set_rls_user(db, user.id)
    if user.totp_enabled:
        return {"totp_required": True,
                "pre_token": create_totp_pending_token(user.id),
                "email": user.email}
    return _auth_out(response, db, user)


@app.post(f"{V1}/auth/2fa/verify", response_model=AuthOut)
def totp_verify(body: TotpVerifyIn, response: Response, db: Session = Depends(get_db)):
    """Second login step (audit F6): exchanges the 5-minute pre-auth
    token + a 6-digit authenticator code — or a single-use backup code
    — for real tokens. 5 wrong codes in 15 minutes -> 429."""
    user_id = decode_totp_pending_token(body.pre_token)
    if user_id is None:
        raise HTTPException(401, "Invalid or expired login session — log in again")
    user = db.query(User).get(user_id)
    if user is None or not user.totp_enabled:
        raise HTTPException(401, "Invalid or expired login session — log in again")
    # Batch 7 (RLS): the pre_token proves the password step -- scope
    # the session before reading backup codes / the TOTP secret.
    set_rls_user(db, user.id)
    ratelimit.check_totp_allowed(user.id)
    code = body.code.strip().replace(" ", "").replace("-", "")
    for row in db.query(BackupCode).filter_by(user_id=user.id, used_at=None).all():
        if totp.backup_code_matches(code, row.code_hash):
            row.used_at = datetime.utcnow()
            db.commit()
            ratelimit.record_totp_success(user.id)
            return _auth_out(response, db, user)
    secret_row = db.query(TotpSecret).filter_by(user_id=user.id).first()
    secret = totp.decrypt_secret(secret_row.secret_encrypted) if secret_row else None
    if secret is None or not totp.verify_code(secret, code):
        ratelimit.record_totp_failure(user.id)
        raise HTTPException(401, "Wrong code")
    ratelimit.record_totp_success(user.id)
    return _auth_out(response, db, user)


@app.post(f"{V1}/auth/refresh", response_model=AuthOut)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    """Rotates the refresh token from the cp_refresh cookie (Batch 6,
    N4). The CSRF token is NOT rotated here (a005): rotating every 15
    minutes races parallel tabs. The frontend keeps its copy."""
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise HTTPException(401, "Invalid or expired refresh token")
    result = refresh_tokens(db, raw)
    if result is None:
        raise HTTPException(401, "Invalid or expired refresh token")
    tokens, user_id = result
    user = db.query(User).get(user_id)
    set_auth_cookies(response, tokens["access_token"], tokens["refresh_token"])
    return AuthOut(email=user.email if user else "",
                    cf_handle=_cf_handle(db, user) if user else None)


@app.post(f"{V1}/auth/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw or not revoke_refresh_token(db, raw):
        raise HTTPException(401, "Invalid refresh token")
    clear_auth_cookies(response)
    return {"ok": True}


@app.post(f"{V1}/auth/logout-all")
def logout_all(response: Response, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    clear_auth_cookies(response)
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
    # Batch 7 (RLS): under RLS this only ever sees the caller's own
    # accounts, so `taken` is always None here -- the handle_norm
    # UNIQUE constraint in _link_handle is the real cross-user guard
    # (same 400, via IntegrityError). The check still works on SQLite.
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


# SSE stream constants: poll the DB job row every second; a heartbeat
# comment every 15 s keeps proxies from killing an idle stream; the
# stream never lives longer than 10 minutes (the client falls back to
# polling after that).
SSE_POLL_S = 1.0
SSE_HEARTBEAT_S = 15.0
SSE_MAX_S = 600.0


def _job_state(job) -> dict:
    if job is None:
        return {"status": "never", "total_synced": 0,
                "last_synced_at": None, "error": None}
    return {"status": job.status, "total_synced": job.total_synced,
            "last_synced_at": job.last_synced_at.isoformat()
            if job.last_synced_at else None,
            "error": job.error}


@app.get(f"{V1}/sync/stream")
async def sync_stream(request: Request, user: User = Depends(get_current_user)):
    """Live sync progress over Server-Sent Events (batch 5; cookie auth
    in batch 6, N4).

    EventSource sends cookies with withCredentials, so the access
    token no longer travels as ?token= (deleted — a URL token lands in
    server logs, browser history, and the Referer header). The stream
    only ever exposes the caller's own latest job. Origin-checked
    (a001's supplement): EventSource always sends Origin. Events: an
    immediate `state` event, `progress` whenever total_synced/status
    changes, a terminal `done` / `failed` event, then the server
    closes. No job yet: one `state` event ({status: "never"}) and
    close. `: ping` heartbeat comments every 15 s. 401 when the cookie
    is missing or invalid.
    """
    origin = request.headers.get("origin")
    if origin is None or origin not in CORS_ORIGINS:
        raise HTTPException(403, "Forbidden origin")
    ratelimit.check_endpoint_allowed("sync/stream", str(user.id))
    user_id = user.id

    async def _generate():
        # Fresh import: app.db.SessionLocal is rebound by the test
        # harness, so resolve it here, not from main.py's import-time
        # binding (same pattern as sync._run_job_sync).
        from .db import SessionLocal as _stream_session
        started = time.monotonic()
        last_key = None
        last_beat = time.monotonic()
        first = True
        while True:
            if time.monotonic() - started > SSE_MAX_S:
                break
            db = _stream_session()
            try:
                # Batch 7 (RLS): this session is separate from the
                # request's -- scope it to the stream owner, or the
                # job reads below always return "never".
                set_rls_user(db, user_id)
                if db.query(User).get(user_id) is None:
                    yield "event: error\ndata: " + json.dumps(
                        {"detail": "User not found"}) + "\n\n"
                    break
                state = _job_state(sync_engine.latest_job(db, user_id))
            finally:
                db.close()
            key = (state["status"], state["total_synced"])
            if key != last_key:
                last_key = key
                last_beat = time.monotonic()
                if first:
                    first = False
                    yield "event: state\ndata: " + json.dumps(state) + "\n\n"
                    if state["status"] in ("done", "failed"):
                        yield "event: " + state["status"] + "\ndata: " + json.dumps(state) + "\n\n"
                        break
                    if state["status"] == "never":
                        break
                elif state["status"] in ("done", "failed"):
                    yield "event: " + state["status"] + "\ndata: " + json.dumps(state) + "\n\n"
                    break
                else:
                    yield "event: progress\ndata: " + json.dumps(state) + "\n\n"
            elif time.monotonic() - last_beat >= SSE_HEARTBEAT_S:
                last_beat = time.monotonic()
                yield ": ping\n\n"
            await asyncio.sleep(SSE_POLL_S)

    return StreamingResponse(
        _generate(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no",
                 "Connection": "keep-alive"})


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
async def recommendation_action(body: FeedbackIn, user: User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    action = body.action
    if action == "not_interested":  # legacy frontend name
        action = "dismissed"
    if action not in ("later", "dismissed", "interested"):
        raise HTTPException(400, "Unknown action")
    # Hardening H7: don't let arbitrary (contest_id, index) pollute the
    # shared problem catalog. If the problem is already known locally no
    # check is needed; otherwise validate it against the Codeforces
    # problemset (cached 1h). If Codeforces is unreachable, fall back to
    # the old behaviour so a click never breaks on a CF outage.
    known = db.query(Problem).filter_by(
        contest_id=body.contest_id, index=body.index,
        platform="codeforces").first()
    if known is None:
        try:
            problems = await cf.problemset()
        except CFError:
            problems = None
        if problems is not None:
            ids = {(p.get("contestId"), p.get("index")) for p in problems}
            if (body.contest_id, body.index) not in ids:
                raise HTTPException(404, "Unknown problem")
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


def _ics_escape(text: str) -> str:
    return (text.replace("\\", "\\\\").replace(";", "\\;")
            .replace(",", "\\,").replace("\n", "\\n"))


@app.get(f"{V1}/calendar/export.ics")
async def export_calendar_ics(user: User = Depends(get_current_user)):
    """Upcoming Codeforces contests as an .ics file (batch 5)."""
    ratelimit.check_endpoint_allowed("calendar/export.ics", str(user.id))
    try:
        contests = await cf.contest_list()
    except CFError as exc:
        raise HTTPException(502, f"Codeforces didn't respond: {exc}")
    now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0",
             "PRODID:-//CP Compass//Codeforces Contests//EN",
             "CALSCALE:GREGORIAN", "METHOD:PUBLISH"]
    for c in contests:
        if c.get("phase") != "BEFORE":
            continue
        start = c.get("startTimeSeconds")
        if start is None:
            continue
        duration = c.get("durationSeconds") or 0
        dtstart = datetime.utcfromtimestamp(start).strftime("%Y%m%dT%H%M%SZ")
        dtend = datetime.utcfromtimestamp(start + duration).strftime("%Y%m%dT%H%M%SZ")
        lines += ["BEGIN:VEVENT",
                  f"UID:contest-{c.get('id')}@cp-compass",
                  f"DTSTAMP:{now}",
                  f"DTSTART:{dtstart}",
                  f"DTEND:{dtend}",
                  f"SUMMARY:{_ics_escape(str(c.get('name', '')))}",
                  f"URL:https://codeforces.com/contest/{c.get('id')}",
                  "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return Response(content="\r\n".join(lines) + "\r\n",
                    media_type="text/calendar",
                    headers={"Content-Disposition":
                             'attachment; filename="codeforces-contests.ics"'})


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


# ---------- AI Hint Ladder ----------
class HintIn(BaseModel):
    step: int = Field(..., ge=1, le=3)
    lang: str = "en"


async def _hint_problem(db, contest_id, index, user_id):
    """(Problem row, detail dict) for the hint endpoints, or (None, None)
    when the problem exists nowhere. Creates the catalog row from the
    public CF problemset when the problem is not local yet, so the hint
    has a problem to attach to."""
    detail = services.problem_detail(db, user_id, contest_id, index)
    if detail is not None:
        prob = db.query(Problem).filter_by(
            contest_id=contest_id, index=index, platform="codeforces").first()
        return prob, detail
    try:
        problems = await cf.problemset()
    except CFError as exc:
        raise HTTPException(502, f"Codeforces didn't respond: {exc}")
    for p in problems:
        if p.get("contestId") == contest_id and p.get("index") == index:
            prob = Problem(contest_id=contest_id, index=index,
                           name=p.get("name", ""), rating=p.get("rating"),
                           tags=p.get("tags", []))
            db.add(prob)
            db.commit()
            return prob, services.problem_detail(db, user_id, contest_id, index)
    return None, None


@app.get(f"{V1}/problems/{{contest_id}}/{{index}}/hints")
async def get_hints(contest_id: int, index: str,
                    user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    prob, _detail = await _hint_problem(db, contest_id, index, user.id)
    if prob is None:
        raise HTTPException(404, "Problem not found on Codeforces")
    return {
        "configured": hints.is_configured(),
        "hints": [{"step": h.step, "text": h.text, "lang": h.lang,
                   "created_at": h.created_at.isoformat()}
                  for h in hints.get_hints(db, user.id, prob.id)],
        "used_today": hints.used_today(db, user.id),
        "limit": HINT_DAILY_LIMIT,
    }


@app.post(f"{V1}/problems/{{contest_id}}/{{index}}/hints")
async def post_hint(contest_id: int, index: str, body: HintIn,
                    user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    prob, detail = await _hint_problem(db, contest_id, index, user.id)
    if prob is None:
        raise HTTPException(404, "Problem not found on Codeforces")
    lang = body.lang if body.lang in ("en", "bn") else "en"
    try:
        text, cached = hints.unlock_hint(
            db, user,
            {"contest_id": prob.contest_id, "index": prob.index,
             "name": prob.name, "rating": prob.rating,
             "tags": prob.tags or []},
            prob.id, detail, body.step, lang)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except hints.HintNotConfigured:
        raise HTTPException(503, "AI hints are not configured yet")
    except hints.HintLimitReached as exc:
        raise HTTPException(
            429, "Daily hint limit reached — try again tomorrow",
            headers={"Retry-After": str(exc.retry_after)})
    except hints.HintError:
        raise HTTPException(
            502, "The hint service is unavailable — try again later")
    return {"step": body.step, "text": text, "cached": cached,
            "used_today": hints.used_today(db, user.id),
            "limit": HINT_DAILY_LIMIT}


# ---------- Batch 4: contest post-mortem ----------
class PostmortemAnalysisIn(BaseModel):
    lang: str = "en"


async def _contest_name_map() -> dict[int, str]:
    """{contest_id: name} from the cached CF contest list. Returns {}
    when Codeforces is unreachable - names are display-only, so callers
    degrade to None instead of failing."""
    try:
        contests = await cf.contest_list()
    except CFError:
        return {}
    return {c.get("id"): c.get("name") for c in contests
            if isinstance(c.get("id"), int)}


async def _require_known_contest(contest_id: int) -> str | None:
    """Contest name for a known contest. 404 when the contest is unknown
    to Codeforces, 502 when Codeforces does not respond."""
    try:
        contests = await cf.contest_list()
    except CFError as exc:
        raise HTTPException(502, f"Codeforces didn't respond: {exc}")
    for c in contests:
        if c.get("id") == contest_id:
            return c.get("name")
    raise HTTPException(404, "Contest not found on Codeforces")


@app.get(f"{V1}/postmortems")
async def list_postmortems(user: User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    """Batch 4: contests with >= 1 submission, most recently active first."""
    if _cf_handle(db, user) is None:
        raise HTTPException(400, "Connect your Codeforces handle first")
    return services.postmortem_list(db, user.id, await _contest_name_map())


@app.get(f"{V1}/postmortems/latest")
async def latest_postmortem(user: User = Depends(get_current_user),
                           db: Session = Depends(get_db)):
    if _cf_handle(db, user) is None:
        raise HTTPException(400, "Connect your Codeforces handle first")
    items = services.postmortem_list(db, user.id, await _contest_name_map())
    if not items:
        raise HTTPException(404, "No contest submissions yet")
    first = items[0]
    return services.postmortem(db, user.id, first["contest_id"],
                               first["contest_name"])


@app.get(f"{V1}/postmortems/{{contest_id}}")
async def get_postmortem(contest_id: int,
                        user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    """Batch 4: full post-mortem for one contest. A known contest with no
    user submissions returns 200 with has_data false - never a fabricated
    report (e.g. Round 1138 for a user who did not play it)."""
    if _cf_handle(db, user) is None:
        raise HTTPException(400, "Connect your Codeforces handle first")
    name = await _require_known_contest(contest_id)
    return services.postmortem(db, user.id, contest_id, name)


@app.get(f"{V1}/postmortems/{{contest_id}}/analysis")
async def get_postmortem_analysis(contest_id: int,
                                 user: User = Depends(get_current_user),
                                 db: Session = Depends(get_db)):
    if _cf_handle(db, user) is None:
        raise HTTPException(400, "Connect your Codeforces handle first")
    await _require_known_contest(contest_id)
    row = postmortem_ai.get_analysis(db, user.id, contest_id)
    return {
        "analysis": row.text if row else None,
        "lang": row.lang if row else None,
        "model": row.model if row else None,
        "created_at": row.created_at.isoformat() if row else None,
        "configured": postmortem_ai.is_configured(),
        "used_today": postmortem_ai.used_today(db, user.id),
        "limit": POSTMORTEM_DAILY_LIMIT,
    }


@app.post(f"{V1}/postmortems/{{contest_id}}/analysis")
async def post_postmortem_analysis(contest_id: int, body: PostmortemAnalysisIn,
                                  user: User = Depends(get_current_user),
                                  db: Session = Depends(get_db)):
    if _cf_handle(db, user) is None:
        raise HTTPException(400, "Connect your Codeforces handle first")
    name = await _require_known_contest(contest_id)
    report = services.postmortem(db, user.id, contest_id, name)
    lang = body.lang if body.lang in ("en", "bn") else "en"
    try:
        text, cached = postmortem_ai.generate_analysis(
            db, user, report, services.failure_patterns(db, user.id), lang)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except postmortem_ai.PostmortemNotConfigured:
        raise HTTPException(503, "Post-mortem analysis is not configured yet")
    except postmortem_ai.PostmortemLimitReached as exc:
        raise HTTPException(
            429, "Daily analysis limit reached - try again tomorrow",
            headers={"Retry-After": str(exc.retry_after)})
    except postmortem_ai.PostmortemError:
        raise HTTPException(
            502, "The analysis service is unavailable - try again later")
    return {"contest_id": contest_id, "text": text, "cached": cached,
            "used_today": postmortem_ai.used_today(db, user.id),
            "limit": POSTMORTEM_DAILY_LIMIT}
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


@app.post(f"{V1}/settings/public-profile")
def set_public_profile(body: PublicProfileIn, user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    """Opt-in toggle for the public profile (batch 5). Default OFF."""
    ratelimit.check_endpoint_allowed("settings/public-profile", str(user.id))
    user.public_profile = bool(body.public)
    db.commit()
    return {"public_profile": bool(user.public_profile)}


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


# ---------- public profile (batch 5, no auth) ----------
@app.get(f"{V1}/u/{{handle}}")
def public_profile(handle: str, request: Request, db: Session = Depends(get_db)):
    """Public profile. 404 when the handle has no account OR the user
    has not opted in - the two cases are deliberately indistinguishable.
    Only aggregate stats; no email, no user id, no submission data."""
    ratelimit.check_endpoint_allowed("u/handle", _client_ip(request))
    account = db.query(CfAccount).filter_by(handle_norm=handle.lower()).first()
    if account is None:
        raise HTTPException(404, "Profile not found")
    user = db.query(User).get(account.user_id)
    if user is None or not user.public_profile:
        raise HTTPException(404, "Profile not found")
    # Batch 7 (RLS): the user opted in to a public profile -- scope
    # this (unauthenticated) request to them so the aggregate reads
    # below are visible to the policy. Nothing else in this request
    # runs after it.
    set_rls_user(db, user.id)
    return services.public_profile_stats(db, user)


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


@app.get(f"{V1}/demo/postmortems")
def demo_postmortems():
    return seed.postmortems_list_payload()


@app.get(f"{V1}/demo/postmortems/latest")
def demo_latest_postmortem():
    items = seed.postmortems_list_payload()
    if not items:
        raise HTTPException(404, "No contest submissions yet")
    first = items[0]
    return seed.postmortem_payload(first["contest_id"])


@app.get(f"{V1}/demo/postmortems/{{contest_id}}")
def demo_postmortem(contest_id: int):
    report = seed.postmortem_payload(contest_id)
    if report is None:
        raise HTTPException(404, "Contest not found in the demo data")
    return report

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

