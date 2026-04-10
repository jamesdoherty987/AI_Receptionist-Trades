import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)

// Register service worker for PWA
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js')
      .then((registration) => {
        // Force an immediate update check on every page load
        registration.update();

        // Also check periodically
        setInterval(() => registration.update(), 60 * 60 * 1000);

        registration.addEventListener('updatefound', () => {
          const newWorker = registration.installing;
          if (newWorker) {
            newWorker.addEventListener('statechange', () => {
              if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                // New version available — activate it immediately
                newWorker.postMessage('skipWaiting');
              }
            });
          }
        });
      })
      .catch((err) => console.warn('SW registration failed:', err));

    // When a new SW takes control, reload to get fresh assets
    let refreshing = false;
    navigator.serviceWorker.addEventListener('controllerchange', () => {
      if (!refreshing) {
        refreshing = true;
        window.location.reload();
      }
    });
  });

  // Emergency: if ?clear-cache is in the URL, unregister SW and clear caches
  if (window.location.search.includes('clear-cache')) {
    navigator.serviceWorker.getRegistrations().then((registrations) => {
      registrations.forEach((r) => r.unregister());
    });
    caches.keys().then((names) => {
      names.forEach((name) => caches.delete(name));
    });
    // Remove the query param and reload
    const url = new URL(window.location.href);
    url.searchParams.delete('clear-cache');
    window.history.replaceState({}, '', url.pathname);
    console.log('[PWA] Cache cleared, service workers unregistered');
  }
}
