# Outline (inversion first) — a010

## Failures to make impossible
1. Private API cached / served to another user / after logout / shared device -> bypass /api entirely, never respondWith, never read Authorization, no cache.put for API, logout clears? SW never holds token.
2. Stale shell forever -> versioned cache name with BUILD_ID injected at build, network-first navigations, no-cache on sw.js itself, activate deletes old caches, update toast.
3. Offline shell fails -> precache stable shell + runtime-cache hashed assets on first visit.
4. Hashed assets unknown at author time -> don't precache hashed names; runtime cache-first /assets/*, immutable by hash.
5. SSE broken / latency / backend hammered -> fetch handler returns early for /api/*, no respondWith, no background/periodic sync, no precache of API.
6. New SW breaks app / buggy worker traps users -> kill-switch SW (empty fetch + delete all caches), sw.js no-cache, unregister path, registration only in prod.
7. index.html cached stale while assets deleted -> single versioned cache holds index+assets together; navigation network-first updates both together.
8. Cross-origin / non-GET / opaque cached -> only same-origin GET 200, bypass rest.
9. User loses work on forced reload -> no forced reload; toast + manual Refresh, skipWaiting+claim but reload only on user action.

## Outline vs task checklist
- Cache names/versioning: SHELL cache `cp-compass-shell-<BUILD_ID>`, BUILD_ID injected by build script, fallback, activate deletes others. ✓
- Precache list + NOT precached: precache /, /index.html, /compass.svg, /manifest.webmanifest, /fonts/* stable; NOT: hashed /assets (runtime), /api, sw.js. ✓
- Fetch routing table: navigations network-first+cache fallback; /assets cache-first; /fonts cache-first; /api network-only/bypass; else SWR; non-GET/cross-origin bypass. Each WHY. ✓
- Update flow: install precache, skipWaiting, activate delete old + claim, controllerchange toast, no forced reload. ✓
- Offline: what loads, deep link /app/dashboard -> cached index.html, router mounts, API fails -> offline banner/empty state, no data. ✓
- NOT cached + failure mode: list + kill-switch + DevTools unregister + clear site data. ✓
- Verification (a)(b)(c): Cache Storage check, offline reload, deploy bump check. ✓
- Files: sw.js full skeleton, manifest check, main.tsx registration, vercel.json no-cache for sw.js, build inject step. ✓
- Assumptions: BUILD_ID injection, fonts stable names, Vercel headers. ✓
- Word budget: aim ~950 words total incl code.
