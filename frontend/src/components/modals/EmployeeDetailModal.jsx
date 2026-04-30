import { useState, useMemo, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getEmployee, updateEmployee, deleteEmployee, getEmployeeJobs, getEmployeeHoursThisWeek, inviteEmployee, getEmployeeWorkSchedule, updateEmployeeWorkSchedule } from '../../services/api';
import Modal from './Modal';
import MessageEmployeeModal from './MessageEmployeeModal';
import { useToast } from '../Toast';
import ImageUpload from '../ImageUpload';
import JobDetailModal from './JobDetailModal';
import { formatPhone, getStatusBadgeClass } from '../../utils/helpers';
import { useIndustry } from '../../context/IndustryContext';
import './EmployeeDetailModal.css';

const DAY_KEYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];
const DAY_LABELS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

function EmployeeDetailModal({ isOpen, onClose, employeeId }) {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const { terminology } = useIndustry();
  const [isEditing, setIsEditing] = useState(false);
  const [editData, setEditData] = useState({});
  const [selectedJobId, setSelectedJobId] = useState(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [inviteLink, setInviteLink] = useState(null);
  const [portalStatus, setPortalStatus] = useState(null);
  const [showMessageModal, setShowMessageModal] = useState(false);
  const [detailTab, setDetailTab] = useState('overview'); // 'overview' | 'schedule'
  const [editingSchedule, setEditingSchedule] = useState(null);

  useEffect(() => { setInviteLink(null); setPortalStatus(null); setDetailTab('overview'); setEditingSchedule(null); }, [employeeId]);

  useEffect(() => {
    const handleEscape = (e) => { if (e.key === 'Escape' && showDeleteConfirm) setShowDeleteConfirm(false); };
    if (showDeleteConfirm) document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [showDeleteConfirm]);

  const { data: employee, isLoading: loadingEmployee } = useQuery({
    queryKey: ['employee', employeeId],
    queryFn: async () => { const r = await getEmployee(employeeId); return r.data; },
    enabled: isOpen && !!employeeId, staleTime: 30_000, gcTime: 5 * 60 * 1000,
  });

  useEffect(() => { if (employee?.portal_status) setPortalStatus(employee.portal_status); }, [employee]);

  const { data: employeeJobs } = useQuery({
    queryKey: ['employee-jobs', employeeId],
    queryFn: async () => { const r = await getEmployeeJobs(employeeId); return r.data; },
    enabled: isOpen && !!employeeId, staleTime: 30_000, gcTime: 5 * 60 * 1000,
  });

  const { data: hoursData } = useQuery({
    queryKey: ['employee-hours', employeeId],
    queryFn: async () => { const r = await getEmployeeHoursThisWeek(employeeId); return r.data; },
    enabled: isOpen && !!employeeId, staleTime: 60_000, gcTime: 10 * 60 * 1000,
  });

  // Work schedule
  const { data: workScheduleData } = useQuery({
    queryKey: ['employee-work-schedule', employeeId],
    queryFn: async () => { const r = await getEmployeeWorkSchedule(employeeId); return r.data; },
    enabled: isOpen && !!employeeId, staleTime: 60_000, gcTime: 5 * 60 * 1000,
  });

  useEffect(() => {
    if (workScheduleData?.work_schedule) {
      setEditingSchedule(workScheduleData.work_schedule);
    }
  }, [workScheduleData]);

  const saveScheduleMutation = useMutation({
    mutationFn: (schedule) => updateEmployeeWorkSchedule(employeeId, schedule),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['employee-work-schedule', employeeId] });
      queryClient.invalidateQueries({ queryKey: ['employee-schedules'] });
      queryClient.invalidateQueries({ queryKey: ['employee', employeeId] });
      queryClient.invalidateQueries({ queryKey: ['employee-hours', employeeId] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['all-work-schedules'] });
      addToast('Work schedule saved', 'success');
    },
    onError: (err) => addToast('Error saving schedule: ' + (err.response?.data?.error || err.message), 'error'),
  });

  const updateMutation = useMutation({
    mutationFn: (data) => updateEmployee(employeeId, data),
    onMutate: async (updatedData) => {
      await queryClient.cancelQueries({ queryKey: ['employee', employeeId] });
      const prev = queryClient.getQueryData(['employee', employeeId]);
      queryClient.setQueryData(['employee', employeeId], (old) => ({ ...old, ...updatedData }));
      return { prev };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['employee', employeeId] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      setIsEditing(false);
      addToast('Employee updated successfully!', 'success');
    },
    onError: (error, _, context) => {
      if (context?.prev) queryClient.setQueryData(['employee', employeeId], context.prev);
      addToast('Error updating employee: ' + (error.response?.data?.error || error.message), 'error');
    }
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteEmployee(employeeId),
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: ['dashboard'] });
      const previousDashboard = queryClient.getQueryData(['dashboard']);
      if (previousDashboard) {
        queryClient.setQueryData(['dashboard'], {
          ...previousDashboard,
          employees: (previousDashboard.employees || []).filter(e => e.id !== employeeId),
        });
      }
      return { previousDashboard };
    },
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['employees'] });
      setShowDeleteConfirm(false); onClose();
      const n = response.data?.assignments_removed || 0;
      addToast(`Employee deleted${n > 0 ? ` (removed from ${n} job${n !== 1 ? 's' : ''})` : ''}`, 'success');
    },
    onError: (error, _, context) => {
      if (context?.previousDashboard) queryClient.setQueryData(['dashboard'], context.previousDashboard);
      setShowDeleteConfirm(false); addToast('Error: ' + (error.response?.data?.error || error.message), 'error');
    }
  });

  const inviteMutation = useMutation({
    mutationFn: () => inviteEmployee(employeeId),
    onSuccess: (response) => {
      const data = response.data;
      setInviteLink(data.invite_link); setPortalStatus('invited');
      addToast(data.email_sent ? 'Invite email sent!' : 'Invite link generated.', data.email_sent ? 'success' : 'info');
    },
    onError: (error) => {
      if (error.response?.status === 409) { setPortalStatus('active'); addToast('Already has an active portal account.', 'info'); }
      else addToast('Error: ' + (error.response?.data?.error || error.message), 'error');
    }
  });

  const jobsByPeriod = useMemo(() => {
    const jobs = employeeJobs || [];
    const now = new Date(); const today = now.toDateString();
    const weekFromNow = new Date(); weekFromNow.setDate(weekFromNow.getDate() + 7);
    const todayJobs = jobs.filter(j => new Date(j.appointment_time).toDateString() === today && j.status !== 'cancelled').sort((a, b) => new Date(a.appointment_time) - new Date(b.appointment_time));
    const next7Days = jobs.filter(j => { const d = new Date(j.appointment_time); return d.toDateString() !== today && d > now && d <= weekFromNow && j.status !== 'cancelled'; }).sort((a, b) => new Date(a.appointment_time) - new Date(b.appointment_time));
    return { todayJobs, next7Days, completed: jobs.filter(j => j.status === 'completed').length, total: jobs.length };
  }, [employeeJobs]);

  const handleEditStart = () => {
    setEditData({ name: employee.name || '', phone: employee.phone || '', email: employee.email || '', specialty: employee.specialty || employee.trade_specialty || '', image_url: employee.image_url || '' });
    setIsEditing(true);
  };

  const handleEditSave = () => {
    const d = { ...editData };
    if (!d.name?.trim()) { addToast('Employee name is required', 'warning'); return; }
    updateMutation.mutate(d);
  };

  const handleScheduleDayToggle = (day) => {
    setEditingSchedule(prev => ({ ...prev, [day]: { ...prev[day], enabled: !prev[day]?.enabled } }));
  };

  const handleScheduleTimeChange = (day, field, value) => {
    setEditingSchedule(prev => ({ ...prev, [day]: { ...prev[day], [field]: value } }));
  };

  // Calculate total weekly hours from schedule
  const scheduledWeeklyHours = useMemo(() => {
    if (!editingSchedule) return 0;
    let total = 0;
    DAY_KEYS.forEach(d => {
      const day = editingSchedule[d];
      if (day?.enabled && day.start && day.end) {
        const [sh, sm] = day.start.split(':').map(Number);
        const [eh, em] = day.end.split(':').map(Number);
        total += (eh + em / 60) - (sh + sm / 60);
      }
    });
    return Math.max(0, Math.round(total * 10) / 10);
  }, [editingSchedule]);

  if (loadingEmployee) {
    return (
      <Modal isOpen={isOpen} onClose={onClose} title={`${terminology.employee || 'Employee'} Details`} size="xlarge">
        <div className="modal-loading"><div className="loading-spinner"></div><p>Loading...</p></div>
      </Modal>
    );
  }
  if (!employee) return null;

  const isBusy = jobsByPeriod.todayJobs.some(j => { const now = new Date(); const d = (now - new Date(j.appointment_time)) / 60000; return d >= -30 && d <= 120; });

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`${terminology.employee || 'Employee'} Details`} size="xlarge">
      <div className="employee-detail-modal">
        {/* Header */}
        <div className="employee-modal-header">
          <div className="employee-modal-avatar">
            {employee.image_url ? <img src={employee.image_url} alt={employee.name} /> : <i className="fas fa-hard-hat"></i>}
          </div>
          <div className="employee-modal-info">
            {isEditing ? (
              <div className="edit-header-fields">
                <input type="text" className="form-input name-input" value={editData.name} onChange={(e) => setEditData({...editData, name: e.target.value})} placeholder="Employee Name" />
                <input type="text" className="form-input specialty-input" value={editData.specialty} onChange={(e) => setEditData({...editData, specialty: e.target.value})} placeholder="Specialty (e.g., Plumber)" />
              </div>
            ) : (
              <>
                <h2>{employee.name}</h2>
                {employee.specialty && <span className="specialty-badge"><i className="fas fa-wrench"></i> {employee.specialty}</span>}
              </>
            )}
            <div className="stats-row">
              <div className={`stat-badge ${isBusy ? 'busy' : 'available'}`}><i className={`fas ${isBusy ? 'fa-tools' : 'fa-check'}`}></i><span>{isBusy ? (terminology.statusBusy || 'On Job') : (terminology.statusAvailable || 'Available')}</span></div>
              <div className="stat-badge"><i className="fas fa-briefcase"></i><span>{jobsByPeriod.total} Total</span></div>
              <div className="stat-badge completed"><i className="fas fa-check-circle"></i><span>{jobsByPeriod.completed} Done</span></div>
              <div className="stat-badge hours"><i className="fas fa-clock"></i><span>{hoursData?.hours_worked || 0}h{scheduledWeeklyHours > 0 ? ` / ${scheduledWeeklyHours}h` : ''} this week</span></div>
            </div>
          </div>
          <div className="employee-modal-actions">
            {isEditing ? (
              <>
                <button className="btn btn-secondary" onClick={() => setIsEditing(false)}>Cancel</button>
                <button className="btn btn-primary" onClick={handleEditSave} disabled={updateMutation.isPending}>{updateMutation.isPending ? 'Saving...' : 'Save Changes'}</button>
              </>
            ) : (
              <>
                <button className="btn btn-message-primary" onClick={() => setShowMessageModal(true)}><i className="fas fa-comment-dots"></i> Message</button>
                <button className="btn btn-secondary" onClick={handleEditStart}><i className="fas fa-edit"></i> Edit</button>
                {employee.email && portalStatus !== 'active' && (
                  <button className="btn btn-secondary" onClick={() => inviteMutation.mutate()} disabled={inviteMutation.isPending} title={portalStatus === 'invited' ? 'Resend invite' : 'Invite to portal'}>
                    <i className={`fas ${inviteMutation.isPending ? 'fa-spinner fa-spin' : 'fa-envelope'}`}></i>
                    {inviteMutation.isPending ? 'Sending...' : portalStatus === 'invited' ? 'Resend Invite' : 'Invite to Portal'}
                  </button>
                )}
                {portalStatus === 'active' && <span className="portal-active-badge"><i className="fas fa-check-circle"></i> Portal Active</span>}
                <button className="btn-icon-danger" onClick={() => setShowDeleteConfirm(true)} disabled={deleteMutation.isPending} title="Delete employee"><i className="fas fa-trash"></i></button>
              </>
            )}
          </div>
        </div>

        {inviteLink && (
          <div className="invite-link-banner">
            <i className="fas fa-link"></i>
            <div className="invite-link-content">
              <span className="invite-link-label">Employee invite link:</span>
              <code className="invite-link-url">{inviteLink}</code>
            </div>
            <button className="btn btn-secondary btn-sm" onClick={() => { navigator.clipboard.writeText(inviteLink); addToast('Link copied!', 'success'); }}><i className="fas fa-copy"></i> Copy</button>
          </div>
        )}

        {/* Tab Switcher */}
        <div className="edm-tabs">
          <button className={`edm-tab ${detailTab === 'overview' ? 'active' : ''}`} onClick={() => setDetailTab('overview')}>
            <i className="fas fa-briefcase"></i> Jobs & Info
          </button>
          <button className={`edm-tab ${detailTab === 'schedule' ? 'active' : ''}`} onClick={() => setDetailTab('schedule')}>
            <i className="fas fa-calendar-alt"></i> Work Schedule
          </button>
        </div>

        {/* OVERVIEW TAB */}
        {detailTab === 'overview' && (
          <div className="employee-modal-grid">
            <div className="employee-modal-column">
              <div className="info-card">
                <h3><i className="fas fa-address-card"></i> Contact Information</h3>
                {isEditing ? (
                  <div className="edit-form">
                    <div className="form-row">
                      <div className="form-group"><label>Phone</label><input type="tel" className="form-input" value={editData.phone} onChange={(e) => setEditData({...editData, phone: e.target.value})} placeholder="Phone number" /></div>
                      <div className="form-group"><label>Email</label><input type="email" className="form-input" value={editData.email} onChange={(e) => setEditData({...editData, email: e.target.value})} placeholder="Email address" /></div>
                    </div>
                    <div className="form-group"><label>Profile Picture</label><ImageUpload value={editData.image_url} onChange={(v) => setEditData({...editData, image_url: v})} placeholder="Upload Profile Picture" /></div>
                  </div>
                ) : (
                  <div className="info-row">
                    <div className="info-cell"><span className="info-label">Phone</span><span className="info-value">{employee.phone ? <a href={`tel:${employee.phone}`} className="link">{formatPhone(employee.phone)}</a> : <span className="not-provided">Not provided</span>}</span></div>
                    <div className="info-cell"><span className="info-label">Email</span><span className="info-value">{employee.email ? <a href={`mailto:${employee.email}`} className="link">{employee.email}</a> : <span className="not-provided">Not provided</span>}</span></div>
                  </div>
                )}
              </div>
              <div className="info-card schedule-card">
                <div className="schedule-header today"><h3>Today's Jobs</h3><span className="job-count">{jobsByPeriod.todayJobs.length}</span></div>
                <div className="schedule-list">
                  {jobsByPeriod.todayJobs.length === 0 ? (
                    <div className="empty-schedule"><i className="fas fa-beach"></i><span>No jobs scheduled today</span></div>
                  ) : jobsByPeriod.todayJobs.map(job => {
                    const jobTime = new Date(job.appointment_time); const now = new Date(); const diff = (now - jobTime) / 60000; const isNow = diff >= -30 && diff <= 120;
                    return (
                      <div key={job.id} className={`schedule-item ${isNow ? 'current' : ''}`} onClick={() => setSelectedJobId(job.id)}>
                        <div className="schedule-time">{jobTime.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}{isNow && <span className="now-badge">NOW</span>}</div>
                        <div className="schedule-details"><span className="schedule-customer">{job.customer_name || job.client_name || 'Customer'}</span><span className="schedule-service">{job.service_type || job.service || 'Service'}</span></div>
                        <span className={`badge badge-sm ${getStatusBadgeClass(job.status)}`}>{job.status}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
            <div className="employee-modal-column">
              <div className="info-card schedule-card">
                <div className="schedule-header week"><h3>Next 7 Days</h3><span className="job-count">{jobsByPeriod.next7Days.length}</span></div>
                <div className="schedule-list">
                  {jobsByPeriod.next7Days.length === 0 ? (
                    <div className="empty-schedule"><i className="fas fa-calendar-check"></i><span>No upcoming {(terminology.jobs || 'jobs').toLowerCase()} this week</span></div>
                  ) : jobsByPeriod.next7Days.map(job => {
                    const d = new Date(job.appointment_time);
                    return (
                      <div key={job.id} className="schedule-item upcoming" onClick={() => setSelectedJobId(job.id)}>
                        <div className="schedule-date-box"><span className="day-name">{d.toLocaleDateString('en-US', { weekday: 'short' })}</span><span className="day-num">{d.getDate()}</span></div>
                        <div className="schedule-details">
                          <span className="schedule-customer">{job.customer_name || job.client_name || 'Customer'}</span>
                          <span className="schedule-service">{d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })} • {job.service_type || job.service || 'Service'}</span>
                          {(job.job_address || job.address) && <span className="schedule-location"><i className="fas fa-map-marker-alt"></i>{job.job_address || job.address}</span>}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* WORK SCHEDULE TAB */}
        {detailTab === 'schedule' && (
          <div className="edm-schedule-section">
            <div className="edm-schedule-header">
              <div>
                <h3><i className="fas fa-clock"></i> Default Weekly Schedule</h3>
                <p className="edm-schedule-hint">Set the regular working hours for this employee. Defaults to your business hours.</p>
              </div>
              <div className="edm-schedule-summary">
                <span className="edm-hours-badge"><i className="fas fa-clock"></i> {scheduledWeeklyHours}h / week</span>
              </div>
            </div>

            {editingSchedule ? (
              <div className="edm-schedule-grid">
                {DAY_KEYS.map((day, i) => {
                  const dayData = editingSchedule[day] || { enabled: false, start: '09:00', end: '17:00' };
                  return (
                    <div key={day} className={`edm-schedule-row ${dayData.enabled ? 'active' : 'off'}`}>
                      <div className="edm-day-toggle">
                        <button
                          className={`edm-day-btn ${dayData.enabled ? 'on' : ''}`}
                          onClick={() => handleScheduleDayToggle(day)}
                          aria-label={`Toggle ${DAY_LABELS[i]}`}
                        >
                          <span className="edm-day-label">{DAY_LABELS[i]}</span>
                          <span className={`edm-toggle-switch ${dayData.enabled ? 'on' : ''}`}>
                            <span className="edm-toggle-knob"></span>
                          </span>
                        </button>
                      </div>
                      {dayData.enabled ? (
                        <div className="edm-time-inputs">
                          <div className="edm-time-group">
                            <label>Start</label>
                            <input
                              type="time"
                              value={dayData.start || '09:00'}
                              onChange={(e) => handleScheduleTimeChange(day, 'start', e.target.value)}
                              className="edm-time-input"
                            />
                          </div>
                          <span className="edm-time-sep">to</span>
                          <div className="edm-time-group">
                            <label>End</label>
                            <input
                              type="time"
                              value={dayData.end || '17:00'}
                              onChange={(e) => handleScheduleTimeChange(day, 'end', e.target.value)}
                              className="edm-time-input"
                            />
                          </div>
                          <span className="edm-day-hours">
                            {(() => {
                              const [sh, sm] = (dayData.start || '09:00').split(':').map(Number);
                              const [eh, em] = (dayData.end || '17:00').split(':').map(Number);
                              const h = (eh + em / 60) - (sh + sm / 60);
                              return h > 0 ? `${Math.round(h * 10) / 10}h` : '—';
                            })()}
                          </span>
                        </div>
                      ) : (
                        <div className="edm-day-off-label">Day off</div>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="edm-schedule-loading"><i className="fas fa-spinner fa-spin"></i> Loading schedule...</div>
            )}

            <div className="edm-schedule-actions">
              <button
                className="btn btn-primary"
                onClick={() => saveScheduleMutation.mutate(editingSchedule)}
                disabled={saveScheduleMutation.isPending || !editingSchedule}
              >
                <i className={`fas ${saveScheduleMutation.isPending ? 'fa-spinner fa-spin' : 'fa-save'}`}></i>
                {saveScheduleMutation.isPending ? 'Saving...' : 'Save Schedule'}
              </button>
            </div>
          </div>
        )}
      </div>

      <JobDetailModal isOpen={!!selectedJobId} onClose={() => setSelectedJobId(null)} jobId={selectedJobId} />

      {showDeleteConfirm && (
        <div className="delete-confirm-overlay">
          <div className="delete-confirm-dialog">
            <div className="delete-confirm-icon"><i className="fas fa-exclamation-triangle"></i></div>
            <h3>Delete Employee?</h3>
            <p className="delete-warning">This will permanently delete <strong>{employee.name}</strong>.</p>
            {jobsByPeriod.total > 0 && <p className="delete-cascade-warning"><i className="fas fa-exclamation-circle"></i>Employee will be removed from <strong>{jobsByPeriod.total} job assignment{jobsByPeriod.total !== 1 ? 's' : ''}</strong>.</p>}
            <div className="delete-confirm-actions">
              <button className="btn btn-secondary" onClick={() => setShowDeleteConfirm(false)}>Cancel</button>
              <button className="btn btn-danger" onClick={() => deleteMutation.mutate()} disabled={deleteMutation.isPending}>{deleteMutation.isPending ? 'Deleting...' : 'Delete Employee'}</button>
            </div>
          </div>
        </div>
      )}
      <MessageEmployeeModal isOpen={showMessageModal} onClose={() => setShowMessageModal(false)} employeeId={employeeId} employeeName={employee?.name} />
    </Modal>
  );
}

export default EmployeeDetailModal;
