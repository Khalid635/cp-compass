# CP Compass — Premium Apply (spec draft, VM copy)

Drafted 2026-11-27 ~21:50. Khalid's go-ahead: "koro" (21:49). The repo copy of this
spec goes in `specs/premium-apply/` when the batch starts. Runs AFTER the dashboard
batch finishes — same repo, one batch at a time.

## Goal

Use all seven newly installed sources across CP Compass so it looks and feels
premium: Context7 (3 skills), react-bits, 21st.dev, motion-primitives, GlassyUI,
taste-skill, Reticle — plus the realtimecolors palette he shared. Target: 8.5–9/10
on the reviewer's bar; 10/10 is NOT promised (Render free-tier ~50s cold start
alone blocks it; mobile + a11y + real-user testing still pending after this).

## Scope (in order)

1. **Landing v3** (review #3 fixes, received 21:15):
   - One `score()` for demo + landing + real app; drop "simplified preview".
   - Why-text generated from factors + unit tests (reviewer's `explain()` sketch).
   - Minimum-score threshold; fewer picks is fine ("আজ ২টা পিক").
   - One-line explanation/tooltip per factor (Recent need, Practice priority).
   - Verify factors actually vary across candidates on a real account.
   - README: AUC 0.834 methodology (data size, split by user/time, baseline =
     rating-gap-only Elo, log-loss/calibration next to AUC). Under-the-hood line
     → "resumable sync, Argon2, solvability model (method in README)".
   - Showcase tabs: add Practice + Revision; `role="tablist"` + keyboard arrows.
   - FAQ: one open by default + 3 new questions (vs Codeforces profile, why
     first load is slow, why lower-rated problems).
   - Why-card score alignment (always right), small text 11–12px → 13–14px.
   - Centering check at 768/1024/1440px; hero real screenshot (or shrink section).
   - "Beta"/"Coming soon" chips teal → `--muted` outline; hero gradient emphasis
     on "practice next"; feature cards get small visuals.
2. **Premium UI** (same batch, landing + dashboard touch-ups only where the
   dashboard batch left room):
   - GlassyUI glass components (glass-panel, glass-button, glass-tabs, glass-scene)
     for chrome: cards, panels, navbar — NOT for data-dense tables.
   - motion-primitives + react-bits motion in hero/showcase only: count-up stats,
     hero text animation, rings animate once ~300ms. Dashboard data stays static.
   - 21st.dev: search registry for Practice/Revision tab + FAQ components first;
     hand-write only when nothing matches; adapt every pick to CP Compass tokens.
   - Wide Signal fonts (already approved 21:04): Michroma display only, Manrope
     body, Spline Sans Mono mono; Noto Sans Bengali fallback.
   - taste-skill finish gate on every changed page (anti-slop check).
3. **Context7 MCP wiring** for the project (resolve-library-id + query-docs);
   free API key from context7.com/dashboard if rate limits bite.
4. **Reticle first verdict**: after host reload + one dev-server restart
   (post-contest), drive a real flow (login) and get a pass/fail verdict.

## Palette decision (needs Khalid's call before the colour step)

- Current: dark glassy teal (+ Freight mono black in dashboard).
- His realtimecolors link: indigo — bg #050315, text #fbfbfe, primary #2f27ce,
  secondary #dedcff, accent #433bff, Inter.
- Plan: build teal vs indigo variants, show before/after screenshots, he decides
  with his eyes. Do NOT silently switch the palette.

## Constraints

- Laptop-first: all work in D:\Projects\cp-compass via SSH; VM is a mirror only.
- Commit ONLY this batch's files. Reticle init changes stay uncommitted.
- No dev-server restart during the contest (till 22:50).
- Read every third-party component file before adding it; copy-paste only, never
  run install/build scripts inside the cloned repos (motion-primitives,
  glassyui, react-bits, 21st, context7).
- GlassyUI needs React 19 + Tailwind 4 — VERIFY the frontend's Tailwind version
  first (prep check was blocked 21:49: laptop SSH unreachable, 2× exit 255).
- Motion budget: rings once, hover lift + border brighten only, respect
  reduced-motion / reduced-transparency. No autoplay video/parallax in dashboard.
- Live verify with DB-backed probes + probe cleanup; screenshots before/after to
  ~/workspace/shots-premium-apply/; report with screenshots for his verdict.

## Out of scope (separate tracks)

- Resend custom-domain fix (waiting on his domain + DNS provider).
- Batch 3 (backtest + README results), Batch 4 (contest post-mortem), Batch 5
  (SSE, PWA, public profile, friend compare, .ics).
- Reticle commit decision; Canvix MCP helper.
