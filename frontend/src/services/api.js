import axios from 'axios';

// Use environment variable for API URL, fallback to relative path for local dev
const API_URL = import.meta.env.VITE_API_URL || '';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // Important for session cookies
});

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

// Bookings / Jobs
export const getBookings = () => api.get('/api/bookings');
export const getBooking = (id) => api.get(`/api/bookings/${id}`);
export const createBooking = (data) => api.post('/api/bookings', data);
export const updateBooking = (id, data) => api.put(`/api/bookings/${id}`, data);
export const deleteBooking = (id) => api.delete(`/api/bookings/${id}`);

// Dashboard - Batch endpoint for better performance
export const getDashboardData = () => api.get('/api/dashboard');

// Clients
export const getClients = () => api.get('/api/clients');
export const getClient = (id) => api.get(`/api/clients/${id}`);
export const createClient = (data) => api.post('/api/clients', data);
export const updateClient = (id, data) => api.put(`/api/clients/${id}`, data);
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

// Job-Worker Assignment
export const assignWorkerToJob = (jobId, data) => api.post(`/api/bookings/${jobId}/assign-worker`, data);
export const removeWorkerFromJob = (jobId, data) => api.post(`/api/bookings/${jobId}/remove-worker`, data);
export const getJobWorkers = (jobId) => api.get(`/api/bookings/${jobId}/workers`);

// Finances
export const getFinances = () => api.get('/api/finances');
export const getFinanceStats = () => api.get('/api/finances/stats');

// Invoices
export const sendInvoice = (bookingId) => api.post(`/api/bookings/${bookingId}/send-invoice`);

// Calendar
export const getCalendarEvents = (params) => api.get('/api/calendar/events', { params });

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
export const getInvoices = () => api.get('/api/subscription/invoices');

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

export default api;
