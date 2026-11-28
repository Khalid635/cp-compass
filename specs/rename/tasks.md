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
- [ ] Commit ONLY rename files; push; HEAD == origin/main
- [ ] Live verify: old Vercel URL serves renamed app, "Rung" visible, backend health 200, /docs 404, DB probes deleted, users back to 1, alembic 0010
- [ ] Report: Vercel rung.vercel.app TAKEN — needs Khalid's alternative subdomain pick

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
