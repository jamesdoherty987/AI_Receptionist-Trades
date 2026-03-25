import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import Header from '../components/Header';
import LoadingSpinner from '../components/LoadingSpinner';
import ImageUpload from '../components/ImageUpload';
import PhoneConfigModal from '../components/modals/PhoneConfigModal';
import SubscriptionManager from '../components/dashboard/SubscriptionManager';
import PaymentSetup from '../components/dashboard/PaymentSetup';
import { 
  getBusinessSettings, 
  updateBusinessSettings,
  getAIReceptionistStatus,
  toggleAIReceptionist,
  syncSubscription,
  deleteAccount,
  getGoogleCalendarStatus,
  connectGoogleCalendar,
  disconnectGoogleCalendar,
  syncGoogleCalendar
} from '../services/api';
import './Settings.css';

// Global flag to remove Stripe Connect from UI
const REMOVE_STRIPE_CONNECT = true;

function Settings() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { checkAuth, logout } = useAuth();
  const [searchParams] = useSearchParams();
  const [formData, setFormData] = useState({});
  const [saveMessage, setSaveMessage] = useState('');
  const [showPhoneModal, setShowPhoneModal] = useState(false);
  const [activeTab, setActiveTab] = useState('business');
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteConfirmation, setDeleteConfirmation] = useState('');
  const [deleteError, setDeleteError] = useState('');
  const [gcalConnecting, setGcalConnecting] = useState(false);
  const [gcalSyncing, setGcalSyncing] = useState(false);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  // Flag to hide Stripe Connect component
  const hideStripeConnect = REMOVE_STRIPE_CONNECT;
  
  // Handle subscription redirect messages and tab param
  useEffect(() => {
    const subscriptionStatus = searchParams.get('subscription');
    const tabParam = searchParams.get('tab');
    let pollTimeoutId = null;
    let isCancelled = false;
    
    if (tabParam === 'subscription') {
      setActiveTab('subscription');
      window.history.replaceState({}, '', '/settings');
    }
    
    const gcalParam = searchParams.get('gcal');
    if (gcalParam === 'connected') {
      setActiveTab('business');
      queryClient.invalidateQueries({ queryKey: ['gcal-status'] });
      setSaveMessage('Google Calendar connected successfully!');
      window.history.replaceState({}, '', '/settings');
      setTimeout(() => setSaveMessage(''), 5000);
    } else if (gcalParam === 'error') {
      setActiveTab('business');
      setSaveMessage('Failed to connect Google Calendar. Please try again.');
      window.history.replaceState({}, '', '/settings');
      setTimeout(() => setSaveMessage(''), 5000);
    }
    
    if (subscriptionStatus === 'success') {
      console.log('[SUBSCRIPTION] ========== CHECKOUT SUCCESS ==========');
      setSaveMessage('Subscription activated successfully! Welcome to BookedForYou Pro.');
      setActiveTab('subscription');
      // Clear the URL parameter
      window.history.replaceState({}, '', '/settings');
      
      // Poll for subscription update (webhook may take a moment to process)
      const pollSubscription = async (attempts = 0) => {
        console.log(`[SUBSCRIPTION] Poll attempt ${attempts + 1}/15`);
        if (isCancelled) {
          console.log('[SUBSCRIPTION] Polling cancelled');
          return;
        }
        
        try {
          // Try to sync from Stripe directly (bypasses webhook delay)
          console.log('[SUBSCRIPTION] Calling syncSubscription...');
          const syncResponse = await syncSubscription();
          console.log('[SUBSCRIPTION] Sync response:', syncResponse.data);
          
          if (syncResponse.data.subscription?.tier === 'pro') {
            console.log('[SUBSCRIPTION] SUCCESS! Tier is now pro');
            // Refresh auth state and query cache
            await checkAuth();
            queryClient.invalidateQueries({ queryKey: ['subscription-status'] });
            return; // Success - stop polling
          } else {
            console.log('[SUBSCRIPTION] Tier is still:', syncResponse.data.subscription?.tier);
          }
        } catch (error) {
          console.log('[SUBSCRIPTION] Sync error:', error.response?.data || error.message);
          // Sync may fail - continue polling
        }
        
        if (isCancelled) return;
        
        // Also refresh auth state
        console.log('[SUBSCRIPTION] Calling checkAuth...');
        await checkAuth();
        queryClient.invalidateQueries({ queryKey: ['subscription-status'] });
        
        // Wait a moment for the query to refetch
        await new Promise(resolve => setTimeout(resolve, 500));
        
        if (isCancelled) return;
        
        // Get fresh subscription data from the query cache
        const cachedData = queryClient.getQueryData(['subscription-status']);
        const authSub = JSON.parse(sessionStorage.getItem('authSubscription') || '{}');
        
        console.log('[SUBSCRIPTION] Cached data tier:', cachedData?.tier);
        console.log('[SUBSCRIPTION] Auth session tier:', authSub.tier);
        
        // Check if subscription is now pro from either source
        const isPro = cachedData?.tier === 'pro' || authSub.tier === 'pro';
        
        if (!isPro && attempts < 15) {
          // Exponential backoff: 1s, 1.5s, 2s, 2.5s, etc. up to 15 attempts (~30s total)
          const delay = 1000 + (attempts * 500);
          console.log(`[SUBSCRIPTION] Not pro yet, retrying in ${delay}ms...`);
          pollTimeoutId = setTimeout(() => pollSubscription(attempts + 1), delay);
        } else if (isPro) {
          console.log('[SUBSCRIPTION] SUCCESS! Subscription is now pro');
          // Final refresh to ensure everything is in sync
          queryClient.invalidateQueries({ queryKey: ['subscription-status'] });
          await checkAuth();
        } else {
          console.log('[SUBSCRIPTION] FAILED: Max attempts reached, tier still not pro');
          setSaveMessage('Payment received! Your subscription is being activated. Please click the refresh button if the status doesn\'t update shortly.');
        }
      };
      pollSubscription();
      
      setTimeout(() => setSaveMessage(''), 8000);
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
    
    // Cleanup function to cancel polling on unmount
    return () => {
      isCancelled = true;
      if (pollTimeoutId) {
        clearTimeout(pollTimeoutId);
      }
    };
  }, [searchParams, checkAuth, queryClient]);
  
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
      setHasUnsavedChanges(false);
      if (settings.business_hours) {
        parseBusinessHours(settings.business_hours);
      }
    }
  }, [settings]);

  // Expose unsaved changes flag globally so Header can check it
  useEffect(() => {
    window.__settingsUnsavedChanges = hasUnsavedChanges;
    return () => { window.__settingsUnsavedChanges = false; };
  }, [hasUnsavedChanges]);

  // Warn on browser tab close / refresh with unsaved changes
  useEffect(() => {
    if (!hasUnsavedChanges) return;
    const handler = (e) => {
      e.preventDefault();
      e.returnValue = '';
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [hasUnsavedChanges]);

  // Block in-app navigation with unsaved changes via popstate (browser back button)
  useEffect(() => {
    if (!hasUnsavedChanges) return;
    const handler = (e) => {
      // Push state back so the user stays on the page
      window.history.pushState(null, '', window.location.href);
      if (!window.confirm('You have unsaved changes. Are you sure you want to leave?')) {
        return;
      }
      // User confirmed — actually navigate back
      setHasUnsavedChanges(false);
      window.history.back();
    };
    window.history.pushState(null, '', window.location.href);
    window.addEventListener('popstate', handler);
    return () => window.removeEventListener('popstate', handler);
  }, [hasUnsavedChanges]);

  const { data: aiStatus } = useQuery({
    queryKey: ['ai-status'],
    queryFn: async () => {
      const response = await getAIReceptionistStatus();
      return response.data;
    },
  });

  const { data: gcalStatus, refetch: refetchGcalStatus } = useQuery({
    queryKey: ['gcal-status'],
    queryFn: async () => {
      const response = await getGoogleCalendarStatus();
      return response.data;
    },
  });

  const saveMutation = useMutation({
    mutationFn: updateBusinessSettings,
    onSuccess: async () => {
      queryClient.invalidateQueries({ queryKey: ['business-settings'] });
      await checkAuth();
      setHasUnsavedChanges(false);
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
      queryClient.invalidateQueries({ queryKey: ['ai-status'] });
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

  const deleteMutation = useMutation({
    mutationFn: (confirmation) => deleteAccount(confirmation),
    onSuccess: () => {
      // Clear all auth state and redirect to home
      logout();
      navigate('/');
    },
    onError: (error) => {
      const errorMsg = error?.response?.data?.error || 'Failed to delete account';
      setDeleteError(errorMsg);
    },
  });

  const handleDeleteAccount = () => {
    setDeleteError('');
    if (deleteConfirmation.toLowerCase() !== 'delete account') {
      setDeleteError("Please type 'delete account' to confirm");
      return;
    }
    deleteMutation.mutate(deleteConfirmation);
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
    setHasUnsavedChanges(true);
  };

  const handleHoursChange = (field, value) => {
    setHoursConfig(prev => ({
      ...prev,
      [field]: value
    }));
    setHasUnsavedChanges(true);
  };

  const handleDayToggle = (day) => {
    setHoursConfig(prev => ({
      ...prev,
      days: {
        ...prev.days,
        [day]: !prev.days[day]
      }
    }));
    setHasUnsavedChanges(true);
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
    if (e) e.preventDefault();
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
    queryClient.invalidateQueries({ queryKey: ['business-settings'] });
    setSaveMessage('Phone number configured successfully!');
    setTimeout(() => setSaveMessage(''), 3000);
  };

  const handleConnectGoogleCalendar = async () => {
    setGcalConnecting(true);
    try {
      const response = await connectGoogleCalendar();
      const { auth_url } = response.data;
      // Open Google OAuth in a popup
      const popup = window.open(auth_url, 'google-calendar-auth', 'width=600,height=700,scrollbars=yes');
      
      // Listen for the callback message
      const handleMessage = (event) => {
        if (event.data === 'google-calendar-connected') {
          window.removeEventListener('message', handleMessage);
          if (popup) popup.close();
          refetchGcalStatus();
          setSaveMessage('Google Calendar connected successfully!');
          setTimeout(() => setSaveMessage(''), 3000);
          setGcalConnecting(false);
        }
      };
      window.addEventListener('message', handleMessage);
      
      // Also poll in case popup message doesn't work (e.g. cross-origin)
      const pollInterval = setInterval(() => {
        if (popup && popup.closed) {
          clearInterval(pollInterval);
          window.removeEventListener('message', handleMessage);
          refetchGcalStatus();
          setGcalConnecting(false);
        }
      }, 1000);
    } catch (error) {
      const errorMsg = error?.response?.data?.error || 'Failed to start Google Calendar connection';
      setSaveMessage(errorMsg);
      setTimeout(() => setSaveMessage(''), 5000);
      setGcalConnecting(false);
    }
  };

  const handleDisconnectGoogleCalendar = async () => {
    if (!window.confirm('Are you sure you want to disconnect Google Calendar? Bookings will still be saved in the app, but will no longer sync to Google Calendar.')) {
      return;
    }
    try {
      await disconnectGoogleCalendar();
      refetchGcalStatus();
      setSaveMessage('Google Calendar disconnected');
      setTimeout(() => setSaveMessage(''), 3000);
    } catch (error) {
      setSaveMessage('Failed to disconnect Google Calendar');
      setTimeout(() => setSaveMessage(''), 5000);
    }
  };

  const handleSyncGoogleCalendar = async () => {
    setGcalSyncing(true);
    try {
      const response = await syncGoogleCalendar();
      const { message, push_created, push_updated, pull_imported, errors } = response.data;

      // Build a friendly summary
      const parts = [];
      if (push_created) parts.push(`${push_created} added`);
      if (push_updated) parts.push(`${push_updated} updated`);
      if (pull_imported) parts.push(`${pull_imported} imported`);
      if (!push_created && !push_updated && !pull_imported) parts.push('Already in sync');
      if (errors) parts.push(`${errors} failed`);

      const summary = `✅ Sync complete — ${parts.join(', ')}`;
      setSaveMessage(summary);
      setTimeout(() => setSaveMessage(''), 6000);
    } catch (error) {
      const errorMsg = error?.response?.data?.error || 'Failed to sync calendars';
      setSaveMessage(`❌ ${errorMsg}`);
      setTimeout(() => setSaveMessage(''), 6000);
    } finally {
      setGcalSyncing(false);
    }
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
            <button 
              className="btn btn-secondary"
              onClick={() => {
                if (hasUnsavedChanges && !window.confirm('You have unsaved changes. Are you sure you want to leave?')) {
                  return;
                }
                navigate('/dashboard');
              }}
            >
              <i className="fas fa-arrow-left"></i>
              Back to Dashboard
            </button>
          </div>
          
          {/* Success/Error Message */}
          {saveMessage && (
            <div className={`settings-message ${saveMessage.includes('cancelled') || saveMessage.includes('Error') || saveMessage.includes('Failed') ? 'warning' : 'success'}`}>
              <i className={`fas ${saveMessage.includes('cancelled') || saveMessage.includes('Error') || saveMessage.includes('Failed') ? 'fa-exclamation-circle' : 'fa-check-circle'}`}></i>
              {saveMessage}
            </div>
          )}

          {/* Setup Progress Card - show only when AI phone number is not configured */}
          {settings && !settings.twilio_phone_number && (
            <div className="setup-progress-card">
              <div className="setup-progress-header">
                <div className="setup-progress-title">
                  <i className="fas fa-phone"></i>
                  <div>
                    <h3>Configure AI Phone Number</h3>
                    <p>Set up your AI receptionist phone number to start receiving calls</p>
                  </div>
                </div>
              </div>
              <div className="setup-checklist">
                <div className="setup-item">
                  <div className="setup-item-icon">
                    <i className="far fa-circle"></i>
                  </div>
                  <div className="setup-item-content">
                    <span className="setup-item-title">AI phone number</span>
                    <button 
                      className="setup-item-action"
                      onClick={() => {
                        setActiveTab('business');
                        setShowPhoneModal(true);
                      }}
                    >
                      Configure
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

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
                      placeholder="e.g., 085 123 4567"
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

              {/* Google Calendar Integration */}
              <div className="form-section">
                <h3>
                  <i className="fab fa-google" style={{ marginRight: '8px', color: '#4285f4' }}></i>
                  Google Calendar
                </h3>
                <p className="section-description">
                  Connect your Google Calendar to keep both calendars in sync.
                  {' '}Bookings made by the AI receptionist appear in Google Calendar, and existing Google Calendar events are imported here.
                </p>
                <div className="gcal-status-card" style={{
                  padding: '1rem 1.25rem',
                  background: gcalStatus?.connected ? '#f0fdf4' : 'var(--bg-secondary)',
                  border: `1px solid ${gcalStatus?.connected ? '#86efac' : 'var(--border-color)'}`,
                  borderRadius: 'var(--radius-md)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '1rem',
                  flexWrap: 'wrap'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <i className={`fas ${gcalStatus?.connected ? 'fa-check-circle' : 'fa-circle'}`} 
                       style={{ color: gcalStatus?.connected ? '#16a34a' : '#9ca3af', fontSize: '1.25rem' }}></i>
                    <div>
                      <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                        {gcalStatus?.connected ? 'Connected' : 'Not connected'}
                      </div>
                      {gcalStatus?.connected && gcalStatus?.calendar_email && (
                        <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                          {gcalStatus.calendar_email}
                        </div>
                      )}
                    </div>
                  </div>
                  {gcalStatus?.connected ? (
                    <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                      <button
                        type="button"
                        className="btn btn-primary"
                        onClick={handleSyncGoogleCalendar}
                        disabled={gcalSyncing}
                        style={{ fontSize: '0.875rem' }}
                      >
                        <i className={`fas ${gcalSyncing ? 'fa-spinner fa-spin' : 'fa-sync'}`}></i>
                        {gcalSyncing ? 'Syncing...' : 'Sync Now'}
                      </button>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={handleDisconnectGoogleCalendar}
                        style={{ fontSize: '0.875rem' }}
                      >
                        <i className="fas fa-unlink"></i>
                        Disconnect
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={handleConnectGoogleCalendar}
                      disabled={gcalConnecting}
                      style={{ fontSize: '0.875rem' }}
                    >
                      <i className="fab fa-google"></i>
                      {gcalConnecting ? 'Connecting...' : 'Connect Google Calendar'}
                    </button>
                  )}
                </div>
                {!gcalStatus?.connected && (
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '0.5rem', lineHeight: '1.4' }}>
                    <i className="fas fa-info-circle" style={{ marginRight: '4px' }}></i>
                    Google will show a "Google hasn't verified this app" warning. Click <strong>Advanced</strong>, then <strong>Go to ai-receptionist-backend... (unsafe)</strong> at the bottom to continue. This is normal for new apps awaiting verification.
                  </p>
                )}
                {gcalStatus?.connected && (
                  <div className="toggle-row" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.6rem 0', marginTop: '0.75rem' }}>
                    <div>
                      <div style={{ fontWeight: 500, color: 'var(--text-primary)', fontSize: '0.9rem' }}>Invite Workers to Calendar Events</div>
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Workers with email addresses will receive Google Calendar invites for their assigned jobs</div>
                    </div>
                    <label className="toggle-switch">
                      <input
                        type="checkbox"
                        checked={formData.gcal_invite_workers || false}
                        onChange={(e) => { setFormData(prev => ({ ...prev, gcal_invite_workers: e.target.checked })); setHasUnsavedChanges(true); }}
                      />
                      <span className="toggle-slider"></span>
                    </label>
                  </div>
                )}
              </div>

              {/* Dashboard Feature Toggles */}
              <div className="form-section">
                <h3>
                  <i className="fas fa-sliders-h" style={{ marginRight: '8px', color: '#6366f1' }}></i>
                  Dashboard Features
                </h3>
                <p className="section-description">
                  Choose which features to show on your dashboard.
                </p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  <div className="toggle-row" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.6rem 0' }}>
                    <div>
                      <div style={{ fontWeight: 500, color: 'var(--text-primary)', fontSize: '0.9rem' }}>Finances Tab</div>
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Show the Finances tab on the dashboard</div>
                    </div>
                    <label className="toggle-switch">
                      <input
                        type="checkbox"
                        checked={formData.show_finances_tab !== false}
                        onChange={(e) => { setFormData(prev => ({ ...prev, show_finances_tab: e.target.checked })); setHasUnsavedChanges(true); }}
                      />
                      <span className="toggle-slider"></span>
                    </label>
                  </div>
                  <div className="toggle-row" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.6rem 0' }}>
                    <div>
                      <div style={{ fontWeight: 500, color: 'var(--text-primary)', fontSize: '0.9rem' }}>Insights Tab</div>
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Show the Insights tab with business analytics</div>
                    </div>
                    <label className="toggle-switch">
                      <input
                        type="checkbox"
                        checked={formData.show_insights_tab !== false}
                        onChange={(e) => { setFormData(prev => ({ ...prev, show_insights_tab: e.target.checked })); setHasUnsavedChanges(true); }}
                      />
                      <span className="toggle-slider"></span>
                    </label>
                  </div>
                  <div className="toggle-row" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.6rem 0' }}>
                    <div>
                      <div style={{ fontWeight: 500, color: 'var(--text-primary)', fontSize: '0.9rem' }}>Send Invoice Buttons</div>
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Show invoice buttons on jobs and finances</div>
                    </div>
                    <label className="toggle-switch">
                      <input
                        type="checkbox"
                        checked={formData.show_invoice_buttons !== false}
                        onChange={(e) => { setFormData(prev => ({ ...prev, show_invoice_buttons: e.target.checked })); setHasUnsavedChanges(true); }}
                      />
                      <span className="toggle-slider"></span>
                    </label>
                  </div>
                  <div className="toggle-row" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.6rem 0' }}>
                    <div>
                      <div style={{ fontWeight: 500, color: 'var(--text-primary)', fontSize: '0.9rem' }}>Booking Confirmation SMS</div>
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Send an SMS to the customer when a booking is confirmed</div>
                    </div>
                    <label className="toggle-switch">
                      <input
                        type="checkbox"
                        checked={formData.send_confirmation_sms !== false}
                        onChange={(e) => { setFormData(prev => ({ ...prev, send_confirmation_sms: e.target.checked })); setHasUnsavedChanges(true); }}
                      />
                      <span className="toggle-slider"></span>
                    </label>
                  </div>
                  <div className="toggle-row" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.6rem 0' }}>
                    <div>
                      <div style={{ fontWeight: 500, color: 'var(--text-primary)', fontSize: '0.9rem' }}>Day-Before Reminder SMS</div>
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Send a reminder SMS to the customer the day before their appointment</div>
                    </div>
                    <label className="toggle-switch">
                      <input
                        type="checkbox"
                        checked={formData.send_reminder_sms !== false}
                        onChange={(e) => { setFormData(prev => ({ ...prev, send_reminder_sms: e.target.checked })); setHasUnsavedChanges(true); }}
                      />
                      <span className="toggle-slider"></span>
                    </label>
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
                  more accurately -- things like where to park, your company history, specific policies, 
                  certifications, or any other details callers might ask about.
                </p>
                <div className="form-grid">
                  <div className="form-group full-width">
                    <label htmlFor="coverage_area">Coverage Area / Service Area</label>
                    <input
                      type="text"
                      id="coverage_area"
                      name="coverage_area"
                      value={formData.coverage_area || ''}
                      onChange={handleChange}
                      placeholder="e.g., Limerick and surrounding counties, Dublin city and suburbs, Nationwide"
                    />
                    <small className="form-help">
                      Where do you provide services? The AI will use this to answer questions about your service area.
                    </small>
                  </div>
                  <div className="form-group full-width">
                    <label htmlFor="company_context">Additional Company Context &amp; Details</label>
                    <textarea
                      id="company_context"
                      name="company_context"
                      value={formData.company_context || ''}
                      onChange={handleChange}
                      rows={8}
                      placeholder={"Example:\n- Free parking available in the car park behind the building\n- We've been in business since 2005, family-run company\n- All our technicians are fully insured and certified\n- We offer a 12-month warranty on all work\n- Please have the area clear before our team arrives"}
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
                    onChange={(value) => { setFormData(prev => ({ ...prev, logo_url: value })); setHasUnsavedChanges(true); }}
                    placeholder="Upload Your Company Logo"
                  />
                  <small className="form-help" style={{ display: 'block', marginTop: '10px', color: '#666' }}>
                    Upload your company logo. It will appear in the header and on invoices. Images are automatically optimized.
                  </small>
                </div>
              </div>

              {/* Fallback settings section removed - business phone is now used for everything */}
            </form>
          </div>

          {/* Danger Zone - Delete Account */}
          <div className="settings-card danger-zone">
            <h3>
              <i className="fas fa-exclamation-triangle" style={{ marginRight: '8px', color: '#dc2626' }}></i>
              Danger Zone
            </h3>
            <p className="section-description">
              Permanently delete your account and all associated data. This action cannot be undone.
            </p>
            <button 
              type="button"
              className="btn btn-danger"
              onClick={() => setShowDeleteModal(true)}
            >
              <i className="fas fa-trash-alt"></i>
              Delete Account
            </button>
          </div>
          
          {/* Floating Save Button */}
          <div className="floating-save-container">
            {hasUnsavedChanges && (
              <div className="unsaved-changes-hint">
                <i className="fas fa-exclamation-circle"></i>
                You have unsaved changes
              </div>
            )}
            <button 
              type="button"
              className="btn btn-primary floating-save-btn"
              disabled={saveMutation.isPending}
              onClick={handleSubmit}
            >
              <i className="fas fa-save"></i>
              {saveMutation.isPending ? 'Saving...' : 'Save Settings'}
            </button>
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

      {/* Delete Account Confirmation Modal */}
      {showDeleteModal && (
        <div className="modal-overlay" onClick={() => {
          setShowDeleteModal(false);
          setDeleteConfirmation('');
          setDeleteError('');
        }}>
          <div className="modal-content delete-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>
                <i className="fas fa-exclamation-triangle" style={{ color: '#dc2626', marginRight: '10px' }}></i>
                Delete Account
              </h2>
              <button className="modal-close" onClick={() => {
                setShowDeleteModal(false);
                setDeleteConfirmation('');
                setDeleteError('');
              }}>
                <i className="fas fa-times"></i>
              </button>
            </div>
            <div className="modal-body">
              <div className="delete-warning">
                <p><strong>This action is permanent and cannot be undone.</strong></p>
                <p>Deleting your account will remove:</p>
                <ul>
                  <li>All your business information</li>
                  <li>All customers and their data</li>
                  <li>All jobs and bookings</li>
                  <li>All workers</li>
                  <li>All services</li>
                  <li>Your subscription (if active)</li>
                </ul>
              </div>
              <div className="delete-confirm-input">
                <label>Type <strong>delete account</strong> to confirm:</label>
                <input
                  type="text"
                  value={deleteConfirmation}
                  onChange={(e) => setDeleteConfirmation(e.target.value)}
                  placeholder="delete account"
                  autoComplete="off"
                />
              </div>
              {deleteError && (
                <div className="delete-error">
                  <i className="fas fa-exclamation-circle"></i>
                  {deleteError}
                </div>
              )}
            </div>
            <div className="modal-footer">
              <button 
                className="btn btn-secondary" 
                onClick={() => {
                  setShowDeleteModal(false);
                  setDeleteConfirmation('');
                  setDeleteError('');
                }}
              >
                Cancel
              </button>
              <button 
                className="btn btn-danger"
                onClick={handleDeleteAccount}
                disabled={deleteMutation.isPending || deleteConfirmation.toLowerCase() !== 'delete account'}
              >
                {deleteMutation.isPending ? (
                  <>
                    <i className="fas fa-spinner fa-spin"></i>
                    Deleting...
                  </>
                ) : (
                  <>
                    <i className="fas fa-trash-alt"></i>
                    Delete My Account
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Settings;
