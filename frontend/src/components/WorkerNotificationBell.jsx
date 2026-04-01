import { useState, useEffect, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getWorkerNotifications } from '../services/api';
import './NotificationBell.css';

function WorkerNotificationBell({ onNavigate }) {
  const [isOpen, setIsOpen] = useState(false);
  const [seenIds, setSeenIds] = useState(() => {
    try {
      const stored = localStorage.getItem('workerSeenNotifications');
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });
  const dropdownRef = useRef(null);
  const queryClient = useQueryClient();

  const { data } = useQuery({
    queryKey: ['worker-notifications'],
    queryFn: async () => {
      const response = await getWorkerNotifications();
      return response.data;
    },
    refetchInterval: 30000,
    staleTime: 10000,
  });

  const notifications = data?.notifications || [];
  const unseenCount = notifications.filter(n => !seenIds.includes(n.id)).length;

  // Close dropdown when clicking outside
  // Use mousedown only — touchstart + mousedown causes double-firing on mobile
  // which races with onClick and prevents the dropdown from toggling properly
  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const handleOpen = () => {
    setIsOpen(!isOpen);
    if (!isOpen && notifications.length > 0) {
      const allIds = notifications.map(n => n.id);
      const newSeenIds = [...new Set([...seenIds, ...allIds])].slice(-100);
      setSeenIds(newSeenIds);
      localStorage.setItem('workerSeenNotifications', JSON.stringify(newSeenIds));
    }
  };

  const formatTime = (isoString) => {
    if (!isoString) return '';
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return date.toLocaleDateString();
  };

  const getIcon = (type) => {
    switch (type) {
      case 'job_assigned': return 'fa-briefcase';
      case 'time_off_approved': return 'fa-check-circle';
      case 'time_off_denied': return 'fa-times-circle';
      case 'new_message': return 'fa-comment-dots';
      default: return 'fa-bell';
    }
  };

  const getIconClass = (type) => {
    switch (type) {
      case 'job_assigned': return 'notif-new';
      case 'time_off_approved': return 'notif-completed';
      case 'time_off_denied': return 'notif-cancelled';
      case 'new_message': return 'notif-new';
      default: return 'notif-new';
    }
  };

  return (
    <div className="notification-bell-container" ref={dropdownRef}>
      <button
        className={`notification-bell-btn ${unseenCount > 0 ? 'has-unseen' : ''}`}
        onClick={handleOpen}
        aria-label={`Notifications${unseenCount > 0 ? `, ${unseenCount} unread` : ''}`}
      >
        <i className="fas fa-bell"></i>
        {unseenCount > 0 && (
          <span className="notification-badge">{unseenCount > 9 ? '9+' : unseenCount}</span>
        )}
      </button>

      {isOpen && (
        <div className="notification-dropdown">
          <div className="notification-header">
            <span>Notifications</span>
            {notifications.length > 0 && (
              <button
                className="refresh-btn"
                onClick={() => queryClient.invalidateQueries({ queryKey: ['worker-notifications'] })}
                aria-label="Refresh notifications"
              >
                <i className="fas fa-sync-alt"></i>
              </button>
            )}
          </div>

          <div className="notification-list">
            {notifications.length === 0 ? (
              <div className="notification-empty">
                <i className="fas fa-inbox"></i>
                <p>No recent notifications</p>
              </div>
            ) : (
              notifications.map(notif => (
                <div
                  key={notif.id}
                  className={`notification-item clickable ${getIconClass(notif.type)}`}
                  onClick={() => {
                    if (onNavigate) onNavigate(notif);
                    setIsOpen(false);
                  }}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      if (onNavigate) onNavigate(notif);
                      setIsOpen(false);
                    }
                  }}
                >
                  <div className="notification-icon">
                    <i className={`fas ${getIcon(notif.type)}`}></i>
                  </div>
                  <div className="notification-content">
                    <p className="notification-message">{notif.message}</p>
                    <span className="notification-meta">{formatTime(notif.created_at)}</span>
                  </div>
                  <div className="notification-arrow">
                    <i className="fas fa-chevron-right"></i>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default WorkerNotificationBell;
