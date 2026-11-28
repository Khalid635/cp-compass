# Batch 6 arena task — N4 cookie + CSRF design for CP Compass

You are one of 10 competing designers. Produce the BEST concrete
design for moving CP Compass authentication from localStorage JWTs to
HttpOnly cookies + CSRF protection. The batch follows the winning
design. Aim ~1200 words, concrete and specific — names, flags,
headers, endpoint changes, and code sketches where they decide
something. No fluff, no generic advice.

## The app (facts — do not invent others)

- Stack: FastAPI backend (Python 3.14, PyJWT HS256) on Render free
  (1 worker, HTTPS only); React 19 + Vite + TypeScript frontend on
  Vercel; Neon Postgres (Singapore); SQLAlchemy; PWA with a
  hand-written service worker (precaches the app shell only — never
  any /api response; SSE bypasses the worker).
- Prod is CROSS-SITE: frontend https://cp-compass-phi.vercel.app,
  backend https://cp-compass-api-1j9a.onrender.com. Dev is plain HTTP
  localhost: frontend :5173 (vite dev) / :4173 (vite preview, listens
  [::1] only), backend 127.0.0.1:8004.
- Current auth (all to be replaced): access JWT 15 min + opaque
  refresh token 7 days, both returned in JSON and stored in
  localStorage (cp_access_token, cp_refresh_token). Refresh rotates;
  presenting an already-rotated refresh token revokes the WHOLE
  token family (theft detection). Login has per-account lockout (5
  failures / 15 min) + per-IP failure budget. TOTP 2FA is optional;
  a 5-minute totp_pending JWT bridges the second step. Google OAuth
  (authorization-code flow, HMAC-signed state) returns the same
  tokens. Logout revokes one refresh token; logout-all revokes all.
- CORS: allow_origins is an exact list (never "*"),
  allow_credentials=True, all methods/headers allowed.
- SSE: GET /api/v1/sync/stream is an EventSource stream. EventSource
  cannot send an Authorization header, so today the access JWT
  travels as ?token=<jwt> (decoded by decode_access_token_query).
  The stream only ever exposes the caller's own latest sync job.
- Frontend auth flow: api/client.ts (fetch wrapper, single-flight
  refresh on 401 + retry once), hooks/useAuth.tsx (boot = api.me(),
  login/register/verifyEmail/verifyTotp/completeGoogleSignIn all
  store tokens then call api.me()), components/layout.tsx (opens the
  EventSource while a sync runs). AuthOut today:
  {access_token, refresh_token, token_type, email, cf_handle}.
- Security headers already on: HSTS, CSP frame-ancestors 'none',
  X-Frame-Options DENY, nosniff, no-referrer, COOP same-origin,
  Permissions-Policy. /docs + /redoc + /openapi.json are 404 in prod.
- Email verification codes go via Resend (test domain: only the
  account owner's address receives mail until a custom domain is
  live). Password recovery (forgot/reset, 30-min single-use tokens)
  is being built in the same batch — it returns JSON messages only,
  no tokens.
- No new dependencies. One Render worker (in-memory rate limiters
  are acceptable). The live user base is 1 (the owner) — a
  same-day live-session migration is tolerable, but say what happens
  to a session that is live during the deploy.

## Hard constraints (your design MUST satisfy all of them)

1. Tokens leave localStorage entirely. No token in any JS-readable
   storage (no localStorage, no sessionStorage, no JS variable that
   persists across reloads).
2. Cookies must work cross-site in prod AND on plain-HTTP localhost
   in dev.
3. The SSE stream must keep working.
4. Google OAuth callback + TOTP second step must keep working.
5. Logout revokes server-side AND clears cookies.
6. Refresh rotation + reuse → revoke-family must keep working.
7. No new dependencies.

## Decide these six questions (each one explicitly, with reasons)

1. Cookie-only auth, or cookie + Authorization-header fallback?
2. CSRF mechanism: double-submit cookie, Origin/Referer check,
   SameSite-only, or a combination? Say exactly which requests are
   checked and which (if any) are exempt — and why the exempt ones
   are safe.
3. SameSite policy: None+Secure in prod / Lax in dev, or something
   else? Address the Secure flag on plain-HTTP dev.
4. CSRF token lifecycle: issued when, rotated when, stored where,
   how the frontend gets it before the first mutation (incl. the
   pre-login state: login/register/forgot/reset are mutations too).
5. SSE auth: cookie + EventSource withCredentials, or keep the
   ?token= query param? (Note: a URL token lands in server logs,
   browser history and the Referer header.)
6. What breaks if the user blocks third-party cookies, and what is
   the honest fallback? (Say what the user sees and what still works.)

## Also cover (briefly, concretely)

- Cookie names, flags (HttpOnly/Secure/SameSite/Path/Max-Age) for
  each cookie, in prod AND in dev.
- Which backend functions/endpoints change (get_current_user,
  login, verify-email, totp-verify, google callback, refresh,
  logout, logout-all, /sync/stream, the new /auth/csrf if you use
  one) and how AuthOut changes.
- Which frontend files change (client.ts, useAuth.tsx, layout.tsx,
  types) and how the 401 → refresh → retry flow works now.
- What happens to a session live during the deploy, and to the
  legacy localStorage keys left in a returning user's browser.
- The three most likely ways your design fails in production, and
  the concrete patch for each.

## Your angle (lean into it — this is what makes you different)

{ANGLE}

## Output

Write your design to this exact file (create it):
D:\Projects\cp-compass\specs\batch6\arena-run\r0\{ID}.md
Use SSH (ssh -F /home/hatch/.ssh/config kbjr07l) and a Python
heredoc (py -X utf8 -) to write the file with LF line endings.
Start the file with "# Arena {ID} — <your one-line design name>".
If writing the file fails, return the FULL text in your final report
instead. Also give a one-line summary of your design in your report.
