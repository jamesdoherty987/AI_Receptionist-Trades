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
            !window.location.pathname.startsWith('/worker/')) {
          window.location.href = '/login';
        }
        if (window.location.pathname.startsWith('/worker/') &&
            window.location.pathname !== '/worker/login' &&
            window.location.pathname !== '/worker/set-password' &&
            window.location.pathname !== '/worker/forgot-password' &&
            window.location.pathname !== '/worker/reset-password') {
          window.location.href = '/worker/login';
        }
      }
    }

    // Handle 403 subscription required — update cached subscription state
    // so the UI can show the expired/inactive banner immediately
    if (
      error.response?.status === 403 &&
      error.response?.data?.subscription_status === 'inactive'
    ) {
      const subData = error.response.data.subscription;
      if (subData) {
        localStorage.setItem('authSubscription', JSON.stringify(subData));
      }
      // Redirect to settings subscription tab if not already there
      if (!window.location.pathname.startsWith('/settings')) {
        window.location.href = '/settings?tab=subscription';
      }
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

// Bookings / Jobs
export const getBookings = () => api.get('/api/bookings');
export const getBooking = (id) => api.get(`/api/bookings/${id}`);
export const createBooking = (data) => api.post('/api/bookings', data);
export const updateBooking = (id, data) => api.put(`/api/bookings/${id}`, data);
export const deleteBooking = (id) => api.delete(`/api/bookings/${id}`);
export const checkAvailability = (date, serviceType, workerId = null, anyWorker = false, durationMinutes = null) => api.get('/api/bookings/availability', { params: { date, service_type: serviceType, worker_id: workerId, any_worker: anyWorker || undefined, duration_minutes: durationMinutes || undefined } });
export const checkMonthlyAvailability = (year, month, serviceType, workerId = null, anyWorker = false, durationMinutes = null) => api.get('/api/bookings/availability/month', { params: { year, month, service_type: serviceType, worker_id: workerId, any_worker: anyWorker || undefined, duration_minutes: durationMinutes || undefined } });

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

// Job Materials
export const getJobMaterials = (bookingId) => api.get(`/api/bookings/${bookingId}/materials`);
export const addJobMaterial = (bookingId, data) => api.post(`/api/bookings/${bookingId}/materials`, data);
export const updateJobMaterial = (bookingId, itemId, data) => api.put(`/api/bookings/${bookingId}/materials/${itemId}`, data);
export const deleteJobMaterial = (bookingId, itemId) => api.delete(`/api/bookings/${bookingId}/materials/${itemId}`);

// Worker Job Materials
export const getWorkerJobMaterials = (jobId) => api.get(`/api/worker/jobs/${jobId}/materials`);
export const addWorkerJobMaterial = (jobId, data) => api.post(`/api/worker/jobs/${jobId}/materials`, data);
export const deleteWorkerJobMaterial = (jobId, itemId) => api.delete(`/api/worker/jobs/${jobId}/materials/${itemId}`);

export const getBusinessHours = () => api.get('/api/services/business-hours');
export const updateBusinessHours = (data) => api.post('/api/services/business-hours', data);

// Workers
export const getWorkers = () => api.get('/api/workers');
export const getWorker = (id) => api.get(`/api/workers/${id}`);
export const createWorker = (data) => api.post('/api/workers', data);
export const updateWorker = (id, data) => api.put(`/api/workers/${id}`, data);
export const deleteWorker = (id) => api.delete(`/api/workers/${id}`);
export const getWorkerJobs = (id) => api.get(`/api/workers/${id}/jobs`);
export const getWorkerSchedule = (id) => api.get(`/api/workers/${id}/schedule`);
export const getWorkerHoursThisWeek = (id) => api.get(`/api/workers/${id}/hours-this-week`);
export const checkWorkerAvailability = (id, appointmentTime, durationMinutes) => 
  api.get(`/api/workers/${id}/availability`, { params: { appointment_time: appointmentTime, duration_minutes: durationMinutes } });

// Job-Worker Assignment
export const assignWorkerToJob = (jobId, data) => api.post(`/api/bookings/${jobId}/assign-worker`, data);
export const removeWorkerFromJob = (jobId, data) => api.post(`/api/bookings/${jobId}/remove-worker`, data);
export const getJobWorkers = (jobId) => api.get(`/api/bookings/${jobId}/workers`);
export const getAvailableWorkersForJob = (jobId) => api.get(`/api/bookings/${jobId}/available-workers`);

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
export const createCheckoutSession = (baseUrl) => 
  api.post('/api/subscription/create-checkout', { base_url: baseUrl });
export const getBillingPortalUrl = (baseUrl) => 
  api.post('/api/subscription/billing-portal', { base_url: baseUrl });
export const cancelSubscription = () => api.post('/api/subscription/cancel');
export const reactivateSubscription = () => api.post('/api/subscription/reactivate');
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

// Worker Portal
export const workerLogin = (email, password) => api.post('/api/worker/auth/login', { email, password });
export const workerLogout = () => api.post('/api/worker/auth/logout');
export const getWorkerMe = () => api.get('/api/worker/auth/me');
export const workerSetPassword = (token, password) => api.post('/api/worker/auth/set-password', { token, password });
export const ownerSetPassword = (token, password) => api.post('/api/owner/set-password', { token, password });
export const workerForgotPassword = (email) => api.post('/api/worker/auth/forgot-password', { email });
export const workerResetPassword = (token, newPassword) => api.post('/api/worker/auth/reset-password', { token, new_password: newPassword });
export const inviteWorker = (workerId) => api.post('/api/worker/invite', { worker_id: workerId });
export const getWorkerDashboard = () => api.get('/api/worker/dashboard');
export const updateWorkerProfile = (data) => api.put('/api/worker/profile', data);
export const getWorkerJobDetail = (id) => api.get(`/api/worker/jobs/${id}`);
export const workerUploadJobPhoto = (jobId, imageData) => api.post(`/api/worker/jobs/${jobId}/photos`, { image: imageData });
export const workerUploadJobMedia = (jobId, file) => {
  const formData = new FormData();
  formData.append('file', file);
  return api.post(`/api/worker/jobs/${jobId}/photos`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  });
};
export const workerUpdateJobStatus = (jobId, data) => api.put(`/api/worker/jobs/${jobId}/status`, typeof data === 'string' ? { status: data } : data);
export const workerBulkCompleteJobs = (filter) => api.post('/api/worker/jobs/bulk-complete', { filter });
export const workerUpdateJobDetails = (jobId, data) => api.put(`/api/worker/jobs/${jobId}/details`, data);
export const getWorkerJobNotes = (jobId) => api.get(`/api/worker/jobs/${jobId}/notes`);
export const addWorkerJobNote = (jobId, note) => api.post(`/api/worker/jobs/${jobId}/notes`, { note });
export const getWorkerTimeOff = () => api.get('/api/worker/time-off');
export const createTimeOffRequest = (data) => api.post('/api/worker/time-off', data);
export const deleteTimeOffRequest = (id) => api.delete(`/api/worker/time-off/${id}`);
export const workerChangePassword = (currentPassword, newPassword) =>
  api.post('/api/worker/change-password', { current_password: currentPassword, new_password: newPassword });
export const getWorkerHoursSummary = () => api.get('/api/worker/hours-summary');
export const getWorkerCustomers = () => api.get('/api/worker/customers');

// Owner: Time-off management
export const getCompanyTimeOffRequests = (status = null) =>
  api.get('/api/time-off/requests', { params: status ? { status } : {} });
export const reviewTimeOffRequest = (id, status, note = '') =>
  api.put(`/api/time-off/requests/${id}`, { status, note });

// Worker Notifications
export const getWorkerNotifications = () => api.get('/api/worker/notifications');
export const acceptEmergencyJob = (bookingId) => api.post(`/api/worker/emergency/${bookingId}/accept`);

// Owner-Worker Messaging
export const getConversations = () => api.get('/api/messages/conversations');
export const getMessages = (workerId, beforeId = null) => 
  api.get(`/api/messages/${workerId}`, { params: beforeId ? { before_id: beforeId } : {} });
export const sendMessageToWorker = (workerId, content) => 
  api.post(`/api/messages/${workerId}`, { content });
export const getUnreadMessageCounts = () => api.get('/api/messages/unread-counts');

// Worker Messaging
export const getWorkerMessages = (beforeId = null) => 
  api.get('/api/worker/messages', { params: beforeId ? { before_id: beforeId } : {} });
export const workerSendMessage = (content) => 
  api.post('/api/worker/messages', { content });
export const getWorkerUnreadMessageCount = () => api.get('/api/worker/messages/unread-count');

// Worker Job Creation
export const workerGetServices = () => api.get('/api/worker/services');
export const workerGetClients = () => api.get('/api/worker/clients');
export const workerGetClient = (id) => api.get(`/api/worker/clients/${id}`);
export const workerGetWorkers = () => api.get('/api/worker/workers');
export const workerCheckAvailability = (date, serviceType, workerId = null, anyWorker = false, durationMinutes = null) => api.get('/api/worker/availability', { params: { date, service_type: serviceType, worker_id: workerId, any_worker: anyWorker || undefined, duration_minutes: durationMinutes || undefined } });
export const workerCheckMonthlyAvailability = (year, month, serviceType, workerId = null, anyWorker = false, durationMinutes = null) => api.get('/api/worker/availability/month', { params: { year, month, service_type: serviceType, worker_id: workerId, any_worker: anyWorker || undefined, duration_minutes: durationMinutes || undefined } });
export const workerCheckWorkerAvailability = (id, appointmentTime, durationMinutes) =>
  api.get(`/api/worker/workers/${id}/availability`, { params: { appointment_time: appointmentTime, duration_minutes: durationMinutes } });
export const workerCreateBooking = (data) => api.post('/api/worker/bookings', data);
export const workerCreateClient = (data) => api.post('/api/worker/clients/create', data);

// Call Logs
export const getCallLogs = (params = {}) => api.get('/api/call-logs', { params });
export const getUnseenCallCount = (since) => api.get('/api/call-logs/unseen-count', { params: { since } });

export default api;
