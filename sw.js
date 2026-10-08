// Service Worker for Patchpile Web Push Notifications
const CACHE_NAME = 'patchpile-sw-v3';

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('push', (event) => {
  let data = {
    title: 'Patchpile: New Release Published',
    body: 'New patched APKs are ready for download!',
    icon: './assets/favicon.svg',
    badge: './assets/favicon.svg',
    tag: 'patchpile-release',
    data: {
      url: self.location.origin,
    },
  };

  if (event.data) {
    try {
      const json = event.data.json();
      data = Object.assign({}, data, json);
      if (json.data) {
        data.data = Object.assign({}, data.data, json.data);
      }
    } catch (e) {
      data.body = event.data.text() || data.body;
    }
  }

  const notificationOptions = {
    body: data.body,
    icon: data.icon || './assets/favicon.svg',
    badge: data.badge || './assets/favicon.svg',
    tag: data.tag || 'patchpile-release',
    renotify: true,
    vibrate: [150, 80, 150],
    data: data.data || { url: self.location.origin },
  };

  event.waitUntil(
    self.registration.showNotification(data.title, notificationOptions)
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  if (event.action === 'dismiss') return;

  const notifData = event.notification.data || {};
  const targetUrl = notifData.url || notifData.site_url || self.location.origin;

  event.waitUntil(
    clients
      .matchAll({ type: 'window', includeUncontrolled: true })
      .then((clientList) => {
        for (const client of clientList) {
          if ('focus' in client && client.url.includes(self.location.origin)) {
            client.navigate(targetUrl);
            return client.focus();
          }
        }
        if (clients.openWindow) {
          return clients.openWindow(targetUrl);
        }
      })
  );
});
