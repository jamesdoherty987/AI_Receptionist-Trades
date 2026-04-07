import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { formatCurrency, formatDate } from '../../utils/helpers';
import { getQuotes, createQuote, updateQuote, deleteQuote, convertQuoteToJob, getClients, getTaxSettings } from '../../services/api';
import { useToast } from '../Toast';
import DocumentPreview from './DocumentPreview';
import LoadingSpinner from '../LoadingSpinner';

const STATUS_CONFIG = {
  draft: { label: 'Draft', color: '#94a3b8', bg: '#f1f5f9', icon: 'fa-file' },
  sent: { label: 'Sent', color: '#3b82f6', bg: '#eff6ff', icon: 'fa-paper-plane' },
  accepted: { label: 'Accepted', color: '#10b981', bg: '#ecfdf5', icon: 'fa-check-circle' },
  declined: { label: 'Declined', color: '#ef4444', bg: '#fef2f2', icon: 'fa-times-circle' },
  expired: { label: 'Expired', color: '#f59e0b', bg: '#fffbeb', icon: 'fa-clock' },
  converted: { label: 'Converted to Job', color: '#8b5cf6', bg: '#f5f3ff', icon: 'fa-exchange-alt' },
};

function QuotesPanel() {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [convertModal, setConvertModal] = useState(null);
  const [convertDate, setConvertDate] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');
  const [previewQuote, setPreviewQuote] = useState(null);
  const [formData, setFormData] = useState({
    client_id: '', title: '', description: '', notes: '',
    valid_until: '', line_items: [{ description: '', quantity: 1, amount: 0 }],
  });

  const { data: quotes = [], isLoading } = useQuery({
    queryKey: ['quotes'],
    queryFn: async () => (await getQuotes()).data,
    staleTime: 30000,
  });

  const { data: clients = [] } = useQuery({
    queryKey: ['clients'],
    queryFn: async () => (await getClients()).data,
    staleTime: 60000,
  });

  const { data: taxSettings } = useQuery({
    queryKey: ['tax-settings'],
    queryFn: async () => (await getTaxSettings()).data,
    staleTime: 60000,
  });

  const taxRate = taxSettings?.tax_rate || 0;

  const createMut = useMutation({
    mutationFn: (data) => createQuote({ ...data, tax_rate: taxRate }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['quotes'] }); addToast('Quote created', 'success'); resetForm(); },
    onError: (e) => addToast(e.response?.data?.error || 'Failed to create quote', 'error'),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }) => updateQuote(id, { ...data, tax_rate: taxRate }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['quotes'] }); addToast('Quote updated', 'success'); resetForm(); },
    onError: (e) => addToast(e.response?.data?.error || 'Failed to update', 'error'),
  });

  const deleteMut = useMutation({
    mutationFn: deleteQuote,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['quotes'] }); addToast('Quote deleted', 'success'); setDeleteConfirm(null); },
  });

  const convertMut = useMutation({
    mutationFn: ({ id, data }) => convertQuoteToJob(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['quotes'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      addToast('Quote converted to job', 'success');
      setConvertModal(null);
    },
    onError: (e) => addToast(e.response?.data?.error || 'Failed to convert', 'error'),
  });

  const resetForm = () => {
    setFormData({ client_id: '', title: '', description: '', notes: '', valid_until: '',
      line_items: [{ description: '', quantity: 1, amount: 0 }] });
    setShowForm(false); setEditingId(null);
  };

  const addLineItem = () => setFormData({ ...formData, line_items: [...formData.line_items, { description: '', quantity: 1, amount: 0 }] });
  const removeLineItem = (idx) => setFormData({ ...formData, line_items: formData.line_items.filter((_, i) => i !== idx) });
  const updateLineItem = (idx, field, value) => {
    const items = [...formData.line_items];
    items[idx] = { ...items[idx], [field]: value };
    setFormData({ ...formData, line_items: items });
  };

  const formSubtotal = formData.line_items.reduce((s, i) => s + (parseFloat(i.amount) || 0) * (parseFloat(i.quantity) || 1), 0);
  const formTax = Math.round(formSubtotal * taxRate) / 100;
  const formTotal = formSubtotal + formTax;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (formData.line_items.length === 0 || formSubtotal <= 0) {
      addToast('Add at least one line item with a value', 'warning'); return;
    }
    if (editingId) updateMut.mutate({ id: editingId, data: formData });
    else createMut.mutate(formData);
  };

  const startEdit = (q) => {
    setFormData({
      client_id: q.client_id || '', title: q.title || '', description: q.description || '',
      notes: q.notes || '', valid_until: q.valid_until?.split('T')[0] || '',
      line_items: (q.line_items || []).length > 0 ? q.line_items : [{ description: '', quantity: 1, amount: 0 }],
    });
    setEditingId(q.id); setShowForm(true);
  };

  const stats = useMemo(() => {
    const draft = quotes.filter(q => q.status === 'draft').length;
    const sent = quotes.filter(q => q.status === 'sent').length;
    const accepted = quotes.filter(q => q.status === 'accepted').length;
    const totalValue = quotes.reduce((s, q) => s + (q.total || 0), 0);
    return { draft, sent, accepted, totalValue };
  }, [quotes]);

  const filtered = filterStatus === 'all' ? quotes : quotes.filter(q => q.status === filterStatus);

  if (isLoading) return <LoadingSpinner message="Loading quotes..." />;

  return (
    <div className="acct-panel">
      <div className="acct-stats-row">
        <div className="acct-stat-card">
          <div className="acct-stat-icon" style={{ background: 'rgba(99, 102, 241, 0.1)' }}>
            <i className="fas fa-file-invoice" style={{ color: '#6366f1' }}></i>
          </div>
          <div className="acct-stat-content">
            <div className="acct-stat-value">{formatCurrency(stats.totalValue)}</div>
            <div className="acct-stat-label">Total Quoted</div>
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
            <i className="fas fa-check-circle" style={{ color: '#10b981' }}></i>
          </div>
          <div className="acct-stat-content">
            <div className="acct-stat-value">{stats.accepted}</div>
            <div className="acct-stat-label">Accepted</div>
          </div>
        </div>
      </div>

      <div className="acct-toolbar">
        <button className="acct-btn-primary" onClick={() => { resetForm(); setShowForm(!showForm); }}>
          <i className={`fas ${showForm ? 'fa-times' : 'fa-plus'}`}></i>
          {showForm ? 'Cancel' : 'New Quote'}
        </button>
        <div className="acct-toolbar-right">
          <div className="acct-filter-pills">
            {['all', 'draft', 'sent', 'accepted', 'declined', 'converted'].map(s => (
              <button key={s} className={`acct-pill ${filterStatus === s ? 'active' : ''}`}
                onClick={() => setFilterStatus(s)}>
                {s === 'all' ? 'All' : STATUS_CONFIG[s]?.label || s}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Quote Form */}
      {showForm && (
        <form className="acct-form" onSubmit={handleSubmit}>
          <div className="acct-form-grid">
            <div className="acct-field">
              <label>Customer</label>
              <select value={formData.client_id} onChange={e => setFormData({ ...formData, client_id: e.target.value })}>
                <option value="">Select customer...</option>
                {clients.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
            <div className="acct-field">
              <label>Title *</label>
              <input type="text" placeholder="e.g. Bathroom Renovation Quote" required
                value={formData.title} onChange={e => setFormData({ ...formData, title: e.target.value })} />
            </div>
            <div className="acct-field">
              <label>Valid Until</label>
              <input type="date" value={formData.valid_until}
                onChange={e => setFormData({ ...formData, valid_until: e.target.value })} />
            </div>
            <div className="acct-field acct-field-wide">
              <label>Description</label>
              <textarea rows={2} placeholder="Brief description of the work..."
                value={formData.description} onChange={e => setFormData({ ...formData, description: e.target.value })} />
            </div>
          </div>

          {/* Line Items */}
          <div className="acct-line-items">
            <div className="acct-line-header">
              <span className="acct-line-desc-h">Item</span>
              <span className="acct-line-qty-h">Qty</span>
              <span className="acct-line-price-h">Price</span>
              <span className="acct-line-total-h">Total</span>
              <span className="acct-line-action-h"></span>
            </div>
            {formData.line_items.map((item, idx) => (
              <div key={idx} className="acct-line-row">
                <input className="acct-line-desc" type="text" placeholder="Item description"
                  value={item.description} onChange={e => updateLineItem(idx, 'description', e.target.value)} />
                <input className="acct-line-qty" type="number" min="1" step="1"
                  value={item.quantity} onChange={e => updateLineItem(idx, 'quantity', e.target.value)} />
                <div className="acct-line-price-wrap">
                  <span className="acct-input-prefix-sm">€</span>
                  <input className="acct-line-price" type="number" min="0" step="0.01"
                    value={item.amount} onChange={e => updateLineItem(idx, 'amount', e.target.value)} />
                </div>
                <span className="acct-line-total">{formatCurrency((parseFloat(item.amount) || 0) * (parseFloat(item.quantity) || 1))}</span>
                {formData.line_items.length > 1 && (
                  <button type="button" className="acct-btn-icon acct-btn-icon-danger" onClick={() => removeLineItem(idx)}>
                    <i className="fas fa-times"></i>
                  </button>
                )}
              </div>
            ))}
            <button type="button" className="acct-btn-link" onClick={addLineItem}>
              <i className="fas fa-plus"></i> Add Line Item
            </button>
          </div>

          {/* Totals */}
          <div className="acct-totals">
            <div className="acct-total-row"><span>Subtotal</span><span>{formatCurrency(formSubtotal)}</span></div>
            {taxRate > 0 && <div className="acct-total-row"><span>Tax ({taxRate}%)</span><span>{formatCurrency(formTax)}</span></div>}
            <div className="acct-total-row acct-total-final"><span>Total</span><span>{formatCurrency(formTotal)}</span></div>
          </div>

          <div className="acct-field acct-field-wide" style={{ marginTop: '0.75rem' }}>
            <label>Notes</label>
            <textarea rows={2} placeholder="Additional notes for the customer..."
              value={formData.notes} onChange={e => setFormData({ ...formData, notes: e.target.value })} />
          </div>

          <div className="acct-form-actions">
            <button type="button" className="acct-btn-secondary" onClick={resetForm}>Cancel</button>
            <button type="submit" className="acct-btn-primary" disabled={createMut.isPending || updateMut.isPending}>
              <i className={`fas ${createMut.isPending || updateMut.isPending ? 'fa-spinner fa-spin' : 'fa-check'}`}></i>
              {editingId ? 'Update Quote' : 'Create Quote'}
            </button>
          </div>
        </form>
      )}

      {/* Convert Modal */}
      {convertModal && (
        <div className="acct-modal-overlay" onClick={() => setConvertModal(null)}>
          <div className="acct-modal" onClick={e => e.stopPropagation()}>
            <h3><i className="fas fa-exchange-alt"></i> Convert to Job</h3>
            <p>Schedule this quote as a job. Choose an appointment date/time:</p>
            <input type="datetime-local" className="acct-modal-input" value={convertDate}
              onChange={e => setConvertDate(e.target.value)} />
            <div className="acct-modal-actions">
              <button className="acct-btn-secondary" onClick={() => setConvertModal(null)}>Cancel</button>
              <button className="acct-btn-primary" disabled={!convertDate || convertMut.isPending}
                onClick={() => convertMut.mutate({ id: convertModal.id, data: { appointment_time: convertDate } })}>
                <i className={`fas ${convertMut.isPending ? 'fa-spinner fa-spin' : 'fa-check'}`}></i> Convert
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Quotes List */}
      <div className="acct-list">
        {filtered.length === 0 ? (
          <div className="acct-empty">
            <i className="fas fa-file-invoice"></i>
            <p>{quotes.length === 0 ? 'No quotes yet. Create your first estimate above.' : 'No quotes match this filter.'}</p>
          </div>
        ) : (
          filtered.map(q => {
            const sc = STATUS_CONFIG[q.status] || STATUS_CONFIG.draft;
            return (
              <div key={q.id} className="acct-list-item">
                <div className="acct-list-icon" style={{ background: sc.bg, color: sc.color }}>
                  <i className={`fas ${sc.icon}`}></i>
                </div>
                <div className="acct-list-content">
                  <div className="acct-list-title">{q.title || `Quote #${q.quote_number}`}</div>
                  <div className="acct-list-meta">
                    {q.client_name && <span><i className="fas fa-user"></i> {q.client_name}</span>}
                    <span><i className="fas fa-calendar"></i> {formatDate(q.created_at)}</span>
                    {q.valid_until && <span><i className="fas fa-hourglass-half"></i> Valid until {formatDate(q.valid_until)}</span>}
                    <span className="acct-badge" style={{ background: sc.bg, color: sc.color }}>{sc.label}</span>
                  </div>
                </div>
                <div className="acct-list-amount" style={{ color: '#1e293b' }}>{formatCurrency(q.total)}</div>
                <div className="acct-list-actions">
                  <button className="acct-btn-icon" onClick={() => setPreviewQuote(q)} title="Preview"><i className="fas fa-eye"></i></button>
                  {q.status !== 'converted' && (
                    <button className="acct-btn-icon" onClick={() => startEdit(q)} title="Edit"><i className="fas fa-pen"></i></button>
                  )}
                  {q.status === 'draft' && (
                    <button className="acct-btn-icon" title="Mark Sent"
                      onClick={() => updateMut.mutate({ id: q.id, data: { status: 'sent' } })}>
                      <i className="fas fa-paper-plane"></i>
                    </button>
                  )}
                  {q.status === 'sent' && (
                    <>
                      <button className="acct-btn-icon acct-btn-icon-success" title="Mark Accepted"
                        onClick={() => updateMut.mutate({ id: q.id, data: { status: 'accepted' } })}>
                        <i className="fas fa-check"></i>
                      </button>
                      <button className="acct-btn-icon acct-btn-icon-danger" title="Mark Declined"
                        onClick={() => updateMut.mutate({ id: q.id, data: { status: 'declined' } })}>
                        <i className="fas fa-times"></i>
                      </button>
                    </>
                  )}
                  {(q.status === 'accepted') && q.status !== 'converted' && (
                    <button className="acct-btn-icon acct-btn-icon-success" title="Convert to Job"
                      onClick={() => { setConvertModal(q); setConvertDate(''); }}>
                      <i className="fas fa-exchange-alt"></i>
                    </button>
                  )}
                  {deleteConfirm === q.id ? (
                    <div className="acct-confirm-inline">
                      <button className="acct-btn-danger-sm" onClick={() => deleteMut.mutate(q.id)}>Delete</button>
                      <button className="acct-btn-secondary-sm" onClick={() => setDeleteConfirm(null)}>Cancel</button>
                    </div>
                  ) : (
                    <button className="acct-btn-icon acct-btn-icon-danger" onClick={() => setDeleteConfirm(q.id)} title="Delete">
                      <i className="fas fa-trash"></i>
                    </button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Document Preview */}
      {previewQuote && (
        <DocumentPreview
          type="quote"
          docNumber={previewQuote.quote_number}
          date={previewQuote.created_at}
          dueDate={previewQuote.valid_until}
          customer={{ name: previewQuote.client_name, phone: previewQuote.client_phone, email: previewQuote.client_email }}
          lineItems={previewQuote.line_items || []}
          subtotal={previewQuote.subtotal}
          taxRate={previewQuote.tax_rate}
          taxAmount={previewQuote.tax_amount}
          total={previewQuote.total}
          notes={previewQuote.notes}
          status={STATUS_CONFIG[previewQuote.status]?.label}
          onClose={() => setPreviewQuote(null)}
        />
      )}
    </div>
  );
}

export default QuotesPanel;
