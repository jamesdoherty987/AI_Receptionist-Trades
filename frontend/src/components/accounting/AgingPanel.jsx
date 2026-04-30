import { useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { formatCurrency, formatDate } from '../../utils/helpers';
import { getInvoiceAging, sendInvoice } from '../../services/api';
import { useToast } from '../Toast';
import { invalidateRelated } from '../../utils/queryInvalidation';
import LoadingSpinner from '../LoadingSpinner';

const BUCKET_COLORS = {
  current: { bar: '#10b981', bg: 'rgba(16, 185, 129, 0.1)', icon: 'fa-check-circle' },
  '15_30': { bar: '#f59e0b', bg: 'rgba(245, 158, 11, 0.1)', icon: 'fa-clock' },
  '31_60': { bar: '#f97316', bg: 'rgba(249, 115, 22, 0.1)', icon: 'fa-exclamation-triangle' },
  '61_90': { bar: '#ef4444', bg: 'rgba(239, 68, 68, 0.1)', icon: 'fa-exclamation-circle' },
  over_90: { bar: '#dc2626', bg: 'rgba(220, 38, 38, 0.1)', icon: 'fa-skull-crossbones' },
};

function AgingPanel() {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const { data: aging, isLoading } = useQuery({
    queryKey: ['invoice-aging'],
    queryFn: async () => (await getInvoiceAging()).data,
  });

  const bucketEntries = useMemo(() => {
    if (!aging?.buckets) return [];
    return Object.entries(aging.buckets).map(([key, bucket]) => ({
      key, ...bucket, colors: BUCKET_COLORS[key] || BUCKET_COLORS.current,
    }));
  }, [aging]);

  const maxBucket = useMemo(() => Math.max(...bucketEntries.map(b => b.total), 1), [bucketEntries]);

  const reminderMut = useMutation({
    mutationFn: (bookingId) => sendInvoice(bookingId),
    onSuccess: (res) => {
      addToast(`Reminder sent to ${res.data?.sent_to || 'customer'}`, 'success');
      invalidateRelated(queryClient, 'finances', 'jobs');
    },
    onError: (e) => addToast(e.response?.data?.error || 'Failed to send reminder', 'error'),
  });

  if (isLoading) return <LoadingSpinner message="Loading aging report..." />;

  const totalOutstanding = aging?.total_outstanding || 0;

  return (
    <div className="acct-panel">
      {/* Panel Header */}
      <div className="acct-panel-header">
        <h2 className="acct-panel-title"><i className="fas fa-hourglass-half"></i> Unpaid Invoices</h2>
      </div>

      {/* Summary */}
      <div className="acct-stats-row">
        <div className="acct-stat-card" style={{ flex: '1 1 200px' }}>
          <div className="acct-stat-icon" style={{ background: 'rgba(245, 158, 11, 0.1)' }}>
            <i className="fas fa-hourglass-half" style={{ color: '#f59e0b' }}></i>
          </div>
          <div className="acct-stat-content">
            <div className="acct-stat-value">{formatCurrency(totalOutstanding)}</div>
            <div className="acct-stat-label">Total Outstanding</div>
          </div>
        </div>
        {bucketEntries.filter(b => b.count > 0).map(b => (
          <div key={b.key} className="acct-stat-card">
            <div className="acct-stat-icon" style={{ background: b.colors.bg }}>
              <i className={`fas ${b.colors.icon}`} style={{ color: b.colors.bar }}></i>
            </div>
            <div className="acct-stat-content">
              <div className="acct-stat-value">{formatCurrency(b.total)}</div>
              <div className="acct-stat-label">{b.label} ({b.count})</div>
            </div>
          </div>
        ))}
      </div>

      {/* Aging Bar Chart */}
      {totalOutstanding > 0 && (
        <div className="acct-section">
          <div className="acct-section-header"><h3><i className="fas fa-chart-bar"></i> Aging Breakdown</h3></div>
          <div className="aging-chart">
            {bucketEntries.map(b => {
              const pct = maxBucket > 0 ? (b.total / maxBucket) * 100 : 0;
              return (
                <div key={b.key} className="aging-chart-row">
                  <div className="aging-chart-label">{b.label}</div>
                  <div className="aging-chart-bar-track">
                    <div className="aging-chart-bar-fill" style={{ width: `${Math.max(pct, b.total > 0 ? 3 : 0)}%`, background: b.colors.bar }}></div>
                  </div>
                  <div className="aging-chart-value">
                    <span className="aging-chart-amount">{formatCurrency(b.total)}</span>
                    <span className="aging-chart-count">{b.count} invoice{b.count !== 1 ? 's' : ''}</span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Stacked bar visual */}
          {totalOutstanding > 0 && (
            <div className="aging-stacked-bar">
              {bucketEntries.filter(b => b.total > 0).map(b => (
                <div key={b.key} className="aging-stacked-segment"
                  style={{ width: `${(b.total / totalOutstanding) * 100}%`, background: b.colors.bar }}
                  title={`${b.label}: ${formatCurrency(b.total)}`}>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Detailed Items by Bucket */}
      {bucketEntries.filter(b => b.items && b.items.length > 0).map(b => (
        <div key={b.key} className="acct-section">
          <div className="acct-section-header">
            <h3 style={{ color: b.colors.bar }}>
              <i className={`fas ${b.colors.icon}`}></i> {b.label}
              <span className="acct-section-count">{b.count} unpaid &middot; {formatCurrency(b.total)}</span>
            </h3>
          </div>
          <div className="acct-list">
            {b.items.sort((a, c) => c.days_overdue - a.days_overdue).map((item, idx) => (
              <div key={idx} className="acct-list-item">
                <div className="acct-list-icon" style={{ background: b.colors.bg, color: b.colors.bar }}>
                  <span style={{ fontSize: '0.7rem', fontWeight: 700 }}>{item.days_overdue}d</span>
                </div>
                <div className="acct-list-content">
                  <div className="acct-list-title">{item.customer_name}</div>
                  <div className="acct-list-meta">
                    <span><i className="fas fa-wrench"></i> {item.service}</span>
                    <span><i className="fas fa-calendar"></i> {formatDate(item.date)}</span>
                    {item.days_overdue > 0 && (
                      <span className="acct-badge" style={{ background: b.colors.bg, color: b.colors.bar }}>
                        {item.days_overdue} days overdue
                      </span>
                    )}
                  </div>
                </div>
                <div className="acct-list-amount" style={{ color: b.colors.bar }}>{formatCurrency(item.amount)}</div>
                <button className="acct-btn-reminder" title="Send payment reminder SMS"
                  onClick={() => reminderMut.mutate(item.booking_id)}
                  disabled={reminderMut.isPending}>
                  <i className={`fas ${reminderMut.isPending ? 'fa-spinner fa-spin' : 'fa-bell'}`}></i>
                  <span>Remind</span>
                </button>
              </div>
            ))}
          </div>
        </div>
      ))}

      {totalOutstanding === 0 && (
        <div className="acct-empty" style={{ marginTop: '1rem' }}>
          <i className="fas fa-check-circle" style={{ color: '#10b981' }}></i>
          <p>All caught up. No outstanding invoices.</p>
        </div>
      )}
    </div>
  );
}

export default AgingPanel;
