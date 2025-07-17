
const CACHE_NAME = 'family-food-cache-v1';
const urlsToCache = [
  '/',
  '/welcome',
  '/menu',
  '/profile',
  '/history',
  '/favorites',
  '/static/icon-192.png',
  '/static/icon-512.png',
  '/static/manifest.json'
];

self.addEventListener('install', function(event) {
  event.waitUntil(
    caches.open(CACHE_NAME).then(function(cache) {
      return cache.addAll(urlsToCache);
    })
  );
});

self.addEventListener('fetch', function(event) {
  event.respondWith(
    caches.match(event.request).then(function(response) {
      return response || fetch(event.request);
    })
  );
});
