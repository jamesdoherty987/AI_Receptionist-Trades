import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { formatCurrency } from '../../utils/helpers';
import { getPnlReport } from '../../services/api';
import LoadingSpinner from '../LoadingSpinner';

function PnlPanel() {
  const [period, setPeriod] = useState('year');

  const { data: pnl, isLoading } = useQuery({
    queryKey: ['pnl-report', period],
    queryFn: async () => (await getPnlReport(period)).data,
    staleTime: 30000,
  });

  const chartData = useMemo(() => {
    if (!pnl?.monthly_pnl || pnl.monthly_pnl.length === 0) return null;
    const maxVal = Math.max(...pnl.monthly_pnl.map(m => Math.max(m.revenue, m.expenses)), 1);
    return { months: pnl.monthly_pnl, maxVal };
  }, [pnl]);

  const formatMonth = (m) => {
    const [y, mo] = m.split('-');
    const d = new Date(parseInt(y), parseInt(mo) - 1);
    return d.toLocaleDateString('en-US', { month: 'short', year: '2-digit' });
  };

  if (isLoading) return <LoadingSpinner message="Generating P&L report..." />;
  if (!pnl) return null;

  const isProfit = pnl.net_profit >= 0;

  return (
    <div className="acct-panel">
      {/* Period Selector */}
      <div className="acct-toolbar" style={{ justifyContent: 'space-between' }}>
        <h3 className="acct-panel-title"><i className="fas fa-file-invoice-dollar"></i> Profit & Loss Statement</h3>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <div className="acct-filter-pills">
            {[
              { key: 'month', label: 'This Month' },
              { key: 'quarter', label: 'This Quarter' },
              { key: 'year', label: 'This Year' },
              { key: 'all', label: 'All Time' },
            ].map(p => (
              <button key={p.key} className={`acct-pill ${period === p.key ? 'active' : ''}`}
                onClick={() => setPeriod(p.key)}>{p.label}</button>
            ))}
          </div>
          {pnl && (
            <button className="acct-btn-secondary" title="Export CSV" style={{ padding: '0.4rem 0.6rem', fontSize: '0.78rem' }}
              onClick={() => {
                const rows = [['Month', 'Revenue', 'Expenses', 'Net Profit']];
                (pnl.monthly_pnl || []).forEach(m => rows.push([m.month, m.revenue, m.expenses, m.net_profit]));
                rows.push(['Total', pnl.total_revenue, pnl.total_expenses, pnl.net_profit]);
                const csv = rows.map(r => r.join(',')).join('\n');
                const blob = new Blob([csv], { type: 'text/csv' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a'); a.href = url; a.download = `pnl-${period}-${new Date().toISOString().split('T')[0]}.csv`; a.click();
                URL.revokeObjectURL(url);
              }}>
              <i className="fas fa-download"></i> Export
            </button>
          )}
        </div>
      </div>

      {/* Summary Cards */}
      <div className="pnl-summary">
        <div className="pnl-card pnl-revenue">
          <div className="pnl-card-header">
            <i className="fas fa-arrow-trend-up"></i>
            <span>Revenue</span>
          </div>
          <div className="pnl-card-value">{formatCurrency(pnl.total_revenue)}</div>
        </div>
        <div className="pnl-operator">−</div>
        <div className="pnl-card pnl-costs">
          <div className="pnl-card-header">
            <i className="fas fa-arrow-trend-down"></i>
            <span>Total Costs</span>
          </div>
          <div className="pnl-card-value">{formatCurrency(pnl.total_costs)}</div>
          <div className="pnl-card-breakdown">
            <span><i className="fas fa-cubes"></i> Materials: {formatCurrency(pnl.total_materials)}</span>
            <span><i className="fas fa-receipt"></i> Expenses: {formatCurrency(pnl.total_expenses)}</span>
          </div>
        </div>
        <div className="pnl-operator">=</div>
        <div className={`pnl-card ${isProfit ? 'pnl-profit' : 'pnl-loss'}`}>
          <div className="pnl-card-header">
            <i className={`fas ${isProfit ? 'fa-chart-line' : 'fa-chart-line-down'}`}></i>
            <span>Net {isProfit ? 'Profit' : 'Loss'}</span>
          </div>
          <div className="pnl-card-value">{formatCurrency(pnl.net_profit)}</div>
          <div className="pnl-card-breakdown">
            <span>{pnl.profit_margin}% margin</span>
          </div>
        </div>
      </div>

      {/* Monthly Chart */}
      {chartData && chartData.months.length > 1 && (
        <div className="acct-section">
          <div className="acct-section-header"><h3><i className="fas fa-chart-bar"></i> Monthly Breakdown</h3></div>
          <div className="pnl-chart">
            {chartData.months.map((m, i) => {
              const revH = (m.revenue / chartData.maxVal) * 100;
              const expH = (m.expenses / chartData.maxVal) * 100;
              return (
                <div key={i} className="pnl-chart-col">
                  <div className="pnl-chart-bars">
                    <div className="pnl-chart-bar pnl-bar-revenue" style={{ height: `${Math.max(revH, 2)}%` }}
                      title={`Revenue: ${formatCurrency(m.revenue)}`}></div>
                    <div className="pnl-chart-bar pnl-bar-expense" style={{ height: `${Math.max(expH, m.expenses > 0 ? 2 : 0)}%` }}
                      title={`Expenses: ${formatCurrency(m.expenses)}`}></div>
                  </div>
                  <div className="pnl-chart-label">{formatMonth(m.month)}</div>
                </div>
              );
            })}
          </div>
          <div className="pnl-chart-legend">
            <span><span className="pnl-legend-dot" style={{ background: '#6366f1' }}></span> Revenue</span>
            <span><span className="pnl-legend-dot" style={{ background: '#ef4444' }}></span> Expenses</span>
          </div>
        </div>
      )}

      {/* Expense Category Breakdown */}
      {pnl.expense_categories && pnl.expense_categories.length > 0 && (
        <div className="acct-section">
          <div className="acct-section-header"><h3><i className="fas fa-pie-chart"></i> Expense Breakdown</h3></div>
          <div className="acct-category-bars">
            {pnl.expense_categories.map((cat, i) => {
              const pct = pnl.total_expenses > 0 ? (cat.total / pnl.total_expenses) * 100 : 0;
              return (
                <div key={i} className="acct-bar-row">
                  <div className="acct-bar-label" style={{ textTransform: 'capitalize' }}>{cat.category}</div>
                  <div className="acct-bar-track">
                    <div className="acct-bar-fill" style={{ width: `${Math.max(pct, 3)}%`, background: '#ef4444' }}></div>
                  </div>
                  <div className="acct-bar-value">{formatCurrency(cat.total)} <span style={{ color: '#94a3b8', fontSize: '0.7rem' }}>({cat.count})</span></div>
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
                  <th style={{ textAlign: 'right' }}>Expenses</th>
                  <th style={{ textAlign: 'right' }}>Net Profit</th>
                </tr>
              </thead>
              <tbody>
                {chartData.months.map((m, i) => (
                  <tr key={i}>
                    <td>{formatMonth(m.month)}</td>
                    <td style={{ textAlign: 'right', color: '#10b981' }}>{formatCurrency(m.revenue)}</td>
                    <td style={{ textAlign: 'right', color: '#ef4444' }}>{formatCurrency(m.expenses)}</td>
                    <td style={{ textAlign: 'right', fontWeight: 700, color: m.net_profit >= 0 ? '#10b981' : '#ef4444' }}>
                      {formatCurrency(m.net_profit)}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <td style={{ fontWeight: 700 }}>Total</td>
                  <td style={{ textAlign: 'right', fontWeight: 700, color: '#10b981' }}>{formatCurrency(pnl.total_revenue)}</td>
                  <td style={{ textAlign: 'right', fontWeight: 700, color: '#ef4444' }}>{formatCurrency(pnl.total_expenses)}</td>
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
