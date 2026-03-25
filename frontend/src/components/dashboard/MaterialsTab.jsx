import { useState, useEffect } from 'react';
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

  // Get unique categories from existing materials
  const existingCategories = [...new Set(materials.map(m => m.category).filter(Boolean))];
  const allCategories = [...new Set([...COMMON_CATEGORIES, ...existingCategories])].sort();

  // Filter materials
  let filtered = materials;
  if (searchTerm.trim()) {
    const term = searchTerm.toLowerCase();
    filtered = filtered.filter(m =>
      m.name.toLowerCase().includes(term) ||
      m.supplier?.toLowerCase().includes(term) ||
      m.category?.toLowerCase().includes(term)
    );
  }
  if (filterCategory !== 'all') {
    filtered = filtered.filter(m => m.category === filterCategory);
  }

  // Group by category
  const grouped = {};
  filtered.forEach(m => {
    const cat = m.category || 'Uncategorised';
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(m);
  });

  const totalItems = materials.length;
  const totalValue = materials.reduce((sum, m) => sum + parseFloat(m.unit_price || 0), 0);

  return (
    <div className="materials-tab">
      <div className="materials-header">
        <div>
          <h2>Materials</h2>
          <p className="materials-subtitle">
            Your price list — {totalItems} item{totalItems !== 1 ? 's' : ''}
            {totalItems > 0 && <span className="materials-avg"> · avg {formatCurrency(totalValue / totalItems)}/item</span>}
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => {
          if (!isSubscriptionActive) { addToast('Active subscription required', 'warning'); return; }
          setShowAddForm(!showAddForm);
        }}>
          <i className={`fas ${isSubscriptionActive ? 'fa-plus' : 'fa-lock'}`}></i> Add Material
        </button>
      </div>

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

      {/* Search & Filter */}
      {materials.length > 0 && (
        <div className="mat-controls">
          <div className="mat-search">
            <i className="fas fa-search"></i>
            <input type="text" placeholder="Search materials..." value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)} />
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
      )}

      {/* Materials List */}
      {materials.length === 0 ? (
        <div className="mat-empty">
          <div className="mat-empty-icon">🔩</div>
          <h3>No materials yet</h3>
          <p>Add the parts and materials you commonly use. They'll be available to pick from when logging materials on jobs.</p>
          <button className="btn btn-primary" onClick={() => setShowAddForm(true)}>
            Add Your First Material
          </button>
        </div>
      ) : filtered.length === 0 ? (
        <div className="mat-empty">
          <p>No materials match your search</p>
        </div>
      ) : (
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
                    allCategories={allCategories} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

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

function MaterialCard({ material, isEditing, onEdit, onSave, onCancel, onDelete, isPending, allCategories }) {
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

  return (
    <div className="mat-card">
      <div className="mat-card-icon">
        <i className="fas fa-cube"></i>
      </div>
      <div className="mat-card-content">
        <span className="mat-card-name">{material.name}</span>
        <div className="mat-card-meta">
          <span className="mat-price">{formatCurrency(material.unit_price)}<span className="mat-unit">/{material.unit || 'each'}</span></span>
          {material.supplier && <span className="mat-supplier"><i className="fas fa-store"></i> {material.supplier}</span>}
        </div>
      </div>
      <div className="mat-card-actions">
        <button className="btn-icon" onClick={onEdit} title="Edit"><i className="fas fa-edit"></i></button>
        <button className="btn-icon danger" onClick={onDelete} title="Delete"><i className="fas fa-trash"></i></button>
      </div>
    </div>
  );
}

export default MaterialsTab;
