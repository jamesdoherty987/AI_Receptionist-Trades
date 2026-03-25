import { useState, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../context/AuthContext';
import { Link, useNavigate } from 'react-router-dom';
import {
  getWorkerDashboard,
  getWorkerJobDetail,
  workerUploadJobPhoto,
  workerUploadJobMedia,
  workerUpdateJobStatus,
  getWorkerTimeOff,
  createTimeOffRequest,
  deleteTimeOffRequest,
  workerChangePassword,
  getWorkerHoursSummary,
  addWorkerJobNote,
  updateWorkerProfile
} from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';
import ImageUpload from '../components/ImageUpload';
import { formatPhone, getStatusBadgeClass, formatDateTime, getProxiedMediaUrl } from '../utils/helpers';
import { formatDuration } from '../utils/durationOptions';
import './WorkerDashboard.css';

function WorkerDashboard() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState('jobs');
  const [selectedJobId, setSelectedJobId] = useState(null);
  const [lightboxPhoto, setLightboxPhoto] = useState(null);
  const [uploadingPhoto, setUploadingPhoto] = useState(false);
  const photoInputRef = useRef(null);

  // Time-off form state
  const [showTimeOffForm, setShowTimeOffForm] = useState(false);
  const [timeOffForm, setTimeOffForm] = useState({
    start_date: '', end_date: '', reason: '', type: 'vacation'
  });

  // Change password state
  const [showChangePassword, setShowChangePassword] = useState(false);
  const [passwordForm, setPasswordForm] = useState({
    current_password: '', new_password: '', confirm_password: ''
  });
  const [passwordError, setPasswordError] = useState('');
  const [passwordSuccess, setPasswordSuccess] = useState('');

  // Job note state
  const [noteText, setNoteText] = useState('');

  // Profile editing state
  const [isEditingProfile, setIsEditingProfile] = useState(false);
  const [profileForm, setProfileForm] = useState({ phone: '', image_url: '' });

  // Job history state
  const [showAllCompleted, setShowAllCompleted] = useState(false);
  const [showAllHistory, setShowAllHistory] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ['worker-dashboard'],
    queryFn: async () => { const r = await getWorkerDashboard(); return r.data; },
  });

  const { data: hoursSummary } = useQuery({
    queryKey: ['worker-hours-summary'],
    queryFn: async () => { const r = await getWorkerHoursSummary(); return r.data; },
  });

  const { data: selectedJob, isLoading: loadingJob } = useQuery({
    queryKey: ['worker-job', selectedJobId],
    queryFn: async () => { const r = await getWorkerJobDetail(selectedJobId); return r.data; },
    enabled: !!selectedJobId,
  });

  const { data: timeOffData } = useQuery({
    queryKey: ['worker-time-off'],
    queryFn: async () => { const r = await getWorkerTimeOff(); return r.data; },
    enabled: activeTab === 'hr',
  });

  const statusMutation = useMutation({
    mutationFn: ({ jobId, status }) => workerUpdateJobStatus(jobId, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['worker-dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['worker-job', selectedJobId] });
    },
  });

  const photoMutation = useMutation({
    mutationFn: (data) => {
      // data is either a base64 string (image) or a File object (video)
      if (typeof data === 'string') {
        return workerUploadJobPhoto(selectedJobId, data);
      }
      return workerUploadJobMedia(selectedJobId, data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['worker-job', selectedJobId] });
      setUploadingPhoto(false);
    },
    onError: () => { setUploadingPhoto(false); },
  });

  const timeOffMutation = useMutation({
    mutationFn: (data) => createTimeOffRequest(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['worker-time-off'] });
      setShowTimeOffForm(false);
      setTimeOffForm({ start_date: '', end_date: '', reason: '', type: 'vacation' });
    },
  });

  const deleteTimeOffMutation = useMutation({
    mutationFn: (id) => deleteTimeOffRequest(id),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['worker-time-off'] }); },
  });

  const passwordMutation = useMutation({
    mutationFn: ({ current_password, new_password }) =>
      workerChangePassword(current_password, new_password),
    onSuccess: () => {
      setPasswordSuccess('Password changed successfully');
      setPasswordError('');
      setPasswordForm({ current_password: '', new_password: '', confirm_password: '' });
      setTimeout(() => setPasswordSuccess(''), 3000);
    },
    onError: (err) => {
      setPasswordError(err.response?.data?.error || 'Failed to change password');
    },
  });

  const noteMutation = useMutation({
    mutationFn: ({ jobId, note }) => addWorkerJobNote(jobId, note),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['worker-job', selectedJobId] });
      setNoteText('');
    },
  });

  const profileMutation = useMutation({
    mutationFn: (data) => updateWorkerProfile(data),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['worker-dashboard'] });
      setIsEditingProfile(false);
    },
  });

  const handleLogout = async () => { await logout(); navigate('/worker/login'); };

  const handlePhotoSelect = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const isVideo = file.type.startsWith('video/');
    const isImage = file.type.startsWith('image/');

    if (!isImage && !isVideo) return;

    const maxSize = isVideo ? 50 * 1024 * 1024 : 10 * 1024 * 1024;
    if (file.size > maxSize) return;

    setUploadingPhoto(true);

    if (isVideo) {
      // Upload video as raw file via FormData
      photoMutation.mutate(file);
    } else {
      // Compress image before uploading
      const canvas = document.createElement('canvas');
      const img = new Image();
      const reader = new FileReader();
      reader.onload = (ev) => {
        img.onload = () => {
          let w = img.width, h = img.height;
          if (w > 1200) { h = (h * 1200) / w; w = 1200; }
          canvas.width = w; canvas.height = h;
          canvas.getContext('2d').drawImage(img, 0, 0, w, h);
          const result = canvas.toDataURL('image/jpeg', 0.8);
          photoMutation.mutate(result);
        };
        img.src = ev.target.result;
      };
      reader.readAsDataURL(file);
    }

    if (photoInputRef.current) photoInputRef.current.value = '';
  };

  const handlePasswordSubmit = (e) => {
    e.preventDefault();
    setPasswordError('');
    if (passwordForm.new_password !== passwordForm.confirm_password) {
      setPasswordError('Passwords do not match'); return;
    }
    if (passwordForm.new_password.length < 8) {
      setPasswordError('Password must be at least 8 characters'); return;
    }
    passwordMutation.mutate({
      current_password: passwordForm.current_password,
      new_password: passwordForm.new_password,
    });
  };

  const handleTimeOffSubmit = (e) => {
    e.preventDefault();
    if (!timeOffForm.start_date || !timeOffForm.end_date) return;
    timeOffMutation.mutate(timeOffForm);
  };

  const getDirectionsUrl = (job) => {
    const address = job?.job_address || job?.address;
    const eircode = job?.eircode;
    let dest = '';
    if (address && eircode) dest = `${address}, ${eircode}`;
    else if (eircode) dest = eircode;
    else if (address) dest = address;
    return dest ? `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(dest)}` : null;
  };

  const isVideoUrl = (url) => /\.(mp4|mov|webm|avi)(\?|$)/i.test(url);

  if (isLoading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f8fafc' }}>
        <LoadingSpinner />
      </div>
    );
  }

  const worker = data?.worker || {};
  const jobs = data?.jobs || [];
  const schedule = data?.schedule || [];
  const upcomingJobs = jobs.filter(j => j.status !== 'completed' && j.status !== 'cancelled');
  const completedJobs = jobs.filter(j => j.status === 'completed');
  const timeOffRequests = timeOffData?.requests || [];

  const tabs = [
    { id: 'jobs', label: 'My Jobs', icon: 'fas fa-briefcase' },
    { id: 'schedule', label: 'Schedule', icon: 'fas fa-calendar' },
    { id: 'hr', label: 'HR', icon: 'fas fa-user-clock' },
    { id: 'profile', label: 'Profile', icon: 'fas fa-user' },
  ];

  // ---- Job Detail View ----
  if (selectedJobId) {
    const job = selectedJob?.job;
    const assignedWorkers = selectedJob?.assigned_workers || [];
    const directionsUrl = job ? getDirectionsUrl(job) : null;

    return (
      <div className="worker-portal">
        <header className="worker-header">
          <div className="worker-header-content">
            <button className="worker-back-btn" onClick={() => setSelectedJobId(null)}>
              <i className="fas fa-arrow-left"></i> Back to Jobs
            </button>
            <div className="worker-header-right">
              <span className="worker-greeting">Hi, {user?.name || 'Worker'}</span>
              <button className="worker-logout-btn" onClick={handleLogout}>
                <i className="fas fa-sign-out-alt"></i> Sign Out
              </button>
            </div>
          </div>
        </header>
        <main className="worker-main">
          <div className="worker-container">
            {loadingJob ? <LoadingSpinner /> : !job ? (
              <div className="worker-empty"><i className="fas fa-exclamation-circle"></i><p>Job not found</p></div>
            ) : (
              <div className="wjd">
                {/* Job Header */}
                <div className="wjd-header">
                  <div className="wjd-title">
                    <h2>{job.customer_name || job.client_name || 'Job'}</h2>
                    <span className={`worker-job-status ${getStatusBadgeClass(job.status)}`}>{job.status}</span>
                  </div>
                  <div className="wjd-actions">
                    {directionsUrl && (
                      <a href={directionsUrl} target="_blank" rel="noopener noreferrer" className="wjd-btn wjd-btn-directions">
                        <i className="fas fa-directions"></i> Get Directions
                      </a>
                    )}
                    {job.status !== 'completed' && job.status !== 'cancelled' && (
                      <>
                        {job.status !== 'in-progress' && (
                          <button className="wjd-btn wjd-btn-progress" onClick={() => statusMutation.mutate({ jobId: selectedJobId, status: 'in-progress' })}
                            disabled={statusMutation.isPending}>
                            <i className="fas fa-wrench"></i> Start Job
                          </button>
                        )}
                        {job.status === 'in-progress' && (
                          <button className="wjd-btn wjd-btn-complete" onClick={() => statusMutation.mutate({ jobId: selectedJobId, status: 'completed' })}
                            disabled={statusMutation.isPending}>
                            <i className="fas fa-check-circle"></i> Mark Complete
                          </button>
                        )}
                      </>
                    )}
                  </div>
                </div>

                {/* Job Details Grid */}
                <div className="wjd-grid">
                  <div className="wjd-col">
                    <div className="wjd-card">
                      <h3><i className="fas fa-briefcase"></i> Job Details</h3>
                      <div className="wjd-info-row">
                        <div className="wjd-info-cell">
                          <span className="wjd-label">Date & Time</span>
                          <span className="wjd-value">{formatDateTime(job.appointment_time)}
                            {job.duration_minutes && <span className="wjd-duration"> ({formatDuration(job.duration_minutes)})</span>}
                          </span>
                        </div>
                        <div className="wjd-info-cell">
                          <span className="wjd-label">Service</span>
                          <span className="wjd-value">{job.service_type || job.service || 'N/A'}</span>
                        </div>
                      </div>
                      {(job.job_address || job.address || job.eircode) && (
                        <div className="wjd-info-row wjd-full">
                          <div className="wjd-info-cell">
                            <span className="wjd-label">Address</span>
                            <span className="wjd-value">
                              {[job.job_address || job.address, job.eircode].filter(Boolean).join(' ')}
                            </span>
                          </div>
                        </div>
                      )}
                      {job.property_type && (
                        <div className="wjd-info-row">
                          <div className="wjd-info-cell">
                            <span className="wjd-label">Property</span>
                            <span className="wjd-value">{job.property_type}</span>
                          </div>
                        </div>
                      )}
                      {job.notes && (
                        <div className="wjd-info-row wjd-full">
                          <div className="wjd-info-cell">
                            <span className="wjd-label">Notes</span>
                            <span className="wjd-value wjd-notes">{job.notes}</span>
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Customer Card */}
                    <div className="wjd-card">
                      <h3><i className="fas fa-user"></i> Customer</h3>
                      <div className="wjd-info-row">
                        <div className="wjd-info-cell">
                          <span className="wjd-label">Name</span>
                          <span className="wjd-value">{job.customer_name || job.client_name || 'N/A'}</span>
                        </div>
                        <div className="wjd-info-cell">
                          <span className="wjd-label">Phone</span>
                          <span className="wjd-value">
                            {(job.phone || job.phone_number) ? (
                              <a href={`tel:${job.phone || job.phone_number}`} className="wjd-link">
                                {formatPhone(job.phone || job.phone_number)}
                              </a>
                            ) : 'N/A'}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="wjd-col">
                    {/* Assigned Workers */}
                    <div className="wjd-card">
                      <h3><i className="fas fa-hard-hat"></i> Team on This Job</h3>
                      {assignedWorkers.length === 0 ? (
                        <p className="wjd-empty-text">No other workers assigned</p>
                      ) : (
                        <div className="wjd-workers-list">
                          {assignedWorkers.map(w => (
                            <div key={w.id} className="wjd-worker-item">
                              <div className="wjd-worker-avatar">{w.name?.charAt(0)?.toUpperCase() || 'W'}</div>
                              <div>
                                <span className="wjd-worker-name">{w.name}</span>
                                {w.trade_specialty && <span className="wjd-worker-spec">{w.trade_specialty}</span>}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Photos */}
                    <div className="wjd-card">
                      <div className="wjd-card-header">
                        <h3><i className="fas fa-camera"></i> Photos & Videos</h3>
                        <button className="wjd-btn wjd-btn-sm" onClick={() => photoInputRef.current?.click()} disabled={uploadingPhoto}>
                          {uploadingPhoto ? <i className="fas fa-spinner fa-spin"></i> : <i className="fas fa-plus"></i>}
                          {uploadingPhoto ? ' Uploading...' : ' Add Media'}
                        </button>
                        <input ref={photoInputRef} type="file" accept="image/*,video/mp4,video/quicktime,video/webm" capture="environment" onChange={handlePhotoSelect} style={{ display: 'none' }} />
                      </div>
                      {job.photo_urls && job.photo_urls.length > 0 ? (
                        <div className="wjd-photos-grid">
                          {job.photo_urls.map((url, idx) => (
                            <div key={idx} className="wjd-photo-item" onClick={() => setLightboxPhoto(url)}>
                              {isVideoUrl(url) ? (
                                <>
                                  <video src={getProxiedMediaUrl(url)} muted preload="metadata" />
                                  <div className="wjd-video-badge"><i className="fas fa-play"></i></div>
                                </>
                              ) : (
                                <img src={getProxiedMediaUrl(url)} alt={`Photo ${idx + 1}`} />
                              )}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="wjd-empty-text">No photos or videos yet. Capture media on site.</p>
                      )}
                    </div>

                    {/* Job Notes */}
                    <div className="wjd-card">
                      <h3><i className="fas fa-clipboard"></i> Job Notes</h3>
                      <div className="wjd-notes-form">
                        <textarea
                          className="wjd-note-input"
                          placeholder="Log work done, materials used, issues found..."
                          value={noteText}
                          onChange={e => setNoteText(e.target.value)}
                          rows={3}
                        />
                        <button
                          className="wjd-btn wjd-btn-complete wjd-btn-sm"
                          onClick={() => { if (noteText.trim()) noteMutation.mutate({ jobId: selectedJobId, note: noteText }); }}
                          disabled={!noteText.trim() || noteMutation.isPending}
                        >
                          {noteMutation.isPending ? 'Adding...' : 'Add Note'}
                        </button>
                      </div>
                      {(selectedJob?.notes || []).length > 0 ? (
                        <div className="wjd-notes-list">
                          {selectedJob.notes.map((note, idx) => (
                            <div key={note.id || idx} className="wjd-note-item">
                              <div className="wjd-note-header">
                                <span className="wjd-note-author">
                                  <i className="fas fa-user-circle"></i>
                                  {note.created_by?.replace('worker:', '') || 'System'}
                                </span>
                                <span className="wjd-note-time">
                                  {note.created_at ? new Date(note.created_at).toLocaleString('en-IE', {
                                    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
                                  }) : ''}
                                </span>
                              </div>
                              <p className="wjd-note-text">{note.note}</p>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="wjd-empty-text" style={{ marginTop: '0.5rem' }}>No notes yet</p>
                      )}
                    </div>
                  </div>
                </div>

                {/* Lightbox */}
                {lightboxPhoto && (
                  <div className="wjd-lightbox" onClick={() => setLightboxPhoto(null)}>
                    <button className="wjd-lightbox-close" onClick={() => setLightboxPhoto(null)}><i className="fas fa-times"></i></button>
                    {isVideoUrl(lightboxPhoto) ? (
                      <video src={getProxiedMediaUrl(lightboxPhoto)} controls autoPlay onClick={e => e.stopPropagation()} style={{ maxWidth: '90vw', maxHeight: '90vh', borderRadius: '8px' }} />
                    ) : (
                      <img src={getProxiedMediaUrl(lightboxPhoto)} alt="Full size" onClick={e => e.stopPropagation()} />
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </main>
      </div>
    );
  }

  // ---- Main Dashboard View ----
  return (
    <div className="worker-portal">
      <header className="worker-header">
        <div className="worker-header-content">
          <Link to="/worker/dashboard" className="worker-logo">
            <i className="fas fa-bolt" style={{ color: '#fbbf24' }}></i>
            <span>{user?.company_name || 'BookedForYou'}</span>
          </Link>
          <div className="worker-header-right">
            <span className="worker-greeting">Hi, {user?.name || 'Worker'}</span>
            <button className="worker-logout-btn" onClick={handleLogout}>
              <i className="fas fa-sign-out-alt"></i> Sign Out
            </button>
          </div>
        </div>
      </header>

      <main className="worker-main">
        <div className="worker-container">
          {/* Stats Bar */}
          <div className="worker-stats-bar">
            <div className="worker-stat">
              <i className="fas fa-briefcase"></i>
              <div>
                <span className="stat-number">{hoursSummary?.active_jobs ?? upcomingJobs.length}</span>
                <span className="stat-label">Active Jobs</span>
              </div>
            </div>
            <div className="worker-stat">
              <i className="fas fa-check-circle"></i>
              <div>
                <span className="stat-number">{hoursSummary?.completed_jobs ?? completedJobs.length}</span>
                <span className="stat-label">Completed</span>
              </div>
            </div>
            <div className="worker-stat">
              <i className="fas fa-clock"></i>
              <div>
                <span className="stat-number">{hoursSummary?.hours_this_week ?? 0}h</span>
                <span className="stat-label">This Week</span>
              </div>
            </div>
          </div>

          {/* Tabs */}
          <div className="worker-tabs">
            {tabs.map(tab => (
              <button key={tab.id} className={`worker-tab ${activeTab === tab.id ? 'active' : ''}`}
                onClick={() => setActiveTab(tab.id)}>
                <i className={tab.icon}></i> {tab.label}
              </button>
            ))}
          </div>

          <div className="worker-tab-content">
            {/* ---- JOBS TAB ---- */}
            {activeTab === 'jobs' && (
              <div className="worker-jobs">
                <h2>Upcoming Jobs ({upcomingJobs.length})</h2>
                {upcomingJobs.length === 0 ? (
                  <div className="worker-empty"><i className="fas fa-calendar-check"></i><p>No upcoming jobs</p></div>
                ) : (
                  <div className="worker-job-list">
                    {upcomingJobs.map(job => {
                      const dirUrl = getDirectionsUrl(job);
                      const isToday = new Date(job.appointment_time).toDateString() === new Date().toDateString();
                      return (
                        <div key={job.id} className={`worker-job-card ${isToday ? 'today' : ''}`} onClick={() => setSelectedJobId(job.id)}>
                          <div className="worker-job-header">
                            <span className={`worker-job-status ${getStatusBadgeClass(job.status)}`}>{job.status}</span>
                            <span className="worker-job-date">
                              {isToday ? 'Today' : new Date(job.appointment_time).toLocaleDateString('en-IE', { weekday: 'short', month: 'short', day: 'numeric' })}
                            </span>
                          </div>
                          <div className="worker-job-body">
                            <h3>{job.service_type || 'Job'}</h3>
                            <p><i className="fas fa-user"></i> {job.client_name || 'No client'}</p>
                            <p><i className="fas fa-clock"></i> {new Date(job.appointment_time).toLocaleTimeString('en-IE', { hour: '2-digit', minute: '2-digit' })}</p>
                            {job.address && <p><i className="fas fa-map-marker-alt"></i> {job.address}</p>}
                          </div>
                          <div className="worker-job-footer" onClick={e => e.stopPropagation()}>
                            {dirUrl && (
                              <a href={dirUrl} target="_blank" rel="noopener noreferrer" className="wjd-btn wjd-btn-directions wjd-btn-sm">
                                <i className="fas fa-directions"></i> Directions
                              </a>
                            )}
                            {job.phone_number && (
                              <a href={`tel:${job.phone_number}`} className="wjd-btn wjd-btn-sm">
                                <i className="fas fa-phone"></i> Call
                              </a>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
                {completedJobs.length > 0 && (
                  <>
                    <h2 style={{ marginTop: '2rem' }}>Completed ({completedJobs.length})</h2>
                    <div className="worker-job-list">
                      {completedJobs.slice(0, showAllCompleted ? undefined : 5).map(job => (
                        <div key={job.id} className="worker-job-card completed" onClick={() => setSelectedJobId(job.id)}>
                          <div className="worker-job-header">
                            <span className="worker-job-status badge-completed">completed</span>
                            <span className="worker-job-date">
                              {new Date(job.appointment_time).toLocaleDateString('en-IE', { weekday: 'short', month: 'short', day: 'numeric' })}
                            </span>
                          </div>
                          <div className="worker-job-body">
                            <h3>{job.service_type || 'Job'}</h3>
                            <p><i className="fas fa-user"></i> {job.client_name || 'No client'}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                    {completedJobs.length > 5 && (
                      <button className="wjd-btn wjd-btn-sm" style={{ marginTop: '0.75rem' }}
                        onClick={() => setShowAllCompleted(!showAllCompleted)}>
                        {showAllCompleted ? 'Show Less' : `Show All ${completedJobs.length} Completed`}
                      </button>
                    )}
                  </>
                )}
              </div>
            )}

            {/* ---- SCHEDULE TAB ---- */}
            {activeTab === 'schedule' && (
              <div className="worker-schedule">
                <h2>My Schedule</h2>
                {schedule.length === 0 ? (
                  <div className="worker-empty"><i className="fas fa-calendar"></i><p>No scheduled appointments</p></div>
                ) : (
                  <div className="worker-schedule-list">
                    {schedule.map((item, idx) => (
                      <div key={idx} className="worker-schedule-item" onClick={() => setSelectedJobId(item.id)}>
                        <div className="worker-schedule-date">
                          <span className="schedule-day">{new Date(item.appointment_time).toLocaleDateString('en-IE', { weekday: 'short' })}</span>
                          <span className="schedule-date-num">{new Date(item.appointment_time).getDate()}</span>
                          <span className="schedule-month">{new Date(item.appointment_time).toLocaleDateString('en-IE', { month: 'short' })}</span>
                        </div>
                        <div className="worker-schedule-details">
                          <h3>{item.service_type || 'Job'}</h3>
                          <p><i className="fas fa-clock"></i> {new Date(item.appointment_time).toLocaleTimeString('en-IE', { hour: '2-digit', minute: '2-digit' })}</p>
                          {item.client_name && <p><i className="fas fa-user"></i> {item.client_name}</p>}
                          {item.address && <p><i className="fas fa-map-marker-alt"></i> {item.address}</p>}
                        </div>
                        <span className={`worker-job-status ${getStatusBadgeClass(item.status)}`}>{item.status}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* ---- HR TAB ---- */}
            {activeTab === 'hr' && (
              <div className="worker-hr">
                <div className="whr-section">
                  <div className="whr-section-header">
                    <h2><i className="fas fa-umbrella-beach"></i> Time Off</h2>
                    <button className="wjd-btn wjd-btn-sm" onClick={() => setShowTimeOffForm(!showTimeOffForm)}>
                      <i className="fas fa-plus"></i> Request Time Off
                    </button>
                  </div>

                  {showTimeOffForm && (
                    <form className="whr-form" onSubmit={handleTimeOffSubmit}>
                      <div className="whr-form-row">
                        <div className="whr-field">
                          <label>Type</label>
                          <select value={timeOffForm.type} onChange={e => setTimeOffForm({ ...timeOffForm, type: e.target.value })}>
                            <option value="vacation">Vacation</option>
                            <option value="sick">Sick Leave</option>
                            <option value="personal">Personal</option>
                            <option value="other">Other</option>
                          </select>
                        </div>
                        <div className="whr-field">
                          <label>Start Date</label>
                          <input type="date" required value={timeOffForm.start_date}
                            min={new Date().toISOString().split('T')[0]}
                            onChange={e => setTimeOffForm({ ...timeOffForm, start_date: e.target.value })} />
                        </div>
                        <div className="whr-field">
                          <label>End Date</label>
                          <input type="date" required value={timeOffForm.end_date}
                            min={timeOffForm.start_date || new Date().toISOString().split('T')[0]}
                            onChange={e => setTimeOffForm({ ...timeOffForm, end_date: e.target.value })} />
                        </div>
                      </div>
                      <div className="whr-field">
                        <label>Reason (optional)</label>
                        <input type="text" value={timeOffForm.reason} placeholder="Brief reason..."
                          onChange={e => setTimeOffForm({ ...timeOffForm, reason: e.target.value })} />
                      </div>
                      <div className="whr-form-actions">
                        <button type="button" className="wjd-btn wjd-btn-sm" onClick={() => setShowTimeOffForm(false)}>Cancel</button>
                        <button type="submit" className="wjd-btn wjd-btn-complete wjd-btn-sm" disabled={timeOffMutation.isPending}>
                          {timeOffMutation.isPending ? 'Submitting...' : 'Submit Request'}
                        </button>
                      </div>
                    </form>
                  )}

                  {timeOffRequests.length === 0 ? (
                    <div className="worker-empty" style={{ padding: '2rem' }}><p>No time-off requests</p></div>
                  ) : (
                    <div className="whr-requests-list">
                      {timeOffRequests.map(req => (
                        <div key={req.id} className={`whr-request-card whr-${req.status}`}>
                          <div className="whr-request-header">
                            <span className={`whr-type-badge whr-type-${req.type}`}>{req.type}</span>
                            <span className={`whr-status-badge whr-status-${req.status}`}>{req.status}</span>
                          </div>
                          <div className="whr-request-dates">
                            <i className="fas fa-calendar"></i>
                            {new Date(req.start_date).toLocaleDateString('en-IE', { month: 'short', day: 'numeric' })}
                            {' — '}
                            {new Date(req.end_date).toLocaleDateString('en-IE', { month: 'short', day: 'numeric', year: 'numeric' })}
                          </div>
                          {req.reason && <p className="whr-request-reason">{req.reason}</p>}
                          {req.reviewer_note && <p className="whr-reviewer-note"><i className="fas fa-comment"></i> {req.reviewer_note}</p>}
                          {req.status === 'pending' && (
                            <button className="whr-cancel-btn" onClick={() => deleteTimeOffMutation.mutate(req.id)}
                              disabled={deleteTimeOffMutation.isPending}>
                              <i className="fas fa-times"></i> Cancel Request
                            </button>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Hours Summary */}
                <div className="whr-section">
                  <h2><i className="fas fa-chart-bar"></i> Hours Summary</h2>
                  <div className="whr-hours-grid">
                    <div className="whr-hours-card">
                      <span className="whr-hours-num">{hoursSummary?.hours_this_week ?? 0}h</span>
                      <span className="whr-hours-label">This Week</span>
                    </div>
                    <div className="whr-hours-card">
                      <span className="whr-hours-num">{hoursSummary?.weekly_hours_expected ?? 40}h</span>
                      <span className="whr-hours-label">Expected</span>
                    </div>
                    <div className="whr-hours-card">
                      <span className="whr-hours-num">{hoursSummary?.total_jobs ?? jobs.length}</span>
                      <span className="whr-hours-label">Total Jobs</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* ---- PROFILE TAB ---- */}
            {activeTab === 'profile' && (
              <div className="worker-profile">
                <div className="whr-section-header">
                  <h2>My Profile</h2>
                  {!isEditingProfile ? (
                    <button className="wjd-btn wjd-btn-sm" onClick={() => {
                      setProfileForm({ phone: worker.phone || '', image_url: worker.image_url || '' });
                      setIsEditingProfile(true);
                    }}>
                      <i className="fas fa-edit"></i> Edit Profile
                    </button>
                  ) : (
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      <button className="wjd-btn wjd-btn-sm" onClick={() => setIsEditingProfile(false)}>Cancel</button>
                      <button className="wjd-btn wjd-btn-complete wjd-btn-sm"
                        onClick={() => profileMutation.mutate(profileForm)}
                        disabled={profileMutation.isPending}>
                        {profileMutation.isPending ? 'Saving...' : 'Save'}
                      </button>
                    </div>
                  )}
                </div>

                <div className="worker-profile-card">
                  <div className="worker-profile-avatar">
                    {isEditingProfile ? (
                      <ImageUpload
                        value={profileForm.image_url}
                        onChange={(val) => setProfileForm({ ...profileForm, image_url: val })}
                        placeholder="Upload Photo"
                      />
                    ) : worker.image_url ? (
                      <img src={worker.image_url} alt={worker.name} />
                    ) : (
                      <div className="worker-avatar-placeholder">{worker.name?.charAt(0)?.toUpperCase() || 'W'}</div>
                    )}
                  </div>
                  <div className="worker-profile-info">
                    <div className="worker-profile-row"><label>Name</label><span>{worker.name}</span></div>
                    <div className="worker-profile-row"><label>Email</label><span>{worker.email}</span></div>
                    <div className="worker-profile-row">
                      <label>Phone</label>
                      {isEditingProfile ? (
                        <input type="tel" className="whr-inline-input" value={profileForm.phone}
                          onChange={e => setProfileForm({ ...profileForm, phone: e.target.value })}
                          placeholder="Your phone number" />
                      ) : (
                        <span>{worker.phone ? formatPhone(worker.phone) : 'Not set'}</span>
                      )}
                    </div>
                    <div className="worker-profile-row"><label>Specialty</label><span>{worker.trade_specialty || 'Not set'}</span></div>
                    <div className="worker-profile-row"><label>Status</label>
                      <span className={`worker-job-status ${worker.status === 'active' ? 'badge-confirmed' : 'badge-pending'}`}>{worker.status || 'active'}</span>
                    </div>
                  </div>
                </div>

                {/* Job History */}
                <div className="whr-section" style={{ marginTop: '1.5rem' }}>
                  <h2><i className="fas fa-history"></i> Job History ({jobs.length} total)</h2>
                  {jobs.length === 0 ? (
                    <p className="wjd-empty-text">No job history yet</p>
                  ) : (
                    <>
                      <div className="whr-job-history">
                        {jobs.slice(0, showAllHistory ? undefined : 10).map(job => (
                          <div key={job.id} className="whr-history-item" onClick={() => setSelectedJobId(job.id)}>
                            <div className="whr-history-date">
                              {new Date(job.appointment_time).toLocaleDateString('en-IE', { month: 'short', day: 'numeric' })}
                            </div>
                            <div className="whr-history-details">
                              <span className="whr-history-service">{job.service_type || 'Job'}</span>
                              <span className="whr-history-client">{job.client_name || ''}</span>
                            </div>
                            <span className={`worker-job-status ${getStatusBadgeClass(job.status)}`}>{job.status}</span>
                          </div>
                        ))}
                      </div>
                      {jobs.length > 10 && (
                        <button className="wjd-btn wjd-btn-sm" style={{ marginTop: '0.75rem' }}
                          onClick={() => setShowAllHistory(!showAllHistory)}>
                          {showAllHistory ? 'Show Less' : `Show All ${jobs.length} Jobs`}
                        </button>
                      )}
                    </>
                  )}
                </div>

                {/* Change Password */}
                <div className="whr-section" style={{ marginTop: '1.5rem' }}>
                  <div className="whr-section-header">
                    <h2><i className="fas fa-lock"></i> Security</h2>
                    <button className="wjd-btn wjd-btn-sm" onClick={() => setShowChangePassword(!showChangePassword)}>
                      <i className="fas fa-key"></i> Change Password
                    </button>
                  </div>
                  {showChangePassword && (
                    <form className="whr-form" onSubmit={handlePasswordSubmit}>
                      {passwordError && <div className="whr-error"><i className="fas fa-exclamation-circle"></i> {passwordError}</div>}
                      {passwordSuccess && <div className="whr-success"><i className="fas fa-check-circle"></i> {passwordSuccess}</div>}
                      <div className="whr-field">
                        <label>Current Password</label>
                        <input type="password" required value={passwordForm.current_password}
                          onChange={e => setPasswordForm({ ...passwordForm, current_password: e.target.value })} />
                      </div>
                      <div className="whr-form-row">
                        <div className="whr-field">
                          <label>New Password</label>
                          <input type="password" required minLength={8} value={passwordForm.new_password}
                            onChange={e => setPasswordForm({ ...passwordForm, new_password: e.target.value })} />
                        </div>
                        <div className="whr-field">
                          <label>Confirm New Password</label>
                          <input type="password" required minLength={8} value={passwordForm.confirm_password}
                            onChange={e => setPasswordForm({ ...passwordForm, confirm_password: e.target.value })} />
                        </div>
                      </div>
                      <div className="whr-form-actions">
                        <button type="button" className="wjd-btn wjd-btn-sm" onClick={() => setShowChangePassword(false)}>Cancel</button>
                        <button type="submit" className="wjd-btn wjd-btn-complete wjd-btn-sm" disabled={passwordMutation.isPending}>
                          {passwordMutation.isPending ? 'Changing...' : 'Update Password'}
                        </button>
                      </div>
                    </form>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

export default WorkerDashboard;
