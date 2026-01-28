import axios from 'axios';

const api = axios.create({
  baseURL: '',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Bookings / Jobs
export const getBookings = () => api.get('/api/bookings');
export const getBooking = (id) => api.get(`/api/bookings/${id}`);
export const createBooking = (data) => api.post('/api/bookings', data);
export const updateBooking = (id, data) => api.put(`/api/bookings/${id}`, data);
export const deleteBooking = (id) => api.delete(`/api/bookings/${id}`);

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

// Job-Worker Assignment
export const assignWorkerToJob = (jobId, data) => api.post(`/api/bookings/${jobId}/assign-worker`, data);
export const removeWorkerFromJob = (jobId, data) => api.post(`/api/bookings/${jobId}/remove-worker`, data);
export const getJobWorkers = (jobId) => api.get(`/api/bookings/${jobId}/workers`);

// Finances
export const getFinances = () => api.get('/api/finances');
export const getFinanceStats = () => api.get('/api/finances/stats');

// Calendar
export const getCalendarEvents = (params) => api.get('/api/calendar/events', { params });

// AI Chat
export const sendChatMessage = (message, conversation) => 
  api.post('/api/chat', { message, conversation });

export default api;
