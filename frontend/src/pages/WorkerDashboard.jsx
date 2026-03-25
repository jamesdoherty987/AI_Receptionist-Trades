import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../context/AuthContext';
import { Link, useNavigate } from 'react-router-dom';
import { getWorkerDashboard } from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';
import { formatPhone, getStatusBadgeClass } from '../utils/helpers';
import './WorkerDashboard.css';

function WorkerDashboard() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('jobs');

  const { data, isLoading } = useQuery({
    queryKey: ['worker-dashboard'],
    queryFn: async () => {
      const response = await getWorkerDashboard();
      return response.data;
    },
  });

  const handleLogout = async () => {
    await logout();
    navigate('/worker/login');
  };

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

  const now = new Date();
  const upcomingJobs = jobs.filter(j => j.status !== 'completed' && j.status !== 'cancelled');
  const completedJobs = jobs.filter(j => j.status === 'completed');

  const tabs = [
    { id: 'jobs', label: 'My Jobs', icon: 'fas fa-briefcase' },
    { id: 'schedule', label: 'Schedule', icon: 'fas fa-calendar' },
    { id: 'profile', label: 'Profile', icon: 'fas fa-user' },
  ];

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
              <i className="fas fa-sign-out-alt"></i>
              Sign Out
            </button>
          </div>
        </div>
      </header>

      <main className="worker-main">
        <div className="worker-container">
          <div className="worker-tabs">
            {tabs.map(tab => (
              <button
                key={tab.id}
                className={`worker-tab ${activeTab === tab.id ? 'active' : ''}`}
                onClick={() => setActiveTab(tab.id)}
              >
                <i className={tab.icon}></i>
                {tab.label}
              </button>
            ))}
          </div>

          <div className="worker-tab-content">
            {activeTab === 'jobs' && (
              <div className="worker-jobs">
                <h2>Upcoming Jobs ({upcomingJobs.length})</h2>
                {upcomingJobs.length === 0 ? (
                  <div className="worker-empty">
                    <i className="fas fa-calendar-check"></i>
                    <p>No upcoming jobs</p>
                  </div>
                ) : (
                  <div className="worker-job-list">
                    {upcomingJobs.map(job => (
                      <div key={job.id} className="worker-job-card">
                        <div className="worker-job-header">
                          <span className={`worker-job-status ${getStatusBadgeClass(job.status)}`}>
                            {job.status}
                          </span>
                          <span className="worker-job-date">
                            {new Date(job.appointment_time).toLocaleDateString('en-IE', {
                              weekday: 'short', month: 'short', day: 'numeric'
                            })}
                          </span>
                        </div>
                        <div className="worker-job-body">
                          <h3>{job.service_type || 'Job'}</h3>
                          <p className="worker-job-client">
                            <i className="fas fa-user"></i>
                            {job.client_name || 'No client'}
                          </p>
                          <p className="worker-job-time">
                            <i className="fas fa-clock"></i>
                            {new Date(job.appointment_time).toLocaleTimeString('en-IE', {
                              hour: '2-digit', minute: '2-digit'
                            })}
                          </p>
                          {job.address && (
                            <p className="worker-job-address">
                              <i className="fas fa-map-marker-alt"></i>
                              {job.address}
                            </p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {completedJobs.length > 0 && (
                  <>
                    <h2 style={{ marginTop: '2rem' }}>Completed ({completedJobs.length})</h2>
                    <div className="worker-job-list">
                      {completedJobs.slice(0, 10).map(job => (
                        <div key={job.id} className="worker-job-card completed">
                          <div className="worker-job-header">
                            <span className="worker-job-status badge-completed">completed</span>
                            <span className="worker-job-date">
                              {new Date(job.appointment_time).toLocaleDateString('en-IE', {
                                weekday: 'short', month: 'short', day: 'numeric'
                              })}
                            </span>
                          </div>
                          <div className="worker-job-body">
                            <h3>{job.service_type || 'Job'}</h3>
                            <p className="worker-job-client">
                              <i className="fas fa-user"></i>
                              {job.client_name || 'No client'}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </div>
            )}

            {activeTab === 'schedule' && (
              <div className="worker-schedule">
                <h2>My Schedule</h2>
                {schedule.length === 0 ? (
                  <div className="worker-empty">
                    <i className="fas fa-calendar"></i>
                    <p>No scheduled appointments</p>
                  </div>
                ) : (
                  <div className="worker-schedule-list">
                    {schedule.map((item, idx) => (
                      <div key={idx} className="worker-schedule-item">
                        <div className="worker-schedule-date">
                          <span className="schedule-day">
                            {new Date(item.appointment_time).toLocaleDateString('en-IE', { weekday: 'short' })}
                          </span>
                          <span className="schedule-date-num">
                            {new Date(item.appointment_time).getDate()}
                          </span>
                          <span className="schedule-month">
                            {new Date(item.appointment_time).toLocaleDateString('en-IE', { month: 'short' })}
                          </span>
                        </div>
                        <div className="worker-schedule-details">
                          <h3>{item.service_type || 'Job'}</h3>
                          <p>
                            <i className="fas fa-clock"></i>
                            {new Date(item.appointment_time).toLocaleTimeString('en-IE', {
                              hour: '2-digit', minute: '2-digit'
                            })}
                          </p>
                          {item.client_name && (
                            <p><i className="fas fa-user"></i> {item.client_name}</p>
                          )}
                          {item.address && (
                            <p><i className="fas fa-map-marker-alt"></i> {item.address}</p>
                          )}
                        </div>
                        <span className={`worker-job-status ${getStatusBadgeClass(item.status)}`}>
                          {item.status}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {activeTab === 'profile' && (
              <div className="worker-profile">
                <h2>My Profile</h2>
                <div className="worker-profile-card">
                  <div className="worker-profile-avatar">
                    {worker.image_url ? (
                      <img src={worker.image_url} alt={worker.name} />
                    ) : (
                      <div className="worker-avatar-placeholder">
                        {worker.name?.charAt(0)?.toUpperCase() || 'W'}
                      </div>
                    )}
                  </div>
                  <div className="worker-profile-info">
                    <div className="worker-profile-row">
                      <label>Name</label>
                      <span>{worker.name}</span>
                    </div>
                    <div className="worker-profile-row">
                      <label>Email</label>
                      <span>{worker.email}</span>
                    </div>
                    <div className="worker-profile-row">
                      <label>Phone</label>
                      <span>{worker.phone ? formatPhone(worker.phone) : 'Not set'}</span>
                    </div>
                    <div className="worker-profile-row">
                      <label>Specialty</label>
                      <span>{worker.trade_specialty || 'Not set'}</span>
                    </div>
                    <div className="worker-profile-row">
                      <label>Status</label>
                      <span className={`worker-job-status ${worker.status === 'active' ? 'badge-confirmed' : 'badge-pending'}`}>
                        {worker.status || 'active'}
                      </span>
                    </div>
                  </div>
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
