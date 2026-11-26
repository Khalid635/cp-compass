"""CP Compass backend — config."""
import os

from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-secret-change-me")
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./cpcompass.db")
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
