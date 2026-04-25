/**
 * WaitlistTab — Live waitlist management for walk-in guests.
 * Guests join the queue with party size and get SMS when their table is ready.
 */
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useToast } from '../Toast';
import {
  getWaitlist,
  addToWaitlist,
  updateWaitlistEntry,
  removeFromWaitlist,
  notifyWaitlistGuest,
} from '../../services/api';
import './WaitlistTab.css';

function WaitlistTab() {
  const { addToast } = useToast();
  const queryClient = useQueryClient();
  const [showAddForm, setShowAddForm] = useState(false);
  const [form, setForm] = useState({ name: '', phone: '', party_size: '2', notes: '' });

  const { data, isLoading } = useQuery({
    queryKey: ['waitlist'],
    queryFn: async () => {
      try { const r = await getWaitlist(); return r.data; }
      catch { return { entries: [] }; }
    },
    refetchInterval: 30000,
  });

  const entries = data?.entries || [];
  const waiting = entries.filter(e => e.status === 'waiting');
  const seated = entries.filter(e => e.status === 'seated');
  const noShow = entries.filter(e => e.status === 'no_show');

  const addMutation = useMutation({
    mutationFn: (data) => addToWaitlist(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['waitlist'] });
      addToast('Guest added to waitlist', 'success');
      setShowAddForm(false);
      setForm({ name: '', phone: '', party_size: '2', notes: '' });
    },
    onError: () => addToast('Failed to add guest', 'error'),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, status }) => updateWaitlistEntry(id, status),
    onSuccess: (_, { status }) => {
      queryClient.invalidateQueries({ queryKey: ['waitlist'] });
      addToast(status === 'seated' ? 'Guest seated!' : 'Status updated', 'success');
    },
    onError: () => addToast('Failed to update', 'error'),
  });

  const removeMutation = useMutation({
    mutationFn: (id) => removeFromWaitlist(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['waitlist'] });
      addToast('Removed from waitlist', 'success');
    },
  });

  const notifyMutation = useMutation({
    mutationFn: (id) => notifyWaitlistGuest(id),
    onSuccess: () => addToast('SMS notification sent', 'success'),
    onError: () => addToast('Failed to send notification', 'error'),
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!form.name.trim()) return;
    addMutation.mutate({
      name: form.name,
      phone: form.phone,
      party_size: parseInt(form.party_size) || 2,
      notes: form.notes,
    });
  };

  const getWaitTime = (createdAt) => {
    if (!createdAt) return '';
    const mins = Math.floor((Date.now() - new Date(createdAt)) / 60000);
    if (mins < 1) return 'Just now';
    if (mins < 60) return `${mins}m`;
    return `${Math.floor(mins / 60)}h ${mins % 60}m`;
  };

  if (isLoading) return <div className="wl-loading"><div className="wl-spinner"></div></div>;

  return (
    <div className="waitlist-tab">
      <div className="wl-header">
        <div>
          <h2><i className="fas fa-users"></i> Waitlist</h2>
          <p className="wl-subtitle">{waiting.length} waiting · {seated.length} seated today</p>
        </div>
        <button className="btn-primary btn-sm" onClick={() => setShowAddForm(!showAddForm)}>
          <i className="fas fa-plus"></i> Add Guest
        </button>
      </div>

      {showAddForm && (
        <form className="wl-add-form" onSubmit={handleSubmit}>
          <div className="wl-form-row">
            <input type="text" placeholder="Guest name *" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required />
            <input type="tel" placeholder="Phone (for SMS)" value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} />
            <div className="wl-party-input">
              <i className="fas fa-users"></i>
              <input type="number" min="1" max="20" value={form.party_size} onChange={e => setForm({ ...form, party_size: e.target.value })} />
            </div>
          </div>
          <div className="wl-form-row">
            <input type="text" placeholder="Notes (e.g., high chair needed)" value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} style={{ flex: 1 }} />
            <button type="submit" className="btn-primary btn-sm" disabled={addMutation.isPending}>
              {addMutation.isPending ? 'Adding...' : 'Add'}
            </button>
            <button type="button" className="btn-secondary btn-sm" onClick={() => setShowAddForm(false)}>Cancel</button>
          </div>
        </form>
      )}

      {waiting.length === 0 && !showAddForm ? (
        <div className="wl-empty">
          <i className="fas fa-couch"></i>
          <h4>No one waiting</h4>
          <p>Add walk-in guests to the waitlist. They'll get an SMS when their table is ready.</p>
        </div>
      ) : waiting.length > 0 && (
        <div className="wl-list">
          {waiting.map((entry, idx) => (
            <div key={entry.id} className="wl-card">
              <div className="wl-card-pos">{idx + 1}</div>
              <div className="wl-card-info">
                <span className="wl-card-name">{entry.name}</span>
                <div className="wl-card-meta">
                  <span><i className="fas fa-users"></i> {entry.party_size}</span>
                  <span><i className="fas fa-clock"></i> {getWaitTime(entry.created_at)}</span>
                  {entry.notes && <span className="wl-card-note"><i className="fas fa-sticky-note"></i> {entry.notes}</span>}
                </div>
              </div>
              <div className="wl-card-actions">
                {entry.phone && (
                  <button className="wl-action-btn notify" onClick={() => notifyMutation.mutate(entry.id)} title="Send SMS: table ready" disabled={notifyMutation.isPending}>
                    <i className="fas fa-bell"></i>
                  </button>
                )}
                <button className="wl-action-btn seat" onClick={() => updateMutation.mutate({ id: entry.id, status: 'seated' })} title="Seat guest">
                  <i className="fas fa-chair"></i>
                </button>
                <button className="wl-action-btn remove" onClick={() => removeMutation.mutate(entry.id)} title="Remove">
                  <i className="fas fa-times"></i>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Today's history */}
      {(seated.length > 0 || noShow.length > 0) && (
        <div className="wl-history">
          <h4>Today's Activity</h4>
          <div className="wl-history-list">
            {[...seated, ...noShow].map(entry => (
              <div key={entry.id} className={`wl-history-item ${entry.status}`}>
                <span className="wl-history-name">{entry.name}</span>
                <span className="wl-history-party"><i className="fas fa-users"></i> {entry.party_size}</span>
                <span className={`wl-history-badge ${entry.status}`}>
                  {entry.status === 'seated' ? 'Seated' : 'No Show'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default WaitlistTab;
