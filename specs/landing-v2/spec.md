# Landing v2 — spec

## Problem
Landing v1 (commit 9f0d8fa) shipped FAQ, showcase, Beta badge, og:image,
scroll animation, roadmap. A second review (2026-11-27 15:36) found fixes —
this batch implements them. Reviewer was right on: "Free forever" is an
unkeepable promise, the FAQ data answer is wrong, 3-card grid x4 is
monotonous, showcase screenshots too small with no zoom, GitHub link too
small, no author name, "Built with" order reversed, "/" search IS on the
landing navbar (the earlier claim it wasn't was wrong), feature cards still
text-only. Best item: "Why this problem?" — a score-breakdown bar per pick
using ONLY the code's real formula. Reviewer was WRONG on 1 fact: Render
free Postgres dies after 90 days, not 30 — conclusion still holds.

## Verified facts (checked 2026-11-27, before building)
- Free tiers: the promise "Free forever" can't be kept — free tiers change.
- FAQ data answer (faqA3) is wrong as written: notes/settings are
  user-written, NOT from the API; email + Argon2-hashed password not
  mentioned at all.
- Live demo numbers (GET /api/v1/demo/recommendations + /demo/dashboard,
  2026-11-27): top picks 1366C Palindromic Paths 1500 (mirror score 67),
  1360E Polygon 1300 (mirror 80, why weak_acceptance dp 45%), 1367C Social
  Distance 1300 (mirror 55). Demo user rating 1478, distinct solved 138
  (NOT 144 — the v1 preview hardcodes 144, stale), streak 2 (NOT "3 days"
  — stale; streak is date-relative, the seed guarantees today+yesterday).
- The demo endpoint scores use a SIMPLIFIED MIRROR formula
  (seed.py score_for: 55 base + 25 weak-tag bonus + closeness bonus, max
  99) — NOT the production formula. The production formula
  (services.recommend: Score = 0.35W + 0.30D + 0.20R + 0.15P) computed
  on the same demo data gives DIFFERENT totals (script
  /tmp/landing-v2/why_numbers.py, exact replication of services.tag_stats
  + recommend math over seed.SUBMISSIONS, 2026-11-27):
  - 1366C Palindromic Paths (1500): W 0.0, D 61.0, R 50.0, P 60.0 → 37
  - 1360E Polygon (1300): W 56.6 (dp weak_score 0.566), D 0.0, R 73.0,
    P 60.0 → 43
  - 1367C Social Distance (1300): W 0.0, D 0.0, R 50.0, P 60.0 → 19
  Same order as the mirror (80/67/55), different scale. The why-section
  shows the PRODUCTION totals with a footnote that demo pages show a
  simplified preview score. Follow-up (backend, out of scope here): align
  the demo mirror to the production formula so the two never disagree.
  1360E/1367C are below the real recommender's band (1300 < 1478) — the
  real recommender would not surface them; the demo tops up with
  below-band practice for weak tags. The section says so plainly.
- Under-the-hood facts: 16 tables in backend/app/models.py (11 blueprint
  + 5 Batch 1 security: refresh_tokens, email_verifications, totp_secrets,
  backup_codes, handle_verifications) — NOT 11; sync_jobs table = the
  DB-backed job queue; Argon2 password hashing (Batch 1); ML solvability
  model held-out test AUC 0.834 vs baseline 0.317 (README).
- Muted-contrast REAL check (WCAG script, exact token values, 18 pairs):
  17 pass. ONE real failure: light theme, primary #0e7490 on primary/10
  over page bg = 4.47:1 (< 4.5) — the Beta badge in light mode. Fix: badge
  background bg-primary/10 -> bg-surface (primary on surface passes in
  both themes: dark ~7.3:1, light ~5.5:1). "Coming soon" chips sit on
  cards (surface) — 4.67:1 light / 6.01:1 dark, PASS, untouched.
- og:image is still the v1 placeholder https://cp-compass.vercel.app/og.png
  — real domain is cp-compass-phi.vercel.app. Fix in this batch.
- Showcase images are 1440x900 — full-width tab display IS bigger than
  the current half-width grid; lightbox adds zoom. No recapture needed.
- Colour tokens FROZEN (teal only) for this batch — the dashboard-apply
  batch after this one owns colour changes (Khalid's go-ahead 19:39).

## Decisions
- Hero line: "Free to use — no card, no trial." (BN: "ফ্রি — কার্ড লাগে
  না, ট্রায়াল নেই।"). faqA1 stays ("no paid plan, no card, no trial
  that runs out" is consistent).
- FAQ A3 rewritten: email + Argon2-hashed password; submissions/problems
  from the public CF API; notes/settings written by the user; export or
  delete in Settings.
- Footer BELOW the CTA: "Built by Khalid Bin Masud" + links GitHub
  (icon, prominent) + /privacy + codeforces.com + the not-affiliated note.
- Navbar: Features · Demo · FAQ in-page anchors (#features, #showcase,
  #faq) + GitHub icon link; REMOVE the "/" search (PaletteTrigger) from
  the landing navbar ONLY (AppShell topbar keeps it).
- Bands alternate: Features (band) / Showcase (plain) / How (plain,
  numbered steps without card chrome) / Why (band) / FAQ (plain,
  <details> accordions) / Roadmap (band) / Built-with + under-the-hood
  (plain, border-t) / CTA + footer (border-t, tightened).
- Showcase: tabbed viewer (reuse ui.tsx Tabs: Dashboard / Analytics),
  one big image at a time, click opens a lightbox (overlay, Esc/click to
  close, close button, role=dialog).
- "Why this problem?": the 3 demo picks above, each with the why sentence
  (existing formatWhy) + 4 factor bars (W/D/R/P as 0–100 values, weight,
  contribution points) + production total. Caption names the formula and
  the demo account; footnote names the mirror-score difference.
- Privacy page at /privacy (EN+BN, plain, honest): stored (email,
  Argon2-hashed password, CF handle + public submissions/problems from
  the CF API, user-written notes/settings/preferences), never asked (CF
  password), login tokens in browser localStorage, verification emails
  via Resend, no analytics/ads/trackers in the app, export/delete in
  Settings, GitHub repo as contact.
- Bonus honesty fixes: preview numbers 144 -> 138 solved, "3 days" ->
  "2 days" streak (live values 2026-11-27; comment notes they are a
  snapshot — the demo streak is date-relative); og:image URL fixed.
- No fake testimonials/counts anywhere. No new colours. No auth/backend/
  security changes (H1 stays deferred per SECURITY.md).

## Scope
- Files: frontend/src/pages/Landing.tsx, frontend/src/pages/Privacy.tsx
  (new), frontend/src/App.tsx (route), frontend/src/components/layout.tsx
  (LandingHeader only), frontend/src/i18n/dict.ts + en.ts + bn.ts,
  frontend/index.html (og:image URL), specs/landing-v2/.
- Both locales (EN + BN) for every new string. No hardcoded user-facing
  text in components (repo rule: all strings via useLanguage().t).
- Checks: build passes (tsc + vite); screenshots desktop + mobile 390px,
  EN + BN, light + dark, 0 console errors, 0 horizontal overflow;
  Lighthouse quick check if available; pytest still green (backend
  untouched — run as a sanity check).

## Out of scope
- No dashboard changes (dashboard-apply batch runs after this one).
- No backend changes (incl. the demo mirror formula — flagged above).
- No design-direction or colour change. No repo cleanup.

## Verification notes (2026-11-27)
- Showcase images re-captured from the current demo (local backend,
  demo API confirmed solved=138, streak=2, rating=1478 first). The v1
  captures were stale: Batch 2 changed seed.py after they were taken,
  so they showed 144 solved / 3-day streak / "graphs 49%"; the new
  ones show 138 / 2 days / "dp 45%", matching the live demo API.
- Unscrolled full-page captures look empty below the fold — expected:
  the showcase img is loading="lazy" and section headings use
  framer-motion whileInView (initial opacity 0). Scroll-through
  captures render everything; verified.
- Lighthouse not installed on the laptop — skipped ("if available").
- Privacy route deviation: App.tsx imports Privacy directly (like
  Landing), not lazily as tasks.md first said. Same behaviour, one
  less chunk boundary; recorded here, not worth reworking.
