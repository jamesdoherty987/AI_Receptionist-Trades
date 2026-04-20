import { useState, useEffect } from 'react';
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

const PLAN_FEATURES = {
  dashboard: {
    name: 'Dashboard',
    price: 99,
    tagline: 'Business management tools',
    features: [
      { text: 'Job management & scheduling', included: true },
      { text: 'Customer management', included: true },
      { text: 'Worker management', included: true },
      { text: 'Calendar & availability', included: true },
      { text: 'Financial tracking & invoicing', included: true },
      { text: 'Materials tracking', included: true },
      { text: 'Insights & reports', included: true },
      { text: 'AI receptionist & phone calls', included: false },
      { text: 'Smart AI scheduling', included: false },
      { text: 'Dedicated AI phone number', included: false },
    ],
  },
  pro: {
    name: 'Pro',
    price: 249,
    tagline: 'Everything + AI receptionist',
    features: [
      { text: 'Job management & scheduling', included: true },
      { text: 'Customer management', included: true },
      { text: 'Worker management', included: true },
      { text: 'Calendar & availability', included: true },
      { text: 'Financial tracking & invoicing', included: true },
      { text: 'Materials tracking', included: true },
      { text: 'Insights & reports', included: true },
      { text: 'AI receptionist & phone calls', included: true },
      { text: 'Smart AI scheduling', included: true },
      { text: 'Dedicated AI phone number', included: true },
    ],
  },
};

function SubscriptionManager() {
  const { checkAuth } = useAuth();
  const queryClient = useQueryClient();
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);
  const [syncAttempted, setSyncAttempted] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState('dashboard');

  const { data: subscriptionData, isLoading, refetch } = useQuery({
    queryKey: ['subscription-status'],
    queryFn: async () => {
      const response = await getSubscriptionStatus();
      return response.data.subscription;
    },
    refetchOnMount: 'always',
    refetchOnWindowFocus: true,
    staleTime: 0,
    gcTime: 10 * 60 * 1000
  });

  // Auto-sync on mount if user has a stripe_customer_id but tier is not active paid
  useEffect(() => {
    const autoSync = async () => {
      if (syncAttempted) return;
      if (!subscriptionData) return;
      // Sync if user has a Stripe customer but isn't on an active paid tier
      if (subscriptionData.stripe_customer_id && subscriptionData.tier !== 'pro') {
        setSyncAttempted(true);
        try {
          const syncResponse = await syncSubscription();
          if (syncResponse.data.subscription?.tier === 'pro') {
            await checkAuth();
            refetch();
          }
        } catch (error) {
          console.log('[SUBSCRIPTION_MANAGER] Auto-sync error:', error);
        }
      }
    };
    autoSync();
  }, [subscriptionData, syncAttempted, checkAuth, refetch]);

  const { data: invoicesData } = useQuery({
    queryKey: ['invoices'],
    queryFn: async () => {
      const response = await getInvoices();
      return response.data.invoices || [];
    },
    enabled: !!subscriptionData?.stripe_customer_id
  });

  const checkoutMutation = useMutation({
    mutationFn: async (plan) => {
      const baseUrl = window.location.origin;
      const response = await createCheckoutSession(baseUrl, plan);
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
      queryClient.invalidateQueries({ queryKey: ['subscription-status'] });
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
      queryClient.invalidateQueries({ queryKey: ['subscription-status'] });
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
      queryClient.invalidateQueries({ queryKey: ['subscription-status'] });
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
      const syncResponse = await syncSubscription();
      if (syncResponse.data.subscription?.tier === 'pro') {
        // synced
      }
    } catch (error) {
      // Sync may fail if no Stripe customer yet
    }
    await checkAuth();
    refetch();
    setSyncAttempted(false);
  };

  const subscription = subscriptionData || {};
  const isActive = subscription.is_active;
  const isTrial = subscription.tier === 'trial';
  const isPro = subscription.tier === 'pro';
  const currentPlan = subscription.plan || 'pro';
  const isNone = subscription.tier === 'none' || (!subscription.tier && !isActive);
  const cancelAtPeriodEnd = subscription.cancel_at_period_end;
  const hasUsedTrial = subscription.has_used_trial;
  const customPrice = subscription.custom_monthly_price;
  const customDashboardPrice = subscription.custom_dashboard_price;
  const customProPrice = subscription.custom_pro_price;

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString('en-IE', {
      year: 'numeric', month: 'long', day: 'numeric'
    });
  };

  // Active subscriber view — show current plan status
  if (isPro && isActive) {
    const planInfo = PLAN_FEATURES[currentPlan] || PLAN_FEATURES.pro;
    return (
      <div className="subscription-manager">
        <div className="subscription-card active">
          <div className="subscription-header">
            <div className="plan-info">
              <div className="plan-title-row">
                <span className="plan-badge pro">{planInfo.name} Plan</span>
                <button className="btn-refresh" onClick={handleRefresh} title="Refresh subscription status">
                  <i className="fas fa-sync-alt"></i>
                </button>
              </div>
              <h3>BookedForYou {planInfo.name}</h3>
            </div>
            <div className="plan-price">
              <span className="price">&euro;{customPrice || planInfo.price}</span>
              <span className="period">/month</span>
            </div>
          </div>

          <div className="subscription-status">
            {!cancelAtPeriodEnd ? (
              <div className="active-info">
                <i className="fas fa-check-circle"></i>
                <div>
                  <strong>Active Subscription</strong>
                  <p>Next billing date: {formatDate(subscription.current_period_end)}</p>
                </div>
              </div>
            ) : (
              <div className="cancelling-info">
                <i className="fas fa-exclamation-circle"></i>
                <div>
                  <strong>Cancelling at Period End</strong>
                  <p>Your subscription will end on {formatDate(subscription.current_period_end)}</p>
                </div>
              </div>
            )}
          </div>

          <div className="subscription-features">
            <h4>Your plan includes:</h4>
            <ul>
              {planInfo.features.filter(f => f.included).map((f, i) => (
                <li key={i}><i className="fas fa-check"></i> {f.text}</li>
              ))}
            </ul>
          </div>

          {/* Upgrade prompt for dashboard users */}
          {currentPlan === 'dashboard' && (
            <div className="upgrade-banner">
              <div className="upgrade-banner-content">
                <i className="fas fa-rocket"></i>
                <div>
                  <strong>Upgrade to Pro</strong>
                  <p>Add AI receptionist, smart scheduling, and a dedicated phone number for just €150/month more.</p>
                </div>
              </div>
              <button
                className="btn btn-primary"
                onClick={() => portalMutation.mutate()}
                disabled={portalMutation.isPending}
              >
                {portalMutation.isPending ? 'Loading...' : 'Upgrade to Pro'}
              </button>
            </div>
          )}

          <div className="subscription-actions">
            {!cancelAtPeriodEnd ? (
              <div className="pro-actions">
                <button className="btn btn-secondary" onClick={() => portalMutation.mutate()} disabled={portalMutation.isPending}>
                  <i className="fas fa-file-invoice-dollar"></i>
                  {portalMutation.isPending ? 'Loading...' : 'Manage Billing'}
                </button>
                <button className="btn-cancel-link" onClick={() => setShowCancelConfirm(true)}>
                  Cancel subscription
                </button>
              </div>
            ) : (
              <div className="pro-actions">
                <button className="btn btn-primary" onClick={() => reactivateMutation.mutate()} disabled={reactivateMutation.isPending}>
                  <i className="fas fa-redo"></i>
                  {reactivateMutation.isPending ? 'Loading...' : 'Reactivate Subscription'}
                </button>
                <button className="btn btn-secondary" onClick={() => portalMutation.mutate()} disabled={portalMutation.isPending}>
                  <i className="fas fa-file-invoice-dollar"></i>
                  {portalMutation.isPending ? 'Loading...' : 'Manage Billing'}
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Invoices */}
        {invoicesData && invoicesData.length > 0 && (
          <div className="invoices-section">
            <h3><i className="fas fa-file-invoice"></i> Billing History</h3>
            <div className="invoices-list">
              {invoicesData.map((invoice) => (
                <div key={invoice.id} className="invoice-item">
                  <div className="invoice-info">
                    <span className="invoice-number">{invoice.number || 'Invoice'}</span>
                    <span className="invoice-date">{new Date(invoice.created).toLocaleDateString()}</span>
                  </div>
                  <div className="invoice-amount">€{invoice.amount_paid?.toFixed(2) || '0.00'}</div>
                  <span className={`invoice-status ${invoice.status}`}>{invoice.status}</span>
                  {invoice.invoice_pdf && (
                    <a href={invoice.invoice_pdf} target="_blank" rel="noopener noreferrer" className="btn btn-small">
                      <i className="fas fa-download"></i> PDF
                    </a>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Cancel Modal */}
        {showCancelConfirm && (
          <div className="sub-modal-overlay" onClick={() => setShowCancelConfirm(false)}>
            <div className="sub-modal-box" onClick={(e) => e.stopPropagation()}>
              <h3><i className="fas fa-exclamation-triangle"></i> Cancel Subscription?</h3>
              <p>Your subscription will remain active until the end of your current billing period. After that, you will lose access to all features.</p>
              <div className="sub-modal-actions">
                <button className="btn btn-secondary" onClick={() => setShowCancelConfirm(false)}>Keep Subscription</button>
                <button className="btn btn-danger" onClick={() => cancelMutation.mutate()} disabled={cancelMutation.isPending}>
                  {cancelMutation.isPending ? 'Cancelling...' : 'Yes, Cancel'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // Non-subscriber view — show plan selection cards
  return (
    <div className="subscription-manager">
      {/* Status banner */}
      <div className={`subscription-card ${isActive ? 'active' : 'inactive'}`}>
        <div className="subscription-header">
          <div className="plan-info">
            <div className="plan-title-row">
              <span className={`plan-badge ${isTrial && isActive ? 'trial' : isNone ? 'none' : 'expired'}`}>
                {isTrial && isActive && 'Free Trial'}
                {isTrial && !isActive && 'Trial Expired'}
                {isNone && 'No Plan'}
                {!isTrial && !isNone && !isActive && 'Expired'}
              </span>
              <button className="btn-refresh" onClick={handleRefresh} title="Refresh subscription status">
                <i className="fas fa-sync-alt"></i>
              </button>
            </div>
            <h3>
              {isTrial && isActive && 'Free Trial'}
              {isTrial && !isActive && 'Trial Expired'}
              {isNone && 'Get Started with BookedForYou'}
              {!isTrial && !isNone && !isActive && 'Subscription Expired'}
            </h3>
          </div>
        </div>

        <div className="subscription-status">
          {isTrial && isActive && (
            <div className="trial-info">
              <i className="fas fa-clock"></i>
              <div>
                <strong>{subscription.trial_days_remaining} days left</strong>
                <p>Your trial ends on {formatDate(subscription.trial_end)}. All features are unlocked during the trial.</p>
              </div>
            </div>
          )}
          {isTrial && !isActive && (
            <div className="expired-info">
              <i className="fas fa-times-circle"></i>
              <div>
                <strong>Trial Expired</strong>
                <p>Choose a plan below to continue using BookedForYou.</p>
              </div>
            </div>
          )}
          {isNone && (
            <div className="none-info">
              <i className="fas fa-info-circle"></i>
              <div>
                <strong>No Active Subscription</strong>
                <p>{hasUsedTrial
                  ? 'Choose a plan below to get started.'
                  : 'Start a free 14-day trial to explore all features, or choose a plan below.'
                }</p>
              </div>
            </div>
          )}
          {!isTrial && !isNone && !isActive && (
            <div className="expired-info">
              <i className="fas fa-times-circle"></i>
              <div>
                <strong>Subscription Expired</strong>
                <p>Choose a plan below to resubscribe.</p>
              </div>
            </div>
          )}
        </div>

        {/* Trial button */}
        {!hasUsedTrial && !isActive && (
          <div className="subscription-actions">
            <button
              className="btn btn-success btn-subscribe"
              onClick={() => trialMutation.mutate()}
              disabled={trialMutation.isPending}
            >
              <i className="fas fa-gift"></i>
              {trialMutation.isPending ? 'Starting...' : 'Start 14-Day Free Trial — All Features'}
            </button>
          </div>
        )}
      </div>

      {/* Plan comparison cards */}
      <div className="plan-comparison">
        <h3 className="plan-comparison-title">Choose Your Plan</h3>
        <p style={{ margin: '-0.5rem 0 1rem', color: '#6b7280', fontSize: '0.875rem' }}>
          Subscribe instantly — no setup calls needed. Pick a plan and start using BookedForYou right away.
        </p>
        <div className="plan-cards">
          {['dashboard', 'pro'].map((planKey) => {
            const plan = PLAN_FEATURES[planKey];
            const isSelected = selectedPlan === planKey;
            const isHighlighted = planKey === 'pro';
            return (
              <div
                key={planKey}
                className={`plan-card ${isSelected ? 'selected' : ''} ${isHighlighted ? 'highlighted' : ''}`}
                onClick={() => setSelectedPlan(planKey)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setSelectedPlan(planKey); }}
              >
                {isHighlighted && <div className="popular-badge">Most Popular</div>}
                <div className="plan-card-header">
                  <h4>{plan.name}</h4>
                  <p className="plan-card-tagline">{plan.tagline}</p>
                  <div className="plan-card-price">
                    <span className="plan-card-amount">&euro;{(planKey === 'dashboard' ? customDashboardPrice : customProPrice) || plan.price}</span>
                    <span className="plan-card-period">/month</span>
                  </div>
                </div>
                <ul className="plan-card-features">
                  {plan.features.map((f, i) => (
                    <li key={i} className={f.included ? 'included' : 'excluded'}>
                      <i className={`fas ${f.included ? 'fa-check' : 'fa-times'}`}></i>
                      {f.text}
                    </li>
                  ))}
                </ul>
                <button
                  className={`btn ${isHighlighted ? 'btn-primary' : 'btn-secondary'} btn-subscribe plan-card-cta`}
                  onClick={(e) => { e.stopPropagation(); checkoutMutation.mutate(planKey); }}
                  disabled={checkoutMutation.isPending}
                >
                  <i className="fas fa-credit-card"></i>
                  {checkoutMutation.isPending
                    ? 'Loading...'
                    : `Subscribe — €${(planKey === 'dashboard' ? customDashboardPrice : customProPrice) || plan.price}/month`}
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* Invoices for returning users */}
      {invoicesData && invoicesData.length > 0 && (
        <div className="invoices-section">
          <h3><i className="fas fa-file-invoice"></i> Billing History</h3>
          <div className="invoices-list">
            {invoicesData.map((invoice) => (
              <div key={invoice.id} className="invoice-item">
                <div className="invoice-info">
                  <span className="invoice-number">{invoice.number || 'Invoice'}</span>
                  <span className="invoice-date">{new Date(invoice.created).toLocaleDateString()}</span>
                </div>
                <div className="invoice-amount">€{invoice.amount_paid?.toFixed(2) || '0.00'}</div>
                <span className={`invoice-status ${invoice.status}`}>{invoice.status}</span>
                {invoice.invoice_pdf && (
                  <a href={invoice.invoice_pdf} target="_blank" rel="noopener noreferrer" className="btn btn-small">
                    <i className="fas fa-download"></i> PDF
                  </a>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default SubscriptionManager;
