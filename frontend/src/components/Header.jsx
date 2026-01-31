import { useState, useRef, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../context/AuthContext';
import { getBusinessSettings } from '../services/api';
import './Header.css';

function Header() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [showUserMenu, setShowUserMenu] = useState(false);
  const menuRef = useRef(null);

  const { data: settings } = useQuery({
    queryKey: ['business-settings'],
    queryFn: async () => {
      const response = await getBusinessSettings();
      return response.data;
    },
    staleTime: 10 * 60 * 1000, // Cache for 10 minutes
  });

  // Use user's company name if available, fallback to settings
  const businessName = user?.company_name || settings?.business_name || 'AI Trades Receptionist';
  const logoUrl = user?.logo_url || settings?.logo_url;

  const isActive = (path) => {
    return location.pathname === path || location.pathname.startsWith(path + '/');
  };

  const handleLogout = async () => {
    await logout();
    navigate('/');
    setShowUserMenu(false);
  };

  // Close menu when clicking/touching outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setShowUserMenu(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('touchstart', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('touchstart', handleClickOutside);
    };
  }, []);

  return (
    <header className="header">
      <div className="container">
        <div className="header-content">
          <Link to="/dashboard" className="logo">
            {logoUrl ? (
              <img src={logoUrl} alt={businessName} className="header-logo-img" />
            ) : (
              <i className="fas fa-bolt" style={{ color: '#fbbf24' }}></i>
            )}
            <span className="logo-text">{businessName}</span>
          </Link>
          <nav className="header-nav">
            <Link 
              to="/dashboard" 
              className={`nav-link ${isActive('/dashboard') ? 'active' : ''}`}
            >
              <i className="fas fa-home"></i>
              Dashboard
            </Link>
            <Link 
              to="/settings" 
              className={`nav-link ${isActive('/settings') ? 'active' : ''}`}
            >
              <i className="fas fa-cog"></i>
              Settings
            </Link>
            
            {/* User Menu */}
            <div className="user-menu-container" ref={menuRef}>
              <button 
                className="user-menu-trigger"
                onClick={() => setShowUserMenu(!showUserMenu)}
              >
                <div className="user-avatar">
                  {user?.owner_name?.charAt(0).toUpperCase() || 'U'}
                </div>
                <span className="user-name">{user?.owner_name || 'User'}</span>
                <i className={`fas fa-chevron-${showUserMenu ? 'up' : 'down'}`}></i>
              </button>
              
              {showUserMenu && (
                <div className="user-dropdown">
                  <div className="user-dropdown-header">
                    <div className="user-info">
                      <span className="user-full-name">{user?.owner_name}</span>
                      <span className="user-email">{user?.email}</span>
                    </div>
                  </div>
                  <div className="user-dropdown-divider"></div>
                  <Link 
                    to="/settings" 
                    className="user-dropdown-item"
                    onClick={() => setShowUserMenu(false)}
                  >
                    <i className="fas fa-user-cog"></i>
                    Account Settings
                  </Link>
                  <div className="user-dropdown-divider"></div>
                  <button className="user-dropdown-item logout" onClick={handleLogout}>
                    <i className="fas fa-sign-out-alt"></i>
                    Sign Out
                  </button>
                </div>
              )}
            </div>
          </nav>
        </div>
      </div>
    </header>
  );
}

export default Header;
