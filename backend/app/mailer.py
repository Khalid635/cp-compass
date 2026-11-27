"""Pluggable mailer for the email-verification code (Batch 1 / audit F6).

- Production: Resend (https://api.resend.com/emails) when RESEND_API_KEY
  is set in the environment. The key is never in code and never printed.
- Local dev: the code is appended to backend/dev_outbox.log — the Hisab
  AI pattern (local SMTP was never configured there either). The file is
  gitignored (*.log).

No SMS: sending codes by SMS costs money per message, so email code +
authenticator app is the whole second-factor story.
"""
import json
import os
from datetime import datetime

import httpx

from .config import MAIL_DEV_OUTBOX, MAIL_FROM, RESEND_API_KEY

RESEND_URL = "https://api.resend.com/emails"


def send_verification_code(email: str, code: str) -> bool:
    """Sends the 6-digit signup code. Returns True on success.
    Never raises — callers log and decide (dev mode always succeeds by
    writing the outbox; a failed Resend call in production is a 503)."""
    subject = "Your CP Compass verification code"
    text = (
        f"Your CP Compass verification code is: {code}\n\n"
        "It expires in 15 minutes. If you didn't create this account, "
        "ignore this email."
    )
    if RESEND_API_KEY:
        try:
            resp = httpx.post(
                RESEND_URL,
                headers={
                    "Authorization": f"Bearer {RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={"from": MAIL_FROM, "to": [email],
                      "subject": subject, "text": text},
                timeout=15,
            )
            if resp.status_code in (200, 201):
                return True
            print(f"[mailer] Resend rejected the email: {resp.status_code}")
            return False
        except Exception as exc:  # noqa: BLE001 — mail failure is not fatal
            print(f"[mailer] Resend call failed: {exc}")
            return False
    # Dev mode: write to the local outbox (never print the code to stdout
    # in production logs either — the file is the dev-only channel).
    try:
        os.makedirs(os.path.dirname(MAIL_DEV_OUTBOX) or ".", exist_ok=True)
        with open(MAIL_DEV_OUTBOX, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "to": email,
                "subject": subject,
                "code": code,
                "sent_at": datetime.utcnow().isoformat() + "Z",
            }) + "\n")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[mailer] dev outbox write failed: {exc}")
        return False
