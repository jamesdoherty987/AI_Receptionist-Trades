import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../../context/AuthContext';
import { 
  getServicesMenu, 
  createService,
  updateService,
  deleteService
} from '../../services/api';
import LoadingSpinner from '../LoadingSpinner';
import { useToast } from '../Toast';
import ImageUpload from '../ImageUpload';
import { formatCurrency } from '../../utils/helpers';
import { DURATION_OPTIONS_GROUPED, formatDuration } from '../../utils/durationOptions';
import './ServicesTab.css';

function ServicesTab() {
  const { hasActiveSubscription } = useAuth();
  const isSubscriptionActive = hasActiveSubscription();
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [editingId, setEditingId] = useState(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [formData, setFormData] = useState({ name: '', price: '', duration: '1440', image_url: '', workers_required: '1' });
  const [deleteConfirm, setDeleteConfirm] = useState({ show: false, service: null });

  // Handle escape key to close delete confirmation
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && deleteConfirm.show) {
        setDeleteConfirm({ show: false, service: null });
      }
    };
    if (deleteConfirm.show) {
      document.addEventListener('keydown', handleEscape);
    }
    return () => document.removeEventListener('keydown', handleEscape);
  }, [deleteConfirm.show]);

  const handleAddClick = () => {
    if (!isSubscriptionActive) {
      addToast('You need an active subscription to add services', 'warning');
      return;
    }
    setShowAddForm(!showAddForm);
  };

  const { data: menu, isLoading } = useQuery({
    queryKey: ['services-menu'],
    queryFn: async () => {
      const response = await getServicesMenu();
      return response.data;
    },
  });

  const createMutation = useMutation({
    mutationFn: createService,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['services-menu'] });
      addToast('Service added!', 'success');
      setShowAddForm(false);
      setFormData({ name: '', price: '', duration: '1440', image_url: '', workers_required: '1' });
    },
    onError: () => addToast('Failed to add service', 'error'),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => updateService(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['services-menu'] });
      addToast('Service updated!', 'success');
      setEditingId(null);
    },
    onError: () => addToast('Failed to update service', 'error'),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteService,
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['services-menu'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      const jobsAffected = response.data?.jobs_affected || 0;
      addToast(`Service deleted${jobsAffected > 0 ? ` (${jobsAffected} job${jobsAffected !== 1 ? 's' : ''} used this service)` : ''}`, 'success');
      setDeleteConfirm({ show: false, service: null });
    },
    onError: () => {
      setDeleteConfirm({ show: false, service: null });
      addToast('Failed to delete service', 'error');
    },
  });


  const handleSubmit = (e) => {
    e.preventDefault();
    if (!formData.name.trim()) return;
    createMutation.mutate({
      name: formData.name,
      price: parseFloat(formData.price) || 0,
      duration_minutes: parseInt(formData.duration) || 60,
      image_url: formData.image_url,
      workers_required: parseInt(formData.workers_required) || 1,
    });
  };

  const handleUpdate = (service) => {
    updateMutation.mutate({
      id: service.id,
      data: {
        name: service.name,
        price: parseFloat(service.price) || 0,
        duration_minutes: parseInt(service.duration_minutes) || 60,
        image_url: service.image_url,
        workers_required: parseInt(service.workers_required) || 1,
      },
    });
  };

  const handleDelete = (service) => {
    setDeleteConfirm({ show: true, service });
  };

  const confirmDelete = () => {
    if (deleteConfirm.service) {
      deleteMutation.mutate(deleteConfirm.service.id);
    }
  };

  const startEdit = (service) => {
    setEditingId(service.id);
  };

  if (isLoading) {
    return <LoadingSpinner message="Loading services..." />;
  }

  const services = menu?.services || [];

  return (
    <div className="services-tab">
      <div className="services-header">
        <div>
          <h2>Services</h2>
          <p className="services-subtitle">Manage your services and pricing</p>
        </div>
        <div className="services-controls">
          <button 
            className="btn btn-primary"
            onClick={handleAddClick}
          >
            <i className={`fas ${isSubscriptionActive ? 'fa-plus' : 'fa-lock'}`}></i> Add Service
          </button>
        </div>
      </div>

      {showAddForm && (
        <form className="service-form-card" onSubmit={handleSubmit}>
          <h3>New Service</h3>
          <div className="form-grid">
            <div className="form-group form-group-wide">
              <label>Service Name *</label>
              <input
                type="text"
                className="form-input"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="e.g., Emergency Plumbing"
                required
              />
            </div>
            <div className="form-group">
              <label>Price (€)</label>
              <input
                type="number"
                className="form-input"
                value={formData.price}
                onChange={(e) => setFormData({ ...formData, price: e.target.value })}
                placeholder="0.00"
                step="0.01"
                min="0"
              />
            </div>
            <div className="form-group">
              <label>Duration</label>
              <select
                className="form-input"
                value={formData.duration}
                onChange={(e) => setFormData({ ...formData, duration: e.target.value })}
              >
                {Object.entries(DURATION_OPTIONS_GROUPED).map(([group, options]) => (
                  <optgroup key={group} label={group}>
                    {options.map((opt) => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label>Workers Required</label>
              <input
                type="number"
                className="form-input"
                value={formData.workers_required}
                onChange={(e) => setFormData({ ...formData, workers_required: e.target.value })}
                min="1"
                max="10"
              />
            </div>
          </div>
          <div className="form-group">
            <label>Image (optional)</label>
            <ImageUpload
              value={formData.image_url}
              onChange={(value) => setFormData({ ...formData, image_url: value })}
              placeholder="Upload Image"
            />
          </div>
          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={() => setShowAddForm(false)}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={createMutation.isPending}>
              {createMutation.isPending ? 'Adding...' : 'Add Service'}
            </button>
          </div>
        </form>
      )}

      {services.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">🔧</div>
          <p>No services yet</p>
          <button 
            className="btn btn-primary" 
            onClick={handleAddClick}
          >
            Add Your First Service
          </button>
        </div>
      ) : (
        <div className="services-list">
          {services.map((service) => (
            <ServiceCard
              key={service.id}
              service={service}
              isEditing={editingId === service.id}
              onEdit={() => startEdit(service)}
              onSave={handleUpdate}
              onCancel={() => setEditingId(null)}
              onDelete={() => handleDelete(service)}
              isPending={updateMutation.isPending || deleteMutation.isPending}
            />
          ))}
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      {deleteConfirm.show && deleteConfirm.service && (
        <div className="delete-confirm-overlay">
          <div className="delete-confirm-dialog">
            <div className="delete-confirm-icon">
              <i className="fas fa-exclamation-triangle"></i>
            </div>
            <h3>Delete Service?</h3>
            <p className="delete-warning">
              This will permanently delete <strong>{deleteConfirm.service.name}</strong>.
            </p>
            <p className="delete-cascade-warning">
              <i className="fas fa-info-circle"></i>
              Jobs using this service will keep their service type but the service will no longer be available for new bookings.
            </p>
            <div className="delete-confirm-actions">
              <button className="btn btn-secondary" onClick={() => setDeleteConfirm({ show: false, service: null })}>
                Cancel
              </button>
              <button 
                className="btn btn-danger" 
                onClick={confirmDelete}
                disabled={deleteMutation.isPending}
              >
                {deleteMutation.isPending ? 'Deleting...' : 'Delete Service'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


function ServiceCard({ service, isEditing, onEdit, onSave, onCancel, onDelete, isPending }) {
  const [editData, setEditData] = useState(service);

  // Reset edit data when editing starts
  useEffect(() => {
    if (isEditing) {
      setEditData(service);
    }
  }, [isEditing, service]);

  const handleSave = () => {
    if (!editData.name?.trim()) return;
    onSave(editData);
  };

  if (isEditing) {
    return (
      <div className="service-card editing">
        <div className="edit-form">
          <input
            type="text"
            className="form-input"
            value={editData.name || ''}
            onChange={(e) => setEditData({ ...editData, name: e.target.value })}
            placeholder="Service Name"
          />
          <div className="edit-row">
            <input
              type="number"
              className="form-input"
              value={editData.price || ''}
              onChange={(e) => setEditData({ ...editData, price: e.target.value })}
              placeholder="Price"
              step="0.01"
              min="0"
            />
            <select
              className="form-input"
              value={editData.duration_minutes || 60}
              onChange={(e) => setEditData({ ...editData, duration_minutes: parseInt(e.target.value) })}
            >
              {Object.entries(DURATION_OPTIONS_GROUPED).map(([group, options]) => (
                <optgroup key={group} label={group}>
                  {options.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </optgroup>
              ))}
            </select>
            <input
              type="number"
              className="form-input"
              value={editData.workers_required || 1}
              onChange={(e) => setEditData({ ...editData, workers_required: parseInt(e.target.value) || 1 })}
              placeholder="Workers"
              min="1"
              max="10"
              title="Workers required"
            />
          </div>
          <ImageUpload
            value={editData.image_url || ''}
            onChange={(value) => setEditData({ ...editData, image_url: value })}
            placeholder="Upload Image"
          />
          <div className="edit-actions">
            <button type="button" className="btn btn-secondary btn-sm" onClick={onCancel}>Cancel</button>
            <button type="button" className="btn btn-primary btn-sm" onClick={handleSave} disabled={isPending || !editData.name?.trim()}>
              {isPending ? 'Saving...' : 'Save'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="service-card">
      <div className="service-image">
        {service.image_url ? (
          <img src={service.image_url} alt={service.name} />
        ) : (
          <i className="fas fa-wrench"></i>
        )}
      </div>
      <div className="service-content">
        <h3 className="service-title">{service.name || 'Unnamed Service'}</h3>
        <div className="service-meta">
          {service.price > 0 && (
            <span className="meta-item price">{formatCurrency(service.price)}</span>
          )}
          {(service.duration_minutes || service.duration) && (
            <span className="meta-item duration">
              <i className="fas fa-clock"></i> {formatDuration(service.duration_minutes || service.duration)}
            </span>
          )}
          {service.workers_required > 1 && (
            <span className="meta-item workers">
              <i className="fas fa-users"></i> {service.workers_required} workers
            </span>
          )}
        </div>
      </div>
      <div className="service-actions">
        <button type="button" className="btn-icon" onClick={onEdit} title="Edit" aria-label="Edit service">
          <i className="fas fa-edit"></i>
        </button>
        <button type="button" className="btn-icon danger" onClick={onDelete} title="Delete" aria-label="Delete service" disabled={isPending}>
          <i className="fas fa-trash"></i>
        </button>
      </div>
    </div>
  );
}

export default ServicesTab;
