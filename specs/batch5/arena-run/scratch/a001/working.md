# a001 working notes (NOT part of the solution)

## Adversarial attacks (harshest reviewer) — build the answer backwards from these
1. "Your cache-first index.html strands users on a stale shell forever." → versioned cache names + activate deletes all non-current caches + skipWaiting + update check on focus.
2. "You cached /api/demo — it's public, but a later auth change turns it private." → never cache ANY /api/v1 path, even public demo; allowlist is shell-only, everything else network-only by default.
3. "Shared device: user B sees user A's dashboard." → no API response ever enters any cache; caches hold only public, identical-for-everyone shell bytes; logout needs no purge.
4. "Your SW intercepts the SSE sync stream and buffers/kills it." → /api/* returns before any cache logic; no fetch-handler interference at all.
5. "Hashed assets change every build; your precache list is stale on day one." → precache only stable URLs; hashed /assets/* handled by a runtime cache-first cache keyed by full URL (old hashes simply never match again).
6. "skipWaiting + claim reloads mid-sync and corrupts a sync." → never auto-reload; update banner with a user-tapped Refresh; claim only affects navigations after reload.
7. "A buggy SW bricks the app and your design has no escape hatch." → versioned caches + byte-change update + emergency no-op SW kill-switch + clear-site-data path.
8. "Stale index.html references evicted hashed JS → white screen offline." → navigation is network-first with cache fallback (fresh shell whenever online); runtime asset cache is versioned with the shell cache so old pairs die together.
9. "Background update checks hammer the sleeping Render backend." → update checks fetch only /sw.js from Vercel (static), never touch the backend; no background/periodic sync at all.
10. "Opaque/cross-origin responses or a POST get cached." → cache only same-origin GET, status 200, type 'basic', request without Authorization, URL on the allowlist; try/catch falls through to network.

## Three drafts
### Draft A — Precached shell + versioned runtime caches (chosen)
Precache stable shell URLs at install; runtime cache-first for hashed /assets/* and /fonts/*; network-first navigations with cached-shell fallback; network-only /api/*; skipWaiting + user-confirmed reload. No build-time manifest injection, no new deps. Strongest: every hard constraint met with the fewest moving parts; failure modes are loud (offline fallback page) not silent.

### Draft B — Network-first everything + offline fallback page
Every navigation goes to network, fallback to a dedicated offline.html. Simpler reasoning, but: shell does NOT load offline as the real app (only a stub page), violating constraint 2 in spirit; every online navigation pays full latency; stale-shell risk merely moves, not solved. Rejected.

### Draft C — Workbox generateSW
Precaching, versioning and routing all handled. Rejected outright: task forbids new deps by default, adds a build step and a second cache layer to audit, and its default precache of index.html with cache-first navigation is exactly the stale-shell trap in attack 1. Rejected.

## Pick: Draft A. Develop only that one fully.
