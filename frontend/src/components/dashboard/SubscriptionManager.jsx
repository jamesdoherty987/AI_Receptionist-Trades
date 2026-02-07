import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../../context/AuthContext';
import {
  getSubscriptionStatus,
  createCheckoutSession,
  getBillingPortalUrl,
  cancelSubscription,
  reactivateSubscription,
  getInvoices
} from '../../services/api';
import './SubscriptionManager.css';

function SubscriptionManager() {
  const { checkAuth } = useAuth();
  const queryClient = useQueryClient();
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);

  const { data: subscriptionData, isLoading } = useQuery({
    queryKey: ['subscription-status'],
    queryFn: async () => {
      const response = await getSubscriptionStatus();
      return response.data.subscription;
    },
    refetchOnMount: true
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
    }
  });

  const cancelMutation = useMutation({
    mutationFn: cancelSubscription,
    onSuccess: () => {
      queryClient.invalidateQueries(['subscription-status']);
      checkAuth();
      setShowCancelConfirm(false);
    }
  });

  const reactivateMutation = useMutation({
    mutationFn: reactivateSubscription,
    onSuccess: () => {
      queryClient.invalidateQueries(['subscription-status']);
      checkAuth();
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

  const subscription = subscriptionData || {};
  const isActive = subscription.is_active;
  const isTrial = subscription.tier === 'trial';
  const isPro = subscription.tier === 'pro';
  const isExpired = subscription.tier === 'expired' || (!isActive && !isTrial);
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
            <span className={`plan-badge ${subscription.tier}`}>
              {isTrial && 'Free Trial'}
              {isPro && 'Pro Plan'}
              {isExpired && 'Expired'}
            </span>
            <h3>
              {isTrial && 'Free Trial'}
              {isPro && 'BookedForYou Pro'}
              {isExpired && 'Subscription Expired'}
            </h3>
          </div>
          <div className="plan-price">
            {isPro && (
              <>
                <span className="price">€59</span>
                <span className="period">/month</span>
              </>
            )}
            {isTrial && (
              <span className="price free">Free</span>
            )}
          </div>
        </div>

        <div className="subscription-status">
          {isTrial && isActive && (
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
          
          {isExpired && (
            <div className="expired-info">
              <i className="fas fa-times-circle"></i>
              <div>
                <strong>Subscription Inactive</strong>
                <p>Subscribe to continue using BookedForYou</p>
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
          {/* Show Subscribe button for trial or expired users */}
          {(isTrial || isExpired) && (
            <button
              className="btn btn-primary btn-subscribe"
              onClick={() => checkoutMutation.mutate()}
              disabled={checkoutMutation.isPending}
            >
              <i className="fas fa-credit-card"></i>
              {checkoutMutation.isPending ? 'Loading...' : 'Subscribe Now - €59/month'}
            </button>
          )}

          {/* Show billing portal for pro users */}
          {isPro && !cancelAtPeriodEnd && (
            <>
              <button
                className="btn btn-secondary"
                onClick={() => portalMutation.mutate()}
                disabled={portalMutation.isPending}
              >
                <i className="fas fa-file-invoice-dollar"></i>
                {portalMutation.isPending ? 'Loading...' : 'Manage Billing'}
              </button>
              <button
                className="btn btn-danger btn-outline"
                onClick={() => setShowCancelConfirm(true)}
              >
                <i className="fas fa-times"></i>
                Cancel Subscription
              </button>
            </>
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
        <div className="modal-overlay" onClick={() => setShowCancelConfirm(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h3><i className="fas fa-exclamation-triangle"></i> Cancel Subscription?</h3>
            <p>
              Your subscription will remain active until the end of your current billing period.
              After that, you will lose access to all features.
            </p>
            <div className="modal-actions">
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
