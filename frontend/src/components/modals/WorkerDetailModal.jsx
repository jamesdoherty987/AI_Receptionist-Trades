import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getWorker, updateWorker, deleteWorker, getWorkerJobs, getWorkerHoursThisWeek } from '../../services/api';
import Modal from './Modal';
import { useToast } from '../Toast';
import ImageUpload from '../ImageUpload';
import JobDetailModal from './JobDetailModal';
import { formatPhone, getStatusBadgeClass } from '../../utils/helpers';
import './WorkerDetailModal.css';

function WorkerDetailModal({ isOpen, onClose, workerId }) {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [isEditing, setIsEditing] = useState(false);
  const [editData, setEditData] = useState({});
  const [selectedJobId, setSelectedJobId] = useState(null);

  const { data: worker, isLoading: loadingWorker } = useQuery({
    queryKey: ['worker', workerId],
    queryFn: async () => {
      const response = await getWorker(workerId);
      return response.data;
    },
    enabled: isOpen && !!workerId
  });

  const { data: workerJobs } = useQuery({
    queryKey: ['worker-jobs', workerId],
    queryFn: async () => {
      const response = await getWorkerJobs(workerId);
      return response.data;
    },
    enabled: isOpen && !!workerId
  });

  const { data: hoursData } = useQuery({
    queryKey: ['worker-hours', workerId],
    queryFn: async () => {
      const response = await getWorkerHoursThisWeek(workerId);
      return response.data;
    },
    enabled: isOpen && !!workerId
  });

  const updateMutation = useMutation({
    mutationFn: (data) => updateWorker(workerId, data),
    onSuccess: () => {
      queryClient.invalidateQueries(['worker', workerId]);
      queryClient.invalidateQueries(['workers']);
      setIsEditing(false);
      addToast('Worker updated successfully!', 'success');
    },
    onError: (error) => {
      addToast('Error updating worker: ' + (error.response?.data?.error || error.message), 'error');
    }
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteWorker(workerId),
    onSuccess: () => {
      queryClient.invalidateQueries(['workers']);
      onClose();
      addToast('Worker deleted', 'success');
    },
    onError: (error) => {
      addToast('Error deleting worker', 'error');
    }
  });

  // Group jobs by time period
  const jobsByPeriod = useMemo(() => {
    const jobs = workerJobs || [];
    const now = new Date();
    const today = now.toDateString();
    const weekFromNow = new Date();
    weekFromNow.setDate(weekFromNow.getDate() + 7);

    const todayJobs = jobs.filter(job => {
      const jobDate = new Date(job.appointment_time);
      return jobDate.toDateString() === today && job.status !== 'completed' && job.status !== 'cancelled';
    }).sort((a, b) => new Date(a.appointment_time) - new Date(b.appointment_time));

    const next7Days = jobs.filter(job => {
      const jobDate = new Date(job.appointment_time);
      const isAfterToday = jobDate.toDateString() !== today && jobDate > now;
      const isWithinWeek = jobDate <= weekFromNow;
      return isAfterToday && isWithinWeek && job.status !== 'completed' && job.status !== 'cancelled';
    }).sort((a, b) => new Date(a.appointment_time) - new Date(b.appointment_time));

    const completed = jobs.filter(j => j.status === 'completed').length;
    const total = jobs.length;

    return { todayJobs, next7Days, completed, total };
  }, [workerJobs]);

  const handleEditStart = () => {
    setEditData({
      name: worker.name || '',
      phone: worker.phone || '',
      email: worker.email || '',
      specialty: worker.specialty || worker.trade_specialty || '',
      image_url: worker.image_url || '',
      weekly_hours_expected: worker.weekly_hours_expected || 40.0
    });
    setIsEditing(true);
  };

  const handleEditSave = () => {
    updateMutation.mutate(editData);
  };

  const handleDelete = () => {
    if (window.confirm(`Delete ${worker.name}? This cannot be undone.`)) {
      deleteMutation.mutate();
    }
  };

  if (loadingWorker) {
    return (
      <Modal isOpen={isOpen} onClose={onClose} title="Worker Details" size="xlarge">
        <div className="modal-loading">
          <div className="loading-spinner"></div>
          <p>Loading worker details...</p>
        </div>
      </Modal>
    );
  }

  if (!worker) return null;

  const isBusy = jobsByPeriod.todayJobs.some(job => {
    const now = new Date();
    const jobTime = new Date(job.appointment_time);
    const diffMinutes = (now - jobTime) / (1000 * 60);
    return diffMinutes >= -30 && diffMinutes <= 120;
  });

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Worker Details" size="xlarge">
      <div className="worker-detail-modal">
        {/* Header */}
        <div className="worker-modal-header">
          <div className="worker-modal-avatar">
            {worker.image_url ? (
              <img src={worker.image_url} alt={worker.name} />
            ) : (
              <i className="fas fa-hard-hat"></i>
            )}
          </div>
          <div className="worker-modal-info">
            {isEditing ? (
              <div className="edit-header-fields">
                <input
                  type="text"
                  className="form-input name-input"
                  value={editData.name}
                  onChange={(e) => setEditData({...editData, name: e.target.value})}
                  placeholder="Worker Name"
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
                <h2>{worker.name}</h2>
                {worker.specialty && (
                  <span className="specialty-badge">
                    <i className="fas fa-wrench"></i> {worker.specialty}
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
                  {hoursData?.hours_worked || 0}h / {worker.weekly_hours_expected || 40}h this week
                </span>
              </div>
            </div>
          </div>
          <div className="worker-modal-actions">
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
                <button className="btn btn-secondary" onClick={handleEditStart}>
                  <i className="fas fa-edit"></i> Edit
                </button>
                <button 
                  className="btn btn-danger"
                  onClick={handleDelete}
                  disabled={deleteMutation.isPending}
                >
                  <i className="fas fa-trash"></i> Delete
                </button>
              </>
            )}
          </div>
        </div>

        {/* Content Grid */}
        <div className="worker-modal-grid">
          {/* Left Column - Contact & Today */}
          <div className="worker-modal-column">
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
                      value={editData.weekly_hours_expected}
                      onChange={(e) => setEditData({...editData, weekly_hours_expected: parseFloat(e.target.value) || 40.0})}
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
                      {worker.phone ? (
                        <a href={`tel:${worker.phone}`} className="link">{formatPhone(worker.phone)}</a>
                      ) : <span className="not-provided">Not provided</span>}
                    </span>
                  </div>
                  <div className="info-cell">
                    <span className="info-label">Email</span>
                    <span className="info-value">
                      {worker.email ? (
                        <a href={`mailto:${worker.email}`} className="link">{worker.email}</a>
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
                          <span className="schedule-customer">{job.customer_name || 'Customer'}</span>
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
          <div className="worker-modal-column">
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
                          <span className="schedule-customer">{job.customer_name || 'Customer'}</span>
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
    </Modal>
  );
}

export default WorkerDetailModal;
