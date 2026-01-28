import { Link, useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getBusinessSettings } from '../services/api';
import './Header.css';

function Header() {
  const location = useLocation();

  const { data: settings } = useQuery({
    queryKey: ['business-settings'],
    queryFn: async () => {
      const response = await getBusinessSettings();
      return response.data;
    },
    staleTime: 10 * 60 * 1000, // Cache for 10 minutes
  });

  const businessName = settings?.business_name || 'AI Trades Receptionist';
  const logoUrl = settings?.logo_url;

  const isActive = (path) => {
    return location.pathname === path;
  };

  return (
    <header className="header">
      <div className="container">
        <div className="header-content">
          <Link to="/" className="logo">
            {logoUrl ? (
              <img src={logoUrl} alt={businessName} className="header-logo-img" />
            ) : (
              <i className="fas fa-tools"></i>
            )}
            <span className="logo-text">{businessName}</span>
          </Link>
          <nav className="header-nav">
            <Link 
              to="/" 
              className={`nav-link ${isActive('/') ? 'active' : ''}`}
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
          </nav>
        </div>
      </div>
    </header>
  );
}

export default Header;
