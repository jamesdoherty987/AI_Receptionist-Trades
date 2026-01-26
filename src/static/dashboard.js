// AI Trades Receptionist Dashboard JavaScript

// Global state
let allJobs = [];
let allCustomers = [];
let allWorkers = [];
let currentJobFilter = 'all';
let chatConversation = [];

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    initializeTabs();
    loadJobs();
    loadCustomers();
    loadWorkers();
    loadFinances();
    loadCalendar();
    
    // Setup job filters
    document.querySelectorAll('.filter-btn[data-filter]').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.filter-btn[data-filter]').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            currentJobFilter = this.dataset.filter;
            
            // Preserve search term when changing filters
            const searchInput = document.getElementById('jobSearchInput');
            const searchTerm = searchInput ? searchInput.value : null;
            filterJobs(searchTerm);
        });
    });
    
    // Setup Enter key for chat
    const chatInput = document.getElementById('chatInput');
    if (chatInput) {
        chatInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendChatMessage();
            }
        });
    }
    
    console.log('💬 Chat initialized. Conversation has', chatConversation.length, 'messages');
});

// Tab functionality
function initializeTabs() {
    const tabButtons = document.querySelectorAll('.tab-button');
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const tabName = button.dataset.tab;
            
            // Update active states
            document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');
            
            document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
            document.getElementById(tabName + '-tab').classList.add('active');
            
            // Load data when switching tabs
            if (tabName === 'finances') loadFinances();
            if (tabName === 'calendar') loadCalendar();
        });
    });
}

// Load Jobs
async function loadJobs() {
    try {
        const response = await fetch('/api/bookings');
        const bookings = await response.json();
        
        allJobs = bookings.map(booking => ({
            ...booking,
            date: new Date(booking.appointment_time)
        }));
        
        filterJobs();
    } catch (error) {
        console.error('Error loading jobs:', error);
        document.getElementById('jobsContent').innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">❌</div>
                <p>Error loading jobs</p>
            </div>
        `;
    }
}

function filterJobs(searchTerm = null) {
    let filteredJobs = allJobs;
    
    // Filter by status
    if (currentJobFilter !== 'all') {
        filteredJobs = filteredJobs.filter(job => job.status === currentJobFilter);
    }
    
    // Filter by search term
    if (searchTerm && searchTerm.trim() !== '') {
        const term = searchTerm.toLowerCase().trim();
        filteredJobs = filteredJobs.filter(job => {
            const clientName = (job.client_name || '').toLowerCase();
            const service = (job.service_type || '').toLowerCase();
            const phone = (job.phone_number || '').toLowerCase();
            const email = (job.email || '').toLowerCase();
            const address = (job.address || '').toLowerCase();
            
            return clientName.includes(term) || 
                   service.includes(term) || 
                   phone.includes(term) || 
                   email.includes(term) ||
                   address.includes(term);
        });
    }
    
    displayJobs(filteredJobs);
}

// Display jobs as cards
function displayJobs(jobs) {
    const content = document.getElementById('jobsContent');
    
    if (!jobs || jobs.length === 0) {
        content.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📋</div>
                <p>No jobs found</p>
            </div>
        `;
        return;
    }
    
    content.innerHTML = jobs.map(job => `
        <div class="job-card" id="job-${job.id}" onclick="showJobDetail(${job.id})" style="cursor: pointer;">
            <div class="job-header">
                <div>
                    <div class="job-client-name">${escapeHtml(job.client_name || 'Unknown')}</div>
                    <div class="job-date">
                        📅 ${formatDateTime(job.appointment_time)}
                    </div>
                </div>
                <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
                    <span class="badge badge-${getStatusColor(job.status)}">${job.status}</span>
                </div>
            </div>
            <div class="job-details">
                <div class="job-detail-item">
                    <span class="job-detail-label">Service:</span> ${escapeHtml(job.service_type || 'N/A')}
                </div>
                <div class="job-detail-item">
                    <span class="job-detail-label">Phone:</span> ${escapeHtml(job.phone_number || 'N/A')}
                </div>
                <div class="job-detail-item">
                    <span class="job-detail-label">Email:</span> ${escapeHtml(job.email || 'N/A')}
                </div>
                <div class="job-detail-item">
                    <span class="job-detail-label">Address:</span> ${escapeHtml(job.address || 'No address provided')}
                </div>
                ${job.eircode ? `
                <div class="job-detail-item">
                    <span class="job-detail-label">Eircode:</span> ${escapeHtml(job.eircode)}
                </div>
                ` : ''}
                <div class="job-detail-item">
                    <span class="job-detail-label">Charge:</span> €${(job.charge || 0).toFixed(2)}
                </div>
                <div class="job-detail-item" id="workers-display-${job.id}">
                    <span class="job-detail-label">👷 Workers:</span> <span class="worker-loading">Loading...</span>
                </div>
            </div>
            <div style="margin-top: 1rem; display: flex; gap: 0.5rem; flex-wrap: wrap;">
                <button class="btn btn-sm btn-primary" onclick="event.stopPropagation(); showAssignWorkerModal(${job.id})">👷 Assign Worker</button>
                <button class="btn btn-sm btn-secondary job-action-btn" data-booking-id="${job.id}" data-status="in-progress" onclick="event.stopPropagation()">▶ Start Job</button>
                <button class="btn btn-sm btn-success job-action-btn" data-booking-id="${job.id}" data-status="completed" onclick="event.stopPropagation()">✓ Complete</button>
                <button class="btn btn-sm btn-danger job-action-btn" data-booking-id="${job.id}" data-status="cancelled" onclick="event.stopPropagation()">✕ Cancel</button>
                ${(job.address && job.address !== 'No address provided') ? `
                <button class="btn btn-sm btn-primary" onclick="event.stopPropagation(); openDirections('${escapeHtml(job.address)}${job.eircode ? ', ' + escapeHtml(job.eircode) : ''}')">🗺️ Directions</button>
                ` : ''}
            </div>
        </div>
    `).join('');
    
    // Load workers for each job
    jobs.forEach(job => loadJobWorkers(job.id));
    
    // Add event delegation for job action buttons
    setupJobActionButtons();
}

// Setup event delegation for job action buttons
function setupJobActionButtons() {
    const jobsContent = document.getElementById('jobsContent');
    if (!jobsContent) return;
    
    // Remove old listeners by cloning and replacing
    const newJobsContent = jobsContent.cloneNode(true);
    jobsContent.parentNode.replaceChild(newJobsContent, jobsContent);
    
    // Add new listener
    document.getElementById('jobsContent').addEventListener('click', function(e) {
        if (e.target.classList.contains('job-action-btn')) {
            const bookingId = parseInt(e.target.dataset.bookingId);
            const status = e.target.dataset.status;
            changeJobStatus(bookingId, status, e.target);
        }
    });
}

// Load workers assigned to a job
async function loadJobWorkers(jobId) {
    try {
        const response = await fetch(`/api/bookings/${jobId}/workers`);
        const workers = await response.json();
        
        const displayElement = document.getElementById(`workers-display-${jobId}`);
        if (!displayElement) return;
        
        if (workers.length === 0) {
            displayElement.innerHTML = '<span class="job-detail-label">👷 Workers:</span> <span style="color: #94a3b8;">None assigned</span>';
        } else {
            displayElement.innerHTML = `
                <span class="job-detail-label">👷 Workers:</span>
                <div style="display: flex; gap: 0.5rem; flex-wrap: wrap; margin-top: 0.25rem;">
                    ${workers.map(w => `
                        <span class="worker-badge">
                            ${escapeHtml(w.name)}
                            <button onclick="removeWorkerFromJob(${jobId}, ${w.id}); event.stopPropagation();" class="remove-worker-btn" title="Remove">
                                ×
                            </button>
                        </span>
                    `).join('')}
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading job workers:', error);
        const displayElement = document.getElementById(`workers-display-${jobId}`);
        if (displayElement) {
            displayElement.innerHTML = '<span class="job-detail-label">👷 Workers:</span> <span style="color: #ef4444;">Error loading</span>';
        }
    }
}

// Show assign worker modal
function showAssignWorkerModal(jobId) {
    const job = allJobs.find(j => j.id === jobId);
    if (!job) return;
    
    const modalContent = `
        <h2>Assign Worker to Job</h2>
        <div style="margin: 1rem 0; padding: 1rem; background: #f8fafc; border-radius: 8px;">
            <div><strong>Client:</strong> ${escapeHtml(job.client_name || 'Unknown')}</div>
            <div><strong>Time:</strong> ${formatDateTime(job.appointment_time)}</div>
            <div><strong>Service:</strong> ${escapeHtml(job.service_type || 'N/A')}</div>
        </div>
        <div style="margin: 1rem 0;">
            <label style="display: block; margin-bottom: 0.5rem; font-weight: 500;">Select Worker:</label>
            <select id="workerSelect" style="width: 100%; padding: 0.5rem; border: 1px solid #cbd5e1; border-radius: 4px;">
                <option value="">-- Choose a worker --</option>
                ${allWorkers.filter(w => w.status === 'active').map(w => `
                    <option value="${w.id}">${escapeHtml(w.name)} ${w.trade_specialty ? '(' + escapeHtml(w.trade_specialty) + ')' : ''}</option>
                `).join('')}
            </select>
        </div>
        <div id="assignmentError" style="color: #ef4444; margin: 0.5rem 0; display: none;"></div>
        <div style="display: flex; gap: 0.5rem; justify-content: flex-end; margin-top: 1.5rem;">
            <button class="btn btn-secondary" onclick="closeModal('assignWorkerModal')">Cancel</button>
            <button class="btn btn-primary" onclick="assignWorker(${jobId})">Assign Worker</button>
        </div>
    `;
    
    document.getElementById('assignWorkerModalContent').innerHTML = modalContent;
    document.getElementById('assignWorkerModal').classList.add('active');
}

// Assign worker to job
async function assignWorker(jobId) {
    const workerId = document.getElementById('workerSelect').value;
    const errorDiv = document.getElementById('assignmentError');
    
    if (!workerId) {
        errorDiv.textContent = 'Please select a worker';
        errorDiv.style.display = 'block';
        return;
    }
    
    try {
        const response = await fetch(`/api/bookings/${jobId}/assign-worker`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ worker_id: parseInt(workerId) })
        });
        
        const result = await response.json();
        
        if (result.success) {
            closeModal('assignWorkerModal');
            loadJobWorkers(jobId);
        } else {
            errorDiv.textContent = result.error || 'Error assigning worker';
            errorDiv.style.display = 'block';
            
            // If there's a conflict, show details
            if (result.conflict) {
                errorDiv.innerHTML = `
                    <strong>⚠️ Schedule Conflict!</strong><br>
                    This worker is already assigned to:<br>
                    <em>${escapeHtml(result.conflict.client)} - ${formatDateTime(result.conflict.time)}</em>
                `;
            }
        }
    } catch (error) {
        console.error('Error assigning worker:', error);
        errorDiv.textContent = 'Error assigning worker';
        errorDiv.style.display = 'block';
    }
}

// Remove worker from job
async function removeWorkerFromJob(jobId, workerId) {
    if (!confirm('Remove this worker from the job?')) return;
    
    try {
        const response = await fetch(`/api/bookings/${jobId}/remove-worker`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ worker_id: workerId })
        });
        
        if (response.ok) {
            loadJobWorkers(jobId);
        } else {
            alert('Error removing worker');
        }
    } catch (error) {
        console.error('Error removing worker:', error);
        alert('Error removing worker');
    }
}

// Load Customers
async function loadCustomers() {
    try {
        const response = await fetch('/api/clients');
        allCustomers = await response.json();
        
        displayCustomers();
    } catch (error) {
        console.error('Error loading customers:', error);
        document.getElementById('customersTable').innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">❌</div>
                <p>Error loading customers</p>
            </div>
        `;
    }
}

// Alias for consistency with addClient function
const loadClients = loadCustomers;

// Display customers table
function displayCustomers(filteredCustomers = null) {
    const container = document.getElementById('customersTable');
    const customersToDisplay = filteredCustomers || allCustomers;
    
    if (customersToDisplay.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">👥</div>
                <p>${filteredCustomers ? 'No customers match your search' : 'No customers yet'}</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = `
        <div class="table-wrapper">
        <table class="table">
            <thead>
                <tr>
                    <th>Name</th>
                    <th>Phone</th>
                    <th>Email</th>
                    <th>Total Jobs</th>
                    <th>Last Visit</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                ${customersToDisplay.map(customer => `
                    <tr>
                        <td><strong>${escapeHtml(customer.name)}</strong></td>
                        <td>${escapeHtml(customer.phone || 'N/A')}</td>
                        <td>${escapeHtml(customer.email || 'N/A')}</td>
                        <td>${customer.total_appointments || 0}</td>
                        <td>${customer.last_visit ? formatDate(customer.last_visit) : 'Never'}</td>
                        <td>
                            <button class="btn btn-secondary btn-sm" onclick="showClientDetail(${customer.id})">View</button>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
        </div>
    `;
}

// Filter clients by search term
function filterClients(searchTerm) {
    if (!searchTerm || searchTerm.trim() === '') {
        // Show all clients if search is empty
        displayCustomers();
        return;
    }
    
    const term = searchTerm.toLowerCase().trim();
    const filtered = allCustomers.filter(customer => {
        const name = (customer.name || '').toLowerCase();
        const phone = (customer.phone || '').toLowerCase();
        const email = (customer.email || '').toLowerCase();
        
        return name.includes(term) || phone.includes(term) || email.includes(term);
    });
    
    displayCustomers(filtered);
}

// Load Workers
async function loadWorkers() {
    try {
        const response = await fetch('/api/workers');
        allWorkers = await response.json();
        
        displayWorkers();
    } catch (error) {
        console.error('Error loading workers:', error);
        document.getElementById('workersContent').innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">❌</div>
                <p>Error loading workers</p>
            </div>
        `;
    }
}

// Display workers
function displayWorkers() {
    const container = document.getElementById('workersContent');
    
    if (allWorkers.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">👷</div>
                <p>No workers added yet</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = allWorkers.map(worker => `
        <div class="worker-card" onclick="showWorkerDetail(${worker.id})" style="cursor: pointer;">
            <div class="worker-info">
                <h3>${escapeHtml(worker.name)}</h3>
                <div class="worker-details">
                    <div>📞 ${escapeHtml(worker.phone || 'N/A')}</div>
                    <div>✉️ ${escapeHtml(worker.email || 'N/A')}</div>
                    <div>🔧 ${escapeHtml(worker.trade_specialty || 'General')}</div>
                </div>
            </div>
        </div>
    `).join('');
}

// Load Finances
async function loadFinances() {
    try {
        const response = await fetch('/api/finances/stats');
        const stats = await response.json();
        
        document.getElementById('totalRevenue').textContent = `€${(stats.total_revenue || 0).toFixed(2)}`;
        document.getElementById('paidAmount').textContent = `€${(stats.paid_total || 0).toFixed(2)}`;
        document.getElementById('unpaidAmount').textContent = `€${(stats.unpaid_total || 0).toFixed(2)}`;
        
        // Load transactions
        const bookingsResponse = await fetch('/api/bookings');
        const bookings = await bookingsResponse.json();
        
        displayFinances(bookings);
    } catch (error) {
        console.error('Error loading finances:', error);
    }
}

// Load Calendar
async function loadCalendar() {
    try {
        const response = await fetch('/api/bookings');
        const bookings = await response.json();
        
        // Create calendar view
        displayCalendar(bookings);
    } catch (error) {
        console.error('Error loading calendar:', error);
        document.getElementById('calendarContent').innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">❌</div>
                <p>Error loading calendar</p>
            </div>
        `;
    }
}

// Display calendar
function displayCalendar(bookings) {
    const container = document.getElementById('calendarContent');
    
    if (!bookings || bookings.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📅</div>
                <p>No appointments scheduled</p>
            </div>
        `;
        return;
    }
    
    // Get current date
    const today = new Date();
    const currentMonth = today.getMonth();
    const currentYear = today.getFullYear();
    
    // Create calendar HTML with navigation
    let html = `
        <div style="padding: 1.5rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem;">
                <button class="btn btn-secondary btn-sm" onclick="navigateMonth(-1)">← Previous</button>
                <h2 id="calendarMonthYear" style="font-size: 1.5rem; font-weight: 600; color: #0f172a;"></h2>
                <button class="btn btn-secondary btn-sm" onclick="navigateMonth(1)">Next →</button>
            </div>
            <div id="calendarGrid"></div>
        </div>
    `;
    
    container.innerHTML = html;
    
    // Store bookings globally for navigation
    window.calendarBookings = bookings;
    window.calendarCurrentMonth = currentMonth;
    window.calendarCurrentYear = currentYear;
    
    // Render the calendar
    renderCalendarMonth();
}

// Navigate between months
function navigateMonth(direction) {
    window.calendarCurrentMonth += direction;
    
    if (window.calendarCurrentMonth > 11) {
        window.calendarCurrentMonth = 0;
        window.calendarCurrentYear++;
    } else if (window.calendarCurrentMonth < 0) {
        window.calendarCurrentMonth = 11;
        window.calendarCurrentYear--;
    }
    
    renderCalendarMonth();
}

// Render calendar month
function renderCalendarMonth() {
    const month = window.calendarCurrentMonth;
    const year = window.calendarCurrentYear;
    const bookings = window.calendarBookings || [];
    
    // Update header
    const monthNames = ['January', 'February', 'March', 'April', 'May', 'June',
                       'July', 'August', 'September', 'October', 'November', 'December'];
    document.getElementById('calendarMonthYear').textContent = `${monthNames[month]} ${year}`;
    
    // Get first day of month and number of days
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const daysInMonth = lastDay.getDate();
    const startingDayOfWeek = firstDay.getDay();
    
    // Group bookings by date
    const bookingsByDate = {};
    bookings.forEach(booking => {
        try {
            const bookingDate = new Date(booking.appointment_time);
            if (bookingDate.getMonth() === month && bookingDate.getFullYear() === year) {
                const dateKey = bookingDate.getDate();
                if (!bookingsByDate[dateKey]) {
                    bookingsByDate[dateKey] = [];
                }
                bookingsByDate[dateKey].push(booking);
            }
        } catch (e) {
            console.error('Error parsing booking date:', booking.appointment_time);
        }
    });
    
    // Build calendar grid
    let html = `
        <div style="display: grid; grid-template-columns: repeat(7, 1fr); gap: 1px; background: #e2e8f0; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden;">
            <!-- Day headers -->
            <div style="background: #6366f1; color: white; padding: 0.75rem; text-align: center; font-weight: 600;">Sun</div>
            <div style="background: #6366f1; color: white; padding: 0.75rem; text-align: center; font-weight: 600;">Mon</div>
            <div style="background: #6366f1; color: white; padding: 0.75rem; text-align: center; font-weight: 600;">Tue</div>
            <div style="background: #6366f1; color: white; padding: 0.75rem; text-align: center; font-weight: 600;">Wed</div>
            <div style="background: #6366f1; color: white; padding: 0.75rem; text-align: center; font-weight: 600;">Thu</div>
            <div style="background: #6366f1; color: white; padding: 0.75rem; text-align: center; font-weight: 600;">Fri</div>
            <div style="background: #6366f1; color: white; padding: 0.75rem; text-align: center; font-weight: 600;">Sat</div>
    `;
    
    // Add empty cells for days before month starts
    for (let i = 0; i < startingDayOfWeek; i++) {
        html += '<div style="background: #f8fafc; min-height: 120px;"></div>';
    }
    
    // Add calendar days
    const today = new Date();
    const isCurrentMonth = today.getMonth() === month && today.getFullYear() === year;
    
    for (let day = 1; day <= daysInMonth; day++) {
        const isToday = isCurrentMonth && today.getDate() === day;
        const dayBookings = bookingsByDate[day] || [];
        
        html += `
            <div style="background: white; min-height: 120px; padding: 0.5rem; position: relative; ${isToday ? 'border: 2px solid #6366f1;' : ''}">
                <div style="font-weight: 600; color: ${isToday ? '#6366f1' : '#0f172a'}; margin-bottom: 0.5rem; font-size: 0.875rem;">
                    ${day}
                    ${isToday ? '<span style="background: #6366f1; color: white; padding: 0.125rem 0.5rem; border-radius: 999px; font-size: 0.75rem; margin-left: 0.25rem;">Today</span>' : ''}
                </div>
                <div style="display: flex; flex-direction: column; gap: 0.25rem;">
        `;
        
        // Sort bookings by time
        dayBookings.sort((a, b) => new Date(a.appointment_time) - new Date(b.appointment_time));
        
        // Show up to 3 bookings per day
        dayBookings.slice(0, 3).forEach(booking => {
            const time = new Date(booking.appointment_time).toLocaleTimeString('en-US', { 
                hour: 'numeric', 
                minute: '2-digit',
                hour12: true 
            });
            const statusColor = getStatusColor(booking.status);
            const bgColor = statusColor === 'success' ? '#dcfce7' : statusColor === 'warning' ? '#fef3c7' : '#dbeafe';
            const textColor = statusColor === 'success' ? '#166534' : statusColor === 'warning' ? '#92400e' : '#1e40af';
            
            html += `
                <div onclick="showJobDetail(${booking.id})" style="
                    background: ${bgColor};
                    color: ${textColor};
                    padding: 0.375rem;
                    border-radius: 4px;
                    font-size: 0.75rem;
                    cursor: pointer;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                " title="${escapeHtml(booking.client_name)} - ${time}">
                    <strong>${time}</strong> ${escapeHtml(booking.client_name)}
                </div>
            `;
        });
        
        // Show "more" indicator if there are more than 3 bookings
        if (dayBookings.length > 3) {
            html += `
                <div style="font-size: 0.75rem; color: #6366f1; font-weight: 600; padding: 0.25rem;">
                    +${dayBookings.length - 3} more
                </div>
            `;
        }
        
        html += `
                </div>
            </div>
        `;
    }
    
    // Add empty cells to complete the grid
    const totalCells = startingDayOfWeek + daysInMonth;
    const remainingCells = 7 - (totalCells % 7);
    if (remainingCells < 7) {
        for (let i = 0; i < remainingCells; i++) {
            html += '<div style="background: #f8fafc; min-height: 120px;"></div>';
        }
    }
    
    html += '</div>';
    
    document.getElementById('calendarGrid').innerHTML = html;
}


// Display finances table
function displayFinances(bookings) {
    const container = document.getElementById('financesTable');
    
    if (bookings.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">💰</div>
                <p>No transactions yet</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = `
        <div class="table-wrapper">
        <table class="table">
            <thead>
                <tr>
                    <th>Customer</th>
                    <th>Date</th>
                    <th>Service</th>
                    <th>Amount</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                ${bookings.map(booking => `
                    <tr>
                        <td><strong>${escapeHtml(booking.client_name || 'Unknown')}</strong></td>
                        <td>${formatDate(booking.appointment_time)}</td>
                        <td>${escapeHtml(booking.service_type || 'N/A')}</td>
                        <td>€${(booking.charge || 0).toFixed(2)}</td>
                        <td><span class="badge badge-${booking.payment_status === 'paid' ? 'success' : 'warning'}">${booking.payment_status || 'unpaid'}</span></td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
        </div>
    `;
}

// Show client detail
async function showClientDetail(clientId) {
    try {
        const response = await fetch(`/api/clients/${clientId}`);
        const client = await response.json();
        
        document.getElementById('clientDetailName').textContent = client.name;
        document.getElementById('clientDetailContent').innerHTML = `
            <div>
                <h3 style="margin-bottom: 1rem;">Contact Information</h3>
                <p><strong>Phone:</strong> ${escapeHtml(client.phone || 'N/A')}</p>
                <p><strong>Email:</strong> ${escapeHtml(client.email || 'N/A')}</p>
                <p><strong>Total Jobs:</strong> ${client.total_appointments || 0}</p>
                <p><strong>First Visit:</strong> ${client.first_visit ? formatDate(client.first_visit) : 'N/A'}</p>
                <p><strong>Last Visit:</strong> ${client.last_visit ? formatDate(client.last_visit) : 'N/A'}</p>
                
                ${client.description ? `
                    <h3 style="margin-top: 1.5rem; margin-bottom: 1rem;">Notes</h3>
                    <p>${escapeHtml(client.description)}</p>
                ` : ''}
                
                <h3 style="margin-top: 1.5rem; margin-bottom: 1rem;">Job History</h3>
                ${client.bookings && client.bookings.length > 0 ? `
                    <div class="table-wrapper">
                    <table class="table">
                        <thead>
                            <tr>
                                <th>Date</th>
                                <th>Service</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${client.bookings.map(booking => `
                                <tr>
                                    <td>${formatDateTime(booking.appointment_time)}</td>
                                    <td>${escapeHtml(booking.service_type || 'N/A')}</td>
                                    <td><span class="badge badge-${getStatusColor(booking.status)}">${booking.status}</span></td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                    </div>
                ` : '<p>No job history</p>'}
            </div>
        `;
        
        document.getElementById('clientDetailModal').classList.add('active');
    } catch (error) {
        console.error('Error loading customer details:', error);
        alert('Error loading customer details');
    }
}

// Show job detail with notes and invoice option
async function showJobDetail(bookingId) {
    try {
        // Fetch booking details
        const bookingResponse = await fetch(`/api/bookings`);
        const allBookings = await bookingResponse.json();
        const job = allBookings.find(b => b.id === bookingId);
        
        if (!job) {
            alert('Job not found');
            return;
        }
        
        // Fetch notes for this job
        const notesResponse = await fetch(`/api/bookings/${bookingId}/notes`);
        const notes = await notesResponse.json();
        
        // Build comprehensive job details section
        let detailsHtml = `
            <div style="background: #f8fafc; border-radius: 12px; padding: 1.5rem; margin-bottom: 2rem; border: 2px solid #e2e8f0;">
                <h3 style="margin: 0 0 1.5rem 0; color: #1e293b; font-size: 1.25rem;">📋 Job Details</h3>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.5rem;">
                    <div>
                        <div style="color: #64748b; font-size: 0.875rem; margin-bottom: 0.25rem;">Customer</div>
                        <div style="font-weight: 600; font-size: 1.1rem;">${escapeHtml(job.client_name || 'N/A')}</div>
                    </div>
                    <div>
                        <div style="color: #64748b; font-size: 0.875rem; margin-bottom: 0.25rem;">Date & Time</div>
                        <div style="font-weight: 600;">${formatDateTime(job.appointment_time)}</div>
                    </div>
                    <div>
                        <div style="color: #64748b; font-size: 0.875rem; margin-bottom: 0.25rem;">Service Requested</div>
                        <div style="font-weight: 600;">${escapeHtml(job.service_type || 'Not specified')}</div>
                    </div>
                    <div>
                        <div style="color: #64748b; font-size: 0.875rem; margin-bottom: 0.25rem;">Status</div>
                        <div><span class="badge badge-${getStatusColor(job.status)}">${job.status}</span></div>
                    </div>
                    ${job.address ? `
                    <div style="grid-column: 1 / -1;">
                        <div style="color: #64748b; font-size: 0.875rem; margin-bottom: 0.25rem;">📍 Job Address</div>
                        <div style="font-weight: 600; font-size: 1.1rem;">${escapeHtml(job.address)}</div>
                    </div>
                    ` : ''}
                </div>
            </div>
            
            <div style="background: #f8fafc; border-radius: 12px; padding: 1.5rem; margin-bottom: 2rem; border: 2px solid #e2e8f0;">
                <h3 style="margin: 0 0 1.5rem 0; color: #1e293b; font-size: 1.25rem;">📞 Contact Information</h3>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.5rem;">
                    <div>
                        <div style="color: #64748b; font-size: 0.875rem; margin-bottom: 0.25rem;">Phone Number</div>
                        <div style="font-weight: 600;">${escapeHtml(job.phone_number || 'Not provided')}</div>
                    </div>
                    <div>
                        <div style="color: #64748b; font-size: 0.875rem; margin-bottom: 0.25rem;">Email Address</div>
                        <div style="font-weight: 600;">${escapeHtml(job.email || 'Not provided')}</div>
                    </div>
                </div>
            </div>
        `;
        
        // Add property information if available
        if (job.address || job.eircode || job.property_type) {
            detailsHtml += `
                <div style="background: #f8fafc; border-radius: 12px; padding: 1.5rem; margin-bottom: 2rem; border: 2px solid #e2e8f0;">
                    <h3 style="margin: 0 0 1.5rem 0; color: #1e293b; font-size: 1.25rem;">🏠 Property Details</h3>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.5rem;">
                        ${job.address ? `
                        <div>
                            <div style="color: #64748b; font-size: 0.875rem; margin-bottom: 0.25rem;">Address</div>
                            <div style="font-weight: 600;">${escapeHtml(job.address)}</div>
                        </div>
                        ` : ''}
                        ${job.eircode ? `
                        <div>
                            <div style="color: #64748b; font-size: 0.875rem; margin-bottom: 0.25rem;">Eircode</div>
                            <div style="font-weight: 600;">${escapeHtml(job.eircode)}</div>
                        </div>
                        ` : ''}
                        ${job.property_type ? `
                        <div>
                            <div style="color: #64748b; font-size: 0.875rem; margin-bottom: 0.25rem;">Property Type</div>
                            <div style="font-weight: 600;">${escapeHtml(job.property_type)}</div>
                        </div>
                        ` : ''}
                        ${job.urgency && job.urgency !== 'scheduled' ? `
                        <div>
                            <div style="color: #64748b; font-size: 0.875rem; margin-bottom: 0.25rem;">Urgency</div>
                            <div style="font-weight: 600; color: #ef4444;">${escapeHtml(job.urgency)}</div>
                        </div>
                        ` : ''}
                    </div>
                </div>
            `;
        }
        
        // Add payment information
        detailsHtml += `
            <div style="background: #f8fafc; border-radius: 12px; padding: 1.5rem; margin-bottom: 2rem; border: 2px solid #e2e8f0;">
                <h3 style="margin: 0 0 1.5rem 0; color: #1e293b; font-size: 1.25rem;">💰 Payment Information</h3>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.5rem;">
                    <div>
                        <div style="color: #64748b; font-size: 0.875rem; margin-bottom: 0.25rem;">Charge Amount</div>
                        <div style="font-size: 1.75rem; font-weight: 700; color: #10b981;">€${(job.charge || 0).toFixed(2)}</div>
                    </div>
                    <div>
                        <div style="color: #64748b; font-size: 0.875rem; margin-bottom: 0.25rem;">Payment Status</div>
                        <div style="margin-top: 0.5rem;">
                            ${job.payment_status === 'paid' 
                                ? '<span class="badge badge-success" style="font-size: 1rem; padding: 0.5rem 1rem;">Paid</span>' 
                                : '<span class="badge badge-warning" style="font-size: 1rem; padding: 0.5rem 1rem;">Unpaid</span>'}
                        </div>
                    </div>
                    ${job.payment_method ? `
                    <div>
                        <div style="color: #64748b; font-size: 0.875rem; margin-bottom: 0.25rem;">Payment Method</div>
                        <div style="font-weight: 600;">${escapeHtml(job.payment_method)}</div>
                    </div>
                    ` : ''}
                </div>
            </div>
        `;
        
        // Add additional notes if available
        if (notes && notes.length > 0) {
            const notesHtml = notes.map(note => {
                // Replace placeholder text with actual database values
                let noteText = note.note;
                
                // Replace address placeholders
                if (job.address) {
                    noteText = noteText.replace(/same address on file/gi, job.address);
                    noteText = noteText.replace(/address on file/gi, job.address);
                }
                
                // Replace eircode placeholders
                if (job.eircode) {
                    noteText = noteText.replace(/same eircode on file/gi, job.eircode);
                    noteText = noteText.replace(/eircode on file/gi, job.eircode);
                }
                
                // Replace phone placeholders
                if (job.phone_number) {
                    noteText = noteText.replace(/same phone number on file/gi, job.phone_number);
                    noteText = noteText.replace(/phone number on file/gi, job.phone_number);
                    noteText = noteText.replace(/same number on file/gi, job.phone_number);
                }
                
                // Replace email placeholders
                if (job.email) {
                    noteText = noteText.replace(/same email on file/gi, job.email);
                    noteText = noteText.replace(/email on file/gi, job.email);
                }
                
                return `
                    <div style="background: white; padding: 1rem; border-radius: 8px; margin-bottom: 0.75rem; border-left: 3px solid #3b82f6;">
                        <p style="margin: 0; white-space: pre-wrap; color: #334155;">${escapeHtml(noteText)}</p>
                        <small style="color: #94a3b8; margin-top: 0.5rem; display: block;">
                            Added by ${note.created_by} • ${formatDateTime(note.created_at)}
                        </small>
                    </div>
                `;
            }).join('');
            
            detailsHtml += `
                <div style="background: #f8fafc; border-radius: 12px; padding: 1.5rem; margin-bottom: 2rem; border: 2px solid #e2e8f0;">
                    <h3 style="margin: 0 0 1rem 0; color: #1e293b; font-size: 1.25rem;">📝 Additional Notes</h3>
                    ${notesHtml}
                </div>
            `;
        }
        
        document.getElementById('jobDetailTitle').textContent = `Job Details: ${job.client_name || 'Unknown'}`;
        document.getElementById('jobDetailContent').innerHTML = `
            <div>
                ${detailsHtml}
                
                <div style="display: flex; gap: 1rem; padding-top: 1.5rem; border-top: 2px solid #e2e8f0; flex-wrap: wrap;">
                    <button class="btn btn-primary" onclick="sendInvoice(${bookingId})" id="invoiceBtn-${bookingId}">
                        📧 Send Invoice
                    </button>
                    ${(job.address && job.address !== 'No address provided') ? `
                    <button class="btn btn-primary" onclick="openDirections('${escapeHtml(job.address)}${job.eircode ? ', ' + escapeHtml(job.eircode) : ''}')">
                        🗺️ Get Directions
                    </button>
                    ` : ''}
                    <button class="btn btn-secondary" onclick="closeModal('jobDetailModal')">
                        Close
                    </button>
                </div>
            </div>
        `;
        
        document.getElementById('jobDetailModal').classList.add('active');
    } catch (error) {
        console.error('Error loading job details:', error);
        alert('Error loading job details');
    }
}

// Send invoice via email
async function sendInvoice(bookingId) {
    const btn = document.getElementById(`invoiceBtn-${bookingId}`);
    if (!btn) return;
    
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = '📤 Sending...';
    
    try {
        const response = await fetch(`/api/bookings/${bookingId}/send-invoice`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const data = await response.json();
        
        if (response.ok) {
            btn.textContent = '✅ Invoice Sent!';
            btn.style.background = '#10b981';
            setTimeout(() => {
                btn.textContent = originalText;
                btn.style.background = '';
                btn.disabled = false;
            }, 3000);
        } else {
            throw new Error(data.error || 'Failed to send invoice');
        }
    } catch (error) {
        console.error('Error sending invoice:', error);
        btn.textContent = '❌ Failed';
        btn.style.background = '#ef4444';
        alert('Error sending invoice: ' + error.message);
        setTimeout(() => {
            btn.textContent = originalText;
            btn.style.background = '';
            btn.disabled = false;
        }, 3000);
    }
}


// Change job status
async function changeJobStatus(bookingId, newStatus, buttonElement) {
    if (!buttonElement) return;
    
    // Add loading state
    buttonElement.classList.add('loading');
    buttonElement.disabled = true;
    
    try {
        const response = await fetch(`/api/bookings/${bookingId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        });
        
        if (response.ok) {
            // Show success feedback
            buttonElement.style.background = '#10b981';
            buttonElement.textContent = '✓ Done';
            
            setTimeout(() => {
                loadJobs(); // Reload jobs
            }, 400);
        } else {
            buttonElement.classList.remove('loading');
            buttonElement.disabled = false;
            alert('Error updating job status');
        }
    } catch (error) {
        console.error('Error updating job status:', error);
        buttonElement.classList.remove('loading');
        buttonElement.disabled = false;
        alert('Error updating job status');
    }
}

// Modal functions
function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
}

// Close modals when clicking outside
window.addEventListener('click', function(event) {
    if (event.target.classList.contains('modal')) {
        event.target.classList.remove('active');
    }
});

// Utility functions
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
}

function formatDate(dateString) {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-IE', { 
        year: 'numeric', 
        month: 'short', 
        day: 'numeric' 
    });
}

function formatDateTime(dateString) {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleString('en-IE', { 
        year: 'numeric', 
        month: 'short', 
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function getStatusColor(status) {
    switch (status) {
        case 'completed':
            return 'success';
        case 'scheduled':
            return 'primary';
        case 'in-progress':
            return 'warning';
        case 'cancelled':
            return 'danger';
        default:
            return 'secondary';
    }
}

// Placeholder functions for future features
function showAddClientModal() {
    document.getElementById('addClientModal').classList.add('active');
}

function showAddWorkerModal() {
    document.getElementById('addWorkerModal').classList.add('active');
}

// Show Add Job Modal
async function showAddJobModal() {
    // Load customers into dropdown
    try {
        const response = await fetch('/api/clients');
        const clients = await response.json();
        
        // Store all clients globally for filtering
        window.allJobClients = clients;
        
        const select = document.getElementById('jobClient');
        select.innerHTML = '<option value="" disabled selected>Select a customer...</option>';
        select.size = 1; // Reset to normal dropdown
        
        clients.forEach(client => {
            const option = document.createElement('option');
            option.value = client.id;
            option.textContent = `${client.name}${client.phone ? ' - ' + client.phone : ''}`;
            option.dataset.name = client.name.toLowerCase();
            option.dataset.phone = (client.phone || '').toLowerCase();
            select.appendChild(option);
        });
        
        // Clear search input
        document.getElementById('jobClientSearch').value = '';
        
        // Set default date to tomorrow at 9 AM
        const tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        tomorrow.setHours(9, 0, 0, 0);
        
        document.getElementById('jobDate').value = tomorrow.toISOString().split('T')[0];
        document.getElementById('jobTime').value = '09:00';
        
        // Clear other fields
        document.getElementById('jobService').value = '';
        document.getElementById('jobAddress').value = '';
        document.getElementById('jobEircode').value = '';
        document.getElementById('jobPropertyType').value = '';
        document.getElementById('jobCharge').value = '';
        document.getElementById('jobNotes').value = '';
        
        document.getElementById('addJobModal').classList.add('active');
    } catch (error) {
        console.error('Error loading customers:', error);
        alert('Error loading customer list');
    }
}

// Filter job client dropdown based on search
function filterJobClientDropdown(searchTerm) {
    const select = document.getElementById('jobClient');
    const options = select.querySelectorAll('option');
    
    if (!searchTerm || searchTerm.trim() === '') {
        // Show all options and reset to normal dropdown
        options.forEach(option => {
            option.style.display = '';
        });
        select.value = '';
        return;
    }
    
    const term = searchTerm.toLowerCase().trim();
    let visibleCount = 0;
    let firstVisibleOption = null;
    
    options.forEach(option => {
        if (option.value === '') {
            option.style.display = 'none'; // Hide the placeholder
            return;
        }
        
        const name = option.dataset.name || '';
        const phone = option.dataset.phone || '';
        
        if (name.includes(term) || phone.includes(term)) {
            option.style.display = '';
            visibleCount++;
            if (!firstVisibleOption) {
                firstVisibleOption = option;
            }
        } else {
            option.style.display = 'none';
        }
    });
    
    // Auto-select if only one match
    if (visibleCount === 1 && firstVisibleOption) {
        select.value = firstVisibleOption.value;
    } else if (visibleCount === 0) {
        select.value = '';
    }
}

// Set quick date for job scheduling
function setQuickDate(type) {
    const dateInput = document.getElementById('jobDate');
    const timeInput = document.getElementById('jobTime');
    const now = new Date();
    
    let targetDate = new Date();
    let targetTime = '09:00';
    
    switch(type) {
        case 'today':
            // If it's past 9 AM, set to next available hour, otherwise 9 AM
            if (now.getHours() >= 9) {
                const nextHour = now.getHours() + 1;
                targetTime = `${String(nextHour).padStart(2, '0')}:00`;
            }
            break;
            
        case 'tomorrow':
            targetDate.setDate(targetDate.getDate() + 1);
            targetTime = '09:00';
            break;
            
        case 'nextWeek':
            // Next Monday at 9 AM
            const daysUntilMonday = (8 - targetDate.getDay()) % 7 || 7;
            targetDate.setDate(targetDate.getDate() + daysUntilMonday);
            targetTime = '09:00';
            break;
            
        case 'custom':
            // Just focus on the date input
            dateInput.focus();
            return;
    }
    
    dateInput.value = targetDate.toISOString().split('T')[0];
    timeInput.value = targetTime;
}

// Add new job
async function addJob(event) {
    event.preventDefault();
    
    // Get the submit button and add loading state
    const submitBtn = event.target.querySelector('button[type="submit"]');
    const originalText = submitBtn.textContent;
    
    // Disable button and show loading state
    submitBtn.disabled = true;
    submitBtn.classList.add('loading');
    submitBtn.textContent = '⏳ Creating Job...';
    
    // Combine date and time
    const dateValue = document.getElementById('jobDate').value;
    const timeValue = document.getElementById('jobTime').value;
    const dateTimeString = `${dateValue}T${timeValue}:00`;
    
    const jobData = {
        client_id: parseInt(document.getElementById('jobClient').value),
        appointment_time: dateTimeString,
        service_type: document.getElementById('jobService').value,
        address: document.getElementById('jobAddress').value || null,
        eircode: document.getElementById('jobEircode').value || null,
        property_type: document.getElementById('jobPropertyType').value || null,
        charge: parseFloat(document.getElementById('jobCharge').value) || null,
        notes: document.getElementById('jobNotes').value || null
    };
    
    try {
        const response = await fetch('/api/bookings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(jobData)
        });
        
        const result = await response.json();
        
        if (response.ok) {
            closeModal('addJobModal');
            await loadJobs(); // Reload jobs list
            alert('✅ Job created successfully!');
        } else if (response.status === 409) {
            // Time conflict error
            alert('⚠️ ' + result.error);
        } else {
            alert('Error: ' + (result.error || 'Failed to create job'));
        }
    } catch (error) {
        console.error('Error creating job:', error);
        alert('Error creating job');
    } finally {
        // Re-enable button and restore original state
        submitBtn.disabled = false;
        submitBtn.classList.remove('loading');
        submitBtn.textContent = originalText;
    }
}

// Add new client
async function addClient(event) {
    event.preventDefault();
    
    // Get the submit button and add loading state
    const submitBtn = event.target.querySelector('button[type="submit"]');
    const originalText = submitBtn.textContent;
    
    // Disable button and show loading state
    submitBtn.disabled = true;
    submitBtn.textContent = '⏳ Adding...';
    
    const clientData = {
        name: document.getElementById('clientName').value,
        phone: document.getElementById('clientPhone').value || null,
        email: document.getElementById('clientEmail').value || null
    };
    
    try {
        const response = await fetch('/api/clients', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(clientData)
        });
        
        const result = await response.json();
        
        if (response.ok) {
            closeModal('addClientModal');
            await loadClients(); // Reload customers list
            alert('✅ Customer added successfully!');
        } else {
            alert('Error: ' + (result.error || 'Failed to add customer'));
        }
    } catch (error) {
        console.error('Error adding customer:', error);
        alert('Error adding customer');
    } finally {
        // Re-enable button and restore original state
        submitBtn.disabled = false;
        submitBtn.textContent = originalText;
    }
}

// Add new worker
async function addWorker(event) {
    event.preventDefault();
    
    // Get the submit button and add loading state
    const submitBtn = event.target.querySelector('button[type="submit"]');
    const originalText = submitBtn.textContent;
    
    // Disable button and show loading state
    submitBtn.disabled = true;
    submitBtn.textContent = '⏳ Adding...';
    
    const workerData = {
        name: document.getElementById('workerName').value,
        phone: document.getElementById('workerPhone').value || null,
        email: document.getElementById('workerEmail').value || null,
        trade_specialty: document.getElementById('workerTrade').value || null
    };
    
    try {
        const response = await fetch('/api/workers', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(workerData)
        });
        
        const result = await response.json();
        
        if (response.ok) {
            closeModal('addWorkerModal');
            await loadWorkers(); // Reload workers list
            alert('✅ Worker added successfully!');
        } else {
            alert('Error: ' + (result.error || 'Failed to add worker'));
        }
    } catch (error) {
        console.error('Error adding worker:', error);
        alert('Error adding worker');
    } finally {
        // Re-enable button and restore original state
        submitBtn.disabled = false;
        submitBtn.textContent = originalText;
    }
}

// Show worker detail modal
async function showWorkerDetail(workerId) {
    try {
        const response = await fetch(`/api/workers/${workerId}`);
        const worker = await response.json();
        
        if (!worker || worker.error) {
            alert('Worker not found');
            return;
        }
        
        // Get worker's jobs
        const jobsResponse = await fetch(`/api/workers/${workerId}/jobs?include_completed=true`);
        const jobs = await jobsResponse.json();
        
        const activeJobs = jobs.filter(j => j.status !== 'completed' && j.status !== 'cancelled');
        const completedJobs = jobs.filter(j => j.status === 'completed' || j.status === 'cancelled');
        
        document.getElementById('workerDetailContent').innerHTML = `
            <div class="detail-header">
                <h2>👷 ${escapeHtml(worker.name)}</h2>
            </div>
            
            <div style="background: #f8fafc; padding: 1.5rem; border-radius: 8px; margin: 1rem 0;">
                <h3 style="margin-bottom: 1rem;">Contact Information</h3>
                <div class="form-group">
                    <label class="form-label">Name</label>
                    <input type="text" class="form-input" id="editWorkerName" value="${escapeHtml(worker.name)}">
                </div>
                <div class="form-group">
                    <label class="form-label">Phone</label>
                    <input type="tel" class="form-input" id="editWorkerPhone" value="${escapeHtml(worker.phone || '')}">
                </div>
                <div class="form-group">
                    <label class="form-label">Email</label>
                    <input type="email" class="form-input" id="editWorkerEmail" value="${escapeHtml(worker.email || '')}">
                </div>
                <div class="form-group">
                    <label class="form-label">Trade Specialty</label>
                    <input type="text" class="form-input" id="editWorkerTrade" value="${escapeHtml(worker.trade_specialty || '')}" placeholder="e.g., Electrician, Plumber">
                </div>
                <div style="display: flex; gap: 0.5rem; margin-top: 1rem;">
                    <button class="btn btn-primary" onclick="saveWorkerChanges(${workerId})">💾 Save Changes</button>
                    <button class="btn btn-danger" onclick="deleteWorker(${workerId})">🗑️ Delete Worker</button>
                </div>
            </div>
            
            <div style="margin-top: 2rem;">
                <h3>📋 Active Jobs (${activeJobs.length})</h3>
                ${activeJobs.length > 0 ? `
                    <div style="margin-top: 1rem;">
                        ${activeJobs.map(job => `
                            <div style="background: white; border: 1px solid #e2e8f0; padding: 1rem; margin-bottom: 0.5rem; border-radius: 6px;">
                                <div style="display: flex; justify-content: space-between; align-items: start;">
                                    <div>
                                        <strong>${escapeHtml(job.client_name || 'Unknown')}</strong>
                                        <div style="color: #64748b; font-size: 0.875rem;">
                                            📅 ${formatDateTime(job.appointment_time)}
                                        </div>
                                        <div style="color: #64748b; font-size: 0.875rem;">
                                            ${escapeHtml(job.service_type || 'N/A')}
                                        </div>
                                    </div>
                                    <span class="badge badge-${getStatusColor(job.status)}">${job.status}</span>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                ` : '<p style="color: #94a3b8; margin-top: 0.5rem;">No active jobs</p>'}
            </div>
            
            <div style="margin-top: 2rem;">
                <h3>✅ Completed Jobs (${completedJobs.length})</h3>
                ${completedJobs.length > 0 ? `
                    <div style="margin-top: 1rem; max-height: 300px; overflow-y: auto;">
                        ${completedJobs.slice(0, 10).map(job => `
                            <div style="background: #f8fafc; border: 1px solid #e2e8f0; padding: 0.75rem; margin-bottom: 0.5rem; border-radius: 6px; font-size: 0.875rem;">
                                <div style="display: flex; justify-content: space-between;">
                                    <div>
                                        <strong>${escapeHtml(job.client_name || 'Unknown')}</strong> - ${formatDateTime(job.appointment_time)}
                                    </div>
                                    <span class="badge badge-${getStatusColor(job.status)}">${job.status}</span>
                                </div>
                            </div>
                        `).join('')}
                        ${completedJobs.length > 10 ? `<p style="color: #64748b; font-size: 0.875rem; margin-top: 0.5rem;">Showing 10 of ${completedJobs.length} completed jobs</p>` : ''}
                    </div>
                ` : '<p style="color: #94a3b8; margin-top: 0.5rem;">No completed jobs</p>'}
            </div>
        `;
        
        document.getElementById('workerDetailModal').classList.add('active');
    } catch (error) {
        console.error('Error loading worker details:', error);
        alert('Error loading worker details');
    }
}

// Save worker changes
async function saveWorkerChanges(workerId) {
    const name = document.getElementById('editWorkerName').value.trim();
    const phone = document.getElementById('editWorkerPhone').value.trim();
    const email = document.getElementById('editWorkerEmail').value.trim();
    const trade_specialty = document.getElementById('editWorkerTrade').value.trim();
    
    if (!name) {
        alert('Worker name is required');
        return;
    }
    
    try {
        const response = await fetch(`/api/workers/${workerId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, phone, email, trade_specialty })
        });
        
        if (response.ok) {
            closeModal('workerDetailModal');
            loadWorkers();
        } else {
            alert('Error updating worker');
        }
    } catch (error) {
        console.error('Error updating worker:', error);
        alert('Error updating worker');
    }
}

// Delete worker
async function deleteWorker(workerId) {
    if (!confirm('Are you sure you want to delete this worker? This cannot be undone.')) return;
    
    try {
        const response = await fetch(`/api/workers/${workerId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            closeModal('workerDetailModal');
            loadWorkers();
        } else {
            alert('Error deleting worker');
        }
    } catch (error) {
        console.error('Error deleting worker:', error);
        alert('Error deleting worker');
    }
}

// Chat functionality
async function sendChatMessage() {
    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    
    if (!message) return;
    
    console.log('💬 User message:', message);
    
    // Clear input
    input.value = '';
    
    // Add user message to UI
    addChatMessage('user', message);
    
    // Show typing indicator
    const typingId = addChatMessage('assistant', 'Typing...');
    
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: message,
                conversation: chatConversation
            })
        });
        
        const data = await response.json();
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        // Update conversation
        chatConversation = data.conversation;
        
        console.log('🤖 AI response:', data.response);
        console.log('📋 Full conversation (' + data.conversation.length + ' messages):', data.conversation);
        
        // Check if response is empty or just whitespace
        const cleanResponse = data.response.trim();
        if (!cleanResponse) {
            console.error('⚠️ Empty response received from server!');
            replaceChatMessage(typingId, 'assistant', 'I apologize, I had trouble responding. Could you please try again?');
            return;
        }
        
        // Replace typing indicator with actual response
        replaceChatMessage(typingId, 'assistant', data.response);
        
    } catch (error) {
        console.error('❌ Chat error:', error);
        console.error('Error details:', error.message, error.stack);
        replaceChatMessage(typingId, 'assistant', '❌ Error: ' + error.message);
    }
}

// Open Google Maps directions
function openDirections(address) {
    if (!address || address === 'No address provided') {
        alert('No address available for this job');
        return;
    }
    
    // Encode the address for URL
    const encodedAddress = encodeURIComponent(address);
    
    // Open Google Maps in a new tab with directions
    // This will show directions from the user's current location to the destination
    const mapsUrl = `https://www.google.com/maps/dir/?api=1&destination=${encodedAddress}`;
    
    window.open(mapsUrl, '_blank');
}

function addChatMessage(role, text) {
    const messagesDiv = document.getElementById('chatMessages');
    const messageId = 'msg-' + Date.now();
    
    // Remove the empty state message if it exists
    const emptyState = messagesDiv.querySelector('.empty-state, div[style*=\"text-align: center\"]');
    if (emptyState) {
        emptyState.remove();
    }
    
    const messageDiv = document.createElement('div');
    messageDiv.id = messageId;
    messageDiv.style.cssText = `
        margin-bottom: 1rem;
        padding: 0.75rem 1rem;
        border-radius: 8px;
        max-width: 80%;
        ${role === 'user' ? 'background: #2563eb; color: white; margin-left: auto;' : 'background: white; border: 1px solid #e2e8f0;'}
    `;
    messageDiv.textContent = text;
    
    messagesDiv.appendChild(messageDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
    
    console.log('💬 Added ' + role + ' message:', text.substring(0, 50) + (text.length > 50 ? '...' : ''));
    
    return messageId;
}

function replaceChatMessage(messageId, role, text) {
    const messageDiv = document.getElementById(messageId);
    if (messageDiv) {
        messageDiv.textContent = text;
    }
}

async function resetChat() {
    if (!confirm('Are you sure you want to reset the chat?')) return;
    
    try {
        await fetch('/api/chat/reset', {
            method: 'POST'
        });
        
        // Clear conversation
        chatConversation = [];
        
        // Clear UI
        const messagesDiv = document.getElementById('chatMessages');
        messagesDiv.innerHTML = `
            <div style="text-align: center; color: #64748b; padding: 2rem;">
                <p>💬 Start a conversation with the AI receptionist</p>
                <p style="font-size: 0.875rem; margin-top: 0.5rem;">This uses the same AI as phone calls - perfect for testing!</p>
            </div>
        `;
        
    } catch (error) {
        console.error('Reset error:', error);
        alert('Error resetting chat: ' + error.message);
    }
}

// Function to display full conversation history (useful for debugging)
function displayConversationHistory() {
    console.log('📋 Displaying conversation history (' + chatConversation.length + ' messages)');
    const messagesDiv = document.getElementById('chatMessages');
    
    // Clear the messages div first
    messagesDiv.innerHTML = '';
    
    // Display each message in the conversation
    for (const msg of chatConversation) {
        // Skip system messages (they're internal)
        if (msg.role === 'system') continue;
        
        // Add user or assistant message
        if (msg.role === 'user' || msg.role === 'assistant') {
            addChatMessage(msg.role, msg.content);
        }
    }
}
