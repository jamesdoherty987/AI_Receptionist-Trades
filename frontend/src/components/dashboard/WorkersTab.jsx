import { useState, useMemo, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getWorkerHoursThisWeek } from '../../services/api';
import AddWorkerModal from '../modals/AddWorkerModal';
import WorkerDetailModal from '../modals/WorkerDetailModal';
import './WorkersTab.css';

function WorkersTab({ workers, bookings }) {
  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedWorkerId, setSelectedWorkerId] = useState(null);
  const [workersHours, setWorkersHours] = useState({});

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
      // Find jobs assigned to this worker for today
      const workerJobsToday = bookings.filter(job => {
        const jobDate = new Date(job.appointment_time);
        const isToday = jobDate.toDateString() === today;
        const isAssigned = job.worker_id === worker.id || job.assigned_worker_id === worker.id;
        const isActive = job.status !== 'completed' && job.status !== 'cancelled';
        return isToday && isAssigned && isActive;
      });

      // Check if currently on a job (within job time window)
      const currentJob = workerJobsToday.find(job => {
        const jobTime = new Date(job.appointment_time);
        const diffMinutes = (now - jobTime) / (1000 * 60);
        // Consider busy if job started within last 2 hours
        return diffMinutes >= -30 && diffMinutes <= 120;
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
        weeklyHoursExpected: worker.weekly_hours_expected || 40
      };
    });
  }, [workers, bookings, workersHours]);

  return (
    <div className="workers-tab">
      <div className="workers-header">
        <h2>Workers Directory</h2>
        <button className="btn btn-primary btn-sm" onClick={() => setShowAddModal(true)}>
          <i className="fas fa-plus"></i> Add Worker
        </button>
      </div>

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
                <span className={`status-badge ${worker.isBusy ? 'busy' : 'available'}`}>
                  {worker.isBusy ? (
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
