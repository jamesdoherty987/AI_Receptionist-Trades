import { useState, useMemo, useRef, useEffect, useCallback } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { createBooking, getClients, checkAvailability, checkMonthlyAvailability, getServicesMenu, getWorkers, checkWorkerAvailability } from '../../services/api';
import Modal from './Modal';
import { useToast } from '../Toast';
import AddClientModal from './AddClientModal';
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
    else if (dayInfo?.status === 'full') statusClass = 'mc-full';
    else if (dayInfo?.status === 'partial') statusClass = 'mc-partial';
    else if (dayInfo?.status === 'free') statusClass = 'mc-free';

    cells.push(
      <button
        key={d}
        type="button"
        className={`mc-cell mc-day ${statusClass} ${isSelected ? 'mc-selected' : ''}`}
        disabled={isPast || dayInfo?.status === 'closed'}
        onClick={() => !isPast && dayInfo?.status !== 'closed' && onSelectDate(iso)}
        title={isPast ? 'Past date' : dayInfo?.status === 'closed' ? 'Closed' : dayInfo?.status === 'full' ? 'Fully booked' : dayInfo?.status === 'partial' ? `${dayInfo.free} slot${dayInfo.free !== 1 ? 's' : ''} free` : 'Available'}
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
        <span className="mc-legend-item"><span className="mc-dot mc-dot-closed"></span>Closed</span>
      </div>
    </div>
  );
}

function AddJobModal({ isOpen, onClose }) {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  
  const [formData, setFormData] = useState({
    client_id: '', appointment_time: '', service_type: '', job_address: '', eircode: '',
    property_type: '', estimated_charge: '', duration_minutes: 1440, notes: '', worker_id: '', requires_callout: false
  });
  
  const [selectedDate, setSelectedDate] = useState('');
  const [selectedService, setSelectedService] = useState(null);
  const [selectedWorker, setSelectedWorker] = useState(null);
  const [workerAvailability, setWorkerAvailability] = useState(null);
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

  const { data: clients } = useQuery({ queryKey: ['clients'], queryFn: async () => (await getClients()).data, enabled: isOpen });
  const { data: servicesMenu } = useQuery({ queryKey: ['services-menu'], queryFn: async () => (await getServicesMenu()).data, enabled: isOpen });
  const { data: workers } = useQuery({ queryKey: ['workers'], queryFn: async () => (await getWorkers()).data, enabled: isOpen });

  // Monthly availability (fires when service is selected)
  const { data: monthlyData, isLoading: isLoadingMonthly } = useQuery({
    queryKey: ['monthly-availability', calYear, calMonth + 1, formData.service_type, formData.worker_id],
    queryFn: async () => (await checkMonthlyAvailability(calYear, calMonth + 1, formData.service_type, formData.worker_id || null)).data,
    enabled: !!formData.service_type && isOpen
  });

  // Daily slots (fires when date is selected)
  const { data: availability, isLoading: isLoadingAvailability } = useQuery({
    queryKey: ['availability', selectedDate, formData.service_type, formData.worker_id],
    queryFn: async () => (await checkAvailability(selectedDate, formData.service_type, formData.worker_id || null)).data,
    enabled: !!selectedDate && !!formData.service_type && isOpen
  });

  const isFullDayJob = (formData.duration_minutes || 0) >= 1440;

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
    mutationFn: createBooking,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['dashboard'] }); queryClient.invalidateQueries({ queryKey: ['bookings'] }); onClose(); addToast('Job created successfully!', 'success'); },
    onError: (error) => { addToast('Error creating job: ' + (error.response?.data?.error || error.message), 'error'); }
  });

  const resetForm = () => {
    setFormData({ client_id: '', appointment_time: '', service_type: '', job_address: '', eircode: '', property_type: '', estimated_charge: '', duration_minutes: 1440, notes: '', worker_id: '', requires_callout: false });
    setSelectedDate(''); setSelectedService(null); setSelectedWorker(null); setWorkerAvailability(null);
    setCustomerPickerOpen(false); setCustomerSearch(''); setSelectedCustomer(null);
    const n = new Date(); setCalMonth(n.getMonth()); setCalYear(n.getFullYear());
  };

  const handleSelectCustomer = (customer) => { setSelectedCustomer(customer); setFormData(prev => ({ ...prev, client_id: customer.id })); setCustomerPickerOpen(false); setCustomerSearch(''); };
  const handleClearCustomer = () => { setSelectedCustomer(null); setFormData(prev => ({ ...prev, client_id: '' })); };

  const handleServiceSelect = (service) => {
    setSelectedService(service);
    const newDuration = service.duration_minutes || 60;
    setFormData(prev => ({ ...prev, service_type: service.name, estimated_charge: service.price || '', duration_minutes: newDuration }));
    // Reset date selection when service changes (availability changes)
    setSelectedDate('');
    setFormData(prev => ({ ...prev, appointment_time: '' }));
    if (formData.worker_id && formData.appointment_time) checkWorkerAvailabilityForJob(formData.worker_id, formData.appointment_time, newDuration);
  };

  const handleWorkerSelect = async (workerId) => {
    if (!workerId) { setSelectedWorker(null); setFormData(prev => ({ ...prev, worker_id: '' })); setWorkerAvailability(null); return; }
    const worker = workers?.find(w => w.id === parseInt(workerId));
    setSelectedWorker(worker || null);
    setFormData(prev => ({ ...prev, worker_id: workerId }));
    if (formData.appointment_time) await checkWorkerAvailabilityForJob(workerId, formData.appointment_time, formData.duration_minutes || 60);
  };

  const checkWorkerAvailabilityForJob = async (workerId, appointmentTime, duration) => {
    if (!workerId || !appointmentTime) { setWorkerAvailability(null); return; }
    try { const response = await checkWorkerAvailability(workerId, appointmentTime, duration || 60); setWorkerAvailability(response.data); }
    catch (error) { console.error('Error checking worker availability:', error); setWorkerAvailability(null); }
  };

  const handleDateSelect = (iso) => {
    setSelectedDate(iso);
    if (isFullDayJob) {
      // For full-day jobs, set time to business hours start
      const dateTime = `${iso}T${String(monthlyData?.business_hours?.start || 9).padStart(2, '0')}:00`;
      setFormData(prev => ({ ...prev, appointment_time: dateTime }));
      if (formData.worker_id) checkWorkerAvailabilityForJob(formData.worker_id, dateTime, formData.duration_minutes || 60);
    } else {
      // For hourly jobs, clear time so user picks a slot
      setFormData(prev => ({ ...prev, appointment_time: '' }));
    }
  };

  const handleTimeSlotClick = (slot) => {
    if (!slot.available) { addToast(`Slot booked${slot.booking?.client_name ? ` for ${slot.booking.client_name}` : ''}`, 'warning'); return; }
    const dateTime = `${selectedDate}T${slot.time}`;
    setFormData(prev => ({ ...prev, appointment_time: dateTime }));
    if (formData.worker_id) checkWorkerAvailabilityForJob(formData.worker_id, dateTime, formData.duration_minutes || 60);
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    if (name === 'duration_minutes') {
      // If duration changes, reset date/time since availability changes
      setSelectedDate('');
      setFormData(prev => ({ ...prev, [name]: value, appointment_time: '' }));
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!formData.client_id || !formData.appointment_time || !formData.service_type) { addToast('Please fill in all required fields', 'warning'); return; }
    if (workerAvailability && !workerAvailability.available) { addToast(`Worker not available: ${workerAvailability.message}`, 'error'); return; }
    mutation.mutate(formData);
  };

  const handleOpenAddClient = () => { setCustomerPickerOpen(false); setIsAddClientModalOpen(true); };
  const handleCloseAddClient = () => { setIsAddClientModalOpen(false); queryClient.invalidateQueries({ queryKey: ['clients'] }); };

  const handleMonthChange = (m, y) => { setCalMonth(m); setCalYear(y); };

  return (
    <>
      <Modal isOpen={isOpen} onClose={onClose} title="Add New Job" size="large">
        <form onSubmit={handleSubmit} className="form add-job-form">
          
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
                    <option key={s.id} value={s.name}>{s.name} {s.duration_minutes ? `(${formatDuration(s.duration_minutes)})` : ''} {s.price ? `- €${s.price}` : ''}</option>
                  ))}
                </select>
                {selectedService && (
                  <div className="service-badge">
                    <span><i className="fas fa-clock"></i> {formatDuration(selectedService.duration_minutes || 60)}</span>
                    {selectedService.price && <span><i className="fas fa-euro-sign"></i> €{selectedService.price}</span>}
                  </div>
                )}
              </>
            ) : (
              <input type="text" name="service_type" className="form-input" value={formData.service_type} onChange={handleChange} placeholder="e.g., Plumbing repair" required />
            )}
          </div>

          {/* Worker Assignment */}
          <div className="form-group">
            <label className="form-label">Assign Worker</label>
            <select name="worker_id" className="form-input" value={formData.worker_id} onChange={(e) => handleWorkerSelect(e.target.value)}>
              <option value="">No worker (check all availability)</option>
              {workers?.map(w => <option key={w.id} value={w.id}>{w.name} {w.trade_specialty && `(${w.trade_specialty})`}</option>)}
            </select>
            {selectedWorker && <div className="worker-selected-info"><i className="fas fa-hard-hat"></i> Showing availability for <strong>{selectedWorker.name}</strong></div>}
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
                        {selectedWorker ? ` — ${selectedWorker.name}` : ''}
                      </h4>
                    </div>
                    {isLoadingAvailability ? (
                      <div className="time-slots-loading"><i className="fas fa-spinner fa-spin"></i> Loading slots...</div>
                    ) : availability?.slots?.length > 0 ? (
                      <div className="time-slots-grid">
                        {availability.slots.map(slot => (
                          <button key={slot.time} type="button"
                            className={`time-slot ${slot.available ? 'available' : 'booked'} ${formData.appointment_time === `${selectedDate}T${slot.time}` ? 'selected' : ''}`}
                            onClick={() => handleTimeSlotClick(slot)}
                            disabled={!slot.available}
                            title={slot.available ? 'Available' : `Booked: ${slot.booking?.client_name || ''} — ${slot.booking?.service_type || ''}`}
                          >
                            <span className="slot-time">{slot.time}</span>
                            {!slot.available && slot.booking && <span className="slot-info">{slot.booking.client_name}</span>}
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

            {/* Worker availability status */}
            {workerAvailability && formData.worker_id && formData.appointment_time && (
              workerAvailability.available ? (
                <div className="worker-available-badge"><i className="fas fa-check-circle"></i> {selectedWorker?.name} is available at this time</div>
              ) : (
                <div className="worker-conflict-warning"><i className="fas fa-exclamation-triangle"></i> {workerAvailability.message}</div>
              )
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
              <label className="form-label">Property Type</label>
              <input type="text" name="property_type" className="form-input" value={formData.property_type} onChange={handleChange} placeholder="e.g., House" />
            </div>
            <div className="form-group">
              <label className="form-label">Eircode</label>
              <input type="text" name="eircode" className="form-input" value={formData.eircode} onChange={handleChange} />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Job Address</label>
            <textarea name="job_address" className="form-textarea" value={formData.job_address} onChange={handleChange} rows="2" placeholder="If different from customer's address" />
          </div>
          
          <div className="form-group">
            <label className="form-label">Estimated Charge (€)</label>
            <input type="number" name="estimated_charge" className="form-input" value={formData.estimated_charge} onChange={handleChange} step="0.01" min="0" placeholder="0.00" />
          </div>

          {/* Initial Callout Toggle */}
          <div className="form-group">
            <label className="form-label">Requires Initial Callout?</label>
            <div className="callout-toggle-wrapper">
              <button type="button" className={`callout-toggle ${formData.requires_callout ? 'active' : ''}`}
                onClick={() => setFormData(prev => ({ ...prev, requires_callout: !prev.requires_callout }))}
                role="switch" aria-checked={formData.requires_callout}>
                <span className="callout-toggle-slider" />
              </button>
              <span className="callout-toggle-label">{formData.requires_callout ? 'Yes — callout visit needed before work begins' : 'No — go straight to the job'}</span>
            </div>
          </div>
          
          <div className="form-group">
            <label className="form-label">Notes</label>
            <textarea name="notes" className="form-textarea" value={formData.notes} onChange={handleChange} rows="3" placeholder="Additional details" />
          </div>

          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={mutation.isPending}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={mutation.isPending}>{mutation.isPending ? 'Creating...' : 'Create Job'}</button>
          </div>
        </form>
      </Modal>
      <AddClientModal isOpen={isAddClientModalOpen} onClose={handleCloseAddClient} />
    </>
  );
}

export default AddJobModal;
