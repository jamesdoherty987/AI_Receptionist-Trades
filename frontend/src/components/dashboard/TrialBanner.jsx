import { Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import './TrialBanner.css';

function TrialBanner() {
  const { subscription, getTrialDaysRemaining, getSubscriptionTier } = useAuth();
  
  // No subscription data yet - don't show anything
  if (!subscription) return null;
  
  const tier = getSubscriptionTier();
  const daysRemaining = getTrialDaysRemaining();
  const isActive = subscription.is_active === true; // Explicit check for true
  
  // Active pro users - no banner needed
  if (tier === 'pro' && isActive) {
    return null;
  }
  
  // Active trial - show trial banner with days remaining
  if (tier === 'trial' && isActive) {
    return (
      <div className="trial-banner banner-trial">
        <div className="banner-left">
          <div className="days-badge">
            <span className="days-number">{daysRemaining}</span>
            <span className="days-label">{daysRemaining === 1 ? 'day' : 'days'}</span>
          </div>
          <div className="banner-text">
            <strong>Free trial active</strong>
            <span className="banner-sub">
              {`You have ${daysRemaining} day${daysRemaining !== 1 ? 's' : ''} left in your free trial.`}
            </span>
          </div>
        </div>
        <Link to="/settings?tab=subscription" className="banner-btn">
          <i className="fas fa-credit-card"></i> Subscribe - €99/mo
        </Link>
      </div>
    );
  }
  
  // No subscription / tier is 'none' - don't show banner (users know they don't have a subscription)
  if (tier === 'none' || !tier) {
    return null;
  }
  
  // Any inactive subscription (expired trial, cancelled pro, etc) - show expired banner
  if (!isActive) {
    return (
      <div className="trial-banner banner-expired">
        <div className="banner-left">
          <i className="fas fa-exclamation-triangle banner-icon"></i>
          <div className="banner-text">
            <strong>Your subscription has expired</strong>
            <span className="banner-sub">Subscribe to continue using BookedForYou.</span>
          </div>
        </div>
        <Link to="/settings?tab=subscription" className="banner-btn">
          <i className="fas fa-credit-card"></i> Subscribe Now
        </Link>
      </div>
    );
  }
  
  // Fallback - no banner
  return null;
}

export default TrialBanner;
