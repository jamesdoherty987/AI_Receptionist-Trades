import { useState, useMemo } from 'react';
import { formatDateTime, getStatusBadgeClass } from '../../utils/helpers';
import AddJobModal from '../modals/AddJobModal';
import JobDetailModal from '../modals/JobDetailModal';
import './JobsTab.css';

function JobsTab({ bookings }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedJobId, setSelectedJobId] = useState(null);

  // Get job time status for color coding
  const getJobTimeStatus = (appointmentTime) => {
    const now = new Date();
    const jobTime = new Date(appointmentTime);
    const diffMinutes = (jobTime - now) / (1000 * 60);
    
    // Job is currently happening (within 30 min window)
    if (diffMinutes >= -30 && diffMinutes <= 30) {
      return 'now';
    }
    // Job time has passed
    if (diffMinutes < -30) {
      return 'past';
    }
    // Coming up soon (within 2 hours)
    if (diffMinutes <= 120) {
      return 'soon';
    }
    return 'upcoming';
  };

  // Check if date is today
  const isToday = (date) => {
    const today = new Date();
    const jobDate = new Date(date);
    return jobDate.toDateString() === today.toDateString();
  };

  // Check if date is tomorrow
  const isTomorrow = (date) => {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const jobDate = new Date(date);
    return jobDate.toDateString() === tomorrow.toDateString();
  };

  // Check if date is in this week (next 7 days)
  const isThisWeek = (date) => {
    const now = new Date();
    const jobDate = new Date(date);
    const weekFromNow = new Date();
    weekFromNow.setDate(weekFromNow.getDate() + 7);
    return jobDate > now && jobDate <= weekFromNow;
  };

  // Group and sort jobs
  const groupedJobs = useMemo(() => {
    let jobs = [...bookings];

    // Filter by search term
    if (searchTerm.trim()) {
      const term = searchTerm.toLowerCase();
      jobs = jobs.filter(job =>
        job.customer_name?.toLowerCase().includes(term) ||
        job.service?.toLowerCase().includes(term) ||
        job.service_type?.toLowerCase().includes(term) ||
        job.phone?.includes(term) ||
        job.email?.toLowerCase().includes(term) ||
        job.job_address?.toLowerCase().includes(term) ||
        job.address?.toLowerCase().includes(term)
      );
    }

    // Sort all jobs chronologically (earliest first)
    jobs.sort((a, b) => new Date(a.appointment_time) - new Date(b.appointment_time));

    // Group by day
    const today = jobs.filter(j => isToday(j.appointment_time) && j.status !== 'completed' && j.status !== 'cancelled');
    const tomorrow = jobs.filter(j => isTomorrow(j.appointment_time) && j.status !== 'completed' && j.status !== 'cancelled');
    const thisWeek = jobs.filter(j => 
      !isToday(j.appointment_time) && 
      !isTomorrow(j.appointment_time) && 
      isThisWeek(j.appointment_time) &&
      j.status !== 'completed' && 
      j.status !== 'cancelled'
    );
    const completed = jobs.filter(j => j.status === 'completed');
    const cancelled = jobs.filter(j => j.status === 'cancelled');

    return { today, tomorrow, thisWeek, completed, cancelled };
  }, [bookings, searchTerm]);

  const stats = useMemo(() => {
    const total = bookings.length;
    const todayCount = bookings.filter(j => isToday(j.appointment_time) && j.status !== 'completed' && j.status !== 'cancelled').length;
    const upcoming = bookings.filter(j => new Date(j.appointment_time) > new Date() && j.status !== 'completed' && j.status !== 'cancelled').length;
    const completed = bookings.filter(j => j.status === 'completed').length;

    return { total, todayCount, upcoming, completed };
  }, [bookings]);

  const renderJobCard = (job) => {
    const timeStatus = getJobTimeStatus(job.appointment_time);
    
    return (
      <div 
        key={job.id} 
        className={`job-card status-${job.status} time-${timeStatus}`}
        onClick={() => setSelectedJobId(job.id)}
      >
        <div className="job-card-indicator"></div>
        <div className="job-card-content">
          <div className="job-header">
            <div className="job-title">
              <h3>{job.customer_name}</h3>
              <span className={`badge ${getStatusBadgeClass(job.status)}`}>
                {job.status}
              </span>
            </div>
            <div className={`job-time-badge time-${timeStatus}`}>
              <i className="fas fa-clock"></i>
              {new Date(job.appointment_time).toLocaleTimeString('en-US', { 
                hour: '2-digit', 
                minute: '2-digit'
              })}
              {timeStatus === 'now' && <span className="pulse-dot"></span>}
            </div>
          </div>
          
          {/* Address displayed prominently */}
          {(job.job_address || job.address) && (
            <div className="job-address-row">
              <i className="fas fa-map-marker-alt"></i>
              <span>{job.job_address || job.address}{job.eircode ? ` (${job.eircode})` : ''}</span>
            </div>
          )}
          
          <div className="job-details">
            <div className="job-detail">
              <i className="fas fa-wrench"></i>
              <span>{job.service_type || job.service || 'No service specified'}</span>
            </div>
            <div className="job-detail">
              <i className="fas fa-phone"></i>
              <span>{job.phone || job.phone_number || 'No phone'}</span>
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="jobs-tab">
      {/* Controls */}
      <div className="jobs-controls">
        <div className="search-box">
          <i className="fas fa-search"></i>
          <input
            type="text"
            placeholder="Search jobs..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        
        {/* Compact Stats Badges */}
        <div className="stats-badges">
          <div className="stats-badge stats-today">
            <span className="badge-value">{stats.todayCount}</span>
            <span className="badge-label">Today</span>
          </div>
          <div className="stats-badge stats-upcoming">
            <span className="badge-value">{stats.upcoming}</span>
            <span className="badge-label">Upcoming</span>
          </div>
          <div className="stats-badge stats-completed">
            <span className="badge-value">{stats.completed}</span>
            <span className="badge-label">Completed</span>
          </div>
          <div className="stats-badge stats-total">
            <span className="badge-value">{stats.total}</span>
            <span className="badge-label">Total Jobs</span>
          </div>
        </div>
        
        <button className="btn btn-primary" onClick={() => setShowAddModal(true)}>
          <i className="fas fa-plus"></i> Add Job
        </button>
      </div>

      {/* Jobs List Grouped by Day */}
      <div className="jobs-grouped">
        {/* Today's Jobs */}
        {groupedJobs.today.length > 0 && (
          <div className="jobs-group">
            <div className="group-header today">
              <h3>Today</h3>
              <span className="group-count">{groupedJobs.today.length} jobs</span>
            </div>
            <div className="jobs-list">
              {groupedJobs.today.map(renderJobCard)}
            </div>
          </div>
        )}

        {/* Tomorrow's Jobs */}
        {groupedJobs.tomorrow.length > 0 && (
          <div className="jobs-group">
            <div className="group-header tomorrow">
              <h3>Tomorrow</h3>
              <span className="group-count">{groupedJobs.tomorrow.length} jobs</span>
            </div>
            <div className="jobs-list">
              {groupedJobs.tomorrow.map(renderJobCard)}
            </div>
          </div>
        )}

        {/* This Week */}
        {groupedJobs.thisWeek.length > 0 && (
          <div className="jobs-group">
            <div className="group-header week">
              <h3>This Week</h3>
              <span className="group-count">{groupedJobs.thisWeek.length} jobs</span>
            </div>
            <div className="jobs-list">
              {groupedJobs.thisWeek.map(job => (
                <div 
                  key={job.id} 
                  className={`job-card status-${job.status}`}
                  onClick={() => setSelectedJobId(job.id)}
                >
                  <div className="job-card-indicator"></div>
                  <div className="job-card-content">
                    <div className="job-header">
                      <div className="job-title">
                        <h3>{job.customer_name}</h3>
                        <span className={`badge ${getStatusBadgeClass(job.status)}`}>
                          {job.status}
                        </span>
                      </div>
                      <div className="job-date">
                        <i className="fas fa-calendar"></i>
                        {formatDateTime(job.appointment_time)}
                      </div>
                    </div>
                    
                    {(job.job_address || job.address) && (
                      <div className="job-address-row">
                        <i className="fas fa-map-marker-alt"></i>
                        <span>{job.job_address || job.address}</span>
                      </div>
                    )}
                    
                    <div className="job-details">
                      <div className="job-detail">
                        <i className="fas fa-wrench"></i>
                        <span>{job.service_type || job.service || 'No service'}</span>
                      </div>
                      <div className="job-detail">
                        <i className="fas fa-phone"></i>
                        <span>{job.phone || 'No phone'}</span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Completed Jobs (collapsed) */}
        {groupedJobs.completed.length > 0 && (
          <details className="jobs-group collapsed-group">
            <summary className="group-header completed">
              <h3>Completed</h3>
              <span className="group-count">{groupedJobs.completed.length} jobs</span>
            </summary>
            <div className="jobs-list">
              {groupedJobs.completed.slice(0, 10).map(job => (
                <div 
                  key={job.id} 
                  className="job-card status-completed"
                  onClick={() => setSelectedJobId(job.id)}
                >
                  <div className="job-card-indicator"></div>
                  <div className="job-card-content">
                    <div className="job-header">
                      <div className="job-title">
                        <h3>{job.customer_name}</h3>
                        <span className="badge badge-success">{job.status}</span>
                      </div>
                      <div className="job-date">
                        <i className="fas fa-calendar"></i>
                        {formatDateTime(job.appointment_time)}
                      </div>
                    </div>
                    <div className="job-details">
                      <div className="job-detail">
                        <i className="fas fa-wrench"></i>
                        <span>{job.service_type || job.service || 'No service'}</span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </details>
        )}

        {/* Empty State */}
        {groupedJobs.today.length === 0 && 
         groupedJobs.tomorrow.length === 0 && 
         groupedJobs.thisWeek.length === 0 && 
         groupedJobs.completed.length === 0 && (
          <div className="empty-state">
            <div className="empty-state-icon">📋</div>
            <p>No jobs found</p>
          </div>
        )}
      </div>

      {/* Modals */}
      <AddJobModal 
        isOpen={showAddModal} 
        onClose={() => setShowAddModal(false)} 
      />
      <JobDetailModal
        isOpen={!!selectedJobId}
        onClose={() => setSelectedJobId(null)}
        jobId={selectedJobId}
      />
    </div>
  );
}

export default JobsTab;
