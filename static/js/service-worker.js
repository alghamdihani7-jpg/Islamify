// Service Worker for Prayer Notifications
const CACHE_NAME = 'islamify-v1';
const ASSETS_TO_CACHE = [
  '/',
  '/static/css/style.css',
  '/static/js/main.js'
];

// Install event
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(ASSETS_TO_CACHE).catch(() => {
        // Fail silently if cache fails
      });
    })
  );
  self.skipWaiting();
});

// Activate event
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  self.clients.claim();
});

// Handle push notifications
self.addEventListener('push', event => {
  if (!event.data) {
    return;
  }

  const data = event.data.json();
  const options = {
    body: data.body || 'Prayer time notification',
    icon: '/static/img/icon-192x192.png',
    badge: '/static/img/badge-72x72.png',
    tag: data.tag || 'prayer-notification',
    requireInteraction: true,
    actions: [
      {
        action: 'mark-done',
        title: 'تم صلاتها'
      },
      {
        action: 'snooze',
        title: 'اذكرني لاحقاً'
      }
    ],
    data: {
      prayer: data.prayer,
      timestamp: new Date().getTime()
    }
  };

  event.waitUntil(
    self.registration.showNotification(data.title || 'وقت الصلاة', options)
  );
});

// Handle notification clicks
self.addEventListener('notificationclick', event => {
  event.notification.close();

  if (event.action === 'mark-done') {
    // Mark prayer as done
    event.waitUntil(
      clients.matchAll({ type: 'window' }).then(clientList => {
        clientList.forEach(client => {
          client.postMessage({
            type: 'PRAYER_MARKED_DONE',
            prayer: event.notification.data.prayer
          });
        });
      })
    );
  } else if (event.action === 'snooze') {
    // Snooze notification
    event.waitUntil(
      clients.matchAll({ type: 'window' }).then(clientList => {
        clientList.forEach(client => {
          client.postMessage({
            type: 'PRAYER_SNOOZED',
            prayer: event.notification.data.prayer
          });
        });
      })
    );
  } else {
    // Open prayer times page
    event.waitUntil(
      clients.matchAll({ type: 'window' }).then(clientList => {
        for (let client of clientList) {
          if (client.url === '/' && 'focus' in client) {
            return client.focus();
          }
        }
        if (clients.openWindow) {
          return clients.openWindow('/prayer-times');
        }
      })
    );
  }
});
