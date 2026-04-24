import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { createClient, employeeCreateClient } from '../../services/api';
import Modal from './Modal';
import { useToast } from '../Toast';
import HelpTooltip from '../HelpTooltip';
import './AddClientModal.css';

function AddClientModal({ isOpen, onClose, employeeMode = false }) {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [formData, setFormData] = useState({
    name: '',
    phone: '',
    email: '',
    address: '',
    eircode: '',
    notes: ''
  });

  const mutation = useMutation({
    mutationFn: employeeMode ? employeeCreateClient : createClient,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      onClose();
      setFormData({ name: '', phone: '', email: '', address: '', eircode: '', notes: '' });
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
            placeholder="customer@example.com"
          />
          <small style={{ fontSize: '0.72rem', color: '#94a3b8', marginTop: '0.2rem', display: 'block' }}>
            Quotes and invoices will be sent via email when available, SMS as fallback.
          </small>
        </div>

        <div className="form-group">
          <label className="form-label">Address</label>
          <input
            type="text"
            name="address"
            className="form-input"
            value={formData.address}
            onChange={handleChange}
            placeholder="Full address"
          />
        </div>

        <div className="form-group">
          <label className="form-label">Eircode</label>
          <input
            type="text"
            name="eircode"
            className="form-input"
            value={formData.eircode}
            onChange={handleChange}
            placeholder="e.g. V94 X2Y3"
          />
        </div>

        <div className="form-group">
          <label className="form-label">Notes <HelpTooltip text="Any extra details about this customer — access codes, preferences, or things your team should know." /></label>
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
    </Modal>
  );
}

export default AddClientModal;
