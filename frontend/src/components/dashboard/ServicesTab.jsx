import { useState, useEffect, useMemo, lazy, Suspense } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../../context/AuthContext';
import { useIndustry } from '../../context/IndustryContext';
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

// Lazy-load MenuDesigner — only loaded for restaurant industry
const MenuDesigner = lazy(() => import('./MenuDesigner'));

// ─── Months for seasonal picker ──────────────────────────────────────────────
const MONTHS = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

// ─── Filter duration groups based on industry config ─────────────────────────
function getFilteredDurationGroups(allowedGroups) {
  if (!allowedGroups || allowedGroups.length === 0) return DURATION_OPTIONS_GROUPED;
  const filtered = {};
  for (const group of allowedGroups) {
    if (DURATION_OPTIONS_GROUPED[group]) {
      filtered[group] = DURATION_OPTIONS_GROUPED[group];
    }
  }
  return Object.keys(filtered).length > 0 ? filtered : DURATION_OPTIONS_GROUPED;
}

// ─── Empty form state ────────────────────────────────────────────────────────
const EMPTY_FORM = {
  name: '', 
  description: '',
  price: '', 
  price_max: null,
  duration: '60', 
  image_url: '', 
  employees_required: '1',
  employee_restrictions: { type: 'all', employee_ids: [] },
  requires_callout: false,
  requires_quote: false,
  package_only: false,
  show_price_duration: false,
  default_materials: [],
  // New industry fields
  category: '',
  tags: [],
  capacity_min: '',
  capacity_max: '',
  area: '',
  requires_deposit: false,
  deposit_amount: '',
  warranty: '',
  seasonal: false,
  seasonal_months: [],
  ai_notes: '',
  follow_up_service_id: '',
};

function ServicesTab() {
  const { hasActiveSubscription } = useAuth();
  const isSubscriptionActive = hasActiveSubscription();
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const { terminology, features, serviceConfig } = useIndustry();
  const svc = serviceConfig || {};

  const [editingId, setEditingId] = useState(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [showMenuDesigner, setShowMenuDesigner] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState('name');
  const [sortDir, setSortDir] = useState('asc');
  const [viewMode, setViewMode] = useState('grid');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [formData, setFormData] = useState({ ...EMPTY_FORM });
  const [deleteConfirm, setDeleteConfirm] = useState({ show: false, service: null });

  const durationGroups = useMemo(() => getFilteredDurationGroups(svc.durationGroups), [svc.durationGroups]);

  const { data: employeesData } = useQuery({
    queryKey: ['employees'],
    queryFn: async () => { const r = await getEmployees(); return r.data; },
  });
  const employees = Array.isArray(employeesData) ? employeesData : (employeesData?.employees || []);

  const { data: materialsData } = useQuery({
    queryKey: ['materials'],
    queryFn: async () => { const r = await getMaterials(); return r.data; },
  });
  const materialsCatalog = materialsData?.materials || [];

  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && deleteConfirm.show) setDeleteConfirm({ show: false, service: null });
    };
    if (deleteConfirm.show) document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [deleteConfirm.show]);

  const handleAddClick = () => {
    if (!isSubscriptionActive) { addToast(`Please upgrade your plan to add ${(terminology.services || 'services').toLowerCase()}`, 'warning'); return; }
    setShowAddForm(!showAddForm);
  };

  const { data: menu, isLoading } = useQuery({
    queryKey: ['services-menu'],
    queryFn: async () => { const r = await getServicesMenu(); return r.data; },
  });

  const createMutation = useMutation({
    mutationFn: createService,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['services-menu'] });
      addToast(`${terminology.service || 'Service'} added!`, 'success');
      setShowAddForm(false);
      setFormData({ ...EMPTY_FORM });
    },
    onError: () => addToast(`Failed to add ${(terminology.service || 'service').toLowerCase()}`, 'error'),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => updateService(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['services-menu'] });
      addToast(`${terminology.service || 'Service'} updated!`, 'success');
      setEditingId(null);
    },
    onError: () => addToast(`Failed to update ${(terminology.service || 'service').toLowerCase()}`, 'error'),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteService,
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['services-menu'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      const jobsAffected = response.data?.jobs_affected || 0;
      addToast(`${terminology.service || 'Service'} deleted${jobsAffected > 0 ? ` (${jobsAffected} ${terminology.job?.toLowerCase() || 'job'}${jobsAffected !== 1 ? 's' : ''} used this ${(terminology.service || 'service').toLowerCase()})` : ''}`, 'success');
      setDeleteConfirm({ show: false, service: null });
    },
    onError: () => { setDeleteConfirm({ show: false, service: null }); addToast(`Failed to delete ${(terminology.service || 'service').toLowerCase()}`, 'error'); },
  });

  // ─── Build payload from form data ──────────────────────────────────────────
  function buildPayload(fd) {
    const restrictions = fd.employee_restrictions?.type === 'all' ? null : fd.employee_restrictions;
    return {
      name: fd.name,
      description: fd.description || null,
      price: Math.round((parseFloat(fd.price) || 0) * 100) / 100,
      price_max: fd.price_max && parseFloat(fd.price_max) > (parseFloat(fd.price) || 0) 
        ? Math.round(parseFloat(fd.price_max) * 100) / 100 : null,
      duration_minutes: parseInt(fd.duration || fd.duration_minutes) || 60,
      image_url: fd.image_url,
      employees_required: parseInt(fd.employees_required) || 1,
      employee_restrictions: restrictions,
      requires_callout: fd.requires_callout || false,
      requires_quote: fd.requires_quote || false,
      package_only: fd.package_only || false,
      default_materials: fd.default_materials || [],
      // New fields
      category: fd.category || null,
      tags: Array.isArray(fd.tags) && fd.tags.length > 0 ? fd.tags : null,
      capacity_min: fd.capacity_min ? parseInt(fd.capacity_min) : null,
      capacity_max: fd.capacity_max ? parseInt(fd.capacity_max) : null,
      area: fd.area || null,
      requires_deposit: fd.requires_deposit || false,
      deposit_amount: fd.requires_deposit && fd.deposit_amount ? Math.round(parseFloat(fd.deposit_amount) * 100) / 100 : null,
      warranty: fd.warranty || null,
      seasonal: fd.seasonal || false,
      seasonal_months: fd.seasonal && Array.isArray(fd.seasonal_months) && fd.seasonal_months.length > 0 ? fd.seasonal_months : null,
      ai_notes: fd.ai_notes || null,
      follow_up_service_id: fd.follow_up_service_id || null,
    };
  }

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!formData.name.trim()) return;
    const rt = formData.employee_restrictions?.type;
    const hasIds = formData.employee_restrictions?.employee_ids?.length > 0;
    if ((rt === 'only' || rt === 'except') && !hasIds) {
      addToast('Please select at least one employee for the restriction', 'warning'); return;
    }
    createMutation.mutate(buildPayload(formData));
  };

  const handleUpdate = (service) => {
    const rt = service.employee_restrictions?.type;
    const hasIds = service.employee_restrictions?.employee_ids?.length > 0;
    if ((rt === 'only' || rt === 'except') && !hasIds) {
      addToast('Please select at least one employee for the restriction', 'warning'); return;
    }
    updateMutation.mutate({ id: service.id, data: buildPayload(service) });
  };

  const handleDelete = (service) => setDeleteConfirm({ show: true, service });
  const confirmDelete = () => { if (deleteConfirm.service) deleteMutation.mutate(deleteConfirm.service.id); };
  const startEdit = (service) => setEditingId(service.id);

  const services = menu?.services || [];

  // ─── Filter & sort ─────────────────────────────────────────────────────────
  const filteredServices = useMemo(() => {
    let result = [...services];
    if (categoryFilter) result = result.filter(s => s.category === categoryFilter);
    if (searchTerm.trim()) {
      const term = searchTerm.toLowerCase();
      result = result.filter(s => {
        if (s.name?.toLowerCase().includes(term)) return true;
        if (s.description?.toLowerCase().includes(term)) return true;
        if (s.category?.toLowerCase().includes(term)) return true;
        // tags may be an array or a JSON string from the backend
        let tags = s.tags;
        if (typeof tags === 'string') { try { tags = JSON.parse(tags); } catch { tags = []; } }
        if (Array.isArray(tags) && tags.some(t => String(t).toLowerCase().includes(term))) return true;
        return false;
      });
    }
    result.sort((a, b) => {
      let cmp = 0;
      switch (sortBy) {
        case 'name': cmp = (a.name || '').localeCompare(b.name || ''); break;
        case 'price': cmp = (parseFloat(a.price) || 0) - (parseFloat(b.price) || 0); break;
        case 'duration': cmp = (a.duration_minutes || 0) - (b.duration_minutes || 0); break;
        case 'category': cmp = (a.category || '').localeCompare(b.category || ''); break;
        default: cmp = 0;
      }
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return result;
  }, [services, searchTerm, sortBy, sortDir, categoryFilter]);

  // Unique categories from existing services
  const usedCategories = useMemo(() => {
    const cats = new Set(services.map(s => s.category).filter(Boolean));
    return [...cats].sort();
  }, [services]);

  const toggleSort = (field) => {
    if (sortBy === field) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortBy(field); setSortDir('asc'); }
  };

  if (isLoading) return <LoadingSpinner message={`Loading ${(terminology.services || 'services').toLowerCase()}...`} />;

  return (
    <div className="services-tab">
      <div className="services-header">
        <div>
          <h2>{terminology.services || 'Services'}</h2>
          <p className="services-subtitle">
            {services.length} {services.length !== 1 ? (terminology.services || 'services').toLowerCase() : (terminology.service || 'service').toLowerCase()} · Manage your {(terminology.services || 'services').toLowerCase()} and pricing
          </p>
        </div>
        <div className="services-controls">
          {features.menuDesigner && (
            <button className="btn-secondary" onClick={() => setShowMenuDesigner(true)} style={{ marginRight: '0.5rem' }}>
              <i className="fas fa-file-pdf"></i> Design Menu
            </button>
          )}
          <button className="btn-add" onClick={handleAddClick}>
            <i className={`fas ${isSubscriptionActive ? 'fa-plus' : 'fa-lock'}`}></i> Add {terminology.service || 'Service'}
          </button>
        </div>
      </div>

      {showAddForm && (
        <ServiceForm
          formData={formData}
          setFormData={setFormData}
          onSubmit={handleSubmit}
          onCancel={() => setShowAddForm(false)}
          isPending={createMutation.isPending}
          employees={employees}
          services={services}
          materialsCatalog={materialsCatalog}
          svc={svc}
          features={features}
          terminology={terminology}
          durationGroups={durationGroups}
          isNew
        />
      )}

      {services.length > 0 && (
        <div className="svc-toolbar">
          <div className="svc-search">
            <i className="fas fa-search"></i>
            <input type="text" placeholder={`Search ${(terminology.services || 'services').toLowerCase()}...`} value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} />
            {searchTerm && (
              <button className="svc-search-clear" onClick={() => setSearchTerm('')} aria-label="Clear search"><i className="fas fa-times"></i></button>
            )}
          </div>
          <div className="svc-toolbar-right">
            {svc.showCategory && usedCategories.length > 0 && (
              <select className="svc-category-filter" value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)} aria-label="Filter by category">
                <option value="">All categories</option>
                {(svc.categories || []).filter(c => usedCategories.includes(c)).map(c => (
                  <option key={c} value={c}>{c}</option>
                ))}
                {usedCategories.filter(c => !(svc.categories || []).includes(c)).map(c => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            )}
            <div className="svc-sort-chips">
              {[
                { key: 'name', label: 'Name', icon: 'fa-font' },
                { key: 'price', label: 'Price', icon: 'fa-euro-sign' },
                { key: 'duration', label: 'Duration', icon: 'fa-clock' },
              ].map(s => (
                <button key={s.key} className={`svc-sort-chip ${sortBy === s.key ? 'active' : ''}`} onClick={() => toggleSort(s.key)} title={`Sort by ${s.label}`}>
                  <i className={`fas ${s.icon}`}></i>
                  <span className="svc-sort-chip-label">{s.label}</span>
                  {sortBy === s.key && <i className={`fas fa-arrow-${sortDir === 'asc' ? 'up' : 'down'} svc-sort-dir`}></i>}
                </button>
              ))}
            </div>
            <div className="svc-view-toggle">
              <button className={`svc-view-btn ${viewMode === 'grid' ? 'active' : ''}`} onClick={() => setViewMode('grid')} title="Grid view" aria-label="Grid view"><i className="fas fa-th-large"></i></button>
              <button className={`svc-view-btn ${viewMode === 'list' ? 'active' : ''}`} onClick={() => setViewMode('list')} title="List view" aria-label="List view"><i className="fas fa-list"></i></button>
            </div>
          </div>
        </div>
      )}

      {services.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">{svc.emptyIcon || '🔧'}</div>
          <p>{svc.emptyTitle || 'No services yet'}</p>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '-0.5rem' }}>{svc.emptyDescription || ''}</p>
          <button className="btn btn-primary" onClick={handleAddClick}>Add Your First {terminology.service || 'Service'}</button>
        </div>
      ) : filteredServices.length === 0 ? (
        <div className="svc-no-results">
          <i className="fas fa-search"></i>
          <p>No services match "{searchTerm || categoryFilter}"</p>
          <button className="btn btn-secondary btn-sm" onClick={() => { setSearchTerm(''); setCategoryFilter(''); }}>Clear filters</button>
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
              services={services}
              viewMode={viewMode}
              materialsCatalog={materialsCatalog}
              svc={svc}
              features={features}
              terminology={terminology}
              durationGroups={durationGroups}
            />
          ))}
        </div>
      )}

      {deleteConfirm.show && deleteConfirm.service && (
        <div className="delete-confirm-overlay">
          <div className="delete-confirm-dialog">
            <div className="delete-confirm-icon"><i className="fas fa-exclamation-triangle"></i></div>
            <h3>Delete {terminology.service || 'Service'}?</h3>
            <p className="delete-warning">This will permanently delete <strong>{deleteConfirm.service.name}</strong>.</p>
            <p className="delete-cascade-warning">
              <i className="fas fa-info-circle"></i>
              {terminology.jobs} using this service will keep their service type but the service will no longer be available for new {terminology.booking?.toLowerCase()}s.
            </p>
            <div className="delete-confirm-actions">
              <button className="btn btn-secondary" onClick={() => setDeleteConfirm({ show: false, service: null })}>Cancel</button>
              <button className="btn btn-danger" onClick={confirmDelete} disabled={deleteMutation.isPending}>
                {deleteMutation.isPending ? 'Deleting...' : `Delete ${terminology.service || 'Service'}`}
              </button>
            </div>
          </div>
        </div>
      )}

      <PackagesSection services={services} isSubscriptionActive={isSubscriptionActive} materialsCatalog={materialsCatalog} durationGroups={durationGroups} />

      {/* Menu Designer modal — restaurant industry only */}
      {features.menuDesigner && showMenuDesigner && (
        <Suspense fallback={<LoadingSpinner />}>
          <MenuDesigner
            services={services}
            svc={svc}
            onClose={() => setShowMenuDesigner(false)}
          />
        </Suspense>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// ServiceForm — Industry-aware add/edit form
// ═══════════════════════════════════════════════════════════════════════════════
function ServiceForm({ formData, setFormData, onSubmit, onCancel, isPending, employees, services, materialsCatalog, svc, features, terminology, durationGroups, isNew }) {
  const [tagInput, setTagInput] = useState('');

  const addTag = (tag) => {
    const trimmed = tag.trim();
    if (!trimmed) return;
    const current = formData.tags || [];
    if (!current.includes(trimmed)) setFormData({ ...formData, tags: [...current, trimmed] });
    setTagInput('');
  };

  const removeTag = (tag) => {
    setFormData({ ...formData, tags: (formData.tags || []).filter(t => t !== tag) });
  };

  const toggleMonth = (idx) => {
    const months = formData.seasonal_months || [];
    setFormData({
      ...formData,
      seasonal_months: months.includes(idx) ? months.filter(m => m !== idx) : [...months, idx],
    });
  };

  const showPriceDuration = !formData.package_only || formData.show_price_duration;

  return (
    <form className="service-form-card" onSubmit={onSubmit}>
      <h3>{isNew ? `New ${terminology.service || 'Service'}` : `Edit ${terminology.service || 'Service'}`}</h3>

      {/* ─── Name + Category row ─────────────────────────────────────── */}
      <div className="form-grid">
        <div className={`form-group ${svc.showCategory ? '' : 'form-group-wide'}`}>
          <label>{terminology.service || 'Service'} Name *</label>
          <input type="text" className="form-input" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} placeholder="e.g., Emergency Plumbing" required />
        </div>
        {svc.showCategory && (
          <div className="form-group">
            <label>Category</label>
            <select className="form-input" value={formData.category || ''} onChange={(e) => setFormData({ ...formData, category: e.target.value })}>
              <option value="">No category</option>
              {(svc.categories || []).map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
        )}
      </div>

      <div className="form-grid">
        <div className="form-group form-group-wide">
          <label>Description (optional)</label>
          <textarea className="form-input" value={formData.description} onChange={(e) => setFormData({ ...formData, description: e.target.value })} placeholder="Brief description of this service" rows={2} />
        </div>
      </div>

      {/* ─── Tags ────────────────────────────────────────────────────── */}
      {svc.showTags && (
        <div className="form-group" style={{ marginBottom: '0.75rem' }}>
          <label>{svc.tagLabel || 'Tags'}</label>
          <div className="svc-tags-wrap">
            {(formData.tags || []).map(tag => (
              <span key={tag} className="svc-tag">
                {tag}
                <button type="button" onClick={() => removeTag(tag)} className="svc-tag-remove" aria-label={`Remove ${tag}`}><i className="fas fa-times"></i></button>
              </span>
            ))}
            <input
              type="text"
              className="svc-tag-input"
              value={tagInput}
              onChange={(e) => setTagInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); addTag(tagInput); } }}
              onBlur={() => addTag(tagInput)}
              placeholder={formData.tags?.length ? '' : (svc.tagPlaceholder || 'Add tags...')}
            />
          </div>
          {(svc.tagPresets || []).length > 0 && (
            <div className="svc-tag-presets">
              {svc.tagPresets.filter(t => !(formData.tags || []).includes(t)).slice(0, 8).map(t => (
                <button key={t} type="button" className="svc-tag-preset" onClick={() => addTag(t)}>+ {t}</button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ─── Package Only toggle ─────────────────────────────────────── */}
      <div className="callout-toggle-group">
        <label>Package Only? <HelpTooltip text="If enabled, this service can only be booked as part of a package — not on its own." /></label>
        <div className="callout-toggle-row">
          <button type="button" className={`callout-toggle ${formData.package_only ? 'active' : ''}`} onClick={() => setFormData({ ...formData, package_only: !formData.package_only })} role="switch" aria-checked={formData.package_only}>
            <span className="callout-toggle-slider" />
          </button>
          <span className="callout-toggle-label">{formData.package_only ? 'Yes — only available as part of a package' : 'No — available as a standalone service'}</span>
        </div>
      </div>

      {formData.package_only && (
        <div className="callout-toggle-group">
          <label>Set Price & Duration?</label>
          <div className="callout-toggle-row">
            <button type="button" className={`callout-toggle ${formData.show_price_duration ? 'active' : ''}`} onClick={() => setFormData({ ...formData, show_price_duration: !formData.show_price_duration })} role="switch" aria-checked={formData.show_price_duration || false}>
              <span className="callout-toggle-slider" />
            </button>
            <span className="callout-toggle-label">{formData.show_price_duration ? 'Yes — set individual price & duration' : 'No — price & duration will come from the package'}</span>
          </div>
        </div>
      )}

      {/* ─── Price + Duration ────────────────────────────────────────── */}
      {showPriceDuration && (
        <div className="form-grid">
          <div className="form-group">
            <label>Price (€)</label>
            {formData.price_max != null && formData.price_max !== undefined && <span className="price-from-label">from</span>}
            <input type="number" className="form-input" value={formData.price} onChange={(e) => setFormData({ ...formData, price: e.target.value })} placeholder="0.00" step="0.01" min="0" />
            <div className="price-range-toggle-row">
              <button type="button" className={`price-range-toggle ${formData.price_max != null && formData.price_max !== undefined ? 'active' : ''}`} onClick={() => setFormData({ ...formData, price_max: formData.price_max != null && formData.price_max !== undefined ? null : '' })} role="switch" aria-checked={formData.price_max != null && formData.price_max !== undefined}>
                <span className="price-range-toggle-slider" />
              </button>
              <span className="price-range-toggle-label">Price range</span>
            </div>
            {formData.price_max != null && formData.price_max !== undefined && (
              <div className="price-max-row"><div className="price-max-field"><span className="price-max-label">to</span><input type="number" className="form-input" value={formData.price_max} onChange={(e) => setFormData({ ...formData, price_max: e.target.value })} placeholder="Max price" step="0.01" min="0" autoFocus /></div></div>
            )}
          </div>
          <div className="form-group">
            <label>Duration</label>
            <select className="form-input" value={formData.duration || formData.duration_minutes || '60'} onChange={(e) => setFormData({ ...formData, duration: e.target.value, duration_minutes: parseInt(e.target.value) })}>
              {Object.entries(durationGroups).map(([group, options]) => (
                <optgroup key={group} label={group}>
                  {options.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                </optgroup>
              ))}
            </select>
          </div>
        </div>
      )}

      {/* ─── Capacity (restaurant: party size) ───────────────────────── */}
      {svc.showCapacity && (
        <div className="form-grid">
          <div className="form-group">
            <label>{svc.capacityMinLabel || 'Min capacity'}</label>
            <input type="number" className="form-input" value={formData.capacity_min || ''} onChange={(e) => setFormData({ ...formData, capacity_min: e.target.value })} placeholder="e.g., 1" min="1" />
          </div>
          <div className="form-group">
            <label>{svc.capacityMaxLabel || 'Max capacity'}</label>
            <input type="number" className="form-input" value={formData.capacity_max || ''} onChange={(e) => setFormData({ ...formData, capacity_max: e.target.value })} placeholder="e.g., 12" min="1" />
          </div>
        </div>
      )}

      {/* ─── Area (restaurant: dining section) ───────────────────────── */}
      {svc.showArea && (svc.areaOptions || []).length > 0 && (
        <div className="form-grid">
          <div className="form-group">
            <label>{svc.areaLabel || 'Area'}</label>
            <select className="form-input" value={formData.area || ''} onChange={(e) => setFormData({ ...formData, area: e.target.value })}>
              <option value="">Any area</option>
              {svc.areaOptions.map(a => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
        </div>
      )}

      {/* ─── Employees Required ──────────────────────────────────────── */}
      <div className="form-grid">
        <div className="form-group">
          <label>{terminology.employees || 'Employees'} Required <HelpTooltip text={`How many ${(terminology.employees || 'employees').toLowerCase()} are needed at the same time for this service.`} /></label>
          <div className="employees-input-wrapper">
            <button type="button" className="employees-btn" onClick={() => setFormData({ ...formData, employees_required: Math.max(1, parseInt(formData.employees_required || 1) - 1).toString() })} disabled={parseInt(formData.employees_required || 1) <= 1}><i className="fas fa-minus"></i></button>
            <span className="employees-value">{formData.employees_required || 1}</span>
            <button type="button" className="employees-btn" onClick={() => setFormData({ ...formData, employees_required: (parseInt(formData.employees_required || 1) + 1).toString() })} disabled={parseInt(formData.employees_required || 1) >= 10}><i className="fas fa-plus"></i></button>
          </div>
        </div>
      </div>

      <EmployeeRestrictions restrictions={formData.employee_restrictions} onChange={(r) => setFormData({ ...formData, employee_restrictions: r })} employees={employees} terminology={terminology} />

      {/* ─── Callout toggle (trades only) ────────────────────────────── */}
      {features.callouts && !formData.package_only && (
        <div className="callout-toggle-group">
          <label>Requires Initial Callout? <HelpTooltip text="If enabled, the AI books a callout visit first so an employee can assess the job." /></label>
          <div className="callout-toggle-row">
            <button type="button" className={`callout-toggle ${formData.requires_callout ? 'active' : ''}`} onClick={() => setFormData({ ...formData, requires_callout: !formData.requires_callout, requires_quote: false })} role="switch" aria-checked={formData.requires_callout}><span className="callout-toggle-slider" /></button>
            <span className="callout-toggle-label">{formData.requires_callout ? 'Yes — AI will book a callout visit instead of the full job' : 'No — book the full job directly'}</span>
          </div>
        </div>
      )}

      {/* ─── Quote toggle (trades/cleaning) ──────────────────────────── */}
      {features.quotes && !formData.package_only && !formData.requires_callout && (
        <div className="callout-toggle-group">
          <label>Requires Quote Visit? <HelpTooltip text="If enabled, the AI books a free quote visit first so an employee can assess and quote the job." /></label>
          <div className="callout-toggle-row">
            <button type="button" className={`callout-toggle ${formData.requires_quote ? 'active' : ''}`} onClick={() => setFormData({ ...formData, requires_quote: !formData.requires_quote })} role="switch" aria-checked={formData.requires_quote}><span className="callout-toggle-slider" /></button>
            <span className="callout-toggle-label">{formData.requires_quote ? 'Yes — AI will book a free quote visit instead of the full job' : 'No — book the full job directly'}</span>
          </div>
        </div>
      )}

      {/* ─── Deposit toggle ──────────────────────────────────────────── */}
      {svc.showDeposit && (
        <div className="callout-toggle-group">
          <label>{svc.depositLabel || 'Deposit Required'} <HelpTooltip text={svc.depositHint || 'Require a deposit before confirming'} /></label>
          <div className="callout-toggle-row">
            <button type="button" className={`callout-toggle ${formData.requires_deposit ? 'active' : ''}`} onClick={() => setFormData({ ...formData, requires_deposit: !formData.requires_deposit })} role="switch" aria-checked={formData.requires_deposit}><span className="callout-toggle-slider" /></button>
            <span className="callout-toggle-label">{formData.requires_deposit ? 'Yes — deposit required' : 'No deposit needed'}</span>
          </div>
          {formData.requires_deposit && (
            <div style={{ marginTop: '0.5rem', maxWidth: '200px' }}>
              <input type="number" className="form-input" value={formData.deposit_amount || ''} onChange={(e) => setFormData({ ...formData, deposit_amount: e.target.value })} placeholder="Deposit amount (€)" step="0.01" min="0" />
            </div>
          )}
        </div>
      )}

      {/* ─── Warranty (trades) ───────────────────────────────────────── */}
      {svc.showWarranty && (
        <div className="form-group" style={{ marginTop: '0.5rem' }}>
          <label>{svc.warrantyLabel || 'Warranty'}</label>
          <input type="text" className="form-input" value={formData.warranty || ''} onChange={(e) => setFormData({ ...formData, warranty: e.target.value })} placeholder={svc.warrantyPlaceholder || 'e.g., 12-month guarantee'} />
        </div>
      )}

      {/* ─── Seasonal toggle ─────────────────────────────────────────── */}
      {svc.showSeasonal && (
        <div className="callout-toggle-group">
          <label>{svc.seasonalLabel || 'Seasonal Service'} <HelpTooltip text={svc.seasonalHint || 'Only available during certain months'} /></label>
          <div className="callout-toggle-row">
            <button type="button" className={`callout-toggle ${formData.seasonal ? 'active' : ''}`} onClick={() => setFormData({ ...formData, seasonal: !formData.seasonal })} role="switch" aria-checked={formData.seasonal}><span className="callout-toggle-slider" /></button>
            <span className="callout-toggle-label">{formData.seasonal ? 'Yes — only available in selected months' : 'No — available year-round'}</span>
          </div>
          {formData.seasonal && (
            <div className="svc-months-grid">
              {MONTHS.map((m, idx) => (
                <button key={m} type="button" className={`svc-month-chip ${(formData.seasonal_months || []).includes(idx) ? 'active' : ''}`} onClick={() => toggleMonth(idx)}>{m}</button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ─── AI Notes ────────────────────────────────────────────────── */}
      {svc.showAiNotes && (
        <div className="form-group" style={{ marginTop: '0.5rem' }}>
          <label>{svc.aiNotesLabel || 'Notes for AI'} <HelpTooltip text="These notes are included in the AI prompt for this service. Use them to guide the AI's behaviour." /></label>
          <textarea className="form-input" value={formData.ai_notes || ''} onChange={(e) => setFormData({ ...formData, ai_notes: e.target.value })} placeholder={svc.aiNotesPlaceholder || 'Notes for the AI receptionist...'} rows={2} />
        </div>
      )}

      {/* ─── Follow-up service (trades/salon/cleaning) ───────────────── */}
      {svc.showFollowUp && services.length > 0 && (
        <div className="form-group" style={{ marginTop: '0.5rem' }}>
          <label>{svc.followUpLabel || 'Follow-up Service'} <HelpTooltip text={svc.followUpHint || 'Suggest this service as a follow-up'} /></label>
          <select className="form-input" value={formData.follow_up_service_id || ''} onChange={(e) => setFormData({ ...formData, follow_up_service_id: e.target.value })}>
            <option value="">None</option>
            {services.filter(s => s.id !== formData.id).map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </div>
      )}

      {/* ─── Image ───────────────────────────────────────────────────── */}
      <div className="form-group" style={{ marginTop: '0.5rem' }}>
        <label>Image (optional)</label>
        <ImageUpload value={formData.image_url} onChange={(value) => setFormData({ ...formData, image_url: value })} placeholder="Upload Image" />
      </div>

      {/* ─── Default Materials ───────────────────────────────────────── */}
      {features.materials && (
        <DefaultMaterialsPicker materials={materialsCatalog} selectedMaterials={formData.default_materials || []} onChange={(mats) => setFormData({ ...formData, default_materials: mats })} />
      )}

      <div className="form-actions">
        <button type="button" className="btn btn-secondary" onClick={onCancel}>Cancel</button>
        <button type="submit" className="btn btn-primary" disabled={isPending}>{isPending ? 'Saving...' : (isNew ? `Add ${terminology.service || 'Service'}` : 'Save')}</button>
      </div>
    </form>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// DefaultMaterialsPicker
// ═══════════════════════════════════════════════════════════════════════════════
function DefaultMaterialsPicker({ materials, selectedMaterials, onChange }) {
  const [search, setSearch] = useState('');
  const catalog = materials || [];
  const selected = Array.isArray(selectedMaterials) ? selectedMaterials : [];
  const filtered = catalog.filter(m => !search || m.name.toLowerCase().includes(search.toLowerCase()));

  const addMaterial = (mat) => {
    if (selected.find(m => m.material_id === mat.id)) return;
    onChange([...selected, { material_id: mat.id, name: mat.name, unit_price: parseFloat(mat.unit_price) || 0, unit: mat.unit || 'each', quantity: 1 }]);
  };
  const removeMaterial = (idx) => onChange(selected.filter((_, i) => i !== idx));
  const updateQuantity = (idx, rawVal) => {
    const updated = [...selected];
    if (rawVal === '' || rawVal === undefined) updated[idx] = { ...updated[idx], quantity: '' };
    else { const parsed = parseFloat(rawVal); updated[idx] = { ...updated[idx], quantity: isNaN(parsed) ? '' : parsed }; }
    onChange(updated);
  };
  const finalizeQuantity = (idx) => {
    const updated = [...selected];
    const val = parseFloat(updated[idx].quantity);
    updated[idx] = { ...updated[idx], quantity: isNaN(val) || val <= 0 ? 1 : val };
    onChange(updated);
  };
  const safePrice = (mat) => ((parseFloat(mat.unit_price) || 0) * (parseFloat(mat.quantity) || 0)).toFixed(2);
  const totalCost = selected.reduce((sum, m) => sum + (parseFloat(m.unit_price) || 0) * (parseFloat(m.quantity) || 0), 0).toFixed(2);

  return (
    <div className="default-materials-picker">
      <label>Default Materials <span className="form-hint-inline">— auto-added when a job is created</span></label>
      {selected.length > 0 && (
        <div className="dm-selected-list">
          {selected.map((mat, idx) => (
            <div key={mat.material_id || idx} className="dm-selected-item">
              <span className="dm-item-name">{mat.name}</span>
              <div className="dm-item-qty">
                <input type="number" value={mat.quantity} onChange={(e) => updateQuantity(idx, e.target.value)} onBlur={() => finalizeQuantity(idx)} min="0.01" step="0.01" className="dm-qty-input" />
                <span className="dm-item-unit">{mat.unit || 'each'}</span>
              </div>
              <span className="dm-item-price">€{safePrice(mat)}</span>
              <button type="button" className="dm-remove-btn" onClick={() => removeMaterial(idx)} title="Remove" aria-label="Remove material"><i className="fas fa-times"></i></button>
            </div>
          ))}
          <div className="dm-total">Total: €{totalCost}</div>
        </div>
      )}
      {catalog.length > 0 ? (
        <div className="dm-catalog">
          {catalog.length > 5 && <input type="text" className="dm-search" placeholder="Search materials..." value={search} onChange={(e) => setSearch(e.target.value)} />}
          <div className="dm-catalog-list">
            {filtered.slice(0, 20).map(mat => {
              const alreadyAdded = selected.some(m => m.material_id === mat.id);
              return (
                <button key={mat.id} type="button" className={`dm-catalog-item ${alreadyAdded ? 'dm-added' : ''}`} onClick={() => !alreadyAdded && addMaterial(mat)} disabled={alreadyAdded}>
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

// ═══════════════════════════════════════════════════════════════════════════════
// EmployeeRestrictions
// ═══════════════════════════════════════════════════════════════════════════════
function EmployeeRestrictions({ restrictions, onChange, employees, terminology }) {
  const type = restrictions?.type || 'all';
  const selectedIds = restrictions?.employee_ids || [];
  const handleTypeChange = (newType) => onChange({ type: newType, employee_ids: newType === 'all' ? [] : selectedIds });
  const toggleEmployee = (employeeId) => {
    const newIds = selectedIds.includes(employeeId) ? selectedIds.filter(id => id !== employeeId) : [...selectedIds, employeeId];
    onChange({ type, employee_ids: newIds });
  };
  const empLabel = (terminology?.employees || 'Employees').toLowerCase();

  if (!employees || employees.length === 0) {
    return (
      <div className="employee-restrictions">
        <label>Who Can Do This <HelpTooltip text={`Control which ${empLabel} are eligible for this service.`} /></label>
        <div className="no-employees-message"><i className="fas fa-info-circle"></i><span>Add {empLabel} in the {terminology?.employees || 'Employees'} tab to set restrictions</span></div>
      </div>
    );
  }

  return (
    <div className="employee-restrictions">
      <label>Who Can Do This <HelpTooltip text={`Control which ${empLabel} are eligible for this service.`} /></label>
      <div className="restriction-type-selector">
        <button type="button" className={`restriction-type-btn ${type === 'all' ? 'active' : ''}`} onClick={() => handleTypeChange('all')}><i className="fas fa-users"></i> All {terminology?.employees || 'Employees'}</button>
        <button type="button" className={`restriction-type-btn ${type === 'only' ? 'active' : ''}`} onClick={() => handleTypeChange('only')}><i className="fas fa-user-check"></i> Only Selected</button>
        <button type="button" className={`restriction-type-btn ${type === 'except' ? 'active' : ''}`} onClick={() => handleTypeChange('except')}><i className="fas fa-user-times"></i> All Except</button>
      </div>
      {type !== 'all' && (
        <div className="employee-selection">
          <span className="selection-hint">{type === 'only' ? `Select ${empLabel} who CAN do this:` : `Select ${empLabel} who CANNOT do this:`}</span>
          <div className="employee-chips">
            {employees.map(emp => (
              <button key={emp.id} type="button" className={`employee-chip ${selectedIds.includes(emp.id) ? 'selected' : ''}`} onClick={() => toggleEmployee(emp.id)}>
                <i className={`fas ${selectedIds.includes(emp.id) ? 'fa-check' : 'fa-user'}`}></i> {emp.name}
              </button>
            ))}
          </div>
          {type !== 'all' && selectedIds.length === 0 && <span className="selection-warning"><i className="fas fa-exclamation-circle"></i> Select at least one {terminology?.employee?.toLowerCase() || 'employee'}</span>}
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// ServiceCard — Display + inline edit
// ═══════════════════════════════════════════════════════════════════════════════
function ServiceCard({ service, isEditing, onEdit, onSave, onCancel, onDelete, isPending, employees, services, viewMode, materialsCatalog, svc, features, terminology, durationGroups }) {
  const [editData, setEditData] = useState(service);
  const [imageError, setImageError] = useState(false);

  useEffect(() => {
    if (isEditing) {
      const hasRange = service.price_max != null && parseFloat(service.price_max) > (parseFloat(service.price) || 0);
      // Safely parse JSON fields that may come as strings from the backend
      let parsedTags = service.tags;
      if (typeof parsedTags === 'string') { try { parsedTags = JSON.parse(parsedTags); } catch { parsedTags = []; } }
      if (!Array.isArray(parsedTags)) parsedTags = [];
      
      let parsedMonths = service.seasonal_months;
      if (typeof parsedMonths === 'string') { try { parsedMonths = JSON.parse(parsedMonths); } catch { parsedMonths = []; } }
      if (!Array.isArray(parsedMonths)) parsedMonths = [];
      
      let parsedMaterials = service.default_materials;
      if (typeof parsedMaterials === 'string') { try { parsedMaterials = JSON.parse(parsedMaterials); } catch { parsedMaterials = []; } }
      if (!Array.isArray(parsedMaterials)) parsedMaterials = [];
      
      let parsedRestrictions = service.employee_restrictions;
      if (typeof parsedRestrictions === 'string') { try { parsedRestrictions = JSON.parse(parsedRestrictions); } catch { parsedRestrictions = null; } }
      
      setEditData({
        ...service,
        price_max: hasRange ? service.price_max : null,
        employee_restrictions: parsedRestrictions || { type: 'all', employee_ids: [] },
        show_price_duration: service.package_only ? (parseFloat(service.price) > 0) : false,
        default_materials: parsedMaterials,
        tags: parsedTags,
        seasonal_months: parsedMonths,
      });
    }
  }, [isEditing, service]);

  useEffect(() => { setImageError(false); }, [service.image_url]);

  if (isEditing) {
    return (
      <div className="service-card editing">
        <ServiceForm
          formData={editData}
          setFormData={setEditData}
          onSubmit={(e) => { e.preventDefault(); onSave(editData); }}
          onCancel={onCancel}
          isPending={isPending}
          employees={employees}
          services={services}
          materialsCatalog={materialsCatalog}
          svc={svc}
          features={features}
          terminology={terminology}
          durationGroups={durationGroups}
          isNew={false}
        />
      </div>
    );
  }

  const getRestrictionSummary = () => {
    const r = service.employee_restrictions;
    if (!r || r.type === 'all') return null;
    const count = r.employee_ids?.length || 0;
    return r.type === 'only' ? `${count} ${(terminology?.employee || 'employee').toLowerCase()}${count !== 1 ? 's' : ''} only` : `All except ${count}`;
  };

  const restrictionSummary = getRestrictionSummary();
  const isGrid = viewMode === 'grid';
  let tags = service.tags;
  if (typeof tags === 'string') { try { tags = JSON.parse(tags); } catch { tags = []; } }
  if (!Array.isArray(tags)) tags = [];
  const defaultIcon = svc.defaultServiceIcon || 'fa-wrench';

  return (
    <div className={`service-card ${isGrid ? 'service-card-grid' : ''}`}>
      <div className={`service-image ${isGrid ? 'service-image-grid' : ''}`}>
        {service.image_url && !imageError ? (
          <img src={service.image_url} alt={service.name} onError={() => setImageError(true)} loading="lazy" />
        ) : (
          <i className={`fas ${defaultIcon}`}></i>
        )}
      </div>
      <div className="service-content">
        <h3 className="service-title">{service.name || `Unnamed ${terminology?.service || 'Service'}`}</h3>
        {service.description && <p className="service-description">{service.description}</p>}
        {isGrid && service.price > 0 && <div className="service-grid-price">{formatPriceRange(service.price, service.price_max)}</div>}
        <div className="service-meta">
          {!isGrid && service.price > 0 && <span className="meta-item price">{formatPriceRange(service.price, service.price_max)}</span>}
          {(service.duration_minutes || service.duration) && (
            <span className="meta-item duration"><i className="fas fa-clock"></i> {formatDuration(service.duration_minutes || service.duration)}</span>
          )}
          <span className="meta-item employees" title={`${terminology?.employees || 'Employees'} required`}>
            <i className="fas fa-user"></i> {service.employees_required || 1}
          </span>
          {service.category && <span className="meta-item svc-category-badge"><i className="fas fa-folder"></i> {service.category}</span>}
          {service.capacity_min && <span className="meta-item" title="Party size"><i className="fas fa-users"></i> {service.capacity_min}{service.capacity_max ? `–${service.capacity_max}` : '+'}</span>}
          {service.area && <span className="meta-item" title="Area"><i className="fas fa-map-marker-alt"></i> {service.area}</span>}
          {restrictionSummary && <span className="meta-item restriction" title="Employee restrictions"><i className="fas fa-user-lock"></i> {restrictionSummary}</span>}
          {service.requires_callout && <span className="meta-item callout-badge" title="Requires initial callout visit"><i className="fas fa-phone-alt"></i> Callout</span>}
          {service.requires_quote && <span className="meta-item callout-badge" title="Requires free quote visit"><i className="fas fa-file-invoice"></i> Quote</span>}
          {service.package_only && <span className="meta-item callout-badge" title="Only available as part of a package"><i className="fas fa-box"></i> Pkg only</span>}
          {service.requires_deposit && <span className="meta-item callout-badge" title={service.deposit_amount ? `€${service.deposit_amount} deposit` : 'Deposit required'}><i className="fas fa-credit-card"></i> Deposit{service.deposit_amount ? ` €${service.deposit_amount}` : ''}</span>}
          {service.warranty && <span className="meta-item callout-badge" title={service.warranty}><i className="fas fa-shield-alt"></i> Warranty</span>}
          {service.seasonal && <span className="meta-item callout-badge" title="Seasonal service"><i className="fas fa-snowflake"></i> Seasonal</span>}
          {Array.isArray(service.default_materials) && service.default_materials.length > 0 && (
            <span className="meta-item callout-badge" title={`${service.default_materials.length} default material${service.default_materials.length !== 1 ? 's' : ''}`}><i className="fas fa-cubes"></i> {service.default_materials.length} material{service.default_materials.length !== 1 ? 's' : ''}</span>
          )}
        </div>
        {tags.length > 0 && (
          <div className="svc-card-tags">
            {tags.slice(0, 4).map(t => <span key={t} className="svc-card-tag">{t}</span>)}
            {tags.length > 4 && <span className="svc-card-tag svc-card-tag-more">+{tags.length - 4}</span>}
          </div>
        )}
      </div>
      <div className={`service-actions ${isGrid ? 'service-actions-grid' : ''}`}>
        <button type="button" className="btn-icon" onClick={onEdit} title="Edit" aria-label="Edit service"><i className="fas fa-edit"></i></button>
        <button type="button" className="btn-icon danger" onClick={onDelete} title="Delete" aria-label="Delete service" disabled={isPending}><i className="fas fa-trash"></i></button>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// PackagesSection
// ═══════════════════════════════════════════════════════════════════════════════
function PackagesSection({ services, isSubscriptionActive, materialsCatalog, durationGroups }) {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingPkgId, setEditingPkgId] = useState(null);
  const [deletePkgConfirm, setDeletePkgConfirm] = useState({ show: false, pkg: null });
  const [pkgFormData, setPkgFormData] = useState({
    name: '', description: '', selectedServiceIds: [],
    price_override: null, price_max_override: null, duration_override: null,
    use_when_uncertain: false, default_materials: [],
  });

  const { data: packagesData } = useQuery({
    queryKey: ['packages'],
    queryFn: async () => { const r = await getPackages(); return r.data; },
  });
  const packages = packagesData?.packages || packagesData || [];

  useEffect(() => {
    const handleEscape = (e) => { if (e.key === 'Escape' && deletePkgConfirm.show) setDeletePkgConfirm({ show: false, pkg: null }); };
    if (deletePkgConfirm.show) document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [deletePkgConfirm.show]);

  const createPkgMutation = useMutation({
    mutationFn: createPackage,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['packages'] }); addToast('Package added!', 'success'); setShowAddForm(false); resetForm(); },
    onError: (err) => addToast(err?.response?.data?.error || 'Failed to add package', 'error'),
  });
  const updatePkgMutation = useMutation({
    mutationFn: ({ id, data }) => updatePackage(id, data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['packages'] }); addToast('Package updated!', 'success'); setEditingPkgId(null); },
    onError: (err) => addToast(err?.response?.data?.error || 'Failed to update package', 'error'),
  });
  const deletePkgMutation = useMutation({
    mutationFn: deletePackage,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['packages'] }); addToast('Package deleted!', 'success'); setDeletePkgConfirm({ show: false, pkg: null }); },
    onError: () => { setDeletePkgConfirm({ show: false, pkg: null }); addToast('Failed to delete package', 'error'); },
  });

  const resetForm = () => setPkgFormData({ name: '', description: '', selectedServiceIds: [], price_override: null, price_max_override: null, duration_override: null, use_when_uncertain: false, default_materials: [] });

  const handleAddClick = () => {
    if (!isSubscriptionActive) { addToast('Please upgrade your plan to add packages', 'warning'); return; }
    setShowAddForm(!showAddForm);
    if (showAddForm) resetForm();
  };

  const buildServicesPayload = (selectedIds) => selectedIds.map((id, idx) => ({ service_id: id, sort_order: idx }));

  const handlePkgSubmit = (e) => {
    e.preventDefault();
    if (!pkgFormData.name.trim()) return;
    if (pkgFormData.selectedServiceIds.length < 2) { addToast('A package needs at least 2 services', 'warning'); return; }
    const payload = { name: pkgFormData.name, description: pkgFormData.description || '', services: buildServicesPayload(pkgFormData.selectedServiceIds), use_when_uncertain: pkgFormData.use_when_uncertain, default_materials: pkgFormData.default_materials || [] };
    if (pkgFormData.price_override != null && pkgFormData.price_override !== '') {
      payload.price_override = Math.round((parseFloat(pkgFormData.price_override) || 0) * 100) / 100;
      if (pkgFormData.price_max_override != null && pkgFormData.price_max_override !== '') payload.price_max_override = Math.round((parseFloat(pkgFormData.price_max_override) || 0) * 100) / 100;
    }
    if (pkgFormData.duration_override != null && pkgFormData.duration_override !== '') payload.duration_override = parseInt(pkgFormData.duration_override) || null;
    createPkgMutation.mutate(payload);
  };

  const handlePkgUpdate = (pkgData) => {
    if (!pkgData.name?.trim()) return;
    if (pkgData.selectedServiceIds.length < 2) { addToast('A package needs at least 2 services', 'warning'); return; }
    const payload = { name: pkgData.name, description: pkgData.description || '', services: buildServicesPayload(pkgData.selectedServiceIds), use_when_uncertain: pkgData.use_when_uncertain, default_materials: pkgData.default_materials || [] };
    if (pkgData.price_override != null && pkgData.price_override !== '') {
      payload.price_override = Math.round((parseFloat(pkgData.price_override) || 0) * 100) / 100;
      if (pkgData.price_max_override != null && pkgData.price_max_override !== '') payload.price_max_override = Math.round((parseFloat(pkgData.price_max_override) || 0) * 100) / 100;
    } else { payload.price_override = null; payload.price_max_override = null; }
    if (pkgData.duration_override != null && pkgData.duration_override !== '') payload.duration_override = parseInt(pkgData.duration_override) || null;
    else payload.duration_override = null;
    updatePkgMutation.mutate({ id: pkgData.id, data: payload });
  };

  const confirmDeletePkg = () => { if (deletePkgConfirm.pkg) deletePkgMutation.mutate(deletePkgConfirm.pkg.id); };

  const toggleServiceSelection = (serviceId) => {
    setPkgFormData(prev => ({ ...prev, selectedServiceIds: prev.selectedServiceIds.includes(serviceId) ? prev.selectedServiceIds.filter(id => id !== serviceId) : [...prev.selectedServiceIds, serviceId] }));
  };
  const moveService = (index, direction) => {
    setPkgFormData(prev => {
      const ids = [...prev.selectedServiceIds]; const ni = index + direction;
      if (ni < 0 || ni >= ids.length) return prev;
      [ids[index], ids[ni]] = [ids[ni], ids[index]];
      return { ...prev, selectedServiceIds: ids };
    });
  };
  const getSelectedServiceDetails = (selectedIds) => {
    const selected = selectedIds.map(id => services.find(s => s.id === id)).filter(Boolean);
    return { selected, totalDuration: selected.reduce((s, sv) => s + (sv.duration_minutes || 0), 0), totalPrice: selected.reduce((s, sv) => s + (parseFloat(sv.price) || 0), 0), totalPriceMax: selected.reduce((s, sv) => s + (parseFloat(sv.price_max) || parseFloat(sv.price) || 0), 0) };
  };

  return (
    <div className="packages-section">
      <div className="packages-header">
        <div><h2>📦 Packages</h2><p className="services-subtitle">Bundle multiple services into ordered sequences</p></div>
        <div className="services-controls"><button className="btn btn-primary" onClick={handleAddClick}><i className={`fas ${isSubscriptionActive ? 'fa-plus' : 'fa-lock'}`}></i> Add Package</button></div>
      </div>

      {showAddForm && (
        <PackageForm formData={pkgFormData} setFormData={setPkgFormData} services={services} onSubmit={handlePkgSubmit} onCancel={() => { setShowAddForm(false); resetForm(); }} isPending={createPkgMutation.isPending} toggleServiceSelection={toggleServiceSelection} moveService={moveService} getSelectedServiceDetails={getSelectedServiceDetails} isNew materialsCatalog={materialsCatalog} durationGroups={durationGroups} />
      )}

      {packages.length === 0 && !showAddForm ? (
        <div className="empty-state"><div className="empty-icon">📦</div><p>No packages yet</p><button className="btn btn-primary" onClick={handleAddClick}>Create Your First Package</button></div>
      ) : (
        <div className="services-list">
          {packages.map((pkg) => (
            <PackageCard key={pkg.id} pkg={pkg} services={services} isEditing={editingPkgId === pkg.id} onEdit={() => setEditingPkgId(pkg.id)} onSave={handlePkgUpdate} onCancel={() => setEditingPkgId(null)} onDelete={() => setDeletePkgConfirm({ show: true, pkg })} isPending={updatePkgMutation.isPending || deletePkgMutation.isPending} getSelectedServiceDetails={getSelectedServiceDetails} materialsCatalog={materialsCatalog} durationGroups={durationGroups} />
          ))}
        </div>
      )}

      {deletePkgConfirm.show && deletePkgConfirm.pkg && (
        <div className="delete-confirm-overlay">
          <div className="delete-confirm-dialog">
            <div className="delete-confirm-icon"><i className="fas fa-exclamation-triangle"></i></div>
            <h3>Delete Package?</h3>
            <p className="delete-warning">This will permanently delete <strong>{deletePkgConfirm.pkg.name}</strong>.</p>
            <p className="delete-cascade-warning"><i className="fas fa-info-circle"></i> The individual services in this package will not be affected.</p>
            <div className="delete-confirm-actions">
              <button className="btn btn-secondary" onClick={() => setDeletePkgConfirm({ show: false, pkg: null })}>Cancel</button>
              <button className="btn btn-danger" onClick={confirmDeletePkg} disabled={deletePkgMutation.isPending}>{deletePkgMutation.isPending ? 'Deleting...' : 'Delete Package'}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// PackageForm
// ═══════════════════════════════════════════════════════════════════════════════
function PackageForm({ formData, setFormData, services, onSubmit, onCancel, isPending, toggleServiceSelection, moveService, getSelectedServiceDetails, isNew, materialsCatalog, durationGroups }) {
  return (
    <form className="package-form-card" onSubmit={onSubmit}>
      <h3>{isNew ? 'New Package' : 'Edit Package'}</h3>
      <div className="form-grid">
        <div className="form-group form-group-wide">
          <label>Package Name *</label>
          <input type="text" className="form-input" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} placeholder="e.g., Leak Investigation and Fix" required />
        </div>
        <div className="form-group form-group-wide">
          <label>Description (optional)</label>
          <textarea className="form-input" value={formData.description} onChange={(e) => setFormData({ ...formData, description: e.target.value })} placeholder="Describe what this package covers" rows={2} />
        </div>
      </div>

      <div className="service-picker">
        <label>Select Services (min 2) *</label>
        <div className="service-picker-list">
          {services.map((svc) => (
            <label key={svc.id} className="service-picker-item">
              <input type="checkbox" checked={formData.selectedServiceIds.includes(svc.id)} onChange={() => toggleServiceSelection(svc.id)} />
              <span className="service-picker-name">{svc.name}</span>
              <span className="service-picker-meta">{svc.duration_minutes ? formatDuration(svc.duration_minutes) : ''}{svc.price > 0 ? ` · ${formatPriceRange(svc.price, svc.price_max)}` : ''}</span>
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
                      <button type="button" className="btn-icon" onClick={() => moveService(idx, -1)} disabled={idx === 0} title="Move up" aria-label="Move up"><i className="fas fa-chevron-up"></i></button>
                      <button type="button" className="btn-icon" onClick={() => moveService(idx, 1)} disabled={idx === formData.selectedServiceIds.length - 1} title="Move down" aria-label="Move down"><i className="fas fa-chevron-down"></i></button>
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
          {formData.price_max_override != null && <span className="price-from-label">from</span>}
          <input type="number" className="form-input" value={formData.price_override ?? ''} onChange={(e) => setFormData({ ...formData, price_override: e.target.value === '' ? null : e.target.value })} placeholder="0.00" step="0.01" min="0" />
          <div className="price-range-toggle-row">
            <button type="button" className={`price-range-toggle ${formData.price_max_override != null ? 'active' : ''}`} onClick={() => setFormData({ ...formData, price_max_override: formData.price_max_override != null ? null : '' })} role="switch" aria-checked={formData.price_max_override != null}><span className="price-range-toggle-slider" /></button>
            <span className="price-range-toggle-label">Price range</span>
          </div>
          {formData.price_max_override != null && (
            <div className="price-max-row"><div className="price-max-field"><span className="price-max-label">to</span><input type="number" className="form-input" value={formData.price_max_override ?? ''} onChange={(e) => setFormData({ ...formData, price_max_override: e.target.value === '' ? null : e.target.value })} placeholder="Max price" step="0.01" min="0" /></div></div>
          )}
        </div>
        <div className="form-group">
          <label>Total Duration *</label>
          <select className="form-input" value={formData.duration_override ?? ''} onChange={(e) => setFormData({ ...formData, duration_override: e.target.value === '' ? null : e.target.value })}>
            <option value="">Select duration</option>
            {Object.entries(durationGroups).map(([group, options]) => (
              <optgroup key={group} label={group}>
                {options.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
              </optgroup>
            ))}
          </select>
        </div>
      </div>

      <div className="callout-toggle-group">
        <label>Requires investigation first?</label>
        <div className="callout-toggle-row">
          <button type="button" className={`callout-toggle ${formData.use_when_uncertain ? 'active' : ''}`} onClick={() => setFormData({ ...formData, use_when_uncertain: !formData.use_when_uncertain })} role="switch" aria-checked={formData.use_when_uncertain}><span className="callout-toggle-slider" /></button>
          <span className="callout-toggle-label">{formData.use_when_uncertain ? 'Yes — needs assessment before starting' : 'No — can start straight away'}</span>
        </div>
      </div>

      <DefaultMaterialsPicker materials={materialsCatalog} selectedMaterials={formData.default_materials || []} onChange={(mats) => setFormData({ ...formData, default_materials: mats })} />

      <div className="form-actions">
        <button type="button" className="btn btn-secondary" onClick={onCancel}>Cancel</button>
        <button type="submit" className="btn btn-primary" disabled={isPending}>{isPending ? 'Saving...' : (isNew ? 'Add Package' : 'Save Package')}</button>
      </div>
    </form>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// PackageCard
// ═══════════════════════════════════════════════════════════════════════════════
function PackageCard({ pkg, services, isEditing, onEdit, onSave, onCancel, onDelete, isPending, getSelectedServiceDetails, materialsCatalog, durationGroups }) {
  const resolvedServices = (pkg.services || [])
    .sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0))
    .map(ref => { const svc = services.find(s => s.id === (ref.service_id || ref.id)); return svc ? { ...svc, sort_order: ref.sort_order } : (ref.name ? ref : null); })
    .filter(Boolean);

  const [editData, setEditData] = useState({ id: null, name: '', description: '', selectedServiceIds: [], price_override: null, price_max_override: null, duration_override: null, use_when_uncertain: false, default_materials: [] });

  useEffect(() => {
    if (isEditing) {
      const serviceIds = (pkg.services || []).sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0)).map(ref => ref.service_id || ref.id).filter(Boolean);
      setEditData({
        id: pkg.id, name: pkg.name || '', description: pkg.description || '', selectedServiceIds: serviceIds,
        price_override: pkg.price_override ?? null, price_max_override: pkg.price_max_override ?? null,
        duration_override: pkg.duration_override ?? null, use_when_uncertain: pkg.use_when_uncertain || false,
        default_materials: Array.isArray(pkg.default_materials) ? pkg.default_materials : (typeof pkg.default_materials === 'string' ? JSON.parse(pkg.default_materials || '[]') : []),
      });
    }
  }, [isEditing, pkg]);

  const editToggleService = (serviceId) => setEditData(prev => ({ ...prev, selectedServiceIds: prev.selectedServiceIds.includes(serviceId) ? prev.selectedServiceIds.filter(id => id !== serviceId) : [...prev.selectedServiceIds, serviceId] }));
  const editMoveService = (index, direction) => {
    setEditData(prev => {
      const ids = [...prev.selectedServiceIds]; const ni = index + direction;
      if (ni < 0 || ni >= ids.length) return prev;
      [ids[index], ids[ni]] = [ids[ni], ids[index]];
      return { ...prev, selectedServiceIds: ids };
    });
  };

  if (isEditing) {
    return (
      <div className="package-card editing">
        <PackageForm formData={editData} setFormData={setEditData} services={services} onSubmit={(e) => { e.preventDefault(); onSave(editData); }} onCancel={onCancel} isPending={isPending} toggleServiceSelection={editToggleService} moveService={editMoveService} getSelectedServiceDetails={getSelectedServiceDetails} isNew={false} materialsCatalog={materialsCatalog} durationGroups={durationGroups} />
      </div>
    );
  }

  const totalDuration = pkg.total_duration_minutes || resolvedServices.reduce((sum, s) => sum + (s.duration_minutes || 0), 0);
  const totalPrice = pkg.price_override != null ? pkg.price_override : (pkg.total_price || resolvedServices.reduce((sum, s) => sum + (parseFloat(s.price) || 0), 0));
  const totalPriceMax = pkg.price_max_override != null ? pkg.price_max_override : (pkg.total_price_max || resolvedServices.reduce((sum, s) => sum + (parseFloat(s.price_max) || parseFloat(s.price) || 0), 0));

  return (
    <div className="package-card">
      <div className="service-image">📦</div>
      <div className="service-content">
        <h3 className="service-title">{pkg.name || 'Unnamed Package'}</h3>
        <div className="package-services-list">
          {resolvedServices.map((svc, idx) => (
            <span key={svc.id || idx}>{idx > 0 && <span className="service-arrow"> → </span>}<span className="service-step">{svc.name}</span></span>
          ))}
        </div>
        <div className="service-meta">
          {totalPrice > 0 && <span className="meta-item price">{formatPriceRange(totalPrice, totalPriceMax > totalPrice ? totalPriceMax : null)}</span>}
          {totalDuration > 0 && <span className="meta-item duration"><i className="fas fa-clock"></i> {formatDuration(totalDuration)}</span>}
          {pkg.use_when_uncertain && <span className="badge-uncertain" title="Requires investigation">🔍 Requires investigation</span>}
          {Array.isArray(pkg.default_materials) && pkg.default_materials.length > 0 && (
            <span className="meta-item callout-badge" title={`${pkg.default_materials.length} default material${pkg.default_materials.length !== 1 ? 's' : ''}`}><i className="fas fa-cubes"></i> {pkg.default_materials.length} material{pkg.default_materials.length !== 1 ? 's' : ''}</span>
          )}
        </div>
      </div>
      <div className="service-actions">
        <button type="button" className="btn-icon" onClick={onEdit} title="Edit" aria-label="Edit package"><i className="fas fa-edit"></i></button>
        <button type="button" className="btn-icon danger" onClick={onDelete} title="Delete" aria-label="Delete package" disabled={isPending}><i className="fas fa-trash"></i></button>
      </div>
    </div>
  );
}

export default ServicesTab;
