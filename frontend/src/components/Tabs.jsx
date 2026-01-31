import { useState, useEffect } from 'react';
import './Tabs.css';

function Tabs({ tabs, defaultTab = 0 }) {
  const [activeTab, setActiveTab] = useState(defaultTab);
  const [menuOpen, setMenuOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth <= 768);
    };
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  const handleTabSelect = (index) => {
    setActiveTab(index);
    setMenuOpen(false);
  };

  return (
    <div className="tabs-container">
      {isMobile ? (
        <>
          <div className="mobile-tabs-header">
            <span className="current-tab-label">
              {tabs[activeTab]?.icon && <i className={tabs[activeTab].icon}></i>}
              {tabs[activeTab]?.label}
            </span>
            <button 
              className={`hamburger-btn ${menuOpen ? 'open' : ''}`}
              onClick={() => setMenuOpen(!menuOpen)}
              aria-label="Toggle menu"
            >
              <span className="hamburger-line"></span>
              <span className="hamburger-line"></span>
              <span className="hamburger-line"></span>
            </button>
          </div>
          <div className={`mobile-menu-overlay ${menuOpen ? 'open' : ''}`} onClick={() => setMenuOpen(false)}></div>
          <div className={`mobile-side-menu ${menuOpen ? 'open' : ''}`}>
            <div className="mobile-menu-header">
              <h3>Navigation</h3>
              <button className="close-menu-btn" onClick={() => setMenuOpen(false)}>
                <i className="fas fa-times"></i>
              </button>
            </div>
            <div className="mobile-menu-items">
              {tabs.map((tab, index) => (
                <button
                  key={index}
                  className={`mobile-menu-item ${activeTab === index ? 'active' : ''}`}
                  onClick={() => handleTabSelect(index)}
                >
                  {tab.icon && <i className={tab.icon}></i>}
                  <span>{tab.label}</span>
                </button>
              ))}
            </div>
          </div>
        </>
      ) : (
        <div className="tabs-header">
          {tabs.map((tab, index) => (
            <button
              key={index}
              className={`tab-button ${activeTab === index ? 'active' : ''}`}
              onClick={() => setActiveTab(index)}
            >
              {tab.icon && <i className={tab.icon}></i>}
              {tab.label}
            </button>
          ))}
        </div>
      )}
      <div className="tabs-content">
        {tabs[activeTab]?.content}
      </div>
    </div>
  );
}

export default Tabs;
