"""CP Compass backend — config."""
import os

from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-secret-change-me")
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./cpcompass.db")
CF_API_BASE = os.environ.get("CF_API_BASE", "https://codeforces.com/api")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "10080"))

# Codeforces allows at most 1 API call per 2 seconds.
CF_MIN_INTERVAL_S = 2.0
# Max seconds a "running" sync job may be stale before it is treated as dead.
SYNC_STALE_AFTER_S = 3600
