import { useState, useMemo, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../../context/AuthContext';
import { useIndustry } from '../../context/IndustryContext';
import { useToast } from '../Toast';
import { getEmployeeHoursThisWeek, getEmployeesHoursThisWeek, getCompanyTimeOffRequests, reviewTimeOffRequest, getUnreadMessageCounts } from '../../services/api';
import MessageEmployeeModal from '../modals/MessageEmployeeModal';
import AddEmployeeModal from '../modals/AddEmployeeModal';
import EmployeeDetailModal from '../modals/EmployeeDetailModal';
import './EmployeesTab.css';
import './SharedDashboard.css';

// Same color palette as CalendarTab for consistency
const EMPLOYEE_COLORS = [
  '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
  '#ec4899', '#06b6d4', '#f97316', '#6366f1', '#14b8a6',
];

function EmployeesTab({ employees, bookings }) {
  const { hasActiveSubscription } = useAuth();
  const { terminology } = useIndustry();
  const isSubscriptionActive = hasActiveSubscription();
  const { addToast } = useToast();
  const queryClient = useQueryClient();
  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedEmployeeId, setSelectedEmployeeId] = useState(null);
  const [employeesHours, setEmployeesHours] = useState({});
  const [showTimeOff, setShowTimeOff] = useState(false);
  const [reviewNotes, setReviewNotes] = useState({});
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [messageEmployeeId, setMessageEmployeeId] = useState(null);
  const [messageEmployeeName, setMessageEmployeeName] = useState('');

  // Fetch time-off requests
  const { data: timeOffData } = useQuery({
    queryKey: ['company-time-off'],
    queryFn: async () => {
      const response = await getCompanyTimeOffRequests();
      return response.data;
    },
  });

  // Fetch unread message counts per employee
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
      addToast(`Please upgrade your plan to add ${terminology.employees.toLowerCase()}`, 'warning');
      return;
    }
    setShowAddModal(true);
  };

  // Fetch hours for all employees (batch endpoint when available, falls back to parallel requests)
  useEffect(() => {
    let cancelled = false;
    const fetchHours = async () => {
      try {
        // Try the batch endpoint first — returns { hours: { [employee_id]: hours } }
        const batch = await getEmployeesHoursThisWeek().catch(() => null);
        if (!cancelled && batch?.data?.hours) {
          // Normalize string keys (JSON) back to numeric employee ids
          const normalized = {};
          for (const [k, v] of Object.entries(batch.data.hours)) {
            const n = Number(k);
            normalized[Number.isNaN(n) ? k : n] = v;
          }
          setEmployeesHours(normalized);
          return;
        }
        // Fallback: parallel fetches (still much faster than sequential)
        const results = await Promise.all(
          employees.map(w =>
            getEmployeeHoursThisWeek(w.id)
              .then(r => [w.id, r.data.hours_worked])
              .catch(() => [w.id, 0])
          )
        );
        if (!cancelled) setEmployeesHours(Object.fromEntries(results));
      } catch (error) {
        console.error('Error fetching employee hours:', error);
      }
    };

    if (employees.length > 0) fetchHours();
    return () => { cancelled = true; };
  }, [employees]);

  // Calculate employee status based on their jobs today
  const employeesWithStatus = useMemo(() => {
    const now = new Date();
    const today = now.toDateString();
    
    return employees.map(employee => {
      // Find jobs assigned to this employee for today using assigned_employee_ids array
      const employeeJobsToday = (bookings || []).filter(job => {
        if (!job || !job.appointment_time) return false;
        const jobDate = new Date(job.appointment_time);
        const isToday = jobDate.toDateString() === today;
        // Check if employee is in the assigned_employee_ids array (handle both number and string IDs)
        const assignedIds = job.assigned_employee_ids || [];
        const isAssigned = assignedIds.includes(employee.id) || assignedIds.includes(String(employee.id));
        const isActive = job.status !== 'completed' && job.status !== 'cancelled';
        return isToday && isAssigned && isActive;
      });

      // Check if currently on a job (within job time window)
      const currentJob = employeeJobsToday.find(job => {
        const jobTime = new Date(job.appointment_time);
        const diffMinutes = (now - jobTime) / (1000 * 60);
        // Use job duration if available, otherwise default to 2 hours
        const jobDuration = job.duration_minutes || 120;
        // Consider busy if job started within last 30 mins before or during job duration
        return diffMinutes >= -30 && diffMinutes <= jobDuration;
      });

      // Count jobs today
      const jobsToday = employeeJobsToday.length;
      const nextJob = employeeJobsToday
        .filter(job => new Date(job.appointment_time) > now)
        .sort((a, b) => new Date(a.appointment_time) - new Date(b.appointment_time))[0];

      return {
        ...employee,
        isBusy: !!currentJob,
        currentJob,
        jobsToday,
        nextJob,
        hoursWorked: employeesHours[employee.id] || 0,
        weeklyHoursExpected: employee.weekly_hours_expected || 40,
        isOnLeave: (timeOffData?.requests || []).some(r => {
          if (r.status !== 'approved' || r.employee_id !== employee.id) return false;
          const todayStr = now.toISOString().split('T')[0]; // YYYY-MM-DD
          return r.start_date <= todayStr && r.end_date >= todayStr;
        })
      };
    });
  }, [employees, bookings, employeesHours, timeOffData]);

  // Build unread counts map { employeeId: count }
  const unreadCounts = useMemo(() => {
    const map = {};
    const counts = unreadData?.counts;
    if (counts && typeof counts === 'object') {
      Object.entries(counts).forEach(([wId, count]) => { map[wId] = count; });
    }
    return map;
  }, [unreadData]);

  // Filter employees by search and status
  const filteredEmployees = useMemo(() => {
    return employeesWithStatus.filter(w => {
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
  }, [employeesWithStatus, searchQuery, statusFilter]);

  // Summary stats
  const stats = useMemo(() => ({
    total: employeesWithStatus.length,
    available: employeesWithStatus.filter(w => !w.isBusy && !w.isOnLeave).length,
    busy: employeesWithStatus.filter(w => w.isBusy).length,
    onLeave: employeesWithStatus.filter(w => w.isOnLeave).length,
  }), [employeesWithStatus]);

  // Employee color map — same order as calendar
  const employeeColorMap = useMemo(() => {
    const map = {};
    (employees || []).forEach((employee, index) => {
      map[employee.id] = EMPLOYEE_COLORS[index % EMPLOYEE_COLORS.length];
    });
    return map;
  }, [employees]);

  const handleQuickMessage = (e, employee) => {
    e.stopPropagation();
    setMessageEmployeeId(employee.id);
    setMessageEmployeeName(employee.name);
  };

  return (
    <div className="employees-tab">
      <div className="tab-page-header">
        <div>
          <h2>{terminology.employees}</h2>
          {employees.length > 0 && (
            <div className="employees-stats-bar" style={{ marginTop: '0.35rem' }}>
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
          <i className={`fas ${isSubscriptionActive ? 'fa-plus' : 'fa-lock'}`}></i> Add {terminology.employee}
        </button>
      </div>

      {/* Search & Filter Bar */}
      {employees.length > 0 && (
        <div className="employees-toolbar">
          <div className="employees-search">
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
          <div className="employees-filter-pills">
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
                const reqEmployeeColor = employeeColorMap[req.employee_id] || '#94a3b8';
                return (
                  <div key={req.id} className="time-off-card pending" style={{ borderLeftColor: reqEmployeeColor }}>
                    <div className="time-off-card-top">
                      <div className="time-off-card-header">
                        <span className="time-off-employee-name">
                          <span className="time-off-color-dot" style={{ backgroundColor: reqEmployeeColor }}></span>
                          {req.employee_name}
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
                      <span className="time-off-color-dot" style={{ backgroundColor: employeeColorMap[req.employee_id] || '#94a3b8' }}></span>
                      <span className="time-off-employee-name">{req.employee_name}</span>
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

      <div className="employees-list">
        {filteredEmployees.length === 0 ? (
          <div className="empty-state">
            {searchQuery || statusFilter !== 'all' ? (
              <>
                <div className="empty-state-icon">🔍</div>
                <p>No {terminology.employees.toLowerCase()} match your filters</p>
                <button className="btn btn-secondary btn-sm" onClick={() => { setSearchQuery(''); setStatusFilter('all'); }}>
                  Clear Filters
                </button>
              </>
            ) : (
              <>
                <div className="empty-state-icon">👷</div>
                <p>No {terminology.employees.toLowerCase()} found</p>
              </>
            )}
          </div>
        ) : (
          filteredEmployees.map((employee) => {
            const unread = unreadCounts[employee.id] || unreadCounts[String(employee.id)] || 0;
            const employeeColor = employeeColorMap[employee.id] || '#94a3b8';
            return (
              <div 
                key={employee.id} 
                className={`employee-card ${employee.isBusy ? 'is-busy' : ''} ${employee.isOnLeave ? 'is-leave' : ''}`}
                onClick={() => setSelectedEmployeeId(employee.id)}
                style={{ '--employee-color': employeeColor }}
              >
                <div className="employee-avatar">
                  {employee.image_url ? (
                    <img src={employee.image_url} alt={employee.name} className="employee-avatar-img" />
                  ) : (
                    <i className="fas fa-hard-hat"></i>
                  )}
                  <span className={`status-dot ${employee.isOnLeave ? 'leave' : employee.isBusy ? 'busy' : 'available'}`}></span>
                </div>
                <div className="employee-info">
                  <div className="employee-name-row">
                    <h3>{employee.name}</h3>
                    {employee.isOnLeave && <span className="leave-chip"><i className="fas fa-umbrella-beach"></i> Leave</span>}
                  </div>
                  {employee.specialty && (
                    <span className="employee-specialty-tag">{employee.specialty}</span>
                  )}
                  <div className="employee-meta-row">
                    {employee.jobsToday > 0 && (
                      <span className="meta-chip jobs">
                        <i className="fas fa-briefcase"></i>
                        {employee.jobsToday} today
                      </span>
                    )}
                    {employee.nextJob && !employee.isBusy && (
                      <span className="meta-chip next">
                        <i className="fas fa-arrow-right"></i>
                        {new Date(employee.nextJob.appointment_time).toLocaleTimeString('en-US', { 
                          hour: 'numeric', 
                          minute: '2-digit' 
                        })}
                      </span>
                    )}
                    <span className="meta-chip hours">
                      <i className="fas fa-clock"></i>
                      {employee.hoursWorked}h / {employee.weeklyHoursExpected}h
                    </span>
                  </div>
                </div>
                <div className="employee-card-actions">
                  <button 
                    className="card-action-btn message"
                    onClick={(e) => handleQuickMessage(e, employee)}
                    title={`Message ${employee.name}`}
                  >
                    <i className="fas fa-comment-dots"></i>
                    {unread > 0 && <span className="unread-dot">{unread}</span>}
                  </button>
                  {employee.phone && (
                    <a 
                      href={`tel:${employee.phone}`} 
                      className="card-action-btn call"
                      onClick={(e) => e.stopPropagation()}
                      title={`Call ${employee.name}`}
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
      <AddEmployeeModal 
        isOpen={showAddModal} 
        onClose={() => setShowAddModal(false)} 
      />
      <EmployeeDetailModal
        isOpen={!!selectedEmployeeId}
        onClose={() => setSelectedEmployeeId(null)}
        employeeId={selectedEmployeeId}
      />
      <MessageEmployeeModal
        isOpen={!!messageEmployeeId}
        onClose={() => { setMessageEmployeeId(null); setMessageEmployeeName(''); }}
        employeeId={messageEmployeeId}
        employeeName={messageEmployeeName}
      />
    </div>
  );
}

export default EmployeesTab;
