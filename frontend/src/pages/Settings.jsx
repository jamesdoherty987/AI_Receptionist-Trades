import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import Header from '../components/Header';
import LoadingSpinner from '../components/LoadingSpinner';
import ImageUpload from '../components/ImageUpload';
import PhoneConfigModal from '../components/modals/PhoneConfigModal';
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
  const [formData, setFormData] = useState({});
  const [saveMessage, setSaveMessage] = useState('');
  const [showPhoneModal, setShowPhoneModal] = useState(false);
  
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
    onError: () => {
      setSaveMessage('Error saving settings');
      setTimeout(() => setSaveMessage(''), 3000);
    },
  });

  const toggleMutation = useMutation({
    mutationFn: (enabled) => toggleAIReceptionist(enabled),
    onSuccess: () => {
      queryClient.invalidateQueries(['ai-status']);
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
            <h1>Business Settings</h1>
            <p className="settings-subtitle">Configure your AI receptionist and business information</p>
          </div>

          {/* Navigation Buttons */}
          <div className="settings-nav">
            <Link to="/dashboard" className="btn btn-secondary">
              <i className="fas fa-arrow-left"></i>
              Back to Dashboard
            </Link>
          </div>

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
              {aiStatus?.fallback_number && (
                <span className="fallback-info">
                  <i className="fas fa-phone"></i>
                  Fallback: {aiStatus.fallback_number}
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
                <h3>Business Logo</h3>
                <div className="logo-upload-section">
                  <ImageUpload
                    value={formData.logo_url}
                    onChange={(value) => setFormData(prev => ({ ...prev, logo_url: value }))}
                    placeholder="Upload Your Company Logo"
                  />
                  <small className="form-help" style={{ display: 'block', marginTop: '10px', color: '#666' }}>
                    Upload your company logo. It will appear in the header and on invoices. Maximum file size: 2MB.
                  </small>
                </div>
              </div>

              {/* Fallback settings section removed - business phone is now used for everything */}

              <div className="form-actions">
                {saveMessage && (
                  <div className={`save-message ${saveMessage.includes('Error') ? 'error' : 'success'}`}>
                    {saveMessage}
                  </div>
                )}
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
