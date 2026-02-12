import { useState, useMemo, useRef, useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { createBooking, getClients, checkAvailability, getServicesMenu, getWorkers, checkWorkerAvailability } from '../../services/api';
import Modal from './Modal';
import { useToast } from '../Toast';
import AddClientModal from './AddClientModal';
import './AddJobModal.css';

function AddJobModal({ isOpen, onClose }) {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const { hasActiveSubscription } = useAuth();
  const isSubscriptionActive = hasActiveSubscription();
  
  const [formData, setFormData] = useState({
    client_id: '',
    appointment_time: '',
    service_type: '',
    job_address: '',
    eircode: '',
    property_type: '',
    estimated_charge: '',
    duration_minutes: '',
    notes: '',
    worker_id: ''
  });
  
  const [selectedQuickDate, setSelectedQuickDate] = useState('');
  const [selectedDate, setSelectedDate] = useState('');
  const [showTimeSlots, setShowTimeSlots] = useState(false);
  const [selectedService, setSelectedService] = useState(null);
  const [selectedWorker, setSelectedWorker] = useState(null);
  const [workerAvailability, setWorkerAvailability] = useState(null);
  const [customerPickerOpen, setCustomerPickerOpen] = useState(false);
  const [customerSearch, setCustomerSearch] = useState('');
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [isAddClientModalOpen, setIsAddClientModalOpen] = useState(false);
  const customerPickerRef = useRef(null);

  // Reset form when modal closes
  useEffect(() => {
    if (!isOpen) {
      resetForm();
    }
  }, [isOpen]);

  const { data: clients } = useQuery({
    queryKey: ['clients'],
    queryFn: async () => (await getClients()).data,
    enabled: isOpen
  });

  const { data: servicesMenu } = useQuery({
    queryKey: ['services-menu'],
    queryFn: async () => (await getServicesMenu()).data,
    enabled: isOpen
  });

  const { data: workers } = useQuery({
    queryKey: ['workers'],
    queryFn: async () => (await getWorkers()).data,
    enabled: isOpen
  });

  const { data: availability, isLoading: isLoadingAvailability } = useQuery({
    queryKey: ['availability', selectedDate, formData.service_type, formData.worker_id],
    queryFn: async () => (await checkAvailability(selectedDate, formData.service_type, formData.worker_id || null)).data,
    enabled: !!selectedDate && !!formData.service_type && isOpen
  });

  const filteredCustomers = useMemo(() => {
    if (!clients) return [];
    if (!customerSearch.trim()) return clients;
    const term = customerSearch.toLowerCase();
    return clients.filter(c =>
      c.name?.toLowerCase().includes(term) ||
      c.phone?.includes(customerSearch) ||
      c.email?.toLowerCase().includes(term)
    );
  }, [clients, customerSearch]);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (customerPickerRef.current && !customerPickerRef.current.contains(e.target)) {
        setCustomerPickerOpen(false);
      }
    };
    if (customerPickerOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [customerPickerOpen]);

  const mutation = useMutation({
    mutationFn: createBooking,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['bookings'] });
      onClose();
      addToast('Job created successfully!', 'success');
    },
    onError: (error) => {
      addToast('Error creating job: ' + (error.response?.data?.error || error.message), 'error');
    }
  });

  const resetForm = () => {
    setFormData({ client_id: '', appointment_time: '', service_type: '', job_address: '', eircode: '', property_type: '', estimated_charge: '', duration_minutes: '', notes: '', worker_id: '' });
    setSelectedQuickDate('');
    setSelectedDate('');
    setShowTimeSlots(false);
    setSelectedService(null);
    setSelectedWorker(null);
    setWorkerAvailability(null);
    setCustomerPickerOpen(false);
    setCustomerSearch('');
    setSelectedCustomer(null);
  };

  const handleSelectCustomer = (customer) => {
    setSelectedCustomer(customer);
    setFormData(prev => ({ ...prev, client_id: customer.id }));
    setCustomerPickerOpen(false);
    setCustomerSearch('');
  };

  const handleClearCustomer = () => {
    setSelectedCustomer(null);
    setFormData(prev => ({ ...prev, client_id: '' }));
  };

  const handleServiceSelect = (service) => {
    setSelectedService(service);
    const newDuration = service.duration_minutes || 60;
    setFormData(prev => ({ ...prev, service_type: service.name, estimated_charge: service.price || '', duration_minutes: newDuration }));
    if (formData.worker_id && formData.appointment_time) {
      checkWorkerAvailabilityForJob(formData.worker_id, formData.appointment_time, newDuration);
    }
  };

  const handleWorkerSelect = async (workerId) => {
    if (!workerId) {
      setSelectedWorker(null);
      setFormData(prev => ({ ...prev, worker_id: '' }));
      setWorkerAvailability(null);
      return;
    }
    const worker = workers?.find(w => w.id === parseInt(workerId));
    setSelectedWorker(worker || null);
    setFormData(prev => ({ ...prev, worker_id: workerId }));
    if (formData.appointment_time) {
      await checkWorkerAvailabilityForJob(workerId, formData.appointment_time, formData.duration_minutes || 60);
    }
  };

  const checkWorkerAvailabilityForJob = async (workerId, appointmentTime, duration) => {
    if (!workerId || !appointmentTime) { 
      setWorkerAvailability(null); 
      return; 
    }
    try {
      const response = await checkWorkerAvailability(workerId, appointmentTime, duration || 60);
      setWorkerAvailability(response.data);
    } catch (error) {
      console.error('Error checking worker availability:', error);
      setWorkerAvailability(null);
    }
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    if (name === 'appointment_time' && value) {
      const dateOnly = value.split('T')[0];
      if (dateOnly !== selectedDate) { 
        setSelectedDate(dateOnly); 
      }
      setShowTimeSlots(true);
      if (formData.worker_id) {
        checkWorkerAvailabilityForJob(formData.worker_id, value, formData.duration_minutes || 60);
      }
    }
  };

  const setQuickDate = (type) => {
    setSelectedQuickDate(type);
    const now = new Date();
    if (type === 'tomorrow') now.setDate(now.getDate() + 1);
    else if (type === 'nextWeek') now.setDate(now.getDate() + 7);
    const date = now.toISOString().split('T')[0];
    const dateTime = `${date}T09:00`;
    setSelectedDate(date);
    setShowTimeSlots(true);
    setFormData(prev => ({ ...prev, appointment_time: dateTime }));
    if (formData.worker_id) {
      checkWorkerAvailabilityForJob(formData.worker_id, dateTime, formData.duration_minutes || 60);
    }
  };

  const handleTimeSlotClick = (slot) => {
    if (!slot.available) { 
      addToast(`Slot booked${slot.booking?.client_name ? ` for ${slot.booking.client_name}` : ''}`, 'warning'); 
      return; 
    }
    const dateTime = `${selectedDate}T${slot.time}`;
    setFormData(prev => ({ ...prev, appointment_time: dateTime }));
    if (formData.worker_id) {
      checkWorkerAvailabilityForJob(formData.worker_id, dateTime, formData.duration_minutes || 60);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!formData.client_id || !formData.appointment_time || !formData.service_type) { 
      addToast('Please fill in all required fields', 'warning'); 
      return; 
    }
    if (workerAvailability && !workerAvailability.available) { 
      addToast(`Worker not available: ${workerAvailability.message}`, 'error'); 
      return; 
    }
    mutation.mutate(formData);
  };

  const handleOpenAddClient = () => { 
    setCustomerPickerOpen(false); 
    setIsAddClientModalOpen(true); 
  };
  
  const handleCloseAddClient = () => { 
    setIsAddClientModalOpen(false); 
    queryClient.invalidateQueries({ queryKey: ['clients'] }); 
  };

  return (
    <>
      <Modal isOpen={isOpen} onClose={onClose} title="Add New Job" size="large">
        {!isSubscriptionActive ? (
          <div className="subscription-required-message">
            <div className="subscription-required-content">
              <i className="fas fa-lock"></i>
              <h3>Subscription Required</h3>
              <p>Your trial has expired. Subscribe to continue adding jobs.</p>
              <Link to="/settings?tab=subscription" className="btn btn-primary" onClick={onClose}>
                <i className="fas fa-credit-card"></i> Subscribe Now
              </Link>
            </div>
          </div>
        ) : (
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
                  <button type="button" className="customer-clear-btn" onClick={handleClearCustomer}>
                    <i className="fas fa-times"></i>
                  </button>
                </div>
              ) : (
                <button type="button" className="customer-picker-trigger" onClick={() => setCustomerPickerOpen(!customerPickerOpen)}>
                  <i className="fas fa-user"></i>
                  <span>Select a customer...</span>
                  <i className={`fas fa-chevron-${customerPickerOpen ? 'up' : 'down'}`}></i>
                </button>
              )}
              {customerPickerOpen && (
                <div className="customer-picker-dropdown">
                  <div className="customer-picker-search">
                    <i className="fas fa-search"></i>
                    <input 
                      type="text" 
                      placeholder="Search customers..." 
                      value={customerSearch} 
                      onChange={(e) => setCustomerSearch(e.target.value)} 
                      autoFocus 
                    />
                  </div>
                  <div className="customer-picker-list">
                    {filteredCustomers.length === 0 ? (
                      <div className="customer-picker-empty"><p>No customers found</p></div>
                    ) : (
                      filteredCustomers.slice(0, 10).map(customer => (
                        <div key={customer.id} className="customer-picker-item" onClick={() => handleSelectCustomer(customer)}>
                          <div className="customer-picker-avatar">{customer.name?.charAt(0).toUpperCase() || '?'}</div>
                          <div className="customer-picker-info">
                            <span className="customer-picker-name">{customer.name}</span>
                            <span className="customer-picker-contact">{customer.phone || customer.email || 'No contact'}</span>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                  <div className="customer-picker-footer">
                    <button type="button" className="customer-add-btn" onClick={handleOpenAddClient}>
                      <i className="fas fa-plus"></i> Add New Customer
                    </button>
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
                <select 
                  name="service_type" 
                  className="form-input" 
                  value={formData.service_type} 
                  onChange={(e) => { 
                    const s = servicesMenu.services.find(x => x.name === e.target.value); 
                    if (s) {
                      handleServiceSelect(s);
                    } else {
                      setFormData(prev => ({ ...prev, service_type: e.target.value })); 
                      setSelectedService(null);
                    }
                  }} 
                  required
                >
                  <option value="">Select a service...</option>
                  {servicesMenu.services.map(s => (
                    <option key={s.id} value={s.name}>
                      {s.name} {s.duration_minutes ? `(${s.duration_minutes} mins)` : ''} {s.price ? `- €${s.price}` : ''}
                    </option>
                  ))}
                </select>
                {selectedService && (
                  <div className="service-badge">
                    <span><i className="fas fa-clock"></i> {selectedService.duration_minutes || 60} mins</span>
                    {selectedService.price && <span><i className="fas fa-euro-sign"></i> €{selectedService.price}</span>}
                  </div>
                )}
              </>
            ) : (
              <input 
                type="text" 
                name="service_type" 
                className="form-input" 
                value={formData.service_type} 
                onChange={handleChange} 
                placeholder="e.g., Plumbing repair" 
                required 
              />
            )}
          </div>

          {/* Worker Assignment */}
          <div className="form-group">
            <label className="form-label">Assign Worker</label>
            <select 
              name="worker_id" 
              className="form-input" 
              value={formData.worker_id} 
              onChange={(e) => handleWorkerSelect(e.target.value)}
            >
              <option value="">No worker (check all availability)</option>
              {workers?.map(w => (
                <option key={w.id} value={w.id}>
                  {w.name} {w.trade_specialty && `(${w.trade_specialty})`}
                </option>
              ))}
            </select>
            {selectedWorker && (
              <div className="worker-selected-info">
                <i className="fas fa-hard-hat"></i> Showing availability for <strong>{selectedWorker.name}</strong>
              </div>
            )}
          </div>

          {/* Date & Time */}
          <div className="form-group">
            <label className="form-label">Date & Time <span className="required">*</span></label>
            <div className="quick-date-buttons">
              <button type="button" className={`quick-date-btn ${selectedQuickDate === 'today' ? 'active' : ''}`} onClick={() => setQuickDate('today')}>Today</button>
              <button type="button" className={`quick-date-btn ${selectedQuickDate === 'tomorrow' ? 'active' : ''}`} onClick={() => setQuickDate('tomorrow')}>Tomorrow</button>
              <button type="button" className={`quick-date-btn ${selectedQuickDate === 'nextWeek' ? 'active' : ''}`} onClick={() => setQuickDate('nextWeek')}>Next Week</button>
            </div>
            <input 
              type="datetime-local" 
              name="appointment_time" 
              className="form-input" 
              value={formData.appointment_time} 
              onChange={handleChange} 
              required 
            />
            
            {/* Time Slots */}
            {showTimeSlots && selectedDate && formData.service_type && (
              <div className="time-slots-container">
                <div className="time-slots-header">
                  <h4>{selectedWorker ? `${selectedWorker.name}'s Available Slots` : 'Available Slots'}</h4>
                </div>
                {isLoadingAvailability ? (
                  <div className="time-slots-loading"><i className="fas fa-spinner fa-spin"></i> Loading...</div>
                ) : availability?.slots?.length > 0 ? (
                  <div className="time-slots-grid">
                    {availability.slots.map(slot => (
                      <button 
                        key={slot.time} 
                        type="button" 
                        className={`time-slot ${slot.available ? 'available' : 'booked'} ${formData.appointment_time === `${selectedDate}T${slot.time}` ? 'selected' : ''}`} 
                        onClick={() => handleTimeSlotClick(slot)} 
                        disabled={!slot.available}
                      >
                        {slot.time}
                      </button>
                    ))}
                  </div>
                ) : (
                  <div className="time-slots-empty">No slots available for this day</div>
                )}
              </div>
            )}
            
            {/* Prompt to select service */}
            {showTimeSlots && selectedDate && !formData.service_type && (
              <div className="time-slots-prompt">
                <i className="fas fa-info-circle"></i> Select a service first to see available slots
              </div>
            )}
            
            {/* Worker availability status */}
            {workerAvailability && formData.worker_id && formData.appointment_time && (
              workerAvailability.available ? (
                <div className="worker-available-badge">
                  <i className="fas fa-check-circle"></i> {selectedWorker?.name} is available at this time
                </div>
              ) : (
                <div className="worker-conflict-warning">
                  <i className="fas fa-exclamation-triangle"></i> {workerAvailability.message}
                </div>
              )
            )}
          </div>

          {/* Additional Fields */}
          <div className="form-grid">
            <div className="form-group">
              <label className="form-label">Duration (mins)</label>
              <select 
                name="duration_minutes" 
                className="form-input" 
                value={formData.duration_minutes} 
                onChange={handleChange}
              >
                <option value="30">30 mins</option>
                <option value="60">1 hour</option>
                <option value="90">1.5 hours</option>
                <option value="120">2 hours</option>
                <option value="150">2.5 hours</option>
                <option value="180">3 hours</option>
                <option value="240">4 hours</option>
                <option value="300">5 hours</option>
                <option value="360">6 hours</option>
                <option value="480">8 hours</option>
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
          
          <div className="form-group">
            <label className="form-label">Notes</label>
            <textarea name="notes" className="form-textarea" value={formData.notes} onChange={handleChange} rows="3" placeholder="Additional details" />
          </div>

          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={mutation.isPending}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={mutation.isPending}>
              {mutation.isPending ? 'Creating...' : 'Create Job'}
            </button>
          </div>
        </form>
        )}
      </Modal>
      
      <AddClientModal isOpen={isAddClientModalOpen} onClose={handleCloseAddClient} />
    </>
  );
}

export default AddJobModal;
