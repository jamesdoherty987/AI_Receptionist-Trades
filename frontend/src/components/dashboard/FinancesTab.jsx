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
    gcTime: 5 * 60 * 1000,
  });

  const {
    total_revenue = 0,
    paid_revenue = 0,
    unpaid_revenue = 0,
    total_materials_cost = 0,
    gross_profit = 0,
    profit_margin = 0,
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

  // Insights computed from transactions
  const insights = useMemo(() => {
    const nonCancelled = transactions.filter(t => t.status !== 'cancelled');
    const totalJobs = nonCancelled.length;
    const avgJobValue = totalJobs > 0 ? nonCancelled.reduce((s, t) => s + (t.amount || 0), 0) / totalJobs : 0;
    const collectionRate = total_revenue > 0 ? (paid_revenue / total_revenue) * 100 : 0;

    // Profit per job
    const jobsWithMaterials = nonCancelled.filter(t => t.materials_cost > 0);
    const avgProfit = jobsWithMaterials.length > 0 
      ? jobsWithMaterials.reduce((s, t) => s + (t.profit || 0), 0) / jobsWithMaterials.length 
      : 0;

    // Most expensive materials (top spending jobs)
    const topCostJobs = [...nonCancelled]
      .filter(t => t.materials_cost > 0)
      .sort((a, b) => b.materials_cost - a.materials_cost)
      .slice(0, 5);

    // Revenue by service type
    const byService = {};
    nonCancelled.forEach(t => {
      const svc = t.description || 'Other';
      if (!byService[svc]) byService[svc] = { revenue: 0, materials: 0 };
      byService[svc].revenue += (t.amount || 0);
      byService[svc].materials += (t.materials_cost || 0);
    });
    const serviceBreakdown = Object.entries(byService)
      .map(([name, data]) => ({ name, revenue: data.revenue, materials: data.materials, profit: data.revenue - data.materials }))
      .sort((a, b) => b.revenue - a.revenue);

    // Top customers by total spend
    const byCustomer = {};
    nonCancelled.forEach(t => {
      const name = t.customer_name || 'Unknown';
      if (!byCustomer[name]) byCustomer[name] = { revenue: 0, jobs: 0 };
      byCustomer[name].revenue += (t.amount || 0);
      byCustomer[name].jobs += 1;
    });
    const topCustomers = Object.entries(byCustomer)
      .map(([name, data]) => ({ name, ...data }))
      .sort((a, b) => b.revenue - a.revenue)
      .slice(0, 5);

    return { totalJobs, avgJobValue, collectionRate, serviceBreakdown, topCustomers, avgProfit, topCostJobs };
  }, [transactions, total_revenue, paid_revenue]);

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

  // Build smooth SVG area chart using monotone cubic interpolation
  const renderChart = () => {
    if (!daily_revenue || daily_revenue.length === 0) {
      return (
        <div className="chart-empty">
          <i className="fas fa-chart-line"></i>
          <p>Revenue data will appear here as jobs are completed</p>
        </div>
      );
    }

    // For a single data point, show a centered dot instead of a line
    if (daily_revenue.length === 1) {
      const item = daily_revenue[0];
      return (
        <div className="chart-svg-container">
          <svg viewBox="0 0 600 180" preserveAspectRatio="xMidYMid meet" className="chart-svg">
            <circle cx="300" cy="80" r="5" fill="#6366f1" />
          </svg>
          <div className="chart-labels">
            <div className="chart-label-item" style={{ left: '50%' }}>
              <span className="chart-label-value">{formatCurrency(item.revenue)}</span>
              <span className="chart-label-month">{formatDayLabel(item.day)}</span>
            </div>
          </div>
        </div>
      );
    }

    const padding = { top: 16, right: 16, bottom: 8, left: 16 };
    const width = 600;
    const height = 180;
    const chartW = width - padding.left - padding.right;
    const chartH = height - padding.top - padding.bottom;

    const points = daily_revenue.map((item, i) => {
      const x = padding.left + (i / (daily_revenue.length - 1)) * chartW;
      const y = padding.top + chartH - (maxRevenue > 0 ? (item.revenue / maxRevenue) * chartH * 0.85 : 0);
      return { x, y, ...item };
    });

    // Monotone cubic hermite spline — prevents overshoot so the curve
    // never dips below 0 or spikes above the max value
    const monotonePath = (pts) => {
      const n = pts.length;
      if (n < 2) return `M${pts[0].x},${pts[0].y}`;

      // 1. Compute slopes between consecutive points
      const dx = [];
      const dy = [];
      const m = []; // tangent at each point
      for (let i = 0; i < n - 1; i++) {
        dx.push(pts[i + 1].x - pts[i].x);
        dy.push(pts[i + 1].y - pts[i].y);
      }
      const slopes = dx.map((d, i) => dy[i] / d);

      // 2. Compute tangents using Fritsch-Carlson method
      m.push(slopes[0]);
      for (let i = 1; i < n - 1; i++) {
        if (slopes[i - 1] * slopes[i] <= 0) {
          m.push(0);
        } else {
          m.push((slopes[i - 1] + slopes[i]) / 2);
        }
      }
      m.push(slopes[n - 2]);

      // 3. Adjust tangents to ensure monotonicity
      for (let i = 0; i < n - 1; i++) {
        if (Math.abs(slopes[i]) < 1e-6) {
          m[i] = 0;
          m[i + 1] = 0;
        } else {
          const alpha = m[i] / slopes[i];
          const beta = m[i + 1] / slopes[i];
          const s = alpha * alpha + beta * beta;
          if (s > 9) {
            const t = 3 / Math.sqrt(s);
            m[i] = t * alpha * slopes[i];
            m[i + 1] = t * beta * slopes[i];
          }
        }
      }

      // 4. Build cubic bezier segments
      let d = `M${pts[0].x},${pts[0].y}`;
      for (let i = 0; i < n - 1; i++) {
        const seg = dx[i] / 3;
        const cp1x = pts[i].x + seg;
        const cp1y = pts[i].y + m[i] * seg;
        const cp2x = pts[i + 1].x - seg;
        const cp2y = pts[i + 1].y - m[i + 1] * seg;
        d += ` C${cp1x},${cp1y} ${cp2x},${cp2y} ${pts[i + 1].x},${pts[i + 1].y}`;
      }
      return d;
    };

    const linePath = monotonePath(points);
    const bottomY = padding.top + chartH;
    const areaPath = `${linePath} L${points[points.length - 1].x},${bottomY} L${points[0].x},${bottomY} Z`;

    // Subtle horizontal grid lines
    const gridLines = [0.25, 0.5, 0.75].map(pct => padding.top + chartH * (1 - pct * 0.85));

    // Show labels for a reasonable subset
    const maxLabels = 8;
    const step = Math.max(1, Math.ceil(points.length / maxLabels));
    const labelIndices = new Set();
    for (let i = 0; i < points.length; i += step) labelIndices.add(i);
    labelIndices.add(points.length - 1);

    return (
      <div className="chart-svg-container">
        <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="xMidYMid meet" className="chart-svg">
          <defs>
            <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#6366f1" stopOpacity="0.15" />
              <stop offset="100%" stopColor="#6366f1" stopOpacity="0.01" />
            </linearGradient>
          </defs>
          {gridLines.map((y, i) => (
            <line key={i} x1={padding.left} y1={y} x2={width - padding.right} y2={y} stroke="#f1f5f9" strokeWidth="0.7" />
          ))}
          <path d={areaPath} fill="url(#areaGradient)" />
          <path d={linePath} fill="none" stroke="#6366f1" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
          {/* Data point dots */}
          {points.filter((_, i) => labelIndices.has(i)).map((p, i) => (
            <circle key={i} cx={p.x} cy={p.y} r="3" fill="white" stroke="#6366f1" strokeWidth="1.8" />
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
        {total_materials_cost > 0 && (
          <div className="revenue-card materials-cost">
            <div className="revenue-icon" style={{ background: 'rgba(239, 68, 68, 0.1)' }}>
              <i className="fas fa-cubes" style={{ color: '#ef4444' }}></i>
            </div>
            <div className="revenue-content">
              <div className="revenue-value">{formatCurrency(total_materials_cost)}</div>
              <div className="revenue-label">Materials Cost</div>
            </div>
          </div>
        )}
        {total_materials_cost > 0 && (
          <div className="revenue-card profit">
            <div className="revenue-icon" style={{ background: gross_profit >= 0 ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)' }}>
              <i className={`fas ${gross_profit >= 0 ? 'fa-trending-up' : 'fa-trending-down'}`} style={{ color: gross_profit >= 0 ? '#10b981' : '#ef4444' }}></i>
            </div>
            <div className="revenue-content">
              <div className="revenue-value" style={{ color: gross_profit >= 0 ? '#10b981' : '#ef4444' }}>{formatCurrency(gross_profit)}</div>
              <div className="revenue-label">Gross Profit ({profit_margin}%)</div>
            </div>
          </div>
        )}
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

      {/* Quick Insights Row */}
      <div className="insights-row">
        <div className="insight-card">
          <div className="insight-icon" style={{ background: 'rgba(99, 102, 241, 0.1)' }}>
            <i className="fas fa-receipt" style={{ color: '#6366f1' }}></i>
          </div>
          <div className="insight-content">
            <div className="insight-value">{insights.totalJobs}</div>
            <div className="insight-label">Total Jobs</div>
          </div>
        </div>
        <div className="insight-card">
          <div className="insight-icon" style={{ background: 'rgba(14, 165, 233, 0.1)' }}>
            <i className="fas fa-calculator" style={{ color: '#0ea5e9' }}></i>
          </div>
          <div className="insight-content">
            <div className="insight-value">{formatCurrency(insights.avgJobValue)}</div>
            <div className="insight-label">Avg Job Value</div>
          </div>
        </div>
        {insights.avgProfit > 0 && (
          <div className="insight-card">
            <div className="insight-icon" style={{ background: 'rgba(16, 185, 129, 0.1)' }}>
              <i className="fas fa-coins" style={{ color: '#10b981' }}></i>
            </div>
            <div className="insight-content">
              <div className="insight-value">{formatCurrency(insights.avgProfit)}</div>
              <div className="insight-label">Avg Profit/Job</div>
            </div>
          </div>
        )}
        <div className="insight-card">
          <div className="insight-icon" style={{ background: paid_revenue > 0 && insights.collectionRate >= 70 ? 'rgba(16, 185, 129, 0.1)' : 'rgba(245, 158, 11, 0.1)' }}>
            <i className="fas fa-percentage" style={{ color: paid_revenue > 0 && insights.collectionRate >= 70 ? '#10b981' : '#f59e0b' }}></i>
          </div>
          <div className="insight-content">
            <div className="insight-value">{insights.collectionRate.toFixed(0)}%</div>
            <div className="insight-label">Collection Rate</div>
          </div>
        </div>
      </div>

      {/* Revenue by Service & Top Customers side by side */}
      {(insights.serviceBreakdown.length > 0 || insights.topCustomers.length > 0) && (
        <div className="insights-grid">
          {/* Revenue by Service Type */}
          {insights.serviceBreakdown.length > 0 && (
            <div className="chart-section">
              <div className="chart-header">
                <h3><i className="fas fa-chart-bar"></i> Revenue by Service</h3>
              </div>
              <div className="service-bars">
                {insights.serviceBreakdown.slice(0, 6).map((svc, i) => {
                  const maxSvcRevenue = insights.serviceBreakdown[0]?.revenue || 1;
                  const pct = (svc.revenue / maxSvcRevenue) * 100;
                  return (
                    <div key={i} className="service-bar-row">
                      <div className="service-bar-label">{svc.name}</div>
                      <div className="service-bar-track">
                        <div
                          className="service-bar-fill"
                          style={{ width: `${Math.max(pct, 3)}%` }}
                        />
                      </div>
                      <div className="service-bar-value">{formatCurrency(svc.revenue)}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Top Customers */}
          {insights.topCustomers.length > 0 && (
            <div className="chart-section">
              <div className="chart-header">
                <h3><i className="fas fa-users"></i> Top Customers</h3>
              </div>
              <div className="top-customers-list">
                {insights.topCustomers.map((cust, i) => (
                  <div key={i} className="top-customer-row">
                    <div className="top-customer-rank">{i + 1}</div>
                    <div className="top-customer-info">
                      <div className="top-customer-name">{cust.name}</div>
                      <div className="top-customer-jobs">{cust.jobs} job{cust.jobs !== 1 ? 's' : ''}</div>
                    </div>
                    <div className="top-customer-revenue">{formatCurrency(cust.revenue)}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

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
                      {transaction.materials_cost > 0 && (
                        <div className="transaction-profit-line">
                          <span className="transaction-materials">-{formatCurrency(transaction.materials_cost)} materials</span>
                          <span className={`transaction-profit ${transaction.profit >= 0 ? 'profit-positive' : 'profit-negative'}`}>
                            = {formatCurrency(transaction.profit)} profit
                          </span>
                        </div>
                      )}
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
