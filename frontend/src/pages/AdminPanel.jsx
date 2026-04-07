import { useState, useEffect, useCallback } from 'react';
import api from '../services/api';
import './AdminPanel.css';

const ADMIN_SECRET_KEY = 'bfy_admin_secret';

function AdminPanel() {
  const [authed, setAuthed] = useState(false);
  const [secretInput, setSecretInput] = useState('');
  const [authError, setAuthError] = useState('');

  // State
  const [accounts, setAccounts] = useState([]);
  const [selectedAccount, setSelectedAccount] = useState(null);
  const [workers, setWorkers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [view, setView] = useState('list'); // list | create | edit
  const [toast, setToast] = useState('');

  // Create form
  const [createForm, setCreateForm] = useState({
    company_name: '', owner_name: '', email: '', phone: '', trade_type: '',
    company_context: '', coverage_area: '', address: '',
    business_hours: '8 AM - 6 PM Mon-Sat (24/7 emergency available)',
    auto_assign_phone: true, subscription_tier: 'pro', subscription_status: 'active',
  });
  const [newWorkers, setNewWorkers] = useState([]);
  const [newServices, setNewServices] = useState([]);

  // Edit form
  const [editForm, setEditForm] = useState({});

  const adminHeaders = useCallback(() => ({
    'X-Admin-Secret': localStorage.getItem(ADMIN_SECRET_KEY) || '',
    'Content-Type': 'application/json',
  }), []);

  const showToast = (msg) => { setToast(msg); setTimeout(() => setToast(''), 4000); };

  // Auth check
  const handleAuth = async () => {
    setAuthError('');
    try {
      const res = await fetch(`${api.defaults.baseURL}/api/admin/accounts`, {
        headers: { 'X-Admin-Secret': secretInput },
      });
      if (res.ok) {
        localStorage.setItem(ADMIN_SECRET_KEY, secretInput);
        setAuthed(true);
      } else {
        setAuthError('Invalid admin secret');
      }
    } catch {
      setAuthError('Cannot connect to server');
    }
  };

  useEffect(() => {
    const saved = localStorage.getItem(ADMIN_SECRET_KEY);
    if (saved) {
      fetch(`${api.defaults.baseURL}/api/admin/accounts`, {
        headers: { 'X-Admin-Secret': saved },
      }).then(r => { if (r.ok) setAuthed(true); });
    }
  }, []);

  // Load accounts
  const loadAccounts = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${api.defaults.baseURL}/api/admin/accounts`, { headers: adminHeaders() });
      const data = await res.json();
      if (data.success) setAccounts(data.accounts);
    } catch (e) { showToast('Failed to load accounts'); }
    setLoading(false);
  }, [adminHeaders]);

  useEffect(() => { if (authed) loadAccounts(); }, [authed, loadAccounts]);

  // Load single account
  const loadAccount = async (id) => {
    setLoading(true);
    try {
      const res = await fetch(`${api.defaults.baseURL}/api/admin/accounts/${id}`, { headers: adminHeaders() });
      const data = await res.json();
      if (data.success) {
        setSelectedAccount(data.account);
        setWorkers(data.workers || []);
        setEditForm({
          company_name: data.account.company_name || '',
          owner_name: data.account.owner_name || '',
          email: data.account.email || '',
          phone: data.account.phone || '',
          trade_type: data.account.trade_type || '',
          address: data.account.address || '',
          business_hours: data.account.business_hours || '',
          company_context: data.account.company_context || '',
          coverage_area: data.account.coverage_area || '',
          subscription_tier: data.account.subscription_tier || 'none',
          subscription_status: data.account.subscription_status || 'inactive',
          ai_enabled: data.account.ai_enabled !== false,
          send_confirmation_sms: data.account.send_confirmation_sms !== false,
          send_reminder_sms: data.account.send_reminder_sms || false,
        });
        setView('edit');
      }
    } catch { showToast('Failed to load account'); }
    setLoading(false);
  };

  // Create account
  const handleCreate = async (e) => {
    e.preventDefault();
    if (!createForm.company_name || !createForm.owner_name || !createForm.email) {
      showToast('Company name, owner name, and email are required');
      return;
    }
    setLoading(true);
    try {
      const payload = {
        ...createForm,
        frontend_url: window.location.origin,
        workers: newWorkers.filter(w => w.name),
        services: newServices.filter(s => s.name),
      };
      const res = await fetch(`${api.defaults.baseURL}/api/admin/create-account`, {
        method: 'POST', headers: adminHeaders(), body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (data.success) {
        showToast(`Account created! Invite link: ${data.invite_link}`);
        setCreateForm({
          company_name: '', owner_name: '', email: '', phone: '', trade_type: '',
          company_context: '', coverage_area: '', address: '',
          business_hours: '8 AM - 6 PM Mon-Sat (24/7 emergency available)',
          auto_assign_phone: true, subscription_tier: 'pro', subscription_status: 'active',
        });
        setNewWorkers([]);
        setNewServices([]);
        // Show invite link in a copyable way
        setLastInviteLink(data.invite_link);
        setLastEmailSent(data.email_sent);
        loadAccounts();
      } else {
        showToast(data.error || 'Failed to create account');
      }
    } catch { showToast('Failed to create account'); }
    setLoading(false);
  };

  const [lastInviteLink, setLastInviteLink] = useState('');
  const [lastEmailSent, setLastEmailSent] = useState(false);

  // Update account
  const handleUpdate = async () => {
    if (!selectedAccount) return;
    setLoading(true);
    try {
      const res = await fetch(`${api.defaults.baseURL}/api/admin/accounts/${selectedAccount.id}`, {
        method: 'PUT', headers: adminHeaders(), body: JSON.stringify(editForm),
      });
      const data = await res.json();
      if (data.success) {
        showToast('Account updated');
        loadAccounts();
        loadAccount(selectedAccount.id);
      } else {
        showToast(data.error || 'Failed to update');
      }
    } catch { showToast('Failed to update account'); }
    setLoading(false);
  };

  // Resend invite
  const handleResendInvite = async () => {
    if (!selectedAccount) return;
    try {
      const res = await fetch(`${api.defaults.baseURL}/api/admin/accounts/${selectedAccount.id}/resend-invite`, {
        method: 'POST', headers: adminHeaders(),
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

  // Copy to clipboard
  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text).then(() => showToast('Copied to clipboard'));
  };

  // Logout
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
              <input
                type="password"
                value={secretInput}
                onChange={(e) => setSecretInput(e.target.value)}
                placeholder="Admin secret"
                autoFocus
              />
              <button type="submit">Authenticate</button>
            </form>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="admin-page">
      {toast && <div className="admin-toast">{toast}</div>}

      <header className="admin-header">
        <div className="admin-header-left">
          <i className="fas fa-shield-alt"></i>
          <h1>Admin Panel</h1>
        </div>
        <div className="admin-header-right">
          <button className="admin-nav-btn" onClick={() => { setView('list'); setSelectedAccount(null); setLastInviteLink(''); }}>
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
                      <th>ID</th>
                      <th>Company</th>
                      <th>Owner</th>
                      <th>Email</th>
                      <th>Phone</th>
                      <th>Plan</th>
                      <th>Setup</th>
                      <th>AI Number</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {accounts.map(acc => (
                      <tr key={acc.id}>
                        <td className="id-cell">{acc.id}</td>
                        <td className="name-cell">{acc.company_name}</td>
                        <td>{acc.owner_name}</td>
                        <td className="email-cell">{acc.email}</td>
                        <td>{acc.phone || '—'}</td>
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
                        <td>
                          <button className="admin-btn small" onClick={() => loadAccount(acc.id)}>
                            <i className="fas fa-edit"></i> Edit
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

            {lastInviteLink && (
              <div className="admin-invite-banner">
                <div className="invite-banner-icon"><i className="fas fa-check-circle"></i></div>
                <div className="invite-banner-content">
                  <strong>Account created!</strong>
                  <p>{lastEmailSent ? 'Invite email sent. Link also available below:' : 'Share this link with the customer to set their password:'}</p>
                  <div className="invite-link-row">
                    <code>{lastInviteLink}</code>
                    <button onClick={() => copyToClipboard(lastInviteLink)}><i className="fas fa-copy"></i></button>
                  </div>
                </div>
              </div>
            )}

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
                <h3><i className="fas fa-robot"></i> AI Receptionist Setup</h3>
                <div className="admin-form-grid">
                  <div className="admin-field full">
                    <label>Coverage Area</label>
                    <input value={createForm.coverage_area} onChange={e => setCreateForm(p => ({...p, coverage_area: e.target.value}))} placeholder="e.g., Dublin and surrounding areas" />
                  </div>
                  <div className="admin-field full">
                    <label>Business Hours</label>
                    <input value={createForm.business_hours} onChange={e => setCreateForm(p => ({...p, business_hours: e.target.value}))} />
                  </div>
                  <div className="admin-field full">
                    <label>Company Context (AI Knowledge)</label>
                    <textarea value={createForm.company_context} onChange={e => setCreateForm(p => ({...p, company_context: e.target.value}))} rows={6}
                      placeholder="Parking info, warranties, certifications, policies — anything the AI should know" />
                  </div>
                </div>
              </div>

              <div className="admin-form-section">
                <h3><i className="fas fa-phone"></i> Phone & Subscription</h3>
                <div className="admin-form-grid">
                  <div className="admin-field">
                    <label>
                      <input type="checkbox" checked={createForm.auto_assign_phone} onChange={e => setCreateForm(p => ({...p, auto_assign_phone: e.target.checked}))} />
                      {' '}Auto-assign AI phone number
                    </label>
                  </div>
                  <div className="admin-field">
                    <label>Subscription</label>
                    <select value={createForm.subscription_tier} onChange={e => setCreateForm(p => ({...p, subscription_tier: e.target.value}))}>
                      <option value="pro">Pro (Active)</option>
                      <option value="trial">Trial</option>
                      <option value="none">None</option>
                    </select>
                  </div>
                </div>
              </div>

              <div className="admin-form-section">
                <h3><i className="fas fa-hard-hat"></i> Workers ({newWorkers.length})</h3>
                {newWorkers.map((w, i) => (
                  <div key={i} className="admin-inline-row">
                    <input placeholder="Name" value={w.name} onChange={e => { const u = [...newWorkers]; u[i].name = e.target.value; setNewWorkers(u); }} />
                    <input placeholder="Phone" value={w.phone} onChange={e => { const u = [...newWorkers]; u[i].phone = e.target.value; setNewWorkers(u); }} />
                    <input placeholder="Email" value={w.email || ''} onChange={e => { const u = [...newWorkers]; u[i].email = e.target.value; setNewWorkers(u); }} />
                    <input placeholder="Specialty" value={w.trade_specialty} onChange={e => { const u = [...newWorkers]; u[i].trade_specialty = e.target.value; setNewWorkers(u); }} />
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
                    <input placeholder="Service name" value={s.name} onChange={e => { const u = [...newServices]; u[i].name = e.target.value; setNewServices(u); }} />
                    <input placeholder="Price (€)" type="number" value={s.price || ''} onChange={e => { const u = [...newServices]; u[i].price = e.target.value; setNewServices(u); }} style={{width: 100}} />
                    <input placeholder="Duration (min)" type="number" value={s.duration_minutes || ''} onChange={e => { const u = [...newServices]; u[i].duration_minutes = e.target.value; setNewServices(u); }} style={{width: 120}} />
                    <input placeholder="Category" value={s.category || ''} onChange={e => { const u = [...newServices]; u[i].category = e.target.value; setNewServices(u); }} style={{width: 120}} />
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

        {/* ========== EDIT ACCOUNT ========== */}
        {view === 'edit' && selectedAccount && (
          <div className="admin-section">
            <div className="admin-section-header">
              <h2><i className="fas fa-edit"></i> Edit: {selectedAccount.company_name}</h2>
              <div className="admin-header-badges">
                <span className={`badge ${selectedAccount.easy_setup === false ? 'badge-blue' : 'badge-gray'}`}>
                  {selectedAccount.easy_setup === false ? 'Managed' : 'Self-service'}
                </span>
                <span className={`badge ${selectedAccount.subscription_status === 'active' ? 'badge-green' : 'badge-gray'}`}>
                  {selectedAccount.subscription_tier}
                </span>
              </div>
            </div>

            {lastInviteLink && (
              <div className="admin-invite-banner">
                <div className="invite-banner-icon"><i className="fas fa-link"></i></div>
                <div className="invite-banner-content">
                  <strong>Invite Link</strong>
                  <p>{lastEmailSent ? 'Email sent. Link:' : 'Share this link:'}</p>
                  <div className="invite-link-row">
                    <code>{lastInviteLink}</code>
                    <button onClick={() => copyToClipboard(lastInviteLink)}><i className="fas fa-copy"></i></button>
                  </div>
                </div>
              </div>
            )}

            <div className="admin-edit-grid">
              {/* Left column — Business info */}
              <div className="admin-edit-col">
                <div className="admin-form-section">
                  <h3><i className="fas fa-building"></i> Business Info</h3>
                  <div className="admin-form-stack">
                    <div className="admin-field">
                      <label>Company Name</label>
                      <input value={editForm.company_name} onChange={e => setEditForm(p => ({...p, company_name: e.target.value}))} />
                    </div>
                    <div className="admin-field">
                      <label>Owner Name</label>
                      <input value={editForm.owner_name} onChange={e => setEditForm(p => ({...p, owner_name: e.target.value}))} />
                    </div>
                    <div className="admin-field">
                      <label>Email</label>
                      <input value={editForm.email} onChange={e => setEditForm(p => ({...p, email: e.target.value}))} />
                    </div>
                    <div className="admin-field">
                      <label>Phone</label>
                      <input value={editForm.phone} onChange={e => setEditForm(p => ({...p, phone: e.target.value}))} />
                    </div>
                    <div className="admin-field">
                      <label>Trade Type</label>
                      <input value={editForm.trade_type} onChange={e => setEditForm(p => ({...p, trade_type: e.target.value}))} />
                    </div>
                    <div className="admin-field">
                      <label>Address</label>
                      <input value={editForm.address} onChange={e => setEditForm(p => ({...p, address: e.target.value}))} />
                    </div>
                    <div className="admin-field">
                      <label>Business Hours</label>
                      <input value={editForm.business_hours} onChange={e => setEditForm(p => ({...p, business_hours: e.target.value}))} />
                    </div>
                    <div className="admin-field">
                      <label>Subscription</label>
                      <div className="admin-inline-selects">
                        <select value={editForm.subscription_tier} onChange={e => setEditForm(p => ({...p, subscription_tier: e.target.value}))}>
                          <option value="pro">Pro</option><option value="trial">Trial</option><option value="none">None</option>
                        </select>
                        <select value={editForm.subscription_status} onChange={e => setEditForm(p => ({...p, subscription_status: e.target.value}))}>
                          <option value="active">Active</option><option value="inactive">Inactive</option>
                        </select>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="admin-form-section">
                  <h3><i className="fas fa-sliders-h"></i> Toggles</h3>
                  <div className="admin-toggles">
                    <label><input type="checkbox" checked={editForm.ai_enabled} onChange={e => setEditForm(p => ({...p, ai_enabled: e.target.checked}))} /> AI Enabled</label>
                    <label><input type="checkbox" checked={editForm.send_confirmation_sms} onChange={e => setEditForm(p => ({...p, send_confirmation_sms: e.target.checked}))} /> Confirmation SMS</label>
                    <label><input type="checkbox" checked={editForm.send_reminder_sms} onChange={e => setEditForm(p => ({...p, send_reminder_sms: e.target.checked}))} /> Reminder SMS</label>
                  </div>
                </div>

                <div className="admin-form-actions">
                  <button className="admin-btn primary" onClick={handleUpdate} disabled={loading}>
                    <i className="fas fa-save"></i> Save Changes
                  </button>
                  <button className="admin-btn secondary" onClick={handleResendInvite}>
                    <i className="fas fa-paper-plane"></i> Resend Invite
                  </button>
                </div>
              </div>

              {/* Right column — AI context + workers */}
              <div className="admin-edit-col">
                <div className="admin-form-section">
                  <h3><i className="fas fa-robot"></i> AI Receptionist Context</h3>
                  <div className="admin-form-stack">
                    <div className="admin-field">
                      <label>Coverage Area</label>
                      <input value={editForm.coverage_area} onChange={e => setEditForm(p => ({...p, coverage_area: e.target.value}))} />
                    </div>
                    <div className="admin-field">
                      <label>Company Context</label>
                      <textarea value={editForm.company_context} onChange={e => setEditForm(p => ({...p, company_context: e.target.value}))} rows={8} />
                    </div>
                  </div>
                </div>

                <div className="admin-form-section">
                  <h3><i className="fas fa-hard-hat"></i> Workers ({workers.length})</h3>
                  {workers.length === 0 ? (
                    <p className="admin-empty">No workers added yet.</p>
                  ) : (
                    <div className="admin-worker-list">
                      {workers.map(w => (
                        <div key={w.id} className="admin-worker-card">
                          <div className="worker-info">
                            <strong>{w.name}</strong>
                            {w.trade_specialty && <span className="worker-specialty">{w.trade_specialty}</span>}
                          </div>
                          <div className="worker-contact">
                            {w.phone && <span><i className="fas fa-phone"></i> {w.phone}</span>}
                            {w.email && <span><i className="fas fa-envelope"></i> {w.email}</span>}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="admin-form-section">
                  <h3><i className="fas fa-info-circle"></i> Account Details</h3>
                  <div className="admin-meta">
                    <div><strong>ID:</strong> {selectedAccount.id}</div>
                    <div><strong>AI Phone:</strong> {selectedAccount.twilio_phone_number || 'Not assigned'}</div>
                    <div><strong>Created:</strong> {selectedAccount.created_at ? new Date(selectedAccount.created_at).toLocaleDateString() : '—'}</div>
                    <div><strong>Last Login:</strong> {selectedAccount.last_login ? new Date(selectedAccount.last_login).toLocaleDateString() : 'Never'}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default AdminPanel;
