# Batch 6 — security fixes N1–N4 + reel 27-check leftovers + cache-bust + sync wart

Status: spec first, then a 10-agent spawn probe on the cookie+CSRF
design (full-100 tournament is INFEASIBLE in this host — 595 calls,
70 waves, ~9h; proven in Batch 5, recorded in
specs/batch5/arena-result.md), then build.
Base: 80c3d8c (Batch 5). All items ordered by Khalid ("Thik korba shob
gulo", 2026-11-28 11:26). Laptop only, via SSH. Commit ONLY batch6
files. Backend security is automatic (standing rule): rate limits on
EVERY sensitive endpoint, no enumeration oracle, pinned deps, no
secrets in code/bundle/logs, DB-backed probes after deploy.

## 0. The arena decision — N4 cookie + CSRF design

The most consequential decision in this batch. Hard constraints
(non-negotiable, the probe must satisfy all of them):

- Tokens leave localStorage entirely; no token in any JS-readable
  storage (no localStorage, no sessionStorage, no JS variable that
  persists across reloads).
- Prod is cross-site: frontend https://cp-compass-phi.vercel.app,
  backend https://cp-compass-api-1j9a.onrender.com. Cookies must work
  cross-site in prod AND on plain-HTTP localhost in dev
  (frontend :5173 / :4173, backend :8004).
- CORS allow_credentials=True already; CORS_ORIGINS is an exact list
  (never "*").
- SSE GET /api/v1/sync/stream must keep working (EventSource cannot
  send an Authorization header).
- Google OAuth callback + TOTP second step must keep working.
- Logout must revoke server-side AND clear cookies.
- Refresh rotation + reuse → revoke whole family (audit F4) must keep
  working.
- No new dependencies.

Open questions the probe must decide (see arena-task.md):

1. Cookie-only auth vs cookie + Authorization-header fallback?
2. CSRF mechanism: double-submit cookie vs Origin/Referer check vs
   SameSite-only?
3. SameSite policy: None+Secure in prod / Lax in dev, or something else?
4. CSRF token lifecycle: issued when, rotated when, which endpoints
   (if any) are exempt?
5. SSE auth: cookie + withCredentials vs keep the ?token= query param?
6. What breaks if the user blocks third-party cookies, and what is the
   honest fallback?

The probe winner's design is what the N4 build follows (recorded in
specs/batch6/arena-result.md). There is no full-tournament winner —
state that plainly.

## 1. N1 — register rate limit

- POST /api/v1/auth/register: per-email limit, the SAME budget as
  resend-code (1/min, 5/hour) in a SHARED bucket
  (check_resend_allowed / record_resend) so register + resend cannot
  be alternated to exceed 5/hour. Checked BEFORE the DB lookup,
  recorded on every call that passes the check — exactly like
  resend-code today, so no enumeration oracle is introduced.
- _issue_email_code: keep the old code until the new one is actually
  sent. Create the new row, send the mail, and only then delete the
  old rows; if the send fails, delete the new row and keep the old code
  valid. (Today it deletes the old code FIRST — a re-register kills
  the victim's pending code and a failed send strands them.)
- Tests: 6 register attempts for one email in an hour → 429 on the
  6th; register with a failing mailer leaves the old code usable;
  register for a new email still 201 + code sent.

## 2. N2 — password recovery

- New model PasswordResetToken (migration 0009): id, user_id FK
  CASCADE, token_hash (SHA-256 of a 32-byte urlsafe token),
  expires_at (30 minutes), used_at, created_at. Single-use: used_at
  is set on success; expired or used rows are never valid.
- POST /api/v1/auth/forgot-password {email}: generic response always
  ("If an account exists for this email, a reset link was sent"),
  rate-limited per email in its OWN bucket (1/min, 5/hour, same shape
  as resend). If a user exists, create a token row and mail a link to
  FRONTEND_URL/auth/reset?token=<raw>; if not, do nothing — same
  response. Works for Google-only users too (password_hash NULL):
  reset sets their first password (the OAuth batch's "set password"
  follow-up, delivered here).
- FRONTEND_URL config: env FRONTEND_URL, default
  http://localhost:5173; prod https://cp-compass-phi.vercel.app
  (must be set in Render env — until then a live reset link points at
  localhost; state this limit in the report).
- POST /api/v1/auth/reset-password {token, new_password}: validate
  the token hash (unused, unexpired — every failure is the same
  generic 400 "Invalid or expired reset link"); set the Argon2 hash;
  mark the token used; revoke ALL refresh tokens (a password change
  invalidates every session). Rate-limit reset attempts per IP
  (10/hour) to slow token guessing (the token is 256-bit, but the
  limit is cheap).
- Mailer: send_password_reset(email, reset_url) via Resend in prod /
  dev outbox in dev. Same test-domain caveat as verification mail:
  until a custom domain is live, reset mail only delivers to Khalid's
  own address. Build it correctly anyway; state the limit.
- Frontend: /auth/forgot page (email form, generic success message)
  + /auth/reset?token= page (new password + confirm, EN+BN).
  "Forgot password?" link on the login page. i18n keys in en.ts/bn.ts.
- Tests: forgot for an unknown email → 200 generic, no token row;
  forgot for a known email → token row + outbox mail; reset with the
  token → 200, password changed, old password fails, token is
  single-use (second use → 400); expired token → 400; per-email rate
  limit → 429; reset revokes refresh tokens (old refresh → 401).

## 3. N3 — stop trusting X-Forwarded-For

- _client_ip: Render's edge appends the connecting IP as the LAST
  X-Forwarded-For entry; earlier entries are client-controlled and
  must never be trusted (hacker review N3). New rule: when the app is
  behind Render (prod detection, same as the docs check), use the LAST
  XFF entry; otherwise (local dev, no proxy) use request.client.host.
  Document the reasoning in the function.
- Tests: a spoofed first entry is ignored (the last entry is used);
  no XFF → peer; in dev (non-prod) XFF is ignored entirely.

## 4. N4 — HttpOnly cookies + CSRF + frontend auth rework

The arena winner's design governs the details (section 0). The
shape below is what the build must cover, whatever the winner picks:

- Backend: set cp_access (HttpOnly, 15 min) + cp_refresh (HttpOnly,
  7 days) cookies on login / verify-email / totp-verify /
  google-callback / refresh; clear them on logout (and revoke the
  refresh token). Cookie flags: Secure + SameSite=None in prod
  (cross-site), Secure=False + SameSite=Lax in dev (plain-HTTP
  localhost). Path=/.
- get_current_user reads the access cookie (the probe decides whether
  the Authorization header stays as a fallback).
- CSRF: the probe picks the mechanism. The shape is: a CSRF token the
  frontend can read (cookie, not HttpOnly) + a matching
  X-CSRF-Token header on mutations; GET /api/v1/auth/csrf issues the
  token for the pre-login state; rotate on login/logout.
- Refresh endpoint: cookie-based (no token in the body). Logout:
  cookie-based (no token in the body).
- SSE: cookie auth (the probe decides vs ?token=); the frontend uses
  EventSource withCredentials:true if cookies win.
- Frontend: client.ts sends credentials:'include' on every request,
  no Authorization header, no localStorage tokens; tryRefresh is a
  cookie POST; useAuth boot is just api.me() (no localStorage check);
  legacy localStorage token keys (cp_access_token, cp_refresh_token,
  cp_token) are removed once at boot; syncStreamUrl carries no token;
  logout is an empty-body POST.
- AuthOut: tokens leave the JSON body (email + cf_handle only).
  Update api/types.ts.
- Tests: login sets HttpOnly cookies (flags asserted); no token in
  any JSON body; an authed request via cookie works; a request
  without a cookie → 401; a mutation with a missing/mismatched CSRF
  token → 403; logout clears cookies + revokes the refresh token;
  SSE works via cookie; the old ?token= path is 401 if removed
  (tested), or still works if the probe keeps it (tested).

## 5. Reel 27-check #8 — audit logging

- New module backend/app/audit.py: stdlib logging only, logger
  "cpcompass.audit", one line per event (ts, event, ip,
  email/user_id, outcome). No passwords, codes or tokens are ever
  logged. Events: auth.login_failed, auth.login_locked (429 from
  check_login_allowed), auth.login_ok, auth.refresh_reused (token
  family revoked after a replayed refresh), auth.rate_limited
  (register / resend / reset 429s), auth.totp_failed.
- Call sites: login (failure + lockout + success), refresh (reuse),
  register/resend/forgot (rate-limit 429s), totp verify (failure).
- Tests: caplog asserts each event is emitted at the right place.

## 6. Reel 27-check #3 — least-privilege Neon role

- Create role cpcompass_app (LOGIN, strong random password generated
  server-side, never in code or chat) on Neon. Grants: USAGE on
  schema public; SELECT/INSERT/UPDATE/DELETE on all 21 app tables;
  USAGE,SELECT on all sequences; ALTER DEFAULT PRIVILEGES for future
  tables (same grants) + future sequences. NO createdb / createrole /
  DDL.
- Migrations stay on the owner role: new config
  MIGRATION_DATABASE_URL (env; falls back to DATABASE_URL); alembic
  env.py reads it; _run_migrations uses it. The runtime engine keeps
  DATABASE_URL.
- Safety order — do not skip steps:
  1. Create the role + grants on Neon (owner connection).
  2. Point the LAPTOP dev server at Neon with the app role and run
     the full pytest + manual probes (login, sync read, write paths).
     The live app is untouched during this step.
  3. Only then switch Render env — MANUAL, in the Render dashboard
     (the Render connector is read-only by design): DATABASE_URL to
     the app-role URL, MIGRATION_DATABASE_URL to the owner URL.
  4. Verify live health + login after the switch.
  If step 2 fails, STOP and report — do not touch Render.
- The app-role password goes into Render env only (dashboard), never
  chat/code. Record the role name + grants in the report.

## 7. Reel 27-check #22 — remove unused @react-three/drei

- npm uninstall @react-three/drei (frontend); grep to confirm no src
  references remain; frontend build green. Check first whether
  @react-three/fiber and three are referenced — only drei is in the
  finding, so only drei goes (if fiber/three are also unreferenced,
  say so in the report, do not silently remove more).

## 8. Rate limits on the 4 Batch 5 endpoints

- Generic per-user limiter in ratelimit.py: (endpoint, user_id)
  buckets with a window + max per endpoint. Limits: GET
  /api/v1/sync/stream 20/hour per user (stream starts); POST
  /api/v1/settings/public-profile 20/hour per user; GET
  /api/v1/calendar/export.ics 30/hour per user; GET /api/v1/u/{handle}
  100/hour per IP (public, unauthenticated — uses the fixed
  _client_ip). 429 with Retry-After.
- Tests: exceeding each limit → 429; a different user is unaffected.

## 9. Border cache-bust — showcase PNGs

- Rename frontend/public/showcase-{dashboard,analytics,practice,
  revision}.png → *-v2.png; update every reference (Landing.tsx,
  and anything else a grep finds — check the service worker precache
  list too); verify the new files are served by the production build;
  the old URLs must 404 after deploy.
- Root cause (verified 2026-11-28, 6 ways): the live site has NO
  orange border — what Khalid sees is his browser's cached OLD PNG
  (same stable URL, old file had the gold Reticle frame baked into all
  4 sides). The rename is the permanent fix; he was already told to
  hard-refresh (Ctrl+Shift+R).

## 10. "Synced never" wart

- sync.py run_sync: set job.last_synced_at = datetime.utcnow() when
  the job completes (status "done"), even when 0 new submissions were
  found. (Today it is only set inside the per-submission loop.)
- Test: a sync with 0 new submissions → status done AND
  last_synced_at set.

## Verification (all)

- Full pytest on the laptop venv (target: 114 + new tests, 0 failed;
  the 2 UTC flakes pass after 06:00 Dhaka — run after that window or
  note it).
- Frontend build green (tsc + vite build + SW BUILD_ID injection).
- Live: health 200, /docs 404, DB-backed probes (register → 503
  Resend limit / login 403 unverified / wrong-pw 401), cookie flags
  checked on a live login, probe deleted, live users back to 1.
- Commit ONLY batch6 files; normalize line endings to match each
  blob; push via Python-stdin winreg GITHUB_TOKEN + throwaway askpass
  (deleted right after); token never printed.

## Honest limits (to state in the final report)

- Live password-reset mail is bounded by the Resend test domain
  (only Khalid's address) until a custom domain is live.
- The Render env switch for the Neon app role is manual (dashboard)
  — the connector is read-only.
- No authenticated live testing of the reset flow for a second user
  (Resend limit).
- Arena: 10-agent spawn probe only; no full-100 tournament winner.
