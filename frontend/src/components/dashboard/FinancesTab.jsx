import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { formatCurrency, formatDate } from '../../utils/helpers';
import { useIndustry } from '../../context/IndustryContext';
import { getFinances, getExpenses, getRevenueEntries, createRevenueEntry, createExpense, getBookings, getInvoiceAging, updateBooking, getCreditNotes } from '../../services/api';
import LoadingSpinner from '../LoadingSpinner';
import { useToast } from '../Toast';
import ExpensesPanel from '../accounting/ExpensesPanel';
import AgingPanel from '../accounting/AgingPanel';
import PnlPanel from '../accounting/PnlPanel';
import TaxSettings from '../accounting/TaxSettings';
import PurchaseOrdersPanel from '../accounting/PurchaseOrdersPanel';
import MileagePanel from '../accounting/MileagePanel';
import CreditNotesPanel from '../accounting/CreditNotesPanel';
import RevenueLedgerPanel from '../accounting/RevenueLedgerPanel';
import '../accounting/Accounting.css';
import './FinancesTab.css';
import './SharedDashboard.css';

const SECTIONS = [
  { key: 'overview', label: 'Overview', icon: 'fa-chart-line' },
  { key: 'log', label: 'Transaction Log', icon: 'fa-list-ul' },
  { key: 'income', label: 'Income', icon: 'fa-arrow-up' },
  { key: 'expenses', label: 'Expenses', icon: 'fa-arrow-down' },
  { key: 'invoicing', label: 'Invoicing', icon: 'fa-file-invoice' },
  { key: 'reports', label: 'Reports', icon: 'fa-chart-pie' },
];

const REVENUE_CATEGORIES = [
  { value: 'walk_in', label: 'Walk-in Sale', icon: 'fa-door-open' },
  { value: 'cash_sale', label: 'Cash Sale', icon: 'fa-money-bill-wave' },
  { value: 'service', label: 'Service Income', icon: 'fa-concierge-bell' },
  { value: 'product', label: 'Product Sale', icon: 'fa-box' },
  { value: 'tip', label: 'Tip / Gratuity', icon: 'fa-hand-holding-dollar' },
  { value: 'deposit', label: 'Deposit Received', icon: 'fa-piggy-bank' },
  { value: 'other', label: 'Other Income', icon: 'fa-ellipsis' },
];

const PAYMENT_METHODS = [
  { value: 'cash', label: 'Cash', icon: 'fa-money-bill-wave' },
  { value: 'card', label: 'Card', icon: 'fa-credit-card' },
  { value: 'bank_transfer', label: 'Bank Transfer', icon: 'fa-building-columns' },
  { value: 'stripe', label: 'Stripe', icon: 'fa-bolt' },
  { value: 'cheque', label: 'Cheque', icon: 'fa-money-check' },
  { value: 'other', label: 'Other', icon: 'fa-ellipsis' },
];

const EXPENSE_CATEGORIES = [
  { value: 'fuel', label: 'Fuel & Mileage', icon: 'fa-gas-pump' },
  { value: 'tools', label: 'Tools & Equipment', icon: 'fa-wrench' },
  { value: 'materials', label: 'Materials & Supplies', icon: 'fa-cubes' },
  { value: 'vehicle', label: 'Vehicle Maintenance', icon: 'fa-car' },
  { value: 'insurance', label: 'Insurance', icon: 'fa-shield-halved' },
  { value: 'software', label: 'Software & Subscriptions', icon: 'fa-laptop' },
  { value: 'office', label: 'Office & Admin', icon: 'fa-building' },
  { value: 'marketing', label: 'Marketing', icon: 'fa-bullhorn' },
  { value: 'refund', label: 'Refund / Credit', icon: 'fa-undo' },
  { value: 'other', label: 'Other', icon: 'fa-ellipsis' },
];

function FinancesTab() {
  const { terminology } = useIndustry();
  const [activeSection, setActiveSection] = useState('overview');
  const [chartRange, setChartRange] = useState('year');

  // ── Data fetching ──
  const { data: finances, isLoading } = useQuery({
    queryKey: ['finances', chartRange],
    queryFn: async () => (await getFinances(chartRange)).data,
    gcTime: 5 * 60 * 1000,
  });

  const { data: expensesData } = useQuery({
    queryKey: ['expenses'],
    queryFn: async () => (await getExpenses()).data,
  });

  const { data: bookingsData } = useQuery({
    queryKey: ['bookings'],
    queryFn: async () => (await getBookings()).data,
    staleTime: 30000,
  });

  const { data: revenueEntries = [] } = useQuery({
    queryKey: ['revenue-entries'],
    queryFn: async () => (await getRevenueEntries()).data,
  });

  const { data: agingData } = useQuery({
    queryKey: ['invoice-aging'],
    queryFn: async () => (await getInvoiceAging()).data,
    enabled: activeSection === 'overview',
  });

  const { data: creditNotes = [] } = useQuery({
    queryKey: ['credit-notes'],
    queryFn: async () => (await getCreditNotes()).data,
  });

  const {
    total_revenue = 0, paid_revenue = 0, unpaid_revenue = 0,
    manual_revenue = 0, total_materials_cost = 0, total_refunds = 0,
    gross_profit = 0, profit_margin = 0, transactions = [], daily_revenue = []
  } = finances || {};

  const totalExpenses = (expensesData || []).reduce((s, e) => s + (e.amount || 0), 0);
  const netCashFlow = paid_revenue - totalExpenses - total_materials_cost;
  const totalOutstanding = agingData?.total_outstanding || 0;

  // ── Insights ──
  const insights = useMemo(() => {
    const nonCancelled = transactions.filter(t => t.status !== 'cancelled');
    const totalJobs = nonCancelled.length;
    const avgJobValue = totalJobs > 0 ? nonCancelled.reduce((s, t) => s + (t.amount || 0), 0) / totalJobs : 0;
    const collectionRate = total_revenue > 0 ? (paid_revenue / total_revenue) * 100 : 0;
    const byService = {};
    nonCancelled.forEach(t => {
      const svc = t.description || 'Other';
      if (!byService[svc]) byService[svc] = { revenue: 0 };
      byService[svc].revenue += (t.amount || 0);
    });
    const serviceBreakdown = Object.entries(byService)
      .map(([name, data]) => ({ name, revenue: data.revenue }))
      .sort((a, b) => b.revenue - a.revenue);
    const byCustomer = {};
    nonCancelled.forEach(t => {
      const name = t.customer_name || 'Unknown';
      if (!byCustomer[name]) byCustomer[name] = { revenue: 0, jobs: 0 };
      byCustomer[name].revenue += (t.amount || 0);
      byCustomer[name].jobs += 1;
    });
    const topCustomers = Object.entries(byCustomer)
      .map(([name, data]) => ({ name, ...data }))
      .sort((a, b) => b.revenue - a.revenue).slice(0, 5);
    return { totalJobs, avgJobValue, collectionRate, serviceBreakdown, topCustomers };
  }, [transactions, total_revenue, paid_revenue]);

  // ── Chart ──
  const maxRevenue = useMemo(() => {
    if (!daily_revenue || daily_revenue.length === 0) return 0;
    return Math.max(...daily_revenue.map(m => m.revenue));
  }, [daily_revenue]);

  const formatDayLabel = (dayStr) => {
    const d = new Date(dayStr + 'T00:00:00');
    return d.toLocaleDateString('en-IE', { day: 'numeric', month: 'short' });
  };

  if (isLoading) return <LoadingSpinner message="Loading finances..." />;

  return (
    <div className="finances-tab">
      {/* Section Navigation — flat, single level */}
      <div className="fin-nav">
        {SECTIONS.map(s => (
          <button key={s.key}
            className={`fin-nav-btn ${activeSection === s.key ? 'active' : ''}`}
            onClick={() => setActiveSection(s.key)}>
            <i className={`fas ${s.icon}`}></i>
            <span>{s.label}</span>
          </button>
        ))}
      </div>

      {/* ═══════════════════════════════════════
          OVERVIEW
         ═══════════════════════════════════════ */}
      {activeSection === 'overview' && (
        <OverviewSection
          finances={{ total_revenue, paid_revenue, unpaid_revenue, manual_revenue, total_materials_cost, total_refunds, gross_profit, profit_margin, netCashFlow, totalExpenses, totalOutstanding }}
          insights={insights}
          daily_revenue={daily_revenue}
          maxRevenue={maxRevenue}
          chartRange={chartRange}
          setChartRange={setChartRange}
          formatDayLabel={formatDayLabel}
          terminology={terminology}
          onNavigate={setActiveSection}
        />
      )}

      {/* ═══════════════════════════════════════
          TRANSACTION LOG
         ═══════════════════════════════════════ */}
      {activeSection === 'log' && (
        <TransactionLog
          bookings={bookingsData || []}
          revenueEntries={revenueEntries}
          expenses={expensesData || []}
          creditNotes={creditNotes}
          terminology={terminology}
        />
      )}

      {/* ═══════════════════════════════════════
          INCOME (Revenue Ledger)
         ═══════════════════════════════════════ */}
      {activeSection === 'income' && <RevenueLedgerPanel />}

      {/* ═══════════════════════════════════════
          EXPENSES — flat, no sub-tabs
         ═══════════════════════════════════════ */}
      {activeSection === 'expenses' && <ExpensesSection />}

      {/* ═══════════════════════════════════════
          INVOICING — flat
         ═══════════════════════════════════════ */}
      {activeSection === 'invoicing' && <InvoicingSection />}

      {/* ═══════════════════════════════════════
          REPORTS — flat
         ═══════════════════════════════════════ */}
      {activeSection === 'reports' && <ReportsSection />}
    </div>
  );
}


/* ============================================
   OVERVIEW SECTION
   ============================================ */
function OverviewSection({ finances, insights, daily_revenue, maxRevenue, chartRange, setChartRange, formatDayLabel, terminology, onNavigate }) {
  const { total_revenue, paid_revenue, unpaid_revenue, manual_revenue, total_materials_cost, total_refunds, gross_profit, profit_margin, netCashFlow, totalExpenses, totalOutstanding } = finances;

  return (
    <div className="fin-overview">
      {/* Key Metrics Row */}
      <div className="fin-metrics">
        <div className="fin-metric fin-metric-primary">
          <div className="fin-metric-icon" style={{ background: 'rgba(99, 102, 241, 0.1)' }}>
            <i className="fas fa-euro-sign" style={{ color: '#6366f1' }}></i>
          </div>
          <div className="fin-metric-body">
            <span className="fin-metric-value">{formatCurrency(total_revenue)}</span>
            <span className="fin-metric-label">Total Revenue</span>
          </div>
        </div>
        <div className="fin-metric">
          <div className="fin-metric-icon" style={{ background: 'rgba(16, 185, 129, 0.1)' }}>
            <i className="fas fa-check-circle" style={{ color: '#10b981' }}></i>
          </div>
          <div className="fin-metric-body">
            <span className="fin-metric-value">{formatCurrency(paid_revenue)}</span>
            <span className="fin-metric-label">Collected</span>
          </div>
        </div>
        <div className="fin-metric fin-metric-clickable" onClick={() => onNavigate('invoicing')}>
          <div className="fin-metric-icon" style={{ background: 'rgba(245, 158, 11, 0.1)' }}>
            <i className="fas fa-clock" style={{ color: '#f59e0b' }}></i>
          </div>
          <div className="fin-metric-body">
            <span className="fin-metric-value">{formatCurrency(unpaid_revenue)}</span>
            <span className="fin-metric-label">Outstanding →</span>
          </div>
        </div>
        <div className="fin-metric">
          <div className="fin-metric-icon" style={{ background: netCashFlow >= 0 ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)' }}>
            <i className={`fas ${netCashFlow >= 0 ? 'fa-wallet' : 'fa-exclamation-triangle'}`} style={{ color: netCashFlow >= 0 ? '#10b981' : '#ef4444' }}></i>
          </div>
          <div className="fin-metric-body">
            <span className="fin-metric-value" style={{ color: netCashFlow >= 0 ? '#10b981' : '#ef4444' }}>{formatCurrency(netCashFlow)}</span>
            <span className="fin-metric-label">Net Cash Flow</span>
          </div>
        </div>
      </div>

      {/* Secondary metrics */}
      <div className="fin-metrics-secondary">
        {total_materials_cost > 0 && (
          <div className="fin-chip"><i className="fas fa-cubes"></i> Materials: {formatCurrency(total_materials_cost)}</div>
        )}
        {totalExpenses > 0 && (
          <div className="fin-chip fin-chip-clickable" onClick={() => onNavigate('expenses')}><i className="fas fa-receipt"></i> Expenses: {formatCurrency(totalExpenses)} →</div>
        )}
        {total_refunds > 0 && (
          <div className="fin-chip fin-chip-red"><i className="fas fa-undo"></i> Refunds: {formatCurrency(total_refunds)}</div>
        )}
        {manual_revenue > 0 && (
          <div className="fin-chip fin-chip-clickable" onClick={() => onNavigate('income')}><i className="fas fa-pen-to-square"></i> Manual Income: {formatCurrency(manual_revenue)} →</div>
        )}
        {gross_profit > 0 && (
          <div className="fin-chip" style={{ color: '#10b981' }}><i className="fas fa-arrow-trend-up"></i> Gross Profit: {formatCurrency(gross_profit)} ({profit_margin}%)</div>
        )}
        {totalOutstanding > 0 && (
          <div className="fin-chip fin-chip-warn fin-chip-clickable" onClick={() => onNavigate('invoicing')}>
            <i className="fas fa-hourglass-half"></i> Overdue: {formatCurrency(totalOutstanding)} →
          </div>
        )}
      </div>

      {/* Revenue Chart */}
      <div className="fin-card">
        <div className="fin-card-header">
          <h3><i className="fas fa-chart-line"></i> Revenue</h3>
          <div className="fin-range-toggle">
            {[{ key: 'month', label: 'Month' }, { key: 'year', label: 'Year' }, { key: 'all', label: 'All' }].map(opt => (
              <button key={opt.key} className={`fin-range-btn ${chartRange === opt.key ? 'active' : ''}`}
                onClick={() => setChartRange(opt.key)}>{opt.label}</button>
            ))}
          </div>
        </div>
        <RevenueChart daily_revenue={daily_revenue} maxRevenue={maxRevenue} formatDayLabel={formatDayLabel} />
      </div>

      {/* Insights + Breakdowns */}
      <div className="fin-insights-row">
        <div className="fin-insight"><span className="fin-insight-val">{insights.totalJobs}</span><span className="fin-insight-lbl">Total {terminology.jobs || 'Jobs'}</span></div>
        <div className="fin-insight"><span className="fin-insight-val">{formatCurrency(insights.avgJobValue)}</span><span className="fin-insight-lbl">Avg {terminology.job || 'Job'} Value</span></div>
        <div className="fin-insight"><span className="fin-insight-val">{insights.collectionRate.toFixed(0)}%</span><span className="fin-insight-lbl">Collection Rate</span></div>
      </div>

      {(insights.serviceBreakdown.length > 0 || insights.topCustomers.length > 0) && (
        <div className="fin-grid-2">
          {insights.serviceBreakdown.length > 0 && (
            <div className="fin-card">
              <div className="fin-card-header"><h3><i className="fas fa-chart-bar"></i> Revenue by Service</h3></div>
              <div className="service-bars">
                {insights.serviceBreakdown.slice(0, 6).map((svc, i) => {
                  const maxR = insights.serviceBreakdown[0]?.revenue || 1;
                  return (
                    <div key={i} className="service-bar-row">
                      <div className="service-bar-label">{svc.name}</div>
                      <div className="service-bar-track">
                        <div className="service-bar-fill" style={{ width: `${Math.max((svc.revenue / maxR) * 100, 3)}%` }} />
                      </div>
                      <div className="service-bar-value">{formatCurrency(svc.revenue)}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
          {insights.topCustomers.length > 0 && (
            <div className="fin-card">
              <div className="fin-card-header"><h3><i className="fas fa-users"></i> Top Customers</h3></div>
              <div className="top-customers-list">
                {insights.topCustomers.map((cust, i) => (
                  <div key={i} className="top-customer-row">
                    <div className="top-customer-rank">{i + 1}</div>
                    <div className="top-customer-info">
                      <div className="top-customer-name">{cust.name}</div>
                      <div className="top-customer-jobs">{cust.jobs} {cust.jobs !== 1 ? (terminology.jobs || 'jobs') : (terminology.job || 'job')}</div>
                    </div>
                    <div className="top-customer-revenue">{formatCurrency(cust.revenue)}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}


/* ============================================
   REVENUE CHART (extracted for reuse)
   ============================================ */
function RevenueChart({ daily_revenue, maxRevenue, formatDayLabel }) {
  if (!daily_revenue || daily_revenue.length === 0) {
    return (
      <div className="chart-empty">
        <i className="fas fa-chart-line"></i>
        <p>Revenue data will appear here as jobs are completed</p>
      </div>
    );
  }

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
  const width = 600, height = 180;
  const chartW = width - padding.left - padding.right;
  const chartH = height - padding.top - padding.bottom;

  const points = daily_revenue.map((item, i) => {
    const x = padding.left + (i / (daily_revenue.length - 1)) * chartW;
    const y = padding.top + chartH - (maxRevenue > 0 ? (item.revenue / maxRevenue) * chartH * 0.85 : 0);
    return { x, y, ...item };
  });

  const monotonePath = (pts) => {
    const n = pts.length;
    if (n < 2) return `M${pts[0].x},${pts[0].y}`;
    const dx = [], dy = [], m = [];
    for (let i = 0; i < n - 1; i++) { dx.push(pts[i + 1].x - pts[i].x); dy.push(pts[i + 1].y - pts[i].y); }
    const slopes = dx.map((d, i) => dy[i] / d);
    m.push(slopes[0]);
    for (let i = 1; i < n - 1; i++) { m.push(slopes[i - 1] * slopes[i] <= 0 ? 0 : (slopes[i - 1] + slopes[i]) / 2); }
    m.push(slopes[n - 2]);
    for (let i = 0; i < n - 1; i++) {
      if (Math.abs(slopes[i]) < 1e-6) { m[i] = 0; m[i + 1] = 0; } else {
        const alpha = m[i] / slopes[i], beta = m[i + 1] / slopes[i], s = alpha * alpha + beta * beta;
        if (s > 9) { const t = 3 / Math.sqrt(s); m[i] = t * alpha * slopes[i]; m[i + 1] = t * beta * slopes[i]; }
      }
    }
    let d = `M${pts[0].x},${pts[0].y}`;
    for (let i = 0; i < n - 1; i++) {
      const seg = dx[i] / 3;
      d += ` C${pts[i].x + seg},${pts[i].y + m[i] * seg} ${pts[i + 1].x - seg},${pts[i + 1].y - m[i + 1] * seg} ${pts[i + 1].x},${pts[i + 1].y}`;
    }
    return d;
  };

  const linePath = monotonePath(points);
  const bottomY = padding.top + chartH;
  const areaPath = `${linePath} L${points[points.length - 1].x},${bottomY} L${points[0].x},${bottomY} Z`;
  const gridLines = [0.25, 0.5, 0.75].map(pct => padding.top + chartH * (1 - pct * 0.85));
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
}


/* ============================================
   TRANSACTION LOG — unified timeline of all
   financial activity
   ============================================ */
function TransactionLog({ bookings, revenueEntries, expenses, creditNotes, terminology }) {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [filter, setFilter] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [showAddForm, setShowAddForm] = useState(false);
  const [direction, setDirection] = useState('in'); // 'in' = money in, 'out' = money out
  const [formData, setFormData] = useState({
    amount: '', category: 'walk_in', description: '', payment_method: 'cash',
    date: new Date().toISOString().split('T')[0], notes: ''
  });

  // Reset category when direction changes
  const handleDirectionChange = (dir) => {
    setDirection(dir);
    setFormData(prev => ({
      ...prev,
      category: dir === 'in' ? 'walk_in' : 'other',
    }));
  };

  const createIncomeMut = useMutation({
    mutationFn: createRevenueEntry,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['revenue-entries'] });
      queryClient.invalidateQueries({ queryKey: ['finances'] });
      queryClient.invalidateQueries({ queryKey: ['pnl-report'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      addToast('Income added', 'success');
      resetForm();
    },
    onError: (e) => addToast(e.response?.data?.error || 'Failed to add', 'error'),
  });

  const createExpenseMut = useMutation({
    mutationFn: createExpense,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expenses'] });
      queryClient.invalidateQueries({ queryKey: ['finances'] });
      queryClient.invalidateQueries({ queryKey: ['pnl-report'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      addToast('Expense added', 'success');
      resetForm();
    },
    onError: (e) => addToast(e.response?.data?.error || 'Failed to add', 'error'),
  });

  const markPaidMut = useMutation({
    mutationFn: (jobId) => updateBooking(jobId, { payment_status: 'paid', payment_method: 'manual' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bookings'] });
      queryClient.invalidateQueries({ queryKey: ['finances'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['invoice-aging'] });
      queryClient.invalidateQueries({ queryKey: ['revenue-entries'] });
      queryClient.invalidateQueries({ queryKey: ['pnl-report'] });
      addToast(`${terminology.job || 'Job'} marked as paid`, 'success');
    },
    onError: () => addToast('Failed to update', 'error'),
  });

  const unmarkPaidMut = useMutation({
    mutationFn: (jobId) => updateBooking(jobId, { payment_status: 'unpaid', payment_method: null }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bookings'] });
      queryClient.invalidateQueries({ queryKey: ['finances'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['invoice-aging'] });
      queryClient.invalidateQueries({ queryKey: ['revenue-entries'] });
      queryClient.invalidateQueries({ queryKey: ['pnl-report'] });
      addToast(`${terminology.job || 'Job'} marked as unpaid`, 'success');
    },
    onError: () => addToast('Failed to update', 'error'),
  });

  const resetForm = () => {
    setShowAddForm(false);
    setDirection('in');
    setFormData({ amount: '', category: 'walk_in', description: '', payment_method: 'cash', date: new Date().toISOString().split('T')[0], notes: '' });
  };

  // Build unified log
  const allEntries = useMemo(() => {
    const items = [];

    // Booked jobs
    (Array.isArray(bookings) ? bookings : []).forEach(b => {
      if (!b.charge || parseFloat(b.charge) <= 0 || b.status === 'cancelled') return;
      items.push({
        id: `job-${b.id}`,
        rawId: b.id,
        type: 'job',
        amount: parseFloat(b.charge || 0),
        description: b.service_type || b.service || (terminology.job || 'Job'),
        customer: b.customer_name || b.client_name || '',
        date: b.appointment_time ? (typeof b.appointment_time === 'string' ? b.appointment_time.split('T')[0] : new Date(b.appointment_time).toISOString().split('T')[0]) : '',
        payment_status: b.payment_status,
        payment_method: b.payment_method,
        status: b.status,
        direction: 'in',
      });
    });

    // Manual revenue entries
    (revenueEntries || []).forEach(e => {
      items.push({
        id: `rev-${e.id}`,
        rawId: e.id,
        type: 'manual_income',
        amount: e.amount || 0,
        description: e.description || getCatLabel(e.category),
        customer: e.notes || '',
        date: e.date ? e.date.split('T')[0] : '',
        payment_method: e.payment_method,
        category: e.category,
        direction: 'in',
      });
    });

    // Expenses
    (expenses || []).forEach(e => {
      items.push({
        id: `exp-${e.id}`,
        rawId: e.id,
        type: 'expense',
        amount: e.amount || 0,
        description: e.description || e.category || 'Expense',
        customer: e.vendor || '',
        date: e.date ? e.date.split('T')[0] : '',
        category: e.category,
        direction: 'out',
      });
    });

    // Credit notes / refunds
    (creditNotes || []).forEach(n => {
      items.push({
        id: `cn-${n.id}`,
        rawId: n.id,
        type: 'credit_note',
        amount: n.amount || 0,
        description: n.reason || 'Credit Note',
        customer: n.client_name || '',
        date: n.created_at ? (typeof n.created_at === 'string' ? n.created_at.split('T')[0] : new Date(n.created_at).toISOString().split('T')[0]) : '',
        credit_note_number: n.credit_note_number,
        stripe_refund: !!n.stripe_refund_id,
        direction: 'out',
      });
    });

    // Sort by date descending
    items.sort((a, b) => (b.date || '').localeCompare(a.date || ''));
    return items;
  }, [bookings, revenueEntries, expenses, creditNotes, terminology]);

  // Filter
  const filtered = useMemo(() => {
    let list = allEntries;
    if (filter === 'income') list = list.filter(e => e.direction === 'in');
    else if (filter === 'expenses') list = list.filter(e => e.direction === 'out');
    else if (filter === 'jobs') list = list.filter(e => e.type === 'job');
    else if (filter === 'manual') list = list.filter(e => e.type === 'manual_income');
    else if (filter === 'unpaid') list = list.filter(e => e.type === 'job' && e.payment_status !== 'paid');
    else if (filter === 'refunds') list = list.filter(e => e.type === 'credit_note');
    if (searchTerm) {
      const q = searchTerm.toLowerCase();
      list = list.filter(e => (e.description || '').toLowerCase().includes(q) || (e.customer || '').toLowerCase().includes(q));
    }
    return list;
  }, [allEntries, filter, searchTerm]);

  // Group by month
  const grouped = useMemo(() => {
    const groups = {};
    filtered.forEach(e => {
      const d = new Date((e.date || '') + 'T00:00:00');
      const key = isNaN(d) ? '0000-00' : `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
      const label = isNaN(d) ? 'Unknown' : d.toLocaleDateString('en-IE', { month: 'long', year: 'numeric' });
      if (!groups[key]) groups[key] = { key, label, items: [], income: 0, expense: 0 };
      groups[key].items.push(e);
      if (e.direction === 'in') groups[key].income += e.amount;
      else groups[key].expense += e.amount;
    });
    return Object.values(groups).sort((a, b) => b.key.localeCompare(a.key));
  }, [filtered]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!formData.amount || parseFloat(formData.amount) <= 0) { addToast('Enter a valid amount', 'warning'); return; }
    if (direction === 'in') {
      createIncomeMut.mutate(formData);
    } else {
      createExpenseMut.mutate({
        amount: formData.amount,
        category: formData.category,
        description: formData.description,
        vendor: formData.notes || '',
        date: formData.date,
        tax_deductible: true,
      });
    }
  };

  const isPending = createIncomeMut.isPending || createExpenseMut.isPending;

  const totals = useMemo(() => {
    const inc = filtered.filter(e => e.direction === 'in').reduce((s, e) => s + e.amount, 0);
    const exp = filtered.filter(e => e.direction === 'out').reduce((s, e) => s + e.amount, 0);
    return { income: inc, expense: exp, net: inc - exp };
  }, [filtered]);

  return (
    <div className="fin-log">
      {/* Header */}
      <div className="fin-log-header">
        <h2><i className="fas fa-list-ul"></i> Transaction Log</h2>
        <button className="acct-btn-primary" onClick={() => setShowAddForm(!showAddForm)}>
          <i className={`fas ${showAddForm ? 'fa-times' : 'fa-plus'}`}></i>
          {showAddForm ? 'Cancel' : 'Add Entry'}
        </button>
      </div>

      {/* Quick Add Form */}
      {showAddForm && (
        <form className="fin-log-form" onSubmit={handleSubmit}>
          {/* Money In / Out Toggle */}
          <div className="fin-direction-toggle">
            <button type="button" className={`fin-dir-btn in ${direction === 'in' ? 'active' : ''}`}
              onClick={() => handleDirectionChange('in')}>
              <i className="fas fa-arrow-down"></i> Money In
            </button>
            <button type="button" className={`fin-dir-btn out ${direction === 'out' ? 'active' : ''}`}
              onClick={() => handleDirectionChange('out')}>
              <i className="fas fa-arrow-up"></i> Money Out
            </button>
          </div>
          <div className="fin-log-form-grid">
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
                {direction === 'in'
                  ? REVENUE_CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)
                  : EXPENSE_CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)
                }
              </select>
            </div>
            <div className="acct-field">
              <label>Date</label>
              <input type="date" value={formData.date} onChange={e => setFormData({ ...formData, date: e.target.value })} />
            </div>
            {direction === 'in' && (
              <div className="acct-field">
                <label>Payment Method</label>
                <select value={formData.payment_method} onChange={e => setFormData({ ...formData, payment_method: e.target.value })}>
                  {PAYMENT_METHODS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
                </select>
              </div>
            )}
            <div className="acct-field" style={{ gridColumn: 'span 2' }}>
              <label>Description</label>
              <input type="text"
                placeholder={direction === 'in' ? 'e.g. Walk-in customer, cash payment...' : 'e.g. Refund to customer, supply purchase...'}
                value={formData.description}
                onChange={e => setFormData({ ...formData, description: e.target.value })} />
            </div>
          </div>
          <div className="fin-log-form-actions">
            <button type="button" className="acct-btn-secondary" onClick={resetForm}>Cancel</button>
            <button type="submit" className={`acct-btn-primary ${direction === 'out' ? 'fin-btn-expense' : ''}`} disabled={isPending}>
              <i className={`fas ${isPending ? 'fa-spinner fa-spin' : 'fa-check'}`}></i>
              {direction === 'in' ? 'Add Income' : 'Add Expense'}
            </button>
          </div>
        </form>
      )}

      {/* Summary Bar */}
      <div className="fin-log-summary">
        <span className="fin-log-summary-item" style={{ color: '#10b981' }}>
          <i className="fas fa-arrow-up"></i> {formatCurrency(totals.income)}
        </span>
        <span className="fin-log-summary-item" style={{ color: '#ef4444' }}>
          <i className="fas fa-arrow-down"></i> {formatCurrency(totals.expense)}
        </span>
        <span className="fin-log-summary-item" style={{ color: totals.net >= 0 ? '#10b981' : '#ef4444', fontWeight: 700 }}>
          Net: {formatCurrency(totals.net)}
        </span>
        <span className="fin-log-summary-count">{filtered.length} entries</span>
      </div>

      {/* Filters */}
      <div className="fin-log-toolbar">
        <div className="fin-log-filters">
          {[
            { key: 'all', label: 'All' },
            { key: 'income', label: 'Income' },
            { key: 'expenses', label: 'Expenses' },
            { key: 'jobs', label: terminology.jobs || 'Jobs' },
            { key: 'manual', label: 'Manual' },
            { key: 'unpaid', label: 'Unpaid' },
            { key: 'refunds', label: 'Refunds' },
          ].map(f => (
            <button key={f.key} className={`fin-filter-pill ${filter === f.key ? 'active' : ''}`}
              onClick={() => setFilter(f.key)}>{f.label}</button>
          ))}
        </div>
        <div className="dash-search" style={{ flex: 1, maxWidth: 260 }}>
          <i className="fas fa-search"></i>
          <input type="text" placeholder="Search..." value={searchTerm} onChange={e => setSearchTerm(e.target.value)} />
        </div>
      </div>

      {/* Log List */}
      <div className="fin-log-list">
        {filtered.length === 0 ? (
          <div className="acct-empty">
            <i className="fas fa-list-ul"></i>
            <p>No transactions found. Add income, expenses, or complete jobs to see them here.</p>
          </div>
        ) : grouped.map(group => (
          <div key={group.key} className="fin-log-group">
            <div className="fin-log-month">
              <span className="fin-log-month-label">{group.label}</span>
              <span className="fin-log-month-totals">
                <span style={{ color: '#10b981' }}>+{formatCurrency(group.income)}</span>
                {group.expense > 0 && <span style={{ color: '#ef4444' }}>-{formatCurrency(group.expense)}</span>}
              </span>
            </div>
            {group.items.map(entry => (
              <div key={entry.id} className={`fin-log-row ${entry.direction}`}>
                <div className={`fin-log-icon ${entry.direction}`}>
                  <i className={`fas ${getLogIcon(entry)}`}></i>
                </div>
                <div className="fin-log-content">
                  <div className="fin-log-title">
                    {entry.credit_note_number ? `${entry.credit_note_number} — ` : ''}{entry.description}
                  </div>
                  <div className="fin-log-meta">
                    {entry.customer && <span><i className="fas fa-user"></i> {entry.customer}</span>}
                    <span><i className="fas fa-calendar"></i> {formatDate(entry.date)}</span>
                    <span className={`fin-log-badge ${getBadgeClass(entry)}`}>{getBadgeLabel(entry)}</span>
                    {entry.type === 'job' && entry.payment_method && entry.payment_status === 'paid' && (
                      <span><i className="fas fa-credit-card"></i> {entry.payment_method}</span>
                    )}
                    {entry.type === 'credit_note' && entry.stripe_refund && (
                      <span><i className="fas fa-credit-card"></i> Stripe</span>
                    )}
                  </div>
                </div>
                <div className="fin-log-amount-col">
                  <span className={`fin-log-amount ${entry.direction}`}>
                    {entry.direction === 'in' ? '+' : '-'}{formatCurrency(entry.amount)}
                  </span>
                  {entry.type === 'job' && (
                    <button
                      className={`fin-log-pay-btn ${entry.payment_status === 'paid' ? 'paid' : 'unpaid'}`}
                      onClick={() => entry.payment_status === 'paid' ? unmarkPaidMut.mutate(entry.rawId) : markPaidMut.mutate(entry.rawId)}
                      disabled={markPaidMut.isPending || unmarkPaidMut.isPending}
                      title={entry.payment_status === 'paid' ? 'Mark as unpaid' : 'Mark as paid'}
                    >
                      <i className={`fas ${entry.payment_status === 'paid' ? 'fa-check-circle' : 'fa-circle'}`}></i>
                      {entry.payment_status === 'paid' ? 'Paid' : 'Mark Paid'}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

function getCatLabel(cat) {
  const found = REVENUE_CATEGORIES.find(c => c.value === cat);
  return found ? found.label : 'Income';
}

function getLogIcon(entry) {
  if (entry.type === 'job') return 'fa-calendar-check';
  if (entry.type === 'expense') return 'fa-receipt';
  if (entry.type === 'credit_note') return 'fa-undo';
  return 'fa-pen-to-square';
}

function getBadgeClass(entry) {
  if (entry.type === 'expense') return 'expense';
  if (entry.type === 'credit_note') return 'refund';
  if (entry.type === 'job' && entry.payment_status === 'paid') return 'paid';
  if (entry.type === 'job') return 'unpaid';
  return 'manual';
}

function getBadgeLabel(entry) {
  if (entry.type === 'expense') return 'Expense';
  if (entry.type === 'credit_note') return entry.stripe_refund ? 'Stripe Refund' : 'Credit Note';
  if (entry.type === 'job' && entry.payment_status === 'paid') return 'Paid';
  if (entry.type === 'job') return 'Unpaid';
  return 'Manual';
}


/* ============================================
   EXPENSES SECTION — flat, no sub-tabs
   Shows expenses panel with mileage & POs
   accessible via toggle, not nested tabs
   ============================================ */
function ExpensesSection() {
  const [view, setView] = useState('expenses');
  return (
    <div className="fin-section-flat">
      <div className="fin-section-switcher">
        <button className={view === 'expenses' ? 'active' : ''} onClick={() => setView('expenses')}>
          <i className="fas fa-receipt"></i> Expenses
        </button>
        <button className={view === 'mileage' ? 'active' : ''} onClick={() => setView('mileage')}>
          <i className="fas fa-car"></i> Mileage
        </button>
        <button className={view === 'purchase-orders' ? 'active' : ''} onClick={() => setView('purchase-orders')}>
          <i className="fas fa-file-export"></i> Purchase Orders
        </button>
      </div>
      {view === 'expenses' && <ExpensesPanel />}
      {view === 'mileage' && <MileagePanel />}
      {view === 'purchase-orders' && <PurchaseOrdersPanel />}
    </div>
  );
}

/* ============================================
   INVOICING SECTION — flat
   ============================================ */
function InvoicingSection() {
  const [view, setView] = useState('outstanding');
  return (
    <div className="fin-section-flat">
      <div className="fin-section-switcher">
        <button className={view === 'outstanding' ? 'active' : ''} onClick={() => setView('outstanding')}>
          <i className="fas fa-hourglass-half"></i> Outstanding
        </button>
        <button className={view === 'credits' ? 'active' : ''} onClick={() => setView('credits')}>
          <i className="fas fa-undo"></i> Credit Notes
        </button>
      </div>
      {view === 'outstanding' && <AgingPanel />}
      {view === 'credits' && <CreditNotesPanel />}
    </div>
  );
}

/* ============================================
   REPORTS SECTION — flat
   ============================================ */
function ReportsSection() {
  const [view, setView] = useState('pnl');
  return (
    <div className="fin-section-flat">
      <div className="fin-section-switcher">
        <button className={view === 'pnl' ? 'active' : ''} onClick={() => setView('pnl')}>
          <i className="fas fa-file-invoice-dollar"></i> Profit & Loss
        </button>
        <button className={view === 'tax' ? 'active' : ''} onClick={() => setView('tax')}>
          <i className="fas fa-cog"></i> Tax Settings
        </button>
      </div>
      {view === 'pnl' && <PnlPanel />}
      {view === 'tax' && <TaxSettings />}
    </div>
  );
}

export default FinancesTab;
