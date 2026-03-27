import { useState, useEffect, useMemo } from 'react';
import './Tabs.css';

function Tabs({ tabs, defaultTab = 0, activeTab: controlledTab, onTabChange }) {
  const [internalTab, setInternalTab] = useState(defaultTab);
  const activeTab = controlledTab !== undefined ? controlledTab : internalTab;
  const setActiveTab = (idx) => {
    setInternalTab(idx);
    if (onTabChange) onTabChange(idx);
  };
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

  // Build grouped structure for rendering
  const groupedTabs = useMemo(() => {
    const groups = [];
    let currentGroup = null;
    tabs.forEach((tab, index) => {
      const group = tab.group || '';
      if (group !== currentGroup) {
        groups.push({ name: group, tabs: [] });
        currentGroup = group;
      }
      groups[groups.length - 1].tabs.push({ ...tab, index });
    });
    return groups;
  }, [tabs]);

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
              {groupedTabs.map((group) => (
                <div key={group.name} className="mobile-menu-group">
                  {group.name && <div className="mobile-group-label">{group.name}</div>}
                  {group.tabs.map((tab) => (
                    <button
                      key={tab.index}
                      className={`mobile-menu-item ${activeTab === tab.index ? 'active' : ''}`}
                      onClick={() => handleTabSelect(tab.index)}
                    >
                      {tab.icon && <i className={tab.icon}></i>}
                      <span>{tab.label}</span>
                    </button>
                  ))}
                </div>
              ))}
            </div>
          </div>
        </>
      ) : (
        <div className="tabs-header">
          {groupedTabs.map((group, gi) => (
            <div key={group.name} className="tab-group">
              {group.tabs.map((tab) => (
                <button
                  key={tab.index}
                  className={`tab-button ${activeTab === tab.index ? 'active' : ''}`}
                  onClick={() => setActiveTab(tab.index)}
                >
                  {tab.icon && <i className={tab.icon}></i>}
                  {tab.label}
                </button>
              ))}
              {gi < groupedTabs.length - 1 && <span className="tab-group-divider" />}
            </div>
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
