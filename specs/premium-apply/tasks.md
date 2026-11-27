# Premium Apply — task tracker (batch, 2026-11-27)

Spec: `spec.md` in this folder. Steps 1–3 only; Step 4 (Reticle verdict) is the parent's job.
Do NOT commit/push. Do NOT touch Reticle files. Dev server :5173 already running — do not restart.

## Decisions (recorded as made)
- `MIN_SCORE_THRESHOLD = 25`. Demo under the unified formula: only 1360E (43) and
  1366C (37) survive; everything else sits at the 19 floor (0.20*50 + 0.15*60).
  Landing "Why" shows 2 picks ("আজ ২টা পিক"), demo Practice shows 2 cards.
- Factor variance on demo (26 FAMOUS candidates, unsolved): W 0–56.6 (2 distinct),
  D 0–61 (2 distinct), R 50–73 (2 distinct), P constant 60 (no FAMOUS problem was
  attempted-but-unsolved; P varies on real accounts). Factors DO vary.
- ML methodology (live artifact 2026-11-27T07:36Z, n=208: 197 synthetic demo + 11 real):
  RF test AUC 0.856, test Brier 0.129, CV AUC 0.818; baseline (rule score as
  probability) AUC 0.34, Brier 0.389; test n≈42. Split is stratified RANDOM 80/20 —
  NOT by user/time (say so honestly). Log-loss was never computed (gap for Batch 3).
  README's old 0.834 and ml.py's 0.821 are both stale vs the live artifact.
  Calibration: sigmoid tried, CV Brier 0.147 vs 0.148 → this artifact shipped WITH
  calibration (ml.py docstring's "rejected" is stale).
- GlassyUI: the full engine (glass-surface + scene-renderer 2,211 lines +
  use-refraction-filter 1,110 lines + liquid.css 5,458 lines, needs clsx +
  @radix-ui/react-slot) is too heavy to copy verbatim for chrome-only use.
  Adapted lightweight `GlassPanel`/`GlassButton` in CP Compass tokens, grounded in
  GlassyUI's liquid.css values (blur 14px, saturate 1.4–1.8, 1px rim,
  reduced-transparency kills backdrop-filter). Documented in glass.tsx.
- motion-primitives: `TextEffect` copied faithfully (cn replaced by a local join);
  used for the hero subtitle, per-word fade-in-blur. Count-up: existing CountUp
  (700ms ease-out) reused for the hero stat strip. Rings already sweep once 300ms.
- 21st.dev: CLI token surrogate is sandbox-blocked (authd 403), so the registry was
  searched via the web instead. Patterns found: Animated Tabs (Motion sliding
  indicator), MiniDev tabs (Base UI, arrow/Home/End keys, reduced motion),
  Faq1 FAQ accordion section, Base UI Accordion (single/multiple open).
  Per the skill's "build it myself" workflow: hand-wrote Tabs keyboard nav +
  FAQ accordion in CP Compass's own stack, following those patterns. No code
  retrieval spent.
- Palette: teal stays base + default. Indigo variant (`?palette=indigo` →
  `data-palette="indigo"`) as comparison only, never default.
- react-bits: no new component copied — its CountUp is equivalent to the existing
  CountUp; reusing the existing one avoids a duplicate.

## Step 1 — Landing v3
- [x] Shared score: `frontend/src/lib/score.ts` (scoreFromFactors, explainFactors,
      FACTOR_META, MIN_SCORE_THRESHOLD=25) + `score.test.ts` (node --test)
- [x] Backend: `services.recommend` returns `factors`; `seed.py` unified on the
      real formula (extended `_tag_strengths` with weak_score + recent_acceptance,
      production weak rule — same single weak tag dp, 0.566); threshold 25 in both
- [x] Backend tests: `tests/test_score_unification.py`
- [x] Landing WHY_PICKS computed from score.ts, 2 picks (1367C dropped, 19 < 25)
- [x] explainFactors sentence from factor values on why cards + factor tooltips
- [x] FAQ: controlled accordion, first open by default + 3 new questions (EN+BN)
- [x] Showcase: + Practice + Revision tabs; Tabs arrow-key/Home/End nav
- [x] Beta/Coming-soon chips → --muted outline; hero gradient on "practice";
      feature cards get small SVG visuals
- [x] Why-card score always right (ml-auto, nowrap); small text 11–12px → 13–14px
- [x] Hero: real dashboard screenshot in browser frame + count-up stat strip
- [x] README methodology (live artifact numbers, random split stated honestly,
      log-loss gap marked); underHood line → "resumable sync, Argon2, solvability
      model (method in README)"
- [x] Centering check at 768/1024/1440 (screenshots) — REVIEWED 2026-11-28: 768/1024/1440/390 all centred, no horizontal overflow; 1024 why-card titles wrap to 2-3 lines (score stays right-aligned, reads fine); mobile header wraps to 2-3 rows (tall but clean)

## Step 2 — Premium UI
- [x] GlassyUI-adapted `GlassPanel`/`GlassButton` (chrome only: landing feature
      cards, why cards, showcase frame, hero CTAs) + glass CSS in base.css
- [x] TextEffect hero subtitle; count-up hero stats; rings once 300ms (already)
- [x] 21st.dev patterns applied (see Decisions); hand-written, CP Compass tokens
- [x] Wide Signal fonts kept, unchanged
- [x] Indigo palette variant via `?palette=indigo` (data-palette), teal default
- [x] taste-skill gate run + fixes — Round 1: GATE FAIL 61; Round 2: GATE FAIL 55; Round 3 refused ("rounds used up", page unchanged) -> final GATE: OPEN 55, 4 waivers applied, 42 WARNs. Fixed: tap-size (LanguageToggle gap), off-viewport at 320 (Tabs scroll), heading-order (sr-only h2 in #features), FAQ trigger 44px, footer links 44px. Verified by CDP at 320px: scrollWidth 320, FAQ buttons 45/66px, footer links 44px
- [x] Teal vs indigo comparison screenshots (landing + dashboard) — REVIEWED 2026-11-28: both coherent; indigo is clean/premium but generic-purple, teal is more distinctive and the gold accents (SPECIALIST rank, practice gradient) read better on it; indigo links are dimmer. NO VERDICT — Khalid decides with his eyes

## Step 3 — Context7 wiring
- [x] Repo-root `.mcp.json` (stdio, npx @upstash/context7-mcp) + `specs/premium-apply/context7.md`
- [x] Verify config JSON valid + server command resolves — 2026-11-27: `npm view @upstash/context7-mcp@4.0.3` -> 4.0.3 + registry tarball; server runs on stdio, exit 0; `.mcp.json` valid JSON (latest published is 4.9.1, pin kept at 4.0.3 per spec)

## Verification
- [x] `npm run build` passes (tsc + vite) — 3357 modules, ~2.3s; re-run 5x after fixes, last 2026-11-28 BUILD-OK after LF normalization; only pre-existing >500kB chunk warning
- [x] pytest passes — 2026-11-27: **45 passed** (40 existing + 5 new test_score_unification.py) in 24.5s; warnings are pre-existing utcnow deprecations
- [x] Screenshots: desktop + true-390 mobile + light + Bangla, every changed page
- [x] 0 console errors on changed pages (CDP) — app console errors 0 on all 19 shots + all re-captures; only noise is the Reticle plugin ws://localhost:4400 WebSocket failing (its dev server is not running) — pre-existing, not from this batch
- [x] Factor-variance numbers reported (see Decisions)

## Gate fixes (round 2-3, 2026-11-28)
- `src/i18n/index.tsx`: LanguageToggle `gap-2 sm:gap-0` (8px separation on phones).
- `src/components/ui.tsx`: Tabs tablist `overflow-x-auto`, tab buttons `shrink-0 whitespace-nowrap`.
- `src/pages/Landing.tsx`: sr-only h2 in #features (reuses `t.navFeatures`); FAQ trigger padding moved onto the button (`py-3 min-h-11`, container `pb-3` — row height unchanged); footer bottom-bar links `inline-flex min-h-11 items-center sm:min-h-0`.
- `shots-premium-apply/cdp-shot.mjs` (NEW, this batch): CDP screenshots, true-390, console-error capture, Reticle-tour Skip, scroll-through + `--reducedMotion` for full-page captures, `--eval` for measurements.
- `frontend/public/showcase-dashboard.png` RE-CAPTURED 2026-11-28 from live /demo (old file showed pre-unification scores 83/67/55; new file shows 43/37, consistent with the Why cards). `showcase-practice.png` + `showcase-revision.png` captured this batch (1440x900).
- Line endings: `ui.tsx` + `i18n/index.tsx` + `package.json` were converted to CRLF by this batch's edits and normalized back to LF 2026-11-28 (diffs now 39/4, 1/1, 44/1). `package.json` also reformatted 1-line -> pretty-printed (my json.dump edit) + Reticle deps + my deps — see HANDOFF §9.
- Scratch removed: `backend/uvicorn-premium.err` deleted. `build-premium*.log`, `uvicorn-premium*.log`, `dev-premium.log` are gitignored; left in place.
