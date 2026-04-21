import { useState, useMemo, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../Toast';
import { getWorkerHoursThisWeek, getWorkersHoursThisWeek, getCompanyTimeOffRequests, reviewTimeOffRequest, getUnreadMessageCounts } from '../../services/api';
import MessageWorkerModal from '../modals/MessageWorkerModal';
import AddWorkerModal from '../modals/AddWorkerModal';
import WorkerDetailModal from '../modals/WorkerDetailModal';
import './WorkersTab.css';
import './SharedDashboard.css';

// Same color palette as CalendarTab for consistency
const WORKER_COLORS = [
  '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
  '#ec4899', '#06b6d4', '#f97316', '#6366f1', '#14b8a6',
];

function WorkersTab({ workers, bookings }) {
  const { hasActiveSubscription } = useAuth();
  const isSubscriptionActive = hasActiveSubscription();
  const { addToast } = useToast();
  const queryClient = useQueryClient();
  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedWorkerId, setSelectedWorkerId] = useState(null);
  const [workersHours, setWorkersHours] = useState({});
  const [showTimeOff, setShowTimeOff] = useState(false);
  const [reviewNotes, setReviewNotes] = useState({});
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [messageWorkerId, setMessageWorkerId] = useState(null);
  const [messageWorkerName, setMessageWorkerName] = useState('');

  // Fetch time-off requests
  const { data: timeOffData } = useQuery({
    queryKey: ['company-time-off'],
    queryFn: async () => {
      const response = await getCompanyTimeOffRequests();
      return response.data;
    },
  });

  // Fetch unread message counts per worker
  const { data: unreadData } = useQuery({
    queryKey: ['unread-message-counts'],
    queryFn: async () => {
      const response = await getUnreadMessageCounts();
      return response.data;
    },
    refetchInterval: 60000,
  });

  const reviewMutation = useMutation({
    mutationFn: ({ id, status, note }) => reviewTimeOffRequest(id, status, note),
    onSuccess: (response, variables) => {
      queryClient.invalidateQueries({ queryKey: ['company-time-off'] });
      queryClient.invalidateQueries({ queryKey: ['calendar-time-off'] });
      const data = response.data;
      if (variables.status === 'approved' && data?.has_conflicts && data.conflicting_jobs?.length > 0) {
        const jobList = data.conflicting_jobs.map(j => `${j.date}: ${j.service}${j.client ? ` (${j.client})` : ''}`).join(', ');
        addToast(`Approved — but ${data.conflicting_jobs.length} existing job(s) overlap: ${jobList}. You may need to reassign them.`, 'warning');
      } else {
        addToast(`Request ${variables.status}`, 'success');
      }
      setReviewNotes(prev => { const n = { ...prev }; delete n[variables.id]; return n; });
    },
    onError: (error) => {
      addToast(error.response?.data?.error || 'Failed to update request', 'error');
    },
  });

  const pendingRequests = (timeOffData?.requests || []).filter(r => r.status === 'pending');
  const pastRequests = (timeOffData?.requests || []).filter(r => r.status !== 'pending');

  // Auto-expand time-off when pending requests arrive
  useEffect(() => {
    if (pendingRequests.length > 0) setShowTimeOff(true);
  }, [pendingRequests.length]);

  const handleAddClick = () => {
    if (!isSubscriptionActive) {
      addToast('Please upgrade your plan to add workers', 'warning');
      return;
    }
    setShowAddModal(true);
  };

  // Fetch hours for all workers (batch endpoint when available, falls back to parallel requests)
  useEffect(() => {
    let cancelled = false;
    const fetchHours = async () => {
      try {
        // Try the batch endpoint first — returns { hours: { [worker_id]: hours } }
        const batch = await getWorkersHoursThisWeek().catch(() => null);
        if (!cancelled && batch?.data?.hours) {
          // Normalize string keys (JSON) back to numeric worker ids
          const normalized = {};
          for (const [k, v] of Object.entries(batch.data.hours)) {
            const n = Number(k);
            normalized[Number.isNaN(n) ? k : n] = v;
          }
          setWorkersHours(normalized);
          return;
        }
        // Fallback: parallel fetches (still much faster than sequential)
        const results = await Promise.all(
          workers.map(w =>
            getWorkerHoursThisWeek(w.id)
              .then(r => [w.id, r.data.hours_worked])
              .catch(() => [w.id, 0])
          )
        );
        if (!cancelled) setWorkersHours(Object.fromEntries(results));
      } catch (error) {
        console.error('Error fetching worker hours:', error);
      }
    };

    if (workers.length > 0) fetchHours();
    return () => { cancelled = true; };
  }, [workers]);

  // Calculate worker status based on their jobs today
  const workersWithStatus = useMemo(() => {
    const now = new Date();
    const today = now.toDateString();
    
    return workers.map(worker => {
      // Find jobs assigned to this worker for today using assigned_worker_ids array
      const workerJobsToday = (bookings || []).filter(job => {
        if (!job || !job.appointment_time) return false;
        const jobDate = new Date(job.appointment_time);
        const isToday = jobDate.toDateString() === today;
        // Check if worker is in the assigned_worker_ids array (handle both number and string IDs)
        const assignedIds = job.assigned_worker_ids || [];
        const isAssigned = assignedIds.includes(worker.id) || assignedIds.includes(String(worker.id));
        const isActive = job.status !== 'completed' && job.status !== 'cancelled';
        return isToday && isAssigned && isActive;
      });

      // Check if currently on a job (within job time window)
      const currentJob = workerJobsToday.find(job => {
        const jobTime = new Date(job.appointment_time);
        const diffMinutes = (now - jobTime) / (1000 * 60);
        // Use job duration if available, otherwise default to 2 hours
        const jobDuration = job.duration_minutes || 120;
        // Consider busy if job started within last 30 mins before or during job duration
        return diffMinutes >= -30 && diffMinutes <= jobDuration;
      });

      // Count jobs today
      const jobsToday = workerJobsToday.length;
      const nextJob = workerJobsToday
        .filter(job => new Date(job.appointment_time) > now)
        .sort((a, b) => new Date(a.appointment_time) - new Date(b.appointment_time))[0];

      return {
        ...worker,
        isBusy: !!currentJob,
        currentJob,
        jobsToday,
        nextJob,
        hoursWorked: workersHours[worker.id] || 0,
        weeklyHoursExpected: worker.weekly_hours_expected || 40,
        isOnLeave: (timeOffData?.requests || []).some(r => {
          if (r.status !== 'approved' || r.worker_id !== worker.id) return false;
          const todayStr = now.toISOString().split('T')[0]; // YYYY-MM-DD
          return r.start_date <= todayStr && r.end_date >= todayStr;
        })
      };
    });
  }, [workers, bookings, workersHours, timeOffData]);

  // Build unread counts map { workerId: count }
  const unreadCounts = useMemo(() => {
    const map = {};
    const counts = unreadData?.counts;
    if (counts && typeof counts === 'object') {
      Object.entries(counts).forEach(([wId, count]) => { map[wId] = count; });
    }
    return map;
  }, [unreadData]);

  // Filter workers by search and status
  const filteredWorkers = useMemo(() => {
    return workersWithStatus.filter(w => {
      const matchesSearch = !searchQuery || 
        w.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        w.specialty?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        w.phone?.includes(searchQuery);
      
      if (!matchesSearch) return false;
      
      if (statusFilter === 'available') return !w.isBusy && !w.isOnLeave;
      if (statusFilter === 'busy') return w.isBusy;
      if (statusFilter === 'leave') return w.isOnLeave;
      return true;
    });
  }, [workersWithStatus, searchQuery, statusFilter]);

  // Summary stats
  const stats = useMemo(() => ({
    total: workersWithStatus.length,
    available: workersWithStatus.filter(w => !w.isBusy && !w.isOnLeave).length,
    busy: workersWithStatus.filter(w => w.isBusy).length,
    onLeave: workersWithStatus.filter(w => w.isOnLeave).length,
  }), [workersWithStatus]);

  // Worker color map — same order as calendar
  const workerColorMap = useMemo(() => {
    const map = {};
    (workers || []).forEach((worker, index) => {
      map[worker.id] = WORKER_COLORS[index % WORKER_COLORS.length];
    });
    return map;
  }, [workers]);

  const handleQuickMessage = (e, worker) => {
    e.stopPropagation();
    setMessageWorkerId(worker.id);
    setMessageWorkerName(worker.name);
  };

  return (
    <div className="workers-tab">
      <div className="tab-page-header">
        <div>
          <h2>Workers</h2>
          {workers.length > 0 && (
            <div className="workers-stats-bar" style={{ marginTop: '0.35rem' }}>
              <span className="ws-stat">{stats.total} total</span>
              <span className="ws-stat available">{stats.available} available</span>
              {stats.busy > 0 && <span className="ws-stat busy">{stats.busy} on job</span>}
              {stats.onLeave > 0 && <span className="ws-stat leave">{stats.onLeave} on leave</span>}
            </div>
          )}
        </div>
        <button 
          className="btn-add" 
          onClick={handleAddClick}
        >
          <i className={`fas ${isSubscriptionActive ? 'fa-plus' : 'fa-lock'}`}></i> Add Worker
        </button>
      </div>

      {/* Search & Filter Bar */}
      {workers.length > 0 && (
        <div className="workers-toolbar">
          <div className="workers-search">
            <i className="fas fa-search"></i>
            <input
              type="text"
              placeholder="Search by name, specialty, or phone..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            {searchQuery && (
              <button className="search-clear" onClick={() => setSearchQuery('')}>
                <i className="fas fa-times"></i>
              </button>
            )}
          </div>
          <div className="workers-filter-pills">
            {['all', 'available', 'busy', 'leave'].map(f => (
              <button
                key={f}
                className={`filter-pill ${statusFilter === f ? 'active' : ''}`}
                onClick={() => setStatusFilter(f)}
              >
                {f === 'all' ? 'All' : f === 'available' ? 'Available' : f === 'busy' ? 'On Job' : 'On Leave'}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Time-Off Requests */}
      {(timeOffData?.requests || []).length > 0 && (
        <div className="time-off-section">
          <button className="time-off-toggle" onClick={() => setShowTimeOff(!showTimeOff)}>
            <div className="time-off-toggle-left">
              <i className="fas fa-umbrella-beach"></i>
              <span>Time-Off Requests</span>
              {pendingRequests.length > 0 && (
                <span className="time-off-badge">{pendingRequests.length} pending</span>
              )}
            </div>
            <i className={`fas fa-chevron-${showTimeOff ? 'up' : 'down'}`}></i>
          </button>

          {showTimeOff && (
            <div className="time-off-content">
              {pendingRequests.length > 0 && pendingRequests.map(req => {
                const reqWorkerColor = workerColorMap[req.worker_id] || '#94a3b8';
                return (
                  <div key={req.id} className="time-off-card pending" style={{ borderLeftColor: reqWorkerColor }}>
                    <div className="time-off-card-top">
                      <div className="time-off-card-header">
                        <span className="time-off-worker-name">
                          <span className="time-off-color-dot" style={{ backgroundColor: reqWorkerColor }}></span>
                          {req.worker_name}
                        </span>
                        <span className="time-off-type-badge">{req.type}</span>
                      </div>
                      <div className="time-off-dates">
                        <i className="fas fa-calendar"></i>
                        {new Date(req.start_date).toLocaleDateString('en-IE', { month: 'short', day: 'numeric' })}
                        {' — '}
                        {new Date(req.end_date).toLocaleDateString('en-IE', { month: 'short', day: 'numeric', year: 'numeric' })}
                      </div>
                      {req.reason && <p className="time-off-reason">{req.reason}</p>}
                    </div>
                    <div className="time-off-inline-actions">
                      <input
                        type="text"
                        className="time-off-note-input"
                        placeholder="Note (optional)"
                        value={reviewNotes[req.id] || ''}
                        onChange={e => setReviewNotes(prev => ({ ...prev, [req.id]: e.target.value }))}
                      />
                      <button
                        className="btn-pill approve"
                        onClick={() => { reviewMutation.mutate({ id: req.id, status: 'approved', note: reviewNotes[req.id] || '' }); }}
                        disabled={reviewMutation.isPending}
                        title="Approve"
                      >
                        <i className="fas fa-check"></i>
                      </button>
                      <button
                        className="btn-pill deny"
                        onClick={() => { reviewMutation.mutate({ id: req.id, status: 'denied', note: reviewNotes[req.id] || '' }); }}
                        disabled={reviewMutation.isPending}
                        title="Deny"
                      >
                        <i className="fas fa-times"></i>
                      </button>
                    </div>
                  </div>
                );
              })}

              {pastRequests.length > 0 && (
                <div className="time-off-past-summary">
                  <span className="time-off-past-label">Recent</span>
                  {pastRequests.slice(0, 5).map(req => (
                    <div key={req.id} className={`time-off-past-item ${req.status}`}>
                      <span className="time-off-color-dot" style={{ backgroundColor: workerColorMap[req.worker_id] || '#94a3b8' }}></span>
                      <span className="time-off-worker-name">{req.worker_name}</span>
                      <span className="time-off-dates-inline">
                        {new Date(req.start_date).toLocaleDateString('en-IE', { month: 'short', day: 'numeric' })}
                        {' — '}
                        {new Date(req.end_date).toLocaleDateString('en-IE', { month: 'short', day: 'numeric' })}
                      </span>
                      <span className={`time-off-status-dot ${req.status}`}>{req.status}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      <div className="workers-list">
        {filteredWorkers.length === 0 ? (
          <div className="empty-state">
            {searchQuery || statusFilter !== 'all' ? (
              <>
                <div className="empty-state-icon">🔍</div>
                <p>No workers match your filters</p>
                <button className="btn btn-secondary btn-sm" onClick={() => { setSearchQuery(''); setStatusFilter('all'); }}>
                  Clear Filters
                </button>
              </>
            ) : (
              <>
                <div className="empty-state-icon">👷</div>
                <p>No workers found</p>
              </>
            )}
          </div>
        ) : (
          filteredWorkers.map((worker) => {
            const unread = unreadCounts[worker.id] || unreadCounts[String(worker.id)] || 0;
            const workerColor = workerColorMap[worker.id] || '#94a3b8';
            return (
              <div 
                key={worker.id} 
                className={`worker-card ${worker.isBusy ? 'is-busy' : ''} ${worker.isOnLeave ? 'is-leave' : ''}`}
                onClick={() => setSelectedWorkerId(worker.id)}
                style={{ '--worker-color': workerColor }}
              >
                <div className="worker-avatar">
                  {worker.image_url ? (
                    <img src={worker.image_url} alt={worker.name} className="worker-avatar-img" />
                  ) : (
                    <i className="fas fa-hard-hat"></i>
                  )}
                  <span className={`status-dot ${worker.isOnLeave ? 'leave' : worker.isBusy ? 'busy' : 'available'}`}></span>
                </div>
                <div className="worker-info">
                  <div className="worker-name-row">
                    <h3>{worker.name}</h3>
                    {worker.isOnLeave && <span className="leave-chip"><i className="fas fa-umbrella-beach"></i> Leave</span>}
                  </div>
                  {worker.specialty && (
                    <span className="worker-specialty-tag">{worker.specialty}</span>
                  )}
                  <div className="worker-meta-row">
                    {worker.jobsToday > 0 && (
                      <span className="meta-chip jobs">
                        <i className="fas fa-briefcase"></i>
                        {worker.jobsToday} today
                      </span>
                    )}
                    {worker.nextJob && !worker.isBusy && (
                      <span className="meta-chip next">
                        <i className="fas fa-arrow-right"></i>
                        {new Date(worker.nextJob.appointment_time).toLocaleTimeString('en-US', { 
                          hour: 'numeric', 
                          minute: '2-digit' 
                        })}
                      </span>
                    )}
                    <span className="meta-chip hours">
                      <i className="fas fa-clock"></i>
                      {worker.hoursWorked}h / {worker.weeklyHoursExpected}h
                    </span>
                  </div>
                </div>
                <div className="worker-card-actions">
                  <button 
                    className="card-action-btn message"
                    onClick={(e) => handleQuickMessage(e, worker)}
                    title={`Message ${worker.name}`}
                  >
                    <i className="fas fa-comment-dots"></i>
                    {unread > 0 && <span className="unread-dot">{unread}</span>}
                  </button>
                  {worker.phone && (
                    <a 
                      href={`tel:${worker.phone}`} 
                      className="card-action-btn call"
                      onClick={(e) => e.stopPropagation()}
                      title={`Call ${worker.name}`}
                    >
                      <i className="fas fa-phone"></i>
                    </a>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Modals */}
      <AddWorkerModal 
        isOpen={showAddModal} 
        onClose={() => setShowAddModal(false)} 
      />
      <WorkerDetailModal
        isOpen={!!selectedWorkerId}
        onClose={() => setSelectedWorkerId(null)}
        workerId={selectedWorkerId}
      />
      <MessageWorkerModal
        isOpen={!!messageWorkerId}
        onClose={() => { setMessageWorkerId(null); setMessageWorkerName(''); }}
        workerId={messageWorkerId}
        workerName={messageWorkerName}
      />
    </div>
  );
}

export default WorkersTab;
