# Landing fixes — spec (light)

Batch: landing-fixes. Repo `D:\Projects\cp-compass`, base `86f6a4b`.
Khalid approved both fixes after seeing the live landing screenshots
(teal palette already decided 2026-11-28 01:01).

## Fix 1 — gold frames on the landing page: REMOVE

### Corrected diagnosis (verified 2026-11-28 ~01:10, do not re-litigate)

The gold is NOT a CSS design element. There is no gold border anywhere
in the landing CSS (`--border` is `#31493d`; `--gold #ffc800` is used
only by `.text-gradient-gold` on the "practice" headline word).

What Khalid saw breaks down into two different causes:

1. **Baked into `frontend/public/showcase-dashboard.png`.** The PNG is
   1440x900 and its outer 1-2px on all four sides are gold
   (top/bottom 1440/1440 px, left/right 900/900 px). It was captured
   from the Reticle-instrumented dev server, so Reticle's gold viewport
   overlay got baked into the image. The other three showcase PNGs
   (analytics, practice, revision) are clean. This image is shown in
   TWO places, so one bad file causes both gold frames Khalid saw:
   - hero mockup (`Landing.tsx` ~354, `object-cover object-top`,
     top 340px shown) — gold top + side edges visible;
   - showcase figure, Dashboard tab (`Landing.tsx` ~440, `w-full`)
     — full gold rectangle visible.
2. **Reticle dev overlay (dev screenshots only).** A fresh CDP shot of
   the dev server (`:5173`) reproduces a gold 1440x900 rectangle around
   the first viewport (top row 720/720 px gold); a fresh CDP shot of
   the production build (`:4173` preview) has ZERO gold on the
   viewport edges, and the live Vercel bundle
   (`index-B5B4AIRK.js`) contains zero occurrences of "reticle".
   The "thin gold rule under the hero" is the bottom edge of that
   dev-only frame (y=898-899). It does NOT exist on the live site.

### Fix

- Re-capture `showcase-dashboard.png` cleanly from the production
  build (`:4173` preview, `/demo`, 1440x900 viewport shot, no Reticle)
  and replace `frontend/public/showcase-dashboard.png`.
- No CSS change for the frames: there is nothing gold to remove in
  code. Do NOT touch `.text-gradient-gold` (headline "practice" word)
  or the SPECIALIST rank accent — gold stays there per the F1-gold rule.
- If the fresh capture's demo numbers drifted from the hardcoded hero
  stats (1478 / 138 / 2-day streak / 3 due in `Landing.tsx` ~366-376),
  update the hardcoded values to match the fresh image so text and
  image agree.

## Fix 2 — Features section has no visible heading: ADD ONE

Verified in code: `Landing.tsx:401` `<section id="features">`,
`:403` `<h2 className="sr-only">{t.navFeatures}</h2>` — screen-reader
only. The three cards sit under the hero with no visible label, so the
navbar "Features" link lands on an unidentifiable section.

Fix: replace the sr-only h2 with a visible heading in the same pattern
as the other sections (`<motion.h2 {...fadeUp} className="text-2xl
font-semibold tracking-tight">`), reusing `t.navFeatures`
("Features" / "ফিচার" — already bilingual, no new strings).
Keep `id="features"` so the navbar anchor still lands on it.

## Verification (before commit)

- Frontend build passes (tsc + vite).
- pytest: 2 pre-existing UTC-vs-local date flakes
  (`test_10_heatmap_full_history`, `test_11_cumulative_solved`) fail
  only 00:00-06:00 Dhaka — do not chase them.
- Screenshots before/after, desktop + true-390 mobile (CDP script
  `shots-premium-apply/cdp-shot.mjs`; headless `--window-size` does NOT
  give 390px). Copy to `~/workspace/shots-landing-fixes/` and VIEW them.
- After shots must be taken from the preview build (`:4173`), NOT the
  dev server, or Reticle's overlay will pollute them again.

## Ship

- One commit, only this batch's files (never `git add -A`). Reticle
  changes stay uncommitted.
- Push via askpass pattern (token from HKCU Environment, throwaway
  `.bat`, deleted right after, token never printed).
- Wait for the Render deploy, then live-verify: `/api/v1/health` 200,
  `/docs` 404, landing renders with no gold frames + visible Features
  heading, navbar Features link scrolls to it.
- No DB-backed probe: no auth code changed.

## Out of scope

Google OAuth, AI features (Hint Ladder / post-mortem / mistake mining),
Batch 3/4/5 — queued separately, do not start.
