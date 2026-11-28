# Batch 5 — arena result (PWA service-worker caching strategy)

## What actually ran (honest status — read this first)

The full 100-agent tournament did NOT run. This is the fallback the
batch brief anticipates, not a tournament winner.

- Arena initialised: run-20261128-043930-s7, seed 7, 100 agents, 100
  distinct cards from 2160, 7 rounds, 595 sub-agent calls in 70 waves
  (bracket.py plan output on record).
- Spawn wave 1 ran for real: 10 competitors (a001-a010), all 10 DONE,
  solutions on disk (1153-1425 words each, 12077 words total).
- Wave 1 took ~8 minutes wall time for 10 calls. At that rate the full
  70-wave tournament is ~9+ hours of continuous waves — plus one
  orchestrator turn per wave and ~600 result handoffs through a single
  session's context. That cannot run in this host inside one batch
  session alongside building Batch 5, so waves 2-10 of spawn and all 7
  attack/defend/judge rounds did not run. No bracket winner exists.
- What happened instead (transparent fallback): I scored all 10 spawn
  solutions myself against the arena rubric
  (correctness 30 / completeness 25 / specificity 15 / robustness 20 /
  clarity 10; robustness scored on flaws I found myself, since no
  attacks ran). The highest scorer is the design the PWA build
  follows. This is a "spawn-probe pick", NOT an arena tournament
  winner — no attack, defend, or judge round ran, so no solution was
  ever attacked or revised.
- Full run folder: specs/batch5/arena-run/ (arena.json, task.md,
  rubric.md, prompts/, r0/a001-a010.md). VM copy:
  ~/workspace/cp-compass-arena-batch5/.arena/.

## Scores (my rubric scoring of the 10 spawn solutions)

| id | words | correctness /30 | completeness /25 | specificity /15 | robustness /20 | clarity /10 | total /100 |
|----|-------|-----------------|------------------|-----------------|----------------|-------------|------------|
| a002 | 1198 | 9 | 10 | 8 | 9 | 9 | **91.0** |
| a008 | 1146 | 9 | 10 | 9 | 8 | 9 | 90.5 |
| a006 | 1180 | 9 | 9 | 9 | 9 | 9 | 90.0 |
| a009 | 1425 | 8 | 10 | 9 | 8 | 8 | 86.5 |
| a001 | 1195 | 9 | 8 | 9 | 8 | 9 | 85.5 |
| a004 | 1192 | 9 | 8 | 9 | 8 | 9 | 85.5 |
| a007 | 1194 | 8 | 9 | 9 | 7 | 9 | 83.0 |
| a003 | 1197 | 8 | 9 | 9 | 7 | 8 | 82.0 |
| a010 | 1153 | 8 | 8 | 7 | 7 | 8 | 76.5 |
| a005 | 1197 | 7 | 8 | 8 | 6 | 8 | 73.0 |

## Winner (spawn-probe pick): a002

Why a002, in one line: it is the only design that patches the
old-tab race (unversioned assets cache) AND red-teams itself (five
hostile cases with patches) AND makes the update mechanism concrete
(vercel.json headers block).

Design (a002, condensed):
- Two caches: `cp-shell-vN` (versioned shell) + `cp-assets`
  (UNVERSIONED — keys are hashed URLs, so content versions itself;
  an old tab running Deploy 47 keeps working after Deploy 48).
- Precache at install (with cache:'reload'): `/`, `/index.html`,
  `/compass.svg`, `/manifest.webmanifest`, the shipped woff2 fonts.
  Hashed /assets/* NOT precached (names unknowable in static sw.js);
  cached at runtime on first fetch. Nothing under /api/v1, ever.
- Fetch gate first: non-GET, /api/* (incl. /demo/* and SSE
  /api/v1/sync/stream), any request with Authorization, cross-origin
  -> return without respondWith (zero latency, zero cloning, zero
  chance of caching).
- Navigations: network-first, cache fallback; only 200 cached, key
  /index.html. /assets/*: cache-first (immutable hashes). /fonts/*,
  /compass.svg: cache-first. /icons/*, manifest, favicon:
  stale-while-revalidate. Everything else: network-only.
- Update: every navigation re-fetches /sw.js (Cache-Control: no-cache
  in vercel.json); byte change (VERSION bump) installs a new worker;
  install precaches, skipWaiting(), activate deletes all caches
  except the two current ones, clients.claim(). Banner "New version
  available — Reload" on updatefound; reload only on tap; no forced
  reload. Old-tab race patched by the unversioned assets cache.
- Offline: shell + fonts + logo load; deep links serve cached
  /index.html; data views show the offline state (nothing faked).
  First-ever visit offline: browser offline page (stated, not hidden).
- Never cached: every /api/v1 response (auth or public /demo/*), SSE,
  non-GET, cross-origin, non-200, Authorization. Recovery: kill-switch
  worker (skipWaiting + delete all caches + unregister), or DevTools
  clear site data. vercel.json headers: /sw.js no-cache,
  /index.html max-age=0 must-revalidate, /assets/* immutable.
- Verification: (a) Cache Storage holds only the two caches, zero
  /api keys; second-user check; (b) offline reload of / and
  /app/dashboard; (c) VERSION bump -> new worker, old shell cache
  gone, banner path via reg.update().

Known wart of a002 (scored, not hidden): VERSION is a manual bump on
every deploy (release checklist). A forgotten bump leaves precached
fonts/logo stale — but NOT the shell: navigations are network-first,
so online users still get fresh index.html. The build will use a
build-time BUILD_ID injection (a008/a006 pattern) instead of a manual
bump, which removes the wart without changing the design.

## Supplements borrowed (explicit, not silent)

- a008: the complete sw.js file layout as the implementation template
  (a002 gave routing code + table, not one pasted file), and the
  192/512 PNG icon requirement for installability (outside the arena
  decision's scope — the task file said the manifest already exists —
  but required by spec item 2; handled in the build).
- a006: the waiting-worker + SKIP_WAITING message flow was considered;
  NOT adopted — a002's skipWaiting() is safe here because activation
  never reloads the page and the unversioned assets cache keeps old
  tabs working, so the waiting flow adds complexity for no gain.
- a003's 4 s navigation race and a007's stale-while-revalidate
  catch-all were rejected: the race adds failure modes for a problem
  Vercel hosting does not have (index.html is static, not Render),
  and the SWR catch-all caches URLs the design never listed.

## One-line notes on the other nine

- a008 (90.5): complete code, three defences, icons fix, trade-offs;
  lost by half a point — no old-tab-race patch (single versioned
  cache deleted on activate) and no attack-testing.
- a006 (90.0): waiting worker done right, backend no-store defence in
  depth, kill-switch with unregister; manual VERSION bump and no
  unversioned assets cache.
- a009 (86.5): best update UX (banner with snooze, SW_ACTIVATED);
  1425 words over the 1200 aim; manual bump; font names exactly right
  (Manrope/SplineSansMono/Michroma).
- a001/a004 (85.5): sound, complete code; thin on icons/verification
  detail; a001's precached font filename is a guess.
- a007 (83.0): SWR catch-all caches unlisted URLs; fonts cache is
  never deleted (stale font forever on a forgotten bump).
- a003 (82.0): build-manifest precache is elegant but adds build
  config; cache.put without an ok-check caches error responses.
- a010 (76.5): fetch handler given as rules only, no complete code;
  activate deletes EVERY cache name (over-broad).
- a005 (73.0): install discovers assets by regex-parsing fetched
  HTML; best-effort install can activate with an empty cache —
  fail-open on the offline guarantee.

## Decision for the build

Implement a002's design, with BUILD_ID injected at build time
(removing the manual-bump wart) and the a008 icon fix. No other item
in Batch 5 is affected by this decision.
