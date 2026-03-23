import { useState, useEffect } from 'react';
import Modal from './Modal';
import { formatCurrency } from '../../utils/helpers';
import './InvoiceConfirmModal.css';

function InvoiceConfirmModal({ 
  isOpen, 
  onClose, 
  onConfirm, 
  job, 
  invoiceConfig,
  isPending 
}) {
  const [editableData, setEditableData] = useState({
    customer_name: '',
    phone: '',
    service_type: '',
    charge: '',
    job_address: '',
    eircode: ''
  });

  // Initialize editable data when job changes
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
    }
  }, [job]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setEditableData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleConfirm = () => {
    onConfirm(editableData);
  };

  if (!job) return null;

  const deliveryMethod = invoiceConfig?.delivery_method || 'sms';
  const serviceName = invoiceConfig?.service_name || 'SMS';

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Confirm Invoice Details" size="medium">
      <div className="invoice-confirm-modal">
        <p className="invoice-confirm-intro">
          Review the invoice details below. You can edit any field before sending.
        </p>

        <div className="invoice-preview">
          <div className="invoice-field">
            <label>Customer Name</label>
            <input
              type="text"
              name="customer_name"
              value={editableData.customer_name}
              onChange={handleChange}
              placeholder="Customer name"
            />
          </div>

          <div className="invoice-field">
            <label>Phone Number</label>
            <input
              type="tel"
              name="phone"
              value={editableData.phone}
              onChange={handleChange}
              placeholder="Phone number"
            />
            <span className="field-hint">Invoice will be sent to this number</span>
          </div>

          <div className="invoice-field">
            <label>Service</label>
            <input
              type="text"
              name="service_type"
              value={editableData.service_type}
              onChange={handleChange}
              placeholder="Service type"
            />
          </div>

          <div className="invoice-field">
            <label>Amount (€)</label>
            <input
              type="number"
              name="charge"
              value={editableData.charge}
              onChange={handleChange}
              step="0.01"
              min="0"
              placeholder="0.00"
            />
          </div>

          <div className="invoice-field">
            <label>Job Address</label>
            <input
              type="text"
              name="job_address"
              value={editableData.job_address}
              onChange={handleChange}
              placeholder="Job address"
            />
          </div>

          <div className="invoice-field">
            <label>Eircode</label>
            <input
              type="text"
              name="eircode"
              value={editableData.eircode}
              onChange={handleChange}
              placeholder="e.g., D01 X2Y3"
            />
          </div>
        </div>

        <div className="invoice-summary">
          <div className="summary-row">
            <span className="summary-label">Delivery Method:</span>
            <span className="summary-value">
              <i className={`fas ${deliveryMethod === 'sms' ? 'fa-sms' : 'fa-envelope'}`}></i>
              {serviceName}
            </span>
          </div>
          <div className="summary-row total">
            <span className="summary-label">Total Amount:</span>
            <span className="summary-value">{formatCurrency(editableData.charge || 0)}</span>
          </div>
        </div>

        <div className="invoice-confirm-actions">
          <button 
            className="btn btn-secondary" 
            onClick={onClose}
            disabled={isPending}
          >
            Cancel
          </button>
          <button 
            className="btn btn-primary"
            onClick={handleConfirm}
            disabled={isPending || !editableData.charge}
          >
            <i className={`fas ${isPending ? 'fa-spinner fa-spin' : 'fa-paper-plane'}`}></i>
            {isPending ? 'Sending...' : 'Send Invoice'}
          </button>
        </div>
      </div>
    </Modal>
  );
}

export default InvoiceConfirmModal;
