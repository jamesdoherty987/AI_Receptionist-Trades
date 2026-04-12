// BookedForYou Service Worker v1.1.0
const CACHE_NAME = 'bfy-cache-v1.2';
const RUNTIME_CACHE = 'bfy-runtime-v1.2';

// Only pre-cache actual static files (not SPA routes)
const PRECACHE_URLS = [
  '/manifest.json',
  '/logo.png',
];

// Install — pre-cache static assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
  );
});

// Activate — clean old caches
self.addEventListener('activate', (event) => {
  const currentCaches = [CACHE_NAME, RUNTIME_CACHE];
  event.waitUntil(
    caches.keys().then((cacheNames) =>
      Promise.all(
        cacheNames
          .filter((name) => !currentCaches.includes(name))
          .map((name) => caches.delete(name))
      )
    ).then(() => self.clients.claim())
  );
});

// Fetch strategy
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests (POST, PUT, DELETE go straight to network)
  if (request.method !== 'GET') return;

  // Skip non-http(s) protocols
  if (!url.protocol.startsWith('http')) return;

  // API calls — NEVER intercept, always go to network
  if (url.pathname.startsWith('/api/') || 
      url.pathname.startsWith('/api') ||
      url.pathname.startsWith('/twilio/') || 
      url.pathname.startsWith('/health')) {
    return;
  }

  // External resources (fonts, CDN) — cache-first with network fallback
  if (url.origin !== location.origin) {
    event.respondWith(
      caches.match(request).then((cached) => {
        if (cached) return cached;
        return fetch(request).then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(RUNTIME_CACHE).then((cache) => cache.put(request, clone));
          }
          return response;
        }).catch(() => {
          // Return empty response if both cache and network fail for external resources
          return new Response('', { status: 408, statusText: 'Offline' });
        });
      })
    );
    return;
  }

  // Hashed static assets (JS, CSS, images) — cache-first (they have unique filenames)
  if (url.pathname.match(/\.(js|css|png|jpg|jpeg|svg|gif|ico|woff2?|ttf|eot)(\?|$)/)) {
    event.respondWith(
      caches.match(request).then((cached) => {
        const fetchPromise = fetch(request).then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(RUNTIME_CACHE).then((cache) => cache.put(request, clone));
          }
          return response;
        }).catch(() => null);

        // Return cached immediately, update in background
        if (cached) return cached;
        return fetchPromise.then((response) => response || new Response('', { status: 408 }));
      })
    );
    return;
  }

  // Navigation requests (SPA routes) — network-first, fallback to cached index
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          // Cache the index.html response for offline fallback
          if (response.ok) {
            const clone = response.clone();
            caches.open(RUNTIME_CACHE).then((cache) => cache.put('/', clone));
          }
          return response;
        })
        .catch(() => {
          // Offline — serve cached index.html for any route (SPA handles routing)
          return caches.match('/').then((cached) => {
            if (cached) return cached;
            return new Response(
              '<html><body style="font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;background:#f8fafc"><div style="text-align:center"><h2>You\'re offline</h2><p>Please check your connection and try again.</p></div></body></html>',
              { headers: { 'Content-Type': 'text/html' } }
            );
          });
        })
    );
    return;
  }
});

// Listen for skip-waiting messages from the app
self.addEventListener('message', (event) => {
  if (event.data === 'skipWaiting') {
    self.skipWaiting();
  }
});
