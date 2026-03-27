import { useState, useRef, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../context/AuthContext';
import { Link, useNavigate } from 'react-router-dom';
import {
  getWorkerDashboard,
  getWorkerJobDetail,
  workerUploadJobPhoto,
  workerUploadJobMedia,
  workerUpdateJobStatus,
  workerUpdateJobDetails,
  workerBulkCompleteJobs,
  getWorkerTimeOff,
  createTimeOffRequest,
  deleteTimeOffRequest,
  workerChangePassword,
  getWorkerHoursSummary,
  addWorkerJobNote,
  updateWorkerProfile,
  getWorkerCustomers,
  getWorkerJobMaterials,
  addWorkerJobMaterial,
  deleteWorkerJobMaterial,
  getWorkerMessages,
  workerSendMessage,
  getWorkerUnreadMessageCount
} from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';
import ImageUpload from '../components/ImageUpload';
import WorkerNotificationBell from '../components/WorkerNotificationBell';
import { formatPhone, getStatusBadgeClass, formatDateTime, getProxiedMediaUrl } from '../utils/helpers';
import { formatDuration } from '../utils/durationOptions';
import './WorkerDashboard.css';

// Live timer component for in-progress jobs
function JobTimer({ startedAt }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!startedAt) return;
    const start = new Date(startedAt).getTime();
    const tick = () => setElapsed(Math.floor((Date.now() - start) / 1000));
    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, [startedAt]);

  if (!startedAt) return null;

  const hrs = Math.floor(elapsed / 3600);
  const mins = Math.floor((elapsed % 3600) / 60);
  const secs = elapsed % 60;
  const pad = (n) => String(n).padStart(2, '0');

  return (
    <div className="wjd-timer">
      <i className="fas fa-stopwatch"></i>
      <span className="wjd-timer-display">
        {hrs > 0 ? `${pad(hrs)}:` : ''}{pad(mins)}:{pad(secs)}
      </span>
    </div>
  );
}

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

  // Job materials state
  const [showAddMaterial, setShowAddMaterial] = useState(false);
  const [workerMaterialSearch, setWorkerMaterialSearch] = useState('');
  const [workerCustomMat, setWorkerCustomMat] = useState({ name: '', unit_price: '', quantity: '1' });

  // Messages state
  const [msgInput, setMsgInput] = useState('');
  const msgEndRef = useRef(null);
  const prevMsgCountRef = useRef(0);

  // Profile editing state
  const [isEditingProfile, setIsEditingProfile] = useState(false);
  const [profileForm, setProfileForm] = useState({ phone: '', image_url: '' });

  // Job history state
  const [showAllCompleted, setShowAllCompleted] = useState(false);
  const [showAllHistory, setShowAllHistory] = useState(false);
  const [bulkCompleteFilter, setBulkCompleteFilter] = useState(null); // null | 'today' | 'week' | 'all'

  // Schedule view state
  const [scheduleView, setScheduleView] = useState('list'); // 'list' | 'month' | 'year'
  const [calMonth, setCalMonth] = useState(new Date().getMonth());
  const [calYear, setCalYear] = useState(new Date().getFullYear());
  const [selectedCalDay, setSelectedCalDay] = useState(null);

  // Customer tab state
  const [customerSearch, setCustomerSearch] = useState('');
  const [selectedCustomer, setSelectedCustomer] = useState(null);

  // Job timer state
  const [jobTimerStart, setJobTimerStart] = useState(null); // ISO string when timer started
  const [jobTimerElapsed, setJobTimerElapsed] = useState(0); // seconds
  const [showStatusDropdown, setShowStatusDropdown] = useState(false);
  
  // Job detail editing state
  const [isEditingJobDetails, setIsEditingJobDetails] = useState(false);
  const [editActualCharge, setEditActualCharge] = useState('');
  const [editActualDuration, setEditActualDuration] = useState('');

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
    enabled: true,
  });

  const { data: customersData } = useQuery({
    queryKey: ['worker-customers'],
    queryFn: async () => { const r = await getWorkerCustomers(); return r.data; },
    enabled: activeTab === 'customers',
  });

  // Job materials for selected job
  const { data: workerJobMaterials } = useQuery({
    queryKey: ['worker-job-materials', selectedJobId],
    queryFn: async () => { const r = await getWorkerJobMaterials(selectedJobId); return r.data; },
    enabled: !!selectedJobId,
  });

  const addWorkerMatMut = useMutation({
    mutationFn: (data) => addWorkerJobMaterial(selectedJobId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['worker-job-materials', selectedJobId] });
      setShowAddMaterial(false);
      setWorkerMaterialSearch('');
      setWorkerCustomMat({ name: '', unit_price: '', quantity: '1' });
    },
  });

  // Messages queries
  const { data: messagesData } = useQuery({
    queryKey: ['worker-messages'],
    queryFn: async () => { const r = await getWorkerMessages(); return r.data; },
    enabled: activeTab === 'messages',
    refetchInterval: activeTab === 'messages' ? 8000 : false,
  });

  // Auto-scroll messages to bottom only when new messages arrive
  useEffect(() => {
    const count = messagesData?.messages?.length || 0;
    if (activeTab === 'messages' && msgEndRef.current && count > prevMsgCountRef.current) {
      msgEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
    prevMsgCountRef.current = count;
  }, [activeTab, messagesData]);

  const { data: unreadMsgData } = useQuery({
    queryKey: ['worker-unread-messages'],
    queryFn: async () => { const r = await getWorkerUnreadMessageCount(); return r.data; },
    refetchInterval: 30000,
  });

  const sendMsgMutation = useMutation({
    mutationFn: (content) => workerSendMessage(content),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['worker-messages'] });
      queryClient.invalidateQueries({ queryKey: ['worker-unread-messages'] });
      queryClient.invalidateQueries({ queryKey: ['worker-notifications'] });
      setMsgInput('');
    },
    onError: (error) => {
      console.error('Failed to send message:', error);
      alert(error.response?.data?.error || 'Failed to send message. Please try again.');
    },
  });

  const removeWorkerMatMut = useMutation({
    mutationFn: (itemId) => deleteWorkerJobMaterial(selectedJobId, itemId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['worker-job-materials', selectedJobId] });
    },
  });

  const statusMutation = useMutation({
    mutationFn: ({ jobId, status, started_at, completed_at, actual_duration_minutes }) => 
      workerUpdateJobStatus(jobId, { status, started_at, completed_at, actual_duration_minutes }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['worker-dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['worker-job', selectedJobId] });
    },
  });

  const detailsMutation = useMutation({
    mutationFn: ({ jobId, data }) => workerUpdateJobDetails(jobId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['worker-dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['worker-job', selectedJobId] });
      setIsEditingJobDetails(false);
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
    },
  });

  const timeOffMutation = useMutation({
    mutationFn: (data) => createTimeOffRequest(data),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['worker-time-off'] });
      setShowTimeOffForm(false);
      setTimeOffForm({ start_date: '', end_date: '', reason: '', type: 'vacation' });
      // Warn about conflicting bookings
      const data = response.data;
      if (data?.has_conflicts && data.conflicting_jobs?.length > 0) {
        const jobList = data.conflicting_jobs.map(j => `${j.date}: ${j.service}${j.client ? ` (${j.client})` : ''}`).join('\n');
        alert(`Note: You have ${data.conflicting_jobs.length} existing job(s) during this period:\n\n${jobList}\n\nYour manager will see this when reviewing your request.`);
      }
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

  const bulkCompleteMutation = useMutation({
    mutationFn: (filter) => workerBulkCompleteJobs(filter),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['worker-dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['worker-hours-summary'] });
      setBulkCompleteFilter(null);
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
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;

    setUploadingPhoto(true);

    const processFile = (file) => new Promise((resolve) => {
      const isVideo = file.type.startsWith('video/');
      const isImage = file.type.startsWith('image/');
      if (!isImage && !isVideo) { resolve(); return; }

      const maxSize = isVideo ? 50 * 1024 * 1024 : 10 * 1024 * 1024;
      if (file.size > maxSize) { resolve(); return; }

      if (isVideo) {
        photoMutation.mutate(file, { onSettled: resolve });
      } else {
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
            photoMutation.mutate(result, { onSettled: resolve });
          };
          img.src = ev.target.result;
        };
        reader.readAsDataURL(file);
      }
    });

    for (const file of files) {
      await processFile(file);
    }

    setUploadingPhoto(false);

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
  const timeOffRequests = timeOffData?.requests || [];

  // Smart job grouping
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const tomorrowStart = new Date(todayStart); tomorrowStart.setDate(tomorrowStart.getDate() + 1);
  const weekEnd = new Date(todayStart); weekEnd.setDate(weekEnd.getDate() + 7);

  const activeJobs = jobs.filter(j => j.status !== 'completed' && j.status !== 'cancelled' && j.status !== 'paid');
  const completedJobs = jobs.filter(j => j.status === 'completed' || j.status === 'paid');

  // In-progress jobs always on top
  const inProgressJobs = activeJobs.filter(j => j.status === 'in-progress');

  // Overdue: past appointment time, not started
  const overdueJobs = activeJobs.filter(j => {
    if (j.status === 'in-progress') return false;
    return new Date(j.appointment_time) < now;
  });

  // Today's upcoming
  const todayJobs = activeJobs.filter(j => {
    if (j.status === 'in-progress') return false;
    const t = new Date(j.appointment_time);
    return t >= now && t < tomorrowStart;
  });

  // Tomorrow
  const tomorrowJobs = activeJobs.filter(j => {
    if (j.status === 'in-progress') return false;
    const t = new Date(j.appointment_time);
    const dayAfterTomorrow = new Date(tomorrowStart); dayAfterTomorrow.setDate(dayAfterTomorrow.getDate() + 1);
    return t >= tomorrowStart && t < dayAfterTomorrow;
  });

  // This week (after tomorrow, within 7 days)
  const thisWeekJobs = activeJobs.filter(j => {
    if (j.status === 'in-progress') return false;
    const t = new Date(j.appointment_time);
    const dayAfterTomorrow = new Date(tomorrowStart); dayAfterTomorrow.setDate(dayAfterTomorrow.getDate() + 1);
    return t >= dayAfterTomorrow && t < weekEnd;
  });

  // Later (beyond this week)
  const laterJobs = activeJobs.filter(j => {
    if (j.status === 'in-progress') return false;
    return new Date(j.appointment_time) >= weekEnd;
  });

  const upcomingJobs = activeJobs;

  const tabs = [
    { id: 'jobs', label: 'My Jobs', icon: 'fas fa-briefcase' },
    { id: 'messages', label: 'Messages', icon: 'fas fa-comment-dots' },
    { id: 'schedule', label: 'Schedule', icon: 'fas fa-calendar' },
    { id: 'customers', label: 'Customers', icon: 'fas fa-users' },
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
            <button className="worker-back-btn" onClick={() => { setSelectedJobId(null); setShowAddMaterial(false); }}>
              <i className="fas fa-arrow-left"></i> Back to Jobs
            </button>
            <div className="worker-header-right">
              <span className="worker-greeting">Hi, {user?.name || 'Worker'}</span>
              <WorkerNotificationBell />
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
                    {/* Start Job button — records timer start */}
                    {job.status !== 'completed' && job.status !== 'cancelled' && job.status !== 'in-progress' && (
                      <button className="wjd-btn wjd-btn-progress" onClick={() => {
                        const now = new Date().toISOString();
                        setJobTimerStart(now);
                        setJobTimerElapsed(0);
                        statusMutation.mutate({ jobId: selectedJobId, status: 'in-progress', started_at: now });
                      }} disabled={statusMutation.isPending}>
                        <i className="fas fa-play-circle"></i> Start Job
                      </button>
                    )}
                    {/* Live timer when in-progress */}
                    {job.status === 'in-progress' && (
                      <JobTimer startedAt={job.job_started_at || jobTimerStart} />
                    )}
                    {/* Mark Complete button — records timer end and calculates duration */}
                    {job.status === 'in-progress' && (
                      <button className="wjd-btn wjd-btn-complete" onClick={() => {
                        const now = new Date().toISOString();
                        const start = job.job_started_at || jobTimerStart;
                        let durationMins = null;
                        if (start) {
                          durationMins = Math.round((new Date(now) - new Date(start)) / 60000);
                          if (durationMins < 1) durationMins = 1;
                        }
                        statusMutation.mutate({ 
                          jobId: selectedJobId, 
                          status: 'completed', 
                          completed_at: now,
                          actual_duration_minutes: durationMins 
                        });
                        setJobTimerStart(null);
                      }} disabled={statusMutation.isPending}>
                        <i className="fas fa-check-circle"></i> Mark Complete
                      </button>
                    )}
                    {/* Status dropdown for all statuses */}
                    <div className="wjd-status-dropdown" style={{ position: 'relative' }}>
                      <button className="wjd-btn" onClick={() => setShowStatusDropdown(!showStatusDropdown)}>
                        <i className="fas fa-exchange-alt"></i> Status <i className="fas fa-chevron-down" style={{ fontSize: '0.7em', marginLeft: 2 }}></i>
                      </button>
                      {showStatusDropdown && (
                        <>
                          <div className="wjd-dropdown-backdrop" onClick={() => setShowStatusDropdown(false)}></div>
                          <div className="wjd-dropdown-menu">
                            {[
                              { value: 'pending', label: 'Pending', icon: 'fas fa-clock', color: '#f59e0b' },
                              { value: 'confirmed', label: 'Confirmed', icon: 'fas fa-calendar-check', color: '#3b82f6' },
                              { value: 'scheduled', label: 'Scheduled', icon: 'fas fa-calendar-alt', color: '#6366f1' },
                              { value: 'in-progress', label: 'In Progress', icon: 'fas fa-wrench', color: '#8b5cf6' },
                              { value: 'completed', label: 'Completed', icon: 'fas fa-check-circle', color: '#22c55e' },
                              { value: 'paid', label: 'Paid', icon: 'fas fa-money-check-alt', color: '#10b981' },
                              { value: 'cancelled', label: 'Cancelled', icon: 'fas fa-times-circle', color: '#ef4444' },
                            ].map(s => (
                              <button key={s.value} 
                                className={job.status === s.value ? 'active' : ''}
                                onClick={() => {
                                  if (s.value === 'in-progress' && !job.job_started_at) {
                                    const now = new Date().toISOString();
                                    setJobTimerStart(now);
                                    statusMutation.mutate({ jobId: selectedJobId, status: s.value, started_at: now });
                                  } else {
                                    statusMutation.mutate({ jobId: selectedJobId, status: s.value });
                                  }
                                  setShowStatusDropdown(false);
                                }}>
                                <i className={s.icon} style={{ color: s.color }}></i> {s.label}
                              </button>
                            ))}
                          </div>
                        </>
                      )}
                    </div>
                  </div>
                </div>

                {/* Time Tracking & Charge Card (shown after completion or when time data exists) */}
                {(job.status === 'completed' || job.status === 'paid' || job.actual_duration_minutes || job.job_started_at) && (
                  <div className="wjd-card wjd-time-card">
                    <div className="wjd-time-card-header">
                      <h3><i className="fas fa-stopwatch"></i> Time & Charge</h3>
                      {!isEditingJobDetails && (job.status === 'completed' || job.status === 'paid') && (
                        <button className="wjd-btn wjd-btn-sm" onClick={() => {
                          setEditActualCharge(job.charge || job.estimated_charge || '');
                          setEditActualDuration(job.actual_duration_minutes || '');
                          setIsEditingJobDetails(true);
                        }}>
                          <i className="fas fa-edit"></i> Edit
                        </button>
                      )}
                    </div>
                    {isEditingJobDetails ? (
                      <div className="wjd-edit-row">
                        <div className="wjd-edit-field">
                          <label>Actual Time (minutes)</label>
                          <input type="number" min="1" value={editActualDuration} 
                            onChange={e => setEditActualDuration(e.target.value)} placeholder="e.g. 90" />
                        </div>
                        <div className="wjd-edit-field">
                          <label>Actual Charge (€)</label>
                          <input type="number" min="0" step="0.01" value={editActualCharge}
                            onChange={e => setEditActualCharge(e.target.value)} placeholder="e.g. 150.00" />
                        </div>
                        <div className="wjd-edit-actions">
                          <button className="wjd-btn wjd-btn-sm" onClick={() => setIsEditingJobDetails(false)}>Cancel</button>
                          <button className="wjd-btn wjd-btn-complete wjd-btn-sm" 
                            disabled={detailsMutation.isPending}
                            onClick={() => {
                              const payload = {};
                              if (editActualDuration) payload.actual_duration_minutes = parseInt(editActualDuration);
                              if (editActualCharge !== '') payload.actual_charge = parseFloat(editActualCharge);
                              detailsMutation.mutate({ jobId: selectedJobId, data: payload });
                            }}>
                            {detailsMutation.isPending ? 'Saving...' : 'Save'}
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="wjd-info-row">
                        {job.job_started_at && (
                          <div className="wjd-info-cell">
                            <span className="wjd-label">Started</span>
                            <span className="wjd-value">{new Date(job.job_started_at).toLocaleTimeString('en-IE', { hour: '2-digit', minute: '2-digit' })}</span>
                          </div>
                        )}
                        {job.job_completed_at && (
                          <div className="wjd-info-cell">
                            <span className="wjd-label">Finished</span>
                            <span className="wjd-value">{new Date(job.job_completed_at).toLocaleTimeString('en-IE', { hour: '2-digit', minute: '2-digit' })}</span>
                          </div>
                        )}
                        {job.actual_duration_minutes && (
                          <div className="wjd-info-cell">
                            <span className="wjd-label">Time Taken</span>
                            <span className="wjd-value">{job.actual_duration_minutes >= 60 ? `${Math.floor(job.actual_duration_minutes / 60)}h ${job.actual_duration_minutes % 60}m` : `${job.actual_duration_minutes}m`}</span>
                          </div>
                        )}
                        <div className="wjd-info-cell">
                          <span className="wjd-label">Charge</span>
                          <span className="wjd-value" style={{ color: '#22c55e', fontWeight: 700 }}>
                            {(job.charge || job.estimated_charge) 
                              ? (job.charge_max && parseFloat(job.charge_max) > parseFloat(job.charge || job.estimated_charge)
                                ? `€${parseFloat(job.charge || job.estimated_charge).toFixed(2)} – €${parseFloat(job.charge_max).toFixed(2)}`
                                : `€${parseFloat(job.charge || job.estimated_charge).toFixed(2)}`)
                              : '—'}
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Profit Summary - shown when materials are logged */}
                {workerJobMaterials?.materials?.length > 0 && !!(job.charge || job.estimated_charge) && (() => {
                  const charge = parseFloat(job.charge || job.estimated_charge || 0);
                  const matCost = parseFloat(workerJobMaterials?.total_cost || 0);
                  const profit = charge - matCost;
                  const margin = charge > 0 ? (profit / charge * 100) : 0;
                  return (
                    <div className="wjd-card" style={{ background: profit >= 0 ? 'linear-gradient(135deg, #f0fdf4, #ecfdf5)' : 'linear-gradient(135deg, #fef2f2, #fff1f2)', border: `1px solid ${profit >= 0 ? '#bbf7d0' : '#fecaca'}` }}>
                      <h3 style={{ margin: '0 0 0.5rem 0' }}><i className="fas fa-chart-line"></i> Job Profit</h3>
                      <div className="wjd-info-row">
                        <div className="wjd-info-cell">
                          <span className="wjd-label">Charged</span>
                          <span className="wjd-value">€{charge.toFixed(2)}</span>
                        </div>
                        <div className="wjd-info-cell">
                          <span className="wjd-label">Materials</span>
                          <span className="wjd-value" style={{ color: '#ef4444' }}>-€{matCost.toFixed(2)}</span>
                        </div>
                        <div className="wjd-info-cell">
                          <span className="wjd-label">Profit</span>
                          <span className="wjd-value" style={{ color: profit >= 0 ? '#16a34a' : '#ef4444', fontWeight: 700 }}>
                            €{profit.toFixed(2)} ({margin.toFixed(0)}%)
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })()}

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
                        <input ref={photoInputRef} type="file" accept="image/*,video/mp4,video/quicktime,video/webm" multiple onChange={handlePhotoSelect} style={{ display: 'none' }} />
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

                    {/* Materials Used */}
                    <div className="wjd-card">
                      <div className="wjd-card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                        <h3 style={{ margin: 0 }}><i className="fas fa-cubes"></i> Materials Used</h3>
                        <button className="wjd-btn wjd-btn-sm" onClick={() => setShowAddMaterial(!showAddMaterial)}>
                          <i className="fas fa-plus"></i> Add
                        </button>
                      </div>

                      {showAddMaterial && (
                        <div className="wjd-mat-add" style={{ background: '#f8fafc', borderRadius: 8, padding: '0.75rem', marginBottom: '0.75rem' }}>
                          <input type="text" className="wjd-note-input" style={{ marginBottom: '0.5rem' }}
                            placeholder="Search catalog or type material name..."
                            value={workerMaterialSearch}
                            onChange={e => setWorkerMaterialSearch(e.target.value)} autoFocus />
                          {/* Catalog results */}
                          {workerMaterialSearch && workerJobMaterials?.catalog?.length > 0 && (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 2, marginBottom: '0.5rem' }}>
                              {workerJobMaterials.catalog
                                .filter(m => m.name.toLowerCase().includes(workerMaterialSearch.toLowerCase()))
                                .slice(0, 5)
                                .map(m => (
                                  <button key={m.id} className="wjd-btn wjd-btn-sm" style={{ justifyContent: 'space-between', width: '100%' }}
                                    onClick={() => addWorkerMatMut.mutate({
                                      material_id: m.id, name: m.name, unit_price: m.unit_price,
                                      unit: m.unit || 'each', quantity: 1
                                    })}>
                                    <span>{m.name}</span>
                                    <span style={{ color: '#22c55e', fontWeight: 700 }}>€{parseFloat(m.unit_price).toFixed(2)}</span>
                                  </button>
                                ))}
                            </div>
                          )}
                          {/* Custom entry */}
                          <div style={{ fontSize: '0.78rem', color: '#64748b', marginBottom: '0.3rem' }}>Or add custom:</div>
                          <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                            <input type="text" placeholder="Name" value={workerCustomMat.name}
                              onChange={e => setWorkerCustomMat({...workerCustomMat, name: e.target.value})}
                              className="wjd-note-input" style={{ flex: 2, minWidth: 100, marginBottom: 0 }} />
                            <input type="number" placeholder="€" value={workerCustomMat.unit_price} min="0" step="0.01"
                              onChange={e => setWorkerCustomMat({...workerCustomMat, unit_price: e.target.value})}
                              className="wjd-note-input" style={{ flex: 0.8, minWidth: 60, marginBottom: 0 }} />
                            <input type="number" placeholder="Qty" value={workerCustomMat.quantity} min="1" step="1"
                              onChange={e => setWorkerCustomMat({...workerCustomMat, quantity: e.target.value})}
                              className="wjd-note-input" style={{ flex: 0.6, minWidth: 50, marginBottom: 0 }} />
                          </div>
                          <div style={{ display: 'flex', gap: '0.4rem', justifyContent: 'flex-end', marginTop: '0.5rem' }}>
                            <button className="wjd-btn wjd-btn-sm" onClick={() => setShowAddMaterial(false)}>Cancel</button>
                            <button className="wjd-btn wjd-btn-complete wjd-btn-sm"
                              disabled={!workerCustomMat.name.trim() || addWorkerMatMut.isPending}
                              onClick={() => addWorkerMatMut.mutate({
                                name: workerCustomMat.name, unit_price: parseFloat(workerCustomMat.unit_price) || 0,
                                quantity: parseFloat(workerCustomMat.quantity) || 1, unit: 'each'
                              })}>
                              {addWorkerMatMut.isPending ? 'Adding...' : 'Add'}
                            </button>
                          </div>
                        </div>
                      )}

                      {workerJobMaterials?.materials?.length > 0 ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                          {workerJobMaterials.materials.map(item => (
                            <div key={item.id} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.4rem 0.5rem', background: 'white', borderRadius: 6, border: '1px solid var(--border-color, #e2e8f0)' }}>
                              <div style={{ flex: 1, minWidth: 0 }}>
                                <span style={{ fontWeight: 600, fontSize: '0.85rem', display: 'block' }}>{item.name}</span>
                                <span style={{ fontSize: '0.75rem', color: '#64748b' }}>{item.quantity} × €{parseFloat(item.unit_price).toFixed(2)}</span>
                              </div>
                              <span style={{ fontWeight: 700, color: '#22c55e', fontSize: '0.85rem', whiteSpace: 'nowrap' }}>€{parseFloat(item.total_cost).toFixed(2)}</span>
                              <button className="wjd-btn wjd-btn-sm" style={{ padding: '0.2rem 0.4rem', color: '#ef4444', borderColor: '#fecaca' }}
                                onClick={() => removeWorkerMatMut.mutate(item.id)}>
                                <i className="fas fa-times"></i>
                              </button>
                            </div>
                          ))}
                          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem 0.6rem', background: 'linear-gradient(135deg, #f0fdf4, #ecfdf5)', border: '1px solid #bbf7d0', borderRadius: 8, fontWeight: 600, fontSize: '0.88rem', marginTop: '0.25rem' }}>
                            <span>Total</span>
                            <span style={{ color: '#16a34a', fontWeight: 700 }}>€{parseFloat(workerJobMaterials.total_cost).toFixed(2)}</span>
                          </div>
                        </div>
                      ) : (
                        <p className="wjd-empty-text">No materials logged yet</p>
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
            <WorkerNotificationBell />
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
                onClick={() => {
                  setActiveTab(tab.id);
                  if (tab.id === 'messages') {
                    queryClient.invalidateQueries({ queryKey: ['worker-unread-messages'] });
                  }
                }}>
                <i className={tab.icon}></i> {tab.label}
                {tab.id === 'messages' && (unreadMsgData?.unread_count || 0) > 0 && activeTab !== 'messages' && (
                  <span className="wm-tab-badge">{unreadMsgData.unread_count > 9 ? '9+' : unreadMsgData.unread_count}</span>
                )}
              </button>
            ))}
          </div>

          <div className="worker-tab-content">
            {/* ---- JOBS TAB ---- */}
            {activeTab === 'jobs' && (
              <div className="worker-jobs">
                {/* In Progress — always visible at top */}
                {inProgressJobs.length > 0 && (
                  <div className="wj-section wj-in-progress">
                    <h2><i className="fas fa-wrench"></i> In Progress ({inProgressJobs.length})</h2>
                    <div className="worker-job-list">
                      {inProgressJobs.map(job => {
                        const dirUrl = getDirectionsUrl(job);
                        return (
                          <div key={job.id} className="worker-job-card in-progress" onClick={() => setSelectedJobId(job.id)}>
                            <div className="worker-job-header">
                              <span className="worker-job-status badge-in-progress"><i className="fas fa-wrench"></i> in-progress</span>
                              <JobTimer startedAt={job.job_started_at} />
                            </div>
                            <div className="worker-job-body">
                              <h3>{job.client_name || 'No client'}</h3>
                              <p><i className="fas fa-briefcase"></i> {job.service_type || 'Job'}</p>
                              <p><i className="fas fa-clock"></i> {new Date(job.appointment_time).toLocaleTimeString('en-IE', { hour: '2-digit', minute: '2-digit' })}</p>
                              {(job.address || job.job_address) && <p><i className="fas fa-map-marker-alt"></i> {job.job_address || job.address}{job.address_audio_url && <button className="wjd-btn wjd-btn-sm" style={{marginLeft: 6, padding: "0.15rem 0.4rem", fontSize: "0.7rem"}} onClick={e => { e.stopPropagation(); new Audio(getProxiedMediaUrl(job.address_audio_url)).play(); }}><i className="fas fa-volume-up"></i></button>}</p>}
                            </div>
                            <div className="worker-job-footer" onClick={e => e.stopPropagation()}>
                              {dirUrl && (
                                <a href={dirUrl} target="_blank" rel="noopener noreferrer" className="wjd-btn wjd-btn-directions wjd-btn-sm">
                                  <i className="fas fa-directions"></i> Directions
                                </a>
                              )}
                              <button className="wjd-btn wjd-btn-complete wjd-btn-sm" onClick={() => {
                                const nowIso = new Date().toISOString();
                                const start = job.job_started_at;
                                let durationMins = null;
                                if (start) {
                                  durationMins = Math.round((new Date(nowIso) - new Date(start)) / 60000);
                                  if (durationMins < 1) durationMins = 1;
                                }
                                statusMutation.mutate({ jobId: job.id, status: 'completed', completed_at: nowIso, actual_duration_minutes: durationMins });
                              }} disabled={statusMutation.isPending}>
                                <i className="fas fa-check-circle"></i> Complete
                              </button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Overdue — needs attention */}
                {overdueJobs.length > 0 && (
                  <div className="wj-section wj-overdue">
                    <div className="wj-section-header">
                      <h2><i className="fas fa-exclamation-triangle"></i> Overdue ({overdueJobs.length})</h2>
                      <button className="wjd-btn wjd-btn-complete wjd-btn-sm" onClick={() => setBulkCompleteFilter(bulkCompleteFilter ? null : 'overdue')}>
                        <i className="fas fa-check-double"></i> Mark All Complete
                      </button>
                    </div>
                    {bulkCompleteFilter === 'overdue' && (
                      <div className="wj-bulk-confirm">
                        <p>Mark all {overdueJobs.length} overdue job(s) as completed?</p>
                        <div className="wj-bulk-actions">
                          <button className="wjd-btn wjd-btn-sm" onClick={() => setBulkCompleteFilter(null)}>Cancel</button>
                          <button className="wjd-btn wjd-btn-complete wjd-btn-sm" disabled={bulkCompleteMutation.isPending}
                            onClick={() => bulkCompleteMutation.mutate('all')}>
                            {bulkCompleteMutation.isPending ? 'Completing...' : 'Confirm'}
                          </button>
                        </div>
                      </div>
                    )}
                    <div className="worker-job-list">
                      {overdueJobs.map(job => {
                        const dirUrl = getDirectionsUrl(job);
                        return (
                          <div key={job.id} className="worker-job-card overdue" onClick={() => setSelectedJobId(job.id)}>
                            <div className="worker-job-header">
                              <span className="worker-job-status badge-overdue"><i className="fas fa-exclamation-circle"></i> overdue</span>
                              <span className="worker-job-date">
                                {new Date(job.appointment_time).toLocaleDateString('en-IE', { weekday: 'short', month: 'short', day: 'numeric' })}
                              </span>
                            </div>
                            <div className="worker-job-body">
                              <h3>{job.client_name || 'No client'}</h3>
                              <p><i className="fas fa-briefcase"></i> {job.service_type || 'Job'}</p>
                              <p><i className="fas fa-clock"></i> {new Date(job.appointment_time).toLocaleTimeString('en-IE', { hour: '2-digit', minute: '2-digit' })}</p>
                              {(job.address || job.job_address) && <p><i className="fas fa-map-marker-alt"></i> {job.job_address || job.address}{job.address_audio_url && <button className="wjd-btn wjd-btn-sm" style={{marginLeft: 6, padding: "0.15rem 0.4rem", fontSize: "0.7rem"}} onClick={e => { e.stopPropagation(); new Audio(getProxiedMediaUrl(job.address_audio_url)).play(); }}><i className="fas fa-volume-up"></i></button>}</p>}
                            </div>
                            <div className="worker-job-footer" onClick={e => e.stopPropagation()}>
                              {dirUrl && (
                                <a href={dirUrl} target="_blank" rel="noopener noreferrer" className="wjd-btn wjd-btn-directions wjd-btn-sm">
                                  <i className="fas fa-directions"></i> Directions
                                </a>
                              )}
                              <button className="wjd-btn wjd-btn-progress wjd-btn-sm" onClick={() => {
                                const nowIso = new Date().toISOString();
                                statusMutation.mutate({ jobId: job.id, status: 'in-progress', started_at: nowIso });
                              }} disabled={statusMutation.isPending}>
                                <i className="fas fa-play-circle"></i> Start
                              </button>
                              <button className="wjd-btn wjd-btn-complete wjd-btn-sm" onClick={() => {
                                statusMutation.mutate({ jobId: job.id, status: 'completed', completed_at: new Date().toISOString() });
                              }} disabled={statusMutation.isPending}>
                                <i className="fas fa-check-circle"></i> Complete
                              </button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Today */}
                {todayJobs.length > 0 && (
                  <div className="wj-section wj-today">
                    <h2><i className="fas fa-sun"></i> Today ({todayJobs.length})</h2>
                    <div className="worker-job-list">
                      {todayJobs.map(job => {
                        const dirUrl = getDirectionsUrl(job);
                        return (
                          <div key={job.id} className="worker-job-card today" onClick={() => setSelectedJobId(job.id)}>
                            <div className="worker-job-header">
                              <span className={`worker-job-status ${getStatusBadgeClass(job.status)}`}>{job.status}</span>
                              <span className="worker-job-date">Today</span>
                            </div>
                            <div className="worker-job-body">
                              <h3>{job.client_name || 'No client'}</h3>
                              <p><i className="fas fa-briefcase"></i> {job.service_type || 'Job'}</p>
                              <p><i className="fas fa-clock"></i> {new Date(job.appointment_time).toLocaleTimeString('en-IE', { hour: '2-digit', minute: '2-digit' })}</p>
                              {(job.address || job.job_address) && <p><i className="fas fa-map-marker-alt"></i> {job.job_address || job.address}{job.address_audio_url && <button className="wjd-btn wjd-btn-sm" style={{marginLeft: 6, padding: "0.15rem 0.4rem", fontSize: "0.7rem"}} onClick={e => { e.stopPropagation(); new Audio(getProxiedMediaUrl(job.address_audio_url)).play(); }}><i className="fas fa-volume-up"></i></button>}</p>}
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
                              <button className="wjd-btn wjd-btn-progress wjd-btn-sm" onClick={() => {
                                const nowIso = new Date().toISOString();
                                statusMutation.mutate({ jobId: job.id, status: 'in-progress', started_at: nowIso });
                              }} disabled={statusMutation.isPending}>
                                <i className="fas fa-play-circle"></i> Start
                              </button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Tomorrow */}
                {tomorrowJobs.length > 0 && (
                  <div className="wj-section">
                    <h2><i className="fas fa-calendar-day"></i> Tomorrow ({tomorrowJobs.length})</h2>
                    <div className="worker-job-list">
                      {tomorrowJobs.map(job => {
                        const dirUrl = getDirectionsUrl(job);
                        return (
                          <div key={job.id} className="worker-job-card" onClick={() => setSelectedJobId(job.id)}>
                            <div className="worker-job-header">
                              <span className={`worker-job-status ${getStatusBadgeClass(job.status)}`}>{job.status}</span>
                              <span className="worker-job-date">Tomorrow</span>
                            </div>
                            <div className="worker-job-body">
                              <h3>{job.client_name || 'No client'}</h3>
                              <p><i className="fas fa-briefcase"></i> {job.service_type || 'Job'}</p>
                              <p><i className="fas fa-clock"></i> {new Date(job.appointment_time).toLocaleTimeString('en-IE', { hour: '2-digit', minute: '2-digit' })}</p>
                              {(job.address || job.job_address) && <p><i className="fas fa-map-marker-alt"></i> {job.job_address || job.address}{job.address_audio_url && <button className="wjd-btn wjd-btn-sm" style={{marginLeft: 6, padding: "0.15rem 0.4rem", fontSize: "0.7rem"}} onClick={e => { e.stopPropagation(); new Audio(getProxiedMediaUrl(job.address_audio_url)).play(); }}><i className="fas fa-volume-up"></i></button>}</p>}
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
                  </div>
                )}

                {/* This Week */}
                {thisWeekJobs.length > 0 && (
                  <div className="wj-section">
                    <h2><i className="fas fa-calendar-week"></i> This Week ({thisWeekJobs.length})</h2>
                    <div className="worker-job-list">
                      {thisWeekJobs.map(job => {
                        const dirUrl = getDirectionsUrl(job);
                        return (
                          <div key={job.id} className="worker-job-card" onClick={() => setSelectedJobId(job.id)}>
                            <div className="worker-job-header">
                              <span className={`worker-job-status ${getStatusBadgeClass(job.status)}`}>{job.status}</span>
                              <span className="worker-job-date">
                                {new Date(job.appointment_time).toLocaleDateString('en-IE', { weekday: 'short', month: 'short', day: 'numeric' })}
                              </span>
                            </div>
                            <div className="worker-job-body">
                              <h3>{job.client_name || 'No client'}</h3>
                              <p><i className="fas fa-briefcase"></i> {job.service_type || 'Job'}</p>
                              <p><i className="fas fa-clock"></i> {new Date(job.appointment_time).toLocaleTimeString('en-IE', { hour: '2-digit', minute: '2-digit' })}</p>
                              {(job.address || job.job_address) && <p><i className="fas fa-map-marker-alt"></i> {job.job_address || job.address}{job.address_audio_url && <button className="wjd-btn wjd-btn-sm" style={{marginLeft: 6, padding: "0.15rem 0.4rem", fontSize: "0.7rem"}} onClick={e => { e.stopPropagation(); new Audio(getProxiedMediaUrl(job.address_audio_url)).play(); }}><i className="fas fa-volume-up"></i></button>}</p>}
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
                  </div>
                )}

                {/* Later */}
                {laterJobs.length > 0 && (
                  <div className="wj-section">
                    <h2><i className="fas fa-calendar-alt"></i> Later ({laterJobs.length})</h2>
                    <div className="worker-job-list">
                      {laterJobs.map(job => (
                        <div key={job.id} className="worker-job-card" onClick={() => setSelectedJobId(job.id)}>
                          <div className="worker-job-header">
                            <span className={`worker-job-status ${getStatusBadgeClass(job.status)}`}>{job.status}</span>
                            <span className="worker-job-date">
                              {new Date(job.appointment_time).toLocaleDateString('en-IE', { weekday: 'short', month: 'short', day: 'numeric' })}
                            </span>
                          </div>
                          <div className="worker-job-body">
                            <h3>{job.client_name || 'No client'}</h3>
                            <p><i className="fas fa-briefcase"></i> {job.service_type || 'Job'}</p>
                            <p><i className="fas fa-clock"></i> {new Date(job.appointment_time).toLocaleTimeString('en-IE', { hour: '2-digit', minute: '2-digit' })}</p>
                            {(job.address || job.job_address) && <p><i className="fas fa-map-marker-alt"></i> {job.job_address || job.address}{job.address_audio_url && <button className="wjd-btn wjd-btn-sm" style={{marginLeft: 6, padding: "0.15rem 0.4rem", fontSize: "0.7rem"}} onClick={e => { e.stopPropagation(); new Audio(getProxiedMediaUrl(job.address_audio_url)).play(); }}><i className="fas fa-volume-up"></i></button>}</p>}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Empty state */}
                {upcomingJobs.length === 0 && (
                  <div className="worker-empty"><i className="fas fa-calendar-check"></i><p>No active jobs</p></div>
                )}

                {/* Completed */}
                {completedJobs.length > 0 && (
                  <div className="wj-section wj-completed">
                    <h2 style={{ cursor: 'pointer' }} onClick={() => setShowAllCompleted(!showAllCompleted)}>
                      <i className="fas fa-check-circle"></i> Completed ({completedJobs.length})
                      <i className={`fas fa-chevron-${showAllCompleted ? 'up' : 'down'}`} style={{ fontSize: '0.75em', marginLeft: '0.5rem' }}></i>
                    </h2>
                    {showAllCompleted && (
                      <div className="worker-job-list">
                        {completedJobs.slice(0, 10).map(job => (
                          <div key={job.id} className="worker-job-card completed" onClick={() => setSelectedJobId(job.id)}>
                            <div className="worker-job-header">
                              <span className={`worker-job-status ${getStatusBadgeClass(job.status)}`}>{job.status}</span>
                              <span className="worker-job-date">
                                {new Date(job.appointment_time).toLocaleDateString('en-IE', { weekday: 'short', month: 'short', day: 'numeric' })}
                              </span>
                            </div>
                            <div className="worker-job-body">
                              <h3>{job.client_name || 'No client'}</h3>
                              <p><i className="fas fa-briefcase"></i> {job.service_type || 'Job'}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* ---- MESSAGES TAB ---- */}
            {activeTab === 'messages' && (() => {
              const workerMsgs = messagesData?.messages || [];
              // Group messages by date
              const grouped = [];
              let lastD = '';
              workerMsgs.forEach(m => {
                const d = new Date(m.created_at).toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' });
                if (d !== lastD) { grouped.push({ type: 'date', date: d }); lastD = d; }
                grouped.push({ type: 'msg', ...m });
              });

              const handleMsgSend = () => {
                const text = msgInput.trim();
                if (!text || sendMsgMutation.isPending) return;
                sendMsgMutation.mutate(text);
              };

              return (
                <div className="worker-messages-tab">
                  <div className="wm-header">
                    <h2><i className="fas fa-comment-dots"></i> Messages</h2>
                    <p className="wm-subtitle">Chat with your manager</p>
                  </div>
                  <div className="wm-chat-container">
                    <div className="wm-messages">
                      {workerMsgs.length === 0 ? (
                        <div className="wm-empty">
                          <div className="wm-empty-icon"><i className="fas fa-comments"></i></div>
                          <h3>No messages yet</h3>
                          <p>Send a message to your manager</p>
                        </div>
                      ) : (
                        grouped.map((item, i) => {
                          if (item.type === 'date') {
                            return (
                              <div key={`d-${i}`} className="wm-date-divider"><span>{item.date}</span></div>
                            );
                          }
                          const isMine = item.sender_type === 'worker';
                          return (
                            <div key={item.id} className={`wm-bubble ${isMine ? 'sent' : 'received'}`}>
                              <div className="wm-bubble-content">
                                <p>{item.content}</p>
                                <span className="wm-time">
                                  {(() => {
                                    const d = new Date(item.created_at);
                                    const diff = Math.floor((Date.now() - d) / 60000);
                                    if (diff < 1) return 'Just now';
                                    if (diff < 60) return `${diff}m ago`;
                                    return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
                                  })()}
                                  {isMine && item.read && <i className="fas fa-check-double wm-read" title="Read"></i>}
                                </span>
                              </div>
                            </div>
                          );
                        })
                      )}
                      <div ref={msgEndRef} />
                    </div>
                    <div className="wm-input-bar">
                      <textarea
                        className="wm-input"
                        placeholder="Type a message..."
                        value={msgInput}
                        onChange={(e) => setMsgInput(e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleMsgSend(); } }}
                        rows="1"
                        maxLength={2000}
                      />
                      <button
                        className="wm-send-btn"
                        onClick={handleMsgSend}
                        disabled={!msgInput.trim() || sendMsgMutation.isPending}
                        aria-label="Send message"
                      >
                        <i className={`fas ${sendMsgMutation.isPending ? 'fa-spinner fa-spin' : 'fa-paper-plane'}`}></i>
                      </button>
                    </div>
                  </div>
                </div>
              );
            })()}

            {/* ---- SCHEDULE TAB ---- */}
            {activeTab === 'schedule' && (
              <div className="worker-schedule">
                <div className="ws-header">
                  <h2>My Schedule</h2>
                  <div className="ws-view-toggle">
                    {[
                      { id: 'list', icon: 'fas fa-list', label: 'List' },
                      { id: 'week', icon: 'fas fa-calendar-week', label: 'Week' },
                      { id: 'month', icon: 'fas fa-calendar-alt', label: 'Month' },
                      { id: 'year', icon: 'fas fa-calendar', label: 'Year' },
                    ].map(v => (
                      <button key={v.id} className={`ws-view-btn ${scheduleView === v.id ? 'active' : ''}`}
                        onClick={() => { setScheduleView(v.id); setSelectedCalDay(null); }}>
                        <i className={v.icon}></i> {v.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* LIST VIEW */}
                {scheduleView === 'list' && (
                  <>
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
                  </>
                )}

                {/* WEEK VIEW */}
                {scheduleView === 'week' && (() => {
                  const allJobs = jobs || [];
                  const approvedLeave = (timeOffData?.requests || []).filter(r => r.status === 'approved' || r.status === 'pending');
                  const today = new Date();

                  // Get the week's start (Sunday)
                  const refDate = selectedCalDay
                    ? new Date(calYear, calMonth, selectedCalDay)
                    : new Date(); // Default to current week
                  const dayOfWeek = refDate.getDay();
                  const weekStart = new Date(refDate);
                  weekStart.setDate(refDate.getDate() - dayOfWeek);
                  weekStart.setHours(0, 0, 0, 0);

                  const weekDays = Array.from({ length: 7 }, (_, i) => {
                    const d = new Date(weekStart);
                    d.setDate(weekStart.getDate() + i);
                    return d;
                  });

                  const weekLabel = (() => {
                    const s = weekDays[0];
                    const e = weekDays[6];
                    if (s.getMonth() === e.getMonth()) {
                      return `${s.toLocaleDateString('en-IE', { month: 'long' })} ${s.getDate()} – ${e.getDate()}, ${s.getFullYear()}`;
                    }
                    return `${s.toLocaleDateString('en-IE', { month: 'short' })} ${s.getDate()} – ${e.toLocaleDateString('en-IE', { month: 'short' })} ${e.getDate()}, ${e.getFullYear()}`;
                  })();

                  const navigateWeek = (dir) => {
                    const ref = new Date(weekStart);
                    ref.setDate(ref.getDate() + dir * 7);
                    setCalYear(ref.getFullYear());
                    setCalMonth(ref.getMonth());
                    setSelectedCalDay(ref.getDate());
                  };

                  return (
                    <div className="ws-week-view">
                      <div className="ws-month-nav">
                        <button className="ws-nav-btn" onClick={() => navigateWeek(-1)}><i className="fas fa-chevron-left"></i></button>
                        <span className="ws-month-title">{weekLabel}</span>
                        <button className="ws-nav-btn" onClick={() => navigateWeek(1)}><i className="fas fa-chevron-right"></i></button>
                      </div>
                      <div className="ws-week-grid">
                        {weekDays.map((date, idx) => {
                          const dateStr = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
                          const dayJobs = allJobs.filter(j => {
                            const jd = new Date(j.appointment_time);
                            return jd.toDateString() === date.toDateString();
                          }).sort((a, b) => new Date(a.appointment_time) - new Date(b.appointment_time));
                          const onLeave = approvedLeave.some(l => dateStr >= l.start_date && dateStr <= l.end_date);
                          const isToday = date.toDateString() === today.toDateString();

                          return (
                            <div key={idx} className={`ws-week-day ${isToday ? 'today' : ''} ${onLeave ? 'on-leave' : ''}`}>
                              <div className="ws-week-day-header">
                                <span className="ws-week-day-name">{date.toLocaleDateString('en-IE', { weekday: 'short' })}</span>
                                <span className={`ws-week-day-num ${isToday ? 'today' : ''}`}>{date.getDate()}</span>
                                {onLeave && <span className="ws-leave-icon-sm"><i className="fas fa-umbrella-beach"></i></span>}
                              </div>
                              <div className="ws-week-day-jobs">
                                {onLeave && (
                                  <div className="ws-week-leave-bar">
                                    <i className="fas fa-umbrella-beach"></i> On Leave
                                  </div>
                                )}
                                {dayJobs.length === 0 && !onLeave && (
                                  <span className="ws-week-empty">—</span>
                                )}
                                {dayJobs.map(job => (
                                  <div key={job.id} className="ws-week-job" onClick={() => setSelectedJobId(job.id)}>
                                    <span className="ws-week-job-time">
                                      {new Date(job.appointment_time).toLocaleTimeString('en-IE', { hour: '2-digit', minute: '2-digit' })}
                                    </span>
                                    <span className="ws-week-job-title">{job.service_type || 'Job'}</span>
                                    <span className={`worker-job-status ${getStatusBadgeClass(job.status)}`}>{job.status}</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })()}

                {/* MONTH VIEW */}
                {scheduleView === 'month' && (() => {
                  const allJobs = jobs || [];
                  const approvedLeave = (timeOffData?.requests || []).filter(r => r.status === 'approved' || r.status === 'pending');
                  const firstDay = new Date(calYear, calMonth, 1).getDay();
                  const daysInMonth = new Date(calYear, calMonth + 1, 0).getDate();
                  const today = new Date();
                  const monthName = new Date(calYear, calMonth).toLocaleDateString('en-IE', { month: 'long', year: 'numeric' });

                  // Build job map for this month: day -> jobs[]
                  const jobsByDay = {};
                  allJobs.forEach(j => {
                    const d = new Date(j.appointment_time);
                    if (d.getMonth() === calMonth && d.getFullYear() === calYear) {
                      const day = d.getDate();
                      if (!jobsByDay[day]) jobsByDay[day] = [];
                      jobsByDay[day].push(j);
                    }
                  });

                  // Check if a day falls within approved leave
                  const isOnLeave = (day) => {
                    const dateStr = `${calYear}-${String(calMonth + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
                    return approvedLeave.some(l => dateStr >= l.start_date && dateStr <= l.end_date);
                  };

                  // Get leave info for selected day
                  const selectedDayLeave = selectedCalDay ? approvedLeave.filter(l => {
                    const dateStr = `${calYear}-${String(calMonth + 1).padStart(2, '0')}-${String(selectedCalDay).padStart(2, '0')}`;
                    return dateStr >= l.start_date && dateStr <= l.end_date;
                  }) : [];

                  // Jobs for selected day
                  const selectedDayJobs = selectedCalDay ? (jobsByDay[selectedCalDay] || []).sort((a, b) =>
                    new Date(a.appointment_time) - new Date(b.appointment_time)
                  ) : [];

                  return (
                    <div className="ws-month-view">
                      <div className="ws-month-main">
                        <div className="ws-month-nav">
                          <button className="ws-nav-btn" onClick={() => {
                            if (calMonth === 0) { setCalMonth(11); setCalYear(calYear - 1); }
                            else setCalMonth(calMonth - 1);
                            setSelectedCalDay(null);
                          }}><i className="fas fa-chevron-left"></i></button>
                          <span className="ws-month-title">{monthName}</span>
                          <button className="ws-nav-btn" onClick={() => {
                            if (calMonth === 11) { setCalMonth(0); setCalYear(calYear + 1); }
                            else setCalMonth(calMonth + 1);
                            setSelectedCalDay(null);
                          }}><i className="fas fa-chevron-right"></i></button>
                        </div>
                        <div className="ws-cal-grid">
                          {['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].map(d => (
                            <div key={d} className="ws-cal-header">{d}</div>
                          ))}
                          {Array.from({ length: firstDay }).map((_, i) => (
                            <div key={`e-${i}`} className="ws-cal-cell empty"></div>
                          ))}
                          {Array.from({ length: daysInMonth }).map((_, i) => {
                            const day = i + 1;
                            const dayJobs = jobsByDay[day] || [];
                            const onLeave = isOnLeave(day);
                            const isToday = day === today.getDate() && calMonth === today.getMonth() && calYear === today.getFullYear();
                            const isSelected = day === selectedCalDay;
                            return (
                              <div key={day}
                                className={`ws-cal-cell ${isToday ? 'today' : ''} ${isSelected ? 'selected' : ''} ${dayJobs.length > 0 ? 'has-jobs' : ''} ${onLeave ? 'on-leave' : ''}`}
                                onClick={() => setSelectedCalDay(day === selectedCalDay ? null : day)}>
                                <span className="ws-cal-day">{day}</span>
                                {onLeave && <span className="ws-leave-icon"><i className="fas fa-umbrella-beach"></i></span>}
                                {dayJobs.length > 0 && (
                                  <div className="ws-cal-dots">
                                    {dayJobs.slice(0, 3).map((j, idx) => (
                                      <span key={idx} className={`ws-cal-dot ${j.status === 'completed' ? 'done' : j.status === 'cancelled' ? 'cancelled' : ''}`}></span>
                                    ))}
                                    {dayJobs.length > 3 && <span className="ws-cal-more">+{dayJobs.length - 3}</span>}
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>

                      {/* Side panel for selected day */}
                      <div className="ws-events-panel">
                        <div className="ws-events-panel-header">
                          <h3>
                            {selectedCalDay
                              ? new Date(calYear, calMonth, selectedCalDay).toLocaleDateString('en-IE', { weekday: 'long', month: 'long', day: 'numeric' })
                              : 'Select a day'
                            }
                          </h3>
                          {selectedCalDay && (
                            <span className="ws-event-count">
                              {selectedDayJobs.length} job{selectedDayJobs.length !== 1 ? 's' : ''}
                              {selectedDayLeave.length > 0 && ' · leave'}
                            </span>
                          )}
                        </div>
                        <div className="ws-events-list">
                          {!selectedCalDay ? (
                            <div className="ws-events-empty">
                              <i className="fas fa-hand-pointer"></i>
                              <p>Tap a day to see details</p>
                            </div>
                          ) : (selectedDayJobs.length === 0 && selectedDayLeave.length === 0) ? (
                            <div className="ws-events-empty">
                              <i className="fas fa-calendar-check"></i>
                              <p>Nothing scheduled</p>
                            </div>
                          ) : (
                            <>
                              {selectedDayLeave.length > 0 && (
                                <div className={`ws-leave-banner ${selectedDayLeave.some(l => l.status === 'pending') ? 'pending' : ''}`}>
                                  <i className="fas fa-umbrella-beach"></i>
                                  {selectedDayLeave.map(l => (
                                    <span key={l.id}>
                                      {l.type.charAt(0).toUpperCase() + l.type.slice(1)} leave
                                      {l.status === 'pending' ? ' (pending)' : ''}
                                      {' · '}
                                      {new Date(l.start_date + 'T00:00').toLocaleDateString('en-IE', { month: 'short', day: 'numeric' })}
                                      {' — '}
                                      {new Date(l.end_date + 'T00:00').toLocaleDateString('en-IE', { month: 'short', day: 'numeric' })}
                                    </span>
                                  ))}
                                </div>
                              )}
                              {selectedDayJobs.map(job => (
                                <div key={job.id} className="ws-event-card" onClick={() => setSelectedJobId(job.id)}>
                                  <div className="ws-event-time">
                                    {new Date(job.appointment_time).toLocaleTimeString('en-IE', { hour: '2-digit', minute: '2-digit' })}
                                  </div>
                                  <div className="ws-event-info">
                                    <span className="ws-event-title">{job.service_type || 'Job'}</span>
                                    {job.client_name && <span className="ws-event-sub"><i className="fas fa-user"></i> {job.client_name}</span>}
                                    {job.address && <span className="ws-event-sub"><i className="fas fa-map-marker-alt"></i> {job.address}</span>}
                                  </div>
                                  <div className="ws-event-right">
                                    <span className={`worker-job-status ${getStatusBadgeClass(job.status)}`}>{job.status}</span>
                                    <i className="fas fa-chevron-right ws-event-arrow"></i>
                                  </div>
                                </div>
                              ))}
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })()}

                {/* YEAR VIEW */}
                {scheduleView === 'year' && (() => {
                  const allJobs = jobs || [];
                  const leaveRequests = (timeOffData?.requests || []).filter(r => r.status === 'approved' || r.status === 'pending');
                  const today = new Date();

                  // Build job count per month
                  const jobsByMonth = {};
                  allJobs.forEach(j => {
                    const d = new Date(j.appointment_time);
                    if (d.getFullYear() === calYear) {
                      const m = d.getMonth();
                      jobsByMonth[m] = (jobsByMonth[m] || 0) + 1;
                    }
                  });

                  return (
                    <div className="ws-year-view">
                      <div className="ws-month-nav">
                        <button className="ws-nav-btn" onClick={() => setCalYear(calYear - 1)}>
                          <i className="fas fa-chevron-left"></i>
                        </button>
                        <span className="ws-month-title">{calYear}</span>
                        <button className="ws-nav-btn" onClick={() => setCalYear(calYear + 1)}>
                          <i className="fas fa-chevron-right"></i>
                        </button>
                      </div>
                      <div className="ws-year-grid">
                        {Array.from({ length: 12 }).map((_, m) => {
                          const monthName = new Date(calYear, m).toLocaleDateString('en-IE', { month: 'short' });
                          const count = jobsByMonth[m] || 0;
                          const isCurrent = m === today.getMonth() && calYear === today.getFullYear();
                          const daysInMonth = new Date(calYear, m + 1, 0).getDate();
                          const firstDay = new Date(calYear, m, 1).getDay();

                          // Mini job map for this month
                          const miniJobDays = new Set();
                          allJobs.forEach(j => {
                            const d = new Date(j.appointment_time);
                            if (d.getMonth() === m && d.getFullYear() === calYear) miniJobDays.add(d.getDate());
                          });

                          // Mini leave map for this month
                          const miniLeaveDays = new Set();
                          leaveRequests.forEach(l => {
                            const s = new Date(l.start_date + 'T00:00');
                            const e = new Date(l.end_date + 'T00:00');
                            const cur = new Date(s);
                            while (cur <= e) {
                              if (cur.getMonth() === m && cur.getFullYear() === calYear) miniLeaveDays.add(cur.getDate());
                              cur.setDate(cur.getDate() + 1);
                            }
                          });

                          return (
                            <div key={m} className={`ws-year-month ${isCurrent ? 'current' : ''}`}
                              onClick={() => { setCalMonth(m); setScheduleView('month'); setSelectedCalDay(null); }}>
                              <div className="ws-ym-header">
                                <span className="ws-ym-name">{monthName}</span>
                                {count > 0 && <span className="ws-ym-count">{count}</span>}
                              </div>
                              <div className="ws-mini-cal">
                                {['S','M','T','W','T','F','S'].map((d, i) => (
                                  <span key={i} className="ws-mini-header">{d}</span>
                                ))}
                                {Array.from({ length: firstDay }).map((_, i) => (
                                  <span key={`e-${i}`} className="ws-mini-day empty"></span>
                                ))}
                                {Array.from({ length: daysInMonth }).map((_, i) => {
                                  const day = i + 1;
                                  const hasJob = miniJobDays.has(day);
                                  const hasLeave = miniLeaveDays.has(day);
                                  const isToday = day === today.getDate() && m === today.getMonth() && calYear === today.getFullYear();
                                  return (
                                    <span key={day} className={`ws-mini-day ${hasJob ? 'has-job' : ''} ${hasLeave ? 'has-leave' : ''} ${isToday ? 'today' : ''}`}>
                                      {day}
                                    </span>
                                  );
                                })}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })()}
              </div>
            )}

            {/* ---- CUSTOMERS TAB ---- */}
            {activeTab === 'customers' && (() => {
              const customers = customersData?.customers || [];
              const filtered = customerSearch.trim()
                ? customers.filter(c =>
                    c.name?.toLowerCase().includes(customerSearch.toLowerCase()) ||
                    c.phone?.includes(customerSearch) ||
                    c.email?.toLowerCase().includes(customerSearch.toLowerCase())
                  )
                : customers;

              return (
                <div className="worker-customers">
                  <div className="wc-header">
                    <h2>My Customers ({customers.length})</h2>
                    <div className="wc-search">
                      <i className="fas fa-search"></i>
                      <input
                        type="text"
                        placeholder="Search customers..."
                        value={customerSearch}
                        onChange={e => setCustomerSearch(e.target.value)}
                      />
                    </div>
                  </div>

                  {filtered.length === 0 ? (
                    <div className="worker-empty">
                      <i className="fas fa-users"></i>
                      <p>{customerSearch ? 'No customers match your search' : 'No customers yet — they\'ll appear here as you get assigned jobs'}</p>
                    </div>
                  ) : (
                    <div className="wc-list">
                      {filtered.map(customer => (
                        <div key={customer.id} className={`wc-card ${selectedCustomer?.id === customer.id ? 'expanded' : ''}`}
                          onClick={() => setSelectedCustomer(selectedCustomer?.id === customer.id ? null : customer)}>
                          <div className="wc-card-main">
                            <div className="wc-avatar">
                              {customer.name?.charAt(0)?.toUpperCase() || 'C'}
                            </div>
                            <div className="wc-info">
                              <h3>{customer.name}</h3>
                              <div className="wc-contact">
                                {customer.phone && (
                                  <span onClick={e => e.stopPropagation()}>
                                    <a href={`tel:${customer.phone}`}><i className="fas fa-phone"></i> {formatPhone(customer.phone)}</a>
                                  </span>
                                )}
                                {customer.email && (
                                  <span><i className="fas fa-envelope"></i> {customer.email}</span>
                                )}
                              </div>
                            </div>
                            <div className="wc-stats">
                              <div className="wc-stat">
                                <span className="wc-stat-num">{customer.total_jobs || 0}</span>
                                <span className="wc-stat-label">Jobs</span>
                              </div>
                              <div className="wc-stat">
                                <span className="wc-stat-num">{customer.completed_jobs || 0}</span>
                                <span className="wc-stat-label">Done</span>
                              </div>
                            </div>
                            <i className={`fas fa-chevron-${selectedCustomer?.id === customer.id ? 'up' : 'down'} wc-expand-icon`}></i>
                          </div>

                          {selectedCustomer?.id === customer.id && (
                            <div className="wc-details" onClick={e => e.stopPropagation()}>
                              {(customer.address || customer.eircode) && (
                                <div className="wc-detail-row">
                                  <i className="fas fa-map-marker-alt"></i>
                                  <span>{[customer.address, customer.eircode].filter(Boolean).join(', ')}</span>
                                </div>
                              )}
                              {customer.last_job_date && (
                                <div className="wc-detail-row">
                                  <i className="fas fa-calendar"></i>
                                  <span>Last job: {new Date(customer.last_job_date).toLocaleDateString('en-IE', { month: 'short', day: 'numeric', year: 'numeric' })}</span>
                                </div>
                              )}
                              {customer.description && (
                                <div className="wc-detail-row">
                                  <i className="fas fa-sticky-note"></i>
                                  <span>{customer.description}</span>
                                </div>
                              )}
                              <div className="wc-detail-actions">
                                {customer.phone && (
                                  <a href={`tel:${customer.phone}`} className="wjd-btn wjd-btn-sm">
                                    <i className="fas fa-phone"></i> Call
                                  </a>
                                )}
                                {(customer.address || customer.eircode) && (
                                  <a href={`https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent([customer.address, customer.eircode].filter(Boolean).join(', '))}`}
                                    target="_blank" rel="noopener noreferrer" className="wjd-btn wjd-btn-directions wjd-btn-sm">
                                    <i className="fas fa-directions"></i> Directions
                                  </a>
                                )}
                              </div>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })()}

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
