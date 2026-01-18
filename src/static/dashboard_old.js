// Dashboard JavaScript
let currentClient = null;
let chatConversation = [];
let allBookings = [];
let allClients = [];
let currentHomeView = 'list';
let currentUpcomingView = 'list';
let currentMonth = new Date();
let currentHomeDate = new Date(); // Track current date for home view
let notifications = [];
let unreadCount = 0;
let appConfig = null; // Application configuration from backend

// Initialize dashboard
document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    loadAppConfig();
    loadStats();
    loadClients();
    loadBookings();
    loadHomeView();
    loadUpcomingView();
    loadPastView();
    initializeChat();
    loadBusinessHours();
    initNotifications();
    setupNotificationPolling();
    setupAutoRefresh(); // Auto-refresh bookings periodically
});

// Load application configuration
async function loadAppConfig() {
    try {
        const response = await fetch('/api/config');
        if (response.ok) {
            appConfig = await response.json();
            console.log('App config loaded:', appConfig);
        }
    } catch (error) {
        console.error('Error loading app config:', error);
        // Set defaults if config fails to load
        appConfig = {
            default_charge: 50.0,
            currency: 'EUR',
            business_hours: { start: 9, end: 17 },
            timezone: 'Europe/Dublin'
        };
    }
}

// Tab switching
function initTabs() {
    const tabButtons = document.querySelectorAll('.tab-button');
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const tabName = button.dataset.tab;
            switchTab(tabName);
        });
    });
}

function switchTab(tabName) {
    // Update buttons
    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
    
    // Update content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(`${tabName}-tab`).classList.add('active');
    
    // Load data when switching to a tab
    if (tabName === 'home') loadHomeView();
    if (tabName === 'upcoming') loadUpcomingView();
    if (tabName === 'past') loadPastView();
    if (tabName === 'finances') loadFinancesView();
}

// Load stats
async function loadStats() {
    try {
        const response = await fetch('/api/stats');
        if (!response.ok) {
            throw new Error('Failed to load stats');
        }
        const stats = await response.json();
        
        document.getElementById('totalClients').textContent = stats.total_clients || 0;
        document.getElementById('totalBookings').textContent = stats.total_bookings || 0;
        document.getElementById('upcomingAppointments').textContent = stats.upcoming_appointments || 0;
    } catch (error) {
        console.error('Error loading stats:', error);
        // Set defaults on error
        document.getElementById('totalClients').textContent = '0';
        document.getElementById('totalBookings').textContent = '0';
        document.getElementById('upcomingAppointments').textContent = '0';
    }
}

// Load clients
async function loadClients() {
    try {
        const response = await fetch('/api/clients');
        if (!response.ok) {
            throw new Error('Failed to load clients');
        }
        allClients = await response.json();
        
        displayClients(allClients);
    } catch (error) {
        console.error('Error loading clients:', error);
        document.getElementById('clientsTable').innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">❌</div>
                <p>Error loading clients</p>
            </div>
        `;
    }
}

// Display clients with optional filtering
function displayClients(clients) {
    const tableHtml = clients.length > 0 ? `
        <div style="margin-bottom: 1rem;">
            <input type="text" 
                   id="clientSearch" 
                   class="form-input" 
                   placeholder="🔍 Search clients by name, phone, or email..." 
                   onkeyup="filterClients()" 
                   style="max-width: 500px;">
        </div>
        <table class="table">
            <thead>
                <tr>
                    <th>Name</th>
                    <th>Phone</th>
                    <th>Email</th>
                    <th>Appointments</th>
                    <th>Last Visit</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody id="clientsTableBody">
                ${clients.map(client => `
                    <tr>
                        <td><strong class="capitalize-name">${client.name}</strong></td>
                        <td>${client.phone || 'N/A'}</td>
                        <td>${client.email || 'N/A'}</td>
                        <td>${client.total_appointments}</td>
                        <td>${client.last_visit ? formatDate(client.last_visit) : 'Never'}</td>
                        <td>
                            <button class="btn btn-secondary" onclick="viewClient(${client.id})">
                                View
                            </button>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    ` : `
        <div class="empty-state">
            <div class="empty-state-icon">👥</div>
            <p>No clients yet. Add your first client to get started!</p>
        </div>
    `;
    
    document.getElementById('clientsTable').innerHTML = tableHtml;
}

// Filter clients based on search
function filterClients() {
    const searchTerm = document.getElementById('clientSearch').value.toLowerCase();
    
    const filtered = allClients.filter(client => {
        return client.name.toLowerCase().includes(searchTerm) ||
               (client.phone && client.phone.toLowerCase().includes(searchTerm)) ||
               (client.email && client.email.toLowerCase().includes(searchTerm));
    });
    
    const tbody = document.getElementById('clientsTableBody');
    tbody.innerHTML = filtered.map(client => `
        <tr>
            <td><strong class="capitalize-name">${client.name}</strong></td>
            <td>${client.phone || 'N/A'}</td>
            <td>${client.email || 'N/A'}</td>
            <td>${client.total_appointments}</td>
            <td>${client.last_visit ? formatDate(client.last_visit) : 'Never'}</td>
            <td>
                <button class="btn btn-secondary" onclick="viewClient(${client.id})">
                    View
                </button>
            </td>
        </tr>
    `).join('');
}

// Load bookings
async function loadBookings() {
    try {
        const response = await fetch('/api/bookings');
        if (!response.ok) {
            throw new Error('Failed to load bookings');
        }
        const newBookings = await response.json();
        
        // NOTE: Do NOT call detectBookingChanges here to prevent duplicate notifications
        // Notifications are handled by the polling system (checkForNewBookings)
        
        allBookings = newBookings;
        
        const tableHtml = allBookings.length > 0 ? `
            <table class="table">
                <thead>
                    <tr>
                        <th>Client</th>
                        <th>Service</th>
                        <th>Date & Time</th>
                        <th>Status</th>
                        <th>Contact</th>
                    </tr>
                </thead>
                <tbody>
                    ${allBookings.map(booking => `
                        <tr>
                            <td><strong>${booking.client_name || 'Unknown'}</strong></td>
                            <td>${booking.service_type || 'General'}</td>
                            <td>${formatDateTime(booking.appointment_time)}</td>
                            <td><span class="badge badge-success">${booking.status}</span></td>
                            <td>${booking.phone_number || booking.email || 'N/A'}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        ` : `
            <div class="empty-state">
                <div class="empty-state-icon">📅</div>
                <p>No bookings yet</p>
            </div>
        `;
        
        document.getElementById('bookingsTable').innerHTML = tableHtml;
        return allBookings;
    } catch (error) {
        console.error('Error loading bookings:', error);
        document.getElementById('bookingsTable').innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">❌</div>
                <p>Error loading bookings</p>
            </div>
        `;
        return [];
    }
}

// Home View Functions
function setHomeView(view) {
    currentHomeView = view;
    document.querySelectorAll('#home-tab .view-toggle-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.view === view);
    });
    loadHomeView();
}

async function loadHomeView() {
    if (allBookings.length === 0) {
        await loadBookings();
    }
    
    const now = new Date();
    const viewDate = new Date(currentHomeDate);
    viewDate.setHours(0, 0, 0, 0);
    const nextDay = new Date(viewDate);
    nextDay.setDate(nextDay.getDate() + 1);
    
    const dayBookings = allBookings.filter(booking => {
        const bookingDate = new Date(booking.appointment_time);
        return bookingDate >= viewDate && bookingDate < nextDay;
    });
    
    // Separate upcoming and past appointments for today
    const upcomingToday = dayBookings.filter(b => new Date(b.appointment_time) > now);
    const pastToday = dayBookings.filter(b => new Date(b.appointment_time) <= now);
    
    const content = document.getElementById('homeContent');
    
    // Add date header with navigation
    const isToday = viewDate.toDateString() === new Date().toDateString();
    const dateHeader = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; padding: 1rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 12px; flex-wrap: wrap; gap: 0.5rem; box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);">
            <button class="btn btn-secondary" onclick="changeHomeDate(-1)" style="flex: 0 0 auto;">← Previous Day</button>
            <div style="display: flex; align-items: center; gap: 1rem; flex: 1; justify-content: center;">
                <div style="font-size: 1.35rem; font-weight: 700; color: white;">
                    ${isToday ? '📅 Today - ' : '📆 '}${viewDate.toLocaleDateString('en-IE', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
                </div>
                ${!isToday ? `<button class="btn" onclick="jumpToToday()" style="padding: 0.5rem 1rem; font-size: 0.875rem; background: white; color: var(--primary-color);">📅 Jump to Today</button>` : ''}
            </div>
            <button class="btn btn-secondary" onclick="changeHomeDate(1)" style="flex: 0 0 auto;">Next Day →</button>
        </div>
    `;
    
    if (currentHomeView === 'list') {
        // Show upcoming and past separately if viewing today
        if (isToday && dayBookings.length > 0) {
            content.innerHTML = dateHeader + `
                ${upcomingToday.length > 0 ? `
                    <div style="margin-bottom: 2rem;">
                        <div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); padding: 15px 20px; border-radius: 10px; margin-bottom: 1rem; box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);">
                            <h3 style="margin: 0; color: white; font-size: 1.25rem; display: flex; align-items: center; gap: 10px;">
                                <span style="font-size: 28px;">🔔</span>
                                <span>Upcoming Today</span>
                                <span style="background: rgba(255,255,255,0.3); padding: 4px 12px; border-radius: 20px; font-size: 14px;">${upcomingToday.length}</span>
                            </h3>
                        </div>
                        ${renderAppointmentList(upcomingToday, 'No upcoming appointments', false, false)}
                    </div>
                ` : ''}
                ${pastToday.length > 0 ? `
                    <div>
                        <div style="background: linear-gradient(135deg, #64748b 0%, #475569 100%); padding: 15px 20px; border-radius: 10px; margin-bottom: 1rem; box-shadow: 0 4px 12px rgba(100, 116, 139, 0.3);">
                            <h3 style="margin: 0; color: white; font-size: 1.25rem; display: flex; align-items: center; gap: 10px;">
                                <span style="font-size: 28px;">📋</span>
                                <span>Completed Today</span>
                                <span style="background: rgba(255,255,255,0.3); padding: 4px 12px; border-radius: 20px; font-size: 14px;">${pastToday.length}</span>
                            </h3>
                        </div>
                        ${renderAppointmentList(pastToday, 'No past appointments', true, false)}
                    </div>
                ` : ''}
                ${dayBookings.length === 0 ? `
                    <div class="empty-state">
                        <div class="empty-state-icon">📅</div>
                        <p>No appointments today</p>
                    </div>
                ` : ''}
            `;
        } else {
            content.innerHTML = dateHeader + renderAppointmentList(dayBookings, `No appointments on ${viewDate.toLocaleDateString('en-IE')}`);
        }
    } else {
        content.innerHTML = renderCalendarView(viewDate, allBookings);
    }
}

// Change home date
function changeHomeDate(days) {
    currentHomeDate.setDate(currentHomeDate.getDate() + days);
    loadHomeView();
}

// Jump to today
function jumpToToday() {
    currentHomeDate = new Date();
    loadHomeView();
}

// Upcoming View Functions
function setUpcomingView(view) {
    currentUpcomingView = view;
    document.querySelectorAll('#upcoming-tab .view-toggle-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.view === view);
    });
    loadUpcomingView();
}

async function loadUpcomingView() {
    if (allBookings.length === 0) {
        await loadBookings();
    }
    
    const now = new Date();
    const upcomingBookings = allBookings.filter(booking => {
        const bookingDate = new Date(booking.appointment_time);
        return bookingDate > now;
    }).sort((a, b) => new Date(a.appointment_time) - new Date(b.appointment_time));
    
    const content = document.getElementById('upcomingContent');
    
    if (currentUpcomingView === 'list') {
        content.innerHTML = renderAppointmentList(upcomingBookings, "No upcoming appointments");
    } else {
        content.innerHTML = renderCalendarView(currentMonth, upcomingBookings);
    }
}

// Past View Functions
async function loadPastView() {
    if (allBookings.length === 0) {
        await loadBookings();
    }
    
    const now = new Date();
    const pastBookings = allBookings.filter(booking => {
        const bookingDate = new Date(booking.appointment_time);
        return bookingDate <= now;
    }).sort((a, b) => new Date(b.appointment_time) - new Date(a.appointment_time));
    
    const content = document.getElementById('pastContent');
    content.innerHTML = renderAppointmentList(pastBookings, "No past appointments", true);
}

// Render appointment list view
function renderAppointmentList(bookings, emptyMessage, isPast = false, includeSearch = true) {
    if (bookings.length === 0) {
        return `
            <div class="empty-state">
                <div class="empty-state-icon">📅</div>
                <p>${emptyMessage}</p>
            </div>
        `;
    }
    
    const searchBarHtml = includeSearch ? `
        <div style="margin-bottom: 1rem;">
            <input type="text" 
                   id="appointmentSearch" 
                   class="form-input" 
                   placeholder="🔍 Search appointments by client name or phone..." 
                   onkeyup="filterAppointments()" 
                   style="max-width: 500px;">
        </div>
    ` : '';
    
    return searchBarHtml + `
        <div class="appointment-list" id="appointmentListContainer">
            ${bookings.map(booking => {
                const bookingDate = new Date(booking.appointment_time);
                return `
                    <div class="appointment-card ${isPast ? 'past' : ''}" onclick="viewAppointmentDetails(${booking.id})">
                        <div class="appointment-card-header">
                            <div>
                                <div class="appointment-card-client capitalize-name" onclick="event.stopPropagation(); viewClient(${booking.client_id})" style="cursor: pointer; text-decoration: underline;">${booking.client_name || 'Unknown Client'}</div>
                                <div class="appointment-card-time">
                                    ${formatDate(booking.appointment_time)} at ${formatTime(booking.appointment_time)}
                                </div>
                            </div>
                            <span class="badge ${isPast ? 'badge-secondary' : 'badge-success'}">
                                ${booking.service_type || 'General'}
                            </span>
                        </div>
                        <div class="appointment-card-details">
                            <div class="appointment-card-detail">
                                📞 ${booking.phone_number || 'No phone'}
                            </div>
                            <div class="appointment-card-detail">
                                ✉️ ${booking.email || 'No email'}
                            </div>
                            <div class="appointment-card-detail">
                                🏷️ Event ID: ${booking.calendar_event_id}
                            </div>
                        </div>
                    </div>
                `;
            }).join('')}
        </div>
    `;
}

// Filter appointments based on search
function filterAppointments() {
    const searchTerm = document.getElementById('appointmentSearch').value.toLowerCase();
    const container = document.getElementById('appointmentListContainer');
    if (!container) return;
    
    const cards = container.getElementsByClassName('appointment-card');
    
    Array.from(cards).forEach(card => {
        const text = card.textContent.toLowerCase();
        if (text.includes(searchTerm)) {
            card.style.display = '';
        } else {
            card.style.display = 'none';
        }
    });
}

// Render calendar view
function renderCalendarView(month, bookings) {
    const year = month.getFullYear();
    const monthIndex = month.getMonth();
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    
    const firstDay = new Date(year, monthIndex, 1);
    const lastDay = new Date(year, monthIndex + 1, 0);
    const daysInMonth = lastDay.getDate();
    const startDay = firstDay.getDay();
    
    const monthNames = ['January', 'February', 'March', 'April', 'May', 'June',
                        'July', 'August', 'September', 'October', 'November', 'December'];
    
    let html = `
        <div class="calendar-header">
            <div class="calendar-month">${monthNames[monthIndex]} ${year}</div>
            <div class="calendar-nav">
                <button class="btn btn-secondary" onclick="changeMonth(-1)">← Previous</button>
                <button class="btn btn-secondary" onclick="changeMonth(0)">Today</button>
                <button class="btn btn-secondary" onclick="changeMonth(1)">Next →</button>
            </div>
        </div>
        <div class="calendar-grid">
            <div class="calendar-day-header">Sun</div>
            <div class="calendar-day-header">Mon</div>
            <div class="calendar-day-header">Tue</div>
            <div class="calendar-day-header">Wed</div>
            <div class="calendar-day-header">Thu</div>
            <div class="calendar-day-header">Fri</div>
            <div class="calendar-day-header">Sat</div>
    `;
    
    // Fill empty cells before first day
    for (let i = 0; i < startDay; i++) {
        html += '<div class="calendar-day other-month"></div>';
    }
    
    // Fill days of month
    for (let day = 1; day <= daysInMonth; day++) {
        const currentDate = new Date(year, monthIndex, day);
        currentDate.setHours(0, 0, 0, 0);
        const isToday = currentDate.getTime() === today.getTime();
        
        // Get appointments for this day
        const dayBookings = bookings.filter(booking => {
            const bookingDate = new Date(booking.appointment_time);
            return bookingDate.getFullYear() === year &&
                   bookingDate.getMonth() === monthIndex &&
                   bookingDate.getDate() === day;
        });
        
        const isPast = currentDate < today;
        
        html += `
            <div class="calendar-day ${isToday ? 'today' : ''}">
                <div class="calendar-day-number">${day}</div>
                ${dayBookings.map(booking => {
                    const bookingTime = formatTime(booking.appointment_time);
                    return `
                        <div class="calendar-appointment ${isPast ? 'past' : ''}" 
                             onclick="viewAppointmentDetails(${booking.id})"
                             title="${booking.client_name} - ${booking.service_type}">
                            <span class="calendar-appointment-time">${bookingTime}</span>
                            <span class="capitalize-name" onclick="event.stopPropagation(); viewClient(${booking.client_id})" style="text-decoration: underline; cursor: pointer;">${booking.client_name}</span>
                        </div>
                    `;
                }).join('')}
            </div>
        `;
    }
    
    html += '</div>';
    return html;
}

// Change calendar month
function changeMonth(delta) {
    if (delta === 0) {
        currentMonth = new Date();
    } else {
        currentMonth.setMonth(currentMonth.getMonth() + delta);
    }
    loadUpcomingView();
}

// View appointment details popup
async function viewAppointmentDetails(bookingId) {
    if (!bookingId) return;
    
    try {
        // Get booking details
        const response = await fetch(`/api/bookings`);
        const allBookings = await response.json();
        const booking = allBookings.find(b => b.id === bookingId);
        
        if (!booking) {
            alert('Appointment not found');
            return;
        }
        
        // Get notes for this appointment
        const notesResponse = await fetch(`/api/bookings/${bookingId}/notes`);
        const notes = await notesResponse.json();
        
        // Check if appointment is in the past
        const apptDate = new Date(booking.appointment_time);
        const isPast = apptDate < new Date();
        
        // Create modal
        const modal = document.createElement('div');
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 9999;
        `;
        
        const modalContent = document.createElement('div');
        modalContent.style.cssText = `
            background: white;
            border-radius: 10px;
            padding: 30px;
            max-width: 600px;
            width: 90%;
            max-height: 80vh;
            overflow-y: auto;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        `;
        
        modalContent.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 20px;">
                <div>
                    <h3 style="margin: 0 0 5px 0;">📅 Appointment Details</h3>
                    <p style="margin: 0; color: #666; font-size: 14px;">${formatDate(booking.appointment_time)} at ${formatTime(booking.appointment_time)}</p>
                </div>
                <button id="close-modal-btn" 
                        style="background: #f43f5e; border: none; font-size: 24px; cursor: pointer; color: white; line-height: 1; padding: 5px; width: 35px; height: 35px; border-radius: 8px; transition: all 0.2s;" 
                        onmouseover="this.style.background='#dc2626'" 
                        onmouseout="this.style.background='#f43f5e'">&times;</button>
            </div>
            
            <div style="background: var(--bg-secondary); padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                <div style="margin-bottom: 10px;">
                    <strong>Client:</strong> 
                    <span id="client-name-link" class="capitalize-name" style="color: var(--primary-color); cursor: pointer; text-decoration: underline;">
                        ${booking.client_name || 'Unknown'}
                    </span>
                </div>
                <div style="margin-bottom: 10px;"><strong>Service:</strong> ${booking.service_type || 'General'}</div>
                <div style="margin-bottom: 10px;"><strong>Status:</strong> <span class="badge badge-${booking.status === 'completed' ? 'success' : 'warning'}">${booking.status}</span></div>
                <div style="margin-bottom: 10px;"><strong>Phone:</strong> ${booking.phone_number || 'N/A'}</div>
                <div style="margin-bottom: 10px;"><strong>Email:</strong> ${booking.email || 'N/A'}</div>
                <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #ddd;">
                    <label style="font-weight: bold; display: block; margin-bottom: 8px;">💰 Appointment Charge:</label>
                    <div style="display: flex; gap: 10px; align-items: center;">
                        <input type="number" 
                               id="modal-charge-input" 
                               value="${booking.charge || 50}" 
                               min="0" 
                               step="0.01"
                               style="flex: 1; padding: 8px 12px; border: 2px solid #cbd5e0; border-radius: 6px; font-size: 16px; font-weight: bold;">
                        <span style="font-weight: bold; font-size: 16px;">€</span>
                        <button class="btn btn-primary btn-sm" onclick="saveAppointmentCharge(${bookingId})" style="white-space: nowrap;">
                            💾 Save Charge
                        </button>
                    </div>
                </div>
            </div>
            
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 15px; border-radius: 10px; margin-bottom: 20px;">
                <h4 style="margin: 0; color: white; display: flex; align-items: center; gap: 10px;">
                    <span style="font-size: 24px;">📝</span>
                    <span>Appointment Notes</span>
                    ${notes.length > 0 ? `<span style="background: rgba(255,255,255,0.3); padding: 4px 12px; border-radius: 20px; font-size: 14px;">${notes.length}</span>` : ''}
                </h4>
                <p style="margin: 8px 0 0 0; color: rgba(255,255,255,0.9); font-size: 13px;">💡 Notes automatically update the AI-generated client history</p>
            </div>
            
            <div id="modal-notes-list" style="margin-bottom: 20px; max-height: 300px; overflow-y: auto;">
                ${notes.length === 0 ? `
                    <div style="background: #fef3c7; border: 2px dashed #f59e0b; padding: 20px; border-radius: 8px; text-align: center;">
                        <p style="margin: 0; color: #92400e; font-weight: 600;">⚠️ No notes yet - Add notes to update client history!</p>
                        <p style="margin: 8px 0 0 0; color: #92400e; font-size: 13px;">Notes are required to complete appointments</p>
                    </div>
                ` : notes.map(note => `
                    <div style="background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%); padding: 15px; border-radius: 10px; margin-bottom: 12px; border-left: 4px solid #0284c7; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                        <div style="font-size: 15px; margin-bottom: 10px; line-height: 1.6; color: #0f172a; font-weight: 500;">${escapeHtml(note.note)}</div>
                        <div style="font-size: 12px; color: #64748b; margin-bottom: 10px; display: flex; align-items: center; gap: 8px;">
                            <span style="background: white; padding: 4px 8px; border-radius: 4px;">👤 ${note.created_by}</span>
                            <span>•</span>
                            <span>${new Date(note.created_at).toLocaleString()}</span>
                        </div>
                        <div style="display: flex; gap: 8px;">
                            <button class="btn btn-secondary btn-sm" onclick="editAppointmentNoteModal(${bookingId}, ${note.id}, '${escapeHtml(note.note).replace(/'/g, "\\'")}')">✏️ Edit</button>
                            <button class="btn btn-danger btn-sm" onclick="deleteAppointmentNoteModal(${bookingId}, ${note.id})">🗑️ Delete</button>
                        </div>
                    </div>
                `).join('')}
            </div>
            
            <div style="background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%); padding: 20px; border-radius: 10px; border: 2px solid #10b981; margin-bottom: 15px; box-shadow: 0 4px 6px rgba(16, 185, 129, 0.1);">
                <label style="font-weight: bold; margin-bottom: 12px; display: flex; align-items: center; gap: 8px; color: #065f46; font-size: 16px;">
                    <span style="font-size: 24px;">✍️</span>
                    <span>Add New Note</span>
                </label>
                <textarea id="modal-new-note" 
                          style="width: 100%; padding: 15px; border: 2px solid #10b981; border-radius: 8px; font-size: 14px; font-family: inherit; resize: vertical; min-height: 120px; background: white;"
                          rows="4" 
                          placeholder="📋 Treatment details, observations, progress notes, follow-up plans...
                          
💡 Tip: Be specific! These notes help AI understand the client better.

Example: 'Client reported improved sleep quality. Recommended continuing treatment for 2 more weeks.'"></textarea>
                <button class="btn btn-primary" onclick="addNoteFromModal(${bookingId}, ${booking.client_id})" style="margin-top: 12px; width: 100%; font-weight: bold; font-size: 15px; padding: 14px;">
                    💾 Save Note & Update Client History
                </button>
            </div>
            
            ${isPast && booking.status !== 'completed' ? `
                <button class="btn btn-success" onclick="completeAppointmentFromModal(${bookingId}, ${booking.client_id})" 
                        style="width: 100%; font-weight: bold; padding: 12px;">
                    ✅ Complete Appointment
                </button>
            ` : ''}
            
            ${booking.status === 'completed' ? `
                <div style="background: var(--success-bg); border: 1px solid var(--success-border); padding: 10px; border-radius: 5px; text-align: center; color: var(--success-text);">
                    ✓ Appointment Completed
                </div>
            ` : ''}
        `;
        
        modal.appendChild(modalContent);
        document.body.appendChild(modal);
        
        // Add event listeners after modal is in DOM
        document.getElementById('close-modal-btn').addEventListener('click', () => {
            modal.remove();
        });
        
        document.getElementById('client-name-link').addEventListener('click', () => {
            modal.remove();
            viewClient(booking.client_id);
        });
        
        // Close on background click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.remove();
            }
        });
        
    } catch (error) {
        console.error('Error loading appointment details:', error);
        alert('Error loading appointment details');
    }
}

// View client from appointment (kept for backward compatibility)
async function viewAppointmentClient(clientId) {
    if (!clientId) return;
    
    // Open client details directly without switching tabs
    await viewClient(clientId);
}

// View client details
async function viewClient(clientId) {
    try {
        const response = await fetch(`/api/clients/${clientId}`);
        const client = await response.json();
        currentClient = client;
        
        const content = `
            <div class="grid grid-2">
                <div>
                    <h3>Contact Information</h3>
                    <p><strong>Phone:</strong> ${client.phone || 'Not provided'}</p>
                    <p><strong>Email:</strong> ${client.email || 'Not provided'}</p>
                    <p><strong>Date of Birth:</strong> ${client.date_of_birth || 'Not provided'}</p>
                    <p><strong>First Visit:</strong> ${formatDate(client.first_visit)}</p>
                    <p><strong>Last Visit:</strong> ${client.last_visit ? formatDate(client.last_visit) : 'Never'}</p>
                    <p><strong>Total Appointments:</strong> ${client.total_appointments}</p>
                </div>
                <div>
                    <h3>Quick Actions</h3>
                    <button class="btn btn-primary" onclick="showAddNoteForm()" style="width: 100%; margin-bottom: 0.5rem;">
                        Add Note
                    </button>
                </div>
            </div>
            
            ${client.description ? `
                <div style="margin-top: 2rem;">
                    <h3>Client History Summary</h3>
                    <div class="card" style="background: var(--bg-tertiary); padding: 1rem;">
                        <p style="margin: 0; color: var(--text-primary);">${escapeHtml(client.description)}</p>
                    </div>
                </div>
            ` : ''}
            
            <div style="margin-top: 2rem;">
                <h3>Appointment History</h3>
                ${client.bookings && client.bookings.length > 0 ? `
                    <div class="appointments-list">
                        ${client.bookings.map(booking => `
                            <div class="card" style="margin-bottom: 1.5rem;">
                                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; padding: 0.5rem; background: ${booking.status === 'completed' ? 'var(--bg-tertiary)' : 'transparent'}; border-radius: 8px;">
                                    <div style="flex: 1;">
                                        <h4 style="margin: 0 0 0.5rem 0; color: ${booking.status === 'completed' ? 'var(--text-secondary)' : 'var(--text-primary)'}">${formatDateTime(booking.appointment_time)}</h4>
                                        <div style="display: flex; align-items: center; gap: 0.5rem;">
                                            <span class="badge ${booking.status === 'completed' ? 'badge-success' : 'badge-warning'}">
                                                ${booking.status === 'completed' ? '✓ COMPLETED' : '⏳ ' + booking.status.toUpperCase()}
                                            </span>
                                            <span style="color: var(--text-secondary);">${booking.service_type}</span>
                                            ${booking.notes && booking.notes.length > 0 ? 
                                                `<span style="color: var(--success-color); font-size: 0.9em;">📝 ${booking.notes.length} note${booking.notes.length > 1 ? 's' : ''}</span>` : 
                                                booking.status !== 'completed' ? `<span style="color: var(--error-color); font-size: 0.9em;">⚠️ No notes yet</span>` : ''
                                            }
                                        </div>
                                    </div>
                                    <div style="display: flex; gap: 0.5rem; align-items: center;">
                                        <button class="btn ${booking.status === 'completed' ? 'btn-secondary' : 'btn-primary'} btn-sm" onclick="toggleAppointmentNotes(${booking.id})">
                                            📝 ${booking.status === 'completed' ? 'View' : 'Add'} Notes
                                        </button>
                                        ${booking.status !== 'completed' ? `
                                            <button class="btn btn-success btn-sm" onclick="completeAppointment(${booking.id}, ${client.id})" 
                                                    title="Mark as complete (requires at least 1 note)" 
                                                    style="font-weight: bold;">
                                                ✓ Complete
                                            </button>
                                        ` : `
                                            <span style="color: var(--success-color); font-size: 1.2em;" title="Completed">✓</span>
                                        `}
                                    </div>
                                </div>
                                <div id="appointment-notes-${booking.id}" style="display: none;">
                                    <h5 style="margin: 1rem 0 0.5rem 0;">Appointment Notes</h5>
                                    <div id="notes-list-${booking.id}">
                                        ${booking.notes && booking.notes.length > 0 ? 
                                            booking.notes.map(note => `
                                                <div class="card" style="margin-bottom: 0.5rem; background: var(--bg-color);">
                                                    <div style="display: flex; justify-content: space-between; align-items: start;">
                                                        <div style="flex: 1;">
                                                            <p style="margin: 0 0 0.5rem 0;">${escapeHtml(note.note)}</p>
                                                            <small style="color: var(--text-secondary)">
                                                                ${note.created_by} - ${formatDateTime(note.created_at)}
                                                            </small>
                                                        </div>
                                                        <div style="display: flex; gap: 0.5rem;">
                                                            <button class="btn btn-secondary btn-sm" onclick="editAppointmentNote(${booking.id}, ${note.id}, '${escapeHtml(note.note).replace(/'/g, "\\'")}')">Edit</button>
                                                            <button class="btn btn-danger btn-sm" onclick="deleteAppointmentNote(${booking.id}, ${note.id})">Delete</button>
                                                        </div>
                                                    </div>
                                                </div>
                                            `).join('') 
                                            : '<p style="color: var(--text-secondary); font-style: italic;">No notes for this appointment yet</p>'
                                        }
                                    </div>
                                    <div style="margin-top: 1rem;">
                                        <textarea class="form-textarea" id="new-note-${booking.id}" placeholder="Add a note for this appointment..." style="min-height: 60px;"></textarea>
                                        <button class="btn btn-primary btn-sm" onclick="addAppointmentNote(${booking.id})" style="margin-top: 0.5rem;">Add Note</button>
                                    </div>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                ` : '<p>No appointments yet</p>'}
            </div>
            
            <div style="margin-top: 2rem;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                    <h3>Notes</h3>
                </div>
                <div id="notesContainer">
                    ${client.notes && client.notes.length > 0 ? 
                        client.notes.map(note => `
                            <div class="card" style="margin-bottom: 1rem;">
                                <p>${note.note}</p>
                                <small style="color: var(--text-secondary)">
                                    ${note.created_by} - ${formatDateTime(note.created_at)}
                                </small>
                            </div>
                        `).join('') 
                        : '<p>No notes yet</p>'
                    }
                </div>
                <div id="addNoteForm" style="display: none; margin-top: 1rem;">
                    <textarea class="form-textarea" id="noteText" placeholder="Enter note..."></textarea>
                    <div style="margin-top: 1rem;">
                        <button class="btn btn-primary" onclick="addNote()">Save Note</button>
                        <button class="btn btn-secondary" onclick="hideAddNoteForm()">Cancel</button>
                    </div>
                </div>
            </div>
        `;
        
        document.getElementById('clientDetailName').textContent = client.name;
        document.getElementById('clientDetailName').classList.add('capitalize-name');
        document.getElementById('clientDetailContent').innerHTML = content;
        showModal('clientDetailModal');
    } catch (error) {
        console.error('Error loading client:', error);
        alert('Error loading client details');
    }
}

// Add client
async function addClient(event) {
    event.preventDefault();
    
    const data = {
        name: document.getElementById('clientName').value.trim(),
        phone: document.getElementById('clientPhone').value.trim(),
        email: document.getElementById('clientEmail').value.trim()
    };
    
    if (!data.name) {
        alert('Client name is required');
        return;
    }
    
    try {
        const response = await fetch('/api/clients', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        
        if (response.ok) {
            closeModal('addClientModal');
            loadClients();
            loadStats();
            // Reset form
            document.getElementById('clientName').value = '';
            document.getElementById('clientPhone').value = '';
            document.getElementById('clientEmail').value = '';
        } else {
            const errorData = await response.json();
            alert('Error adding client: ' + (errorData.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error adding client:', error);
        alert('Error adding client: ' + error.message);
    }
}

// Add note
async function addNote() {
    const noteText = document.getElementById('noteText').value;
    if (!noteText.trim()) return;
    
    try {
        const response = await fetch(`/api/clients/${currentClient.id}/notes`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ note: noteText, created_by: 'user' })
        });
        
        if (response.ok) {
            viewClient(currentClient.id); // Refresh
        }
    } catch (error) {
        console.error('Error adding note:', error);
        alert('Error adding note');
    }
}

function showAddNoteForm() {
    document.getElementById('addNoteForm').style.display = 'block';
}

function hideAddNoteForm() {
    document.getElementById('addNoteForm').style.display = 'none';
    document.getElementById('noteText').value = '';
}

// Test runner
async function runTests(testType) {
    const button = event.target;
    const originalText = button.innerHTML;
    button.innerHTML = '<span class="loading"></span> Running...';
    button.disabled = true;
    
    try {
        const response = await fetch('/api/tests/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ test_type: testType })
        });
        
        const result = await response.json();
        document.getElementById('testResults').style.display = 'block';
        document.getElementById('testOutput').textContent = result.output;
        document.getElementById('testOutput').style.color = result.success ? 'green' : 'red';
    } catch (error) {
        console.error('Error running tests:', error);
        document.getElementById('testResults').style.display = 'block';
        document.getElementById('testOutput').textContent = 'Error running tests: ' + error.message;
        document.getElementById('testOutput').style.color = 'red';
    } finally {
        button.innerHTML = originalText;
        button.disabled = false;
    }
}

// Chat
function initializeChat() {
    // Initialize with greeting
    chatConversation = [{
        role: 'assistant',
        content: 'Hi, thank you for calling. How can I help you today?'
    }];
    
    const messagesDiv = document.getElementById('chatMessages');
    messagesDiv.innerHTML = `
        <div class="chat-message assistant">
            Hi, thank you for calling. How can I help you today?
        </div>
    `;
}

function handleChatKeypress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendChatMessage();
    }
}

async function sendChatMessage() {
    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    if (!message) return;
    
    // Disable input while processing
    input.disabled = true;
    const messagesDiv = document.getElementById('chatMessages');
    
    // Add user message to UI
    messagesDiv.innerHTML += `
        <div class="chat-message user">${escapeHtml(message)}</div>
    `;
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
    
    // Clear input
    input.value = '';
    
    // Show typing indicator
    const typingId = 'typing-' + Date.now();
    messagesDiv.innerHTML += `
        <div class="chat-message assistant" id="${typingId}">
            <span class="loading"></span> Thinking...
        </div>
    `;
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
    
    try {
        // Send to API
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: message,
                conversation: chatConversation
            })
        });
        
        const data = await response.json();
        
        // Remove typing indicator
        document.getElementById(typingId).remove();
        
        if (data.error) {
            messagesDiv.innerHTML += `
                <div class="chat-message assistant" style="background: #fee2e2; border-color: #ef4444;">
                    ❌ Error: ${escapeHtml(data.error)}
                </div>
            `;
        } else {
            // Update conversation history
            chatConversation = data.conversation;
            
            // Add assistant response
            messagesDiv.innerHTML += `
                <div class="chat-message assistant">${escapeHtml(data.response)}</div>
            `;
            
            // Auto-refresh data after any booking/cancellation/reschedule actions
            const response_lower = data.response.toLowerCase();
            const shouldRefresh = (
                response_lower.includes('booked') || 
                response_lower.includes('confirmed') ||
                response_lower.includes('all set') ||
                response_lower.includes('you\'re set') ||
                response_lower.includes('cancelled') ||
                response_lower.includes('rescheduled') ||
                response_lower.includes('moved your appointment') ||
                response_lower.includes('looking forward to seeing you')
            );
            
            if (shouldRefresh) {
                console.log('📊 Refreshing dashboard data after booking/cancellation/reschedule');
                setTimeout(() => {
                    loadStats();
                    loadClients();
                    loadBookings();
                }, 500);
            }
        }
    } catch (error) {
        // Remove typing indicator
        const typingEl = document.getElementById(typingId);
        if (typingEl) typingEl.remove();
        
        messagesDiv.innerHTML += `
            <div class="chat-message assistant" style="background: #fee2e2; border-color: #ef4444;">
                ❌ Error: ${escapeHtml(error.message)}
            </div>
        `;
    } finally {
        input.disabled = false;
        input.focus();
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }
}

async function resetChat() {
    try {
        await fetch('/api/chat/reset', { method: 'POST' });
        initializeChat();
    } catch (error) {
        console.error('Error resetting chat:', error);
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Appointment notes functions
function toggleAppointmentNotes(bookingId) {
    const notesDiv = document.getElementById(`appointment-notes-${bookingId}`);
    notesDiv.style.display = notesDiv.style.display === 'none' ? 'block' : 'none';
}

async function addAppointmentNote(bookingId) {
    const noteText = document.getElementById(`new-note-${bookingId}`).value.trim();
    if (!noteText) {
        alert('Please enter a note');
        return;
    }
    
    // Show loading indicator
    const loadingMsg = document.createElement('div');
    loadingMsg.style.cssText = `
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: white;
        padding: 20px 40px;
        border-radius: 10px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        z-index: 10000;
        text-align: center;
        font-size: 16px;
    `;
    loadingMsg.innerHTML = `
        <div style="margin-bottom: 10px; font-size: 30px;">📝</div>
        <div style="font-weight: bold;">Saving note...</div>
        <div style="margin-top: 10px;">
            <div class="spinner-border spinner-border-sm text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
        </div>
    `;
    document.body.appendChild(loadingMsg);
    
    try {
        const response = await fetch(`/api/bookings/${bookingId}/notes`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ note: noteText, created_by: 'user' })
        });
        
        // Remove loading indicator
        document.body.removeChild(loadingMsg);
        
        if (response.ok) {
            document.getElementById(`new-note-${bookingId}`).value = '';
            
            // Show updating description message
            const updateMsg = document.createElement('div');
            updateMsg.style.cssText = loadingMsg.style.cssText;
            updateMsg.innerHTML = `
                <div style="margin-bottom: 10px; font-size: 30px;">🤖</div>
                <div style="font-weight: bold;">Updating client history...</div>
                <div style="margin-top: 10px;">
                    <div class="spinner-border spinner-border-sm text-primary" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                </div>
            `;
            document.body.appendChild(updateMsg);
            
            // Wait a moment then refresh
            setTimeout(async () => {
                document.body.removeChild(updateMsg);
                await viewClient(currentClient.id);
            }, 1500);
        } else {
            const errorData = await response.json();
            if (errorData.error && errorData.error.includes('future')) {
                alert('⚠️ ' + errorData.message + '\n\nNotes can only be added to past appointments.');
            } else {
                alert('Error adding note');
            }
        }
    } catch (error) {
        // Remove loading indicator if still there
        if (document.body.contains(loadingMsg)) {
            document.body.removeChild(loadingMsg);
        }
        console.error('Error adding appointment note:', error);
        alert('Error adding note');
    }
}

async function editAppointmentNote(bookingId, noteId, currentNote) {
    const newNote = prompt('Edit note:', currentNote);
    if (newNote === null || newNote.trim() === '') return;
    
    // Show loading indicator
    const loadingMsg = document.createElement('div');
    loadingMsg.style.cssText = `
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: white;
        padding: 20px 40px;
        border-radius: 10px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        z-index: 10000;
        text-align: center;
        font-size: 16px;
    `;
    loadingMsg.innerHTML = `
        <div style="margin-bottom: 10px; font-size: 30px;">🤖</div>
        <div style="font-weight: bold;">Updating client history...</div>
        <div style="margin-top: 10px;">
            <div class="spinner-border spinner-border-sm text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
        </div>
    `;
    document.body.appendChild(loadingMsg);
    
    try {
        const response = await fetch(`/api/bookings/${bookingId}/notes/${noteId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ note: newNote })
        });
        
        // Wait a moment to let AI update
        await new Promise(resolve => setTimeout(resolve, 1500));
        
        // Remove loading indicator
        document.body.removeChild(loadingMsg);
        
        if (response.ok) {
            await viewClient(currentClient.id);
        } else {
            alert('Error updating note');
        }
    } catch (error) {
        // Remove loading indicator if still there
        if (document.body.contains(loadingMsg)) {
            document.body.removeChild(loadingMsg);
        }
        console.error('Error updating appointment note:', error);
        alert('Error updating note');
    }
}

async function deleteAppointmentNote(bookingId, noteId) {
    if (!confirm('Are you sure you want to delete this note?')) return;
    
    // Show loading indicator
    const loadingMsg = document.createElement('div');
    loadingMsg.style.cssText = `
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: white;
        padding: 20px 40px;
        border-radius: 10px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        z-index: 10000;
        text-align: center;
        font-size: 16px;
    `;
    loadingMsg.innerHTML = `
        <div style="margin-bottom: 10px; font-size: 30px;">🤖</div>
        <div style="font-weight: bold;">Updating client history...</div>
        <div style="margin-top: 10px;">
            <div class="spinner-border spinner-border-sm text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
        </div>
    `;
    document.body.appendChild(loadingMsg);
    
    try {
        const response = await fetch(`/api/bookings/${bookingId}/notes/${noteId}`, {
            method: 'DELETE'
        });
        
        // Wait a moment to let AI update
        await new Promise(resolve => setTimeout(resolve, 1500));
        
        // Remove loading indicator
        document.body.removeChild(loadingMsg);
        
        if (response.ok) {
            await viewClient(currentClient.id);
        } else {
            alert('Error deleting note');
        }
    } catch (error) {
        // Remove loading indicator if still there
        if (document.body.contains(loadingMsg)) {
            document.body.removeChild(loadingMsg);
        }
        console.error('Error deleting appointment note:', error);
        alert('Error deleting note');
    }
}

// Modal-specific note functions
async function addNoteFromModal(bookingId, clientId) {
    const noteText = document.getElementById('modal-new-note').value.trim();
    if (!noteText) {
        alert('Please enter a note');
        return;
    }
    
    // Show loading indicator
    const loadingMsg = document.createElement('div');
    loadingMsg.style.cssText = `
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: white;
        padding: 20px 40px;
        border-radius: 10px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        z-index: 10001;
        text-align: center;
        font-size: 16px;
    `;
    loadingMsg.innerHTML = `
        <div style="margin-bottom: 10px; font-size: 30px;">🤖</div>
        <div style="font-weight: bold;">Saving & updating client history...</div>
        <div style="margin-top: 10px;">
            <div class="spinner-border spinner-border-sm text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
        </div>
    `;
    document.body.appendChild(loadingMsg);
    
    try {
        const response = await fetch(`/api/bookings/${bookingId}/notes`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ note: noteText, created_by: 'user' })
        });
        
        // Wait for AI update
        await new Promise(resolve => setTimeout(resolve, 2000));
        
        // Remove loading indicator
        document.body.removeChild(loadingMsg);
        
        if (response.ok) {
            // Close modal and refresh appointments
            document.querySelector('div[style*="position: fixed"]').remove();
            await loadUpcomingView();
            // Note saved silently - no popup needed
        } else {
            const errorData = await response.json();
            if (errorData.error && errorData.error.includes('future')) {
                alert('⚠️ ' + errorData.message);
            } else {
                alert('Error adding note');
            }
        }
    } catch (error) {
        if (document.body.contains(loadingMsg)) {
            document.body.removeChild(loadingMsg);
        }
        console.error('Error adding appointment note:', error);
        alert('Error adding note');
    }
}

async function editAppointmentNoteModal(bookingId, noteId, currentNote) {
    const newNote = prompt('Edit note:', currentNote);
    if (newNote === null || newNote.trim() === '') return;
    
    // Show loading indicator
    const loadingMsg = document.createElement('div');
    loadingMsg.style.cssText = `
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: white;
        padding: 20px 40px;
        border-radius: 10px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        z-index: 10001;
        text-align: center;
        font-size: 16px;
    `;
    loadingMsg.innerHTML = `
        <div style="margin-bottom: 10px; font-size: 30px;">🤖</div>
        <div style="font-weight: bold;">Updating client history...</div>
        <div style="margin-top: 10px;">
            <div class="spinner-border spinner-border-sm text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
        </div>
    `;
    document.body.appendChild(loadingMsg);
    
    try {
        const response = await fetch(`/api/bookings/${bookingId}/notes/${noteId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ note: newNote })
        });
        
        await new Promise(resolve => setTimeout(resolve, 2000));
        document.body.removeChild(loadingMsg);
        
        if (response.ok) {
            // Refresh the modal
            document.querySelector('div[style*="position: fixed"]').remove();
            await viewAppointmentDetails(bookingId);
        } else {
            alert('Error updating note');
        }
    } catch (error) {
        if (document.body.contains(loadingMsg)) {
            document.body.removeChild(loadingMsg);
        }
        console.error('Error updating appointment note:', error);
        alert('Error updating note');
    }
}

async function deleteAppointmentNoteModal(bookingId, noteId) {
    if (!confirm('Are you sure you want to delete this note?')) return;
    
    // Show loading indicator
    const loadingMsg = document.createElement('div');
    loadingMsg.style.cssText = `
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: white;
        padding: 20px 40px;
        border-radius: 10px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        z-index: 10001;
        text-align: center;
        font-size: 16px;
    `;
    loadingMsg.innerHTML = `
        <div style="margin-bottom: 10px; font-size: 30px;">🤖</div>
        <div style="font-weight: bold;">Updating client history...</div>
        <div style="margin-top: 10px;">
            <div class="spinner-border spinner-border-sm text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
        </div>
    `;
    document.body.appendChild(loadingMsg);
    
    try {
        const response = await fetch(`/api/bookings/${bookingId}/notes/${noteId}`, {
            method: 'DELETE'
        });
        
        await new Promise(resolve => setTimeout(resolve, 2000));
        document.body.removeChild(loadingMsg);
        
        if (response.ok) {
            // Refresh the modal
            document.querySelector('div[style*="position: fixed"]').remove();
            await viewAppointmentDetails(bookingId);
        } else {
            alert('Error deleting note');
        }
    } catch (error) {
        if (document.body.contains(loadingMsg)) {
            document.body.removeChild(loadingMsg);
        }
        console.error('Error deleting appointment note:', error);
        alert('Error deleting note');
    }
}

async function completeAppointmentFromModal(bookingId, clientId) {
    // Check if appointment has notes first
    try {
        const notesResponse = await fetch(`/api/bookings/${bookingId}/notes`);
        const notes = await notesResponse.json();
        
        if (!notes || notes.length === 0) {
            alert('⚠️ Please add at least one note before completing this appointment.');
            return;
        }
    } catch (error) {
        console.error('Error checking notes:', error);
    }
    
    if (!confirm('✅ Mark this appointment as COMPLETE?\n\nThis will update the client history with AI.')) {
        return;
    }
    
    // Get the charge from the input field
    const chargeInput = document.getElementById('modal-charge-input');
    const charge = chargeInput ? parseFloat(chargeInput.value) : 50;
    
    // Show loading indicator
    const loadingMsg = document.createElement('div');
    loadingMsg.style.cssText = `
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: white;
        padding: 30px 50px;
        border-radius: 10px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        z-index: 10001;
        text-align: center;
        font-size: 18px;
    `;
    loadingMsg.innerHTML = `
        <div style="margin-bottom: 15px; font-size: 40px;">🤖</div>
        <div style="font-weight: bold; margin-bottom: 10px;">Updating client history...</div>
        <div style="color: #666; font-size: 14px;">AI is analyzing appointment notes</div>
        <div style="margin-top: 15px;">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
        </div>
    `;
    document.body.appendChild(loadingMsg);
    
    try {
        // First, update the charge if needed
        if (!isNaN(charge) && charge >= 0) {
            await fetch(`/api/bookings/${bookingId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ charge: charge })
            });
        }
        
        // Then complete the appointment
        const response = await fetch(`/api/bookings/${bookingId}/complete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const data = await response.json();
        document.body.removeChild(loadingMsg);
        
        if (response.ok && data.success) {
            // Close modal and refresh
            document.querySelector('div[style*="position: fixed"]').remove();
            await loadUpcomingView();
            await loadFinancesView();
            
            const previewDesc = data.description ? data.description.substring(0, 150) + '...' : 'Updated';
            alert(`✅ APPOINTMENT COMPLETED!\n\n📝 New Client History:\n${previewDesc}`);
        } else {
            alert('⚠️ Error completing appointment');
        }
    } catch (error) {
        if (document.body.contains(loadingMsg)) {
            document.body.removeChild(loadingMsg);
        }
        console.error('Error completing appointment:', error);
        alert('Error completing appointment');
    }
}

async function completeAppointment(bookingId, clientId) {
    // Check if appointment has notes first
    try {
        const notesResponse = await fetch(`/api/bookings/${bookingId}/notes`);
        const notes = await notesResponse.json();
        
        if (!notes || notes.length === 0) {
            alert('⚠️ Please add at least one note before completing this appointment.\n\nClick the "📝 Notes" button to add treatment notes, observations, or progress updates.');
            return;
        }
    } catch (error) {
        console.error('Error checking notes:', error);
    }
    
    if (!confirm('✅ Mark this appointment as COMPLETE?\n\nThis will:\n• Update the client history with AI\n• Mark the appointment as finished\n• Generate a new description from all notes')) {
        return;
    }
    
    // Show loading message
    const loadingMsg = document.createElement('div');
    loadingMsg.style.cssText = `
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: white;
        padding: 30px 50px;
        border-radius: 10px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        z-index: 10000;
        text-align: center;
        font-size: 18px;
    `;
    loadingMsg.innerHTML = `
        <div style="margin-bottom: 15px; font-size: 40px;">🤖</div>
        <div style="font-weight: bold; margin-bottom: 10px;">Updating client history...</div>
        <div style="color: #666; font-size: 14px;">AI is analyzing appointment notes</div>
        <div style="margin-top: 15px;">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
        </div>
    `;
    document.body.appendChild(loadingMsg);
    
    try {
        const response = await fetch(`/api/bookings/${bookingId}/complete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const data = await response.json();
        
        // Remove loading message
        document.body.removeChild(loadingMsg);
        
        if (response.ok && data.success) {
            // Force reload the entire clients list and stats
            await loadClients();
            await loadStats();
            
            // Then view the client with fresh data
            await viewClient(clientId);
            
            // Show success message with new description preview
            const previewDesc = data.description ? data.description.substring(0, 150) + '...' : 'Updated';
            alert(`✅ APPOINTMENT COMPLETED!\n\n📝 New Client History:\n${previewDesc}`);
        } else {
            alert('⚠️ Appointment marked complete, but description update may have failed.');
            await viewClient(clientId);
        }
    } catch (error) {
        // Remove loading message if still there
        if (document.body.contains(loadingMsg)) {
            document.body.removeChild(loadingMsg);
        }
        console.error('Error completing appointment:', error);
        alert('❌ Error completing appointment');
    }
}

// Modal functions
function showModal(modalId) {
    document.getElementById(modalId).classList.add('active');
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
}

function showAddClientModal() {
    showModal('addClientModal');
}

// Utility functions
function formatDate(dateString) {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-IE');
}

function formatDateTime(dateString) {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleString('en-IE');
}

function formatTime(dateString) {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleTimeString('en-IE', { hour: '2-digit', minute: '2-digit' });
}

// Business hours function
async function loadBusinessHours() {
    try {
        const response = await fetch('/config/business_info.json');
        const config = await response.json();
        
        const hoursDisplay = document.getElementById('businessHoursDisplay');
        if (config.hours) {
            let hoursHtml = '<div style="font-family: monospace; line-height: 1.8;">';
            hoursHtml += `<div><strong>Days:</strong> ${config.hours.days_open || 'N/A'}</div>`;
            hoursHtml += `<div><strong>Timezone:</strong> ${config.hours.timezone || 'N/A'}</div>`;
            if (config.hours.note) {
                hoursHtml += `<div style="margin-top: 0.5rem; color: var(--text-light);"><em>${config.hours.note}</em></div>`;
            }
            hoursHtml += '</div>';
            hoursDisplay.innerHTML = hoursHtml;
        } else {
            hoursDisplay.innerHTML = '<p style="color: var(--text-light);">No business hours configured</p>';
        }
    } catch (error) {
        console.error('Error loading business hours:', error);
        document.getElementById('businessHoursDisplay').innerHTML = 
            '<p style="color: var(--danger-color);">Error loading business hours</p>';
    }
}

// Export functions
function exportToCSV(data, filename) {
    if (!data || data.length === 0) {
        alert('No data to export');
        return;
    }
    
    // Get headers from first object
    const headers = Object.keys(data[0]);
    
    // Create CSV content
    let csv = headers.join(',') + '\n';
    
    data.forEach(row => {
        const values = headers.map(header => {
            const val = row[header];
            // Escape commas and quotes
            return typeof val === 'string' && (val.includes(',') || val.includes('"')) 
                ? `"${val.replace(/"/g, '""')}"` 
                : val;
        });
        csv += values.join(',') + '\n';
    });
    
    // Download
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    window.URL.revokeObjectURL(url);
}

function exportClients() {
    if (allClients.length === 0) {
        alert('No clients to export');
        return;
    }
    
    const exportData = allClients.map(client => ({
        'Name': client.name,
        'Phone': client.phone || '',
        'Email': client.email || '',
        'Total Appointments': client.total_appointments,
        'Last Visit': client.last_visit ? formatDate(client.last_visit) : 'Never'
    }));
    
    exportToCSV(exportData, `clients_${new Date().toISOString().split('T')[0]}.csv`);
}

function exportAppointments() {
    if (allBookings.length === 0) {
        alert('No appointments to export');
        return;
    }
    
    const exportData = allBookings.map(booking => ({
        'Client Name': booking.client_name,
        'Date': formatDate(booking.appointment_time),
        'Time': formatTime(booking.appointment_time),
        'Phone': booking.phone_number || '',
        'Email': booking.email || '',
        'Service Type': booking.service_type || 'General',
        'Calendar Event ID': booking.calendar_event_id || ''
    }));
    
    exportToCSV(exportData, `appointments_${new Date().toISOString().split('T')[0]}.csv`);
}

// ============ Finances Tab Functions ============
let revenueChart = null;
let financialStats = null;

async function loadFinancesView() {
    try {
        const response = await fetch('/api/finances/stats');
        if (!response.ok) {
            throw new Error('Failed to load financial stats');
        }
        financialStats = await response.json();
        
        // Calculate revenue for last 365 days and expected revenue for next 30 days
        const now = new Date();
        const last365Days = new Date();
        last365Days.setDate(last365Days.getDate() - 365);
        const next30Days = new Date();
        next30Days.setDate(next30Days.getDate() + 30);
        
        let moneyMadeLast365 = 0;
        let expectedRevenue = 0;
        let totalPaid = 0;
        let totalUnpaid = 0;
        
        // Calculate from actual bookings data from database
        allBookings.forEach(booking => {
            const apptDate = new Date(booking.appointment_time);
            const charge = parseFloat(booking.charge) || (appConfig ? appConfig.default_charge : 50.0);
            const isPaid = booking.payment_status === 'paid';
            
            // Money made in last 365 days (past appointments only)
            if (apptDate >= last365Days && apptDate < now) {
                moneyMadeLast365 += charge;
            }
            
            // Expected revenue in next 30 days (future appointments)
            if (apptDate >= now && apptDate <= next30Days) {
                expectedRevenue += charge;
            }
            
            // Calculate paid vs unpaid totals (all appointments)
            if (isPaid) {
                totalPaid += charge;
            } else {
                totalUnpaid += charge;
            }
        });
        
        // Update summary cards with actual database values
        document.getElementById('moneyMade').textContent = `€${moneyMadeLast365.toFixed(2)}`;
        document.getElementById('expectedRevenue').textContent = `€${expectedRevenue.toFixed(2)}`;
        document.getElementById('paidAmount').textContent = `€${totalPaid.toFixed(2)}`;
        document.getElementById('unpaidAmount').textContent = `€${totalUnpaid.toFixed(2)}`;
        
        // Render charts
        renderRevenueChart();
        
        // Load bookings table
        filterFinancialBookings();
        
    } catch (error) {
        console.error('Error loading finances:', error);
        document.getElementById('financialBookingsTable').innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">⚠️</div>
                <p>Error loading financial data</p>
            </div>
        `;
    }
}

function renderRevenueChart() {
    const ctx = document.getElementById('revenueChart').getContext('2d');
    
    if (revenueChart) {
        revenueChart.destroy();
    }
    
    const monthlyData = financialStats.monthly_revenue || [];
    const labels = monthlyData.map(item => item.month);
    const data = monthlyData.map(item => item.revenue);
    
    revenueChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Revenue (€)',
                data: data,
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                tension: 0.4,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return '€' + value;
                        }
                    }
                }
            }
        }
    });
}

function filterFinancialBookings() {
    const statusFilter = document.getElementById('paymentStatusFilter').value;
    const searchInput = document.getElementById('financeSearch');
    const searchTerm = searchInput ? searchInput.value.toLowerCase() : '';
    
    let filtered = [...allBookings];
    
    if (statusFilter !== 'all') {
        filtered = filtered.filter(b => b.payment_status === statusFilter);
    }
    
    if (searchTerm) {
        filtered = filtered.filter(b => 
            (b.client_name && b.client_name.toLowerCase().includes(searchTerm)) ||
            (b.phone_number && b.phone_number.toLowerCase().includes(searchTerm))
        );
    }
    
    // Sort by appointment time descending
    filtered.sort((a, b) => new Date(b.appointment_time) - new Date(a.appointment_time));
    
    displayFinancialBookings(filtered);
}

function displayFinancialBookings(bookings) {
    const container = document.getElementById('financialBookingsTable');
    
    if (bookings.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">💰</div>
                <p>No appointments found</p>
            </div>
        `;
        return;
    }
    
    let html = `
        <table class="data-table">
            <thead>
                <tr>
                    <th>Date & Time</th>
                    <th>Client Name</th>
                    <th>Phone</th>
                    <th>Service</th>
                    <th>Charge</th>
                    <th>Paid</th>
                    <th>Edit</th>
                </tr>
            </thead>
            <tbody>
    `;
    
    bookings.forEach(booking => {
        const isPast = new Date(booking.appointment_time) < new Date();
        const charge = booking.charge || (appConfig ? appConfig.default_charge : 50.0);
        const isPaid = booking.payment_status === 'paid';
        
        html += `
            <tr>
                <td style="min-width: 120px;">${formatDate(booking.appointment_time)}<br/><small style="color: #6b7280;">${formatTime(booking.appointment_time)}</small></td>
                <td class="capitalize-name"><strong>${booking.client_name}</strong></td>
                <td>${booking.phone_number || '-'}</td>
                <td>${booking.service_type || 'General'}</td>
                <td style="font-weight: 600; color: #059669;">€${charge.toFixed(2)}</td>
                <td>
                    <select class="payment-status-dropdown ${isPaid ? 'paid' : 'unpaid'}" 
                            onchange="changePaymentStatus(${booking.id}, this.value)" 
                            data-booking-id="${booking.id}">
                        <option value="paid" ${isPaid ? 'selected' : ''}>✅ Paid</option>
                        <option value="unpaid" ${!isPaid ? 'selected' : ''}>⏳ Unpaid</option>
                    </select>
                </td>
                <td>
                    <button class="edit-btn" onclick="editCharge(${booking.id})" title="Edit Charge">
                        Edit Charge
                    </button>
                </td>
            </tr>
        `;
    });
    
    html += `
            </tbody>
        </table>
    `;
    
    container.innerHTML = html;
}

function editCharge(bookingId) {
    const booking = allBookings.find(b => b.id === bookingId);
    if (!booking) return;
    
    const newCharge = prompt(`Edit charge for ${booking.client_name}:`, booking.charge || (appConfig ? appConfig.default_charge : 50.0));
    if (newCharge === null) return;
    
    const charge = parseFloat(newCharge);
    if (isNaN(charge) || charge < 0) {
        alert('Please enter a valid charge amount');
        return;
    }
    
    updateBookingFinance(bookingId, { charge: charge });
}

function changePaymentStatus(bookingId, status) {
    const paymentMethod = status === 'paid' ? 'cash' : null;
    
    updateBookingFinance(bookingId, { 
        payment_status: status,
        payment_method: paymentMethod
    });
    
    // Update dropdown styling
    const dropdown = document.querySelector(`select[data-booking-id="${bookingId}"]`);
    if (dropdown) {
        dropdown.className = `payment-status-dropdown ${status}`;
    }
}

async function updateBookingFinance(bookingId, updates) {
    try {
        const response = await fetch(`/api/bookings/${bookingId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(updates)
        });
        
        if (!response.ok) {
            throw new Error('Failed to update booking');
        }
        
        // Refresh data
        await loadBookings();
        await loadFinancesView();
        
    } catch (error) {
        console.error('Error updating booking:', error);
        alert('Failed to update payment information');
    }
}

async function saveAppointmentCharge(bookingId) {
    const chargeInput = document.getElementById('modal-charge-input');
    if (!chargeInput) return;
    
    const charge = parseFloat(chargeInput.value);
    if (isNaN(charge) || charge < 0) {
        alert('Please enter a valid charge amount (0 or greater)');
        return;
    }
    
    try {
        const response = await fetch(`/api/bookings/${bookingId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ charge: charge })
        });
        
        if (!response.ok) {
            throw new Error('Failed to save charge');
        }
        
        // Show success message
        const successMsg = document.createElement('div');
        successMsg.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: var(--success-color);
            color: white;
            padding: 15px 25px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 10000;
            font-weight: bold;
        `;
        successMsg.textContent = '✅ Charge saved successfully!';
        document.body.appendChild(successMsg);
        
        setTimeout(() => successMsg.remove(), 3000);
        
        // Refresh data
        await loadBookings();
        await loadFinancesView();
        
    } catch (error) {
        console.error('Error saving charge:', error);
        alert('Failed to save charge. Please try again.');
    }
}

function exportFinances() {
    if (allBookings.length === 0) {
        alert('No financial data to export');
        return;
    }
    
    const exportData = allBookings.map(booking => ({
        'Date': formatDate(booking.appointment_time),
        'Time': formatTime(booking.appointment_time),
        'Client Name': booking.client_name,
        'Service Type': booking.service_type || 'General',
        'Charge': `€${(booking.charge || (appConfig ? appConfig.default_charge : 50.0)).toFixed(2)}`,
        'Payment Status': booking.payment_status || 'unpaid',
        'Payment Method': booking.payment_method || '-',
        'Phone': booking.phone_number || '',
        'Email': booking.email || ''
    }));
    
    exportToCSV(exportData, `finances_${new Date().toISOString().split('T')[0]}.csv`);
}

// ============================================
// Notification System
// ============================================

function initNotifications() {
    const bell = document.getElementById('notificationBell');
    const dropdown = document.getElementById('notificationDropdown');
    
    // Toggle dropdown on bell click
    bell.addEventListener('click', (e) => {
        e.stopPropagation();
        dropdown.classList.toggle('show');
        
        // Mark all as read when opening
        if (dropdown.classList.contains('show')) {
            markAllAsRead();
        }
    });
    
    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (!bell.contains(e.target) && !dropdown.contains(e.target)) {
            dropdown.classList.remove('show');
        }
    });
    
    // Load existing notifications from localStorage
    loadNotificationsFromStorage();
    renderNotifications();
}

function loadNotificationsFromStorage() {
    const stored = localStorage.getItem('notifications');
    if (stored) {
        try {
            notifications = JSON.parse(stored);
            updateBadgeCount();
        } catch (e) {
            console.error('Error loading notifications:', e);
            notifications = [];
        }
    }
}

function saveNotificationsToStorage() {
    try {
        localStorage.setItem('notifications', JSON.stringify(notifications));
    } catch (e) {
        console.error('Error saving notifications:', e);
    }
}

function addNotification(type, clientName, appointmentTime, details = '') {
    const notification = {
        id: Date.now() + Math.random(),
        type: type, // 'booking', 'reschedule', 'cancel'
        clientName: clientName,
        appointmentTime: appointmentTime,
        details: details,
        timestamp: new Date().toISOString(),
        read: false
    };
    
    // Add to beginning of array
    notifications.unshift(notification);
    
    // Keep only last 50 notifications
    if (notifications.length > 50) {
        notifications = notifications.slice(0, 50);
    }
    
    saveNotificationsToStorage();
    updateBadgeCount();
    renderNotifications();
    
    // Show brief animation
    const bellIcon = document.querySelector('.bell-icon');
    bellIcon.style.animation = 'none';
    setTimeout(() => {
        bellIcon.style.animation = '';
    }, 10);
}

function updateBadgeCount() {
    unreadCount = notifications.filter(n => !n.read).length;
    const badge = document.getElementById('notificationBadge');
    
    if (unreadCount > 0) {
        badge.textContent = unreadCount > 99 ? '99+' : unreadCount;
        badge.classList.remove('hidden');
    } else {
        badge.classList.add('hidden');
    }
}

function renderNotifications() {
    const list = document.getElementById('notificationList');
    
    if (notifications.length === 0) {
        list.innerHTML = `
            <div class="no-notifications">
                <div class="no-notifications-icon">🔔</div>
                <p>No notifications yet</p>
            </div>
        `;
        return;
    }
    
    list.innerHTML = notifications.map(notif => {
        const icon = notif.type === 'booking' ? '✅' : 
                     notif.type === 'reschedule' ? '📅' : '❌';
        
        const title = notif.type === 'booking' ? 'New Booking' :
                     notif.type === 'reschedule' ? 'Appointment Rescheduled' :
                     'Appointment Cancelled';
        
        const timeAgo = getTimeAgo(new Date(notif.timestamp));
        const appointmentDate = new Date(notif.appointmentTime);
        const formattedTime = appointmentDate.toLocaleString('en-IE', {
            weekday: 'short',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
        
        return `
            <div class="notification-item ${notif.read ? '' : 'unread'} ${notif.type}" 
                 onclick="markNotificationRead('${notif.id}')">
                <div class="notification-content">
                    <div class="notification-icon">${icon}</div>
                    <div class="notification-text">
                        <div class="notification-title">${title}</div>
                        <div class="notification-message">
                            <strong>${notif.clientName}</strong> - ${formattedTime}
                            ${notif.details ? `<br><em>${notif.details}</em>` : ''}
                        </div>
                        <div class="notification-time">${timeAgo}</div>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

function getTimeAgo(date) {
    const seconds = Math.floor((new Date() - date) / 1000);
    
    if (seconds < 60) return 'Just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)} minutes ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)} hours ago`;
    if (seconds < 604800) return `${Math.floor(seconds / 86400)} days ago`;
    
    return date.toLocaleDateString('en-IE', { month: 'short', day: 'numeric' });
}

function markNotificationRead(id) {
    const notif = notifications.find(n => n.id == id);
    if (notif && !notif.read) {
        notif.read = true;
        saveNotificationsToStorage();
        updateBadgeCount();
        renderNotifications();
    }
}

function markAllAsRead() {
    let changed = false;
    notifications.forEach(notif => {
        if (!notif.read) {
            notif.read = true;
            changed = true;
        }
    });
    
    if (changed) {
        saveNotificationsToStorage();
        updateBadgeCount();
        renderNotifications();
    }
}

function clearAllNotifications() {
    if (notifications.length === 0) return;
    
    if (confirm('Are you sure you want to clear all notifications?')) {
        notifications = [];
        saveNotificationsToStorage();
        updateBadgeCount();
        renderNotifications();
    }
}

// Poll for new bookings and detect changes
let lastBookingsCheck = null;

function setupNotificationPolling() {
    // Load last bookings state from localStorage to detect changes across page reloads
    loadLastBookingsFromStorage();
    
    // Do an immediate check
    checkForNewBookings();
    
    // Check every N seconds for new bookings (configurable from backend)
    const pollInterval = (appConfig && appConfig.notification_poll_interval) || 30000;
    setInterval(checkForNewBookings, pollInterval);
}

function loadLastBookingsFromStorage() {
    try {
        const stored = localStorage.getItem('lastBookingsCheck');
        if (stored) {
            lastBookingsCheck = JSON.parse(stored);
            console.log('Loaded previous bookings state from storage');
        }
    } catch (e) {
        console.error('Error loading last bookings check:', e);
        lastBookingsCheck = null;
    }
}

function saveLastBookingsToStorage() {
    try {
        localStorage.setItem('lastBookingsCheck', JSON.stringify(lastBookingsCheck));
    } catch (e) {
        console.error('Error saving last bookings check:', e);
    }
}

async function checkForNewBookings() {
    try {
        const response = await fetch('/api/bookings');
        if (!response.ok) return;
        
        const currentBookings = await response.json();
        
        if (lastBookingsCheck) {
            // Compare with previous state
            detectBookingChanges(lastBookingsCheck, currentBookings);
        }
        
        lastBookingsCheck = currentBookings;
        saveLastBookingsToStorage();
        
    } catch (error) {
        console.error('Error checking for new bookings:', error);
    }
}

function detectBookingChanges(oldBookings, newBookings) {
    const oldMap = new Map(oldBookings.map(b => [b.id, b]));
    const newMap = new Map(newBookings.map(b => [b.id, b]));
    
    // Detect new bookings
    newBookings.forEach(booking => {
        if (!oldMap.has(booking.id)) {
            // New booking detected
            addNotification(
                'booking',
                booking.client_name,
                booking.appointment_time,
                `New appointment booked`
            );
        } else {
            // Check for reschedules (time change)
            const oldBooking = oldMap.get(booking.id);
            if (oldBooking.appointment_time !== booking.appointment_time) {
                addNotification(
                    'reschedule',
                    booking.client_name,
                    booking.appointment_time,
                    `Moved from ${new Date(oldBooking.appointment_time).toLocaleString('en-IE')}`
                );
            }
        }
    });
    
    // Detect cancellations
    oldBookings.forEach(booking => {
        if (!newMap.has(booking.id)) {
            addNotification(
                'cancel',
                booking.client_name,
                booking.appointment_time,
                `Appointment cancelled`
            );
        }
    });
}

// Auto-complete overdue appointments
async function triggerAutoComplete() {
    if (!confirm('🤖 Auto-complete all appointments that are more than 24 hours overdue?\\n\\nThis will:\\n• Mark them as completed\\n• Add a system note if no notes exist\\n• Update client AI descriptions\\n\\nContinue?')) {
        return;
    }
    
    const button = event.target;
    const originalText = button.innerHTML;
    button.innerHTML = '<span class="loading"></span> Processing...';
    button.disabled = true;
    
    try {
        const response = await fetch('/api/appointments/auto-complete', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert(`✅ ${data.message}\\n\\nRefreshing dashboard...`);
            await loadStats();
            await loadBookings();
            await loadHomeView();
            await loadUpcomingView();
            await loadPastView();
        } else {
            alert(`❌ Error: ${data.error || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error triggering auto-complete:', error);
        alert('❌ Error triggering auto-complete: ' + error.message);
    } finally {
        button.innerHTML = originalText;
        button.disabled = false;
    }
}

// Auto-refresh dashboard data periodically
function setupAutoRefresh() {
    // Refresh every 30 seconds when page is visible
    setInterval(() => {
        if (!document.hidden) {
            console.log('🔄 Auto-refreshing dashboard data...');
            loadStats();
            loadBookings();
        }
    }, 30000); // 30 seconds
    
    // Also refresh when page becomes visible
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) {
            console.log('🔄 Page visible - refreshing dashboard data...');
            loadStats();
            loadBookings();
        }
    });
}
