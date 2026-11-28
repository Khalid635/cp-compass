# Outline — Batch 5 SW design (a006) — scratch, not the solution

## Decomposition (independent sub-problems)
1. Privacy / cross-user leak — the hard constraint that kills designs.
2. Offline shell — what must load, what must not.
3. Updates / staleness — new deploy must reach users.
4. Hashed assets + single index.html — build-time mechanics.
5. API/SSE bypass — zero fetch-handler interference.
6. Backend load — sleeping Render, no wake-ups.
7. Failure recovery — buggy SW escape hatch.
8. Verification — provable claims (a)(b)(c).

## Edge cases first (design around these)
- Shared device, user A logs out, user B logs in: cache holds only public shell → nothing to leak; no per-user cache, no logout purge needed.
- /demo/* is public BUT under /api/v1 → network-only anyway (API prefix rule wins; no exception list to get wrong).
- SSE /api/v1/sync/stream: long-lived stream; any respondWith/clone would break or delay it → early return, no interception.
- Hashed assets: never hardcode hashed names in source sw.js → build script injects precache manifest + BUILD_ID.
- index.html cache-first = stuck forever on stale shell → navigations network-first, precached copy is offline fallback only.
- SW update check must not hit Render: /sw.js is static on Vercel; registration.update() on focus is cheap.
- Buggy SW: install failure keeps old SW; emergency kill-switch SW (unregister + delete caches); /sw.js served no-cache.
- Non-GET, cross-origin, opaque responses, Set-Cookie / no-store responses → never cached; only same-origin GET 200, allowlisted prefixes.
- Safari: skipWaiting/clients.claim supported; no Background Sync/Periodic Sync APIs used at all.
- Offline deep link /app/dashboard: serve cached index.html; router renders route; API fails → app's own offline state, never stale data.
- Token in localStorage, not cookie: SW never reads localStorage (can't) and must never read/forward Authorization.

## Outline check vs task requirements
- Cache names + versioning: single versioned cache cp-compass-shell-<BUILD_ID>, BUILD_ID = short git SHA + build timestamp, injected by post-build script; activate deletes all other cp-compass-* caches. ✓
- Precache list: / , /index.html, /manifest.webmanifest, /compass.svg + injected hashed JS/CSS + fonts. NOT precached: /api/*, /demo/*, anything with auth, cross-origin, non-GET. ✓
- Fetch routing table: navigations network-first→cached index.html; /assets/* cache-first; /fonts/* cache-first; /api/* network-only (no respondWith); else same-origin GET network-first, no put; cross-origin network-only. ✓
- Update flow: skipWaiting after precache, clients.claim, delete old caches, main.tsx updatefound → "New version" toast, user-tap reload (never forced mid-sync). ✓
- Offline behaviour: shell + router + offline banner/empty state; deep link works. ✓
- Not cached + failure mode: list + kill-switch + DevTools unregister + Clear-Site-Data header option. ✓
- Verification: (a) Cache Storage inspection + caches.match checks; (b) offline reload + deep link; (c) redeploy, new cache name, old gone, toast. ✓
- Deliverables: full sw.js, manifest notes, main.tsx lines, Vercel headers (index.html no-cache, assets immutable, sw.js no-cache). ✓
- Constraints: no new deps (Node fs-only post-build script), prod-only registration, no background/periodic sync. ✓
- Length: <1200 words. Target ~950.

## Structure of final file
1. Principles (3 bullets: privacy, shell-only cache, one versioned cache)
2. Cache name + versioning + build-time injection (script)
3. Precache list (table: precached / not)
4. sw.js (full file, compact)
5. Fetch routing table with WHY
6. Update flow + main.tsx registration
7. Offline behaviour
8. What is never cached + failure/recovery
9. Verification steps
10. Assumptions (short)
