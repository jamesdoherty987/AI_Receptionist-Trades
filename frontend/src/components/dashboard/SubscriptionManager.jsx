import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../../context/AuthContext';
import {
  getSubscriptionStatus,
  createCheckoutSession,
  getBillingPortalUrl,
  cancelSubscription,
  reactivateSubscription,
  startFreeTrial,
  getInvoices,
  syncSubscription
} from '../../services/api';
import './SubscriptionManager.css';

function SubscriptionManager() {
  const { checkAuth } = useAuth();
  const queryClient = useQueryClient();
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);

  const { data: subscriptionData, isLoading, refetch } = useQuery({
    queryKey: ['subscription-status'],
    queryFn: async () => {
      const response = await getSubscriptionStatus();
      return response.data.subscription;
    },
    refetchOnMount: 'always',
    refetchOnWindowFocus: true,
    staleTime: 0,
    cacheTime: 10 * 60 * 1000
  });

  const { data: invoicesData } = useQuery({
    queryKey: ['invoices'],
    queryFn: async () => {
      const response = await getInvoices();
      return response.data.invoices || [];
    },
    enabled: !!subscriptionData?.stripe_customer_id
  });

  const checkoutMutation = useMutation({
    mutationFn: async () => {
      const baseUrl = window.location.origin;
      const response = await createCheckoutSession(baseUrl);
      return response.data;
    },
    onSuccess: (data) => {
      if (data.checkout_url) {
        window.location.href = data.checkout_url;
      }
    },
    onError: (error) => {
      alert(error.response?.data?.error || 'Failed to start checkout. Please try again.');
    }
  });

  const trialMutation = useMutation({
    mutationFn: async () => {
      const response = await startFreeTrial();
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['subscription-status']);
      checkAuth();
    },
    onError: (error) => {
      alert(error.response?.data?.error || 'Failed to start trial. Please try again.');
    }
  });

  const portalMutation = useMutation({
    mutationFn: async () => {
      const baseUrl = window.location.origin;
      const response = await getBillingPortalUrl(baseUrl);
      return response.data;
    },
    onSuccess: (data) => {
      if (data.portal_url) {
        window.location.href = data.portal_url;
      }
    },
    onError: (error) => {
      alert(error.response?.data?.error || 'Failed to open billing portal. Please try again.');
    }
  });

  const cancelMutation = useMutation({
    mutationFn: cancelSubscription,
    onSuccess: () => {
      queryClient.invalidateQueries(['subscription-status']);
      checkAuth();
      setShowCancelConfirm(false);
    },
    onError: (error) => {
      alert(error.response?.data?.error || 'Failed to cancel subscription. Please try again.');
      setShowCancelConfirm(false);
    }
  });

  const reactivateMutation = useMutation({
    mutationFn: reactivateSubscription,
    onSuccess: () => {
      queryClient.invalidateQueries(['subscription-status']);
      checkAuth();
    },
    onError: (error) => {
      alert(error.response?.data?.error || 'Failed to reactivate subscription. Please try again.');
    }
  });

  if (isLoading) {
    return (
      <div className="subscription-manager loading">
        <div className="loading-spinner"></div>
        <p>Loading subscription info...</p>
      </div>
    );
  }

  const handleRefresh = async () => {
    try {
      // First try to sync from Stripe (in case webhook was delayed)
      await syncSubscription();
    } catch (error) {
      // Sync may fail if no Stripe customer yet - that's okay
    }
    // Then refresh auth and query
    await checkAuth();
    refetch();
  };

  const subscription = subscriptionData || {};
  const isActive = subscription.is_active;
  const isTrial = subscription.tier === 'trial';
  const isPro = subscription.tier === 'pro';
  const isNone = subscription.tier === 'none' || (!subscription.tier && !isActive);
  // Expired: trial that ran out, or explicitly expired tier (but NOT pro users)
  const isExpired = !isActive && !isPro && (isTrial || subscription.tier === 'expired' || isNone);
  const cancelAtPeriodEnd = subscription.cancel_at_period_end;

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString('en-IE', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  };

  return (
    <div className="subscription-manager">
      {/* Current Plan Card */}
      <div className={`subscription-card ${isActive ? 'active' : 'inactive'}`}>
        <div className="subscription-header">
          <div className="plan-info">
            <div className="plan-title-row">
              <span className={`plan-badge ${isPro ? 'pro' : isTrial && isActive ? 'trial' : isNone ? 'none' : 'expired'}`}>
                {isPro && 'Pro Plan'}
                {isTrial && isActive && !isPro && 'Free Trial'}
                {isTrial && !isActive && !isPro && 'Trial Expired'}
                {isNone && !isPro && 'No Plan'}
                {!isPro && !isTrial && !isNone && 'Expired'}
              </span>
              <button 
                className="btn-refresh" 
                onClick={handleRefresh}
                title="Refresh subscription status"
              >
                <i className="fas fa-sync-alt"></i>
              </button>
            </div>
            <h3>
              {isPro && 'BookedForYou Pro'}
              {isTrial && isActive && !isPro && 'Free Trial'}
              {isTrial && !isActive && !isPro && 'Trial Expired'}
              {isNone && !isPro && 'Get Started with BookedForYou'}
              {!isPro && !isTrial && !isNone && 'Subscription Expired'}
            </h3>
          </div>
          <div className="plan-price">
            {isPro && (
              <>
                <span className="price">&euro;99</span>
                <span className="period">/month</span>
              </>
            )}
            {isTrial && isActive && !isPro && (
              <span className="price free">Free</span>
            )}
            {!isPro && (isNone || isExpired) && (
              <span className="price inactive-price">&euro;0</span>
            )}
          </div>
        </div>

        <div className="subscription-status">
          {/* Only show trial info for actual trial users, never for pro */}
          {isTrial && isActive && !isPro && (
            <div className="trial-info">
              <i className="fas fa-clock"></i>
              <div>
                <strong>{subscription.trial_days_remaining} days left</strong>
                <p>Your trial ends on {formatDate(subscription.trial_end)}</p>
              </div>
            </div>
          )}
          
          {isPro && isActive && !cancelAtPeriodEnd && (
            <div className="active-info">
              <i className="fas fa-check-circle"></i>
              <div>
                <strong>Active Subscription</strong>
                <p>Next billing date: {formatDate(subscription.current_period_end)}</p>
              </div>
            </div>
          )}
          
          {isPro && cancelAtPeriodEnd && (
            <div className="cancelling-info">
              <i className="fas fa-exclamation-circle"></i>
              <div>
                <strong>Cancelling at Period End</strong>
                <p>Your subscription will end on {formatDate(subscription.current_period_end)}</p>
              </div>
            </div>
          )}
          
          {/* Only show trial expired for non-pro users */}
          {isTrial && !isActive && !isPro && (
            <div className="expired-info">
              <i className="fas fa-times-circle"></i>
              <div>
                <strong>Trial Expired</strong>
                <p>Your free trial has ended. Subscribe to continue using BookedForYou.</p>
              </div>
            </div>
          )}
          
          {/* Generic expired for non-pro, non-trial users */}
          {!isPro && !isTrial && !isNone && !isActive && (
            <div className="expired-info">
              <i className="fas fa-times-circle"></i>
              <div>
                <strong>Subscription Expired</strong>
                <p>Your subscription has ended. Resubscribe or start a trial to continue.</p>
              </div>
            </div>
          )}
          
          {isNone && (
            <div className="none-info">
              <i className="fas fa-info-circle"></i>
              <div>
                <strong>No Active Subscription</strong>
                <p>Start a free 14-day trial to explore all features, or subscribe to get started right away.</p>
              </div>
            </div>
          )}
        </div>

        <div className="subscription-features">
          <h4>All Features Included:</h4>
          <ul>
            <li><i className="fas fa-check"></i> Unlimited AI phone calls</li>
            <li><i className="fas fa-check"></i> Smart appointment scheduling</li>
            <li><i className="fas fa-check"></i> Customer management</li>
            <li><i className="fas fa-check"></i> Worker management</li>
            <li><i className="fas fa-check"></i> Financial tracking & invoicing</li>
            <li><i className="fas fa-check"></i> AI chat support</li>
            <li><i className="fas fa-check"></i> Priority support</li>
          </ul>
        </div>

        <div className="subscription-actions">
          {/* Show Start Trial only for users with no plan (never tried before) - never for pro users */}
          {isNone && !isPro && (
            <button
              className="btn btn-success btn-subscribe"
              onClick={() => trialMutation.mutate()}
              disabled={trialMutation.isPending}
            >
              <i className="fas fa-gift"></i>
              {trialMutation.isPending ? 'Starting...' : 'Start 14-Day Free Trial'}
            </button>
          )}

          {/* Show Subscribe button for trial (active or expired) or no-plan users - but not for active pro users */}
          {!isPro && (
            <button
              className="btn btn-primary btn-subscribe"
              onClick={() => checkoutMutation.mutate()}
              disabled={checkoutMutation.isPending}
            >
              <i className="fas fa-credit-card"></i>
              {checkoutMutation.isPending ? 'Loading...' : 'Subscribe Now - €99/month'}
            </button>
          )}

          {/* Show billing portal for pro users */}
          {isPro && !cancelAtPeriodEnd && (
            <div className="pro-actions">
              <button
                className="btn btn-secondary"
                onClick={() => portalMutation.mutate()}
                disabled={portalMutation.isPending}
              >
                <i className="fas fa-file-invoice-dollar"></i>
                {portalMutation.isPending ? 'Loading...' : 'Manage Billing'}
              </button>
              <button
                className="btn-cancel-link"
                onClick={() => setShowCancelConfirm(true)}
              >
                Cancel subscription
              </button>
            </div>
          )}

          {/* Show reactivate button if cancelling */}
          {isPro && cancelAtPeriodEnd && (
            <button
              className="btn btn-primary"
              onClick={() => reactivateMutation.mutate()}
              disabled={reactivateMutation.isPending}
            >
              <i className="fas fa-redo"></i>
              {reactivateMutation.isPending ? 'Loading...' : 'Reactivate Subscription'}
            </button>
          )}
        </div>
      </div>

      {/* Invoices Section */}
      {invoicesData && invoicesData.length > 0 && (
        <div className="invoices-section">
          <h3><i className="fas fa-file-invoice"></i> Billing History</h3>
          <div className="invoices-list">
            {invoicesData.map((invoice) => (
              <div key={invoice.id} className="invoice-item">
                <div className="invoice-info">
                  <span className="invoice-number">{invoice.number || 'Invoice'}</span>
                  <span className="invoice-date">
                    {new Date(invoice.created).toLocaleDateString()}
                  </span>
                </div>
                <div className="invoice-amount">
                  €{invoice.amount_paid?.toFixed(2) || '0.00'}
                </div>
                <span className={`invoice-status ${invoice.status}`}>
                  {invoice.status}
                </span>
                {invoice.invoice_pdf && (
                  <a 
                    href={invoice.invoice_pdf} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="btn btn-small"
                  >
                    <i className="fas fa-download"></i>
                    PDF
                  </a>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Cancel Confirmation Modal */}
      {showCancelConfirm && (
        <div className="sub-modal-overlay" onClick={() => setShowCancelConfirm(false)}>
          <div className="sub-modal-box" onClick={(e) => e.stopPropagation()}>
            <h3><i className="fas fa-exclamation-triangle"></i> Cancel Subscription?</h3>
            <p>
              Your subscription will remain active until the end of your current billing period.
              After that, you will lose access to all features.
            </p>
            <div className="sub-modal-actions">
              <button
                className="btn btn-secondary"
                onClick={() => setShowCancelConfirm(false)}
              >
                Keep Subscription
              </button>
              <button
                className="btn btn-danger"
                onClick={() => cancelMutation.mutate()}
                disabled={cancelMutation.isPending}
              >
                {cancelMutation.isPending ? 'Cancelling...' : 'Yes, Cancel'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default SubscriptionManager;
