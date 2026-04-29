import { useState, useMemo, useRef, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { formatCurrency, formatDate } from '../../utils/helpers';
import { formatDuration } from '../../utils/durationOptions';
import { getQuotes, createQuote, updateQuote, deleteQuote, convertQuoteToJob, getClients, getTaxSettings, getServicesMenu, getEmployees, checkAvailability, checkMonthlyAvailability, checkEmployeeAvailability, sendQuote, generateQuoteAcceptLink, sendQuoteFollowUp } from '../../services/api';
import { useToast } from '../Toast';
import DocumentPreview from './DocumentPreview';
import LoadingSpinner from '../LoadingSpinner';
import Modal from '../modals/Modal';
import AddClientModal from '../modals/AddClientModal';
import { DURATION_OPTIONS_GROUPED } from '../../utils/durationOptions';

const STATUS_CONFIG = {
  draft: { label: 'Draft', color: '#94a3b8', bg: '#f1f5f9', icon: 'fa-file' },
  sent: { label: 'Sent', color: '#3b82f6', bg: '#eff6ff', icon: 'fa-paper-plane' },
  accepted: { label: 'Accepted', color: '#10b981', bg: '#ecfdf5', icon: 'fa-check-circle' },
  declined: { label: 'Declined', color: '#ef4444', bg: '#fef2f2', icon: 'fa-times-circle' },
  expired: { label: 'Expired', color: '#f59e0b', bg: '#fffbeb', icon: 'fa-clock' },
  converted: { label: 'Converted to Job', color: '#8b5cf6', bg: '#f5f3ff', icon: 'fa-exchange-alt' },
};

/* ===== Mini Calendar (reused from AddJobModal pattern) ===== */
function MiniCalendar({ selectedDate, onSelectDate, monthData, isLoading, calMonth, calYear, onMonthChange }) {
  const daysInMonth = new Date(calYear, calMonth + 1, 0).getDate();
  const firstDayOfWeek = new Date(calYear, calMonth, 1).getDay();
  const startOffset = (firstDayOfWeek + 6) % 7;
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const monthNames = ['January','February','March','April','May','June','July','August','September','October','November','December'];

  const prevMonth = () => { if (calMonth === 0) onMonthChange(11, calYear - 1); else onMonthChange(calMonth - 1, calYear); };
  const nextMonth = () => { if (calMonth === 11) onMonthChange(0, calYear + 1); else onMonthChange(calMonth + 1, calYear); };

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
      <button key={d} type="button" className={`mc-cell mc-day ${statusClass} ${isSelected ? 'mc-selected' : ''}`}
        disabled={isDisabled} onClick={() => !isDisabled && onSelectDate(iso)}
        title={isPast ? 'Past date' : dayInfo?.status === 'closed' ? 'Closed' : dayInfo?.status === 'leave' ? 'Employee on leave' : dayInfo?.status === 'full' ? 'Fully booked' : dayInfo?.status === 'partial' ? `${dayInfo.free} slot${dayInfo.free !== 1 ? 's' : ''} free` : 'Available'}>
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
      <div className="mc-weekdays">{['Mo','Tu','We','Th','Fr','Sa','Su'].map(d => <div key={d} className="mc-weekday">{d}</div>)}</div>
      <div className="mc-grid">{isLoading ? <div className="mc-loading"><i className="fas fa-spinner fa-spin"></i></div> : cells}</div>
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

/* ===== Convert to Job Modal ===== */
function ConvertToJobModal({ isOpen, onClose, quote, onConverted }) {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [selectedDate, setSelectedDate] = useState('');
  const [appointmentTime, setAppointmentTime] = useState('');
  const [anyEmployeeMode, setAnyEmployeeMode] = useState(true);
  const [assignedEmployees, setAssignedEmployees] = useState([]);
  const assignedEmployeesRef = useRef([]);
  const [durationMinutes, setDurationMinutes] = useState(60);
  const [address, setAddress] = useState('');
  const [notes, setNotes] = useState('');

  const now = new Date();
  const [calMonth, setCalMonth] = useState(now.getMonth());
  const [calYear, setCalYear] = useState(now.getFullYear());

  const { data: employees } = useQuery({ queryKey: ['employees'], queryFn: async () => (await getEmployees()).data, enabled: isOpen });
  const { data: servicesMenu } = useQuery({ queryKey: ['services-menu'], queryFn: async () => (await getServicesMenu()).data, enabled: isOpen });

  // Find matching service for the quote title
  const matchedService = useMemo(() => {
    if (!servicesMenu?.services || !quote?.title) return null;
    return servicesMenu.services.find(s => s.name?.toLowerCase() === quote.title?.toLowerCase());
  }, [servicesMenu, quote]);

  // Use matched service duration or default
  const effectiveDuration = matchedService?.duration_minutes || durationMinutes;
  const serviceType = quote?.title || 'Service';

  const effectiveEmployeeList = useMemo(() => assignedEmployees, [assignedEmployees]);
  const assignedEmployeeIds = effectiveEmployeeList.map(w => w.id).sort().join(',');

  // Monthly availability
  const { data: monthlyData, isLoading: isLoadingMonthly } = useQuery({
    queryKey: ['monthly-availability', calYear, calMonth + 1, serviceType, anyEmployeeMode, effectiveDuration, assignedEmployeeIds],
    queryFn: async () => {
      if (effectiveEmployeeList.length > 0) {
        const results = await Promise.all(
          effectiveEmployeeList.map(w => checkMonthlyAvailability(calYear, calMonth + 1, serviceType, w.id, false, effectiveDuration).then(r => r.data))
        );
        if (!results.length || !results[0]) return results[0];
        const merged = { ...results[0], days: { ...results[0].days } };
        if (merged.days) {
          for (const dayKey of Object.keys(merged.days)) {
            const dayStatuses = results.map(r => r.days?.[dayKey]?.status || 'closed');
            if (dayStatuses.some(s => s === 'closed')) merged.days[dayKey] = { ...merged.days[dayKey], status: 'closed', free: 0 };
            else if (dayStatuses.some(s => s === 'leave' || s === 'full')) merged.days[dayKey] = { ...merged.days[dayKey], status: 'full', free: 0 };
            else if (dayStatuses.some(s => s === 'partial')) {
              const minFree = Math.min(...results.map(r => r.days?.[dayKey]?.free ?? 0));
              merged.days[dayKey] = { ...merged.days[dayKey], status: minFree > 0 ? 'partial' : 'full', free: minFree };
            }
          }
        }
        return merged;
      }
      return (await checkMonthlyAvailability(calYear, calMonth + 1, serviceType, null, anyEmployeeMode, effectiveDuration)).data;
    },
    enabled: isOpen,
  });

  // Daily slots
  const { data: availability, isLoading: isLoadingAvailability } = useQuery({
    queryKey: ['availability', selectedDate, serviceType, anyEmployeeMode, effectiveDuration, assignedEmployeeIds],
    queryFn: async () => {
      if (effectiveEmployeeList.length > 0) {
        const results = await Promise.all(
          effectiveEmployeeList.map(w => checkAvailability(selectedDate, serviceType, w.id, false, effectiveDuration).then(r => r.data))
        );
        if (!results.length || !results[0]) return results[0];
        const merged = { ...results[0] };
        if (merged.slots) {
          const slotMaps = results.map(r => { const map = {}; (r.slots || []).forEach(s => { map[s.time] = s; }); return map; });
          merged.slots = merged.slots.map(slot => {
            const allAvailable = slotMaps.every(m => m[slot.time]?.available);
            if (!allAvailable) {
              const conflictMap = slotMaps.find(m => m[slot.time] && !m[slot.time].available);
              return { ...slot, available: false, booking: conflictMap?.[slot.time]?.booking || slot.booking };
            }
            return slot;
          });
        }
        return merged;
      }
      return (await checkAvailability(selectedDate, serviceType, null, anyEmployeeMode, effectiveDuration)).data;
    },
    enabled: !!selectedDate && isOpen,
  });

  const isFullDayJob = effectiveDuration >= 1440;

  useEffect(() => { assignedEmployeesRef.current = assignedEmployees; }, [assignedEmployees]);

  const recheckAssignedEmployees = async (apptTime, duration) => {
    const current = assignedEmployeesRef.current;
    if (!apptTime || current.length === 0) return;
    const updated = await Promise.all(current.map(async (w) => {
      try { const res = await checkEmployeeAvailability(w.id, apptTime, duration || 60); return { ...w, availability: res.data }; }
      catch { return { ...w, availability: null }; }
    }));
    setAssignedEmployees(updated);
  };

  // Reset when modal opens
  useEffect(() => {
    if (isOpen && quote) {
      setSelectedDate(''); setAppointmentTime(''); setAnyEmployeeMode(true); setAssignedEmployees([]);
      setAddress(''); setNotes(quote.notes || '');
      setDurationMinutes(matchedService?.duration_minutes || 60);
      const n = new Date(); setCalMonth(n.getMonth()); setCalYear(n.getFullYear());
    }
  }, [isOpen, quote]);

  const handleDateSelect = (iso) => {
    setSelectedDate(iso);
    if (isFullDayJob) {
      const dateTime = `${iso}T${String(monthlyData?.business_hours?.start || 9).padStart(2, '0')}:00`;
      setAppointmentTime(dateTime);
      recheckAssignedEmployees(dateTime, effectiveDuration);
    } else {
      setAppointmentTime('');
    }
  };

  const handleTimeSlotClick = (slot) => {
    if (!slot.available) { addToast(`Slot booked${slot.booking?.client_name ? ` for ${slot.booking.client_name}` : ''}`, 'warning'); return; }
    const dateTime = `${selectedDate}T${slot.time}`;
    setAppointmentTime(dateTime);
    recheckAssignedEmployees(dateTime, effectiveDuration);
  };

  const addEmployeeToJob = async (employeeId) => {
    if (!employeeId) return;
    const id = parseInt(employeeId);
    if (assignedEmployees.some(w => w.id === id)) { addToast('Employee already assigned', 'warning'); return; }
    const employee = employees?.find(w => w.id === id);
    if (!employee) return;
    setAnyEmployeeMode(false);
    let avail = null;
    if (appointmentTime) {
      try { const res = await checkEmployeeAvailability(id, appointmentTime, effectiveDuration); avail = res.data; } catch { /* ignore */ }
    }
    setAssignedEmployees(prev => [...prev, { id: employee.id, name: employee.name, trade_specialty: employee.trade_specialty, availability: avail }]);
  };

  const removeEmployeeFromJob = (employeeId) => {
    setAssignedEmployees(prev => {
      const updated = prev.filter(w => w.id !== employeeId);
      if (updated.length === 0) setAnyEmployeeMode(true);
      return updated;
    });
  };

  const convertMut = useMutation({
    mutationFn: ({ id, data }) => convertQuoteToJob(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['quotes'] });
      queryClient.invalidateQueries({ queryKey: ['quote-pipeline'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['availability'] });
      queryClient.invalidateQueries({ queryKey: ['monthly-availability'] });
      addToast('Quote converted to job successfully', 'success');
      onClose();
      if (onConverted) onConverted();
    },
    onError: (e) => addToast(e.response?.data?.error || 'Failed to convert quote to job', 'error'),
  });

  const handleConvert = () => {
    if (!appointmentTime) { addToast('Please select a date and time', 'warning'); return; }
    const unavailableEmployee = assignedEmployees.find(w => w.availability && !w.availability.available);
    if (unavailableEmployee) { addToast(`${unavailableEmployee.name} is not available at this time`, 'error'); return; }
    const allEmployeeIds = assignedEmployees.map(w => w.id);
    const autoAssign = anyEmployeeMode && allEmployeeIds.length === 0;
    convertMut.mutate({
      id: quote.id,
      data: { appointment_time: appointmentTime, address, notes, employee_ids: allEmployeeIds, auto_assign_employee: autoAssign, duration_minutes: effectiveDuration }
    });
  };

  if (!quote) return null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Schedule Job from Quote" size="large">
      <div className="convert-job-form">
        {/* Quote Summary Banner */}
        <div className="convert-quote-summary">
          <div className="convert-quote-info">
            <h4>{quote.title || `Quote #${quote.quote_number}`}</h4>
            <div className="convert-quote-meta">
              {quote.client_name && <span><i className="fas fa-user"></i> {quote.client_name}</span>}
              <span><i className="fas fa-euro-sign"></i> {formatCurrency(quote.total)}</span>
              {quote.line_items?.length > 0 && <span><i className="fas fa-list"></i> {quote.line_items.length} item{quote.line_items.length !== 1 ? 's' : ''}</span>}
            </div>
          </div>
        </div>

        {/* Employee Assignment */}
        <div className="form-group">
          <label className="form-label">Assign Employees</label>
          {assignedEmployees.length > 0 && (
            <div className="assigned-employees-list">
              {assignedEmployees.map(w => (
                <div key={w.id} className={`assigned-employee-chip ${w.availability && !w.availability.available ? 'conflict' : ''}`}>
                  <i className="fas fa-hard-hat"></i>
                  <span className="assigned-employee-name">{w.name}</span>
                  {w.trade_specialty && <span className="assigned-employee-specialty">({w.trade_specialty})</span>}
                  {w.availability && !w.availability.available && <span className="assigned-employee-conflict" title={w.availability.message}><i className="fas fa-exclamation-triangle"></i></span>}
                  {w.availability && w.availability.available && <span className="assigned-employee-ok"><i className="fas fa-check-circle"></i></span>}
                  <button type="button" className="assigned-employee-remove" onClick={() => removeEmployeeFromJob(w.id)} title="Remove employee"><i className="fas fa-times"></i></button>
                </div>
              ))}
            </div>
          )}
          {assignedEmployees.length > 0 && (
            <div className="add-employee-row">
              <select className="form-input add-employee-select" value="" onChange={(e) => { if (e.target.value) addEmployeeToJob(e.target.value); }}>
                <option value="">+ Add another employee...</option>
                {(employees || []).filter(w => !assignedEmployees.some(aw => aw.id === w.id)).map(w => (
                  <option key={w.id} value={w.id}>{w.name} {w.trade_specialty && `(${w.trade_specialty})`}</option>
                ))}
              </select>
            </div>
          )}
          {assignedEmployees.length === 0 && (
            <div className="add-employee-row">
              <select className="form-input" value={anyEmployeeMode ? 'any' : ''} onChange={(e) => {
                const val = e.target.value;
                if (val === 'any') { setAnyEmployeeMode(true); setSelectedDate(''); setAppointmentTime(''); }
                else if (val) addEmployeeToJob(val);
              }}>
                <option value="any">Any available employee</option>
                {(employees || []).map(w => <option key={w.id} value={w.id}>{w.name} {w.trade_specialty && `(${w.trade_specialty})`}</option>)}
              </select>
            </div>
          )}
          {anyEmployeeMode && assignedEmployees.length === 0 && (
            <div className="employee-selected-info any-employee-info"><i className="fas fa-users"></i> Showing combined availability — slot is open if <strong>any</strong> employee is free</div>
          )}
          {assignedEmployees.length > 0 && <div className="employee-selected-info"><i className="fas fa-users"></i> <strong>{assignedEmployees.length}</strong> employee{assignedEmployees.length !== 1 ? 's' : ''} assigned</div>}
        </div>

        {/* Duration */}
        <div className="form-group">
          <label className="form-label">Duration</label>
          <select className="form-input" value={effectiveDuration} onChange={(e) => { setDurationMinutes(parseInt(e.target.value)); setSelectedDate(''); setAppointmentTime(''); }}>
            {Object.entries(DURATION_OPTIONS_GROUPED).map(([group, options]) => (
              <optgroup key={group} label={group}>
                {options.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
              </optgroup>
            ))}
          </select>
          {matchedService && <div className="convert-service-match"><i className="fas fa-link"></i> Matched to service: {matchedService.name} ({formatDuration(matchedService.duration_minutes)})</div>}
        </div>

        {/* Date & Time with Calendar */}
        <div className="form-group">
          <label className="form-label">Date & Time <span className="required">*</span></label>
          <MiniCalendar
            selectedDate={selectedDate} onSelectDate={handleDateSelect}
            monthData={monthlyData?.days} isLoading={isLoadingMonthly}
            calMonth={calMonth} calYear={calYear} onMonthChange={(m, y) => { setCalMonth(m); setCalYear(y); }}
          />

          {selectedDate && isFullDayJob && (
            <div className="fullday-status">
              {monthlyData?.days?.[selectedDate]?.status === 'full'
                ? <div className="fullday-booked"><i className="fas fa-times-circle"></i> This day is fully booked</div>
                : <div className="fullday-available"><i className="fas fa-check-circle"></i> Day selected: {new Date(selectedDate + 'T00:00').toLocaleDateString('en-IE', { weekday: 'long', day: 'numeric', month: 'long' })}</div>
              }
            </div>
          )}

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
                      className={`time-slot ${slot.available ? 'available' : 'booked'} ${appointmentTime === `${selectedDate}T${slot.time}` ? 'selected' : ''}`}
                      onClick={() => handleTimeSlotClick(slot)} disabled={!slot.available}
                      title={slot.available ? 'Available' : `Booked: ${slot.booking?.client_name || ''} — ${slot.booking?.service_type || ''}`}>
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

          {appointmentTime && (
            <div className="selected-time-badge">
              <i className="fas fa-calendar-check"></i>
              {new Date(appointmentTime).toLocaleString('en-IE', { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}
            </div>
          )}
        </div>

        {/* Address */}
        <div className="form-group">
          <label className="form-label">Job Address</label>
          <input type="text" className="form-input" value={address} onChange={(e) => setAddress(e.target.value)} placeholder="Job location address" />
        </div>

        {/* Notes */}
        <div className="form-group">
          <label className="form-label">Notes</label>
          <textarea className="form-textarea" value={notes} onChange={(e) => setNotes(e.target.value)} rows="2" placeholder="Additional notes for the job" />
        </div>

        {/* Actions */}
        <div className="form-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button type="button" className="btn btn-primary" onClick={handleConvert} disabled={!appointmentTime || convertMut.isPending}>
            {convertMut.isPending ? <><i className="fas fa-spinner fa-spin"></i> Converting...</> : <><i className="fas fa-calendar-plus"></i> Create Job</>}
          </button>
        </div>
      </div>
    </Modal>
  );
}

function QuotesPanel() {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [convertModal, setConvertModal] = useState(null);
  const [filterStatus, setFilterStatus] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [previewQuote, setPreviewQuote] = useState(null);
  const [isAddClientOpen, setIsAddClientOpen] = useState(false);
  const [customerSearch, setCustomerSearch] = useState('');
  const [customerPickerOpen, setCustomerPickerOpen] = useState(false);
  const customerPickerRef = useRef(null);
  const [formData, setFormData] = useState({
    client_id: '', title: '', description: '', notes: '',
    valid_until: '', line_items: [{ description: '', quantity: 1, amount: 0 }],
  });

  const { data: quotes = [], isLoading } = useQuery({
    queryKey: ['quotes'],
    queryFn: async () => (await getQuotes()).data,
  });

  const { data: clients = [] } = useQuery({
    queryKey: ['clients'],
    queryFn: async () => (await getClients()).data,
    staleTime: 60000,
  });

  const { data: taxSettings } = useQuery({
    queryKey: ['tax-settings'],
    queryFn: async () => (await getTaxSettings()).data,
    staleTime: 60000,
  });

  const taxRate = taxSettings?.tax_rate || 0;

  // Close customer picker on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (customerPickerRef.current && !customerPickerRef.current.contains(e.target)) setCustomerPickerOpen(false);
    };
    if (customerPickerOpen) { document.addEventListener('mousedown', handleClickOutside); return () => document.removeEventListener('mousedown', handleClickOutside); }
  }, [customerPickerOpen]);

  const filteredCustomers = useMemo(() => {
    if (!clients) return [];
    if (!customerSearch.trim()) return clients;
    const term = customerSearch.toLowerCase();
    return clients.filter(c => c.name?.toLowerCase().includes(term) || c.phone?.includes(customerSearch) || c.email?.toLowerCase().includes(term));
  }, [clients, customerSearch]);

  const selectedClient = useMemo(() => {
    if (!formData.client_id || !clients) return null;
    return clients.find(c => String(c.id) === String(formData.client_id));
  }, [formData.client_id, clients]);

  const createMut = useMutation({
    mutationFn: (data) => createQuote({ ...data, tax_rate: taxRate }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['quotes'] }); queryClient.invalidateQueries({ queryKey: ['quote-pipeline'] }); addToast('Quote created', 'success'); resetForm(); },
    onError: (e) => addToast(e.response?.data?.error || 'Failed to create quote', 'error'),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }) => updateQuote(id, { ...data, tax_rate: taxRate }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['quotes'] }); queryClient.invalidateQueries({ queryKey: ['quote-pipeline'] }); addToast('Quote updated', 'success'); resetForm(); },
    onError: (e) => addToast(e.response?.data?.error || 'Failed to update', 'error'),
  });

  const deleteMut = useMutation({
    mutationFn: deleteQuote,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['quotes'] }); queryClient.invalidateQueries({ queryKey: ['quote-pipeline'] }); addToast('Quote deleted', 'success'); setDeleteConfirm(null); },
  });

  const sendMut = useMutation({
    mutationFn: (id) => sendQuote(id),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['quotes'] });
      queryClient.invalidateQueries({ queryKey: ['quote-pipeline'] });
      addToast(`Quote sent via ${res.data?.sent_via || 'email'} to ${res.data?.sent_to || 'customer'}`, 'success');
    },
    onError: (e) => addToast(e.response?.data?.error || 'Failed to send quote', 'error'),
  });

  const resetForm = () => {
    setFormData({ client_id: '', title: '', description: '', notes: '', valid_until: '',
      line_items: [{ description: '', quantity: 1, amount: 0 }] });
    setShowForm(false); setEditingId(null); setCustomerPickerOpen(false); setCustomerSearch('');
  };

  const addLineItem = () => setFormData({ ...formData, line_items: [...formData.line_items, { description: '', quantity: 1, amount: 0 }] });
  const removeLineItem = (idx) => setFormData({ ...formData, line_items: formData.line_items.filter((_, i) => i !== idx) });
  const updateLineItem = (idx, field, value) => {
    const items = [...formData.line_items];
    items[idx] = { ...items[idx], [field]: value };
    setFormData({ ...formData, line_items: items });
  };

  const formSubtotal = formData.line_items.reduce((s, i) => s + (parseFloat(i.amount) || 0) * (parseFloat(i.quantity) || 1), 0);
  const formTax = Math.round(formSubtotal * taxRate) / 100;
  const formTotal = formSubtotal + formTax;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!formData.title.trim()) { addToast('Please enter a quote title', 'warning'); return; }
    if (formData.line_items.length === 0 || formSubtotal <= 0) {
      addToast('Add at least one line item with a value', 'warning'); return;
    }
    const emptyItems = formData.line_items.filter(i => !i.description?.trim());
    if (emptyItems.length > 0) { addToast('Please add a description for all line items', 'warning'); return; }
    if (editingId) updateMut.mutate({ id: editingId, data: formData });
    else createMut.mutate(formData);
  };

  const startEdit = (q) => {
    setFormData({
      client_id: q.client_id || '', title: q.title || '', description: q.description || '',
      notes: q.notes || '', valid_until: q.valid_until?.split('T')[0] || '',
      line_items: (q.line_items || []).length > 0 ? q.line_items : [{ description: '', quantity: 1, amount: 0 }],
    });
    setEditingId(q.id); setShowForm(true);
  };

  const duplicateQuote = (q) => {
    setFormData({
      client_id: q.client_id || '', title: `${q.title || 'Quote'} (Copy)`, description: q.description || '',
      notes: q.notes || '', valid_until: '',
      line_items: (q.line_items || []).length > 0 ? q.line_items.map(i => ({ ...i })) : [{ description: '', quantity: 1, amount: 0 }],
    });
    setEditingId(null); setShowForm(true);
    addToast('Quote duplicated — edit and save as new', 'info');
  };

  const stats = useMemo(() => {
    const draft = quotes.filter(q => q.status === 'draft').length;
    const sent = quotes.filter(q => q.status === 'sent').length;
    const accepted = quotes.filter(q => q.status === 'accepted').length;
    const totalValue = quotes.reduce((s, q) => s + (q.total || 0), 0);
    const acceptedValue = quotes.filter(q => q.status === 'accepted' || q.status === 'converted').reduce((s, q) => s + (q.total || 0), 0);
    return { draft, sent, accepted, totalValue, acceptedValue };
  }, [quotes]);

  const filtered = useMemo(() => {
    let list = filterStatus === 'all' ? quotes : quotes.filter(q => q.status === filterStatus);
    if (searchTerm.trim()) {
      const term = searchTerm.toLowerCase();
      list = list.filter(q =>
        (q.title || '').toLowerCase().includes(term) ||
        (q.client_name || '').toLowerCase().includes(term) ||
        (q.quote_number || '').toString().includes(term) ||
        (q.description || '').toLowerCase().includes(term)
      );
    }
    return list;
  }, [quotes, filterStatus, searchTerm]);

  // Check if a quote is expiring soon (within 7 days)
  const getExpiryStatus = (q) => {
    if (!q.valid_until || q.status === 'converted' || q.status === 'declined') return null;
    const expiry = new Date(q.valid_until);
    const now = new Date();
    const daysLeft = Math.ceil((expiry - now) / (1000 * 60 * 60 * 24));
    if (daysLeft < 0) return { label: 'Expired', color: '#ef4444', bg: '#fef2f2' };
    if (daysLeft <= 3) return { label: `${daysLeft}d left`, color: '#ef4444', bg: '#fef2f2' };
    if (daysLeft <= 7) return { label: `${daysLeft}d left`, color: '#f59e0b', bg: '#fffbeb' };
    return null;
  };

  if (isLoading) return <LoadingSpinner message="Loading quotes..." />;

  return (
    <div className="acct-panel">
      {/* Panel Header */}
      <div className="acct-panel-header">
        <h2 className="acct-panel-title"><i className="fas fa-file-invoice"></i> Quotes</h2>
        <button className="acct-btn-primary" onClick={() => { resetForm(); setShowForm(!showForm); }}>
          <i className={`fas ${showForm ? 'fa-times' : 'fa-plus'}`}></i>
          {showForm ? 'Cancel' : 'New Quote'}
        </button>
      </div>

      <div className="acct-stats-row">
        <div className="acct-stat-card">
          <div className="acct-stat-icon" style={{ background: 'rgba(99, 102, 241, 0.1)' }}>
            <i className="fas fa-file-invoice" style={{ color: '#6366f1' }}></i>
          </div>
          <div className="acct-stat-content">
            <div className="acct-stat-value">{formatCurrency(stats.totalValue)}</div>
            <div className="acct-stat-label">Total Quoted</div>
          </div>
        </div>
        <div className="acct-stat-card">
          <div className="acct-stat-icon" style={{ background: 'rgba(16, 185, 129, 0.1)' }}>
            <i className="fas fa-handshake" style={{ color: '#10b981' }}></i>
          </div>
          <div className="acct-stat-content">
            <div className="acct-stat-value">{formatCurrency(stats.acceptedValue)}</div>
            <div className="acct-stat-label">Won</div>
          </div>
        </div>
        <div className="acct-stat-card">
          <div className="acct-stat-icon" style={{ background: 'rgba(148, 163, 184, 0.1)' }}>
            <i className="fas fa-file" style={{ color: '#94a3b8' }}></i>
          </div>
          <div className="acct-stat-content">
            <div className="acct-stat-value">{stats.draft}</div>
            <div className="acct-stat-label">Drafts</div>
          </div>
        </div>
        <div className="acct-stat-card">
          <div className="acct-stat-icon" style={{ background: 'rgba(59, 130, 246, 0.1)' }}>
            <i className="fas fa-paper-plane" style={{ color: '#3b82f6' }}></i>
          </div>
          <div className="acct-stat-content">
            <div className="acct-stat-value">{stats.sent}</div>
            <div className="acct-stat-label">Awaiting Response</div>
          </div>
        </div>
      </div>

      <div className="acct-toolbar">
        <div className="dash-search" style={{ flex: 1 }}>
          <i className="fas fa-search"></i>
          <input type="text" placeholder="Search quotes..." value={searchTerm} onChange={e => setSearchTerm(e.target.value)} />
        </div>
        <div className="acct-toolbar-right">
          <div className="acct-filter-pills">
            {['all', 'draft', 'sent', 'accepted', 'declined', 'converted'].map(s => (
              <button key={s} className={`acct-pill ${filterStatus === s ? 'active' : ''}`}
                onClick={() => setFilterStatus(s)}>
                {s === 'all' ? 'All' : STATUS_CONFIG[s]?.label || s}
              </button>
            ))}
          </div>
        </div>
        {quotes.length > 0 && (
          <button className="acct-btn-secondary" title="Export CSV" style={{ padding: '0.4rem 0.6rem' }}
            onClick={() => {
              const rows = [['Quote #', 'Title', 'Customer', 'Status', 'Total', 'Created', 'Valid Until']];
              filtered.forEach(q => rows.push([q.quote_number, q.title || '', q.client_name || '', q.status, q.total, q.created_at, q.valid_until || '']));
              const csv = rows.map(r => r.map(c => `"${String(c || '').replace(/"/g, '""')}"`).join(',')).join('\n');
              const blob = new Blob([csv], { type: 'text/csv' });
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a'); a.href = url; a.download = `quotes-${new Date().toISOString().split('T')[0]}.csv`; a.click();
              URL.revokeObjectURL(url);
              addToast('Quotes exported', 'success');
            }}>
            <i className="fas fa-download"></i>
          </button>
        )}
      </div>

      {/* Quote Form */}
      {showForm && (
        <form className="acct-form" onSubmit={handleSubmit}>
          <div className="acct-form-grid">
            <div className="acct-field">
              <label>Customer</label>
              <div className="quote-customer-picker" ref={customerPickerRef}>
                {selectedClient ? (
                  <div className="quote-customer-selected">
                    <div className="quote-customer-avatar">{selectedClient.name?.charAt(0).toUpperCase() || '?'}</div>
                    <div className="quote-customer-details">
                      <span className="quote-customer-name">{selectedClient.name}</span>
                      <span className="quote-customer-contact">{selectedClient.phone || selectedClient.email || ''}</span>
                    </div>
                    <button type="button" className="quote-customer-clear" onClick={() => setFormData({ ...formData, client_id: '' })}><i className="fas fa-times"></i></button>
                  </div>
                ) : (
                  <button type="button" className="quote-customer-trigger" onClick={() => setCustomerPickerOpen(!customerPickerOpen)}>
                    <i className="fas fa-user"></i> Select customer...
                    <i className={`fas fa-chevron-${customerPickerOpen ? 'up' : 'down'}`} style={{ marginLeft: 'auto' }}></i>
                  </button>
                )}
                {customerPickerOpen && (
                  <div className="quote-customer-dropdown">
                    <div className="quote-customer-search">
                      <i className="fas fa-search"></i>
                      <input type="text" placeholder="Search by name, phone, email..." value={customerSearch}
                        onChange={e => setCustomerSearch(e.target.value)} autoFocus />
                    </div>
                    <div className="quote-customer-list">
                      {filteredCustomers.length === 0 ? (
                        <div className="quote-customer-empty">No customers found</div>
                      ) : filteredCustomers.slice(0, 10).map(c => (
                        <div key={c.id} className="quote-customer-item" onClick={() => {
                          setFormData({ ...formData, client_id: c.id });
                          setCustomerPickerOpen(false); setCustomerSearch('');
                        }}>
                          <div className="quote-customer-avatar">{c.name?.charAt(0).toUpperCase() || '?'}</div>
                          <div>
                            <div className="quote-customer-name">{c.name}</div>
                            <div className="quote-customer-contact">{c.phone || c.email || ''}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                    <div className="quote-customer-footer">
                      <button type="button" className="quote-customer-add" onClick={() => { setCustomerPickerOpen(false); setIsAddClientOpen(true); }}>
                        <i className="fas fa-plus"></i> Add New Customer
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
            <div className="acct-field">
              <label>Title *</label>
              <input type="text" placeholder="e.g. Bathroom Renovation Quote" required
                value={formData.title} onChange={e => setFormData({ ...formData, title: e.target.value })} />
            </div>
            <div className="acct-field">
              <label>Valid Until</label>
              <input type="date" value={formData.valid_until}
                min={new Date().toISOString().split('T')[0]}
                onChange={e => setFormData({ ...formData, valid_until: e.target.value })} />
            </div>
            <div className="acct-field acct-field-wide">
              <label>Description</label>
              <textarea rows={2} placeholder="Brief description of the work..."
                value={formData.description} onChange={e => setFormData({ ...formData, description: e.target.value })} />
            </div>
          </div>

          {/* Line Items */}
          <div className="acct-line-items">
            <div className="acct-line-header">
              <span className="acct-line-desc-h">Item</span>
              <span className="acct-line-qty-h">Qty</span>
              <span className="acct-line-price-h">Price</span>
              <span className="acct-line-total-h">Total</span>
              <span className="acct-line-action-h"></span>
            </div>
            {formData.line_items.map((item, idx) => (
              <div key={idx} className="acct-line-row">
                <input className="acct-line-desc" type="text" placeholder="Item description *"
                  value={item.description} onChange={e => updateLineItem(idx, 'description', e.target.value)} />
                <input className="acct-line-qty" type="number" min="1" step="1"
                  value={item.quantity} onChange={e => updateLineItem(idx, 'quantity', e.target.value)} />
                <div className="acct-line-price-wrap">
                  <span className="acct-input-prefix-sm">€</span>
                  <input className="acct-line-price" type="number" min="0" step="0.01"
                    value={item.amount} onChange={e => updateLineItem(idx, 'amount', e.target.value)} />
                </div>
                <span className="acct-line-total">{formatCurrency((parseFloat(item.amount) || 0) * (parseFloat(item.quantity) || 1))}</span>
                {formData.line_items.length > 1 && (
                  <button type="button" className="acct-btn-icon acct-btn-icon-danger" onClick={() => removeLineItem(idx)}>
                    <i className="fas fa-times"></i>
                  </button>
                )}
              </div>
            ))}
            <button type="button" className="acct-btn-link" onClick={addLineItem}>
              <i className="fas fa-plus"></i> Add Line Item
            </button>
          </div>

          {/* Totals */}
          <div className="acct-totals">
            <div className="acct-total-row"><span>Subtotal</span><span>{formatCurrency(formSubtotal)}</span></div>
            {taxRate > 0 && <div className="acct-total-row"><span>Tax ({taxRate}%)</span><span>{formatCurrency(formTax)}</span></div>}
            <div className="acct-total-row acct-total-final"><span>Total</span><span>{formatCurrency(formTotal)}</span></div>
          </div>

          <div className="acct-field acct-field-wide" style={{ marginTop: '0.75rem' }}>
            <label>Notes</label>
            <textarea rows={2} placeholder="Additional notes for the customer (payment terms, conditions, etc.)..."
              value={formData.notes} onChange={e => setFormData({ ...formData, notes: e.target.value })} />
          </div>

          <div className="acct-form-actions">
            <button type="button" className="acct-btn-secondary" onClick={resetForm}>Cancel</button>
            <button type="submit" className="acct-btn-primary" disabled={createMut.isPending || updateMut.isPending}>
              <i className={`fas ${createMut.isPending || updateMut.isPending ? 'fa-spinner fa-spin' : 'fa-check'}`}></i>
              {editingId ? 'Update Quote' : 'Create Quote'}
            </button>
          </div>
        </form>
      )}

      {/* Quotes List */}
      <div className="acct-list">
        {filtered.length === 0 ? (
          <div className="acct-empty">
            <i className="fas fa-file-invoice"></i>
            <p>{quotes.length === 0 ? 'No quotes yet. Create your first estimate above.' : 'No quotes match your search or filter.'}</p>
          </div>
        ) : (
          filtered.map(q => {
            const sc = STATUS_CONFIG[q.status] || STATUS_CONFIG.draft;
            const expiry = getExpiryStatus(q);
            return (
              <div key={q.id} className="acct-list-item">
                <div className="acct-list-icon" style={{ background: sc.bg, color: sc.color }}>
                  <i className={`fas ${sc.icon}`}></i>
                </div>
                <div className="acct-list-content">
                  <div className="acct-list-title">
                    {q.title || `Quote #${q.quote_number}`}
                    {q.quote_number && <span style={{ fontSize: '0.7rem', color: '#94a3b8', marginLeft: '0.5rem' }}>#{q.quote_number}</span>}
                  </div>
                  <div className="acct-list-meta">
                    {q.client_name && <span><i className="fas fa-user"></i> {q.client_name}</span>}
                    <span><i className="fas fa-calendar"></i> {formatDate(q.created_at)}</span>
                    {q.valid_until && <span><i className="fas fa-hourglass-half"></i> Valid until {formatDate(q.valid_until)}</span>}
                    <span className="acct-badge" style={{ background: sc.bg, color: sc.color }}>{sc.label}</span>
                    {expiry && <span className="acct-badge" style={{ background: expiry.bg, color: expiry.color }}><i className="fas fa-exclamation-triangle" style={{ marginRight: 3, fontSize: '0.55rem' }}></i>{expiry.label}</span>}
                    {q.line_items?.length > 0 && <span style={{ color: '#94a3b8' }}>{q.line_items.length} item{q.line_items.length !== 1 ? 's' : ''}</span>}
                  </div>
                </div>
                <div className="acct-list-amount" style={{ color: '#1e293b' }}>{formatCurrency(q.total)}</div>
                <div className="acct-list-actions quote-actions-enhanced">
                  {/* Preview - always visible */}
                  <button className="quote-action-btn quote-action-preview" onClick={() => setPreviewQuote(q)} title="Preview quote">
                    <i className="fas fa-eye"></i><span>Preview</span>
                  </button>

                  {/* Edit - not for converted */}
                  {q.status !== 'converted' && (
                    <button className="quote-action-btn quote-action-edit" onClick={() => startEdit(q)} title="Edit quote">
                      <i className="fas fa-pen"></i><span>Edit</span>
                    </button>
                  )}

                  {/* Duplicate */}
                  <button className="quote-action-btn quote-action-edit" onClick={() => duplicateQuote(q)} title="Duplicate this quote">
                    <i className="fas fa-copy"></i>
                  </button>

                  {/* Send via SMS */}
                  {(q.status === 'draft' || q.status === 'sent') && (
                    <button className="quote-action-btn quote-action-send" title="Send quote to customer (email first, SMS fallback)"
                      onClick={() => sendMut.mutate(q.id)} disabled={sendMut.isPending}>
                      <i className={`fas ${sendMut.isPending ? 'fa-spinner fa-spin' : 'fa-paper-plane'}`}></i><span>Send</span>
                    </button>
                  )}

                  {/* Copy Accept Link */}
                  {q.status !== 'converted' && q.status !== 'declined' && (
                    <button className="quote-action-btn quote-action-edit" title="Copy customer accept link"
                      onClick={() => generateQuoteAcceptLink(q.id).then(res => { navigator.clipboard?.writeText(res.data.link); addToast('Accept link copied!', 'success'); }).catch(() => addToast('Failed to generate link', 'error'))}>
                      <i className="fas fa-link"></i>
                    </button>
                  )}

                  {/* Follow Up */}
                  {(q.status === 'sent' || q.pipeline_stage === 'follow_up') && (
                    <button className="quote-action-btn quote-action-send" title="Send follow-up to customer"
                      onClick={() => sendQuoteFollowUp(q.id, '').then(res => { addToast(`Follow-up sent via ${res.data?.sent_via}`, 'success'); queryClient.invalidateQueries({ queryKey: ['quotes'] }); queryClient.invalidateQueries({ queryKey: ['quote-pipeline'] }); }).catch(e => addToast(e.response?.data?.error || 'Failed', 'error'))}>
                      <i className="fas fa-redo"></i><span>Follow Up</span>
                    </button>
                  )}

                  {/* Draft → Mark Sent */}
                  {q.status === 'draft' && (
                    <button className="quote-action-btn quote-action-send" title="Mark as sent to customer"
                      onClick={() => updateMut.mutate({ id: q.id, data: { status: 'sent' } })}>
                      <i className="fas fa-paper-plane"></i><span>Mark Sent</span>
                    </button>
                  )}

                  {/* Sent → Accept / Decline */}
                  {q.status === 'sent' && (
                    <>
                      <button className="quote-action-btn quote-action-accept" title="Customer accepted this quote"
                        onClick={() => updateMut.mutate({ id: q.id, data: { status: 'accepted' } })}>
                        <i className="fas fa-check"></i><span>Accept</span>
                      </button>
                      <button className="quote-action-btn quote-action-decline" title="Customer declined this quote"
                        onClick={() => updateMut.mutate({ id: q.id, data: { status: 'declined' } })}>
                        <i className="fas fa-times"></i><span>Decline</span>
                      </button>
                    </>
                  )}

                  {/* Accepted → Convert to Job */}
                  {q.status === 'accepted' && (
                    <button className="quote-action-btn quote-action-convert" title="Schedule this quote as a job"
                      onClick={() => setConvertModal(q)}>
                      <i className="fas fa-calendar-plus"></i><span>Schedule Job</span>
                    </button>
                  )}

                  {/* Delete */}
                  {deleteConfirm === q.id ? (
                    <div className="acct-confirm-inline">
                      <button className="acct-btn-danger-sm" onClick={() => deleteMut.mutate(q.id)}>Delete</button>
                      <button className="acct-btn-secondary-sm" onClick={() => setDeleteConfirm(null)}>Cancel</button>
                    </div>
                  ) : (
                    <button className="quote-action-btn quote-action-delete" onClick={() => setDeleteConfirm(q.id)} title="Delete quote">
                      <i className="fas fa-trash"></i>
                    </button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Convert to Job Modal */}
      <ConvertToJobModal
        isOpen={!!convertModal}
        onClose={() => setConvertModal(null)}
        quote={convertModal}
      />

      {/* Document Preview */}
      {previewQuote && (
        <DocumentPreview
          type="quote"
          docNumber={previewQuote.quote_number}
          date={previewQuote.created_at}
          dueDate={previewQuote.valid_until}
          customer={{ name: previewQuote.client_name, phone: previewQuote.client_phone, email: previewQuote.client_email }}
          lineItems={previewQuote.line_items || []}
          subtotal={previewQuote.subtotal}
          taxRate={previewQuote.tax_rate}
          taxAmount={previewQuote.tax_amount}
          total={previewQuote.total}
          notes={previewQuote.notes}
          status={STATUS_CONFIG[previewQuote.status]?.label}
          onClose={() => setPreviewQuote(null)}
        />
      )}

      {/* Add Client Modal */}
      <AddClientModal isOpen={isAddClientOpen} onClose={() => { setIsAddClientOpen(false); queryClient.invalidateQueries({ queryKey: ['clients'] }); }} />
    </div>
  );
}

export default QuotesPanel;
