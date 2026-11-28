"""Structured audit logging (Batch 6, reel 27-check #8).

One JSON line per security event on the "cpcompass.audit" logger, so
Render's log stream carries a searchable record of suspicious
activity: failed logins, lockouts, rate-limit 429s, refresh-token
reuse revocations, TOTP failures. No passwords, codes or tokens are
ever logged — only the event, the (lowercased) email or user id, and
the client IP.

The logger carries its own stdout handler (uvicorn's default logging
config leaves the root logger at WARNING, so a bare logger.info would
never print in production). Records also propagate, so pytest's
caplog sees them.
"""
import json
import logging
from datetime import datetime

logger = logging.getLogger("cpcompass.audit")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setLevel(logging.INFO)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(_handler)


def log(event: str, *, ip: str | None = None, email: str | None = None,
        user_id: int | None = None, detail: str | None = None) -> None:
    """Emits one audit event. Never logs secrets — callers pass only
    the event, the ip/email/user_id, and a short detail string."""
    record = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "event": event,
    }
    if ip is not None:
        record["ip"] = ip
    if email is not None:
        record["email"] = email.strip().lower()
    if user_id is not None:
        record["user_id"] = user_id
    if detail is not None:
        record["detail"] = detail
    logger.info(json.dumps(record))
