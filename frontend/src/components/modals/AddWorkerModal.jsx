import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../../context/AuthContext';
import { createWorker } from '../../services/api';
import Modal from './Modal';
import { useToast } from '../Toast';
import ImageUpload from '../ImageUpload';

function AddWorkerModal({ isOpen, onClose }) {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const { hasActiveSubscription } = useAuth();
  const isSubscriptionActive = hasActiveSubscription();
  const [formData, setFormData] = useState({
    name: '',
    phone: '',
    email: '',
    specialty: '',
    image_url: '',
    weekly_hours_expected: 40.0
  });

  const mutation = useMutation({
    mutationFn: createWorker,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['workers'] });
      onClose();
      setFormData({ name: '', phone: '', email: '', specialty: '', image_url: '', weekly_hours_expected: 40.0 });
      addToast('Worker added successfully!', 'success');
    },
    onError: (error) => {
      addToast('Error adding worker: ' + (error.response?.data?.error || error.message), 'error');
    }
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!formData.name.trim()) {
      addToast('Please enter a worker name', 'warning');
      return;
    }
    mutation.mutate(formData);
  };

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Add New Worker">
      {!isSubscriptionActive ? (
        <div className="subscription-required-message" style={{ padding: '3rem 2rem', textAlign: 'center' }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem' }}>
            <i className="fas fa-lock" style={{ fontSize: '3rem', color: '#f59e0b' }}></i>
            <h3 style={{ margin: 0, fontSize: '1.25rem', color: '#1f2937' }}>Subscription Required</h3>
            <p style={{ margin: 0, color: '#6b7280', maxWidth: '300px' }}>Your trial has expired. Subscribe to continue adding workers.</p>
            <Link to="/settings?tab=subscription" className="btn btn-primary" onClick={onClose}>
              <i className="fas fa-credit-card"></i> Subscribe Now
            </Link>
          </div>
        </div>
      ) : (
      <form onSubmit={handleSubmit} className="form">
        <div className="form-group">
          <label className="form-label">Name *</label>
          <input
            type="text"
            name="name"
            className="form-input"
            value={formData.name}
            onChange={handleChange}
            required
          />
        </div>

        <div className="form-group">
          <label className="form-label">Phone</label>
          <input
            type="tel"
            name="phone"
            className="form-input"
            value={formData.phone}
            onChange={handleChange}
            placeholder="+353..."
          />
        </div>

        <div className="form-group">
          <label className="form-label">Email</label>
          <input
            type="email"
            name="email"
            className="form-input"
            value={formData.email}
            onChange={handleChange}
          />
        </div>

        <div className="form-group">
          <label className="form-label">Trade Specialty</label>
          <input
            type="text"
            name="specialty"
            className="form-input"
            value={formData.specialty}
            onChange={handleChange}
            placeholder="e.g., Plumber, Electrician, Carpenter"
          />
        </div>

        <div className="form-group">
          <label className="form-label">Profile Picture (optional)</label>
          <ImageUpload
            value={formData.image_url}
            onChange={(value) => setFormData({ ...formData, image_url: value })}
            placeholder="Upload Profile Picture"
          />
        </div>

        <div className="form-group">
          <label className="form-label">Expected Weekly Hours</label>
          <input
            type="number"
            name="weekly_hours_expected"
            className="form-input"
            value={formData.weekly_hours_expected}
            onChange={(e) => setFormData({ ...formData, weekly_hours_expected: parseFloat(e.target.value) || 40.0 })}
            placeholder="40"
            min="0"
            max="168"
            step="0.5"
          />
        </div>

        <div className="form-actions">
          <button 
            type="button" 
            className="btn btn-secondary"
            onClick={onClose}
            disabled={mutation.isPending}
          >
            Cancel
          </button>
          <button 
            type="submit" 
            className="btn btn-primary"
            disabled={mutation.isPending}
          >
            {mutation.isPending ? 'Adding...' : 'Add Worker'}
          </button>
        </div>
      </form>
      )}
    </Modal>
  );
}

export default AddWorkerModal;
