"""CP Compass backend — config.

Security (Batch 1 / audit F3): SECRET_KEY must come from the environment
in any non-dev run. A hard-coded default is kept ONLY for local
development (ENV=development, the default, with a SQLite DATABASE_URL).
If the default key is used while the app looks like production — ENV is
"production", or DATABASE_URL points at a real Postgres — the process
refuses to start instead of silently issuing forgeable JWTs.
"""
import os

from dotenv import load_dotenv

load_dotenv()

ENV = os.environ.get("ENV", "development").lower()
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./cpcompass.db")

_DEV_DEFAULT_SECRET = "dev-only-insecure-secret-change-me"
SECRET_KEY = os.environ.get("SECRET_KEY", _DEV_DEFAULT_SECRET)

if SECRET_KEY == _DEV_DEFAULT_SECRET:
    _looks_like_prod = ENV == "production" or not DATABASE_URL.startswith("sqlite")
    if _looks_like_prod:
        raise RuntimeError(
            "SECRET_KEY is the insecure dev default but the app looks like "
            "production (ENV=%r, DATABASE_URL is not SQLite). Set a strong "
            "SECRET_KEY via the environment." % ENV
        )

CF_API_BASE = os.environ.get("CF_API_BASE", "https://codeforces.com/api")
JWT_ALGORITHM = "HS256"

# Access tokens are short-lived; refresh tokens (7 days) renew them.
ACCESS_EXPIRE_MINUTES = int(os.environ.get("ACCESS_EXPIRE_MINUTES", "15"))
REFRESH_EXPIRE_DAYS = int(os.environ.get("REFRESH_EXPIRE_DAYS", "7"))

# Codeforces allows at most 1 API call per 2 seconds.
CF_MIN_INTERVAL_S = 2.0

# Sync job queue: lease length, worker poll interval, max resume attempts
# for a job that keeps dying mid-run.
SYNC_LEASE_S = int(os.environ.get("SYNC_LEASE_S", "120"))
WORKER_POLL_S = int(os.environ.get("WORKER_POLL_S", "2"))
SYNC_MAX_ATTEMPTS = int(os.environ.get("SYNC_MAX_ATTEMPTS", "3"))

# CORS: comma-separated allowed origins. Local dev defaults; production
# sets this to the Vercel frontend URL (never "*" with credentials).
CORS_ORIGINS = [o.strip() for o in os.environ.get(
    "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]

# --- Batch 1: email verification + TOTP 2FA -------------------------------
# Email verification codes: 6 digits, 15 minutes, 5 attempts per code.
EMAIL_CODE_LENGTH = 6
EMAIL_CODE_EXPIRE_MINUTES = int(os.environ.get("EMAIL_CODE_EXPIRE_MINUTES", "15"))
EMAIL_CODE_MAX_ATTEMPTS = 5

# Mailer: if RESEND_API_KEY is set, codes go out via Resend; otherwise
# (local dev) they are appended to backend/dev_outbox.log — the Hisab AI
# pattern. Never put a key in code; it comes from the environment only.
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
MAIL_FROM = os.environ.get("MAIL_FROM", "CP Compass <noreply@cpcompass.app>")
MAIL_DEV_OUTBOX = os.environ.get(
    "MAIL_DEV_OUTBOX",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "dev_outbox.log"))

# TOTP 2FA (authenticator app): 30 s step, accept +-1 step of clock skew.
TOTP_ISSUER = "CP Compass"
TOTP_VALID_WINDOW = 1
BACKUP_CODE_COUNT = 10

# --- Batch 1: login brute-force protection (F2) ---------------------------
LOGIN_MAX_FAILURES = int(os.environ.get("LOGIN_MAX_FAILURES", "5"))
LOGIN_FAILURE_WINDOW_S = int(os.environ.get("LOGIN_FAILURE_WINDOW_S", "900"))  # 15 min
LOGIN_LOCKOUT_S = int(os.environ.get("LOGIN_LOCKOUT_S", "900"))  # 15 min
LOGIN_MAX_PER_IP = int(os.environ.get("LOGIN_MAX_PER_IP", "20"))  # per 15 min

# --- Batch 1: ML retrain cooldown (F5) ------------------------------------
RETRAIN_COOLDOWN_S = int(os.environ.get("RETRAIN_COOLDOWN_S", "3600"))  # 1 h / user
RETRAIN_GLOBAL_MIN_GAP_S = int(os.environ.get("RETRAIN_GLOBAL_MIN_GAP_S", "600"))  # 10 min

# --- Batch 1: request body size limit (F10) -------------------------------
MAX_BODY_BYTES = int(os.environ.get("MAX_BODY_BYTES", "1048576"))  # 1 MiB

# Minimum password length (F2): raised from 6 to 8.
MIN_PASSWORD_LENGTH = 8

# --- Google OAuth sign-in -------------------------------------------------
# Client ID/secret come from the Google Cloud Console OAuth client and
# live in the environment (Render env in production) — never in code.
# Until they are set, GET /api/v1/auth/google answers 503 and the
# frontend button is inert. The redirect URI must match one registered
# on the OAuth client exactly; the frontend /auth/callback route is the
# target in both dev and prod.
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.environ.get(
    "GOOGLE_REDIRECT_URI", "http://localhost:5173/auth/callback")
# --- AI Hint Ladder (Gemini Flash, server-side only) ----------------------
# The key lives in the environment (Render env in production) — never in
# code. Until it is set, the hint endpoints answer 503. Hints are
# generated server-side only; end users never supply their own key.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")  # 2.5-flash 404s for new keys; 3.8-flash hangs on generateContent (verified 2026-11-28)
HINT_DAILY_LIMIT = int(os.environ.get("HINT_DAILY_LIMIT", "10"))
HINT_HTTP_TIMEOUT_S = int(os.environ.get("HINT_HTTP_TIMEOUT_S", "30"))
