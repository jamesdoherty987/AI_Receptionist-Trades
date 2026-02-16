import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../../context/AuthContext';
import PhoneConfigModal from '../modals/PhoneConfigModal';
import { getBusinessSettings, updateBusinessSettings } from '../../services/api';
import './OnboardingWizard.css';

function OnboardingWizard({ onComplete, onDismiss }) {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [currentStep, setCurrentStep] = useState(0);
  const [showPhoneModal, setShowPhoneModal] = useState(false);
  const [formData, setFormData] = useState({
    business_name: '',
    business_phone: '',
    coverage_area: ''
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

  // Pre-fill form with existing settings or signup data
  useEffect(() => {
    if (settings || user) {
      setFormData({
        business_name: settings?.business_name || user?.company_name || '',
        business_phone: settings?.business_phone || user?.phone || '',
        coverage_area: settings?.coverage_area || ''
      });
    }
  }, [settings, user]);

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

  const handleSaveAndContinue = async () => {
    if (!formData.business_name.trim()) {
      setError('Please enter your business name');
      return;
    }
    if (!formData.business_phone.trim()) {
      setError('Please enter your phone number');
      return;
    }
    
    setSaving(true);
    setError('');
    try {
      await saveMutation.mutateAsync(formData);
      setCurrentStep(1);
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
    // Go to finish step
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

  return (
    <>
      <div className="onboarding-overlay">
        <div className="onboarding-wizard">
          {/* Simple progress indicator */}
          <div className="onboarding-progress">
            <div className={`progress-dot ${currentStep >= 0 ? 'active' : ''}`}>
              {currentStep > 0 ? <i className="fas fa-check"></i> : <span>1</span>}
            </div>
            <div className={`progress-dot ${currentStep >= 1 ? 'active' : ''}`}>
              <span>2</span>
            </div>
          </div>

          <div className="onboarding-content">
            {/* Step 1: Business Details (combined with welcome) */}
            {currentStep === 0 && (
              <div className="onboarding-step">
                <div className="step-icon welcome-icon">
                  <i className="fas fa-hand-sparkles"></i>
                </div>
                <h2>Welcome{user?.owner_name ? `, ${user.owner_name.split(' ')[0]}` : ''}!</h2>
                <p className="step-description">
                  Let's quickly set up your AI receptionist. Just 2 quick steps.
                </p>
                
                {error && (
                  <div className="onboarding-error">
                    <i className="fas fa-exclamation-circle"></i> {error}
                  </div>
                )}
                
                <div className="onboarding-form">
                  <div className="form-group">
                    <label htmlFor="ob_business_name">Business Name</label>
                    <input
                      type="text"
                      id="ob_business_name"
                      name="business_name"
                      value={formData.business_name}
                      onChange={handleChange}
                      placeholder="e.g., Smith's Plumbing"
                      autoFocus
                    />
                  </div>
                  
                  <div className="form-group">
                    <label htmlFor="ob_business_phone">Your Phone Number</label>
                    <input
                      type="tel"
                      id="ob_business_phone"
                      name="business_phone"
                      value={formData.business_phone}
                      onChange={handleChange}
                      placeholder="e.g., 085 123 4567"
                    />
                    <small>For call transfers when AI is unavailable</small>
                  </div>
                </div>

                <div className="step-actions">
                  <button 
                    className="btn btn-primary btn-lg"
                    onClick={handleSaveAndContinue}
                    disabled={saving}
                  >
                    {saving ? 'Saving...' : 'Continue'}
                    {!saving && <i className="fas fa-arrow-right"></i>}
                  </button>
                </div>
                <button className="skip-link" onClick={onDismiss}>
                  I'll do this later
                </button>
              </div>
            )}

            {/* Step 2: Phone Number */}
            {currentStep === 1 && (
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
                        onClick={() => setCurrentStep(0)}
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
