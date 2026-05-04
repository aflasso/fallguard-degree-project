importScripts("https://www.gstatic.com/firebasejs/10.12.2/firebase-app-compat.js");
importScripts("https://www.gstatic.com/firebasejs/10.12.2/firebase-messaging-compat.js");

firebase.initializeApp({
  apiKey: "AIzaSyBno2GSk4ZAb88KzcFAe9cpRJbK7lt9zdM",
  authDomain: "fallguard-8e840.firebaseapp.com",
  projectId: "fallguard-8e840",
  storageBucket: "fallguard-8e840.firebasestorage.app",
  messagingSenderId: "279122252609",
  appId: "1:279122252609:web:ca386b04a64cd24c1747c0",
  measurementId: "G-JKTXJXYRY7",
});

firebase.messaging();

self.addEventListener('push', (event) => {
  const payload = event.data?.json() ?? {};
  const data = payload.data ?? {};

  // Notificar a todos los tabs abiertos vía BroadcastChannel
  new BroadcastChannel('fcm_fallguard').postMessage(data);

  // Mostrar notificación del sistema solo si no hay tab enfocado
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      const hasFocused = clients.some((c) => c.focused);
      if (!hasFocused) {
        return self.registration.showNotification(
          data.title ?? 'FallGuard',
          {
            body: data.body ?? 'Se detectó una caída en tu hogar',
            icon: '/icons/Icon-192.png',
            data: data,
          }
        );
      }
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(
    self.clients.matchAll({ type: 'window' }).then((clients) => {
      if (clients.length > 0) return clients[0].focus();
      return self.clients.openWindow('/');
    })
  );
});
