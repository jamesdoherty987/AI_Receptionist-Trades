import { useState, useMemo, useEffect, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../../context/AuthContext';
import { useIndustry } from '../../context/IndustryContext';
import { useToast } from '../Toast';
import { getEmployeeHoursThisWeek, getEmployeesHoursThisWeek, getCompanyTimeOffRequests, reviewTimeOffRequest, getUnreadMessageCounts, getEmployeeSchedule, getBusinessHours, getAllEmployeeWorkSchedules } from '../../services/api';
import { parseServerDate } from '../../utils/helpers';
import MessageEmployeeModal from '../modals/MessageEmployeeModal';
import AddEmployeeModal from '../modals/AddEmployeeModal';
import EmployeeDetailModal from '../modals/EmployeeDetailModal';
import JobDetailModal from '../modals/JobDetailModal';
import './EmployeesTab.css';
import './SharedDashboard.css';

const EMPLOYEE_COLORS = [
  '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
  '#ec4899', '#06b6d4', '#f97316', '#6366f1', '#14b8a6',
];

const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const DAY_NAMES_FULL = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

function getWeekDates(offset = 0) {
  const now = new Date();
  const dayOfWeek = now.getDay();
  const mondayOffset = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
  const monday = new Date(now);
  monday.setDate(now.getDate() + mondayOffset + (offset * 7));
  monday.setHours(0, 0, 0, 0);

  const dates = [];
  for (let i = 0; i < 7; i++) {
    const d = new Date(monday);
    d.setDate(monday.getDate() + i);
    dates.push(d);
  }
  return dates;
}

function formatDateKey(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

function formatShortDate(date) {
  return date.toLocaleDateString('en-IE', { day: 'numeric', month: 'short' });
}

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
  const [viewMode, setViewMode] = useState('schedule'); // 'schedule' | 'team'
  const [weekOffset, setWeekOffset] = useState(0);
  const [dayPopover, setDayPopover] = useState(null); // { employeeId, date, jobs, shift, onLeave, employeeName, color }
  const [selectedJobId, setSelectedJobId] = useState(null);

  const weekDates = useMemo(() => getWeekDates(weekOffset), [weekOffset]);
  const weekLabel = useMemo(() => {
    const start = weekDates[0];
    const end = weekDates[6];
    if (weekOffset === 0) return 'This Week';
    if (weekOffset === 1) return 'Next Week';
    if (weekOffset === -1) return 'Last Week';
    return `${start.toLocaleDateString('en-IE', { day: 'numeric', month: 'short' })} – ${end.toLocaleDateString('en-IE', { day: 'numeric', month: 'short' })}`;
  }, [weekDates, weekOffset]);

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

  // Fetch business hours
  const { data: bizHoursData } = useQuery({
    queryKey: ['business-hours'],
    queryFn: async () => {
      const response = await getBusinessHours();
      return response.data;
    },
    staleTime: 5 * 60 * 1000,
  });

  // Fetch work schedules for all employees (shift data)
  const { data: workSchedulesData } = useQuery({
    queryKey: ['all-work-schedules'],
    queryFn: async () => {
      const response = await getAllEmployeeWorkSchedules();
      return response.data;
    },
    enabled: employees.length > 0,
    staleTime: 3 * 60 * 1000,
  });

  // Fetch schedules for all employees for the selected week
  const weekStart = formatDateKey(weekDates[0]);
  const weekEnd = formatDateKey(weekDates[6]) + 'T23:59:59';

  const { data: allSchedules } = useQuery({
    queryKey: ['employee-schedules', weekStart, weekEnd, employees.map(e => e.id).join(',')],
    queryFn: async () => {
      const results = await Promise.all(
        employees.map(e =>
          getEmployeeSchedule(e.id)
            .then(r => ({ id: e.id, jobs: r.data || [] }))
            .catch(() => ({ id: e.id, jobs: [] }))
        )
      );
      return results;
    },
    enabled: employees.length > 0 && viewMode === 'schedule',
    staleTime: 2 * 60 * 1000,
  });

  const reviewMutation = useMutation({
    mutationFn: ({ id, status, note }) => reviewTimeOffRequest(id, status, note),
    onSuccess: (response, variables) => {
      queryClient.invalidateQueries({ queryKey: ['company-time-off'] });
      queryClient.invalidateQueries({ queryKey: ['calendar-time-off'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
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

  // Fetch hours for all employees
  useEffect(() => {
    let cancelled = false;
    const fetchHours = async () => {
      try {
        const batch = await getEmployeesHoursThisWeek().catch(() => null);
        if (!cancelled && batch?.data?.hours) {
          const normalized = {};
          for (const [k, v] of Object.entries(batch.data.hours)) {
            const n = Number(k);
            normalized[Number.isNaN(n) ? k : n] = v;
          }
          setEmployeesHours(normalized);
          return;
        }
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
      const employeeJobsToday = (bookings || []).filter(job => {
        if (!job || !job.appointment_time) return false;
        const jobDate = parseServerDate(job.appointment_time);
        const isToday = jobDate.toDateString() === today;
        const assignedIds = job.assigned_employee_ids || [];
        const isAssigned = assignedIds.includes(employee.id) || assignedIds.includes(String(employee.id));
        const isActive = job.status !== 'completed' && job.status !== 'cancelled';
        return isToday && isAssigned && isActive;
      });

      const currentJob = employeeJobsToday.find(job => {
        const jobTime = parseServerDate(job.appointment_time);
        const diffMinutes = (now - jobTime) / (1000 * 60);
        const jobDuration = job.duration_minutes || 120;
        return diffMinutes >= -30 && diffMinutes <= jobDuration;
      });

      const jobsToday = employeeJobsToday.length;
      const nextJob = employeeJobsToday
        .filter(job => parseServerDate(job.appointment_time) > now)
        .sort((a, b) => parseServerDate(a.appointment_time) - parseServerDate(b.appointment_time))[0];

      return {
        ...employee,
        isBusy: !!currentJob,
        currentJob,
        jobsToday,
        nextJob,
        hoursWorked: employeesHours[employee.id] || 0,
        isOnLeave: (timeOffData?.requests || []).some(r => {
          if (r.status !== 'approved' || r.employee_id !== employee.id) return false;
          const todayStr = now.toISOString().split('T')[0];
          return r.start_date <= todayStr && r.end_date >= todayStr;
        })
      };
    });
  }, [employees, bookings, employeesHours, timeOffData]);

  const unreadCounts = useMemo(() => {
    const map = {};
    const counts = unreadData?.counts;
    if (counts && typeof counts === 'object') {
      Object.entries(counts).forEach(([wId, count]) => { map[wId] = count; });
    }
    return map;
  }, [unreadData]);

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

  const stats = useMemo(() => ({
    total: employeesWithStatus.length,
    available: employeesWithStatus.filter(w => !w.isBusy && !w.isOnLeave).length,
    busy: employeesWithStatus.filter(w => w.isBusy).length,
    onLeave: employeesWithStatus.filter(w => w.isOnLeave).length,
  }), [employeesWithStatus]);

  const employeeColorMap = useMemo(() => {
    const map = {};
    (employees || []).forEach((employee, index) => {
      map[employee.id] = EMPLOYEE_COLORS[index % EMPLOYEE_COLORS.length];
    });
    return map;
  }, [employees]);

  // Build schedule grid data: { employeeId: { 'YYYY-MM-DD': [jobs] } }
  const scheduleGrid = useMemo(() => {
    if (!allSchedules) return {};
    const grid = {};
    allSchedules.forEach(({ id, jobs }) => {
      grid[id] = {};
      weekDates.forEach(d => { grid[id][formatDateKey(d)] = []; });
      jobs.forEach(job => {
        if (!job.appointment_time) return;
        const jobDate = parseServerDate(job.appointment_time);
        const key = formatDateKey(jobDate);
        if (grid[id][key]) {
          grid[id][key].push(job);
        }
      });
    });
    return grid;
  }, [allSchedules, weekDates]);

  // Build time-off lookup: { employeeId: Set<'YYYY-MM-DD'> }
  const timeOffByEmployee = useMemo(() => {
    const map = {};
    (timeOffData?.requests || []).forEach(req => {
      if (req.status !== 'approved') return;
      if (!map[req.employee_id]) map[req.employee_id] = new Set();
      const start = new Date(req.start_date);
      const end = new Date(req.end_date);
      for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
        map[req.employee_id].add(formatDateKey(d));
      }
    });
    return map;
  }, [timeOffData]);

  // Build work schedule lookup: { employeeId: { mon: {enabled, start, end}, ... } }
  const workScheduleMap = useMemo(() => {
    const map = {};
    const defaultSched = workSchedulesData?.default_schedule || {};
    (workSchedulesData?.employees || []).forEach(emp => {
      map[emp.id] = emp.work_schedule || defaultSched;
    });
    return map;
  }, [workSchedulesData]);

  // Helper: get shift info for an employee on a given date
  const getShiftForDate = useCallback((employeeId, date) => {
    const ws = workScheduleMap[employeeId];
    if (!ws) return null;
    const dayIndex = (date.getDay() + 6) % 7; // 0=Mon, 6=Sun
    const dayKey = DAY_NAMES[dayIndex].toLowerCase().slice(0, 3);
    const day = ws[dayKey];
    if (!day?.enabled) return null;
    return { start: day.start || '09:00', end: day.end || '17:00' };
  }, [workScheduleMap]);

  // Helper: compute total weekly hours from work schedule
  const getWeeklyHours = useCallback((employeeId) => {
    const ws = workScheduleMap[employeeId];
    if (!ws) return null;
    let total = 0;
    ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'].forEach(d => {
      const day = ws[d];
      if (day?.enabled && day.start && day.end) {
        const [sh, sm] = day.start.split(':').map(Number);
        const [eh, em] = day.end.split(':').map(Number);
        const h = (eh + em / 60) - (sh + sm / 60);
        if (h > 0) total += h;
      }
    });
    return Math.round(total * 10) / 10;
  }, [workScheduleMap]);

  const handleQuickMessage = (e, employee) => {
    e.stopPropagation();
    setMessageEmployeeId(employee.id);
    setMessageEmployeeName(employee.name);
  };

  const isToday = useCallback((date) => {
    const now = new Date();
    return date.toDateString() === now.toDateString();
  }, []);

  const isPast = useCallback((date) => {
    const now = new Date();
    now.setHours(0, 0, 0, 0);
    return date < now;
  }, []);

  const handleDownloadTimetable = async () => {
    try {
      const res = await getAllEmployeeWorkSchedules();
      const data = res.data;
      const emps = data.employees || [];
      if (emps.length === 0) { addToast('No employees to export', 'warning'); return; }
      const days = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];
      const dayLabels = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
      let csv = 'Employee,Specialty,' + dayLabels.join(',') + ',Total Hours\n';
      emps.forEach(emp => {
        const ws = emp.work_schedule || {};
        let total = 0;
        const cells = days.map(d => {
          const day = ws[d];
          if (!day?.enabled) return 'Off';
          const [sh, sm] = (day.start || '09:00').split(':').map(Number);
          const [eh, em] = (day.end || '17:00').split(':').map(Number);
          const h = (eh + em / 60) - (sh + sm / 60);
          total += Math.max(0, h);
          return `${day.start} - ${day.end}`;
        });
        csv += `"${emp.name}","${emp.specialty || ''}",${cells.join(',')},${Math.round(total * 10) / 10}h\n`;
      });
      const blob = new Blob([csv], { type: 'text/csv' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `timetable-${new Date().toISOString().split('T')[0]}.csv`;
      a.click(); URL.revokeObjectURL(url);
      addToast('Timetable downloaded', 'success');
    } catch (err) {
      addToast('Error downloading timetable', 'error');
    }
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
        <div className="employees-header-right">
          {employees.length > 0 && (
            <div className="view-toggle">
              <button
                className={`view-toggle-btn ${viewMode === 'schedule' ? 'active' : ''}`}
                onClick={() => setViewMode('schedule')}
                title="Schedule view"
              >
                <i className="fas fa-calendar-week"></i> Schedule
              </button>
              <button
                className={`view-toggle-btn ${viewMode === 'team' ? 'active' : ''}`}
                onClick={() => setViewMode('team')}
                title="Team view"
              >
                <i className="fas fa-users"></i> Team
              </button>
            </div>
          )}
          <button className="btn-add" onClick={handleAddClick}>
            <i className={`fas ${isSubscriptionActive ? 'fa-plus' : 'fa-lock'}`}></i> Add {terminology.employee}
          </button>
          {employees.length > 0 && (
            <button className="btn-download-timetable" onClick={handleDownloadTimetable} title="Download weekly timetable as CSV">
              <i className="fas fa-download"></i> Timetable
            </button>
          )}
        </div>
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

      {/* ===== SCHEDULE VIEW ===== */}
      {viewMode === 'schedule' && employees.length > 0 && (
        <div className="schedule-view">
          {/* Week Navigation */}
          <div className="schedule-week-nav">
            <button className="week-nav-btn" onClick={() => setWeekOffset(w => w - 1)}>
              <i className="fas fa-chevron-left"></i>
            </button>
            <button
              className="week-nav-label"
              onClick={() => setWeekOffset(0)}
              title="Go to current week"
            >
              <i className="fas fa-calendar-alt"></i> {weekLabel}
            </button>
            <button className="week-nav-btn" onClick={() => setWeekOffset(w => w + 1)}>
              <i className="fas fa-chevron-right"></i>
            </button>
          </div>

          {/* Schedule Grid */}
          <div className="schedule-grid-wrapper">
            <div className="schedule-grid">
              {/* Header row */}
              <div className="sg-header-cell sg-corner">
                <span className="sg-corner-label">{terminology.employee}</span>
              </div>
              {weekDates.map((date, i) => {
                const today = isToday(date);
                const past = isPast(date) && !today;
                return (
                  <div key={i} className={`sg-header-cell ${today ? 'sg-today' : ''} ${past ? 'sg-past' : ''}`}>
                    <span className="sg-day-name">{DAY_NAMES[i]}</span>
                    <span className={`sg-day-num ${today ? 'sg-today-num' : ''}`}>{date.getDate()}</span>
                    <span className="sg-day-month">{date.toLocaleDateString('en-IE', { month: 'short' })}</span>
                  </div>
                );
              })}

              {/* Employee rows */}
              {filteredEmployees.map(employee => {
                const color = employeeColorMap[employee.id] || '#94a3b8';
                const empSchedule = scheduleGrid[employee.id] || {};
                const empTimeOff = timeOffByEmployee[employee.id] || new Set();

                return (
                  <div className="sg-row" key={employee.id}>
                    <div
                      className="sg-employee-cell"
                      onClick={() => setSelectedEmployeeId(employee.id)}
                      style={{ '--emp-color': color }}
                    >
                      <div className="sg-emp-avatar" style={{ background: color }}>
                        {employee.image_url ? (
                          <img src={employee.image_url} alt="" className="sg-emp-avatar-img" />
                        ) : (
                          <span>{employee.name?.charAt(0)?.toUpperCase()}</span>
                        )}
                      </div>
                      <div className="sg-emp-info">
                        <span className="sg-emp-name">{employee.name}</span>
                        {employee.specialty && <span className="sg-emp-role">{employee.specialty}</span>}
                      </div>
                      {getWeeklyHours(employee.id) !== null && (
                        <span className="meta-chip hours" style={{ marginLeft: 'auto', flexShrink: 0 }}>
                          <i className="fas fa-clock"></i>
                          {employee.hoursWorked}h/{getWeeklyHours(employee.id)}h
                        </span>
                      )}
                    </div>

                    {weekDates.map((date, i) => {
                      const dateKey = formatDateKey(date);
                      const dayJobs = empSchedule[dateKey] || [];
                      const onLeave = empTimeOff.has(dateKey);
                      const today = isToday(date);
                      const past = isPast(date) && !today;
                      const shift = getShiftForDate(employee.id, date);
                      const onShift = shift && !onLeave;

                      return (
                        <div
                          key={i}
                          className={`sg-day-cell ${today ? 'sg-today' : ''} ${past ? 'sg-past' : ''} ${onLeave ? 'sg-leave' : ''} ${dayJobs.length > 0 ? 'sg-has-jobs' : ''} ${onShift ? 'sg-on-shift' : ''}`}
                          onClick={() => setDayPopover({ employeeId: employee.id, date, jobs: dayJobs, shift, onLeave, employeeName: employee.name, color })}
                        >
                          {onLeave ? (
                            <div className="sg-leave-badge">
                              <i className="fas fa-umbrella-beach"></i>
                              <span>Off</span>
                            </div>
                          ) : (
                            <>
                              {dayJobs.length > 0 ? (
                                <div className="sg-jobs-stack">
                                  {dayJobs.slice(0, 4).map((job, ji) => (
                                    <div key={ji} className="sg-job-chip" style={{ borderLeftColor: color }}
                                      onClick={(e) => { e.stopPropagation(); setSelectedJobId(job.id); }}>
                                      <span className="sg-job-time">
                                        {parseServerDate(job.appointment_time).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}
                                      </span>
                                      <span className="sg-job-name">{job.service_type || job.client_name || 'Job'}</span>
                                    </div>
                                  ))}
                                  {dayJobs.length > 4 && (
                                    <span className="sg-more-jobs">+{dayJobs.length - 4} more</span>
                                  )}
                                </div>
                              ) : onShift ? (
                                <div className="sg-on-shift-empty">
                                  <span className="sg-shift-hint">{shift.start}–{shift.end}</span>
                                </div>
                              ) : (
                                <div className="sg-empty-cell">
                                  <span className="sg-free-label">—</span>
                                </div>
                              )}
                            </>
                          )}
                        </div>
                      );
                    })}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Schedule Legend */}
          <div className="schedule-legend">
            <span className="legend-item"><span className="legend-dot legend-shift"></span> On Shift</span>
            <span className="legend-item"><span className="legend-dot legend-booked"></span> Has Jobs</span>
            <span className="legend-item"><span className="legend-dot legend-leave"></span> Time Off</span>
            <span className="legend-item"><span className="legend-dot legend-free"></span> Not Scheduled</span>
            <span className="legend-item"><span className="legend-dot legend-today"></span> Today</span>
          </div>
        </div>
      )}

      {/* ===== TEAM VIEW ===== */}
      {viewMode === 'team' && (
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
                          {parseServerDate(employee.nextJob.appointment_time).toLocaleTimeString('en-US', { 
                            hour: 'numeric', 
                            minute: '2-digit' 
                          })}
                        </span>
                      )}
                      {getWeeklyHours(employee.id) !== null && (
                        <span className="meta-chip hours">
                          <i className="fas fa-clock"></i>
                          {employee.hoursWorked}h / {getWeeklyHours(employee.id)}h
                        </span>
                      )}
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
      )}

      {/* Day Popover — Calendar Timeline */}
      {dayPopover && (
        <div className="sg-popover-overlay" onClick={() => setDayPopover(null)}>
          <div className="sg-popover" onClick={(e) => e.stopPropagation()}>
            <div className="sg-popover-header">
              <div>
                <span className="sg-popover-name" style={{ color: dayPopover.color }}>{dayPopover.employeeName}</span>
                <span className="sg-popover-date">
                  {dayPopover.date.toLocaleDateString('en-IE', { weekday: 'long', day: 'numeric', month: 'long' })}
                </span>
              </div>
              <button className="sg-popover-close" onClick={() => setDayPopover(null)}><i className="fas fa-times"></i></button>
            </div>

            {dayPopover.onLeave ? (
              <div className="sg-popover-leave"><i className="fas fa-umbrella-beach"></i> On leave this day</div>
            ) : (
              <div className="sg-popover-timeline">
                {/* Shift indicator */}
                {dayPopover.shift ? (
                  <div className="sg-tl-shift">
                    <div className="sg-tl-shift-bar" style={{ borderColor: dayPopover.color + '40', background: dayPopover.color + '08' }}>
                      <i className="fas fa-clock" style={{ color: dayPopover.color }}></i>
                      <span>Shift: {dayPopover.shift.start} – {dayPopover.shift.end}</span>
                    </div>
                  </div>
                ) : (
                  <div className="sg-tl-no-shift">Not scheduled to work</div>
                )}

                {/* Timeline hours */}
                {(() => {
                  const startH = dayPopover.shift ? parseInt(dayPopover.shift.start) : 8;
                  const endH = dayPopover.shift ? Math.min(parseInt(dayPopover.shift.end) + 1, 24) : 18;
                  const HOUR_HEIGHT = 60; // pixels per hour
                  const totalHeight = (endH - startH) * HOUR_HEIGHT;
                  const hours = [];
                  for (let h = startH; h < endH; h++) hours.push(h);
                  return (
                    <div className="sg-tl-grid" style={{ height: `${totalHeight}px` }}>
                      {hours.map(h => (
                        <div key={h} className="sg-tl-hour" style={{ height: `${HOUR_HEIGHT}px` }}>
                          <span className="sg-tl-hour-label">{h === 0 ? '12 AM' : h < 12 ? `${h} AM` : h === 12 ? '12 PM' : `${h - 12} PM`}</span>
                          <div className="sg-tl-hour-line"></div>
                        </div>
                      ))}

                      {/* Job blocks positioned on timeline */}
                      {dayPopover.jobs.map(job => {
                        const jobTime = parseServerDate(job.appointment_time);
                        const jobH = jobTime.getHours() + jobTime.getMinutes() / 60;
                        const top = Math.max(0, (jobH - startH) * HOUR_HEIGHT);
                        const duration = job.duration_minutes || 60;
                        const height = Math.max(30, (duration / 60) * HOUR_HEIGHT - 4);
                        return (
                          <div
                            key={job.id}
                            className="sg-tl-job"
                            style={{ top: `${top}px`, height: `${height}px`, borderLeftColor: dayPopover.color }}
                            onClick={() => { setDayPopover(null); setSelectedJobId(job.id); }}
                          >
                            <span className="sg-tl-job-time">
                              {jobTime.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}
                            </span>
                            <span className="sg-tl-job-name">{job.service_type || 'Job'}</span>
                            {job.client_name && <span className="sg-tl-job-client">{job.client_name}</span>}
                          </div>
                        );
                      })}
                    </div>
                  );
                })()}

                {dayPopover.jobs.length === 0 && dayPopover.shift && (
                  <p className="sg-tl-empty">No jobs scheduled — available for assignments</p>
                )}
              </div>
            )}

            <div className="sg-popover-actions">
              <button className="btn btn-secondary btn-sm" onClick={() => { setDayPopover(null); setSelectedEmployeeId(dayPopover.employeeId); }}>
                <i className="fas fa-user"></i> Full Profile
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modals */}
      {showAddModal && <AddEmployeeModal 
        isOpen={showAddModal} 
        onClose={() => setShowAddModal(false)} 
      />}
      {!!selectedEmployeeId && <EmployeeDetailModal
        isOpen={!!selectedEmployeeId}
        onClose={() => setSelectedEmployeeId(null)}
        employeeId={selectedEmployeeId}
      />}
      {!!messageEmployeeId && <MessageEmployeeModal
        isOpen={!!messageEmployeeId}
        onClose={() => { setMessageEmployeeId(null); setMessageEmployeeName(''); }}
        employeeId={messageEmployeeId}
        employeeName={messageEmployeeName}
      />}
      {!!selectedJobId && <JobDetailModal
        isOpen={!!selectedJobId}
        onClose={() => setSelectedJobId(null)}
        jobId={selectedJobId}
      />}
    </div>
  );
}

export default EmployeesTab;
