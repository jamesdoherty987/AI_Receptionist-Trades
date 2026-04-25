import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { formatCurrency, formatDate } from '../../utils/helpers';
import { getRevenueEntries, createRevenueEntry, updateRevenueEntry, deleteRevenueEntry, getBookings } from '../../services/api';
import { useIndustry } from '../../context/IndustryContext';
import { useToast } from '../Toast';
import LoadingSpinner from '../LoadingSpinner';

const REVENUE_CATEGORIES = [
  { value: 'walk_in', label: 'Walk-in Sale', icon: 'fa-door-open', color: '#10b981' },
  { value: 'cash_sale', label: 'Cash Sale', icon: 'fa-money-bill-wave', color: '#16a34a' },
  { value: 'service', label: 'Service Income', icon: 'fa-concierge-bell', color: '#6366f1' },
  { value: 'product', label: 'Product Sale', icon: 'fa-box', color: '#8b5cf6' },
  { value: 'tip', label: 'Tip / Gratuity', icon: 'fa-hand-holding-dollar', color: '#f59e0b' },
  { value: 'deposit', label: 'Deposit Received', icon: 'fa-piggy-bank', color: '#0ea5e9' },
  { value: 'catering', label: 'Catering / Event', icon: 'fa-champagne-glasses', color: '#ec4899' },
  { value: 'subscription', label: 'Subscription / Retainer', icon: 'fa-rotate', color: '#14b8a6' },
  { value: 'refund_received', label: 'Refund Received', icon: 'fa-arrow-rotate-left', color: '#64748b' },
  { value: 'other', label: 'Other Income', icon: 'fa-ellipsis', color: '#94a3b8' },
];

const PAYMENT_METHODS = [
  { value: 'cash', label: 'Cash', icon: 'fa-money-bill-wave' },
  { value: 'card', label: 'Card', icon: 'fa-credit-card' },
  { value: 'bank_transfer', label: 'Bank Transfer', icon: 'fa-building-columns' },
  { value: 'stripe', label: 'Stripe', icon: 'fa-bolt' },
  { value: 'cheque', label: 'Cheque', icon: 'fa-money-check' },
  { value: 'other', label: 'Other', icon: 'fa-ellipsis' },
];

const getCategoryInfo = (val) => REVENUE_CATEGORIES.find(c => c.value === val) || REVENUE_CATEGORIES[REVENUE_CATEGORIES.length - 1];
const getPaymentInfo = (val) => PAYMENT_METHODS.find(m => m.value === val) || PAYMENT_METHODS[PAYMENT_METHODS.length - 1];

function RevenueLedgerPanel() {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const { terminology } = useIndustry();
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [filterCategory, setFilterCategory] = useState('all');
  const [viewMode, setViewMode] = useState('all'); // 'all', 'manual', 'booked'
  const [searchTerm, setSearchTerm] = useState('');
  const [formData, setFormData] = useState({
    amount: '', category: 'walk_in', description: '', payment_method: 'cash',
    date: new Date().toISOString().split('T')[0], notes: '', booking_id: ''
  });

  // Fetch manual revenue entries
  const { data: entries = [], isLoading } = useQuery({
    queryKey: ['revenue-entries'],
    queryFn: async () => (await getRevenueEntries()).data,
  });

  // Fetch booked jobs for the combined ledger view
  const { data: bookings = [] } = useQuery({
    queryKey: ['bookings'],
    queryFn: async () => (await getBookings()).data,
    staleTime: 60000,
  });

  // Build combined ledger: manual entries + completed/paid booked jobs
  const bookedRevenue = useMemo(() => {
    return (Array.isArray(bookings) ? bookings : [])
      .filter(b => b.charge && parseFloat(b.charge) > 0 && b.status !== 'cancelled')
      .map(b => ({
        id: `booking-${b.id}`,
        booking_id: b.id,
        amount: parseFloat(b.charge || 0),
        category: 'booked_job',
        description: b.service_type || b.service || (terminology.job || 'Job'),
        payment_method: b.payment_method || (b.payment_status === 'paid' ? 'card' : 'pending'),
        date: b.appointment_time ? (typeof b.appointment_time === 'string' ? b.appointment_time.split('T')[0] : b.appointment_time) : '',
        notes: b.customer_name || b.client_name || '',
        payment_status: b.payment_status,
        status: b.status,
        is_booking: true,
      }));
  }, [bookings, terminology]);

  const createMut = useMutation({
    mutationFn: createRevenueEntry,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['revenue-entries'] });
      queryClient.invalidateQueries({ queryKey: ['finances'] });
      queryClient.invalidateQueries({ queryKey: ['pnl-report'] });
      addToast('Revenue entry added', 'success');
      resetForm();
    },
    onError: (e) => addToast(e.response?.data?.error || 'Failed to add entry', 'error'),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }) => updateRevenueEntry(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['revenue-entries'] });
      queryClient.invalidateQueries({ queryKey: ['finances'] });
      queryClient.invalidateQueries({ queryKey: ['pnl-report'] });
      addToast('Entry updated', 'success');
      resetForm();
    },
    onError: (e) => addToast(e.response?.data?.error || 'Failed to update', 'error'),
  });

  const deleteMut = useMutation({
    mutationFn: deleteRevenueEntry,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['revenue-entries'] });
      queryClient.invalidateQueries({ queryKey: ['finances'] });
      queryClient.invalidateQueries({ queryKey: ['pnl-report'] });
      addToast('Entry deleted', 'success');
      setDeleteConfirm(null);
    },
    onError: (e) => addToast(e.response?.data?.error || 'Failed to delete', 'error'),
  });

  const resetForm = () => {
    setFormData({ amount: '', category: 'walk_in', description: '', payment_method: 'cash',
      date: new Date().toISOString().split('T')[0], notes: '', booking_id: '' });
    setShowForm(false);
    setEditingId(null);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!formData.amount || parseFloat(formData.amount) <= 0) {
      addToast('Enter a valid amount', 'warning');
      return;
    }
    if (editingId) {
      updateMut.mutate({ id: editingId, data: formData });
    } else {
      createMut.mutate(formData);
    }
  };

  const startEdit = (entry) => {
    setFormData({
      amount: entry.amount, category: entry.category, description: entry.description || '',
      payment_method: entry.payment_method || 'cash', date: entry.date?.split('T')[0] || '',
      notes: entry.notes || '', booking_id: entry.booking_id || ''
    });
    setEditingId(entry.id);
    setShowForm(true);
  };

  // Stats
  const stats = useMemo(() => {
    const manualTotal = entries.reduce((s, e) => s + (e.amount || 0), 0);
    const bookedTotal = bookedRevenue.reduce((s, b) => s + (b.amount || 0), 0);
    const bookedPaid = bookedRevenue.filter(b => b.payment_status === 'paid').reduce((s, b) => s + (b.amount || 0), 0);
    const thisMonth = entries.filter(e => {
      const d = new Date(e.date);
      const now = new Date();
      return d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear();
    }).reduce((s, e) => s + (e.amount || 0), 0);
    const byCategory = {};
    entries.forEach(e => {
      byCategory[e.category] = (byCategory[e.category] || 0) + (e.amount || 0);
    });
    const topCategory = Object.entries(byCategory).sort((a, b) => b[1] - a[1])[0];
    return { manualTotal, bookedTotal, bookedPaid, thisMonth, topCategory, byCategory, combinedTotal: manualTotal + bookedTotal };
  }, [entries, bookedRevenue]);

  // Build combined + filtered list
  const filtered = useMemo(() => {
    let list;
    if (viewMode === 'manual') {
      list = entries.map(e => ({ ...e, is_booking: false }));
    } else if (viewMode === 'booked') {
      list = bookedRevenue;
    } else {
      list = [
        ...entries.map(e => ({ ...e, is_booking: false })),
        ...bookedRevenue,
      ];
    }
    if (filterCategory !== 'all') {
      if (filterCategory === 'booked_job') {
        list = list.filter(e => e.is_booking);
      } else {
        list = list.filter(e => e.category === filterCategory);
      }
    }
    if (searchTerm) {
      const q = searchTerm.toLowerCase();
      list = list.filter(e =>
        (e.description || '').toLowerCase().includes(q) ||
        (e.notes || '').toLowerCase().includes(q) ||
        (e.category || '').toLowerCase().includes(q)
      );
    }
    // Sort by date descending
    list.sort((a, b) => {
      const da = a.date || '';
      const db = b.date || '';
      return db.localeCompare(da);
    });
    return list;
  }, [entries, bookedRevenue, viewMode, filterCategory, searchTerm]);

  // Group by month
  const groupedByMonth = useMemo(() => {
    const groups = {};
    filtered.forEach(e => {
      const dateStr = e.date || '';
      const d = new Date(dateStr.includes('T') ? dateStr : dateStr + 'T00:00:00');
      const key = isNaN(d) ? '0000-00' : `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
      const label = isNaN(d) ? 'Unknown Date' : d.toLocaleDateString('en-IE', { month: 'long', year: 'numeric' });
      if (!groups[key]) groups[key] = { key, label, items: [], total: 0 };
      groups[key].items.push(e);
      groups[key].total += (e.amount || 0);
    });
    return Object.values(groups).sort((a, b) => b.key.localeCompare(a.key));
  }, [filtered]);

  if (isLoading) return <LoadingSpinner message="Loading income ledger..." />;

  const jobLabel = terminology.job || 'Job';
  const jobsLabel = terminology.jobs || 'Jobs';

  return (
    <div className="acct-panel">
      {/* Panel Header */}
      <div className="acct-panel-header">
        <h2 className="acct-panel-title"><i className="fas fa-book"></i> Income Ledger</h2>
        <button className="acct-btn-primary" onClick={() => { resetForm(); setShowForm(!showForm); }}>
          <i className={`fas ${showForm ? 'fa-times' : 'fa-plus'}`}></i>
          {showForm ? 'Cancel' : 'Add Income'}
        </button>
      </div>

      {/* Stats Row */}
      <div className="acct-stats-row">
        <div className="acct-stat-card">
          <div className="acct-stat-icon" style={{ background: 'rgba(16, 185, 129, 0.1)' }}>
            <i className="fas fa-coins" style={{ color: '#10b981' }}></i>
          </div>
          <div className="acct-stat-content">
            <div className="acct-stat-value">{formatCurrency(stats.combinedTotal)}</div>
            <div className="acct-stat-label">Total Income</div>
          </div>
        </div>
        <div className="acct-stat-card">
          <div className="acct-stat-icon" style={{ background: 'rgba(99, 102, 241, 0.1)' }}>
            <i className="fas fa-calendar-check" style={{ color: '#6366f1' }}></i>
          </div>
          <div className="acct-stat-content">
            <div className="acct-stat-value">{formatCurrency(stats.bookedTotal)}</div>
            <div className="acct-stat-label">From {jobsLabel}</div>
          </div>
        </div>
        <div className="acct-stat-card">
          <div className="acct-stat-icon" style={{ background: 'rgba(245, 158, 11, 0.1)' }}>
            <i className="fas fa-pen-to-square" style={{ color: '#f59e0b' }}></i>
          </div>
          <div className="acct-stat-content">
            <div className="acct-stat-value">{formatCurrency(stats.manualTotal)}</div>
            <div className="acct-stat-label">Manual Entries</div>
          </div>
        </div>
        <div className="acct-stat-card">
          <div className="acct-stat-icon" style={{ background: 'rgba(14, 165, 233, 0.1)' }}>
            <i className="fas fa-calendar-day" style={{ color: '#0ea5e9' }}></i>
          </div>
          <div className="acct-stat-content">
            <div className="acct-stat-value">{formatCurrency(stats.thisMonth)}</div>
            <div className="acct-stat-label">Manual This Month</div>
          </div>
        </div>
      </div>

      {/* Category Breakdown */}
      {Object.keys(stats.byCategory).length > 0 && (
        <div className="acct-section">
          <div className="acct-section-header"><h3><i className="fas fa-chart-bar"></i> Income by Category</h3></div>
          <div className="acct-category-bars">
            {Object.entries(stats.byCategory).sort((a, b) => b[1] - a[1]).slice(0, 6).map(([cat, amt]) => {
              const info = getCategoryInfo(cat);
              const pct = stats.manualTotal > 0 ? (amt / stats.manualTotal) * 100 : 0;
              return (
                <div key={cat} className="acct-bar-row">
                  <div className="acct-bar-label">
                    <i className={`fas ${info.icon}`} style={{ color: info.color, marginRight: 6 }}></i>
                    {info.label}
                  </div>
                  <div className="acct-bar-track">
                    <div className="acct-bar-fill" style={{ width: `${Math.max(pct, 3)}%`, background: info.color }}></div>
                  </div>
                  <div className="acct-bar-value">{formatCurrency(amt)}</div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Filter Toolbar */}
      <div className="acct-toolbar">
        <div className="acct-filter-pills">
          <button className={`acct-pill ${viewMode === 'all' ? 'active' : ''}`} onClick={() => setViewMode('all')}>All</button>
          <button className={`acct-pill ${viewMode === 'manual' ? 'active' : ''}`} onClick={() => setViewMode('manual')}>Manual</button>
          <button className={`acct-pill ${viewMode === 'booked' ? 'active' : ''}`} onClick={() => setViewMode('booked')}>{jobsLabel}</button>
        </div>
        {viewMode !== 'booked' && (
          <select className="acct-select" value={filterCategory} onChange={e => setFilterCategory(e.target.value)}>
            <option value="all">All Categories</option>
            {REVENUE_CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
          </select>
        )}
        <div className="acct-search" style={{ flex: 1 }}>
          <i className="fas fa-search"></i>
          <input type="text" placeholder="Search income..." value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)} />
        </div>
        {filtered.length > 0 && (
          <button className="acct-btn-secondary" title="Export CSV" style={{ padding: '0.4rem 0.6rem' }}
            onClick={() => {
              const rows = [['Date', 'Type', 'Category', 'Description', 'Payment Method', 'Amount', 'Notes']];
              filtered.forEach(e => rows.push([
                e.date, e.is_booking ? `Booked ${jobLabel}` : 'Manual',
                e.is_booking ? (e.description || '') : (getCategoryInfo(e.category).label),
                e.description || '', e.payment_method || '', e.amount, e.notes || ''
              ]));
              const csv = rows.map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n');
              const blob = new Blob([csv], { type: 'text/csv' });
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a'); a.href = url; a.download = `income-ledger-${new Date().toISOString().split('T')[0]}.csv`; a.click();
              URL.revokeObjectURL(url);
              addToast('Income ledger exported', 'success');
            }}>
            <i className="fas fa-download"></i>
          </button>
        )}
      </div>

      {/* Add/Edit Form */}
      {showForm && (
        <form className="acct-form" onSubmit={handleSubmit}>
          <div className="acct-form-grid">
            <div className="acct-field">
              <label>Amount *</label>
              <div className="acct-input-icon">
                <span className="acct-input-prefix">€</span>
                <input type="number" step="0.01" min="0" placeholder="0.00" required
                  value={formData.amount} onChange={e => setFormData({ ...formData, amount: e.target.value })} />
              </div>
            </div>
            <div className="acct-field">
              <label>Category</label>
              <select value={formData.category} onChange={e => setFormData({ ...formData, category: e.target.value })}>
                {REVENUE_CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
              </select>
            </div>
            <div className="acct-field">
              <label>Date</label>
              <input type="date" value={formData.date} onChange={e => setFormData({ ...formData, date: e.target.value })} />
            </div>
            <div className="acct-field">
              <label>Payment Method</label>
              <select value={formData.payment_method} onChange={e => setFormData({ ...formData, payment_method: e.target.value })}>
                {PAYMENT_METHODS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
              </select>
            </div>
            <div className="acct-field acct-field-wide">
              <label>Description</label>
              <input type="text" placeholder="e.g. Table 5 dinner, walk-in haircut, emergency callout..." value={formData.description}
                onChange={e => setFormData({ ...formData, description: e.target.value })} />
            </div>
            <div className="acct-field acct-field-wide">
              <label>Notes</label>
              <input type="text" placeholder="Any additional details..." value={formData.notes}
                onChange={e => setFormData({ ...formData, notes: e.target.value })} />
            </div>
          </div>
          <div className="acct-form-actions">
            <button type="button" className="acct-btn-secondary" onClick={resetForm}>Cancel</button>
            <button type="submit" className="acct-btn-primary" disabled={createMut.isPending || updateMut.isPending}>
              <i className={`fas ${createMut.isPending || updateMut.isPending ? 'fa-spinner fa-spin' : 'fa-check'}`}></i>
              {editingId ? 'Update' : 'Add Income'}
            </button>
          </div>
        </form>
      )}

      {/* Ledger List */}
      <div className="acct-list">
        {filtered.length === 0 ? (
          <div className="acct-empty">
            <i className="fas fa-book"></i>
            <p>{entries.length === 0 && bookedRevenue.length === 0
              ? 'No income recorded yet. Add your first income entry above, or complete a job to see it here.'
              : 'No entries match your filters.'}</p>
          </div>
        ) : (
          groupedByMonth.map(group => (
            <div key={group.key}>
              <div className="acct-month-header">
                <span className="acct-month-label">{group.label}</span>
                <span className="acct-month-total" style={{ color: '#10b981' }}>{formatCurrency(group.total)}</span>
              </div>
              {group.items.map(entry => {
                if (entry.is_booking) {
                  // Booked job row
                  const isPaid = entry.payment_status === 'paid';
                  return (
                    <div key={entry.id} className="acct-list-item">
                      <div className="acct-list-icon" style={{ background: 'rgba(99, 102, 241, 0.1)', color: '#6366f1' }}>
                        <i className="fas fa-calendar-check"></i>
                      </div>
                      <div className="acct-list-content">
                        <div className="acct-list-title">{entry.description}</div>
                        <div className="acct-list-meta">
                          {entry.notes && <span><i className="fas fa-user"></i> {entry.notes}</span>}
                          <span><i className="fas fa-calendar"></i> {formatDate(entry.date)}</span>
                          <span className={isPaid ? 'acct-badge-green' : 'acct-badge'} style={!isPaid ? { background: '#fffbeb', color: '#b45309' } : undefined}>
                            {isPaid ? 'Paid' : entry.status === 'completed' ? 'Unpaid' : 'Pending'}
                          </span>
                          {entry.payment_method && entry.payment_method !== 'pending' && (
                            <span><i className={`fas ${getPaymentInfo(entry.payment_method).icon}`}></i> {getPaymentInfo(entry.payment_method).label}</span>
                          )}
                          <span className="acct-badge" style={{ background: '#eef2ff', color: '#6366f1' }}>
                            <i className="fas fa-calendar-check" style={{ marginRight: 3 }}></i> Booked {jobLabel}
                          </span>
                        </div>
                      </div>
                      <div className="acct-list-amount" style={{ color: '#10b981' }}>+{formatCurrency(entry.amount)}</div>
                    </div>
                  );
                }

                // Manual entry row
                const info = getCategoryInfo(entry.category);
                return (
                  <div key={entry.id} className="acct-list-item">
                    <div className="acct-list-icon" style={{ background: `${info.color}15`, color: info.color }}>
                      <i className={`fas ${info.icon}`}></i>
                    </div>
                    <div className="acct-list-content">
                      <div className="acct-list-title">{entry.description || info.label}</div>
                      <div className="acct-list-meta">
                        <span><i className="fas fa-calendar"></i> {formatDate(entry.date)}</span>
                        <span><i className={`fas ${getPaymentInfo(entry.payment_method).icon}`}></i> {getPaymentInfo(entry.payment_method).label}</span>
                        {entry.notes && <span><i className="fas fa-sticky-note"></i> {entry.notes}</span>}
                        <span className="acct-badge" style={{ background: '#fef3c7', color: '#b45309' }}>
                          <i className="fas fa-pen-to-square" style={{ marginRight: 3 }}></i> Manual
                        </span>
                      </div>
                    </div>
                    <div className="acct-list-amount" style={{ color: '#10b981' }}>+{formatCurrency(entry.amount)}</div>
                    <div className="acct-list-actions">
                      <button className="acct-btn-icon" onClick={() => startEdit(entry)} title="Edit">
                        <i className="fas fa-pen"></i>
                      </button>
                      {deleteConfirm === entry.id ? (
                        <div className="acct-confirm-inline">
                          <button className="acct-btn-danger-sm" onClick={() => deleteMut.mutate(entry.id)}>Delete</button>
                          <button className="acct-btn-secondary-sm" onClick={() => setDeleteConfirm(null)}>Cancel</button>
                        </div>
                      ) : (
                        <button className="acct-btn-icon acct-btn-icon-danger" onClick={() => setDeleteConfirm(entry.id)} title="Delete">
                          <i className="fas fa-trash"></i>
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default RevenueLedgerPanel;
