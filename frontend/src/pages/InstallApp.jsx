import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { isStandalone, getDeferredPrompt, clearDeferredPrompt } from '../components/PWAInstallPrompt';
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
  const [canInstall, setCanInstall] = useState(!!getDeferredPrompt());
  const [installed, setInstalled] = useState(isStandalone());
  const [activeTab, setActiveTab] = useState(isIOS() ? 'ios' : isAndroid() ? 'android' : 'ios');

  useEffect(() => {
    const handler = (e) => {
      e.preventDefault();
      setCanInstall(true);
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
    const prompt = getDeferredPrompt();
    if (!prompt) return;
    try {
      prompt.prompt();
      const { outcome } = await prompt.userChoice;
      if (outcome === 'accepted') setInstalled(true);
    } catch (err) {
      console.warn('Install error:', err);
    }
    clearDeferredPrompt();
    setCanInstall(false);
  };

  return (
    <div className="install-page">
      <div className="install-container">
        <Link to="/" className="install-back">
          <i className="fas fa-arrow-left"></i> Back
        </Link>

        <div className="install-hero">
          <div className="install-app-icon">
            <img src="/logo.png" alt="BookedForYou" width="72" height="72" />
          </div>
          <h1>Get the App</h1>
          <p className="install-subtitle">
            Install BookedForYou on your phone — no app store needed. It works just like a native app.
          </p>
        </div>

        {installed && (
          <div className="install-success-card">
            <i className="fas fa-check-circle"></i>
            <h2>Already Installed</h2>
            <p>BookedForYou is on your home screen. Open it from there anytime.</p>
          </div>
        )}

        {/* One-tap install for Android/Desktop */}
        {canInstall && !installed && (
          <div className="install-action-card">
            <button className="install-now-btn" onClick={handleInstall}>
              <i className="fas fa-download"></i>
              Install Now
            </button>
            <p className="install-note">Installs instantly, no app store needed</p>
          </div>
        )}

        {/* Platform tabs */}
        {!installed && (
          <div className="install-guides">
            <div className="install-tabs">
              <button
                className={`install-tab ${activeTab === 'ios' ? 'active' : ''}`}
                onClick={() => setActiveTab('ios')}
              >
                <i className="fab fa-apple"></i> iPhone / iPad
              </button>
              <button
                className={`install-tab ${activeTab === 'android' ? 'active' : ''}`}
                onClick={() => setActiveTab('android')}
              >
                <i className="fab fa-android"></i> Android
              </button>
              <button
                className={`install-tab ${activeTab === 'desktop' ? 'active' : ''}`}
                onClick={() => setActiveTab('desktop')}
              >
                <i className="fas fa-desktop"></i> Desktop
              </button>
            </div>

            {activeTab === 'ios' && (
              <div className="install-guide-card">
                {!isIOSSafari() && isIOS() && (
                  <div className="install-warning">
                    <i className="fas fa-exclamation-triangle"></i>
                    <span>Open this page in <strong>Safari</strong> to install. Copy the URL and paste it in Safari.</span>
                  </div>
                )}
                <div className="install-steps">
                  <div className="install-step">
                    <div className="step-number">1</div>
                    <div className="step-content">
                      <h3>Open bookedforyou.ie in Safari</h3>
                      <p>Make sure you're using Safari — other browsers on iPhone don't support app install.</p>
                    </div>
                  </div>
                  <div className="install-step">
                    <div className="step-number">2</div>
                    <div className="step-content">
                      <h3>Tap the Share button <i className="fas fa-arrow-up-from-bracket" style={{ color: '#0ea5e9' }}></i></h3>
                      <p>It's the square with an arrow at the bottom of Safari (or top on iPad).</p>
                    </div>
                  </div>
                  <div className="install-step">
                    <div className="step-number">3</div>
                    <div className="step-content">
                      <h3>Scroll down and tap "Add to Home Screen"</h3>
                      <p>You may need to scroll down in the share menu to find it. Look for the <i className="fas fa-plus-square" style={{ color: '#64748b' }}></i> icon.</p>
                    </div>
                  </div>
                  <div className="install-step">
                    <div className="step-number">4</div>
                    <div className="step-content">
                      <h3>Tap "Add" in the top right</h3>
                      <p>Done — BookedForYou will appear on your home screen like any other app.</p>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'android' && (
              <div className="install-guide-card">
                <div className="install-steps">
                  <div className="install-step">
                    <div className="step-number">1</div>
                    <div className="step-content">
                      <h3>Open bookedforyou.ie in Chrome</h3>
                      <p>Chrome works best. Samsung Internet and Edge also support this.</p>
                    </div>
                  </div>
                  <div className="install-step">
                    <div className="step-number">2</div>
                    <div className="step-content">
                      <h3>Tap the menu <i className="fas fa-ellipsis-vertical" style={{ color: '#64748b' }}></i></h3>
                      <p>Three dots in the top right corner of Chrome.</p>
                    </div>
                  </div>
                  <div className="install-step">
                    <div className="step-number">3</div>
                    <div className="step-content">
                      <h3>Tap "Install app"</h3>
                      <p>On older Chrome versions it may say "Add to Home screen" instead.</p>
                    </div>
                  </div>
                  <div className="install-step">
                    <div className="step-number">4</div>
                    <div className="step-content">
                      <h3>Tap "Install" to confirm</h3>
                      <p>The app will download and appear on your home screen in seconds.</p>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'desktop' && (
              <div className="install-guide-card">
                <div className="install-steps">
                  <div className="install-step">
                    <div className="step-number">1</div>
                    <div className="step-content">
                      <h3>Open bookedforyou.ie in Chrome or Edge</h3>
                      <p>Firefox and Safari don't support desktop PWA install yet.</p>
                    </div>
                  </div>
                  <div className="install-step">
                    <div className="step-number">2</div>
                    <div className="step-content">
                      <h3>Click the install icon <i className="fas fa-download" style={{ color: '#64748b' }}></i> in the address bar</h3>
                      <p>It's on the right side of the URL bar. You may also see a popup asking to install.</p>
                    </div>
                  </div>
                  <div className="install-step">
                    <div className="step-number">3</div>
                    <div className="step-content">
                      <h3>Click "Install"</h3>
                      <p>The app opens in its own window and appears in your dock or taskbar.</p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        <div className="install-benefits">
          <h2>Why install?</h2>
          <div className="benefits-grid">
            <div className="benefit-item">
              <i className="fas fa-bolt"></i>
              <h3>Instant Access</h3>
              <p>Open from your home screen</p>
            </div>
            <div className="benefit-item">
              <i className="fas fa-expand"></i>
              <h3>Full Screen</h3>
              <p>No browser bars, feels native</p>
            </div>
            <div className="benefit-item">
              <i className="fas fa-camera"></i>
              <h3>Camera</h3>
              <p>Take job photos on site</p>
            </div>
            <div className="benefit-item">
              <i className="fas fa-wifi"></i>
              <h3>Offline</h3>
              <p>Basic pages load without internet</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default InstallApp;
