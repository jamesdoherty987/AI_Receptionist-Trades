import { useState, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import Modal from './Modal';
import { formatCurrency } from '../../utils/helpers';
import { createQuote, updateBooking, sendQuote } from '../../services/api';
import { useToast } from '../Toast';
import DocumentPreview from '../accounting/DocumentPreview';

function CreateQuoteFromJobModal({ isOpen, onClose, job }) {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [showPreview, setShowPreview] = useState(false);
  const [title, setTitle] = useState('');
  const [notes, setNotes] = useState('');
  const [lineItems, setLineItems] = useState([{ description: '', quantity: 1, amount: 0 }]);

  useEffect(() => {
    if (job && isOpen) {
      const charge = parseFloat(job.estimated_charge || job.charge || 0);
      const svc = job.service_type || job.service || 'Service';
      setTitle(svc);
      setNotes(job.job_address ? `Job address: ${job.job_address}${job.eircode ? ` (${job.eircode})` : ''}` : '');
      setLineItems([{ description: svc, quantity: 1, amount: charge }]);
      setShowPreview(false);
    }
  }, [job, isOpen]);

  const subtotal = lineItems.reduce((s, i) => s + (parseFloat(i.amount) || 0) * (parseFloat(i.quantity) || 1), 0);

  const createMut = useMutation({
    mutationFn: async (data) => {
      const res = await createQuote(data);
      const originalCharge = parseFloat(job.estimated_charge || job.charge || 0);
      if (Math.abs(subtotal - originalCharge) > 0.01 && subtotal > 0) {
        await updateBooking(job.id, { estimated_charge: subtotal });
      }
      return res;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['quotes'] });
      queryClient.invalidateQueries({ queryKey: ['booking', job.id] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      addToast('Quote created and linked to job', 'success');
      onClose();
    },
    onError: (e) => addToast(e.response?.data?.error || 'Failed to create quote', 'error'),
  });

  const createAndSendMut = useMutation({
    mutationFn: async (data) => {
      const res = await createQuote(data);
      const originalCharge = parseFloat(job.estimated_charge || job.charge || 0);
      if (Math.abs(subtotal - originalCharge) > 0.01 && subtotal > 0) {
        await updateBooking(job.id, { estimated_charge: subtotal });
      }
      const quoteId = res.data?.id || res.data?.quote?.id;
      const sendRes = await sendQuote(quoteId);
      return sendRes;
    },
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['quotes'] });
      queryClient.invalidateQueries({ queryKey: ['quote-pipeline'] });
      queryClient.invalidateQueries({ queryKey: ['booking', job.id] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      addToast(`Quote created & sent via ${res.data?.sent_via || 'email'} to ${res.data?.sent_to || 'customer'}`, 'success');
      onClose();
    },
    onError: (e) => addToast(e.response?.data?.error || 'Failed to create & send quote', 'error'),
  });

  const isBusy = createMut.isPending || createAndSendMut.isPending;

  const buildPayload = () => ({
    client_id: job.client_id || null,
    title,
    description: '',
    line_items: lineItems,
    valid_days: 30,
    notes,
    booking_id: job.id,
  });

  const handleSubmit = () => {
    createMut.mutate(buildPayload());
  };

  const handleCreateAndSend = () => {
    createAndSendMut.mutate(buildPayload());
  };

  const updateItem = (idx, field, value) => {
    setLineItems(prev => prev.map((item, i) => i === idx ? { ...item, [field]: value } : item));
  };

  if (!job) return null;

  if (showPreview) {
    return (
      <Modal isOpen={isOpen} onClose={onClose} title="Quote Preview" size="large">
        <DocumentPreview
          type="quote"
          date={new Date().toISOString()}
          customer={{ name: job.customer_name || job.client_name || '', address: job.job_address, phone: job.phone || job.phone_number }}
          lineItems={lineItems}
          subtotal={subtotal}
          total={subtotal}
          notes={notes}
          status="Draft"
          onClose={() => setShowPreview(false)}
          inline={true}
        />
        <div className="cqj-footer">
          <button className="cqj-btn cqj-btn-ghost" onClick={() => setShowPreview(false)}>
            <i className="fas fa-arrow-left"></i> Back
          </button>
          <button className="cqj-btn cqj-btn-outline" onClick={handleSubmit} disabled={isBusy}>
            <i className={`fas ${createMut.isPending ? 'fa-spinner fa-spin' : 'fa-save'}`}></i>
            {createMut.isPending ? 'Creating...' : 'Save as Draft'}
          </button>
          <button className="cqj-btn cqj-btn-primary" onClick={handleCreateAndSend} disabled={isBusy}>
            <i className={`fas ${createAndSendMut.isPending ? 'fa-spinner fa-spin' : 'fa-paper-plane'}`}></i>
            {createAndSendMut.isPending ? 'Sending...' : 'Create & Send'}
          </button>
        </div>
      </Modal>
    );
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Create Quote" size="medium">
      <div className="cqj-container">
        {/* Job context badge */}
        <div className="cqj-context">
          <i className="fas fa-link"></i>
          <span>For <strong>{job.customer_name || job.client_name}</strong> — {job.service_type || job.service}</span>
        </div>

        {/* Title */}
        <div className="cqj-group">
          <label className="cqj-label">Quote Title</label>
          <input className="cqj-input" type="text" value={title} onChange={e => setTitle(e.target.value)} placeholder="What is this quote for?" />
        </div>

        {/* Line Items */}
        <div className="cqj-group">
          <label className="cqj-label">Line Items</label>
          <div className="cqj-table">
            <div className="cqj-table-head">
              <span className="cqj-col-desc">Item</span>
              <span className="cqj-col-qty">Qty</span>
              <span className="cqj-col-price">Price</span>
              <span className="cqj-col-total">Total</span>
              <span className="cqj-col-action"></span>
            </div>
            {lineItems.map((item, idx) => (
              <div key={idx} className="cqj-table-row">
                <input className="cqj-col-desc" type="text" value={item.description} placeholder="Description"
                  onChange={e => updateItem(idx, 'description', e.target.value)} />
                <input className="cqj-col-qty" type="number" min="1" step="1" value={item.quantity}
                  onChange={e => updateItem(idx, 'quantity', e.target.value)} />
                <div className="cqj-col-price cqj-price-wrap">
                  <span className="cqj-currency">€</span>
                  <input type="number" min="0" step="0.01" value={item.amount}
                    onChange={e => updateItem(idx, 'amount', e.target.value)} />
                </div>
                <span className="cqj-col-total cqj-row-total">
                  {formatCurrency((parseFloat(item.amount) || 0) * (parseFloat(item.quantity) || 1))}
                </span>
                <span className="cqj-col-action">
                  {lineItems.length > 1 && (
                    <button className="cqj-remove" onClick={() => setLineItems(prev => prev.filter((_, i) => i !== idx))}>
                      <i className="fas fa-trash-alt"></i>
                    </button>
                  )}
                </span>
              </div>
            ))}
          </div>
          <button className="cqj-add-row" onClick={() => setLineItems(prev => [...prev, { description: '', quantity: 1, amount: 0 }])}>
            <i className="fas fa-plus-circle"></i> Add line item
          </button>
        </div>

        {/* Total */}
        <div className="cqj-total-bar">
          <span>Total</span>
          <span className="cqj-total-amount">{formatCurrency(subtotal)}</span>
        </div>

        {/* Sync notice */}
        {Math.abs(subtotal - parseFloat(job.estimated_charge || job.charge || 0)) > 0.01 && subtotal > 0 && (
          <div className="cqj-notice">
            <i className="fas fa-info-circle"></i>
            Job charge will update to {formatCurrency(subtotal)}
          </div>
        )}

        {/* Notes */}
        <div className="cqj-group">
          <label className="cqj-label">Notes <span className="cqj-optional">(optional)</span></label>
          <textarea className="cqj-textarea" rows={2} value={notes} onChange={e => setNotes(e.target.value)} placeholder="Any additional notes for the customer..." />
        </div>

        {/* Actions */}
        <div className="cqj-footer">
          <button className="cqj-btn cqj-btn-ghost" onClick={onClose}>Cancel</button>
          <button className="cqj-btn cqj-btn-outline" onClick={() => setShowPreview(true)} disabled={subtotal <= 0}>
            <i className="fas fa-eye"></i> Preview
          </button>
          <button className="cqj-btn cqj-btn-outline" onClick={handleSubmit} disabled={isBusy || !title.trim()}>
            <i className={`fas ${createMut.isPending ? 'fa-spinner fa-spin' : 'fa-save'}`}></i>
            {createMut.isPending ? 'Creating...' : 'Save as Draft'}
          </button>
          <button className="cqj-btn cqj-btn-primary" onClick={handleCreateAndSend} disabled={isBusy || !title.trim()}>
            <i className={`fas ${createAndSendMut.isPending ? 'fa-spinner fa-spin' : 'fa-paper-plane'}`}></i>
            {createAndSendMut.isPending ? 'Sending...' : 'Create & Send'}
          </button>
        </div>
      </div>
    </Modal>
  );
}

export default CreateQuoteFromJobModal;
