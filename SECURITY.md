# Rung — security notes

Audit: 2026-11-27 (full report kept in the agent workspace, not in this
repo). Batch 1 fixed + verified F1, F2, F6, F8, F9, F10. F3/F4/F5/F7 were
verified live on 2026-11-27. The hardening batch (same day) implemented
H3–H5, H7, H9, H10; H2 (8-char minimum password) and H8 (security tests)
were already in Batch 1. H6 (calendar year validation) was already in the
code and was verified live.

## H1 — Tokens in localStorage: DEFERRED (deliberate)

Access + refresh tokens live in `localStorage`
(`frontend/src/api/client.ts`). Moving the refresh token to HttpOnly
cookies is a real auth migration, not a patch: cross-origin (Vercel
frontend → Render backend) needs `SameSite=None; Secure` cookies + CSRF
tokens + a frontend client rewrite (interceptor, logout, refresh flow) +
demo-mode handling. Half-doing it (cookies without CSRF) would be worse
than the status quo.

Residual risk: any future XSS becomes instant account takeover via the
7-day refresh token. Mitigations in place today:

- The 2026-11-27 audit found zero XSS sinks; CSP `frame-ancestors 'none'`
  (H5) plus `X-Frame-Options: DENY` block framing.
- Refresh-token reuse detection (F4, verified live): the first replay of
  a rotated token revokes the whole token family, so a stolen chain dies
  on first use by either party.
- Access tokens expire in 15 minutes; refresh tokens in 7 days.

Revisit when the frontend gets a proper cookie-based auth pass with CSRF.

## H10 — Model artifact (joblib.load)

`backend/app/ml.py` loads `ml_model.joblib` only from a fixed server-side
path (`MODEL_PATH`); the path is never user-influenced. `_load_artifact()`
additionally rejects any artifact that is not a dict with the exact shape
`train_model()` writes (`metadata` dict + `model` + `feature_names` +
`top_tags`). Never let the artifact path become user-influenced.

## Dependencies

`python-jose` was removed 2026-11-27 (security-fixes batch) and replaced
by `PyJWT==2.15.1` (0 OSV vulns at that version): python-jose 3.5.0 has
GHSA-3qf3-8w2g-rqmx and is unmaintained (last release 2022) with no fixed
release. The app verifies HS256 symmetric tokens only, so the
algorithm-confusion issue was not directly exploitable here.

## Email verification (ops)

Verification codes are sent via Resend only when `RESEND_API_KEY` is set
on Render. Without it, codes go to the container's ephemeral
`dev_outbox.log` and no live user can verify — check Gmail delivery after
any Render env change.
