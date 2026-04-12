import { Navigate } from 'react-router-dom';

/**
 * Legacy SettingsMenu page — redirects to Dashboard Services tab.
 * Services are now managed from the Dashboard → Services tab.
 */
function SettingsMenu() {
  return <Navigate to="/dashboard?tab=services" replace />;
}

export default SettingsMenu;
