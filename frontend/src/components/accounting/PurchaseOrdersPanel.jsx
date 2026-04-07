import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { formatCurrency, formatDate } from '../../utils/helpers';
import { getPurchaseOrders, createPurchaseOrder, updatePurchaseOrder, deletePurchaseOrder } from '../../services/api';
import { useToast } from '../Toast';
import LoadingSpinner from '../LoadingSpinner';
import DocumentPreview from './DocumentPreview';

const PO_STATUS = {
  draft: { label: 'Draft', color: '#94a3b8', bg: '#f1f5f9', icon: 'fa-file' },
  sent: { label: 'Sent', color: '#3b82f6', bg: '#eff6ff', icon: 'fa-paper-plane' },
  received: { label: 'Received', color: '#10b981', bg: '#ecfdf5', icon: 'fa-check-circle' },
  cancelled: { label: 'Cancelled', color: '#ef4444', bg: '#fef2f2', icon: 'fa-times-circle' },
};

function PurchaseOrdersPanel() {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [expandedId, setExpandedId] = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [filterStatus, setFilterStatus] = useState('all');
  const [previewPO, setPreviewPO] = useState(null);
  const [formData, setFormData] = useState({
    supplier: '', notes: '',
    items: [{ name: '', unit_price: 0, quantity: 1, unit: 'each' }],
  });

  const { data: orders = [], isLoading } = useQuery({
    queryKey: ['purchase-orders'],
    queryFn: async () => (await getPurchaseOrders()).data,
    staleTime: 30000,
  });

  const createMut = useMutation({
    mutationFn: createPurchaseOrder,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['purchase-orders'] });
      addToast('Purchase order created', 'success');
      resetForm();
    },
    onError: (e) => addToast(e.response?.data?.error || 'Failed to create PO', 'error'),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }) => updatePurchaseOrder(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['purchase-orders'] });
      addToast('Purchase order updated', 'success');
      resetForm();
    },
    onError: (e) => addToast(e.response?.data?.error || 'Failed to update', 'error'),
  });

  const deleteMut = useMutation({
    mutationFn: deletePurchaseOrder,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['purchase-orders'] });
      addToast('Purchase order deleted', 'success');
      setDeleteConfirm(null);
    },
  });

  const resetForm = () => {
    setFormData({ supplier: '', notes: '', items: [{ name: '', unit_price: 0, quantity: 1, unit: 'each' }] });
    setShowForm(false);
    setEditingId(null);
  };

  const startEdit = (po) => {
    const items = (po.items || []).length > 0 ? po.items : [{ name: '', unit_price: 0, quantity: 1, unit: 'each' }];
    setFormData({ supplier: po.supplier || '', notes: po.notes || '', items });
    setEditingId(po.id);
    setShowForm(true);
  };

  const addItem = () => setFormData({ ...formData, items: [...formData.items, { name: '', unit_price: 0, quantity: 1, unit: 'each' }] });
  const removeItem = (idx) => setFormData({ ...formData, items: formData.items.filter((_, i) => i !== idx) });
  const updateItem = (idx, field, value) => {
    const items = [...formData.items];
    items[idx] = { ...items[idx], [field]: value };
    setFormData({ ...formData, items });
  };

  const formTotal = formData.items.reduce((s, i) => s + (parseFloat(i.unit_price) || 0) * (parseFloat(i.quantity) || 1), 0);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (formData.items.length === 0 || !formData.items.some(i => i.name.trim())) {
      addToast('Add at least one item', 'warning'); return;
    }
    if (editingId) {
      updateMut.mutate({ id: editingId, data: formData });
    } else {
      createMut.mutate(formData);
    }
  };

  const stats = useMemo(() => {
    const total = orders.reduce((s, o) => s + (o.total || 0), 0);
    const draft = orders.filter(o => o.status === 'draft').length;
    const sent = orders.filter(o => o.status === 'sent').length;
    return { total, draft, sent, count: orders.length };
  }, [orders]);

  const filtered = filterStatus === 'all' ? orders : orders.filter(o => o.status === filterStatus);

  if (isLoading) return <LoadingSpinner message="Loading purchase orders..." />;

  return (
    <div className="acct-panel">
      <div className="acct-stats-row">
        <div className="acct-stat-card">
          <div className="acct-stat-icon" style={{ background: 'rgba(99, 102, 241, 0.1)' }}>
            <i className="fas fa-file-export" style={{ color: '#6366f1' }}></i>
          </div>
          <div className="acct-stat-content">
            <div className="acct-stat-value">{formatCurrency(stats.total)}</div>
            <div className="acct-stat-label">Total PO Value</div>
          </div>
        </div>
        <div className="acct-stat-card">
          <div className="acct-stat-icon" style={{ background: 'rgba(148, 163, 184, 0.1)' }}>
            <i className="fas fa-file" style={{ color: '#94a3b8' }}></i>
          </div>
          <div className="acct-stat-content">
            <div className="acct-stat-value">{stats.draft}</div>
            <div className="acct-stat-label">Drafts</div>
          </div>
        </div>
        <div className="acct-stat-card">
          <div className="acct-stat-icon" style={{ background: 'rgba(59, 130, 246, 0.1)' }}>
            <i className="fas fa-paper-plane" style={{ color: '#3b82f6' }}></i>
          </div>
          <div className="acct-stat-content">
            <div className="acct-stat-value">{stats.sent}</div>
            <div className="acct-stat-label">Sent</div>
          </div>
        </div>
        <div className="acct-stat-card">
          <div className="acct-stat-icon" style={{ background: 'rgba(16, 185, 129, 0.1)' }}>
            <i className="fas fa-list" style={{ color: '#10b981' }}></i>
          </div>
          <div className="acct-stat-content">
            <div className="acct-stat-value">{stats.count}</div>
            <div className="acct-stat-label">Total Orders</div>
          </div>
        </div>
      </div>

      <div className="acct-toolbar">
        <button className="acct-btn-primary" onClick={() => { resetForm(); setShowForm(!showForm); }}>
          <i className={`fas ${showForm ? 'fa-times' : 'fa-plus'}`}></i>
          {showForm ? 'Cancel' : 'New Purchase Order'}
        </button>
        <div className="acct-toolbar-right">
          <div className="acct-filter-pills">
            {['all', 'draft', 'sent', 'received', 'cancelled'].map(s => (
              <button key={s} className={`acct-pill ${filterStatus === s ? 'active' : ''}`}
                onClick={() => setFilterStatus(s)}>
                {s === 'all' ? 'All' : PO_STATUS[s]?.label || s}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Create / Edit Form */}
      {showForm && (
        <form className="acct-form" onSubmit={handleSubmit}>
          <div className="acct-form-grid">
            <div className="acct-field">
              <label>Supplier</label>
              <input type="text" placeholder="e.g. Screwfix, Plumb Center..." value={formData.supplier}
                onChange={e => setFormData({ ...formData, supplier: e.target.value })} />
            </div>
            <div className="acct-field acct-field-wide">
              <label>Notes</label>
              <input type="text" placeholder="What is this order for?" value={formData.notes}
                onChange={e => setFormData({ ...formData, notes: e.target.value })} />
            </div>
          </div>

          <div className="acct-line-items">
            <div className="acct-line-header">
              <span className="acct-line-desc-h">Item</span>
              <span className="acct-line-qty-h">Qty</span>
              <span className="acct-line-price-h">Unit Price</span>
              <span className="acct-line-total-h">Total</span>
              <span className="acct-line-action-h"></span>
            </div>
            {formData.items.map((item, idx) => (
              <div key={idx} className="acct-line-row">
                <input className="acct-line-desc" type="text" placeholder="Item name"
                  value={item.name} onChange={e => updateItem(idx, 'name', e.target.value)} />
                <input className="acct-line-qty" type="number" min="1" step="1"
                  value={item.quantity} onChange={e => updateItem(idx, 'quantity', e.target.value)} />
                <div className="acct-line-price-wrap">
                  <span className="acct-input-prefix-sm">€</span>
                  <input className="acct-line-price" type="number" min="0" step="0.01"
                    value={item.unit_price} onChange={e => updateItem(idx, 'unit_price', e.target.value)} />
                </div>
                <span className="acct-line-total">{formatCurrency((parseFloat(item.unit_price) || 0) * (parseFloat(item.quantity) || 1))}</span>
                {formData.items.length > 1 && (
                  <button type="button" className="acct-btn-icon acct-btn-icon-danger" onClick={() => removeItem(idx)}>
                    <i className="fas fa-times"></i>
                  </button>
                )}
              </div>
            ))}
            <button type="button" className="acct-btn-link" onClick={addItem}>
              <i className="fas fa-plus"></i> Add Item
            </button>
          </div>

          <div className="acct-totals">
            <div className="acct-total-row acct-total-final"><span>Total</span><span>{formatCurrency(formTotal)}</span></div>
          </div>

          <div className="acct-form-actions">
            <button type="button" className="acct-btn-secondary" onClick={resetForm}>Cancel</button>
            <button type="submit" className="acct-btn-primary" disabled={createMut.isPending || updateMut.isPending}>
              <i className={`fas ${createMut.isPending || updateMut.isPending ? 'fa-spinner fa-spin' : 'fa-check'}`}></i>
              {editingId ? 'Save Changes' : 'Create PO'}
            </button>
          </div>
        </form>
      )}

      {/* Orders List */}
      <div className="acct-list">
        {filtered.length === 0 ? (
          <div className="acct-empty">
            <i className="fas fa-file-export"></i>
            <p>{orders.length === 0 ? 'No purchase orders yet. Create one above or generate from a job\'s materials.' : 'No orders match this filter.'}</p>
          </div>
        ) : (
          filtered.map(po => {
            const sc = PO_STATUS[po.status] || PO_STATUS.draft;
            const items = po.items || [];
            const isExpanded = expandedId === po.id;
            return (
              <div key={po.id} className="acct-list-item" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', cursor: 'pointer' }}
                  onClick={() => setExpandedId(isExpanded ? null : po.id)}>
                  <div className="acct-list-icon" style={{ background: sc.bg, color: sc.color }}>
                    <i className={`fas ${sc.icon}`}></i>
                  </div>
                  <div className="acct-list-content">
                    <div className="acct-list-title">{po.po_number}{po.supplier ? ` — ${po.supplier}` : ''}</div>
                    <div className="acct-list-meta">
                      <span><i className="fas fa-calendar"></i> {formatDate(po.created_at)}</span>
                      <span><i className="fas fa-box"></i> {items.length} item{items.length !== 1 ? 's' : ''}</span>
                      {po.notes && <span><i className="fas fa-sticky-note"></i> {po.notes}</span>}
                      <span className="acct-badge" style={{ background: sc.bg, color: sc.color }}>{sc.label}</span>
                    </div>
                  </div>
                  <div className="acct-list-amount" style={{ color: '#1e293b' }}>{formatCurrency(po.total)}</div>
                  <i className={`fas fa-chevron-${isExpanded ? 'up' : 'down'}`} style={{ color: '#94a3b8', fontSize: '0.75rem' }}></i>
                </div>

                {/* Expanded detail */}
                {isExpanded && (
                  <div style={{ marginTop: '0.75rem', paddingTop: '0.75rem', borderTop: '1px solid #f1f5f9' }}>
                    {items.length > 0 && (
                      <div style={{ marginBottom: '0.75rem' }}>
                        {items.map((item, idx) => (
                          <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', padding: '0.3rem 0', fontSize: '0.82rem', color: '#475569', borderBottom: '1px solid #f8fafc' }}>
                            <span>{item.name}</span>
                            <span>{item.quantity} × {formatCurrency(item.unit_price)} = {formatCurrency((parseFloat(item.unit_price) || 0) * (parseFloat(item.quantity) || 1))}</span>
                          </div>
                        ))}
                      </div>
                    )}
                    <div className="acct-list-actions" style={{ justifyContent: 'flex-start', gap: '0.4rem' }}>
                      <button className="acct-btn-icon" onClick={(e) => { e.stopPropagation(); setPreviewPO(po); }} title="Preview">
                        <i className="fas fa-eye"></i>
                      </button>
                      {(po.status === 'draft' || po.status === 'sent') && (
                        <button className="acct-btn-icon" onClick={(e) => { e.stopPropagation(); startEdit(po); }} title="Edit">
                          <i className="fas fa-pen"></i>
                        </button>
                      )}
                      {po.status === 'draft' && (
                        <button className="acct-btn-icon" title="Mark Sent"
                          onClick={(e) => { e.stopPropagation(); updateMut.mutate({ id: po.id, data: { status: 'sent' } }); }}>
                          <i className="fas fa-paper-plane"></i>
                        </button>
                      )}
                      {po.status === 'sent' && (
                        <button className="acct-btn-icon acct-btn-icon-success" title="Mark Received"
                          onClick={(e) => { e.stopPropagation(); updateMut.mutate({ id: po.id, data: { status: 'received' } }); }}>
                          <i className="fas fa-check"></i>
                        </button>
                      )}
                      {po.status !== 'cancelled' && po.status !== 'received' && (
                        <button className="acct-btn-icon" title="Cancel PO"
                          onClick={(e) => { e.stopPropagation(); updateMut.mutate({ id: po.id, data: { status: 'cancelled' } }); }}>
                          <i className="fas fa-ban" style={{ color: '#f59e0b' }}></i>
                        </button>
                      )}
                      {deleteConfirm === po.id ? (
                        <div className="acct-confirm-inline">
                          <button className="acct-btn-danger-sm" onClick={(e) => { e.stopPropagation(); deleteMut.mutate(po.id); }}>Delete</button>
                          <button className="acct-btn-secondary-sm" onClick={(e) => { e.stopPropagation(); setDeleteConfirm(null); }}>Cancel</button>
                        </div>
                      ) : (
                        <button className="acct-btn-icon acct-btn-icon-danger" onClick={(e) => { e.stopPropagation(); setDeleteConfirm(po.id); }} title="Delete">
                          <i className="fas fa-trash"></i>
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Document Preview */}
      {previewPO && (
        <DocumentPreview
          type="purchase-order"
          docNumber={previewPO.po_number}
          date={previewPO.created_at}
          supplier={previewPO.supplier}
          lineItems={(previewPO.items || []).map(i => ({ description: i.name, quantity: i.quantity, amount: i.unit_price }))}
          subtotal={previewPO.total}
          total={previewPO.total}
          notes={previewPO.notes}
          status={PO_STATUS[previewPO.status]?.label}
          onClose={() => setPreviewPO(null)}
        />
      )}
    </div>
  );
}

export default PurchaseOrdersPanel;
