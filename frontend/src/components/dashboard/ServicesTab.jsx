import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../../context/AuthContext';
import { 
  getServicesMenu, 
  createService,
  updateService,
  deleteService,
  getWorkers,
  getPackages,
  createPackage,
  updatePackage,
  deletePackage
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
    requires_callout: false,
    package_only: false
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
        requires_callout: false,
        package_only: false
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
      package_only: formData.package_only,
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
        package_only: service.package_only || false,
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
              {formData.price_max !== null && formData.price_max !== undefined && (
                <span className="price-from-label">from</span>
              )}
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

          {/* Package Only Toggle */}
          <div className="callout-toggle-group">
            <label>Package Only?</label>
            <div className="callout-toggle-row">
              <button
                type="button"
                className={`callout-toggle ${formData.package_only ? 'active' : ''}`}
                onClick={() => setFormData({ ...formData, package_only: !formData.package_only })}
                role="switch"
                aria-checked={formData.package_only}
              >
                <span className="callout-toggle-slider" />
              </button>
              <span className="callout-toggle-label">
                {formData.package_only 
                  ? 'Yes — only available as part of a package' 
                  : 'No — available as a standalone service'}
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

      <PackagesSection services={services} isSubscriptionActive={isSubscriptionActive} />
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
              {editData.price_max !== '' && editData.price_max !== null && editData.price_max !== undefined && (
                <span className="price-from-label">from</span>
              )}
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

          {/* Package Only Toggle */}
          <div className="callout-toggle-group">
            <label>Package Only?</label>
            <div className="callout-toggle-row">
              <button
                type="button"
                className={`callout-toggle ${editData.package_only ? 'active' : ''}`}
                onClick={() => setEditData({ ...editData, package_only: !editData.package_only })}
                role="switch"
                aria-checked={editData.package_only}
              >
                <span className="callout-toggle-slider" />
              </button>
              <span className="callout-toggle-label">
                {editData.package_only 
                  ? 'Yes — only available as part of a package' 
                  : 'No — available as a standalone service'}
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
          {service.package_only && (
            <span className="meta-item callout-badge" title="Only available as part of a package">
              <i className="fas fa-box"></i> Package only
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

function PackagesSection({ services, isSubscriptionActive }) {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingPkgId, setEditingPkgId] = useState(null);
  const [deletePkgConfirm, setDeletePkgConfirm] = useState({ show: false, pkg: null });
  const [pkgFormData, setPkgFormData] = useState({
    name: '',
    description: '',
    selectedServiceIds: [],
    price_override: null,
    price_max_override: null,
    use_when_uncertain: false,
  });

  const { data: packagesData } = useQuery({
    queryKey: ['packages'],
    queryFn: async () => {
      const response = await getPackages();
      return response.data;
    },
  });

  const packages = packagesData?.packages || packagesData || [];

  // Handle escape key to close delete confirmation
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && deletePkgConfirm.show) {
        setDeletePkgConfirm({ show: false, pkg: null });
      }
    };
    if (deletePkgConfirm.show) {
      document.addEventListener('keydown', handleEscape);
    }
    return () => document.removeEventListener('keydown', handleEscape);
  }, [deletePkgConfirm.show]);

  const createPkgMutation = useMutation({
    mutationFn: createPackage,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['packages'] });
      addToast('Package added!', 'success');
      setShowAddForm(false);
      resetForm();
    },
    onError: (err) => addToast(err?.response?.data?.error || 'Failed to add package', 'error'),
  });

  const updatePkgMutation = useMutation({
    mutationFn: ({ id, data }) => updatePackage(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['packages'] });
      addToast('Package updated!', 'success');
      setEditingPkgId(null);
    },
    onError: (err) => addToast(err?.response?.data?.error || 'Failed to update package', 'error'),
  });

  const deletePkgMutation = useMutation({
    mutationFn: deletePackage,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['packages'] });
      addToast('Package deleted!', 'success');
      setDeletePkgConfirm({ show: false, pkg: null });
    },
    onError: () => {
      setDeletePkgConfirm({ show: false, pkg: null });
      addToast('Failed to delete package', 'error');
    },
  });

  const resetForm = () => {
    setPkgFormData({
      name: '',
      description: '',
      selectedServiceIds: [],
      price_override: null,
      price_max_override: null,
      use_when_uncertain: false,
    });
  };

  const handleAddClick = () => {
    if (!isSubscriptionActive) {
      addToast('You need an active subscription to add packages', 'warning');
      return;
    }
    setShowAddForm(!showAddForm);
    if (showAddForm) resetForm();
  };

  const buildServicesPayload = (selectedIds) => {
    return selectedIds.map((id, idx) => ({ service_id: id, sort_order: idx }));
  };

  const handlePkgSubmit = (e) => {
    e.preventDefault();
    if (!pkgFormData.name.trim()) return;
    if (pkgFormData.selectedServiceIds.length < 2) {
      addToast('A package needs at least 2 services', 'warning');
      return;
    }

    const payload = {
      name: pkgFormData.name,
      description: pkgFormData.description || '',
      services: buildServicesPayload(pkgFormData.selectedServiceIds),
      use_when_uncertain: pkgFormData.use_when_uncertain,
    };

    if (pkgFormData.price_override !== null && pkgFormData.price_override !== undefined && pkgFormData.price_override !== '') {
      payload.price_override = Math.round((parseFloat(pkgFormData.price_override) || 0) * 100) / 100;
      if (pkgFormData.price_max_override !== null && pkgFormData.price_max_override !== undefined && pkgFormData.price_max_override !== '') {
        payload.price_max_override = Math.round((parseFloat(pkgFormData.price_max_override) || 0) * 100) / 100;
      }
    }

    createPkgMutation.mutate(payload);
  };

  const handlePkgUpdate = (pkgData) => {
    if (!pkgData.name?.trim()) return;
    if (pkgData.selectedServiceIds.length < 2) {
      addToast('A package needs at least 2 services', 'warning');
      return;
    }

    const payload = {
      name: pkgData.name,
      description: pkgData.description || '',
      services: buildServicesPayload(pkgData.selectedServiceIds),
      use_when_uncertain: pkgData.use_when_uncertain,
    };

    if (pkgData.price_override !== null && pkgData.price_override !== undefined && pkgData.price_override !== '') {
      payload.price_override = Math.round((parseFloat(pkgData.price_override) || 0) * 100) / 100;
      if (pkgData.price_max_override !== null && pkgData.price_max_override !== undefined && pkgData.price_max_override !== '') {
        payload.price_max_override = Math.round((parseFloat(pkgData.price_max_override) || 0) * 100) / 100;
      }
    } else {
      payload.price_override = null;
      payload.price_max_override = null;
    }

    updatePkgMutation.mutate({ id: pkgData.id, data: payload });
  };

  const confirmDeletePkg = () => {
    if (deletePkgConfirm.pkg) {
      deletePkgMutation.mutate(deletePkgConfirm.pkg.id);
    }
  };

  const toggleServiceSelection = (serviceId) => {
    setPkgFormData(prev => {
      const ids = prev.selectedServiceIds.includes(serviceId)
        ? prev.selectedServiceIds.filter(id => id !== serviceId)
        : [...prev.selectedServiceIds, serviceId];
      return { ...prev, selectedServiceIds: ids };
    });
  };

  const moveService = (index, direction) => {
    setPkgFormData(prev => {
      const ids = [...prev.selectedServiceIds];
      const newIndex = index + direction;
      if (newIndex < 0 || newIndex >= ids.length) return prev;
      [ids[index], ids[newIndex]] = [ids[newIndex], ids[index]];
      return { ...prev, selectedServiceIds: ids };
    });
  };

  // Calculate totals from selected services
  const getSelectedServiceDetails = (selectedIds) => {
    const selected = selectedIds
      .map(id => services.find(s => s.id === id))
      .filter(Boolean);
    const totalDuration = selected.reduce((sum, s) => sum + (s.duration_minutes || 0), 0);
    const totalPrice = selected.reduce((sum, s) => sum + (parseFloat(s.price) || 0), 0);
    const totalPriceMax = selected.reduce((sum, s) => sum + (parseFloat(s.price_max) || parseFloat(s.price) || 0), 0);
    return { selected, totalDuration, totalPrice, totalPriceMax };
  };

  return (
    <div className="packages-section">
      <div className="packages-header">
        <div>
          <h2>📦 Packages</h2>
          <p className="services-subtitle">Bundle multiple services into ordered sequences</p>
        </div>
        <div className="services-controls">
          <button className="btn btn-primary" onClick={handleAddClick}>
            <i className={`fas ${isSubscriptionActive ? 'fa-plus' : 'fa-lock'}`}></i> Add Package
          </button>
        </div>
      </div>

      {showAddForm && (
        <PackageForm
          formData={pkgFormData}
          setFormData={setPkgFormData}
          services={services}
          onSubmit={handlePkgSubmit}
          onCancel={() => { setShowAddForm(false); resetForm(); }}
          isPending={createPkgMutation.isPending}
          toggleServiceSelection={toggleServiceSelection}
          moveService={moveService}
          getSelectedServiceDetails={getSelectedServiceDetails}
          isNew
        />
      )}

      {packages.length === 0 && !showAddForm ? (
        <div className="empty-state">
          <div className="empty-icon">📦</div>
          <p>No packages yet</p>
          <button className="btn btn-primary" onClick={handleAddClick}>
            Create Your First Package
          </button>
        </div>
      ) : (
        <div className="services-list">
          {packages.map((pkg) => (
            <PackageCard
              key={pkg.id}
              pkg={pkg}
              services={services}
              isEditing={editingPkgId === pkg.id}
              onEdit={() => setEditingPkgId(pkg.id)}
              onSave={handlePkgUpdate}
              onCancel={() => setEditingPkgId(null)}
              onDelete={() => setDeletePkgConfirm({ show: true, pkg })}
              isPending={updatePkgMutation.isPending || deletePkgMutation.isPending}
              getSelectedServiceDetails={getSelectedServiceDetails}
            />
          ))}
        </div>
      )}

      {/* Package Delete Confirmation Dialog */}
      {deletePkgConfirm.show && deletePkgConfirm.pkg && (
        <div className="delete-confirm-overlay">
          <div className="delete-confirm-dialog">
            <div className="delete-confirm-icon">
              <i className="fas fa-exclamation-triangle"></i>
            </div>
            <h3>Delete Package?</h3>
            <p className="delete-warning">
              This will permanently delete <strong>{deletePkgConfirm.pkg.name}</strong>.
            </p>
            <p className="delete-cascade-warning">
              <i className="fas fa-info-circle"></i>
              The individual services in this package will not be affected.
            </p>
            <div className="delete-confirm-actions">
              <button className="btn btn-secondary" onClick={() => setDeletePkgConfirm({ show: false, pkg: null })}>
                Cancel
              </button>
              <button
                className="btn btn-danger"
                onClick={confirmDeletePkg}
                disabled={deletePkgMutation.isPending}
              >
                {deletePkgMutation.isPending ? 'Deleting...' : 'Delete Package'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function PackageForm({ formData, setFormData, services, onSubmit, onCancel, isPending, toggleServiceSelection, moveService, getSelectedServiceDetails, isNew }) {
  const { selected, totalDuration, totalPrice, totalPriceMax } = getSelectedServiceDetails(formData.selectedServiceIds);

  return (
    <form className="package-form-card" onSubmit={onSubmit}>
      <h3>{isNew ? 'New Package' : 'Edit Package'}</h3>
      <div className="form-grid">
        <div className="form-group form-group-wide">
          <label>Package Name *</label>
          <input
            type="text"
            className="form-input"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            placeholder="e.g., Roof Leak Investigation"
            required
          />
        </div>
        <div className="form-group form-group-wide">
          <label>Description (optional)</label>
          <textarea
            className="form-input"
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            placeholder="Describe what this package covers"
            rows={2}
          />
        </div>
      </div>

      {/* Service Picker */}
      <div className="service-picker">
        <label>Select Services (min 2) *</label>
        <div className="service-picker-list">
          {services.map((svc) => (
            <label key={svc.id} className="service-picker-item">
              <input
                type="checkbox"
                checked={formData.selectedServiceIds.includes(svc.id)}
                onChange={() => toggleServiceSelection(svc.id)}
              />
              <span className="service-picker-name">{svc.name}</span>
              <span className="service-picker-meta">
                {formatDuration(svc.duration_minutes)} · {formatPriceRange(svc.price, svc.price_max)}
              </span>
            </label>
          ))}
        </div>
        {formData.selectedServiceIds.length > 0 && (
          <div className="service-picker-order">
            <label>Service Order</label>
            <div className="service-order-list">
              {formData.selectedServiceIds.map((id, idx) => {
                const svc = services.find(s => s.id === id);
                if (!svc) return null;
                return (
                  <div key={id} className="service-order-item">
                    <span className="service-order-num">{idx + 1}</span>
                    <span className="service-order-name">{svc.name}</span>
                    <div className="service-order-btns">
                      <button type="button" className="btn-icon" onClick={() => moveService(idx, -1)} disabled={idx === 0} title="Move up" aria-label="Move up">
                        <i className="fas fa-chevron-up"></i>
                      </button>
                      <button type="button" className="btn-icon" onClick={() => moveService(idx, 1)} disabled={idx === formData.selectedServiceIds.length - 1} title="Move down" aria-label="Move down">
                        <i className="fas fa-chevron-down"></i>
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Calculated totals */}
      {selected.length >= 2 && (
        <div className="package-meta">
          <span className="meta-item duration"><i className="fas fa-clock"></i> {formatDuration(totalDuration)}</span>
        </div>
      )}

      {/* Package Price — auto-fills from services sum, with price range toggle */}
      <div className="form-group" style={{ marginTop: '0.75rem' }}>
        <label>Price (€)</label>
        {formData.price_max_override != null && (
          <span className="price-from-label">from</span>
        )}
        <input
          type="number"
          className="form-input"
          value={formData.price_override ?? (selected.length >= 2 ? totalPrice : '')}
          onChange={(e) => setFormData({ ...formData, price_override: e.target.value === '' ? null : e.target.value })}
          placeholder="0.00"
          step="0.01"
          min="0"
        />
        {selected.length >= 2 && formData.price_override == null && (
          <span className="form-hint">Auto-calculated from services (€{totalPrice})</span>
        )}
        <div className="price-range-toggle-row">
          <button
            type="button"
            className={`price-range-toggle ${formData.price_max_override != null ? 'active' : ''}`}
            onClick={() => setFormData({ ...formData, price_max_override: formData.price_max_override != null ? null : (selected.length >= 2 && totalPriceMax > totalPrice ? totalPriceMax : '') })}
            role="switch"
            aria-checked={formData.price_max_override != null}
          >
            <span className="price-range-toggle-slider" />
          </button>
          <span className="price-range-toggle-label">Price range</span>
        </div>
        {formData.price_max_override != null && (
          <div className="price-max-row">
            <div className="price-max-field">
              <span className="price-max-label">to</span>
              <input
                type="number"
                className="form-input"
                value={formData.price_max_override ?? ''}
                onChange={(e) => setFormData({ ...formData, price_max_override: e.target.value === '' ? null : e.target.value })}
                placeholder="Max price"
                step="0.01"
                min="0"
              />
            </div>
          </div>
        )}
      </div>

      {/* Book when uncertain toggle */}
      <div className="callout-toggle-group">
        <label>Book when uncertain?</label>
        <div className="callout-toggle-row">
          <button
            type="button"
            className={`callout-toggle ${formData.use_when_uncertain ? 'active' : ''}`}
            onClick={() => setFormData({ ...formData, use_when_uncertain: !formData.use_when_uncertain })}
            role="switch"
            aria-checked={formData.use_when_uncertain}
            title="When enabled, the AI receptionist will prefer this package when the caller's issue is vague or ambiguous"
          >
            <span className="callout-toggle-slider" />
          </button>
          <span className="callout-toggle-label">
            {formData.use_when_uncertain
              ? 'Yes — AI prefers this package when the issue is vague'
              : 'No — only match when clearly relevant'}
          </span>
        </div>
      </div>

      <div className="form-actions">
        <button type="button" className="btn btn-secondary" onClick={onCancel}>Cancel</button>
        <button type="submit" className="btn btn-primary" disabled={isPending}>
          {isPending ? 'Saving...' : (isNew ? 'Add Package' : 'Save Package')}
        </button>
      </div>
    </form>
  );
}

function PackageCard({ pkg, services, isEditing, onEdit, onSave, onCancel, onDelete, isPending, getSelectedServiceDetails }) {
  const resolvedServices = (pkg.services || [])
    .sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0))
    .map(ref => {
      const svc = services.find(s => s.id === (ref.service_id || ref.id));
      return svc ? { ...svc, sort_order: ref.sort_order } : (ref.name ? ref : null);
    })
    .filter(Boolean);

  const [editData, setEditData] = useState({});

  useEffect(() => {
    if (isEditing) {
      const serviceIds = (pkg.services || [])
        .sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0))
        .map(ref => ref.service_id || ref.id)
        .filter(Boolean);
      setEditData({
        id: pkg.id,
        name: pkg.name || '',
        description: pkg.description || '',
        selectedServiceIds: serviceIds,
        price_override: pkg.price_override != null ? pkg.price_override : null,
        price_max_override: pkg.price_max_override != null ? pkg.price_max_override : null,
        use_when_uncertain: pkg.use_when_uncertain || false,
      });
    }
  }, [isEditing, pkg]);

  const editToggleService = (serviceId) => {
    setEditData(prev => {
      const ids = prev.selectedServiceIds.includes(serviceId)
        ? prev.selectedServiceIds.filter(id => id !== serviceId)
        : [...prev.selectedServiceIds, serviceId];
      return { ...prev, selectedServiceIds: ids };
    });
  };

  const editMoveService = (index, direction) => {
    setEditData(prev => {
      const ids = [...prev.selectedServiceIds];
      const newIndex = index + direction;
      if (newIndex < 0 || newIndex >= ids.length) return prev;
      [ids[index], ids[newIndex]] = [ids[newIndex], ids[index]];
      return { ...prev, selectedServiceIds: ids };
    });
  };

  if (isEditing) {
    return (
      <div className="package-card editing">
        <PackageForm
          formData={editData}
          setFormData={setEditData}
          services={services}
          onSubmit={(e) => { e.preventDefault(); onSave(editData); }}
          onCancel={onCancel}
          isPending={isPending}
          toggleServiceSelection={editToggleService}
          moveService={editMoveService}
          getSelectedServiceDetails={getSelectedServiceDetails}
          isNew={false}
        />
      </div>
    );
  }

  const totalDuration = pkg.total_duration_minutes || resolvedServices.reduce((sum, s) => sum + (s.duration_minutes || 0), 0);
  const totalPrice = pkg.price_override != null ? pkg.price_override : (pkg.total_price || resolvedServices.reduce((sum, s) => sum + (parseFloat(s.price) || 0), 0));
  const totalPriceMax = pkg.price_max_override != null ? pkg.price_max_override : (pkg.total_price_max || resolvedServices.reduce((sum, s) => sum + (parseFloat(s.price_max) || parseFloat(s.price) || 0), 0));

  return (
    <div className="package-card">
      <div className="service-image">
        📦
      </div>
      <div className="service-content">
        <h3 className="service-title">{pkg.name || 'Unnamed Package'}</h3>
        <div className="package-services-list">
          {resolvedServices.map((svc, idx) => (
            <span key={svc.id || idx}>
              {idx > 0 && <span className="service-arrow"> → </span>}
              <span className="service-step">{svc.name}</span>
            </span>
          ))}
        </div>
        <div className="service-meta">
          {totalPrice > 0 && (
            <span className="meta-item price">{formatPriceRange(totalPrice, totalPriceMax > totalPrice ? totalPriceMax : null)}</span>
          )}
          {totalDuration > 0 && (
            <span className="meta-item duration">
              <i className="fas fa-clock"></i> {formatDuration(totalDuration)}
            </span>
          )}
          {pkg.use_when_uncertain && (
            <span className="badge-uncertain" title="AI prefers this package when the caller's issue is vague or ambiguous">
              🤔 Book when uncertain
            </span>
          )}
        </div>
      </div>
      <div className="service-actions">
        <button type="button" className="btn-icon" onClick={onEdit} title="Edit" aria-label="Edit package">
          <i className="fas fa-edit"></i>
        </button>
        <button type="button" className="btn-icon danger" onClick={onDelete} title="Delete" aria-label="Delete package" disabled={isPending}>
          <i className="fas fa-trash"></i>
        </button>
      </div>
    </div>
  );
}

export default ServicesTab;
