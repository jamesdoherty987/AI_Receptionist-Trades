import axios from 'axios';

// Use environment variable for API URL, fallback to relative path for local dev
const API_URL = import.meta.env.VITE_API_URL || '';

// Warn if API URL is empty in production (common misconfiguration)
if (!API_URL && import.meta.env.PROD) {
  console.warn(
    '[API] VITE_API_URL is not set. API calls will use relative paths. ' +
    'This only works if the backend is on the same domain or a proxy is configured.'
  );
}

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // Still send cookies when they work
  timeout: 30000,
});

// Request interceptor: attach auth token header on every request.
// This is the reliable fallback when cross-origin cookies are blocked.
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('authToken');
  if (token) {
    config.headers['X-Auth-Token'] = token;
    // Debug: log that we're attaching the token (only for auth endpoints)
    if (config.url?.includes('/api/auth/')) {
      console.log('[API] Attaching X-Auth-Token to', config.url);
    }
  }
  return config;
});

// Response interceptor: only redirect on 401 for non-auth endpoints
// and only if we have no local auth state (prevents false logouts).
api.interceptors.response.use(
  (response) => {
    // Detect if we got HTML back instead of JSON (API URL misconfiguration)
    const contentType = response.headers?.['content-type'] || '';
    if (contentType.includes('text/html') && response.config?.url?.includes('/api/')) {
      console.error('[API] Got HTML response for API call — API URL may be misconfigured. URL:', response.config.url);
      return Promise.reject(new Error('Server returned an unexpected response. Please try again or clear the app cache.'));
    }
    return response;
  },
  (error) => {
    if (
      error.response?.status === 401 &&
      !error.config?.url?.includes('/api/auth/')
    ) {
      // Only wipe auth if we don't have a token — if we do, the token
      // itself is expired/invalid and we should force re-login.
      const hasToken = !!localStorage.getItem('authToken');
      if (hasToken) {
        localStorage.removeItem('authUser');
        localStorage.removeItem('authSubscription');
        localStorage.removeItem('authToken');
        if (window.location.pathname !== '/login' && 
            window.location.pathname !== '/signup' &&
            window.location.pathname !== '/' &&
            window.location.pathname !== '/forgot-password' &&
            window.location.pathname !== '/reset-password' &&
            window.location.pathname !== '/set-password' &&
            window.location.pathname !== '/bfy-ops' &&
            !window.location.pathname.startsWith('/employee/')) {
          window.location.href = '/login';
        }
        if (window.location.pathname.startsWith('/employee/') &&
            window.location.pathname !== '/employee/login' &&
            window.location.pathname !== '/employee/set-password' &&
            window.location.pathname !== '/employee/forgot-password' &&
            window.location.pathname !== '/employee/reset-password') {
          window.location.href = '/employee/login';
        }
      }
    }

    // Handle 403 subscription required — show friendly message
    if (
      error.response?.status === 403 &&
      error.response?.data?.subscription_status === 'inactive'
    ) {
      const subData = error.response.data.subscription;
      if (subData) {
        localStorage.setItem('authSubscription', JSON.stringify(subData));
      }
      // Replace the raw error with a user-friendly message
      error.response.data.error = 'Please upgrade your plan to use this feature.';
      error.response.data.friendly = true;
      // Only redirect for write operations (POST/PUT/DELETE), not reads
      const method = (error.config?.method || '').toUpperCase();
      if (method !== 'GET' && !window.location.pathname.startsWith('/settings')) {
        window.location.href = '/settings?tab=subscription';
      }
    }

    // Handle 500 errors — replace raw server errors with friendly messages
    if (error.response?.status === 500) {
      const rawError = error.response?.data?.error || '';
      // Don't expose internal server errors to users
      if (!error.response.data) error.response.data = {};
      error.response.data.error = 'Something went wrong. Please try again.';
      error.response.data.friendly = true;
      console.error('[API] Server error:', rawError);
    }

    return Promise.reject(error);
  }
);

// Authentication
export const login = (email, password) => api.post('/api/auth/login', { email, password });
export const signup = (data) => api.post('/api/auth/signup', data);
export const logout = () => api.post('/api/auth/logout');
export const getCurrentUser = () => api.get('/api/auth/me');
export const updateProfile = (data) => api.put('/api/auth/profile', data);
export const changePassword = (currentPassword, newPassword) => 
  api.post('/api/auth/change-password', { current_password: currentPassword, new_password: newPassword });
export const forgotPassword = (email) => api.post('/api/auth/forgot-password', { email });
export const resetPassword = (token, newPassword) => 
  api.post('/api/auth/reset-password', { token, new_password: newPassword });
export const deleteAccount = (confirmation) => 
  api.post('/api/auth/delete-account', { confirmation }, { timeout: 120000 });
export const exportUserData = () => api.get('/api/auth/export-data', { responseType: 'blob', timeout: 120000 });

// Bookings / Jobs
export const getBookings = () => api.get('/api/bookings');
export const getBooking = (id) => api.get(`/api/bookings/${id}`);
export const createBooking = (data) => api.post('/api/bookings', data);
export const updateBooking = (id, data) => api.put(`/api/bookings/${id}`, data);
export const deleteBooking = (id) => api.delete(`/api/bookings/${id}`);
export const rejectBooking = (id, reason = '') => api.post(`/api/bookings/${id}/reject`, { reason });
export const checkAvailability = (date, serviceType, employeeId = null, anyEmployee = false, durationMinutes = null) => api.get('/api/bookings/availability', { params: { date, service_type: serviceType, employee_id: employeeId, any_employee: anyEmployee || undefined, duration_minutes: durationMinutes || undefined } });
export const checkMonthlyAvailability = (year, month, serviceType, employeeId = null, anyEmployee = false, durationMinutes = null) => api.get('/api/bookings/availability/month', { params: { year, month, service_type: serviceType, employee_id: employeeId, any_employee: anyEmployee || undefined, duration_minutes: durationMinutes || undefined } });

// Dashboard - Batch endpoint for better performance
export const getDashboardData = () => api.get('/api/dashboard');

// Clients
export const getClients = () => api.get('/api/clients');
export const getClient = (id) => api.get(`/api/clients/${id}`);
export const createClient = (data) => api.post('/api/clients', data);
export const updateClient = (id, data) => api.put(`/api/clients/${id}`, data);
export const deleteClient = (id) => api.delete(`/api/clients/${id}`);
export const addClientNote = (id, note) => api.post(`/api/clients/${id}/notes`, { note });
export const getClientTimeline = (id) => api.get(`/api/clients/${id}/timeline`);

// Settings
export const getBusinessSettings = () => api.get('/api/settings/business');
export const updateBusinessSettings = (data) => api.post('/api/settings/business', data);

export const getDeveloperSettings = () => api.get('/api/settings/developer');
export const updateDeveloperSettings = (data) => api.post('/api/settings/developer', data);

export const getAIReceptionistStatus = () => api.get('/api/ai-receptionist/toggle');
export const toggleAIReceptionist = (enabled, ai_schedule_override) => {
  const data = { enabled };
  if (ai_schedule_override !== undefined) data.ai_schedule_override = ai_schedule_override;
  return api.post('/api/ai-receptionist/toggle', data);
};
export const updateAISchedule = (enabled, ai_schedule) => api.post('/api/ai-receptionist/toggle', { enabled, ai_schedule });

export const getSettingsHistory = () => api.get('/api/settings/history');

// Services Menu
export const getServicesMenu = () => api.get('/api/services/menu');
export const updateServicesMenu = (data) => api.post('/api/services/menu', data);
export const createService = (data) => api.post('/api/services/menu/service', data);
export const updateService = (id, data) => api.put(`/api/services/menu/service/${id}`, data);
export const deleteService = (id) => api.delete(`/api/services/menu/service/${id}`);

// Packages
export const getPackages = () => api.get('/api/packages');
export const createPackage = (data) => api.post('/api/packages', data);
export const updatePackage = (id, data) => api.put(`/api/packages/${id}`, data);
export const deletePackage = (id) => api.delete(`/api/packages/${id}`);

// Materials Catalog
export const getMaterials = () => api.get('/api/materials');
export const createMaterial = (data) => api.post('/api/materials', data);
export const updateMaterial = (id, data) => api.put(`/api/materials/${id}`, data);
export const deleteMaterial = (id) => api.delete(`/api/materials/${id}`);
export const adjustMaterialStock = (id, adjustment) => api.post(`/api/materials/${id}/adjust-stock`, { adjustment });

// Job Materials
export const getJobMaterials = (bookingId) => api.get(`/api/bookings/${bookingId}/materials`);
export const addJobMaterial = (bookingId, data) => api.post(`/api/bookings/${bookingId}/materials`, data);
export const updateJobMaterial = (bookingId, itemId, data) => api.put(`/api/bookings/${bookingId}/materials/${itemId}`, data);
export const deleteJobMaterial = (bookingId, itemId) => api.delete(`/api/bookings/${bookingId}/materials/${itemId}`);

// Employee Job Materials
export const getEmployeeJobMaterials = (jobId) => api.get(`/api/employee/jobs/${jobId}/materials`);
export const addEmployeeJobMaterial = (jobId, data) => api.post(`/api/employee/jobs/${jobId}/materials`, data);
export const deleteEmployeeJobMaterial = (jobId, itemId) => api.delete(`/api/employee/jobs/${jobId}/materials/${itemId}`);

export const getBusinessHours = () => api.get('/api/services/business-hours');
export const updateBusinessHours = (data) => api.post('/api/services/business-hours', data);

// Employees
export const getEmployees = () => api.get('/api/employees');
export const getEmployee = (id) => api.get(`/api/employees/${id}`);
export const createEmployee = (data) => api.post('/api/employees', data);
export const updateEmployee = (id, data) => api.put(`/api/employees/${id}`, data);
export const deleteEmployee = (id) => api.delete(`/api/employees/${id}`);
export const getEmployeeJobs = (id) => api.get(`/api/employees/${id}/jobs`);
export const getEmployeeSchedule = (id) => api.get(`/api/employees/${id}/schedule`);
export const getEmployeeWorkSchedule = (id) => api.get(`/api/employees/${id}/work-schedule`);
export const updateEmployeeWorkSchedule = (id, workSchedule) => api.put(`/api/employees/${id}/work-schedule`, { work_schedule: workSchedule });
export const getAllEmployeeWorkSchedules = () => api.get('/api/employees/work-schedules');
export const getMyWorkSchedule = () => api.get('/api/employee/my-work-schedule');
export const getEmployeeHoursThisWeek = (id) => api.get(`/api/employees/${id}/hours-this-week`);
// Batch: fetches hours-this-week for all employees in the company in one request
export const getEmployeesHoursThisWeek = () => api.get('/api/employees/hours-this-week');
export const checkEmployeeAvailability = (id, appointmentTime, durationMinutes) => 
  api.get(`/api/employees/${id}/availability`, { params: { appointment_time: appointmentTime, duration_minutes: durationMinutes } });

// Job-Employee Assignment
export const assignEmployeeToJob = (jobId, data) => api.post(`/api/bookings/${jobId}/assign-employee`, data);
export const removeEmployeeFromJob = (jobId, data) => api.post(`/api/bookings/${jobId}/remove-employee`, data);
export const getJobEmployees = (jobId) => api.get(`/api/bookings/${jobId}/employees`);
export const getAvailableEmployeesForJob = (jobId) => api.get(`/api/bookings/${jobId}/available-employees`);

// Job Photos & Videos
export const uploadJobMedia = (jobId, file) => {
  const formData = new FormData();
  formData.append('file', file);
  return api.post(`/api/bookings/${jobId}/photos`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000, // 2 min for large videos
  });
};
export const uploadJobPhoto = (jobId, imageData) => api.post(`/api/bookings/${jobId}/photos`, { image: imageData });
export const deleteJobPhoto = (jobId, photoUrl) => api.post(`/api/bookings/${jobId}/photos/delete`, { photo_url: photoUrl });

// Finances
export const getFinances = (range = 'year') => api.get('/api/finances', { params: { range } });
export const getFinanceStats = () => api.get('/api/finances/stats');
export const markBookingsPaid = (scope) => api.post('/api/finances/mark-paid', { scope });

// Invoices
export const sendInvoice = (bookingId, invoiceData = null) => 
  api.post(`/api/bookings/${bookingId}/send-invoice`, invoiceData || {});
export const getInvoiceConfig = () => api.get('/api/invoice-config');
// Batch: invoice-config + services menu + packages in a single round-trip
export const getJobSetupData = () => api.get('/api/job-setup-data');

// Calendar
export const getCalendarEvents = (params) => api.get('/api/calendar/events', { params });

// Google Calendar OAuth
export const getGoogleCalendarStatus = () => api.get('/api/google-calendar/status');
export const connectGoogleCalendar = () => api.post('/api/google-calendar/connect');
export const disconnectGoogleCalendar = () => api.post('/api/google-calendar/disconnect');
export const syncGoogleCalendar = () => api.post('/api/google-calendar/sync', {}, { timeout: 120000 });

// Accounting Integration (Xero / QuickBooks)
export const getAccountingStatus = () => api.get('/api/accounting/status');
export const setAccountingProvider = (provider) => api.post('/api/accounting/provider', { provider });
export const connectXero = () => api.post('/api/accounting/xero/connect');
export const disconnectXero = () => api.post('/api/accounting/xero/disconnect');
export const connectQuickBooks = () => api.post('/api/accounting/quickbooks/connect');
export const disconnectQuickBooks = () => api.post('/api/accounting/quickbooks/disconnect');

// AI Chat
export const sendChatMessage = (message, conversation) => 
  api.post('/api/chat', { message, conversation });

// Subscription & Billing
export const getSubscriptionStatus = () => api.get('/api/subscription/status');
export const createCheckoutSession = (baseUrl, plan = 'pro') => 
  api.post('/api/subscription/create-checkout', { base_url: baseUrl, plan });
export const getBillingPortalUrl = (baseUrl) => 
  api.post('/api/subscription/billing-portal', { base_url: baseUrl });
export const cancelSubscription = () => api.post('/api/subscription/cancel');
export const reactivateSubscription = () => api.post('/api/subscription/reactivate');
export const upgradeSubscription = (plan) => api.post('/api/subscription/upgrade', { plan });
export const startFreeTrial = () => api.post('/api/subscription/start-trial');
export const getInvoices = () => api.get('/api/subscription/invoices');
export const syncSubscription = () => api.post('/api/subscription/sync');

// Stripe Connect (Payment Setup for receiving payments)
export const getConnectStatus = () => api.get('/api/connect/status');
export const createConnectAccount = (country = 'IE') => 
  api.post('/api/connect/create', { country });
export const getConnectOnboardingLink = (baseUrl, country = 'IE') => 
  api.post('/api/connect/onboarding-link', { base_url: baseUrl, country });
export const getConnectDashboardLink = () => 
  api.post('/api/connect/dashboard-link');
export const disconnectStripeConnect = () => 
  api.post('/api/connect/disconnect');
export const getConnectBalance = () => api.get('/api/connect/balance');
export const getConnectPayouts = () => api.get('/api/connect/payouts');

// Bank Details (for invoice bank transfer option)
export const saveBankDetails = (data) => api.post('/api/settings/business', data);
export const getBankDetails = () => api.get('/api/settings/business');

// Expenses
export const getExpenses = () => api.get('/api/expenses');
export const createExpense = (data) => api.post('/api/expenses', data);
export const updateExpense = (id, data) => api.put(`/api/expenses/${id}`, data);
export const deleteExpense = (id) => api.delete(`/api/expenses/${id}`);

// Revenue Entries (Income Ledger)
export const getRevenueEntries = () => api.get('/api/revenue-entries');
export const createRevenueEntry = (data) => api.post('/api/revenue-entries', data);
export const updateRevenueEntry = (id, data) => api.put(`/api/revenue-entries/${id}`, data);
export const deleteRevenueEntry = (id) => api.delete(`/api/revenue-entries/${id}`);

// Quotes / Estimates
export const getQuotes = () => api.get('/api/quotes');
export const createQuote = (data) => api.post('/api/quotes', data);
export const updateQuote = (id, data) => api.put(`/api/quotes/${id}`, data);
export const deleteQuote = (id) => api.delete(`/api/quotes/${id}`);
export const convertQuoteToJob = (id, data) => api.post(`/api/quotes/${id}/convert`, data);
export const sendQuote = (id) => api.post(`/api/quotes/${id}/send`);

// Tax Settings
export const getTaxSettings = () => api.get('/api/settings/tax');
export const updateTaxSettings = (data) => api.post('/api/settings/tax', data);

// Reports
export const getPnlReport = (period = 'year') => api.get('/api/reports/pnl', { params: { period } });
export const getInvoiceAging = () => api.get('/api/finances/aging');

// Job Sub-Tasks
export const getJobTasks = (bookingId) => api.get(`/api/bookings/${bookingId}/tasks`);
export const createJobTask = (bookingId, data) => api.post(`/api/bookings/${bookingId}/tasks`, data);
export const updateJobTask = (bookingId, taskId, data) => api.put(`/api/bookings/${bookingId}/tasks/${taskId}`, data);
export const deleteJobTask = (bookingId, taskId) => api.delete(`/api/bookings/${bookingId}/tasks/${taskId}`);

// Purchase Orders
export const getPurchaseOrders = () => api.get('/api/purchase-orders');
export const createPurchaseOrder = (data) => api.post('/api/purchase-orders', data);
export const updatePurchaseOrder = (id, data) => api.put(`/api/purchase-orders/${id}`, data);
export const deletePurchaseOrder = (id) => api.delete(`/api/purchase-orders/${id}`);
export const generatePOFromJob = (bookingId) => api.post(`/api/purchase-orders/generate-from-job/${bookingId}`);

// Mileage Tracking
export const getMileageLogs = () => api.get('/api/mileage');
export const createMileageLog = (data) => api.post('/api/mileage', data);
export const updateMileageLog = (id, data) => api.put(`/api/mileage/${id}`, data);
export const deleteMileageLog = (id) => api.delete(`/api/mileage/${id}`);

// Credit Notes
export const getCreditNotes = () => api.get('/api/credit-notes');
export const createCreditNote = (data) => api.post('/api/credit-notes', data);
export const processStripeRefund = (creditNoteId) => api.post(`/api/credit-notes/${creditNoteId}/refund`);

// Customer Statements
export const getCustomerStatement = (clientId) => api.get(`/api/clients/${clientId}/statement`);

// Notifications
export const getNotifications = (since = null) => 
  api.get('/api/notifications', { params: since ? { since } : {} });

// Employee Portal
export const employeeLogin = (email, password) => api.post('/api/employee/auth/login', { email, password });
export const employeeLogout = () => api.post('/api/employee/auth/logout');
export const getEmployeeMe = () => api.get('/api/employee/auth/me');
export const employeeSetPassword = (token, password) => api.post('/api/employee/auth/set-password', { token, password });
export const ownerSetPassword = (token, password) => api.post('/api/owner/set-password', { token, password });
export const employeeForgotPassword = (email) => api.post('/api/employee/auth/forgot-password', { email });
export const employeeResetPassword = (token, newPassword) => api.post('/api/employee/auth/reset-password', { token, new_password: newPassword });
export const inviteEmployee = (employeeId) => api.post('/api/employee/invite', { employee_id: employeeId });
export const getEmployeeDashboard = () => api.get('/api/employee/dashboard');
export const updateEmployeeProfile = (data) => api.put('/api/employee/profile', data);
export const getEmployeeJobDetail = (id) => api.get(`/api/employee/jobs/${id}`);
export const employeeUploadJobPhoto = (jobId, imageData) => api.post(`/api/employee/jobs/${jobId}/photos`, { image: imageData });
export const employeeUploadJobMedia = (jobId, file) => {
  const formData = new FormData();
  formData.append('file', file);
  return api.post(`/api/employee/jobs/${jobId}/photos`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  });
};
export const employeeUpdateJobStatus = (jobId, data) => api.put(`/api/employee/jobs/${jobId}/status`, typeof data === 'string' ? { status: data } : data);
export const employeeBulkCompleteJobs = (filter) => api.post('/api/employee/jobs/bulk-complete', { filter });
export const employeeUpdateJobDetails = (jobId, data) => api.put(`/api/employee/jobs/${jobId}/details`, data);
export const getEmployeeJobNotes = (jobId) => api.get(`/api/employee/jobs/${jobId}/notes`);
export const addEmployeeJobNote = (jobId, note) => api.post(`/api/employee/jobs/${jobId}/notes`, { note });
export const getEmployeeTimeOff = () => api.get('/api/employee/time-off');
export const createTimeOffRequest = (data) => api.post('/api/employee/time-off', data);
export const deleteTimeOffRequest = (id) => api.delete(`/api/employee/time-off/${id}`);
export const employeeChangePassword = (currentPassword, newPassword) =>
  api.post('/api/employee/change-password', { current_password: currentPassword, new_password: newPassword });
export const getEmployeeHoursSummary = () => api.get('/api/employee/hours-summary');
export const getEmployeeCustomers = () => api.get('/api/employee/customers');

// Owner: Time-off management
export const getCompanyTimeOffRequests = (status = null) =>
  api.get('/api/time-off/requests', { params: status ? { status } : {} });
export const reviewTimeOffRequest = (id, status, note = '') =>
  api.put(`/api/time-off/requests/${id}`, { status, note });

// Employee Notifications
export const getEmployeeNotifications = () => api.get('/api/employee/notifications');
export const acceptEmergencyJob = (bookingId) => api.post(`/api/employee/emergency/${bookingId}/accept`);

// Owner-Employee Messaging
export const getConversations = () => api.get('/api/messages/conversations');
export const getMessages = (employeeId, beforeId = null) => 
  api.get(`/api/messages/${employeeId}`, { params: beforeId ? { before_id: beforeId } : {} });
export const sendMessageToEmployee = (employeeId, content) => 
  api.post(`/api/messages/${employeeId}`, { content });
export const getUnreadMessageCounts = () => api.get('/api/messages/unread-counts');

// Employee Messaging
export const getEmployeeMessages = (beforeId = null) => 
  api.get('/api/employee/messages', { params: beforeId ? { before_id: beforeId } : {} });
export const employeeSendMessage = (content) => 
  api.post('/api/employee/messages', { content });
export const getEmployeeUnreadMessageCount = () => api.get('/api/employee/messages/unread-count');

// Employee Job Creation
export const employeeGetServices = () => api.get('/api/employee/services');
export const employeeGetClients = () => api.get('/api/employee/clients');
export const employeeGetClient = (id) => api.get(`/api/employee/clients/${id}`);
export const employeeGetEmployees = () => api.get('/api/employee/employees');
export const employeeCheckAvailability = (date, serviceType, employeeId = null, anyEmployee = false, durationMinutes = null) => api.get('/api/employee/availability', { params: { date, service_type: serviceType, employee_id: employeeId, any_employee: anyEmployee || undefined, duration_minutes: durationMinutes || undefined } });
export const employeeCheckMonthlyAvailability = (year, month, serviceType, employeeId = null, anyEmployee = false, durationMinutes = null) => api.get('/api/employee/availability/month', { params: { year, month, service_type: serviceType, employee_id: employeeId, any_employee: anyEmployee || undefined, duration_minutes: durationMinutes || undefined } });
export const employeeCheckEmployeeAvailability = (id, appointmentTime, durationMinutes) =>
  api.get(`/api/employee/employees/${id}/availability`, { params: { appointment_time: appointmentTime, duration_minutes: durationMinutes } });
export const employeeCreateBooking = (data) => api.post('/api/employee/bookings', data);
export const employeeCreateClient = (data) => api.post('/api/employee/clients/create', data);

// Call Logs
export const getCallLogs = (params = {}) => api.get('/api/call-logs', { params });
export const getUnseenCallCount = (since) => api.get('/api/call-logs/unseen-count', { params: { since } });

// Outbound Calls
export const triggerLostJobCallback = (callLogId) => api.post(`/api/call-logs/${callLogId}/callback`);
export const getOutboundCallsEnabled = () => api.get('/api/outbound-calls/enabled');

// Reviews
export const getCompanyReviews = () => api.get('/api/reviews');
export const getBookingReview = (bookingId) => api.get(`/api/bookings/${bookingId}/review`);
export const getReviewByToken = (token) => api.get(`/api/review/${token}`);
export const submitReview = (token, data) => api.post(`/api/review/${token}`, data);

// Leads / CRM
export const getLeads = () => api.get('/api/leads');
export const createLead = (data) => api.post('/api/leads', data);
export const updateLead = (id, data) => api.put(`/api/leads/${id}`, data);
export const deleteLead = (id) => api.delete(`/api/leads/${id}`);
export const convertLead = (id) => api.post(`/api/leads/${id}/convert`);
export const getCrmStats = () => api.get('/api/crm/stats');
export const updateClientTags = (id, tags) => api.put(`/api/clients/${id}/tags`, { tags });
export const sendCrmEmail = (data) => api.post('/api/crm/send-email', data);
export const sendBulkCrmEmail = (data) => api.post('/api/crm/send-bulk-email', data);

// Quote Pipeline
export const getQuotePipeline = () => api.get('/api/quotes/pipeline');
export const updateQuotePipelineStage = (id, stage, lostReason) => api.put(`/api/quotes/${id}/pipeline-stage`, { stage, lost_reason: lostReason });
export const generateQuoteAcceptLink = (id) => api.post(`/api/quotes/${id}/accept-link`);
export const sendQuoteFollowUp = (id, message) => api.post(`/api/quotes/${id}/follow-up`, { message });
export const getQuoteByAcceptToken = (token) => api.get(`/api/quote/accept/${token}`);
export const acceptQuoteByToken = (token) => api.post(`/api/quote/accept/${token}`);

// Follow-up Sequences
export const getSequences = () => api.get('/api/sequences');
export const createSequence = (data) => api.post('/api/sequences', data);
export const updateSequence = (id, data) => api.put(`/api/sequences/${id}`, data);
export const deleteSequence = (id) => api.delete(`/api/sequences/${id}`);

// Workflow Automations
export const getAutomations = () => api.get('/api/automations');
export const createAutomation = (data) => api.post('/api/automations', data);
export const updateAutomation = (id, data) => api.put(`/api/automations/${id}`, data);
export const deleteAutomation = (id) => api.delete(`/api/automations/${id}`);

// Customer Portal
export const generatePortalLink = (clientId) => api.post(`/api/clients/${clientId}/portal-link`);
export const getPortalData = (token) => api.get(`/api/portal/${token}`);
export const portalRequestJob = (token, data) => api.post(`/api/portal/${token}/request-job`, data);
export const portalUploadJobPhoto = (token, jobId, imageData) => api.post(`/api/portal/${token}/jobs/${jobId}/photos`, { image: imageData });
export const portalUploadJobMedia = (token, jobId, file) => {
  const formData = new FormData();
  formData.append('file', file);
  return api.post(`/api/portal/${token}/jobs/${jobId}/photos`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  });
};

// Review Automation
export const getReviewAutomationSettings = () => api.get('/api/settings/review-automation');
export const updateReviewAutomationSettings = (data) => api.post('/api/settings/review-automation', data);

export default api;
