import { useState, useMemo, useCallback, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../../context/AuthContext';
import { formatPhone, formatCurrency } from '../../utils/helpers';
import { useToast } from '../Toast';
import { getLeads, createLead, updateLead, deleteLead, convertLead, getCrmStats, getCompanyReviews, generatePortalLink } from '../../services/api';
import AddClientModal from '../modals/AddClientModal';
import CustomerDetailModal from '../modals/CustomerDetailModal';
import PipelineTab from './PipelineTab';
import './CrmTab.css';
import './SharedDashboard.css';

function formatRelativeTime(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  const now = new Date();
  const diffMs = now - d;
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays < 1) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays}d ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
  if (diffDays < 365) return `${Math.floor(diffDays / 30)}mo ago`;
  return `${Math.floor(diffDays / 365)}y ago`;
}

const PIPELINE_STAGES = [
  { key: 'new', label: 'New', icon: 'fa-sparkles', color: '#3b82f6' },
  { key: 'contacted', label: 'Contacted', icon: 'fa-phone-alt', color: '#8b5cf6' },
  { key: 'quoted', label: 'Quoted', icon: 'fa-file-invoice', color: '#f59e0b' },
  { key: 'won', label: 'Won', icon: 'fa-trophy', color: '#10b981' },
  { key: 'lost', label: 'Lost', icon: 'fa-times-circle', color: '#ef4444' },
];

const LEAD_SOURCES = [
  { key: 'phone', label: 'Phone Call', icon: 'fa-phone' },
  { key: 'website', label: 'Website', icon: 'fa-globe' },
  { key: 'referral', label: 'Referral', icon: 'fa-user-friends' },
  { key: 'social', label: 'Social Media', icon: 'fa-share-alt' },
  { key: 'manual', label: 'Manual', icon: 'fa-pen' },
  { key: 'ai_call', label: 'AI Call', icon: 'fa-robot' },
];

const CRM_VIEWS = [
  { key: 'customers', label: 'Customers', icon: 'fa-users' },
  { key: 'leads', label: 'Leads', icon: 'fa-stream' },
  { key: 'quotes', label: 'Quotes', icon: 'fa-file-invoice' },
  { key: 'reviews', label: 'Reviews', icon: 'fa-star' },
];

function CrmTab({ clients, bookings = [] }) {
  const { hasActiveSubscription } = useAuth();
  const isSubscriptionActive = hasActiveSubscription();
  const { addToast } = useToast();
  const queryClient = useQueryClient();
  const [activeView, setActiveView] = useState('customers');
  const [searchTerm, setSearchTerm] = useState('');
  const [showAddLead, setShowAddLead] = useState(false);
  const [showAddClient, setShowAddClient] = useState(false);
  const [selectedClientId, setSelectedClientId] = useState(null);
  const [editingLead, setEditingLead] = useState(null);
  const [customerSort, setCustomerSort] = useState('recent');
  const [customerFilter, setCustomerFilter] = useState('all');
  const [deleteConfirm, setDeleteConfirm] = useState(null);

  // Fetch leads
  const { data: leadsData } = useQuery({
    queryKey: ['leads'],
    queryFn: async () => (await getLeads()).data,
  });
  const leads = leadsData?.leads || [];

  // Fetch CRM stats
  const { data: crmStats } = useQuery({
    queryKey: ['crm-stats'],
    queryFn: async () => (await getCrmStats()).data,
  });

  // Fetch reviews
  const { data: reviewsData } = useQuery({
    queryKey: ['reviews'],
    queryFn: async () => (await getCompanyReviews()).data,
  });
  const reviews = reviewsData?.reviews || [];

  // Mutations
  const createMutation = useMutation({
    mutationFn: createLead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leads'] });
      queryClient.invalidateQueries({ queryKey: ['crm-stats'] });
      setShowAddLead(false);
      addToast('Lead created', 'success');
    },
    onError: (e) => addToast(e.response?.data?.error || 'Failed to create lead', 'error'),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, ...data }) => updateLead(id, data),
    onMutate: async ({ id, ...data }) => {
      // Optimistic update: immediately move the lead in the UI
      await queryClient.cancelQueries({ queryKey: ['leads'] });
      const previous = queryClient.getQueryData(['leads']);
      if (data.stage && previous?.leads) {
        queryClient.setQueryData(['leads'], {
          ...previous,
          leads: previous.leads.map(l => l.id === id ? { ...l, ...data } : l),
        });
      }
      return { previous };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leads'] });
      queryClient.invalidateQueries({ queryKey: ['crm-stats'] });
      setEditingLead(null);
    },
    onError: (e, variables, context) => {
      // Roll back on error
      if (context?.previous) queryClient.setQueryData(['leads'], context.previous);
      addToast(e.response?.data?.error || 'Failed to update lead', 'error');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteLead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leads'] });
      queryClient.invalidateQueries({ queryKey: ['crm-stats'] });
      addToast('Lead removed', 'success');
    },
  });

  const convertMutation = useMutation({
    mutationFn: convertLead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leads'] });
      queryClient.invalidateQueries({ queryKey: ['crm-stats'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      addToast('Lead converted to customer', 'success');
    },
    onError: (e) => addToast(e.response?.data?.error || 'Failed to convert lead', 'error'),
  });

  const handleStageDrop = useCallback((leadId, newStage) => {
    updateMutation.mutate({ id: leadId, stage: newStage });
  }, [updateMutation]);

  // Clear search when switching views
  const handleViewSwitch = useCallback((view) => {
    setActiveView(view);
    setSearchTerm('');
  }, []);

  // Delete with confirmation
  const handleDeleteLead = useCallback((id) => {
    setDeleteConfirm(id);
  }, []);
  const confirmDeleteLead = useCallback(() => {
    if (deleteConfirm) {
      deleteMutation.mutate(deleteConfirm);
      setDeleteConfirm(null);
    }
  }, [deleteConfirm, deleteMutation]);

  // Customer health scoring
  const customerHealth = useMemo(() => {
    const healthData = crmStats?.customer_health || [];
    const now = new Date();

    // If CRM stats haven't loaded yet, fall back to the clients prop
    const sourceData = healthData.length > 0 ? healthData : clients.map(c => ({
      id: c.id, name: c.name, phone: c.phone, email: c.email, created_at: c.created_at,
      total_jobs: c.total_bookings || 0, completed_jobs: 0, total_revenue: 0, last_job_date: null,
    }));

    return sourceData.map(c => {
      const daysSinceLastJob = c.last_job_date
        ? Math.floor((now - new Date(c.last_job_date)) / (1000 * 60 * 60 * 24))
        : 999;
      const isRepeat = c.completed_jobs > 1;
      const revenue = parseFloat(c.total_revenue) || 0;

      // Health score: 0-100
      let score = 50;
      if (c.completed_jobs >= 5) score += 20;
      else if (c.completed_jobs >= 2) score += 10;
      if (daysSinceLastJob < 30) score += 20;
      else if (daysSinceLastJob < 90) score += 10;
      else if (daysSinceLastJob > 180) score -= 20;
      if (revenue > 1000) score += 10;
      score = Math.max(0, Math.min(100, score));

      let status = 'healthy';
      if (score < 30) status = 'at-risk';
      else if (score < 60) status = 'needs-attention';

      // Auto-segment
      let segment = 'regular';
      if (c.completed_jobs === 0 && c.total_jobs === 0) segment = 'new';
      else if (revenue > 500 && isRepeat) segment = 'vip';
      else if (daysSinceLastJob > 120) segment = 'dormant';
      else if (isRepeat) segment = 'loyal';

      return { ...c, score, status, segment, daysSinceLastJob, revenue };
    });
  }, [crmStats, clients]);

  // Filtered & sorted customers
  const filteredCustomers = useMemo(() => {
    let list = customerHealth;
    if (searchTerm.trim()) {
      const term = searchTerm.toLowerCase();
      list = list.filter(c =>
        c.name?.toLowerCase().includes(term) ||
        c.phone?.includes(term) ||
        c.email?.toLowerCase().includes(term)
      );
    }
    if (customerFilter !== 'all') {
      list = list.filter(c => c.segment === customerFilter);
    }
    if (customerSort === 'recent') list = [...list].sort((a, b) => (b.last_job_date || '').localeCompare(a.last_job_date || ''));
    else if (customerSort === 'revenue') list = [...list].sort((a, b) => b.revenue - a.revenue);
    else if (customerSort === 'health') list = [...list].sort((a, b) => a.score - b.score);
    else if (customerSort === 'name') list = [...list].sort((a, b) => (a.name || '').localeCompare(b.name || ''));
    return list;
  }, [customerHealth, searchTerm, customerFilter, customerSort]);

  // Pipeline stats
  const pipelineStats = useMemo(() => {
    const counts = crmStats?.lead_counts || {};
    const active = (counts.new || 0) + (counts.contacted || 0) + (counts.quoted || 0);
    const won = counts.won || 0;
    const lost = counts.lost || 0;
    const total = active + won + lost;
    const conversionRate = total > 0 ? Math.round((won / total) * 100) : 0;
    // Total pipeline value from active leads
    const pipelineValue = leads
      .filter(l => l.stage !== 'won' && l.stage !== 'lost')
      .reduce((sum, l) => sum + (parseFloat(l.estimated_value) || 0), 0);
    return { active, won, lost, total, conversionRate, counts, pipelineValue };
  }, [crmStats, leads]);

  // Reviews stats
  const reviewStats = useMemo(() => {
    const submitted = reviews.filter(r => r.submitted_at);
    const pending = reviews.filter(r => !r.submitted_at);
    const avgRating = submitted.length > 0
      ? (submitted.reduce((s, r) => s + r.rating, 0) / submitted.length).toFixed(1)
      : null;
    return { submitted, pending, avgRating, total: reviews.length };
  }, [reviews]);

  // Segment counts
  const segmentCounts = useMemo(() => {
    const counts = { all: customerHealth.length, vip: 0, loyal: 0, regular: 0, new: 0, dormant: 0 };
    customerHealth.forEach(c => { if (counts[c.segment] !== undefined) counts[c.segment]++; });
    return counts;
  }, [customerHealth]);

  return (
    <div className="crm-tab">
      {/* CRM Header */}
      <div className="crm-header">
        <div className="crm-header-left">
          <h2>CRM</h2>
          <div className="crm-view-switcher">
            {CRM_VIEWS.map(v => (
              <button key={v.key} className={`crm-view-btn ${activeView === v.key ? 'active' : ''}`}
                onClick={() => handleViewSwitch(v.key)}>
                <i className={`fas ${v.icon}`}></i> {v.label}
              </button>
            ))}
          </div>
        </div>
        <div className="crm-header-right">
          <div className="dash-search">
            <i className="fas fa-search"></i>
            <input type="text" placeholder={activeView === 'leads' ? 'Search leads...' : activeView === 'customers' ? 'Search customers...' : activeView === 'quotes' ? 'Search quotes...' : 'Search reviews...'}
              value={searchTerm} onChange={e => setSearchTerm(e.target.value)} />
            {searchTerm && <button className="dash-search-clear" onClick={() => setSearchTerm('')}><i className="fas fa-times"></i></button>}
          </div>
          {activeView === 'leads' && (
            <button className="btn-add" onClick={() => setShowAddLead(true)}>
              <i className="fas fa-plus"></i> Add Lead
            </button>
          )}
          {activeView === 'customers' && (
            <button className="btn-add" onClick={() => {
              if (!isSubscriptionActive) { addToast('Please upgrade your plan to add customers', 'warning'); return; }
              setShowAddClient(true);
            }}>
              <i className={`fas ${isSubscriptionActive ? 'fa-plus' : 'fa-lock'}`}></i> Add Customer
            </button>
          )}
        </div>
      </div>

      {/* Leads View */}
      {activeView === 'leads' && (
        <PipelineView
          leads={leads}
          searchTerm={searchTerm}
          pipelineStats={pipelineStats}
          onStageDrop={handleStageDrop}
          onEdit={setEditingLead}
          onDelete={handleDeleteLead}
          onConvert={id => convertMutation.mutate(id)}
        />
      )}

      {/* Quotes View — renders the PipelineTab component */}
      {activeView === 'quotes' && (
        <QuotePipelineEmbed />
      )}

      {/* Customers View */}
      {activeView === 'customers' && (
        <CustomersView
          customers={filteredCustomers}
          segmentCounts={segmentCounts}
          customerFilter={customerFilter}
          setCustomerFilter={setCustomerFilter}
          customerSort={customerSort}
          setCustomerSort={setCustomerSort}
          onSelectClient={setSelectedClientId}
          crmStats={crmStats}
          onPortalLink={(clientId) => {
            generatePortalLink(clientId).then(res => {
              navigator.clipboard?.writeText(res.data.link);
              addToast('Portal link copied to clipboard', 'success');
            }).catch(() => addToast('Failed to generate portal link', 'error'));
          }}
        />
      )}

      {/* Reviews View */}
      {activeView === 'reviews' && (
        <ReviewsView reviews={reviews} reviewStats={reviewStats} />
      )}

      {/* Modals */}
      {showAddLead && (
        <LeadFormModal
          onClose={() => setShowAddLead(false)}
          onSubmit={data => createMutation.mutate(data)}
          isPending={createMutation.isPending}
        />
      )}
      {editingLead && (
        <LeadFormModal
          lead={editingLead}
          onClose={() => setEditingLead(null)}
          onSubmit={data => updateMutation.mutate({ id: editingLead.id, ...data })}
          isPending={updateMutation.isPending}
        />
      )}
      <AddClientModal isOpen={showAddClient} onClose={() => setShowAddClient(false)} />
      <CustomerDetailModal isOpen={!!selectedClientId} onClose={() => setSelectedClientId(null)} clientId={selectedClientId} />

      {/* Delete Confirmation */}
      {deleteConfirm && (
        <div className="crm-modal-overlay" onClick={() => setDeleteConfirm(null)}>
          <div className="crm-delete-confirm" onClick={e => e.stopPropagation()}>
            <div className="crm-delete-icon"><i className="fas fa-exclamation-triangle"></i></div>
            <h3>Delete this lead?</h3>
            <p>This action cannot be undone.</p>
            <div className="crm-delete-actions">
              <button className="btn btn-secondary" onClick={() => setDeleteConfirm(null)}>Cancel</button>
              <button className="btn btn-danger" onClick={confirmDeleteLead}>Delete</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ============================================
   PIPELINE VIEW
   ============================================ */
function PipelineView({ leads, searchTerm, pipelineStats, onStageDrop, onEdit, onDelete, onConvert }) {
  const [dragOverStage, setDragOverStage] = useState(null);

  const filteredLeads = useMemo(() => {
    if (!searchTerm.trim()) return leads;
    const term = searchTerm.toLowerCase();
    return leads.filter(l =>
      l.name?.toLowerCase().includes(term) ||
      l.phone?.includes(term) ||
      l.email?.toLowerCase().includes(term) ||
      l.service_interest?.toLowerCase().includes(term)
    );
  }, [leads, searchTerm]);

  const leadsByStage = useMemo(() => {
    const grouped = {};
    PIPELINE_STAGES.forEach(s => { grouped[s.key] = []; });
    filteredLeads.forEach(l => {
      if (grouped[l.stage]) grouped[l.stage].push(l);
      else grouped.new.push(l);
    });
    return grouped;
  }, [filteredLeads]);

  const handleDragStart = (e, leadId) => {
    e.dataTransfer.setData('text/plain', leadId);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e, stage) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    setDragOverStage(stage);
  };

  const handleDrop = (e, stage) => {
    e.preventDefault();
    const leadId = parseInt(e.dataTransfer.getData('text/plain'));
    if (leadId) onStageDrop(leadId, stage);
    setDragOverStage(null);
  };

  return (
    <>
      {/* Pipeline Stats - compact strip */}
      <div className="crm-mini-stats">
        <span className="crm-mini-stat"><i className="fas fa-stream" style={{ color: '#3b82f6' }}></i> {pipelineStats.active} active</span>
        <span className="crm-mini-stat"><i className="fas fa-trophy" style={{ color: '#10b981' }}></i> {pipelineStats.won} won</span>
        <span className="crm-mini-stat"><i className="fas fa-coins" style={{ color: '#f59e0b' }}></i> {pipelineStats.pipelineValue > 0 ? formatCurrency(pipelineStats.pipelineValue) : '—'} pipeline</span>
        <span className="crm-mini-stat"><i className="fas fa-percentage" style={{ color: '#8b5cf6' }}></i> {pipelineStats.conversionRate}% conversion</span>
      </div>

      {/* Kanban Board — always visible */}
      <div className="crm-pipeline">
        {PIPELINE_STAGES.map(stage => (
          <div key={stage.key}
            className={`pipeline-column ${dragOverStage === stage.key ? 'drag-over' : ''}`}
            onDragOver={e => handleDragOver(e, stage.key)}
            onDragLeave={() => setDragOverStage(null)}
            onDrop={e => handleDrop(e, stage.key)}>
            <div className="pipeline-column-header">
              <div className="pipeline-stage-label">
                <span className="pipeline-stage-dot" style={{ background: stage.color }}></span>
                <span>{stage.label}</span>
                <span className="pipeline-count">{leadsByStage[stage.key]?.length || 0}</span>
              </div>
            </div>
            <div className="pipeline-cards">
              {(leadsByStage[stage.key] || []).map(lead => (
                <LeadCard key={lead.id} lead={lead} stage={stage}
                  onDragStart={handleDragStart} onEdit={onEdit}
                  onDelete={onDelete} onConvert={onConvert} />
              ))}
              {(leadsByStage[stage.key] || []).length === 0 && (
                <div className="pipeline-empty">
                  <i className={`fas ${stage.icon}`}></i>
                  <span>{stage.key === 'new' ? 'Add your first lead' : 'No leads'}</span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}


/* ============================================
   LEAD CARD
   ============================================ */
function LeadCard({ lead, stage, onDragStart, onEdit, onDelete, onConvert }) {
  const [showActions, setShowActions] = useState(false);
  const sourceInfo = LEAD_SOURCES.find(s => s.key === lead.source) || LEAD_SOURCES[4];

  return (
    <div className={`lead-card ${lead.follow_up_date && new Date(lead.follow_up_date) < new Date() && lead.stage !== 'won' && lead.stage !== 'lost' ? 'has-overdue' : ''}`}
      draggable onDragStart={e => onDragStart(e, lead.id)}
      onMouseEnter={() => setShowActions(true)} onMouseLeave={() => setShowActions(false)}>
      <div className="lead-card-header">
        <span className="lead-name">{lead.name}</span>
        {showActions && (
          <div className="lead-actions">
            <button className="lead-action-btn" onClick={() => onEdit(lead)} title="Edit">
              <i className="fas fa-pen"></i>
            </button>
            {lead.stage !== 'won' && lead.stage !== 'lost' && (
              <button className="lead-action-btn convert" onClick={() => onConvert(lead.id)} title="Convert to customer">
                <i className="fas fa-user-plus"></i>
              </button>
            )}
            <button className="lead-action-btn delete" onClick={() => onDelete(lead.id)} title="Delete">
              <i className="fas fa-trash"></i>
            </button>
          </div>
        )}
      </div>
      {lead.service_interest && (
        <div className="lead-service">
          <i className="fas fa-concierge-bell"></i> {lead.service_interest}
        </div>
      )}
      <div className="lead-card-meta">
        {lead.phone && <span><i className="fas fa-phone"></i> {formatPhone(lead.phone)}</span>}
        {lead.email && <span><i className="fas fa-envelope"></i> {lead.email}</span>}
      </div>
      <div className="lead-card-footer">
        <span className="lead-source-badge">
          <i className={`fas ${sourceInfo.icon}`}></i> {sourceInfo.label}
        </span>
        {lead.estimated_value > 0 && (
          <span className="lead-value">{formatCurrency(lead.estimated_value)}</span>
        )}
        {lead.follow_up_date && (() => {
          const isOverdue = new Date(lead.follow_up_date) < new Date() && lead.stage !== 'won' && lead.stage !== 'lost';
          return (
            <span className={`lead-followup ${isOverdue ? 'overdue' : ''}`} title="Follow-up date">
              <i className={`fas ${isOverdue ? 'fa-exclamation-circle' : 'fa-bell'}`}></i>
              {new Date(lead.follow_up_date).toLocaleDateString('en-IE', { month: 'short', day: 'numeric' })}
            </span>
          );
        })()}
      </div>
      {lead.notes && <p className="lead-notes">{lead.notes}</p>}
      {lead.created_at && (
        <div className="lead-card-bottom">
          <span className="lead-created-time">{formatRelativeTime(lead.created_at)}</span>
          {lead.follow_up_date && (() => {
            const isOverdue = new Date(lead.follow_up_date) < new Date() && lead.stage !== 'won' && lead.stage !== 'lost';
            return isOverdue ? (
              <span className="lead-overdue-badge"><i className="fas fa-exclamation-circle"></i> Overdue</span>
            ) : null;
          })()}
        </div>
      )}
    </div>
  );
}

/* ============================================
   CUSTOMERS VIEW
   ============================================ */
function CustomersView({ customers, segmentCounts, customerFilter, setCustomerFilter, customerSort, setCustomerSort, onSelectClient, crmStats, onPortalLink }) {
  const SEGMENTS = [
    { key: 'all', label: 'All', icon: 'fa-users', color: '#64748b' },
    { key: 'vip', label: 'VIP', icon: 'fa-crown', color: '#f59e0b' },
    { key: 'loyal', label: 'Loyal', icon: 'fa-heart', color: '#ec4899' },
    { key: 'regular', label: 'Regular', icon: 'fa-user', color: '#3b82f6' },
    { key: 'new', label: 'New', icon: 'fa-user-plus', color: '#10b981' },
    { key: 'dormant', label: 'Dormant', icon: 'fa-moon', color: '#94a3b8' },
  ];

  const clientStats = crmStats?.client_stats || { total_clients: customers.length, new_this_month: 0 };

  return (
    <>
      {/* Customer Stats - compact strip */}
      <div className="crm-mini-stats">
        <span className="crm-mini-stat"><i className="fas fa-users" style={{ color: '#3b82f6' }}></i> {clientStats.total_clients || 0} customers</span>
        <span className="crm-mini-stat"><i className="fas fa-user-plus" style={{ color: '#10b981' }}></i> {clientStats.new_this_month || 0} new this month</span>
        <span className="crm-mini-stat"><i className="fas fa-crown" style={{ color: '#f59e0b' }}></i> {segmentCounts.vip} VIP</span>
        <span className="crm-mini-stat"><i className="fas fa-moon" style={{ color: '#94a3b8' }}></i> {segmentCounts.dormant} dormant</span>
      </div>

      {/* Segment Filter + Sort */}
      <div className="crm-customer-toolbar">
        <div className="crm-segment-filters">
          {SEGMENTS.map(s => (
            <button key={s.key}
              className={`crm-segment-btn ${customerFilter === s.key ? 'active' : ''}`}
              onClick={() => setCustomerFilter(s.key)}
              style={customerFilter === s.key ? { borderColor: s.color, color: s.color } : {}}>
              <i className={`fas ${s.icon}`}></i>
              <span>{s.label}</span>
              <span className="crm-segment-count">{segmentCounts[s.key] || 0}</span>
            </button>
          ))}
        </div>
        <div className="crm-sort-select">
          <select value={customerSort} onChange={e => setCustomerSort(e.target.value)}>
            <option value="recent">Last Activity</option>
            <option value="revenue">Revenue</option>
            <option value="health">Health Score</option>
            <option value="name">Name</option>
          </select>
        </div>
      </div>

      {/* Customer List */}
      <div className="crm-customer-list">
        {customers.length === 0 ? (
          <div className="crm-empty">
            <i className="fas fa-users"></i>
            <h3>No customers found</h3>
            <p>{customerFilter !== 'all'
              ? 'No customers match this filter. Try "All" to see everyone.'
              : 'Customers will appear here as you add them or convert leads.'}</p>
          </div>
        ) : (
          customers.map(c => (
            <div key={c.id} className="crm-customer-card" onClick={() => onSelectClient(c.id)}>
              <div className="crm-customer-avatar">
                <HealthRing score={c.score} />
                <div className="crm-avatar-inner">
                  <i className="fas fa-user"></i>
                </div>
              </div>
              <div className="crm-customer-info">
                <div className="crm-customer-name-row">
                  <h3>{c.name}</h3>
                  <SegmentBadge segment={c.segment} />
                </div>
                <div className="crm-customer-details">
                  {c.phone && <span><i className="fas fa-phone"></i> {formatPhone(c.phone)}</span>}
                  {c.email && <span><i className="fas fa-envelope"></i> {c.email}</span>}
                </div>
              </div>
              <div className="crm-customer-quick-actions">
                {c.phone && (
                  <a href={`tel:${c.phone}`} className="crm-quick-btn" onClick={e => e.stopPropagation()} title="Call">
                    <i className="fas fa-phone"></i>
                  </a>
                )}
                {c.email && (
                  <a href={`mailto:${c.email}`} className="crm-quick-btn" onClick={e => e.stopPropagation()} title="Email">
                    <i className="fas fa-envelope"></i>
                  </a>
                )}
              </div>
              <div className="crm-customer-metrics">
                <div className="crm-metric">
                  <span className="crm-metric-value">{c.completed_jobs || 0}</span>
                  <span className="crm-metric-label">Jobs</span>
                </div>
                <div className="crm-metric">
                  <span className="crm-metric-value">{formatCurrency(c.revenue)}</span>
                  <span className="crm-metric-label">Revenue</span>
                </div>
                <div className="crm-metric">
                  <span className={`crm-metric-value crm-health-${c.status}`}>{c.score}</span>
                  <span className="crm-metric-label">Health</span>
                </div>
                {c.last_job_date && (
                  <div className="crm-metric">
                    <span className="crm-metric-value crm-metric-time">{formatRelativeTime(c.last_job_date)}</span>
                    <span className="crm-metric-label">Last Job</span>
                  </div>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </>
  );
}

/* ============================================
   HEALTH RING (SVG)
   ============================================ */
function HealthRing({ score }) {
  const radius = 22;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const color = score >= 70 ? '#10b981' : score >= 40 ? '#f59e0b' : '#ef4444';
  return (
    <svg className="health-ring" width="52" height="52" viewBox="0 0 52 52">
      <circle cx="26" cy="26" r={radius} fill="none" stroke="#f1f5f9" strokeWidth="3" />
      <circle cx="26" cy="26" r={radius} fill="none" stroke={color} strokeWidth="3"
        strokeDasharray={circumference} strokeDashoffset={offset}
        strokeLinecap="round" transform="rotate(-90 26 26)" />
    </svg>
  );
}

/* ============================================
   SEGMENT BADGE
   ============================================ */
function SegmentBadge({ segment }) {
  const config = {
    vip: { label: 'VIP', color: '#f59e0b', bg: 'rgba(245,158,11,0.1)', icon: 'fa-crown' },
    loyal: { label: 'Loyal', color: '#ec4899', bg: 'rgba(236,72,153,0.1)', icon: 'fa-heart' },
    regular: { label: 'Regular', color: '#3b82f6', bg: 'rgba(59,130,246,0.1)', icon: 'fa-user' },
    new: { label: 'New', color: '#10b981', bg: 'rgba(16,185,129,0.1)', icon: 'fa-user-plus' },
    dormant: { label: 'Dormant', color: '#94a3b8', bg: 'rgba(148,163,184,0.1)', icon: 'fa-moon' },
  };
  const c = config[segment] || config.regular;
  return (
    <span className="crm-segment-badge" style={{ color: c.color, background: c.bg }}>
      <i className={`fas ${c.icon}`}></i> {c.label}
    </span>
  );
}

/* ============================================
   REVIEWS VIEW
   ============================================ */
function ReviewsView({ reviews, reviewStats }) {
  return (
    <>
      {/* Review Stats - compact strip */}
      <div className="crm-mini-stats">
        <span className="crm-mini-stat"><i className="fas fa-star" style={{ color: '#f59e0b' }}></i> {reviewStats.avgRating || '—'} avg rating</span>
        <span className="crm-mini-stat"><i className="fas fa-check-circle" style={{ color: '#10b981' }}></i> {reviewStats.submitted.length} reviews</span>
        <span className="crm-mini-stat"><i className="fas fa-clock" style={{ color: '#f59e0b' }}></i> {reviewStats.pending.length} pending</span>
        <span className="crm-mini-stat"><i className="fas fa-envelope" style={{ color: '#3b82f6' }}></i> {reviewStats.total} sent</span>
      </div>

      {/* Rating Breakdown */}
      {reviewStats.submitted.length > 0 && (
        <div className="crm-reviews-breakdown">
          {[5,4,3,2,1].map(star => {
            const count = reviewStats.submitted.filter(r => r.rating === star).length;
            const pct = reviewStats.submitted.length > 0 ? (count / reviewStats.submitted.length * 100) : 0;
            return (
              <div key={star} className="breakdown-row">
                <span className="breakdown-label">{star} <i className="fas fa-star" style={{ color: '#f59e0b', fontSize: '0.7rem' }}></i></span>
                <div className="breakdown-bar"><div className="breakdown-fill" style={{ width: `${pct}%` }}></div></div>
                <span className="breakdown-count">{count}</span>
              </div>
            );
          })}
        </div>
      )}

      {/* Reviews List */}
      {reviews.length === 0 ? (
        <div className="crm-empty">
          <i className="fas fa-star"></i>
          <h3>No reviews yet</h3>
          <p>When you complete jobs for customers with email addresses, they'll receive a satisfaction survey.</p>
        </div>
      ) : (
        <div className="crm-reviews-list">
          {reviews.map(review => (
            <div key={review.id} className={`crm-review-item ${review.submitted_at ? 'submitted' : 'pending'}`}>
              <div className="crm-review-header">
                <div className="crm-review-left">
                  <span className="crm-review-customer">{review.customer_name || 'Customer'}</span>
                  <span className="crm-review-service">{review.service_type || 'Job'}</span>
                </div>
                <div className="crm-review-right">
                  {review.submitted_at ? (
                    <div className="crm-review-stars">
                      {[1,2,3,4,5].map(s => (
                        <span key={s} style={{ color: s <= review.rating ? '#f59e0b' : '#e5e7eb', fontSize: '1rem' }}>★</span>
                      ))}
                    </div>
                  ) : (
                    <span className="crm-review-pending"><i className="fas fa-clock"></i> Awaiting</span>
                  )}
                </div>
              </div>
              {review.review_text && <p className="crm-review-text">"{review.review_text}"</p>}
              <div className="crm-review-footer">
                {review.submitted_at && (
                  <span className="crm-review-date">
                    Reviewed {new Date(review.submitted_at).toLocaleDateString('en-IE', { month: 'short', day: 'numeric', year: 'numeric' })}
                  </span>
                )}
                {!review.submitted_at && review.email_sent_at && (
                  <span className="crm-review-date">
                    Sent {new Date(review.email_sent_at).toLocaleDateString('en-IE', { month: 'short', day: 'numeric' })}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

/* ============================================
   LEAD FORM MODAL
   ============================================ */
function LeadFormModal({ lead, onClose, onSubmit, isPending }) {
  const [form, setForm] = useState({
    name: lead?.name || '',
    phone: lead?.phone || '',
    email: lead?.email || '',
    address: lead?.address || '',
    source: lead?.source || 'manual',
    stage: lead?.stage || 'new',
    service_interest: lead?.service_interest || '',
    estimated_value: lead?.estimated_value || '',
    notes: lead?.notes || '',
    follow_up_date: lead?.follow_up_date ? lead.follow_up_date.split('T')[0] : '',
  });

  // Close on Escape
  useEffect(() => {
    const handleEsc = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handleEsc);
    return () => document.removeEventListener('keydown', handleEsc);
  }, [onClose]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!form.name.trim()) return;
    onSubmit({
      ...form,
      estimated_value: form.estimated_value ? parseFloat(form.estimated_value) : null,
      follow_up_date: form.follow_up_date || null,
    });
  };

  return (
    <div className="crm-modal-overlay" onClick={onClose}>
      <div className="crm-modal" onClick={e => e.stopPropagation()}>
        <div className="crm-modal-header">
          <h3>{lead ? 'Edit Lead' : 'New Lead'}</h3>
          <button className="crm-modal-close" onClick={onClose}><i className="fas fa-times"></i></button>
        </div>
        <form onSubmit={handleSubmit} className="crm-lead-form">
          <div className="crm-form-row">
            <div className="crm-form-group">
              <label>Name *</label>
              <input type="text" value={form.name} onChange={e => setForm({...form, name: e.target.value})} required />
            </div>
            <div className="crm-form-group">
              <label>Phone</label>
              <input type="tel" value={form.phone} onChange={e => setForm({...form, phone: e.target.value})} placeholder="+353..." />
            </div>
          </div>
          <div className="crm-form-row">
            <div className="crm-form-group">
              <label>Email</label>
              <input type="email" value={form.email} onChange={e => setForm({...form, email: e.target.value})} />
            </div>
            <div className="crm-form-group">
              <label>Service Interest</label>
              <input type="text" value={form.service_interest} onChange={e => setForm({...form, service_interest: e.target.value})} placeholder="e.g. Lawn Care" />
            </div>
          </div>
          <div className="crm-form-row">
            <div className="crm-form-group">
              <label>Source</label>
              <select value={form.source} onChange={e => setForm({...form, source: e.target.value})}>
                {LEAD_SOURCES.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}
              </select>
            </div>
            <div className="crm-form-group">
              <label>Stage</label>
              <select value={form.stage} onChange={e => setForm({...form, stage: e.target.value})}>
                {PIPELINE_STAGES.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}
              </select>
            </div>
          </div>
          <div className="crm-form-row">
            <div className="crm-form-group">
              <label>Estimated Value</label>
              <input type="number" step="0.01" value={form.estimated_value} onChange={e => setForm({...form, estimated_value: e.target.value})} placeholder="€0.00" />
            </div>
            <div className="crm-form-group">
              <label>Follow-up Date</label>
              <input type="date" value={form.follow_up_date} onChange={e => setForm({...form, follow_up_date: e.target.value})} />
            </div>
          </div>
          <div className="crm-form-group full">
            <label>Address</label>
            <input type="text" value={form.address} onChange={e => setForm({...form, address: e.target.value})} />
          </div>
          <div className="crm-form-group full">
            <label>Notes</label>
            <textarea value={form.notes} onChange={e => setForm({...form, notes: e.target.value})} rows={3} placeholder="Any additional details..." />
          </div>
          <div className="crm-form-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={isPending}>
              {isPending ? 'Saving...' : (lead ? 'Update Lead' : 'Create Lead')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

/* ============================================
   QUOTE PIPELINE EMBED
   Renders the existing PipelineTab inside CRM
   ============================================ */
function QuotePipelineEmbed() {
  return (
    <div className="crm-quotes-embed">
      <PipelineTab />
    </div>
  );
}

/* AI CRM Insights */
function CrmAiInsights({ leads, customerHealth, reviews, pipelineStats }) {
  const insights = useMemo(() => {
    const items = [];

    // Stale leads
    const now = new Date();
    const staleDays = 7;
    const staleLeads = leads.filter(l => {
      if (l.stage === 'won' || l.stage === 'lost') return false;
      const updated = new Date(l.updated_at || l.created_at);
      return (now - updated) / (1000 * 60 * 60 * 24) > staleDays;
    });
    if (staleLeads.length > 0) {
      items.push({ icon: 'fa-hourglass-half', text: `${staleLeads.length} lead${staleLeads.length > 1 ? 's' : ''} haven't been updated in ${staleDays}+ days. Follow up to keep them warm.`, type: 'action' });
    }

    // Dormant customers
    const dormant = customerHealth.filter(c => c.segment === 'dormant');
    if (dormant.length > 2) {
      items.push({ icon: 'fa-user-clock', text: `${dormant.length} dormant customers. Send a re-engagement message or special offer to win them back.`, type: 'action' });
    }

    // VIP customers
    const vips = customerHealth.filter(c => c.segment === 'vip');
    if (vips.length > 0) {
      items.push({ icon: 'fa-crown', text: `${vips.length} VIP customer${vips.length > 1 ? 's' : ''} — your top spenders. Consider loyalty perks or priority scheduling.`, type: 'positive' });
    }

    // Review score
    if (reviews.length > 0) {
      const avgRating = reviews.reduce((s, r) => s + (r.rating || 0), 0) / reviews.length;
      if (avgRating >= 4.5) {
        items.push({ icon: 'fa-star', text: `Excellent ${avgRating.toFixed(1)}★ average rating across ${reviews.length} reviews. Share these on your website!`, type: 'positive' });
      } else if (avgRating < 3.5 && reviews.length > 3) {
        items.push({ icon: 'fa-star-half-alt', text: `Average rating is ${avgRating.toFixed(1)}★. Review recent feedback for improvement areas.`, type: 'warning' });
      }
    }

    // Pipeline conversion
    if (pipelineStats) {
      const total = leads.length;
      const won = leads.filter(l => l.stage === 'won').length;
      if (total > 5 && won / total < 0.2) {
        items.push({ icon: 'fa-filter-circle-dollar', text: `Lead conversion is below 20%. Focus on moving "Contacted" leads to "Quoted" stage.`, type: 'action' });
      }
    }

    if (items.length === 0) {
      items.push({ icon: 'fa-check-circle', text: 'CRM is in good shape. Keep nurturing your customer relationships!', type: 'positive' });
    }

    return items.slice(0, 3);
  }, [leads, customerHealth, reviews, pipelineStats]);

  return (
    <div className="ai-insight-card">
      <div className="ai-insight-header">
        <span className="ai-insight-badge"><i className="fas fa-sparkles"></i> AI</span>
        <span className="ai-insight-title">Relationship Insights</span>
      </div>
      <div className="ai-insight-body">
        {insights.map((item, i) => (
          <div key={i} className="ai-insight-item">
            <i className={`fas ${item.icon}`} style={{ color: item.type === 'positive' ? '#10b981' : item.type === 'warning' ? '#f59e0b' : '#6366f1' }}></i>
            <span>{item.text}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default CrmTab;
