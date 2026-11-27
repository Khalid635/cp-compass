# Dashboard-apply batch — spec (2026-11-27)

Apply the approved design-preview elements + Freight mono ops style +
segmented score + colour changes where genuinely better + Wide Signal
fonts to CP Compass. Bar (Khalid, 19:39-19:40): the result must look GOOD
and BETTER than the current dark-glassy teal, judged by before/after
screenshots + his eyes. If a change looks worse, keep the old teal for
that spot and say so in the report.

## Approved sources
- Design preview approved 19:34 ("shundor to shudhu motion use kore r
  perfect size kore dile shei lagbe"): frosted-glass stat cards, progress
  rings animated once ~300ms, HUD telemetry panel, landing-hero display
  type (solid + outlined + gold word). Settled rule: HUD language in
  data pages + glass on chrome.
- motionsites.ai sweep (pass 2, 19:38): Freight Command monospace ops
  black (#050505, white, hairline borders, all-mono, no glass/gradient)
  is the best dashboard fit — swap its green dots for teal. 10-block
  segmented score (Finance Assistant) for rating bands / topic mastery.
  Beige-gold bars #c9b89a as secondary bars where teal is primary.
  F1 gold #ffc800 for ONE headline total only (never red+gold+teal
  together).
- Fonts: Wide Signal, picked by Khalid 21:04 — Michroma (display only),
  Manrope (body), Spline Sans Mono (mono/data). All free Google Fonts.
  Remove Inter + JetBrains Mono. Keep Noto Sans Bengali fallback.
- Full colour change allowed ("lagle puro colour bodlaba no prb but
  good looking hote hobe ager theke better hote hobe").

## Scope
1. Fonts: self-host woff2 in frontend/public/fonts/ (@font-face, no
   Google Fonts link at runtime). --font-sans Manrope, --font-mono
   Spline Sans Mono, --font-display Michroma. Display font on landing
   hero headline + logo wordmark only — never body text.
2. Tokens (dark only; light mode was verified good): --bg #0a0f0e ->
   #050505 (Freight near-black; also makes #131f1b cards stand out —
   the flatness nit from the 18:28 colour review). --gold #ffc800
   (dark) / #8a6d00 (light, 3:1+ on light bg). --gold-bar #c9b89a
   (dark) / #a08c5f (light).
3. HUD telemetry panel (new, Dashboard row 0): mono uppercase labels,
   hairline dividers, status dots (teal, never green), gold rank
   highlight, ONE coral alert only when a real problem exists (rating
   dropped last contest or revisions overdue). All values from the
   dashboard query — nothing invented.
4. Frosted-glass stat cards: StatCard gets the frost treatment + hover
   lift. Rings (GoalRings) sweep in once over ~300ms on load.
5. Segmented score (new component, 10 blocks): under each goal ring
   (mastery at a glance) + weekly-goal progress bar (10 blocks = 10%
   each instead of the continuous bar).
6. Hero display type (Landing): solid + outlined "Codeforces" + gold
   "practice"/"প্র্যাকটিস" — one gold word total on the whole page.
   New i18n keys in en.ts + bn.ts + dict.ts; same words, only styling.
7. Beige-gold secondary bars: Analytics difficulty distribution —
   "attempted" bars var(--surface-2) (nearly invisible) ->
   var(--gold-bar) + legend swatch.
8. Colour-fix follow-ups: already in (neutral rating pill, lifted
   surfaces, heat-0 floor, brighter muted) — verified in tokens.css,
   no action.

## Out of scope
Auth/backend/security code, H1 cookies, Resend mail, Batch 3/4/5,
Reticle files (do not touch), dev-server restart, visible browsers.

## Constraints
- Reticle init left UNCOMMITTED changes (package.json, package-lock,
  vite.config.ts modified; .reticle.json, src/reticle-dev.ts, CLAUDE.md,
  AGENTS.md, RETICLE.md, .claude/, .codex/, .gemini/, .github/,
  .reticle/ untracked). Commit ONLY dashboard files (scoped git add).
- Khalid is in a Codeforces contest on the laptop until 22:50 Dhaka.
  Do NOT restart the :5173 dev server. No visible browser windows —
  headless Chrome/CDP screenshots only.
- If the build breaks because of the Reticle Vite plugin, STOP and
  report exactly that instead of removing Reticle.

## Verification
- Frontend build passes (tsc + vite). pytest passes (backend untouched).
- CDP screenshots BEFORE vs AFTER, viewed: desktop 1280 + mobile 390,
  EN + BN, light + dark, landing + dashboard + demo. 0 console errors,
  0 horizontal overflow. Rings animate once; segments render.
- Commit + push (known-good askpass pattern). Live verify WITH
  DB-backed probes (register -> 201/503, login wrong pw -> 401,
  +alias probe, delete afterwards; never Khalid's own email).
