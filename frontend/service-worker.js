// Cache basico de los archivos estaticos de la app (shell), para que cargue rapido
// y sea instalable como PWA. Los datos (ventas, productos, etc) NO se cachean aca:
// eso ya lo maneja OfflineDB (IndexedDB) en pos.js para el modo offline del POS.
const CACHE_NOMBRE = 'ventas-stock-shell-v1';
const ARCHIVOS_SHELL = [
  'login.html',
  'pos.html',
  'admin.html',
  'css/styles.css',
  'js/api.js',
  'js/config.js',
  'js/pos.js',
  'js/admin.js',
  'manifest.json',
  'icon-192.png',
  'icon-512.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NOMBRE).then((cache) => cache.addAll(ARCHIVOS_SHELL))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((nombres) =>
      Promise.all(nombres.filter((n) => n !== CACHE_NOMBRE).map((n) => caches.delete(n)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Las llamadas a la API NUNCA se sirven desde cache: siempre van a la red
  // (OfflineDB ya se encarga de la logica offline de ventas en pos.js).
  if (url.pathname.startsWith('/ventas') || url.pathname.startsWith('/productos') ||
      url.pathname.includes(':8000') || url.hostname !== self.location.hostname) {
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cacheada) => {
      if (cacheada) return cacheada;
      return fetch(event.request).catch(() => cacheada);
    })
  );
});
