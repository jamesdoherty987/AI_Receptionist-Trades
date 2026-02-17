import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../../context/AuthContext';
import PhoneConfigModal from '../modals/PhoneConfigModal';
import { getBusinessSettings, updateBusinessSettings } from '../../services/api';
import './OnboardingWizard.css';

function OnboardingWizard({ onComplete }) {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [currentStep, setCurrentStep] = useState(0);
  const [showPhoneModal, setShowPhoneModal] = useState(false);
  const [formData, setFormData] = useState({
    address: '',
    coverage_area: '',
    business_hours: '',
    bank_iban: '',
    bank_bic: '',
    bank_name: '',
    bank_account_holder: ''
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
        address: settings?.address || '',
        coverage_area: settings?.coverage_area || '',
        business_hours: settings?.business_hours || '',
        bank_iban: settings?.bank_iban || '',
        bank_bic: settings?.bank_bic || '',
        bank_name: settings?.bank_name || '',
        bank_account_holder: settings?.bank_account_holder || ''
      });
    }
  }, [settings]);

  const saveMutation = useMutation({
    mutationFn: updateBusinessSettings,
    onSuccess: () => {
      queryClient.invalidateQueries(['business-settings']);
    },
  });

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    setError('');
  };

  const handleSaveStep = async (nextStep) => {
    setSaving(true);
    setError('');
    try {
      await saveMutation.mutateAsync(formData);
      setCurrentStep(nextStep);
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

  const totalSteps = 3;

  return (
    <>
      <div className="onboarding-overlay">
        <div className="onboarding-wizard">
          {/* Progress indicator */}
          <div className="onboarding-progress">
            {[...Array(totalSteps)].map((_, i) => (
              <div key={i} className="progress-step-wrapper">
                <div className={`progress-dot ${currentStep >= i ? 'active' : ''} ${currentStep > i ? 'complete' : ''}`}>
                  {currentStep > i ? <i className="fas fa-check"></i> : <span>{i + 1}</span>}
                </div>
                {i < totalSteps - 1 && <div className={`progress-line ${currentStep > i ? 'active' : ''}`}></div>}
              </div>
            ))}
          </div>

          <div className="onboarding-content">
            {/* Step 0: Welcome & Service Area */}
            {currentStep === 0 && (
              <div className="onboarding-step">
                <div className="step-icon welcome-icon">
                  <i className="fas fa-map-marker-alt"></i>
                </div>
                <h2>Welcome{user?.owner_name ? `, ${user.owner_name.split(' ')[0]}` : ''}! 👋</h2>
                <p className="step-description">
                  Let's set up a few things to get your AI receptionist ready.
                </p>
                
                {error && (
                  <div className="onboarding-error">
                    <i className="fas fa-exclamation-circle"></i> {error}
                  </div>
                )}
                
                <div className="onboarding-form">
                  <div className="form-group">
                    <label htmlFor="ob_address">Business Address</label>
                    <input
                      type="text"
                      id="ob_address"
                      name="address"
                      value={formData.address}
                      onChange={handleChange}
                      placeholder="e.g., 123 Main St, Dublin"
                    />
                  </div>
                  
                  <div className="form-group">
                    <label htmlFor="ob_coverage_area">Service Area</label>
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
                    <label htmlFor="ob_business_hours">Business Hours</label>
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
                  <button 
                    className="btn btn-primary btn-lg"
                    onClick={() => handleSaveStep(1)}
                    disabled={saving}
                  >
                    {saving ? 'Saving...' : 'Continue'}
                    {!saving && <i className="fas fa-arrow-right"></i>}
                  </button>
                </div>
                <button className="skip-link" onClick={() => setCurrentStep(1)}>
                  Skip for now
                </button>
              </div>
            )}

            {/* Step 1: Payment Setup */}
            {currentStep === 1 && (
              <div className="onboarding-step">
                <div className="step-icon">
                  <i className="fas fa-university"></i>
                </div>
                <h2>Payment Details</h2>
                <p className="step-description">
                  Add your bank details so customers can pay you via bank transfer on invoices.
                </p>
                
                {error && (
                  <div className="onboarding-error">
                    <i className="fas fa-exclamation-circle"></i> {error}
                  </div>
                )}
                
                <div className="onboarding-form">
                  <div className="form-group">
                    <label htmlFor="ob_bank_account_holder">Name on Account</label>
                    <input
                      type="text"
                      id="ob_bank_account_holder"
                      name="bank_account_holder"
                      value={formData.bank_account_holder}
                      onChange={handleChange}
                      placeholder="e.g., John Smith"
                    />
                  </div>

                  <div className="form-group">
                    <label htmlFor="ob_bank_name">Bank Name</label>
                    <input
                      type="text"
                      id="ob_bank_name"
                      name="bank_name"
                      value={formData.bank_name}
                      onChange={handleChange}
                      placeholder="e.g., AIB, Bank of Ireland"
                    />
                  </div>
                  
                  <div className="form-group">
                    <label htmlFor="ob_bank_iban">IBAN</label>
                    <input
                      type="text"
                      id="ob_bank_iban"
                      name="bank_iban"
                      value={formData.bank_iban}
                      onChange={handleChange}
                      placeholder="e.g., IE29 AIBK 9311 5212 3456 78"
                    />
                  </div>

                  <div className="form-group">
                    <label htmlFor="ob_bank_bic">BIC / SWIFT Code</label>
                    <input
                      type="text"
                      id="ob_bank_bic"
                      name="bank_bic"
                      value={formData.bank_bic}
                      onChange={handleChange}
                      placeholder="e.g., AIBKIE2D"
                    />
                  </div>
                </div>

                <div className="step-actions">
                  <button 
                    className="btn btn-secondary" 
                    onClick={() => setCurrentStep(0)}
                  >
                    <i className="fas fa-arrow-left"></i> Back
                  </button>
                  <button 
                    className="btn btn-primary btn-lg"
                    onClick={() => handleSaveStep(2)}
                    disabled={saving}
                  >
                    {saving ? 'Saving...' : 'Continue'}
                    {!saving && <i className="fas fa-arrow-right"></i>}
                  </button>
                </div>
                <button className="skip-link" onClick={() => setCurrentStep(2)}>
                  Skip for now
                </button>
              </div>
            )}

            {/* Step 2: Phone Number */}
            {currentStep === 2 && (
              <div className="onboarding-step">
                <div className="step-icon phone-icon">
                  <i className="fas fa-phone"></i>
                </div>
                <h2>Your AI Phone Number</h2>
                
                {settings?.twilio_phone_number ? (
                  <>
                    <p className="step-description">
                      You're all set! Your AI receptionist is ready to take calls.
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
                      Choose a phone number that customers will call to reach your AI receptionist.
                    </p>
                    <div className="phone-cta">
                      <button 
                        className="btn btn-primary btn-lg"
                        onClick={() => setShowPhoneModal(true)}
                      >
                        <i className="fas fa-phone"></i>
                        Choose Phone Number
                      </button>
                    </div>
                    <div className="step-actions">
                      <button 
                        className="btn btn-secondary" 
                        onClick={() => setCurrentStep(1)}
                      >
                        <i className="fas fa-arrow-left"></i> Back
                      </button>
                    </div>
                    <button className="skip-link" onClick={handleFinish}>
                      I'll do this later
                    </button>
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
