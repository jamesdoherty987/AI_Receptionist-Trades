import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { formatCurrency, formatDate } from '../../utils/helpers';
import { getCreditNotes, createCreditNote, getClients } from '../../services/api';
import { useToast } from '../Toast';
import LoadingSpinner from '../LoadingSpinner';

function CreditNotesPanel() {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({ client_id: '', amount: '', reason: '', notes: '', booking_id: '', stripe_refund: false });

  const { data: notes = [], isLoading } = useQuery({
    queryKey: ['credit-notes'],
    queryFn: async () => (await getCreditNotes()).data,
    staleTime: 30000,
  });

  const { data: clients = [] } = useQuery({
    queryKey: ['clients'],
    queryFn: async () => (await getClients()).data,
    staleTime: 60000,
  });

  const createMut = useMutation({
    mutationFn: createCreditNote,
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['credit-notes'] });
      queryClient.invalidateQueries({ queryKey: ['finances'] });
      if (res.data?.stripe_refund_status === 'success') {
        addToast(`Credit note created and Stripe refund processed (${res.data.stripe_refund_id})`, 'success');
      } else if (res.data?.stripe_refund_error) {
        addToast(`Credit note created but Stripe refund failed: ${res.data.stripe_refund_error}`, 'warning');
      } else {
        addToast('Credit note created', 'success');
      }
      setFormData({ client_id: '', amount: '', reason: '', notes: '', booking_id: '', stripe_refund: false });
      setShowForm(false);
    },
    onError: (e) => addToast(e.response?.data?.error || 'Failed to create', 'error'),
  });

  const totalCredits = useMemo(() => notes.reduce((s, n) => s + (n.amount || 0), 0), [notes]);

  if (isLoading) return <LoadingSpinner message="Loading credit notes..." />;

  return (
    <div className="acct-panel">
      <div className="acct-stats-row">
        <div className="acct-stat-card">
          <div className="acct-stat-icon" style={{ background: 'rgba(239, 68, 68, 0.1)' }}>
            <i className="fas fa-undo" style={{ color: '#ef4444' }}></i>
          </div>
          <div className="acct-stat-content">
            <div className="acct-stat-value">{formatCurrency(totalCredits)}</div>
            <div className="acct-stat-label">Total Credits Issued</div>
          </div>
        </div>
        <div className="acct-stat-card">
          <div className="acct-stat-icon" style={{ background: 'rgba(99, 102, 241, 0.1)' }}>
            <i className="fas fa-file-alt" style={{ color: '#6366f1' }}></i>
          </div>
          <div className="acct-stat-content">
            <div className="acct-stat-value">{notes.length}</div>
            <div className="acct-stat-label">Credit Notes</div>
          </div>
        </div>
      </div>

      <div className="acct-toolbar">
        <button className="acct-btn-primary" onClick={() => setShowForm(!showForm)}>
          <i className={`fas ${showForm ? 'fa-times' : 'fa-plus'}`}></i>
          {showForm ? 'Cancel' : 'New Credit Note'}
        </button>
      </div>

      {showForm && (
        <form className="acct-form" onSubmit={e => {
          e.preventDefault();
          if (!formData.amount || parseFloat(formData.amount) <= 0) { addToast('Enter an amount', 'warning'); return; }
          createMut.mutate(formData);
        }}>
          <div className="acct-form-grid">
            <div className="acct-field">
              <label>Customer</label>
              <select value={formData.client_id} onChange={e => setFormData({ ...formData, client_id: e.target.value })}>
                <option value="">Select customer...</option>
                {clients.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
            <div className="acct-field">
              <label>Amount (€) *</label>
              <input type="number" step="0.01" min="0" placeholder="0.00" required
                value={formData.amount} onChange={e => setFormData({ ...formData, amount: e.target.value })} />
            </div>
            <div className="acct-field acct-field-wide">
              <label>Reason *</label>
              <input type="text" placeholder="e.g. Overcharged on invoice, partial refund..." required
                value={formData.reason} onChange={e => setFormData({ ...formData, reason: e.target.value })} />
            </div>
            <div className="acct-field acct-field-wide">
              <label>Notes</label>
              <input type="text" placeholder="Additional details..."
                value={formData.notes} onChange={e => setFormData({ ...formData, notes: e.target.value })} />
            </div>
            <div className="acct-field">
              <label className="acct-checkbox-label">
                <input type="checkbox" checked={formData.stripe_refund}
                  onChange={e => setFormData({ ...formData, stripe_refund: e.target.checked })} />
                Refund via Stripe
              </label>
              <span className="acct-field-hint">
                {formData.stripe_refund
                  ? 'Will process a card refund if the customer paid online'
                  : 'Accounting record only — refund cash/bank transfer separately'}
              </span>
            </div>
          </div>
          <div className="acct-form-actions">
            <button type="button" className="acct-btn-secondary" onClick={() => setShowForm(false)}>Cancel</button>
            <button type="submit" className="acct-btn-primary" disabled={createMut.isPending}>
              <i className={`fas ${createMut.isPending ? 'fa-spinner fa-spin' : 'fa-check'}`}></i> Create Credit Note
            </button>
          </div>
        </form>
      )}

      <div className="acct-list">
        {notes.length === 0 ? (
          <div className="acct-empty">
            <i className="fas fa-undo"></i>
            <p>No credit notes yet. Issue a credit note when you need to refund or credit a customer.</p>
          </div>
        ) : notes.map(n => (
          <div key={n.id} className="acct-list-item">
            <div className="acct-list-icon" style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444' }}>
              <i className="fas fa-undo"></i>
            </div>
            <div className="acct-list-content">
              <div className="acct-list-title">{n.credit_note_number} {n.client_name ? `— ${n.client_name}` : ''}</div>
              <div className="acct-list-meta">
                <span><i className="fas fa-calendar"></i> {formatDate(n.created_at)}</span>
                {n.reason && <span><i className="fas fa-comment"></i> {n.reason}</span>}
                {n.stripe_refund_id && <span className="acct-badge-green"><i className="fas fa-credit-card"></i> Stripe refund</span>}
              </div>
            </div>
            <div className="acct-list-amount" style={{ color: '#ef4444' }}>-{formatCurrency(n.amount)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default CreditNotesPanel;
