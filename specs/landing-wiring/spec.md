# Landing wiring — spec

Batch 6 has landed (HEAD da9d3ed). Wire the landing prep work that was done
on disk while Batch 6 was running, without touching Batch 6's commit.

## Pre-existing (uncommitted, from the landing-prep agent)
- `frontend/index.html` — favicon link now `/favicon.svg`
- `frontend/public/favicon.svg` + `frontend/public/logo-512.png` — Concept 1
  "Rising Needle", byte-identical to the VM originals
- `frontend/src/pages/Terms.tsx` — EN+BN Terms page, self-contained strings,
  follows Privacy.tsx structure, never type-checked

## Scope (exactly three items)
1. **Header logo**: swap the shared `Logo` component (layout.tsx) from the
   lucide `Compass` icon to the Rising Needle `/favicon.svg` mark. The same
   component serves the app shell and the landing header. Delete
   `public/compass.svg` once nothing in `src/` references it (verified:
   only stale `dist/index.html` mentions it).
2. **Terms route + footer link**: `/terms` route in App.tsx following the
   `/privacy` route pattern exactly; footer link next to `/privacy` in the
   Landing.tsx footer. Add `termsLink` to i18n en/bn/dict (footer label only);
   Terms.tsx itself needs no i18n keys.
3. **Build + visual verify**: `npm run build` must be green (Terms.tsx was
   never type-checked). CDP screenshots: landing desktop + mobile 390px,
   /terms EN + BN. 0 console errors.

## Verification
- `npm run build` green; `git status` shows ONLY the landing files
- Screenshots viewed: header logo + favicon render, /terms renders EN + BN
- After push + Render deploy: health 200, live /terms 200, favicon loads

## Out of scope (explicit)
- vite.config.ts / Reticle files (next batch), specs/batch4|batch5/tasks.md
- backend files, NEON-APP-ROLE.txt, .env files, Render DATABASE_URL switch
- Product name stays "CP Compass" (rename question still open with Khalid)
- PWA manifest icons (`public/icons/*`) — still the old mark; follow-up, not
  this batch
