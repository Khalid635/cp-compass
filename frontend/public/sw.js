/* CP Compass service worker — Batch 5, arena spawn-probe pick a002.
 *
 * Privacy rule: only the public shell is ever cached. No /api response
 * (authenticated or public /demo), no request carrying an Authorization
 * header, no non-GET request and no cross-origin response is ever
 * stored. The SSE stream and all /api traffic bypass this worker
 * entirely (the fetch handler returns before respondWith, so the worker
 * never sees, clones or delays them).
 *
 * Two caches: cp-shell-<BUILD_ID> (versioned shell) + cp-assets
 * (UNVERSIONED — keys are hashed URLs, so content versions itself; an
 * old tab running the previous deploy keeps working after a new one
 * activates). BUILD_ID is injected at build time by
 * scripts/inject-sw-build-id.mjs; a worker with a literal placeholder
 * must never ship (the inject script fails the build if it survives).
 *
 * Recovery from a buggy worker: ship a fixed sw.js (the byte change
 * triggers an update on next navigation) or, as a kill-switch, a no-op
 * sw.js whose activate deletes all caches and unregisters the worker.
 */
const BUILD_ID = '__BUILD_ID__';
const SHELL_CACHE = `cp-shell-${BUILD_ID}`;
const ASSETS_CACHE = 'cp-assets';
const ALL_CACHES = [SHELL_CACHE, ASSETS_CACHE];
const PRECACHE_URLS = [
  '/',
  '/index.html',
  '/compass.svg',
  '/manifest.webmanifest',
  '/fonts/Manrope.woff2',
  '/fonts/Michroma.woff2',
  '/fonts/SplineSansMono.woff2',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      .then((cache) =>
        cache.addAll(
          PRECACHE_URLS.map((url) => new Request(url, { cache: 'reload' })),
        ),
      )
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => !ALL_CACHES.includes(key))
            .map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);
  // Privacy gate first: anything here returns without respondWith —
  // the browser fetches it normally, untouched.
  if (request.method !== 'GET') return;
  if (url.pathname.startsWith('/api/')) return;
  if (request.headers.has('Authorization')) return;
  if (url.origin !== self.location.origin) return;
  if (request.mode === 'navigate') {
    event.respondWith(networkFirstNavigation(request));
    return;
  }
  if (url.pathname.startsWith('/assets/')) {
    event.respondWith(cacheFirst(request, ASSETS_CACHE));
    return;
  }
  if (url.pathname.startsWith('/fonts/') || url.pathname === '/compass.svg') {
    event.respondWith(cacheFirst(request, SHELL_CACHE));
    return;
  }
  if (
    url.pathname.startsWith('/icons/') ||
    url.pathname === '/manifest.webmanifest'
  ) {
    event.respondWith(staleWhileRevalidate(request, SHELL_CACHE));
    return;
  }
  // Everything else: network-only, never cached (default-deny).
});

async function networkFirstNavigation(request) {
  try {
    const res = await fetch(request);
    if (res.ok) {
      const copy = res.clone();
      caches.open(SHELL_CACHE).then((cache) => cache.put('/index.html', copy));
    }
    return res;
  } catch {
    const cached = await caches.match('/index.html');
    if (cached) return cached;
    return new Response('CP Compass is offline. Reconnect to load the app.', {
      status: 503,
      headers: { 'Content-Type': 'text/plain' },
    });
  }
}

async function cacheFirst(request, cacheName) {
  const cached = await caches.match(request);
  if (cached) return cached;
  const res = await fetch(request);
  if (res.ok && res.type === 'basic') {
    const copy = res.clone();
    caches.open(cacheName).then((cache) => cache.put(request, copy));
  }
  return res;
}

async function staleWhileRevalidate(request, cacheName) {
  const cached = await caches.match(request);
  const network = fetch(request)
    .then((res) => {
      if (res.ok && res.type === 'basic') {
        const copy = res.clone();
        caches.open(cacheName).then((cache) => cache.put(request, copy));
      }
      return res;
    })
    .catch(() => null);
  return cached ?? (await network) ?? Response.error();
}
