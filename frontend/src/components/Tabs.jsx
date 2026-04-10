import { useState, useEffect, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import './Tabs.css';

function Tabs({ tabs, defaultTab = 0, activeTab: controlledTab, onTabChange }) {
  const [internalTab, setInternalTab] = useState(defaultTab);
  const activeTab = controlledTab !== undefined ? controlledTab : internalTab;
  const navigate = useNavigate();
  const setActiveTab = useCallback((idx) => {
    setInternalTab(idx);
    if (onTabChange) onTabChange(idx);
  }, [onTabChange]);
  const [menuOpen, setMenuOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try { return localStorage.getItem('sidebar_collapsed') === 'true'; } catch { return false; }
  });

  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth <= 768);
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  const toggleSidebar = () => {
    const next = !sidebarCollapsed;
    setSidebarCollapsed(next);
    try { localStorage.setItem('sidebar_collapsed', String(next)); } catch {}
  };

  const handleTabSelect = (index) => {
    setActiveTab(index);
    setMenuOpen(false);
  };

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
              {tabs[activeTab]?.badge > 0 && (
                <span className="tab-badge mobile">{tabs[activeTab].badge > 9 ? '9+' : tabs[activeTab].badge}</span>
              )}
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
                      {tab.badge > 0 && (
                        <span className="tab-badge mobile">{tab.badge > 9 ? '9+' : tab.badge}</span>
                      )}
                    </button>
                  ))}
                </div>
              ))}
              <div className="mobile-menu-group">
                <div className="mobile-group-label">Account</div>
                <button
                  className="mobile-menu-item"
                  onClick={() => { setMenuOpen(false); navigate('/settings'); }}
                >
                  <i className="fas fa-cog"></i>
                  <span>Settings</span>
                </button>
              </div>
            </div>
          </div>
          <div className="tabs-content">
            {tabs[activeTab]?.content}
          </div>
        </>
      ) : (
        <div className={`sidebar-layout ${sidebarCollapsed ? 'collapsed' : ''}`}>
          {/* Sidebar */}
          <nav className="sidebar-nav" role="navigation" aria-label="Dashboard navigation">
            <div className="sidebar-toggle" onClick={toggleSidebar} title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}>
              <i className={`fas fa-chevron-${sidebarCollapsed ? 'right' : 'left'}`}></i>
            </div>
            <div className="sidebar-items">
              {groupedTabs.map((group, gi) => (
                <div key={group.name} className="sidebar-group">
                  {group.name && !sidebarCollapsed && (
                    <div className="sidebar-group-label">{group.name}</div>
                  )}
                  {group.name && sidebarCollapsed && gi > 0 && (
                    <div className="sidebar-group-dot"></div>
                  )}
                  {group.tabs.map((tab) => (
                    <button
                      key={tab.index}
                      className={`sidebar-item ${activeTab === tab.index ? 'active' : ''}`}
                      onClick={() => setActiveTab(tab.index)}
                      title={sidebarCollapsed ? tab.label : undefined}
                    >
                      {tab.icon && <i className={tab.icon}></i>}
                      {!sidebarCollapsed && <span className="sidebar-item-label">{tab.label}</span>}
                      {tab.badge > 0 && (
                        <span className={`tab-badge ${sidebarCollapsed ? 'collapsed' : ''}`}>
                          {tab.badge > 9 ? '9+' : tab.badge}
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              ))}
            </div>
            <div className="sidebar-footer">
              <button
                className="sidebar-item sidebar-settings-link"
                onClick={() => navigate('/settings')}
                title={sidebarCollapsed ? 'Settings' : undefined}
              >
                <i className="fas fa-cog"></i>
                {!sidebarCollapsed && <span className="sidebar-item-label">Settings</span>}
              </button>
            </div>
          </nav>
          {/* Content */}
          <div className="tabs-content">
            {tabs[activeTab]?.content}
          </div>
        </div>
      )}
    </div>
  );
}

export default Tabs;
