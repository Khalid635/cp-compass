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
            raise HTTPException(
                429, f"Too many failed login attempts — try again in {retry} seconds",
                headers={"Retry-After": str(retry)})
        ip_bucket = _prune(_ip_failures[ip], LOGIN_FAILURE_WINDOW_S, now)
        _ip_failures[ip] = ip_bucket
        if len(ip_bucket) >= LOGIN_MAX_PER_IP:
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


def record_login_success(email: str) -> None:
    with _lock:
        _account_buckets.pop(email.strip().lower(), None)


def check_totp_allowed(user_id: int) -> None:
    """Raises 429 after 5 wrong second-factor codes in 15 minutes."""
    now = time.monotonic()
    with _lock:
        bucket = _prune(_totp_failures[user_id], LOGIN_FAILURE_WINDOW_S, now)
        _totp_failures[user_id] = bucket
        if len(bucket) >= LOGIN_MAX_FAILURES:
            raise HTTPException(
                429, "Too many wrong codes — try again in 15 minutes",
                headers={"Retry-After": str(LOGIN_LOCKOUT_S)})


def record_totp_failure(user_id: int) -> None:
    now = time.monotonic()
    with _lock:
        _totp_failures[user_id] = _prune(
            _totp_failures[user_id], LOGIN_FAILURE_WINDOW_S, now)
        _totp_failures[user_id].append(now)


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
            raise HTTPException(
                429, "A code was just sent — wait a minute before asking again",
                headers={"Retry-After": "60"})
        if len(bucket) >= 5:
            raise HTTPException(
                429, "Too many codes sent — try again in an hour",
                headers={"Retry-After": "3600"})


def record_resend(email: str) -> None:
    with _lock:
        _resend_times[email.strip().lower()].append(time.monotonic())


def reset() -> None:
    """Test helper: clears every in-memory bucket."""
    with _lock:
        _account_buckets.clear()
        _ip_failures.clear()
        _totp_failures.clear()
        _resend_times.clear()
