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
        <div class="job-card" id="job-${job.id}">
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
                <div class="job-detail-item" id="workers-display-${job.id}">
                    <span class="job-detail-label">👷 Workers:</span> <span class="worker-loading">Loading...</span>
                </div>
            </div>
            <div style="margin-top: 1rem; display: flex; gap: 0.5rem; flex-wrap: wrap;">
                <button class="btn btn-sm btn-primary" onclick="showAssignWorkerModal(${job.id})">👷 Assign Worker</button>
                <button class="btn btn-sm btn-secondary" onclick="changeJobStatus(${job.id}, 'in-progress')">Start Job</button>
                <button class="btn btn-sm btn-success" onclick="changeJobStatus(${job.id}, 'completed')">Mark Complete</button>
                <button class="btn btn-sm btn-danger" onclick="changeJobStatus(${job.id}, 'cancelled')">Cancel</button>
            </div>
        </div>
    `).join('');
    
    // Load workers for each job
    jobs.forEach(job => loadJobWorkers(job.id));
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
                            <button onclick="removeWorkerFromJob(${jobId}, ${w.id})" class="remove-worker-btn" title="Remove">
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
let messageCounter = 0; // Counter to ensure unique message IDs

async function sendChatMessage() {
    // Initialize chatConversation if not already defined
    if (typeof chatConversation === 'undefined') {
        chatConversation = [];
    }
    
    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    
    if (!message) return;
    
    // Clear input immediately
    input.value = '';
    
    // Add user message to UI
    addChatMessage('user', message);
    
    // Add a small delay to ensure unique IDs
    await new Promise(resolve => setTimeout(resolve, 10));
    
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
    // Use both timestamp and counter for truly unique IDs
    const messageId = 'msg-' + Date.now() + '-' + (messageCounter++);
    const wrapperId = 'wrapper-' + messageId;
    
    // Create wrapper div for proper alignment
    const wrapperDiv = document.createElement('div');
    wrapperDiv.id = wrapperId;
    wrapperDiv.style.cssText = `
        display: flex;
        margin-bottom: 0.5rem;
        ${role === 'user' ? 'justify-content: flex-end;' : 'justify-content: flex-start;'}
    `;
    
    // Create message div
    const messageDiv = document.createElement('div');
    messageDiv.id = messageId;
    messageDiv.className = role + '-message';
    messageDiv.style.cssText = `
        padding: 0.75rem 1rem;
        border-radius: 8px;
        max-width: 80%;
        word-wrap: break-word;
        ${role === 'user' ? 'background: #2563eb; color: white;' : 'background: #f1f5f9; border: 1px solid #e2e8f0; color: #1e293b;'}
    `;
    messageDiv.textContent = text;
    
    wrapperDiv.appendChild(messageDiv);
    messagesDiv.appendChild(wrapperDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
    
    return messageId;
}

function replaceChatMessage(messageId, role, text) {
    const messageDiv = document.getElementById(messageId);
    if (messageDiv) {
        // Safety check - only replace assistant messages to prevent overwriting user messages
        if (messageDiv.className === 'assistant-message' || messageDiv.className === '') {
            messageDiv.textContent = text;
            messageDiv.className = role + '-message';
            // Ensure styling is correct
            messageDiv.style.cssText = `
                padding: 0.75rem 1rem;
                border-radius: 8px;
                max-width: 80%;
                word-wrap: break-word;
                ${role === 'user' ? 'background: #2563eb; color: white;' : 'background: #f1f5f9; border: 1px solid #e2e8f0; color: #1e293b;'}
            `;
        } else {
            console.warn('Attempted to replace', messageDiv.className, 'with', role, '- skipping for safety');
        }
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
