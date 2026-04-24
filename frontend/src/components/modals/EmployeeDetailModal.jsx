import { useState, useMemo, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getEmployee, updateEmployee, deleteEmployee, getEmployeeJobs, getEmployeeHoursThisWeek, inviteEmployee } from '../../services/api';
import Modal from './Modal';
import MessageEmployeeModal from './MessageEmployeeModal';
import { useToast } from '../Toast';
import ImageUpload from '../ImageUpload';
import JobDetailModal from './JobDetailModal';
import { formatPhone, getStatusBadgeClass } from '../../utils/helpers';
import './EmployeeDetailModal.css';

function EmployeeDetailModal({ isOpen, onClose, employeeId }) {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [isEditing, setIsEditing] = useState(false);
  const [editData, setEditData] = useState({});
  const [selectedJobId, setSelectedJobId] = useState(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [inviteLink, setInviteLink] = useState(null);
  const [portalStatus, setPortalStatus] = useState(null); // null | 'invited' | 'active'
  const [showMessageModal, setShowMessageModal] = useState(false);

  // Reset invite state when switching employees
  useEffect(() => {
    setInviteLink(null);
    setPortalStatus(null);
  }, [employeeId]);

  // Handle escape key to close delete confirmation
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && showDeleteConfirm) {
        setShowDeleteConfirm(false);
      }
    };
    if (showDeleteConfirm) {
      document.addEventListener('keydown', handleEscape);
    }
    return () => document.removeEventListener('keydown', handleEscape);
  }, [showDeleteConfirm]);

  const { data: employee, isLoading: loadingEmployee } = useQuery({
    queryKey: ['employee', employeeId],
    queryFn: async () => {
      const response = await getEmployee(employeeId);
      return response.data;
    },
    enabled: isOpen && !!employeeId,
    gcTime: 5 * 60 * 1000 // 5 minutes
  });

  // Sync portal status from employee data (must be after employee useQuery)
  useEffect(() => {
    if (employee?.portal_status) {
      setPortalStatus(employee.portal_status);
    }
  }, [employee]);

  const { data: employeeJobs } = useQuery({
    queryKey: ['employee-jobs', employeeId],
    queryFn: async () => {
      const response = await getEmployeeJobs(employeeId);
      return response.data;
    },
    enabled: isOpen && !!employeeId,
    gcTime: 5 * 60 * 1000 // 5 minutes
  });

  const { data: hoursData } = useQuery({
    queryKey: ['employee-hours', employeeId],
    queryFn: async () => {
      const response = await getEmployeeHoursThisWeek(employeeId);
      return response.data;
    },
    enabled: isOpen && !!employeeId,
    gcTime: 10 * 60 * 1000 // 10 minutes
  });

  const updateMutation = useMutation({
    mutationFn: (data) => updateEmployee(employeeId, data),
    onMutate: async (updatedData) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['employee', employeeId] });
      
      // Snapshot previous value
      const previousEmployee = queryClient.getQueryData(['employee', employeeId]);
      
      // Optimistically update
      queryClient.setQueryData(['employee', employeeId], (old) => ({
        ...old,
        ...updatedData
      }));
      
      return { previousEmployee };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['employee', employeeId] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      setIsEditing(false);
      addToast('Employee updated successfully!', 'success');
    },
    onError: (error, variables, context) => {
      // Rollback on error
      if (context?.previousEmployee) {
        queryClient.setQueryData(['employee', employeeId], context.previousEmployee);
      }
      addToast('Error updating employee: ' + (error.response?.data?.error || error.message), 'error');
    }
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteEmployee(employeeId),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['employees'] });
      setShowDeleteConfirm(false);
      onClose();
      const assignmentsRemoved = response.data?.assignments_removed || 0;
      addToast(`Employee deleted${assignmentsRemoved > 0 ? ` (removed from ${assignmentsRemoved} job${assignmentsRemoved !== 1 ? 's' : ''})` : ''}`, 'success');
    },
    onError: (error) => {
      setShowDeleteConfirm(false);
      addToast('Error deleting employee: ' + (error.response?.data?.error || error.message), 'error');
    }
  });

  const inviteMutation = useMutation({
    mutationFn: () => inviteEmployee(employeeId),
    onSuccess: (response) => {
      const data = response.data;
      setInviteLink(data.invite_link);
      setPortalStatus('invited');
      if (data.email_sent) {
        addToast('Invite email sent to employee!', 'success');
      } else {
        addToast('Invite link generated. Share it with the employee.', 'info');
      }
    },
    onError: (error) => {
      if (error.response?.status === 409) {
        setPortalStatus('active');
        addToast('This employee already has an active portal account.', 'info');
      } else {
        addToast('Error inviting employee: ' + (error.response?.data?.error || error.message), 'error');
      }
    }
  });

  // Group jobs by time period
  const jobsByPeriod = useMemo(() => {
    const jobs = employeeJobs || [];
    const now = new Date();
    const today = now.toDateString();
    const weekFromNow = new Date();
    weekFromNow.setDate(weekFromNow.getDate() + 7);

    const todayJobs = jobs.filter(job => {
      const jobDate = new Date(job.appointment_time);
      return jobDate.toDateString() === today && job.status !== 'cancelled';
    }).sort((a, b) => new Date(a.appointment_time) - new Date(b.appointment_time));

    const next7Days = jobs.filter(job => {
      const jobDate = new Date(job.appointment_time);
      const isAfterToday = jobDate.toDateString() !== today && jobDate > now;
      const isWithinWeek = jobDate <= weekFromNow;
      return isAfterToday && isWithinWeek && job.status !== 'cancelled';
    }).sort((a, b) => new Date(a.appointment_time) - new Date(b.appointment_time));

    const completed = jobs.filter(j => j.status === 'completed').length;
    const total = jobs.length;

    return { todayJobs, next7Days, completed, total };
  }, [employeeJobs]);

  const handleEditStart = () => {
    setEditData({
      name: employee.name || '',
      phone: employee.phone || '',
      email: employee.email || '',
      specialty: employee.specialty || employee.trade_specialty || '',
      image_url: employee.image_url || '',
      weekly_hours_expected: employee.weekly_hours_expected || 40.0
    });
    setIsEditing(true);
  };

  const handleEditSave = () => {
    // Validate data before saving
    const dataToSave = {
      ...editData,
      weekly_hours_expected: editData.weekly_hours_expected || 40.0
    };
    
    if (!dataToSave.name || dataToSave.name.trim() === '') {
      addToast('Employee name is required', 'warning');
      return;
    }
    
    updateMutation.mutate(dataToSave);
  };

  const handleDelete = () => {
    setShowDeleteConfirm(true);
  };

  const confirmDelete = () => {
    deleteMutation.mutate();
  };

  if (loadingEmployee) {
    return (
      <Modal isOpen={isOpen} onClose={onClose} title="Employee Details" size="xlarge">
        <div className="modal-loading">
          <div className="loading-spinner"></div>
          <p>Loading employee details...</p>
        </div>
      </Modal>
    );
  }

  if (!employee) return null;

  const isBusy = jobsByPeriod.todayJobs.some(job => {
    const now = new Date();
    const jobTime = new Date(job.appointment_time);
    const diffMinutes = (now - jobTime) / (1000 * 60);
    return diffMinutes >= -30 && diffMinutes <= 120;
  });

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Employee Details" size="xlarge">
      <div className="employee-detail-modal">
        {/* Header */}
        <div className="employee-modal-header">
          <div className="employee-modal-avatar">
            {employee.image_url ? (
              <img src={employee.image_url} alt={employee.name} />
            ) : (
              <i className="fas fa-hard-hat"></i>
            )}
          </div>
          <div className="employee-modal-info">
            {isEditing ? (
              <div className="edit-header-fields">
                <input
                  type="text"
                  className="form-input name-input"
                  value={editData.name}
                  onChange={(e) => setEditData({...editData, name: e.target.value})}
                  placeholder="Employee Name"
                />
                <input
                  type="text"
                  className="form-input specialty-input"
                  value={editData.specialty}
                  onChange={(e) => setEditData({...editData, specialty: e.target.value})}
                  placeholder="Trade Specialty (e.g., Plumber)"
                />
              </div>
            ) : (
              <>
                <h2>{employee.name}</h2>
                {employee.specialty && (
                  <span className="specialty-badge">
                    <i className="fas fa-wrench"></i> {employee.specialty}
                  </span>
                )}
              </>
            )}
            <div className="stats-row">
              <div className={`stat-badge ${isBusy ? 'busy' : 'available'}`}>
                <i className={`fas ${isBusy ? 'fa-tools' : 'fa-check'}`}></i>
                <span>{isBusy ? 'On Job' : 'Available'}</span>
              </div>
              <div className="stat-badge">
                <i className="fas fa-briefcase"></i>
                <span>{jobsByPeriod.total} Total</span>
              </div>
              <div className="stat-badge completed">
                <i className="fas fa-check-circle"></i>
                <span>{jobsByPeriod.completed} Done</span>
              </div>
              <div className="stat-badge hours">
                <i className="fas fa-clock"></i>
                <span>
                  {hoursData?.hours_worked || 0}h / {employee.weekly_hours_expected || 40}h this week
                </span>
              </div>
            </div>
          </div>
          <div className="employee-modal-actions">
            {isEditing ? (
              <>
                <button className="btn btn-secondary" onClick={() => setIsEditing(false)}>Cancel</button>
                <button 
                  className="btn btn-primary"
                  onClick={handleEditSave}
                  disabled={updateMutation.isPending}
                >
                  {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
                </button>
              </>
            ) : (
              <>
                <button className="btn btn-message-primary" onClick={() => setShowMessageModal(true)}>
                  <i className="fas fa-comment-dots"></i> Message
                </button>
                <button className="btn btn-secondary" onClick={handleEditStart}>
                  <i className="fas fa-edit"></i> Edit
                </button>
                {employee.email && portalStatus !== 'active' && (
                  <button 
                    className="btn btn-secondary"
                    onClick={() => inviteMutation.mutate()}
                    disabled={inviteMutation.isPending}
                    title={portalStatus === 'invited' ? 'Resend invite email' : 'Invite employee to their own portal'}
                  >
                    <i className={`fas ${inviteMutation.isPending ? 'fa-spinner fa-spin' : 'fa-envelope'}`}></i>
                    {inviteMutation.isPending ? 'Sending...' : portalStatus === 'invited' ? 'Resend Invite' : 'Invite to Portal'}
                  </button>
                )}
                {portalStatus === 'active' && (
                  <span className="portal-active-badge" title="Employee has an active portal account">
                    <i className="fas fa-check-circle"></i> Portal Active
                  </span>
                )}
                <button 
                  className="btn-icon-danger"
                  onClick={handleDelete}
                  disabled={deleteMutation.isPending}
                  title="Delete employee"
                >
                  <i className="fas fa-trash"></i>
                </button>
              </>
            )}
          </div>
        </div>

        {/* Invite Link Display */}
        {inviteLink && (
          <div className="invite-link-banner">
            <i className="fas fa-link"></i>
            <div className="invite-link-content">
              <span className="invite-link-label">Employee invite link:</span>
              <code className="invite-link-url">{inviteLink}</code>
            </div>
            <button 
              className="btn btn-secondary btn-sm"
              onClick={() => {
                navigator.clipboard.writeText(inviteLink);
                addToast('Link copied to clipboard!', 'success');
              }}
            >
              <i className="fas fa-copy"></i> Copy
            </button>
          </div>
        )}

        {/* Content Grid */}
        <div className="employee-modal-grid">
          {/* Left Column - Contact & Today */}
          <div className="employee-modal-column">
            {/* Contact Info */}
            <div className="info-card">
              <h3><i className="fas fa-address-card"></i> Contact Information</h3>
              {isEditing ? (
                <div className="edit-form">
                  <div className="form-row">
                    <div className="form-group">
                      <label>Phone</label>
                      <input
                        type="tel"
                        className="form-input"
                        value={editData.phone}
                        onChange={(e) => setEditData({...editData, phone: e.target.value})}
                        placeholder="Phone number"
                      />
                    </div>
                    <div className="form-group">
                      <label>Email</label>
                      <input
                        type="email"
                        className="form-input"
                        value={editData.email}
                        onChange={(e) => setEditData({...editData, email: e.target.value})}
                        placeholder="Email address"
                      />
                    </div>
                  </div>
                  <div className="form-group">
                    <label>Profile Picture</label>
                    <ImageUpload
                      value={editData.image_url}
                      onChange={(value) => setEditData({...editData, image_url: value})}
                      placeholder="Upload Profile Picture"
                    />
                  </div>
                  <div className="form-group">
                    <label>Expected Weekly Hours</label>
                    <input
                      type="number"
                      className="form-input"
                      value={editData.weekly_hours_expected || ''}
                      onChange={(e) => {
                        const value = e.target.value;
                        if (value === '') {
                          setEditData({...editData, weekly_hours_expected: ''});
                        } else {
                          const numValue = parseFloat(value);
                          if (!isNaN(numValue) && numValue >= 0 && numValue <= 168) {
                            setEditData({...editData, weekly_hours_expected: numValue});
                          }
                        }
                      }}
                      onBlur={(e) => {
                        // Set default of 40 if empty on blur
                        if (e.target.value === '') {
                          setEditData({...editData, weekly_hours_expected: 40.0});
                        }
                      }}
                      placeholder="40"
                      min="0"
                      max="168"
                      step="0.5"
                    />
                  </div>
                </div>
              ) : (
                <div className="info-row">
                  <div className="info-cell">
                    <span className="info-label">Phone</span>
                    <span className="info-value">
                      {employee.phone ? (
                        <a href={`tel:${employee.phone}`} className="link">{formatPhone(employee.phone)}</a>
                      ) : <span className="not-provided">Not provided</span>}
                    </span>
                  </div>
                  <div className="info-cell">
                    <span className="info-label">Email</span>
                    <span className="info-value">
                      {employee.email ? (
                        <a href={`mailto:${employee.email}`} className="link">{employee.email}</a>
                      ) : <span className="not-provided">Not provided</span>}
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Today's Jobs */}
            <div className="info-card schedule-card">
              <div className="schedule-header today">
                <h3>Today's Jobs</h3>
                <span className="job-count">{jobsByPeriod.todayJobs.length}</span>
              </div>
              <div className="schedule-list">
                {jobsByPeriod.todayJobs.length === 0 ? (
                  <div className="empty-schedule">
                    <i className="fas fa-beach"></i>
                    <span>No jobs scheduled today</span>
                  </div>
                ) : (
                  jobsByPeriod.todayJobs.map(job => {
                    const jobTime = new Date(job.appointment_time);
                    const now = new Date();
                    const diffMinutes = (now - jobTime) / (1000 * 60);
                    const isNow = diffMinutes >= -30 && diffMinutes <= 120;
                    
                    return (
                      <div 
                        key={job.id} 
                        className={`schedule-item ${isNow ? 'current' : ''}`}
                        onClick={() => setSelectedJobId(job.id)}
                      >
                        <div className="schedule-time">
                          {jobTime.toLocaleTimeString('en-US', { 
                            hour: '2-digit', 
                            minute: '2-digit' 
                          })}
                          {isNow && <span className="now-badge">NOW</span>}
                        </div>
                        <div className="schedule-details">
                          <span className="schedule-customer">{job.customer_name || job.client_name || 'Customer'}</span>
                          <span className="schedule-service">{job.service_type || job.service || 'Service'}</span>
                        </div>
                        <span className={`badge badge-sm ${getStatusBadgeClass(job.status)}`}>
                          {job.status}
                        </span>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </div>

          {/* Right Column - Next 7 Days */}
          <div className="employee-modal-column">
            <div className="info-card schedule-card">
              <div className="schedule-header week">
                <h3>Next 7 Days</h3>
                <span className="job-count">{jobsByPeriod.next7Days.length}</span>
              </div>
              <div className="schedule-list">
                {jobsByPeriod.next7Days.length === 0 ? (
                  <div className="empty-schedule">
                    <i className="fas fa-calendar-check"></i>
                    <span>No upcoming jobs this week</span>
                  </div>
                ) : (
                  jobsByPeriod.next7Days.map(job => {
                    const jobDate = new Date(job.appointment_time);
                    const dayName = jobDate.toLocaleDateString('en-US', { weekday: 'short' });
                    const dayNum = jobDate.getDate();
                    
                    return (
                      <div 
                        key={job.id} 
                        className="schedule-item upcoming"
                        onClick={() => setSelectedJobId(job.id)}
                      >
                        <div className="schedule-date-box">
                          <span className="day-name">{dayName}</span>
                          <span className="day-num">{dayNum}</span>
                        </div>
                        <div className="schedule-details">
                          <span className="schedule-customer">{job.customer_name || job.client_name || 'Customer'}</span>
                          <span className="schedule-service">
                            {jobDate.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}
                            {' • '}
                            {job.service_type || job.service || 'Service'}
                          </span>
                          {(job.job_address || job.address) && (
                            <span className="schedule-location">
                              <i className="fas fa-map-marker-alt"></i>
                              {job.job_address || job.address}
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Job Detail Modal */}
      <JobDetailModal
        isOpen={!!selectedJobId}
        onClose={() => setSelectedJobId(null)}
        jobId={selectedJobId}
      />

      {/* Delete Confirmation */}
      {showDeleteConfirm && (
        <div className="delete-confirm-overlay">
          <div className="delete-confirm-dialog">
            <div className="delete-confirm-icon">
              <i className="fas fa-exclamation-triangle"></i>
            </div>
            <h3>Delete Employee?</h3>
            <p className="delete-warning">
              This will permanently delete <strong>{employee.name}</strong>.
            </p>
            {jobsByPeriod.total > 0 && (
              <p className="delete-cascade-warning">
                <i className="fas fa-exclamation-circle"></i>
                Employee will be removed from <strong>{jobsByPeriod.total} job assignment{jobsByPeriod.total !== 1 ? 's' : ''}</strong>.
              </p>
            )}
            <div className="delete-confirm-actions">
              <button className="btn btn-secondary" onClick={() => setShowDeleteConfirm(false)}>
                Cancel
              </button>
              <button 
                className="btn btn-danger" 
                onClick={confirmDelete}
                disabled={deleteMutation.isPending}
              >
                {deleteMutation.isPending ? 'Deleting...' : 'Delete Employee'}
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Message Employee Modal */}
      <MessageEmployeeModal
        isOpen={showMessageModal}
        onClose={() => setShowMessageModal(false)}
        employeeId={employeeId}
        employeeName={employee?.name}
      />
    </Modal>
  );
}

export default EmployeeDetailModal;
