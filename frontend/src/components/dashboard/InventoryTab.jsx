import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../../context/AuthContext';
import { useIndustry } from '../../context/IndustryContext';
import { getMaterials, createMaterial, updateMaterial, deleteMaterial, adjustMaterialStock } from '../../services/api';
import LoadingSpinner from '../LoadingSpinner';
import { useToast } from '../Toast';
import { formatCurrency } from '../../utils/helpers';
import './InventoryTab.css';
import './SharedDashboard.css';

/* ── Fallback defaults (used if industry profile has no inventory config) ── */
const FALLBACK_CATEGORIES = [
  'Pipe & Fittings', 'Valves', 'Sealants & Adhesives', 'Fixtures',
  'Electrical', 'Tools & Consumables', 'Cleaning Supplies', 'Other'
];
const FALLBACK_UNITS = [
  { value: 'each', label: 'Each' }, { value: 'm', label: 'Metre (m)' },
  { value: 'ft', label: 'Foot (ft)' }, { value: 'kg', label: 'Kilogram (kg)' },
  { value: 'litre', label: 'Litre' }, { value: 'roll', label: 'Roll' },
  { value: 'box', label: 'Box' }, { value: 'pack', label: 'Pack' },
  { value: 'pair', label: 'Pair' }, { value: 'set', label: 'Set' },
  { value: 'bag', label: 'Bag' }, { value: 'tube', label: 'Tube' },
  { value: 'tin', label: 'Tin' }, { value: 'sheet', label: 'Sheet' },
];

const EMPTY_FORM = {
  name: '', unit_price: '', cost_price: '', unit: 'each', category: '',
  supplier: '', sku: '', notes: '', stock_on_hand: '', reorder_level: '',
  ideal_stock: '', location: '', expiry_date: '', batch_number: '',
};

function InventoryTab() {
  const { hasActiveSubscription } = useAuth();
  const isSubscriptionActive = hasActiveSubscription();
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const industry = useIndustry();
  const invConfig = industry?.inventory || {};

  /* ── Industry-aware config ── */
  const CATEGORIES = invConfig.categories || FALLBACK_CATEGORIES;
  const UNIT_OPTIONS = invConfig.units || FALLBACK_UNITS;
  const showCostPrice = invConfig.showCostPrice ?? true;
  const showExpiry = invConfig.showExpiry ?? false;
  const showBatchNumber = invConfig.showBatchNumber ?? false;
  const showLocation = invConfig.showLocation ?? true;
  const locationLabel = invConfig.locationLabel || 'Location';
  const locationPlaceholder = invConfig.locationPlaceholder || 'e.g., Warehouse, Van';
  const namePlaceholder = invConfig.namePlaceholder || 'e.g., Item name';
  const supplierPlaceholder = invConfig.supplierPlaceholder || 'e.g., Supplier name';
  const emptyIcon = invConfig.emptyIcon || '📦';
  const emptyTitle = invConfig.emptyTitle || 'No inventory items yet';
  const emptyDescription = invConfig.emptyDescription || 'Add items to track stock levels and pricing.';

  /* ── State ── */
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterCategory, setFilterCategory] = useState('all');
  const [filterStock, setFilterStock] = useState('all');
  const [sortBy, setSortBy] = useState('name');
  const [sortDir, setSortDir] = useState('asc');
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [adjustingId, setAdjustingId] = useState(null);
  const [adjustVal, setAdjustVal] = useState('');
  const [formData, setFormData] = useState({ ...EMPTY_FORM });
  const [collapsedCategories, setCollapsedCategories] = useState({});

  /* ── Queries & Mutations ── */
  const { data, isLoading } = useQuery({
    queryKey: ['materials'],
    queryFn: async () => { const r = await getMaterials(); return r.data; },
  });

  const createMut = useMutation({
    mutationFn: createMaterial,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['materials'] });
      addToast('Item added', 'success');
      setShowAddForm(false);
      setFormData({ ...EMPTY_FORM });
    },
    onError: () => addToast('Failed to add item', 'error'),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }) => updateMaterial(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['materials'] });
      addToast('Item updated', 'success');
      setEditingId(null);
    },
    onError: () => addToast('Failed to update', 'error'),
  });

  const deleteMut = useMutation({
    mutationFn: deleteMaterial,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['materials'] });
      addToast('Item deleted', 'success');
      setDeleteConfirm(null);
    },
    onError: () => { addToast('Failed to delete', 'error'); setDeleteConfirm(null); },
  });

  const adjustMut = useMutation({
    mutationFn: ({ id, adjustment }) => adjustMaterialStock(id, adjustment),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['materials'] });
      addToast(`Stock updated to ${res.data.stock_on_hand}`, 'success');
      setAdjustingId(null);
      setAdjustVal('');
    },
    onError: () => addToast('Failed to adjust stock', 'error'),
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!formData.name.trim()) return;
    createMut.mutate({
      name: formData.name.trim(),
      unit_price: parseFloat(formData.unit_price) || 0,
      cost_price: formData.cost_price !== '' ? parseFloat(formData.cost_price) : null,
      unit: formData.unit || 'each',
      category: formData.category || null,
      supplier: formData.supplier || null,
      sku: formData.sku || null,
      notes: formData.notes || null,
      stock_on_hand: formData.stock_on_hand !== '' ? parseFloat(formData.stock_on_hand) : null,
      reorder_level: formData.reorder_level !== '' ? parseFloat(formData.reorder_level) : null,
      ideal_stock: formData.ideal_stock !== '' ? parseFloat(formData.ideal_stock) : null,
      location: formData.location || null,
      expiry_date: formData.expiry_date || null,
      batch_number: formData.batch_number || null,
    });
  };

  /* ── Derived data ── */
  const materials = data?.materials || [];
  const lowStockCount = data?.low_stock_count || 0;
  const expiringCount = data?.expiring_soon_count || 0;
  const existingCategories = [...new Set(materials.map(m => m.category).filter(Boolean))];
  const allCategories = [...new Set([...CATEGORIES, ...existingCategories])].sort();
  const totalItems = materials.length;
  const trackedItems = materials.filter(m => m.stock_on_hand !== null).length;
  const totalValue = materials.reduce((sum, m) => {
    const qty = m.stock_on_hand !== null ? m.stock_on_hand : 1;
    return sum + (parseFloat(m.unit_price || 0) * qty);
  }, 0);
  const outOfStock = materials.filter(m => m.stock_on_hand !== null && m.stock_on_hand <= 0).length;

  /* ── Filter & sort ── */
  const filtered = useMemo(() => {
    let result = [...materials];
    if (searchTerm.trim()) {
      const term = searchTerm.toLowerCase();
      result = result.filter(m =>
        m.name.toLowerCase().includes(term) ||
        m.supplier?.toLowerCase().includes(term) ||
        m.category?.toLowerCase().includes(term) ||
        m.sku?.toLowerCase().includes(term) ||
        m.location?.toLowerCase().includes(term) ||
        m.batch_number?.toLowerCase().includes(term)
      );
    }
    if (filterCategory !== 'all') result = result.filter(m => m.category === filterCategory);
    if (filterStock === 'low') result = result.filter(m => m.low_stock);
    else if (filterStock === 'out') result = result.filter(m => m.stock_on_hand !== null && m.stock_on_hand <= 0);
    else if (filterStock === 'tracked') result = result.filter(m => m.stock_on_hand !== null);
    else if (filterStock === 'expiring') result = result.filter(m => m.expiring_soon);
    else if (filterStock === 'expired') result = result.filter(m => m.expired);

    result.sort((a, b) => {
      let cmp = 0;
      switch (sortBy) {
        case 'name': cmp = (a.name || '').localeCompare(b.name || ''); break;
        case 'price': cmp = (parseFloat(a.unit_price) || 0) - (parseFloat(b.unit_price) || 0); break;
        case 'stock': cmp = (a.stock_on_hand ?? -1) - (b.stock_on_hand ?? -1); break;
        case 'category': cmp = (a.category || 'zzz').localeCompare(b.category || 'zzz'); break;
        case 'expiry': {
          const ea = a.expiry_date || '9999-12-31';
          const eb = b.expiry_date || '9999-12-31';
          cmp = ea.localeCompare(eb); break;
        }
        default: cmp = 0;
      }
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return result;
  }, [materials, searchTerm, filterCategory, filterStock, sortBy, sortDir]);

  /* ── Group by category ── */
  const grouped = useMemo(() => {
    const g = {};
    filtered.forEach(m => {
      const cat = m.category || 'Uncategorised';
      if (!g[cat]) g[cat] = [];
      g[cat].push(m);
    });
    return g;
  }, [filtered]);

  if (isLoading) return <LoadingSpinner message={`Loading ${(industry?.terminology?.inventoryTab || 'inventory').toLowerCase()}...`} />;

  const toggleSort = (field) => {
    if (sortBy === field) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortBy(field); setSortDir('asc'); }
  };

  const toggleCategoryCollapse = (cat) => {
    setCollapsedCategories(prev => ({ ...prev, [cat]: !prev[cat] }));
  };

  const hasMultipleCategories = Object.keys(grouped).length > 1;

  return (
    <div className="inv-tab">
      {/* Header */}
      <div className="inv-header">
        <div>
          <h2 className="tab-page-title">{industry?.terminology?.inventoryTab || 'Inventory'}</h2>
          <p className="tab-page-subtitle">Track your items, stock levels, and pricing</p>
        </div>
        <button className="btn-add" onClick={() => {
          if (!isSubscriptionActive) { addToast('Please upgrade your plan to add items', 'warning'); return; }
          setShowAddForm(!showAddForm);
        }}>
          <i className={`fas ${isSubscriptionActive ? 'fa-plus' : 'fa-lock'}`}></i> Add Item
        </button>
      </div>

      {/* Stats bar */}
      {totalItems > 0 && (
        <div className="inv-stats-bar">
          <div className="inv-stat">
            <span className="inv-stat-value">{totalItems}</span>
            <span className="inv-stat-label">Items</span>
          </div>
          {trackedItems > 0 && (
            <div className="inv-stat">
              <span className="inv-stat-value">{trackedItems}</span>
              <span className="inv-stat-label">Tracked</span>
            </div>
          )}
          {lowStockCount > 0 && (
            <div className="inv-stat inv-stat-warn" onClick={() => setFilterStock('low')} role="button" tabIndex={0} title="Show low stock items">
              <span className="inv-stat-value">{lowStockCount}</span>
              <span className="inv-stat-label">Low Stock</span>
            </div>
          )}
          {outOfStock > 0 && (
            <div className="inv-stat inv-stat-danger" onClick={() => setFilterStock('out')} role="button" tabIndex={0} title="Show out of stock items">
              <span className="inv-stat-value">{outOfStock}</span>
              <span className="inv-stat-label">Out of Stock</span>
            </div>
          )}
          {showExpiry && expiringCount > 0 && (
            <div className="inv-stat inv-stat-warn" onClick={() => setFilterStock('expiring')} role="button" tabIndex={0} title="Expiring within 7 days">
              <span className="inv-stat-value">{expiringCount}</span>
              <span className="inv-stat-label">Expiring Soon</span>
            </div>
          )}
          <div className="inv-stat">
            <span className="inv-stat-value">{formatCurrency(totalValue)}</span>
            <span className="inv-stat-label">Total Value</span>
          </div>
        </div>
      )}

      {/* Add Form */}
      {showAddForm && (
        <form className="inv-form-card" onSubmit={handleSubmit}>
          <h3><i className="fas fa-plus-circle"></i> New Item</h3>
          <div className="inv-form-grid">
            <div className="inv-form-group inv-wide">
              <label>Name *</label>
              <input type="text" className="inv-input" value={formData.name}
                onChange={e => setFormData({...formData, name: e.target.value})}
                placeholder={namePlaceholder} required autoFocus />
            </div>
            <div className="inv-form-group">
              <label>Sell Price (€)</label>
              <input type="number" className="inv-input" value={formData.unit_price}
                onChange={e => setFormData({...formData, unit_price: e.target.value})}
                placeholder="0.00" step="0.01" min="0" />
            </div>
            {showCostPrice && (
              <div className="inv-form-group">
                <label>Cost Price (€)</label>
                <input type="number" className="inv-input" value={formData.cost_price}
                  onChange={e => setFormData({...formData, cost_price: e.target.value})}
                  placeholder="0.00" step="0.01" min="0" />
              </div>
            )}
            <div className="inv-form-group">
              <label>Unit</label>
              <select className="inv-input" value={formData.unit}
                onChange={e => setFormData({...formData, unit: e.target.value})}>
                {UNIT_OPTIONS.map(u => <option key={u.value} value={u.value}>{u.label}</option>)}
              </select>
            </div>
            <div className="inv-form-group">
              <label>Category</label>
              <select className="inv-input" value={formData.category}
                onChange={e => setFormData({...formData, category: e.target.value})}>
                <option value="">None</option>
                {allCategories.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div className="inv-form-group">
              <label>Supplier</label>
              <input type="text" className="inv-input" value={formData.supplier}
                onChange={e => setFormData({...formData, supplier: e.target.value})}
                placeholder={supplierPlaceholder} />
            </div>
            <div className="inv-form-group">
              <label>SKU / Code</label>
              <input type="text" className="inv-input" value={formData.sku}
                onChange={e => setFormData({...formData, sku: e.target.value})}
                placeholder="Optional" />
            </div>
            {showLocation && (
              <div className="inv-form-group">
                <label>{locationLabel}</label>
                <input type="text" className="inv-input" value={formData.location}
                  onChange={e => setFormData({...formData, location: e.target.value})}
                  placeholder={locationPlaceholder} />
              </div>
            )}
            <div className="inv-form-group">
              <label>Stock on Hand</label>
              <input type="number" className="inv-input" value={formData.stock_on_hand}
                onChange={e => setFormData({...formData, stock_on_hand: e.target.value})}
                placeholder="Leave blank to skip tracking" step="0.01" min="0" />
            </div>
            <div className="inv-form-group">
              <label>Reorder Level</label>
              <input type="number" className="inv-input" value={formData.reorder_level}
                onChange={e => setFormData({...formData, reorder_level: e.target.value})}
                placeholder="Alert when stock drops below" step="0.01" min="0" />
            </div>
            <div className="inv-form-group">
              <label>Ideal Stock</label>
              <input type="number" className="inv-input" value={formData.ideal_stock}
                onChange={e => setFormData({...formData, ideal_stock: e.target.value})}
                placeholder="Ideal amount to have" step="0.01" min="0" />
            </div>
            {showExpiry && (
              <div className="inv-form-group">
                <label>Expiry Date</label>
                <input type="date" className="inv-input" value={formData.expiry_date}
                  onChange={e => setFormData({...formData, expiry_date: e.target.value})} />
              </div>
            )}
            {showBatchNumber && (
              <div className="inv-form-group">
                <label>Batch / Lot #</label>
                <input type="text" className="inv-input" value={formData.batch_number}
                  onChange={e => setFormData({...formData, batch_number: e.target.value})}
                  placeholder="Optional" />
              </div>
            )}
            <div className="inv-form-group inv-wide">
              <label>Notes</label>
              <input type="text" className="inv-input" value={formData.notes}
                onChange={e => setFormData({...formData, notes: e.target.value})}
                placeholder="Optional notes" />
            </div>
          </div>
          <div className="inv-form-actions">
            <button type="button" className="btn btn-secondary" onClick={() => { setShowAddForm(false); setFormData({ ...EMPTY_FORM }); }}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={createMut.isPending}>
              {createMut.isPending ? 'Adding...' : 'Add Item'}
            </button>
          </div>
        </form>
      )}

      {/* Toolbar */}
      {materials.length > 0 && (
        <div className="inv-toolbar">
          <div className="dash-search">
            <i className="fas fa-search"></i>
            <input type="text" placeholder={`Search ${(industry?.terminology?.inventoryTab || 'inventory').toLowerCase()}...`} value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)} />
            {searchTerm && (
              <button className="dash-search-clear" onClick={() => setSearchTerm('')} aria-label="Clear search">
                <i className="fas fa-times"></i>
              </button>
            )}
          </div>
          <div className="inv-toolbar-right">
            {existingCategories.length > 0 && (
              <select className="inv-category-filter" value={filterCategory} onChange={e => setFilterCategory(e.target.value)} aria-label="Filter by category">
                <option value="all">All Categories</option>
                {existingCategories.sort().map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            )}
            {(trackedItems > 0 || showExpiry) && (
              <select className="inv-stock-filter" value={filterStock} onChange={e => setFilterStock(e.target.value)} aria-label="Filter by stock">
                <option value="all">All Stock</option>
                <option value="tracked">Tracked Only</option>
                <option value="low">Low Stock</option>
                <option value="out">Out of Stock</option>
                {showExpiry && <option value="expiring">Expiring Soon</option>}
                {showExpiry && <option value="expired">Expired</option>}
              </select>
            )}
            <div className="inv-sort-chips">
              {[
                { key: 'name', label: 'Name', icon: 'fa-font' },
                { key: 'price', label: 'Price', icon: 'fa-euro-sign' },
                { key: 'stock', label: 'Stock', icon: 'fa-boxes-stacked' },
                { key: 'category', label: 'Category', icon: 'fa-tag' },
                ...(showExpiry ? [{ key: 'expiry', label: 'Expiry', icon: 'fa-clock' }] : []),
              ].map(s => (
                <button key={s.key} className={`inv-sort-chip ${sortBy === s.key ? 'active' : ''}`}
                  onClick={() => toggleSort(s.key)} title={`Sort by ${s.label}`}>
                  <i className={`fas ${s.icon}`}></i>
                  <span>{s.label}</span>
                  {sortBy === s.key && <i className={`fas fa-arrow-${sortDir === 'asc' ? 'up' : 'down'} inv-sort-dir`}></i>}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Empty state */}
      {materials.length === 0 && (
        <div className="inv-empty">
          <div className="inv-empty-icon">{emptyIcon}</div>
          <h3>{emptyTitle}</h3>
          <p>{emptyDescription}</p>
          <button className="btn btn-primary" onClick={() => setShowAddForm(true)}>Add Your First Item</button>
        </div>
      )}

      {/* No results */}
      {materials.length > 0 && filtered.length === 0 && (
        <div className="inv-no-results">
          <i className="fas fa-search"></i>
          <p>No items match your filters</p>
          <button className="btn btn-secondary btn-sm" onClick={() => { setSearchTerm(''); setFilterCategory('all'); setFilterStock('all'); }}>Clear filters</button>
        </div>
      )}

      {/* Item list grouped by category */}
      {filtered.length > 0 && hasMultipleCategories && filterCategory === 'all' ? (
        <div className="inv-groups">
          {Object.entries(grouped).sort(([a], [b]) => a.localeCompare(b)).map(([category, items]) => {
            const isCollapsed = collapsedCategories[category];
            return (
              <div key={category} className="inv-group">
                <button className="inv-group-header" onClick={() => toggleCategoryCollapse(category)}>
                  <span className="inv-group-dot"></span>
                  <span className="inv-group-name">{category}</span>
                  <span className="inv-group-count">{items.length}</span>
                  <i className={`fas fa-chevron-${isCollapsed ? 'right' : 'down'} inv-group-arrow`}></i>
                </button>
                {!isCollapsed && (
                  <div className="inv-list">
                    {items.map(item => (
                      <InventoryCard key={item.id} item={item}
                        isEditing={editingId === item.id}
                        isAdjusting={adjustingId === item.id}
                        adjustVal={adjustingId === item.id ? adjustVal : ''}
                        onAdjustValChange={setAdjustVal}
                        onEdit={() => setEditingId(item.id)}
                        onSave={(d) => updateMut.mutate({ id: item.id, data: d })}
                        onCancel={() => setEditingId(null)}
                        onDelete={() => setDeleteConfirm(item)}
                        onAdjustStart={() => { setAdjustingId(item.id); setAdjustVal(''); }}
                        onAdjustCancel={() => { setAdjustingId(null); setAdjustVal(''); }}
                        onAdjustSubmit={(adj) => adjustMut.mutate({ id: item.id, adjustment: adj })}
                        isPending={updateMut.isPending}
                        isAdjustPending={adjustMut.isPending}
                        allCategories={allCategories}
                        invConfig={{ showCostPrice, showExpiry, showBatchNumber, showLocation, locationLabel, locationPlaceholder, namePlaceholder, supplierPlaceholder, UNIT_OPTIONS }} />
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ) : filtered.length > 0 ? (
        <div className="inv-groups">
          {Object.entries(grouped).sort(([a], [b]) => a.localeCompare(b)).map(([category, items]) => (
            <div key={category} className="inv-group">
              <div className="inv-group-header-flat">
                <span className="inv-group-name">{category}</span>
                <span className="inv-group-count">{items.length}</span>
              </div>
              <div className="inv-list">
                {items.map(item => (
                  <InventoryCard key={item.id} item={item}
                    isEditing={editingId === item.id}
                    isAdjusting={adjustingId === item.id}
                    adjustVal={adjustingId === item.id ? adjustVal : ''}
                    onAdjustValChange={setAdjustVal}
                    onEdit={() => setEditingId(item.id)}
                    onSave={(d) => updateMut.mutate({ id: item.id, data: d })}
                    onCancel={() => setEditingId(null)}
                    onDelete={() => setDeleteConfirm(item)}
                    onAdjustStart={() => { setAdjustingId(item.id); setAdjustVal(''); }}
                    onAdjustCancel={() => { setAdjustingId(null); setAdjustVal(''); }}
                    onAdjustSubmit={(adj) => adjustMut.mutate({ id: item.id, adjustment: adj })}
                    isPending={updateMut.isPending}
                    isAdjustPending={adjustMut.isPending}
                    allCategories={allCategories}
                    invConfig={{ showCostPrice, showExpiry, showBatchNumber, showLocation, locationLabel, locationPlaceholder, namePlaceholder, supplierPlaceholder, UNIT_OPTIONS }} />
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : null}

      {/* Delete Confirmation */}
      {deleteConfirm && (
        <div className="delete-confirm-overlay">
          <div className="delete-confirm-dialog">
            <div className="delete-confirm-icon"><i className="fas fa-exclamation-triangle"></i></div>
            <h3>Delete Item?</h3>
            <p className="delete-warning">Remove <strong>{deleteConfirm.name}</strong> from your {(industry?.terminology?.inventoryTab || 'inventory').toLowerCase()}?</p>
            <p className="delete-cascade-warning">
              <i className="fas fa-info-circle"></i>
              Items already logged on {industry?.terminology?.jobs?.toLowerCase() || 'jobs'} won&apos;t be affected.
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

/* ── Helper: margin percentage ── */
function calcMargin(sell, cost) {
  const s = parseFloat(sell);
  const c = parseFloat(cost);
  if (!s || !c || s <= 0) return null;
  return Math.round(((s - c) / s) * 100);
}

/* ── Helper: stock level bar ── */
function StockBar({ current, reorder, ideal }) {
  const cur = parseFloat(current);
  const max = parseFloat(ideal) || parseFloat(reorder) * 2 || cur * 1.5 || 100;
  if (isNaN(cur) || max <= 0) return null;
  const pct = Math.min(100, Math.max(0, (cur / max) * 100));
  const reorderPct = reorder ? Math.min(100, (parseFloat(reorder) / max) * 100) : null;
  let color = '#22c55e';
  if (reorder && cur <= parseFloat(reorder)) color = cur <= 0 ? '#ef4444' : '#f59e0b';
  return (
    <div className="inv-stock-bar-wrap" title={`${cur} / ${ideal ? `ideal ${ideal}` : `max ~${Math.round(max)}`}`}>
      <div className="inv-stock-bar">
        <div className="inv-stock-bar-fill" style={{ width: `${pct}%`, background: color }} />
        {reorderPct !== null && <div className="inv-stock-bar-marker" style={{ left: `${reorderPct}%` }} />}
      </div>
    </div>
  );
}

/* ── Helper: days until expiry ── */
function ExpiryBadge({ expiryDate, expired, expiringSoon }) {
  if (!expiryDate) return null;
  const exp = new Date(expiryDate + 'T00:00:00');
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  const days = Math.ceil((exp - now) / (1000 * 60 * 60 * 24));
  if (expired) return <span className="inv-badge inv-badge-danger" title={`Expired ${expiryDate}`}>Expired</span>;
  if (expiringSoon) return <span className="inv-badge inv-badge-warn" title={`Expires ${expiryDate}`}>{days}d left</span>;
  return <span className="inv-badge inv-badge-expiry" title={`Expires ${expiryDate}`}><i className="fas fa-clock"></i> {expiryDate}</span>;
}

function InventoryCard({ item, isEditing, isAdjusting, adjustVal, onAdjustValChange, onEdit, onSave, onCancel, onDelete, onAdjustStart, onAdjustCancel, onAdjustSubmit, isPending, isAdjustPending, allCategories, invConfig }) {
  const { showCostPrice, showExpiry, showBatchNumber, showLocation, locationLabel, locationPlaceholder, namePlaceholder, supplierPlaceholder, UNIT_OPTIONS } = invConfig;
  const [editData, setEditData] = useState(item);

  const handleEdit = () => {
    setEditData({
      ...item,
      stock_on_hand: item.stock_on_hand ?? '',
      reorder_level: item.reorder_level ?? '',
      ideal_stock: item.ideal_stock ?? '',
      cost_price: item.cost_price ?? '',
      location: item.location ?? '',
      expiry_date: item.expiry_date ?? '',
      batch_number: item.batch_number ?? '',
    });
    onEdit();
  };

  if (isEditing) {
    return (
      <div className="inv-card editing">
        <div className="inv-edit-form">
          <div className="inv-edit-grid">
            <div className="inv-form-group inv-wide">
              <label>Name</label>
              <input type="text" className="inv-input" value={editData.name || ''}
                onChange={e => setEditData({...editData, name: e.target.value})} placeholder={namePlaceholder} />
            </div>
            <div className="inv-form-group">
              <label>Sell Price (€)</label>
              <input type="number" className="inv-input" value={editData.unit_price || ''}
                onChange={e => setEditData({...editData, unit_price: e.target.value})}
                step="0.01" min="0" />
            </div>
            {showCostPrice && (
              <div className="inv-form-group">
                <label>Cost Price (€)</label>
                <input type="number" className="inv-input" value={editData.cost_price ?? ''}
                  onChange={e => setEditData({...editData, cost_price: e.target.value})}
                  step="0.01" min="0" />
              </div>
            )}
            <div className="inv-form-group">
              <label>Unit</label>
              <select className="inv-input" value={editData.unit || 'each'}
                onChange={e => setEditData({...editData, unit: e.target.value})}>
                {UNIT_OPTIONS.map(u => <option key={u.value} value={u.value}>{u.label}</option>)}
              </select>
            </div>
            <div className="inv-form-group">
              <label>Category</label>
              <select className="inv-input" value={editData.category || ''}
                onChange={e => setEditData({...editData, category: e.target.value})}>
                <option value="">None</option>
                {allCategories.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div className="inv-form-group">
              <label>Supplier</label>
              <input type="text" className="inv-input" value={editData.supplier || ''}
                onChange={e => setEditData({...editData, supplier: e.target.value})} placeholder={supplierPlaceholder} />
            </div>
            <div className="inv-form-group">
              <label>SKU / Code</label>
              <input type="text" className="inv-input" value={editData.sku || ''}
                onChange={e => setEditData({...editData, sku: e.target.value})} />
            </div>
            {showLocation && (
              <div className="inv-form-group">
                <label>{locationLabel}</label>
                <input type="text" className="inv-input" value={editData.location || ''}
                  onChange={e => setEditData({...editData, location: e.target.value})} placeholder={locationPlaceholder} />
              </div>
            )}
            <div className="inv-form-group">
              <label>Stock on Hand</label>
              <input type="number" className="inv-input" value={editData.stock_on_hand ?? ''}
                onChange={e => setEditData({...editData, stock_on_hand: e.target.value})}
                placeholder="Leave blank to skip" step="0.01" min="0" />
            </div>
            <div className="inv-form-group">
              <label>Reorder Level</label>
              <input type="number" className="inv-input" value={editData.reorder_level ?? ''}
                onChange={e => setEditData({...editData, reorder_level: e.target.value})}
                placeholder="Low stock alert" step="0.01" min="0" />
            </div>
            <div className="inv-form-group">
              <label>Ideal Stock</label>
              <input type="number" className="inv-input" value={editData.ideal_stock ?? ''}
                onChange={e => setEditData({...editData, ideal_stock: e.target.value})}
                placeholder="Ideal amount to have" step="0.01" min="0" />
            </div>
            {showExpiry && (
              <div className="inv-form-group">
                <label>Expiry Date</label>
                <input type="date" className="inv-input" value={editData.expiry_date || ''}
                  onChange={e => setEditData({...editData, expiry_date: e.target.value})} />
              </div>
            )}
            {showBatchNumber && (
              <div className="inv-form-group">
                <label>Batch / Lot #</label>
                <input type="text" className="inv-input" value={editData.batch_number || ''}
                  onChange={e => setEditData({...editData, batch_number: e.target.value})} />
              </div>
            )}
            <div className="inv-form-group inv-wide">
              <label>Notes</label>
              <input type="text" className="inv-input" value={editData.notes || ''}
                onChange={e => setEditData({...editData, notes: e.target.value})}
                placeholder="Optional notes" />
            </div>
          </div>
          <div className="inv-edit-actions">
            <button className="btn btn-secondary btn-sm" onClick={onCancel}>Cancel</button>
            <button className="btn btn-primary btn-sm" onClick={() => onSave(editData)} disabled={isPending}>
              {isPending ? 'Saving...' : 'Save'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  const hasStock = item.stock_on_hand !== null;
  const isLow = item.low_stock && item.stock_on_hand > 0;
  const isOut = hasStock && item.stock_on_hand <= 0;
  const margin = showCostPrice ? calcMargin(item.unit_price, item.cost_price) : null;

  return (
    <div className={`inv-card ${isLow ? 'inv-card-low' : ''} ${isOut ? 'inv-card-out' : ''} ${item.expired ? 'inv-card-expired' : ''}`}>
      <div className="inv-card-icon">
        <i className={`fas ${isOut ? 'fa-box-open' : item.expired ? 'fa-exclamation-circle' : 'fa-cube'}`}></i>
      </div>
      <div className="inv-card-content">
        <div className="inv-card-top">
          <span className="inv-card-name">{item.name}</span>
          {item.sku && <span className="inv-card-sku">{item.sku}</span>}
          {isLow && <span className="inv-badge inv-badge-warn" title="Below reorder level">Low</span>}
          {isOut && <span className="inv-badge inv-badge-danger">Out</span>}
          {showExpiry && <ExpiryBadge expiryDate={item.expiry_date} expired={item.expired} expiringSoon={item.expiring_soon} />}
        </div>
        <div className="inv-card-meta">
          <span className="inv-price">{formatCurrency(item.unit_price)}<span className="inv-unit">/{item.unit || 'each'}</span></span>
          {showCostPrice && item.cost_price != null && (
            <span className="inv-cost">
              <i className="fas fa-tag"></i> Cost {formatCurrency(item.cost_price)}
              {margin !== null && <span className={`inv-margin ${margin >= 30 ? 'good' : margin >= 10 ? 'ok' : 'low'}`}>{margin}%</span>}
            </span>
          )}
          {hasStock && (
            <span className={`inv-stock ${isLow ? 'inv-stock-low' : ''} ${isOut ? 'inv-stock-out' : ''}`}>
              <i className="fas fa-boxes-stacked"></i> {item.stock_on_hand} {item.unit || 'each'}
              {item.ideal_stock != null && <span className="inv-ideal-hint"> / {item.ideal_stock} ideal</span>}
              {item.ideal_stock == null && item.reorder_level !== null && <span className="inv-reorder-hint"> (reorder at {item.reorder_level})</span>}
            </span>
          )}
        </div>
        {/* Stock level bar */}
        {hasStock && (
          <StockBar current={item.stock_on_hand} reorder={item.reorder_level} ideal={item.ideal_stock} />
        )}
        <div className="inv-card-details">
          {item.supplier && <span className="inv-detail"><i className="fas fa-store"></i> {item.supplier}</span>}
          {showLocation && item.location && <span className="inv-detail"><i className="fas fa-map-marker-alt"></i> {item.location}</span>}
          {showBatchNumber && item.batch_number && <span className="inv-detail"><i className="fas fa-barcode"></i> {item.batch_number}</span>}
        </div>
        {item.notes && <div className="inv-card-notes"><i className="fas fa-sticky-note"></i> {item.notes}</div>}
      </div>

      {/* Quick stock adjust inline */}
      {isAdjusting && hasStock ? (
        <div className="inv-adjust-inline">
          <input type="number" className="inv-adjust-input" value={adjustVal}
            onChange={e => onAdjustValChange(e.target.value)}
            placeholder="+/−" autoFocus
            onKeyDown={e => {
              if (e.key === 'Enter' && adjustVal) onAdjustSubmit(parseFloat(adjustVal));
              if (e.key === 'Escape') onAdjustCancel();
            }} />
          <button className="btn-icon success" onClick={() => adjustVal && onAdjustSubmit(parseFloat(adjustVal))}
            disabled={!adjustVal || isAdjustPending} title="Apply">
            <i className="fas fa-check"></i>
          </button>
          <button className="btn-icon" onClick={onAdjustCancel} title="Cancel">
            <i className="fas fa-times"></i>
          </button>
        </div>
      ) : (
        <div className="inv-card-actions">
          {hasStock && (
            <button className="btn-icon" onClick={onAdjustStart} title="Adjust stock">
              <i className="fas fa-sliders-h"></i>
            </button>
          )}
          <button className="btn-icon" onClick={handleEdit} title="Edit">
            <i className="fas fa-edit"></i>
          </button>
          <button className="btn-icon danger" onClick={onDelete} title="Delete">
            <i className="fas fa-trash"></i>
          </button>
        </div>
      )}
    </div>
  );
}

export default InventoryTab;
