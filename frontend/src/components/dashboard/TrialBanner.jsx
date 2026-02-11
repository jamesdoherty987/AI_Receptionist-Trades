import { Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import './TrialBanner.css';

function TrialBanner() {
  const { subscription, getTrialDaysRemaining, getSubscriptionTier } = useAuth();
  
  if (!subscription) return null;
  
  const tier = getSubscriptionTier();
  const daysRemaining = getTrialDaysRemaining();
  const isActive = subscription.is_active;
  
  // Pro users never see trial banners - they have a paid subscription
  if (tier === 'pro') {
    return null;
  }
  
  // No subscription at all
  if (!isActive && (tier === 'none' || !tier)) {
    return (
      <div className="trial-banner banner-expired">
        <div className="banner-left">
          <i className="fas fa-info-circle banner-icon"></i>
          <div className="banner-text">
            <strong>No active subscription</strong>
            <span className="banner-sub">Start a free trial or subscribe to unlock all features.</span>
          </div>
        </div>
        <Link to="/settings?tab=subscription" className="banner-btn">
          <i className="fas fa-rocket"></i> Get Started
        </Link>
      </div>
    );
  }
  
  // Expired trial / subscription
  if (!isActive && (tier === 'trial' || tier === 'expired')) {
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
  
  // Active trial
  if (tier === 'trial' && isActive) {
    const isUrgent = daysRemaining <= 3;
    return (
      <div className={`trial-banner ${isUrgent ? 'banner-urgent' : 'banner-trial'}`}>
        <div className="banner-left">
          <div className={`days-badge ${isUrgent ? 'days-urgent' : ''}`}>
            <span className="days-number">{daysRemaining}</span>
            <span className="days-label">{daysRemaining === 1 ? 'day' : 'days'}</span>
          </div>
          <div className="banner-text">
            <strong>{isUrgent ? 'Trial ending soon!' : 'Free trial active'}</strong>
            <span className="banner-sub">
              {isUrgent 
                ? 'Subscribe now to keep your data and features.' 
                : `You have ${daysRemaining} days left in your free trial.`
              }
            </span>
          </div>
        </div>
        <Link to="/settings?tab=subscription" className="banner-btn">
          <i className="fas fa-credit-card"></i> Subscribe - €99/mo
        </Link>
      </div>
    );
  }
  
  // Anything else - no banner needed
  return null;
}

export default TrialBanner;
