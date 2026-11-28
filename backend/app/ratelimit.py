"""In-memory login brute-force protection (Batch 1 / audit F2).

Single-worker app (Render free = 1 worker, dev = 1 worker), so an
in-memory limiter is consistent with the existing CF rate limiter and
sync lock. A multi-worker deploy would need a shared store (Redis) —
documented here so nobody assumes this scales as-is.

Rules:
- Per account (email): 5 failed logins in 15 minutes -> locked out for
  15 minutes (429 with Retry-After seconds).
- Per IP: 20 failed logins in 15 minutes -> 429 (stops credential
  stuffing across many accounts from one source).
- A successful login clears the account's failure bucket.
- TOTP second-factor attempts: 5 wrong codes in 15 minutes per user.
"""
import threading
import time
from collections import defaultdict

from fastapi import HTTPException

from . import audit
from .config import (
    LOGIN_FAILURE_WINDOW_S,
    LOGIN_LOCKOUT_S,
    LOGIN_MAX_FAILURES,
    LOGIN_MAX_PER_IP,
)

_lock = threading.Lock()
# email -> {"failures": [ts, ...], "locked_until": float | None}
_account_buckets: dict[str, dict] = defaultdict(
    lambda: {"failures": [], "locked_until": None})
# ip -> [ts, ...] of failures
_ip_failures: dict[str, list] = defaultdict(list)
# user_id -> [ts, ...] of failed TOTP attempts
_totp_failures: dict[int, list] = defaultdict(list)
# email -> [ts, ...] of verification-code resends (1/min, 5/hour)
_resend_times: dict[str, list] = defaultdict(list)


def _prune(bucket: list, window_s: float, now: float) -> list:
    return [ts for ts in bucket if now - ts < window_s]


def check_login_allowed(ip: str, email: str) -> None:
    """Raises 429 if the account is locked out or the IP is over its
    failure budget. Call BEFORE checking the password."""
    now = time.monotonic()
    email = email.strip().lower()
    with _lock:
        acct = _account_buckets[email]
        if acct["locked_until"] is not None and now < acct["locked_until"]:
            retry = int(acct["locked_until"] - now) + 1
            audit.log("auth.login_locked", ip=ip, email=email,
                      detail=f"retry_in_{retry}s")
            raise HTTPException(
                429, f"Too many failed login attempts — try again in {retry} seconds",
                headers={"Retry-After": str(retry)})
        ip_bucket = _prune(_ip_failures[ip], LOGIN_FAILURE_WINDOW_S, now)
        _ip_failures[ip] = ip_bucket
        if len(ip_bucket) >= LOGIN_MAX_PER_IP:
            audit.log("auth.rate_limited", ip=ip, email=email,
                      detail="login per-ip")
            raise HTTPException(
                429, "Too many failed login attempts from this address",
                headers={"Retry-After": str(LOGIN_FAILURE_WINDOW_S)})


def record_login_failure(ip: str, email: str) -> None:
    now = time.monotonic()
    email = email.strip().lower()
    with _lock:
        acct = _account_buckets[email]
        acct["failures"] = _prune(acct["failures"], LOGIN_FAILURE_WINDOW_S, now)
        acct["failures"].append(now)
        if len(acct["failures"]) >= LOGIN_MAX_FAILURES:
            acct["locked_until"] = now + LOGIN_LOCKOUT_S
            acct["failures"] = []
        _ip_failures[ip] = _prune(_ip_failures[ip], LOGIN_FAILURE_WINDOW_S, now)
        _ip_failures[ip].append(now)
    audit.log("auth.login_failed", ip=ip, email=email)


def record_login_success(email: str) -> None:
    with _lock:
        _account_buckets.pop(email.strip().lower(), None)
    audit.log("auth.login_ok", email=email)


def check_totp_allowed(user_id: int) -> None:
    """Raises 429 after 5 wrong second-factor codes in 15 minutes."""
    now = time.monotonic()
    with _lock:
        bucket = _prune(_totp_failures[user_id], LOGIN_FAILURE_WINDOW_S, now)
        _totp_failures[user_id] = bucket
        if len(bucket) >= LOGIN_MAX_FAILURES:
            audit.log("auth.rate_limited", user_id=user_id, detail="totp")
            raise HTTPException(
                429, "Too many wrong codes — try again in 15 minutes",
                headers={"Retry-After": str(LOGIN_LOCKOUT_S)})


def record_totp_failure(user_id: int) -> None:
    now = time.monotonic()
    with _lock:
        _totp_failures[user_id] = _prune(
            _totp_failures[user_id], LOGIN_FAILURE_WINDOW_S, now)
        _totp_failures[user_id].append(now)
    audit.log("auth.totp_failed", user_id=user_id)


def record_totp_success(user_id: int) -> None:
    with _lock:
        _totp_failures.pop(user_id, None)


def check_resend_allowed(email: str) -> None:
    """Verification-code resend: at most 1 per minute, 5 per hour."""
    now = time.monotonic()
    email = email.strip().lower()
    with _lock:
        bucket = _prune(_resend_times[email], 3600, now)
        _resend_times[email] = bucket
        if bucket and now - bucket[-1] < 60:
            audit.log("auth.rate_limited", email=email, detail="resend-code")
            raise HTTPException(
                429, "A code was just sent — wait a minute before asking again",
                headers={"Retry-After": "60"})
        if len(bucket) >= 5:
            audit.log("auth.rate_limited", email=email, detail="resend-code")
            raise HTTPException(
                429, "Too many codes sent — try again in an hour",
                headers={"Retry-After": "3600"})


def record_resend(email: str) -> None:
    with _lock:
        _resend_times[email.strip().lower()].append(time.monotonic())


# --- Batch 6: password-reset buckets -------------------------------------
# email -> [ts, ...] of forgot-password requests (1/min, 5/hour, same
# shape as the resend-code bucket — its own bucket so a reset request
# never eats the signup-code budget and vice versa)
_forgot_times: dict[str, list] = defaultdict(list)
# ip -> [ts, ...] of reset-password attempts (10/hour — slows guessing
# of the 256-bit token, which is otherwise infeasible to brute force)
_reset_attempts: dict[str, list] = defaultdict(list)
# (endpoint, key) -> [ts, ...] of hits, for the per-endpoint limits in
# ENDPOINT_LIMITS below.
_endpoint_hits: dict[tuple[str, str], list] = defaultdict(list)

# endpoint -> (max hits, window seconds). Keys are the limiter names
# used at the call sites, not URL paths.
ENDPOINT_LIMITS: dict[str, tuple[int, int]] = {
    "sync/stream": (20, 3600),               # stream starts per user / hour
    "settings/public-profile": (20, 3600),   # toggles per user / hour
    "calendar/export.ics": (30, 3600),       # downloads per user / hour
    "u/handle": (100, 3600),                 # public views per IP / hour
}


def check_forgot_allowed(email: str) -> None:
    """Forgot-password: at most 1 per minute, 5 per hour, per email.
    Same shape as the resend-code bucket, but its own bucket."""
    now = time.monotonic()
    email = email.strip().lower()
    with _lock:
        bucket = _prune(_forgot_times[email], 3600, now)
        _forgot_times[email] = bucket
        if bucket and now - bucket[-1] < 60:
            audit.log("auth.rate_limited", email=email, detail="forgot-password")
            raise HTTPException(
                429, "A reset link was just sent — wait a minute before asking again",
                headers={"Retry-After": "60"})
        if len(bucket) >= 5:
            audit.log("auth.rate_limited", email=email, detail="forgot-password")
            raise HTTPException(
                429, "Too many reset links sent — try again in an hour",
                headers={"Retry-After": "3600"})


def record_forgot(email: str) -> None:
    with _lock:
        _forgot_times[email.strip().lower()].append(time.monotonic())


def check_reset_attempt_allowed(ip: str) -> None:
    """Reset-password attempts: at most 10 per hour per IP."""
    now = time.monotonic()
    with _lock:
        bucket = _prune(_reset_attempts[ip], 3600, now)
        _reset_attempts[ip] = bucket
        if len(bucket) >= 10:
            audit.log("auth.rate_limited", ip=ip, detail="reset-password")
            raise HTTPException(
                429, "Too many reset attempts — try again in an hour",
                headers={"Retry-After": "3600"})


def record_reset_attempt(ip: str) -> None:
    with _lock:
        _reset_attempts[ip].append(time.monotonic())


def check_endpoint_allowed(name: str, key: str) -> None:
    """Generic per-endpoint limit (Batch 6, section 8). One call per
    request: checks the bucket AND records the hit, so a forgotten
    record call cannot silently disable the limit. 429 with
    Retry-After when the budget is spent."""
    max_n, window_s = ENDPOINT_LIMITS[name]
    now = time.monotonic()
    with _lock:
        bucket = _prune(_endpoint_hits[(name, key)], window_s, now)
        if len(bucket) >= max_n:
            audit.log("auth.rate_limited", detail=f"endpoint:{name} key={key}")
            raise HTTPException(
                429, "Too many requests — try again later",
                headers={"Retry-After": str(window_s)})
        bucket.append(now)
        _endpoint_hits[(name, key)] = bucket


def reset() -> None:
    """Test helper: clears every in-memory bucket."""
    with _lock:
        _account_buckets.clear()
        _ip_failures.clear()
        _totp_failures.clear()
        _resend_times.clear()
        _forgot_times.clear()
        _reset_attempts.clear()
        _endpoint_hits.clear()
