import { useState, useEffect, useMemo } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useToast } from '../Toast';
import { sendCrmEmail, sendBulkCrmEmail } from '../../services/api';
import './EmailComposerModal.css';

function EmailComposerModal({ isOpen, onClose, mode = 'individual', recipient = null, customers = [] }) {
  const { addToast } = useToast();
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [toEmail, setToEmail] = useState('');
  const [selectedSegment, setSelectedSegment] = useState('all');
  const [selectedRecipients, setSelectedRecipients] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [showRecipientPicker, setShowRecipientPicker] = useState(false);

  // Reset form when opening
  useEffect(() => {
    if (isOpen) {
      setSubject('');
      setBody('');
      setSearchTerm('');
      setShowRecipientPicker(false);
      if (mode === 'individual' && recipient) {
        setToEmail(recipient.email || '');
      } else {
        setToEmail('');
        setSelectedSegment('all');
        setSelectedRecipients([]);
      }
    }
  }, [isOpen, mode, recipient]);

  const emailableCustomers = useMemo(() =>
    customers.filter(c => c.email && c.email.trim()),
    [customers]
  );

  const filteredPickerCustomers = useMemo(() => {
    if (!searchTerm.trim()) return emailableCustomers;
    const term = searchTerm.toLowerCase();
    return emailableCustomers.filter(c =>
      c.name?.toLowerCase().includes(term) || c.email?.toLowerCase().includes(term)
    );
  }, [emailableCustomers, searchTerm]);

  const bulkRecipients = useMemo(() => {
    if (selectedRecipients.length > 0) return selectedRecipients;
    if (selectedSegment === 'all') return emailableCustomers;
    return emailableCustomers.filter(c => c.segment === selectedSegment);
  }, [selectedSegment, selectedRecipients, emailableCustomers]);

  const sendIndividual = useMutation({
    mutationFn: (data) => sendCrmEmail(data),
    onSuccess: () => {
      addToast('Email sent successfully', 'success');
      onClose();
    },
    onError: (e) => addToast(e.response?.data?.error || 'Failed to send email', 'error'),
  });

  const sendBulk = useMutation({
    mutationFn: (data) => sendBulkCrmEmail(data),
    onSuccess: (res) => {
      const d = res.data;
      addToast(`Sent ${d.sent} of ${d.total} emails${d.failed > 0 ? ` (${d.failed} failed)` : ''}`, d.failed > 0 ? 'warning' : 'success');
      onClose();
    },
    onError: (e) => addToast(e.response?.data?.error || 'Failed to send emails', 'error'),
  });

  const handleSend = () => {
    if (!subject.trim()) { addToast('Please enter a subject', 'warning'); return; }
    if (!body.trim()) { addToast('Please enter a message', 'warning'); return; }

    if (mode === 'individual') {
      if (!toEmail.trim()) { addToast('Please enter a recipient email', 'warning'); return; }
      sendIndividual.mutate({
        to_email: toEmail.trim(),
        subject: subject.trim(),
        body_text: body.trim(),
        client_id: recipient?.id || null,
      });
    } else {
      if (bulkRecipients.length === 0) { addToast('No recipients with email addresses', 'warning'); return; }
      sendBulk.mutate({
        recipients: bulkRecipients.map(c => ({ email: c.email, name: c.name, client_id: c.id })),
        subject: subject.trim(),
        body_text: body.trim(),
      });
    }
  };

  const toggleRecipient = (customer) => {
    setSelectedRecipients(prev => {
      const exists = prev.find(r => r.id === customer.id);
      if (exists) return prev.filter(r => r.id !== customer.id);
      return [...prev, customer];
    });
  };

  const isPending = sendIndividual.isPending || sendBulk.isPending;

  if (!isOpen) return null;

  return (
    <div className="email-modal-overlay" onClick={onClose}>
      <div className="email-modal" onClick={e => e.stopPropagation()}>
        <div className="email-modal-header">
          <h3>
            <i className={`fas ${mode === 'bulk' ? 'fa-paper-plane' : 'fa-envelope'}`}></i>
            {mode === 'bulk' ? ' Bulk Email' : ' Compose Email'}
          </h3>
          <button className="email-modal-close" onClick={onClose}>
            <i className="fas fa-times"></i>
          </button>
        </div>

        <div className="email-modal-body">
          {/* Recipient(s) */}
          {mode === 'individual' ? (
            <div className="email-field">
              <label>To</label>
              <input
                type="email"
                value={toEmail}
                onChange={e => setToEmail(e.target.value)}
                placeholder="customer@example.com"
              />
            </div>
          ) : (
            <div className="email-field">
              <label>Recipients</label>
              <div className="email-bulk-recipients">
                <div className="email-segment-row">
                  {[
                    { key: 'all', label: 'All Customers', icon: 'fa-users' },
                    { key: 'vip', label: 'VIP', icon: 'fa-crown' },
                    { key: 'loyal', label: 'Loyal', icon: 'fa-heart' },
                    { key: 'dormant', label: 'Dormant', icon: 'fa-moon' },
                    { key: 'new', label: 'New', icon: 'fa-user-plus' },
                  ].map(s => (
                    <button key={s.key}
                      className={`email-seg-btn ${selectedSegment === s.key && selectedRecipients.length === 0 ? 'active' : ''}`}
                      onClick={() => { setSelectedSegment(s.key); setSelectedRecipients([]); }}>
                      <i className={`fas ${s.icon}`}></i> {s.label}
                    </button>
                  ))}
                  <button className={`email-seg-btn ${showRecipientPicker ? 'active' : ''}`}
                    onClick={() => setShowRecipientPicker(!showRecipientPicker)}>
                    <i className="fas fa-user-check"></i> Pick
                  </button>
                </div>

                {showRecipientPicker && (
                  <div className="email-picker">
                    <input type="text" placeholder="Search customers..." value={searchTerm}
                      onChange={e => setSearchTerm(e.target.value)} className="email-picker-search" />
                    <div className="email-picker-list">
                      {filteredPickerCustomers.map(c => (
                        <label key={c.id} className="email-picker-item">
                          <input type="checkbox"
                            checked={selectedRecipients.some(r => r.id === c.id)}
                            onChange={() => toggleRecipient(c)} />
                          <span className="email-picker-name">{c.name}</span>
                          <span className="email-picker-email">{c.email}</span>
                        </label>
                      ))}
                      {filteredPickerCustomers.length === 0 && (
                        <div className="email-picker-empty">No customers with email found</div>
                      )}
                    </div>
                  </div>
                )}

                <div className="email-recipient-count">
                  <i className="fas fa-users"></i>
                  {selectedRecipients.length > 0
                    ? `${selectedRecipients.length} selected`
                    : `${bulkRecipients.length} recipients`}
                  {bulkRecipients.length > 0 && (
                    <span className="email-hint">Use {'{{name}}'} to personalize</span>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Subject */}
          <div className="email-field">
            <label>Subject</label>
            <input
              type="text"
              value={subject}
              onChange={e => setSubject(e.target.value)}
              placeholder="Enter email subject..."
            />
          </div>

          {/* Body */}
          <div className="email-field email-field-body">
            <label>Message</label>
            <textarea
              value={body}
              onChange={e => setBody(e.target.value)}
              placeholder={mode === 'bulk'
                ? "Hi {{name}},\n\nWrite your message here..."
                : `Hi ${recipient?.name || ''},\n\nWrite your message here...`}
              rows={10}
            />
          </div>
        </div>

        <div className="email-modal-footer">
          <button className="btn btn-secondary" onClick={onClose} disabled={isPending}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSend} disabled={isPending}>
            {isPending ? (
              <><i className="fas fa-spinner fa-spin"></i> Sending...</>
            ) : (
              <><i className="fas fa-paper-plane"></i> {mode === 'bulk' ? `Send to ${bulkRecipients.length}` : 'Send'}</>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

export default EmailComposerModal;
