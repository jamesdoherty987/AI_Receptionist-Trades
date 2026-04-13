import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { formatCurrency, formatDate } from '../../utils/helpers';
import { getMileageLogs, createMileageLog, updateMileageLog, deleteMileageLog } from '../../services/api';
import { useToast } from '../Toast';
import LoadingSpinner from '../LoadingSpinner';

const DEFAULT_RATE = 0.338; // Irish Revenue civil service rate per km
const EMPTY_FORM = { date: new Date().toISOString().split('T')[0], from_location: '', to_location: '', distance_km: '', notes: '', rate_per_km: DEFAULT_RATE, driver_name: '' };

function MileagePanel() {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [formData, setFormData] = useState({ ...EMPTY_FORM });

  const { data: logs = [], isLoading } = useQuery({
    queryKey: ['mileage'],
    queryFn: async () => (await getMileageLogs()).data,
    staleTime: 30000,
  });

  const createMut = useMutation({
    mutationFn: createMileageLog,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mileage'] });
      addToast('Trip logged', 'success');
      setFormData({ ...EMPTY_FORM });
      setShowForm(false);
    },
    onError: (e) => addToast(e.response?.data?.error || 'Failed to log trip', 'error'),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }) => updateMileageLog(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mileage'] });
      addToast('Trip updated', 'success');
      setFormData({ ...EMPTY_FORM });
      setShowForm(false);
      setEditingId(null);
    },
    onError: (e) => addToast(e.response?.data?.error || 'Failed to update trip', 'error'),
  });

  const deleteMut = useMutation({
    mutationFn: deleteMileageLog,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['mileage'] }); addToast('Trip deleted', 'success'); setDeleteConfirm(null); },
  });

  const stats = useMemo(() => {
    const totalKm = logs.reduce((s, l) => s + (l.distance_km || 0), 0);
    const totalCost = logs.reduce((s, l) => s + (l.cost || 0), 0);
    const thisMonth = logs.filter(l => {
      const d = new Date(l.date); const now = new Date();
      return d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear();
    });
    const monthKm = thisMonth.reduce((s, l) => s + (l.distance_km || 0), 0);
    const monthCost = thisMonth.reduce((s, l) => s + (l.cost || 0), 0);
    return { totalKm, totalCost, monthKm, monthCost, count: logs.length };
  }, [logs]);

  const estCost = (parseFloat(formData.distance_km) || 0) * (parseFloat(formData.rate_per_km) || DEFAULT_RATE);

  const startEdit = (log) => {
    setFormData({
      date: log.date?.split('T')[0] || '',
      from_location: log.from_location || '',
      to_location: log.to_location || '',
      distance_km: log.distance_km || '',
      rate_per_km: log.rate_per_km || DEFAULT_RATE,
      driver_name: log.driver_name || '',
      notes: log.notes || '',
    });
    setEditingId(log.id);
    setShowForm(true);
  };

  const cancelForm = () => {
    setShowForm(false);
    setEditingId(null);
    setFormData({ ...EMPTY_FORM });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!formData.distance_km) { addToast('Enter distance', 'warning'); return; }
    if (editingId) {
      updateMut.mutate({ id: editingId, data: formData });
    } else {
      createMut.mutate(formData);
    }
  };

  const isSaving = createMut.isPending || updateMut.isPending;

  if (isLoading) return <LoadingSpinner message="Loading mileage..." />;

  return (
    <div className="acct-panel">
      {/* Panel Header */}
      <div className="acct-panel-header">
        <h2 className="acct-panel-title"><i className="fas fa-car"></i> Mileage Tracker</h2>
        <button className="acct-btn-primary" onClick={() => { if (showForm) cancelForm(); else setShowForm(true); }}>
          <i className={`fas ${showForm ? 'fa-times' : 'fa-plus'}`}></i>
          {showForm ? 'Cancel' : 'Log Trip'}
        </button>
      </div>

      <div className="acct-stats-row">
        <div className="acct-stat-card">
          <div className="acct-stat-icon" style={{ background: 'rgba(59, 130, 246, 0.1)' }}>
            <i className="fas fa-car" style={{ color: '#3b82f6' }}></i>
          </div>
          <div className="acct-stat-content">
            <div className="acct-stat-value">{Math.round(stats.totalKm)} km</div>
            <div className="acct-stat-label">Total Distance</div>
          </div>
        </div>
        <div className="acct-stat-card">
          <div className="acct-stat-icon" style={{ background: 'rgba(16, 185, 129, 0.1)' }}>
            <i className="fas fa-euro-sign" style={{ color: '#10b981' }}></i>
          </div>
          <div className="acct-stat-content">
            <div className="acct-stat-value">{formatCurrency(stats.totalCost)}</div>
            <div className="acct-stat-label">Total Deduction</div>
          </div>
        </div>
        <div className="acct-stat-card">
          <div className="acct-stat-icon" style={{ background: 'rgba(245, 158, 11, 0.1)' }}>
            <i className="fas fa-calendar-day" style={{ color: '#f59e0b' }}></i>
          </div>
          <div className="acct-stat-content">
            <div className="acct-stat-value">{Math.round(stats.monthKm)} km</div>
            <div className="acct-stat-label">This Month</div>
          </div>
        </div>
        <div className="acct-stat-card">
          <div className="acct-stat-icon" style={{ background: 'rgba(99, 102, 241, 0.1)' }}>
            <i className="fas fa-route" style={{ color: '#6366f1' }}></i>
          </div>
          <div className="acct-stat-content">
            <div className="acct-stat-value">{stats.count}</div>
            <div className="acct-stat-label">Total Trips</div>
          </div>
        </div>
      </div>

      <div className="acct-toolbar">
        {logs.length > 0 && (
          <button className="acct-btn-secondary" style={{ marginLeft: 'auto', fontSize: '0.78rem' }}
            onClick={() => {
              const rows = [['Date', 'From', 'To', 'Distance (km)', 'Rate/km', 'Cost', 'Driver', 'Notes']];
              logs.forEach(l => rows.push([l.date, l.from_location || '', l.to_location || '', l.distance_km, l.rate_per_km, l.cost, l.driver_name || '', l.notes || '']));
              const csv = rows.map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n');
              const blob = new Blob([csv], { type: 'text/csv' });
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a'); a.href = url; a.download = `mileage-${new Date().toISOString().split('T')[0]}.csv`; a.click();
              URL.revokeObjectURL(url);
            }}>
            <i className="fas fa-download"></i> Export CSV
          </button>
        )}
      </div>

      {showForm && (
        <form className="acct-form" onSubmit={handleSubmit}>
          <div className="acct-form-grid">
            <div className="acct-field">
              <label>Date</label>
              <input type="date" value={formData.date} onChange={e => setFormData({ ...formData, date: e.target.value })} />
            </div>
            <div className="acct-field">
              <label>Distance (km) *</label>
              <input type="number" step="0.1" min="0" placeholder="0" required
                value={formData.distance_km} onChange={e => setFormData({ ...formData, distance_km: e.target.value })} />
            </div>
            <div className="acct-field">
              <label>From</label>
              <input type="text" placeholder="Starting location" value={formData.from_location}
                onChange={e => setFormData({ ...formData, from_location: e.target.value })} />
            </div>
            <div className="acct-field">
              <label>To</label>
              <input type="text" placeholder="Destination" value={formData.to_location}
                onChange={e => setFormData({ ...formData, to_location: e.target.value })} />
            </div>
            <div className="acct-field">
              <label>Driver</label>
              <input type="text" placeholder="Name of driver" value={formData.driver_name}
                onChange={e => setFormData({ ...formData, driver_name: e.target.value })} />
            </div>
            <div className="acct-field">
              <label>Rate (€/km)</label>
              <input type="number" step="0.001" min="0" value={formData.rate_per_km}
                onChange={e => setFormData({ ...formData, rate_per_km: e.target.value })} />
              <span className="acct-field-hint">Irish Revenue rate: €0.338/km</span>
            </div>
            <div className="acct-field">
              <label>Est. Deduction</label>
              <div style={{ padding: '0.5rem 0', fontSize: '1.1rem', fontWeight: 700, color: '#10b981' }}>{formatCurrency(estCost)}</div>
            </div>
            <div className="acct-field acct-field-wide">
              <label>Notes</label>
              <input type="text" placeholder="e.g. Job at 12 Main St" value={formData.notes}
                onChange={e => setFormData({ ...formData, notes: e.target.value })} />
            </div>
          </div>
          <div className="acct-form-actions">
            <button type="button" className="acct-btn-secondary" onClick={cancelForm}>Cancel</button>
            <button type="submit" className="acct-btn-primary" disabled={isSaving}>
              <i className={`fas ${isSaving ? 'fa-spinner fa-spin' : 'fa-check'}`}></i> {editingId ? 'Update Trip' : 'Log Trip'}
            </button>
          </div>
        </form>
      )}

      <div className="acct-list">
        {logs.length === 0 ? (
          <div className="acct-empty">
            <i className="fas fa-car"></i>
            <p>No trips logged yet. Log your business mileage for tax deductions.</p>
          </div>
        ) : logs.map(l => (
          <div key={l.id} className="acct-list-item">
            <div className="acct-list-icon" style={{ background: 'rgba(59, 130, 246, 0.1)', color: '#3b82f6' }}>
              <i className="fas fa-route"></i>
            </div>
            <div className="acct-list-content">
              <div className="acct-list-title">
                {l.from_location && l.to_location ? `${l.from_location} → ${l.to_location}` : l.from_location || l.to_location || 'Trip'}
              </div>
              <div className="acct-list-meta">
                <span><i className="fas fa-calendar"></i> {formatDate(l.date)}</span>
                <span><i className="fas fa-road"></i> {l.distance_km} km</span>
                {l.driver_name && <span><i className="fas fa-user"></i> {l.driver_name}</span>}
                {l.notes && <span><i className="fas fa-sticky-note"></i> {l.notes}</span>}
              </div>
            </div>
            <div className="acct-list-amount" style={{ color: '#10b981' }}>{formatCurrency(l.cost)}</div>
            {deleteConfirm === l.id ? (
              <div className="acct-confirm-inline">
                <button className="acct-btn-danger-sm" onClick={() => deleteMut.mutate(l.id)}>Delete</button>
                <button className="acct-btn-secondary-sm" onClick={() => setDeleteConfirm(null)}>Cancel</button>
              </div>
            ) : (
              <div style={{ display: 'flex', gap: '0.25rem' }}>
                <button className="acct-btn-icon" onClick={() => startEdit(l)} title="Edit trip"><i className="fas fa-pen"></i></button>
                <button className="acct-btn-icon acct-btn-icon-danger" onClick={() => setDeleteConfirm(l.id)} title="Delete trip"><i className="fas fa-trash"></i></button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default MileagePanel;
