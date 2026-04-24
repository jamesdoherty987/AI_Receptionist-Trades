import { useState, useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import Header from '../components/Header';
import LoadingSpinner from '../components/LoadingSpinner';
import { getBusinessSettings, updateBusinessSettings, deleteAccount } from '../services/api';
import './Account.css';

function Account() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { user, checkAuth, logout } = useAuth();
  const [saveMessage, setSaveMessage] = useState('');
  const [ownerName, setOwnerName] = useState('');
  const [email, setEmail] = useState('');
  const [avatarPreview, setAvatarPreview] = useState(null);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteConfirmation, setDeleteConfirmation] = useState('');
  const [deleteError, setDeleteError] = useState('');

  const { data: settings, isLoading } = useQuery({
    queryKey: ['business-settings'],
    queryFn: async () => (await getBusinessSettings()).data,
    staleTime: 0,
  });

  useEffect(() => {
    if (settings) {
      setOwnerName(settings.owner_name || user?.owner_name || '');
      setEmail(settings.email || user?.email || '');
    }
  }, [settings, user]);

  const saveMutation = useMutation({
    mutationFn: updateBusinessSettings,
    onSuccess: async () => {
      queryClient.invalidateQueries({ queryKey: ['business-settings'] });
      await checkAuth();
      setSaveMessage('Profile updated successfully!');
      setTimeout(() => setSaveMessage(''), 3000);
    },
    onError: (error) => {
      setSaveMessage(error?.response?.data?.error || 'Error saving profile');
      setTimeout(() => setSaveMessage(''), 5000);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (confirmation) => deleteAccount(confirmation),
    onSuccess: () => {
      logout();
      navigate('/');
    },
    onError: (error) => {
      setDeleteError(error?.response?.data?.error || 'Failed to delete account');
    },
  });

  const handleSave = (e) => {
    e.preventDefault();
    const payload = { owner_name: ownerName };
    if (avatarPreview) {
      payload.logo_url = avatarPreview;
    }
    saveMutation.mutate(payload);
  };

  const handleAvatarChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      setSaveMessage('Image too large. Please use an image under 5MB.');
      setTimeout(() => setSaveMessage(''), 5000);
      return;
    }
    const reader = new FileReader();
    reader.onload = (ev) => setAvatarPreview(ev.target.result);
    reader.readAsDataURL(file);
  };

  const handleDeleteAccount = () => {
    setDeleteError('');
    if (deleteConfirmation.toLowerCase() !== 'delete account') {
      setDeleteError("Please type 'delete account' to confirm");
      return;
    }
    deleteMutation.mutate(deleteConfirmation);
  };

  if (isLoading) {
    return (
      <div className="account-page">
        <Header />
        <div className="container"><LoadingSpinner message="Loading account..." /></div>
      </div>
    );
  }

  return (
    <div className="account-page">
      <Header />
      <main className="account-main">
        <div className="container">
          <div className="account-header">
            <button className="btn btn-secondary" onClick={() => navigate('/dashboard')}>
              <i className="fas fa-arrow-left"></i> Back to Dashboard
            </button>
          </div>

          <div className="account-profile-card">
            <label className="account-avatar-large account-avatar-clickable" htmlFor="avatar-upload" title="Click to change profile picture">
              {(avatarPreview || settings?.logo_url) ? (
                <img src={avatarPreview || settings?.logo_url} alt="Profile" className="account-avatar-img" />
              ) : (
                ownerName?.charAt(0)?.toUpperCase() || 'U'
              )}
              <div className="account-avatar-overlay">
                <i className="fas fa-camera"></i>
              </div>
              <input type="file" id="avatar-upload" accept="image/*" onChange={handleAvatarChange} style={{ display: 'none' }} />
            </label>
            <div className="account-profile-info">
              <h1>{ownerName || 'Your Account'}</h1>
              <p className="account-email">{email}</p>
            </div>
          </div>

          {saveMessage && (
            <div className={`settings-message ${saveMessage.includes('Error') || saveMessage.includes('Failed') ? 'warning' : 'success'}`}>
              <i className={`fas ${saveMessage.includes('Error') || saveMessage.includes('Failed') ? 'fa-exclamation-circle' : 'fa-check-circle'}`}></i>
              {saveMessage}
            </div>
          )}

          {/* Profile Section */}
          <div className="account-section">
            <div className="account-section-header">
              <i className="fas fa-user"></i>
              <h2>Profile</h2>
            </div>
            <form onSubmit={handleSave}>
              <div className="account-form-grid">
                <div className="account-field">
                  <label htmlFor="owner_name">Full Name</label>
                  <input
                    type="text"
                    id="owner_name"
                    value={ownerName}
                    onChange={(e) => setOwnerName(e.target.value)}
                    placeholder="Your name"
                  />
                </div>
                <div className="account-field">
                  <label htmlFor="account_email">Email Address</label>
                  <input
                    type="email"
                    id="account_email"
                    value={email}
                    disabled
                    className="account-field-disabled"
                  />
                  <small className="account-field-hint">Email cannot be changed. Contact support if needed.</small>
                </div>
              </div>
              <div className="account-form-actions">
                <button type="submit" className="btn btn-primary" disabled={saveMutation.isPending}>
                  <i className={`fas ${saveMutation.isPending ? 'fa-spinner fa-spin' : 'fa-save'}`}></i>
                  {saveMutation.isPending ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </form>
          </div>

          {/* Quick Links */}
          <div className="account-section">
            <div className="account-section-header">
              <i className="fas fa-link"></i>
              <h2>Quick Links</h2>
            </div>
            <div className="account-quick-links">
              <button className="account-link-card" onClick={() => navigate('/settings')}>
                <i className="fas fa-building"></i>
                <div>
                  <span className="account-link-title">Business Settings</span>
                  <span className="account-link-desc">Business info, AI receptionist, integrations</span>
                </div>
                <i className="fas fa-chevron-right"></i>
              </button>
              <button className="account-link-card" onClick={() => navigate('/settings?tab=subscription')}>
                <i className="fas fa-credit-card"></i>
                <div>
                  <span className="account-link-title">Subscription & Billing</span>
                  <span className="account-link-desc">Manage your plan and payment method</span>
                </div>
                <i className="fas fa-chevron-right"></i>
              </button>
            </div>
          </div>

          {/* Danger Zone */}
          <div className="account-section account-danger-zone">
            <div className="account-section-header">
              <i className="fas fa-exclamation-triangle"></i>
              <h2>Danger Zone</h2>
            </div>
            <p className="account-danger-desc">
              Permanently delete your account and all associated data. This action cannot be undone.
            </p>
            <button type="button" className="btn btn-danger" onClick={() => setShowDeleteModal(true)}>
              <i className="fas fa-trash-alt"></i> Delete Account
            </button>
          </div>
        </div>
      </main>

      {/* Delete Account Modal */}
      {showDeleteModal && (
        <div className="modal-overlay" onClick={() => { setShowDeleteModal(false); setDeleteConfirmation(''); setDeleteError(''); }}>
          <div className="modal-content delete-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2><i className="fas fa-exclamation-triangle" style={{ color: '#dc2626', marginRight: '10px' }}></i>Delete Account</h2>
              <button className="modal-close" onClick={() => { setShowDeleteModal(false); setDeleteConfirmation(''); setDeleteError(''); }}>
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
                  <li>All employees and services</li>
                  <li>Your subscription (if active)</li>
                </ul>
              </div>
              <div className="delete-confirm-input">
                <label>Type <strong>delete account</strong> to confirm:</label>
                <input type="text" value={deleteConfirmation} onChange={(e) => setDeleteConfirmation(e.target.value)} placeholder="delete account" autoComplete="off" />
              </div>
              {deleteError && <div className="delete-error"><i className="fas fa-exclamation-circle"></i>{deleteError}</div>}
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => { setShowDeleteModal(false); setDeleteConfirmation(''); setDeleteError(''); }}>Cancel</button>
              <button className="btn btn-danger" onClick={handleDeleteAccount} disabled={deleteMutation.isPending || deleteConfirmation.toLowerCase() !== 'delete account'}>
                {deleteMutation.isPending ? <><i className="fas fa-spinner fa-spin"></i> Deleting...</> : <><i className="fas fa-trash-alt"></i> Delete My Account</>}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Account;
