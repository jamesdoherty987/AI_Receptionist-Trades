import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { formatCurrency } from '../../utils/helpers';
import { getFinances, getExpenses } from '../../services/api';
import LoadingSpinner from '../LoadingSpinner';
import ExpensesPanel from '../accounting/ExpensesPanel';
import AgingPanel from '../accounting/AgingPanel';
import PnlPanel from '../accounting/PnlPanel';
import TaxSettings from '../accounting/TaxSettings';
import PurchaseOrdersPanel from '../accounting/PurchaseOrdersPanel';
import MileagePanel from '../accounting/MileagePanel';
import CreditNotesPanel from '../accounting/CreditNotesPanel';
import '../accounting/Accounting.css';
import './FinancesTab.css';
import './SharedDashboard.css';

const ACCT_TABS = [
  { key: 'overview', label: 'Dashboard', icon: 'fa-chart-line' },
  { key: 'invoicing', label: 'Invoicing', icon: 'fa-file-invoice' },
  { key: 'expenses', label: 'Expenses', icon: 'fa-receipt' },
  { key: 'reports', label: 'Reports', icon: 'fa-file-invoice-dollar' },
];

function FinancesTab() {
  const [acctTab, setAcctTab] = useState('overview');

  const [chartRange, setChartRange] = useState('year');

  // Graph visibility toggles (persisted in localStorage)
  const [showSections, setShowSections] = useState(() => {
    try {
      const saved = localStorage.getItem('finances_visible_sections');
      return saved ? JSON.parse(saved) : {
        revenueCards: true, revenueChart: true, quickInsights: true,
        serviceBreakdown: true, topCustomers: true
      };
    } catch { return { revenueCards: true, revenueChart: true, quickInsights: true, serviceBreakdown: true, topCustomers: true }; }
  });
  const [showSectionPicker, setShowSectionPicker] = useState(false);

  const toggleSection = (key) => {
    const next = { ...showSections, [key]: !showSections[key] };
    setShowSections(next);
    localStorage.setItem('finances_visible_sections', JSON.stringify(next));
  };

  // Fetch finances data with chart range
  const { data: finances, isLoading } = useQuery({
    queryKey: ['finances', chartRange],
    queryFn: async () => {
      const response = await getFinances(chartRange);
      return response.data;
    },
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

  // Fetch expenses for cash flow widget
  const { data: expensesData } = useQuery({
    queryKey: ['expenses'],
    queryFn: async () => (await getExpenses()).data,
    enabled: acctTab === 'overview',
  });
  const totalExpenses = (expensesData || []).reduce((s, e) => s + (e.amount || 0), 0);
  const netCashFlow = paid_revenue - totalExpenses - total_materials_cost;

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

    // Payment method breakdown
    const paidJobs = nonCancelled.filter(t => t.payment_status === 'paid');
    const stripePaid = paidJobs.filter(t => t.payment_method === 'stripe').length;
    const otherPaid = paidJobs.length - stripePaid;
    const stripeRate = paidJobs.length > 0 ? (stripePaid / paidJobs.length) * 100 : 0;

    return { totalJobs, avgJobValue, collectionRate, serviceBreakdown, topCustomers, avgProfit, topCostJobs, stripePaid, otherPaid, stripeRate, paidJobsCount: paidJobs.length };
  }, [transactions, total_revenue, paid_revenue]);

  // Format a YYYY-MM-DD string to a short label
  const formatDayLabel = (dayStr) => {
    const d = new Date(dayStr + 'T00:00:00');
    return d.toLocaleDateString('en-IE', { day: 'numeric', month: 'short' });
  };

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
      {/* Page Header */}
      <div className="tab-page-header">
        <h2 className="tab-page-title">Finances</h2>
      </div>

      {/* Accounting Sub-Navigation */}
      <div className="acct-subnav">
        {ACCT_TABS.map(tab => (
          <button key={tab.key}
            className={`acct-subnav-btn ${acctTab === tab.key ? 'active' : ''}`}
            onClick={() => setAcctTab(tab.key)}>
            <i className={`fas ${tab.icon}`}></i>
            <span className="acct-subnav-label">{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Render active sub-panel */}
      {acctTab === 'overview' && (
        <div className="fin-quick-actions">
          <button className="fin-quick-btn" onClick={() => setAcctTab('expenses')}>
            <i className="fas fa-plus"></i> New Expense
          </button>
          <div style={{ marginLeft: 'auto' }}>
            <button className="fin-section-toggle-btn" onClick={() => setShowSectionPicker(!showSectionPicker)}>
              <i className={`fas ${showSectionPicker ? 'fa-times' : 'fa-sliders-h'}`}></i>
              {showSectionPicker ? 'Done' : 'Customize'}
            </button>
          </div>
        </div>
      )}

      {/* Invoicing — Unpaid invoices + Credit notes */}
      {acctTab === 'invoicing' && (
        <InvoicingView />
      )}

      {/* Expenses — Expenses + Mileage + Purchase Orders */}
      {acctTab === 'expenses' && (
        <ExpensesView />
      )}

      {/* Reports — P&L + Tax Settings */}
      {acctTab === 'reports' && (
        <ReportsView />
      )}

      {acctTab === 'overview' && (<>
      {/* AI Cash Flow Insights */}
      <AiFinanceInsights
        totalRevenue={total_revenue}
        paidRevenue={paid_revenue}
        unpaidRevenue={unpaid_revenue}
        totalExpenses={totalExpenses}
        materialsCost={total_materials_cost}
        netCashFlow={netCashFlow}
        profitMargin={profit_margin}
        transactions={transactions}
        insights={insights}
      />

      {/* Section Visibility Picker */}
      {showSectionPicker && (
      <div className="fin-section-toggle-bar">
        <div className="fin-section-picker">
          {[
              { key: 'revenueCards', label: 'Revenue Cards', icon: 'fa-euro-sign' },
              { key: 'revenueChart', label: 'Revenue Chart', icon: 'fa-chart-line' },
              { key: 'quickInsights', label: 'Quick Insights', icon: 'fa-lightbulb' },
              { key: 'serviceBreakdown', label: 'Revenue by Service', icon: 'fa-chart-bar' },
              { key: 'topCustomers', label: 'Top Customers', icon: 'fa-users' },
            ].map(s => (
              <button key={s.key} className={`fin-section-chip ${showSections[s.key] ? 'active' : ''}`}
                onClick={() => toggleSection(s.key)}>
                <i className={`fas ${s.icon}`}></i> {s.label}
                <i className={`fas ${showSections[s.key] ? 'fa-eye' : 'fa-eye-slash'}`}></i>
              </button>
            ))}
          </div>
      </div>
      )}

      {/* Revenue Cards */}
      {showSections.revenueCards && (
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
              <i className={`fas ${gross_profit >= 0 ? 'fa-arrow-trend-up' : 'fa-arrow-trend-down'}`} style={{ color: gross_profit >= 0 ? '#10b981' : '#ef4444' }}></i>
            </div>
            <div className="revenue-content">
              <div className="revenue-value" style={{ color: gross_profit >= 0 ? '#10b981' : '#ef4444' }}>{formatCurrency(gross_profit)}</div>
              <div className="revenue-label">Gross Profit ({profit_margin}%)</div>
            </div>
          </div>
        )}
        {totalExpenses > 0 && (
          <div className="revenue-card">
            <div className="revenue-icon" style={{ background: 'rgba(139, 92, 246, 0.1)' }}>
              <i className="fas fa-receipt" style={{ color: '#8b5cf6' }}></i>
            </div>
            <div className="revenue-content">
              <div className="revenue-value">{formatCurrency(totalExpenses)}</div>
              <div className="revenue-label">Total Expenses</div>
            </div>
          </div>
        )}
        <div className="revenue-card">
          <div className="revenue-icon" style={{ background: netCashFlow >= 0 ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)' }}>
            <i className={`fas ${netCashFlow >= 0 ? 'fa-wallet' : 'fa-exclamation-triangle'}`} style={{ color: netCashFlow >= 0 ? '#10b981' : '#ef4444' }}></i>
          </div>
          <div className="revenue-content">
            <div className="revenue-value" style={{ color: netCashFlow >= 0 ? '#10b981' : '#ef4444' }}>{formatCurrency(netCashFlow)}</div>
            <div className="revenue-label">Net Cash Flow</div>
          </div>
        </div>
      </div>
      )}

      {/* Monthly Revenue Chart */}
      {showSections.revenueChart && (
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
      )}

      {/* Quick Insights Row */}
      {showSections.quickInsights && (
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
        {insights.paidJobsCount > 0 && (
          <div className="insight-card">
            <div className="insight-icon" style={{ background: 'rgba(99, 102, 241, 0.1)' }}>
              <i className="fas fa-credit-card" style={{ color: '#6366f1' }}></i>
            </div>
            <div className="insight-content">
              <div className="insight-value">{insights.stripePaid}/{insights.paidJobsCount}</div>
              <div className="insight-label">Stripe Payments ({insights.stripeRate.toFixed(0)}%)</div>
            </div>
          </div>
        )}
      </div>
      )}

      {/* Revenue by Service & Top Customers side by side */}
      {(showSections.serviceBreakdown || showSections.topCustomers) && (insights.serviceBreakdown.length > 0 || insights.topCustomers.length > 0) && (
        <div className="insights-grid">
          {/* Revenue by Service Type */}
          {showSections.serviceBreakdown && insights.serviceBreakdown.length > 0 && (
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
          {showSections.topCustomers && insights.topCustomers.length > 0 && (
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

      </>)}
    </div>
  );
}

/* ============================================
   INVOICING VIEW — Unpaid + Credits
   ============================================ */
function InvoicingView() {
  const [subView, setSubView] = useState('unpaid');
  return (
    <div className="fin-grouped-view">
      <div className="fin-sub-toggle">
        <button className={subView === 'unpaid' ? 'active' : ''} onClick={() => setSubView('unpaid')}>
          <i className="fas fa-hourglass-half"></i> Outstanding
        </button>
        <button className={subView === 'credits' ? 'active' : ''} onClick={() => setSubView('credits')}>
          <i className="fas fa-undo"></i> Credit Notes
        </button>
      </div>
      {subView === 'unpaid' && <AgingPanel />}
      {subView === 'credits' && <CreditNotesPanel />}
    </div>
  );
}

/* ============================================
   EXPENSES VIEW — Expenses + Mileage + POs
   ============================================ */
function ExpensesView() {
  const [subView, setSubView] = useState('expenses');
  return (
    <div className="fin-grouped-view">
      <div className="fin-sub-toggle">
        <button className={subView === 'expenses' ? 'active' : ''} onClick={() => setSubView('expenses')}>
          <i className="fas fa-receipt"></i> Expenses
        </button>
        <button className={subView === 'mileage' ? 'active' : ''} onClick={() => setSubView('mileage')}>
          <i className="fas fa-car"></i> Mileage
        </button>
        <button className={subView === 'purchase-orders' ? 'active' : ''} onClick={() => setSubView('purchase-orders')}>
          <i className="fas fa-file-export"></i> Purchase Orders
        </button>
      </div>
      {subView === 'expenses' && <ExpensesPanel />}
      {subView === 'mileage' && <MileagePanel />}
      {subView === 'purchase-orders' && <PurchaseOrdersPanel />}
    </div>
  );
}

/* ============================================
   REPORTS VIEW — P&L + Tax Settings
   ============================================ */
function ReportsView() {
  const [subView, setSubView] = useState('pnl');
  return (
    <div className="fin-grouped-view">
      <div className="fin-sub-toggle">
        <button className={subView === 'pnl' ? 'active' : ''} onClick={() => setSubView('pnl')}>
          <i className="fas fa-file-invoice-dollar"></i> Profit & Loss
        </button>
        <button className={subView === 'tax' ? 'active' : ''} onClick={() => setSubView('tax')}>
          <i className="fas fa-cog"></i> Tax Settings
        </button>
      </div>
      {subView === 'pnl' && <PnlPanel />}
      {subView === 'tax' && <TaxSettings />}
    </div>
  );
}

/* ============================================
   AI FINANCE INSIGHTS
   ============================================ */
function AiFinanceInsights({ totalRevenue, paidRevenue, unpaidRevenue, totalExpenses, materialsCost, netCashFlow, profitMargin, transactions, insights }) {
  const tips = useMemo(() => {
    const items = [];
    const fmt = (v) => new Intl.NumberFormat('en-IE', { style: 'currency', currency: 'EUR' }).format(v);

    // Collection rate
    if (totalRevenue > 0) {
      const collectionRate = (paidRevenue / totalRevenue) * 100;
      if (collectionRate < 70) {
        items.push({ icon: 'fa-exclamation-circle', text: `Collection rate is ${collectionRate.toFixed(0)}%. Send reminders for ${fmt(unpaidRevenue)} in outstanding invoices.`, type: 'warning' });
      } else if (collectionRate > 90) {
        items.push({ icon: 'fa-check-circle', text: `Excellent ${collectionRate.toFixed(0)}% collection rate. Cash flow is healthy.`, type: 'positive' });
      }
    }

    // Profit margin
    if (profitMargin > 0 && profitMargin < 30) {
      items.push({ icon: 'fa-chart-pie', text: `Profit margin is ${profitMargin.toFixed(0)}%. Consider reviewing material costs or adjusting service pricing.`, type: 'action' });
    } else if (profitMargin >= 50) {
      items.push({ icon: 'fa-gem', text: `Strong ${profitMargin.toFixed(0)}% profit margin — well above industry average.`, type: 'positive' });
    }

    // Cash flow
    if (netCashFlow < 0) {
      items.push({ icon: 'fa-arrow-down', text: `Negative cash flow of ${fmt(Math.abs(netCashFlow))}. Expenses and materials exceed collected revenue.`, type: 'warning' });
    }

    // Auto-invoice suggestion
    const unpaidJobs = transactions.filter(t => t.status === 'completed' && t.payment_status !== 'paid');
    if (unpaidJobs.length > 3) {
      items.push({ icon: 'fa-robot', text: `${unpaidJobs.length} jobs awaiting invoices. Enable auto-invoicing in Settings to send invoices automatically when jobs complete.`, type: 'action' });
    }

    // Stripe adoption
    if (insights.paidJobsCount > 0 && insights.stripeRate < 40) {
      items.push({ icon: 'fa-credit-card', text: `Only ${insights.stripeRate.toFixed(0)}% of payments are online. Adding a payment link to invoices can speed up collection.`, type: 'action' });
    }

    if (items.length === 0) {
      items.push({ icon: 'fa-thumbs-up', text: 'Finances look good. No immediate actions needed.', type: 'positive' });
    }

    return items.slice(0, 3);
  }, [totalRevenue, paidRevenue, unpaidRevenue, totalExpenses, materialsCost, netCashFlow, profitMargin, transactions, insights]);

  return (
    <div className="ai-insight-card">
      <div className="ai-insight-header">
        <span className="ai-insight-badge"><i className="fas fa-sparkles"></i> AI</span>
        <span className="ai-insight-title">Financial Health Check</span>
      </div>
      <div className="ai-insight-body">
        {tips.map((item, i) => (
          <div key={i} className="ai-insight-item">
            <i className={`fas ${item.icon}`} style={{ color: item.type === 'positive' ? '#10b981' : item.type === 'warning' ? '#f59e0b' : '#6366f1' }}></i>
            <span>{item.text}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default FinancesTab;
