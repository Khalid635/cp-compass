"""Google OAuth sign-in.

Flow (SPA pattern): the frontend asks GET /api/v1/auth/google for the
authorization URL, the browser goes to Google, Google redirects to the
frontend /auth/callback route, and the frontend POSTs {code, state} to
/api/v1/auth/google/callback, which exchanges the code and returns the
same AuthOut tokens as password login.

- State is HMAC-SHA256-signed with SECRET_KEY and expires after 10
  minutes (stateless: no DB row, survives Render restarts).
- No PKCE: this is a confidential client (the backend holds the client
  secret); PKCE would need server-side verifier storage, and the signed
  state already binds the flow.
- Config is read lazily at call time (never at import) so a missing
  client id degrades to 503 instead of a startup crash, and tests can
  monkeypatch app.config.
"""
import base64
import hashlib
import hmac
import json
import secrets
import time
from urllib.parse import urlencode

import httpx

from . import config

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_SCOPES = "openid email profile"
_STATE_TTL_S = 600  # 10 minutes
_HTTP_TIMEOUT_S = 15


class GoogleOAuthError(Exception):
    """Google (or the network) failed — surfaced as 502, no detail leaked."""


def is_configured() -> bool:
    return bool(config.GOOGLE_CLIENT_ID and config.GOOGLE_CLIENT_SECRET)


def redirect_uri() -> str:
    return config.GOOGLE_REDIRECT_URI


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def build_state() -> str:
    """Signed state: base64url(payload).hex-hmac. Payload carries an
    expiry and a random nonce; the signature binds both to SECRET_KEY."""
    payload = {"exp": int(time.time()) + _STATE_TTL_S,
               "nonce": secrets.token_urlsafe(16)}
    data = _b64(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = hmac.new(config.SECRET_KEY.encode("utf-8"), data.encode("ascii"),
                   hashlib.sha256).hexdigest()
    return f"{data}.{sig}"


def verify_state(state: str) -> bool:
    """True only if the signature matches and the state is unexpired."""
    try:
        data, sig = state.split(".", 1)
        expected = hmac.new(config.SECRET_KEY.encode("utf-8"),
                            data.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return False
        payload = json.loads(_unb64(data))
        return int(payload["exp"]) >= int(time.time())
    except (ValueError, KeyError, TypeError):
        return False


def build_auth_url(state: str) -> str:
    params = {
        "response_type": "code",
        "client_id": config.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri(),
        "scope": GOOGLE_SCOPES,
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def exchange_code(code: str) -> dict:
    """Exchanges the authorization code for Google tokens."""
    try:
        resp = httpx.post(
            GOOGLE_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri(),
                "client_id": config.GOOGLE_CLIENT_ID,
                "client_secret": config.GOOGLE_CLIENT_SECRET,
            },
            timeout=_HTTP_TIMEOUT_S,
        )
    except httpx.HTTPError as exc:
        raise GoogleOAuthError(f"token request failed: {exc}") from exc
    if resp.status_code != 200:
        raise GoogleOAuthError(f"token request failed: {resp.status_code}")
    data = resp.json()
    if not data.get("access_token"):
        raise GoogleOAuthError("token response had no access_token")
    return data


def fetch_userinfo(access_token: str) -> dict:
    """Returns Google's userinfo claims (sub, email, email_verified)."""
    try:
        resp = httpx.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=_HTTP_TIMEOUT_S,
        )
    except httpx.HTTPError as exc:
        raise GoogleOAuthError(f"userinfo request failed: {exc}") from exc
    if resp.status_code != 200:
        raise GoogleOAuthError(f"userinfo request failed: {resp.status_code}")
    return resp.json()
