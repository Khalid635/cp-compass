# Batch 6 arena probe — N4 cookie + CSRF design

## The question

How should CP Compass move auth tokens out of localStorage into
HttpOnly cookies with CSRF protection, and rework the frontend to
match — without breaking the live session, the PWA, or SSE sync?

Six decisions every design had to answer: (Q1) cookie-only auth or
cookie + Authorization-header fallback; (Q2) CSRF mechanism and which
requests it covers; (Q3) SameSite policy in prod vs dev; (Q4) CSRF
token lifecycle; (Q5) SSE auth (the `?token=` query param must die);
(Q6) what breaks when the user blocks third-party cookies.

## Why this is a probe, not a tournament

The full 100-agent arena tournament is INFEASIBLE in this host
(595 sub-agent calls, 70 waves, ~9h — proven in Batch 5, recorded
in `specs/batch5/arena-result.md`). This is the same transparent
fallback Batch 5 used: **10 agents, one round, scored on the rubric
below. There is no full-tournament winner — do not claim one.**

- Probe agents: a001–a010 (strategy cards: security-first,
  compatibility-first, minimal-change, defense-in-depth,
  PWA/service-worker, spec-purist, adversarial, operational,
  simplicity/maintainability, UX+performance).
- Designs: `specs/batch6/arena-run/r0/a001.md` … `a010.md`
  (1,672–2,624 words each, LF).
- Rubric: correctness 30 / completeness 25 / specificity 15 /
  robustness 20 / clarity 10 = 100.

## Scores

| Agent | Design in one line | Corr | Comp | Spec | Rob | Clar | Total |
|---|---|---|---|---|---|---|---|
| **a005** | **Cookie-only, double-submit + strict Origin, JSON-echo token, idempotent issuance** | 28 | 24 | 14 | 18 | 9 | **93** |
| a001 | Cookie-only, triple CSRF (Origin + custom header + double-submit), Vite proxy in dev | 28 | 24 | 14 | 18 | 9 | 93 |
| a008 | Cookie-only, double-submit + Origin, localhost host fix, deploy + rollback runbook | 28 | 25 | 13 | 18 | 9 | 93 |
| a004 | Cookie-only, HMAC-bound CSRF token (cookie-tossing defence), JSON echo | 28 | 23 | 13 | 19 | 9 | 92 |
| a006 | Cookie-only, Origin + double-submit, spec-cited, fail-closed | 28 | 23 | 14 | 18 | 9 | 92 |
| a007 | Cookie-only, triple-lock CSRF, best-attack self-critique (XSS defeats all layers) | 25 | 24 | 14 | 19 | 8 | 90 |
| a002 | First-party cookies via a same-origin Vercel `/api` proxy, Lax everywhere | 25 | 23 | 14 | 17 | 9 | 88 |
| a003 | Cookie-only, Origin + double-submit, zero new state, exact file:line citations | 20 | 24 | 15 | 17 | 9 | 85 |
| a010 | Cookie-only, piggybacked CSRF (no `/auth/csrf` endpoint), owned SSE reconnect | 20 | 23 | 14 | 17 | 9 | 83 |
| a009 | Cookie-only, Origin-only CSRF, no token at all | 22 | 21 | 12 | 15 | 9 | 79 |

## Winner: a005 (93/100)

Three designs tied at 93 (a005, a001, a008). The tie-break, in
order:

1. **Dev fidelity.** a005 and a008 keep dev genuinely cross-origin
   (frontend `localhost:5173` → backend `localhost:8004`; ports do
   not affect same-site, hosts do — so the `127.0.0.1:8004` dev
   address must become `localhost:8004`). a001 instead hides the
   cross-origin behaviour behind a Vite `/api` proxy in dev, which
   masks exactly the class of bug N4 exists to fix.
2. **CSRF bootstrap robustness.** a005 issues the CSRF token
   idempotently — if a `cp_csrf` cookie is already present, it
   returns its value instead of rotating — so no site can rotate the
   victim's token at will (token-rotation DoS). a008 has no such
   rule. a008's runbook is borrowed as a supplement instead (below).

**The winning design (a005, condensed):**

- **Q1 — Cookie-only, no Authorization fallback.** `get_current_user`
  reads `request.cookies["cp_access"]` only; any `Authorization`
  header is ignored. No token lives in JS state that survives reload.
- **Q2 — CSRF: double-submit + strict Origin/Referer.** Both checks
  on every `POST`/`PUT`/`PATCH`/`DELETE` under `/api/v1`, including
  login, register, verify-email, forgot/reset, totp-verify, refresh,
  logout, logout-all. `X-CSRF-Token` must equal the `cp_csrf` cookie
  (`hmac.compare_digest`); mismatch/missing → `403
  {"detail": "csrf_mismatch"}`. Independently, `Origin` must exactly
  match the allowlist (prod `https://cp-compass-phi.vercel.app`;
  dev `http://localhost:5173`, `http://localhost:4173`); if `Origin`
  is absent, `Referer` must match; both absent → reject. SameSite
  counts for nothing in prod (prod cookies are `SameSite=None`).
  Exempt: `GET`/`HEAD`/`OPTIONS`, `GET /api/v1/auth/csrf`,
  `GET /api/v1/sync/stream`, Google callback `GET` (HMAC `state`).
- **Q3 — SameSite: `None`+`Secure` in prod; `Lax`, not `Secure`, in
  dev.** `Secure` cookies are silently dropped over plain HTTP, and
  `None` without `Secure` is rejected, so dev is `Lax; Secure=False`
  — which works only with the `localhost:8004` host fix above.
  One settings object (`COOKIE_SECURE`, `COOKIE_SAMESITE`) with a
  startup assert: `SameSite=None` requires `Secure`.
- **Q4 — CSRF lifecycle.** `GET /api/v1/auth/csrf` returns
  `{"csrf_token": "<value>"}` in the JSON body **and** sets the
  `cp_csrf` cookie to the same value. The JSON body is load-bearing:
  JS on `cp-compass-phi.vercel.app` cannot read a cookie set for
  `cp-compass-api-1j9a.onrender.com` via `document.cookie`. So
  `cp_csrf` is `HttpOnly` too; JS keeps only the body copy in a
  module-level variable in `api/client.ts`, never in
  `localStorage`/`sessionStorage`. Token: `secrets.token_urlsafe(32)`,
  never stored in the DB. Idempotent issuance (above). Rotate only
  on login, TOTP verify, Google callback, password reset, logout.
  Never on refresh or per-request. `client.ts` calls `ensureCsrf()`
  on boot and before the first mutation; on `403 csrf_mismatch` it
  refetches once and retries once. `GET /auth/csrf` sends
  `Cache-Control: no-store`.
- **Q5 — SSE: cookie + `EventSource` with `withCredentials`.**
  Delete `?token=` entirely and delete `decode_access_token_query`.
  On `onerror`, `layout.tsx` closes the stream, calls `api.me()`
  (normal 401 → refresh → retry), and reopens once if `me()`
  succeeds; if `me()` 401s it stays closed.
- **Q6 — Third-party cookies blocked: auth breaks, say so.** Login
  returns 200, `Set-Cookie` is dropped, the next `me()` is 401. No
  localStorage fallback. A login whose immediate `me()` 401s shows a
  full-page banner naming `cp-compass-api-1j9a.onrender.com`. Still
  works: public shell, landing page, offline shell. Real fix
  (follow-up, not N4): serve the API same-site so cookies become
  first-party.

## Supplements borrowed from the other nine

- **a001 — Origin check on the SSE stream.** a005's SSE has no
  Origin check; a001/a004/a006/a008 all add one (EventSource always
  sends `Origin`). Borrowed: `/sync/stream` enforces the exact
  Origin allowlist too. Also a001's "same 403 detail for every CSRF
  failure" (no probing oracle).
- **a003 — CSRF as middleware, not a per-endpoint dependency.** A
  middleware covers every mutation automatically — including the N2
  endpoints built in the same batch — and a future mutation cannot
  forget the check. (a003's exact file:line citation style is also
  the model for the implementation notes.) a003's own Q4 is NOT
  borrowed: it returns `{"ok": true}` from `/auth/csrf` and has the
  frontend read the token via `document.cookie`, which cannot read a
  cross-site cookie — every mutation would 403 in prod.
- **a008 — deploy + rollback runbook and live verification
  checklist.** The only operationally complete design; borrowed whole
  for the deploy phase.
- **a002 — cookie-probe endpoint.** After login, if `me()` 401s, a
  `GET /auth/cookie-probe` (sets a throwaway cookie, reads it back)
  confirms cookies are blocked before showing the banner. Borrowed
  for the Q6 detection.
- **a010 — owned SSE reconnect with backoff.** a005 reopens the
  stream once; a010's backoff (1s → 2s → 5s cap, max 5 attempts per
  sync) is borrowed so a flapping stream does not reconnect-storm.
- **a007 — the best-attack self-critique.** XSS defeats every CSRF
  layer at once (in-origin JS passes Origin and reads the token).
  The patch is not a fourth CSRF check: tighten CSP beyond the
  current headers (`script-src 'self'`, no `unsafe-inline`/
  `unsafe-eval`), sanitise Codeforces-derived strings before render,
  and step-up (re-ask password) for destructive actions. Recorded as
  a follow-up, not smuggled into N4.

## Considered and rejected

- **a002's Vercel `/api` proxy (Lax everywhere, first-party
  cookies).** Genuinely attractive — it is the only design where
  blocking third-party cookies breaks nothing. Rejected for this
  batch: it changes deployment topology, and the SSE stream (up to
  600 s) proxied through Vercel serverless functions risks the
  Hobby-plan timeout, which a002 never addresses. Recorded as the
  real long-term fix for Q6 (same-site API), not this batch.
- **a004's HMAC-bound CSRF token (cookie-tossing defence).** The
  strongest single robustness idea in the probe. Rejected for this
  batch: cookie-tossing needs an attacker-controlled subdomain or a
  cookie-setting endpoint, neither of which this app has; the
  session binding adds server state and a pre-login edge case for a
  low-likelihood threat. Revisit if the app ever gains subdomains.
- **a009's Origin-only CSRF (no token).** Simplest design, thinnest
  defence: a single point of failure, and its `SameSite=None;
  Secure` in dev relies on the localhost secure-context quirk
  (unverified on Safari). Rejected.
- **a010's piggybacked CSRF (no `/auth/csrf` endpoint).** Elegant in
  dev, broken in prod: the frontend reads the token from
  `document.cookie`, which cannot see a cross-site cookie — same
  flaw class as a003. Rejected.

## One-line notes on the other nine

- a001 (93): strongest layered defence; loses the tie-break on the
  dev Vite proxy (hides cross-origin bugs) and the extra preflight
  on every mutation.
- a002 (88): the only design that makes third-party-cookie blocking
  a non-issue; loses on the unaddressed SSE-through-Vercel timeout
  and the vague "session row" for the 60 s token grace.
- a003 (85): the most specific (exact file:line everywhere) and the
  middleware idea is borrowed — but its Q4 is broken in prod
  (`{"ok": true}` + `document.cookie` cannot read a cross-site
  cookie).
- a004 (92): the most robust single idea (HMAC-bound token); loses
  on complexity and the per-refresh rotation race.
- a006 (92): the most spec-cited; loses on the dev Vite proxy and a
  `cp_at` cookie name that breaks the codebase convention.
- a007 (90): the best self-critique in the probe; loses on the
  fragile dev flag (`None` without `Secure` on localhost) and an
  incoherent pre-login token binding.
- a008 (93): the most operationally complete (runbook + checklist);
  loses the tie-break on CSRF bootstrap robustness (no idempotent
  issuance).
- a009 (79): the simplest; loses on single-layer CSRF and the
  dev-flag quirk.
- a010 (83): the most elegant SSE reconnect; loses on the prod-broken
  `document.cookie` token read.

## Verdict

**Implement N4 per a005, with the supplements above.** No
full-tournament winner exists — this probe's winner is the strongest
of 10 designs by the rubric, not a guarantee of correctness.
