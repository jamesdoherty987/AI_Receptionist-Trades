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
    
    // Setup job filters
    document.querySelectorAll('.filter-btn[data-filter]').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.filter-btn[data-filter]').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            currentJobFilter = this.dataset.filter;
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
            
            // Load data when switching tabs
            if (tabName === 'finances') loadFinances();
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

function filterJobs() {
    let filteredJobs = allJobs;
    
    // Filter by status
    if (currentJobFilter !== 'all') {
        filteredJobs = filteredJobs.filter(job => job.status === currentJobFilter);
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
        <div class="job-card">
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
                <div class="job-detail-item">
                    <span class="job-detail-label">Charge:</span> €${(job.charge || 0).toFixed(2)}
                </div>
            </div>
            <div style="margin-top: 1rem; display: flex; gap: 0.5rem; flex-wrap: wrap;">
                <button class="btn btn-sm btn-secondary job-action-btn" data-booking-id="${job.id}" data-status="in-progress">▶ Start Job</button>
                <button class="btn btn-sm btn-success job-action-btn" data-booking-id="${job.id}" data-status="completed">✓ Complete</button>
                <button class="btn btn-sm btn-danger job-action-btn" data-booking-id="${job.id}" data-status="cancelled">✕ Cancel</button>
            </div>
        </div>
    `).join('');
    
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
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                ${allCustomers.map(customer => `
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
        console.error('Error loading customer details:', error);
        alert('Error loading customer details');
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
    alert('Add client feature coming soon!');
}

function showAddWorkerModal() {
    alert('Add worker feature coming soon!');
}

function editWorker(workerId) {
    alert('Edit worker feature coming soon!');
}

function deleteWorker(workerId) {
    if (confirm('Are you sure you want to delete this worker?')) {
        // TODO: Implement delete
        alert('Delete worker feature coming soon!');
    }
}

// Chat functionality
async function sendChatMessage() {
    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    
    if (!message) return;
    
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
        
        // Replace typing indicator with actual response
        replaceChatMessage(typingId, 'assistant', data.response);
        
    } catch (error) {
        console.error('Chat error:', error);
        replaceChatMessage(typingId, 'assistant', '❌ Error: ' + error.message);
    }
}

function addChatMessage(role, text) {
    const messagesDiv = document.getElementById('chatMessages');
    const messageId = 'msg-' + Date.now();
    
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
