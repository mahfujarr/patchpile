// Service Worker for Patchpile Web Push Notifications
const CACHE_NAME = 'patchpile-sw-v2';

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

  const payloadData = data.data || {};
  const validApps = (payloadData.apps || []).filter((a) => Boolean(a.dl_url));

  let actions = [];
  if (validApps.length === 2) {
    const cleanName = (n) =>
      ('⬇️ ' + n.replace(/\s+(Experimental|Stable)/i, '').trim()).slice(0, 24);
    actions = [
      { action: 'download_app_0', title: cleanName(validApps[0].name) },
      { action: 'download_app_1', title: cleanName(validApps[1].name) },
    ];
  } else if (validApps.length === 1 || payloadData.direct_url) {
    actions = [
      { action: 'download_direct', title: '⬇️ Download APK' },
      { action: 'open_site', title: '🌐 View Site' },
    ];
  } else {
    actions = [
      { action: 'open', title: 'Open Patchpile' },
      { action: 'dismiss', title: 'Dismiss' },
    ];
  }

  const notificationOptions = {
    body: data.body,
    icon: data.icon || './assets/favicon.svg',
    badge: data.badge || './assets/favicon.svg',
    tag: data.tag || 'patchpile-release',
    renotify: true,
    vibrate: [150, 80, 150],
    data: data.data || { url: self.location.origin },
    actions: actions,
  };

  event.waitUntil(
    self.registration.showNotification(data.title, notificationOptions)
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const action = event.action;
  if (action === 'dismiss') return;

  const notifData = event.notification.data || {};
  const validApps = (notifData.apps || []).filter((a) => Boolean(a.dl_url));

  // Action: Direct 1-tap download single app
  if (action === 'download_direct') {
    const dl =
      notifData.direct_url ||
      (validApps[0] && validApps[0].dl_url) ||
      (notifData.download_urls && notifData.download_urls[0]);
    if (dl && clients.openWindow) {
      event.waitUntil(clients.openWindow(dl));
      return;
    }
  }

  // Action: Download app 0 in multi-app release
  if (action === 'download_app_0') {
    const dl = validApps[0] && validApps[0].dl_url;
    if (dl && clients.openWindow) {
      event.waitUntil(clients.openWindow(dl));
      return;
    }
  }

  // Action: Download app 1 in multi-app release
  if (action === 'download_app_1') {
    const dl = validApps[1] && validApps[1].dl_url;
    if (dl && clients.openWindow) {
      event.waitUntil(clients.openWindow(dl));
      return;
    }
  }

  // Action: View website only (no auto-download)
  if (action === 'open_site') {
    const siteUrl = notifData.site_url || self.location.origin;
    event.waitUntil(
      clients
        .matchAll({ type: 'window', includeUncontrolled: true })
        .then((clientList) => {
          for (const client of clientList) {
            if ('focus' in client && client.url.includes(self.location.origin)) {
              client.navigate(siteUrl);
              return client.focus();
            }
          }
          if (clients.openWindow) {
            return clients.openWindow(siteUrl);
          }
        })
    );
    return;
  }

  // Default click on notification body:
  const targetUrl =
    notifData.url ||
    notifData.direct_url ||
    notifData.site_url ||
    self.location.origin;

  // Direct APK downloads must always use clients.openWindow (client.navigate rejects cross-origin)
  if (targetUrl.endsWith('.apk') || targetUrl.includes('/releases/download/')) {
    if (clients.openWindow) {
      event.waitUntil(clients.openWindow(targetUrl));
      return;
    }
  }

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

