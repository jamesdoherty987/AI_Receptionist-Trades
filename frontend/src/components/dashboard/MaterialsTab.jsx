import { useState, useEffect, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../../context/AuthContext';
import { getMaterials, createMaterial, updateMaterial, deleteMaterial } from '../../services/api';
import LoadingSpinner from '../LoadingSpinner';
import { useToast } from '../Toast';
import { formatCurrency } from '../../utils/helpers';
import './MaterialsTab.css';

const COMMON_CATEGORIES = [
  'Pipe & Fittings', 'Valves', 'Sealants & Adhesives', 'Fixtures',
  'Electrical', 'Tools & Consumables', 'Heating', 'Drainage', 'Other'
];

const UNIT_OPTIONS = [
  { value: 'each', label: 'Each' },
  { value: 'm', label: 'Metre (m)' },
  { value: 'ft', label: 'Foot (ft)' },
  { value: 'kg', label: 'Kilogram (kg)' },
  { value: 'litre', label: 'Litre' },
  { value: 'roll', label: 'Roll' },
  { value: 'box', label: 'Box' },
  { value: 'pack', label: 'Pack' },
  { value: 'pair', label: 'Pair' },
  { value: 'set', label: 'Set' },
  { value: 'length', label: 'Length' },
  { value: 'bag', label: 'Bag' },
  { value: 'tube', label: 'Tube' },
  { value: 'tin', label: 'Tin' },
  { value: 'sheet', label: 'Sheet' },
  { value: 'hour', label: 'Hour' },
];

function MaterialsTab() {
  const { hasActiveSubscription } = useAuth();
  const isSubscriptionActive = hasActiveSubscription();
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterCategory, setFilterCategory] = useState('all');
  const [sortBy, setSortBy] = useState('name');
  const [sortDir, setSortDir] = useState('asc');
  const [viewMode, setViewMode] = useState('list');
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [formData, setFormData] = useState({
    name: '', unit_price: '', unit: 'each', category: '', supplier: ''
  });

  const { data, isLoading } = useQuery({
    queryKey: ['materials'],
    queryFn: async () => { const r = await getMaterials(); return r.data; },
  });

  const createMut = useMutation({
    mutationFn: createMaterial,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['materials'] });
      addToast('Material added', 'success');
      setShowAddForm(false);
      setFormData({ name: '', unit_price: '', unit: 'each', category: '', supplier: '' });
    },
    onError: () => addToast('Failed to add material', 'error'),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }) => updateMaterial(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['materials'] });
      addToast('Material updated', 'success');
      setEditingId(null);
    },
    onError: () => addToast('Failed to update', 'error'),
  });

  const deleteMut = useMutation({
    mutationFn: deleteMaterial,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['materials'] });
      addToast('Material deleted', 'success');
      setDeleteConfirm(null);
    },
    onError: () => { addToast('Failed to delete', 'error'); setDeleteConfirm(null); },
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!formData.name.trim()) return;
    createMut.mutate({
      name: formData.name.trim(),
      unit_price: parseFloat(formData.unit_price) || 0,
      unit: formData.unit || 'each',
      category: formData.category || null,
      supplier: formData.supplier || null,
    });
  };

  if (isLoading) return <LoadingSpinner message="Loading materials..." />;

  const materials = data?.materials || [];
  const existingCategories = [...new Set(materials.map(m => m.category).filter(Boolean))];
  const allCategories = [...new Set([...COMMON_CATEGORIES, ...existingCategories])].sort();

  const totalItems = materials.length;
  const totalValue = materials.reduce((sum, m) => sum + parseFloat(m.unit_price || 0), 0);
  const categoryCount = existingCategories.length;
  const supplierCount = [...new Set(materials.map(m => m.supplier).filter(Boolean))].length;
  const avgPrice = totalItems > 0 ? totalValue / totalItems : 0;

  return (
    <div className="materials-tab">
      <div className="materials-header">
        <div>
          <h2 className="tab-page-title">Materials Catalog</h2>
          <p className="tab-page-subtitle">
            Your price list for parts and materials used on jobs
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => {
          if (!isSubscriptionActive) { addToast('Please upgrade your plan to add materials', 'warning'); return; }
          setShowAddForm(!showAddForm);
        }}>
          <i className={`fas ${isSubscriptionActive ? 'fa-plus' : 'fa-lock'}`}></i> Add Material
        </button>
      </div>

      {/* Stats bar */}
      {totalItems > 0 && (
        <div className="mat-stats-bar">
          <div className="mat-stat">
            <span className="mat-stat-value">{totalItems}</span>
            <span className="mat-stat-label">Items</span>
          </div>
          <div className="mat-stat">
            <span className="mat-stat-value">{categoryCount}</span>
            <span className="mat-stat-label">Categories</span>
          </div>
          <div className="mat-stat">
            <span className="mat-stat-value">{supplierCount}</span>
            <span className="mat-stat-label">Suppliers</span>
          </div>
          <div className="mat-stat">
            <span className="mat-stat-value">{formatCurrency(avgPrice)}</span>
            <span className="mat-stat-label">Avg Price</span>
          </div>
        </div>
      )}

      {/* Add Form */}
      {showAddForm && (
        <form className="mat-form-card" onSubmit={handleSubmit}>
          <h3><i className="fas fa-plus-circle"></i> New Material</h3>
          <div className="mat-form-grid">
            <div className="mat-form-group mat-wide">
              <label>Name *</label>
              <input type="text" className="mat-input" value={formData.name}
                onChange={e => setFormData({...formData, name: e.target.value})}
                placeholder="e.g., 15mm Copper Pipe" required autoFocus />
            </div>
            <div className="mat-form-group">
              <label>Price (€)</label>
              <input type="number" className="mat-input" value={formData.unit_price}
                onChange={e => setFormData({...formData, unit_price: e.target.value})}
                placeholder="0.00" step="0.01" min="0" />
            </div>
            <div className="mat-form-group">
              <label>Unit</label>
              <select className="mat-input" value={formData.unit}
                onChange={e => setFormData({...formData, unit: e.target.value})}>
                {UNIT_OPTIONS.map(u => <option key={u.value} value={u.value}>{u.label}</option>)}
              </select>
            </div>
            <div className="mat-form-group">
              <label>Category</label>
              <select className="mat-input" value={formData.category}
                onChange={e => setFormData({...formData, category: e.target.value})}>
                <option value="">None</option>
                {allCategories.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div className="mat-form-group">
              <label>Supplier</label>
              <input type="text" className="mat-input" value={formData.supplier}
                onChange={e => setFormData({...formData, supplier: e.target.value})}
                placeholder="e.g., Heatmerchants" />
            </div>
          </div>
          <div className="mat-form-actions">
            <button type="button" className="btn btn-secondary" onClick={() => setShowAddForm(false)}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={createMut.isPending}>
              {createMut.isPending ? 'Adding...' : 'Add Material'}
            </button>
          </div>
        </form>
      )}

      {/* Toolbar: Search + Category Filter + Sort + View Toggle */}
      {materials.length > 0 && (
        <MaterialsToolbar
          searchTerm={searchTerm}
          setSearchTerm={setSearchTerm}
          filterCategory={filterCategory}
          setFilterCategory={setFilterCategory}
          existingCategories={existingCategories}
          sortBy={sortBy}
          setSortBy={setSortBy}
          sortDir={sortDir}
          setSortDir={setSortDir}
          viewMode={viewMode}
          setViewMode={setViewMode}
        />
      )}

      {/* Materials List */}
      <MaterialsList
        materials={materials}
        searchTerm={searchTerm}
        filterCategory={filterCategory}
        sortBy={sortBy}
        sortDir={sortDir}
        viewMode={viewMode}
        editingId={editingId}
        setEditingId={setEditingId}
        updateMut={updateMut}
        setDeleteConfirm={setDeleteConfirm}
        setShowAddForm={setShowAddForm}
        setSearchTerm={setSearchTerm}
        allCategories={allCategories}
      />

      {/* Delete Confirmation */}
      {deleteConfirm && (
        <div className="delete-confirm-overlay">
          <div className="delete-confirm-dialog">
            <div className="delete-confirm-icon"><i className="fas fa-exclamation-triangle"></i></div>
            <h3>Delete Material?</h3>
            <p className="delete-warning">Remove <strong>{deleteConfirm.name}</strong> from your price list?</p>
            <p className="delete-cascade-warning">
              <i className="fas fa-info-circle"></i>
              Materials already logged on jobs won't be affected.
            </p>
            <div className="delete-confirm-actions">
              <button className="btn btn-secondary" onClick={() => setDeleteConfirm(null)}>Cancel</button>
              <button className="btn btn-danger" onClick={() => deleteMut.mutate(deleteConfirm.id)}
                disabled={deleteMut.isPending}>
                {deleteMut.isPending ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function MaterialsToolbar({ searchTerm, setSearchTerm, filterCategory, setFilterCategory, existingCategories, sortBy, setSortBy, sortDir, setSortDir, viewMode, setViewMode }) {
  const toggleSort = (field) => {
    if (sortBy === field) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortDir('asc');
    }
  };

  return (
    <div className="mat-toolbar">
      <div className="mat-toolbar-top">
        <div className="mat-search">
          <i className="fas fa-search"></i>
          <input type="text" placeholder="Search materials..." value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)} />
          {searchTerm && (
            <button className="mat-search-clear" onClick={() => setSearchTerm('')} aria-label="Clear search">
              <i className="fas fa-times"></i>
            </button>
          )}
        </div>
        {existingCategories.length > 0 && (
          <div className="mat-filter">
            <select value={filterCategory} onChange={e => setFilterCategory(e.target.value)}>
              <option value="all">All Categories</option>
              {existingCategories.sort().map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
        )}
      </div>
      <div className="mat-toolbar-bottom">
        <div className="mat-sort-chips">
          {[
            { key: 'name', label: 'Name', icon: 'fa-font' },
            { key: 'price', label: 'Price', icon: 'fa-euro-sign' },
            { key: 'category', label: 'Category', icon: 'fa-tag' },
            { key: 'supplier', label: 'Supplier', icon: 'fa-store' },
          ].map(s => (
            <button
              key={s.key}
              className={`mat-sort-chip ${sortBy === s.key ? 'active' : ''}`}
              onClick={() => toggleSort(s.key)}
              title={`Sort by ${s.label}`}
            >
              <i className={`fas ${s.icon}`}></i>
              <span className="mat-sort-chip-label">{s.label}</span>
              {sortBy === s.key && (
                <i className={`fas fa-arrow-${sortDir === 'asc' ? 'up' : 'down'} mat-sort-dir`}></i>
              )}
            </button>
          ))}
        </div>
        <div className="mat-view-toggle">
          <button
            className={`mat-view-btn ${viewMode === 'list' ? 'active' : ''}`}
            onClick={() => setViewMode('list')}
            title="List view"
            aria-label="List view"
          >
            <i className="fas fa-list"></i>
          </button>
          <button
            className={`mat-view-btn ${viewMode === 'grid' ? 'active' : ''}`}
            onClick={() => setViewMode('grid')}
            title="Grid view"
            aria-label="Grid view"
          >
            <i className="fas fa-th-large"></i>
          </button>
        </div>
      </div>
    </div>
  );
}

function MaterialsList({ materials, searchTerm, filterCategory, sortBy, sortDir, viewMode, editingId, setEditingId, updateMut, setDeleteConfirm, setShowAddForm, setSearchTerm, allCategories }) {
  const filtered = useMemo(() => {
    let result = [...materials];

    if (searchTerm.trim()) {
      const term = searchTerm.toLowerCase();
      result = result.filter(m =>
        m.name.toLowerCase().includes(term) ||
        m.supplier?.toLowerCase().includes(term) ||
        m.category?.toLowerCase().includes(term)
      );
    }
    if (filterCategory !== 'all') {
      result = result.filter(m => m.category === filterCategory);
    }

    result.sort((a, b) => {
      let cmp = 0;
      switch (sortBy) {
        case 'name':
          cmp = (a.name || '').localeCompare(b.name || '');
          break;
        case 'price':
          cmp = (parseFloat(a.unit_price) || 0) - (parseFloat(b.unit_price) || 0);
          break;
        case 'category':
          cmp = (a.category || 'zzz').localeCompare(b.category || 'zzz');
          break;
        case 'supplier':
          cmp = (a.supplier || 'zzz').localeCompare(b.supplier || 'zzz');
          break;
        default:
          cmp = 0;
      }
      return sortDir === 'asc' ? cmp : -cmp;
    });

    return result;
  }, [materials, searchTerm, filterCategory, sortBy, sortDir]);

  // Group by category for list view
  const grouped = useMemo(() => {
    if (viewMode === 'grid') return null;
    const g = {};
    filtered.forEach(m => {
      const cat = m.category || 'Uncategorised';
      if (!g[cat]) g[cat] = [];
      g[cat].push(m);
    });
    return g;
  }, [filtered, viewMode]);

  if (materials.length === 0) {
    return (
      <div className="mat-empty">
        <div className="mat-empty-icon">🔩</div>
        <h3>No materials yet</h3>
        <p>Add the parts and materials you commonly use. They'll be available to pick from when logging materials on jobs.</p>
        <button className="btn btn-primary" onClick={() => setShowAddForm(true)}>
          Add Your First Material
        </button>
      </div>
    );
  }

  if (filtered.length === 0) {
    return (
      <div className="mat-no-results">
        <i className="fas fa-search"></i>
        <p>No materials match your search</p>
        <button className="btn btn-secondary btn-sm" onClick={() => setSearchTerm('')}>Clear search</button>
      </div>
    );
  }

  if (viewMode === 'grid') {
    return (
      <div className="mat-grid">
        {filtered.map(mat => (
          <MaterialCard key={mat.id} material={mat} isEditing={editingId === mat.id}
            onEdit={() => setEditingId(mat.id)}
            onSave={(data) => updateMut.mutate({ id: mat.id, data })}
            onCancel={() => setEditingId(null)}
            onDelete={() => setDeleteConfirm(mat)}
            isPending={updateMut.isPending}
            allCategories={allCategories}
            viewMode={viewMode} />
        ))}
      </div>
    );
  }

  return (
    <div className="mat-groups">
      {Object.entries(grouped).sort(([a], [b]) => a.localeCompare(b)).map(([category, items]) => (
        <div key={category} className="mat-group">
          <div className="mat-group-header">
            <span className="mat-group-name">{category}</span>
            <span className="mat-group-count">{items.length}</span>
          </div>
          <div className="mat-list">
            {items.map(mat => (
              <MaterialCard key={mat.id} material={mat} isEditing={editingId === mat.id}
                onEdit={() => setEditingId(mat.id)}
                onSave={(data) => updateMut.mutate({ id: mat.id, data })}
                onCancel={() => setEditingId(null)}
                onDelete={() => setDeleteConfirm(mat)}
                isPending={updateMut.isPending}
                allCategories={allCategories}
                viewMode={viewMode} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function MaterialCard({ material, isEditing, onEdit, onSave, onCancel, onDelete, isPending, allCategories, viewMode }) {
  const [editData, setEditData] = useState(material);

  useEffect(() => { if (isEditing) setEditData(material); }, [isEditing, material]);

  if (isEditing) {
    return (
      <div className="mat-card editing">
        <div className="mat-edit-form">
          <div className="mat-edit-grid">
            <div className="mat-form-group mat-wide">
              <label>Name</label>
              <input type="text" className="mat-input" value={editData.name || ''}
                onChange={e => setEditData({...editData, name: e.target.value})} />
            </div>
            <div className="mat-form-group">
              <label>Price (€)</label>
              <input type="number" className="mat-input" value={editData.unit_price || ''}
                onChange={e => setEditData({...editData, unit_price: e.target.value})}
                step="0.01" min="0" />
            </div>
            <div className="mat-form-group">
              <label>Unit</label>
              <select className="mat-input" value={editData.unit || 'each'}
                onChange={e => setEditData({...editData, unit: e.target.value})}>
                {UNIT_OPTIONS.map(u => <option key={u.value} value={u.value}>{u.label}</option>)}
              </select>
            </div>
            <div className="mat-form-group">
              <label>Category</label>
              <select className="mat-input" value={editData.category || ''}
                onChange={e => setEditData({...editData, category: e.target.value})}>
                <option value="">None</option>
                {allCategories.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div className="mat-form-group">
              <label>Supplier</label>
              <input type="text" className="mat-input" value={editData.supplier || ''}
                onChange={e => setEditData({...editData, supplier: e.target.value})} />
            </div>
          </div>
          <div className="mat-edit-actions">
            <button className="btn btn-secondary btn-sm" onClick={onCancel}>Cancel</button>
            <button className="btn btn-primary btn-sm" onClick={() => onSave(editData)} disabled={isPending}>
              {isPending ? 'Saving...' : 'Save'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  const isGrid = viewMode === 'grid';

  return (
    <div className={`mat-card ${isGrid ? 'mat-card-grid' : ''}`}>
      <div className={`mat-card-icon ${isGrid ? 'mat-card-icon-grid' : ''}`}>
        <i className="fas fa-cube"></i>
      </div>
      <div className="mat-card-content">
        <span className="mat-card-name">{material.name}</span>
        {isGrid && (
          <div className="mat-card-grid-price">
            {formatCurrency(material.unit_price)}<span className="mat-unit">/{material.unit || 'each'}</span>
          </div>
        )}
        <div className="mat-card-meta">
          {!isGrid && (
            <span className="mat-price">{formatCurrency(material.unit_price)}<span className="mat-unit">/{material.unit || 'each'}</span></span>
          )}
          {material.supplier && <span className="mat-supplier"><i className="fas fa-store"></i> {material.supplier}</span>}
          {isGrid && material.category && <span className="mat-category-badge"><i className="fas fa-tag"></i> {material.category}</span>}
        </div>
      </div>
      <div className={`mat-card-actions ${isGrid ? 'mat-card-actions-grid' : ''}`}>
        <button className="btn-icon" onClick={onEdit} title="Edit"><i className="fas fa-edit"></i></button>
        <button className="btn-icon danger" onClick={onDelete} title="Delete"><i className="fas fa-trash"></i></button>
      </div>
    </div>
  );
}

export default MaterialsTab;
