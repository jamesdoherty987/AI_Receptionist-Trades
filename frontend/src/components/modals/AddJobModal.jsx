import { useState, useMemo, useRef, useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createBooking, getClients, getClient, checkAvailability, checkMonthlyAvailability, getServicesMenu, getWorkers, checkWorkerAvailability,
  workerCreateBooking, workerGetClients, workerGetClient, workerCheckAvailability, workerCheckMonthlyAvailability, workerGetServices, workerGetWorkers, workerCheckWorkerAvailability
} from '../../services/api';
import Modal from './Modal';
import { useToast } from '../Toast';
import AddClientModal from './AddClientModal';
import HelpTooltip from '../HelpTooltip';
import { DURATION_OPTIONS_GROUPED, formatDuration } from '../../utils/durationOptions';
import './AddJobModal.css';

function MiniCalendar({ selectedDate, onSelectDate, monthData, isLoading, calMonth, calYear, onMonthChange }) {
  const daysInMonth = new Date(calYear, calMonth + 1, 0).getDate();
  const firstDayOfWeek = new Date(calYear, calMonth, 1).getDay();
  // Shift so Monday=0
  const startOffset = (firstDayOfWeek + 6) % 7;
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const monthNames = ['January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'];

  const prevMonth = () => {
    if (calMonth === 0) onMonthChange(11, calYear - 1);
    else onMonthChange(calMonth - 1, calYear);
  };
  const nextMonth = () => {
    if (calMonth === 11) onMonthChange(0, calYear + 1);
    else onMonthChange(calMonth + 1, calYear);
  };

  const cells = [];
  for (let i = 0; i < startOffset; i++) cells.push(<div key={`e-${i}`} className="mc-cell mc-empty" />);

  for (let d = 1; d <= daysInMonth; d++) {
    const dateObj = new Date(calYear, calMonth, d);
    const iso = `${calYear}-${String(calMonth + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
    const isPast = dateObj < today;
    const isSelected = selectedDate === iso;
    const dayInfo = monthData?.[iso];
    let statusClass = '';
    if (isPast) statusClass = 'mc-past';
    else if (dayInfo?.status === 'closed') statusClass = 'mc-closed';
    else if (dayInfo?.status === 'leave') statusClass = 'mc-leave';
    else if (dayInfo?.status === 'full') statusClass = 'mc-full';
    else if (dayInfo?.status === 'partial') statusClass = 'mc-partial';
    else if (dayInfo?.status === 'free') statusClass = 'mc-free';

    const isDisabled = isPast || dayInfo?.status === 'closed' || dayInfo?.status === 'leave';

    cells.push(
      <button
        key={d}
        type="button"
        className={`mc-cell mc-day ${statusClass} ${isSelected ? 'mc-selected' : ''}`}
        disabled={isDisabled}
        onClick={() => !isDisabled && onSelectDate(iso)}
        title={isPast ? 'Past date' : dayInfo?.status === 'closed' ? 'Closed' : dayInfo?.status === 'leave' ? 'Worker on leave' : dayInfo?.status === 'full' ? 'Fully booked' : dayInfo?.status === 'partial' ? `${dayInfo.free} slot${dayInfo.free !== 1 ? 's' : ''} free` : 'Available'}
      >
        {d}
      </button>
    );
  }

  return (
    <div className="mini-calendar">
      <div className="mc-header">
        <button type="button" className="mc-nav" onClick={prevMonth}><i className="fas fa-chevron-left"></i></button>
        <span className="mc-title">{monthNames[calMonth]} {calYear}</span>
        <button type="button" className="mc-nav" onClick={nextMonth}><i className="fas fa-chevron-right"></i></button>
      </div>
      <div className="mc-weekdays">
        {['Mo','Tu','We','Th','Fr','Sa','Su'].map(d => <div key={d} className="mc-weekday">{d}</div>)}
      </div>
      <div className="mc-grid">
        {isLoading ? (
          <div className="mc-loading"><i className="fas fa-spinner fa-spin"></i></div>
        ) : cells}
      </div>
      <div className="mc-legend">
        <span className="mc-legend-item"><span className="mc-dot mc-dot-free"></span>Available</span>
        <span className="mc-legend-item"><span className="mc-dot mc-dot-partial"></span>Partial</span>
        <span className="mc-legend-item"><span className="mc-dot mc-dot-full"></span>Full</span>
        <span className="mc-legend-item"><span className="mc-dot mc-dot-leave"></span>Leave</span>
        <span className="mc-legend-item"><span className="mc-dot mc-dot-closed"></span>Closed</span>
      </div>
    </div>
  );
}

function AddJobModal({ isOpen, onClose, workerMode = false, currentWorkerId = null }) {
  const queryClient = useQueryClient();
  const { addToast } = useToast();

  // Select API functions based on mode
  const apiFns = useMemo(() => workerMode ? {
    createBooking: workerCreateBooking, getClients: workerGetClients, getClient: workerGetClient,
    checkAvailability: workerCheckAvailability, checkMonthlyAvailability: workerCheckMonthlyAvailability,
    getServicesMenu: workerGetServices, getWorkers: workerGetWorkers, checkWorkerAvailability: workerCheckWorkerAvailability,
  } : {
    createBooking, getClients, getClient, checkAvailability, checkMonthlyAvailability,
    getServicesMenu, getWorkers, checkWorkerAvailability,
  }, [workerMode]);
  
  const [formData, setFormData] = useState({
    client_id: '', appointment_time: '', service_type: '', job_address: '', eircode: '',
    property_type: '', estimated_charge: '', estimated_charge_max: '', duration_minutes: 1440, notes: '', worker_id: '', requires_callout: false, requires_quote: false, is_emergency: false, recurrence_pattern: '', recurrence_end_date: ''
  });
  
  const [selectedDate, setSelectedDate] = useState('');
  const [selectedService, setSelectedService] = useState(null);
  const [anyWorkerMode, setAnyWorkerMode] = useState(true);
  const [assignedWorkers, setAssignedWorkers] = useState([]); // [{id, name, trade_specialty, availability}]
  const assignedWorkersRef = useRef([]);
  const [customerPickerOpen, setCustomerPickerOpen] = useState(false);
  const [customerSearch, setCustomerSearch] = useState('');
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [isAddClientModalOpen, setIsAddClientModalOpen] = useState(false);
  const customerPickerRef = useRef(null);

  // Calendar month state
  const now = new Date();
  const [calMonth, setCalMonth] = useState(now.getMonth());
  const [calYear, setCalYear] = useState(now.getFullYear());

  useEffect(() => { if (!isOpen) resetForm(); }, [isOpen]);

  const { data: clients } = useQuery({ queryKey: ['clients', workerMode], queryFn: async () => (await apiFns.getClients()).data, enabled: isOpen });
  const { data: servicesMenu } = useQuery({ queryKey: ['services-menu', workerMode], queryFn: async () => (await apiFns.getServicesMenu()).data, enabled: isOpen });
  const { data: workers } = useQuery({ queryKey: ['workers', workerMode], queryFn: async () => (await apiFns.getWorkers()).data, enabled: isOpen });

  // Monthly availability (fires when service is selected)
  const durationMins = parseInt(formData.duration_minutes) || 60;
  // In worker mode, always include the creating worker in availability checks
  const effectiveWorkerList = useMemo(() => {
    if (workerMode && currentWorkerId && assignedWorkers.length > 0) {
      // Add current worker if not already in the list
      if (!assignedWorkers.some(w => w.id === currentWorkerId)) {
        return [{ id: currentWorkerId }, ...assignedWorkers];
      }
    }
    return assignedWorkers;
  }, [assignedWorkers, workerMode, currentWorkerId]);
  const assignedWorkerIds = effectiveWorkerList.map(w => w.id).sort().join(',');

  const { data: monthlyData, isLoading: isLoadingMonthly } = useQuery({
    queryKey: ['monthly-availability', calYear, calMonth + 1, formData.service_type, formData.worker_id, anyWorkerMode, durationMins, workerMode, assignedWorkerIds, currentWorkerId],
    queryFn: async () => {
      console.log('[MONTHLY_AVAIL] Fetching:', { calYear, calMonth: calMonth + 1, service: formData.service_type, duration: durationMins, anyWorker: anyWorkerMode, workers: assignedWorkerIds });
      // When workers are assigned, fetch each worker's availability and intersect
      if (effectiveWorkerList.length > 0) {
        const results = await Promise.all(
          effectiveWorkerList.map(w => apiFns.checkMonthlyAvailability(calYear, calMonth + 1, formData.service_type, w.id, false, durationMins).then(r => r.data))
        );
        if (!results.length || !results[0]) return results[0];
        const merged = { ...results[0], days: { ...results[0].days } };
        if (merged.days) {
          for (const dayKey of Object.keys(merged.days)) {
            const dayStatuses = results.map(r => r.days?.[dayKey]?.status || 'closed');
            // If business is closed for any worker's result, mark closed
            if (dayStatuses.some(s => s === 'closed')) {
              merged.days[dayKey] = { ...merged.days[dayKey], status: 'closed', free: 0 };
            } else if (dayStatuses.some(s => s === 'leave' || s === 'full')) {
              // If any worker is on leave or fully booked, no availability
              merged.days[dayKey] = { ...merged.days[dayKey], status: 'full', free: 0 };
            } else if (dayStatuses.some(s => s === 'partial')) {
              const minFree = Math.min(...results.map(r => r.days?.[dayKey]?.free ?? 0));
              merged.days[dayKey] = { ...merged.days[dayKey], status: minFree > 0 ? 'partial' : 'full', free: minFree };
            }
            // else all 'free' — keep as-is from results[0]
          }
        }
        return merged;
      }
      // In worker mode with no extra workers, show the creating worker's own availability
      const effectiveWorkerId = workerMode && currentWorkerId ? currentWorkerId : (anyWorkerMode ? null : (formData.worker_id || null));
      const effectiveAnyWorker = workerMode && currentWorkerId ? false : anyWorkerMode;
      const result = (await apiFns.checkMonthlyAvailability(calYear, calMonth + 1, formData.service_type, effectiveWorkerId, effectiveAnyWorker, durationMins)).data;
      console.log('[MONTHLY_AVAIL] Result:', { hasDays: !!result?.days, dayCount: result?.days ? Object.keys(result.days).length : 0, sampleDay: result?.days ? Object.values(result.days)[0] : null });
      return result;
    },
    enabled: !!formData.service_type && isOpen
  });

  // Daily slots (fires when date is selected)
  const { data: availability, isLoading: isLoadingAvailability } = useQuery({
    queryKey: ['availability', selectedDate, formData.service_type, formData.worker_id, anyWorkerMode, durationMins, workerMode, assignedWorkerIds, currentWorkerId],
    queryFn: async () => {
      // When workers are assigned, fetch each worker's slots and intersect
      if (effectiveWorkerList.length > 0) {
        const results = await Promise.all(
          effectiveWorkerList.map(w => apiFns.checkAvailability(selectedDate, formData.service_type, w.id, false, durationMins).then(r => r.data))
        );
        if (!results.length || !results[0]) return results[0];
        const merged = { ...results[0] };
        if (merged.slots) {
          // Build lookup maps by time for each worker's slots (safer than index matching)
          const slotMaps = results.map(r => {
            const map = {};
            (r.slots || []).forEach(s => { map[s.time] = s; });
            return map;
          });
          merged.slots = merged.slots.map(slot => {
            const allAvailable = slotMaps.every(m => m[slot.time]?.available);
            if (!allAvailable) {
              // Find the first conflicting worker's booking info
              const conflictMap = slotMaps.find(m => m[slot.time] && !m[slot.time].available);
              return { ...slot, available: false, booking: conflictMap?.[slot.time]?.booking || slot.booking };
            }
            return slot;
          });
        }
        return merged;
      }
      // In worker mode with no extra workers, show the creating worker's own availability
      const effectiveWorkerId = workerMode && currentWorkerId ? currentWorkerId : (anyWorkerMode ? null : (formData.worker_id || null));
      const effectiveAnyWorker = workerMode && currentWorkerId ? false : anyWorkerMode;
      return (await apiFns.checkAvailability(selectedDate, formData.service_type, effectiveWorkerId, effectiveAnyWorker, durationMins)).data;
    },
    enabled: !!selectedDate && !!formData.service_type && isOpen
  });

  const isFullDayJob = durationMins >= 1440;

  // Filter workers based on selected service's worker_restrictions
  const eligibleWorkers = useMemo(() => {
    if (!workers) return [];
    if (!selectedService?.worker_restrictions || selectedService.worker_restrictions.type === 'all') return workers;
    const { type, worker_ids } = selectedService.worker_restrictions;
    if (type === 'only') return workers.filter(w => worker_ids.includes(w.id));
    if (type === 'except') return workers.filter(w => !worker_ids.includes(w.id));
    return workers;
  }, [workers, selectedService]);

  const filteredCustomers = useMemo(() => {
    if (!clients) return [];
    if (!customerSearch.trim()) return clients;
    const term = customerSearch.toLowerCase();
    return clients.filter(c => c.name?.toLowerCase().includes(term) || c.phone?.includes(customerSearch) || c.email?.toLowerCase().includes(term));
  }, [clients, customerSearch]);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (customerPickerRef.current && !customerPickerRef.current.contains(e.target)) setCustomerPickerOpen(false);
    };
    if (customerPickerOpen) { document.addEventListener('mousedown', handleClickOutside); return () => document.removeEventListener('mousedown', handleClickOutside); }
  }, [customerPickerOpen]);

  const mutation = useMutation({
    mutationFn: apiFns.createBooking,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['bookings'] });
      queryClient.invalidateQueries({ queryKey: ['availability'] });
      queryClient.invalidateQueries({ queryKey: ['monthly-availability'] });
      queryClient.invalidateQueries({ queryKey: ['crm-stats'] });
      queryClient.invalidateQueries({ queryKey: ['finances'] });
      if (workerMode) {
        queryClient.invalidateQueries({ queryKey: ['worker-dashboard'] });
      }
      onClose();
      addToast('Job created successfully!', 'success');
    },
    onError: (error) => { addToast('Error creating job: ' + (error.response?.data?.error || error.message), 'error'); }
  });

  const resetForm = () => {
    setFormData({ client_id: '', appointment_time: '', service_type: '', job_address: '', eircode: '', property_type: '', estimated_charge: '', estimated_charge_max: '', duration_minutes: 1440, notes: '', worker_id: '', requires_callout: false, requires_quote: false, is_emergency: false, recurrence_pattern: '', recurrence_end_date: '' });
    setSelectedDate(''); setSelectedService(null); setAnyWorkerMode(true); setAssignedWorkers([]);
    setCustomerPickerOpen(false); setCustomerSearch(''); setSelectedCustomer(null);
    const n = new Date(); setCalMonth(n.getMonth()); setCalYear(n.getFullYear());
  };

  const handleSelectCustomer = async (customer) => {
    setSelectedCustomer(customer);
    setFormData(prev => ({ ...prev, client_id: customer.id }));
    setCustomerPickerOpen(false);
    setCustomerSearch('');
    // Fetch full client details to auto-fill address/eircode/property_type
    try {
      const res = await apiFns.getClient(customer.id);
      const c = res.data;
      setFormData(prev => ({
        ...prev,
        client_id: customer.id,
        job_address: c.address || prev.job_address || '',
        eircode: c.eircode || prev.eircode || '',
        property_type: c.property_type || prev.property_type || '',
      }));
    } catch (e) {
      // Non-critical — form still works without auto-fill
    }
  };
  const handleClearCustomer = () => {
    setSelectedCustomer(null);
    setFormData(prev => ({ ...prev, client_id: '', job_address: '', eircode: '', property_type: '' }));
  };

  const handleServiceSelect = (service) => {
    setSelectedService(service);
    const newDuration = service.duration_minutes || 60;
    // Round price to 2 decimal places to avoid floating point display issues (REAL column)
    const safePrice = service.price ? Math.round(parseFloat(service.price) * 100) / 100 : '';
    const safePriceMax = service.price_max ? Math.round(parseFloat(service.price_max) * 100) / 100 : '';
    // For price ranges, pre-fill estimated charge with min price — user can adjust
    setFormData(prev => ({
      ...prev,
      service_type: service.name,
      estimated_charge: safePrice,
      estimated_charge_max: safePriceMax && safePriceMax > safePrice ? safePriceMax : '',
      duration_minutes: newDuration,
      requires_callout: typeof service.requires_callout === 'boolean' ? service.requires_callout : prev.requires_callout,
      requires_quote: typeof service.requires_quote === 'boolean' ? service.requires_quote : prev.requires_quote,
      appointment_time: '',
    }));
    // Reset date selection when service changes (availability changes)
    setSelectedDate('');

    // Clear ineligible assigned workers when service changes
    if (service.worker_restrictions && service.worker_restrictions.type !== 'all') {
      const { type, worker_ids } = service.worker_restrictions;
      setAssignedWorkers(prev => prev.filter(w => {
        if (type === 'only') return worker_ids.includes(w.id);
        if (type === 'except') return !worker_ids.includes(w.id);
        return true;
      }));
    }
  };

  const handleWorkerSelect = async (workerId) => {
    if (workerId === 'any') {
      // "Any Worker" mode — combined availability across all workers
      setAnyWorkerMode(true);
      setSelectedDate('');
      setFormData(prev => ({ ...prev, worker_id: '', appointment_time: '' }));
      return;
    }
    // "" = no worker filter
    setAnyWorkerMode(false);
    setFormData(prev => ({ ...prev, worker_id: '' }));
  };

  const addWorkerToJob = async (workerId) => {
    if (!workerId) return;
    const id = parseInt(workerId);
    if (assignedWorkers.some(w => w.id === id)) { addToast('Worker already assigned', 'warning'); return; }
    const worker = workers?.find(w => w.id === id);
    if (!worker) return;
    // Clear any-worker mode when switching to multi-worker
    setAnyWorkerMode(false);
    setFormData(prev => ({ ...prev, worker_id: '' }));
    let avail = null;
    if (formData.appointment_time) {
      try {
        const res = await apiFns.checkWorkerAvailability(id, formData.appointment_time, formData.duration_minutes || 60);
        avail = res.data;
      } catch { /* ignore */ }
    }
    setAssignedWorkers(prev => [...prev, { id: worker.id, name: worker.name, trade_specialty: worker.trade_specialty, availability: avail }]);
  };

  const removeWorkerFromJob = (workerId) => {
    setAssignedWorkers(prev => {
      const updated = prev.filter(w => w.id !== workerId);
      // If all workers removed, go back to "Any available worker" mode
      if (updated.length === 0) setAnyWorkerMode(true);
      return updated;
    });
  };

  // Re-check availability for all assigned workers when date/time changes
  // Uses ref to avoid stale closure issues
  useEffect(() => { assignedWorkersRef.current = assignedWorkers; }, [assignedWorkers]);

  const recheckAssignedWorkers = async (appointmentTime, duration) => {
    const current = assignedWorkersRef.current;
    if (!appointmentTime || current.length === 0) return;
    const updated = await Promise.all(current.map(async (w) => {
      try {
        const res = await apiFns.checkWorkerAvailability(w.id, appointmentTime, duration || 60);
        return { ...w, availability: res.data };
      } catch { return { ...w, availability: null }; }
    }));
    setAssignedWorkers(updated);
  };

  const handleDateSelect = (iso) => {
    setSelectedDate(iso);
    if (isFullDayJob) {
      const dateTime = `${iso}T${String(monthlyData?.business_hours?.start || 9).padStart(2, '0')}:00`;
      setFormData(prev => ({ ...prev, appointment_time: dateTime }));
      recheckAssignedWorkers(dateTime, formData.duration_minutes || 60);
    } else {
      setFormData(prev => ({ ...prev, appointment_time: '' }));
    }
  };

  const handleTimeSlotClick = (slot) => {
    if (!slot.available) { addToast(`Slot booked${slot.booking?.client_name ? ` for ${slot.booking.client_name}` : ''}`, 'warning'); return; }
    const dateTime = `${selectedDate}T${slot.time}`;
    setFormData(prev => ({ ...prev, appointment_time: dateTime }));
    recheckAssignedWorkers(dateTime, formData.duration_minutes || 60);
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    if (name === 'duration_minutes') {
      // If duration changes, reset date/time since availability changes
      setSelectedDate('');
      setFormData(prev => ({ ...prev, [name]: value, appointment_time: '' }));
    } else {
      setFormData(prev => ({ ...prev, [name]: value }));
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!formData.client_id || !formData.appointment_time || !formData.service_type) { addToast('Please fill in all required fields', 'warning'); return; }
    // Check multi-worker availability
    const unavailableWorker = assignedWorkers.find(w => w.availability && !w.availability.available);
    if (unavailableWorker) { addToast(`${unavailableWorker.name} is not available at this time`, 'error'); return; }
    // Build worker_ids from the multi-worker list
    const allWorkerIds = assignedWorkers.map(w => w.id);
    // Strip worker_id from payload — we use worker_ids exclusively now
    const { worker_id: _unused, ...cleanFormData } = formData;
    // If "Any available worker" mode and no workers manually assigned, ask backend to auto-assign
    const autoAssign = anyWorkerMode && allWorkerIds.length === 0;
    mutation.mutate({ ...cleanFormData, worker_ids: allWorkerIds, auto_assign_worker: autoAssign });
  };

  const handleOpenAddClient = () => { setCustomerPickerOpen(false); setIsAddClientModalOpen(true); };
  const handleCloseAddClient = () => { setIsAddClientModalOpen(false); queryClient.invalidateQueries({ queryKey: ['clients'] }); };

  const handleMonthChange = (m, y) => { setCalMonth(m); setCalYear(y); };

  return (
    <>
      <Modal isOpen={isOpen} onClose={onClose} title={workerMode ? "Create Job" : "Add New Job"} size="large">
        <form onSubmit={handleSubmit} className="form add-job-form">
          
          {/* Worker mode banner */}
          {workerMode && (
            <div className="worker-job-banner">
              <i className="fas fa-hard-hat"></i>
              <span>You'll be automatically assigned to this job. You can also add other workers below.</span>
            </div>
          )}

          {/* Customer Selection */}
          <div className="form-group">
            <label className="form-label">Customer <span className="required">*</span></label>
            <div className="customer-picker" ref={customerPickerRef}>
              {selectedCustomer ? (
                <div className="customer-selected">
                  <div className="customer-selected-info">
                    <div className="customer-selected-avatar">{selectedCustomer.name?.charAt(0).toUpperCase() || '?'}</div>
                    <div className="customer-selected-details">
                      <span className="customer-selected-name">{selectedCustomer.name}</span>
                      <span className="customer-selected-meta">{selectedCustomer.phone || selectedCustomer.email || 'No contact'}</span>
                    </div>
                  </div>
                  <button type="button" className="customer-clear-btn" onClick={handleClearCustomer}><i className="fas fa-times"></i></button>
                </div>
              ) : (
                <button type="button" className="customer-picker-trigger" onClick={() => setCustomerPickerOpen(!customerPickerOpen)}>
                  <i className="fas fa-user"></i><span>Select a customer...</span><i className={`fas fa-chevron-${customerPickerOpen ? 'up' : 'down'}`}></i>
                </button>
              )}
              {customerPickerOpen && (
                <div className="customer-picker-dropdown">
                  <div className="customer-picker-search">
                    <i className="fas fa-search"></i>
                    <input type="text" placeholder="Search customers..." value={customerSearch} onChange={(e) => setCustomerSearch(e.target.value)} autoFocus />
                  </div>
                  <div className="customer-picker-list">
                    {filteredCustomers.length === 0 ? (
                      <div className="customer-picker-empty"><p>No customers found</p></div>
                    ) : filteredCustomers.slice(0, 10).map(customer => (
                      <div key={customer.id} className="customer-picker-item" onClick={() => handleSelectCustomer(customer)}>
                        <div className="customer-picker-avatar">{customer.name?.charAt(0).toUpperCase() || '?'}</div>
                        <div className="customer-picker-info">
                          <span className="customer-picker-name">{customer.name}</span>
                          <span className="customer-picker-contact">{customer.phone || customer.email || 'No contact'}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="customer-picker-footer">
                    <button type="button" className="customer-add-btn" onClick={handleOpenAddClient}><i className="fas fa-plus"></i> Add New Customer</button>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Service Type */}
          <div className="form-group">
            <label className="form-label">Service Type <span className="required">*</span></label>
            {servicesMenu?.services?.length > 0 ? (
              <>
                <select name="service_type" className="form-input" value={formData.service_type}
                  onChange={(e) => { const s = servicesMenu.services.find(x => x.name === e.target.value); if (s) handleServiceSelect(s); else { setFormData(prev => ({ ...prev, service_type: e.target.value })); setSelectedService(null); } }}
                  required>
                  <option value="">Select a service...</option>
                  {servicesMenu.services.map(s => (
                    <option key={s.id} value={s.name}>{s.name} {s.duration_minutes ? `(${formatDuration(s.duration_minutes)})` : ''} {s.price ? (s.price_max && parseFloat(s.price_max) > parseFloat(s.price) ? `- €${Math.round(parseFloat(s.price) * 100) / 100} – €${Math.round(parseFloat(s.price_max) * 100) / 100}` : `- €${Math.round(parseFloat(s.price) * 100) / 100}`) : ''}</option>
                  ))}
                </select>
                {selectedService && (
                  <div className="service-badge">
                    <span><i className="fas fa-clock"></i> {formatDuration(selectedService.duration_minutes || 60)}</span>
                    {selectedService.price && <span><i className="fas fa-euro-sign"></i> {selectedService.price_max && parseFloat(selectedService.price_max) > parseFloat(selectedService.price) ? `€${Math.round(parseFloat(selectedService.price) * 100) / 100} – €${Math.round(parseFloat(selectedService.price_max) * 100) / 100}` : `€${Math.round(parseFloat(selectedService.price) * 100) / 100}`}</span>}
                  </div>
                )}
              </>
            ) : (
              <input type="text" name="service_type" className="form-input" value={formData.service_type} onChange={handleChange} placeholder="e.g., Plumbing repair" required />
            )}
          </div>

          {/* Worker Assignment */}
          <div className="form-group">
            <label className="form-label">{workerMode ? 'Additional Workers' : 'Assign Workers'}</label>
            {/* Assigned workers list */}
            {assignedWorkers.length > 0 && (
              <div className="assigned-workers-list">
                {assignedWorkers.map(w => (
                  <div key={w.id} className={`assigned-worker-chip ${w.availability && !w.availability.available ? 'conflict' : ''}`}>
                    <i className="fas fa-hard-hat"></i>
                    <span className="assigned-worker-name">{w.name}</span>
                    {w.trade_specialty && <span className="assigned-worker-specialty">({w.trade_specialty})</span>}
                    {w.availability && !w.availability.available && (
                      <span className="assigned-worker-conflict" title={w.availability.message}><i className="fas fa-exclamation-triangle"></i></span>
                    )}
                    {w.availability && w.availability.available && (
                      <span className="assigned-worker-ok"><i className="fas fa-check-circle"></i></span>
                    )}
                    <button type="button" className="assigned-worker-remove" onClick={() => removeWorkerFromJob(w.id)} title="Remove worker"><i className="fas fa-times"></i></button>
                  </div>
                ))}
              </div>
            )}
            {/* When workers are assigned: show "add another" dropdown only */}
            {assignedWorkers.length > 0 && (
              <div className="add-worker-row">
                <select className="form-input add-worker-select" value="" onChange={(e) => { if (e.target.value) addWorkerToJob(e.target.value); }}>
                  <option value="">+ Add another worker...</option>
                  {eligibleWorkers.filter(w => !assignedWorkers.some(aw => aw.id === w.id)).map(w => (
                    <option key={w.id} value={w.id}>{w.name} {w.trade_specialty && `(${w.trade_specialty})`}</option>
                  ))}
                </select>
              </div>
            )}
            {/* When no workers assigned: show combined dropdown with availability modes + worker list */}
            {assignedWorkers.length === 0 && (
              <div className="add-worker-row">
                <select className="form-input" value={anyWorkerMode ? 'any' : ''} onChange={(e) => {
                  const val = e.target.value;
                  if (val === 'any') {
                    handleWorkerSelect(val);
                  } else if (val) {
                    // Add to multi-worker list instead of single-select
                    addWorkerToJob(val);
                  }
                }}>
                  <option value="any">Any available worker</option>
                  {eligibleWorkers.map(w => (
                    <option key={w.id} value={w.id}>{w.name} {w.trade_specialty && `(${w.trade_specialty})`}</option>
                  ))}
                </select>
              </div>
            )}
            {anyWorkerMode && assignedWorkers.length === 0 && (
              workerMode 
                ? <div className="worker-selected-info any-worker-info"><i className="fas fa-user-check"></i> You're assigned to this job. Select additional workers if needed.</div>
                : <div className="worker-selected-info any-worker-info"><i className="fas fa-users"></i> Showing combined availability — slot is open if <strong>any</strong> worker is free</div>
            )}
            {assignedWorkers.length > 0 && <div className="worker-selected-info"><i className="fas fa-users"></i> <strong>{assignedWorkers.length}</strong> worker{assignedWorkers.length !== 1 ? 's' : ''} assigned</div>}
            {selectedService?.worker_restrictions?.type === 'only' && (
              <div className="worker-restriction-hint"><i className="fas fa-info-circle"></i> Only workers qualified for "{selectedService.name}" are shown</div>
            )}
            {selectedService?.worker_restrictions?.type === 'except' && (
              <div className="worker-restriction-hint"><i className="fas fa-info-circle"></i> Some workers are excluded from "{selectedService.name}"</div>
            )}
          </div>

          {/* Date & Time — with mini calendar */}
          <div className="form-group">
            <label className="form-label">Date & Time <span className="required">*</span></label>

            {!formData.service_type ? (
              <div className="time-slots-prompt">
                <i className="fas fa-info-circle"></i> Select a service above to see availability
              </div>
            ) : (
              <>
                <MiniCalendar
                  selectedDate={selectedDate}
                  onSelectDate={handleDateSelect}
                  monthData={monthlyData?.days}
                  isLoading={isLoadingMonthly}
                  calMonth={calMonth}
                  calYear={calYear}
                  onMonthChange={handleMonthChange}
                />

                {/* For full-day jobs: just show day status */}
                {selectedDate && isFullDayJob && (
                  <div className="fullday-status">
                    {monthlyData?.days?.[selectedDate]?.status === 'full' ? (
                      <div className="fullday-booked"><i className="fas fa-times-circle"></i> This day is fully booked</div>
                    ) : (
                      <div className="fullday-available"><i className="fas fa-check-circle"></i> Day selected: {new Date(selectedDate + 'T00:00').toLocaleDateString('en-IE', { weekday: 'long', day: 'numeric', month: 'long' })}</div>
                    )}
                  </div>
                )}

                {/* For hourly jobs: show time slots */}
                {selectedDate && !isFullDayJob && (
                  <div className="time-slots-container">
                    <div className="time-slots-header">
                      <h4>
                        <i className="fas fa-clock"></i>{' '}
                        {new Date(selectedDate + 'T00:00').toLocaleDateString('en-IE', { weekday: 'short', day: 'numeric', month: 'short' })}
                        {assignedWorkers.length > 0 ? ` — ${assignedWorkers.length} worker${assignedWorkers.length !== 1 ? 's' : ''}` : anyWorkerMode ? ' — Any Worker' : ''}
                      </h4>
                    </div>
                    {isLoadingAvailability ? (
                      <div className="time-slots-loading"><i className="fas fa-spinner fa-spin"></i> Loading slots...</div>
                    ) : availability?.slots?.length > 0 ? (
                      <div className="time-slots-grid">
                        {availability.slots.map(slot => (
                          <button key={slot.time} type="button"
                            className={`time-slot ${slot.available ? 'available' : slot.booking?.past ? 'past' : 'booked'} ${formData.appointment_time === `${selectedDate}T${slot.time}` ? 'selected' : ''}`}
                            onClick={() => handleTimeSlotClick(slot)}
                            disabled={!slot.available}
                            title={slot.available ? 'Available' : slot.booking?.past ? 'Time has passed' : `Booked: ${slot.booking?.client_name || ''} — ${slot.booking?.service_type || ''}`}
                          >
                            <span className="slot-time">{slot.time}</span>
                            {!slot.available && slot.booking && !slot.booking.past && <span className="slot-info">{slot.booking.client_name}</span>}
                          </button>
                        ))}
                      </div>
                    ) : (
                      <div className="time-slots-empty">No slots available for this day</div>
                    )}
                  </div>
                )}

                {/* Selected time confirmation */}
                {formData.appointment_time && (
                  <div className="selected-time-badge">
                    <i className="fas fa-calendar-check"></i>
                    {new Date(formData.appointment_time).toLocaleString('en-IE', { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}
                  </div>
                )}
              </>
            )}

          </div>

          {/* Additional Fields */}
          <div className="form-grid">
            <div className="form-group">
              <label className="form-label">Duration</label>
              <select name="duration_minutes" className="form-input" value={formData.duration_minutes || 60} onChange={handleChange}>
                {Object.entries(DURATION_OPTIONS_GROUPED).map(([group, options]) => (
                  <optgroup key={group} label={group}>
                    {options.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                  </optgroup>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Property Type <HelpTooltip text="The type of property for this job — e.g. house, apartment, office. Helps workers prepare." /></label>
              <input type="text" name="property_type" className="form-input" value={formData.property_type} onChange={handleChange} placeholder="e.g., House" />
            </div>
            <div className="form-group">
              <label className="form-label">Eircode <HelpTooltip text="Irish postal code for the job location. Helps with routing and navigation." /></label>
              <input type="text" name="eircode" className="form-input" value={formData.eircode} onChange={handleChange} />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Job Address</label>
            <textarea name="job_address" className="form-textarea" value={formData.job_address} onChange={handleChange} rows="2" placeholder="If different from customer's address" />
          </div>
          
          <div className="form-group">
            <label className="form-label">Estimated Charge (€) <HelpTooltip text="The price you'll charge the customer. Pre-filled from the service — adjust if needed for this specific job." /></label>
            {formData.estimated_charge_max ? (
              <div className="price-range-display">
                <div className="price-range-inputs">
                  <input type="number" name="estimated_charge" className="form-input" value={formData.estimated_charge} onChange={handleChange} step="0.01" min="0" placeholder="Min" />
                  <span className="price-range-sep">to</span>
                  <input type="number" name="estimated_charge_max" className="form-input" value={formData.estimated_charge_max} onChange={handleChange} step="0.01" min="0" placeholder="Max" />
                </div>
                <span className="price-range-hint">Price range from service — adjust as needed</span>
              </div>
            ) : (
              <input type="number" name="estimated_charge" className="form-input" value={formData.estimated_charge} onChange={handleChange} step="0.01" min="0" placeholder="0.00" />
            )}
          </div>

          {/* Initial Callout Toggle */}
          <div className="form-group">
            <label className="form-label">Requires Initial Callout? <HelpTooltip text="Enable if a worker needs to visit the site first to assess the job. This books the callout service from your Services tab rather than the full job." /></label>
            <div className="callout-toggle-wrapper">
              <button type="button" className={`callout-toggle ${formData.requires_callout ? 'active' : ''}`}
                onClick={() => setFormData(prev => ({ ...prev, requires_callout: !prev.requires_callout, requires_quote: false }))}
                role="switch" aria-checked={formData.requires_callout}>
                <span className="callout-toggle-slider" />
              </button>
              <span className="callout-toggle-label">{formData.requires_callout ? 'Yes — callout visit needed before work begins' : 'No — go straight to the job'}</span>
            </div>
          </div>

          {/* Quote Visit Toggle */}
          {!formData.requires_callout && (
          <div className="form-group">
            <label className="form-label">Requires Quote Visit? <HelpTooltip text="Enable if a worker needs to visit the site first to give a free quote. This books the quote service from your Services tab rather than the full job." /></label>
            <div className="callout-toggle-wrapper">
              <button type="button" className={`callout-toggle ${formData.requires_quote ? 'active' : ''}`}
                onClick={() => setFormData(prev => ({ ...prev, requires_quote: !prev.requires_quote }))}
                role="switch" aria-checked={formData.requires_quote}>
                <span className="callout-toggle-slider" />
              </button>
              <span className="callout-toggle-label">{formData.requires_quote ? 'Yes — free quote visit needed before work begins' : 'No — go straight to the job'}</span>
            </div>
          </div>
          )}
          
          {/* Emergency Job Toggle */}
          <div className="form-group">
            <label className="form-label">Emergency Job? <HelpTooltip text="Mark as emergency to immediately notify all available workers via dashboard and email. A worker must accept the job to be dispatched." /></label>
            <div className="callout-toggle-wrapper">
              <button type="button" className={`callout-toggle emergency-toggle ${formData.is_emergency ? 'active' : ''}`}
                onClick={() => setFormData(prev => ({ ...prev, is_emergency: !prev.is_emergency }))}
                role="switch" aria-checked={formData.is_emergency}>
                <span className="callout-toggle-slider" />
              </button>
              <span className="callout-toggle-label">{formData.is_emergency ? 'Yes — notify workers immediately' : 'No — standard job'}</span>
            </div>
          </div>

          {/* Recurring Job Toggle */}
          <div className="form-group">
            <label className="form-label">Recurring Job? <HelpTooltip text="Set this job to repeat automatically. When completed, the next occurrence will be auto-created at the same time and day of week." /></label>
            <div className="callout-toggle-wrapper">
              <button type="button" className={`callout-toggle ${formData.recurrence_pattern ? 'active' : ''}`}
                onClick={() => setFormData(prev => ({ ...prev, recurrence_pattern: prev.recurrence_pattern ? '' : 'weekly' }))}
                role="switch" aria-checked={!!formData.recurrence_pattern}>
                <span className="callout-toggle-slider" />
              </button>
              <span className="callout-toggle-label">{formData.recurrence_pattern ? 'Yes — this job repeats' : 'No — one-time job'}</span>
            </div>
            {formData.recurrence_pattern && (
              <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.5rem', flexWrap: 'wrap' }}>
                <select name="recurrence_pattern" className="form-input" style={{ flex: '1', minWidth: '140px' }}
                  value={formData.recurrence_pattern} onChange={handleChange}>
                  <option value="weekly">Every Week</option>
                  <option value="biweekly">Every 2 Weeks</option>
                  <option value="monthly">Every Month</option>
                  <option value="quarterly">Every 3 Months</option>
                </select>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <label className="form-label" style={{ margin: 0, fontSize: '0.82rem' }}>Until</label>
                  <input type="date" name="recurrence_end_date" className="form-input" style={{ width: 'auto' }}
                    value={formData.recurrence_end_date || ''} onChange={handleChange}
                    min={new Date().toISOString().split('T')[0]} placeholder="No end date" />
                </div>
              </div>
            )}
          </div>

          <div className="form-group">
            <label className="form-label">Notes</label>
            <textarea name="notes" className="form-textarea" value={formData.notes} onChange={handleChange} rows="3" placeholder="Additional details" />
          </div>

          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={mutation.isPending}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={mutation.isPending}>{mutation.isPending ? 'Creating...' : workerMode ? 'Create & Assign to Me' : 'Create Job'}</button>
          </div>
        </form>
      </Modal>
      <AddClientModal isOpen={isAddClientModalOpen} onClose={handleCloseAddClient} workerMode={workerMode} />
    </>
  );
}

export default AddJobModal;
