import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { isStandalone } from '../components/PWAInstallPrompt';
import './InstallApp.css';

function isIOSSafari() {
  const ua = navigator.userAgent;
  const isIOS = /iPad|iPhone|iPod/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  const isSafari = /Safari/.test(ua) && !/CriOS|FxiOS|OPiOS|EdgiOS/.test(ua);
  return isIOS && isSafari;
}

function isIOS() {
  const ua = navigator.userAgent;
  return /iPad|iPhone|iPod/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
}

function isAndroid() {
  return /Android/.test(navigator.userAgent);
}

function InstallApp() {
  const [deferredPrompt, setDeferredPrompt] = useState(null);
  const [installed, setInstalled] = useState(isStandalone());

  useEffect(() => {
    const handler = (e) => {
      e.preventDefault();
      setDeferredPrompt(e);
    };
    window.addEventListener('beforeinstallprompt', handler);

    const installedHandler = () => setInstalled(true);
    window.addEventListener('appinstalled', installedHandler);

    return () => {
      window.removeEventListener('beforeinstallprompt', handler);
      window.removeEventListener('appinstalled', installedHandler);
    };
  }, []);

  const handleInstall = async () => {
    if (!deferredPrompt) return;
    try {
      deferredPrompt.prompt();
      const { outcome } = await deferredPrompt.userChoice;
      if (outcome === 'accepted') setInstalled(true);
    } catch (err) {
      console.warn('Install error:', err);
    }
    setDeferredPrompt(null);
  };

  const platform = isIOS() ? 'ios' : isAndroid() ? 'android' : 'desktop';

  return (
    <div className="install-page">
      <div className="install-container">
        <Link to="/login" className="install-back">
          <i className="fas fa-arrow-left"></i> Back
        </Link>

        <div className="install-hero">
          <div className="install-app-icon">
            <img src="/logo.png" alt="BookedForYou" width="80" height="80" />
          </div>
          <h1>Install BookedForYou</h1>
          <p className="install-subtitle">
            Get the app on your phone for quick access to your dashboard, jobs, and notifications.
          </p>
        </div>

        {installed ? (
          <div className="install-success-card">
            <i className="fas fa-check-circle"></i>
            <h2>App Installed</h2>
            <p>BookedForYou is on your home screen. You can open it from there anytime.</p>
          </div>
        ) : (
          <>
            {/* Direct install button for Android/Desktop */}
            {deferredPrompt && (
              <div className="install-action-card">
                <button className="install-now-btn" onClick={handleInstall}>
                  <i className="fas fa-download"></i>
                  Install App Now
                </button>
                <p className="install-note">No app store needed. Installs instantly.</p>
              </div>
            )}

            {/* iOS Safari Guide */}
            {platform === 'ios' && (
              <div className="install-guide-card">
                <h2><i className="fab fa-apple"></i> Install on iPhone / iPad</h2>
                {!isIOSSafari() && (
                  <div className="install-warning">
                    <i className="fas fa-exclamation-triangle"></i>
                    <span>You need to open this page in <strong>Safari</strong> to install the app. Copy this URL and paste it in Safari.</span>
                  </div>
                )}
                <div className="install-steps">
                  <div className="install-step">
                    <div className="step-number">1</div>
                    <div className="step-content">
                      <h3>Tap the Share button</h3>
                      <p>
                        Tap <i className="fas fa-arrow-up-from-bracket" style={{ color: '#0ea5e9' }}></i> at the bottom of Safari
                      </p>
                    </div>
                  </div>
                  <div className="install-step">
                    <div className="step-number">2</div>
                    <div className="step-content">
                      <h3>Scroll down and tap "Add to Home Screen"</h3>
                      <p>
                        Look for <i className="fas fa-plus-square" style={{ color: '#64748b' }}></i> Add to Home Screen in the share menu
                      </p>
                    </div>
                  </div>
                  <div className="install-step">
                    <div className="step-number">3</div>
                    <div className="step-content">
                      <h3>Tap "Add"</h3>
                      <p>Confirm the name and tap Add in the top right corner</p>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Android Guide (fallback if beforeinstallprompt didn't fire) */}
            {platform === 'android' && !deferredPrompt && (
              <div className="install-guide-card">
                <h2><i className="fab fa-android"></i> Install on Android</h2>
                <div className="install-steps">
                  <div className="install-step">
                    <div className="step-number">1</div>
                    <div className="step-content">
                      <h3>Tap the menu</h3>
                      <p>Tap <i className="fas fa-ellipsis-vertical"></i> in the top right of Chrome</p>
                    </div>
                  </div>
                  <div className="install-step">
                    <div className="step-number">2</div>
                    <div className="step-content">
                      <h3>Tap "Install app" or "Add to Home screen"</h3>
                      <p>It may say either depending on your browser version</p>
                    </div>
                  </div>
                  <div className="install-step">
                    <div className="step-number">3</div>
                    <div className="step-content">
                      <h3>Tap "Install"</h3>
                      <p>The app will appear on your home screen</p>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Desktop Guide */}
            {platform === 'desktop' && !deferredPrompt && (
              <div className="install-guide-card">
                <h2><i className="fas fa-desktop"></i> Install on Desktop</h2>
                <div className="install-steps">
                  <div className="install-step">
                    <div className="step-number">1</div>
                    <div className="step-content">
                      <h3>Look for the install icon</h3>
                      <p>In Chrome, click the <i className="fas fa-download"></i> icon in the address bar (right side)</p>
                    </div>
                  </div>
                  <div className="install-step">
                    <div className="step-number">2</div>
                    <div className="step-content">
                      <h3>Click "Install"</h3>
                      <p>The app will open in its own window and appear in your dock/taskbar</p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </>
        )}

        <div className="install-benefits">
          <h2>Why install?</h2>
          <div className="benefits-grid">
            <div className="benefit-item">
              <i className="fas fa-bolt"></i>
              <h3>Instant Access</h3>
              <p>Open straight from your home screen, no browser needed</p>
            </div>
            <div className="benefit-item">
              <i className="fas fa-expand"></i>
              <h3>Full Screen</h3>
              <p>Runs like a native app with no browser bars</p>
            </div>
            <div className="benefit-item">
              <i className="fas fa-camera"></i>
              <h3>Camera Access</h3>
              <p>Take job photos directly from the worker portal</p>
            </div>
            <div className="benefit-item">
              <i className="fas fa-wifi"></i>
              <h3>Works Offline</h3>
              <p>Basic pages load even without internet</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default InstallApp;
