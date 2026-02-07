import { Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import './TrialBanner.css';

function TrialBanner() {
  const { subscription, getTrialDaysRemaining, getSubscriptionTier } = useAuth();
  
  if (!subscription) return null;
  
  const tier = getSubscriptionTier();
  const daysRemaining = getTrialDaysRemaining();
  const isActive = subscription.is_active;
  
  // Show expired banner for expired/cancelled subscriptions
  if (!isActive && (tier === 'trial' || tier === 'expired')) {
    return (
      <div className="trial-banner expired">
        <div className="trial-banner-content">
          <div className="trial-info">
            <i className="fas fa-exclamation-triangle"></i>
            <span>
              <strong>Your trial has expired.</strong> Subscribe to unlock all features and continue using BookedForYou.
            </span>
          </div>
          <Link to="/settings" className="btn btn-primary btn-small">
            <i className="fas fa-credit-card"></i>
            Subscribe Now - €59/month
          </Link>
        </div>
      </div>
    );
  }
  
  // Show for active trial users only
  if (tier !== 'trial' || !isActive) return null;
  
  const isUrgent = daysRemaining <= 3;
  
  return (
    <div className={`trial-banner ${isUrgent ? 'urgent' : ''}`}>
      <div className="trial-banner-content">
        <div className="trial-info">
          <i className={`fas ${isUrgent ? 'fa-exclamation-circle' : 'fa-clock'}`}></i>
          <span>
            {isUrgent ? (
              <strong>Only {daysRemaining} day{daysRemaining !== 1 ? 's' : ''} left in your trial!</strong>
            ) : (
              <>You have <strong>{daysRemaining} days</strong> left in your free trial</>
            )}
          </span>
        </div>
        <Link to="/settings" className="btn btn-primary btn-small">
          <i className="fas fa-credit-card"></i>
          Subscribe Now - €59/month
        </Link>
      </div>
    </div>
  );
}

export default TrialBanner;
