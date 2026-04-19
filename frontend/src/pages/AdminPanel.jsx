import { useState, useEffect, useCallback, useMemo } from 'react';
import api from '../services/api';
import './AdminPanel.css';

const ADMIN_SECRET_KEY = 'bfy_admin_secret';

// ==================== HELPER COMPONENTS ====================

function StatCard({ icon, label, value, sub, color = '#818cf8' }) {
  return (
    <div className="ap-stat-card">
      <div className="ap-stat-icon" style={{ color }}><i className={`fas fa-${icon}`}></i></div>
      <div className="ap-stat-info">
        <span className="ap-stat-value">{value}</span>
        <span className="ap-stat-label">{label}</span>
        {sub && <span className="ap-stat-sub">{sub}</span>}
      </div>
    </div>
  );
}

function MiniBar({ value, max, color = '#818cf8' }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  return (
    <div className="ap-mini-bar">
      <div className="ap-mini-bar-fill" style={{ width: `${pct}%`, background: color }}></div>
    </div>
  );
}

function Badge({ type, children }) {
  const cls = type === 'green' ? 'ap-badge-green' : type === 'blue' ? 'ap-badge-blue' : type === 'yellow' ? 'ap-badge-yellow' : type === 'red' ? 'ap-badge-red' : 'ap-badge-gray';
  return <span className={`ap-badge ${cls}`}>{children}</span>;
}

// ==================== MAIN COMPONENT ====================

function AdminPanel() {
  const [authed, setAuthed] = useState(false);
  const [secretInput, setSecretInput] = useState('');
  const [authError, setAuthError] = useState('');
  const [view, setView] = useState('overview');
  const [toast, setToast] = useState('');
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // Data
  const [accounts, setAccounts] = useState([]);
  const [overview, setOverview] = useState(null);
  const [companyInsights, setCompanyInsights] = useState(null);
  const [selectedCompanyId, setSelectedCompanyId] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [accountFilter, setAccountFilter] = useState('all');
  const [accountSort, setAccountSort] = useState('newest');

  // Create form
  const [createForm, setCreateForm] = useState({
    company_name: '', owner_name: '', email: '', phone: '', trade_type: '',
    company_context: '', coverage_area: '', address: '',
    business_hours: '8 AM - 6 PM Mon-Sat (24/7 emergency available)',
    auto_assign_phone: false, phone_number: '', subscription_tier: 'none', subscription_status: 'inactive',
    custom_stripe_price_id: '', custom_monthly_price: '',
  });
  const [newWorkers, setNewWorkers] = useState([]);
  const [newServices, setNewServices] = useState([]);
  const [availablePhones, setAvailablePhones] = useState([]);
  const [phonesLoading, setPhonesLoading] = useState(false);
  const [lastInviteLink, setLastInviteLink] = useState('');
  const [lastEmailSent, setLastEmailSent] = useState(false);

  // Business hours picker
  const [hoursConfig, setHoursConfig] = useState({
    startHour: '8', startPeriod: 'AM', endHour: '6', endPeriod: 'PM',
    days: { monday: true, tuesday: true, wednesday: true, thursday: true, friday: true, saturday: true, sunday: false },
    emergency: true,
  });

  const adminHeaders = useCallback(() => {
    const secret = (localStorage.getItem(ADMIN_SECRET_KEY) || '').replace(/[^\x20-\x7E]/g, '').trim();
    return { 'X-Admin-Secret': secret, 'Content-Type': 'application/json' };
  }, []);

  const adminFetch = useCallback(async (path, options = {}) => {
    const url = `${api.defaults.baseURL}${path}`;
    return fetch(url, { ...options, headers: { ...adminHeaders(), ...(options.headers || {}) } });
  }, [adminHeaders]);

  const showToast = (msg) => { setToast(msg); setTimeout(() => setToast(''), 5000); };

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

  useEffect(() => {
    setCreateForm(p => ({ ...p, business_hours: formatHours() }));
  }, [hoursConfig]);

  // ==================== AUTH ====================
  const handleAuth = async () => {
    setAuthError('');
    const cleanSecret = secretInput.replace(/[^\x20-\x7E]/g, '').trim();
    if (!cleanSecret) { setAuthError('Please enter the admin secret'); return; }
    try {
      const res = await fetch(`${api.defaults.baseURL}/api/admin/accounts`, {
        headers: { 'X-Admin-Secret': cleanSecret, 'Content-Type': 'application/json' },
      });
      if (res.ok) { localStorage.setItem(ADMIN_SECRET_KEY, cleanSecret); setAuthed(true); }
      else setAuthError('Invalid admin secret');
    } catch (err) { setAuthError('Cannot connect to server: ' + err.message); }
  };

  useEffect(() => {
    const saved = localStorage.getItem(ADMIN_SECRET_KEY);
    if (saved) {
      const clean = saved.replace(/[^\x20-\x7E]/g, '').trim();
      if (!clean) { localStorage.removeItem(ADMIN_SECRET_KEY); return; }
      if (clean !== saved) localStorage.setItem(ADMIN_SECRET_KEY, clean);
      fetch(`${api.defaults.baseURL}/api/admin/accounts`, {
        headers: { 'X-Admin-Secret': clean, 'Content-Type': 'application/json' },
      }).then(r => { if (r.ok) setAuthed(true); }).catch(() => {});
    }
  }, []);

  // ==================== DATA LOADING ====================
  const loadAccounts = useCallback(async () => {
    setLoading(true);
    try {
      const res = await adminFetch('/api/admin/accounts');
      const data = await res.json();
      if (data.success) setAccounts(data.accounts);
    } catch { showToast('Failed to load accounts'); }
    setLoading(false);
  }, [adminFetch]);

  const loadOverview = useCallback(async () => {
    try {
      const res = await adminFetch('/api/admin/insights/overview');
      const data = await res.json();
      if (data.success) setOverview(data.overview);
    } catch { /* silent */ }
  }, [adminFetch]);

  const loadCompanyInsights = useCallback(async (companyId) => {
    setCompanyInsights(null);
    try {
      const res = await adminFetch(`/api/admin/insights/company/${companyId}`);
      const data = await res.json();
      if (data.success) setCompanyInsights(data);
    } catch { showToast('Failed to load company insights'); }
  }, [adminFetch]);

  const loadPhones = useCallback(async () => {
    setPhonesLoading(true);
    try {
      const res = await adminFetch('/api/admin/phone-numbers/available');
      const data = await res.json();
      if (data.success) setAvailablePhones(data.numbers || []);
    } catch { /* ignore */ }
    setPhonesLoading(false);
  }, [adminFetch]);

  useEffect(() => { if (authed) { loadAccounts(); loadOverview(); } }, [authed, loadAccounts, loadOverview]);
  useEffect(() => { if (authed && view === 'create') loadPhones(); }, [authed, view, loadPhones]);
  useEffect(() => {
    if (authed && view === 'company' && selectedCompanyId) loadCompanyInsights(selectedCompanyId);
  }, [authed, view, selectedCompanyId, loadCompanyInsights]);

  // ==================== ACTIONS ====================
  const handleImpersonate = async (accountId) => {
    try {
      const res = await adminFetch(`/api/admin/accounts/${accountId}/impersonate`, { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        localStorage.setItem('authToken', data.auth_token);
        localStorage.setItem('authUser', JSON.stringify(data.user));
        localStorage.removeItem('authSubscription');
        window.location.href = '/dashboard';
      } else { showToast(data.error || 'Failed to impersonate'); }
    } catch { showToast('Failed to impersonate'); }
  };

  const handleResendInvite = async (accountId) => {
    try {
      const res = await adminFetch(`/api/admin/accounts/${accountId}/resend-invite`, {
        method: 'POST', body: JSON.stringify({ frontend_url: window.location.origin }),
      });
      const data = await res.json();
      if (data.success) {
        setLastInviteLink(data.invite_link);
        setLastEmailSent(data.email_sent);
        showToast(data.email_sent ? 'Invite email sent!' : 'Invite link generated');
      }
    } catch { showToast('Failed to resend invite'); }
  };

  const handleSearch = async () => {
    if (!searchQuery || searchQuery.length < 2) return;
    setSearchLoading(true);
    try {
      const res = await adminFetch(`/api/admin/search?q=${encodeURIComponent(searchQuery)}`);
      const data = await res.json();
      if (data.success) setSearchResults(data.results);
    } catch { showToast('Search failed'); }
    setSearchLoading(false);
  };

  const openCompany = (id) => {
    setSelectedCompanyId(id);
    setView('company');
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text).then(() => showToast('Copied!'));
  };

  const handleLogout = () => {
    localStorage.removeItem(ADMIN_SECRET_KEY);
    setAuthed(false);
    setSecretInput('');
  };

  // ==================== CREATE ACCOUNT ====================
  const handleCreate = async (e) => {
    e.preventDefault();
    if (!createForm.company_name || !createForm.owner_name || !createForm.email) {
      showToast('Company name, owner name, and email are required'); return;
    }
    setLoading(true);
    try {
      const payload = {
        ...createForm, frontend_url: window.location.origin,
        workers: newWorkers.filter(w => w.name), services: newServices.filter(s => s.name),
      };
      const res = await adminFetch('/api/admin/create-account', { method: 'POST', body: JSON.stringify(payload) });
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
          custom_stripe_price_id: '', custom_monthly_price: '',
        });
        setNewWorkers([]); setNewServices([]);
        loadAccounts(); loadPhones(); loadOverview();
      } else { showToast(data.error || `Failed (${res.status})`); }
    } catch (err) { showToast('Failed to create account: ' + (err.message || 'network error')); }
    setLoading(false);
  };

  // ==================== FILTERED/SORTED ACCOUNTS ====================
  const filteredAccounts = useMemo(() => {
    let list = [...accounts];
    if (accountFilter === 'active') list = list.filter(a => a.subscription_status === 'active');
    else if (accountFilter === 'trial') list = list.filter(a => a.subscription_tier === 'trial');
    else if (accountFilter === 'inactive') list = list.filter(a => a.subscription_status !== 'active');
    else if (accountFilter === 'stripe') list = list.filter(a => a.stripe_connect_account_id);
    else if (accountFilter === 'no_phone') list = list.filter(a => !a.twilio_phone_number);

    if (accountSort === 'newest') list.sort((a, b) => (b.id || 0) - (a.id || 0));
    else if (accountSort === 'oldest') list.sort((a, b) => (a.id || 0) - (b.id || 0));
    else if (accountSort === 'name') list.sort((a, b) => (a.company_name || '').localeCompare(b.company_name || ''));
    return list;
  }, [accounts, accountFilter, accountSort]);

  // ==================== RENDER ====================

  if (!authed) {
    return (
      <div className="ap-page">
        <div className="ap-auth">
          <div className="ap-auth-card">
            <div className="ap-auth-icon"><i className="fas fa-shield-alt"></i></div>
            <h1>Admin Panel</h1>
            <p>Enter your admin secret to continue.</p>
            {authError && <div className="ap-error">{authError}</div>}
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

  const navItems = [
    { id: 'overview', icon: 'chart-pie', label: 'Overview' },
    { id: 'accounts', icon: 'building', label: 'Accounts' },
    { id: 'search', icon: 'search', label: 'Search' },
    { id: 'create', icon: 'plus-circle', label: 'New Account' },
  ];

  return (
    <div className="ap-page">
      {toast && <div className="ap-toast">{toast}</div>}

      {/* Sidebar */}
      <aside className={`ap-sidebar ${sidebarOpen ? 'open' : 'collapsed'}`}>
        <div className="ap-sidebar-header">
          <div className="ap-sidebar-brand">
            <i className="fas fa-shield-alt"></i>
            {sidebarOpen && <span>Admin</span>}
          </div>
          <button className="ap-sidebar-toggle" onClick={() => setSidebarOpen(!sidebarOpen)}>
            <i className={`fas fa-chevron-${sidebarOpen ? 'left' : 'right'}`}></i>
          </button>
        </div>
        <nav className="ap-sidebar-nav">
          {navItems.map(item => (
            <button
              key={item.id}
              className={`ap-sidebar-item ${view === item.id ? 'active' : ''}`}
              onClick={() => { setView(item.id); setLastInviteLink(''); }}
              title={item.label}
            >
              <i className={`fas fa-${item.icon}`}></i>
              {sidebarOpen && <span>{item.label}</span>}
            </button>
          ))}
          {view === 'company' && (
            <button className="ap-sidebar-item active" title="Company Details">
              <i className="fas fa-chart-line"></i>
              {sidebarOpen && <span>Company</span>}
            </button>
          )}
        </nav>
        <div className="ap-sidebar-footer">
          <button className="ap-sidebar-item logout" onClick={handleLogout} title="Logout">
            <i className="fas fa-sign-out-alt"></i>
            {sidebarOpen && <span>Logout</span>}
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="ap-main">
        {/* Invite banner */}
        {lastInviteLink && (
          <div className="ap-invite-banner">
            <div className="ap-invite-icon"><i className="fas fa-check-circle"></i></div>
            <div className="ap-invite-content">
              <strong>{lastEmailSent ? 'Invite email sent!' : 'Invite link ready'}</strong>
              <p>Share this link with the customer to set their password:</p>
              <div className="ap-invite-link-row">
                <code>{lastInviteLink}</code>
                <button onClick={() => copyToClipboard(lastInviteLink)}><i className="fas fa-copy"></i></button>
              </div>
            </div>
            <button className="ap-invite-dismiss" onClick={() => setLastInviteLink('')}><i className="fas fa-times"></i></button>
          </div>
        )}

        {/* ==================== OVERVIEW ==================== */}
        {view === 'overview' && (
          <div className="ap-view">
            <div className="ap-view-header">
              <h1><i className="fas fa-chart-pie"></i> Platform Overview</h1>
              <button className="ap-btn secondary" onClick={() => { loadOverview(); loadAccounts(); }}>
                <i className="fas fa-sync-alt"></i> Refresh
              </button>
            </div>

            {overview ? (
              <>
                <div className="ap-stats-grid">
                  <StatCard icon="building" label="Total Accounts" value={overview.total_accounts} color="#818cf8" />
                  <StatCard icon="check-circle" label="Active Subs" value={overview.tier_counts?.pro || 0} sub={`${overview.tier_counts?.trial || 0} trials`} color="#34d399" />
                  <StatCard icon="phone" label="With AI Phone" value={overview.with_phone} sub={`of ${overview.total_accounts}`} color="#06b6d4" />
                  <StatCard icon="credit-card" label="Stripe Connected" value={overview.stripe_connected} color="#f472b6" />
                  <StatCard icon="calendar-check" label="Total Bookings" value={overview.booking_stats?.total || 0} sub={`${overview.booking_stats?.completed || 0} completed`} color="#a78bfa" />
                  <StatCard icon="phone-alt" label="Total Calls" value={overview.call_stats?.total || 0} sub={`${overview.call_stats?.booked || 0} booked, ${overview.call_stats?.lost || 0} lost`} color="#fbbf24" />
                  <StatCard icon="euro-sign" label="Platform Revenue" value={`€${(overview.total_revenue || 0).toLocaleString('en', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`} color="#34d399" />
                  <StatCard icon="chart-bar" label="Cancelled" value={overview.booking_stats?.cancelled || 0} color="#f87171" />
                </div>

                {/* Subscription breakdown */}
                <div className="ap-card">
                  <h3><i className="fas fa-layer-group"></i> Subscription Tiers</h3>
                  <div className="ap-tier-bars">
                    {Object.entries(overview.tier_counts || {}).map(([tier, count]) => (
                      <div key={tier} className="ap-tier-row">
                        <span className="ap-tier-label">{tier || 'none'}</span>
                        <MiniBar value={count} max={overview.total_accounts} color={tier === 'pro' ? '#34d399' : tier === 'trial' ? '#fbbf24' : '#64748b'} />
                        <span className="ap-tier-count">{count}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Signups chart */}
                {overview.signups_by_month?.length > 0 && (
                  <div className="ap-card">
                    <h3><i className="fas fa-user-plus"></i> Monthly Signups</h3>
                    <div className="ap-bar-chart">
                      {overview.signups_by_month.map(m => (
                        <div key={m.month} className="ap-bar-col">
                          <div className="ap-bar" style={{ height: `${Math.max((m.cnt / Math.max(...overview.signups_by_month.map(x => x.cnt))) * 120, 8)}px` }}>
                            <span className="ap-bar-val">{m.cnt}</span>
                          </div>
                          <span className="ap-bar-label">{m.month.slice(5)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Recent accounts */}
                <div className="ap-card">
                  <h3><i className="fas fa-clock"></i> Recent Accounts</h3>
                  <div className="ap-mini-table">
                    {overview.recent_accounts?.map(acc => (
                      <div key={acc.id} className="ap-mini-row" onClick={() => openCompany(acc.id)}>
                        <div className="ap-mini-row-main">
                          <span className="ap-mini-name">{acc.company_name}</span>
                          <span className="ap-mini-email">{acc.email}</span>
                        </div>
                        <div className="ap-mini-row-meta">
                          <Badge type={acc.subscription_tier === 'pro' ? 'green' : acc.subscription_tier === 'trial' ? 'yellow' : 'gray'}>
                            {acc.subscription_tier || 'none'}{acc.subscription_plan && acc.subscription_tier === 'pro' ? ` (${acc.subscription_plan})` : ''}
                          </Badge>
                          {acc.stripe_connect_account_id && <Badge type="blue">Stripe</Badge>}
                          {acc.twilio_phone_number && <Badge type="blue"><i className="fas fa-phone"></i></Badge>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            ) : (
              <div className="ap-loading"><i className="fas fa-spinner fa-spin"></i> Loading overview...</div>
            )}
          </div>
        )}

        {/* ==================== ACCOUNTS LIST ==================== */}
        {view === 'accounts' && (
          <div className="ap-view">
            <div className="ap-view-header">
              <h1><i className="fas fa-building"></i> Accounts ({filteredAccounts.length})</h1>
              <div className="ap-view-actions">
                <select className="ap-select" value={accountFilter} onChange={e => setAccountFilter(e.target.value)}>
                  <option value="all">All</option>
                  <option value="active">Active</option>
                  <option value="trial">Trial</option>
                  <option value="inactive">Inactive</option>
                  <option value="stripe">Stripe Connected</option>
                  <option value="no_phone">No Phone</option>
                </select>
                <select className="ap-select" value={accountSort} onChange={e => setAccountSort(e.target.value)}>
                  <option value="newest">Newest</option>
                  <option value="oldest">Oldest</option>
                  <option value="name">Name A-Z</option>
                </select>
                <button className="ap-btn primary" onClick={() => setView('create')}>
                  <i className="fas fa-plus"></i> New
                </button>
              </div>
            </div>

            {loading ? (
              <div className="ap-loading"><i className="fas fa-spinner fa-spin"></i> Loading...</div>
            ) : (
              <div className="ap-accounts-grid">
                {filteredAccounts.map(acc => (
                  <div key={acc.id} className="ap-account-card" onClick={() => openCompany(acc.id)}>
                    <div className="ap-account-top">
                      <div className="ap-account-avatar">
                        {(acc.company_name || '?')[0].toUpperCase()}
                      </div>
                      <div className="ap-account-info">
                        <span className="ap-account-name">{acc.company_name}</span>
                        <span className="ap-account-owner">{acc.owner_name}</span>
                        <span className="ap-account-email">{acc.email}</span>
                      </div>
                    </div>
                    <div className="ap-account-meta">
                      <Badge type={acc.subscription_status === 'active' ? 'green' : 'gray'}>
                        {acc.subscription_tier || 'none'}
                      </Badge>
                      <Badge type={acc.easy_setup === false ? 'blue' : 'gray'}>
                        {acc.easy_setup === false ? 'Managed' : 'Self-service'}
                      </Badge>
                      {acc.twilio_phone_number && (
                        <span className="ap-account-phone"><i className="fas fa-phone"></i> {acc.twilio_phone_number}</span>
                      )}
                    </div>
                    <div className="ap-account-actions" onClick={e => e.stopPropagation()}>
                      <button className="ap-btn primary small" onClick={() => handleImpersonate(acc.id)} title="Log in as this account">
                        <i className="fas fa-sign-in-alt"></i> Log In
                      </button>
                      <button className="ap-btn secondary small" onClick={() => handleResendInvite(acc.id)} title="Resend invite">
                        <i className="fas fa-paper-plane"></i>
                      </button>
                      <button className="ap-btn secondary small" onClick={() => openCompany(acc.id)} title="View insights">
                        <i className="fas fa-chart-line"></i>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ==================== COMPANY INSIGHTS ==================== */}
        {view === 'company' && (
          <div className="ap-view">
            <div className="ap-view-header">
              <button className="ap-btn secondary" onClick={() => setView('accounts')}>
                <i className="fas fa-arrow-left"></i> Back
              </button>
              <h1>
                <i className="fas fa-chart-line"></i>{' '}
                {companyInsights?.company?.company_name || 'Loading...'}
              </h1>
              <div className="ap-view-actions">
                <button className="ap-btn primary small" onClick={() => handleImpersonate(selectedCompanyId)}>
                  <i className="fas fa-sign-in-alt"></i> Log In As
                </button>
                <button className="ap-btn secondary small" onClick={() => handleResendInvite(selectedCompanyId)}>
                  <i className="fas fa-paper-plane"></i> Resend Invite
                </button>
              </div>
            </div>

            {companyInsights ? (
              <>
                {/* Company info bar */}
                <div className="ap-company-info-bar">
                  <div className="ap-info-item">
                    <i className="fas fa-user"></i>
                    <span>{companyInsights.company.owner_name}</span>
                  </div>
                  <div className="ap-info-item">
                    <i className="fas fa-envelope"></i>
                    <span>{companyInsights.company.email}</span>
                  </div>
                  {companyInsights.company.phone && (
                    <div className="ap-info-item">
                      <i className="fas fa-phone"></i>
                      <span>{companyInsights.company.phone}</span>
                    </div>
                  )}
                  <div className="ap-info-item">
                    <Badge type={companyInsights.company.subscription_status === 'active' ? 'green' : 'gray'}>
                      {companyInsights.company.subscription_tier || 'none'} — {companyInsights.company.subscription_status}
                    </Badge>
                  </div>
                  {companyInsights.company.trade_type && (
                    <div className="ap-info-item">
                      <i className="fas fa-hard-hat"></i>
                      <span>{companyInsights.company.trade_type}</span>
                    </div>
                  )}
                  {companyInsights.company.twilio_phone_number && (
                    <div className="ap-info-item">
                      <i className="fas fa-robot"></i>
                      <span>AI: {companyInsights.company.twilio_phone_number}</span>
                    </div>
                  )}
                </div>

                {/* KPI cards */}
                <div className="ap-stats-grid">
                  <StatCard icon="calendar-check" label="Total Jobs" value={companyInsights.insights.booking_stats.total} sub={`${companyInsights.insights.booking_stats.completed} completed`} color="#818cf8" />
                  <StatCard icon="euro-sign" label="Total Revenue" value={`€${companyInsights.insights.booking_stats.total_revenue.toLocaleString('en', {minimumFractionDigits:0, maximumFractionDigits:0})}`} sub={`€${companyInsights.insights.booking_stats.unpaid_revenue.toLocaleString()} unpaid`} color="#34d399" />
                  <StatCard icon="credit-card" label="Stripe Payments" value={companyInsights.insights.booking_stats.stripe_payments} sub={`of ${companyInsights.insights.booking_stats.paid_count} paid jobs`} color="#f472b6" />
                  <StatCard icon="phone-alt" label="AI Calls" value={companyInsights.insights.call_stats.total} sub={`${companyInsights.insights.call_stats.booked} → bookings`} color="#fbbf24" />
                  <StatCard icon="users" label="Clients" value={companyInsights.insights.client_count} color="#06b6d4" />
                  <StatCard icon="hard-hat" label="Workers" value={companyInsights.insights.worker_count} color="#a78bfa" />
                  <StatCard icon="concierge-bell" label="Services" value={companyInsights.insights.service_count} color="#fb923c" />
                  <StatCard icon="phone-slash" label="Lost Jobs" value={companyInsights.insights.call_stats.lost_jobs} color="#f87171" />
                </div>

                {/* Stripe & Payment Analysis */}
                <div className="ap-grid-2">
                  <div className="ap-card">
                    <h3><i className="fas fa-credit-card"></i> Stripe Connect</h3>
                    <div className="ap-detail-list">
                      <div className="ap-detail-row">
                        <span>Status</span>
                        <Badge type={companyInsights.insights.stripe_info.connect_status === 'active' ? 'green' : companyInsights.insights.stripe_info.connect_account_id ? 'yellow' : 'gray'}>
                          {companyInsights.insights.stripe_info.connect_status || 'Not connected'}
                        </Badge>
                      </div>
                      <div className="ap-detail-row">
                        <span>Account ID</span>
                        <code>{companyInsights.insights.stripe_info.connect_account_id || '—'}</code>
                      </div>
                      <div className="ap-detail-row">
                        <span>Onboarding</span>
                        <Badge type={companyInsights.insights.stripe_info.connect_onboarding_complete ? 'green' : 'gray'}>
                          {companyInsights.insights.stripe_info.connect_onboarding_complete ? 'Complete' : 'Incomplete'}
                        </Badge>
                      </div>
                      <div className="ap-detail-row">
                        <span>Customer ID</span>
                        <code>{companyInsights.insights.stripe_info.customer_id || '—'}</code>
                      </div>
                    </div>
                  </div>

                  <div className="ap-card">
                    <h3><i className="fas fa-money-bill-wave"></i> Payment Breakdown</h3>
                    <div className="ap-payment-grid">
                      <div className="ap-payment-item">
                        <span className="ap-payment-count">{companyInsights.insights.booking_stats.stripe_payments}</span>
                        <span className="ap-payment-label">Stripe</span>
                        <MiniBar value={companyInsights.insights.booking_stats.stripe_payments} max={companyInsights.insights.booking_stats.total} color="#818cf8" />
                      </div>
                      <div className="ap-payment-item">
                        <span className="ap-payment-count">{companyInsights.insights.booking_stats.cash_payments}</span>
                        <span className="ap-payment-label">Cash</span>
                        <MiniBar value={companyInsights.insights.booking_stats.cash_payments} max={companyInsights.insights.booking_stats.total} color="#34d399" />
                      </div>
                      <div className="ap-payment-item">
                        <span className="ap-payment-count">{companyInsights.insights.booking_stats.bank_payments}</span>
                        <span className="ap-payment-label">Bank</span>
                        <MiniBar value={companyInsights.insights.booking_stats.bank_payments} max={companyInsights.insights.booking_stats.total} color="#fbbf24" />
                      </div>
                      <div className="ap-payment-item">
                        <span className="ap-payment-count">{companyInsights.insights.booking_stats.unpaid_count}</span>
                        <span className="ap-payment-label">Unpaid</span>
                        <MiniBar value={companyInsights.insights.booking_stats.unpaid_count} max={companyInsights.insights.booking_stats.total} color="#f87171" />
                      </div>
                    </div>
                    <div className="ap-payment-summary">
                      <span>Jobs completed: <strong>{companyInsights.insights.booking_stats.completed}</strong></span>
                      <span>Stripe payments: <strong>{companyInsights.insights.booking_stats.stripe_payments}</strong></span>
                      <span>Collection rate: <strong>
                        {companyInsights.insights.booking_stats.completed > 0
                          ? Math.round((companyInsights.insights.booking_stats.paid_count / companyInsights.insights.booking_stats.completed) * 100)
                          : 0}%
                      </strong></span>
                    </div>
                  </div>
                </div>

                {/* Monthly trend */}
                {companyInsights.insights.monthly_bookings?.length > 0 && (
                  <div className="ap-card">
                    <h3><i className="fas fa-chart-bar"></i> Monthly Activity</h3>
                    <div className="ap-monthly-table">
                      <div className="ap-monthly-header">
                        <span>Month</span><span>Jobs</span><span>Completed</span><span>Stripe</span><span>Revenue</span>
                      </div>
                      {companyInsights.insights.monthly_bookings.map(m => (
                        <div key={m.month} className="ap-monthly-row">
                          <span>{m.month}</span>
                          <span>{m.total}</span>
                          <span>{m.completed}</span>
                          <span>{m.stripe_paid}</span>
                          <span>€{m.revenue.toLocaleString('en', {minimumFractionDigits:0, maximumFractionDigits:0})}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Call stats & recent calls */}
                <div className="ap-grid-2">
                  <div className="ap-card">
                    <h3><i className="fas fa-phone-alt"></i> Call Performance</h3>
                    <div className="ap-detail-list">
                      <div className="ap-detail-row"><span>Total Calls</span><strong>{companyInsights.insights.call_stats.total}</strong></div>
                      <div className="ap-detail-row"><span>Bookings Made</span><strong>{companyInsights.insights.call_stats.booked}</strong></div>
                      <div className="ap-detail-row"><span>Callbacks Requested</span><strong>{companyInsights.insights.call_stats.callbacks}</strong></div>
                      <div className="ap-detail-row"><span>Info Only</span><strong>{companyInsights.insights.call_stats.info_only}</strong></div>
                      <div className="ap-detail-row"><span>Lost Jobs</span><strong style={{color:'#f87171'}}>{companyInsights.insights.call_stats.lost_jobs}</strong></div>
                      <div className="ap-detail-row"><span>Avg Duration</span><strong>{companyInsights.insights.call_stats.avg_duration}s</strong></div>
                      <div className="ap-detail-row">
                        <span>Booking Rate</span>
                        <strong>
                          {companyInsights.insights.call_stats.total > 0
                            ? Math.round((companyInsights.insights.call_stats.booked / companyInsights.insights.call_stats.total) * 100)
                            : 0}%
                        </strong>
                      </div>
                    </div>
                  </div>

                  <div className="ap-card">
                    <h3><i className="fas fa-history"></i> Recent Calls</h3>
                    {companyInsights.insights.recent_calls?.length > 0 ? (
                      <div className="ap-recent-calls">
                        {companyInsights.insights.recent_calls.map(call => (
                          <div key={call.id} className="ap-call-item">
                            <div className="ap-call-top">
                              <span className="ap-call-name">{call.caller_name || call.phone_number || 'Unknown'}</span>
                              <Badge type={call.call_outcome === 'booking_made' ? 'green' : call.is_lost_job ? 'red' : 'gray'}>
                                {call.call_outcome?.replace(/_/g, ' ') || 'unknown'}
                              </Badge>
                            </div>
                            {call.ai_summary && <p className="ap-call-summary">{call.ai_summary.slice(0, 120)}...</p>}
                            <span className="ap-call-time">{new Date(call.created_at).toLocaleString()}</span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="ap-empty">No calls recorded yet</p>
                    )}
                  </div>
                </div>

                {/* Feature toggles */}
                <div className="ap-card">
                  <h3><i className="fas fa-sliders-h"></i> Feature Toggles</h3>
                  <div className="ap-toggles-grid">
                    {[
                      ['ai_enabled', 'AI Enabled', companyInsights.company.ai_enabled],
                      ['show_finances_tab', 'Finances Tab', companyInsights.company.show_finances_tab],
                      ['show_insights_tab', 'Insights Tab', companyInsights.company.show_insights_tab],
                      ['show_invoice_buttons', 'Invoice Buttons', companyInsights.company.show_invoice_buttons],
                      ['send_confirmation_sms', 'Confirmation SMS', companyInsights.company.send_confirmation_sms],
                      ['send_reminder_sms', 'Reminder SMS', companyInsights.company.send_reminder_sms],
                      ['gcal_invite_workers', 'GCal Worker Invites', companyInsights.company.gcal_invite_workers],
                    ].map(([key, label, val]) => (
                      <div key={key} className="ap-toggle-item">
                        <span className={`ap-toggle-dot ${val !== false ? 'on' : 'off'}`}></span>
                        <span>{label}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            ) : (
              <div className="ap-loading"><i className="fas fa-spinner fa-spin"></i> Loading insights...</div>
            )}
          </div>
        )}

        {/* ==================== SEARCH ==================== */}
        {view === 'search' && (
          <div className="ap-view">
            <div className="ap-view-header">
              <h1><i className="fas fa-search"></i> Search</h1>
            </div>
            <div className="ap-search-bar">
              <input
                type="text"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSearch()}
                placeholder="Search companies, clients, phone numbers..."
                autoFocus
              />
              <button className="ap-btn primary" onClick={handleSearch} disabled={searchLoading}>
                {searchLoading ? <i className="fas fa-spinner fa-spin"></i> : <i className="fas fa-search"></i>}
              </button>
            </div>

            {searchResults && (
              <div className="ap-search-results">
                {/* Companies */}
                {searchResults.companies?.length > 0 && (
                  <div className="ap-search-section">
                    <h3><i className="fas fa-building"></i> Companies ({searchResults.companies.length})</h3>
                    {searchResults.companies.map(c => (
                      <div key={c.id} className="ap-search-item" onClick={() => openCompany(c.id)}>
                        <div className="ap-search-item-main">
                          <strong>{c.company_name}</strong>
                          <span>{c.owner_name} — {c.email}</span>
                        </div>
                        <div className="ap-search-item-meta">
                          <Badge type={c.subscription_status === 'active' ? 'green' : 'gray'}>{c.subscription_tier}</Badge>
                          {c.twilio_phone_number && <span className="ap-mini-phone">{c.twilio_phone_number}</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Clients */}
                {searchResults.clients?.length > 0 && (
                  <div className="ap-search-section">
                    <h3><i className="fas fa-users"></i> Clients ({searchResults.clients.length})</h3>
                    {searchResults.clients.map(c => (
                      <div key={c.id} className="ap-search-item" onClick={() => openCompany(c.company_id)}>
                        <div className="ap-search-item-main">
                          <strong>{c.name}</strong>
                          <span>{c.phone} {c.email && `— ${c.email}`}</span>
                        </div>
                        <span className="ap-search-company-tag">{c.company_name}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Calls */}
                {searchResults.calls?.length > 0 && (
                  <div className="ap-search-section">
                    <h3><i className="fas fa-phone-alt"></i> Call Logs ({searchResults.calls.length})</h3>
                    {searchResults.calls.map(c => (
                      <div key={c.id} className="ap-search-item" onClick={() => openCompany(c.company_id)}>
                        <div className="ap-search-item-main">
                          <strong>{c.caller_name || c.phone_number}</strong>
                          <span>{c.ai_summary?.slice(0, 100)}</span>
                        </div>
                        <div className="ap-search-item-meta">
                          <Badge type={c.call_outcome === 'booking_made' ? 'green' : 'gray'}>{c.call_outcome?.replace(/_/g, ' ')}</Badge>
                          <span className="ap-search-company-tag">{c.company_name}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {searchResults.companies?.length === 0 && searchResults.clients?.length === 0 && searchResults.calls?.length === 0 && (
                  <div className="ap-empty-search">
                    <i className="fas fa-search"></i>
                    <p>No results found for "{searchQuery}"</p>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ==================== CREATE ACCOUNT ==================== */}
        {view === 'create' && (
          <div className="ap-view">
            <div className="ap-view-header">
              <h1><i className="fas fa-plus-circle"></i> Create New Account</h1>
            </div>

            <form onSubmit={handleCreate} className="ap-form">
              <div className="ap-card">
                <h3><i className="fas fa-building"></i> Business Info</h3>
                <div className="ap-form-grid">
                  <div className="ap-field">
                    <label>Company Name *</label>
                    <input value={createForm.company_name} onChange={e => setCreateForm(p => ({...p, company_name: e.target.value}))} required />
                  </div>
                  <div className="ap-field">
                    <label>Owner Name *</label>
                    <input value={createForm.owner_name} onChange={e => setCreateForm(p => ({...p, owner_name: e.target.value}))} required />
                  </div>
                  <div className="ap-field">
                    <label>Email *</label>
                    <input type="email" value={createForm.email} onChange={e => setCreateForm(p => ({...p, email: e.target.value}))} required />
                  </div>
                  <div className="ap-field">
                    <label>Phone</label>
                    <input value={createForm.phone} onChange={e => setCreateForm(p => ({...p, phone: e.target.value}))} placeholder="085 123 4567" />
                  </div>
                  <div className="ap-field">
                    <label>Trade Type</label>
                    <select value={createForm.trade_type} onChange={e => setCreateForm(p => ({...p, trade_type: e.target.value}))}>
                      <option value="">Select...</option>
                      {['Plumbing','Electrical','Roofing','HVAC','Carpentry','Painting','Landscaping','General Contracting','Flooring','Masonry','Other'].map(t => <option key={t} value={t}>{t}</option>)}
                    </select>
                  </div>
                  <div className="ap-field">
                    <label>Address</label>
                    <input value={createForm.address} onChange={e => setCreateForm(p => ({...p, address: e.target.value}))} />
                  </div>
                </div>
              </div>

              <div className="ap-card">
                <h3><i className="fas fa-clock"></i> Business Hours</h3>
                <div className="ap-hours-picker">
                  <div className="ap-hours-time">
                    <div className="ap-time-group">
                      <label>Start</label>
                      <select value={hoursConfig.startHour} onChange={e => setHoursConfig(p => ({...p, startHour: e.target.value}))}>
                        {[...Array(12)].map((_, i) => <option key={i+1} value={i+1}>{i+1}</option>)}
                      </select>
                      <select value={hoursConfig.startPeriod} onChange={e => setHoursConfig(p => ({...p, startPeriod: e.target.value}))}>
                        <option value="AM">AM</option><option value="PM">PM</option>
                      </select>
                    </div>
                    <span className="ap-time-sep">to</span>
                    <div className="ap-time-group">
                      <label>End</label>
                      <select value={hoursConfig.endHour} onChange={e => setHoursConfig(p => ({...p, endHour: e.target.value}))}>
                        {[...Array(12)].map((_, i) => <option key={i+1} value={i+1}>{i+1}</option>)}
                      </select>
                      <select value={hoursConfig.endPeriod} onChange={e => setHoursConfig(p => ({...p, endPeriod: e.target.value}))}>
                        <option value="AM">AM</option><option value="PM">PM</option>
                      </select>
                    </div>
                  </div>
                  <div className="ap-hours-days">
                    {dayLabels.map(d => (
                      <label key={d.key} className={`ap-day-chip ${hoursConfig.days[d.key] ? 'active' : ''}`}>
                        <input type="checkbox" checked={hoursConfig.days[d.key]} onChange={() => setHoursConfig(p => ({...p, days: {...p.days, [d.key]: !p.days[d.key]}}))} />
                        {d.label}
                      </label>
                    ))}
                  </div>
                  <label className="ap-emergency-check">
                    <input type="checkbox" checked={hoursConfig.emergency} onChange={e => setHoursConfig(p => ({...p, emergency: e.target.checked}))} />
                    24/7 emergency available
                  </label>
                  <div className="ap-hours-preview">Preview: {formatHours()}</div>
                </div>
              </div>

              <div className="ap-card">
                <h3><i className="fas fa-robot"></i> AI Receptionist</h3>
                <div className="ap-form-grid">
                  <div className="ap-field full">
                    <label>Coverage Area</label>
                    <input value={createForm.coverage_area} onChange={e => setCreateForm(p => ({...p, coverage_area: e.target.value}))} placeholder="e.g., Dublin and surrounding areas" />
                  </div>
                  <div className="ap-field full">
                    <label>Company Context (AI Knowledge)</label>
                    <textarea value={createForm.company_context} onChange={e => setCreateForm(p => ({...p, company_context: e.target.value}))} rows={6}
                      placeholder="Parking info, warranties, certifications, policies — anything the AI should know" />
                  </div>
                </div>
              </div>

              <div className="ap-card">
                <h3><i className="fas fa-cog"></i> Phone & Subscription</h3>
                <div className="ap-form-grid">
                  <div className="ap-field">
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
                  <div className="ap-field">
                    <label>Subscription</label>
                    <select value={createForm.subscription_tier} onChange={e => setCreateForm(p => ({...p, subscription_tier: e.target.value, subscription_status: e.target.value === 'none' ? 'inactive' : 'active'}))}>
                      <option value="none">None</option>
                      <option value="trial">Trial</option>
                      <option value="pro">Pro (Active)</option>
                    </select>
                  </div>
                  <div className="ap-field">
                    <label>Custom Price (€/month)</label>
                    <input type="number" step="0.01" min="0" value={createForm.custom_monthly_price} onChange={e => setCreateForm(p => ({...p, custom_monthly_price: e.target.value}))} placeholder="Leave blank for default" />
                  </div>
                  <div className="ap-field">
                    <label>Custom Stripe Price ID</label>
                    <input value={createForm.custom_stripe_price_id} onChange={e => setCreateForm(p => ({...p, custom_stripe_price_id: e.target.value}))} placeholder="price_xxx (from Stripe)" />
                  </div>
                </div>
              </div>

              <div className="ap-card">
                <h3><i className="fas fa-hard-hat"></i> Workers ({newWorkers.length})</h3>
                {newWorkers.map((w, i) => (
                  <div key={i} className="ap-inline-row">
                    <input placeholder="Name *" value={w.name} onChange={e => { const u = [...newWorkers]; u[i] = {...u[i], name: e.target.value}; setNewWorkers(u); }} />
                    <input placeholder="Phone" value={w.phone} onChange={e => { const u = [...newWorkers]; u[i] = {...u[i], phone: e.target.value}; setNewWorkers(u); }} />
                    <input placeholder="Email" value={w.email || ''} onChange={e => { const u = [...newWorkers]; u[i] = {...u[i], email: e.target.value}; setNewWorkers(u); }} />
                    <input placeholder="Specialty" value={w.trade_specialty} onChange={e => { const u = [...newWorkers]; u[i] = {...u[i], trade_specialty: e.target.value}; setNewWorkers(u); }} />
                    <button type="button" className="ap-btn danger small" onClick={() => setNewWorkers(newWorkers.filter((_, j) => j !== i))}><i className="fas fa-trash"></i></button>
                  </div>
                ))}
                <button type="button" className="ap-btn secondary small" onClick={() => setNewWorkers([...newWorkers, { name: '', phone: '', email: '', trade_specialty: '' }])}>
                  <i className="fas fa-plus"></i> Add Worker
                </button>
              </div>

              <div className="ap-card">
                <h3><i className="fas fa-concierge-bell"></i> Services ({newServices.length})</h3>
                {newServices.map((s, i) => (
                  <div key={i} className="ap-inline-row">
                    <input placeholder="Service name *" value={s.name} onChange={e => { const u = [...newServices]; u[i] = {...u[i], name: e.target.value}; setNewServices(u); }} />
                    <input placeholder="Price (€)" type="number" value={s.price || ''} onChange={e => { const u = [...newServices]; u[i] = {...u[i], price: e.target.value}; setNewServices(u); }} style={{width: 100}} />
                    <input placeholder="Duration (min)" type="number" value={s.duration_minutes || ''} onChange={e => { const u = [...newServices]; u[i] = {...u[i], duration_minutes: e.target.value}; setNewServices(u); }} style={{width: 130}} />
                    <input placeholder="Category" value={s.category || ''} onChange={e => { const u = [...newServices]; u[i] = {...u[i], category: e.target.value}; setNewServices(u); }} style={{width: 120}} />
                    <button type="button" className="ap-btn danger small" onClick={() => setNewServices(newServices.filter((_, j) => j !== i))}><i className="fas fa-trash"></i></button>
                  </div>
                ))}
                <button type="button" className="ap-btn secondary small" onClick={() => setNewServices([...newServices, { name: '', price: '', duration_minutes: '', category: 'General' }])}>
                  <i className="fas fa-plus"></i> Add Service
                </button>
              </div>

              <div className="ap-form-actions">
                <button type="submit" className="ap-btn primary large" disabled={loading}>
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
