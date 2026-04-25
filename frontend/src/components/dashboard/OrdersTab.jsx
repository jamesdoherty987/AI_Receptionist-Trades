/**
 * OrdersTab — Online ordering / takeaway management for restaurants.
 * Shows incoming orders, order status tracking, and takeaway/delivery toggle.
 */
import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useToast } from '../Toast';
import {
  getOnlineOrders,
  updateOrderStatus,
  toggleOnlineOrdering,
  getOnlineOrderingSettings,
  updateOnlineOrderingSettings,
} from '../../services/api';
import './OrdersTab.css';

const ORDER_STATUSES = [
  { key: 'new', label: 'New', icon: 'fa-bell', color: '#3b82f6' },
  { key: 'preparing', label: 'Preparing', icon: 'fa-fire', color: '#f59e0b' },
  { key: 'ready', label: 'Ready', icon: 'fa-check-circle', color: '#10b981' },
  { key: 'collected', label: 'Collected', icon: 'fa-shopping-bag', color: '#8b5cf6' },
  { key: 'cancelled', label: 'Cancelled', icon: 'fa-times-circle', color: '#ef4444' },
];

function OrdersTab() {
  const { addToast } = useToast();
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState('active');
  const [showSettings, setShowSettings] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ['online-orders'],
    queryFn: async () => {
      try { const r = await getOnlineOrders(); return r.data; }
      catch { return { orders: [], settings: { enabled: false } }; }
    },
    refetchInterval: 15000,
  });

  const { data: settingsData } = useQuery({
    queryKey: ['online-ordering-settings'],
    queryFn: async () => {
      try { const r = await getOnlineOrderingSettings(); return r.data; }
      catch { return { enabled: false, takeaway: true, delivery: false, min_order: 0, prep_time_mins: 20 }; }
    },
  });

  const orders = data?.orders || [];
  const settings = settingsData || { enabled: false, takeaway: true, delivery: false };

  const statusMutation = useMutation({
    mutationFn: ({ id, status }) => updateOrderStatus(id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['online-orders'] });
      addToast('Order updated', 'success');
    },
    onError: () => addToast('Failed to update order', 'error'),
  });

  const toggleMutation = useMutation({
    mutationFn: (enabled) => toggleOnlineOrdering(enabled),
    onSuccess: (_, enabled) => {
      queryClient.invalidateQueries({ queryKey: ['online-ordering-settings'] });
      addToast(enabled ? 'Online ordering enabled' : 'Online ordering paused', 'success');
    },
  });

  const settingsMutation = useMutation({
    mutationFn: (data) => updateOnlineOrderingSettings(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['online-ordering-settings'] });
      addToast('Settings saved', 'success');
      setShowSettings(false);
    },
  });

  const filtered = useMemo(() => {
    if (statusFilter === 'active') return orders.filter(o => !['collected', 'cancelled'].includes(o.status));
    if (statusFilter === 'all') return orders;
    return orders.filter(o => o.status === statusFilter);
  }, [orders, statusFilter]);

  const stats = useMemo(() => {
    const newOrders = orders.filter(o => o.status === 'new').length;
    const preparing = orders.filter(o => o.status === 'preparing').length;
    const ready = orders.filter(o => o.status === 'ready').length;
    const todayRevenue = orders
      .filter(o => o.status !== 'cancelled' && o.created_at && new Date(o.created_at).toDateString() === new Date().toDateString())
      .reduce((s, o) => s + (parseFloat(o.total) || 0), 0);
    return { newOrders, preparing, ready, todayRevenue };
  }, [orders]);

  const getNextStatus = (current) => {
    const flow = ['new', 'preparing', 'ready', 'collected'];
    const idx = flow.indexOf(current);
    return idx >= 0 && idx < flow.length - 1 ? flow[idx + 1] : null;
  };

  const formatTime = (dateStr) => {
    if (!dateStr) return '';
    return new Date(dateStr).toLocaleTimeString('en-IE', { hour: '2-digit', minute: '2-digit' });
  };

  if (isLoading) return <div className="ord-loading"><div className="ord-spinner"></div></div>;

  return (
    <div className="orders-tab">
      <div className="ord-header">
        <div className="ord-header-left">
          <h2><i className="fas fa-shopping-bag"></i> Online Orders</h2>
          <p className="ord-subtitle">
            {stats.newOrders > 0 && <span className="ord-new-badge">{stats.newOrders} new</span>}
            {stats.preparing > 0 && <span>{stats.preparing} preparing</span>}
            {stats.ready > 0 && <span>{stats.ready} ready</span>}
          </p>
        </div>
        <div className="ord-header-right">
          <button className="btn-secondary btn-sm" onClick={() => setShowSettings(!showSettings)}>
            <i className="fas fa-cog"></i>
          </button>
          <button
            className={`ord-toggle-btn ${settings.enabled ? 'active' : ''}`}
            onClick={() => toggleMutation.mutate(!settings.enabled)}
          >
            <span className="ord-toggle-slider"></span>
            <span>{settings.enabled ? 'Accepting Orders' : 'Paused'}</span>
          </button>
        </div>
      </div>

      {/* Settings panel */}
      {showSettings && (
        <OrderSettings settings={settings} onSave={(s) => settingsMutation.mutate(s)} onClose={() => setShowSettings(false)} />
      )}

      {/* Filter chips */}
      <div className="ord-filters">
        {[
          { key: 'active', label: 'Active' },
          { key: 'new', label: 'New' },
          { key: 'preparing', label: 'Preparing' },
          { key: 'ready', label: 'Ready' },
          { key: 'all', label: 'All' },
        ].map(f => (
          <button key={f.key} className={`ord-filter ${statusFilter === f.key ? 'active' : ''}`} onClick={() => setStatusFilter(f.key)}>
            {f.label}
            {f.key === 'new' && stats.newOrders > 0 && <span className="ord-filter-badge">{stats.newOrders}</span>}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div className="ord-empty">
          <i className="fas fa-receipt"></i>
          <h4>No orders</h4>
          <p>{settings.enabled ? 'Waiting for incoming orders...' : 'Enable online ordering to start receiving orders.'}</p>
        </div>
      ) : (
        <div className="ord-list">
          {filtered.map(order => {
            const nextStatus = getNextStatus(order.status);
            const statusDef = ORDER_STATUSES.find(s => s.key === order.status);
            return (
              <div key={order.id} className={`ord-card ord-status-${order.status}`}>
                <div className="ord-card-top">
                  <div className="ord-card-id">
                    <span className="ord-order-num">#{order.order_number || order.id}</span>
                    <span className={`ord-type-badge ${order.order_type}`}>
                      <i className={`fas ${order.order_type === 'delivery' ? 'fa-motorcycle' : 'fa-shopping-bag'}`}></i>
                      {order.order_type === 'delivery' ? 'Delivery' : 'Takeaway'}
                    </span>
                  </div>
                  <span className="ord-card-time">{formatTime(order.created_at)}</span>
                </div>
                <div className="ord-card-customer">
                  <span>{order.customer_name || 'Guest'}</span>
                  {order.customer_phone && <span className="ord-card-phone">{order.customer_phone}</span>}
                </div>
                <div className="ord-card-items">
                  {(order.items || []).slice(0, 4).map((item, i) => (
                    <span key={i} className="ord-item">{item.quantity}× {item.name}</span>
                  ))}
                  {(order.items || []).length > 4 && <span className="ord-item-more">+{order.items.length - 4} more</span>}
                </div>
                {order.notes && <div className="ord-card-notes"><i className="fas fa-sticky-note"></i> {order.notes}</div>}
                <div className="ord-card-bottom">
                  <span className="ord-card-total">€{(parseFloat(order.total) || 0).toFixed(2)}</span>
                  <div className="ord-card-actions">
                    <span className="ord-status-badge" style={{ background: `${statusDef?.color}18`, color: statusDef?.color }}>
                      <i className={`fas ${statusDef?.icon}`}></i> {statusDef?.label}
                    </span>
                    {nextStatus && (
                      <button className="btn-primary btn-sm" onClick={() => statusMutation.mutate({ id: order.id, status: nextStatus })}>
                        {nextStatus === 'preparing' && 'Accept'}
                        {nextStatus === 'ready' && 'Mark Ready'}
                        {nextStatus === 'collected' && 'Collected'}
                      </button>
                    )}
                    {order.status === 'new' && (
                      <button className="btn-danger btn-sm" onClick={() => statusMutation.mutate({ id: order.id, status: 'cancelled' })}>
                        Decline
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function OrderSettings({ settings, onSave, onClose }) {
  const [form, setForm] = useState({
    takeaway: settings.takeaway !== false,
    delivery: settings.delivery || false,
    min_order: settings.min_order || 0,
    prep_time_mins: settings.prep_time_mins || 20,
    delivery_fee: settings.delivery_fee || 0,
    delivery_radius_km: settings.delivery_radius_km || 5,
  });

  return (
    <div className="ord-settings">
      <div className="ord-settings-header">
        <h4>Order Settings</h4>
        <button className="ord-settings-close" onClick={onClose}><i className="fas fa-times"></i></button>
      </div>
      <div className="ord-settings-grid">
        <label className="ord-setting-toggle">
          <input type="checkbox" checked={form.takeaway} onChange={e => setForm({ ...form, takeaway: e.target.checked })} />
          <span>Takeaway</span>
        </label>
        <label className="ord-setting-toggle">
          <input type="checkbox" checked={form.delivery} onChange={e => setForm({ ...form, delivery: e.target.checked })} />
          <span>Delivery</span>
        </label>
        <div className="ord-setting-field">
          <label>Prep time (mins)</label>
          <input type="number" min="5" max="120" value={form.prep_time_mins} onChange={e => setForm({ ...form, prep_time_mins: parseInt(e.target.value) || 20 })} />
        </div>
        <div className="ord-setting-field">
          <label>Min order (€)</label>
          <input type="number" min="0" step="0.50" value={form.min_order} onChange={e => setForm({ ...form, min_order: parseFloat(e.target.value) || 0 })} />
        </div>
        {form.delivery && (
          <>
            <div className="ord-setting-field">
              <label>Delivery fee (€)</label>
              <input type="number" min="0" step="0.50" value={form.delivery_fee} onChange={e => setForm({ ...form, delivery_fee: parseFloat(e.target.value) || 0 })} />
            </div>
            <div className="ord-setting-field">
              <label>Delivery radius (km)</label>
              <input type="number" min="1" max="50" value={form.delivery_radius_km} onChange={e => setForm({ ...form, delivery_radius_km: parseInt(e.target.value) || 5 })} />
            </div>
          </>
        )}
      </div>
      <div className="ord-settings-actions">
        <button className="btn-secondary btn-sm" onClick={onClose}>Cancel</button>
        <button className="btn-primary btn-sm" onClick={() => onSave(form)}>Save</button>
      </div>
    </div>
  );
}

export default OrdersTab;
