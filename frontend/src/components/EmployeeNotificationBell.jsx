import { useState, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getEmployeeNotifications, acceptEmergencyJob } from '../services/api';
import './NotificationBell.css';

function EmployeeNotificationBell({ onNavigate, userKey }) {
  const [isOpen, setIsOpen] = useState(false);
  const storageKey = `employeeSeenNotifications_${userKey || 'default'}`;
  const [seenIds, setSeenIds] = useState(() => {
    try {
      const stored = localStorage.getItem(storageKey);
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });
  const dropdownRef = useRef(null);
  const queryClient = useQueryClient();

  // Re-sync seenIds when userKey changes (e.g. after login)
  useEffect(() => {
    try {
      const stored = localStorage.getItem(storageKey);
      setSeenIds(stored ? JSON.parse(stored) : []);
    } catch {
      setSeenIds([]);
    }
  }, [storageKey]);

  const { data } = useQuery({
    queryKey: ['employee-notifications'],
    queryFn: async () => {
      const response = await getEmployeeNotifications();
      return response.data;
    },
    refetchInterval: 30000,
  });

  const notifications = data?.notifications || [];
  const unseenCount = notifications.filter(n => !seenIds.includes(n.id)).length;
  const hasEmergency = notifications.some(n => n.type === 'emergency_job' && n.metadata?.booking_id);

  const [acceptingId, setAcceptingId] = useState(null);
  const [acceptedIds, setAcceptedIds] = useState(new Set());
  const [acceptErrors, setAcceptErrors] = useState({});

  const acceptMutation = useMutation({
    mutationFn: (bookingId) => acceptEmergencyJob(bookingId),
    onMutate: (bookingId) => setAcceptingId(bookingId),
    onSuccess: (_, bookingId) => {
      setAcceptedIds(prev => new Set([...prev, bookingId]));
      setAcceptingId(null);
      queryClient.invalidateQueries({ queryKey: ['employee-notifications'] });
      queryClient.invalidateQueries({ queryKey: ['employee-dashboard'] });
    },
    onError: (error, bookingId) => {
      setAcceptErrors(prev => ({ ...prev, [bookingId]: error?.response?.data?.error || 'Failed' }));
      setAcceptingId(null);
    },
  });

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
      const allIds = notifications.map(n => n.id);
      // Don't mark emergency notifications as seen until accepted
      const nonEmergencyIds = notifications.filter(n => n.type !== 'emergency_job').map(n => n.id);
      const newSeenIds = [...new Set([...seenIds, ...nonEmergencyIds])].slice(-100);
      setSeenIds(newSeenIds);
      localStorage.setItem(storageKey, JSON.stringify(newSeenIds));
    }
  };

  const handleAcceptEmergency = (e, bookingId) => {
    e.stopPropagation();
    if (acceptingId || acceptedIds.has(bookingId)) return;
    acceptMutation.mutate(bookingId);
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
      case 'emergency_job': return 'fa-exclamation-triangle';
      case 'emergency_accepted': return 'fa-check-double';
      case 'job_assigned': return 'fa-briefcase';
      case 'time_off_approved': return 'fa-check-circle';
      case 'time_off_denied': return 'fa-times-circle';
      case 'new_message': return 'fa-comment-dots';
      default: return 'fa-bell';
    }
  };

  const getIconClass = (type) => {
    switch (type) {
      case 'emergency_job': return 'notif-emergency';
      case 'emergency_accepted': return 'notif-completed';
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
        className={`notification-bell-btn ${unseenCount > 0 ? 'has-unseen' : ''} ${hasEmergency ? 'has-emergency' : ''}`}
        onClick={handleOpen}
        aria-label={`Notifications${unseenCount > 0 ? `, ${unseenCount} unread` : ''}${hasEmergency ? ', emergency job pending' : ''}`}
      >
        <i className={`fas ${hasEmergency ? 'fa-exclamation-triangle' : 'fa-bell'}`}></i>
        {unseenCount > 0 && (
          <span className={`notification-badge ${hasEmergency ? 'emergency-badge' : ''}`}>
            {unseenCount > 9 ? '9+' : unseenCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="notification-dropdown">
          <div className="notification-header">
            <span>Notifications</span>
            <div className="notification-header-actions">
              {notifications.length > 0 && (
                <button
                  className="refresh-btn"
                  onClick={() => queryClient.invalidateQueries({ queryKey: ['employee-notifications'] })}
                  aria-label="Refresh notifications"
                >
                  <i className="fas fa-sync-alt"></i>
                </button>
              )}
              <button
                className="notification-close-btn"
                onClick={() => setIsOpen(false)}
                aria-label="Close notifications"
              >
                <i className="fas fa-times"></i>
              </button>
            </div>
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
                  className={`notification-item ${notif.type !== 'emergency_job' ? 'clickable' : ''} ${getIconClass(notif.type)}`}
                  onClick={() => {
                    if (notif.type !== 'emergency_job' && onNavigate) {
                      onNavigate(notif);
                      setIsOpen(false);
                    }
                  }}
                  role={notif.type !== 'emergency_job' ? 'button' : undefined}
                  tabIndex={notif.type !== 'emergency_job' ? 0 : undefined}
                >
                  <div className="notification-icon">
                    <i className={`fas ${getIcon(notif.type)}`}></i>
                  </div>
                  <div className="notification-content">
                    <p className="notification-message">{notif.message}</p>
                    {notif.type === 'emergency_job' && notif.metadata?.booking_id && (
                      <button
                        className="emergency-accept-btn"
                        onClick={(e) => handleAcceptEmergency(e, notif.metadata.booking_id)}
                        disabled={acceptingId === notif.metadata.booking_id || acceptedIds.has(notif.metadata.booking_id)}
                      >
                        {acceptingId === notif.metadata.booking_id ? (
                          <><i className="fas fa-spinner fa-spin"></i> Accepting...</>
                        ) : acceptedIds.has(notif.metadata.booking_id) ? (
                          <><i className="fas fa-check"></i> Accepted</>
                        ) : acceptErrors[notif.metadata.booking_id] ? (
                          <>{acceptErrors[notif.metadata.booking_id]}</>
                        ) : (
                          <><i className="fas fa-check"></i> Accept Job</>
                        )}
                      </button>
                    )}
                    <span className="notification-meta">{formatTime(notif.created_at)}</span>
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

export default EmployeeNotificationBell;
