import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getBookings, getWorkers, getBusinessHours, getCompanyTimeOffRequests, getBusinessSettings } from '../../services/api';
import { getStatusBadgeClass, parseServerDate } from '../../utils/helpers';
import LoadingSpinner from '../LoadingSpinner';
import JobDetailModal from '../modals/JobDetailModal';
import './CalendarTab.css';
import './SharedDashboard.css';

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

// Convert duration_minutes to business days, matching backend duration_to_business_days().
// "1 week" (10080 mins) = daysPerWeek biz days (a work week).
const durationToBusinessDays = (durationMinutes, daysPerWeek = 5) => {
  if (durationMinutes <= 1440) return 1;
  const calendarDays = durationMinutes / 1440;
  // Week-based durations: 7 cal days = daysPerWeek biz days
  if (calendarDays >= 7 && Math.round(calendarDays) % 7 === 0) {
    const weeks = Math.round(calendarDays) / 7;
    return weeks * daysPerWeek;
  }
  // Sub-week multi-day: calendar days = business days
  return Math.ceil(calendarDays);
};

// Map day names from backend (days_open) to JS getDay() indices (0=Sun, 6=Sat)
const DAY_NAME_TO_JS_INDEX = {
  'Sunday': 0, 'Monday': 1, 'Tuesday': 2, 'Wednesday': 3,
  'Thursday': 4, 'Friday': 5, 'Saturday': 6,
};

// Calculate the business-day end date for multi-day jobs.
// openDayIndices: JS getDay() values the company is open (e.g. [1,2,3,4,5] for Mon-Fri).
// Falls back to Mon-Fri if not provided.
const getMultiDayJobEnd = (startDate, durationMinutes, openDayIndices, closingHour = 17) => {
  const daysPerWeek = openDayIndices ? openDayIndices.length : 5;
  const bizDaysNeeded = durationToBusinessDays(durationMinutes, daysPerWeek);
  const openSet = new Set(openDayIndices || [1, 2, 3, 4, 5]);
  let cur = new Date(startDate);
  cur.setHours(0, 0, 0, 0);
  let counted = 0;
  let lastBiz = new Date(cur);
  for (let i = 0; i < 365; i++) {
    if (openSet.has(cur.getDay())) {
      counted++;
      lastBiz = new Date(cur);
      if (counted >= bizDaysNeeded) break;
    }
    cur.setDate(cur.getDate() + 1);
  }
  lastBiz.setHours(closingHour, 0, 0, 0);
  return lastBiz;
};

// Format time range for display (e.g., "8am - 10am" or "Full Day" or "3 Days")
const formatTimeRange = (appointmentTime, durationMinutes) => {
  if (!appointmentTime) return '';
  
  const start = parseServerDate(appointmentTime);
  
  // DEBUG: Log timezone conversion to diagnose +1 hour issue
  if (typeof appointmentTime === 'string' && appointmentTime.includes('T')) {
    const rawDate = new Date(appointmentTime);
    if (rawDate.getHours() !== start.getHours()) {
      console.warn(`[TZ_DEBUG] Time mismatch! raw="${appointmentTime}" -> new Date().getHours()=${rawDate.getHours()}, parseServerDate().getHours()=${start.getHours()}, tzOffset=${rawDate.getTimezoneOffset()}min`);
    }
  }
  
  // Multi-day job (> 24 hours)
  if (durationMinutes > 1440) {
    const days = Math.round(durationMinutes / 1440);
    if (durationMinutes >= 10080) {
      const weeks = Math.round(durationMinutes / 10080);
      return `${weeks} Week${weeks > 1 ? 's' : ''}`;
    }
    return `${days} Day${days > 1 ? 's' : ''}`;
  }
  
  // Full day job (8+ hours up to 24 hours)
  if (durationMinutes >= 480) {
    return 'Full Day';
  }
  
  // Calculate end time
  const end = new Date(start.getTime() + (durationMinutes || 60) * 60000);
  
  const formatHour = (date) => {
    const h = date.getHours();
    const m = date.getMinutes();
    const hour12 = h % 12 || 12;
    const ampm = h < 12 ? 'am' : 'pm';
    return m > 0 ? `${hour12}:${String(m).padStart(2, '0')}${ampm}` : `${hour12}${ampm}`;
  };
  
  return `${formatHour(start)} - ${formatHour(end)}`;
};

function CalendarTab() {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [selectedDate, setSelectedDate] = useState(null);
  const [selectedJobId, setSelectedJobId] = useState(null);
  const [selectedWorkerId, setSelectedWorkerId] = useState(null);
  const [viewMode, setViewMode] = useState('month'); // 'month' or 'week'
  
  const { data: settings } = useQuery({
    queryKey: ['business-settings'],
    queryFn: async () => {
      const response = await getBusinessSettings();
      return response.data;
    },
  });

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

  const { data: businessHours } = useQuery({
    queryKey: ['businessHours'],
    queryFn: async () => {
      const response = await getBusinessHours();
      return response.data;
    },
  });

  // Fetch approved time-off for calendar display
  const { data: approvedTimeOff } = useQuery({
    queryKey: ['calendar-time-off'],
    queryFn: async () => {
      const response = await getCompanyTimeOffRequests('approved');
      return response.data?.requests || [];
    },
  });

  // Get business hours with fallbacks
  const openingHour = businessHours?.start_hour ?? businessHours?.start ?? 8;
  const closingHour = businessHours?.end_hour ?? businessHours?.end ?? 18;

  // Derive open day indices (JS getDay: 0=Sun..6=Sat) from settings
  const openDayIndices = useMemo(() => {
    const daysOpen = businessHours?.days_open;
    if (Array.isArray(daysOpen) && daysOpen.length > 0) {
      return daysOpen.map(name => DAY_NAME_TO_JS_INDEX[name]).filter(v => v !== undefined);
    }
    return [1, 2, 3, 4, 5]; // Mon-Fri default
  }, [businessHours]);

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

  // Get all worker colors for a booking (for multi-worker display)
  const getWorkerColors = (booking) => {
    const assignedIds = booking.assigned_worker_ids || [];
    if (assignedIds.length === 0) return ['#94a3b8'];
    return assignedIds.map(id => workerColorMap[id] || '#94a3b8');
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

  // Get events for a specific date (including multi-day jobs that span into this date)
  const getEventsForDate = (date) => {
    if (!filteredBookings) return [];
    const openSet = new Set(openDayIndices);
    return filteredBookings.filter(booking => {
      const bookingDate = parseServerDate(booking.appointment_time);
      // Job starts on this date
      if (bookingDate.toDateString() === date.toDateString()) return true;
      // Multi-day job: started before this date but duration extends into it
      const duration = booking.duration_minutes || 60;
      if (duration > 1440) {
        // Skip closed days — the job doesn't run on days the company is closed
        if (!openSet.has(date.getDay())) return false;
        const bookingEnd = getMultiDayJobEnd(bookingDate, duration, openDayIndices, closingHour);
        const dayStart = new Date(date.getFullYear(), date.getMonth(), date.getDate());
        if (bookingDate < dayStart && bookingEnd > dayStart) return true;
      }
      return false;
    }).sort((a, b) => parseServerDate(a.appointment_time) - parseServerDate(b.appointment_time));
  };

  // Get events for selected date (including multi-day continuations)
  const selectedDateEvents = useMemo(() => {
    if (!selectedDate || !filteredBookings) return [];
    const openSet = new Set(openDayIndices);
    return filteredBookings
      .filter(booking => {
        const bookingDate = parseServerDate(booking.appointment_time);
        if (bookingDate.toDateString() === selectedDate.toDateString()) return true;
        const duration = booking.duration_minutes || 60;
        if (duration > 1440) {
          // Skip closed days — the job doesn't run on days the company is closed
          if (!openSet.has(selectedDate.getDay())) return false;
          const bookingEnd = getMultiDayJobEnd(bookingDate, duration, openDayIndices, closingHour);
          const dayStart = new Date(selectedDate.getFullYear(), selectedDate.getMonth(), selectedDate.getDate());
          if (bookingDate < dayStart && bookingEnd > dayStart) return true;
        }
        return false;
      })
      .sort((a, b) => parseServerDate(a.appointment_time) - parseServerDate(b.appointment_time));
  }, [selectedDate, filteredBookings, openDayIndices, closingHour]);

  // Get time-off events for a specific date
  const getTimeOffForDate = (date) => {
    if (!approvedTimeOff) return [];
    const dateStr = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
    return approvedTimeOff.filter(to => {
      // Filter by selected worker if applicable
      if (selectedWorkerId && to.worker_id !== selectedWorkerId) return false;
      return dateStr >= to.start_date && dateStr <= to.end_date;
    });
  };

  // Time-off for selected date
  const selectedDateTimeOff = useMemo(() => {
    if (!selectedDate || !approvedTimeOff) return [];
    const dateStr = `${selectedDate.getFullYear()}-${String(selectedDate.getMonth() + 1).padStart(2, '0')}-${String(selectedDate.getDate()).padStart(2, '0')}`;
    return approvedTimeOff.filter(to => {
      if (selectedWorkerId && to.worker_id !== selectedWorkerId) return false;
      return dateStr >= to.start_date && dateStr <= to.end_date;
    });
  }, [selectedDate, approvedTimeOff, selectedWorkerId]);

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
  
  // Time slots for week view (based on business hours)
  const timeSlots = useMemo(() => {
    const slots = [];
    for (let h = openingHour; h <= closingHour; h++) {
      slots.push(h);
    }
    return slots;
  }, [openingHour, closingHour]);

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
      {/* Page Header */}
      <div className="tab-page-header">
        <h2 className="tab-page-title">Calendar</h2>
      </div>

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
            <i className="fas fa-calendar-day"></i>
            {selectedDate && !isToday(selectedDate)
              ? selectedDate.toLocaleDateString('en-IE', { weekday: 'short', day: 'numeric', month: 'short' })
              : 'Today'
            }
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
                const timeOff = getTimeOffForDate(dayData.date);
                const hasEvents = events.length > 0;
                const hasTimeOff = timeOff.length > 0;
                
                return (
                  <div
                    key={index}
                    className={`calendar-day ${!dayData.isCurrentMonth ? 'other-month' : ''} ${isToday(dayData.date) ? 'today' : ''} ${isSelected(dayData.date) ? 'selected' : ''} ${hasEvents ? 'has-events' : ''} ${hasTimeOff ? 'has-time-off' : ''}`}
                    onClick={() => setSelectedDate(dayData.date)}
                  >
                    <span className="day-number">{dayData.day}</span>
                    {hasTimeOff && (
                      <div className="time-off-indicator" title={timeOff.map(t => `${t.worker_name} - ${t.type}`).join(', ')}>
                        <i className="fas fa-umbrella-beach"></i>
                      </div>
                    )}
                    {hasEvents && (
                      <div className="event-dots">
                        {(() => {
                          const allDots = [];
                          for (const event of events.slice(0, 3)) {
                            const colors = getWorkerColors(event);
                            for (const [ci, color] of colors.entries()) {
                              allDots.push(
                                <span 
                                  key={`${event.id}-${ci}`} 
                                  className={`event-dot worker-colored${event.status === 'completed' ? ' completed' : ''}`}
                                  style={{ backgroundColor: event.status === 'completed' ? 'var(--success)' : color }}
                                  title={`${event.customer_name || 'Customer'} - ${event.service_type || 'Service'}`}
                                ></span>
                              );
                              if (allDots.length >= 6) break;
                            }
                            if (allDots.length >= 6) break;
                          }
                          return allDots;
                        })()}
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
                <span className="event-count">
                  {selectedDateEvents.length} event{selectedDateEvents.length !== 1 ? 's' : ''}
                  {selectedDateTimeOff.length > 0 && ` · ${selectedDateTimeOff.length} leave`}
                </span>
              )}
            </div>
            
            <div className="events-list">
              {!selectedDate ? (
                <div className="empty-events">
                  <i className="fas fa-hand-pointer"></i>
                  <p>Click on a day to see events</p>
                </div>
              ) : (selectedDateEvents.length === 0 && selectedDateTimeOff.length === 0) ? (
                <div className="empty-events">
                  <i className="fas fa-calendar-check"></i>
                  <p>No events on this day</p>
                </div>
              ) : (
                <>
                  {/* Time-off entries */}
                  {selectedDateTimeOff.map(to => (
                    <div key={`to-${to.id}`} className="event-card time-off-card">
                      <div className="time-off-icon">
                        <i className={`fas ${to.type === 'sick' ? 'fa-thermometer-half' : to.type === 'personal' ? 'fa-user' : 'fa-umbrella-beach'}`}></i>
                      </div>
                      <div className="event-info">
                        <div className="event-header">
                          <span className="event-customer">{to.worker_name}</span>
                          <span className="badge badge-sm time-off-badge">{to.type}</span>
                        </div>
                        <div className="event-service time-off-dates">
                          <i className="fas fa-calendar"></i>
                          {new Date(to.start_date + 'T00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                          {' — '}
                          {new Date(to.end_date + 'T00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                        </div>
                        {to.reason && <div className="event-location">{to.reason}</div>}
                      </div>
                    </div>
                  ))}
                  {/* Job events */}
                  {selectedDateEvents.map(event => {
                  const colors = event.status === 'completed' ? ['#22c55e'] : getWorkerColors(event);
                  return (
                    <div 
                      key={event.id} 
                      className={`event-card clickable${event.status === 'completed' ? ' completed' : ''}`}
                      onClick={() => setSelectedJobId(event.id)}
                      style={colors.length === 1 ? { borderLeftColor: colors[0] } : { borderLeftColor: 'transparent' }}
                    >
                      {colors.length > 1 && (
                        <div className="multi-worker-border" aria-hidden="true">
                          {colors.map((c, i) => (
                            <span key={i} style={{ background: c, flex: 1 }} />
                          ))}
                        </div>
                      )}
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
                        {(event.assigned_worker_ids?.length > 0) ? (
                          <div className="event-worker">
                            <span className="worker-indicators">
                              {getWorkerColors(event).map((c, ci) => (
                                <span key={ci} className="worker-indicator" style={{ backgroundColor: c }}></span>
                              ))}
                            </span>
                            {event.assigned_worker_ids.map(id => getWorkerName(id)).join(', ')}
                          </div>
                        ) : !['completed', 'paid', 'cancelled'].includes(event.status) && (
                          <div className="event-no-worker-warning">
                            <i className="fas fa-exclamation-triangle"></i> No worker assigned
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
                  );
                })}
                </>
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
              
              // Group overlapping events to position them side by side
              const getEventLayout = (events) => {
                const layouts = [];
                const columns = []; // Track which column each event is in
                
                // Sort events by start time
                const sortedEvents = [...events].sort((a, b) => 
                  parseServerDate(a.appointment_time) - parseServerDate(b.appointment_time)
                );
                
                sortedEvents.forEach(event => {
                  const eventStart = parseServerDate(event.appointment_time);
                  const duration = event.duration_minutes || 60;
                  const isFullDay = duration >= 480;
                  
                  let eventEnd;
                  if (isFullDay) {
                    eventEnd = new Date(eventStart);
                    eventEnd.setHours(closingHour, 0, 0, 0);
                  } else {
                    eventEnd = new Date(eventStart.getTime() + duration * 60000);
                  }
                  
                  // Find first column where this event doesn't overlap
                  let column = 0;
                  while (columns[column]) {
                    const lastInColumn = columns[column];
                    const lastEnd = lastInColumn.end;
                    if (eventStart >= lastEnd) {
                      break; // No overlap, can use this column
                    }
                    column++;
                  }
                  
                  columns[column] = { event, end: eventEnd };
                  layouts.push({ event, column, totalColumns: 0 });
                });
                
                // Calculate total columns for width calculation
                const maxColumn = layouts.reduce((max, l) => Math.max(max, l.column), 0) + 1;
                layouts.forEach(l => l.totalColumns = maxColumn);
                
                return layouts;
              };
              
              const eventLayouts = getEventLayout(dayEvents);
              const dayTimeOff = getTimeOffForDate(date);
              
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
                    {dayTimeOff.length > 0 && (
                      <span className="week-time-off-badge" title={dayTimeOff.map(t => `${t.worker_name} - ${t.type}`).join(', ')}>
                        <i className="fas fa-umbrella-beach"></i>
                      </span>
                    )}
                  </div>
                  
                  <div className="day-slots">
                    {timeSlots.map(hour => (
                      <div key={hour} className="time-slot"></div>
                    ))}
                    
                    {/* Events positioned absolutely with overlap handling */}
                    {eventLayouts.map(({ event, column, totalColumns }) => {
                      const eventTime = parseServerDate(event.appointment_time);
                      const startHour = eventTime.getHours() + eventTime.getMinutes() / 60;
                      const duration = event.duration_minutes || 60;
                      const durationHours = duration / 60;
                      
                      // Full day jobs (8+ hours) - show from opening to closing
                      const isFullDay = duration >= 480;
                      
                      // Calculate position based on business hours
                      let top, height;
                      if (isFullDay) {
                        // Full day spans from opening to closing
                        top = 0;
                        height = timeSlots.length * 50;
                      } else {
                        // Clamp start hour to visible range (business hours)
                        const visibleStart = Math.max(openingHour, Math.min(startHour, closingHour));
                        const visibleEnd = Math.min(closingHour, startHour + durationHours);
                        
                        top = (visibleStart - openingHour) * 50;
                        height = Math.max((visibleEnd - visibleStart) * 50, 25);
                        
                        // Skip if completely outside visible range
                        if (startHour >= closingHour || startHour + durationHours <= openingHour) return null;
                      }
                      
                      // Calculate width and left position for overlapping events
                      const width = totalColumns > 1 ? `calc((100% - 8px) / ${totalColumns})` : 'calc(100% - 8px)';
                      const left = totalColumns > 1 ? `calc(4px + (100% - 8px) * ${column} / ${totalColumns})` : '4px';
                      
                      const weekColors = event.status === 'completed' ? ['#22c55e'] : getWorkerColors(event);
                      
                      return (
                        <div
                          key={event.id}
                          className={`week-event ${isFullDay ? 'full-day' : ''}${event.status === 'completed' ? ' completed' : ''}`}
                          style={{
                            top: `${top}px`,
                            height: `${height}px`,
                            width,
                            left,
                            right: 'auto',
                            backgroundColor: event.status === 'completed' ? '#22c55e' : getWorkerColor(event),
                            borderColor: weekColors.length === 1 ? weekColors[0] : 'transparent'
                          }}
                          onClick={() => setSelectedJobId(event.id)}
                          title={`${event.customer_name} - ${event.service_type || 'Service'}`}
                        >
                          {weekColors.length > 1 && (
                            <div className="multi-worker-border" aria-hidden="true">
                              {weekColors.map((c, i) => (
                                <span key={i} style={{ background: c, flex: 1 }} />
                              ))}
                            </div>
                          )}
                          <div className="week-event-time">
                            {formatTimeRange(event.appointment_time, event.duration_minutes)}
                          </div>
                          <div className="week-event-title">{event.customer_name}</div>
                          {height > 40 && (
                            <div className="week-event-service">{event.service_type || event.service}</div>
                          )}
                          {(!event.assigned_worker_ids || event.assigned_worker_ids.length === 0) && !['completed', 'paid', 'cancelled'].includes(event.status) && (
                            <div className="week-event-no-worker" title="No worker assigned">
                              <i className="fas fa-exclamation-triangle"></i>
                            </div>
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
        showInvoiceButtons={settings?.show_invoice_buttons !== false}
      />
    </div>
  );
}

export default CalendarTab;
