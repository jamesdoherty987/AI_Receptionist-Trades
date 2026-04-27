import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../../context/AuthContext';
import { useIndustry } from '../../context/IndustryContext';
import { formatCurrency, getProxiedMediaUrl, parseServerDate } from '../../utils/helpers';
import { formatDuration } from '../../utils/durationOptions';
import { updateBooking, getJobSetupData, sendInvoice } from '../../services/api';
import { useToast } from '../Toast';
import AddJobModal from '../modals/AddJobModal';
import JobDetailModal from '../modals/JobDetailModal';
import InvoiceConfirmModal from '../modals/InvoiceConfirmModal';
import './JobsTab.css';
import './SharedDashboard.css';

const STATUS_FILTERS = [
  { key: 'active', label: 'Upcoming', icon: 'fa-calendar-check' },
  { key: 'recent', label: 'New', icon: 'fa-bell' },
  { key: 'overdue', label: 'Late', icon: 'fa-exclamation-circle' },
  { key: 'in-progress', label: 'In Progress', icon: 'fa-wrench' },
  { key: 'needs-invoice', label: 'Unpaid', icon: 'fa-file-invoice' },
  { key: 'completed', label: 'Done', icon: 'fa-check-circle' },
  { key: 'cancelled', label: 'Cancelled', icon: 'fa-ban' },
  { key: 'rejected', label: 'Rejected', icon: 'fa-times-circle' },
  { key: 'all', label: 'All', icon: 'fa-list' },
];

function JobsTab({ bookings, showInvoiceButtons = true }) {
  const queryClient = useQueryClient();
  const { hasActiveSubscription } = useAuth();
  const { terminology, features } = useIndustry();
  const isSubscriptionActive = hasActiveSubscription();
  const { addToast } = useToast();
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('active');
  const [viewMode, setViewMode] = useState('list');
  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedJobId, setSelectedJobId] = useState(null);
  const [markingPaidJobId, setMarkingPaidJobId] = useState(null);
  const [servicePopup, setServicePopup] = useState(null);
  const [invoiceJob, setInvoiceJob] = useState(null);
  const [dragOverCol, setDragOverCol] = useState(null);
  const [localStatusOverrides, setLocalStatusOverrides] = useState({});

  // Single batch request replaces 3 separate fetches (invoice-config, services-menu, packages)
  const { data: jobSetupData } = useQuery({
    queryKey: ['job-setup-data'],
    queryFn: async () => (await getJobSetupData()).data,
    staleTime: 5 * 60 * 1000, // 5 min — this data changes rarely
  });

  const invoiceConfig = jobSetupData?.invoice_config;
  const servicesMenu = jobSetupData?.services_menu;
  const packagesData = jobSetupData?.packages;

  const services = servicesMenu?.services || [];
  const packages = packagesData?.packages || packagesData || [];

  const findServiceOrPackage = (serviceType) => {
    if (!serviceType) return null;
    const name = serviceType.toLowerCase().trim();
    const svc = services.find(s => s.name?.toLowerCase().trim() === name);
    if (svc) return { type: 'service', data: svc };
    const pkg = packages.find(p => p.name?.toLowerCase().trim() === name);
    if (pkg) return { type: 'package', data: pkg };
    return null;
  };

  const markPaidMutation = useMutation({
    mutationFn: (jobId) => updateBooking(jobId, { payment_status: 'paid', payment_method: 'manual' }),
    onMutate: async (jobId) => {
      setMarkingPaidJobId(jobId);
      await queryClient.cancelQueries({ queryKey: ['dashboard'] });
      const previousDashboard = queryClient.getQueryData(['dashboard']);
      if (previousDashboard) {
        queryClient.setQueryData(['dashboard'], {
          ...previousDashboard,
          bookings: (previousDashboard.bookings || []).map(b =>
            b.id === jobId ? { ...b, payment_status: 'paid', payment_method: 'manual' } : b
          ),
        });
      }
      return { previousDashboard };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['finances'] });
      queryClient.invalidateQueries({ queryKey: ['bookings'] });
      queryClient.invalidateQueries({ queryKey: ['invoice-aging'] });
      queryClient.invalidateQueries({ queryKey: ['revenue-entries'] });
      queryClient.invalidateQueries({ queryKey: ['pnl-report'] });
      addToast(`${terminology.job} marked as paid`, 'success');
      setMarkingPaidJobId(null);
    },
    onError: (_, __, context) => {
      if (context?.previousDashboard) queryClient.setQueryData(['dashboard'], context.previousDashboard);
      addToast('Failed to mark job as paid', 'error');
      setMarkingPaidJobId(null);
    }
  });

  const unmarkPaidMutation = useMutation({
    mutationFn: (jobId) => updateBooking(jobId, { payment_status: 'unpaid', payment_method: null }),
    onMutate: async (jobId) => {
      setMarkingPaidJobId(jobId);
      await queryClient.cancelQueries({ queryKey: ['dashboard'] });
      const previousDashboard = queryClient.getQueryData(['dashboard']);
      if (previousDashboard) {
        queryClient.setQueryData(['dashboard'], {
          ...previousDashboard,
          bookings: (previousDashboard.bookings || []).map(b =>
            b.id === jobId ? { ...b, payment_status: 'unpaid', payment_method: null } : b
          ),
        });
      }
      return { previousDashboard };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['finances'] });
      queryClient.invalidateQueries({ queryKey: ['bookings'] });
      queryClient.invalidateQueries({ queryKey: ['invoice-aging'] });
      queryClient.invalidateQueries({ queryKey: ['revenue-entries'] });
      queryClient.invalidateQueries({ queryKey: ['pnl-report'] });
      addToast(`${terminology.job} marked as unpaid`, 'success');
      setMarkingPaidJobId(null);
    },
    onError: (_, __, context) => {
      if (context?.previousDashboard) queryClient.setQueryData(['dashboard'], context.previousDashboard);
      addToast('Failed to update payment status', 'error');
      setMarkingPaidJobId(null);
    }
  });

  const dragStatusMutation = useMutation({
    mutationFn: ({ jobId, status }) => updateBooking(jobId, { status }),
    onMutate: async ({ jobId, status }) => {
      await queryClient.cancelQueries({ queryKey: ['dashboard'] });
      const previousDashboard = queryClient.getQueryData(['dashboard']);
      if (previousDashboard) {
        queryClient.setQueryData(['dashboard'], {
          ...previousDashboard,
          bookings: (previousDashboard.bookings || []).map(b =>
            b.id === jobId ? { ...b, status } : b
          ),
        });
      }
      return { previousDashboard };
    },
    onSuccess: (_, { jobId }) => {
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      setLocalStatusOverrides(prev => { const n = { ...prev }; delete n[jobId]; return n; });
    },
    onError: (_, { jobId }, context) => {
      if (context?.previousDashboard) queryClient.setQueryData(['dashboard'], context.previousDashboard);
      setLocalStatusOverrides(prev => { const n = { ...prev }; delete n[jobId]; return n; });
      addToast('Failed to update status', 'error');
    },
  });

  const handleBoardDrop = (e, targetStatus) => {
    e.preventDefault();
    setDragOverCol(null);
    const jobId = parseInt(e.dataTransfer.getData('text/plain'));
    if (!jobId) return;
    const job = bookings.find(b => b.id === jobId);
    if (!job) return;
    const currentStatus = localStatusOverrides[jobId] || (job.status === 'confirmed' ? 'scheduled' : job.status);
    if (currentStatus === targetStatus) return;
    // Instantly move the card via local state
    setLocalStatusOverrides(prev => ({ ...prev, [jobId]: targetStatus }));
    // Fire the API call in the background
    dragStatusMutation.mutate({ jobId, status: targetStatus });
  };

  const invoiceMutation = useMutation({
    mutationFn: ({ jobId, invoiceData }) => sendInvoice(jobId, invoiceData),
    onSuccess: (response) => {
      const data = response.data;
      let msg = `Invoice sent via ${data?.delivery_method || 'email'} to ${data?.sent_to || 'customer'}`;
      if (data && !data.has_payment_link) msg += ' (no payment link)';
      addToast(msg, 'success');
      setInvoiceJob(null);
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['finances'] });
      queryClient.invalidateQueries({ queryKey: ['bookings'] });
      queryClient.invalidateQueries({ queryKey: ['invoice-aging'] });
    },
    onError: (error) => addToast(error.response?.data?.error || 'Failed to send invoice', 'error'),
  });

  const handleAddClick = () => {
    if (!isSubscriptionActive) { addToast(`Please upgrade your plan to add ${terminology.jobs.toLowerCase()}`, 'warning'); return; }
    setShowAddModal(true);
  };

  const now = useMemo(() => new Date(), [bookings]);
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const tomorrowStart = new Date(todayStart); tomorrowStart.setDate(tomorrowStart.getDate() + 1);
  const dayAfterTomorrow = new Date(tomorrowStart); dayAfterTomorrow.setDate(dayAfterTomorrow.getDate() + 1);
  const weekEnd = new Date(todayStart); weekEnd.setDate(weekEnd.getDate() + 7);

  const counts = useMemo(() => {
    // Normalize legacy 'paid' status to 'completed' for counting
    const norm = (s) => s === 'paid' ? 'completed' : s;
    const activeAll = bookings.filter(j => !['completed', 'paid', 'cancelled', 'rejected'].includes(j.status));
    const overdue = activeAll.filter(j => j.status !== 'in-progress' && parseServerDate(j.appointment_time) < now);
    const active = activeAll.filter(j => j.status === 'in-progress' || parseServerDate(j.appointment_time) >= now);
    const inProg = bookings.filter(j => j.status === 'in-progress');
    const needsInv = bookings.filter(j => (norm(j.status) === 'completed') && j.payment_status !== 'paid');
    const done = bookings.filter(j => norm(j.status) === 'completed');
    const canc = bookings.filter(j => j.status === 'cancelled');
    const rej = bookings.filter(j => j.status === 'rejected');
    // Recently booked = created in last 48 hours
    const recentCutoff = new Date(now.getTime() - 48 * 60 * 60 * 1000);
    const recent = bookings.filter(j => {
      const created = new Date(j.created_at);
      return created >= recentCutoff && !['cancelled', 'rejected'].includes(j.status);
    });
    return { active: active.length, recent: recent.length, overdue: overdue.length, 'in-progress': inProg.length, 'needs-invoice': needsInv.length, completed: done.length, cancelled: canc.length, rejected: rej.length, all: bookings.length };
  }, [bookings]);

  // Filter and group jobs
  const { groups } = useMemo(() => {
    let jobs = [...bookings];

    // Search filter
    if (searchTerm.trim()) {
      const term = searchTerm.toLowerCase();
      jobs = jobs.filter(j =>
        j.customer_name?.toLowerCase().includes(term) ||
        j.service?.toLowerCase().includes(term) ||
        j.service_type?.toLowerCase().includes(term) ||
        j.phone?.includes(term) ||
        j.email?.toLowerCase().includes(term) ||
        j.job_address?.toLowerCase().includes(term) ||
        j.address?.toLowerCase().includes(term) ||
        j.eircode?.toLowerCase().includes(term) ||
        j.table_number?.toLowerCase().includes(term) ||
        j.dining_area?.toLowerCase().includes(term) ||
        j.special_requests?.toLowerCase().includes(term) ||
        j.status?.toLowerCase().includes(term)
      );
    }

    // Status filter
    if (statusFilter === 'active') {
      jobs = jobs.filter(j => !['completed', 'paid', 'cancelled', 'rejected'].includes(j.status) && (j.status === 'in-progress' || parseServerDate(j.appointment_time) >= now));
    } else if (statusFilter === 'recent') {
      const recentCutoff = new Date(now.getTime() - 48 * 60 * 60 * 1000);
      jobs = jobs.filter(j => {
        const created = new Date(j.created_at);
        return created >= recentCutoff && !['cancelled', 'rejected'].includes(j.status);
      });
    } else if (statusFilter === 'overdue') {
      jobs = jobs.filter(j => !['completed', 'paid', 'cancelled', 'rejected', 'in-progress'].includes(j.status) && parseServerDate(j.appointment_time) < now);
    } else if (statusFilter === 'in-progress') {
      jobs = jobs.filter(j => j.status === 'in-progress');
    } else if (statusFilter === 'needs-invoice') {
      jobs = jobs.filter(j => (j.status === 'completed' || j.status === 'paid') && j.payment_status !== 'paid');
    } else if (statusFilter === 'completed') {
      jobs = jobs.filter(j => j.status === 'completed' || j.status === 'paid');
    } else if (statusFilter === 'cancelled') {
      jobs = jobs.filter(j => j.status === 'cancelled');
    } else if (statusFilter === 'rejected') {
      jobs = jobs.filter(j => j.status === 'rejected');
    }

    jobs.sort((a, b) => {
      // In-progress always first
      if (a.status === 'in-progress' && b.status !== 'in-progress') return -1;
      if (b.status === 'in-progress' && a.status !== 'in-progress') return 1;
      return parseServerDate(a.appointment_time) - parseServerDate(b.appointment_time);
    });

    // Group into sections
    const sections = [];
    const isActive = (j) => !['completed', 'paid', 'cancelled', 'rejected'].includes(j.status);

    // For 'recent' filter, show as a single flat section sorted by creation time
    if (statusFilter === 'recent') {
      const sortedByCreated = [...jobs].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
      if (sortedByCreated.length > 0) {
        sections.push({ key: 'recent', label: 'Booked in Last 48 Hours', icon: 'fa-bell', color: '#8b5cf6', jobs: sortedByCreated });
      }
      return { groups: sections, totalFiltered: jobs.length };
    }

    // In Progress (always shown first if any)
    const inProg = jobs.filter(j => j.status === 'in-progress');
    if (inProg.length > 0) sections.push({ key: 'in-progress', label: 'In Progress', icon: 'fa-wrench', color: '#8b5cf6', jobs: inProg });

    // Overdue
    const overdue = jobs.filter(j => isActive(j) && j.status !== 'in-progress' && parseServerDate(j.appointment_time) < now);
    if (overdue.length > 0) sections.push({ key: 'overdue', label: 'Late — Past Appointment Time', icon: 'fa-exclamation-circle', color: '#ef4444', jobs: overdue });

    // Today
    const today = jobs.filter(j => isActive(j) && j.status !== 'in-progress' && (() => { const t = parseServerDate(j.appointment_time); return t >= now && t < tomorrowStart; })());
    if (today.length > 0) sections.push({ key: 'today', label: 'Today', icon: 'fa-sun', color: '#f59e0b', jobs: today });

    // Tomorrow
    const tomorrow = jobs.filter(j => isActive(j) && j.status !== 'in-progress' && (() => { const t = parseServerDate(j.appointment_time); return t >= tomorrowStart && t < dayAfterTomorrow; })());
    if (tomorrow.length > 0) sections.push({ key: 'tomorrow', label: 'Tomorrow', icon: 'fa-calendar-day', color: '#3b82f6', jobs: tomorrow });

    // This Week
    const thisWeek = jobs.filter(j => isActive(j) && j.status !== 'in-progress' && (() => { const t = parseServerDate(j.appointment_time); return t >= dayAfterTomorrow && t < weekEnd; })());
    if (thisWeek.length > 0) sections.push({ key: 'this-week', label: 'This Week', icon: 'fa-calendar-week', color: '#6366f1', jobs: thisWeek });

    // Later
    const later = jobs.filter(j => isActive(j) && j.status !== 'in-progress' && parseServerDate(j.appointment_time) >= weekEnd);
    if (later.length > 0) sections.push({ key: 'later', label: 'Upcoming', icon: 'fa-calendar-alt', color: '#0ea5e9', jobs: later });

    // Needs Invoice
    const needsInv = jobs.filter(j => (j.status === 'completed' || j.status === 'paid') && j.payment_status !== 'paid');
    if (needsInv.length > 0 && (statusFilter === 'needs-invoice' || statusFilter === 'all' || statusFilter === 'completed')) {
      sections.push({ key: 'needs-invoice', label: 'Done — Unpaid', icon: 'fa-file-invoice', color: '#f59e0b', jobs: needsInv.slice(0, 20) });
    }

    // Completed/Paid
    const done = jobs.filter(j => (j.status === 'completed' || j.status === 'paid') && j.payment_status === 'paid');
    if (done.length > 0 && (statusFilter === 'completed' || statusFilter === 'all')) {
      sections.push({ key: 'completed', label: 'Completed & Paid', icon: 'fa-check-circle', color: '#10b981', jobs: done.slice(0, 20) });
    }

    // Cancelled
    const canc = jobs.filter(j => j.status === 'cancelled');
    if (canc.length > 0 && (statusFilter === 'cancelled' || statusFilter === 'all')) {
      sections.push({ key: 'cancelled', label: 'Cancelled', icon: 'fa-ban', color: '#9ca3af', jobs: canc.slice(0, 10) });
    }

    // Rejected
    const rej = jobs.filter(j => j.status === 'rejected');
    if (rej.length > 0 && (statusFilter === 'rejected' || statusFilter === 'all')) {
      sections.push({ key: 'rejected', label: 'Rejected', icon: 'fa-times-circle', color: '#ef4444', jobs: rej.slice(0, 10) });
    }

    return { groups: sections, totalFiltered: jobs.length };
  }, [bookings, searchTerm, statusFilter]);

  const getAddress = (job) => {
    const addr = job.job_address || job.address || '';
    const code = job.eircode || '';
    if (addr && code) return `${addr} (${code})`;
    return addr || code || 'No address';
  };

  const BOARD_COLUMNS = [
    { key: 'pending', label: 'New', color: '#f59e0b', icon: 'fa-clock' },
    { key: 'quote_sent', label: 'Quote Sent', color: '#3b82f6', icon: 'fa-paper-plane' },
    { key: 'scheduled', label: 'Scheduled', color: '#6366f1', icon: 'fa-calendar-check' },
    { key: 'in-progress', label: 'In Progress', color: '#8b5cf6', icon: 'fa-wrench' },
    { key: 'completed', label: 'Completed', color: '#22c55e', icon: 'fa-check-circle' },
  ];

  const boardData = useMemo(() => {
    const cols = {};
    BOARD_COLUMNS.forEach(c => { cols[c.key] = []; });
    let filtered = [...bookings];
    if (searchTerm.trim()) {
      const term = searchTerm.toLowerCase();
      filtered = filtered.filter(j =>
        j.customer_name?.toLowerCase().includes(term) || j.service_type?.toLowerCase().includes(term) ||
        j.phone?.includes(term) || j.job_address?.toLowerCase().includes(term)
      );
    }
    filtered.forEach(j => {
      if (['cancelled', 'rejected'].includes(j.status)) return;
      // Apply local overrides for instant drag feedback
      const effectiveStatus = localStatusOverrides[j.id] || (j.status === 'confirmed' ? 'scheduled' : j.status === 'paid' ? 'completed' : j.status);
      if (cols[effectiveStatus]) cols[effectiveStatus].push(j);
      else if (cols.pending) cols.pending.push(j);
    });
    Object.values(cols).forEach(arr => arr.sort((a, b) => parseServerDate(a.appointment_time) - parseServerDate(b.appointment_time)));
    return cols;
  }, [bookings, searchTerm, localStatusOverrides]);

  return (
    <div className="jobs-tab">
      {/* Page Header */}
      <div className="tab-page-header">
        <h2 className="tab-page-title">{terminology.jobs}</h2>
      </div>

      {/* Header with search and add */}
      <div className="jt-header">
        <div className="jt-search">
          <i className="fas fa-search"></i>
          <input type="text" placeholder={features.tableManagement ? "Search by name, table, area, requests..." : "Search by name, service, address, phone..."} value={searchTerm} onChange={e => setSearchTerm(e.target.value)} />
          {searchTerm && <button className="jt-search-clear" onClick={() => setSearchTerm('')}><i className="fas fa-times"></i></button>}
        </div>
        <div className="jt-header-actions">
          <div className="jt-view-toggle">
            <button className={viewMode === 'list' ? 'active' : ''} onClick={() => setViewMode('list')} title="List view"><i className="fas fa-list"></i> List</button>
            <button className={viewMode === 'board' ? 'active' : ''} onClick={() => setViewMode('board')} title="Board view"><i className="fas fa-columns"></i> Board</button>
          </div>
          <button className="btn-add" onClick={handleAddClick} title={`Create a new ${terminology.job.toLowerCase()}`}>
            <i className={`fas ${isSubscriptionActive ? 'fa-plus' : 'fa-lock'}`}></i> Add {terminology.job}
          </button>
        </div>
      </div>

      {/* Filter pills - list view only */}
      {viewMode === 'list' && (
      <>
      <div className="jt-filters">
        {STATUS_FILTERS.map(f => (
          <button key={f.key} className={`jt-filter ${statusFilter === f.key ? 'active' : ''} ${f.key === 'overdue' && counts.overdue > 0 ? 'has-alert' : ''}`}
            onClick={() => setStatusFilter(f.key)}>
            <i className={`fas ${f.icon}`}></i>
            <span className="jt-filter-label">{f.label}</span>
            {counts[f.key] > 0 && <span className="jt-filter-count">{counts[f.key]}</span>}
          </button>
        ))}
      </div>

      {/* Job sections */}
      <div className="jt-sections">
        {groups.length === 0 ? (
          <div className="dash-empty">
            <span className="dash-empty-icon">{statusFilter === 'overdue' ? '✅' : statusFilter === 'needs-invoice' ? '💰' : '📋'}</span>
            <h3>{statusFilter === 'overdue' ? 'All caught up' : statusFilter === 'needs-invoice' ? 'All invoiced' : searchTerm ? 'No matches' : `No ${terminology.jobs.toLowerCase()} yet`}</h3>
            <p>{statusFilter === 'overdue' ? `No overdue ${terminology.jobs.toLowerCase()} — nice work!` : statusFilter === 'needs-invoice' ? `All completed ${terminology.jobs.toLowerCase()} have been invoiced` : searchTerm ? 'Try a different search term' : `${terminology.jobs} will appear here as they are booked`}</p>
          </div>
        ) : (
          groups.map(section => (
            <div key={section.key} className={`jt-section jt-section-${section.key}`}>
              <div className="jt-section-header" style={{ '--section-color': section.color }}>
                <div className="jt-section-title">
                  <i className={`fas ${section.icon}`} style={{ color: section.color }}></i>
                  <h3>{section.label}</h3>
                </div>
                <span className="jt-section-count">{section.jobs.length}</span>
              </div>
              <div className="jt-cards">
                {section.jobs.map(job => {
                  const isPast = parseServerDate(job.appointment_time) < now && job.status !== 'in-progress' && job.status !== 'completed' && job.status !== 'paid' && job.status !== 'cancelled';
                  const isNow = Math.abs(parseServerDate(job.appointment_time) - now) < 30 * 60 * 1000 && job.status !== 'completed' && job.status !== 'cancelled';
                  return (
                    <div key={job.id} className={`jt-card ${isPast ? 'jt-card-overdue' : ''} ${isNow ? 'jt-card-now' : ''} ${job.status === 'in-progress' ? 'jt-card-active' : ''}`}
                      onClick={() => setSelectedJobId(job.id)}>
                      <div className="jt-card-left">
                        <div className="jt-card-time">
                          <span className="jt-time">{parseServerDate(job.appointment_time).toLocaleTimeString('en-IE', { hour: '2-digit', minute: '2-digit' })}</span>
                          <span className="jt-date">{parseServerDate(job.appointment_time).toLocaleDateString('en-IE', { weekday: 'short', day: 'numeric', month: 'short' })}</span>
                        </div>
                      </div>
                      <div className="jt-card-body">
                        <div className="jt-card-top">
                          <h4>{job.customer_name || 'Unknown'}</h4>
                          {(!job.assigned_employee_ids || job.assigned_employee_ids.length === 0) && !['completed', 'cancelled', 'rejected'].includes(job.status) && (
                            <span className="jt-no-employee-badge" title="No employee assigned to this job">
                              <i className="fas fa-exclamation-triangle"></i> No Employee Assigned
                            </span>
                          )}
                          <span className={`jt-status-badge jt-status-${job.status === 'paid' ? 'completed' : job.status}`}>{
                            job.status === 'in-progress' ? 'In Progress' :
                            job.status === 'quote_sent' ? 'Quote Sent' :
                            job.status === 'pending' ? 'New' :
                            job.status === 'paid' ? 'Completed' :
                            job.status
                          }</span>
                          {job.payment_status === 'paid' && <span className="jt-paid-badge"><i className="fas fa-check-circle"></i> Paid</span>}
                          {job.payment_status === 'invoiced' && <span className="jt-invoiced-badge"><i className="fas fa-file-invoice"></i> Invoiced</span>}
                          {job.payment_status === 'refunded' && <span className="jt-refunded-badge"><i className="fas fa-undo"></i> Refunded</span>}
                          {job.payment_status === 'partial_refund' && <span className="jt-refunded-badge"><i className="fas fa-undo"></i> Partial Refund</span>}
                          {features.emergencyJobs && job.urgency === 'emergency' && <span className="jt-emergency-badge"><i className="fas fa-bolt"></i> Emergency{job.emergency_status === 'pending_acceptance' ? ' — Pending' : job.emergency_status === 'accepted' ? ' — Accepted' : ''}</span>}
                          {job.status_label && <span className="jt-label-badge"><i className="fas fa-tag"></i> {job.status_label}</span>}
                          {job.recurrence_pattern && <span className="jt-recurring-badge"><i className="fas fa-redo"></i> {job.recurrence_pattern}</span>}
                        </div>
                        <div className="jt-card-info">
                          {(() => {
                            const match = findServiceOrPackage(job.service_type || job.service);
                            if (match) {
                              return (
                                <button
                                  className={`jt-service-chip jt-service-chip-${match.type}`}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setServicePopup(servicePopup?.data?.id === match.data.id ? null : match);
                                  }}
                                  title={`View ${match.type} details`}
                                >
                                  <i className={`fas ${match.type === 'package' ? 'fa-box' : 'fa-wrench'}`}></i>
                                  {job.service_type || job.service || 'Service'}
                                </button>
                              );
                            }
                            return <span className="jt-info-item"><i className="fas fa-wrench"></i> {job.service_type || job.service || 'Service'}</span>;
                          })()}
                          {features.tableManagement ? (
                            <>
                              {job.table_number && (
                                <span className="jt-info-item"><i className="fas fa-chair"></i> Table {job.table_number}</span>
                              )}
                              {job.party_size && (
                                <span className="jt-info-item"><i className="fas fa-users"></i> {job.party_size} guest{Number(job.party_size) !== 1 ? 's' : ''}</span>
                              )}
                              {job.dining_area && (
                                <span className="jt-info-item"><i className="fas fa-utensils"></i> {job.dining_area}</span>
                              )}
                            </>
                          ) : (
                            <span className="jt-info-item"><i className="fas fa-map-marker-alt"></i> {getAddress(job)}</span>
                          )}
                          {job.address_audio_url && (
                            <button className="jt-audio-btn" onClick={e => { e.stopPropagation(); new Audio(getProxiedMediaUrl(job.address_audio_url)).play(); }} title="Listen to address audio">
                              <i className="fas fa-volume-up"></i> Listen
                            </button>
                          )}
                        </div>
                        <div className="jt-card-bottom">
                          {/* Customer media thumbnails */}
                          {(job.customer_photo_urls?.length > 0 || job.photo_urls?.length > 0) && (
                            <span className="jt-media-badge" title={`${(job.customer_photo_urls?.length || 0) + (job.photo_urls?.length || 0)} media files`}>
                              <i className="fas fa-images"></i> {(job.customer_photo_urls?.length || 0) + (job.photo_urls?.length || 0)}
                            </span>
                          )}
                          {features.tableManagement && job.special_requests && (
                            <span className="jt-special-requests" title={job.special_requests}>
                              <i className="fas fa-comment-dots"></i> {job.special_requests.length > 40 ? job.special_requests.slice(0, 40) + '...' : job.special_requests}
                            </span>
                          )}
                          {(job.phone || job.phone_number) && (
                            <a href={`tel:${job.phone || job.phone_number}`} className="jt-phone" onClick={e => e.stopPropagation()}>
                              <i className="fas fa-phone"></i> {job.phone || job.phone_number}
                            </a>
                          )}
                          {job.duration_minutes && job.duration_minutes < 1440 && (
                            <span className="jt-duration"><i className="fas fa-clock"></i> {formatDuration(job.duration_minutes)}</span>
                          )}
                          {!!(job.charge || job.estimated_charge) && (
                            <span className="jt-charge">
                              {job.charge_max && parseFloat(job.charge_max) > parseFloat(job.charge || job.estimated_charge)
                                ? `${formatCurrency(job.charge || job.estimated_charge)} – ${formatCurrency(job.charge_max)}`
                                : formatCurrency(job.charge || job.estimated_charge)}
                            </span>
                          )}
                          {job.status !== 'completed' && job.status !== 'cancelled' && job.status !== 'rejected' && job.payment_status !== 'paid' && (job.charge || job.estimated_charge) && (
                            <button className="jt-mark-paid" onClick={e => { e.stopPropagation(); markPaidMutation.mutate(job.id); }}
                              disabled={markingPaidJobId === job.id}>
                              <i className={`fas ${markingPaidJobId === job.id ? 'fa-spinner fa-spin' : 'fa-check'}`}></i> Mark Paid
                            </button>
                          )}
                          {job.status === 'completed' && job.payment_status !== 'paid' && (job.charge || job.estimated_charge) && showInvoiceButtons && invoiceConfig?.can_send_invoice && (
                            <button className="jt-send-invoice" onClick={e => { e.stopPropagation(); setInvoiceJob(job); }}
                              title={`Send invoice via ${invoiceConfig?.service_name || 'SMS'}`}>
                              <i className="fas fa-file-invoice-dollar"></i> Invoice
                            </button>
                          )}
                          {job.status === 'completed' && job.payment_status !== 'paid' && (
                            <button className="jt-mark-paid" onClick={e => { e.stopPropagation(); markPaidMutation.mutate(job.id); }}
                              disabled={markingPaidJobId === job.id}>
                              <i className={`fas ${markingPaidJobId === job.id ? 'fa-spinner fa-spin' : 'fa-check'}`}></i> Paid
                            </button>
                          )}
                          {job.payment_status === 'paid' && job.payment_method === 'manual' && (
                            <button className="jt-unmark-paid" onClick={e => { e.stopPropagation(); unmarkPaidMutation.mutate(job.id); }}
                              disabled={markingPaidJobId === job.id} title="Undo manual payment">
                              <i className={`fas ${markingPaidJobId === job.id ? 'fa-spinner fa-spin' : 'fa-undo'}`}></i> Undo Paid
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))
        )}
      </div>
      </>
      )}

      {/* Board View */}
      {viewMode === 'board' && (
        <div className="jt-board">
          {BOARD_COLUMNS.map(col => (
            <div key={col.key}
              className={`jt-board-col ${dragOverCol === col.key ? 'jt-board-col-dragover' : ''}`}
              onDragOver={e => { e.preventDefault(); setDragOverCol(col.key); }}
              onDragLeave={() => setDragOverCol(null)}
              onDrop={e => handleBoardDrop(e, col.key)}>
              <div className="jt-board-col-head">
                <span className="jt-board-dot" style={{ background: col.color }}></span>
                <span className="jt-board-col-label">{col.label}</span>
                <span className="jt-board-col-count">{boardData[col.key]?.length || 0}</span>
              </div>
              <div className="jt-board-cards">
                {(boardData[col.key] || []).map(job => (
                  <div key={job.id} className="jt-board-card"
                    draggable
                    onDragStart={e => e.dataTransfer.setData('text/plain', String(job.id))}
                    onClick={() => setSelectedJobId(job.id)}>
                    <div className="jt-board-card-top">
                      <span className="jt-board-card-name">{job.customer_name || 'Unknown'}</span>
                      {job.payment_status === 'paid' && <span className="jt-paid-badge"><i className="fas fa-check-circle"></i> Paid</span>}
                      {job.payment_status === 'invoiced' && <span className="jt-invoiced-badge"><i className="fas fa-file-invoice"></i> Invoiced</span>}
                      {job.payment_status === 'refunded' && <span className="jt-refunded-badge"><i className="fas fa-undo"></i> Refunded</span>}
                    </div>
                    <div className="jt-board-card-service">{job.service_type || job.service || 'Service'}</div>
                    <div className="jt-board-card-meta">
                      <span><i className="fas fa-calendar"></i> {parseServerDate(job.appointment_time).toLocaleDateString('en-IE', { day: 'numeric', month: 'short' })}</span>
                      {features.tableManagement && job.table_number && <span><i className="fas fa-chair"></i> T{job.table_number}</span>}
                      {features.tableManagement && job.party_size && <span><i className="fas fa-users"></i> {job.party_size}</span>}
                      {!!(job.charge || job.estimated_charge) && <span className="jt-board-card-charge">{formatCurrency(job.charge || job.estimated_charge)}</span>}
                    </div>
                    {job.status_label && <span className="jt-label-badge" style={{ fontSize: '0.62rem', marginTop: '0.25rem' }}><i className="fas fa-tag"></i> {job.status_label}</span>}
                  </div>
                ))}
                {(boardData[col.key] || []).length === 0 && (
                  <div className="jt-board-empty">Drag jobs here</div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Service/Package Detail Popup */}
      {servicePopup && (
        <div className="jt-service-popup-overlay" onClick={() => setServicePopup(null)}>
          <div className="jt-service-popup" onClick={(e) => e.stopPropagation()}>
            <button className="jt-service-popup-close" onClick={() => setServicePopup(null)}>
              <i className="fas fa-times"></i>
            </button>
            <div className="jt-service-popup-header">
              <i className={`fas ${servicePopup.type === 'package' ? 'fa-box' : 'fa-wrench'}`}></i>
              <div>
                <h4>{servicePopup.data.name}</h4>
                <span className="jt-service-popup-type">{servicePopup.type === 'package' ? 'Package' : 'Service'}</span>
              </div>
            </div>
            {servicePopup.data.image_url && (
              <img src={servicePopup.data.image_url} alt={servicePopup.data.name} className="jt-service-popup-img" />
            )}
            <div className="jt-service-popup-meta">
              {servicePopup.type === 'service' ? (
                <>
                  {servicePopup.data.description && (
                    <p className="jt-popup-desc">{servicePopup.data.description}</p>
                  )}
                  {servicePopup.data.price > 0 && (
                    <div className="jt-popup-row">
                      <span className="jt-popup-label">Price</span>
                      <span className="jt-popup-value">
                        €{parseFloat(servicePopup.data.price).toFixed(2)}
                        {servicePopup.data.price_max && parseFloat(servicePopup.data.price_max) > parseFloat(servicePopup.data.price) && ` – €${parseFloat(servicePopup.data.price_max).toFixed(2)}`}
                      </span>
                    </div>
                  )}
                  {servicePopup.data.duration_minutes > 0 && (
                    <div className="jt-popup-row">
                      <span className="jt-popup-label">Duration</span>
                      <span className="jt-popup-value">{formatDuration(servicePopup.data.duration_minutes)}</span>
                    </div>
                  )}
                  {servicePopup.data.employees_required > 1 && (
                    <div className="jt-popup-row">
                      <span className="jt-popup-label">Employees</span>
                      <span className="jt-popup-value">{servicePopup.data.employees_required}</span>
                    </div>
                  )}
                  {servicePopup.data.requires_callout && (
                    <div className="jt-popup-badge"><i className="fas fa-phone-alt"></i> Requires callout</div>
                  )}
                  {servicePopup.data.requires_quote && (
                    <div className="jt-popup-badge"><i className="fas fa-file-invoice"></i> Requires quote</div>
                  )}
                  {servicePopup.data.package_only && (
                    <div className="jt-popup-badge"><i className="fas fa-box"></i> Package only</div>
                  )}
                </>
              ) : (
                <>
                  {servicePopup.data.description && (
                    <p className="jt-popup-desc">{servicePopup.data.description}</p>
                  )}
                  {(servicePopup.data.total_price > 0 || servicePopup.data.price_override > 0) && (
                    <div className="jt-popup-row">
                      <span className="jt-popup-label">Price</span>
                      <span className="jt-popup-value">
                        €{parseFloat(servicePopup.data.price_override || servicePopup.data.total_price).toFixed(2)}
                        {(servicePopup.data.price_max_override || servicePopup.data.total_price_max) > (servicePopup.data.price_override || servicePopup.data.total_price) &&
                          ` – €${parseFloat(servicePopup.data.price_max_override || servicePopup.data.total_price_max).toFixed(2)}`}
                      </span>
                    </div>
                  )}
                  {(servicePopup.data.total_duration_minutes > 0 || servicePopup.data.duration_override > 0) && (
                    <div className="jt-popup-row">
                      <span className="jt-popup-label">Duration</span>
                      <span className="jt-popup-value">{formatDuration(servicePopup.data.duration_override || servicePopup.data.total_duration_minutes)}</span>
                    </div>
                  )}
                  {servicePopup.data.services?.length > 0 && (
                    <div className="jt-popup-services">
                      <span className="jt-popup-label">Services included</span>
                      <div className="jt-popup-service-list">
                        {[...servicePopup.data.services]
                          .sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0))
                          .map((s, i) => (
                            <span key={s.id || i} className="jt-popup-service-step">
                              {i > 0 && <i className="fas fa-arrow-right jt-popup-arrow"></i>}
                              {s.name}
                            </span>
                          ))}
                      </div>
                    </div>
                  )}
                  {servicePopup.data.use_when_uncertain && (
                    <div className="jt-popup-badge"><i className="fas fa-search"></i> Requires investigation</div>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {showAddModal && <AddJobModal isOpen={showAddModal} onClose={() => setShowAddModal(false)} />}
      {!!selectedJobId && <JobDetailModal isOpen={!!selectedJobId} onClose={() => setSelectedJobId(null)} jobId={selectedJobId} showInvoiceButtons={showInvoiceButtons} />}
      {!!invoiceJob && <InvoiceConfirmModal
        isOpen={!!invoiceJob}
        onClose={() => setInvoiceJob(null)}
        onConfirm={(editedData) => invoiceMutation.mutate({ jobId: invoiceJob?.id, invoiceData: editedData })}
        job={invoiceJob}
        invoiceConfig={invoiceConfig}
        isPending={invoiceMutation.isPending}
      />}
    </div>
  );
}

export default JobsTab;
