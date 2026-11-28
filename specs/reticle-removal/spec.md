# Reticle overlay removal — spec

## Goal
Remove the Reticle gold viewport overlay from the CP Compass dev setup.
Approved by Khalid 2026-11-28 12:57 ("Reticle overlay soriye dao (Batch 6 sesh hole)").
Scope is the overlay only (plugin removal). No full Reticle uninstall.

## Findings (verified 2026-11-28 16:03, before any edit)
- `frontend/vite.config.ts` (working tree) contains the plugin:
  `import { reticle } from '@reticlehq/vite-plugin';` and
  `plugins: [reticle({ sourceMapping: false }), react(), tailwindcss()]`.
- HEAD's `vite.config.ts` does NOT contain Reticle (verified via `git show HEAD:`).
  The plugin lines are uncommitted working-tree changes only. Removing them
  restores the file to its committed state; there will be no vite.config.ts
  diff to commit. The removal is real (working tree no longer loads the
  plugin), it is just not a committable change.
- `frontend/package.json` and `package-lock.json` contain NO Reticle entry
  (findstr: no match). The premium-apply batch already removed the dep lines.
  package.json / package-lock.json stay untouched.
- `frontend/src/reticle-dev.ts` imports `@reticlehq/react`, but NOTHING imports
  reticle-dev.ts (grep over frontend/src: no import). It is loaded only by the
  vite-plugin's injected connect, so removing the plugin leaves it dead code
  that the bundler never resolves. It stays on disk per scope (not deleted).
- Dev server running: node PID 24188, listening [::1]:5173, HTTP 200.
  Vite binds ::1 only on this machine; check http://localhost:5173, never
  127.0.0.1. A restart is required: Vite does not hot-reload plugin changes.

## Steps
1. Remove the two Reticle lines from frontend/vite.config.ts (LF endings
   preserved; file must become byte-identical to HEAD).
2. Verify: `git diff frontend/vite.config.ts` empty; grep finds no `reticle`
   in vite.config.ts; package.json untouched.
3. `npm run build` in frontend/ must be green. If it fails because something
   still imports Reticle, report exactly what and STOP (do not delete more
   files to force it green).
4. Restart the dev server cleanly (taskkill PID 24188, then start detached
   via Python with logs; never --bypass-lock).
5. CDP screenshot of http://localhost:5173 via
   shots-premium-apply/cdp-shot.mjs; view it; all 4 viewport edges must be
   free of the gold frame.
6. Commit ONLY specs/reticle-removal/ (vite.config.ts matches HEAD, nothing
   to commit there). Push via HKCU winreg token + throwaway askpass .bat
   (deleted right after; token never printed).
7. Live sanity check: backend health 200 on /api/v1/health (production
   build never had Reticle).

## Out of scope (do NOT touch)
- .reticle.json, src/reticle-dev.ts, CLAUDE.md, AGENTS.md, RETICLE.md,
  .claude/, .codex/, .gemini/, .github/, .reticle/ (all stay as they are)
- specs/batch4/tasks.md, specs/batch5/tasks.md, backend files,
  NEON-APP-ROLE.txt, .env files
- package.json / package-lock.json (already clean)

## Acceptance
- vite.config.ts has no reticle reference; build green; localhost:5173
  screenshot shows no gold frame on any edge; commit pushed; live health 200.
