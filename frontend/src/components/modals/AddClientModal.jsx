import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../../context/AuthContext';
import { createClient } from '../../services/api';
import Modal from './Modal';
import { useToast } from '../Toast';
import './AddClientModal.css';

function AddClientModal({ isOpen, onClose }) {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const { hasActiveSubscription } = useAuth();
  const isSubscriptionActive = hasActiveSubscription();
  const [formData, setFormData] = useState({
    name: '',
    phone: '',
    notes: ''
  });

  const mutation = useMutation({
    mutationFn: createClient,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      onClose();
      setFormData({ name: '', phone: '', notes: '' });
      addToast('Customer added successfully!', 'success');
    },
    onError: (error) => {
      addToast('Error adding customer: ' + (error.response?.data?.error || error.message), 'error');
    }
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!formData.name.trim()) {
      addToast('Please enter a customer name', 'warning');
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
    <Modal isOpen={isOpen} onClose={onClose} title="Add New Customer">
      {!isSubscriptionActive ? (
        <div className="subscription-required-message">
          <div className="subscription-required-content">
            <i className="fas fa-lock"></i>
            <h3>Subscription Required</h3>
            <p>Your trial has expired. Subscribe to continue adding customers.</p>
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
          <label className="form-label">Notes</label>
          <textarea
            name="notes"
            className="form-textarea"
            value={formData.notes}
            onChange={handleChange}
            rows="3"
            placeholder="Additional information about this customer"
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
            {mutation.isPending ? 'Adding...' : 'Add Customer'}
          </button>
        </div>
      </form>
      )}
    </Modal>
  );
}

export default AddClientModal;
