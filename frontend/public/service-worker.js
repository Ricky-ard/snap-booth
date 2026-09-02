/* SnapBooth service worker — offline-first for the event kiosk.

   Strategy:
   - App shell + JS/CSS/font/image assets: cache-first, refresh in background.
   - GET /api/events/active and GET /api/presets/{id}/lut.png: stale-while-revalidate
     so the kiosk survives a wifi blip.
   - GET /api/files/... (already-composed prints, filter thumbnails): cache-first.
   - Everything else on /api: network-first with a cache fallback, so live data
     (sessions, /hardware, /stats) stays fresh when online but the kiosk still
     opens when offline.

   Cache versions are bumped on every deploy — bump SW_VERSION below.
*/

const SW_VERSION = "snapbooth-v1";
const SHELL_CACHE = `${SW_VERSION}-shell`;
const RUNTIME_CACHE = `${SW_VERSION}-runtime`;
const API_CACHE = `${SW_VERSION}-api`;

// Files that must be cached at install time so `/kiosk` loads offline
const SHELL_URLS = [
  "/",
  "/kiosk",
  "/manifest.json",
  "/icon-192.png",
  "/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then((c) => c.addAll(SHELL_URLS)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter((k) => !k.startsWith(SW_VERSION)).map((k) => caches.delete(k)));
    await self.clients.claim();
  })());
});

function isApi(url) { return url.pathname.includes("/api/"); }
function isFilesRead(url) { return url.pathname.includes("/api/files/"); }
function isCacheableApiRead(url) {
  return url.pathname.match(/\/api\/(events\/active|presets\/[^/]+\/lut\.png|qr\/)/);
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;  // never cache mutations
  const url = new URL(req.url);

  // Files (photos, prints, LUT strips) — cache-first
  if (isFilesRead(url)) {
    event.respondWith(cacheFirst(req, RUNTIME_CACHE));
    return;
  }

  // Cacheable API reads (event bundle, LUT strips) — stale-while-revalidate
  if (isApi(url) && isCacheableApiRead(url)) {
    event.respondWith(staleWhileRevalidate(req, API_CACHE));
    return;
  }

  // Other API calls — network first, fall back to cache
  if (isApi(url)) {
    event.respondWith(networkFirst(req, API_CACHE));
    return;
  }

  // App shell / JS / CSS / static — cache-first with refresh
  event.respondWith(cacheFirst(req, SHELL_CACHE));
});

async function cacheFirst(req, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(req);
  if (cached) {
    // refresh in background
    fetch(req).then((res) => { if (res && res.ok) cache.put(req, res.clone()); }).catch(() => {});
    return cached;
  }
  try {
    const res = await fetch(req);
    if (res && res.ok) cache.put(req, res.clone());
    return res;
  } catch (e) {
    return cached || Response.error();
  }
}

async function staleWhileRevalidate(req, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(req);
  const network = fetch(req).then((res) => {
    if (res && res.ok) cache.put(req, res.clone());
    return res;
  }).catch(() => cached);
  return cached || network;
}

async function networkFirst(req, cacheName) {
  const cache = await caches.open(cacheName);
  try {
    const res = await fetch(req);
    if (res && res.ok) cache.put(req, res.clone());
    return res;
  } catch (e) {
    const cached = await cache.match(req);
    return cached || new Response(JSON.stringify({ offline: true }), {
      status: 503, headers: { "Content-Type": "application/json" },
    });
  }
}

// Trigger the backend cloud sync worker on demand (used by our online-listener
// in the app so guest-gallery uploads happen as soon as connectivity returns).
self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "TRIGGER_SYNC") {
    fetch("/api/sync/trigger", { method: "POST" }).catch(() => {});
  }
  if (event.data && event.data.type === "SKIP_WAITING") self.skipWaiting();
});
