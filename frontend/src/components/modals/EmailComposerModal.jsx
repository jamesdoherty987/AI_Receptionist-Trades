import { useState, useEffect, useMemo } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../Toast';
import { sendCrmEmail, sendBulkCrmEmail } from '../../services/api';
import './EmailComposerModal.css';

function EmailComposerModal({ isOpen, onClose, mode = 'individual', recipient = null, customers = [] }) {
  const { user } = useAuth();
  const { addToast } = useToast();
  const companyName = user?.company_name || '';
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [toEmail, setToEmail] = useState('');
  const [selectedSegment, setSelectedSegment] = useState('all');
  const [selectedRecipients, setSelectedRecipients] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [showRecipientPicker, setShowRecipientPicker] = useState(false);

  // Auto-fill greeting + sign-off when opening
  useEffect(() => {
    if (isOpen) {
      setSubject('');
      setSearchTerm('');
      setShowRecipientPicker(false);
      if (mode === 'individual' && recipient) {
        setToEmail(recipient.email || '');
        const firstName = (recipient.name || '').split(' ')[0] || 'there';
        setBody(`Hi ${firstName},\n\n\n\nKind regards,\n${companyName}`);
      } else {
        setToEmail('');
        setSelectedSegment('all');
        setSelectedRecipients([]);
        setBody(`Hi {{name}},\n\n\n\nKind regards,\n${companyName}`);
      }
    }
  }, [isOpen, mode, recipient, companyName]);

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
    onSuccess: () => { addToast('Email sent', 'success'); onClose(); },
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
      sendIndividual.mutate({ to_email: toEmail.trim(), subject: subject.trim(), body_text: body.trim(), client_id: recipient?.id || null });
    } else {
      if (bulkRecipients.length === 0) { addToast('No recipients with email addresses', 'warning'); return; }
      sendBulk.mutate({ recipients: bulkRecipients.map(c => ({ email: c.email, name: c.name, client_id: c.id })), subject: subject.trim(), body_text: body.trim() });
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
          <button className="email-modal-close" onClick={onClose}><i className="fas fa-times"></i></button>
        </div>

        <div className="email-modal-body">
          {/* Recipient(s) */}
          {mode === 'individual' ? (
            <div className="email-field">
              <label>To</label>
              <div className="email-to-display">
                {recipient?.name && <span className="email-to-name">{recipient.name}</span>}
                <input type="email" value={toEmail} onChange={e => setToEmail(e.target.value)} placeholder="customer@example.com" />
              </div>
            </div>
          ) : (
            <div className="email-field">
              <label>Recipients</label>
              <div className="email-bulk-recipients">
                <div className="email-segment-row">
                  {[
                    { key: 'all', label: 'All', icon: 'fa-users' },
                    { key: 'vip', label: 'VIP', icon: 'fa-crown' },
                    { key: 'loyal', label: 'Loyal', icon: 'fa-heart' },
                    { key: 'dormant', label: 'Dormant', icon: 'fa-moon' },
                    { key: 'new', label: 'New', icon: 'fa-user-plus' },
                  ].map(s => (
                    <button key={s.key}
                      className={`email-seg-btn ${selectedSegment === s.key && selectedRecipients.length === 0 ? 'active' : ''}`}
                      onClick={() => { setSelectedSegment(s.key); setSelectedRecipients([]); setShowRecipientPicker(false); }}>
                      <i className={`fas ${s.icon}`}></i> {s.label}
                    </button>
                  ))}
                  <button className={`email-seg-btn ${selectedRecipients.length > 0 ? 'active' : ''}`}
                    onClick={() => setShowRecipientPicker(!showRecipientPicker)}>
                    <i className="fas fa-user-check"></i> Pick{selectedRecipients.length > 0 ? ` (${selectedRecipients.length})` : ''}
                  </button>
                </div>

                {showRecipientPicker && (
                  <div className="email-picker">
                    <div className="email-picker-header">
                      <input type="text" placeholder="Search by name or email..." value={searchTerm}
                        onChange={e => setSearchTerm(e.target.value)} className="email-picker-search" />
                      {selectedRecipients.length > 0 && (
                        <button className="email-picker-clear" onClick={() => setSelectedRecipients([])}>Clear all</button>
                      )}
                    </div>
                    <div className="email-picker-list">
                      {filteredPickerCustomers.map(c => {
                        const checked = selectedRecipients.some(r => r.id === c.id);
                        return (
                          <div key={c.id} className={`email-picker-row ${checked ? 'selected' : ''}`}
                            onClick={() => toggleRecipient(c)}>
                            <div className="email-picker-check">
                              {checked ? <i className="fas fa-check-circle"></i> : <i className="far fa-circle"></i>}
                            </div>
                            <div className="email-picker-info">
                              <span className="email-picker-name">{c.name}</span>
                              <span className="email-picker-email">{c.email}</span>
                            </div>
                          </div>
                        );
                      })}
                      {filteredPickerCustomers.length === 0 && (
                        <div className="email-picker-empty">No customers with email found</div>
                      )}
                    </div>
                  </div>
                )}

                <div className="email-recipient-count">
                  <i className="fas fa-envelope"></i>
                  <span>
                    {selectedRecipients.length > 0
                      ? `${selectedRecipients.length} customer${selectedRecipients.length !== 1 ? 's' : ''} selected`
                      : `${bulkRecipients.length} customer${bulkRecipients.length !== 1 ? 's' : ''} will receive this email`}
                  </span>
                </div>

                {mode === 'bulk' && (
                  <div className="email-personalize-hint">
                    <i className="fas fa-magic"></i>
                    Each customer's name is automatically inserted where it says <code>{'{{name}}'}</code>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Subject */}
          <div className="email-field">
            <label>Subject</label>
            <input type="text" value={subject} onChange={e => setSubject(e.target.value)} placeholder="Enter email subject..." />
          </div>

          {/* Body */}
          <div className="email-field email-field-body">
            <label>Message</label>
            <textarea value={body} onChange={e => setBody(e.target.value)} rows={12} />
          </div>
        </div>

        <div className="email-modal-footer">
          <button className="btn btn-secondary" onClick={onClose} disabled={isPending}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSend} disabled={isPending}>
            {isPending
              ? <><i className="fas fa-spinner fa-spin"></i> Sending...</>
              : <><i className="fas fa-paper-plane"></i> {mode === 'bulk' ? `Send to ${bulkRecipients.length}` : 'Send'}</>}
          </button>
        </div>
      </div>
    </div>
  );
}

export default EmailComposerModal;
