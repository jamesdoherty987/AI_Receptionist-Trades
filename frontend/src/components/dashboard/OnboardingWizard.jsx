import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import PhoneConfigModal from '../modals/PhoneConfigModal';
import { getBusinessSettings, updateBusinessSettings } from '../../services/api';
import './OnboardingWizard.css';

const STEPS = [
  {
    id: 'service-area',
    title: 'Service Area',
    icon: 'fa-map-marker-alt',
    iconClass: 'welcome-icon',
    description: 'Where do you provide services?'
  },
  {
    id: 'company-details',
    title: 'Company Details',
    icon: 'fa-info-circle',
    iconClass: '',
    description: 'Help your AI receptionist know your business'
  },
  {
    id: 'payment',
    title: 'Payment Details',
    icon: 'fa-university',
    iconClass: '',
    description: 'Bank details for invoices'
  },
  {
    id: 'phone',
    title: 'AI Phone Number',
    icon: 'fa-phone',
    iconClass: 'phone-icon',
    description: 'Your AI receptionist number'
  }
];

function OnboardingWizard({ onComplete }) {
  const queryClient = useQueryClient();
  const [currentStepIndex, setCurrentStepIndex] = useState(null);
  const [showPhoneModal, setShowPhoneModal] = useState(false);
  const [formData, setFormData] = useState({
    address: '',
    coverage_area: '',
    business_hours: '',
    company_context: '',
    bank_iban: '',
    bank_bic: '',
    bank_name: '',
    bank_account_holder: ''
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [completedSteps, setCompletedSteps] = useState([]);

  const { data: settings, isLoading } = useQuery({
    queryKey: ['business-settings'],
    queryFn: async () => {
      const response = await getBusinessSettings();
      return response.data;
    },
  });

  // Pre-fill form with existing settings and determine completed steps
  useEffect(() => {
    if (settings) {
      setFormData({
        address: settings?.address || '',
        coverage_area: settings?.coverage_area || '',
        business_hours: settings?.business_hours || '',
        company_context: settings?.company_context || '',
        bank_iban: settings?.bank_iban || '',
        bank_bic: settings?.bank_bic || '',
        bank_name: settings?.bank_name || '',
        bank_account_holder: settings?.bank_account_holder || ''
      });

      // Determine which steps are complete
      const completed = [];
      if (settings.address || settings.coverage_area || settings.business_hours) {
        completed.push('service-area');
      }
      if (settings.company_context) {
        completed.push('company-details');
      }
      if (settings.bank_iban || settings.bank_account_holder) {
        completed.push('payment');
      }
      if (settings.twilio_phone_number) {
        completed.push('phone');
      }
      setCompletedSteps(completed);
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

  const handleSaveStep = async () => {
    setSaving(true);
    setError('');
    try {
      const currentStep = STEPS[currentStepIndex];
      
      // Only send fields relevant to the current step
      let dataToSave = {};
      if (currentStep.id === 'service-area') {
        dataToSave = {
          address: formData.address,
          coverage_area: formData.coverage_area,
          business_hours: formData.business_hours
        };
      } else if (currentStep.id === 'company-details') {
        dataToSave = {
          company_context: formData.company_context
        };
      } else if (currentStep.id === 'payment') {
        dataToSave = {
          bank_iban: formData.bank_iban,
          bank_bic: formData.bank_bic,
          bank_name: formData.bank_name,
          bank_account_holder: formData.bank_account_holder
        };
      }
      
      await saveMutation.mutateAsync(dataToSave);
      if (!completedSteps.includes(currentStep.id)) {
        setCompletedSteps(prev => [...prev, currentStep.id]);
      }
      setCurrentStepIndex(null); // Return to overview
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
    if (!completedSteps.includes('phone')) {
      setCompletedSteps(prev => [...prev, 'phone']);
    }
    setCurrentStepIndex(null);
  };

  const handleFinish = () => {
    localStorage.setItem('onboarding_complete', 'true');
    onComplete();
  };

  const handleSkipStep = () => {
    setCurrentStepIndex(null);
  };

  const isStepComplete = (stepId) => {
    if (stepId === 'phone') return !!settings?.twilio_phone_number;
    if (stepId === 'service-area') return !!(settings?.address || settings?.coverage_area || settings?.business_hours);
    if (stepId === 'company-details') return !!settings?.company_context;
    if (stepId === 'payment') return !!(settings?.bank_iban || settings?.bank_account_holder);
    return completedSteps.includes(stepId);
  };

  if (isLoading) {
    return (
      <div className="onboarding-inline">
        <div className="onboarding-loading">
          <i className="fas fa-spinner fa-spin"></i>
          <p>Loading...</p>
        </div>
      </div>
    );
  }

  // If all steps complete, don't show anything
  const allComplete = STEPS.every(step => isStepComplete(step.id));
  if (allComplete) {
    return null;
  }

  // Show step detail view
  if (currentStepIndex !== null) {
    const currentStep = STEPS[currentStepIndex];
    
    return (
      <>
        <div className="onboarding-inline">
          <div className="onboarding-step-card">
            <button className="step-back-btn" onClick={() => setCurrentStepIndex(null)}>
              <i className="fas fa-arrow-left"></i> Back to setup
            </button>
            
            <div className={`step-icon ${currentStep.iconClass}`}>
              <i className={`fas ${currentStep.icon}`}></i>
            </div>
            <h3>{currentStep.title}</h3>
            <p className="step-description">{currentStep.description}</p>

            {error && (
              <div className="onboarding-error">
                <i className="fas fa-exclamation-circle"></i> {error}
              </div>
            )}

            {currentStep.id === 'service-area' && (
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
                <div className="step-actions">
                  <button className="btn btn-secondary" onClick={handleSkipStep}>
                    Skip for now
                  </button>
                  <button 
                    className="btn btn-primary"
                    onClick={handleSaveStep}
                    disabled={saving}
                  >
                    {saving ? 'Saving...' : 'Save'}
                  </button>
                </div>
              </div>
            )}

            {currentStep.id === 'company-details' && (
              <div className="onboarding-form">
                <div className="form-group">
                  <label htmlFor="ob_company_context">Tell your AI receptionist about your business</label>
                  <textarea
                    id="ob_company_context"
                    name="company_context"
                    value={formData.company_context}
                    onChange={handleChange}
                    rows={6}
                    placeholder={"Examples:\n- Free parking available behind the building\n- Family-run business since 2005\n- All technicians are fully insured\n- 12-month warranty on all work"}
                    style={{ minHeight: '140px', resize: 'vertical' }}
                  />
                  <small>This helps your AI answer customer questions accurately - parking info, policies, certifications, etc.</small>
                </div>
                <div className="step-actions">
                  <button className="btn btn-secondary" onClick={handleSkipStep}>
                    Skip for now
                  </button>
                  <button 
                    className="btn btn-primary"
                    onClick={handleSaveStep}
                    disabled={saving}
                  >
                    {saving ? 'Saving...' : 'Save'}
                  </button>
                </div>
              </div>
            )}

            {currentStep.id === 'payment' && (
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
                <div className="step-actions">
                  <button className="btn btn-secondary" onClick={handleSkipStep}>
                    Skip for now
                  </button>
                  <button 
                    className="btn btn-primary"
                    onClick={handleSaveStep}
                    disabled={saving}
                  >
                    {saving ? 'Saving...' : 'Save'}
                  </button>
                </div>
              </div>
            )}

            {currentStep.id === 'phone' && (
              <div className="onboarding-form">
                {settings?.twilio_phone_number ? (
                  <>
                    <div className="phone-display">
                      <i className="fas fa-check-circle"></i>
                      <span>{settings.twilio_phone_number}</span>
                    </div>
                    <div className="step-actions">
                      <button className="btn btn-primary" onClick={() => setCurrentStepIndex(null)}>
                        Done
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    <p className="phone-cta-text">Choose a phone number for your AI receptionist.</p>
                    <div className="step-actions">
                      <button className="btn btn-secondary" onClick={handleSkipStep}>
                        Skip for now
                      </button>
                      <button 
                        className="btn btn-primary"
                        onClick={() => setShowPhoneModal(true)}
                      >
                        <i className="fas fa-phone"></i> Choose Number
                      </button>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        </div>

        <PhoneConfigModal
          isOpen={showPhoneModal}
          onClose={() => setShowPhoneModal(false)}
          onSuccess={handlePhoneConfigured}
          allowSkip={false}
        />
      </>
    );
  }

  // Show overview with step list
  const completedCount = STEPS.filter(step => isStepComplete(step.id)).length;
  
  return (
    <div className="onboarding-inline">
      <div className="onboarding-overview">
        <div className="onboarding-overview-header">
          <div className="overview-title">
            <i className="fas fa-clipboard-check"></i>
            <div>
              <h3>Quick Setup</h3>
              <p>{completedCount} of {STEPS.length} complete</p>
            </div>
          </div>
          <button className="dismiss-btn" onClick={handleFinish} title="Dismiss">
            <i className="fas fa-times"></i>
          </button>
        </div>
        
        <div className="setup-steps-list">
          {STEPS.map((step, index) => {
            const isComplete = isStepComplete(step.id);
            return (
              <button
                key={step.id}
                className={`setup-step-item ${isComplete ? 'complete' : ''}`}
                onClick={() => setCurrentStepIndex(index)}
              >
                <div className="step-item-icon">
                  {isComplete ? (
                    <i className="fas fa-check-circle"></i>
                  ) : (
                    <i className={`fas ${step.icon}`}></i>
                  )}
                </div>
                <div className="step-item-content">
                  <span className="step-item-title">{step.title}</span>
                  <span className="step-item-desc">{step.description}</span>
                </div>
                <i className="fas fa-chevron-right step-arrow"></i>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default OnboardingWizard;
