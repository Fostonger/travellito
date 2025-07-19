// Service Worker for Travellito Tour App
const CACHE_NAME = 'travellito-cache-v1';
const RUNTIME_CACHE = 'runtime-cache';

// Resources to cache initially
const PRECACHE_URLS = [
  '/',
  '/index.html',
  '/manifest.json'
];

// Install event - precache static resources
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(PRECACHE_URLS))
      .then(self.skipWaiting())
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
  const currentCaches = [CACHE_NAME, RUNTIME_CACHE];
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return cacheNames.filter(cacheName => !currentCaches.includes(cacheName));
    }).then(cachesToDelete => {
      return Promise.all(cachesToDelete.map(cacheToDelete => {
        return caches.delete(cacheToDelete);
      }));
    }).then(() => self.clients.claim())
  );
});

// Fetch event - network-first with cache fallback strategy
self.addEventListener('fetch', event => {
  // Skip non-GET requests
  if (event.request.method !== 'GET') return;
  
  // Skip cross-origin requests
  if (!event.request.url.startsWith(self.location.origin) && 
      !event.request.url.includes('api.trycloudflare.com')) {
    return;
  }

  // API calls strategy - network first with cache fallback
  if (event.request.url.includes('/api/') || event.request.url.includes('api.trycloudflare.com')) {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          // Clone the response before using it
          const responseToCache = response.clone();
          
          // Only cache successful responses
          if (response.status === 200) {
            caches.open(RUNTIME_CACHE).then(cache => {
              cache.put(event.request, responseToCache);
            });
          }
          
          return response;
        })
        .catch(() => {
          // If network fails, try the cache
          return caches.match(event.request);
        })
    );
    return;
  }
  
  // For image requests - cache first with network fallback
  if (event.request.destination === 'image') {
    event.respondWith(
      caches.match(event.request).then(cachedResponse => {
        // Use cached version if available
        if (cachedResponse) {
          return cachedResponse;
        }
        
        // Otherwise fetch from network and cache
        return fetch(event.request).then(response => {
          // Clone the response before using it
          const responseToCache = response.clone();
          
          // Only cache successful responses
          if (response.status === 200) {
            caches.open(CACHE_NAME).then(cache => {
              cache.put(event.request, responseToCache);
            });
          }
          
          return response;
        });
      })
    );
    return;
  }
  
  // For other assets - stale-while-revalidate strategy
  event.respondWith(
    caches.match(event.request).then(cachedResponse => {
      // Use cached version but also fetch an update
      const fetchPromise = fetch(event.request).then(response => {
        // Clone the response before using it
        const responseToCache = response.clone();
        
        // Only cache successful responses
        if (response.status === 200) {
          caches.open(CACHE_NAME).then(cache => {
            cache.put(event.request, responseToCache);
          });
        }
        
        return response;
      }).catch(() => {
        // If network fails and we don't have a cached response, show fallback
        if (!cachedResponse) {
          // For HTML pages, we could return a fallback offline page
          if (event.request.destination === 'document') {
            return caches.match('/index.html');
          }
        }
      });
      
      return cachedResponse || fetchPromise;
    })
  );
}); 