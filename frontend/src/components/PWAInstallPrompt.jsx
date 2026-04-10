// PWA utilities — no intrusive banner, just helpers

// Detect if running as installed PWA
export function isStandalone() {
  return window.matchMedia('(display-mode: standalone)').matches ||
    window.navigator.standalone === true;
}

// Silently capture the beforeinstallprompt event for use by the /install page
// This needs to be set up early so the event isn't missed
let deferredInstallPrompt = null;

if (typeof window !== 'undefined') {
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredInstallPrompt = e;
  });
}

export function getDeferredPrompt() {
  return deferredInstallPrompt;
}

export function clearDeferredPrompt() {
  deferredInstallPrompt = null;
}

// Default export — renders nothing (no banner)
export default function PWAInstallPrompt() {
  return null;
}
