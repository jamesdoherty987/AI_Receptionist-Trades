import { useState, useMemo } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { formatCurrency } from '../../utils/helpers';
import { getPnlReport, createExpense, createCreditNote } from '../../services/api';
import { useToast } from '../Toast';
import LoadingSpinner from '../LoadingSpinner';

function PnlPanel() {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [period, setPeriod] = useState('year');
  const [showAdjustment, setShowAdjustment] = useState(false);
  const [adjustment, setAdjustment] = useState({ type: 'revenue', description: '', amount: '', category: 'other' });

  const { data: pnl, isLoading } = useQuery({
    queryKey: ['pnl-report', period],
    queryFn: async () => (await getPnlReport(period)).data,
    staleTime: 30000,
  });

  const chartData = useMemo(() => {
    if (!pnl?.monthly_pnl || pnl.monthly_pnl.length === 0) return null;
    const maxVal = Math.max(...pnl.monthly_pnl.map(m => Math.max(m.revenue, m.total_costs || m.expenses || 0)), 1);
    return { months: pnl.monthly_pnl, maxVal };
  }, [pnl]);

  const formatMonth = (m) => {
    const [y, mo] = m.split('-');
    const d = new Date(parseInt(y), parseInt(mo) - 1);
    return d.toLocaleDateString('en-US', { month: 'short', year: '2-digit' });
  };

  if (isLoading) return <LoadingSpinner message="Generating P&L report..." />;

  if (!pnl) return (
    <div className="acct-panel">
      <div className="acct-empty">
        <i className="fas fa-file-invoice-dollar"></i>
        <p>No financial data yet. Complete some jobs and log expenses to see your P&L.</p>
      </div>
    </div>
  );

  const isProfit = pnl.net_profit >= 0;
  const netRevenue = pnl.net_revenue ?? (pnl.total_revenue - (pnl.total_credits || 0));
  const grossProfit = pnl.gross_profit ?? (netRevenue - pnl.total_materials);
  const grossMargin = pnl.gross_margin ?? (netRevenue > 0 ? (grossProfit / netRevenue * 100).toFixed(1) : 0);

  return (
    <div className="acct-panel">
      {/* Period Selector */}
      <div className="acct-toolbar acct-toolbar-spread">
        <h3 className="acct-panel-title"><i className="fas fa-file-invoice-dollar"></i> Profit & Loss Statement</h3>
        <div className="acct-toolbar-group">
          <div className="acct-filter-pills">
            {[
              { key: 'month', label: 'This Month' },
              { key: 'quarter', label: 'Quarter' },
              { key: 'year', label: 'This Year' },
              { key: 'all', label: 'All Time' },
            ].map(p => (
              <button key={p.key} className={`acct-pill ${period === p.key ? 'active' : ''}`}
                onClick={() => setPeriod(p.key)}>{p.label}</button>
            ))}
          </div>
          <button className="acct-btn-secondary" title="Export CSV"
            onClick={() => {
              const rows = [['Month', 'Revenue', 'Credits', 'Net Revenue', 'Materials', 'Gross Profit', 'Expenses', 'Mileage', 'Total Costs', 'Net Profit']];
              (pnl.monthly_pnl || []).forEach(m => rows.push([m.month, m.revenue, 0, m.revenue, m.materials || 0, m.gross_profit || 0, m.expenses, m.mileage || 0, m.total_costs || m.expenses, m.net_profit]));
              rows.push(['Total', pnl.total_revenue, pnl.total_credits || 0, netRevenue, pnl.total_materials, grossProfit, pnl.total_expenses, pnl.total_mileage || 0, pnl.total_costs, pnl.net_profit]);
              const csv = rows.map(r => r.join(',')).join('\n');
              const blob = new Blob([csv], { type: 'text/csv' });
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a'); a.href = url; a.download = `pnl-${period}-${new Date().toISOString().split('T')[0]}.csv`; a.click();
              URL.revokeObjectURL(url);
            }}>
            <i className="fas fa-download"></i> Export
          </button>
        </div>
      </div>

      {/* Manual Adjustment */}
      <div className="acct-section">
        <div className="acct-section-header">
          <h3><i className="fas fa-pen"></i> Adjustments</h3>
          <button className="acct-btn-secondary" onClick={() => setShowAdjustment(!showAdjustment)}>
            <i className={`fas ${showAdjustment ? 'fa-times' : 'fa-plus'}`}></i>
            {showAdjustment ? 'Cancel' : 'Add'}
          </button>
        </div>
        {showAdjustment && (
          <div className="acct-form" style={{ borderLeftColor: adjustment.type === 'credit' ? '#ef4444' : adjustment.type === 'expense' ? '#f59e0b' : '#10b981' }}>
            <div className="acct-form-grid">
              <div className="acct-field">
                <label>Adjustment Type</label>
                <select value={adjustment.type} onChange={e => setAdjustment({ ...adjustment, type: e.target.value })}>
                  <option value="expense">Add Expense</option>
                  <option value="credit">Add Credit Note / Refund</option>
                  <option value="revenue">Additional Revenue</option>
                </select>
              </div>
              {adjustment.type === 'expense' && (
                <div className="acct-field">
                  <label>Category</label>
                  <select value={adjustment.category} onChange={e => setAdjustment({ ...adjustment, category: e.target.value })}>
                    <option value="other">Other</option>
                    <option value="tools">Tools & Equipment</option>
                    <option value="materials">Materials & Supplies</option>
                    <option value="vehicle">Vehicle Maintenance</option>
                    <option value="fuel">Fuel & Mileage</option>
                    <option value="insurance">Insurance</option>
                    <option value="software">Software & Subscriptions</option>
                    <option value="office">Office & Admin</option>
                    <option value="marketing">Marketing</option>
                    <option value="training">Training</option>
                    <option value="utilities">Utilities & Rent</option>
                    <option value="subcontractor">Subcontractors</option>
                  </select>
                </div>
              )}
              <div className="acct-field">
                <label>Description</label>
                <input type="text" value={adjustment.description} onChange={e => setAdjustment({ ...adjustment, description: e.target.value })}
                  placeholder={adjustment.type === 'credit' ? 'e.g. Refund for cancelled job, Discount given...' : adjustment.type === 'revenue' ? 'e.g. Cash payment, Side job income...' : 'e.g. New drill, Office supplies...'} />
              </div>
              <div className="acct-field">
                <label>Amount (€)</label>
                <input type="number" min="0" step="0.01" value={adjustment.amount} onChange={e => setAdjustment({ ...adjustment, amount: e.target.value })} placeholder="0.00" />
              </div>
              <div className="acct-field">
                <label>Date</label>
                <input type="date" value={adjustment.date || new Date().toISOString().split('T')[0]} onChange={e => setAdjustment({ ...adjustment, date: e.target.value })} />
              </div>
            </div>
            <div className="acct-form-actions">
              <button className="acct-btn-secondary" onClick={() => setShowAdjustment(false)}>Cancel</button>
              <button className="acct-btn-primary" disabled={!adjustment.description.trim() || !adjustment.amount}
                onClick={() => {
                  const amt = parseFloat(adjustment.amount);
                  const date = adjustment.date || new Date().toISOString().split('T')[0];
                  const done = () => {
                    queryClient.invalidateQueries({ queryKey: ['pnl-report'] });
                    queryClient.invalidateQueries({ queryKey: ['expenses'] });
                    queryClient.invalidateQueries({ queryKey: ['credit-notes'] });
                    setShowAdjustment(false);
                    setAdjustment({ type: 'revenue', description: '', amount: '', category: 'other', date: '' });
                  };

                  if (adjustment.type === 'credit') {
                    createCreditNote({
                      reason: adjustment.description,
                      amount: amt,
                      date,
                    }).then(() => { addToast('Credit note added', 'success'); done(); })
                      .catch(() => addToast('Failed to add credit note', 'error'));
                  } else if (adjustment.type === 'expense') {
                    createExpense({
                      amount: amt, category: adjustment.category,
                      description: adjustment.description, vendor: '',
                      date, tax_deductible: true,
                    }).then(() => { addToast('Expense added', 'success'); done(); })
                      .catch(() => addToast('Failed to add expense', 'error'));
                  } else {
                    createExpense({
                      amount: -Math.abs(amt), category: 'other',
                      description: `[Additional Revenue] ${adjustment.description}`, vendor: '',
                      date, tax_deductible: false,
                    }).then(() => { addToast('Revenue adjustment added', 'success'); done(); })
                      .catch(() => addToast('Failed to add adjustment', 'error'));
                  }
                }}>
                <i className="fas fa-check"></i> Add
              </button>
            </div>
          </div>
        )}
        {!showAdjustment && (
          <p style={{ fontSize: '0.75rem', color: '#94a3b8', margin: 0 }}>
            Add expenses, credit notes/refunds, or additional revenue not captured by jobs.
          </p>
        )}
      </div>

      {/* P&L Statement — Proper accounting format */}
      <div className="acct-section">
        <div className="acct-section-header"><h3><i className="fas fa-file-alt"></i> Income Statement</h3></div>
        <div className="pnl-statement">
          {/* Revenue Section */}
          <div className="pnl-line pnl-line-header">Revenue</div>
          <div className="pnl-line">
            <span>Job Revenue</span>
            <span>{formatCurrency(pnl.total_revenue)}</span>
          </div>
          {(pnl.total_credits || 0) > 0 && (
            <div className="pnl-line pnl-line-deduct">
              <span>Less: Credit Notes / Refunds</span>
              <span>({formatCurrency(pnl.total_credits)})</span>
            </div>
          )}
          <div className="pnl-line pnl-line-subtotal">
            <span>Net Revenue</span>
            <span>{formatCurrency(netRevenue)}</span>
          </div>

          {/* Cost of Sales */}
          <div className="pnl-line pnl-line-header acct-mt-sm">Cost of Sales</div>
          <div className="pnl-line">
            <span>Materials & Supplies</span>
            <span>({formatCurrency(pnl.total_materials)})</span>
          </div>
          <div className="pnl-line pnl-line-subtotal pnl-line-gross">
            <span>Gross Profit</span>
            <span style={{ color: grossProfit >= 0 ? '#10b981' : '#ef4444' }}>
              {formatCurrency(grossProfit)}
              <span className="pnl-margin-badge">{grossMargin}%</span>
            </span>
          </div>

          {/* Operating Expenses */}
          <div className="pnl-line pnl-line-header acct-mt-sm">Operating Expenses</div>
          {pnl.expense_categories && pnl.expense_categories.length > 0 ? (
            pnl.expense_categories.map((cat, i) => (
              <div key={i} className="pnl-line pnl-line-indent">
                <span style={{ textTransform: 'capitalize' }}>{cat.category.replace(/_/g, ' ')}</span>
                <span>({formatCurrency(cat.total)})</span>
              </div>
            ))
          ) : (
            <div className="pnl-line pnl-line-indent">
              <span>General Expenses</span>
              <span>({formatCurrency(pnl.total_expenses)})</span>
            </div>
          )}
          {(pnl.total_mileage || 0) > 0 && (
            <div className="pnl-line pnl-line-indent">
              <span>Mileage Deductions</span>
              <span>({formatCurrency(pnl.total_mileage)})</span>
            </div>
          )}
          <div className="pnl-line pnl-line-subtotal">
            <span>Total Operating Expenses</span>
            <span>({formatCurrency(pnl.total_expenses + (pnl.total_mileage || 0))})</span>
          </div>

          {/* Net Profit */}
          <div className={`pnl-line pnl-line-total ${isProfit ? 'pnl-line-profit' : 'pnl-line-loss'}`}>
            <span>Net {isProfit ? 'Profit' : 'Loss'}</span>
            <span>
              {formatCurrency(pnl.net_profit)}
              <span className="pnl-margin-badge">{pnl.profit_margin}%</span>
            </span>
          </div>
        </div>
      </div>

      {/* Visual Summary Cards */}
      <div className="pnl-summary">
        <div className="pnl-card pnl-revenue">
          <div className="pnl-card-header"><i className="fas fa-arrow-trend-up"></i><span>Revenue</span></div>
          <div className="pnl-card-value">{formatCurrency(netRevenue)}</div>
          {(pnl.total_credits || 0) > 0 && <div className="pnl-card-breakdown"><span>Before credits: {formatCurrency(pnl.total_revenue)}</span></div>}
        </div>
        <div className="pnl-operator">−</div>
        <div className="pnl-card pnl-costs">
          <div className="pnl-card-header"><i className="fas fa-arrow-trend-down"></i><span>Total Costs</span></div>
          <div className="pnl-card-value">{formatCurrency(pnl.total_costs)}</div>
          <div className="pnl-card-breakdown">
            <span><i className="fas fa-cubes"></i> Materials: {formatCurrency(pnl.total_materials)}</span>
            <span><i className="fas fa-receipt"></i> Expenses: {formatCurrency(pnl.total_expenses)}</span>
            {(pnl.total_mileage || 0) > 0 && <span><i className="fas fa-car"></i> Mileage: {formatCurrency(pnl.total_mileage)}</span>}
          </div>
        </div>
        <div className="pnl-operator">=</div>
        <div className={`pnl-card ${isProfit ? 'pnl-profit' : 'pnl-loss'}`}>
          <div className="pnl-card-header"><i className={`fas ${isProfit ? 'fa-chart-line' : 'fa-chart-line-down'}`}></i><span>Net {isProfit ? 'Profit' : 'Loss'}</span></div>
          <div className="pnl-card-value">{formatCurrency(pnl.net_profit)}</div>
          <div className="pnl-card-breakdown"><span>{pnl.profit_margin}% margin</span></div>
        </div>
      </div>

      {/* Monthly Chart */}
      {chartData && chartData.months.length > 1 && (
        <div className="acct-section">
          <div className="acct-section-header"><h3><i className="fas fa-chart-bar"></i> Monthly Trend</h3></div>
          <div className="pnl-chart">
            {chartData.months.map((m, i) => {
              const revH = (m.revenue / chartData.maxVal) * 100;
              const costH = ((m.total_costs || m.expenses || 0) / chartData.maxVal) * 100;
              return (
                <div key={i} className="pnl-chart-col">
                  <div className="pnl-chart-bars">
                    <div className="pnl-chart-bar pnl-bar-revenue" style={{ height: `${Math.max(revH, 2)}%` }}
                      title={`Revenue: ${formatCurrency(m.revenue)}`}></div>
                    <div className="pnl-chart-bar pnl-bar-expense" style={{ height: `${Math.max(costH, (m.total_costs || m.expenses) > 0 ? 2 : 0)}%` }}
                      title={`Costs: ${formatCurrency(m.total_costs || m.expenses)}`}></div>
                  </div>
                  <div className="pnl-chart-label">{formatMonth(m.month)}</div>
                </div>
              );
            })}
          </div>
          <div className="pnl-chart-legend">
            <span><span className="pnl-legend-dot" style={{ background: '#6366f1' }}></span> Revenue</span>
            <span><span className="pnl-legend-dot" style={{ background: '#ef4444' }}></span> Costs</span>
          </div>
        </div>
      )}

      {/* Expense Category Breakdown */}
      {pnl.expense_categories && pnl.expense_categories.length > 0 && (
        <div className="acct-section">
          <div className="acct-section-header"><h3><i className="fas fa-chart-pie"></i> Expense Breakdown</h3></div>
          <div className="acct-category-bars">
            {pnl.expense_categories.map((cat, i) => {
              const totalExp = pnl.total_expenses + (pnl.total_mileage || 0);
              const pct = totalExp > 0 ? (cat.total / totalExp) * 100 : 0;
              return (
                <div key={i} className="acct-bar-row">
                  <div className="acct-bar-label" style={{ textTransform: 'capitalize' }}>{cat.category.replace(/_/g, ' ')}</div>
                  <div className="acct-bar-track">
                    <div className="acct-bar-fill" style={{ width: `${Math.max(pct, 3)}%`, background: '#ef4444' }}></div>
                  </div>
                  <div className="acct-bar-value">{formatCurrency(cat.total)} <span style={{ color: '#94a3b8', fontSize: '0.7rem' }}>({pct.toFixed(0)}%)</span></div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Monthly Detail Table */}
      {chartData && chartData.months.length > 0 && (
        <div className="acct-section">
          <div className="acct-section-header"><h3><i className="fas fa-table"></i> Monthly Detail</h3></div>
          <div className="pnl-table-wrap">
            <table className="pnl-table">
              <thead>
                <tr>
                  <th>Month</th>
                  <th style={{ textAlign: 'right' }}>Revenue</th>
                  <th style={{ textAlign: 'right' }}>Materials</th>
                  <th style={{ textAlign: 'right' }}>Gross Profit</th>
                  <th style={{ textAlign: 'right' }}>Expenses</th>
                  <th style={{ textAlign: 'right' }}>Net Profit</th>
                </tr>
              </thead>
              <tbody>
                {chartData.months.map((m, i) => (
                  <tr key={i}>
                    <td>{formatMonth(m.month)}</td>
                    <td style={{ textAlign: 'right', color: '#10b981' }}>{formatCurrency(m.revenue)}</td>
                    <td style={{ textAlign: 'right', color: '#94a3b8' }}>{formatCurrency(m.materials || 0)}</td>
                    <td style={{ textAlign: 'right', color: (m.gross_profit || 0) >= 0 ? '#10b981' : '#ef4444', fontWeight: 600 }}>
                      {formatCurrency(m.gross_profit || (m.revenue - (m.materials || 0)))}
                    </td>
                    <td style={{ textAlign: 'right', color: '#ef4444' }}>{formatCurrency(m.expenses + (m.mileage || 0))}</td>
                    <td style={{ textAlign: 'right', fontWeight: 700, color: m.net_profit >= 0 ? '#10b981' : '#ef4444' }}>
                      {formatCurrency(m.net_profit)}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <td style={{ fontWeight: 700 }}>Total</td>
                  <td style={{ textAlign: 'right', fontWeight: 700, color: '#10b981' }}>{formatCurrency(netRevenue)}</td>
                  <td style={{ textAlign: 'right', fontWeight: 700, color: '#94a3b8' }}>{formatCurrency(pnl.total_materials)}</td>
                  <td style={{ textAlign: 'right', fontWeight: 700, color: grossProfit >= 0 ? '#10b981' : '#ef4444' }}>{formatCurrency(grossProfit)}</td>
                  <td style={{ textAlign: 'right', fontWeight: 700, color: '#ef4444' }}>{formatCurrency(pnl.total_expenses + (pnl.total_mileage || 0))}</td>
                  <td style={{ textAlign: 'right', fontWeight: 700, color: isProfit ? '#10b981' : '#ef4444' }}>{formatCurrency(pnl.net_profit)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

export default PnlPanel;
