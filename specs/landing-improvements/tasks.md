# Landing improvements — tasks

- [x] T1 i18n: add landing keys to dict.ts (Dict type) + en.ts + bn.ts:
  betaBadge, freeLine, demoDataChip, githubLink, faqTitle, faqQ1/A1,
  faqQ2/A2, faqQ3/A3, showcaseTitle, showcaseCaption,
  showcaseDashboardCaption, showcaseAnalyticsCaption, roadmapTitle,
  roadmapNote, roadmap1/2/3Title + Text.
- [x] T2 Copy fixes (en.ts + bn.ts): whyWeakAcceptance grammar
  ("Your acceptance rate on <tag> is <pct>%"), drop the redundant
  "— this problem is rated <rating>" tail (rating already in the header),
  delete whyDemoOutOfBand key from Dict type + both locales, remove the
  append in formatWhy (i18n/index.tsx); step1Text -> profile-token
  wording; "30-day" -> non-breaking hyphen (U+2011) in feature3Text.
- [x] T3 Landing.tsx: Beta chip next to the hero badge; freeLine under the
  CTA buttons; "Demo data" chip next to the Today's-plan preview heading;
  footer GitHub link (https://github.com/Khalid635/cp-compass).
- [x] T4 Landing.tsx: FAQ section before the CTA (3 Q&As, true answers
  only); roadmap strip (3 approved Batch 2-5 items, marked coming soon).
- [x] T5 Landing.tsx: showcase section with real Dashboard + Analytics
  screenshots (public/showcase-dashboard.png, public/showcase-analytics.png,
  captured from the dev server on /demo, labelled demo).
- [x] T6 Landing.tsx: scroll animation, hero only (GSAP + ScrollTrigger):
  preview panel assembles on scroll (fade/slide/settle), sparkline draws;
  skipped under prefers-reduced-motion; transform/opacity only.
- [x] T7 base.css: add :lang(bn) { line-height: 1.75 } rule.
- [x] T8 index.html: og:title, og:description, og:image
  (https://cp-compass.vercel.app/og.png), twitter:card summary_large_image;
  note the domain placeholder must match the real Vercel URL.
- [x] T9 public/og.png: render 1200x630 social card from the existing
  compass.svg art + title (headless Chrome screenshot of a static page).
- [x] T10 Verify: npm run build passes; pytest still green (25 tests);
  CDP screenshots landing EN/BN desktop + mobile (full page, 0 console
  errors, 0 horizontal overflow) + light theme; view the screenshots.
- [x] T11 Commit: one commit for the landing batch.
