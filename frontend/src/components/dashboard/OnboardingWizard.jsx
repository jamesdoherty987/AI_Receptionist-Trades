import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import PhoneConfigModal from '../modals/PhoneConfigModal';
import { getBusinessSettings, updateBusinessSettings, startFreeTrial } from '../../services/api';
import './OnboardingWizard.css';

function OnboardingWizard({ onComplete, onDismiss }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { user, checkAuth, hasActiveSubscription, getSubscriptionTier } = useAuth();
  const [currentStep, setCurrentStep] = useState(0);
  const [showPhoneModal, setShowPhoneModal] = useState(false);
  const [trialJustStarted, setTrialJustStarted] = useState(false);
  const [formData, setFormData] = useState({
    business_address: '',
    coverage_area: '',
    business_hours: ''
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const { data: settings, isLoading } = useQuery({
    queryKey: ['business-settings'],
    queryFn: async () => {
      const response = await getBusinessSettings();
      return response.data;
    },
  });

  // Pre-fill form with existing settings
  useEffect(() => {
    if (settings) {
      setFormData({
        business_address: settings?.address || '',
        coverage_area: settings?.coverage_area || '',
        business_hours: settings?.business_hours || ''
      });
    }
  }, [settings]);

  const saveMutation = useMutation({
    mutationFn: updateBusinessSettings,
    onSuccess: () => {
      queryClient.invalidateQueries(['business-settings']);
    },
  });

  const trialMutation = useMutation({
    mutationFn: startFreeTrial,
    onSuccess: () => {
      queryClient.invalidateQueries(['subscription-status']);
      checkAuth();
    },
    onError: (error) => {
      setError(error.response?.data?.error || 'Failed to start trial. Please try again.');
    }
  });

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    setError('');
  };

  const handleStartTrial = async () => {
    setSaving(true);
    setError('');
    // Set trialJustStarted BEFORE the mutation to prevent race condition
    // with checkAuth() updating subscription state
    setTrialJustStarted(true);
    try {
      await trialMutation.mutateAsync();
      // Move to business info step (which will be step 0 since needsSubscription is now false)
      setCurrentStep(0);
    } catch (err) {
      // If mutation fails, reset the flag
      setTrialJustStarted(false);
      // Error handled by mutation's onError
    } finally {
      setSaving(false);
    }
  };

  const handleGoToSubscription = () => {
    localStorage.setItem('onboarding_complete', 'true');
    onComplete();
    navigate('/settings?tab=subscription');
  };

  const handleSaveBusinessInfo = async () => {
    setSaving(true);
    setError('');
    try {
      await saveMutation.mutateAsync({
        address: formData.business_address,
        coverage_area: formData.coverage_area,
        business_hours: formData.business_hours
      });
      // Move to phone step - index depends on whether we need subscription
      setCurrentStep(needsSubscription ? 2 : 1);
    } catch (err) {
      setError('Failed to save. Please try again.');
      console.error('Error saving:', err);
    } finally {
      setSaving(false);
    }
  };

  const handlePhoneConfigured = () => {
    setShowPhoneModal(false);
    queryClient.invalidateQueries(['business-settings']);
    handleFinish();
  };

  const handleFinish = () => {
    localStorage.setItem('onboarding_complete', 'true');
    onComplete();
  };

  const tier = getSubscriptionTier();
  const isActive = hasActiveSubscription();
  // If trial was just started, treat as if subscription is active to skip trial step
  const needsSubscription = !trialJustStarted && (tier === 'none' || (!isActive && tier !== 'pro'));

  if (isLoading) {
    return (
      <div className="onboarding-overlay">
        <div className="onboarding-wizard">
          <div className="onboarding-loading">
            <i className="fas fa-spinner fa-spin"></i>
            <p>Loading...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="onboarding-overlay">
        <div className="onboarding-wizard">
          {/* Progress indicator */}
          <div className="onboarding-progress">
            {needsSubscription && (
              <>
                <div className={`progress-dot ${currentStep >= 0 ? 'active' : ''}`}>
                  {currentStep > 0 ? <i className="fas fa-check"></i> : <span>1</span>}
                </div>
                <div className="progress-line"></div>
              </>
            )}
            <div className={`progress-dot ${currentStep >= (needsSubscription ? 1 : 0) ? 'active' : ''}`}>
              {currentStep > (needsSubscription ? 1 : 0) ? <i className="fas fa-check"></i> : <span>{needsSubscription ? '2' : '1'}</span>}
            </div>
            <div className="progress-line"></div>
            <div className={`progress-dot ${currentStep >= (needsSubscription ? 2 : 1) ? 'active' : ''}`}>
              <span>{needsSubscription ? '3' : '2'}</span>
            </div>
          </div>

          <div className="onboarding-content">
            {/* Step 0: Start Trial (only if no subscription) */}
            {needsSubscription && currentStep === 0 && (
              <div className="onboarding-step">
                <div className="step-icon welcome-icon">
                  <i className="fas fa-gift"></i>
                </div>
                <h2>Welcome{user?.owner_name ? `, ${user.owner_name.split(' ')[0]}` : ''}!</h2>
                <p className="step-description">
                  Start your 14-day free trial to unlock all features. No credit card required.
                </p>
                
                {error && (
                  <div className="onboarding-error">
                    <i className="fas fa-exclamation-circle"></i> {error}
                  </div>
                )}

                <div className="trial-features">
                  <h4>What you'll get:</h4>
                  <ul>
                    <li><i className="fas fa-check"></i> AI-powered phone receptionist</li>
                    <li><i className="fas fa-check"></i> Smart appointment scheduling</li>
                    <li><i className="fas fa-check"></i> Customer & worker management</li>
                    <li><i className="fas fa-check"></i> Invoicing & financial tracking</li>
                  </ul>
                </div>

                <div className="step-actions">
                  <button 
                    className="btn btn-success btn-lg"
                    onClick={handleStartTrial}
                    disabled={saving}
                  >
                    {saving ? (
                      <>
                        <i className="fas fa-spinner fa-spin"></i> Starting...
                      </>
                    ) : (
                      <>
                        <i className="fas fa-gift"></i> Start Free Trial
                      </>
                    )}
                  </button>
                  <button 
                    className="btn btn-primary btn-lg"
                    onClick={handleGoToSubscription}
                  >
                    <i className="fas fa-credit-card"></i> Subscribe Now - €99/mo
                  </button>
                </div>
                <button className="skip-link" onClick={onDismiss}>
                  I'll do this later
                </button>
              </div>
            )}

            {/* Step 1: Business Info (address, coverage area, hours) */}
            {currentStep === (needsSubscription ? 1 : 0) && (
              <div className="onboarding-step">
                <div className="step-icon">
                  <i className="fas fa-building"></i>
                </div>
                <h2>Complete Your Business Profile</h2>
                <p className="step-description">
                  Add a few more details to help your AI receptionist serve customers better.
                </p>
                
                {error && (
                  <div className="onboarding-error">
                    <i className="fas fa-exclamation-circle"></i> {error}
                  </div>
                )}
                
                <div className="onboarding-form">
                  <div className="form-group">
                    <label htmlFor="ob_business_address">Business Address <span className="optional-label">(optional)</span></label>
                    <input
                      type="text"
                      id="ob_business_address"
                      name="business_address"
                      value={formData.business_address}
                      onChange={handleChange}
                      placeholder="e.g., 123 Main St, Dublin"
                    />
                  </div>
                  
                  <div className="form-group">
                    <label htmlFor="ob_coverage_area">Service Area <span className="optional-label">(optional)</span></label>
                    <input
                      type="text"
                      id="ob_coverage_area"
                      name="coverage_area"
                      value={formData.coverage_area}
                      onChange={handleChange}
                      placeholder="e.g., Dublin and surrounding areas"
                    />
                    <small>Where do you provide services?</small>
                  </div>

                  <div className="form-group">
                    <label htmlFor="ob_business_hours">Business Hours <span className="optional-label">(optional)</span></label>
                    <input
                      type="text"
                      id="ob_business_hours"
                      name="business_hours"
                      value={formData.business_hours}
                      onChange={handleChange}
                      placeholder="e.g., Mon-Fri 9am-5pm"
                    />
                  </div>
                </div>

                <div className="step-actions">
                  {needsSubscription && (
                    <button 
                      className="btn btn-secondary" 
                      onClick={() => setCurrentStep(0)}
                    >
                      <i className="fas fa-arrow-left"></i> Back
                    </button>
                  )}
                  <button 
                    className="btn btn-primary btn-lg"
                    onClick={handleSaveBusinessInfo}
                    disabled={saving}
                  >
                    {saving ? 'Saving...' : 'Continue'}
                    {!saving && <i className="fas fa-arrow-right"></i>}
                  </button>
                </div>
                <button className="skip-link" onClick={() => setCurrentStep(needsSubscription ? 2 : 1)}>
                  Skip for now
                </button>
              </div>
            )}

            {/* Step 2: Phone Number */}
            {currentStep === (needsSubscription ? 2 : 1) && (
              <div className="onboarding-step">
                <div className="step-icon">
                  <i className="fas fa-phone"></i>
                </div>
                <h2>Get Your AI Phone Number</h2>
                
                {settings?.twilio_phone_number ? (
                  <>
                    <p className="step-description">
                      You're all set! Your AI receptionist is ready.
                    </p>
                    <div className="phone-display">
                      <i className="fas fa-check-circle"></i>
                      <span>{settings.twilio_phone_number}</span>
                    </div>
                    <div className="step-actions">
                      <button className="btn btn-primary btn-lg" onClick={handleFinish}>
                        Go to Dashboard <i className="fas fa-arrow-right"></i>
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    <p className="step-description">
                      Choose a phone number customers will call to reach your AI receptionist.
                    </p>
                    <div className="phone-cta">
                      <button 
                        className="btn btn-primary btn-lg"
                        onClick={() => setShowPhoneModal(true)}
                      >
                        <i className="fas fa-phone"></i>
                        Choose Number
                      </button>
                    </div>
                    <div className="step-actions">
                      <button 
                        className="btn btn-secondary" 
                        onClick={() => setCurrentStep(needsSubscription ? 1 : 0)}
                      >
                        <i className="fas fa-arrow-left"></i> Back
                      </button>
                      <button className="skip-link" onClick={handleFinish}>
                        Skip for now
                      </button>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Phone Configuration Modal */}
      <PhoneConfigModal
        isOpen={showPhoneModal}
        onClose={() => setShowPhoneModal(false)}
        onSuccess={handlePhoneConfigured}
        allowSkip={false}
      />
    </>
  );
}

export default OnboardingWizard;
