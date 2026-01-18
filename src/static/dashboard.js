// AI Trades Receptionist Dashboard JavaScript

// Global state
let allJobs = [];
let allCustomers = [];
let allWorkers = [];
let currentJobFilter = 'all';
let currentUrgencyFilter = 'all';
let chatConversation = [];

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    initializeTabs();
    loadJobs();
    loadCustomers();
    loadWorkers();
    loadFinances();
    
    // Setup test email button
    document.getElementById('sendTestEmail').addEventListener('click', sendTestEmail);
    
    // Setup job filters
    document.querySelectorAll('.filter-btn[data-filter]').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.filter-btn[data-filter]').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            currentJobFilter = this.dataset.filter;
            filterJobs();
        });
    });
    
    // Setup urgency filters
    document.querySelectorAll('.filter-btn[data-urgency]').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.filter-btn[data-urgency]').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            currentUrgencyFilter = this.dataset.urgency;
            filterJobs();
        });
    });
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
    // Filter by status
    if (currentJobFilter !== 'all') {
        if (currentJobFilter === 'scheduled') {
            filteredJobs = filteredJobs.filter(job => job.status === 'scheduled');
        } else if (currentJobFilter === 'in-progress') {
            filteredJobs = filteredJobs.filter(job => job.status === 'in-progress');
        } else if (currentJobFilter === 'completed') {
            filteredJobs = filteredJobs.filter(job => job.status === 'completed');
        } else if (currentJobFilter === 'cancelled') {
            filteredJobs = filteredJobs.filter(job => job.status === 'cancelled');
        }
    }
    
    // Filter by urgency
    if (currentUrgencyFilter !== 'all') {
        filteredJobs = filteredJobs.filter(job => (job.urgency || 'scheduled') === currentUrgencyFilter
function filterJobs() {
    const now = new Date();
    let filteredJobs = allJobs;
    
    if (currentJobFilter === 'upcoming') {
        filteredJobs = allJobs.filter(job => job.date > now && job.status !== 'completed');
    } else if (currentJobFilter === 'in-progress') {
        filteredJobs = allJobs.filter(job => job.status === 'scheduled' && job.date <= now);
    } else if (currentJobFilter === 'past') {
        filteredJobs = allJobs.filter(job => job.status === 'completed' || job.date < now);
    }
    
    displayJobs(filteredJobs);
}

// Display jobs as cards
function displayJobs(jobs) {
    const content = document.getElementById('jobsContent');
    div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
                    <span class="badge badge-${getUrgencyColor(job.urgency || 'scheduled')}">${getUrgencyLabel(job.urgency || 'scheduled')}</span>
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
                ${job.address ? `
                <div class="job-detail-item">
                    <span class="job-detail-label">Address:</span> ${escapeHtml(job.address)}
                </div>
                ` : ''}
                ${job.eircode ? `
                <div class="job-detail-item">
                    <span class="job-detail-label">Eircode:</span> ${escapeHtml(job.eircode)}
                </div>
                ` : ''}
                ${job.property_type ? `
                <div class="job-detail-item">
                    <span class="job-detail-label">Property:</span> ${escapeHtml(job.property_type)}
                </div>
                ` : ''}
                <div class="job-detail-item">
                    <span class="job-detail-label">Charge:</span> €${(job.charge || 0).toFixed(2)}
                </div>
            </div>
            <div style="margin-top: 1rem; display: flex; gap: 0.5rem;">
                <button class="btn btn-sm btn-secondary" onclick="changeJobStatus(${job.id}, 'in-progress')">Start Job</button>
                <button class="btn btn-sm btn-success" onclick="changeJobStatus(${job.id}, 'completed')">Mark Complete</button>
                <button class="btn btn-sm btn-danger" onclick="changeJobStatus(${job.id}, 'cancelled')">Cancel</button
                    <div class="job-client-name">${escapeHtml(job.client_name || 'Unknown')}</div>
                    <div class="job-date">
                        📅 ${formatDateTime(job.appointment_time)}
                    </div>
                </div>
                <span class="badge badge-${getStatusColor(job.status)}">${job.status}</span>
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
                    <span class="job-detail-label">Charge:</span> €${(job.charge || 0).toFixed(2)}
                </div>
            </div>
        </div>
    `).join('');
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

// Display customers table
function displayCustomers() {
    const container = document.getElementById('customersTable');
    
    if (allCustomers.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">👥</div>
                <p>No customers yet</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = `
        <table class="table">
            <thead>
                <tr>
                    <th>Name</th>
                    <th>Phone</th>
                    <th>Email</th>
                    <th>Total Jobs</th>
                    <th>Last Visit</th>
                </tr>
            </thead>
            <tbody>
                ${allCustomers.map(customer => `
                    <tr onclick="showClientDetail(${customer.id})" style="cursor: pointer;">
                        <td><strong>${escapeHtml(customer.name)}</strong></td>
                        <td>${escapeHtml(customer.phone || 'N/A')}</td>
                        <td>${escapeHtml(customer.email || 'N/A')}</td>
                        <td>${customer.total_appointments || 0}</td>
                        <td>${customer.last_visit ? formatDate(customer.last_visit) : 'Never'}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
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
        <div class="worker-card">
            <div class="worker-info">
                <h3>${escapeHtml(worker.name)}</h3>
                <div class="worker-details">
                    <div>📞 ${escapeHtml(worker.phone || 'N/A')}</div>
                    <div>✉️ ${escapeHtml(worker.email || 'N/A')}</div>
                    <div>🔧 ${escapeHtml(worker.trade_specialty || 'General')}</div>
                </div>
            </div>
            <div class="worker-actions">
                <button class="btn btn-secondary btn-sm" onclick="editWorker(${worker.id})">Edit</button>
                <button class="btn btn-danger btn-sm" onclick="deleteWorker(${worker.id})">Delete</button>
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
    `;
}

// Modal functions
function showAddClientModal() {
    document.getElementById('addClientModal').classList.add('active');
}

function showAddWorkerModal() {
    document.getElementById('addWorkerModal').classList.add('active');
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
}

// Add customer
async function addClient(event) {
    event.preventDefault();
    
    const name = document.getElementById('clientName').value;
    const phone = document.getElementById('clientPhone').value;
    const email = document.getElementById('clientEmail').value;
    
    try {
        const response = await fetch('/api/clients', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, phone, email })
        });
        
        if (response.ok) {
            closeModal('addClientModal');
            loadCustomers();
            // Reset form
            document.getElementById('clientName').value = '';
            document.getElementById('clientPhone').value = '';
            document.getElementById('clientEmail').value = '';
        }
    } catch (error) {
        console.error('Error adding customer:', error);
        alert('Error adding customer');
    }
}

// Add worker
async function addWorker(event) {
    event.preventDefault();
    
    const name = document.getElementById('workerName').value;
    const phone = document.getElementById('workerPhone').value;
    const email = document.getElementById('workerEmail').value;
    const trade_specialty = document.getElementById('workerTrade').value;
    
    try {
        const response = await fetch('/api/workers', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, phone, email, trade_specialty })
        });
        
        if (response.ok) {
            closeModal('addWorkerModal');
            loadWorkers();
            // Reset form
            document.getElementById('workerName').value = '';
            document.getElementById('workerPhone').value = '';
            document.getElementById('workerEmail').value = '';
            document.getElementById('workerTrade').value = '';
        }
    } catch (error) {
        console.error('Error adding worker:', error);
        alert('Error adding worker');
    }
}

// Delete worker
async function deleteWorker(workerId) {
    if (!confirm('Are you sure you want to delete this worker?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/workers/${workerId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            loadWorkers();
        }
    } catch (error) {
        console.error('Error deleting worker:', error);
        alert('Error deleting worker');
    }
}

// Edit worker (simplified - just reload for now)
function editWorker(workerId) {
    alert('Edit functionality coming soon!');
}

// Send test email
async function sendTestEmail() {
    try {
        const response = await fetch('/api/email/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert('✅ Test email sent successfully!');
        } else {
            alert('❌ Error sending email: ' + result.error);
        }
    } catch (error) {
        console.error('Error sending test email:', error);
        alert('❌ Error sending test email');
    }
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
                ` : '<p>No job history</p>'}
            </div>
        `;
        
        document.getElementById('clientDetailModal').classList.add('active');
    } catch (error) {
        console.error('Error loading client details:', error);
        alert('Error loading customer details');
    }
}

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

function getUrgencyColor(urgency) {
    switch (urgency) {
        case 'emergency':
            return 'danger';
        case 'same-day':
            return 'warning';
        case 'scheduled':
            return 'primary';
        case 'quote':
            return 'secondary';
        default:
            return 'secondary';
    }
}

function getUrgencyLabel(urgency) {
    switch (urgency) {
        case 'emergency':
            return '🚨 Emergency';
        case 'same-day':
            return '⚡ Same-Day';
        case 'scheduled':
            return '📅 Scheduled';
        case 'quote':
            return '💬 Quote';
        default:
            return urgency;
    }
}

// Change job status
async function changeJobStatus(bookingId, newStatus) {
    try {
        const response = await fetch(`/api/bookings/${bookingId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        });
        
        if (response.ok) {
            loadJobs(); // Reload jobs
        } else {
            alert('Error updating job status');
        }
    } catch (error) {
        console.error('Error updating job status:', error);
        alert('Error updating job status');
    }
}

// Close modals when clicking outside
window.addEventListener('click', function(event) {
    if (event.target.classList.contains('modal')) {
        event.target.classList.remove('active');
    }
});

// Chat functionality
async function sendChatMessage() {
    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    
    if (!message) return;
    
    // Add user message to UI
    const messagesDiv = document.getElementById('chatMessages');
    messagesDiv.innerHTML += `
        <div style="background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%); color: white; border-radius: 12px; padding: 1rem; margin-bottom: 1rem; margin-left: 20%; text-align: right;">
            <strong>You:</strong> ${escapeHtml(message)}
        </div>
    `;
    
    // Clear input
    input.value = '';
    
    // Scroll to bottom
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
    
    // Add loading indicator
    messagesDiv.innerHTML += `
        <div id="loadingMsg" style="background: white; border: 2px solid #e2e8f0; border-radius: 12px; padding: 1rem; margin-bottom: 1rem; margin-right: 20%;">
            <strong>AI Receptionist:</strong> <span style="color: #64748b;">Typing...</span>
        </div>
    `;
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
    
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: message,
                conversation: chatConversation
            })
        });
        
        const data = await response.json();
        
        // Remove loading indicator
        document.getElementById('loadingMsg').remove();
        
        // Add AI response
        messagesDiv.innerHTML += `
            <div style="background: white; border: 2px solid #e2e8f0; border-radius: 12px; padding: 1rem; margin-bottom: 1rem; margin-right: 20%;">
                <strong>AI Receptionist:</strong> ${escapeHtml(data.response)}
            </div>
        `;
        
        // Update conversation
        chatConversation = data.conversation;
        
        // Scroll to bottom
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
        
    } catch (error) {
        console.error('Error sending message:', error);
        document.getElementById('loadingMsg').remove();
        messagesDiv.innerHTML += `
            <div style="background: #fee2e2; border: 2px solid #ef4444; border-radius: 12px; padding: 1rem; margin-bottom: 1rem;">
                <strong>Error:</strong> Failed to send message
            </div>
        `;
    }
}

async function resetChat() {
    try {
        await fetch('/api/chat/reset', { method: 'POST' });
        chatConversation = [];
        
        const messagesDiv = document.getElementById('chatMessages');
        messagesDiv.innerHTML = `
            <div style="background: white; border: 2px solid #e2e8f0; border-radius: 12px; padding: 1rem; margin-bottom: 1rem;">
                <strong>AI Receptionist:</strong> Hi, thank you for calling. How can I help you today?
            </div>
        `;
    } catch (error) {
        console.error('Error resetting chat:', error);
    }
}

