import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import PhoneConfigModal from '../modals/PhoneConfigModal';
import HelpTooltip from '../HelpTooltip';
import { getBusinessSettings, updateBusinessSettings, startFreeTrial, createCheckoutSession, getSubscriptionStatus, getServicesMenu, getEmployees, getMaterials } from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import { useIndustry } from '../../context/IndustryContext';
import './OnboardingWizard.css';

// Build onboarding steps dynamically based on industry profile
function buildSteps(industryProfile) {
  const { terminology, onboarding, features } = industryProfile;
  const steps = [
    {
      id: 'subscription',
      title: 'Subscription',
      icon: 'fa-crown',
      iconClass: 'subscription-icon',
      description: 'Activate your plan'
    },
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
      id: 'employees',
      title: onboarding.employeeLabel || 'Add Employees',
      icon: onboarding.employeeIcon || 'fa-hard-hat',
      iconClass: 'employees-icon',
      description: `Who ${features.materials ? 'does the work' : 'is on your team'}?`
    },
    {
      id: 'services',
      title: 'Add Services',
      icon: 'fa-concierge-bell',
      iconClass: 'services-icon',
      description: 'What services do you offer?'
    },
  ];

  // Only include inventory step if the industry uses materials
  if (onboarding.showMaterialsStep) {
    steps.push({
      id: 'materials',
      title: 'Set Up Inventory',
      icon: 'fa-boxes-stacked',
      iconClass: '',
      description: `Track inventory and stock levels`
    });
  }

  steps.push({
    id: 'phone',
    title: 'AI Phone Number',
    icon: 'fa-phone',
    iconClass: 'phone-icon',
    description: 'Your AI receptionist number',
    proOnly: true
  });

  return steps;
}

function OnboardingWizard({ onComplete }) {
  const queryClient = useQueryClient();
  const { user, subscription, hasActiveSubscription, getSubscriptionTier, checkAuth } = useAuth();
  const industryProfile = useIndustry();
  
  // Build steps dynamically based on industry
  const ALL_STEPS = buildSteps(industryProfile);
  
  // Filter steps based on plan — phone step only for pro/trial users
  const currentPlan = subscription?.plan || 'professional';
  const isSubscriptionActive = subscription?.is_active === true;
  const hasAIFeatures = ['pro', 'starter', 'professional', 'business', 'enterprise'].includes(currentPlan) && isSubscriptionActive;
  const STEPS = hasAIFeatures ? ALL_STEPS : ALL_STEPS.filter(s => !s.proOnly);
  const userKey = user?.email || 'default';
  const [currentStepIndex, setCurrentStepIndex] = useState(null);
  const [showPhoneModal, setShowPhoneModal] = useState(false);
  const [formData, setFormData] = useState({
    business_address: '',
    coverage_area: '',
    business_hours: '',
    company_context: '',
    bank_iban: '',
    bank_bic: '',
    bank_name: '',
    bank_account_holder: ''
  });
  const [hoursConfig, setHoursConfig] = useState({
    startHour: '9',
    startPeriod: 'AM',
    endHour: '5',
    endPeriod: 'PM',
    days: {
      monday: true,
      tuesday: true,
      wednesday: true,
      thursday: true,
      friday: true,
      saturday: false,
      sunday: false
    }
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [completedSteps, setCompletedSteps] = useState(() => {
    try {
      const saved = localStorage.getItem(`onboarding_completed_steps_${userKey}`);
      return saved ? JSON.parse(saved) : [];
    } catch { return []; }
  });
  const [hidden, setHidden] = useState(() => localStorage.getItem(`onboarding_hidden_${userKey}`) === 'true');

  // Re-sync hidden state when user loads (userKey changes from 'default' to actual email)
  useEffect(() => {
    setHidden(localStorage.getItem(`onboarding_hidden_${userKey}`) === 'true');
  }, [userKey]);

  // Re-sync completedSteps from localStorage when userKey changes
  useEffect(() => {
    try {
      const saved = localStorage.getItem(`onboarding_completed_steps_${userKey}`);
      if (saved) {
        setCompletedSteps(prev => {
          const merged = new Set([...prev, ...JSON.parse(saved)]);
          return [...merged];
        });
      }
    } catch { /* ignore */ }
  }, [userKey]);

  // Persist completedSteps to localStorage whenever they change
  useEffect(() => {
    if (completedSteps.length > 0) {
      localStorage.setItem(`onboarding_completed_steps_${userKey}`, JSON.stringify(completedSteps));
    }
  }, [completedSteps, userKey]);

  const handleHide = () => {
    setHidden(true);
    localStorage.setItem(`onboarding_hidden_${userKey}`, 'true');
  };

  const handleUnhide = () => {
    setHidden(false);
    localStorage.removeItem(`onboarding_hidden_${userKey}`);
  };

  const trialMutation = useMutation({
    mutationFn: startFreeTrial,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subscription-status'] });
      checkAuth();
      if (!completedSteps.includes('subscription')) {
        setCompletedSteps(prev => [...prev, 'subscription']);
      }
      setCurrentStepIndex(null);
    },
    onError: (err) => {
      setError(err.response?.data?.error || 'Failed to start trial. Please try again.');
    }
  });

  const checkoutMutation = useMutation({
    mutationFn: async (plan) => {
      const baseUrl = window.location.origin;
      const response = await createCheckoutSession(baseUrl, plan || 'pro');
      return response.data;
    },
    onSuccess: (data) => {
      if (data.checkout_url) {
        window.location.href = data.checkout_url;
      }
    },
    onError: (err) => {
      setError(err.response?.data?.error || 'Failed to start checkout. Please try again.');
    }
  });

  const { data: settings, isLoading } = useQuery({
    queryKey: ['business-settings'],
    queryFn: async () => {
      const response = await getBusinessSettings();
      return response.data;
    },
  });

  const { data: subscriptionData } = useQuery({
    queryKey: ['subscription-status'],
    queryFn: async () => {
      const response = await getSubscriptionStatus();
      return response.data.subscription;
    },
  });

  const { data: servicesData } = useQuery({
    queryKey: ['services-menu'],
    queryFn: async () => {
      const response = await getServicesMenu();
      return response.data;
    },
  });

  const { data: employeesData } = useQuery({
    queryKey: ['employees'],
    queryFn: async () => {
      const response = await getEmployees();
      return response.data;
    },
  });

  const { data: materialsData } = useQuery({
    queryKey: ['materials'],
    queryFn: async () => {
      const response = await getMaterials();
      return response.data;
    },
  });

  const parseBusinessHours = (hoursString) => {
    if (!hoursString) return;
    const timeMatch = hoursString.match(/(\d+)\s*(AM|PM)\s*-\s*(\d+)\s*(AM|PM)/i);
    const daysMatch = hoursString.match(/(Mon-Sat|Mon-Fri|Mon-Sun|Monday-Saturday|Monday-Friday|Monday-Sunday|Daily|[\w\s,-]+?)(?:\s*\(|$)/i);
    if (timeMatch) {
      const daysText = daysMatch ? daysMatch[1].trim().toLowerCase() : 'mon-fri';
      const days = { monday: false, tuesday: false, wednesday: false, thursday: false, friday: false, saturday: false, sunday: false };
      if (daysText.includes('daily') || daysText.includes('mon-sun') || daysText.includes('monday-sunday')) {
        Object.keys(days).forEach(d => days[d] = true);
      } else if (daysText.includes('mon-sat') || daysText.includes('monday-saturday')) {
        days.monday = days.tuesday = days.wednesday = days.thursday = days.friday = days.saturday = true;
      } else if (daysText.includes('mon-fri') || daysText.includes('monday-friday')) {
        days.monday = days.tuesday = days.wednesday = days.thursday = days.friday = true;
      } else {
        if (daysText.includes('mon')) days.monday = true;
        if (daysText.includes('tue')) days.tuesday = true;
        if (daysText.includes('wed')) days.wednesday = true;
        if (daysText.includes('thu')) days.thursday = true;
        if (daysText.includes('fri')) days.friday = true;
        if (daysText.includes('sat')) days.saturday = true;
        if (daysText.includes('sun')) days.sunday = true;
      }
      setHoursConfig({ startHour: timeMatch[1], startPeriod: timeMatch[2].toUpperCase(), endHour: timeMatch[3], endPeriod: timeMatch[4].toUpperCase(), days });
    }
  };

  const formatBusinessHours = () => {
    const { startHour, startPeriod, endHour, endPeriod, days } = hoursConfig;
    const dayNames = { monday: 'Mon', tuesday: 'Tue', wednesday: 'Wed', thursday: 'Thu', friday: 'Fri', saturday: 'Sat', sunday: 'Sun' };
    const selectedDays = Object.keys(days).filter(d => days[d]);
    let daysText = '';
    if (selectedDays.length === 7) daysText = 'Daily';
    else if (selectedDays.length === 6 && !days.sunday) daysText = 'Mon-Sat';
    else if (selectedDays.length === 5 && !days.saturday && !days.sunday) daysText = 'Mon-Fri';
    else if (selectedDays.length > 0) daysText = selectedDays.map(d => dayNames[d]).join(', ');
    else daysText = 'No days selected';
    return `${startHour} ${startPeriod} - ${endHour} ${endPeriod} ${daysText}`;
  };

  const handleHoursChange = (field, value) => {
    setHoursConfig(prev => ({ ...prev, [field]: value }));
  };

  const handleDayToggle = (day) => {
    setHoursConfig(prev => ({ ...prev, days: { ...prev.days, [day]: !prev.days[day] } }));
  };

  // Pre-fill form with existing settings and determine completed steps
  useEffect(() => {
    if (settings) {
      setFormData({
        business_address: settings?.business_address || '',
        coverage_area: settings?.coverage_area || '',
        business_hours: settings?.business_hours || '',
        company_context: settings?.company_context || '',
        bank_iban: settings?.bank_iban || '',
        bank_bic: settings?.bank_bic || '',
        bank_name: settings?.bank_name || '',
        bank_account_holder: settings?.bank_account_holder || ''
      });
      if (settings.business_hours) {
        parseBusinessHours(settings.business_hours);
      }

      // Determine which steps are complete — require all fields for service-area
      const completed = [];
      if (settings.business_address && settings.coverage_area && settings.business_hours) {
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
      if (settings.setup_wizard_complete) {
        // If wizard was already completed on backend, mark all done
        STEPS.forEach(s => completed.push(s.id));
      }
      setCompletedSteps(prev => {
        const merged = new Set([...prev, ...completed]);
        return [...merged];
      });
    }
  }, [settings]);

  // Auto-mark employees/services/materials complete when actual data exists
  useEffect(() => {
    const newCompleted = [];
    const employees = Array.isArray(employeesData) ? employeesData : [];
    if (employees.length > 0 && !completedSteps.includes('employees')) {
      newCompleted.push('employees');
      localStorage.setItem(`employees_setup_visited_${userKey}`, 'true');
    }
    const services = servicesData?.services || [];
    if (services.length > 0 && !completedSteps.includes('services')) {
      newCompleted.push('services');
      localStorage.setItem(`services_setup_visited_${userKey}`, 'true');
    }
    const materials = materialsData?.materials || [];
    if (materials.length > 0 && !completedSteps.includes('materials')) {
      newCompleted.push('materials');
      localStorage.setItem(`inventory_setup_visited_${userKey}`, 'true');
    }
    if (newCompleted.length > 0) {
      setCompletedSteps(prev => {
        const merged = new Set([...prev, ...newCompleted]);
        return [...merged];
      });
    }
  }, [employeesData, servicesData, materialsData, userKey]);

  const saveMutation = useMutation({
    mutationFn: updateBusinessSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['business-settings'] });
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
          business_address: formData.business_address,
          coverage_area: formData.coverage_area,
          business_hours: formatBusinessHours()
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
    queryClient.invalidateQueries({ queryKey: ['business-settings'] });
    if (!completedSteps.includes('phone')) {
      setCompletedSteps(prev => [...prev, 'phone']);
    }
    setCurrentStepIndex(null);
  };

  const handleFinish = () => {
    localStorage.setItem(`onboarding_complete_${userKey}`, 'true');
    // Persist to backend so it survives across devices/browsers
    updateBusinessSettings({ setup_wizard_complete: true }).catch(() => {});
    onComplete();
  };

  const handleSkipStep = () => {
    setCurrentStepIndex(null);
  };

  const isPaymentSkipped = () => localStorage.getItem(`payment_skipped_${userKey}`) === 'true';

  const handleSkipPayment = () => {
    localStorage.setItem(`payment_skipped_${userKey}`, 'true');
    if (!completedSteps.includes('payment')) {
      setCompletedSteps(prev => [...prev, 'payment']);
    }
    setCurrentStepIndex(null);
  };

  const isStepComplete = (stepId) => {
    if (stepId === 'subscription') return subscription?.is_active === true;
    if (stepId === 'phone') return !!settings?.twilio_phone_number || completedSteps.includes('phone');
    if (stepId === 'service-area') return !!(settings?.business_address && settings?.coverage_area && settings?.business_hours) || completedSteps.includes('service-area');
    if (stepId === 'company-details') return !!settings?.company_context || completedSteps.includes('company-details');
    if (stepId === 'payment') return !!(settings?.bank_iban || settings?.bank_account_holder) || isPaymentSkipped() || completedSteps.includes('payment');
    if (stepId === 'services') return (servicesData?.services || []).length > 0 || localStorage.getItem(`services_setup_visited_${userKey}`) === 'true' || completedSteps.includes('services');
    if (stepId === 'employees') return (Array.isArray(employeesData) ? employeesData : []).length > 0 || localStorage.getItem(`employees_setup_visited_${userKey}`) === 'true' || completedSteps.includes('employees');
    if (stepId === 'materials') return (materialsData?.materials || []).length > 0 || localStorage.getItem(`inventory_setup_visited_${userKey}`) === 'true' || localStorage.getItem(`materials_setup_visited_${userKey}`) === 'true' || completedSteps.includes('materials');
    return completedSteps.includes(stepId);
  };

  // Auto-finish the wizard when all steps are complete
  const allComplete = !isLoading && STEPS.every(step => isStepComplete(step.id));
  
  useEffect(() => {
    if (allComplete) {
      localStorage.setItem(`onboarding_complete_${userKey}`, 'true');
      // Persist to backend so it survives across devices/browsers
      updateBusinessSettings({ setup_wizard_complete: true }).catch(() => {});
      onComplete();
    }
  }, [allComplete, userKey, onComplete]);

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

            {currentStep.id === 'subscription' && (
              <div className="onboarding-form" style={{ textAlign: 'center' }}>
                {hasActiveSubscription() ? (
                  <>
                    <div className="subscription-active-display">
                      <i className="fas fa-check-circle"></i>
                      <span>{getSubscriptionTier() === 'trial' ? 'Free Trial Active' : `${(currentPlan || 'professional').charAt(0).toUpperCase() + (currentPlan || 'professional').slice(1)} Plan Active`}</span>
                    </div>
                    <div className="step-actions">
                      <button className="btn btn-primary" onClick={() => setCurrentStepIndex(null)}>
                        Done
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    <p className="subscription-cta-text">
                      {subscriptionData?.has_used_trial !== false
                        ? 'Choose a plan to unlock all features.'
                        : 'Start with a free 14-day trial or choose a plan.'}
                    </p>
                    <div className="step-actions subscription-actions-col">
                      {subscriptionData?.has_used_trial === false && (
                        <button
                          className="btn btn-success"
                          onClick={() => trialMutation.mutate()}
                          disabled={trialMutation.isPending}
                        >
                          <i className="fas fa-gift"></i>
                          {trialMutation.isPending ? 'Starting...' : 'Start 14-Day Free Trial — All Features'}
                        </button>
                      )}
                      <div className="onboarding-plan-cards">
                        <button
                          className="onboarding-plan-card"
                          onClick={() => checkoutMutation.mutate('starter')}
                          disabled={checkoutMutation.isPending}
                        >
                          <span className="onboarding-plan-name">Starter</span>
                          <span className="onboarding-plan-price">€99/month</span>
                          <span className="onboarding-plan-desc">500 AI call minutes included</span>
                        </button>
                        <button
                          className="onboarding-plan-card highlighted"
                          onClick={() => checkoutMutation.mutate('professional')}
                          disabled={checkoutMutation.isPending}
                        >
                          <span className="onboarding-plan-badge">Recommended</span>
                          <span className="onboarding-plan-name">Professional</span>
                          <span className="onboarding-plan-price">€249/month</span>
                          <span className="onboarding-plan-desc">1,200 AI call minutes included</span>
                        </button>
                        <button
                          className="onboarding-plan-card"
                          onClick={() => checkoutMutation.mutate('business')}
                          disabled={checkoutMutation.isPending}
                        >
                          <span className="onboarding-plan-name">Business</span>
                          <span className="onboarding-plan-price">€599/month</span>
                          <span className="onboarding-plan-desc">4,000 AI call minutes included</span>
                        </button>
                      </div>
                      <p style={{ fontSize: '0.8rem', color: '#6b7280', margin: '0.5rem 0 0' }}>
                        All plans include €0.15/min for additional minutes. 14-day free trial on all plans. <a href="mailto:contact@bookedforyou.ie?subject=Enterprise Enquiry" style={{ color: '#818cf8' }}>Contact us</a> for Enterprise with unlimited minutes.
                      </p>
                      <button className="btn btn-secondary" onClick={handleSkipStep}>
                        Skip for now
                      </button>
                    </div>
                  </>
                )}
              </div>
            )}

            {currentStep.id === 'service-area' && (
              <div className="onboarding-form">
                <div className="form-group">
                  <label htmlFor="ob_address">Business Address</label>
                  <input
                    type="text"
                    id="ob_address"
                    name="business_address"
                    value={formData.business_address}
                    onChange={handleChange}
                    placeholder="e.g., 123 Main St, Dublin"
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="ob_coverage_area">Service Area <HelpTooltip text="The geographic area you serve. Your AI receptionist uses this to tell callers if you cover their location." /></label>
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
                  <label>Business Hours</label>
                  <div className="ob-hours-config">
                    <div className="ob-time-row">
                      <div className="ob-time-selector">
                        <label className="ob-time-label">Start Time</label>
                        <div className="ob-time-inputs">
                          <select
                            value={hoursConfig.startHour}
                            onChange={(e) => handleHoursChange('startHour', e.target.value)}
                            className="ob-hour-select"
                          >
                            {[...Array(12)].map((_, i) => (
                              <option key={i + 1} value={i + 1}>{i + 1}</option>
                            ))}
                          </select>
                          <select
                            value={hoursConfig.startPeriod}
                            onChange={(e) => handleHoursChange('startPeriod', e.target.value)}
                            className="ob-period-select"
                          >
                            <option value="AM">AM</option>
                            <option value="PM">PM</option>
                          </select>
                        </div>
                      </div>
                      <span className="ob-time-separator">to</span>
                      <div className="ob-time-selector">
                        <label className="ob-time-label">End Time</label>
                        <div className="ob-time-inputs">
                          <select
                            value={hoursConfig.endHour}
                            onChange={(e) => handleHoursChange('endHour', e.target.value)}
                            className="ob-hour-select"
                          >
                            {[...Array(12)].map((_, i) => (
                              <option key={i + 1} value={i + 1}>{i + 1}</option>
                            ))}
                          </select>
                          <select
                            value={hoursConfig.endPeriod}
                            onChange={(e) => handleHoursChange('endPeriod', e.target.value)}
                            className="ob-period-select"
                          >
                            <option value="AM">AM</option>
                            <option value="PM">PM</option>
                          </select>
                        </div>
                      </div>
                    </div>
                    <div className="ob-days-selector">
                      <label className="ob-time-label">Days Open</label>
                      <div className="ob-days-checkboxes">
                        {[
                          { key: 'monday', label: 'Mon' },
                          { key: 'tuesday', label: 'Tue' },
                          { key: 'wednesday', label: 'Wed' },
                          { key: 'thursday', label: 'Thu' },
                          { key: 'friday', label: 'Fri' },
                          { key: 'saturday', label: 'Sat' },
                          { key: 'sunday', label: 'Sun' }
                        ].map(day => (
                          <label key={day.key} className="ob-day-checkbox">
                            <input
                              type="checkbox"
                              checked={hoursConfig.days[day.key]}
                              onChange={() => handleDayToggle(day.key)}
                            />
                            <span>{day.label}</span>
                          </label>
                        ))}
                      </div>
                    </div>
                    <small className="ob-hours-preview">
                      {formatBusinessHours()}
                    </small>
                  </div>
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
                  <label htmlFor="ob_company_context">Tell your AI receptionist about your business <HelpTooltip text="Anything your AI should know when talking to customers — parking info, warranties, certifications, policies, etc." /></label>
                  <textarea
                    id="ob_company_context"
                    name="company_context"
                    value={formData.company_context}
                    onChange={handleChange}
                    rows={6}
                    placeholder={industryProfile.onboarding?.companyContextPlaceholder || "Examples:\n- Free parking available behind the building\n- Family-run business since 2005\n- All technicians are fully insured\n- 12-month warranty on all work"}
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
                  <label htmlFor="ob_bank_iban">IBAN <HelpTooltip text="Your International Bank Account Number. Appears on invoices so customers can pay you." /></label>
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
                  <label htmlFor="ob_bank_bic">BIC / SWIFT Code <HelpTooltip text="Your bank's identification code. Usually 8 or 11 characters — find it on your bank statement or online banking." /></label>
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
                  <button className="btn btn-secondary" onClick={handleSkipPayment}>
                    I don't need this
                  </button>
                  <button 
                    className="btn btn-primary"
                    onClick={handleSaveStep}
                    disabled={saving}
                  >
                    {saving ? 'Saving...' : 'Save'}
                  </button>
                </div>
                <small className="payment-skip-hint">
                  You can always add payment details later in Settings if you change your mind.
                </small>
              </div>
            )}

            {currentStep.id === 'services' && (
              <div className="onboarding-form" style={{ textAlign: 'center' }}>
                {(servicesData?.services || []).length > 0 && (
                  <div className="subscription-active-display" style={{ marginBottom: '1rem' }}>
                    <i className="fas fa-check-circle"></i>
                    <span>{servicesData.services.length} service{servicesData.services.length !== 1 ? 's' : ''} added</span>
                  </div>
                )}
                <p className="subscription-cta-text">
                  {(servicesData?.services || []).length > 0
                    ? 'Review or add more services for your AI receptionist.'
                    : 'Add the services you offer so your AI receptionist can book them.'}
                </p>
                <div className="step-actions">
                  <button className="btn btn-secondary" onClick={handleSkipStep}>
                    Skip for now
                  </button>
                  <button className="btn btn-primary" onClick={() => { localStorage.setItem(`services_setup_visited_${userKey}`, 'true'); if (!completedSteps.includes('services')) { setCompletedSteps(prev => [...prev, 'services']); } setCurrentStepIndex(null); setTimeout(() => { document.querySelectorAll('.tab-button, .mobile-menu-item').forEach(btn => { if (btn.textContent.trim().includes('Services')) btn.click(); }); }, 100); }}>
                    <i className="fas fa-concierge-bell"></i> Go to Services
                  </button>
                </div>
              </div>
            )}

            {currentStep.id === 'employees' && (
              <div className="onboarding-form" style={{ textAlign: 'center' }}>
                {(Array.isArray(employeesData) ? employeesData : []).length > 0 && (
                  <div className="subscription-active-display" style={{ marginBottom: '1rem' }}>
                    <i className="fas fa-check-circle"></i>
                    <span>{employeesData.length} employee{employeesData.length !== 1 ? 's' : ''} added</span>
                  </div>
                )}
                <p className="subscription-cta-text">
                  {(Array.isArray(employeesData) ? employeesData : []).length > 0
                    ? 'Review or add more employees for job assignments.'
                    : 'Add your employees so jobs can be assigned to them.'}
                </p>
                <div className="step-actions">
                  <button className="btn btn-secondary" onClick={handleSkipStep}>
                    Skip for now
                  </button>
                  <button className="btn btn-primary" onClick={() => { localStorage.setItem(`employees_setup_visited_${userKey}`, 'true'); if (!completedSteps.includes('employees')) { setCompletedSteps(prev => [...prev, 'employees']); } setCurrentStepIndex(null); setTimeout(() => { document.querySelectorAll('.tab-button, .mobile-menu-item').forEach(btn => { if (btn.textContent.trim().includes('Employees')) btn.click(); }); }, 100); }}>
                    <i className="fas fa-hard-hat"></i> Go to Employees
                  </button>
                </div>
              </div>
            )}

            {currentStep.id === 'materials' && (
              <div className="onboarding-form" style={{ textAlign: 'center' }}>
                {(materialsData?.materials || []).length > 0 && (
                  <div className="subscription-active-display" style={{ marginBottom: '1rem' }}>
                    <i className="fas fa-check-circle"></i>
                    <span>{materialsData.materials.length} item{materialsData.materials.length !== 1 ? 's' : ''} added</span>
                  </div>
                )}
                <p className="subscription-cta-text">
                  {(materialsData?.materials || []).length > 0
                    ? 'Review or add more items to your inventory.'
                    : 'Add items you use or sell. Track stock levels and pricing in one place.'}
                </p>
                <div className="step-actions">
                  <button className="btn btn-secondary" onClick={handleSkipStep}>
                    Skip for now
                  </button>
                  <button className="btn btn-primary" onClick={() => { localStorage.setItem(`inventory_setup_visited_${userKey}`, 'true'); if (!completedSteps.includes('materials')) { setCompletedSteps(prev => [...prev, 'materials']); } setCurrentStepIndex(null); setTimeout(() => { document.querySelectorAll('.sidebar-item, .mobile-menu-item').forEach(btn => { if (btn.textContent.trim().includes('Inventory')) btn.click(); }); }, 100); }}>
                    <i className="fas fa-boxes-stacked"></i> Go to Inventory
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
  const remainingCount = STEPS.length - completedCount;

  // Collapsed reminder bar when hidden
  if (hidden) {
    return (
      <div className="onboarding-inline">
        <div className="onboarding-hidden-bar">
          <div className="hidden-bar-content">
            <i className="fas fa-clipboard-check"></i>
            <span>{remainingCount} setup step{remainingCount !== 1 ? 's' : ''} remaining</span>
          </div>
          <button className="hidden-bar-show-btn" onClick={handleUnhide}>
            Show setup
          </button>
        </div>
      </div>
    );
  }
  
  return (
    <div className="onboarding-inline">
      <div className="onboarding-overview">
        <div className="onboarding-overview-header">
          <div className="overview-title">
            <i className="fas fa-clipboard-check"></i>
            <div>
              <h3>Setup Guide</h3>
              <p>{completedCount} of {STEPS.length} complete</p>
            </div>
          </div>
          <div className="overview-header-actions">
            <button className="dismiss-btn" onClick={handleHide} title="Hide setup steps">
              <i className="fas fa-eye-slash"></i>
            </button>
            <button className="dismiss-btn" onClick={handleFinish} title="Dismiss permanently">
              <i className="fas fa-times"></i>
            </button>
          </div>
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
