# Batch 5 — polish: SSE sync, PWA, public profiles, friend compare, .ics, lamp login

Status: spec first, then ONE full-100 arena tournament on the PWA
service-worker caching decision (see arena-task.md), then build.
Base: 2e282a2 (Batch 4). All six items approved by Khalid; chain with no
stopping. Laptop only, via SSH. Commit ONLY batch5 files.

## 1. SSE sync progress

User story: while a sync runs, the top-bar chip shows live progress
(submissions synced so far) instead of a 15-second poll.

- Backend: `GET /api/v1/sync/stream?token=<access-token>`.
  EventSource cannot send an Authorization header, so the same JWT
  access token is accepted as a `token` query param, decoded by a new
  `get_current_user_query` in auth.py (same checks as
  `get_current_user`: type == "access", expiry, user exists).
  401 when missing/invalid. The stream only ever exposes the caller's
  own latest job (looked up by the token's user_id) — a token can never
  read another user's job.
- Events: an immediate `state` event with the current job
  `{status, total_synced, last_synced_at, error}`; then a `progress`
  event whenever `total_synced` or `status` changes (server polls the
  DB job row every 1s); a terminal `done` / `failed` event, after which
  the server closes the stream. `: heartbeat` comment every 15s so
  proxies do not kill an idle stream. No job yet: one `state` event
  `{status: "never", ...}` and close.
- Frontend: SyncChip (components/layout.tsx) opens an EventSource to
  the stream while status is pending/running, shows the live count,
  invalidates `sync-status` + dashboard queries and toasts on `done`,
  and falls back to the existing 15s polling if the stream errors or
  the browser has no EventSource. The stream URL token comes from
  localStorage (`cp_access_token`); never log it.
- Tests: stream emits progress as total_synced changes; terminal done
  closes the stream; 401 with no/bad token; stream for a user with no
  job returns the never-state and closes.

## 2. PWA (installable, offline shell)

User story: the app installs to a home screen and still opens its shell
when offline; no private data is ever served from a cache.

- `frontend/public/manifest.webmanifest`: name "CP Compass",
  short_name "CP Compass", display standalone, theme/background
  colours from the design tokens, icons (192 + 512 PNG generated from
  the existing compass.svg if a generator is available on the laptop,
  else the existing og.png + svg with an honest note that the install
  prompt may vary by browser).
- `frontend/public/sw.js`: hand-written, no new dependency (no
  vite-plugin-pwa). Cache strategy is THE arena decision — see
  arena-task.md for the decision and its hard constraints. Whatever
  wins must at minimum satisfy: NO authenticated API response is ever
  cached or served to another user; the app shell loads offline;
  updates roll out reliably (versioned cache + activate cleanup);
  SSE and all /api traffic bypass the worker entirely.
- Registration in main.tsx: only when `import.meta.env.PROD` and
  `'serviceWorker' in navigator`. Never in dev (a worker would serve
  stale dev assets).
- Small offline indicator in the app shell (online/offline events).
- Tests/verification: manifest + sw.js served with correct content
  types from the production build; shell loads with the network cut in
  a headless check; no /api response cached (verified by inspecting
  the worker source + a runtime check). Full install-prompt
  verification is NOT possible headlessly — honest limit, stated in
  the report.

## 3. Public profile /u/handle — OPT-IN, default OFF

User story: a user can choose to make a public profile at
/cp-compass-phi.vercel.app/u/<handle> showing their stats; nobody is
public unless they turn it on.

- Backend: migration 0008 adds `users.public_profile` Boolean NOT NULL
  DEFAULT FALSE. `POST /api/v1/settings/public-profile`
  `{public: bool}` -> `{public_profile: bool}` (auth required);
  `GET /api/v1/settings` includes `public_profile`.
- `GET /api/v1/u/{handle}` — public, no auth. Resolves handle_norm;
  404 when the handle has no account OR the user has not opted in
  (the two cases are deliberately indistinguishable). Payload:
  `{handle, rank, current_rating, solved, attempted, current_streak,
  top_tags: [{tag, solved, attempted, acceptance}], last_synced_at}`.
  No email, no user id, no submission-level data.
- Frontend: public route `/u/:handle` (no auth): stats cards + top
  tags; honest "private or doesn't exist" empty state. Settings page
  gets the opt-in toggle + a "View your public profile" link when on.
- Tests: default off; 404 when private; payload shape when public;
  toggle flips it; a private user's data never leaks through the
  public route.

## 4. Friend compare

User story: compare my stats side-by-side with a friend's (the friend
must have a public profile).

- Frontend page `/app/compare` (auth required), linked from the app
  nav. Side A defaults to the signed-in user's own dashboard stats.
  Side B is a handle input resolved through `GET /api/v1/u/{handle}`.
  Table + simple bars: rating, solved, attempted, current streak,
  top tags. Side B not public -> honest "not public" state, no data
  shown. Comparing with yourself is allowed (A == B shows identical
  columns).
- No new backend endpoint (reuses /u/{handle} + /dashboard).

## 5. .ics export

User story: download upcoming Codeforces contests as a calendar file.

- Backend: `GET /api/v1/calendar/export.ics` (auth). Uses the existing
  cached `cf.contest_list()` (1h cache). One VEVENT per contest with
  phase == "BEFORE": DTSTART/DTEND in UTC from startTimeSeconds +
  durationSeconds, SUMMARY = contest name, URL =
  https://codeforces.com/contest/{id}, UID = contest-{id}@cp-compass.
  Content-Type `text/calendar`, Content-Disposition attachment
  `codeforces-contests.ics`. CF failure -> 502.
- Frontend: "Export .ics" button on the Calendar page; fetches with
  the auth header, downloads the blob. EN+BN labels.
- Tests: mocked contest_list -> VCALENDAR shape (UID, DTSTART, SUMMARY
  present); 502 when CF raises.

## 6. Lamp-toggle login page

User story: the login page has the floor lamp from the Code with
Mahesh reel — pulling the cord toggles the theme. Login page ONLY,
never the dashboard.

- New `LampToggle` component (frontend/src/components/LampToggle.tsx):
  a floor-lamp illustration (CSS/SVG, no new dependency) that IS a
  real `<button>`: keyboard accessible (native button, Enter/Space),
  `aria-pressed` reflecting the theme, `aria-label` EN+BN, visible
  focus ring. Lamp ON = light theme (glow), lamp OFF = dark theme.
  Respects `prefers-reduced-motion`: the cord-swing/glow animation is
  disabled via the media query (and a matchMedia check).
- Placement: left of the auth card on md+ screens (reel layout: lamp
  left, form right), above the card on small screens. Theme state is
  threaded as props: AppRoutes -> LoginPage/RegisterPage -> AuthPage
  (do NOT instantiate a second useTheme — two instances would drift).
- No behaviour change to login/register/verify/totp flows.
- Verification: screenshots in both themes + a keyboard check (Tab to
  the lamp, Enter toggles, focus ring visible).

## i18n

Every new string gets EN + BN keys in dict.ts / en.ts / bn.ts:
sync stream states (live count already exists as syncingSubmissions),
public profile (title, private-notice, opt-in label + hint, view
link), compare (title, placeholder, not-public, vs labels), ics
(export button + errors), lamp (aria-label on/off), pwa (offline
notice, update notice), stream fallback notice.

## Tests (all must pass before commit)

- Backend pytest: full suite green (existing 94+ tests plus new
  test_sse_stream.py, test_public_profile.py, test_ics_export.py).
  New migration 0008 round-trips on SQLite (alembic upgrade/downgrade
  in tests, same pattern as 0007).
- Frontend: `npm run build` passes (tsc + vite). `node --test` for
  the existing lib tests.
- Live probes (dev backend :8004 + preview :4173): SSE stream with a
  real login (progress events, terminal done); public profile opt-in
  flow end-to-end; .ics download parses; manifest + sw.js served;
  lamp toggle screenshots light/dark + keyboard check.
- Live (Render/Vercel) probes after push: health 200, /docs 404,
  public profile 404 for a private handle, .ics 401 without auth.
  Live AI (hints/analysis) still 503 — GEMINI_API_KEY not on Render;
  do NOT claim live AI works.

## Non-goals

- No change to the sync engine itself (worker, leases, checkpoints).
- No HttpOnly-cookie migration (deferred, see SECURITY.md).
- No change to the dashboard, landing, or demo data.
- No new npm dependencies unless the arena winner requires one AND
  justifies it; hand-written SW is the default.
- Never commit Reticle files or ci.yml. Normalize line endings per
  blob before committing.

## Open decision (arena, before build)

The PWA service-worker caching strategy — see arena-task.md. The
arena picks the design; the build implements the winner. Everything
else in this spec is fixed.
