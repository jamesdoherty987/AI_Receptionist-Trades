import { useState, useEffect, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useLocation, useNavigate } from 'react-router-dom';
import { getNotifications } from '../services/api';
import './NotificationBell.css';

function NotificationBell({ onNavigate }) {
  const [isOpen, setIsOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const [seenIds, setSeenIds] = useState(() => {
    try {
      const stored = localStorage.getItem('seenNotifications');
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });
  const dropdownRef = useRef(null);
  const queryClient = useQueryClient();

  const { data } = useQuery({
    queryKey: ['notifications'],
    queryFn: async () => {
      const response = await getNotifications();
      return response.data;
    },
    refetchInterval: 30000, // Poll every 30 seconds
    staleTime: 10000,
  });

  const notifications = data?.notifications || [];
  const unseenCount = notifications.filter(n => !seenIds.includes(n.id)).length;

  // Close dropdown when clicking/tapping outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('touchstart', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('touchstart', handleClickOutside);
    };
  }, []);

  const handleOpen = () => {
    setIsOpen(!isOpen);
    if (!isOpen && notifications.length > 0) {
      // Mark all as seen when opening
      const allIds = notifications.map(n => n.id);
      const newSeenIds = [...new Set([...seenIds, ...allIds])].slice(-100); // Keep last 100
      setSeenIds(newSeenIds);
      localStorage.setItem('seenNotifications', JSON.stringify(newSeenIds));
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
      case 'cancelled': return 'fa-times-circle';
      case 'completed': return 'fa-check-circle';
      case 'rescheduled': return 'fa-calendar-alt';
      case 'time_off_request': return 'fa-umbrella-beach';
      case 'new_message': return 'fa-comment-dots';
      default: return 'fa-calendar-plus';
    }
  };

  const getIconClass = (type) => {
    switch (type) {
      case 'cancelled': return 'notif-cancelled';
      case 'completed': return 'notif-completed';
      case 'rescheduled': return 'notif-rescheduled';
      case 'time_off_request': return 'notif-time-off';
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
                onClick={() => queryClient.invalidateQueries({ queryKey: ['notifications'] })}
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
                <p>No recent activity</p>
              </div>
            ) : (
              notifications.map(notif => (
                <div
                  key={notif.id}
                  className={`notification-item clickable ${getIconClass(notif.type)}`}
                  onClick={() => {
                    if (location.pathname !== '/dashboard') {
                      navigate('/dashboard', { state: { notificationNav: notif } });
                    } else if (onNavigate) {
                      onNavigate(notif);
                    }
                    setIsOpen(false);
                  }}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      if (location.pathname !== '/dashboard') {
                        navigate('/dashboard', { state: { notificationNav: notif } });
                      } else if (onNavigate) {
                        onNavigate(notif);
                      }
                      setIsOpen(false);
                    }
                  }}
                >
                  <div className="notification-icon">
                    <i className={`fas ${getIcon(notif.type)}`}></i>
                  </div>
                  <div className="notification-content">
                    <p className="notification-message">{notif.message}</p>
                    <span className="notification-meta">
                      {notif.client_name ? `${notif.client_name} • ` : ''}{formatTime(notif.created_at)}
                    </span>
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

export default NotificationBell;
