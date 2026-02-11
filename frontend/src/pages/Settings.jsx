import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import Header from '../components/Header';
import LoadingSpinner from '../components/LoadingSpinner';
import ImageUpload from '../components/ImageUpload';
import PhoneConfigModal from '../components/modals/PhoneConfigModal';
import SubscriptionManager from '../components/dashboard/SubscriptionManager';
import PaymentSetup from '../components/dashboard/PaymentSetup';
// Global flag to remove Stripe Connect from UI
const REMOVE_STRIPE_CONNECT = true;
import { 
  getBusinessSettings, 
  updateBusinessSettings,
  getAIReceptionistStatus,
  toggleAIReceptionist
} from '../services/api';
import './Settings.css';

function Settings() {
  const queryClient = useQueryClient();
  const { checkAuth } = useAuth();
  const [searchParams] = useSearchParams();
  const [formData, setFormData] = useState({});
  const [saveMessage, setSaveMessage] = useState('');
  const [showPhoneModal, setShowPhoneModal] = useState(false);
  const [activeTab, setActiveTab] = useState('business');
  // Flag to hide Stripe Connect component
  const hideStripeConnect = REMOVE_STRIPE_CONNECT;
  
  // Handle subscription redirect messages and tab param
  useEffect(() => {
    const subscriptionStatus = searchParams.get('subscription');
    const tabParam = searchParams.get('tab');
    
    if (tabParam === 'subscription') {
      setActiveTab('subscription');
      window.history.replaceState({}, '', '/settings');
    }
    
    if (subscriptionStatus === 'success') {
      setSaveMessage('Subscription activated successfully! Welcome to BookedForYou Pro.');
      setActiveTab('subscription');
      // Clear the URL parameter
      window.history.replaceState({}, '', '/settings');
      // Refresh auth to get updated subscription info
      checkAuth();
      setTimeout(() => setSaveMessage(''), 5000);
    } else if (subscriptionStatus === 'cancelled') {
      setSaveMessage('Checkout was cancelled. You can try again when ready.');
      setActiveTab('subscription');
      window.history.replaceState({}, '', '/settings');
      setTimeout(() => setSaveMessage(''), 5000);
    } else if (subscriptionStatus === 'required') {
      setSaveMessage('Your trial has expired. Please subscribe to continue using BookedForYou.');
      setActiveTab('subscription');
      window.history.replaceState({}, '', '/settings');
    }
  }, [searchParams, checkAuth]);
  
  // Business hours breakdown state
  const [hoursConfig, setHoursConfig] = useState({
    startHour: '8',
    startPeriod: 'AM',
    endHour: '6',
    endPeriod: 'PM',
    days: {
      monday: true,
      tuesday: true,
      wednesday: true,
      thursday: true,
      friday: true,
      saturday: true,
      sunday: false
    },
    emergencyAvailable: true
  });

  const { data: settings, isLoading } = useQuery({
    queryKey: ['business-settings'],
    queryFn: async () => {
      const response = await getBusinessSettings();
      return response.data;
    },
    staleTime: 0, // Always fetch fresh data
    refetchOnMount: true,
  });

  // Parse business hours string into components
  const parseBusinessHours = (hoursString) => {
    if (!hoursString) return;
    
    // Parse format: "8 AM - 6 PM Mon-Sat (24/7 emergency available)"
    const timeMatch = hoursString.match(/(\d+)\s*(AM|PM)\s*-\s*(\d+)\s*(AM|PM)/i);
    const daysMatch = hoursString.match(/(Mon-Sat|Mon-Fri|Mon-Sun|Monday-Saturday|Monday-Friday|Monday-Sunday|Daily|[\w\s,-]+?)(?:\s*\(|$)/i);
    const emergencyMatch = hoursString.match(/emergency/i);
    
    if (timeMatch) {
      // Parse which days are selected
      const daysText = daysMatch ? daysMatch[1].trim().toLowerCase() : 'mon-sat';
      const days = {
        monday: false,
        tuesday: false,
        wednesday: false,
        thursday: false,
        friday: false,
        saturday: false,
        sunday: false
      };
      
      if (daysText.includes('daily') || daysText.includes('mon-sun') || daysText.includes('monday-sunday')) {
        Object.keys(days).forEach(day => days[day] = true);
      } else if (daysText.includes('mon-sat') || daysText.includes('monday-saturday')) {
        days.monday = days.tuesday = days.wednesday = days.thursday = days.friday = days.saturday = true;
      } else if (daysText.includes('mon-fri') || daysText.includes('monday-friday')) {
        days.monday = days.tuesday = days.wednesday = days.thursday = days.friday = true;
      } else {
        // Parse individual days
        if (daysText.includes('mon')) days.monday = true;
        if (daysText.includes('tue')) days.tuesday = true;
        if (daysText.includes('wed')) days.wednesday = true;
        if (daysText.includes('thu')) days.thursday = true;
        if (daysText.includes('fri')) days.friday = true;
        if (daysText.includes('sat')) days.saturday = true;
        if (daysText.includes('sun')) days.sunday = true;
      }
      
      setHoursConfig({
        startHour: timeMatch[1],
        startPeriod: timeMatch[2].toUpperCase(),
        endHour: timeMatch[3],
        endPeriod: timeMatch[4].toUpperCase(),
        days,
        emergencyAvailable: !!emergencyMatch
      });
    }
  };

  // Update formData when settings data changes
  useEffect(() => {
    if (settings) {
      setFormData(settings);
      if (settings.business_hours) {
        parseBusinessHours(settings.business_hours);
      }
    }
  }, [settings]);

  const { data: aiStatus } = useQuery({
    queryKey: ['ai-status'],
    queryFn: async () => {
      const response = await getAIReceptionistStatus();
      return response.data;
    },
  });

  const saveMutation = useMutation({
    mutationFn: updateBusinessSettings,
    onSuccess: async () => {
      queryClient.invalidateQueries(['business-settings']);
      await checkAuth(); // Refresh user context to update logo
      setSaveMessage('Settings saved successfully!');
      setTimeout(() => setSaveMessage(''), 3000);
    },
    onError: (error) => {
      const errorMsg = error?.response?.data?.error || 'Error saving settings';
      setSaveMessage(errorMsg);
      setTimeout(() => setSaveMessage(''), 5000);
    },
  });

  const toggleMutation = useMutation({
    mutationFn: (enabled) => toggleAIReceptionist(enabled),
    onSuccess: (response) => {
      queryClient.invalidateQueries(['ai-status']);
      const status = response.data?.enabled ? 'enabled' : 'disabled';
      setSaveMessage(`AI Receptionist ${status} successfully!`);
      setTimeout(() => setSaveMessage(''), 3000);
    },
    onError: (error) => {
      const errorMsg = error?.response?.data?.error || 'Failed to toggle AI Receptionist';
      setSaveMessage(errorMsg);
      setTimeout(() => setSaveMessage(''), 5000);
    },
  });

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleHoursChange = (field, value) => {
    setHoursConfig(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleDayToggle = (day) => {
    setHoursConfig(prev => ({
      ...prev,
      days: {
        ...prev.days,
        [day]: !prev.days[day]
      }
    }));
  };

  const formatBusinessHours = () => {
    const { startHour, startPeriod, endHour, endPeriod, days, emergencyAvailable } = hoursConfig;
    
    // Format days string
    const dayNames = {
      monday: 'Mon',
      tuesday: 'Tue',
      wednesday: 'Wed',
      thursday: 'Thu',
      friday: 'Fri',
      saturday: 'Sat',
      sunday: 'Sun'
    };
    
    const selectedDays = Object.keys(days).filter(day => days[day]);
    let daysText = '';
    
    if (selectedDays.length === 7) {
      daysText = 'Daily';
    } else if (selectedDays.length === 6 && !days.sunday) {
      daysText = 'Mon-Sat';
    } else if (selectedDays.length === 5 && !days.saturday && !days.sunday) {
      daysText = 'Mon-Fri';
    } else if (selectedDays.length > 0) {
      daysText = selectedDays.map(day => dayNames[day]).join(', ');
    } else {
      daysText = 'No days selected';
    }
    
    let formatted = `${startHour} ${startPeriod} - ${endHour} ${endPeriod} ${daysText}`;
    if (emergencyAvailable) {
      formatted += ' (24/7 emergency available)';
    }
    return formatted;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const updatedData = {
      ...formData,
      business_hours: formatBusinessHours()
    };
    saveMutation.mutate(updatedData);
  };

  const handleToggleAI = () => {
    const newStatus = !aiStatus?.enabled;
    toggleMutation.mutate(newStatus);
  };

  const handlePhoneConfigSuccess = (phoneNumber) => {
    // Refresh settings to show the new phone number
    queryClient.invalidateQueries(['business-settings']);
    setSaveMessage('Phone number configured successfully!');
    setTimeout(() => setSaveMessage(''), 3000);
  };

  if (isLoading) {
    return (
      <div className="settings-page">
        <Header title="Business Settings" />
        <div className="container">
          <LoadingSpinner message="Loading settings..." />
        </div>
      </div>
    );
  }

  return (
    <div className="settings-page">
      <Header title="Business Settings" />
      <main className="settings-main">
        <div className="container">
          <div className="settings-header">
            <h1>Settings</h1>
            <p className="settings-subtitle">Manage your subscription and business information</p>
          </div>

          {/* Navigation Buttons */}
          <div className="settings-nav">
            <Link to="/dashboard" className="btn btn-secondary">
              <i className="fas fa-arrow-left"></i>
              Back to Dashboard
            </Link>
          </div>
          
          {/* Success/Error Message */}
          {saveMessage && (
            <div className={`settings-message ${saveMessage.includes('cancelled') || saveMessage.includes('Error') || saveMessage.includes('Failed') ? 'warning' : 'success'}`}>
              <i className={`fas ${saveMessage.includes('cancelled') || saveMessage.includes('Error') || saveMessage.includes('Failed') ? 'fa-exclamation-circle' : 'fa-check-circle'}`}></i>
              {saveMessage}
            </div>
          )}

          {/* Setup Suggestions Banner - show one high-priority suggestion at a time */}
          {settings && !saveMessage && (() => {
            // Priority order of suggestions
            if (!settings.business_name) {
              return (
                <div className="setup-suggestion">
                  <i className="fas fa-lightbulb"></i>
                  <span>Add your business name in Business Settings to personalize invoices</span>
                  <button className="btn-dismiss" onClick={() => setActiveTab('business')}>
                    Go to Settings <i className="fas fa-arrow-right"></i>
                  </button>
                </div>
              );
            }
            if (!settings.business_phone) {
              return (
                <div className="setup-suggestion">
                  <i className="fas fa-lightbulb"></i>
                  <span>Add your business phone number for call forwarding when AI is disabled</span>
                  <button className="btn-dismiss" onClick={() => setActiveTab('business')}>
                    Add Phone <i className="fas fa-arrow-right"></i>
                  </button>
                </div>
              );
            }
            if (!settings.bank_iban && !settings.revolut_phone) {
              return (
                <div className="setup-suggestion">
                  <i className="fas fa-lightbulb"></i>
                  <span>Add bank details or Revolut to include payment options on invoices</span>
                  <button className="btn-dismiss" onClick={() => setActiveTab('payments')}>
                    Setup Payments <i className="fas fa-arrow-right"></i>
                  </button>
                </div>
              );
            }
            if (!settings.twilio_phone_number) {
              return (
                <div className="setup-suggestion">
                  <i className="fas fa-lightbulb"></i>
                  <span>Configure your phone number to start receiving AI-handled calls</span>
                  <button className="btn-dismiss" onClick={() => setActiveTab('business')}>
                    Configure Phone <i className="fas fa-arrow-right"></i>
                  </button>
                </div>
              );
            }
            return null;
          })()}

          {/* Settings Tabs */}
          <div className="settings-tabs">
            <button 
              className={`settings-tab ${activeTab === 'subscription' ? 'active' : ''}`}
              onClick={() => setActiveTab('subscription')}
            >
              <i className="fas fa-credit-card"></i>
              <span className="settings-tab-text">Subscription</span>
            </button>
            <button 
              className={`settings-tab ${activeTab === 'payments' ? 'active' : ''}`}
              onClick={() => setActiveTab('payments')}
            >
              <i className="fab fa-stripe-s"></i>
              <span className="settings-tab-text">Payments</span>
            </button>
            <button 
              className={`settings-tab ${activeTab === 'business' ? 'active' : ''}`}
              onClick={() => setActiveTab('business')}
            >
              <i className="fas fa-building"></i>
              <span className="settings-tab-text">Business</span>
            </button>
          </div>

          {/* Subscription Tab */}
          {activeTab === 'subscription' && (
            <div className="settings-tab-content">
              <SubscriptionManager />
            </div>
          )}

          {/* Receive Payments Tab */}
          {activeTab === 'payments' && (
            <div className="settings-tab-content">
                <PaymentSetup />
            </div>
          )}

          {/* Business Settings Tab */}
          {activeTab === 'business' && (
            <>
              {/* AI Receptionist Toggle */}
              <div className="ai-toggle-card">
                <div className="toggle-content">
                  <div className="toggle-info">
                    <h3>
                      <i className="fas fa-robot"></i>
                      AI Receptionist
                </h3>
                <p>
                  {aiStatus?.enabled 
                    ? 'AI is currently handling your calls' 
                    : 'Calls are being forwarded to your fallback number'}
                </p>
              </div>
              <label className="toggle-switch">
                <input
                  type="checkbox"
                  checked={aiStatus?.enabled || false}
                  onChange={handleToggleAI}
                  disabled={toggleMutation.isPending}
                />
                <span className="toggle-slider"></span>
              </label>
            </div>
            <div className="toggle-status">
              <span className={`status-badge ${aiStatus?.enabled ? 'active' : 'inactive'}`}>
                {aiStatus?.enabled ? 'Active' : 'Inactive'}
              </span>
              {aiStatus?.business_phone && (
                <span className="fallback-info">
                  <i className="fas fa-phone"></i>
                  Fallback: {aiStatus.business_phone}
                </span>
              )}
            </div>
          </div>

          {/* Settings Form */}
          <div className="settings-card">
            <form onSubmit={handleSubmit}>
              <div className="form-section">
                <h3>Business Information</h3>
                <div className="form-grid">
                  <div className="form-group">
                    <label htmlFor="business_name">Business Name *</label>
                    <input
                      type="text"
                      id="business_name"
                      name="business_name"
                      value={formData.business_name || ''}
                      onChange={handleChange}
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="business_type">Business Type</label>
                    <input
                      type="text"
                      id="business_type"
                      name="business_type"
                      value={formData.business_type || ''}
                      onChange={handleChange}
                      placeholder="e.g., Plumbing, HVAC, Electrical"
                    />
                  </div>
                  <div className="form-group full-width">
                    <label>Business Hours</label>
                    <div className="hours-config">
                      <div className="time-row">
                        <div className="time-selector">
                          <label className="time-label">Start Time</label>
                          <div className="time-inputs">
                            <select
                              value={hoursConfig.startHour}
                              onChange={(e) => handleHoursChange('startHour', e.target.value)}
                              className="hour-select"
                            >
                              {[...Array(12)].map((_, i) => (
                                <option key={i + 1} value={i + 1}>{i + 1}</option>
                              ))}
                            </select>
                            <select
                              value={hoursConfig.startPeriod}
                              onChange={(e) => handleHoursChange('startPeriod', e.target.value)}
                              className="period-select"
                            >
                              <option value="AM">AM</option>
                              <option value="PM">PM</option>
                            </select>
                          </div>
                        </div>
                        
                        <span className="time-separator">to</span>
                        
                        <div className="time-selector">
                          <label className="time-label">End Time</label>
                          <div className="time-inputs">
                            <select
                              value={hoursConfig.endHour}
                              onChange={(e) => handleHoursChange('endHour', e.target.value)}
                              className="hour-select"
                            >
                              {[...Array(12)].map((_, i) => (
                                <option key={i + 1} value={i + 1}>{i + 1}</option>
                              ))}
                            </select>
                            <select
                              value={hoursConfig.endPeriod}
                              onChange={(e) => handleHoursChange('endPeriod', e.target.value)}
                              className="period-select"
                            >
                              <option value="AM">AM</option>
                              <option value="PM">PM</option>
                            </select>
                          </div>
                        </div>
                      </div>
                      
                      <div className="days-selector">
                        <label className="time-label">Days Open</label>
                        <div className="days-checkboxes">
                          {[
                            { key: 'monday', label: 'Mon' },
                            { key: 'tuesday', label: 'Tue' },
                            { key: 'wednesday', label: 'Wed' },
                            { key: 'thursday', label: 'Thu' },
                            { key: 'friday', label: 'Fri' },
                            { key: 'saturday', label: 'Sat' },
                            { key: 'sunday', label: 'Sun' }
                          ].map(day => (
                            <label key={day.key} className="day-checkbox">
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
                      
                      <div className="emergency-checkbox">
                        <label>
                          <input
                            type="checkbox"
                            checked={hoursConfig.emergencyAvailable}
                            onChange={(e) => handleHoursChange('emergencyAvailable', e.target.checked)}
                          />
                          <span>24/7 emergency available</span>
                        </label>
                      </div>
                    </div>
                    <small className="form-help">
                      Preview: {formatBusinessHours()}
                    </small>
                  </div>
                  <div className="form-group">
                    <label htmlFor="business_phone">Business Phone *</label>
                    <input
                      type="tel"
                      id="business_phone"
                      name="business_phone"
                      value={formData.business_phone || ''}
                      onChange={handleChange}
                      required
                      placeholder="e.g., 0852635954"
                    />
                    <small className="form-help">
                      Main contact number. Also used for call transfers and when AI is disabled.
                    </small>
                  </div>
                  <div className="form-group">
                    <label htmlFor="business_email">Business Email</label>
                    <input
                      type="email"
                      id="business_email"
                      name="business_email"
                      value={formData.business_email || ''}
                      onChange={handleChange}
                    />
                  </div>
                  <div className="form-group full-width">
                    <label htmlFor="business_address">Business Address</label>
                    <input
                      type="text"
                      id="business_address"
                      name="business_address"
                      value={formData.business_address || ''}
                      onChange={handleChange}
                    />
                  </div>
                </div>
              </div>

              <div className="form-section">
                <h3>
                  <i className="fas fa-calendar-alt" style={{ marginRight: '8px', color: '#4a90d9' }}></i>
                  Scheduling Settings
                </h3>
                <p className="section-description">
                  Configure how appointments are scheduled. Buffer time adds travel/preparation time between jobs.
                </p>
                <div className="form-grid">
                  <div className="form-group">
                    <label htmlFor="buffer_time_minutes">Buffer Time Between Jobs (mins)</label>
                    <select
                      id="buffer_time_minutes"
                      name="buffer_time_minutes"
                      value={formData.buffer_time_minutes || 15}
                      onChange={handleChange}
                      className="form-select"
                    >
                      <option value="0">No buffer</option>
                      <option value="5">5 minutes</option>
                      <option value="10">10 minutes</option>
                      <option value="15">15 minutes</option>
                      <option value="20">20 minutes</option>
                      <option value="30">30 minutes</option>
                      <option value="45">45 minutes</option>
                      <option value="60">1 hour</option>
                    </select>
                    <small className="form-help">
                      Time added between appointments for travel, preparation, or cleanup.
                    </small>
                  </div>
                  <div className="form-group">
                    <label htmlFor="default_duration_minutes">Default Job Duration (mins)</label>
                    <select
                      id="default_duration_minutes"
                      name="default_duration_minutes"
                      value={formData.default_duration_minutes || 60}
                      onChange={handleChange}
                      className="form-select"
                    >
                      <option value="15">15 minutes</option>
                      <option value="30">30 minutes</option>
                      <option value="45">45 minutes</option>
                      <option value="60">1 hour</option>
                      <option value="90">1.5 hours</option>
                      <option value="120">2 hours</option>
                      <option value="180">3 hours</option>
                      <option value="240">4 hours</option>
                      <option value="300">5 hours</option>
                      <option value="360">6 hours</option>
                      <option value="480">8 hours</option>
                    </select>
                    <small className="form-help">
                      Default duration when a service doesn't have a specific duration set.
                    </small>
                  </div>
                </div>
              </div>

              <div className="form-section">
                <h3>Phone Configuration</h3>
                <p className="section-description">
                  Your assigned phone number for receiving calls. {!formData.twilio_phone_number ? 'Click the button below to select your number.' : 'This number is permanently assigned to your account.'}
                </p>
                <div className="form-grid">
                  <div className="form-group full-width">
                    <label htmlFor="twilio_phone_number">Assigned Phone Number</label>
                    <div className="phone-number-display">
                      <input
                        type="tel"
                        id="twilio_phone_number"
                        name="twilio_phone_number"
                        value={formData.twilio_phone_number || 'Not assigned'}
                        readOnly
                        disabled
                        style={{ backgroundColor: '#f5f5f5', cursor: 'not-allowed' }}
                      />
                      {!formData.twilio_phone_number && (
                        <button
                          type="button"
                          className="btn btn-primary"
                          onClick={() => setShowPhoneModal(true)}
                          style={{ marginLeft: '1rem' }}
                        >
                          <i className="fas fa-phone"></i>
                          Configure Phone
                        </button>
                      )}
                    </div>
                    <small className="form-help">
                      {formData.twilio_phone_number 
                        ? 'This is your dedicated phone number. It cannot be changed once assigned.'
                        : 'You need to configure a phone number to receive calls.'}
                    </small>
                  </div>
                </div>
              </div>

              <div className="form-section">
                <h3>
                  <i className="fas fa-info-circle" style={{ marginRight: '8px', color: '#4a90d9' }}></i>
                  Company Details for AI Receptionist
                </h3>
                <p className="section-description">
                  Give your AI receptionist context about your business. This information helps it answer customer questions 
                  more accurately -- things like where to park, your company history, specific policies, areas you serve, 
                  certifications, or any other details callers might ask about.
                </p>
                <div className="form-grid">
                  <div className="form-group full-width">
                    <label htmlFor="company_context">Company Context &amp; Details</label>
                    <textarea
                      id="company_context"
                      name="company_context"
                      value={formData.company_context || ''}
                      onChange={handleChange}
                      rows={8}
                      placeholder={"Example:\n- Free parking available in the car park behind the building\n- We've been in business since 2005, family-run company\n- We serve all of Co. Clare, Limerick, and Galway\n- All our technicians are fully insured and certified\n- We offer a 12-month warranty on all work\n- Emergency callouts available 24/7 - extra charges apply after hours\n- Please have the area clear before our team arrives"}
                      style={{ 
                        minHeight: '180px', 
                        resize: 'vertical',
                        fontFamily: 'inherit',
                        lineHeight: '1.5'
                      }}
                    />
                    <small className="form-help">
                      This information is injected into the AI receptionist's knowledge. Write anything you'd want a real receptionist to know about your business.
                    </small>
                  </div>
                </div>
              </div>

              <div className="form-section">
                <h3>Business Logo</h3>
                <div className="logo-upload-section">
                  <ImageUpload
                    value={formData.logo_url}
                    onChange={(value) => setFormData(prev => ({ ...prev, logo_url: value }))}
                    placeholder="Upload Your Company Logo"
                  />
                  <small className="form-help" style={{ display: 'block', marginTop: '10px', color: '#666' }}>
                    Upload your company logo. It will appear in the header and on invoices. Images are automatically optimized.
                  </small>
                </div>
              </div>

              {/* Fallback settings section removed - business phone is now used for everything */}

              <div className="form-actions">
                <button 
                  type="submit" 
                  className="btn btn-primary"
                  disabled={saveMutation.isPending}
                >
                  <i className="fas fa-save"></i>
                  {saveMutation.isPending ? 'Saving...' : 'Save Settings'}
                </button>
              </div>
            </form>
          </div>
            </>
          )}
        </div>
      </main>

      {/* Phone Configuration Modal */}
      <PhoneConfigModal
        isOpen={showPhoneModal}
        onClose={() => setShowPhoneModal(false)}
        onSuccess={handlePhoneConfigSuccess}
        allowSkip={false}
      />
    </div>
  );
}

export default Settings;
