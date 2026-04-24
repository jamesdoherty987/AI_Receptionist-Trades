import { useState, useEffect, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../../context/AuthContext';
import { 
  getServicesMenu, 
  createService,
  updateService,
  deleteService,
  getEmployees,
  getPackages,
  createPackage,
  updatePackage,
  deletePackage,
  getMaterials
} from '../../services/api';
import LoadingSpinner from '../LoadingSpinner';
import { useToast } from '../Toast';
import ImageUpload from '../ImageUpload';
import { formatPriceRange } from '../../utils/helpers';
import HelpTooltip from '../HelpTooltip';
import { DURATION_OPTIONS_GROUPED, formatDuration } from '../../utils/durationOptions';
import './ServicesTab.css';
import './SharedDashboard.css';

function ServicesTab() {
  const { hasActiveSubscription } = useAuth();
  const isSubscriptionActive = hasActiveSubscription();
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [editingId, setEditingId] = useState(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState('name');
  const [sortDir, setSortDir] = useState('asc');
  const [viewMode, setViewMode] = useState('grid');
  const [formData, setFormData] = useState({ 
    name: '', 
    description: '',
    price: '', 
    price_max: null,
    duration: '1440', 
    image_url: '', 
    employees_required: '1',
    employee_restrictions: { type: 'all', employee_ids: [] },
    requires_callout: false,
    requires_quote: false,
    package_only: false,
    show_price_duration: false,
    default_materials: []
  });
  const [deleteConfirm, setDeleteConfirm] = useState({ show: false, service: null });

  const { data: employeesData } = useQuery({
    queryKey: ['employees'],
    queryFn: async () => {
      const response = await getEmployees();
      return response.data;
    },
  });

  const employees = Array.isArray(employeesData) ? employeesData : (employeesData?.employees || []);

  const { data: materialsData } = useQuery({
    queryKey: ['materials'],
    queryFn: async () => {
      const response = await getMaterials();
      return response.data;
    },
  });
  const materialsCatalog = materialsData?.materials || [];

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
      addToast('Please upgrade your plan to add services', 'warning');
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
        description: '',
        price: '', 
        price_max: null,
        duration: '1440', 
        image_url: '', 
        employees_required: '1',
        employee_restrictions: { type: 'all', employee_ids: [] },
        requires_callout: false,
        requires_quote: false,
        package_only: false,
        show_price_duration: false,
        default_materials: []
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
    
    const restrictionType = formData.employee_restrictions?.type;
    const hasEmployeeIds = formData.employee_restrictions?.employee_ids?.length > 0;
    if ((restrictionType === 'only' || restrictionType === 'except') && !hasEmployeeIds) {
      addToast('Please select at least one employee for the restriction', 'warning');
      return;
    }
    
    const restrictions = formData.employee_restrictions?.type === 'all' 
      ? null 
      : formData.employee_restrictions;
    
    createMutation.mutate({
      name: formData.name,
      description: formData.description || null,
      price: Math.round((parseFloat(formData.price) || 0) * 100) / 100,
      price_max: formData.price_max && parseFloat(formData.price_max) > (parseFloat(formData.price) || 0) 
        ? Math.round(parseFloat(formData.price_max) * 100) / 100 
        : null,
      duration_minutes: parseInt(formData.duration) || 60,
      image_url: formData.image_url,
      employees_required: parseInt(formData.employees_required) || 1,
      employee_restrictions: restrictions,
      requires_callout: formData.requires_callout,
      requires_quote: formData.requires_quote,
      package_only: formData.package_only,
      default_materials: formData.default_materials || [],
    });
  };

  const handleUpdate = (service) => {
    const restrictionType = service.employee_restrictions?.type;
    const hasEmployeeIds = service.employee_restrictions?.employee_ids?.length > 0;
    if ((restrictionType === 'only' || restrictionType === 'except') && !hasEmployeeIds) {
      addToast('Please select at least one employee for the restriction', 'warning');
      return;
    }
    
    const restrictions = service.employee_restrictions?.type === 'all' 
      ? null 
      : service.employee_restrictions;
    
    updateMutation.mutate({
      id: service.id,
      data: {
        name: service.name,
        description: service.description || null,
        price: Math.round((parseFloat(service.price) || 0) * 100) / 100,
        price_max: service.price_max && parseFloat(service.price_max) > (parseFloat(service.price) || 0)
          ? Math.round(parseFloat(service.price_max) * 100) / 100 
          : null,
        duration_minutes: parseInt(service.duration_minutes) || 60,
        image_url: service.image_url,
        employees_required: parseInt(service.employees_required) || 1,
        employee_restrictions: restrictions,
        requires_callout: service.requires_callout || false,
        requires_quote: service.requires_quote || false,
        package_only: service.package_only || false,
        default_materials: service.default_materials || [],
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

  const services = menu?.services || [];

  // Filter and sort services
  const filteredServices = useMemo(() => {
    let result = [...services];
    
    if (searchTerm.trim()) {
      const term = searchTerm.toLowerCase();
      result = result.filter(s =>
        s.name?.toLowerCase().includes(term)
      );
    }
    
    result.sort((a, b) => {
      let cmp = 0;
      switch (sortBy) {
        case 'name':
          cmp = (a.name || '').localeCompare(b.name || '');
          break;
        case 'price':
          cmp = (parseFloat(a.price) || 0) - (parseFloat(b.price) || 0);
          break;
        case 'duration':
          cmp = (a.duration_minutes || 0) - (b.duration_minutes || 0);
          break;
        case 'employees':
          cmp = (a.employees_required || 1) - (b.employees_required || 1);
          break;
        default:
          cmp = 0;
      }
      return sortDir === 'asc' ? cmp : -cmp;
    });
    
    return result;
  }, [services, searchTerm, sortBy, sortDir]);

  const toggleSort = (field) => {
    if (sortBy === field) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortDir('asc');
    }
  };

  if (isLoading) {
    return <LoadingSpinner message="Loading services..." />;
  }

  return (
    <div className="services-tab">
      <div className="services-header">
        <div>
          <h2>Services</h2>
          <p className="services-subtitle">
            {services.length} service{services.length !== 1 ? 's' : ''} · Manage your services and pricing
          </p>
        </div>
        <div className="services-controls">
          <button 
            className="btn-add"
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
            <div className="form-group form-group-wide">
              <label>Description (optional)</label>
              <textarea
                className="form-input"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="Brief description of this service"
                rows={2}
              />
            </div>
          </div>

          <div className="callout-toggle-group">
            <label>Package Only? <HelpTooltip text="If enabled, this service can only be booked as part of a package — not on its own." /></label>
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

          {formData.package_only && (
            <div className="callout-toggle-group">
              <label>Set Price & Duration?</label>
              <div className="callout-toggle-row">
                <button
                  type="button"
                  className={`callout-toggle ${formData.show_price_duration ? 'active' : ''}`}
                  onClick={() => setFormData({ ...formData, show_price_duration: !formData.show_price_duration })}
                  role="switch"
                  aria-checked={formData.show_price_duration || false}
                >
                  <span className="callout-toggle-slider" />
                </button>
                <span className="callout-toggle-label">
                  {formData.show_price_duration 
                    ? 'Yes — set individual price & duration' 
                    : 'No — price & duration will come from the package'}
                </span>
              </div>
            </div>
          )}

          {(!formData.package_only || formData.show_price_duration) && (
          <div className="form-grid">
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
          </div>
          )}

          <div className="form-grid">
            <div className="form-group">
              <label>Employees Required <HelpTooltip text="How many employees are needed on-site at the same time for this service." /></label>
              <div className="employees-input-wrapper">
                <button 
                  type="button" 
                  className="employees-btn"
                  onClick={() => setFormData({ ...formData, employees_required: Math.max(1, parseInt(formData.employees_required || 1) - 1).toString() })}
                  disabled={parseInt(formData.employees_required || 1) <= 1}
                >
                  <i className="fas fa-minus"></i>
                </button>
                <span className="employees-value">{formData.employees_required || 1}</span>
                <button 
                  type="button" 
                  className="employees-btn"
                  onClick={() => setFormData({ ...formData, employees_required: (parseInt(formData.employees_required || 1) + 1).toString() })}
                  disabled={parseInt(formData.employees_required || 1) >= 10}
                >
                  <i className="fas fa-plus"></i>
                </button>
              </div>
              <span className="form-hint">How many employees needed for this job</span>
            </div>
          </div>
          
          <EmployeeRestrictions
            restrictions={formData.employee_restrictions}
            onChange={(restrictions) => setFormData({ ...formData, employee_restrictions: restrictions })}
            employees={employees}
          />
          
          {!formData.package_only && (
          <div className="callout-toggle-group">
            <label>Requires Initial Callout? <HelpTooltip text="If enabled, the AI books a callout visit first so an employee can assess the job. The callout service is configured in your Services tab." /></label>
            <div className="callout-toggle-row">
              <button
                type="button"
                className={`callout-toggle ${formData.requires_callout ? 'active' : ''}`}
                onClick={() => setFormData({ ...formData, requires_callout: !formData.requires_callout, requires_quote: false })}
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
          )}
          
          {!formData.package_only && !formData.requires_callout && (
          <div className="callout-toggle-group">
            <label>Requires Quote Visit? <HelpTooltip text="If enabled, the AI books a free quote visit first so an employee can assess and quote the job. The quote service is configured in your Services tab." /></label>
            <div className="callout-toggle-row">
              <button
                type="button"
                className={`callout-toggle ${formData.requires_quote ? 'active' : ''}`}
                onClick={() => setFormData({ ...formData, requires_quote: !formData.requires_quote })}
                role="switch"
                aria-checked={formData.requires_quote}
              >
                <span className="callout-toggle-slider" />
              </button>
              <span className="callout-toggle-label">
                {formData.requires_quote 
                  ? 'Yes — AI will book a free quote visit instead of the full job' 
                  : 'No — book the full job directly'}
              </span>
            </div>
          </div>
          )}
          
          <div className="form-group">
            <label>Image (optional)</label>
            <ImageUpload
              value={formData.image_url}
              onChange={(value) => setFormData({ ...formData, image_url: value })}
              placeholder="Upload Image"
            />
          </div>
          <DefaultMaterialsPicker
            materials={materialsCatalog}
            selectedMaterials={formData.default_materials || []}
            onChange={(mats) => setFormData({ ...formData, default_materials: mats })}
          />
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

      {services.length > 0 && (
        <div className="svc-toolbar">
          <div className="svc-search">
            <i className="fas fa-search"></i>
            <input
              type="text"
              placeholder="Search services..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
            {searchTerm && (
              <button className="svc-search-clear" onClick={() => setSearchTerm('')} aria-label="Clear search">
                <i className="fas fa-times"></i>
              </button>
            )}
          </div>
          <div className="svc-toolbar-right">
            <div className="svc-sort-chips">
              {[
                { key: 'name', label: 'Name', icon: 'fa-font' },
                { key: 'price', label: 'Price', icon: 'fa-euro-sign' },
                { key: 'duration', label: 'Duration', icon: 'fa-clock' },
              ].map(s => (
                <button
                  key={s.key}
                  className={`svc-sort-chip ${sortBy === s.key ? 'active' : ''}`}
                  onClick={() => toggleSort(s.key)}
                  title={`Sort by ${s.label}`}
                >
                  <i className={`fas ${s.icon}`}></i>
                  <span className="svc-sort-chip-label">{s.label}</span>
                  {sortBy === s.key && (
                    <i className={`fas fa-arrow-${sortDir === 'asc' ? 'up' : 'down'} svc-sort-dir`}></i>
                  )}
                </button>
              ))}
            </div>
            <div className="svc-view-toggle">
              <button
                className={`svc-view-btn ${viewMode === 'grid' ? 'active' : ''}`}
                onClick={() => setViewMode('grid')}
                title="Grid view"
                aria-label="Grid view"
              >
                <i className="fas fa-th-large"></i>
              </button>
              <button
                className={`svc-view-btn ${viewMode === 'list' ? 'active' : ''}`}
                onClick={() => setViewMode('list')}
                title="List view"
                aria-label="List view"
              >
                <i className="fas fa-list"></i>
              </button>
            </div>
          </div>
        </div>
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
      ) : filteredServices.length === 0 ? (
        <div className="svc-no-results">
          <i className="fas fa-search"></i>
          <p>No services match "{searchTerm}"</p>
          <button className="btn btn-secondary btn-sm" onClick={() => setSearchTerm('')}>Clear search</button>
        </div>
      ) : (
        <div className={`services-list ${viewMode === 'grid' ? 'services-grid' : ''}`}>
          {filteredServices.map((service) => (
            <ServiceCard
              key={service.id}
              service={service}
              isEditing={editingId === service.id}
              onEdit={() => startEdit(service)}
              onSave={handleUpdate}
              onCancel={() => setEditingId(null)}
              onDelete={() => handleDelete(service)}
              isPending={updateMutation.isPending || deleteMutation.isPending}
              employees={employees}
              viewMode={viewMode}
              materialsCatalog={materialsCatalog}
            />
          ))}
        </div>
      )}

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

      <PackagesSection services={services} isSubscriptionActive={isSubscriptionActive} materialsCatalog={materialsCatalog} />
    </div>
  );
}

function DefaultMaterialsPicker({ materials, selectedMaterials, onChange }) {
  const [search, setSearch] = useState('');
  const catalog = materials || [];
  const selected = Array.isArray(selectedMaterials) ? selectedMaterials : [];
  
  const filtered = catalog.filter(m => 
    !search || m.name.toLowerCase().includes(search.toLowerCase())
  );

  const addMaterial = (mat) => {
    const exists = selected.find(m => m.material_id === mat.id);
    if (exists) return;
    onChange([...selected, {
      material_id: mat.id,
      name: mat.name,
      unit_price: parseFloat(mat.unit_price) || 0,
      unit: mat.unit || 'each',
      quantity: 1
    }]);
  };

  const removeMaterial = (idx) => {
    onChange(selected.filter((_, i) => i !== idx));
  };

  const updateQuantity = (idx, rawVal) => {
    const updated = [...selected];
    // Allow empty string while typing, store as empty string
    if (rawVal === '' || rawVal === undefined) {
      updated[idx] = { ...updated[idx], quantity: '' };
    } else {
      const parsed = parseFloat(rawVal);
      updated[idx] = { ...updated[idx], quantity: isNaN(parsed) ? '' : parsed };
    }
    onChange(updated);
  };

  const finalizeQuantity = (idx) => {
    const updated = [...selected];
    const val = parseFloat(updated[idx].quantity);
    updated[idx] = { ...updated[idx], quantity: isNaN(val) || val <= 0 ? 1 : val };
    onChange(updated);
  };

  const safePrice = (mat) => {
    const price = parseFloat(mat.unit_price) || 0;
    const qty = parseFloat(mat.quantity) || 0;
    return (price * qty).toFixed(2);
  };

  const totalCost = selected.reduce((sum, m) => {
    return sum + (parseFloat(m.unit_price) || 0) * (parseFloat(m.quantity) || 0);
  }, 0).toFixed(2);

  return (
    <div className="default-materials-picker">
      <label>Default Materials <span className="form-hint-inline">— auto-added when a job is created</span></label>
      {selected.length > 0 && (
        <div className="dm-selected-list">
          {selected.map((mat, idx) => (
            <div key={mat.material_id || idx} className="dm-selected-item">
              <span className="dm-item-name">{mat.name}</span>
              <div className="dm-item-qty">
                <input
                  type="number"
                  value={mat.quantity}
                  onChange={(e) => updateQuantity(idx, e.target.value)}
                  onBlur={() => finalizeQuantity(idx)}
                  min="0.01"
                  step="0.01"
                  className="dm-qty-input"
                />
                <span className="dm-item-unit">{mat.unit || 'each'}</span>
              </div>
              <span className="dm-item-price">€{safePrice(mat)}</span>
              <button type="button" className="dm-remove-btn" onClick={() => removeMaterial(idx)} title="Remove" aria-label="Remove material">
                <i className="fas fa-times"></i>
              </button>
            </div>
          ))}
          <div className="dm-total">
            Total: €{totalCost}
          </div>
        </div>
      )}
      {catalog.length > 0 ? (
        <div className="dm-catalog">
          {catalog.length > 5 && (
            <input
              type="text"
              className="dm-search"
              placeholder="Search materials..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          )}
          <div className="dm-catalog-list">
            {filtered.slice(0, 20).map(mat => {
              const alreadyAdded = selected.some(m => m.material_id === mat.id);
              return (
                <button
                  key={mat.id}
                  type="button"
                  className={`dm-catalog-item ${alreadyAdded ? 'dm-added' : ''}`}
                  onClick={() => !alreadyAdded && addMaterial(mat)}
                  disabled={alreadyAdded}
                >
                  <span className="dm-cat-name">{mat.name}</span>
                  <span className="dm-cat-price">€{(parseFloat(mat.unit_price) || 0).toFixed(2)}/{mat.unit || 'each'}</span>
                  {alreadyAdded && <i className="fas fa-check dm-check"></i>}
                </button>
              );
            })}
          </div>
        </div>
      ) : (
        <p className="dm-empty-hint">Add materials in the Materials tab first to use this feature.</p>
      )}
    </div>
  );
}

function EmployeeRestrictions({ restrictions, onChange, employees }) {
  const type = restrictions?.type || 'all';
  const selectedIds = restrictions?.employee_ids || [];

  const handleTypeChange = (newType) => {
    onChange({ type: newType, employee_ids: newType === 'all' ? [] : selectedIds });
  };

  const toggleEmployee = (employeeId) => {
    const newIds = selectedIds.includes(employeeId)
      ? selectedIds.filter(id => id !== employeeId)
      : [...selectedIds, employeeId];
    onChange({ type, employee_ids: newIds });
  };

  if (!employees || employees.length === 0) {
    return (
      <div className="employee-restrictions">
        <label>Who Can Do This Job <HelpTooltip text="Control which employees are eligible for this service. Useful if only certain tradespeople are qualified." /></label>
        <div className="no-employees-message">
          <i className="fas fa-info-circle"></i>
          <span>Add employees in the Employees tab to set job restrictions</span>
        </div>
      </div>
    );
  }

  return (
    <div className="employee-restrictions">
      <label>Who Can Do This Job <HelpTooltip text="Control which employees are eligible for this service. Useful if only certain tradespeople are qualified." /></label>
      <div className="restriction-type-selector">
        <button
          type="button"
          className={`restriction-type-btn ${type === 'all' ? 'active' : ''}`}
          onClick={() => handleTypeChange('all')}
        >
          <i className="fas fa-users"></i>
          All Employees
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
        <div className="employee-selection">
          <span className="selection-hint">
            {type === 'only' 
              ? 'Select employees who CAN do this job:' 
              : 'Select employees who CANNOT do this job:'}
          </span>
          <div className="employee-chips">
            {employees.map(employee => (
              <button
                key={employee.id}
                type="button"
                className={`employee-chip ${selectedIds.includes(employee.id) ? 'selected' : ''}`}
                onClick={() => toggleEmployee(employee.id)}
              >
                <i className={`fas ${selectedIds.includes(employee.id) ? 'fa-check' : 'fa-user'}`}></i>
                {employee.name}
              </button>
            ))}
          </div>
          {type !== 'all' && selectedIds.length === 0 && (
            <span className="selection-warning">
              <i className="fas fa-exclamation-circle"></i>
              Select at least one employee
            </span>
          )}
        </div>
      )}
    </div>
  );
}

function ServiceCard({ service, isEditing, onEdit, onSave, onCancel, onDelete, isPending, employees, viewMode, materialsCatalog }) {
  const [editData, setEditData] = useState(service);
  const [imageError, setImageError] = useState(false);

  useEffect(() => {
    if (isEditing) {
      // Only show price range toggle as "on" if there's a real max price > min price
      const hasRange = service.price_max != null && parseFloat(service.price_max) > (parseFloat(service.price) || 0);
      setEditData({
        ...service,
        price_max: hasRange ? service.price_max : null,
        employee_restrictions: service.employee_restrictions || { type: 'all', employee_ids: [] },
        show_price_duration: service.package_only ? (parseFloat(service.price) > 0) : false,
        default_materials: Array.isArray(service.default_materials) ? service.default_materials : 
          (typeof service.default_materials === 'string' ? JSON.parse(service.default_materials || '[]') : [])
      });
    }
  }, [isEditing, service]);

  useEffect(() => {
    setImageError(false);
  }, [service.image_url]);

  const handleSave = () => {
    if (!editData.name?.trim()) return;
    onSave(editData);
  };

  const getRestrictionSummary = () => {
    const restrictions = service.employee_restrictions;
    if (!restrictions || restrictions.type === 'all') return null;
    
    const count = restrictions.employee_ids?.length || 0;
    if (restrictions.type === 'only') {
      return `${count} employee${count !== 1 ? 's' : ''} only`;
    } else {
      return `All except ${count}`;
    }
  };

  if (isEditing) {
    const showPriceDuration = !editData.package_only || editData.show_price_duration;
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
          <div className="form-group">
            <label>Description (optional)</label>
            <textarea
              className="form-input"
              value={editData.description || ''}
              onChange={(e) => setEditData({ ...editData, description: e.target.value })}
              placeholder="Brief description of this service"
              rows={2}
            />
          </div>

          <div className="callout-toggle-group">
            <label>Package Only? <HelpTooltip text="If enabled, this service can only be booked as part of a package — not on its own." /></label>
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

          {editData.package_only && (
            <div className="callout-toggle-group">
              <label>Set Price & Duration?</label>
              <div className="callout-toggle-row">
                <button
                  type="button"
                  className={`callout-toggle ${editData.show_price_duration ? 'active' : ''}`}
                  onClick={() => setEditData({ ...editData, show_price_duration: !editData.show_price_duration })}
                  role="switch"
                  aria-checked={editData.show_price_duration || false}
                >
                  <span className="callout-toggle-slider" />
                </button>
                <span className="callout-toggle-label">
                  {editData.show_price_duration 
                    ? 'Yes — set individual price & duration' 
                    : 'No — price & duration will come from the package'}
                </span>
              </div>
            </div>
          )}

          {showPriceDuration && (
          <div className="edit-row">
            <div className="form-group">
              <label>Price (€)</label>
              {editData.price_max != null && (
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
                  className={`price-range-toggle ${editData.price_max != null ? 'active' : ''}`}
                  onClick={() => setEditData({ ...editData, price_max: editData.price_max != null ? null : '' })}
                  role="switch"
                  aria-checked={editData.price_max != null}
                >
                  <span className="price-range-toggle-slider" />
                </button>
                <span className="price-range-toggle-label">Price range</span>
              </div>
              {editData.price_max != null && (
                <div className="price-max-row">
                  <div className="price-max-field">
                    <span className="price-max-label">to</span>
                    <input
                      type="number"
                      className="form-input"
                      value={editData.price_max}
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
              <label>Employees</label>
              <div className="employees-input-wrapper compact">
                <button 
                  type="button" 
                  className="employees-btn"
                  onClick={() => setEditData({ ...editData, employees_required: Math.max(1, (editData.employees_required || 1) - 1) })}
                  disabled={(editData.employees_required || 1) <= 1}
                >
                  <i className="fas fa-minus"></i>
                </button>
                <span className="employees-value">{editData.employees_required || 1}</span>
                <button 
                  type="button" 
                  className="employees-btn"
                  onClick={() => setEditData({ ...editData, employees_required: (editData.employees_required || 1) + 1 })}
                  disabled={(editData.employees_required || 1) >= 10}
                >
                  <i className="fas fa-plus"></i>
                </button>
              </div>
            </div>
          </div>
          )}

          {!showPriceDuration && (
          <div className="edit-row">
            <div className="form-group">
              <label>Employees</label>
              <div className="employees-input-wrapper compact">
                <button 
                  type="button" 
                  className="employees-btn"
                  onClick={() => setEditData({ ...editData, employees_required: Math.max(1, (editData.employees_required || 1) - 1) })}
                  disabled={(editData.employees_required || 1) <= 1}
                >
                  <i className="fas fa-minus"></i>
                </button>
                <span className="employees-value">{editData.employees_required || 1}</span>
                <button 
                  type="button" 
                  className="employees-btn"
                  onClick={() => setEditData({ ...editData, employees_required: (editData.employees_required || 1) + 1 })}
                  disabled={(editData.employees_required || 1) >= 10}
                >
                  <i className="fas fa-plus"></i>
                </button>
              </div>
            </div>
          </div>
          )}
          
          <EmployeeRestrictions
            restrictions={editData.employee_restrictions}
            onChange={(restrictions) => setEditData({ ...editData, employee_restrictions: restrictions })}
            employees={employees}
          />
          
          {!editData.package_only && (
          <div className="callout-toggle-group">
            <label>Requires Initial Callout? <HelpTooltip text="If enabled, the AI books a callout visit first so an employee can assess the job. The callout service is configured in your Services tab." /></label>
            <div className="callout-toggle-row">
              <button
                type="button"
                className={`callout-toggle ${editData.requires_callout ? 'active' : ''}`}
                onClick={() => setEditData({ ...editData, requires_callout: !editData.requires_callout, requires_quote: false })}
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
          )}
          
          {!editData.package_only && !editData.requires_callout && (
          <div className="callout-toggle-group">
            <label>Requires Quote Visit? <HelpTooltip text="If enabled, the AI books a free quote visit first so an employee can assess and quote the job. The quote service is configured in your Services tab." /></label>
            <div className="callout-toggle-row">
              <button
                type="button"
                className={`callout-toggle ${editData.requires_quote ? 'active' : ''}`}
                onClick={() => setEditData({ ...editData, requires_quote: !editData.requires_quote })}
                role="switch"
                aria-checked={editData.requires_quote}
              >
                <span className="callout-toggle-slider" />
              </button>
              <span className="callout-toggle-label">
                {editData.requires_quote 
                  ? 'Yes — AI will book a free quote visit instead of the full job' 
                  : 'No — book the full job directly'}
              </span>
            </div>
          </div>
          )}
          
          <DefaultMaterialsPicker
            materials={materialsCatalog}
            selectedMaterials={editData.default_materials || []}
            onChange={(mats) => setEditData({ ...editData, default_materials: mats })}
          />
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
  const isGrid = viewMode === 'grid';

  return (
    <div className={`service-card ${isGrid ? 'service-card-grid' : ''}`}>
      <div className={`service-image ${isGrid ? 'service-image-grid' : ''}`}>
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
        {service.description && (
          <p className="service-description">{service.description}</p>
        )}
        {isGrid && service.price > 0 && (
          <div className="service-grid-price">{formatPriceRange(service.price, service.price_max)}</div>
        )}
        <div className="service-meta">
          {!isGrid && service.price > 0 && (
            <span className="meta-item price">{formatPriceRange(service.price, service.price_max)}</span>
          )}
          {(service.duration_minutes || service.duration) && (
            <span className="meta-item duration">
              <i className="fas fa-clock"></i> {formatDuration(service.duration_minutes || service.duration)}
            </span>
          )}
          <span className="meta-item employees" title="Employees required for this job">
            <i className="fas fa-user-hard-hat"></i> {service.employees_required || 1}
          </span>
          {restrictionSummary && (
            <span className="meta-item restriction" title="Employee restrictions">
              <i className="fas fa-user-lock"></i> {restrictionSummary}
            </span>
          )}
          {service.requires_callout && (
            <span className="meta-item callout-badge" title="Requires initial callout visit">
              <i className="fas fa-phone-alt"></i> Callout
            </span>
          )}
          {service.requires_quote && (
            <span className="meta-item callout-badge" title="Requires free quote visit">
              <i className="fas fa-file-invoice"></i> Quote
            </span>
          )}
          {service.package_only && (
            <span className="meta-item callout-badge" title="Only available as part of a package">
              <i className="fas fa-box"></i> Pkg only
            </span>
          )}
          {Array.isArray(service.default_materials) && service.default_materials.length > 0 && (
            <span className="meta-item callout-badge" title={`${service.default_materials.length} default material${service.default_materials.length !== 1 ? 's' : ''}`}>
              <i className="fas fa-cubes"></i> {service.default_materials.length} material{service.default_materials.length !== 1 ? 's' : ''}
            </span>
          )}
        </div>
      </div>
      <div className={`service-actions ${isGrid ? 'service-actions-grid' : ''}`}>
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

function PackagesSection({ services, isSubscriptionActive, materialsCatalog }) {
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
    duration_override: null,
    use_when_uncertain: false,
    default_materials: [],
  });

  const { data: packagesData } = useQuery({
    queryKey: ['packages'],
    queryFn: async () => {
      const response = await getPackages();
      return response.data;
    },
  });

  const packages = packagesData?.packages || packagesData || [];

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
      duration_override: null,
      use_when_uncertain: false,
      default_materials: [],
    });
  };

  const handleAddClick = () => {
    if (!isSubscriptionActive) {
      addToast('Please upgrade your plan to add packages', 'warning');
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
      default_materials: pkgFormData.default_materials || [],
    };

    if (pkgFormData.price_override !== null && pkgFormData.price_override !== undefined && pkgFormData.price_override !== '') {
      payload.price_override = Math.round((parseFloat(pkgFormData.price_override) || 0) * 100) / 100;
      if (pkgFormData.price_max_override !== null && pkgFormData.price_max_override !== undefined && pkgFormData.price_max_override !== '') {
        payload.price_max_override = Math.round((parseFloat(pkgFormData.price_max_override) || 0) * 100) / 100;
      }
    }

    if (pkgFormData.duration_override !== null && pkgFormData.duration_override !== undefined && pkgFormData.duration_override !== '') {
      payload.duration_override = parseInt(pkgFormData.duration_override) || null;
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
      default_materials: pkgData.default_materials || [],
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

    if (pkgData.duration_override !== null && pkgData.duration_override !== undefined && pkgData.duration_override !== '') {
      payload.duration_override = parseInt(pkgData.duration_override) || null;
    } else {
      payload.duration_override = null;
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
          materialsCatalog={materialsCatalog}
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
              materialsCatalog={materialsCatalog}
            />
          ))}
        </div>
      )}

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

function PackageForm({ formData, setFormData, services, onSubmit, onCancel, isPending, toggleServiceSelection, moveService, getSelectedServiceDetails, isNew, materialsCatalog }) {
  const { selected } = getSelectedServiceDetails(formData.selectedServiceIds);

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
            placeholder="e.g., Leak Investigation and Fix"
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
                {svc.duration_minutes ? formatDuration(svc.duration_minutes) : ''}{svc.price > 0 ? ` · ${formatPriceRange(svc.price, svc.price_max)}` : ''}
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

      <div className="form-grid" style={{ marginTop: '0.75rem' }}>
        <div className="form-group">
          <label>Total Price (€) *</label>
          {formData.price_max_override != null && (
            <span className="price-from-label">from</span>
          )}
          <input
            type="number"
            className="form-input"
            value={formData.price_override ?? ''}
            onChange={(e) => setFormData({ ...formData, price_override: e.target.value === '' ? null : e.target.value })}
            placeholder="0.00"
            step="0.01"
            min="0"
          />
          <div className="price-range-toggle-row">
            <button
              type="button"
              className={`price-range-toggle ${formData.price_max_override != null ? 'active' : ''}`}
              onClick={() => setFormData({ ...formData, price_max_override: formData.price_max_override != null ? null : '' })}
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
        <div className="form-group">
          <label>Total Duration *</label>
          <select
            className="form-input"
            value={formData.duration_override ?? ''}
            onChange={(e) => setFormData({ ...formData, duration_override: e.target.value === '' ? null : e.target.value })}
          >
            <option value="">Select duration</option>
            {Object.entries(DURATION_OPTIONS_GROUPED).map(([group, options]) => (
              <optgroup key={group} label={group}>
                {options.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </optgroup>
            ))}
          </select>
        </div>
      </div>

      <div className="callout-toggle-group">
        <label>Requires investigation first?</label>
        <div className="callout-toggle-row">
          <button
            type="button"
            className={`callout-toggle ${formData.use_when_uncertain ? 'active' : ''}`}
            onClick={() => setFormData({ ...formData, use_when_uncertain: !formData.use_when_uncertain })}
            role="switch"
            aria-checked={formData.use_when_uncertain}
          >
            <span className="callout-toggle-slider" />
          </button>
          <span className="callout-toggle-label">
            {formData.use_when_uncertain
              ? 'Yes — the employee needs to assess/investigate before starting the actual work'
              : 'No — the employee can start the job straight away'}
          </span>
        </div>
        <span className="form-hint">
          Turn this on when the caller's issue needs diagnosing first and the time/scope isn't predictable. E.g., a "Leak Investigation" where the source is unknown, or an "Electrical Fault Finding" where the cause needs tracing.
        </span>
      </div>

      <DefaultMaterialsPicker
        materials={materialsCatalog}
        selectedMaterials={formData.default_materials || []}
        onChange={(mats) => setFormData({ ...formData, default_materials: mats })}
      />

      <div className="form-actions">
        <button type="button" className="btn btn-secondary" onClick={onCancel}>Cancel</button>
        <button type="submit" className="btn btn-primary" disabled={isPending}>
          {isPending ? 'Saving...' : (isNew ? 'Add Package' : 'Save Package')}
        </button>
      </div>
    </form>
  );
}

function PackageCard({ pkg, services, isEditing, onEdit, onSave, onCancel, onDelete, isPending, getSelectedServiceDetails, materialsCatalog }) {
  const resolvedServices = (pkg.services || [])
    .sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0))
    .map(ref => {
      const svc = services.find(s => s.id === (ref.service_id || ref.id));
      return svc ? { ...svc, sort_order: ref.sort_order } : (ref.name ? ref : null);
    })
    .filter(Boolean);

  const [editData, setEditData] = useState({
    id: null,
    name: '',
    description: '',
    selectedServiceIds: [],
    price_override: null,
    price_max_override: null,
    duration_override: null,
    use_when_uncertain: false,
    default_materials: [],
  });

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
        duration_override: pkg.duration_override != null ? pkg.duration_override : null,
        use_when_uncertain: pkg.use_when_uncertain || false,
        default_materials: Array.isArray(pkg.default_materials) ? pkg.default_materials :
          (typeof pkg.default_materials === 'string' ? JSON.parse(pkg.default_materials || '[]') : []),
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
          materialsCatalog={materialsCatalog}
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
            <span className="badge-uncertain" title="Employee needs to assess/investigate before starting — time and scope may vary">
              🔍 Requires investigation
            </span>
          )}
          {Array.isArray(pkg.default_materials) && pkg.default_materials.length > 0 && (
            <span className="meta-item callout-badge" title={`${pkg.default_materials.length} default material${pkg.default_materials.length !== 1 ? 's' : ''}`}>
              <i className="fas fa-cubes"></i> {pkg.default_materials.length} material{pkg.default_materials.length !== 1 ? 's' : ''}
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
