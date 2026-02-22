import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getBookings, getWorkers } from '../../services/api';
import { getStatusBadgeClass } from '../../utils/helpers';
import LoadingSpinner from '../LoadingSpinner';
import JobDetailModal from '../modals/JobDetailModal';
import './CalendarTab.css';

// Color palette for workers
const WORKER_COLORS = [
  '#3b82f6', // blue
  '#10b981', // green
  '#f59e0b', // amber
  '#ef4444', // red
  '#8b5cf6', // purple
  '#ec4899', // pink
  '#06b6d4', // cyan
  '#f97316', // orange
  '#6366f1', // indigo
  '#14b8a6', // teal
];

// Format time range for display (e.g., "8am - 10am" or "Full Day")
const formatTimeRange = (appointmentTime, durationMinutes) => {
  if (!appointmentTime) return '';
  
  const start = new Date(appointmentTime);
  const startHour = start.getHours();
  const startMin = start.getMinutes();
  
  // Full day job (8+ hours)
  if (durationMinutes >= 480) {
    return 'Full Day';
  }
  
  // Calculate end time
  const end = new Date(start.getTime() + (durationMinutes || 60) * 60000);
  const endHour = end.getHours();
  const endMin = end.getMinutes();
  
  const formatHour = (h, m) => {
    const hour12 = h % 12 || 12;
    const ampm = h < 12 ? 'am' : 'pm';
    return m > 0 ? `${hour12}:${String(m).padStart(2, '0')}${ampm}` : `${hour12}${ampm}`;
  };
  
  return `${formatHour(startHour, startMin)} - ${formatHour(endHour, endMin)}`;
};

function CalendarTab() {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [selectedDate, setSelectedDate] = useState(null);
  const [selectedJobId, setSelectedJobId] = useState(null);
  const [selectedWorkerId, setSelectedWorkerId] = useState(null);
  const [viewMode, setViewMode] = useState('month'); // 'month' or 'week'
  
  const { data: bookings, isLoading: bookingsLoading } = useQuery({
    queryKey: ['bookings'],
    queryFn: async () => {
      const response = await getBookings();
      return response.data;
    },
  });

  const { data: workers, isLoading: workersLoading } = useQuery({
    queryKey: ['workers'],
    queryFn: async () => {
      const response = await getWorkers();
      return response.data;
    },
  });

  // Create worker color map
  const workerColorMap = useMemo(() => {
    const map = {};
    (workers || []).forEach((worker, index) => {
      map[worker.id] = WORKER_COLORS[index % WORKER_COLORS.length];
    });
    return map;
  }, [workers]);

  // Get worker color for a booking
  const getWorkerColor = (booking) => {
    const assignedIds = booking.assigned_worker_ids || [];
    if (assignedIds.length > 0) {
      return workerColorMap[assignedIds[0]] || '#94a3b8';
    }
    return '#94a3b8';
  };

  // Filter bookings by selected worker
  const filteredBookings = useMemo(() => {
    if (!bookings) return [];
    if (!selectedWorkerId) return bookings;
    return bookings.filter(booking => {
      const assignedIds = booking.assigned_worker_ids || [];
      return assignedIds.includes(selectedWorkerId) || assignedIds.includes(String(selectedWorkerId));
    });
  }, [bookings, selectedWorkerId]);

  const isLoading = bookingsLoading || workersLoading;

  // Get week data for week view
  const weekData = useMemo(() => {
    const startOfWeek = new Date(currentDate);
    const day = startOfWeek.getDay();
    startOfWeek.setDate(startOfWeek.getDate() - day); // Go to Sunday
    
    const days = [];
    for (let i = 0; i < 7; i++) {
      const date = new Date(startOfWeek);
      date.setDate(startOfWeek.getDate() + i);
      days.push(date);
    }
    return days;
  }, [currentDate]);

  // Get calendar data for month view
  const calendarData = useMemo(() => {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    
    const firstDay = new Date(year, month, 1);
    const startingDay = firstDay.getDay();
    const lastDay = new Date(year, month + 1, 0);
    const totalDays = lastDay.getDate();
    const prevMonth = new Date(year, month, 0);
    const prevMonthDays = prevMonth.getDate();
    
    const days = [];
    
    for (let i = startingDay - 1; i >= 0; i--) {
      days.push({
        date: new Date(year, month - 1, prevMonthDays - i),
        isCurrentMonth: false,
        day: prevMonthDays - i
      });
    }
    
    for (let i = 1; i <= totalDays; i++) {
      days.push({
        date: new Date(year, month, i),
        isCurrentMonth: true,
        day: i
      });
    }
    
    const remaining = 42 - days.length;
    for (let i = 1; i <= remaining; i++) {
      days.push({
        date: new Date(year, month + 1, i),
        isCurrentMonth: false,
        day: i
      });
    }
    
    return days;
  }, [currentDate]);

  // Get events for a specific date
  const getEventsForDate = (date) => {
    if (!filteredBookings) return [];
    return filteredBookings.filter(booking => {
      const bookingDate = new Date(booking.appointment_time);
      return bookingDate.toDateString() === date.toDateString();
    }).sort((a, b) => new Date(a.appointment_time) - new Date(b.appointment_time));
  };

  // Get events for selected date
  const selectedDateEvents = useMemo(() => {
    if (!selectedDate || !filteredBookings) return [];
    return filteredBookings
      .filter(booking => {
        const bookingDate = new Date(booking.appointment_time);
        return bookingDate.toDateString() === selectedDate.toDateString();
      })
      .sort((a, b) => new Date(a.appointment_time) - new Date(b.appointment_time));
  }, [selectedDate, filteredBookings]);

  // Get worker name by ID (just name, no specialty)
  const getWorkerName = (workerId) => {
    const worker = (workers || []).find(w => w.id === workerId || w.id === Number(workerId));
    return worker?.name || 'Unknown';
  };

  // Navigation
  const goToPrev = () => {
    if (viewMode === 'week') {
      setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth(), currentDate.getDate() - 7));
    } else {
      setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() - 1, 1));
    }
  };

  const goToNext = () => {
    if (viewMode === 'week') {
      setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth(), currentDate.getDate() + 7));
    } else {
      setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 1));
    }
  };

  const goToToday = () => {
    const today = new Date();
    setCurrentDate(today);
    setSelectedDate(today);
  };

  const isToday = (date) => {
    const today = new Date();
    return date.toDateString() === today.toDateString();
  };

  const isSelected = (date) => {
    return selectedDate && date.toDateString() === selectedDate.toDateString();
  };

  const monthNames = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];

  const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  
  // Time slots for week view (6am to 8pm)
  const timeSlots = [];
  for (let h = 6; h <= 20; h++) {
    timeSlots.push(h);
  }

  // Get header text based on view mode
  const getHeaderText = () => {
    if (viewMode === 'week') {
      const start = weekData[0];
      const end = weekData[6];
      if (start.getMonth() === end.getMonth()) {
        return `${monthNames[start.getMonth()]} ${start.getDate()} - ${end.getDate()}, ${start.getFullYear()}`;
      }
      return `${monthNames[start.getMonth()]} ${start.getDate()} - ${monthNames[end.getMonth()]} ${end.getDate()}, ${end.getFullYear()}`;
    }
    return `${monthNames[currentDate.getMonth()]} ${currentDate.getFullYear()}`;
  };

  if (isLoading) {
    return <LoadingSpinner message="Loading calendar..." />;
  }

  return (
    <div className="calendar-tab">
      {/* Calendar Header */}
      <div className="calendar-header">
        <div className="calendar-nav">
          <button className="nav-btn" onClick={goToPrev}>
            <i className="fas fa-chevron-left"></i>
          </button>
          <h2 className="current-month">{getHeaderText()}</h2>
          <button className="nav-btn" onClick={goToNext}>
            <i className="fas fa-chevron-right"></i>
          </button>
        </div>
        <div className="calendar-actions">
          <div className="view-toggle">
            <button 
              className={`view-btn ${viewMode === 'month' ? 'active' : ''}`}
              onClick={() => setViewMode('month')}
            >
              <i className="fas fa-calendar-alt"></i> Month
            </button>
            <button 
              className={`view-btn ${viewMode === 'week' ? 'active' : ''}`}
              onClick={() => setViewMode('week')}
            >
              <i className="fas fa-calendar-week"></i> Week
            </button>
          </div>
          <div className="worker-filter">
            <select 
              value={selectedWorkerId || ''} 
              onChange={(e) => setSelectedWorkerId(e.target.value ? Number(e.target.value) : null)}
              className="worker-filter-select"
            >
              <option value="">All Workers</option>
              {(workers || []).map(worker => (
                <option key={worker.id} value={worker.id}>
                  {worker.name}
                </option>
              ))}
            </select>
          </div>
          <button className="today-btn" onClick={goToToday}>
            <i className="fas fa-calendar-day"></i> Today
          </button>
        </div>
      </div>

      {/* Worker Legend */}
      {workers && workers.length > 0 && (
        <div className="worker-legend">
          <span className="legend-label">Workers:</span>
          <div className="legend-items">
            {workers.map(worker => (
              <button
                key={worker.id}
                className={`legend-item ${selectedWorkerId === worker.id ? 'active' : ''}`}
                onClick={() => setSelectedWorkerId(selectedWorkerId === worker.id ? null : worker.id)}
                style={{ '--worker-color': workerColorMap[worker.id] }}
              >
                <span className="legend-dot" style={{ backgroundColor: workerColorMap[worker.id] }}></span>
                {worker.name}
              </button>
            ))}
            {selectedWorkerId && (
              <button className="legend-clear" onClick={() => setSelectedWorkerId(null)}>
                <i className="fas fa-times"></i> Clear
              </button>
            )}
          </div>
        </div>
      )}

      {viewMode === 'month' ? (
        /* Month View */
        <div className="calendar-main">
          <div className="calendar-grid-container">
            <div className="calendar-grid">
              {dayNames.map(day => (
                <div key={day} className="day-header">{day}</div>
              ))}
              
              {calendarData.map((dayData, index) => {
                const events = getEventsForDate(dayData.date);
                const hasEvents = events.length > 0;
                
                return (
                  <div
                    key={index}
                    className={`calendar-day ${!dayData.isCurrentMonth ? 'other-month' : ''} ${isToday(dayData.date) ? 'today' : ''} ${isSelected(dayData.date) ? 'selected' : ''} ${hasEvents ? 'has-events' : ''}`}
                    onClick={() => setSelectedDate(dayData.date)}
                  >
                    <span className="day-number">{dayData.day}</span>
                    {hasEvents && (
                      <div className="event-dots">
                        {events.slice(0, 3).map((event, i) => (
                          <span 
                            key={i} 
                            className="event-dot worker-colored"
                            style={{ backgroundColor: getWorkerColor(event) }}
                            title={`${event.customer_name || 'Customer'} - ${event.service_type || 'Service'}`}
                          ></span>
                        ))}
                        {events.length > 3 && <span className="more-events">+{events.length - 3}</span>}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Selected Day Events Panel */}
          <div className="events-panel">
            <div className="events-panel-header">
              <h3>
                {selectedDate 
                  ? selectedDate.toLocaleDateString('en-US', { 
                      weekday: 'long', 
                      month: 'long', 
                      day: 'numeric' 
                    })
                  : 'Select a day'
                }
              </h3>
              {selectedDate && (
                <span className="event-count">{selectedDateEvents.length} event{selectedDateEvents.length !== 1 ? 's' : ''}</span>
              )}
            </div>
            
            <div className="events-list">
              {!selectedDate ? (
                <div className="empty-events">
                  <i className="fas fa-hand-pointer"></i>
                  <p>Click on a day to see events</p>
                </div>
              ) : selectedDateEvents.length === 0 ? (
                <div className="empty-events">
                  <i className="fas fa-calendar-check"></i>
                  <p>No events on this day</p>
                </div>
              ) : (
                selectedDateEvents.map(event => (
                  <div 
                    key={event.id} 
                    className="event-card clickable"
                    onClick={() => setSelectedJobId(event.id)}
                    style={{ borderLeftColor: getWorkerColor(event) }}
                  >
                    <div className="event-time">
                      <span className="time-range">{formatTimeRange(event.appointment_time, event.duration_minutes)}</span>
                    </div>
                    <div className="event-info">
                      <div className="event-header">
                        <span className="event-customer">{event.customer_name || 'Customer'}</span>
                        <span className={`badge badge-sm ${getStatusBadgeClass(event.status)}`}>
                          {event.status}
                        </span>
                      </div>
                      <div className="event-service">
                        <i className="fas fa-wrench"></i>
                        {event.service_type || event.service || 'Service'}
                      </div>
                      {(event.assigned_worker_ids?.length > 0) && (
                        <div className="event-worker">
                          <span 
                            className="worker-indicator"
                            style={{ backgroundColor: getWorkerColor(event) }}
                          ></span>
                          {event.assigned_worker_ids.map(id => getWorkerName(id)).join(', ')}
                        </div>
                      )}
                      {(event.job_address || event.address) && (
                        <div className="event-location">
                          <i className="fas fa-map-marker-alt"></i>
                          {event.job_address || event.address}
                        </div>
                      )}
                    </div>
                    <div className="event-arrow">
                      <i className="fas fa-chevron-right"></i>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      ) : (
        /* Week View */
        <div className="week-view-container">
          <div className="week-grid">
            {/* Time column */}
            <div className="time-column">
              <div className="time-header"></div>
              {timeSlots.map(hour => (
                <div key={hour} className="time-slot-label">
                  {hour === 12 ? '12pm' : hour > 12 ? `${hour - 12}pm` : `${hour}am`}
                </div>
              ))}
            </div>
            
            {/* Day columns */}
            {weekData.map((date, dayIndex) => {
              const dayEvents = getEventsForDate(date);
              
              return (
                <div 
                  key={dayIndex} 
                  className={`day-column ${isToday(date) ? 'today' : ''}`}
                >
                  <div className="week-day-header" onClick={() => setSelectedDate(date)}>
                    <span className="week-day-name">{dayNames[date.getDay()]}</span>
                    <span className={`week-day-number ${isToday(date) ? 'today-number' : ''}`}>
                      {date.getDate()}
                    </span>
                  </div>
                  
                  <div className="day-slots">
                    {timeSlots.map(hour => (
                      <div key={hour} className="time-slot"></div>
                    ))}
                    
                    {/* Events positioned absolutely */}
                    {dayEvents.map(event => {
                      const eventTime = new Date(event.appointment_time);
                      const startHour = eventTime.getHours() + eventTime.getMinutes() / 60;
                      const duration = event.duration_minutes || 60;
                      const durationHours = duration / 60;
                      
                      // Full day jobs (8+ hours) - show from 6am to 8pm
                      const isFullDay = duration >= 480;
                      
                      // Calculate position (6am = 0, each hour = 50px)
                      let top, height;
                      if (isFullDay) {
                        // Full day spans entire visible area
                        top = 0;
                        height = timeSlots.length * 50; // Full height
                      } else {
                        // Clamp start hour to visible range (6am-8pm)
                        const visibleStart = Math.max(6, Math.min(startHour, 20));
                        const visibleEnd = Math.min(20, startHour + durationHours);
                        
                        top = (visibleStart - 6) * 50;
                        height = Math.max((visibleEnd - visibleStart) * 50, 25);
                        
                        // Skip if completely outside visible range
                        if (startHour >= 20 || startHour + durationHours <= 6) return null;
                      }
                      
                      return (
                        <div
                          key={event.id}
                          className={`week-event ${isFullDay ? 'full-day' : ''}`}
                          style={{
                            top: `${top}px`,
                            height: `${height}px`,
                            backgroundColor: getWorkerColor(event),
                            borderColor: getWorkerColor(event)
                          }}
                          onClick={() => setSelectedJobId(event.id)}
                          title={`${event.customer_name} - ${event.service_type || 'Service'}`}
                        >
                          <div className="week-event-time">
                            {formatTimeRange(event.appointment_time, event.duration_minutes)}
                          </div>
                          <div className="week-event-title">{event.customer_name}</div>
                          {height > 40 && (
                            <div className="week-event-service">{event.service_type || event.service}</div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
      
      {/* Job Detail Modal */}
      <JobDetailModal
        isOpen={!!selectedJobId}
        onClose={() => setSelectedJobId(null)}
        jobId={selectedJobId}
      />
    </div>
  );
}

export default CalendarTab;
