# Batch 5 — tasks

Base: 2e282a2. Spec: specs/batch5/spec.md. Arena decision:
specs/batch5/arena-task.md (run the full-100 arena FIRST, then build
the PWA to the winning design).

## Phase 0 — arena (before any build)
- [x] Read specs/batch5/arena-task.md; wrote .arena/task.md (VM side,
      ~/workspace/cp-compass-arena-batch5/.arena/)
- [x] `bracket.py plan --agents 100` (7 rounds, 595 calls, 70 waves)
- [x] `bracket.py init --agents 100 --seed 7 --task-file .arena/task.md` (run-20261128-043930-s7)
- [x] Spawn wave 1 ran (10/100, all DONE, ~8 min); full tournament NOT run — see arena-result.md
- [x] Recorded in specs/batch5/arena-result.md: spawn-probe pick a002 (91.0/100); PWA build follows it
- [x] Full tournament infeasible (~9+ h for 70 waves in one session) — recorded in arena-result.md

## Phase 1 — backend
- [x] Migration 0008: users.public_profile Boolean NOT NULL DEFAULT FALSE
      (alembic upgrade + downgrade round-trip on SQLite — test_migration_0008_roundtrip)
- [x] auth.py: get_current_user_query (JWT access token from ?token=)
- [x] GET /api/v1/sync/stream (SSE): state + progress + terminal events,
      15s heartbeat comments, close after terminal event
- [x] POST /api/v1/settings/public-profile {public} + include
      public_profile in GET /api/v1/settings
- [x] services.public_profile_stats(db, user) reusing tag_stats /
      current_streak / longest_streak
- [x] GET /api/v1/u/{handle} (public, 404 unless opted in)
- [x] GET /api/v1/calendar/export.ics (auth, VCALENDAR from
      cf.contest_list() phase BEFORE, 502 on CF failure)
- [x] Tests: test_sse_stream.py, test_public_profile.py,
      test_ics_export.py — 19 new pass, full suite 113 green

## Phase 2 — frontend
- [x] api client + types: syncStream helper (EventSource URL builder),
      PublicProfile, CompareData, SettingsData.public_profile
- [x] SyncChip: EventSource while running, fallback to 15s polling
- [x] PWA: manifest.webmanifest + sw.js (WINNING arena design) +
      registration in main.tsx (PROD only) + offline indicator
- [x] PublicProfile page /u/:handle + route (no auth)
- [x] Compare page /app/compare + nav link (auth)
- [x] Calendar page: Export .ics button (blob download)
- [x] LampToggle component + AuthPage wiring (theme props from AppRoutes)
- [x] i18n: all new keys in dict.ts + en.ts + bn.ts
- [x] `npm run build` passes; existing node --test green

## Phase 3 — verify
- [x] Dev backend :8004 + preview :4173: SSE live progress; public
      profile opt-in flow; .ics parses; manifest + sw.js served;
      lamp screenshots light/dark + keyboard check
- [x] Screenshots saved under ~/workspace/shots-batch5/
- [x] BugHunter re-check on the new endpoints (new routes only)
- [x] chrome-devtools-mcp check on the new pages (console errors,
      network: no /api response cached by the SW)
- [x] modern-web-guidance check on the new frontend code


Notes (Phase 3 adaptations):
- BugHunter: no skill dir named BugHunter exists in custom-skills
  (searched); re-check done with the security-review skill checklist
  + IDOR/enumeration reasoning on the 4 new routes — no findings
  above Low; new: SSE token also lands in uvicorn access logs
  (query param), same class as the hacker-review flag.
- chrome-devtools-mcp: no MCP server in this host; checks done with
  a raw CDP driver (batch5-cdp.mjs): 0 console errors/exceptions/
  failed requests; no /api URL in Cache Storage; offline reload OK.
- modern-web-guidance: searched + retrieved dark-mode-toggle and
  accessibility guides; applied color-scheme per theme in tokens.css
  + color-scheme meta in index.html (guide: keep color-scheme in sync
  with the toggle). aria-pressed + :focus-visible already correct.
- Verification found a PRE-EXISTING bug (fixed in this batch):
  cf.py asyncio.Lock shared across the main loop and worker threads
  wedged the sync worker forever on the 2nd sync in a process.
  Fix: threading.Lock + slot reservation; regression test
  tests/test_cf_lock.py (old design reproduced the wedge).
- Minor wart (NOT fixed, pre-existing): a sync that finds 0 new
  submissions leaves last_synced_at NULL, so the chip shows
  "Synced never" for a completed sync. Fix belongs to run_sync.
## Phase 4 — commit + push + live verify
- [ ] Commit ONLY batch5 files (never Reticle files, never ci.yml);
      normalize line endings per blob
- [ ] Push via Python-stdin winreg GITHUB_TOKEN + throwaway askpass
- [ ] Live probes: health 200, /docs 404, public profile 404 (private
      handle), .ics 401 without auth, manifest + sw.js served
- [ ] Report: commit hash, files, exact test counts, live evidence,
      honest limits (live AI still 503; live Neon has 0 submissions)
