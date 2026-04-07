import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import Modal from './Modal';
import { formatCurrency } from '../../utils/helpers';
import { getTaxSettings, getBusinessSettings } from '../../services/api';
import './InvoiceConfirmModal.css';

function InvoiceConfirmModal({ isOpen, onClose, onConfirm, job, invoiceConfig, isPending }) {
  const [editableData, setEditableData] = useState({
    customer_name: '', phone: '', service_type: '',
    charge: '', job_address: '', eircode: ''
  });
  const [showPreview, setShowPreview] = useState(false);

  const { data: taxSettings } = useQuery({
    queryKey: ['tax-settings'],
    queryFn: async () => (await getTaxSettings()).data,
    enabled: isOpen,
    staleTime: 60000,
  });

  const { data: bizSettings } = useQuery({
    queryKey: ['business-settings'],
    queryFn: async () => (await getBusinessSettings()).data,
    enabled: isOpen,
    staleTime: 60000,
  });

  useEffect(() => {
    if (job) {
      setEditableData({
        customer_name: job.customer_name || job.client_name || '',
        phone: job.phone || job.phone_number || '',
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
  const companyName = bizSettings?.business_name || '';
  const companyPhone = bizSettings?.phone || '';
  const companyAddress = bizSettings?.address || '';
  const taxIdLabel = taxSettings?.tax_id_label || 'VAT';
  const taxIdNumber = taxSettings?.tax_id_number || '';
  const invoicePrefix = taxSettings?.invoice_prefix || 'INV';
  const nextNum = taxSettings?.invoice_next_number || 1;
  const invoiceNumber = `${invoicePrefix}-${String(nextNum).padStart(4, '0')}`;
  const paymentTerms = parseInt(taxSettings?.invoice_payment_terms_days || 14);
  const dueDate = new Date();
  dueDate.setDate(dueDate.getDate() + paymentTerms);
  const footerNote = taxSettings?.invoice_footer_note || '';

  const deliveryMethod = invoiceConfig?.delivery_method || 'sms';
  const serviceName = invoiceConfig?.service_name || 'SMS';

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={showPreview ? 'Invoice Preview' : 'Confirm Invoice Details'} size="medium">
      <div className="invoice-confirm-modal">
        {!showPreview ? (
          <>
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
                <span className="field-hint">Invoice will be sent to this number via {serviceName}</span>
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
                  <i className={`fas ${deliveryMethod === 'sms' ? 'fa-sms' : 'fa-envelope'}`}></i>
                  {serviceName}
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
            {/* PDF-style Invoice Preview */}
            <div className="inv-preview-doc">
              <div className="inv-preview-header">
                <div>
                  <div className="inv-preview-company">{companyName || 'Your Company'}</div>
                  {companyAddress && <div className="inv-preview-addr">{companyAddress}</div>}
                  {companyPhone && <div className="inv-preview-addr">{companyPhone}</div>}
                  {taxIdNumber && <div className="inv-preview-addr">{taxIdLabel}: {taxIdNumber}</div>}
                </div>
                <div className="inv-preview-right">
                  <div className="inv-preview-title">INVOICE</div>
                  <div className="inv-preview-num">{invoiceNumber}</div>
                  <div className="inv-preview-date">Date: {new Date().toLocaleDateString('en-IE')}</div>
                  <div className="inv-preview-date">Due: {dueDate.toLocaleDateString('en-IE')}</div>
                </div>
              </div>

              <div className="inv-preview-billto">
                <div className="inv-preview-billto-label">Bill To</div>
                <div className="inv-preview-billto-name">{editableData.customer_name}</div>
                {editableData.job_address && <div className="inv-preview-billto-addr">{editableData.job_address}</div>}
                {editableData.eircode && <div className="inv-preview-billto-addr">{editableData.eircode}</div>}
                <div className="inv-preview-billto-addr">{editableData.phone}</div>
              </div>

              <table className="inv-preview-table">
                <thead>
                  <tr>
                    <th>Description</th>
                    <th style={{ textAlign: 'right' }}>Amount</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>{editableData.service_type || 'Service'}</td>
                    <td style={{ textAlign: 'right' }}>{formatCurrency(subtotal)}</td>
                  </tr>
                </tbody>
              </table>

              <div className="inv-preview-totals">
                <div className="inv-preview-total-row">
                  <span>Subtotal</span><span>{formatCurrency(subtotal)}</span>
                </div>
                {taxRate > 0 && (
                  <div className="inv-preview-total-row">
                    <span>{taxIdLabel} ({taxRate}%)</span><span>{formatCurrency(taxAmount)}</span>
                  </div>
                )}
                <div className="inv-preview-total-row inv-preview-grand-total">
                  <span>Total Due</span><span>{formatCurrency(total)}</span>
                </div>
              </div>

              <div className="inv-preview-terms">
                Payment Terms: {paymentTerms === 0 ? 'Due on Receipt' : `Net ${paymentTerms} days`}
              </div>

              {footerNote && (
                <div className="inv-preview-footer">{footerNote}</div>
              )}
            </div>

            <div className="invoice-confirm-actions">
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
