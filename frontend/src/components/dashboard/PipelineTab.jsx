import { useState, useMemo, useCallback, memo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useToast } from '../Toast';
import {
  getQuotePipeline, updateQuotePipelineStage, sendQuoteFollowUp,
  generateQuoteAcceptLink, getSequences, createSequence, updateSequence,
  deleteSequence, getAutomations, createAutomation, updateAutomation, deleteAutomation
} from '../../services/api';
import './PipelineTab.css';

const STAGES = [
  { key: 'draft', label: 'Draft', color: '#94a3b8', icon: 'fa-file-alt' },
  { key: 'sent', label: 'Sent', color: '#3b82f6', icon: 'fa-paper-plane' },
  { key: 'follow_up', label: 'Follow Up', color: '#f59e0b', icon: 'fa-redo' },
  { key: 'accepted', label: 'Accepted', color: '#10b981', icon: 'fa-check' },
  { key: 'won', label: 'Won', color: '#8b5cf6', icon: 'fa-trophy' },
  { key: 'lost', label: 'Lost', color: '#ef4444', icon: 'fa-times' },
];

const fmt = (v) => v != null ? `€${Number(v).toLocaleString('en-IE', { minimumFractionDigits: 2 })}` : '—';
const relTime = (d) => {
  if (!d) return '';
  const diff = Math.floor((Date.now() - new Date(d)) / 86400000);
  if (diff === 0) return 'Today';
  if (diff === 1) return 'Yesterday';
  if (diff < 7) return `${diff}d ago`;
  return new Date(d).toLocaleDateString('en-IE', { day: 'numeric', month: 'short' });
};

function PipelineTab() {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [view, setView] = useState('pipeline');
  const [dragOverStage, setDragOverStage] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [followUpModal, setFollowUpModal] = useState(null);
  const [followUpMsg, setFollowUpMsg] = useState('');
  const [lostModal, setLostModal] = useState(null);
  const [lostReason, setLostReason] = useState('');
  const [linkCopied, setLinkCopied] = useState(null);

  const { data, isLoading } = useQuery({
    queryKey: ['quote-pipeline'],
    queryFn: async () => (await getQuotePipeline()).data,
  });

  const quotes = data?.quotes || [];
  const stats = data?.stats || {};

  const stageMut = useMutation({
    mutationFn: ({ id, stage, lostReason: lr }) => updateQuotePipelineStage(id, stage, lr),
    onMutate: async ({ id, stage }) => {
      await queryClient.cancelQueries({ queryKey: ['quote-pipeline'] });
      const previous = queryClient.getQueryData(['quote-pipeline']);
      if (previous?.quotes) {
        queryClient.setQueryData(['quote-pipeline'], {
          ...previous,
          quotes: previous.quotes.map(q => q.id === id ? { ...q, pipeline_stage: stage } : q),
        });
      }
      return { previous };
    },
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['quote-pipeline'] }); queryClient.invalidateQueries({ queryKey: ['quotes'] }); },
    onError: (e, vars, context) => {
      if (context?.previous) queryClient.setQueryData(['quote-pipeline'], context.previous);
      addToast(e.response?.data?.error || 'Failed to update stage', 'error');
    },
  });

  const followUpMut = useMutation({
    mutationFn: ({ id, message }) => sendQuoteFollowUp(id, message),
    onSuccess: (res) => { addToast(`Follow-up sent via ${res.data?.sent_via}`, 'success'); queryClient.invalidateQueries({ queryKey: ['quote-pipeline'] }); setFollowUpModal(null); setFollowUpMsg(''); },
    onError: (e) => addToast(e.response?.data?.error || 'Failed to send', 'error'),
  });

  const linkMut = useMutation({
    mutationFn: (id) => generateQuoteAcceptLink(id),
    onSuccess: (res) => {
      navigator.clipboard?.writeText(res.data.link);
      setLinkCopied(res.data.link);
      addToast('Accept link copied to clipboard', 'success');
      setTimeout(() => setLinkCopied(null), 3000);
    },
  });

  const filtered = useMemo(() => {
    if (!searchTerm.trim()) return quotes;
    const t = searchTerm.toLowerCase();
    return quotes.filter(q =>
      q.title?.toLowerCase().includes(t) || q.client_name?.toLowerCase().includes(t) ||
      String(q.quote_number).includes(t)
    );
  }, [quotes, searchTerm]);

  const byStage = useMemo(() => {
    const g = {};
    STAGES.forEach(s => { g[s.key] = []; });
    filtered.forEach(q => {
      const stage = q.pipeline_stage || (q.status === 'converted' ? 'won' : q.status === 'declined' ? 'lost' : q.status === 'accepted' ? 'accepted' : q.status === 'sent' ? 'sent' : 'draft');
      if (g[stage]) g[stage].push(q);
      else g.draft.push(q);
    });
    return g;
  }, [filtered]);

  const handleDragOver = useCallback((e, stageKey) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    setDragOverStage(prev => prev === stageKey ? prev : stageKey);
  }, []);

  const handleDragLeave = useCallback(() => {
    setDragOverStage(null);
  }, []);

  const handleDrop = useCallback((e, stage) => {
    e.preventDefault();
    const id = parseInt(e.dataTransfer.getData('text/plain'));
    if (!id) return;
    setDragOverStage(null);
    if (stage === 'lost') {
      setLostModal(id);
      return;
    }
    stageMut.mutate({ id, stage });
  }, [stageMut]);

  const handleLostConfirm = () => {
    if (lostModal) {
      stageMut.mutate({ id: lostModal, stage: 'lost', lostReason });
      setLostModal(null);
      setLostReason('');
    }
  };

  if (isLoading) return <div className="pipe-loading"><div className="pipe-spinner"></div></div>;

  const hasQuotes = quotes.length > 0;

  return (
    <div className="pipe-tab">
      {/* Header */}
      <div className="pipe-header">
        <div className="pipe-header-left">
          <h2><i className="fas fa-stream"></i> Quote Pipeline</h2>
        </div>
        <div className="pipe-header-right">
          {hasQuotes && (
            <div className="dash-search" style={{ maxWidth: 220 }}>
              <i className="fas fa-search"></i>
              <input placeholder="Search quotes..." value={searchTerm} onChange={e => setSearchTerm(e.target.value)} />
            </div>
          )}
        </div>
      </div>

      {/* Stats strip */}
      {hasQuotes && (
        <div className="pipe-stats">
          <span className="pipe-stat"><i className="fas fa-stream" style={{ color: '#3b82f6' }}></i> {stats.active || 0} active</span>
          <span className="pipe-stat"><i className="fas fa-trophy" style={{ color: '#10b981' }}></i> {stats.won || 0} won</span>
          <span className="pipe-stat"><i className="fas fa-coins" style={{ color: '#f59e0b' }}></i> {fmt(stats.pipeline_value)} pipeline</span>
          <span className="pipe-stat"><i className="fas fa-percentage" style={{ color: '#8b5cf6' }}></i> {stats.conversion_rate || 0}% conversion</span>
        </div>
      )}

      {view === 'pipeline' && (
        <>
          {!hasQuotes ? (
            <div className="seq-empty">
              <i className="fas fa-file-invoice-dollar"></i>
              <h4>No quotes yet</h4>
              <p>Create quotes from job details to start tracking them here.</p>
            </div>
          ) : (
            <div className="pipe-board">
              {STAGES.map(stage => (
                <div key={stage.key}
                  className={`pipe-col ${dragOverStage === stage.key ? 'drag-over' : ''}`}
                  onDragOver={e => handleDragOver(e, stage.key)}
                  onDragLeave={handleDragLeave}
                  onDrop={e => handleDrop(e, stage.key)}>
                  <div className="pipe-col-head">
                    <span className="pipe-dot" style={{ background: stage.color }}></span>
                    <span>{stage.label}</span>
                    <span className="pipe-count">{byStage[stage.key]?.length || 0}</span>
                  </div>
                  <div className="pipe-cards">
                    {(byStage[stage.key] || []).map(q => (
                      <QuoteCard key={q.id} quote={q} stage={stage}
                        onFollowUp={() => setFollowUpModal(q)}
                        onCopyLink={() => linkMut.mutate(q.id)}
                        linkCopied={linkCopied}
                        onStageChange={(id, s) => stageMut.mutate({ id, stage: s })}
                        onMarkLost={(id) => setLostModal(id)} />
                    ))}
                    {(byStage[stage.key] || []).length === 0 && (
                      <div className="pipe-empty"><i className={`fas ${stage.icon}`}></i><span>Drag quotes here</span></div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* Follow-up modal */}
      {followUpModal && (
        <div className="pipe-modal-overlay" onClick={() => setFollowUpModal(null)}>
          <div className="pipe-modal" onClick={e => e.stopPropagation()}>
            <div className="pipe-modal-head">
              <h3>Send Follow-Up</h3>
              <button className="pipe-modal-close" onClick={() => setFollowUpModal(null)}><i className="fas fa-times"></i></button>
            </div>
            <div className="pipe-modal-body">
              <p className="pipe-modal-info">
                <strong>{followUpModal.client_name}</strong> — {followUpModal.title} ({fmt(followUpModal.total)})
                {followUpModal.follow_up_count > 0 && <span className="pipe-followup-badge">{followUpModal.follow_up_count} sent</span>}
              </p>
              <textarea placeholder="Custom message (optional — leave blank for default)" value={followUpMsg}
                onChange={e => setFollowUpMsg(e.target.value)} rows={3} />
              <div className="pipe-modal-actions">
                <button className="btn-secondary" onClick={() => setFollowUpModal(null)}>Cancel</button>
                <button className="btn-primary" onClick={() => followUpMut.mutate({ id: followUpModal.id, message: followUpMsg })}
                  disabled={followUpMut.isPending}>
                  {followUpMut.isPending ? <><i className="fas fa-spinner fa-spin"></i> Sending...</> : <><i className="fas fa-paper-plane"></i> Send</>}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Lost reason modal */}
      {lostModal && (
        <div className="pipe-modal-overlay" onClick={() => setLostModal(null)}>
          <div className="pipe-modal small" onClick={e => e.stopPropagation()}>
            <div className="pipe-modal-head"><h3>Mark as Lost</h3></div>
            <div className="pipe-modal-body">
              <label>Reason (optional)</label>
              <select value={lostReason} onChange={e => setLostReason(e.target.value)}>
                <option value="">Select reason...</option>
                <option value="too_expensive">Too expensive</option>
                <option value="went_competitor">Went with competitor</option>
                <option value="no_response">No response</option>
                <option value="project_cancelled">Project cancelled</option>
                <option value="timing">Bad timing</option>
                <option value="other">Other</option>
              </select>
              <div className="pipe-modal-actions">
                <button className="btn-secondary" onClick={() => { setLostModal(null); setLostReason(''); }}>Cancel</button>
                <button className="btn-danger" onClick={handleLostConfirm}><i className="fas fa-times"></i> Mark Lost</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const QuoteCard = memo(function QuoteCard({ quote, stage, onFollowUp, onCopyLink, linkCopied, onStageChange, onMarkLost }) {
  const q = quote;
  const [showMobileMenu, setShowMobileMenu] = useState(false);
  return (
    <div className="pipe-card" draggable onDragStart={e => { e.dataTransfer.setData('text/plain', String(q.id)); e.dataTransfer.effectAllowed = 'move'; }}>
      <div className="pipe-card-top">
        <span className="pipe-card-title">{q.title || `Quote #${q.quote_number}`}</span>
        <span className="pipe-card-amount">{fmt(q.total)}</span>
      </div>
      {q.client_name && <div className="pipe-card-client"><i className="fas fa-user"></i> {q.client_name}</div>}
      <div className="pipe-card-meta">
        <span><i className="fas fa-clock"></i> {relTime(q.created_at)}</span>
        {q.follow_up_count > 0 && <span className="pipe-fu-badge"><i className="fas fa-redo"></i> {q.follow_up_count}</span>}
        {q.valid_until && (() => {
          const days = Math.ceil((new Date(q.valid_until) - Date.now()) / 86400000);
          if (days < 0) return <span className="pipe-expired">Expired</span>;
          if (days <= 3) return <span className="pipe-expiring">{days}d left</span>;
          return null;
        })()}
      </div>
      {stage.key !== 'won' && stage.key !== 'lost' && (
        <div className="pipe-card-actions">
          {(stage.key === 'sent' || stage.key === 'follow_up') && (
            <button className="pipe-act-btn" onClick={onFollowUp} title="Send follow-up"><i className="fas fa-paper-plane"></i></button>
          )}
          <button className="pipe-act-btn" onClick={onCopyLink} title="Copy accept link"><i className="fas fa-link"></i></button>
          {/* Mobile stage move button */}
          <button className="pipe-act-btn pipe-mobile-move" onClick={() => setShowMobileMenu(!showMobileMenu)} title="Move to stage">
            <i className="fas fa-arrows-alt"></i>
          </button>
        </div>
      )}
      {/* Mobile stage selector */}
      {showMobileMenu && stage.key !== 'won' && stage.key !== 'lost' && (
        <div className="pipe-mobile-stages">
          {STAGES.filter(s => s.key !== stage.key).map(s => (
            <button key={s.key} className="pipe-mobile-stage-btn" onClick={() => {
              setShowMobileMenu(false);
              if (s.key === 'lost') { onMarkLost(q.id); }
              else { onStageChange(q.id, s.key); }
            }}>
              <span className="pipe-dot" style={{ background: s.color }}></span> {s.label}
            </button>
          ))}
        </div>
      )}
      {q.lost_reason && stage.key === 'lost' && (
        <div className="pipe-lost-reason"><i className="fas fa-info-circle"></i> {q.lost_reason.replace(/_/g, ' ')}</div>
      )}
    </div>
  );
});

/* ===== Sequences View ===== */
function SequencesView() {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState(null);
  const [form, setForm] = useState({ name: '', trigger_type: 'quote_sent', steps: [{ delay_days: 3, channel: 'email', message: '' }] });

  const { data } = useQuery({ queryKey: ['sequences'], queryFn: async () => (await getSequences()).data });
  const seqs = data?.sequences || [];

  const saveMut = useMutation({
    mutationFn: (d) => editId ? updateSequence(editId, d) : createSequence(d),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['sequences'] }); addToast(editId ? 'Sequence updated' : 'Sequence created', 'success'); resetForm(); },
    onError: (e) => addToast(e.response?.data?.error || 'Failed', 'error'),
  });

  const delMut = useMutation({
    mutationFn: deleteSequence,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['sequences'] }); addToast('Deleted', 'success'); },
  });

  const resetForm = () => { setShowForm(false); setEditId(null); setForm({ name: '', trigger_type: 'quote_sent', steps: [{ delay_days: 3, channel: 'email', message: '' }] }); };

  const addStep = () => setForm({ ...form, steps: [...form.steps, { delay_days: 7, channel: 'email', message: '' }] });
  const removeStep = (i) => setForm({ ...form, steps: form.steps.filter((_, idx) => idx !== i) });
  const updateStep = (i, field, val) => { const s = [...form.steps]; s[i] = { ...s[i], [field]: val }; setForm({ ...form, steps: s }); };

  const startEdit = (s) => { setForm({ name: s.name, trigger_type: s.trigger_type, steps: s.steps || [] }); setEditId(s.id); setShowForm(true); };

  return (
    <div className="seq-view">
      <div className="seq-header">
        <div>
          <h3>Follow-Up Sequences</h3>
          <p className="seq-desc">Automated follow-ups sent after quotes are sent. Nudge customers who haven't responded.</p>
        </div>
        <button className="btn-primary" onClick={() => { resetForm(); setShowForm(true); }}><i className="fas fa-plus"></i> New Sequence</button>
      </div>

      {seqs.length === 0 && !showForm && (
        <div className="seq-empty">
          <i className="fas fa-paper-plane"></i>
          <h4>No sequences yet</h4>
          <p>Create your first follow-up sequence to automatically chase quotes.</p>
        </div>
      )}

      {seqs.map(s => (
        <div key={s.id} className={`seq-card ${s.enabled ? '' : 'disabled'}`}>
          <div className="seq-card-head">
            <div className="seq-card-info">
              <span className="seq-card-name">{s.name}</span>
              <span className="seq-trigger-badge">{s.trigger_type === 'quote_sent' ? 'After quote sent' : s.trigger_type === 'job_completed' ? 'After job done' : s.trigger_type}</span>
            </div>
            <div className="seq-card-actions">
              <span className={`seq-status ${s.enabled ? 'on' : 'off'}`}>{s.enabled ? 'Active' : 'Paused'}</span>
              <button className="pipe-act-btn" onClick={() => startEdit(s)}><i className="fas fa-edit"></i></button>
              <button className="pipe-act-btn delete" onClick={() => delMut.mutate(s.id)}><i className="fas fa-trash"></i></button>
            </div>
          </div>
          <div className="seq-steps-preview">
            {(s.steps || []).map((step, i) => (
              <span key={i} className="seq-step-chip">
                <i className={`fas ${step.channel === 'sms' ? 'fa-sms' : 'fa-envelope'}`}></i>
                Day {step.delay_days}
              </span>
            ))}
          </div>
        </div>
      ))}

      {showForm && (
        <div className="seq-form-card">
          <h4>{editId ? 'Edit Sequence' : 'New Sequence'}</h4>
          <div className="seq-form-row">
            <div className="seq-form-group">
              <label>Name</label>
              <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="e.g. Quote Follow-Up" />
            </div>
            <div className="seq-form-group">
              <label>Trigger</label>
              <select value={form.trigger_type} onChange={e => setForm({ ...form, trigger_type: e.target.value })}>
                <option value="quote_sent">After quote sent</option>
                <option value="job_completed">After job completed</option>
              </select>
            </div>
          </div>
          <label className="seq-steps-label">Steps</label>
          {form.steps.map((step, i) => (
            <div key={i} className="seq-step-row">
              <span className="seq-step-num">{i + 1}</span>
              <div className="seq-step-fields">
                <label>Wait</label>
                <input type="number" min="1" max="90" value={step.delay_days} onChange={e => updateStep(i, 'delay_days', parseInt(e.target.value) || 1)} />
                <span>days, then</span>
                <select value={step.channel} onChange={e => updateStep(i, 'channel', e.target.value)}>
                  <option value="email">Email</option>
                  <option value="sms">SMS</option>
                </select>
              </div>
              <textarea placeholder="Message (leave blank for default)" value={step.message || ''} onChange={e => updateStep(i, 'message', e.target.value)} rows={2} />
              {form.steps.length > 1 && <button className="seq-step-remove" onClick={() => removeStep(i)}><i className="fas fa-times"></i></button>}
            </div>
          ))}
          <button className="seq-add-step" onClick={addStep}><i className="fas fa-plus"></i> Add Step</button>
          <div className="seq-form-actions">
            <button className="btn-secondary" onClick={resetForm}>Cancel</button>
            <button className="btn-primary" onClick={() => saveMut.mutate(form)} disabled={!form.name.trim() || saveMut.isPending}>
              {saveMut.isPending ? 'Saving...' : editId ? 'Update' : 'Create'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ===== Automations View ===== */
const TRIGGER_TYPES = [
  { value: 'job_completed', label: 'Job completed', icon: 'fa-check-circle' },
  { value: 'job_created', label: 'Job created', icon: 'fa-plus-circle' },
  { value: 'quote_accepted', label: 'Quote accepted', icon: 'fa-handshake' },
  { value: 'quote_expired', label: 'Quote expired', icon: 'fa-clock' },
  { value: 'new_lead', label: 'New lead', icon: 'fa-user-plus' },
  { value: 'review_received', label: 'Review received', icon: 'fa-star' },
];

const ACTION_TYPES = [
  { value: 'send_email', label: 'Send email', icon: 'fa-envelope' },
  { value: 'send_sms', label: 'Send SMS', icon: 'fa-sms' },
  { value: 'send_review_request', label: 'Send review request', icon: 'fa-star' },
  { value: 'create_lead', label: 'Create lead', icon: 'fa-user-plus' },
  { value: 'update_status', label: 'Update status', icon: 'fa-sync' },
  { value: 'notify_owner', label: 'Notify owner', icon: 'fa-bell' },
];

function AutomationsView() {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState(null);
  const [form, setForm] = useState({ name: '', trigger_type: 'job_completed', trigger_config: {}, actions: [{ type: 'send_review_request', config: {} }] });

  const { data } = useQuery({ queryKey: ['automations'], queryFn: async () => (await getAutomations()).data });
  const autos = data?.automations || [];

  const saveMut = useMutation({
    mutationFn: (d) => editId ? updateAutomation(editId, d) : createAutomation(d),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['automations'] }); addToast(editId ? 'Updated' : 'Created', 'success'); resetForm(); },
    onError: (e) => addToast(e.response?.data?.error || 'Failed', 'error'),
  });

  const delMut = useMutation({
    mutationFn: deleteAutomation,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['automations'] }); addToast('Deleted', 'success'); },
  });

  const toggleMut = useMutation({
    mutationFn: ({ id, enabled }) => updateAutomation(id, { ...autos.find(a => a.id === id), enabled }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['automations'] }),
  });

  const resetForm = () => { setShowForm(false); setEditId(null); setForm({ name: '', trigger_type: 'job_completed', trigger_config: {}, actions: [{ type: 'send_review_request', config: {} }] }); };

  const startEdit = (a) => { setForm({ name: a.name, trigger_type: a.trigger_type, trigger_config: a.trigger_config || {}, actions: a.actions || [] }); setEditId(a.id); setShowForm(true); };

  const addAction = () => setForm({ ...form, actions: [...form.actions, { type: 'send_email', config: {} }] });
  const removeAction = (i) => setForm({ ...form, actions: form.actions.filter((_, idx) => idx !== i) });
  const updateAction = (i, field, val) => { const a = [...form.actions]; a[i] = { ...a[i], [field]: val }; setForm({ ...form, actions: a }); };

  return (
    <div className="auto-view">
      <div className="seq-header">
        <div>
          <h3>Workflow Automations</h3>
          <p className="seq-desc">Set up "if this, then that" rules. When something happens, automatically take action.</p>
        </div>
        <button className="btn-primary" onClick={() => { resetForm(); setShowForm(true); }}><i className="fas fa-plus"></i> New Automation</button>
      </div>

      {autos.length === 0 && !showForm && (
        <div className="seq-empty">
          <i className="fas fa-bolt"></i>
          <h4>No automations yet</h4>
          <p>Create your first automation to save time on repetitive tasks.</p>
        </div>
      )}

      {autos.map(a => (
        <div key={a.id} className={`auto-card ${a.enabled ? '' : 'disabled'}`}>
          <div className="auto-card-left">
            <div className="auto-toggle" onClick={() => toggleMut.mutate({ id: a.id, enabled: !a.enabled })}>
              <div className={`auto-toggle-track ${a.enabled ? 'on' : ''}`}><div className="auto-toggle-thumb"></div></div>
            </div>
            <div className="auto-card-info">
              <span className="auto-card-name">{a.name}</span>
              <div className="auto-card-flow">
                <span className="auto-trigger-chip"><i className={`fas ${TRIGGER_TYPES.find(t => t.value === a.trigger_type)?.icon || 'fa-bolt'}`}></i> {TRIGGER_TYPES.find(t => t.value === a.trigger_type)?.label || a.trigger_type}</span>
                <i className="fas fa-arrow-right auto-arrow"></i>
                {(a.actions || []).map((act, i) => (
                  <span key={i} className="auto-action-chip"><i className={`fas ${ACTION_TYPES.find(t => t.value === act.type)?.icon || 'fa-cog'}`}></i> {ACTION_TYPES.find(t => t.value === act.type)?.label || act.type}</span>
                ))}
              </div>
            </div>
          </div>
          <div className="auto-card-right">
            {a.run_count > 0 && <span className="auto-runs">{a.run_count} runs</span>}
            <button className="pipe-act-btn" onClick={() => startEdit(a)}><i className="fas fa-edit"></i></button>
            <button className="pipe-act-btn delete" onClick={() => delMut.mutate(a.id)}><i className="fas fa-trash"></i></button>
          </div>
        </div>
      ))}

      {showForm && (
        <div className="seq-form-card">
          <h4>{editId ? 'Edit Automation' : 'New Automation'}</h4>
          <div className="seq-form-row">
            <div className="seq-form-group" style={{ flex: 2 }}>
              <label>Name</label>
              <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="e.g. Post-Job Review Request" />
            </div>
          </div>
          <div className="auto-flow-builder">
            <div className="auto-flow-section">
              <label className="auto-flow-label"><i className="fas fa-bolt"></i> When this happens...</label>
              <div className="auto-trigger-grid">
                {TRIGGER_TYPES.map(t => (
                  <button key={t.value} className={`auto-trigger-option ${form.trigger_type === t.value ? 'active' : ''}`}
                    onClick={() => setForm({ ...form, trigger_type: t.value })}>
                    <i className={`fas ${t.icon}`}></i> {t.label}
                  </button>
                ))}
              </div>
              {form.trigger_type === 'review_received' && (
                <div className="auto-trigger-extra">
                  <label>Min rating</label>
                  <select value={form.trigger_config.min_rating || ''} onChange={e => setForm({ ...form, trigger_config: { ...form.trigger_config, min_rating: parseInt(e.target.value) || null } })}>
                    <option value="">Any</option>
                    <option value="4">4+ stars</option>
                    <option value="5">5 stars only</option>
                  </select>
                </div>
              )}
              {(form.trigger_type === 'job_completed' || form.trigger_type === 'job_created') && (
                <div className="auto-trigger-extra">
                  <label>Delay</label>
                  <select value={form.trigger_config.delay_hours || 0} onChange={e => setForm({ ...form, trigger_config: { ...form.trigger_config, delay_hours: parseInt(e.target.value) } })}>
                    <option value="0">Immediately</option>
                    <option value="1">1 hour</option>
                    <option value="24">1 day</option>
                    <option value="72">3 days</option>
                    <option value="168">1 week</option>
                  </select>
                </div>
              )}
            </div>
            <div className="auto-flow-arrow"><i className="fas fa-arrow-down"></i></div>
            <div className="auto-flow-section">
              <label className="auto-flow-label"><i className="fas fa-play"></i> Do this...</label>
              {form.actions.map((act, i) => (
                <div key={i} className="auto-action-row">
                  <select value={act.type} onChange={e => updateAction(i, 'type', e.target.value)}>
                    {ACTION_TYPES.map(a => <option key={a.value} value={a.value}>{a.label}</option>)}
                  </select>
                  {(act.type === 'send_email' || act.type === 'send_sms') && (
                    <textarea placeholder="Message template (use {customer_name}, {service_type}, {company_name})"
                      value={act.config?.message || ''} onChange={e => updateAction(i, 'config', { ...act.config, message: e.target.value })} rows={2} />
                  )}
                  {form.actions.length > 1 && <button className="seq-step-remove" onClick={() => removeAction(i)}><i className="fas fa-times"></i></button>}
                </div>
              ))}
              <button className="seq-add-step" onClick={addAction}><i className="fas fa-plus"></i> Add Action</button>
            </div>
          </div>
          <div className="seq-form-actions">
            <button className="btn-secondary" onClick={resetForm}>Cancel</button>
            <button className="btn-primary" onClick={() => saveMut.mutate(form)} disabled={!form.name.trim() || saveMut.isPending}>
              {saveMut.isPending ? 'Saving...' : editId ? 'Update' : 'Create'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default PipelineTab;
