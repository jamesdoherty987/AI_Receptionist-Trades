import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../../context/AuthContext';
import { formatCurrency, formatDateTime } from '../../utils/helpers';
import { getFinances, sendInvoice, markBookingsPaid, updateBooking } from '../../services/api';
import { useToast } from '../Toast';
import LoadingSpinner from '../LoadingSpinner';
import './FinancesTab.css';

function FinancesTab({ showInvoiceButtons = true }) {
  const queryClient = useQueryClient();
  const { hasActiveSubscription } = useAuth();
  const isSubscriptionActive = hasActiveSubscription();
  const [filterMode, setFilterMode] = useState('unpaid');
  const [sendingInvoice, setSendingInvoice] = useState(null);
  const [confirmScope, setConfirmScope] = useState(null);
  const [chartRange, setChartRange] = useState('year');
  const [markingPaidId, setMarkingPaidId] = useState(null);
  const { addToast } = useToast();

  // Fetch finances data with chart range
  const { data: finances, isLoading } = useQuery({
    queryKey: ['finances', chartRange],
    queryFn: async () => {
      const response = await getFinances(chartRange);
      return response.data;
    },
    staleTime: 30 * 1000,
    cacheTime: 5 * 60 * 1000,
  });

  const {
    total_revenue = 0,
    paid_revenue = 0,
    unpaid_revenue = 0,
    transactions = [],
    daily_revenue = []
  } = finances || {};

  // Filter transactions based on selected mode
  const { unpaidTransactions, paidTransactions, displayedTransactions } = useMemo(() => {
    if (!transactions || transactions.length === 0) {
      return { unpaidTransactions: [], paidTransactions: [], displayedTransactions: [] };
    }

    const unpaid = transactions.filter(t =>
      t.status !== 'completed' &&
      t.payment_status !== 'paid' &&
      t.status !== 'cancelled' &&
      t.status !== 'paid'
    );

    const paid = transactions.filter(t =>
      t.status === 'completed' ||
      t.payment_status === 'paid' ||
      t.status === 'paid'
    );

    let displayed = [];
    if (filterMode === 'unpaid') displayed = unpaid;
    else if (filterMode === 'paid') displayed = paid;
    else displayed = transactions.filter(t => t.status !== 'cancelled');

    displayed.sort((a, b) => new Date(b.date || 0) - new Date(a.date || 0));

    return { unpaidTransactions: unpaid, paidTransactions: paid, displayedTransactions: displayed };
  }, [transactions, filterMode]);

  // Calculate max revenue for chart scaling
  const maxRevenue = useMemo(() => {
    if (!daily_revenue || daily_revenue.length === 0) return 0;
    return Math.max(...daily_revenue.map(m => m.revenue));
  }, [daily_revenue]);

  // Format a YYYY-MM-DD string to a short label
  const formatDayLabel = (dayStr) => {
    const d = new Date(dayStr + 'T00:00:00');
    return d.toLocaleDateString('en-IE', { day: 'numeric', month: 'short' });
  };

  const invoiceMutation = useMutation({
    mutationFn: (bookingId) => sendInvoice(bookingId),
    onMutate: (bookingId) => {
      setSendingInvoice(bookingId);
    },
    onSuccess: (response) => {
      const data = response.data;
      addToast(`Invoice sent to ${data.sent_to}!`, 'success');
      setSendingInvoice(null);
    },
    onError: (error) => {
      const message = error.response?.data?.error || 'Failed to send invoice';
      addToast(message, 'error');
      setSendingInvoice(null);
    }
  });

  const handleSendInvoice = (transaction, e) => {
    e.stopPropagation();
    if (!isSubscriptionActive) {
      addToast('You need an active subscription to send invoices', 'warning');
      return;
    }
    if (!transaction.booking_id && !transaction.id) {
      addToast('Cannot send invoice: No booking ID found', 'warning');
      return;
    }
    const bookingId = transaction.booking_id || transaction.id;
    invoiceMutation.mutate(bookingId);
  };

  const markPaidMutation = useMutation({
    mutationFn: (scope) => markBookingsPaid(scope),
    onSuccess: (response) => {
      const { updated, message } = response.data;
      addToast(message || `Marked ${updated} booking(s) as paid`, 'success');
      setConfirmScope(null);
      queryClient.invalidateQueries({ queryKey: ['finances'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
    onError: (error) => {
      addToast(error.response?.data?.error || 'Failed to mark bookings as paid', 'error');
      setConfirmScope(null);
    }
  });

  const scopeLabels = {
    today: "today's and earlier",
    week: "this week's and earlier",
    all: "all past"
  };

  const singleMarkPaidMutation = useMutation({
    mutationFn: (bookingId) => updateBooking(bookingId, { status: 'completed', payment_status: 'paid' }),
    onMutate: (bookingId) => {
      setMarkingPaidId(bookingId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['finances'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      addToast('Job marked as paid', 'success');
      setMarkingPaidId(null);
    },
    onError: () => {
      addToast('Failed to mark job as paid', 'error');
      setMarkingPaidId(null);
    }
  });

  // Build SVG line/area chart
  const renderChart = () => {
    if (!daily_revenue || daily_revenue.length === 0) {
      return (
        <div className="chart-empty">
          <i className="fas fa-chart-line"></i>
          <p>Revenue data will appear here as jobs are completed</p>
        </div>
      );
    }

    const padding = { top: 20, right: 15, bottom: 30, left: 10 };
    const width = 600;
    const height = 200;
    const chartW = width - padding.left - padding.right;
    const chartH = height - padding.top - padding.bottom;

    const points = daily_revenue.map((item, i) => {
      const x = padding.left + (daily_revenue.length === 1 ? chartW / 2 : (i / (daily_revenue.length - 1)) * chartW);
      const y = padding.top + chartH - (maxRevenue > 0 ? (item.revenue / maxRevenue) * chartH : 0);
      return { x, y, ...item };
    });

    const linePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ');
    const areaPath = `${linePath} L${points[points.length - 1].x},${padding.top + chartH} L${points[0].x},${padding.top + chartH} Z`;

    // Show labels for a reasonable subset of points to avoid clutter
    const maxLabels = 10;
    const step = Math.max(1, Math.ceil(points.length / maxLabels));
    const labelIndices = new Set();
    for (let i = 0; i < points.length; i += step) labelIndices.add(i);
    labelIndices.add(points.length - 1); // always show last

    return (
      <div className="chart-svg-container">
        <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" className="chart-svg">
          <defs>
            <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.02" />
            </linearGradient>
          </defs>
          <path d={areaPath} fill="url(#areaGradient)" />
          <path d={linePath} fill="none" stroke="#3b82f6" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />
          {points.map((p, i) => (
            <circle key={i} cx={p.x} cy={p.y} r="3" fill="white" stroke="#3b82f6" strokeWidth="2" />
          ))}
        </svg>
        <div className="chart-labels">
          {points.filter((_, i) => labelIndices.has(i)).map((p, i) => (
            <div key={i} className="chart-label-item" style={{ left: `${(p.x / width) * 100}%` }}>
              <span className="chart-label-value">{formatCurrency(p.revenue)}</span>
              <span className="chart-label-month">{formatDayLabel(p.day)}</span>
            </div>
          ))}
        </div>
      </div>
    );
  };

  if (isLoading) {
    return <LoadingSpinner message="Loading finances..." />;
  }

  return (
    <div className="finances-tab">
      {/* Revenue Cards */}
      <div className="revenue-grid">
        <div className="revenue-card total">
          <div className="revenue-icon" style={{ background: 'rgba(59, 130, 246, 0.1)' }}>
            <i className="fas fa-euro-sign" style={{ color: '#3b82f6' }}></i>
          </div>
          <div className="revenue-content">
            <div className="revenue-value">{formatCurrency(total_revenue)}</div>
            <div className="revenue-label">Total Revenue</div>
          </div>
        </div>
        <div className="revenue-card collected">
          <div className="revenue-icon" style={{ background: 'rgba(16, 185, 129, 0.1)' }}>
            <i className="fas fa-check-circle" style={{ color: '#10b981' }}></i>
          </div>
          <div className="revenue-content">
            <div className="revenue-value">{formatCurrency(paid_revenue)}</div>
            <div className="revenue-label">Collected</div>
          </div>
        </div>
        <div className="revenue-card outstanding">
          <div className="revenue-icon" style={{ background: 'rgba(245, 158, 11, 0.1)' }}>
            <i className="fas fa-clock" style={{ color: '#f59e0b' }}></i>
          </div>
          <div className="revenue-content">
            <div className="revenue-value">{formatCurrency(unpaid_revenue)}</div>
            <div className="revenue-label">Outstanding</div>
          </div>
        </div>
      </div>

      {/* Monthly Revenue Chart */}
      <div className="chart-section">
        <div className="chart-header">
          <h3><i className="fas fa-chart-line"></i> Revenue</h3>
          <div className="chart-range-toggle">
            {[
              { key: 'month', label: 'Past Month' },
              { key: 'year', label: 'Past Year' },
              { key: 'all', label: 'All Time' }
            ].map(opt => (
              <button
                key={opt.key}
                className={`chart-range-btn ${chartRange === opt.key ? 'active' : ''}`}
                onClick={() => setChartRange(opt.key)}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
        {renderChart()}
      </div>

      {/* Mark as Paid Actions - between chart and jobs list */}
      {unpaid_revenue > 0 && (
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button className="btn btn-secondary" style={{ fontSize: '0.8rem', padding: '0.4rem 0.75rem' }}
            onClick={() => setConfirmScope('today')} disabled={markPaidMutation.isPending}>
            <i className="fas fa-check"></i> Mark Today as Paid
          </button>
          <button className="btn btn-secondary" style={{ fontSize: '0.8rem', padding: '0.4rem 0.75rem' }}
            onClick={() => setConfirmScope('week')} disabled={markPaidMutation.isPending}>
            <i className="fas fa-check-double"></i> Mark This Week as Paid
          </button>
          <button className="btn btn-secondary" style={{ fontSize: '0.8rem', padding: '0.4rem 0.75rem' }}
            onClick={() => setConfirmScope('all')} disabled={markPaidMutation.isPending}>
            <i className="fas fa-check-circle"></i> Mark All Past as Paid
          </button>
        </div>
      )}

      {/* Confirmation Dialog */}
      {confirmScope && (
        <div style={{
          background: '#fef3c7', border: '1px solid #f59e0b', borderRadius: '8px',
          padding: '1rem', display: 'flex', alignItems: 'center',
          justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#92400e' }}>
            <i className="fas fa-exclamation-triangle"></i>
            <span style={{ fontSize: '0.85rem' }}>
              This will mark {scopeLabels[confirmScope]} unpaid bookings as paid. This can't be undone easily.
            </span>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button className="btn btn-secondary" style={{ fontSize: '0.8rem', padding: '0.35rem 0.75rem' }}
              onClick={() => setConfirmScope(null)}>
              Cancel
            </button>
            <button className="btn btn-primary" style={{ fontSize: '0.8rem', padding: '0.35rem 0.75rem' }}
              onClick={() => markPaidMutation.mutate(confirmScope)}
              disabled={markPaidMutation.isPending}>
              <i className={`fas ${markPaidMutation.isPending ? 'fa-spinner fa-spin' : 'fa-check'}`}></i>
              {markPaidMutation.isPending ? 'Updating...' : 'Confirm'}
            </button>
          </div>
        </div>
      )}

      {/* Jobs / Transactions List */}
      <div className="transactions-section">
        <div className="section-header">
          <h3>
            <i className="fas fa-file-invoice-dollar"></i>
            Jobs
          </h3>
          <div className="filter-buttons">
            <button
              className={`filter-btn ${filterMode === 'unpaid' ? 'active' : ''}`}
              onClick={() => setFilterMode('unpaid')}
            >
              <i className="fas fa-exclamation-circle"></i>
              Unpaid ({unpaidTransactions.length})
            </button>
            <button
              className={`filter-btn ${filterMode === 'paid' ? 'active' : ''}`}
              onClick={() => setFilterMode('paid')}
            >
              <i className="fas fa-check-circle"></i>
              Paid ({paidTransactions.length})
            </button>
            <button
              className={`filter-btn ${filterMode === 'all' ? 'active' : ''}`}
              onClick={() => setFilterMode('all')}
            >
              <i className="fas fa-list"></i>
              All ({transactions.filter(t => t.status !== 'cancelled').length})
            </button>
          </div>
        </div>

        <div className="transactions-list">
          {displayedTransactions.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">
                {filterMode === 'unpaid' ? '✅' : filterMode === 'paid' ? '📋' : '💰'}
              </div>
              <p>
                {filterMode === 'unpaid' && 'No unpaid jobs!'}
                {filterMode === 'paid' && 'No paid jobs yet'}
                {filterMode === 'all' && 'No jobs with charges yet'}
              </p>
            </div>
          ) : (
            displayedTransactions.map((transaction, index) => {
              const isUnpaid = transaction.status !== 'completed' &&
                               transaction.payment_status !== 'paid' &&
                               transaction.status !== 'cancelled' &&
                               transaction.status !== 'paid';
              const bookingId = transaction.booking_id || transaction.id;
              const isSending = sendingInvoice === bookingId;

              return (
                <div key={transaction.id || index} className={`transaction-card ${isUnpaid ? 'unpaid' : 'paid-card'}`}>
                  <div className="transaction-main">
                    <div className="transaction-customer">
                      <div className={`customer-avatar ${isUnpaid ? 'avatar-warning' : 'avatar-success'}`}>
                        {transaction.customer_name?.charAt(0)?.toUpperCase() || '?'}
                      </div>
                      <div className="customer-info">
                        <h4>{transaction.customer_name || 'Unknown Customer'}</h4>
                        <p>{transaction.description || 'Service'}</p>
                        {transaction.date && (
                          <span className="transaction-date">
                            <i className="fas fa-calendar"></i>
                            {formatDateTime(transaction.date)}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="transaction-status">
                      <div className={`transaction-amount ${isUnpaid ? 'amount-warning' : 'amount-success'}`}>
                        {formatCurrency(transaction.amount)}
                      </div>
                      <span className={`status-pill ${
                        transaction.status === 'completed' || transaction.payment_status === 'paid' || transaction.status === 'paid'
                          ? 'status-paid'
                          : 'status-unpaid'
                      }`}>
                        {transaction.status === 'completed' || transaction.payment_status === 'paid' || transaction.status === 'paid'
                          ? 'Paid'
                          : transaction.payment_status || transaction.status || 'Pending'
                        }
                      </span>
                      {isUnpaid && transaction.amount > 0 && (
                        <button
                          className="btn-mark-paid-single"
                          onClick={(e) => {
                            e.stopPropagation();
                            singleMarkPaidMutation.mutate(bookingId);
                          }}
                          disabled={markingPaidId === bookingId}
                        >
                          <i className={`fas ${markingPaidId === bookingId ? 'fa-spinner fa-spin' : 'fa-check'}`}></i>
                          Mark Paid
                        </button>
                      )}
                      {isUnpaid && transaction.amount > 0 && showInvoiceButtons && (
                        <button
                          className="btn-send-invoice"
                          onClick={(e) => handleSendInvoice(transaction, e)}
                          disabled={isSending}
                        >
                          <i className={`fas ${isSending ? 'fa-spinner fa-spin' : !isSubscriptionActive ? 'fa-lock' : 'fa-paper-plane'}`}></i>
                          {isSending ? 'Sending...' : !isSubscriptionActive ? 'Subscribe' : 'Send Invoice'}
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}

export default FinancesTab;
