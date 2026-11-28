# Rename spec — CP Compass → Rung

Picked by Khalid 2026-11-28 16:27. Chain batch after Batch 8 (HEAD 5b77479).

## Decisions

- Product name everywhere user-facing becomes **Rung**. Rising Needle logo mark
  SURVIVES — only the wordmark/text changes. Teal design untouched.
- GitHub repo: `Khalid635/cp-compass` → `Khalid635/rung`
  (verified free 2026-11-28 17:2x, API 404). GitHub keeps redirects from the old
  name; local remote URL updated anyway.
- Vercel project rename: **BLOCKED — `rung.vercel.app` is TAKEN.** A live fetch
  of https://rung.vercel.app (2026-11-28 17:37) returns a real React Native app
  ("nikerunning" AppRegistry). Per the batch brief, this part is STOPPED and
  reported back — no alternative subdomain picked by the agent. Live site stays
  `cp-compass-phi.vercel.app` until Khalid picks another subdomain.
  (Also: the Vercel connector cannot act here anyway — its OAuth token lacks
  access to team scope `khalid-5855` / team_16rweT4fTamk1FD7yBrBPsc5, and the
  `authorize_team_access` tool is not offered by this connector build.)
- Local repo directory stays `D:\Projects\cp-compass` (scripts, crons and SSH
  paths reference it; renaming the folder is out of scope).
- Render service name (`cp-compass-api`), backend URL, Neon project name stay
  as-is. No Render env changes (MIGRATION_DATABASE_URL is Khalid's manual step).
- DB role `cpcompass_app`, RLS policies, alembic history, cookie names
  (`cp_access`/`cp_refresh`/`cp_csrf`), TOTP key-derivation salt
  (`cp-compass-totp:`), audit logger name (`cpcompass.audit`) all STAY.
  Renaming any of them would break live auth/RLS or invalidate TOTP secrets.
- Historical specs/ (batch1-8, arena runs) are records — NOT rewritten.
- `frontend/public/favicon.svg` is NOT touched (logo file; its internal
  `<title>` still says "CP Compass — Concept 1: Rising Needle").

## User-facing renames (this batch)

- Frontend: index.html title/meta/og:title, manifest name/short_name,
  layout.tsx header wordmark + GitHub link, i18n en.ts/bn.ts strings,
  Terms.tsx, PublicProfile.tsx ("CP Compass" suffix), sw.js offline message,
  export filenames (`rung-export-…`, `rung-weekly-…`), package.json +
  package-lock.json name `rung-frontend`.
- Backend: FastAPI title "Rung API", mailer subjects/body, TOTP_ISSUER "Rung",
  MAIL_FROM default "Rung <noreply@rung.app>", ICS PRODID + UID domain `@rung`,
  health `service: "rung"`, comments/docstrings. Tests updated where they
  assert the old strings (test_ics_export.py UIDs, test_batch6.py:582 subject).
- Docs: README.md, SECURITY.md, docs/architecture.md, render.yaml comments
  (service name + FRONTEND_URL value in render.yaml UNCHANGED), Dockerfile
  comment, .env.example.
- Landing "Coming soon" staleness: all three roadmap items (Failure-pattern
  analysis, Contest post-mortem, Recommender backtest) have SHIPPED. Section
  becomes "Already live" with a `Live` badge; i18n key `comingSoon` renamed to
  `liveBadge`; roadmapNote reworded to present tense; roadmap3Text present tense.
- PWA icons: icon-192.png / icon-512.png still carry the OLD indigo mark.
  Replace with the Rising Needle: logo-512.png is byte-identical to the
  concept-1 512px PNG (md5 e2e97918…), so icon-512 = copy of logo-512,
  icon-192 = PIL downscale to 192x192. Maskable safety: composite on solid
  background if logo-512 is transparent.
- og.png has "CP Compass" + old mark baked in — regenerate with PIL
  (needle mark + "Rung" wordmark + same tagline, 1200x630).

## Risks

- Vercel–GitHub integration follows a repo rename by repo ID, but verify the
  next auto-deploy actually runs after push; if it does not, report it.
- PWA: manifest name change + new icons require a fresh install to show; the
  service-worker BUILD_ID cache-bust handles the shell update.
- Email subjects change: in-flight verification/reset mails (none expected —
  live users = 1) keep the old subject; harmless.

## Verification

- Full backend pytest (expect 148 passed; 2 UTC flakes only 00:00–06:00 Dhaka).
- Frontend build green (`tsc -b && vite build`).
- Push; HEAD == origin/main. Live: old URL still serves the renamed app,
  landing shows "Rung" with no "CP Compass" in user-facing copy, backend
  /api/v1/health 200, /docs 404, DB-backed register/login probes deleted,
  live users back to 1, live alembic 0010.
