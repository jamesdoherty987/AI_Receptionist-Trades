import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { formatCurrency, formatDate } from '../../utils/helpers';
import { getCreditNotes, createCreditNote, getClients, getBookings, processStripeRefund } from '../../services/api';
import { useToast } from '../Toast';
import { invalidateRelated } from '../../utils/queryInvalidation';
import LoadingSpinner from '../LoadingSpinner';

const REFUND_METHOD_OPTIONS = [
  { value: 'record_only', label: 'Record Only', desc: 'Accounting record — refund cash/bank transfer separately', icon: 'fa-file-alt' },
  { value: 'stripe', label: 'Stripe Refund', desc: 'Process card refund via Stripe (customer must have paid online)', icon: 'fa-credit-card' },
];

function CreditNotesPanel() {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    client_id: '', amount: '', reason: '', notes: '', booking_id: '', refund_method: 'record_only'
  });

  const { data: notes = [], isLoading } = useQuery({
    queryKey: ['credit-notes'],
    queryFn: async () => (await getCreditNotes()).data,
  });

  const { data: clients = [] } = useQuery({
    queryKey: ['clients'],
    queryFn: async () => (await getClients()).data,
    staleTime: 60000,
  });

  // Fetch bookings to let user pick which job to refund
  const { data: bookings = [] } = useQuery({
    queryKey: ['bookings'],
    queryFn: async () => (await getBookings()).data,
    enabled: showForm,
  });

  // Filter bookings for selected client that were paid
  const clientBookings = useMemo(() => {
    if (!formData.client_id) return [];
    return (Array.isArray(bookings) ? bookings : []).filter(b =>
      String(b.client_id) === String(formData.client_id) &&
      (b.status === 'completed' || b.payment_status === 'paid')
    ).sort((a, b) => new Date(b.appointment_time || 0) - new Date(a.appointment_time || 0));
  }, [bookings, formData.client_id]);

  // Check if selected booking has Stripe payment
  const selectedBooking = useMemo(() => {
    if (!formData.booking_id) return null;
    return (Array.isArray(bookings) ? bookings : []).find(b => String(b.id) === String(formData.booking_id));
  }, [bookings, formData.booking_id]);

  const hasStripePayment = selectedBooking?.stripe_checkout_session_id || selectedBooking?.payment_method === 'stripe';

  const createMut = useMutation({
    mutationFn: (data) => createCreditNote({
      ...data,
      stripe_refund: data.refund_method === 'stripe',
    }),
    onSuccess: (res) => {
      invalidateRelated(queryClient, 'creditNotes');
      if (res.data?.stripe_refund_status === 'success') {
        addToast(`Credit note created and €${parseFloat(formData.amount).toFixed(2)} refunded to card (${res.data.stripe_refund_id})`, 'success');
      } else if (res.data?.stripe_refund_error) {
        addToast(`Credit note created but Stripe refund failed: ${res.data.stripe_refund_error}. You can retry from the list.`, 'warning');
      } else {
        addToast('Credit note created', 'success');
      }
      setFormData({ client_id: '', amount: '', reason: '', notes: '', booking_id: '', refund_method: 'record_only' });
      setShowForm(false);
    },
    onError: (e) => addToast(e.response?.data?.error || 'Failed to create', 'error'),
  });

  // Mutation to process Stripe refund on an existing credit note
  const refundMut = useMutation({
    mutationFn: (creditNoteId) => processStripeRefund(creditNoteId),
    onSuccess: (res) => {
      invalidateRelated(queryClient, 'creditNotes');
      if (res.data?.stripe_refund_status === 'success') {
        addToast(`Stripe refund processed (${res.data.stripe_refund_id})`, 'success');
      } else {
        addToast(res.data?.stripe_refund_error || 'Refund failed', 'error');
      }
    },
    onError: (e) => addToast(e.response?.data?.error || 'Failed to process refund', 'error'),
  });

  const totalCredits = useMemo(() => notes.reduce((s, n) => s + (n.amount || 0), 0), [notes]);
  const stripeRefunded = useMemo(() => notes.filter(n => n.stripe_refund_id).reduce((s, n) => s + (n.amount || 0), 0), [notes]);

  if (isLoading) return <LoadingSpinner message="Loading credit notes..." />;

  return (
    <div className="acct-panel">
      {/* Panel Header */}
      <div className="acct-panel-header">
        <h2 className="acct-panel-title"><i className="fas fa-undo"></i> Credit Notes</h2>
        <button className="acct-btn-primary" onClick={() => setShowForm(!showForm)}>
          <i className={`fas ${showForm ? 'fa-times' : 'fa-plus'}`}></i>
          {showForm ? 'Cancel' : 'New Credit Note'}
        </button>
      </div>

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
        {stripeRefunded > 0 && (
          <div className="acct-stat-card">
            <div className="acct-stat-icon" style={{ background: 'rgba(99, 102, 241, 0.1)' }}>
              <i className="fas fa-credit-card" style={{ color: '#6366f1' }}></i>
            </div>
            <div className="acct-stat-content">
              <div className="acct-stat-value">{formatCurrency(stripeRefunded)}</div>
              <div className="acct-stat-label">Refunded via Stripe</div>
            </div>
          </div>
        )}
        <div className="acct-stat-card">
          <div className="acct-stat-icon" style={{ background: 'rgba(148, 163, 184, 0.1)' }}>
            <i className="fas fa-file-alt" style={{ color: '#94a3b8' }}></i>
          </div>
          <div className="acct-stat-content">
            <div className="acct-stat-value">{notes.length}</div>
            <div className="acct-stat-label">Credit Notes</div>
          </div>
        </div>
      </div>

      {showForm && (
        <form className="acct-form" onSubmit={e => {
          e.preventDefault();
          if (!formData.amount || parseFloat(formData.amount) <= 0) { addToast('Enter an amount', 'warning'); return; }
          if (!formData.reason.trim()) { addToast('Please enter a reason', 'warning'); return; }
          if (formData.refund_method === 'stripe' && !formData.booking_id) {
            addToast('Select a job to refund via Stripe', 'warning'); return;
          }
          if (formData.refund_method === 'stripe' && !hasStripePayment) {
            addToast('Selected job was not paid via Stripe. Use "Record Only" instead, or select a different job.', 'warning'); return;
          }
          createMut.mutate(formData);
        }}>
          <div className="acct-form-grid">
            <div className="acct-field">
              <label>Customer *</label>
              <select value={formData.client_id} required onChange={e => setFormData({ ...formData, client_id: e.target.value, booking_id: '' })}>
                <option value="">Select customer...</option>
                {clients.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
            <div className="acct-field">
              <label>Amount (€) *</label>
              <input type="number" step="0.01" min="0" placeholder="0.00" required
                value={formData.amount} onChange={e => setFormData({ ...formData, amount: e.target.value })} />
            </div>

            {/* Job selector — needed for Stripe refund, optional otherwise */}
            {formData.client_id && (
              <div className="acct-field">
                <label>Related Job {formData.refund_method === 'stripe' ? '*' : '(optional)'}</label>
                <select value={formData.booking_id} onChange={e => setFormData({ ...formData, booking_id: e.target.value })}
                  required={formData.refund_method === 'stripe'}>
                  <option value="">Select a job...</option>
                  {clientBookings.map(b => (
                    <option key={b.id} value={b.id}>
                      {b.service_type || 'Job'} — {formatDate(b.appointment_time)} — {formatCurrency(b.charge || b.estimated_charge || 0)}
                      {b.stripe_checkout_session_id ? ' (Stripe)' : ''}
                    </option>
                  ))}
                </select>
                {clientBookings.length === 0 && (
                  <span className="acct-field-hint">No completed/paid jobs found for this customer</span>
                )}
              </div>
            )}

            <div className="acct-field acct-field-wide">
              <label>Reason *</label>
              <input type="text" placeholder="e.g. Overcharged on invoice, partial refund, service not completed..." required
                value={formData.reason} onChange={e => setFormData({ ...formData, reason: e.target.value })} />
            </div>

            {/* Refund Method */}
            <div className="acct-field acct-field-wide">
              <label>Refund Method</label>
              <div className="credit-refund-methods">
                {REFUND_METHOD_OPTIONS.map(opt => (
                  <button key={opt.value} type="button"
                    className={`credit-refund-option ${formData.refund_method === opt.value ? 'active' : ''} ${opt.value === 'stripe' && !hasStripePayment && formData.booking_id ? 'disabled' : ''}`}
                    onClick={() => {
                      if (opt.value === 'stripe' && !formData.booking_id) {
                        addToast('Select a job first to enable Stripe refund', 'info');
                        return;
                      }
                      if (opt.value === 'stripe' && formData.booking_id && !hasStripePayment) {
                        addToast('This job was not paid via Stripe — card refund not available', 'warning');
                        return;
                      }
                      setFormData({ ...formData, refund_method: opt.value });
                    }}>
                    <i className={`fas ${opt.icon}`}></i>
                    <div>
                      <div className="credit-refund-label">{opt.label}</div>
                      <div className="credit-refund-desc">{opt.desc}</div>
                    </div>
                  </button>
                ))}
              </div>
              {formData.refund_method === 'stripe' && formData.booking_id && hasStripePayment && (
                <div className="credit-stripe-ready">
                  <i className="fas fa-check-circle"></i> Stripe payment found — refund will be processed to the customer's card
                </div>
              )}
              {formData.refund_method === 'stripe' && formData.booking_id && !hasStripePayment && (
                <div className="credit-stripe-warning">
                  <i className="fas fa-exclamation-triangle"></i> This job was not paid via Stripe. Select a Stripe-paid job or use "Record Only".
                </div>
              )}
            </div>

            <div className="acct-field acct-field-wide">
              <label>Notes</label>
              <input type="text" placeholder="Additional details..."
                value={formData.notes} onChange={e => setFormData({ ...formData, notes: e.target.value })} />
            </div>
          </div>
          <div className="acct-form-actions">
            <button type="button" className="acct-btn-secondary" onClick={() => setShowForm(false)}>Cancel</button>
            <button type="submit" className="acct-btn-primary" disabled={createMut.isPending}>
              <i className={`fas ${createMut.isPending ? 'fa-spinner fa-spin' : formData.refund_method === 'stripe' ? 'fa-credit-card' : 'fa-check'}`}></i>
              {formData.refund_method === 'stripe' ? 'Create & Refund' : 'Create Credit Note'}
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
                {n.stripe_refund_id ? (
                  <span className="acct-badge-green"><i className="fas fa-credit-card" style={{ marginRight: 3 }}></i> Refunded via Stripe</span>
                ) : n.booking_id ? (
                  <span className="acct-badge" style={{ background: '#fffbeb', color: '#b45309' }}>
                    <i className="fas fa-file-alt" style={{ marginRight: 3 }}></i> Record only
                  </span>
                ) : (
                  <span className="acct-badge" style={{ background: '#f1f5f9', color: '#64748b' }}>
                    <i className="fas fa-file-alt" style={{ marginRight: 3 }}></i> Manual
                  </span>
                )}
              </div>
            </div>
            <div className="acct-list-amount" style={{ color: '#ef4444' }}>-{formatCurrency(n.amount)}</div>
            <div className="acct-list-actions">
              {/* Show "Send Refund" button if there's a booking but no Stripe refund yet */}
              {n.booking_id && !n.stripe_refund_id && (
                <button className="quote-action-btn quote-action-send"
                  title="Process Stripe refund for this credit note"
                  onClick={() => refundMut.mutate(n.id)}
                  disabled={refundMut.isPending}>
                  <i className={`fas ${refundMut.isPending ? 'fa-spinner fa-spin' : 'fa-credit-card'}`}></i>
                  <span>Send Refund</span>
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default CreditNotesPanel;
