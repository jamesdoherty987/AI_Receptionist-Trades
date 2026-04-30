import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { createEmployee } from '../../services/api';
import Modal from './Modal';
import { useToast } from '../Toast';
import { invalidateRelated } from '../../utils/queryInvalidation';
import ImageUpload from '../ImageUpload';
import HelpTooltip from '../HelpTooltip';

function AddEmployeeModal({ isOpen, onClose }) {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [formData, setFormData] = useState({
    name: '',
    phone: '',
    email: '',
    specialty: '',
    image_url: ''
  });

  const mutation = useMutation({
    mutationFn: createEmployee,
    onSuccess: () => {
      invalidateRelated(queryClient, 'employees');
      onClose();
      setFormData({ name: '', phone: '', email: '', specialty: '', image_url: '' });
      addToast('Employee added successfully!', 'success');
    },
    onError: (error) => {
      addToast('Error adding employee: ' + (error.response?.data?.error || error.message), 'error');
    }
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!formData.name.trim()) {
      addToast('Please enter an employee name', 'warning');
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
    <Modal isOpen={isOpen} onClose={onClose} title="Add New Employee">
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
          <label className="form-label">Trade Specialty <span style={{ color: 'var(--text-tertiary)', fontWeight: 400, fontSize: '0.85rem' }}>(optional)</span> <HelpTooltip text="The employee's main skill or trade. Used to match them with relevant jobs." /></label>
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
            {mutation.isPending ? 'Adding...' : 'Add Employee'}
          </button>
        </div>
      </form>
    </Modal>
  );
}

export default AddEmployeeModal;
