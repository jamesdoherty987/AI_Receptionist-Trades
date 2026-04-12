import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import Modal from './Modal';
import { formatCurrency } from '../../utils/helpers';
import { getTaxSettings } from '../../services/api';
import DocumentPreview from '../accounting/DocumentPreview';
import './InvoiceConfirmModal.css';

function InvoiceConfirmModal({ isOpen, onClose, onConfirm, job, invoiceConfig, isPending }) {
  const [editableData, setEditableData] = useState({
    customer_name: '', phone: '', email: '', service_type: '',
    charge: '', job_address: '', eircode: ''
  });
  const [showPreview, setShowPreview] = useState(false);

  const { data: taxSettings } = useQuery({
    queryKey: ['tax-settings'],
    queryFn: async () => (await getTaxSettings()).data,
    enabled: isOpen,
    staleTime: 60000,
  });

  useEffect(() => {
    if (job) {
      setEditableData({
        customer_name: job.customer_name || job.client_name || '',
        phone: job.phone || job.phone_number || '',
        email: job.email || '',
        service_type: job.service_type || job.service || '',
        charge: (job.estimated_charge || job.charge) ? Math.round(parseFloat(job.estimated_charge || job.charge) * 100) / 100 : '',
        job_address: job.job_address || job.address || '',
        eircode: job.eircode || ''
      });
      setShowPreview(false);
    }
  }, [job]);

  const handleChange = (e) => {
    setEditableData(prev => ({ ...prev, [e.target.name]: e.target.value }));
  };

  if (!job) return null;

  const taxRate = parseFloat(taxSettings?.tax_rate || 0);
  const subtotal = parseFloat(editableData.charge) || 0;
  const taxAmount = Math.round(subtotal * taxRate) / 100;
  const total = subtotal + taxAmount;
  const invoicePrefix = taxSettings?.invoice_prefix || 'INV';
  const nextNum = taxSettings?.invoice_next_number || 1;
  const invoiceNumber = `${invoicePrefix}-${String(nextNum).padStart(4, '0')}`;
  const paymentTerms = parseInt(taxSettings?.invoice_payment_terms_days || 14);
  const dueDate = new Date();
  dueDate.setDate(dueDate.getDate() + paymentTerms);
  const taxIdLabel = taxSettings?.tax_id_label || 'VAT';

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={showPreview ? 'Invoice Preview' : 'Confirm Invoice Details'} size="medium">
      <div className="invoice-confirm-modal">
        {!showPreview ? (
          <>
            {invoiceConfig && !invoiceConfig.has_stripe_connect && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem 0.75rem', background: '#fffbeb', border: '1px solid #fcd34d', borderRadius: 8, fontSize: '0.78rem', color: '#92400e', marginBottom: '0.75rem' }}>
                <i className="fas fa-exclamation-triangle"></i>
                <span>
                  {invoiceConfig.stripe_setup_incomplete
                    ? 'Stripe setup is incomplete. Complete your account in Settings > Payments to include a payment link.'
                    : 'No online payment link will be included. Set up Stripe Connect in Settings to enable online payments.'}
                </span>
              </div>
            )}
            <p className="invoice-confirm-intro">
              Review and edit the invoice details before sending.
            </p>

            <div className="invoice-preview">
              <div className="invoice-field">
                <label>Customer Name</label>
                <input type="text" name="customer_name" value={editableData.customer_name}
                  onChange={handleChange} placeholder="Customer name" />
              </div>
              <div className="invoice-field">
                <label>Phone Number</label>
                <input type="tel" name="phone" value={editableData.phone}
                  onChange={handleChange} placeholder="Phone number" />
              </div>
              <div className="invoice-field">
                <label>Email</label>
                <input type="email" name="email" value={editableData.email}
                  onChange={handleChange} placeholder="customer@example.com" />
                <span className="field-hint">
                  {editableData.email ? 'Invoice will be sent via email' : editableData.phone ? 'Invoice will be sent via SMS (add email for email delivery)' : 'Add email or phone to send invoice'}
                </span>
              </div>
              <div className="invoice-field">
                <label>Service</label>
                <input type="text" name="service_type" value={editableData.service_type}
                  onChange={handleChange} placeholder="Service type" />
              </div>
              <div className="invoice-field">
                <label>Amount (€)</label>
                <input type="number" name="charge" value={editableData.charge}
                  onChange={handleChange} step="0.01" min="0" placeholder="0.00" />
              </div>
              <div className="invoice-field">
                <label>Job Address</label>
                <input type="text" name="job_address" value={editableData.job_address}
                  onChange={handleChange} placeholder="Job address" />
              </div>
              <div className="invoice-field">
                <label>Eircode</label>
                <input type="text" name="eircode" value={editableData.eircode}
                  onChange={handleChange} placeholder="e.g., D01 X2Y3" />
              </div>
            </div>

            <div className="invoice-summary">
              <div className="summary-row">
                <span className="summary-label">Subtotal</span>
                <span className="summary-value">{formatCurrency(subtotal)}</span>
              </div>
              {taxRate > 0 && (
                <div className="summary-row">
                  <span className="summary-label">{taxIdLabel} ({taxRate}%)</span>
                  <span className="summary-value">{formatCurrency(taxAmount)}</span>
                </div>
              )}
              <div className="summary-row total">
                <span className="summary-label">Total</span>
                <span className="summary-value">{formatCurrency(total)}</span>
              </div>
              <div className="summary-row">
                <span className="summary-label">Delivery</span>
                <span className="summary-value">
                  <i className={`fas ${editableData.email ? 'fa-envelope' : 'fa-sms'}`}></i>
                  {editableData.email ? `Email (${editableData.email})` : editableData.phone ? `SMS (${editableData.phone})` : 'No contact'}
                </span>
              </div>
            </div>

            <div className="invoice-confirm-actions">
              <button className="btn btn-secondary" onClick={onClose} disabled={isPending}>Cancel</button>
              <button className="btn btn-secondary" onClick={() => setShowPreview(true)} disabled={!editableData.charge}>
                <i className="fas fa-eye"></i> Preview
              </button>
              <button className="btn btn-primary" onClick={() => onConfirm(editableData)}
                disabled={isPending || !editableData.charge}>
                <i className={`fas ${isPending ? 'fa-spinner fa-spin' : 'fa-paper-plane'}`}></i>
                {isPending ? 'Sending...' : 'Send Invoice'}
              </button>
            </div>
          </>
        ) : (
          <>
            {/* A4 Document Preview using shared component */}
            <DocumentPreview
              type="invoice"
              docNumber={invoiceNumber}
              date={new Date().toISOString()}
              dueDate={dueDate.toISOString()}
              customer={{
                name: editableData.customer_name,
                address: [editableData.job_address, editableData.eircode].filter(Boolean).join(', '),
                phone: editableData.phone,
              }}
              lineItems={[{
                description: editableData.service_type || 'Service',
                quantity: 1,
                amount: subtotal,
              }]}
              subtotal={subtotal}
              taxRate={taxRate}
              taxAmount={taxAmount}
              total={total}
              notes={null}
              status={null}
              onClose={() => setShowPreview(false)}
              inline={true}
            />

            <div className="invoice-confirm-actions" style={{ marginTop: '0.75rem' }}>
              <button className="btn btn-secondary" onClick={() => setShowPreview(false)}>
                <i className="fas fa-arrow-left"></i> Back to Edit
              </button>
              <button className="btn btn-primary" onClick={() => onConfirm(editableData)}
                disabled={isPending || !editableData.charge}>
                <i className={`fas ${isPending ? 'fa-spinner fa-spin' : 'fa-paper-plane'}`}></i>
                {isPending ? 'Sending...' : 'Send Invoice'}
              </button>
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}

export default InvoiceConfirmModal;
