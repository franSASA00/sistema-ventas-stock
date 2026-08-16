// Cache basico de los archivos estaticos de la app (shell), para que cargue rapido
// y sea instalable como PWA. Los datos (ventas, productos, etc) NO se cachean aca:
// eso ya lo maneja OfflineDB (IndexedDB) en pos.js para el modo offline del POS.
//
// IMPORTANTE: subir este numero de version cada vez que se despliega un cambio de
// codigo importante, para forzar que los celulares con la app ya instalada descarguen
// la version nueva en vez de seguir usando una copia vieja guardada en cache.
const CACHE_NOMBRE = 'ventas-stock-shell-v2';
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

  // Las llamadas a la API NUNCA se sirven desde cache: siempre van a la red.
  if (url.pathname.startsWith('/ventas') || url.pathname.startsWith('/productos') ||
      url.pathname.includes(':8000') || url.hostname !== self.location.hostname) {
    return;
  }

  // HTML, JS y CSS: siempre intenta la RED primero (para tener el codigo mas nuevo),
  // y solo usa la copia en cache si no hay conexion. Asi los deploys nuevos se ven
  // enseguida, sin depender de que alguien suba el numero de version del cache.
  event.respondWith(
    fetch(event.request)
      .then((respuesta) => {
        const clonada = respuesta.clone();
        caches.open(CACHE_NOMBRE).then((cache) => cache.put(event.request, clonada));
        return respuesta;
      })
      .catch(() => caches.match(event.request))
  );
});
