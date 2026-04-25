import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { formatCurrency, formatDate } from '../../utils/helpers';
import { getExpenses, createExpense, updateExpense, deleteExpense } from '../../services/api';
import { useToast } from '../Toast';
import LoadingSpinner from '../LoadingSpinner';

const EXPENSE_CATEGORIES = [
  { value: 'fuel', label: 'Fuel & Mileage', icon: 'fa-gas-pump', color: '#f59e0b' },
  { value: 'tools', label: 'Tools & Equipment', icon: 'fa-wrench', color: '#6366f1' },
  { value: 'materials', label: 'Materials & Supplies', icon: 'fa-cubes', color: '#8b5cf6' },
  { value: 'vehicle', label: 'Vehicle Maintenance', icon: 'fa-car', color: '#3b82f6' },
  { value: 'insurance', label: 'Insurance', icon: 'fa-shield-halved', color: '#10b981' },
  { value: 'software', label: 'Software & Subscriptions', icon: 'fa-laptop', color: '#0ea5e9' },
  { value: 'office', label: 'Office & Admin', icon: 'fa-building', color: '#64748b' },
  { value: 'marketing', label: 'Marketing & Advertising', icon: 'fa-bullhorn', color: '#ec4899' },
  { value: 'training', label: 'Training & Certifications', icon: 'fa-graduation-cap', color: '#14b8a6' },
  { value: 'utilities', label: 'Utilities & Rent', icon: 'fa-bolt', color: '#eab308' },
  { value: 'subcontractor', label: 'Subcontractors', icon: 'fa-people-carry-box', color: '#f97316' },
  { value: 'other', label: 'Other', icon: 'fa-ellipsis', color: '#94a3b8' },
];

const getCategoryInfo = (val) => EXPENSE_CATEGORIES.find(c => c.value === val) || EXPENSE_CATEGORIES[EXPENSE_CATEGORIES.length - 1];

function ExpensesPanel() {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [filterCategory, setFilterCategory] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [formData, setFormData] = useState({
    amount: '', category: 'fuel', description: '', vendor: '',
    date: new Date().toISOString().split('T')[0], tax_deductible: true, notes: '',
    is_recurring: false, recurring_frequency: 'monthly'
  });

  const { data: expenses = [], isLoading } = useQuery({
    queryKey: ['expenses'],
    queryFn: async () => (await getExpenses()).data,
  });

  const createMut = useMutation({
    mutationFn: createExpense,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expenses'] });
      queryClient.invalidateQueries({ queryKey: ['pnl-report'] });
      queryClient.invalidateQueries({ queryKey: ['finances'] });
      addToast('Expense added', 'success');
      resetForm();
    },
    onError: (e) => addToast(e.response?.data?.error || 'Failed to add expense', 'error'),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }) => updateExpense(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expenses'] });
      queryClient.invalidateQueries({ queryKey: ['pnl-report'] });
      queryClient.invalidateQueries({ queryKey: ['finances'] });
      addToast('Expense updated', 'success');
      resetForm();
    },
    onError: (e) => addToast(e.response?.data?.error || 'Failed to update', 'error'),
  });

  const deleteMut = useMutation({
    mutationFn: deleteExpense,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expenses'] });
      queryClient.invalidateQueries({ queryKey: ['pnl-report'] });
      queryClient.invalidateQueries({ queryKey: ['finances'] });
      addToast('Expense deleted', 'success');
      setDeleteConfirm(null);
    },
    onError: (e) => addToast(e.response?.data?.error || 'Failed to delete', 'error'),
  });

  const resetForm = () => {
    setFormData({ amount: '', category: 'fuel', description: '', vendor: '',
      date: new Date().toISOString().split('T')[0], tax_deductible: true, notes: '',
      is_recurring: false, recurring_frequency: 'monthly' });
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

  const startEdit = (exp) => {
    setFormData({
      amount: exp.amount, category: exp.category, description: exp.description || '',
      vendor: exp.vendor || '', date: exp.date?.split('T')[0] || '',
      tax_deductible: exp.tax_deductible !== false, notes: exp.notes || '',
      is_recurring: exp.is_recurring || false, recurring_frequency: exp.recurring_frequency || 'monthly'
    });
    setEditingId(exp.id);
    setShowForm(true);
  };

  // Stats
  const stats = useMemo(() => {
    const total = expenses.reduce((s, e) => s + (e.amount || 0), 0);
    const thisMonth = expenses.filter(e => {
      const d = new Date(e.date);
      const now = new Date();
      return d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear();
    }).reduce((s, e) => s + (e.amount || 0), 0);
    const byCategory = {};
    expenses.forEach(e => {
      byCategory[e.category] = (byCategory[e.category] || 0) + (e.amount || 0);
    });
    const topCategory = Object.entries(byCategory).sort((a, b) => b[1] - a[1])[0];
    return { total, thisMonth, topCategory, byCategory };
  }, [expenses]);

  const filtered = useMemo(() => {
    let list = expenses;
    if (filterCategory !== 'all') list = list.filter(e => e.category === filterCategory);
    if (searchTerm) {
      const q = searchTerm.toLowerCase();
      list = list.filter(e =>
        (e.description || '').toLowerCase().includes(q) ||
        (e.vendor || '').toLowerCase().includes(q) ||
        (e.category || '').toLowerCase().includes(q)
      );
    }
    return list;
  }, [expenses, filterCategory, searchTerm]);

  // Group filtered expenses by month
  const groupedByMonth = useMemo(() => {
    const groups = {};
    filtered.forEach(e => {
      const d = new Date(e.date);
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
      const label = d.toLocaleDateString('en-IE', { month: 'long', year: 'numeric' });
      if (!groups[key]) groups[key] = { key, label, items: [], total: 0 };
      groups[key].items.push(e);
      groups[key].total += (e.amount || 0);
    });
    return Object.values(groups).sort((a, b) => b.key.localeCompare(a.key));
  }, [filtered]);

  if (isLoading) return <LoadingSpinner message="Loading expenses..." />;

  return (
    <div className="acct-panel">
      {/* Panel Header */}
      <div className="acct-panel-header">
        <h2 className="acct-panel-title"><i className="fas fa-receipt"></i> Expenses</h2>
        <button className="acct-btn-primary" onClick={() => { resetForm(); setShowForm(!showForm); }}>
          <i className={`fas ${showForm ? 'fa-times' : 'fa-plus'}`}></i>
          {showForm ? 'Cancel' : 'Add Expense'}
        </button>
      </div>

      {/* Stats Row */}
      <div className="acct-stats-row">
        <div className="acct-stat-card">
          <div className="acct-stat-icon" style={{ background: 'rgba(239, 68, 68, 0.1)' }}>
            <i className="fas fa-receipt" style={{ color: '#ef4444' }}></i>
          </div>
          <div className="acct-stat-content">
            <div className="acct-stat-value">{formatCurrency(stats.total)}</div>
            <div className="acct-stat-label">Total Expenses</div>
          </div>
        </div>
        <div className="acct-stat-card">
          <div className="acct-stat-icon" style={{ background: 'rgba(245, 158, 11, 0.1)' }}>
            <i className="fas fa-calendar-day" style={{ color: '#f59e0b' }}></i>
          </div>
          <div className="acct-stat-content">
            <div className="acct-stat-value">{formatCurrency(stats.thisMonth)}</div>
            <div className="acct-stat-label">This Month</div>
          </div>
        </div>
        <div className="acct-stat-card">
          <div className="acct-stat-icon" style={{ background: 'rgba(99, 102, 241, 0.1)' }}>
            <i className="fas fa-list-ol" style={{ color: '#6366f1' }}></i>
          </div>
          <div className="acct-stat-content">
            <div className="acct-stat-value">{expenses.length}</div>
            <div className="acct-stat-label">Total Entries</div>
          </div>
        </div>
        {stats.topCategory && (
          <div className="acct-stat-card">
            <div className="acct-stat-icon" style={{ background: `${getCategoryInfo(stats.topCategory[0]).color}18` }}>
              <i className={`fas ${getCategoryInfo(stats.topCategory[0]).icon}`} style={{ color: getCategoryInfo(stats.topCategory[0]).color }}></i>
            </div>
            <div className="acct-stat-content">
              <div className="acct-stat-value">{formatCurrency(stats.topCategory[1])}</div>
              <div className="acct-stat-label">Top: {getCategoryInfo(stats.topCategory[0]).label}</div>
            </div>
          </div>
        )}
      </div>

      {/* Category Breakdown Bar */}
      {Object.keys(stats.byCategory).length > 0 && (
        <div className="acct-section">
          <div className="acct-section-header"><h3><i className="fas fa-chart-bar"></i> Spending by Category</h3></div>
          <div className="acct-category-bars">
            {Object.entries(stats.byCategory).sort((a, b) => b[1] - a[1]).slice(0, 6).map(([cat, amt]) => {
              const info = getCategoryInfo(cat);
              const pct = stats.total > 0 ? (amt / stats.total) * 100 : 0;
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
        <select className="acct-select" value={filterCategory} onChange={e => setFilterCategory(e.target.value)}>
          <option value="all">All Categories</option>
          {EXPENSE_CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
        </select>
        <div className="acct-search" style={{ flex: 1 }}>
          <i className="fas fa-search"></i>
          <input type="text" placeholder="Search expenses..." value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)} />
        </div>
        {expenses.length > 0 && (
          <button className="acct-btn-secondary" title="Export CSV" style={{ padding: '0.4rem 0.6rem' }}
            onClick={() => {
              const rows = [['Date', 'Category', 'Description', 'Vendor', 'Amount', 'Tax Deductible', 'Recurring']];
              filtered.forEach(e => rows.push([e.date, e.category, e.description || '', e.vendor || '', e.amount, e.tax_deductible ? 'Yes' : 'No', e.is_recurring ? e.recurring_frequency : 'No']));
              const csv = rows.map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n');
              const blob = new Blob([csv], { type: 'text/csv' });
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a'); a.href = url; a.download = `expenses-${new Date().toISOString().split('T')[0]}.csv`; a.click();
              URL.revokeObjectURL(url);
              addToast('Expenses exported', 'success');
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
                {EXPENSE_CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
              </select>
            </div>
            <div className="acct-field">
              <label>Date</label>
              <input type="date" value={formData.date} onChange={e => setFormData({ ...formData, date: e.target.value })} />
            </div>
            <div className="acct-field">
              <label>Vendor / Supplier</label>
              <input type="text" placeholder="e.g. Screwfix, Shell..." value={formData.vendor}
                onChange={e => setFormData({ ...formData, vendor: e.target.value })} />
            </div>
            <div className="acct-field acct-field-wide">
              <label>Description</label>
              <input type="text" placeholder="What was this expense for?" value={formData.description}
                onChange={e => setFormData({ ...formData, description: e.target.value })} />
            </div>
            <div className="acct-field">
              <label className="acct-checkbox-label">
                <input type="checkbox" checked={formData.tax_deductible}
                  onChange={e => setFormData({ ...formData, tax_deductible: e.target.checked })} />
                Tax Deductible
              </label>
            </div>
            <div className="acct-field">
              <label className="acct-checkbox-label">
                <input type="checkbox" checked={formData.is_recurring}
                  onChange={e => setFormData({ ...formData, is_recurring: e.target.checked })} />
                Recurring Expense
              </label>
            </div>
            {formData.is_recurring && (
              <div className="acct-field">
                <label>Frequency</label>
                <select value={formData.recurring_frequency} onChange={e => setFormData({ ...formData, recurring_frequency: e.target.value })}>
                  <option value="weekly">Weekly</option>
                  <option value="monthly">Monthly</option>
                  <option value="quarterly">Quarterly</option>
                  <option value="yearly">Yearly</option>
                </select>
              </div>
            )}
          </div>
          <div className="acct-form-actions">
            <button type="button" className="acct-btn-secondary" onClick={resetForm}>Cancel</button>
            <button type="submit" className="acct-btn-primary" disabled={createMut.isPending || updateMut.isPending}>
              <i className={`fas ${createMut.isPending || updateMut.isPending ? 'fa-spinner fa-spin' : 'fa-check'}`}></i>
              {editingId ? 'Update' : 'Add Expense'}
            </button>
          </div>
        </form>
      )}

      {/* Expenses List */}
      <div className="acct-list">
        {filtered.length === 0 ? (
          <div className="acct-empty">
            <i className="fas fa-receipt"></i>
            <p>{expenses.length === 0 ? 'No expenses recorded yet. Add your first expense above.' : 'No expenses match your filters.'}</p>
          </div>
        ) : (
          groupedByMonth.map(group => (
            <div key={group.key}>
              <div className="acct-month-header">
                <span className="acct-month-label">{group.label}</span>
                <span className="acct-month-total">{formatCurrency(group.total)}</span>
              </div>
              {group.items.map(exp => {
            const info = getCategoryInfo(exp.category);
            return (
              <div key={exp.id} className="acct-list-item">
                <div className="acct-list-icon" style={{ background: `${info.color}15`, color: info.color }}>
                  <i className={`fas ${info.icon}`}></i>
                </div>
                <div className="acct-list-content">
                  <div className="acct-list-title">{exp.description || info.label}</div>
                  <div className="acct-list-meta">
                    {exp.vendor && <span><i className="fas fa-store"></i> {exp.vendor}</span>}
                    <span><i className="fas fa-calendar"></i> {formatDate(exp.date)}</span>
                    {exp.tax_deductible && <span className="acct-badge-green">Tax Deductible</span>}
                    {exp.is_recurring && <span className="acct-badge" style={{ background: '#eff6ff', color: '#3b82f6' }}><i className="fas fa-redo"></i> {exp.recurring_frequency || 'Recurring'}</span>}
                  </div>
                </div>
                <div className="acct-list-amount" style={{ color: '#ef4444' }}>-{formatCurrency(exp.amount)}</div>
                <div className="acct-list-actions">
                  <button className="acct-btn-icon" onClick={() => startEdit(exp)} title="Edit">
                    <i className="fas fa-pen"></i>
                  </button>
                  {deleteConfirm === exp.id ? (
                    <div className="acct-confirm-inline">
                      <button className="acct-btn-danger-sm" onClick={() => deleteMut.mutate(exp.id)}>Delete</button>
                      <button className="acct-btn-secondary-sm" onClick={() => setDeleteConfirm(null)}>Cancel</button>
                    </div>
                  ) : (
                    <button className="acct-btn-icon acct-btn-icon-danger" onClick={() => setDeleteConfirm(exp.id)} title="Delete">
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

export default ExpensesPanel;
