import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getBookings } from '../../services/api';
import { getStatusBadgeClass } from '../../utils/helpers';
import LoadingSpinner from '../LoadingSpinner';
import JobDetailModal from '../modals/JobDetailModal';
import './CalendarTab.css';

function CalendarTab() {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [selectedDate, setSelectedDate] = useState(null);
  const [selectedJobId, setSelectedJobId] = useState(null);
  
  const { data: bookings, isLoading } = useQuery({
    queryKey: ['bookings'],
    queryFn: async () => {
      const response = await getBookings();
      return response.data;
    },
  });

  // Get calendar data
  const calendarData = useMemo(() => {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    
    // First day of month
    const firstDay = new Date(year, month, 1);
    const startingDay = firstDay.getDay(); // 0 = Sunday
    
    // Last day of month
    const lastDay = new Date(year, month + 1, 0);
    const totalDays = lastDay.getDate();
    
    // Previous month days to show
    const prevMonth = new Date(year, month, 0);
    const prevMonthDays = prevMonth.getDate();
    
    const days = [];
    
    // Previous month days
    for (let i = startingDay - 1; i >= 0; i--) {
      days.push({
        date: new Date(year, month - 1, prevMonthDays - i),
        isCurrentMonth: false,
        day: prevMonthDays - i
      });
    }
    
    // Current month days
    for (let i = 1; i <= totalDays; i++) {
      days.push({
        date: new Date(year, month, i),
        isCurrentMonth: true,
        day: i
      });
    }
    
    // Next month days to fill the grid
    const remaining = 42 - days.length; // 6 rows * 7 days
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
    if (!bookings) return [];
    return bookings.filter(booking => {
      const bookingDate = new Date(booking.appointment_time);
      return bookingDate.toDateString() === date.toDateString();
    });
  };

  // Get events for selected date
  const selectedDateEvents = useMemo(() => {
    if (!selectedDate || !bookings) return [];
    return bookings
      .filter(booking => {
        const bookingDate = new Date(booking.appointment_time);
        return bookingDate.toDateString() === selectedDate.toDateString();
      })
      .sort((a, b) => new Date(a.appointment_time) - new Date(b.appointment_time));
  }, [selectedDate, bookings]);

  // Navigation
  const goToPrevMonth = () => {
    setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() - 1, 1));
  };

  const goToNextMonth = () => {
    setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 1));
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

  if (isLoading) {
    return <LoadingSpinner message="Loading calendar..." />;
  }

  return (
    <div className="calendar-tab">
      {/* Calendar Header */}
      <div className="calendar-header">
        <div className="calendar-nav">
          <button className="nav-btn" onClick={goToPrevMonth}>
            <i className="fas fa-chevron-left"></i>
          </button>
          <h2 className="current-month">
            {monthNames[currentDate.getMonth()]} {currentDate.getFullYear()}
          </h2>
          <button className="nav-btn" onClick={goToNextMonth}>
            <i className="fas fa-chevron-right"></i>
          </button>
        </div>
        <button className="today-btn" onClick={goToToday}>
          <i className="fas fa-calendar-day"></i> Today
        </button>
      </div>

      <div className="calendar-main">
        {/* Calendar Grid */}
        <div className="calendar-grid-container">
          <div className="calendar-grid">
            {/* Day Headers */}
            {dayNames.map(day => (
              <div key={day} className="day-header">{day}</div>
            ))}
            
            {/* Calendar Days */}
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
                          className={`event-dot ${event.status}`}
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
                >
                  <div className="event-time">
                    {new Date(event.appointment_time).toLocaleTimeString('en-US', {
                      hour: '2-digit',
                      minute: '2-digit'
                    })}
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
