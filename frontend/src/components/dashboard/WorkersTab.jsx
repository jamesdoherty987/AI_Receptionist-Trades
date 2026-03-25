import { useState, useMemo, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../Toast';
import { getWorkerHoursThisWeek, getCompanyTimeOffRequests, reviewTimeOffRequest } from '../../services/api';
import AddWorkerModal from '../modals/AddWorkerModal';
import WorkerDetailModal from '../modals/WorkerDetailModal';
import './WorkersTab.css';

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

  // Fetch time-off requests
  const { data: timeOffData } = useQuery({
    queryKey: ['company-time-off'],
    queryFn: async () => {
      const response = await getCompanyTimeOffRequests();
      return response.data;
    },
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

  const handleAddClick = () => {
    if (!isSubscriptionActive) {
      addToast('You need an active subscription to add workers', 'warning');
      return;
    }
    setShowAddModal(true);
  };

  // Fetch hours for all workers
  useEffect(() => {
    const fetchHours = async () => {
      const hoursMap = {};
      for (const worker of workers) {
        try {
          const response = await getWorkerHoursThisWeek(worker.id);
          hoursMap[worker.id] = response.data.hours_worked;
        } catch (error) {
          console.error(`Error fetching hours for worker ${worker.id}:`, error);
          hoursMap[worker.id] = 0;
        }
      }
      setWorkersHours(hoursMap);
    };
    
    if (workers.length > 0) {
      fetchHours();
    }
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

  return (
    <div className="workers-tab">
      <div className="workers-header">
        <h2>Workers Directory</h2>
        <div className="workers-controls">
          <button 
            className="btn btn-primary btn-sm" 
            onClick={handleAddClick}
          >
            <i className={`fas ${isSubscriptionActive ? 'fa-plus' : 'fa-lock'}`}></i> Add Worker
          </button>
        </div>
      </div>

      {/* Time-Off Requests Section */}
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
              {pendingRequests.length > 0 && (
                <div className="time-off-group">
                  <h4>Pending Approval</h4>
                  {pendingRequests.map(req => (
                    <div key={req.id} className="time-off-card pending">
                      <div className="time-off-card-header">
                        <span className="time-off-worker-name">{req.worker_name}</span>
                        <span className="time-off-type-badge">{req.type}</span>
                      </div>
                      <div className="time-off-dates">
                        <i className="fas fa-calendar"></i>
                        {new Date(req.start_date).toLocaleDateString('en-IE', { month: 'short', day: 'numeric' })}
                        {' — '}
                        {new Date(req.end_date).toLocaleDateString('en-IE', { month: 'short', day: 'numeric', year: 'numeric' })}
                      </div>
                      {req.reason && <p className="time-off-reason">{req.reason}</p>}
                      <div className="time-off-review">
                        <input
                          type="text"
                          className="time-off-note-input"
                          placeholder="Add a note (optional)..."
                          value={reviewNotes[req.id] || ''}
                          onChange={e => setReviewNotes(prev => ({ ...prev, [req.id]: e.target.value }))}
                        />
                        <div className="time-off-actions">
                          <button
                            className="btn btn-sm btn-success"
                            onClick={() => { reviewMutation.mutate({ id: req.id, status: 'approved', note: reviewNotes[req.id] || '' }); }}
                            disabled={reviewMutation.isPending}
                          >
                            <i className="fas fa-check"></i> Approve
                          </button>
                          <button
                            className="btn btn-sm btn-danger"
                            onClick={() => { reviewMutation.mutate({ id: req.id, status: 'denied', note: reviewNotes[req.id] || '' }); }}
                            disabled={reviewMutation.isPending}
                          >
                            <i className="fas fa-times"></i> Deny
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {pastRequests.length > 0 && (
                <div className="time-off-group">
                  <h4>Recent Decisions</h4>
                  {pastRequests.slice(0, 5).map(req => (
                    <div key={req.id} className={`time-off-card ${req.status}`}>
                      <div className="time-off-card-header">
                        <span className="time-off-worker-name">{req.worker_name}</span>
                        <span className={`time-off-status-badge ${req.status}`}>{req.status}</span>
                      </div>
                      <div className="time-off-dates">
                        <i className="fas fa-calendar"></i>
                        {new Date(req.start_date).toLocaleDateString('en-IE', { month: 'short', day: 'numeric' })}
                        {' — '}
                        {new Date(req.end_date).toLocaleDateString('en-IE', { month: 'short', day: 'numeric' })}
                        <span className="time-off-type-badge" style={{ marginLeft: '0.5rem' }}>{req.type}</span>
                      </div>
                      {req.reviewer_note && <p className="time-off-reason"><i className="fas fa-comment"></i> {req.reviewer_note}</p>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      <div className="workers-list">
        {workersWithStatus.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">👷</div>
            <p>No workers found</p>
          </div>
        ) : (
          workersWithStatus.map((worker) => (
            <div 
              key={worker.id} 
              className={`worker-card ${worker.isBusy ? 'is-busy' : ''}`}
              onClick={() => setSelectedWorkerId(worker.id)}
            >
              <div className="worker-avatar">
                {worker.image_url ? (
                  <img src={worker.image_url} alt={worker.name} className="worker-avatar-img" />
                ) : (
                  <i className="fas fa-hard-hat"></i>
                )}
                <span className={`status-dot ${worker.isBusy ? 'busy' : 'available'}`}></span>
              </div>
              <div className="worker-info">
                <h3>{worker.name}</h3>
                <div className="worker-details">
                  {worker.specialty && (
                    <div className="worker-detail specialty">
                      <i className="fas fa-wrench"></i>
                      <span>{worker.specialty}</span>
                    </div>
                  )}
                  {worker.phone && (
                    <div className="worker-detail">
                      <i className="fas fa-phone"></i>
                      <span>{worker.phone}</span>
                    </div>
                  )}
                </div>
                {worker.jobsToday > 0 && (
                  <div className="worker-jobs-info">
                    <span className="jobs-today-badge">
                      <i className="fas fa-briefcase"></i>
                      {worker.jobsToday} job{worker.jobsToday !== 1 ? 's' : ''} today
                    </span>
                    {worker.nextJob && !worker.isBusy && (
                      <span className="next-job">
                        Next: {new Date(worker.nextJob.appointment_time).toLocaleTimeString('en-US', { 
                          hour: '2-digit', 
                          minute: '2-digit' 
                        })}
                      </span>
                    )}
                  </div>
                )}
                <div className="worker-hours-info">
                  <span className="hours-badge">
                    <i className="fas fa-clock"></i>
                    {worker.hoursWorked}h / {worker.weeklyHoursExpected}h this week
                  </span>
                </div>
              </div>
              <div className="worker-status">
                <span className={`status-badge ${worker.isOnLeave ? 'on-leave' : worker.isBusy ? 'busy' : 'available'}`}>
                  {worker.isOnLeave ? (
                    <>
                      <i className="fas fa-umbrella-beach"></i> On Leave
                    </>
                  ) : worker.isBusy ? (
                    <>
                      <i className="fas fa-tools"></i> On Job
                    </>
                  ) : (
                    <>
                      <i className="fas fa-check"></i> Available
                    </>
                  )}
                </span>
              </div>
            </div>
          ))
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
    </div>
  );
}

export default WorkersTab;
