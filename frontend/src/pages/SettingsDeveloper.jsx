import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import Header from '../components/Header';
import LoadingSpinner from '../components/LoadingSpinner';
import { getDeveloperSettings, updateDeveloperSettings } from '../services/api';
import './SettingsDeveloper.css';

function SettingsDeveloper() {
  const queryClient = useQueryClient();
  const [formData, setFormData] = useState({});
  const [saveMessage, setSaveMessage] = useState('');
  const [showSecrets, setShowSecrets] = useState({});

  const { data: settings, isLoading } = useQuery({
    queryKey: ['developer-settings'],
    queryFn: async () => {
      const response = await getDeveloperSettings();
      setFormData(response.data);
      return response.data;
    },
  });

  const saveMutation = useMutation({
    mutationFn: updateDeveloperSettings,
    onSuccess: () => {
      queryClient.invalidateQueries(['developer-settings']);
      setSaveMessage('Developer settings saved successfully!');
      setTimeout(() => setSaveMessage(''), 3000);
    },
    onError: () => {
      setSaveMessage('Error saving settings');
      setTimeout(() => setSaveMessage(''), 3000);
    },
  });

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    saveMutation.mutate(formData);
  };

  const toggleSecret = (field) => {
    setShowSecrets(prev => ({
      ...prev,
      [field]: !prev[field]
    }));
  };

  if (isLoading) {
    return (
      <div className="settings-developer-page">
        <Header title="Developer Settings" />
        <div className="container">
          <LoadingSpinner message="Loading developer settings..." />
        </div>
      </div>
    );
  }

  return (
    <div className="settings-developer-page">
      <Header title="Developer Settings" />
      <main className="settings-main">
        <div className="container">
          <div className="settings-header">
            <h1>Developer Settings</h1>
            <p className="settings-subtitle">Configure API keys and technical settings</p>
          </div>

          <div className="settings-nav">
            <Link to="/settings" className="btn btn-secondary">
              <i className="fas fa-arrow-left"></i>
              Back to Settings
            </Link>
          </div>

          <div className="warning-banner">
            <i className="fas fa-exclamation-triangle"></i>
            <div>
              <strong>Warning:</strong> These are sensitive settings. Changing them incorrectly may break your application.
            </div>
          </div>

          <div className="settings-card">
            <form onSubmit={handleSubmit}>
              <div className="form-section">
                <h3><i className="fas fa-phone"></i> Twilio Settings</h3>
                <div className="form-grid">
                  <div className="form-group">
                    <label htmlFor="twilio_account_sid">Account SID</label>
                    <div className="secret-input">
                      <input
                        type={showSecrets.twilio_account_sid ? 'text' : 'password'}
                        id="twilio_account_sid"
                        name="twilio_account_sid"
                        value={formData.twilio_account_sid || ''}
                        onChange={handleChange}
                      />
                      <button
                        type="button"
                        className="secret-toggle"
                        onClick={() => toggleSecret('twilio_account_sid')}
                      >
                        <i className={`fas fa-eye${showSecrets.twilio_account_sid ? '-slash' : ''}`}></i>
                      </button>
                    </div>
                  </div>
                  <div className="form-group">
                    <label htmlFor="twilio_auth_token">Auth Token</label>
                    <div className="secret-input">
                      <input
                        type={showSecrets.twilio_auth_token ? 'text' : 'password'}
                        id="twilio_auth_token"
                        name="twilio_auth_token"
                        value={formData.twilio_auth_token || ''}
                        onChange={handleChange}
                      />
                      <button
                        type="button"
                        className="secret-toggle"
                        onClick={() => toggleSecret('twilio_auth_token')}
                      >
                        <i className={`fas fa-eye${showSecrets.twilio_auth_token ? '-slash' : ''}`}></i>
                      </button>
                    </div>
                  </div>
                  <div className="form-group">
                    <label htmlFor="twilio_phone_number">Phone Number</label>
                    <input
                      type="tel"
                      id="twilio_phone_number"
                      name="twilio_phone_number"
                      value={formData.twilio_phone_number || ''}
                      onChange={handleChange}
                    />
                  </div>
                </div>
              </div>

              <div className="form-section">
                <h3><i className="fas fa-brain"></i> OpenAI Settings</h3>
                <div className="form-grid">
                  <div className="form-group full-width">
                    <label htmlFor="openai_api_key">API Key</label>
                    <div className="secret-input">
                      <input
                        type={showSecrets.openai_api_key ? 'text' : 'password'}
                        id="openai_api_key"
                        name="openai_api_key"
                        value={formData.openai_api_key || ''}
                        onChange={handleChange}
                      />
                      <button
                        type="button"
                        className="secret-toggle"
                        onClick={() => toggleSecret('openai_api_key')}
                      >
                        <i className={`fas fa-eye${showSecrets.openai_api_key ? '-slash' : ''}`}></i>
                      </button>
                    </div>
                  </div>
                  <div className="form-group">
                    <label htmlFor="openai_model">Model</label>
                    <select
                      id="openai_model"
                      name="openai_model"
                      value={formData.openai_model || 'gpt-4'}
                      onChange={handleChange}
                    >
                      <option value="gpt-4">GPT-4</option>
                      <option value="gpt-4-turbo">GPT-4 Turbo</option>
                      <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
                    </select>
                  </div>
                </div>
              </div>

              <div className="form-section">
                <h3><i className="fas fa-microphone"></i> Deepgram Settings</h3>
                <div className="form-grid">
                  <div className="form-group full-width">
                    <label htmlFor="deepgram_api_key">API Key</label>
                    <div className="secret-input">
                      <input
                        type={showSecrets.deepgram_api_key ? 'text' : 'password'}
                        id="deepgram_api_key"
                        name="deepgram_api_key"
                        value={formData.deepgram_api_key || ''}
                        onChange={handleChange}
                      />
                      <button
                        type="button"
                        className="secret-toggle"
                        onClick={() => toggleSecret('deepgram_api_key')}
                      >
                        <i className={`fas fa-eye${showSecrets.deepgram_api_key ? '-slash' : ''}`}></i>
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              <div className="form-section">
                <h3><i className="fas fa-calendar"></i> Google Calendar Settings</h3>
                <div className="form-grid">
                  <div className="form-group full-width">
                    <label htmlFor="google_calendar_id">Calendar ID</label>
                    <input
                      type="text"
                      id="google_calendar_id"
                      name="google_calendar_id"
                      value={formData.google_calendar_id || ''}
                      onChange={handleChange}
                      placeholder="your-calendar@group.calendar.google.com"
                    />
                    <small className="form-help">
                      Find this in your Google Calendar settings under "Integrate calendar"
                    </small>
                  </div>
                </div>
              </div>

              <div className="form-section">
                <h3><i className="fas fa-cog"></i> Other Settings</h3>
                <div className="form-grid">
                  <div className="form-group">
                    <label htmlFor="ws_public_url">WebSocket Public URL</label>
                    <input
                      type="url"
                      id="ws_public_url"
                      name="ws_public_url"
                      value={formData.ws_public_url || ''}
                      onChange={handleChange}
                      placeholder="wss://your-domain.com/media-stream"
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="reminder_method">Reminder Method</label>
                    <select
                      id="reminder_method"
                      name="reminder_method"
                      value={formData.reminder_method || 'email'}
                      onChange={handleChange}
                    >
                      <option value="email">Email</option>
                      <option value="sms">SMS</option>
                      <option value="both">Both</option>
                    </select>
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
                  {saveMutation.isPending ? 'Saving...' : 'Save Developer Settings'}
                </button>
              </div>
            </form>
          </div>

          <div className="info-card">
            <h3><i className="fas fa-info-circle"></i> Configuration Guide</h3>
            <div className="info-content">
              <div className="info-item">
                <strong>Twilio:</strong> Get credentials from <a href="https://console.twilio.com" target="_blank" rel="noopener noreferrer">console.twilio.com</a>
              </div>
              <div className="info-item">
                <strong>OpenAI:</strong> Create API key at <a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener noreferrer">platform.openai.com</a>
              </div>
              <div className="info-item">
                <strong>Deepgram:</strong> Sign up and get API key from <a href="https://console.deepgram.com" target="_blank" rel="noopener noreferrer">console.deepgram.com</a>
              </div>
              <div className="info-item">
                <strong>Google Calendar:</strong> Set up OAuth2 credentials in Google Cloud Console and download credentials.json
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

export default SettingsDeveloper;
