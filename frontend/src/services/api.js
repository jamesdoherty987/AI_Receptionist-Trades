import axios from 'axios';

// Use environment variable for API URL, fallback to relative path for local dev
const API_URL = import.meta.env.VITE_API_URL || '';

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
  const token = sessionStorage.getItem('authToken');
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
  (response) => response,
  (error) => {
    if (
      error.response?.status === 401 &&
      !error.config?.url?.includes('/api/auth/')
    ) {
      // Only wipe auth if we don't have a token — if we do, the token
      // itself is expired/invalid and we should force re-login.
      const hasToken = !!sessionStorage.getItem('authToken');
      if (hasToken) {
        sessionStorage.removeItem('authUser');
        sessionStorage.removeItem('authSubscription');
        sessionStorage.removeItem('authToken');
        if (window.location.pathname !== '/login' && 
            window.location.pathname !== '/signup' &&
            window.location.pathname !== '/' &&
            window.location.pathname !== '/forgot-password' &&
            window.location.pathname !== '/reset-password') {
          window.location.href = '/login';
        }
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
  api.post('/api/auth/delete-account', { confirmation });

// Bookings / Jobs
export const getBookings = () => api.get('/api/bookings');
export const getBooking = (id) => api.get(`/api/bookings/${id}`);
export const createBooking = (data) => api.post('/api/bookings', data);
export const updateBooking = (id, data) => api.put(`/api/bookings/${id}`, data);
export const deleteBooking = (id) => api.delete(`/api/bookings/${id}`);
export const checkAvailability = (date, serviceType, workerId = null, anyWorker = false) => api.get('/api/bookings/availability', { params: { date, service_type: serviceType, worker_id: workerId, any_worker: anyWorker || undefined } });
export const checkMonthlyAvailability = (year, month, serviceType, workerId = null, anyWorker = false) => api.get('/api/bookings/availability/month', { params: { year, month, service_type: serviceType, worker_id: workerId, any_worker: anyWorker || undefined } });

// Dashboard - Batch endpoint for better performance
export const getDashboardData = () => api.get('/api/dashboard');

// Clients
export const getClients = () => api.get('/api/clients');
export const getClient = (id) => api.get(`/api/clients/${id}`);
export const createClient = (data) => api.post('/api/clients', data);
export const updateClient = (id, data) => api.put(`/api/clients/${id}`, data);
export const deleteClient = (id) => api.delete(`/api/clients/${id}`);
export const addClientNote = (id, note) => api.post(`/api/clients/${id}/notes`, { note });

// Settings
export const getBusinessSettings = () => api.get('/api/settings/business');
export const updateBusinessSettings = (data) => api.post('/api/settings/business', data);

export const getDeveloperSettings = () => api.get('/api/settings/developer');
export const updateDeveloperSettings = (data) => api.post('/api/settings/developer', data);

export const getAIReceptionistStatus = () => api.get('/api/ai-receptionist/toggle');
export const toggleAIReceptionist = (enabled) => api.post('/api/ai-receptionist/toggle', { enabled });

export const getSettingsHistory = () => api.get('/api/settings/history');

// Services Menu
export const getServicesMenu = () => api.get('/api/services/menu');
export const updateServicesMenu = (data) => api.post('/api/services/menu', data);
export const createService = (data) => api.post('/api/services/menu/service', data);
export const updateService = (id, data) => api.put(`/api/services/menu/service/${id}`, data);
export const deleteService = (id) => api.delete(`/api/services/menu/service/${id}`);

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
export const syncGoogleCalendar = () => api.post('/api/google-calendar/sync');

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

// Notifications
export const getNotifications = (since = null) => 
  api.get('/api/notifications', { params: since ? { since } : {} });

export default api;
