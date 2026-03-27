import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../../context/AuthContext';
import { 
  getServicesMenu, 
  createService,
  updateService,
  deleteService,
  getWorkers
} from '../../services/api';
import LoadingSpinner from '../LoadingSpinner';
import { useToast } from '../Toast';
import ImageUpload from '../ImageUpload';
import { formatPriceRange } from '../../utils/helpers';
import { DURATION_OPTIONS_GROUPED, formatDuration } from '../../utils/durationOptions';
import './ServicesTab.css';

function ServicesTab() {
  const { hasActiveSubscription } = useAuth();
  const isSubscriptionActive = hasActiveSubscription();
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [editingId, setEditingId] = useState(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [formData, setFormData] = useState({ 
    name: '', 
    price: '', 
    price_max: null,
    duration: '1440', 
    image_url: '', 
    workers_required: '1',
    worker_restrictions: { type: 'all', worker_ids: [] },
    requires_callout: false
  });
  const [deleteConfirm, setDeleteConfirm] = useState({ show: false, service: null });

  // Fetch workers for the worker restrictions selector
  const { data: workersData } = useQuery({
    queryKey: ['workers'],
    queryFn: async () => {
      const response = await getWorkers();
      return response.data;
    },
  });

  // API returns workers as array directly, not { workers: [...] }
  const workers = Array.isArray(workersData) ? workersData : (workersData?.workers || []);

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
      setFormData({ 
        name: '', 
        price: '', 
        price_max: null,
        duration: '1440', 
        image_url: '', 
        workers_required: '1',
        worker_restrictions: { type: 'all', worker_ids: [] },
        requires_callout: false
      });
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
    
    // Validate worker restrictions - if 'only' or 'except' is selected, must have workers
    const restrictionType = formData.worker_restrictions?.type;
    const hasWorkerIds = formData.worker_restrictions?.worker_ids?.length > 0;
    if ((restrictionType === 'only' || restrictionType === 'except') && !hasWorkerIds) {
      addToast('Please select at least one worker for the restriction', 'warning');
      return;
    }
    
    const restrictions = formData.worker_restrictions?.type === 'all' 
      ? null 
      : formData.worker_restrictions;
    
    createMutation.mutate({
      name: formData.name,
      price: Math.round((parseFloat(formData.price) || 0) * 100) / 100,
      price_max: formData.price_max && parseFloat(formData.price_max) > (parseFloat(formData.price) || 0) 
        ? Math.round(parseFloat(formData.price_max) * 100) / 100 
        : null,
      duration_minutes: parseInt(formData.duration) || 60,
      image_url: formData.image_url,
      workers_required: parseInt(formData.workers_required) || 1,
      worker_restrictions: restrictions,
      requires_callout: formData.requires_callout,
    });
  };

  const handleUpdate = (service) => {
    // Validate worker restrictions - if 'only' or 'except' is selected, must have workers
    const restrictionType = service.worker_restrictions?.type;
    const hasWorkerIds = service.worker_restrictions?.worker_ids?.length > 0;
    if ((restrictionType === 'only' || restrictionType === 'except') && !hasWorkerIds) {
      addToast('Please select at least one worker for the restriction', 'warning');
      return;
    }
    
    const restrictions = service.worker_restrictions?.type === 'all' 
      ? null 
      : service.worker_restrictions;
    
    updateMutation.mutate({
      id: service.id,
      data: {
        name: service.name,
        price: Math.round((parseFloat(service.price) || 0) * 100) / 100,
        price_max: service.price_max && parseFloat(service.price_max) > (parseFloat(service.price) || 0)
          ? Math.round(parseFloat(service.price_max) * 100) / 100 
          : null,
        duration_minutes: parseInt(service.duration_minutes) || 60,
        image_url: service.image_url,
        workers_required: parseInt(service.workers_required) || 1,
        worker_restrictions: restrictions,
        requires_callout: service.requires_callout || false,
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
              <div className="price-range-toggle-row">
                <button
                  type="button"
                  className={`price-range-toggle ${formData.price_max !== null && formData.price_max !== undefined ? 'active' : ''}`}
                  onClick={() => setFormData({ ...formData, price_max: formData.price_max !== null && formData.price_max !== undefined ? null : '' })}
                  role="switch"
                  aria-checked={formData.price_max !== null && formData.price_max !== undefined}
                >
                  <span className="price-range-toggle-slider" />
                </button>
                <span className="price-range-toggle-label">Price range</span>
              </div>
              {formData.price_max !== null && formData.price_max !== undefined && (
                <div className="price-max-row">
                  <div className="price-max-field">
                    <span className="price-max-label">to</span>
                    <input
                      type="number"
                      className="form-input"
                      value={formData.price_max}
                      onChange={(e) => setFormData({ ...formData, price_max: e.target.value })}
                      placeholder="Max price"
                      step="0.01"
                      min="0"
                      autoFocus
                    />
                  </div>
                </div>
              )}
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
              <div className="workers-input-wrapper">
                <button 
                  type="button" 
                  className="workers-btn"
                  onClick={() => setFormData({ ...formData, workers_required: Math.max(1, parseInt(formData.workers_required || 1) - 1).toString() })}
                  disabled={parseInt(formData.workers_required || 1) <= 1}
                >
                  <i className="fas fa-minus"></i>
                </button>
                <span className="workers-value">{formData.workers_required || 1}</span>
                <button 
                  type="button" 
                  className="workers-btn"
                  onClick={() => setFormData({ ...formData, workers_required: (parseInt(formData.workers_required || 1) + 1).toString() })}
                  disabled={parseInt(formData.workers_required || 1) >= 10}
                >
                  <i className="fas fa-plus"></i>
                </button>
              </div>
              <span className="form-hint">How many workers needed for this job</span>
            </div>
          </div>
          
          {/* Worker Restrictions */}
          <WorkerRestrictions
            restrictions={formData.worker_restrictions}
            onChange={(restrictions) => setFormData({ ...formData, worker_restrictions: restrictions })}
            workers={workers}
          />
          
          {/* Requires Callout Toggle */}
          <div className="callout-toggle-group">
            <label>Requires Initial Callout?</label>
            <div className="callout-toggle-row">
              <button
                type="button"
                className={`callout-toggle ${formData.requires_callout ? 'active' : ''}`}
                onClick={() => setFormData({ ...formData, requires_callout: !formData.requires_callout })}
                role="switch"
                aria-checked={formData.requires_callout}
              >
                <span className="callout-toggle-slider" />
              </button>
              <span className="callout-toggle-label">
                {formData.requires_callout 
                  ? 'Yes — AI will book a callout visit instead of the full job' 
                  : 'No — book the full job directly'}
              </span>
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
              workers={workers}
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

function WorkerRestrictions({ restrictions, onChange, workers }) {
  const type = restrictions?.type || 'all';
  const selectedIds = restrictions?.worker_ids || [];

  const handleTypeChange = (newType) => {
    onChange({ type: newType, worker_ids: newType === 'all' ? [] : selectedIds });
  };

  const toggleWorker = (workerId) => {
    const newIds = selectedIds.includes(workerId)
      ? selectedIds.filter(id => id !== workerId)
      : [...selectedIds, workerId];
    onChange({ type, worker_ids: newIds });
  };

  // If no workers, show a message
  if (!workers || workers.length === 0) {
    return (
      <div className="worker-restrictions">
        <label>Who Can Do This Job</label>
        <div className="no-workers-message">
          <i className="fas fa-info-circle"></i>
          <span>Add workers in the Workers tab to set job restrictions</span>
        </div>
      </div>
    );
  }

  return (
    <div className="worker-restrictions">
      <label>Who Can Do This Job</label>
      <div className="restriction-type-selector">
        <button
          type="button"
          className={`restriction-type-btn ${type === 'all' ? 'active' : ''}`}
          onClick={() => handleTypeChange('all')}
        >
          <i className="fas fa-users"></i>
          All Workers
        </button>
        <button
          type="button"
          className={`restriction-type-btn ${type === 'only' ? 'active' : ''}`}
          onClick={() => handleTypeChange('only')}
        >
          <i className="fas fa-user-check"></i>
          Only Selected
        </button>
        <button
          type="button"
          className={`restriction-type-btn ${type === 'except' ? 'active' : ''}`}
          onClick={() => handleTypeChange('except')}
        >
          <i className="fas fa-user-times"></i>
          All Except
        </button>
      </div>
      
      {type !== 'all' && (
        <div className="worker-selection">
          <span className="selection-hint">
            {type === 'only' 
              ? 'Select workers who CAN do this job:' 
              : 'Select workers who CANNOT do this job:'}
          </span>
          <div className="worker-chips">
            {workers.map(worker => (
              <button
                key={worker.id}
                type="button"
                className={`worker-chip ${selectedIds.includes(worker.id) ? 'selected' : ''}`}
                onClick={() => toggleWorker(worker.id)}
              >
                <i className={`fas ${selectedIds.includes(worker.id) ? 'fa-check' : 'fa-user'}`}></i>
                {worker.name}
              </button>
            ))}
          </div>
          {type !== 'all' && selectedIds.length === 0 && (
            <span className="selection-warning">
              <i className="fas fa-exclamation-circle"></i>
              Select at least one worker
            </span>
          )}
        </div>
      )}
    </div>
  );
}

function ServiceCard({ service, isEditing, onEdit, onSave, onCancel, onDelete, isPending, workers }) {
  const [editData, setEditData] = useState(service);
  const [imageError, setImageError] = useState(false);

  // Reset edit data when editing starts
  useEffect(() => {
    if (isEditing) {
      setEditData({
        ...service,
        worker_restrictions: service.worker_restrictions || { type: 'all', worker_ids: [] }
      });
    }
  }, [isEditing, service]);

  // Reset image error when service changes
  useEffect(() => {
    setImageError(false);
  }, [service.image_url]);

  const handleSave = () => {
    if (!editData.name?.trim()) return;
    onSave(editData);
  };

  // Get worker restriction summary for display
  const getRestrictionSummary = () => {
    const restrictions = service.worker_restrictions;
    if (!restrictions || restrictions.type === 'all') return null;
    
    const count = restrictions.worker_ids?.length || 0;
    if (restrictions.type === 'only') {
      return `${count} worker${count !== 1 ? 's' : ''} only`;
    } else {
      return `All except ${count}`;
    }
  };

  if (isEditing) {
    return (
      <div className="service-card editing">
        <div className="edit-form">
          <div className="form-group">
            <label>Service Name</label>
            <input
              type="text"
              className="form-input"
              value={editData.name || ''}
              onChange={(e) => setEditData({ ...editData, name: e.target.value })}
              placeholder="Service Name"
            />
          </div>
          <div className="edit-row">
            <div className="form-group">
              <label>Price (€)</label>
              <input
                type="number"
                className="form-input"
                value={editData.price || ''}
                onChange={(e) => setEditData({ ...editData, price: e.target.value })}
                placeholder="Price"
                step="0.01"
                min="0"
              />
              <div className="price-range-toggle-row">
                <button
                  type="button"
                  className={`price-range-toggle ${editData.price_max !== '' && editData.price_max !== null && editData.price_max !== undefined ? 'active' : ''}`}
                  onClick={() => setEditData({ ...editData, price_max: editData.price_max !== '' && editData.price_max !== null && editData.price_max !== undefined ? null : '' })}
                  role="switch"
                  aria-checked={editData.price_max !== '' && editData.price_max !== null && editData.price_max !== undefined}
                >
                  <span className="price-range-toggle-slider" />
                </button>
                <span className="price-range-toggle-label">Price range</span>
              </div>
              {editData.price_max !== '' && editData.price_max !== null && editData.price_max !== undefined && (
                <div className="price-max-row">
                  <div className="price-max-field">
                    <span className="price-max-label">to</span>
                    <input
                      type="number"
                      className="form-input"
                      value={editData.price_max || ''}
                      onChange={(e) => setEditData({ ...editData, price_max: e.target.value })}
                      placeholder="Max price"
                      step="0.01"
                      min="0"
                    />
                  </div>
                </div>
              )}
            </div>
            <div className="form-group">
              <label>Duration</label>
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
            </div>
            <div className="form-group">
              <label>Workers</label>
              <div className="workers-input-wrapper compact">
                <button 
                  type="button" 
                  className="workers-btn"
                  onClick={() => setEditData({ ...editData, workers_required: Math.max(1, (editData.workers_required || 1) - 1) })}
                  disabled={(editData.workers_required || 1) <= 1}
                >
                  <i className="fas fa-minus"></i>
                </button>
                <span className="workers-value">{editData.workers_required || 1}</span>
                <button 
                  type="button" 
                  className="workers-btn"
                  onClick={() => setEditData({ ...editData, workers_required: (editData.workers_required || 1) + 1 })}
                  disabled={(editData.workers_required || 1) >= 10}
                >
                  <i className="fas fa-plus"></i>
                </button>
              </div>
            </div>
          </div>
          
          <WorkerRestrictions
            restrictions={editData.worker_restrictions}
            onChange={(restrictions) => setEditData({ ...editData, worker_restrictions: restrictions })}
            workers={workers}
          />
          
          {/* Requires Callout Toggle */}
          <div className="callout-toggle-group">
            <label>Requires Initial Callout?</label>
            <div className="callout-toggle-row">
              <button
                type="button"
                className={`callout-toggle ${editData.requires_callout ? 'active' : ''}`}
                onClick={() => setEditData({ ...editData, requires_callout: !editData.requires_callout })}
                role="switch"
                aria-checked={editData.requires_callout}
              >
                <span className="callout-toggle-slider" />
              </button>
              <span className="callout-toggle-label">
                {editData.requires_callout 
                  ? 'Yes — AI will book a callout visit instead of the full job' 
                  : 'No — book the full job directly'}
              </span>
            </div>
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

  const restrictionSummary = getRestrictionSummary();

  return (
    <div className="service-card">
      <div className="service-image">
        {service.image_url && !imageError ? (
          <img 
            src={service.image_url} 
            alt={service.name}
            onError={() => setImageError(true)}
            loading="lazy"
          />
        ) : (
          <i className="fas fa-wrench"></i>
        )}
      </div>
      <div className="service-content">
        <h3 className="service-title">{service.name || 'Unnamed Service'}</h3>
        <div className="service-meta">
          {service.price > 0 && (
            <span className="meta-item price">{formatPriceRange(service.price, service.price_max)}</span>
          )}
          {(service.duration_minutes || service.duration) && (
            <span className="meta-item duration">
              <i className="fas fa-clock"></i> {formatDuration(service.duration_minutes || service.duration)}
            </span>
          )}
          <span className="meta-item workers" title="Workers required for this job">
            <i className="fas fa-user-hard-hat"></i> {service.workers_required || 1} worker{(service.workers_required || 1) !== 1 ? 's' : ''}
          </span>
          {restrictionSummary && (
            <span className="meta-item restriction" title="Worker restrictions">
              <i className="fas fa-user-lock"></i> {restrictionSummary}
            </span>
          )}
          {service.requires_callout && (
            <span className="meta-item callout-badge" title="Requires initial callout visit">
              <i className="fas fa-phone-alt"></i> Callout first
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
