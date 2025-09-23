const CACHE_NAME = "family-food-cache-v3";
const urlsToCache = [
  "/welcome",
  "/static/icon-192.png",
  "/static/icon-512.png",
  "/static/manifest.json"
];

self.addEventListener("install", function (event) {
  self.skipWaiting(); // άμεση ενεργοποίηση νέου service worker
  event.waitUntil(
    caches.open(CACHE_NAME).then(function (cache) {
      return cache.addAll(urlsToCache);
    })
  );
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches.keys().then(function (cacheNames) {
      return Promise.all(
        cacheNames.map(function (cacheName) {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName); // καθαρισμός παλιών caches
          }
        })
      );
    })
  );
});

self.addEventListener("fetch", function (event) {
  // 🔎 DEBUG LOG
  console.log("[SW DEBUG] Fetch:", event.request.url, "Mode:", event.request.mode);

  event.respondWith(
    caches.match(event.request).then(function (response) {
      if (response) {
        console.log("[SW DEBUG] Served from cache:", event.request.url);
        return response;
      }
      console.log("[SW DEBUG] Going to network:", event.request.url);
      return fetch(event.request);
    })
  );
});
