# Landing v2 — tasks

- [x] T1 i18n: add keys to dict.ts (Dict type) + en.ts + bn.ts:
  navFeatures, navDemo, navFaq, whyTitle, whyCaption, whyFootnote,
  whyW, whyD, whyR, whyP, whyTotal, whyFormula, whyDemoChip (reuse
  demoDataChip where possible), underHood, builtBy, privacyLink,
  lightboxClose, privacyTitle, privacyUpdated, privacyIntro,
  privacyWhatTitle, privacyWhatText, privacyNotTitle, privacyNotText,
  privacyCookiesTitle, privacyCookiesText, privacyRightsTitle,
  privacyRightsText.
- [x] T2 Copy fixes (en.ts + bn.ts): freeLine -> "Free to use — no card,
  no trial." / "ফ্রি — কার্ড লাগে না, ট্রায়াল নেই।"; faqA3 rewrite
  (email + Argon2 hash; submissions/problems from public CF API;
  notes/settings user-written; export/delete in Settings);
  previewStreakValue "3 days" -> "2 days" / "3 দিন" -> "2 দিন".
- [x] T3 LandingHeader (layout.tsx): add Features · Demo · FAQ anchors
  (#features, #showcase, #faq, hidden on mobile) + GitHub icon link;
  REMOVE PaletteTrigger from the landing navbar only.
- [x] T4 Landing.tsx hero: beta badge bg-primary/10 -> bg-surface
  (light-mode contrast fix, 4.47:1 -> pass); preview solved '144' ->
  '138'; update the header comment (numbers + snapshot note).
- [x] T5 Landing.tsx sections: ids features/showcase/faq; alternating
  bands (Features, Why, Roadmap banded); How-it-works as numbered steps
  without card chrome; FAQ as <details> accordions (full width).
- [x] T6 Landing.tsx showcase: tabbed viewer (reuse ui.tsx Tabs:
  Dashboard / Analytics), one big image, click -> lightbox overlay
  (Esc/click-to-close, close button, role=dialog, aria-modal).
- [x] T7 Landing.tsx "Why this problem?" section (band): 3 picks with
  the numbers from spec.md (real formula, demo data, computed
  2026-11-27): 1366C W 0.0/D 61.0/R 50.0/P 60.0 -> 37; 1360E W 56.6/
  D 0.0/R 73.0/P 60.0 -> 43; 1367C W 0.0/D 0.0/R 50.0/P 60.0 -> 19.
  Each pick: why sentence via formatWhy + 4 factor bars (value, weight,
  contribution) + total. Caption names the formula + demo account;
  footnote names the mirror-score difference + below-band note.
- [x] T8 Landing.tsx built-with: order -> React, FastAPI, PostgreSQL;
  add under-the-hood line (16 tables, DB job queue, Argon2, ML AUC
  0.834). Footer below CTA: "Built by Khalid Bin Masud" + GitHub icon
  link (prominent) + /privacy + codeforces.com + not-affiliated note.
  Tighten spacing below the CTA (py-12 -> py-8, mt-8 -> mt-6).
- [x] T9 Privacy page (frontend/src/pages/Privacy.tsx, new) + route in
  App.tsx (/privacy, lazy like the other pages) + footer link. EN+BN
  via the T1 keys. LandingHeader on top, same footer treatment.
  (Deviation: App.tsx uses a direct import for Privacy, like Landing —
  see spec.md §9.1.)
- [x] T10 index.html: og:image https://cp-compass.vercel.app/og.png ->
  https://cp-compass-phi.vercel.app/og.png (real Vercel URL).
- [x] T11 Verify: npm run build passes; pytest green (sanity, backend
  untouched); CDP screenshots landing EN/BN desktop + mobile 390px +
  light + dark (incl. showcase tabs, lightbox, why-section, footer,
  /privacy) — 0 console errors, 0 horizontal overflow; view them.
  Lighthouse quick check if available.
  Verified 2026-11-27 ~20:05: build passes (tsc + vite, 2.45s);
  pytest 39 passed; 16 screenshots viewed (desktop + mobile, EN + BN,
  light + dark) — 0 console errors, 0 overflow on all 7 page loads.
  Tab switch (Analytics), lightbox open (Esc close), FAQ <details>,
  #faq anchor (top: 0) all exercised live in CDP.
  Showcase images RE-CAPTURED from the current demo (seed changed in
  Batch 2 after the v1 captures): old images showed 144 solved / 3-day
  streak / "graphs 49%"; new ones show 138 / 2 days / "dp 45%",
  matching the live demo API. Local backend demo API confirmed
  solved=138, streak=2, rating=1478 before capture.
  Note: an unscrolled full-page capture looks empty below the fold —
  that is expected, not a bug: the showcase img is loading="lazy" and
  the section headings use framer-motion whileInView (initial opacity
  0). A scroll-through full-page capture renders everything.
  Lighthouse: NOT installed on the laptop (`where lighthouse` finds
  nothing) — skipped, per "if available".
- [x] T12 Commit (one commit, landing v2) + push + live verification:
  health + DB-backed probes (register throwaway account, login, delete
  it) — health-only checks miss total auth outages (lesson 2026-11-27).
  Verify the live landing + /privacy render.
  DONE 2026-11-27 ~20:20: commit 3e090b2, pushed fdcaa17..3e090b2.
  Live frontend: new bundle index-aOvYunCj.js, all 7 new strings present
  ("Why this problem?", "Built by Khalid Bin Masud", "Free to use",
  "Under the hood", "16 database tables", "Privacy", "Score = 0.35W");
  /privacy 200; Render health 200; verify-email/resend-code {} -> 422.
  Probe (khalidmasud22+cpcompassprobe@gmail.com): register 201, but the
  verification email NEVER arrived — first attempt 503 "Could not send
  the verification email", retry + resend-code silent-fail (those paths
  don't surface mail failure). Login correct password -> 403 "Email not
  verified" (row exists, Argon2 passes, gate enforced); wrong password
  -> 401. Full verify -> login -> delete could NOT run: no code was
  delivered, and Gmail redacts verification codes (cannot be recovered
  for an API call). Root cause (evidence, not guess): sender is
  onboarding@resend.dev — Resend's TEST domain, which only delivers to
  the Resend account's own address (khalidmasud22@gmail.com; codes DID
  arrive there at 19:42/19:44/19:55). So today NO new user with any
  other address can verify — signup is broken for everyone except
  Khalid. Fix: verify a custom domain in Resend + set MAIL_FROM to it.
  Secondary gap: register-retry and resend-code hide mail failure
  ("check your inbox" with no email sent). Probe account cleaned up
  via direct Neon delete (user id 6 + 1 code row); login after delete
  -> 401. Lighthouse: not installed — skipped.
