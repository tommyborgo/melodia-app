// Service Worker di Melodia Premium — permette all'app di aprirsi e funzionare anche
// completamente offline (senza rete), non solo di riprodurre le canzoni già salvate.
const SHELL_CACHE = 'melodia-shell-v2';
const SHELL_URLS = ['/', '/spotify_moto.html', '/manifest.json'];

self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(SHELL_CACHE).then((cache) => cache.addAll(SHELL_URLS).catch(() => {}))
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(names.filter((n) => n !== SHELL_CACHE && !n.startsWith('melodia-offline-audio')).map((n) => caches.delete(n)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);
  const isShellRequest = url.pathname === '/' || url.pathname === '/spotify_moto.html' || url.pathname === '/manifest.json';

  if (isShellRequest) {
    // Pagina principale dell'app: prova prima la rete (per avere sempre l'ultima versione),
    // e se non c'è rete usa la copia salvata — così l'app si apre comunque anche offline.
    event.respondWith(
      fetch(req)
        .then((res) => {
          const clone = res.clone();
          caches.open(SHELL_CACHE).then((cache) => cache.put(req, clone));
          return res;
        })
        .catch(() => caches.match(req).then((cached) => cached || caches.match('/spotify_moto.html')))
    );
    return;
  }

  // Tutto il resto (canzoni, ricerche, ecc.) continua a funzionare come già gestito
  // dall'app stessa (che ha già la sua cache dedicata per l'audio offline) — il service
  // worker non si intromette qui, lascia fare al codice dell'app.
});