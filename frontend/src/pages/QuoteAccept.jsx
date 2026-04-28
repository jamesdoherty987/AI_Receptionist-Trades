import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { getQuoteByAcceptToken, acceptQuoteByToken, declineQuoteByToken } from '../services/api';
import './CustomerPortal.css';

function QuoteAccept() {
  const { token } = useParams();
  const [quote, setQuote] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [accepting, setAccepting] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const [alreadyAccepted, setAlreadyAccepted] = useState(false);
  const [declining, setDeclining] = useState(false);
  const [declined, setDeclined] = useState(false);
  const [showDeclineReason, setShowDeclineReason] = useState(false);
  const [declineReason, setDeclineReason] = useState('');

  useEffect(() => {
    const load = async () => {
      try {
        const res = await getQuoteByAcceptToken(token);
        if (res.data.already_accepted) setAlreadyAccepted(true);
        else {
          const q = res.data.quote;
          if (q && (q.status === 'accepted' || q.status === 'converted')) {
            setAlreadyAccepted(true);
          } else if (q && q.status === 'declined') {
            setDeclined(true);
          } else {
            setQuote(q);
          }
        }
      } catch {
        setError('This quote link is invalid or has expired.');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [token]);

  const handleAccept = async () => {
    setAccepting(true);
    try {
      const res = await acceptQuoteByToken(token);
      if (res.data.already_accepted) setAlreadyAccepted(true);
      else setAccepted(true);
    } catch {
      setError('Failed to accept quote.');
    } finally {
      setAccepting(false);
    }
  };

  const handleDecline = async () => {
    setDeclining(true);
    try {
      await declineQuoteByToken(token, declineReason);
      setDeclined(true);
    } catch {
      setError('Failed to decline quote.');
    } finally {
      setDeclining(false);
    }
  };

  if (loading) return <div className="portal-page"><div className="portal-card"><div className="portal-spinner"></div><p>Loading quote...</p></div></div>;
  if (error) return <div className="portal-page"><div className="portal-card"><div className="portal-icon">😕</div><h1>Oops</h1><p>{error}</p></div></div>;
  if (alreadyAccepted) return <div className="portal-page"><div className="portal-card"><div className="portal-icon">✅</div><h1>Already Accepted</h1><p>This quote has already been accepted. We'll be in touch to schedule your job.</p></div></div>;
  if (accepted) return <div className="portal-page"><div className="portal-card"><div className="portal-icon">🎉</div><h1>Quote Accepted!</h1><p>Thank you! We'll be in touch shortly to schedule your job.</p></div></div>;
  if (declined) return <div className="portal-page"><div className="portal-card"><div className="portal-icon">📋</div><h1>Quote Declined</h1><p>No problem. If you change your mind or want to discuss the quote, feel free to get in touch.</p></div></div>;
  if (!quote) return null;

  const items = Array.isArray(quote.line_items) ? quote.line_items : [];

  return (
    <div className="portal-page">
      <div className="portal-container">
        <div className="quote-accept-card">
          <div className="qa-header">
            <h1>Quote from {quote.company_name}</h1>
            <p className="qa-number">#{quote.quote_number}</p>
          </div>
          <h2 className="qa-title">{quote.title}</h2>
          {quote.client_name && <p className="qa-client">For: {quote.client_name}</p>}

          {items.length > 0 && (
            <div className="qa-items">
              <div className="qa-items-head"><span>Item</span><span>Qty</span><span>Amount</span></div>
              {items.map((item, i) => (
                <div key={i} className="qa-item-row">
                  <span>{item.description}</span>
                  <span>{item.quantity || 1}</span>
                  <span>€{(Number(item.amount || 0) * Number(item.quantity || 1)).toFixed(2)}</span>
                </div>
              ))}
            </div>
          )}

          <div className="qa-total">
            <span>Total</span>
            <span>€{Number(quote.total || 0).toFixed(2)}</span>
          </div>

          {quote.valid_until && (
            <p className="qa-valid">Valid until: {new Date(quote.valid_until).toLocaleDateString('en-IE', { day: 'numeric', month: 'long', year: 'numeric' })}</p>
          )}

          {quote.notes && <p className="qa-notes">{quote.notes}</p>}

          {!showDeclineReason ? (
            <>
              <button className="qa-accept-btn" onClick={handleAccept} disabled={accepting || declining}>
                {accepting ? 'Accepting...' : '✓ Accept This Quote'}
              </button>
              <button className="qa-decline-btn" onClick={() => setShowDeclineReason(true)} disabled={accepting || declining}>
                ✕ Decline
              </button>
              <p className="qa-disclaimer">By accepting, you agree to proceed with this work. We'll contact you to confirm timing.</p>
            </>
          ) : (
            <div className="qa-decline-form">
              <p className="qa-decline-prompt">Could you let us know why? (optional)</p>
              <textarea
                className="qa-decline-textarea"
                rows={3}
                value={declineReason}
                onChange={e => setDeclineReason(e.target.value)}
                placeholder="Too expensive, found another provider, not needed anymore..."
              />
              <div className="qa-decline-actions">
                <button className="qa-decline-cancel" onClick={() => setShowDeclineReason(false)}>Back</button>
                <button className="qa-decline-confirm" onClick={handleDecline} disabled={declining}>
                  {declining ? 'Declining...' : 'Confirm Decline'}
                </button>
              </div>
            </div>
          )}
        </div>
        <div className="portal-footer"><p>Powered by <strong>BookedForYou</strong></p></div>
      </div>
    </div>
  );
}

export default QuoteAccept;
