# Google OAuth sign-in — spec (light)

Batch: google-oauth. Repo `D:\Projects\cp-compass`, base `69185fe`.
Khalid approved 2026-11-28 00:15 ("Google sign-in যোগ করো"); tonight he
said chain the batches with no stopping — this runs right after
landing-fixes. One batch, one commit.

## Why

Login today is email + password only. Google sign-in is the missing
button Khalid spotted on the login page — and it also bypasses the
Resend bottleneck: a Google-verified email is already verified, so
Google users can sign up without any verification email.

## Design (verified against the code 2026-11-28 ~01:50)

- **Callback route: none exists yet.** App.tsx routes are `/`, `/privacy`,
  `/login`, `/register`, `/demo/*`, `/app/*`. This batch CREATES
  `/auth/callback` (new `GoogleCallbackPage`) — the redirect URIs
  registered in Google Cloud are
  `https://cp-compass-phi.vercel.app/auth/callback` (prod) and
  `http://localhost:5173/auth/callback` (dev).
- **Flow (SPA pattern):** button → `GET /api/v1/auth/google` returns
  `{auth_url}` → browser navigates to Google → Google redirects to the
  frontend `/auth/callback?code&state` → page POSTs
  `{code, state}` to `/api/v1/auth/google/callback` → backend exchanges
  the code, fetches userinfo, finds/creates the user, returns AuthOut
  (same shape as password login).
- **State:** HMAC-SHA256-signed, 10-minute expiry, `SECRET_KEY` as the
  key (stateless — no DB row, survives Render restarts). No PKCE:
  this is a confidential client (the backend holds the client secret),
  and PKCE would need server-side verifier storage; the signed state
  already binds the flow. Documented, not an oversight.
- **Users:** new module `backend/app/google_oauth.py` (auth URL,
  state sign/verify, token exchange, userinfo via httpx — already a
  dependency). Endpoints in `main.py` next to the other auth routes.
- **Linking:** find by `google_id` first, else by email. Existing
  email+password account with the same email is LINKED (google_id set,
  email_verified=True) — never a duplicate row; password login keeps
  working. A Google account already linked to a different email → 400.
- **Google-only users:** `password_hash` becomes nullable (migration
  0005, batch_alter_table so it works on SQLite dev + Postgres prod).
  Password login for them → 401, no crash (verify_password handles
  None). Google userinfo must have `email_verified=true` or the
  callback is rejected.
- **2FA respected:** a TOTP-enabled user signing in via Google gets
  `{totp_required, pre_token}` exactly like password login — Google
  does not skip the second factor.
- **Not configured:** until the OAuth client exists and
  `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` are set on Render,
  `GET /api/v1/auth/google` returns 503 "Google sign-in is not
  configured yet" and the button still renders. Config values are read
  lazily at call time so tests can monkeypatch `app.config`.
- **Secrets:** client ID/secret live in Render env only, never in code;
  `.env.example` documents the three var NAMES only.

## Frontend

- `api.googleAuthUrl()` / `api.googleCallback(code, state)` in
  `client.ts`; `startGoogleSignIn()` + `completeGoogleSignIn()` in
  `useAuth.tsx` (same token-store + `api.me()` pattern as login).
- Google button on the login AND register pages (shared `AuthPage`
  form step): divider + secondary button with an inline Google "G"
  SVG (lucide has no brand icons). Email+password untouched.
- i18n keys in dict.ts + en.ts + bn.ts: `continueWithGoogle`,
  `orContinueWith`, `googleSignInError`.

## Tests (new `backend/tests/test_google_oauth.py`, same harness as
`test_security.py` — throwaway SQLite, mocked Google)

New user, existing-user link (+ password login still works), duplicate
Google account → 400, bad/expired state → 400, unverified Google
email → 400, exchange failure → 502, Google-only password login →
401, TOTP user → totp_required, not-configured → 503. Frontend build
(tsc + vite) passes. The 2 pre-existing UTC-vs-local flakes
(test_10/test_11) fail only 00:00–06:00 Dhaka — do not chase them.
Migration 0005 is verified separately on a scratch SQLite DB
(`alembic upgrade head`); tests use `create_all`, not migrations.

## Deploy + verify

One commit, push via askpass. Deploy signal: `GET /api/v1/auth/google`
goes 404 → 503 (route exists, not configured). Live: health 200,
/docs 404, Google button renders on the live login page (desktop +
true-390 mobile shots). Full E2E (consent screen with the real
client_id) is BLOCKED on the browser task below — do not fake it.

## Out of scope (browser task for the parent agent — this subagent
cannot drive a live browser)

Google Cloud Console on Khalid's signed-in Chrome: create/select
project "CP Compass", consent screen (External, app name "CP
Compass"), Web-application OAuth client with the two redirect URIs
above. Then set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`,
`GOOGLE_REDIRECT_URI=https://cp-compass-phi.vercel.app/auth/callback`
on Render (service cp-compass-api) and re-verify the consent
redirect. Full E2E sign-in needs Khalid's own click — never complete
a real sign-in with his account.

## Known limits (not fixed in this batch)

- Google-only users cannot disable 2FA, regenerate backup codes, or
  delete their account — those endpoints require a password they never
  set. Proper fix is a "set password" option in Settings (follow-up).
- No GitHub OAuth in this batch (later if Khalid wants it).
