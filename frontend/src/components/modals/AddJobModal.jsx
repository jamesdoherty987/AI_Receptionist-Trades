import { useState, useMemo, useRef, useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createBooking, getClients, getClient, checkAvailability, checkMonthlyAvailability, getServicesMenu, getEmployees, checkEmployeeAvailability,
  employeeCreateBooking, employeeGetClients, employeeGetClient, employeeCheckAvailability, employeeCheckMonthlyAvailability, employeeGetServices, employeeGetEmployees, employeeCheckEmployeeAvailability
} from '../../services/api';
import Modal from './Modal';
import { useToast } from '../Toast';
import { useIndustry } from '../../context/IndustryContext';
import { invalidateRelated } from '../../utils/queryInvalidation';
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
        title={isPast ? 'Past date' : dayInfo?.status === 'closed' ? 'Closed' : dayInfo?.status === 'leave' ? 'Employee on leave' : dayInfo?.status === 'full' ? 'Fully booked' : dayInfo?.status === 'partial' ? `${dayInfo.free} slot${dayInfo.free !== 1 ? 's' : ''} free` : 'Available'}
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

function AddJobModal({ isOpen, onClose, employeeMode = false, currentEmployeeId = null }) {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const { terminology, features } = useIndustry();

  // Select API functions based on mode
  const apiFns = useMemo(() => employeeMode ? {
    createBooking: employeeCreateBooking, getClients: employeeGetClients, getClient: employeeGetClient,
    checkAvailability: employeeCheckAvailability, checkMonthlyAvailability: employeeCheckMonthlyAvailability,
    getServicesMenu: employeeGetServices, getEmployees: employeeGetEmployees, checkEmployeeAvailability: employeeCheckEmployeeAvailability,
  } : {
    createBooking, getClients, getClient, checkAvailability, checkMonthlyAvailability,
    getServicesMenu, getEmployees, checkEmployeeAvailability,
  }, [employeeMode]);
  
  const [formData, setFormData] = useState({
    client_id: '', appointment_time: '', service_type: '', job_address: '', eircode: '',
    property_type: '', estimated_charge: '', estimated_charge_max: '', duration_minutes: 1440, notes: '', employee_id: '', requires_callout: false, requires_quote: false, is_emergency: false, recurrence_pattern: '', recurrence_end_date: '',
    table_number: '', party_size: '', dining_area: '', special_requests: ''
  });
  
  const [selectedDate, setSelectedDate] = useState('');
  const [selectedService, setSelectedService] = useState(null);
  const [anyEmployeeMode, setAnyEmployeeMode] = useState(true);
  const [assignedEmployees, setAssignedEmployees] = useState([]); // [{id, name, trade_specialty, availability}]
  const assignedEmployeesRef = useRef([]);
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

  const { data: clients } = useQuery({ queryKey: ['clients', employeeMode], queryFn: async () => (await apiFns.getClients()).data, enabled: isOpen });
  const { data: servicesMenu } = useQuery({ queryKey: ['services-menu', employeeMode], queryFn: async () => (await apiFns.getServicesMenu()).data, enabled: isOpen });
  const { data: employees } = useQuery({ queryKey: ['employees', employeeMode], queryFn: async () => (await apiFns.getEmployees()).data, enabled: isOpen });

  // Monthly availability (fires when service is selected)
  const durationMins = parseInt(formData.duration_minutes) || 60;
  // In employee mode, always include the creating employee in availability checks
  const effectiveEmployeeList = useMemo(() => {
    if (employeeMode && currentEmployeeId && assignedEmployees.length > 0) {
      // Add current employee if not already in the list
      if (!assignedEmployees.some(w => w.id === currentEmployeeId)) {
        return [{ id: currentEmployeeId }, ...assignedEmployees];
      }
    }
    return assignedEmployees;
  }, [assignedEmployees, employeeMode, currentEmployeeId]);
  const assignedEmployeeIds = effectiveEmployeeList.map(w => w.id).sort().join(',');

  const { data: monthlyData, isLoading: isLoadingMonthly } = useQuery({
    queryKey: ['monthly-availability', calYear, calMonth + 1, formData.service_type, formData.employee_id, anyEmployeeMode, durationMins, employeeMode, assignedEmployeeIds, currentEmployeeId],
    queryFn: async () => {
      console.log('[MONTHLY_AVAIL] Fetching:', { calYear, calMonth: calMonth + 1, service: formData.service_type, duration: durationMins, anyEmployee: anyEmployeeMode, employees: assignedEmployeeIds });
      // When employees are assigned, fetch each employee's availability and intersect
      if (effectiveEmployeeList.length > 0) {
        const results = await Promise.all(
          effectiveEmployeeList.map(w => apiFns.checkMonthlyAvailability(calYear, calMonth + 1, formData.service_type, w.id, false, durationMins).then(r => r.data))
        );
        if (!results.length || !results[0]) return results[0];
        const merged = { ...results[0], days: { ...results[0].days } };
        if (merged.days) {
          for (const dayKey of Object.keys(merged.days)) {
            const dayStatuses = results.map(r => r.days?.[dayKey]?.status || 'closed');
            // If business is closed for any employee's result, mark closed
            if (dayStatuses.some(s => s === 'closed')) {
              merged.days[dayKey] = { ...merged.days[dayKey], status: 'closed', free: 0 };
            } else if (dayStatuses.some(s => s === 'leave' || s === 'full')) {
              // If any employee is on leave or fully booked, no availability
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
      // In employee mode with no extran employees, show the creating employee's own availability
      const effectiveEmployeeId = employeeMode && currentEmployeeId ? currentEmployeeId : (anyEmployeeMode ? null : (formData.employee_id || null));
      const effectiveAnyEmployee = employeeMode && currentEmployeeId ? false : anyEmployeeMode;
      const result = (await apiFns.checkMonthlyAvailability(calYear, calMonth + 1, formData.service_type, effectiveEmployeeId, effectiveAnyEmployee, durationMins)).data;
      console.log('[MONTHLY_AVAIL] Result:', { hasDays: !!result?.days, dayCount: result?.days ? Object.keys(result.days).length : 0, sampleDay: result?.days ? Object.values(result.days)[0] : null });
      return result;
    },
    enabled: !!formData.service_type && isOpen
  });

  // Daily slots (fires when date is selected)
  const { data: availability, isLoading: isLoadingAvailability } = useQuery({
    queryKey: ['availability', selectedDate, formData.service_type, formData.employee_id, anyEmployeeMode, durationMins, employeeMode, assignedEmployeeIds, currentEmployeeId],
    queryFn: async () => {
      // When employees are assigned, fetch each employee's slots and intersect
      if (effectiveEmployeeList.length > 0) {
        const results = await Promise.all(
          effectiveEmployeeList.map(w => apiFns.checkAvailability(selectedDate, formData.service_type, w.id, false, durationMins).then(r => r.data))
        );
        if (!results.length || !results[0]) return results[0];
        const merged = { ...results[0] };
        if (merged.slots) {
          // Build lookup maps by time for each employee's slots (safer than index matching)
          const slotMaps = results.map(r => {
            const map = {};
            (r.slots || []).forEach(s => { map[s.time] = s; });
            return map;
          });
          merged.slots = merged.slots.map(slot => {
            const allAvailable = slotMaps.every(m => m[slot.time]?.available);
            if (!allAvailable) {
              // Find the first conflicting employee's booking info
              const conflictMap = slotMaps.find(m => m[slot.time] && !m[slot.time].available);
              return { ...slot, available: false, booking: conflictMap?.[slot.time]?.booking || slot.booking };
            }
            return slot;
          });
        }
        return merged;
      }
      // In employee mode with no extran employees, show the creating employee's own availability
      const effectiveEmployeeId = employeeMode && currentEmployeeId ? currentEmployeeId : (anyEmployeeMode ? null : (formData.employee_id || null));
      const effectiveAnyEmployee = employeeMode && currentEmployeeId ? false : anyEmployeeMode;
      return (await apiFns.checkAvailability(selectedDate, formData.service_type, effectiveEmployeeId, effectiveAnyEmployee, durationMins)).data;
    },
    enabled: !!selectedDate && !!formData.service_type && isOpen
  });

  const isFullDayJob = durationMins >= 1440;

  // Filter employees based on selected service's employee_restrictions
  const eligibleEmployees = useMemo(() => {
    if (!employees) return [];
    if (!selectedService?.employee_restrictions || selectedService.employee_restrictions.type === 'all') return employees;
    const { type, employee_ids } = selectedService.employee_restrictions;
    if (type === 'only') return employees.filter(w => employee_ids.includes(w.id));
    if (type === 'except') return employees.filter(w => !employee_ids.includes(w.id));
    return employees;
  }, [employees, selectedService]);

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
      invalidateRelated(queryClient, 'jobs', 'calendar', 'finances', 'customers');
      if (employeeMode) {
        invalidateRelated(queryClient, 'employeeDashboard');
      }
      onClose();
      addToast(`${terminology.job} created successfully!`, 'success');
    },
    onError: (error) => { addToast(`Error creating ${terminology.job.toLowerCase()}: ` + (error.response?.data?.error || error.message), 'error'); }
  });

  const resetForm = () => {
    setFormData({ client_id: '', appointment_time: '', service_type: '', job_address: '', eircode: '', property_type: '', estimated_charge: '', estimated_charge_max: '', duration_minutes: 1440, notes: '', employee_id: '', requires_callout: false, requires_quote: false, is_emergency: false, recurrence_pattern: '', recurrence_end_date: '', table_number: '', party_size: '', dining_area: '', special_requests: '' });
    setSelectedDate(''); setSelectedService(null); setAnyEmployeeMode(true); setAssignedEmployees([]);
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

    // Clear ineligible assigned employees when service changes
    if (service.employee_restrictions && service.employee_restrictions.type !== 'all') {
      const { type, employee_ids } = service.employee_restrictions;
      setAssignedEmployees(prev => prev.filter(w => {
        if (type === 'only') return employee_ids.includes(w.id);
        if (type === 'except') return !employee_ids.includes(w.id);
        return true;
      }));
    }
  };

  const handleEmployeeSelect = async (employeeId) => {
    if (employeeId === 'any') {
      // "Any Employee" mode — combined availability across all employees
      setAnyEmployeeMode(true);
      setSelectedDate('');
      setFormData(prev => ({ ...prev, employee_id: '', appointment_time: '' }));
      return;
    }
    // "" = no employee filter
    setAnyEmployeeMode(false);
    setFormData(prev => ({ ...prev, employee_id: '' }));
  };

  const addEmployeeToJob = async (employeeId) => {
    if (!employeeId) return;
    const id = parseInt(employeeId);
    if (assignedEmployees.some(w => w.id === id)) { addToast('Employee already assigned', 'warning'); return; }
    const employee = employees?.find(w => w.id === id);
    if (!employee) return;
    // Clear any-employee mode when switching to multi-employee
    setAnyEmployeeMode(false);
    setFormData(prev => ({ ...prev, employee_id: '' }));
    let avail = null;
    if (formData.appointment_time) {
      try {
        const res = await apiFns.checkEmployeeAvailability(id, formData.appointment_time, formData.duration_minutes || 60);
        avail = res.data;
      } catch { /* ignore */ }
    }
    setAssignedEmployees(prev => [...prev, { id: employee.id, name: employee.name, trade_specialty: employee.trade_specialty, availability: avail }]);
  };

  const removeEmployeeFromJob = (employeeId) => {
    setAssignedEmployees(prev => {
      const updated = prev.filter(w => w.id !== employeeId);
      // If all employees removed, go back to "Any available employee" mode
      if (updated.length === 0) setAnyEmployeeMode(true);
      return updated;
    });
  };

  // Re-check availability for all assigned employees when date/time changes
  // Uses ref to avoid stale closure issues
  useEffect(() => { assignedEmployeesRef.current = assignedEmployees; }, [assignedEmployees]);

  const recheckAssignedEmployees = async (appointmentTime, duration) => {
    const current = assignedEmployeesRef.current;
    if (!appointmentTime || current.length === 0) return;
    const updated = await Promise.all(current.map(async (w) => {
      try {
        const res = await apiFns.checkEmployeeAvailability(w.id, appointmentTime, duration || 60);
        return { ...w, availability: res.data };
      } catch { return { ...w, availability: null }; }
    }));
    setAssignedEmployees(updated);
  };

  const handleDateSelect = (iso) => {
    setSelectedDate(iso);
    if (isFullDayJob) {
      const dateTime = `${iso}T${String(monthlyData?.business_hours?.start || 9).padStart(2, '0')}:00`;
      setFormData(prev => ({ ...prev, appointment_time: dateTime }));
      recheckAssignedEmployees(dateTime, formData.duration_minutes || 60);
    } else {
      setFormData(prev => ({ ...prev, appointment_time: '' }));
    }
  };

  const handleTimeSlotClick = (slot) => {
    if (!slot.available) { addToast(`Slot booked${slot.booking?.client_name ? ` for ${slot.booking.client_name}` : ''}`, 'warning'); return; }
    const dateTime = `${selectedDate}T${slot.time}`;
    setFormData(prev => ({ ...prev, appointment_time: dateTime }));
    recheckAssignedEmployees(dateTime, formData.duration_minutes || 60);
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
    // Check multi-employee availability
    const unavailableEmployee = assignedEmployees.find(w => w.availability && !w.availability.available);
    if (unavailableEmployee) { addToast(`${unavailableEmployee.name} is not available at this time`, 'error'); return; }
    // Build employee_ids from the multi-employee list
    const allEmployeeIds = assignedEmployees.map(w => w.id);
    // Strip employee_id from payload — we use employee_ids exclusively now
    const { employee_id: _unused, ...cleanFormData } = formData;
    // If "Any available employee" mode and no employees manually assigned, ask backend to auto-assign
    const autoAssign = anyEmployeeMode && allEmployeeIds.length === 0;
    mutation.mutate({ ...cleanFormData, employee_ids: allEmployeeIds, auto_assign_employee: autoAssign });
  };

  const handleOpenAddClient = () => { setCustomerPickerOpen(false); setIsAddClientModalOpen(true); };
  const handleCloseAddClient = () => { setIsAddClientModalOpen(false); queryClient.invalidateQueries({ queryKey: ['clients'] }); };

  const handleMonthChange = (m, y) => { setCalMonth(m); setCalYear(y); };

  return (
    <>
      <Modal isOpen={isOpen} onClose={onClose} title={employeeMode ? `Create ${terminology.job}` : `Add New ${terminology.job}`} size="large">
        <form onSubmit={handleSubmit} className="form add-job-form">
          
          {/* Employee mode banner */}
          {employeeMode && (
            <div className="employee-job-banner">
              <i className="fas fa-hard-hat"></i>
              <span>You'll be automatically assigned to this job. You can also add other employees below.</span>
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
                      <div className="customer-picker-empty"><p>No {(terminology.clients || 'customers').toLowerCase()} found</p></div>
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

          {/* Employee Assignment */}
          <div className="form-group">
            <label className="form-label">{employeeMode ? 'Additional Employees' : 'Assign Employees'}</label>
            {/* Assigned employees list */}
            {assignedEmployees.length > 0 && (
              <div className="assigned-employees-list">
                {assignedEmployees.map(w => (
                  <div key={w.id} className={`assigned-employee-chip ${w.availability && !w.availability.available ? 'conflict' : ''}`}>
                    <i className="fas fa-hard-hat"></i>
                    <span className="assigned-employee-name">{w.name}</span>
                    {w.trade_specialty && <span className="assigned-employee-specialty">({w.trade_specialty})</span>}
                    {w.availability && !w.availability.available && (
                      <span className="assigned-employee-conflict" title={w.availability.message}><i className="fas fa-exclamation-triangle"></i></span>
                    )}
                    {w.availability && w.availability.available && (
                      <span className="assigned-employee-ok"><i className="fas fa-check-circle"></i></span>
                    )}
                    <button type="button" className="assigned-employee-remove" onClick={() => removeEmployeeFromJob(w.id)} title="Remove employee"><i className="fas fa-times"></i></button>
                  </div>
                ))}
              </div>
            )}
            {/* When employees are assigned: show "add another" dropdown only */}
            {assignedEmployees.length > 0 && (
              <div className="add-employee-row">
                <select className="form-input add-employee-select" value="" onChange={(e) => { if (e.target.value) addEmployeeToJob(e.target.value); }}>
                  <option value="">+ Add another employee...</option>
                  {eligibleEmployees.filter(w => !assignedEmployees.some(aw => aw.id === w.id)).map(w => (
                    <option key={w.id} value={w.id}>{w.name} {w.trade_specialty && `(${w.trade_specialty})`}</option>
                  ))}
                </select>
              </div>
            )}
            {/* When no employees assigned: show combined dropdown with availability modes + employee list */}
            {assignedEmployees.length === 0 && (
              <div className="add-employee-row">
                <select className="form-input" value={anyEmployeeMode ? 'any' : ''} onChange={(e) => {
                  const val = e.target.value;
                  if (val === 'any') {
                    handleEmployeeSelect(val);
                  } else if (val) {
                    // Add to multi-employee list instead of single-select
                    addEmployeeToJob(val);
                  }
                }}>
                  <option value="any">Any available employee</option>
                  {eligibleEmployees.map(w => (
                    <option key={w.id} value={w.id}>{w.name} {w.trade_specialty && `(${w.trade_specialty})`}</option>
                  ))}
                </select>
              </div>
            )}
            {anyEmployeeMode && assignedEmployees.length === 0 && (
              employeeMode 
                ? <div className="employee-selected-info any-employee-info"><i className="fas fa-user-check"></i> You're assigned to this job. Select additional employees if needed.</div>
                : <div className="employee-selected-info any-employee-info"><i className="fas fa-users"></i> Showing combined availability — slot is open if <strong>any</strong> employee is free</div>
            )}
            {assignedEmployees.length > 0 && <div className="employee-selected-info"><i className="fas fa-users"></i> <strong>{assignedEmployees.length}</strong> employee{assignedEmployees.length !== 1 ? 's' : ''} assigned</div>}
            {selectedService?.employee_restrictions?.type === 'only' && (
              <div className="employee-restriction-hint"><i className="fas fa-info-circle"></i> Only employees qualified for "{selectedService.name}" are shown</div>
            )}
            {selectedService?.employee_restrictions?.type === 'except' && (
              <div className="employee-restriction-hint"><i className="fas fa-info-circle"></i> Some employees are excluded from "{selectedService.name}"</div>
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
                        {assignedEmployees.length > 0 ? ` — ${assignedEmployees.length} employee${assignedEmployees.length !== 1 ? 's' : ''}` : anyEmployeeMode ? ' — Any Employee' : ''}
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
            {features.propertyType && (
            <div className="form-group">
              <label className="form-label">Property Type <HelpTooltip text="The type of property for this job — e.g. house, apartment, office. Helps employees prepare." /></label>
              <input type="text" name="property_type" className="form-input" value={formData.property_type} onChange={handleChange} placeholder="e.g., House" />
            </div>
            )}
            {features.jobAddress && (
            <div className="form-group">
              <label className="form-label">Eircode <HelpTooltip text="Irish postal code for the job location. Helps with routing and navigation." /></label>
              <input type="text" name="eircode" className="form-input" value={formData.eircode} onChange={handleChange} />
            </div>
            )}
          </div>

          {features.jobAddress && (
          <div className="form-group">
            <label className="form-label">{terminology.job} Address</label>
            <textarea name="job_address" className="form-textarea" value={formData.job_address} onChange={handleChange} rows="2" placeholder={`If different from ${terminology.client.toLowerCase()}'s address`} />
          </div>
          )}

          {/* Restaurant-specific fields */}
          {features.tableManagement && (
            <div className="form-grid">
              <div className="form-group">
                <label className="form-label">Table Number</label>
                <input type="text" name="table_number" className="form-input" value={formData.table_number} onChange={handleChange} placeholder="e.g., 5, A3, Bar 2" />
              </div>
              <div className="form-group">
                <label className="form-label">Party Size</label>
                <input type="number" name="party_size" className="form-input" value={formData.party_size} onChange={handleChange} min="1" placeholder="Number of guests" />
              </div>
              <div className="form-group">
                <label className="form-label">Dining Area</label>
                <select name="dining_area" className="form-input" value={formData.dining_area} onChange={handleChange}>
                  <option value="">Any area</option>
                  <option value="Indoor">Indoor</option>
                  <option value="Outdoor">Outdoor</option>
                  <option value="Private Room">Private Room</option>
                  <option value="Bar">Bar</option>
                  <option value="Terrace">Terrace</option>
                  <option value="Rooftop">Rooftop</option>
                  <option value="Garden">Garden</option>
                </select>
              </div>
            </div>
          )}
          {features.tableManagement && (
            <div className="form-group">
              <label className="form-label">Special Requests</label>
              <textarea name="special_requests" className="form-textarea" value={formData.special_requests} onChange={handleChange} rows="2" placeholder="e.g., High chair needed, birthday celebration, allergies..." />
            </div>
          )}
          
          <div className="form-group">
            <label className="form-label">
              {features.tableManagement ? 'Deposit / Pre-set Price (€)' : 'Estimated Charge (€)'}
              {' '}<HelpTooltip text={features.tableManagement
                ? "Optional — leave blank if the final bill will be added after the reservation. Use for deposits or set-menu pricing."
                : "The price you'll charge the customer. Pre-filled from the service — adjust if needed for this specific job."} />
            </label>
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
          {features.callouts && (
          <div className="form-group">
            <label className="form-label">Requires Initial Callout? <HelpTooltip text="Enable if an employee needs to visit the site first to assess the job. This books the callout service from your Services tab rather than the full job." /></label>
            <div className="callout-toggle-wrapper">
              <button type="button" className={`callout-toggle ${formData.requires_callout ? 'active' : ''}`}
                onClick={() => setFormData(prev => ({ ...prev, requires_callout: !prev.requires_callout, requires_quote: false }))}
                role="switch" aria-checked={formData.requires_callout}>
                <span className="callout-toggle-slider" />
              </button>
              <span className="callout-toggle-label">{formData.requires_callout ? 'Yes — callout visit needed before work begins' : 'No — go straight to the job'}</span>
            </div>
          </div>
          )}

          {/* Quote Visit Toggle */}
          {features.quotes && !formData.requires_callout && (
          <div className="form-group">
            <label className="form-label">Requires Quote Visit? <HelpTooltip text="Enable if an employee needs to visit the site first to give a free quote. This books the quote service from your Services tab rather than the full job." /></label>
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
          {features.emergencyJobs && (
          <div className="form-group">
            <label className="form-label">Emergency Job? <HelpTooltip text="Mark as emergency to immediately notify all available employees via dashboard and email. An employee must accept the job to be dispatched." /></label>
            <div className="callout-toggle-wrapper">
              <button type="button" className={`callout-toggle emergency-toggle ${formData.is_emergency ? 'active' : ''}`}
                onClick={() => setFormData(prev => ({ ...prev, is_emergency: !prev.is_emergency }))}
                role="switch" aria-checked={formData.is_emergency}>
                <span className="callout-toggle-slider" />
              </button>
              <span className="callout-toggle-label">{formData.is_emergency ? 'Yes — notify employees immediately' : 'No — standard job'}</span>
            </div>
          </div>
          )}

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
            <button type="submit" className="btn btn-primary" disabled={mutation.isPending}>{mutation.isPending ? 'Creating...' : employeeMode ? 'Create & Assign to Me' : `Create ${terminology.job}`}</button>
          </div>
        </form>
      </Modal>
      <AddClientModal isOpen={isAddClientModalOpen} onClose={handleCloseAddClient} employeeMode={employeeMode} />
    </>
  );
}

export default AddJobModal;
