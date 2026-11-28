# Rename tasks — CP Compass → Rung

- [x] Spec written (specs/rename/spec.md)
- [x] GitHub repo renamed Khalid635/cp-compass → Khalid635/rung (API, verified)
- [x] Local remote updated to https://github.com/Khalid635/rung.git
- [x] Frontend copy renamed (index.html, manifest, layout, i18n en+bn, Terms, PublicProfile, sw.js, export filenames, package.json + lock)
- [x] Landing "Coming soon" → "Already live" (i18n liveBadge, note + roadmap3Text present tense, Landing.tsx comment)
- [x] PWA icons replaced with Rising Needle (icon-512 copy of logo-512, icon-192 PIL downscale)
- [x] og.png regenerated with PIL (needle + "Rung", 1200x630)
- [x] Backend copy renamed (main.py title/PRODID/UID/service, config.py issuer + MAIL_FROM, mailer.py subjects, comments)
- [x] Tests updated for renamed strings (test_ics_export.py UIDs, test_batch6.py:582 subject)
- [x] Docs renamed (README, SECURITY.md, docs/architecture.md, render.yaml comments, Dockerfile, .env.example)
- [x] No "CP Compass" left in user-facing code (grep audit; intentional stays documented in spec)
- [x] Full backend pytest — 148 passed, 6 skipped, 0 failed (166.6s)
- [x] Frontend build green — tsc + vite built in 2.27s (chunk-size warning pre-existing); dict.ts liveBadge fix needed first
- [x] Commit ONLY rename files; push; HEAD == origin/main (c8db71c)
- [x] Live verify: see Results below
- [x] Report: Vercel rung.vercel.app TAKEN — needs Khalid's alternative subdomain pick (in final report)

## Results (2026-11-28 ~17:45)

- GitHub repo renamed via API: Khalid635/cp-compass -> Khalid635/rung (200);
  old URL redirects to the new one; local remote updated; ls-remote OK.
- Vercel: rung.vercel.app TAKEN (live Nike Running RN app) — project rename
  STOPPED per brief; live site stays cp-compass-phi.vercel.app until Khalid
  picks another subdomain. Vercel connector also lacks team scope khalid-5855.
- PWA icons now the Rising Needle (icon-512 = copy of logo-512, md5-verified;
  icon-192 = PIL LANCZOS downscale). og.png regenerated with PIL (needle +
  "Rung", tagline, 1200x630, viewed clean).
- Tests: 148 passed, 6 skipped, 0 failed. Frontend build green.

## Live verification (2026-11-28 ~17:53, deploy dep-dc5bunutlv9c7396u0m0 live)

- GitHub: Khalid635/rung, HEAD c8db71c == origin/main. Old URL redirects.
- Vercel auto-deploy from the renamed repo WORKED: cp-compass-phi.vercel.app
  200, <title>Rung — Codeforces Practice Planner</title>; new bundle
  index-BGrc7SsT.js contains "Already live" (1x), "liveBadge" (2x),
  "CP Compass" 0x. Manifest name/short_name "Rung". All assets 200
  (favicon.svg, logo-512.png, og.png, icons/icon-192.png, icons/icon-512.png).
- Render deploy dep-dc5bunutlv9c7396u0m0 live. Backend /api/v1/health 200,
  /docs 404, /openapi.json 404.
- DB-backed probes (probe users inserted as owner, Argon2 via app code):
  login 200 (cookies cp_access/cp_csrf/cp_refresh), /me 200 email match,
  DELETE /auth/account via API 200. Users back to 1, probe users 0,
  submissions 0, refresh tokens 1 (Khalid's own), live alembic 0010.
- Probe notes: login needs the Batch 6 CSRF double-submit (X-CSRF-Token ==
  cp_csrf cookie) AND an Origin in the CORS allowlist — requests without
  Origin get 403 csrf_check_failed (by design). The CSRF token ROTATES on
  login, so delete needs a fresh token fetched after login. First probe
  insert failed on users.created_at NOT NULL (same trap as Batch 7).
- OPEN: rung.vercel.app is TAKEN (live Nike Running app) — the Vercel project
  rename was STOPPED per the brief. Khalid must pick another subdomain.
  Also: the Vercel connector cannot manage this project — its OAuth token
  lacks team scope khalid-5855 and authorize_team_access is not offered.
