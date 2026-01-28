import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import Header from '../components/Header';
import LoadingSpinner from '../components/LoadingSpinner';
import { 
  getBusinessSettings, 
  updateBusinessSettings,
  getAIReceptionistStatus,
  toggleAIReceptionist
} from '../services/api';
import './Settings.css';

function Settings() {
  const queryClient = useQueryClient();
  const [formData, setFormData] = useState({});
  const [saveMessage, setSaveMessage] = useState('');

  const { data: settings, isLoading } = useQuery({
    queryKey: ['business-settings'],
    queryFn: async () => {
      const response = await getBusinessSettings();
      return response.data;
    },
    staleTime: 0, // Always fetch fresh data
    refetchOnMount: true,
  });

  // Update formData when settings data changes
  useEffect(() => {
    if (settings) {
      setFormData(settings);
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
    onSuccess: () => {
      queryClient.invalidateQueries(['business-settings']);
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

  const handleSubmit = (e) => {
    e.preventDefault();
    saveMutation.mutate(formData);
  };

  const handleToggleAI = () => {
    const newStatus = !aiStatus?.enabled;
    toggleMutation.mutate(newStatus);
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
            <Link to="/" className="btn btn-secondary">
              <i className="fas fa-arrow-left"></i>
              Back to Dashboard
            </Link>
            <Link to="/settings/developer" className="btn btn-secondary">
              <i className="fas fa-code"></i>
              Developer Settings
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
                  <div className="form-group">
                    <label htmlFor="business_phone">Business Phone *</label>
                    <input
                      type="tel"
                      id="business_phone"
                      name="business_phone"
                      value={formData.business_phone || ''}
                      onChange={handleChange}
                      required
                    />
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
                <h3>Business Logo</h3>
                <div className="logo-upload-section">
                  <div className="logo-preview">
                    {formData.logo_url ? (
                      <img src={formData.logo_url} alt="Business Logo" className="logo-image" />
                    ) : (
                      <div className="logo-placeholder">
                        <i className="fas fa-building"></i>
                        <span>No logo</span>
                      </div>
                    )}
                  </div>
                  <div className="logo-input">
                    <label htmlFor="logo_url">Logo URL</label>
                    <input
                      type="url"
                      id="logo_url"
                      name="logo_url"
                      value={formData.logo_url || ''}
                      onChange={handleChange}
                      placeholder="https://example.com/logo.png"
                    />
                    <small className="form-help">
                      Enter a URL to your company logo. The logo will appear in the header.
                    </small>
                  </div>
                </div>
              </div>

              <div className="form-section">
                <h3>Fallback Settings</h3>
                <div className="form-grid">
                  <div className="form-group full-width">
                    <label htmlFor="fallback_phone_number">Fallback Phone Number</label>
                    <input
                      type="tel"
                      id="fallback_phone_number"
                      name="fallback_phone_number"
                      value={formData.fallback_phone_number || ''}
                      onChange={handleChange}
                      placeholder="Number to forward calls when AI is disabled"
                    />
                    <small className="form-help">
                      When AI receptionist is disabled, calls will be forwarded to this number
                    </small>
                  </div>
                </div>
              </div>

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
    </div>
  );
}

export default Settings;
