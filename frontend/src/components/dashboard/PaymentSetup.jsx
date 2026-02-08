import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import {
  getConnectStatus,
  getConnectOnboardingLink,
  getConnectDashboardLink,
  disconnectStripeConnect,
  getConnectBalance,
  getConnectPayouts,
  getBusinessSettings,
  updateBusinessSettings
} from '../../services/api';
import './PaymentSetup.css';

function PaymentSetup() {
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const [message, setMessage] = useState('');
  const [showDisconnectConfirm, setShowDisconnectConfirm] = useState(false);
  const [bankDetails, setBankDetails] = useState({
    bank_iban: '',
    bank_bic: '',
    bank_name: '',
    bank_account_holder: '',
    revolut_phone: ''
  });
  const [bankSaveMessage, setBankSaveMessage] = useState('');

  // Handle return from Stripe onboarding
  useEffect(() => {
    const connectStatus = searchParams.get('connect');
    if (connectStatus === 'return') {
      setMessage('Checking your account status...');
      queryClient.invalidateQueries(['connect-status']);
      // Clear the URL parameter
      window.history.replaceState({}, '', '/settings');
      setTimeout(() => setMessage(''), 3000);
    } else if (connectStatus === 'refresh') {
      setMessage('Your session expired. Please try again.');
      window.history.replaceState({}, '', '/settings');
      setTimeout(() => setMessage(''), 5000);
    }
  }, [searchParams, queryClient]);

  const { data: connectData, isLoading } = useQuery({
    queryKey: ['connect-status'],
    queryFn: async () => {
      const response = await getConnectStatus();
      return response.data;
    },
    refetchOnMount: true
  });

  const { data: balanceData } = useQuery({
    queryKey: ['connect-balance'],
    queryFn: async () => {
      const response = await getConnectBalance();
      return response.data.balance;
    },
    enabled: connectData?.status === 'active'
  });

  const { data: payoutsData } = useQuery({
    queryKey: ['connect-payouts'],
    queryFn: async () => {
      const response = await getConnectPayouts();
      return response.data.payouts || [];
    },
    enabled: connectData?.status === 'active'
  });

  const onboardingMutation = useMutation({
    mutationFn: async () => {
      const baseUrl = window.location.origin;
      const response = await getConnectOnboardingLink(baseUrl);
      return response.data;
    },
    onSuccess: (data) => {
      if (data.onboarding_url) {
        window.location.href = data.onboarding_url;
      }
    },
    onError: () => {
      setMessage('Failed to create setup link. Please try again.');
      setTimeout(() => setMessage(''), 5000);
    }
  });

  const dashboardMutation = useMutation({
    mutationFn: async () => {
      const response = await getConnectDashboardLink();
      return response.data;
    },
    onSuccess: (data) => {
      if (data.dashboard_url) {
        window.open(data.dashboard_url, '_blank');
      }
    }
  });

  const disconnectMutation = useMutation({
    mutationFn: disconnectStripeConnect,
    onSuccess: () => {
      queryClient.invalidateQueries(['connect-status']);
      setShowDisconnectConfirm(false);
      setMessage('Stripe account disconnected successfully.');
      setTimeout(() => setMessage(''), 5000);
    }
  });

  // Bank details - fetch from business settings
  const { data: settingsData } = useQuery({
    queryKey: ['business-settings-bank'],
    queryFn: async () => {
      const response = await getBusinessSettings();
      return response.data;
    },
    refetchOnMount: true
  });

  // Load bank details from settings when they arrive
  useEffect(() => {
    if (settingsData) {
      setBankDetails({
        bank_iban: settingsData.bank_iban || '',
        bank_bic: settingsData.bank_bic || '',
        bank_name: settingsData.bank_name || '',
        bank_account_holder: settingsData.bank_account_holder || '',
        revolut_phone: settingsData.revolut_phone || ''
      });
    }
  }, [settingsData]);

  const bankMutation = useMutation({
    mutationFn: (data) => updateBusinessSettings(data),
    onSuccess: () => {
      queryClient.invalidateQueries(['business-settings-bank']);
      queryClient.invalidateQueries(['business-settings']);
      setBankSaveMessage('Bank details saved successfully!');
      setTimeout(() => setBankSaveMessage(''), 5000);
    },
    onError: () => {
      setBankSaveMessage('Failed to save bank details. Please try again.');
      setTimeout(() => setBankSaveMessage(''), 5000);
    }
  });

  const handleBankChange = (e) => {
    const { name, value } = e.target;
    setBankDetails(prev => ({ ...prev, [name]: value }));
  };

  const handleBankSubmit = (e) => {
    e.preventDefault();
    bankMutation.mutate(bankDetails);
  };

  if (isLoading) {
    return (
      <div className="payment-setup loading">
        <div className="loading-spinner"></div>
        <p>Loading payment setup...</p>
      </div>
    );
  }

  const status = connectData?.status || 'not_connected';
  const isConnected = connectData?.connected;
  const isActive = status === 'active';
  const isPending = status === 'pending';
  const isIncomplete = status === 'incomplete';

  const getStatusBadge = () => {
    if (isActive) return { text: 'Active', class: 'active' };
    if (isPending) return { text: 'Pending Verification', class: 'pending' };
    if (isIncomplete) return { text: 'Setup Incomplete', class: 'incomplete' };
    return { text: 'Not Connected', class: 'not-connected' };
  };

  const statusBadge = getStatusBadge();

  return (
    <div className="payment-setup">
      {message && (
        <div className="payment-message">
          <i className="fas fa-info-circle"></i>
          {message}
        </div>
      )}

      <div className="payment-card">
        <div className="payment-header">
          <div className="payment-icon">
            <i className="fab fa-stripe-s"></i>
          </div>
          <div className="payment-title">
            <h3>Receive Payments</h3>
            <p>Connect your Stripe account to receive payments from customers</p>
          </div>
          <span className={`status-badge ${statusBadge.class}`}>
            {statusBadge.text}
          </span>
        </div>

        {/* Not Connected State */}
        {!isConnected && (
          <div className="payment-content">
            <div className="benefits-list">
              <h4>Why connect Stripe?</h4>
              <ul>
                <li><i className="fas fa-check"></i> Accept card payments from customers</li>
                <li><i className="fas fa-check"></i> Automatic deposits to your bank account</li>
                <li><i className="fas fa-check"></i> Send professional invoices with payment links</li>
                <li><i className="fas fa-check"></i> Track payments and payouts in one place</li>
                <li><i className="fas fa-check"></i> Secure, trusted payment processing</li>
              </ul>
            </div>
            <div className="payment-actions">
              <button
                className="btn btn-primary btn-connect"
                onClick={() => onboardingMutation.mutate()}
                disabled={onboardingMutation.isPending}
              >
                <i className="fab fa-stripe-s"></i>
                {onboardingMutation.isPending ? 'Setting up...' : 'Connect with Stripe'}
              </button>
              <p className="setup-note">
                <i className="fas fa-lock"></i>
                Takes about 5 minutes. You'll need your bank details and ID.
              </p>
            </div>
          </div>
        )}

        {/* Incomplete/Pending State */}
        {isConnected && (isIncomplete || isPending) && (
          <div className="payment-content">
            <div className="status-info pending-info">
              <i className="fas fa-clock"></i>
              <div>
                <strong>{connectData?.message}</strong>
                {connectData?.requirements?.length > 0 && (
                  <p>Items needed: {connectData.requirements.join(', ')}</p>
                )}
              </div>
            </div>
            <div className="payment-actions">
              <button
                className="btn btn-primary"
                onClick={() => onboardingMutation.mutate()}
                disabled={onboardingMutation.isPending}
              >
                <i className="fas fa-arrow-right"></i>
                {onboardingMutation.isPending ? 'Loading...' : 'Complete Setup'}
              </button>
              <button
                className="btn btn-secondary btn-outline"
                onClick={() => setShowDisconnectConfirm(true)}
              >
                <i className="fas fa-unlink"></i>
                Disconnect
              </button>
            </div>
          </div>
        )}

        {/* Active State */}
        {isConnected && isActive && (
          <div className="payment-content">
            <div className="status-info active-info">
              <i className="fas fa-check-circle"></i>
              <div>
                <strong>Ready to receive payments!</strong>
                <p>Your customers can pay invoices directly to your bank account.</p>
              </div>
            </div>

            {/* Balance Display */}
            {balanceData && (
              <div className="balance-section">
                <h4><i className="fas fa-wallet"></i> Account Balance</h4>
                <div className="balance-grid">
                  <div className="balance-item">
                    <span className="balance-label">Available</span>
                    <span className="balance-amount available">
                      {balanceData.available?.map(b => `${b.currency} ${b.amount.toFixed(2)}`).join(', ') || '€0.00'}
                    </span>
                  </div>
                  <div className="balance-item">
                    <span className="balance-label">Pending</span>
                    <span className="balance-amount pending">
                      {balanceData.pending?.map(b => `${b.currency} ${b.amount.toFixed(2)}`).join(', ') || '€0.00'}
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* Recent Payouts */}
            {payoutsData && payoutsData.length > 0 && (
              <div className="payouts-section">
                <h4><i className="fas fa-university"></i> Recent Payouts</h4>
                <div className="payouts-list">
                  {payoutsData.slice(0, 5).map((payout) => (
                    <div key={payout.id} className="payout-item">
                      <div className="payout-info">
                        <span className="payout-amount">
                          {payout.currency} {payout.amount.toFixed(2)}
                        </span>
                        <span className="payout-date">
                          {new Date(payout.created).toLocaleDateString()}
                        </span>
                      </div>
                      <span className={`payout-status ${payout.status}`}>
                        {payout.status}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="payment-actions">
              <button
                className="btn btn-secondary"
                onClick={() => dashboardMutation.mutate()}
                disabled={dashboardMutation.isPending}
              >
                <i className="fas fa-external-link-alt"></i>
                {dashboardMutation.isPending ? 'Opening...' : 'View Stripe Dashboard'}
              </button>
              <button
                className="btn btn-danger btn-outline"
                onClick={() => setShowDisconnectConfirm(true)}
              >
                <i className="fas fa-unlink"></i>
                Disconnect
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Bank Transfer Details Section */}
      <div className="bank-details-card">
        <div className="bank-header">
          <div className="bank-icon">
            <i className="fas fa-university"></i>
          </div>
          <div className="bank-title">
            <h3>Bank Transfer Details</h3>
            <p>Add your bank details so customers can pay via bank transfer on invoices</p>
          </div>
          {(bankDetails.bank_iban || bankDetails.revolut_phone) && (
            <span className="status-badge active">
              Configured
            </span>
          )}
          {!bankDetails.bank_iban && !bankDetails.revolut_phone && (
            <span className="status-badge not-connected">
              Not Set
            </span>
          )}
        </div>

        <div className="bank-content">
          {bankSaveMessage && (
            <div className={`payment-message ${bankSaveMessage.includes('Failed') ? 'error' : ''}`}>
              <i className={`fas ${bankSaveMessage.includes('Failed') ? 'fa-exclamation-circle' : 'fa-check-circle'}`}></i>
              {bankSaveMessage}
            </div>
          )}

          <form onSubmit={handleBankSubmit} className="bank-form">
            <div className="bank-form-grid">
              <div className="bank-form-group">
                <label htmlFor="bank_account_holder">
                  <i className="fas fa-user"></i>
                  Name on Account
                </label>
                <input
                  type="text"
                  id="bank_account_holder"
                  name="bank_account_holder"
                  value={bankDetails.bank_account_holder}
                  onChange={handleBankChange}
                  placeholder="e.g., John Smith"
                />
              </div>
              <div className="bank-form-group">
                <label htmlFor="bank_name">
                  <i className="fas fa-landmark"></i>
                  Bank Name
                </label>
                <input
                  type="text"
                  id="bank_name"
                  name="bank_name"
                  value={bankDetails.bank_name}
                  onChange={handleBankChange}
                  placeholder="e.g., AIB, Bank of Ireland"
                />
              </div>
              <div className="bank-form-group full-width">
                <label htmlFor="bank_iban">
                  <i className="fas fa-credit-card"></i>
                  IBAN
                </label>
                <input
                  type="text"
                  id="bank_iban"
                  name="bank_iban"
                  value={bankDetails.bank_iban}
                  onChange={handleBankChange}
                  placeholder="e.g., IE29 AIBK 9311 5212 3456 78"
                  className="iban-input"
                />
                <small>Your International Bank Account Number</small>
              </div>
              <div className="bank-form-group">
                <label htmlFor="bank_bic">
                  <i className="fas fa-globe"></i>
                  BIC / SWIFT Code
                </label>
                <input
                  type="text"
                  id="bank_bic"
                  name="bank_bic"
                  value={bankDetails.bank_bic}
                  onChange={handleBankChange}
                  placeholder="e.g., AIBKIE2D"
                />
              </div>
            </div>

            {/* Revolut Section */}
            <div className="revolut-section">
              <div className="revolut-header">
                <i className="fas fa-mobile-alt"></i>
                <span>Revolut Payment</span>
              </div>
              <div className="bank-form-grid">
                <div className="bank-form-group full-width">
                  <label htmlFor="revolut_phone">
                    <i className="fas fa-phone-alt"></i>
                    Revolut Phone Number
                  </label>
                  <input
                    type="tel"
                    id="revolut_phone"
                    name="revolut_phone"
                    value={bankDetails.revolut_phone}
                    onChange={handleBankChange}
                    placeholder="e.g., +353 86 123 4567"
                  />
                  <small>Customers can send you money via Revolut using this number</small>
                </div>
              </div>
            </div>

            <div className="bank-actions">
              <button
                type="submit"
                className="btn btn-primary"
                disabled={bankMutation.isPending}
              >
                <i className="fas fa-save"></i>
                {bankMutation.isPending ? 'Saving...' : 'Save Bank Details'}
              </button>
              <p className="bank-note">
                <i className="fas fa-info-circle"></i>
                These details will appear on invoices sent to your customers as a payment option.
              </p>
            </div>
          </form>
        </div>
      </div>

      {/* Disconnect Confirmation Modal */}
      {showDisconnectConfirm && (
        <div className="modal-overlay" onClick={() => setShowDisconnectConfirm(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h3><i className="fas fa-exclamation-triangle"></i> Disconnect Stripe?</h3>
            <p>
              If you disconnect your Stripe account, you won't be able to receive payments through BookedForYou until you reconnect.
            </p>
            <div className="modal-actions">
              <button
                className="btn btn-secondary"
                onClick={() => setShowDisconnectConfirm(false)}
              >
                Cancel
              </button>
              <button
                className="btn btn-danger"
                onClick={() => disconnectMutation.mutate()}
                disabled={disconnectMutation.isPending}
              >
                {disconnectMutation.isPending ? 'Disconnecting...' : 'Yes, Disconnect'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default PaymentSetup;
