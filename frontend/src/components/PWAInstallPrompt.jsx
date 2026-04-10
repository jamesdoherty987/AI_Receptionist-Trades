import { useState, useEffect } from 'react';
import './PWAInstallPrompt.css';

// Detect if running as installed PWA
export function isStandalone() {
  return window.matchMedia('(display-mode: standalone)').matches ||
    window.navigator.standalone === true;
}

// Detect iOS Safari (not Chrome/Firefox on iOS — they don't support PWA install)
function isIOSSafari() {
  const ua = navigator.userAgent;
  const isIOS = /iPad|iPhone|iPod/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  const isSafari = /Safari/.test(ua) && !/CriOS|FxiOS|OPiOS|EdgiOS/.test(ua);
  return isIOS && isSafari;
}

function PWAInstallPrompt() {
  const [deferredPrompt, setDeferredPrompt] = useState(null);
  const [showPrompt, setShowPrompt] = useState(false);
  const [showIOSGuide, setShowIOSGuide] = useState(false);

  useEffect(() => {
    // Don't show if already installed
    if (isStandalone()) return;

    // Check if user dismissed recently (24h cooldown)
    const dismissed = localStorage.getItem('pwa-install-dismissed');
    if (dismissed && Date.now() - parseInt(dismissed) < 24 * 60 * 60 * 1000) return;

    // Android/Desktop — capture the beforeinstallprompt event
    const handler = (e) => {
      e.preventDefault();
      setDeferredPrompt(e);
      // Show after a short delay so it doesn't feel aggressive
      setTimeout(() => setShowPrompt(true), 3000);
    };
    window.addEventListener('beforeinstallprompt', handler);

    // iOS Safari — show manual instructions after delay
    if (isIOSSafari()) {
      const timer = setTimeout(() => setShowIOSGuide(true), 5000);
      return () => {
        clearTimeout(timer);
        window.removeEventListener('beforeinstallprompt', handler);
      };
    }

    return () => window.removeEventListener('beforeinstallprompt', handler);
  }, []);

  const handleInstall = async () => {
    if (!deferredPrompt) return;
    try {
      deferredPrompt.prompt();
      const { outcome } = await deferredPrompt.userChoice;
      if (outcome === 'accepted') {
        setShowPrompt(false);
      }
    } catch (err) {
      console.warn('Install prompt error:', err);
    }
    setDeferredPrompt(null);
  };

  const handleDismiss = () => {
    setShowPrompt(false);
    setShowIOSGuide(false);
    localStorage.setItem('pwa-install-dismissed', Date.now().toString());
  };

  // Android/Desktop install banner
  if (showPrompt && deferredPrompt) {
    return (
      <div className="pwa-install-banner" role="alert">
        <div className="pwa-install-content">
          <div className="pwa-install-icon">
            <img src="/logo.png" alt="" width="40" height="40" />
          </div>
          <div className="pwa-install-text">
            <span className="pwa-install-title">Install BookedForYou</span>
            <span className="pwa-install-desc">Quick access from your home screen</span>
          </div>
          <div className="pwa-install-actions">
            <button className="pwa-install-btn" onClick={handleInstall}>
              Install
            </button>
            <button className="pwa-dismiss-btn" onClick={handleDismiss} aria-label="Dismiss">
              <i className="fas fa-times"></i>
            </button>
          </div>
        </div>
      </div>
    );
  }

  // iOS Safari install guide
  if (showIOSGuide) {
    return (
      <div className="pwa-install-banner pwa-ios-banner" role="alert">
        <div className="pwa-install-content">
          <div className="pwa-install-icon">
            <img src="/logo.png" alt="" width="40" height="40" />
          </div>
          <div className="pwa-install-text">
            <span className="pwa-install-title">Install BookedForYou</span>
            <span className="pwa-install-desc">
              Tap <i className="fas fa-arrow-up-from-bracket" style={{ color: '#0ea5e9', margin: '0 2px' }}></i> below, then <strong>"Add to Home Screen"</strong>
            </span>
          </div>
          <button className="pwa-dismiss-btn" onClick={handleDismiss} aria-label="Dismiss">
            <i className="fas fa-times"></i>
          </button>
        </div>
      </div>
    );
  }

  return null;
}

export default PWAInstallPrompt;
