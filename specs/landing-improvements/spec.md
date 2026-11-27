# Landing improvements — spec

## Problem
The CP Compass landing page (frontend/src/pages/Landing.tsx, 252 lines) has
4 real sections — hero, 3 feature cards, 3 how-it-works steps, CTA — and
one-line copy per card. A review (2026-11-27) found: no FAQ, no real
screenshots, no footer GitHub link, no Beta badge, no og:image, Today's-plan
copy bugs, and a "We verify it" claim that was false at the time.

## Decisions (already approved by Khalid)
- Add ALL of: FAQ, real screenshots, footer GitHub link, Free line, Beta
  badge, og:image, scroll animation (hero only), roadmap strip, Today's-plan
  copy fixes, :lang(bn) line-height, "30-day" non-breaking hyphen.
- Honesty rules (standing): no fake testimonials, no fake user counts, no
  invented features. Every claim must match reality.
- Batch 1 (commit f5cff7a) built handle verification (profile-token proof),
  so "We verify it" is now TRUE — keep it, worded to match reality.
- Roadmap lists ONLY Batch 2-5 approved items (failure pattern, contest
  post-mortem, recommender backtest). Nothing invented.
- Scroll animation: GSAP/CSS only, hero only, lightweight. NOT the
  frame-video method from the namansoni.ai reel (too heavy for low-end
  phones). Dashboard stays static. Respects prefers-reduced-motion.
- og:image reuses the existing compass logo art (public/compass.svg) — no
  new logo invented. Social card rendered at 1200x630 from that art.
- Screenshots are real captures from the running dev server (demo data,
  labelled as demo). Dashboard + Analytics pages.

## Scope
- Files: frontend/src/pages/Landing.tsx, frontend/src/i18n/en.ts,
  frontend/src/i18n/bn.ts, frontend/src/i18n/dict.ts,
  frontend/src/i18n/index.tsx (formatWhy), frontend/src/styles/base.css,
  frontend/index.html, frontend/public/og.png + showcase images.
- Both locales (EN + BN) for every new string. No hardcoded user-facing
  text in components (repo rule: all strings via useLanguage().t).
- Checks: desktop + mobile + light theme, 0 console errors, 0 horizontal
  overflow. Frontend build passes, pytest still green.

## Out of scope
- No design-direction change (HUD vs glassy decision still pending with
  Khalid). No dashboard changes. No new backend work. No repo cleanup
  (separate commit, same agent, after this batch).
