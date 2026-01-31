import { useState, useMemo } from 'react';
import { useMutation } from '@tanstack/react-query';
import { formatCurrency, formatDateTime } from '../../utils/helpers';
import { sendInvoice } from '../../services/api';
import { useToast } from '../Toast';
import './FinancesTab.css';

function FinancesTab({ finances }) {
  const [showAll, setShowAll] = useState(false);
  const [sendingInvoice, setSendingInvoice] = useState(null);
  const { addToast } = useToast();

  const {
    total_revenue = 0,
    paid_revenue = 0,
    unpaid_revenue = 0,
    pending_revenue = 0,
    completed_revenue = 0,
    transactions = [],
    monthly_revenue = []
  } = finances;

  // Calculate collected amount (either paid_revenue or completed_revenue)
  const collected = paid_revenue || completed_revenue || 0;
  // Calculate outstanding (either unpaid_revenue or pending_revenue)
  const outstanding = unpaid_revenue || pending_revenue || 0;

  // Filter for unpaid transactions
  const unpaidTransactions = useMemo(() => {
    if (!transactions) return [];
    return transactions.filter(t => 
      t.status !== 'completed' && 
      t.payment_status !== 'paid' &&
      t.status !== 'cancelled'
    );
  }, [transactions]);

  // Calculate max revenue for chart scaling
  const maxRevenue = useMemo(() => {
    if (!monthly_revenue || monthly_revenue.length === 0) return 0;
    return Math.max(...monthly_revenue.map(m => m.revenue));
  }, [monthly_revenue]);

  const displayedTransactions = showAll ? transactions : unpaidTransactions;

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
    if (!transaction.booking_id && !transaction.id) {
      addToast('Cannot send invoice: No booking ID found', 'warning');
      return;
    }
    const bookingId = transaction.booking_id || transaction.id;
    invoiceMutation.mutate(bookingId);
  };

  return (
    <div className="finances-tab">
      {/* Revenue Cards */}
      <div className="revenue-grid">
        <div className="revenue-card">
          <div className="revenue-icon" style={{ background: 'rgba(59, 130, 246, 0.1)' }}>
            <i className="fas fa-euro-sign" style={{ color: 'var(--accent-blue)' }}></i>
          </div>
          <div className="revenue-content">
            <div className="revenue-value">{formatCurrency(total_revenue)}</div>
            <div className="revenue-label">Total Revenue</div>
          </div>
        </div>
        <div className="revenue-card">
          <div className="revenue-icon" style={{ background: 'rgba(16, 185, 129, 0.1)' }}>
            <i className="fas fa-check-circle" style={{ color: 'var(--success)' }}></i>
          </div>
          <div className="revenue-content">
            <div className="revenue-value">{formatCurrency(collected)}</div>
            <div className="revenue-label">Collected</div>
          </div>
        </div>
        <div className="revenue-card">
          <div className="revenue-icon" style={{ background: 'rgba(245, 158, 11, 0.1)' }}>
            <i className="fas fa-clock" style={{ color: 'var(--warning)' }}></i>
          </div>
          <div className="revenue-content">
            <div className="revenue-value">{formatCurrency(outstanding)}</div>
            <div className="revenue-label">Outstanding</div>
          </div>
        </div>
      </div>

      {/* Monthly Revenue Chart */}
      {monthly_revenue && monthly_revenue.length > 0 && (
        <div className="chart-section">
          <h3><i className="fas fa-chart-bar"></i> Monthly Revenue</h3>
          <div className="chart-container">
            {monthly_revenue.map((item, index) => {
              const heightPercent = maxRevenue > 0 ? (item.revenue / maxRevenue) * 100 : 0;
              return (
                <div key={index} className="chart-bar-wrapper">
                  <div className="chart-bar-value">{formatCurrency(item.revenue)}</div>
                  <div className="chart-bar-container">
                    <div 
                      className="chart-bar"
                      style={{ height: `${heightPercent}%` }}
                    ></div>
                  </div>
                  <div className="chart-bar-label">{item.month}</div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Unpaid Transactions */}
      {transactions && transactions.length > 0 && (
        <div className="transactions-section">
          <div className="section-header">
            <h3>
              <i className="fas fa-file-invoice-dollar"></i> 
              {showAll ? 'All Transactions' : `Unpaid (${unpaidTransactions.length})`}
            </h3>
            <button 
              className="btn btn-secondary btn-sm"
              onClick={() => setShowAll(!showAll)}
            >
              <i className={`fas fa-${showAll ? 'filter' : 'list'}`}></i>
              {showAll ? 'Show Unpaid Only' : 'Show All History'}
            </button>
          </div>
          <div className="transactions-list">
            {displayedTransactions.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-icon">✅</div>
                <p>All invoices paid!</p>
              </div>
            ) : (
              displayedTransactions.map((transaction, index) => {
                const isUnpaid = transaction.status !== 'completed' && 
                                 transaction.payment_status !== 'paid' &&
                                 transaction.status !== 'cancelled';
                const bookingId = transaction.booking_id || transaction.id;
                const isSending = sendingInvoice === bookingId;
                
                return (
                  <div key={index} className="transaction-card">
                    <div className="transaction-main">
                      <div className="transaction-customer">
                        <div className="customer-avatar">
                          {transaction.customer_name?.charAt(0) || '?'}
                        </div>
                        <div className="customer-info">
                          <h4>{transaction.customer_name || 'Unknown'}</h4>
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
                        <div className="transaction-amount">
                          {formatCurrency(transaction.amount)}
                        </div>
                        <span className={`badge badge-${
                          transaction.status === 'completed' || transaction.payment_status === 'paid' 
                            ? 'success' 
                            : 'warning'
                        }`}>
                          {transaction.payment_status || transaction.status}
                        </span>
                        {isUnpaid && transaction.amount > 0 && (
                          <button 
                            className="btn-send-invoice"
                            onClick={(e) => handleSendInvoice(transaction, e)}
                            disabled={isSending}
                            title="Send invoice email"
                          >
                            <i className={`fas ${isSending ? 'fa-spinner fa-spin' : 'fa-paper-plane'}`}></i>
                            {isSending ? 'Sending...' : 'Send Invoice'}
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
      )}

      {/* Empty State */}
      {(!transactions || transactions.length === 0) && (!monthly_revenue || monthly_revenue.length === 0) && (
        <div className="empty-state">
          <div className="empty-state-icon">💰</div>
          <p>No financial data available</p>
        </div>
      )}
    </div>
  );
}

export default FinancesTab;
