import { useState, useEffect, useCallback } from 'react';
import api from '../services/api';
import './AdminPanel.css';

const ADMIN_SECRET_KEY = 'bfy_admin_secret';

function AdminPanel() {
  const [authed, setAuthed] = useState(false);
  const [secretInput, setSecretInput] = useState('');
  const [authError, setAuthError] = useState('');

  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [view, setView] = useState('list');
  const [toast, setToast] = useState('');
  const [lastInviteLink, setLastInviteLink] = useState('');
  const [lastEmailSent, setLastEmailSent] = useState(false);

  // Create form
  const [createForm, setCreateForm] = useState({
    company_name: '', owner_name: '', email: '', phone: '', trade_type: '',
    company_context: '', coverage_area: '', address: '',
    business_hours: '8 AM - 6 PM Mon-Sat (24/7 emergency available)',
    auto_assign_phone: false, phone_number: '', subscription_tier: 'none', subscription_status: 'inactive',
  });
  const [newWorkers, setNewWorkers] = useState([]);
  const [newServices, setNewServices] = useState([]);
  const [availablePhones, setAvailablePhones] = useState([]);
  const [phonesLoading, setPhonesLoading] = useState(false);

  // Business hours picker state
  const [hoursConfig, setHoursConfig] = useState({
    startHour: '8', startPeriod: 'AM', endHour: '6', endPeriod: 'PM',
    days: { monday: true, tuesday: true, wednesday: true, thursday: true, friday: true, saturday: true, sunday: false },
    emergency: true,
  });

  const adminHeaders = useCallback(() => {
    const secret = (localStorage.getItem(ADMIN_SECRET_KEY) || '').replace(/[^\x20-\x7E]/g, '').trim();
    return { 'X-Admin-Secret': secret, 'Content-Type': 'application/json' };
  }, []);

  // Use a helper that works with both proxy (local) and direct (production)
  const adminFetch = useCallback(async (path, options = {}) => {
    const url = `${api.defaults.baseURL}${path}`;
    return fetch(url, { ...options, headers: { ...adminHeaders(), ...(options.headers || {}) } });
  }, [adminHeaders]);

  const showToast = (msg) => { setToast(msg); setTimeout(() => setToast(''), 5000); };

  // Format business hours from picker state
  const formatHours = () => {
    const { startHour, startPeriod, endHour, endPeriod, days, emergency } = hoursConfig;
    const dayNames = { monday:'Mon', tuesday:'Tue', wednesday:'Wed', thursday:'Thu', friday:'Fri', saturday:'Sat', sunday:'Sun' };
    const sel = Object.keys(days).filter(d => days[d]);
    let daysText = 'No days';
    if (sel.length === 7) daysText = 'Daily';
    else if (sel.length === 6 && !days.sunday) daysText = 'Mon-Sat';
    else if (sel.length === 5 && !days.saturday && !days.sunday) daysText = 'Mon-Fri';
    else if (sel.length > 0) daysText = sel.map(d => dayNames[d]).join(', ');
    let s = `${startHour} ${startPeriod} - ${endHour} ${endPeriod} ${daysText}`;
    if (emergency) s += ' (24/7 emergency available)';
    return s;
  };

  // Sync hours picker → createForm
  useEffect(() => {
    setCreateForm(p => ({ ...p, business_hours: formatHours() }));
  }, [hoursConfig]);

  // Auth
  const handleAuth = async () => {
    setAuthError('');
    // Sanitize: strip any non-ASCII characters that break fetch headers
    const cleanSecret = secretInput.replace(/[^\x20-\x7E]/g, '').trim();
    if (!cleanSecret) { setAuthError('Please enter the admin secret'); return; }
    try {
      console.log('[ADMIN] Authenticating...');
      const res = await fetch(`${api.defaults.baseURL}/api/admin/accounts`, {
        headers: { 'X-Admin-Secret': cleanSecret, 'Content-Type': 'application/json' },
      });
      console.log('[ADMIN] Auth response:', res.status);
      if (res.ok) { localStorage.setItem(ADMIN_SECRET_KEY, cleanSecret); setAuthed(true); }
      else setAuthError('Invalid admin secret');
    } catch (err) { console.error('[ADMIN] Auth error:', err); setAuthError('Cannot connect to server: ' + err.message); }
  };

  useEffect(() => {
    const saved = localStorage.getItem(ADMIN_SECRET_KEY);
    if (saved) {
      // Sanitize stored value too
      const clean = saved.replace(/[^\x20-\x7E]/g, '').trim();
      if (!clean) { localStorage.removeItem(ADMIN_SECRET_KEY); return; }
      if (clean !== saved) localStorage.setItem(ADMIN_SECRET_KEY, clean);
      fetch(`${api.defaults.baseURL}/api/admin/accounts`, {
        headers: { 'X-Admin-Secret': clean, 'Content-Type': 'application/json' },
      }).then(r => { if (r.ok) setAuthed(true); }).catch(() => {});
    }
  }, []);

  // Load accounts
  const loadAccounts = useCallback(async () => {
    setLoading(true);
    try {
      const res = await adminFetch('/api/admin/accounts');
      const data = await res.json();
      if (data.success) setAccounts(data.accounts);
    } catch { showToast('Failed to load accounts'); }
    setLoading(false);
  }, [adminHeaders]);

  useEffect(() => { if (authed) loadAccounts(); }, [authed, loadAccounts]);

  // Load available phone numbers
  const loadPhones = useCallback(async () => {
    setPhonesLoading(true);
    try {
      const res = await adminFetch('/api/admin/phone-numbers/available');
      const data = await res.json();
      if (data.success) setAvailablePhones(data.numbers || []);
    } catch { /* ignore */ }
    setPhonesLoading(false);
  }, [adminHeaders]);

  useEffect(() => { if (authed && view === 'create') loadPhones(); }, [authed, view, loadPhones]);

  // Create account
  const handleCreate = async (e) => {
    e.preventDefault();
    if (!createForm.company_name || !createForm.owner_name || !createForm.email) {
      showToast('Company name, owner name, and email are required'); return;
    }
    setLoading(true);
    try {
      const payload = {
        ...createForm,
        frontend_url: window.location.origin,
        workers: newWorkers.filter(w => w.name),
        services: newServices.filter(s => s.name),
      };
      const res = await adminFetch('/api/admin/create-account', {
        method: 'POST', body: JSON.stringify(payload),
      });
      let data;
      try { data = await res.json(); } catch { data = { error: `Server returned ${res.status}` }; }
      if (res.ok && data.success) {
        setLastInviteLink(data.invite_link);
        setLastEmailSent(data.email_sent);
        showToast('Account created!');
        setCreateForm({
          company_name: '', owner_name: '', email: '', phone: '', trade_type: '',
          company_context: '', coverage_area: '', address: '',
          business_hours: formatHours(),
          auto_assign_phone: false, phone_number: '', subscription_tier: 'none', subscription_status: 'inactive',
        });
        setNewWorkers([]);
        setNewServices([]);
        loadAccounts();
        loadPhones();
      } else { showToast(data.error || `Failed (${res.status})`); }
    } catch (err) { showToast('Failed to create account: ' + (err.message || 'network error')); }
    setLoading(false);
  };

  // Impersonate — log in as a customer
  const handleImpersonate = async (accountId) => {
    try {
      const res = await adminFetch(`/api/admin/accounts/${accountId}/impersonate`, {
        method: 'POST',
      });
      const data = await res.json();
      if (data.success) {
        // Store auth data and redirect to dashboard
        localStorage.setItem('authToken', data.auth_token);
        localStorage.setItem('authUser', JSON.stringify(data.user));
        localStorage.removeItem('authSubscription'); // will be fetched fresh
        window.location.href = '/dashboard';
      } else { showToast(data.error || 'Failed to impersonate'); }
    } catch { showToast('Failed to impersonate'); }
  };

  // Resend invite
  const handleResendInvite = async (accountId) => {
    try {
      const res = await adminFetch(`/api/admin/accounts/${accountId}/resend-invite`, {
        method: 'POST',
        body: JSON.stringify({ frontend_url: window.location.origin }),
      });
      const data = await res.json();
      if (data.success) {
        setLastInviteLink(data.invite_link);
        setLastEmailSent(data.email_sent);
        showToast(data.email_sent ? 'Invite email sent!' : 'Invite link generated');
      }
    } catch { showToast('Failed to resend invite'); }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text).then(() => showToast('Copied!'));
  };

  const handleLogout = () => {
    localStorage.removeItem(ADMIN_SECRET_KEY);
    setAuthed(false);
    setSecretInput('');
  };

  // ==================== RENDER ====================

  if (!authed) {
    return (
      <div className="admin-page">
        <div className="admin-auth">
          <div className="admin-auth-card">
            <div className="admin-auth-icon"><i className="fas fa-shield-alt"></i></div>
            <h1>Admin Panel</h1>
            <p>Enter your admin secret to continue.</p>
            {authError && <div className="admin-error">{authError}</div>}
            <form onSubmit={(e) => { e.preventDefault(); handleAuth(); }}>
              <input type="password" value={secretInput} onChange={(e) => setSecretInput(e.target.value)} placeholder="Admin secret" autoFocus />
              <button type="submit">Authenticate</button>
            </form>
          </div>
        </div>
      </div>
    );
  }

  const dayLabels = [
    { key: 'monday', label: 'Mon' }, { key: 'tuesday', label: 'Tue' }, { key: 'wednesday', label: 'Wed' },
    { key: 'thursday', label: 'Thu' }, { key: 'friday', label: 'Fri' }, { key: 'saturday', label: 'Sat' }, { key: 'sunday', label: 'Sun' },
  ];

  return (
    <div className="admin-page">
      {toast && <div className="admin-toast">{toast}</div>}

      <header className="admin-header">
        <div className="admin-header-left">
          <i className="fas fa-shield-alt"></i>
          <h1>Admin Panel</h1>
        </div>
        <div className="admin-header-right">
          <button className="admin-nav-btn" onClick={() => { setView('list'); setLastInviteLink(''); }}>
            <i className="fas fa-list"></i> Accounts
          </button>
          <button className="admin-nav-btn" onClick={() => { setView('create'); setLastInviteLink(''); }}>
            <i className="fas fa-plus"></i> New Account
          </button>
          <button className="admin-nav-btn logout" onClick={handleLogout}>
            <i className="fas fa-sign-out-alt"></i> Logout
          </button>
        </div>
      </header>

      <main className="admin-main">
        {/* ========== INVITE LINK BANNER ========== */}
        {lastInviteLink && (
          <div className="admin-invite-banner">
            <div className="invite-banner-icon"><i className="fas fa-check-circle"></i></div>
            <div className="invite-banner-content">
              <strong>{lastEmailSent ? 'Invite email sent!' : 'Invite link ready'}</strong>
              <p>Share this link with the customer to set their password:</p>
              <div className="invite-link-row">
                <code>{lastInviteLink}</code>
                <button onClick={() => copyToClipboard(lastInviteLink)}><i className="fas fa-copy"></i></button>
              </div>
            </div>
            <button className="invite-dismiss" onClick={() => setLastInviteLink('')}><i className="fas fa-times"></i></button>
          </div>
        )}

        {/* ========== ACCOUNTS LIST ========== */}
        {view === 'list' && (
          <div className="admin-section">
            <div className="admin-section-header">
              <h2><i className="fas fa-building"></i> All Accounts ({accounts.length})</h2>
              <button className="admin-btn primary" onClick={() => setView('create')}>
                <i className="fas fa-plus"></i> Create Account
              </button>
            </div>
            {loading ? (
              <div className="admin-loading"><i className="fas fa-spinner fa-spin"></i> Loading...</div>
            ) : (
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>ID</th><th>Company</th><th>Owner</th><th>Email</th>
                      <th>Plan</th><th>Setup</th><th>AI Number</th><th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {accounts.map(acc => (
                      <tr key={acc.id}>
                        <td className="id-cell">{acc.id}</td>
                        <td className="name-cell">{acc.company_name}</td>
                        <td>{acc.owner_name}</td>
                        <td className="email-cell">{acc.email}</td>
                        <td>
                          <span className={`badge ${acc.subscription_status === 'active' ? 'badge-green' : 'badge-gray'}`}>
                            {acc.subscription_tier || 'none'}
                          </span>
                        </td>
                        <td>
                          <span className={`badge ${acc.easy_setup === false ? 'badge-blue' : 'badge-gray'}`}>
                            {acc.easy_setup === false ? 'Managed' : 'Self-service'}
                          </span>
                        </td>
                        <td className="phone-cell">{acc.twilio_phone_number || '—'}</td>
                        <td className="actions-cell">
                          <button className="admin-btn primary small" onClick={() => handleImpersonate(acc.id)} title="Log in as this account">
                            <i className="fas fa-sign-in-alt"></i> Log In
                          </button>
                          <button className="admin-btn secondary small" onClick={() => handleResendInvite(acc.id)} title="Resend password invite">
                            <i className="fas fa-paper-plane"></i>
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* ========== CREATE ACCOUNT ========== */}
        {view === 'create' && (
          <div className="admin-section">
            <div className="admin-section-header">
              <h2><i className="fas fa-plus-circle"></i> Create New Account</h2>
            </div>

            <form onSubmit={handleCreate} className="admin-form">
              <div className="admin-form-section">
                <h3><i className="fas fa-building"></i> Business Info</h3>
                <div className="admin-form-grid">
                  <div className="admin-field">
                    <label>Company Name *</label>
                    <input value={createForm.company_name} onChange={e => setCreateForm(p => ({...p, company_name: e.target.value}))} required />
                  </div>
                  <div className="admin-field">
                    <label>Owner Name *</label>
                    <input value={createForm.owner_name} onChange={e => setCreateForm(p => ({...p, owner_name: e.target.value}))} required />
                  </div>
                  <div className="admin-field">
                    <label>Email *</label>
                    <input type="email" value={createForm.email} onChange={e => setCreateForm(p => ({...p, email: e.target.value}))} required />
                  </div>
                  <div className="admin-field">
                    <label>Phone</label>
                    <input value={createForm.phone} onChange={e => setCreateForm(p => ({...p, phone: e.target.value}))} placeholder="085 123 4567" />
                  </div>
                  <div className="admin-field">
                    <label>Trade Type</label>
                    <select value={createForm.trade_type} onChange={e => setCreateForm(p => ({...p, trade_type: e.target.value}))}>
                      <option value="">Select...</option>
                      {['Plumbing','Electrical','Roofing','HVAC','Carpentry','Painting','Landscaping','General Contracting','Flooring','Masonry','Other'].map(t => <option key={t} value={t}>{t}</option>)}
                    </select>
                  </div>
                  <div className="admin-field">
                    <label>Address</label>
                    <input value={createForm.address} onChange={e => setCreateForm(p => ({...p, address: e.target.value}))} />
                  </div>
                </div>
              </div>

              <div className="admin-form-section">
                <h3><i className="fas fa-clock"></i> Business Hours</h3>
                <div className="admin-hours-picker">
                  <div className="admin-hours-time">
                    <div className="admin-time-group">
                      <label>Start</label>
                      <select value={hoursConfig.startHour} onChange={e => setHoursConfig(p => ({...p, startHour: e.target.value}))}>
                        {[...Array(12)].map((_, i) => <option key={i+1} value={i+1}>{i+1}</option>)}
                      </select>
                      <select value={hoursConfig.startPeriod} onChange={e => setHoursConfig(p => ({...p, startPeriod: e.target.value}))}>
                        <option value="AM">AM</option><option value="PM">PM</option>
                      </select>
                    </div>
                    <span className="admin-time-sep">to</span>
                    <div className="admin-time-group">
                      <label>End</label>
                      <select value={hoursConfig.endHour} onChange={e => setHoursConfig(p => ({...p, endHour: e.target.value}))}>
                        {[...Array(12)].map((_, i) => <option key={i+1} value={i+1}>{i+1}</option>)}
                      </select>
                      <select value={hoursConfig.endPeriod} onChange={e => setHoursConfig(p => ({...p, endPeriod: e.target.value}))}>
                        <option value="AM">AM</option><option value="PM">PM</option>
                      </select>
                    </div>
                  </div>
                  <div className="admin-hours-days">
                    {dayLabels.map(d => (
                      <label key={d.key} className={`admin-day-chip ${hoursConfig.days[d.key] ? 'active' : ''}`}>
                        <input type="checkbox" checked={hoursConfig.days[d.key]} onChange={() => setHoursConfig(p => ({...p, days: {...p.days, [d.key]: !p.days[d.key]}}))} />
                        {d.label}
                      </label>
                    ))}
                  </div>
                  <label className="admin-emergency-check">
                    <input type="checkbox" checked={hoursConfig.emergency} onChange={e => setHoursConfig(p => ({...p, emergency: e.target.checked}))} />
                    24/7 emergency available
                  </label>
                  <div className="admin-hours-preview">Preview: {formatHours()}</div>
                </div>
              </div>

              <div className="admin-form-section">
                <h3><i className="fas fa-robot"></i> AI Receptionist</h3>
                <div className="admin-form-grid">
                  <div className="admin-field full">
                    <label>Coverage Area</label>
                    <input value={createForm.coverage_area} onChange={e => setCreateForm(p => ({...p, coverage_area: e.target.value}))} placeholder="e.g., Dublin and surrounding areas" />
                  </div>
                  <div className="admin-field full">
                    <label>Company Context (AI Knowledge)</label>
                    <textarea value={createForm.company_context} onChange={e => setCreateForm(p => ({...p, company_context: e.target.value}))} rows={6}
                      placeholder="Parking info, warranties, certifications, policies — anything the AI should know" />
                  </div>
                </div>
              </div>

              <div className="admin-form-section">
                <h3><i className="fas fa-cog"></i> Phone & Subscription</h3>
                <div className="admin-form-grid">
                  <div className="admin-field">
                    <label>AI Phone Number</label>
                    <select value={createForm.phone_number} onChange={e => setCreateForm(p => ({...p, phone_number: e.target.value}))}>
                      <option value="">Don't assign yet</option>
                      {phonesLoading && <option disabled>Loading...</option>}
                      {availablePhones.map(p => (
                        <option key={p.phone_number} value={p.phone_number}>{p.phone_number}</option>
                      ))}
                    </select>
                    {!phonesLoading && availablePhones.length === 0 && (
                      <small style={{color: '#f87171', marginTop: '0.25rem', display: 'block'}}>No phone numbers available in pool</small>
                    )}
                  </div>
                  <div className="admin-field">
                    <label>Subscription</label>
                    <select value={createForm.subscription_tier} onChange={e => setCreateForm(p => ({...p, subscription_tier: e.target.value, subscription_status: e.target.value === 'none' ? 'inactive' : 'active'}))}>
                      <option value="none">None</option>
                      <option value="trial">Trial</option>
                      <option value="pro">Pro (Active)</option>
                    </select>
                  </div>
                </div>
              </div>

              <div className="admin-form-section">
                <h3><i className="fas fa-hard-hat"></i> Workers ({newWorkers.length})</h3>
                {newWorkers.map((w, i) => (
                  <div key={i} className="admin-inline-row">
                    <input placeholder="Name *" value={w.name} onChange={e => { const u = [...newWorkers]; u[i] = {...u[i], name: e.target.value}; setNewWorkers(u); }} />
                    <input placeholder="Phone" value={w.phone} onChange={e => { const u = [...newWorkers]; u[i] = {...u[i], phone: e.target.value}; setNewWorkers(u); }} />
                    <input placeholder="Email" value={w.email || ''} onChange={e => { const u = [...newWorkers]; u[i] = {...u[i], email: e.target.value}; setNewWorkers(u); }} />
                    <input placeholder="Specialty" value={w.trade_specialty} onChange={e => { const u = [...newWorkers]; u[i] = {...u[i], trade_specialty: e.target.value}; setNewWorkers(u); }} />
                    <button type="button" className="admin-btn danger small" onClick={() => setNewWorkers(newWorkers.filter((_, j) => j !== i))}><i className="fas fa-trash"></i></button>
                  </div>
                ))}
                <button type="button" className="admin-btn secondary small" onClick={() => setNewWorkers([...newWorkers, { name: '', phone: '', email: '', trade_specialty: '' }])}>
                  <i className="fas fa-plus"></i> Add Worker
                </button>
              </div>

              <div className="admin-form-section">
                <h3><i className="fas fa-concierge-bell"></i> Services ({newServices.length})</h3>
                {newServices.map((s, i) => (
                  <div key={i} className="admin-inline-row">
                    <input placeholder="Service name *" value={s.name} onChange={e => { const u = [...newServices]; u[i] = {...u[i], name: e.target.value}; setNewServices(u); }} />
                    <input placeholder="Price (€)" type="number" value={s.price || ''} onChange={e => { const u = [...newServices]; u[i] = {...u[i], price: e.target.value}; setNewServices(u); }} style={{width: 100}} />
                    <input placeholder="Duration (min)" type="number" value={s.duration_minutes || ''} onChange={e => { const u = [...newServices]; u[i] = {...u[i], duration_minutes: e.target.value}; setNewServices(u); }} style={{width: 130}} />
                    <input placeholder="Category" value={s.category || ''} onChange={e => { const u = [...newServices]; u[i] = {...u[i], category: e.target.value}; setNewServices(u); }} style={{width: 120}} />
                    <button type="button" className="admin-btn danger small" onClick={() => setNewServices(newServices.filter((_, j) => j !== i))}><i className="fas fa-trash"></i></button>
                  </div>
                ))}
                <button type="button" className="admin-btn secondary small" onClick={() => setNewServices([...newServices, { name: '', price: '', duration_minutes: '', category: 'General' }])}>
                  <i className="fas fa-plus"></i> Add Service
                </button>
              </div>

              <div className="admin-form-actions">
                <button type="submit" className="admin-btn primary large" disabled={loading}>
                  {loading ? <><i className="fas fa-spinner fa-spin"></i> Creating...</> : <><i className="fas fa-rocket"></i> Create Account</>}
                </button>
              </div>
            </form>
          </div>
        )}
      </main>
    </div>
  );
}

export default AdminPanel;
