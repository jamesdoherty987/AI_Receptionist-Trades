import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  getBooking, 
  getWorkers, 
  updateBooking,
  assignWorkerToJob,
  removeWorkerFromJob,
  getJobWorkers,
  getAvailableWorkersForJob,
  sendInvoice,
  getInvoiceConfig,
  getBusinessSettings
} from '../../services/api';
import Modal from './Modal';
import InvoiceConfirmModal from './InvoiceConfirmModal';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../Toast';
import { formatDateTime, getStatusBadgeClass, formatCurrency, formatPhone, getProxiedMediaUrl } from '../../utils/helpers';
import { DURATION_OPTIONS_GROUPED, formatDuration } from '../../utils/durationOptions';
import './JobDetailModal.css';

function JobDetailModal({ isOpen, onClose, jobId, showInvoiceButtons = true }) {
  const queryClient = useQueryClient();
  const { hasActiveSubscription } = useAuth();
  const isSubscriptionActive = hasActiveSubscription();
  const { addToast } = useToast();
  const [showAssignWorker, setShowAssignWorker] = useState(false);
  const [forceAssign, setForceAssign] = useState(false);
  const [selectedWorkerId, setSelectedWorkerId] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [editFormData, setEditFormData] = useState({});
  const [showInvoiceConfirm, setShowInvoiceConfirm] = useState(false);
  const [invoiceData, setInvoiceData] = useState(null);

  const { data: job, isLoading } = useQuery({
    queryKey: ['booking', jobId],
    queryFn: async () => {
      const response = await getBooking(jobId);
      return response.data;
    },
    enabled: isOpen && !!jobId,
    staleTime: 30 * 1000, // 30 seconds
    cacheTime: 5 * 60 * 1000 // 5 minutes
  });

  // Check invoice configuration
  const { data: invoiceConfig } = useQuery({
    queryKey: ['invoice-config'],
    queryFn: async () => {
      const response = await getInvoiceConfig();
      return response.data;
    },
    enabled: isOpen,
    staleTime: 60 * 1000, // 1 minute
    cacheTime: 5 * 60 * 1000
  });

  const { data: businessSettings } = useQuery({
    queryKey: ['business-settings'],
    queryFn: async () => {
      const response = await getBusinessSettings();
      return response.data;
    },
    enabled: isOpen,
    staleTime: 60 * 1000,
  });

  const { data: assignedWorkers } = useQuery({
    queryKey: ['job-workers', jobId],
    queryFn: async () => {
      const response = await getJobWorkers(jobId);
      return response.data;
    },
    enabled: isOpen && !!jobId,
    staleTime: 30 * 1000, // 30 seconds
    cacheTime: 5 * 60 * 1000 // 5 minutes
  });

  // Fetch workers with availability status for this job
  const { data: workersAvailability } = useQuery({
    queryKey: ['available-workers', jobId],
    queryFn: async () => {
      const response = await getAvailableWorkersForJob(jobId);
      return response.data;
    },
    enabled: showAssignWorker && !!jobId,
    staleTime: 30 * 1000,
    cacheTime: 5 * 60 * 1000
  });

  // Fallback to all workers if availability check not available
  const { data: allWorkers } = useQuery({
    queryKey: ['workers'],
    queryFn: async () => {
      const response = await getWorkers();
      return response.data;
    },
    enabled: showAssignWorker && !workersAvailability,
    staleTime: 60 * 1000, // 1 minute
    cacheTime: 10 * 60 * 1000 // 10 minutes
  });

  // Populate edit form when job data is loaded
  useEffect(() => {
    if (job) {
      const appointmentDate = job.appointment_time ? new Date(job.appointment_time) : null;
      const formattedDateTime = appointmentDate 
        ? appointmentDate.toISOString().slice(0, 16) 
        : '';
      
      setEditFormData({
        customer_name: job.customer_name || '',
        phone: job.phone || job.phone_number || '',
        email: job.email || '',
        appointment_time: formattedDateTime,
        service_type: job.service_type || job.service || '',
        property_type: job.property_type || '',
        job_address: job.job_address || job.address || '',
        eircode: job.eircode || '',
        estimated_charge: job.estimated_charge || job.charge || '',
        duration_minutes: job.duration_minutes || 60,
        notes: job.notes || ''
      });
    }
  }, [job]);

  // Reset edit mode when modal closes
  useEffect(() => {
    if (!isOpen) {
      setIsEditing(false);
    }
  }, [isOpen]);

  const editMutation = useMutation({
    mutationFn: (data) => updateBooking(jobId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['booking', jobId] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      setIsEditing(false);
      addToast('Job updated successfully!', 'success');
    },
    onError: (error) => {
      addToast('Failed to update job: ' + (error.response?.data?.error || error.message), 'error');
    }
  });

  const statusMutation = useMutation({
    mutationFn: ({ id, status }) => updateBooking(id, { status }),
    onMutate: async ({ status }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['booking', jobId] });
      
      // Snapshot previous value
      const previousJob = queryClient.getQueryData(['booking', jobId]);
      
      // Optimistically update to the new value
      queryClient.setQueryData(['booking', jobId], (old) => ({
        ...old,
        status: status
      }));
      
      // Return context with previous value
      return { previousJob };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['booking', jobId] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      addToast('Status updated successfully!', 'success');
    },
    onError: (error, variables, context) => {
      // Rollback to previous value on error
      if (context?.previousJob) {
        queryClient.setQueryData(['booking', jobId], context.previousJob);
      }
      addToast('Failed to update status', 'error');
    }
  });

  const assignMutation = useMutation({
    mutationFn: ({ jobId, workerId, force }) => assignWorkerToJob(jobId, { worker_id: workerId, force }),
    onMutate: async ({ workerId }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['job-workers', jobId] });
      
      // Snapshot previous value
      const previousWorkers = queryClient.getQueryData(['job-workers', jobId]);
      
      // Find the worker being assigned from availability data or all workers
      const availabilityData = queryClient.getQueryData(['available-workers', jobId]);
      const allWorkersData = queryClient.getQueryData(['workers']);
      const workerToAdd = availabilityData?.available?.find(w => w.id === workerId) 
        || availabilityData?.busy?.find(w => w.id === workerId)
        || allWorkersData?.find(w => w.id === workerId);
      
      // Optimistically add worker
      if (workerToAdd) {
        queryClient.setQueryData(['job-workers', jobId], (old = []) => [...old, workerToAdd]);
      }
      
      return { previousWorkers };
    },
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['job-workers', jobId] });
      queryClient.invalidateQueries({ queryKey: ['available-workers', jobId] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      setShowAssignWorker(false);
      setSelectedWorkerId('');
      setForceAssign(false);
      if (response.data?.warning) {
        addToast(response.data.warning, 'warning');
      } else {
        addToast('Worker assigned successfully!', 'success');
      }
    },
    onError: (error, variables, context) => {
      // Rollback on error
      if (context?.previousWorkers) {
        queryClient.setQueryData(['job-workers', jobId], context.previousWorkers);
      }
      
      // Check if it's a conflict error
      const errorData = error.response?.data;
      if (error.response?.status === 409 && errorData?.can_force) {
        // Show conflict warning with option to force
        const conflictMsg = errorData.conflicts?.map(c => 
          `${c.time} - ${c.service}`
        ).join(', ');
        addToast(`Worker has conflicts: ${conflictMsg}. Check "Force assign" to override.`, 'warning');
        setForceAssign(false);
      } else {
        addToast(errorData?.error || 'Failed to assign worker', 'error');
      }
    }
  });

  const removeMutation = useMutation({
    mutationFn: ({ jobId, workerId }) => removeWorkerFromJob(jobId, { worker_id: workerId }),
    onMutate: async ({ workerId }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['job-workers', jobId] });
      
      // Snapshot previous value
      const previousWorkers = queryClient.getQueryData(['job-workers', jobId]);
      
      // Optimistically remove worker
      queryClient.setQueryData(['job-workers', jobId], (old = []) => 
        old.filter(w => w.id !== workerId)
      );
      
      return { previousWorkers };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['job-workers', jobId] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      addToast('Worker removed', 'success');
    },
    onError: (error, variables, context) => {
      // Rollback on error
      if (context?.previousWorkers) {
        queryClient.setQueryData(['job-workers', jobId], context.previousWorkers);
      }
      addToast('Failed to remove worker', 'error');
    }
  });

  const invoiceMutation = useMutation({
    mutationFn: ({ jobId, invoiceData }) => sendInvoice(jobId, invoiceData),
    onSuccess: (response) => {
      const data = response.data;
      addToast(`Invoice sent to ${data.sent_to}!`, 'success');
      setShowInvoiceConfirm(false);
      setInvoiceData(null);
    },
    onError: (error) => {
      const message = error.response?.data?.error || 'Failed to send invoice';
      addToast(message, 'error');
    }
  });

  const handleSendInvoice = () => {
    if (!isSubscriptionActive) {
      addToast('You need an active subscription to send invoices', 'warning');
      return;
    }
    if (!job.estimated_charge && !job.charge) {
      addToast('Cannot send invoice: No charge amount set', 'warning');
      return;
    }
    
    // Check if invoice service is configured
    if (invoiceConfig && !invoiceConfig.can_send_invoice) {
      const warnings = invoiceConfig.warnings || [];
      if (warnings.length > 0) {
        addToast(warnings[0], 'error');
      } else {
        addToast('Invoice service is not configured. Please check your settings.', 'error');
      }
      return;
    }
    
    // Open confirmation modal instead of sending directly
    // Warn if bank details are missing
    if (!businessSettings?.bank_iban && !businessSettings?.bank_account_holder) {
      addToast('Your payment details are missing. Add them in Settings so your invoices include bank info.', 'warning');
    }
    setShowInvoiceConfirm(true);
  };

  const handleConfirmInvoice = (editedData) => {
    // Update the job with edited data first if needed, then send invoice
    setInvoiceData(editedData);
    invoiceMutation.mutate({ jobId, invoiceData: editedData });
  };

  const handleStatusChange = (newStatus) => {
    statusMutation.mutate({ id: jobId, status: newStatus });
  };

  const handleAssignWorker = () => {
    if (!selectedWorkerId) {
      addToast('Please select a worker', 'warning');
      return;
    }
    assignMutation.mutate({ jobId, workerId: selectedWorkerId, force: forceAssign });
  };

  const handleEditChange = (e) => {
    const { name, value } = e.target;
    setEditFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSaveEdit = () => {
    if (!editFormData.appointment_time || !editFormData.service_type) {
      addToast('Please fill in required fields', 'warning');
      return;
    }
    editMutation.mutate(editFormData);
  };

  const handleCancelEdit = () => {
    // Reset form data to original job values
    if (job) {
      const appointmentDate = job.appointment_time ? new Date(job.appointment_time) : null;
      const formattedDateTime = appointmentDate 
        ? appointmentDate.toISOString().slice(0, 16) 
        : '';
      
      setEditFormData({
        customer_name: job.customer_name || '',
        phone: job.phone || job.phone_number || '',
        email: job.email || '',
        appointment_time: formattedDateTime,
        service_type: job.service_type || job.service || '',
        property_type: job.property_type || '',
        job_address: job.job_address || job.address || '',
        eircode: job.eircode || '',
        estimated_charge: job.estimated_charge || job.charge || '',
        duration_minutes: job.duration_minutes || 60,
        notes: job.notes || ''
      });
    }
    setIsEditing(false);
  };

  if (isLoading) {
    return (
      <Modal isOpen={isOpen} onClose={onClose} title="Job Details" size="xlarge">
        <div className="modal-loading">
          <div className="loading-spinner"></div>
          <p>Loading job details...</p>
        </div>
      </Modal>
    );
  }

  if (!job) return null;

  // Get workers not already assigned, with availability info
  const getUnassignedWorkers = () => {
    const assignedIds = new Set(assignedWorkers?.map(w => w.id) || []);
    
    if (workersAvailability) {
      // Use availability data - combine available and busy, mark availability
      const available = (workersAvailability.available || [])
        .filter(w => !assignedIds.has(w.id))
        .map(w => ({ ...w, isAvailable: true }));
      const busy = (workersAvailability.busy || [])
        .filter(w => !assignedIds.has(w.id))
        .map(w => ({ ...w, isAvailable: false }));
      return [...available, ...busy];
    }
    
    // Fallback to all workers without availability info
    return (allWorkers || [])
      .filter(w => !assignedIds.has(w.id))
      .map(w => ({ ...w, isAvailable: true }));
  };
  
  const unassignedWorkers = getUnassignedWorkers();

  const getDirectionsUrl = () => {
    const address = job.job_address || job.address;
    const eircode = job.eircode;
    
    // Build the most specific destination possible
    let destination = '';
    if (address && eircode) {
      // Use both for best accuracy
      destination = `${address}, ${eircode}`;
    } else if (eircode) {
      // Eircode alone is very accurate in Ireland
      destination = eircode;
    } else if (address) {
      // Fall back to address only
      destination = address;
    }
    
    if (destination) {
      console.log('Get Directions - Destination:', destination);
      return `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(destination)}`;
    }
    
    console.warn('No address or eircode found for job:', job);
    return null;
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Job Details" size="xlarge">
      <div className="job-detail-modal">
        {/* Top Header Bar */}
        <div className="job-modal-header">
          <div className="job-modal-title">
            <h2>{job.customer_name}</h2>
            <span className={`badge badge-lg ${getStatusBadgeClass(job.status)}`}>
              {job.status}
            </span>
          </div>
          <div className="job-modal-actions">
            {!isEditing && (
              <>
                <button 
                  className="btn btn-edit"
                  onClick={() => setIsEditing(true)}
                >
                  <i className="fas fa-edit"></i> Edit
                </button>
                {(job.estimated_charge || job.charge) && showInvoiceButtons && (
                  <button 
                    className={`btn btn-invoice ${(invoiceConfig && !invoiceConfig.can_send_invoice) || !isSubscriptionActive ? 'btn-disabled' : ''}`}
                    onClick={handleSendInvoice}
                    disabled={invoiceMutation.isPending || (invoiceConfig && !invoiceConfig.can_send_invoice)}
                    title={!isSubscriptionActive 
                      ? 'Subscription required to send invoices'
                      : invoiceConfig && !invoiceConfig.can_send_invoice 
                        ? (invoiceConfig.warnings?.[0] || 'Invoice service not configured') 
                        : `Send invoice via ${invoiceConfig?.service_name || 'email'}`}
                  >
                    <i className={`fas ${invoiceMutation.isPending ? 'fa-spinner fa-spin' : !isSubscriptionActive ? 'fa-lock' : 'fa-file-invoice-dollar'}`}></i>
                    {invoiceMutation.isPending ? 'Sending...' : `Send Invoice${invoiceConfig?.delivery_method === 'sms' ? ' (SMS)' : ''}`}
                  </button>
                )}
                {getDirectionsUrl() && (
                  <a 
                    href={getDirectionsUrl()} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="btn btn-success"
                  >
                    <i className="fas fa-directions"></i> Get Directions
                  </a>
                )}
                <div className="status-dropdown">
                  <button className="btn btn-secondary" disabled={statusMutation.isPending}>
                    {statusMutation.isPending ? (
                      <>
                        <i className="fas fa-spinner fa-spin"></i> Updating...
                      </>
                    ) : (
                      <>
                        Change Status <i className="fas fa-chevron-down"></i>
                      </>
                    )}
                  </button>
                  <div className="status-dropdown-menu">
                    <button onClick={() => handleStatusChange('pending')} className={job.status === 'pending' ? 'active' : ''}>
                      <i className="fas fa-clock" style={{color: '#f59e0b'}}></i> Pending
                    </button>
                    <button onClick={() => handleStatusChange('scheduled')} className={job.status === 'scheduled' ? 'active' : ''}>
                      <i className="fas fa-calendar-check" style={{color: '#3b82f6'}}></i> Scheduled
                    </button>
                    <button onClick={() => handleStatusChange('in-progress')} className={job.status === 'in-progress' ? 'active' : ''}>
                      <i className="fas fa-wrench" style={{color: '#8b5cf6'}}></i> In Progress
                    </button>
                    <button onClick={() => handleStatusChange('completed')} className={job.status === 'completed' ? 'active' : ''}>
                      <i className="fas fa-check-circle" style={{color: '#22c55e'}}></i> Completed
                    </button>
                    <button onClick={() => handleStatusChange('paid')} className={job.status === 'paid' ? 'active' : ''}>
                      <i className="fas fa-money-check-alt" style={{color: '#10b981'}}></i> Paid
                    </button>
                    <button onClick={() => handleStatusChange('cancelled')} className={job.status === 'cancelled' ? 'active' : ''}>
                      <i className="fas fa-times-circle" style={{color: '#ef4444'}}></i> Cancelled
                    </button>
                  </div>
                </div>
              </>
            )}
            {isEditing && (
              <>
                <button 
                  className="btn btn-secondary"
                  onClick={handleCancelEdit}
                  disabled={editMutation.isPending}
                >
                  Cancel
                </button>
                <button 
                  className="btn btn-primary"
                  onClick={handleSaveEdit}
                  disabled={editMutation.isPending}
                >
                  <i className={`fas ${editMutation.isPending ? 'fa-spinner fa-spin' : 'fa-save'}`}></i>
                  {editMutation.isPending ? 'Saving...' : 'Save Changes'}
                </button>
              </>
            )}
          </div>
        </div>

        {/* Two Column Layout */}
        <div className="job-modal-grid">
          {/* Left Column - Job & Customer Info */}
          <div className="job-modal-column">
            {/* Job Details Card */}
            <div className="info-card">
              <h3><i className="fas fa-briefcase"></i> Job Details</h3>
              {isEditing ? (
                <div className="edit-form">
                  <div className="edit-row">
                    <div className="edit-field">
                      <label className="edit-label">Date & Time *</label>
                      <input
                        type="datetime-local"
                        name="appointment_time"
                        className="edit-input"
                        value={editFormData.appointment_time}
                        onChange={handleEditChange}
                        required
                      />
                    </div>
                    <div className="edit-field">
                      <label className="edit-label">Service Type *</label>
                      <input
                        type="text"
                        name="service_type"
                        className="edit-input"
                        value={editFormData.service_type}
                        onChange={handleEditChange}
                        placeholder="e.g., Plumbing repair"
                        required
                      />
                    </div>
                  </div>
                  <div className="edit-row">
                    <div className="edit-field">
                      <label className="edit-label">Property Type</label>
                      <input
                        type="text"
                        name="property_type"
                        className="edit-input"
                        value={editFormData.property_type}
                        onChange={handleEditChange}
                        placeholder="e.g., House, Apartment"
                      />
                    </div>
                    <div className="edit-field">
                      <label className="edit-label">Charge (€)</label>
                      <input
                        type="number"
                        name="estimated_charge"
                        className="edit-input"
                        value={editFormData.estimated_charge}
                        onChange={handleEditChange}
                        step="0.01"
                        min="0"
                        placeholder="0.00"
                      />
                    </div>
                  </div>
                  <div className="edit-row">
                    <div className="edit-field">
                      <label className="edit-label">Duration</label>
                      <select
                        name="duration_minutes"
                        className="edit-input"
                        value={editFormData.duration_minutes || 60}
                        onChange={handleEditChange}
                      >
                        {Object.entries(DURATION_OPTIONS_GROUPED).map(([group, options]) => (
                          <optgroup key={group} label={group}>
                            {options.map((opt) => (
                              <option key={opt.value} value={opt.value}>{opt.label}</option>
                            ))}
                          </optgroup>
                        ))}
                      </select>
                    </div>
                    <div className="edit-field">
                      <label className="edit-label">Eircode</label>
                      <input
                        type="text"
                        name="eircode"
                        className="edit-input"
                        value={editFormData.eircode}
                        onChange={handleEditChange}
                        placeholder="e.g., D01 X2Y3"
                      />
                    </div>
                  </div>
                  <div className="edit-row">
                    <div className="edit-field full-width">
                      <label className="edit-label">Job Address</label>
                      <input
                        type="text"
                        name="job_address"
                        className="edit-input"
                        value={editFormData.job_address}
                        onChange={handleEditChange}
                        placeholder="Job location address"
                      />
                    </div>
                  </div>
                </div>
              ) : (
                <>
                  <div className="info-row">
                    <div className="info-cell">
                      <span className="info-label">Date & Time</span>
                      <span className="info-value">
                        {formatDateTime(job.appointment_time)}
                        {job.duration_minutes && (
                          <span style={{ marginLeft: '8px', color: '#666', fontSize: '0.9em' }}>
                            ({formatDuration(job.duration_minutes)})
                          </span>
                        )}
                      </span>
                    </div>
                    <div className="info-cell">
                      <span className="info-label">Service</span>
                      <span className="info-value">{job.service_type || job.service || 'N/A'}</span>
                    </div>
                  </div>
                  <div className="info-row">
                    {job.property_type && (
                      <div className="info-cell">
                        <span className="info-label">Property</span>
                        <span className="info-value">{job.property_type}</span>
                      </div>
                    )}
                    {(job.estimated_charge || job.charge) && (
                      <div className="info-cell">
                        <span className="info-label">Charge</span>
                        <span className="info-value price">{formatCurrency(job.estimated_charge || job.charge)}</span>
                      </div>
                    )}
                  </div>
                  {(job.job_address || job.address || job.eircode) && (
                    <div className="info-row full">
                      <div className="info-cell">
                        <span className="info-label">Address</span>
                        <span className="info-value">
                          {[job.job_address || job.address, job.eircode && (job.job_address || job.address ? `(${job.eircode})` : job.eircode)].filter(Boolean).join(' ')}
                        </span>
                        {job.address_audio_url && (
                          <div className="address-audio-player" style={{ marginTop: '6px' }}>
                            <audio controls preload="metadata" src={getProxiedMediaUrl(job.address_audio_url)} style={{ height: '32px', width: '100%', maxWidth: '300px' }}>
                              Your browser does not support audio playback.
                            </audio>
                            <span style={{ fontSize: '0.8em', color: '#888', marginLeft: '4px' }}>Listen to address</span>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                  {job.payment_status && (
                    <div className="info-row">
                      <div className="info-cell">
                        <span className="info-label">Payment</span>
                        <span className={`info-value payment-badge ${job.payment_status}`}>
                          {job.payment_status === 'paid' && <><i className="fas fa-check-circle"></i> Paid</>}
                          {job.payment_status === 'invoiced' && <><i className="fas fa-file-invoice"></i> Invoiced</>}
                          {job.payment_status === 'pending' && <><i className="fas fa-clock"></i> Pending</>}
                          {!['paid', 'invoiced', 'pending'].includes(job.payment_status) && job.payment_status}
                        </span>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Customer Details Card */}
            <div className="info-card">
              <h3><i className="fas fa-user"></i> Customer</h3>
              {isEditing ? (
                <div className="edit-form">
                  <div className="edit-row">
                    <div className="edit-field">
                      <label className="edit-label">Name</label>
                      <input
                        type="text"
                        name="customer_name"
                        className="edit-input"
                        value={editFormData.customer_name}
                        onChange={handleEditChange}
                        placeholder="Customer name"
                      />
                    </div>
                    <div className="edit-field">
                      <label className="edit-label">Phone</label>
                      <input
                        type="tel"
                        name="phone"
                        className="edit-input"
                        value={editFormData.phone}
                        onChange={handleEditChange}
                        placeholder="Phone number"
                      />
                    </div>
                  </div>
                  <div className="edit-row">
                    <div className="edit-field full-width">
                      <label className="edit-label">Email</label>
                      <input
                        type="email"
                        name="email"
                        className="edit-input"
                        value={editFormData.email}
                        onChange={handleEditChange}
                        placeholder="Email address"
                      />
                    </div>
                  </div>
                </div>
              ) : (
                <>
                  <div className="info-row">
                    <div className="info-cell">
                      <span className="info-label">Name</span>
                      <span className="info-value">{job.customer_name || job.client_name}</span>
                    </div>
                    <div className="info-cell">
                      <span className="info-label">Phone</span>
                      <span className="info-value">
                        {(job.phone || job.phone_number) ? (
                          <a href={`tel:${job.phone || job.phone_number}`} className="link">
                            {formatPhone(job.phone || job.phone_number)}
                          </a>
                        ) : 'N/A'}
                      </span>
                    </div>
                  </div>
                  {job.email && (
                    <div className="info-row">
                      <div className="info-cell">
                        <span className="info-label">Email</span>
                        <span className="info-value">
                          <a href={`mailto:${job.email}`} className="link">{job.email}</a>
                        </span>
                      </div>
                    </div>
                  )}
                  {(job.customer_address || job.job_address || job.address) && (
                    <div className="info-row full">
                      <div className="info-cell">
                        <span className="info-label">Address</span>
                        <span className="info-value">
                          {job.customer_address || job.job_address || job.address}
                          {job.eircode && ` (${job.eircode})`}
                        </span>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Notes */}
            <div className="info-card">
              <h3><i className="fas fa-sticky-note"></i> Notes</h3>
              {isEditing ? (
                <div className="edit-form">
                  <textarea
                    name="notes"
                    className="edit-textarea"
                    value={editFormData.notes}
                    onChange={handleEditChange}
                    rows="4"
                    placeholder="Additional notes about the job..."
                  />
                </div>
              ) : (
                <p className="notes-text">{job.notes || 'No notes'}</p>
              )}
            </div>
          </div>

          {/* Right Column - Workers */}
          <div className="job-modal-column">
            <div className="info-card workers-card">
              <div className="card-header-row">
                <h3><i className="fas fa-hard-hat"></i> Assigned Workers</h3>
                <button 
                  className="btn btn-sm btn-primary"
                  onClick={() => setShowAssignWorker(!showAssignWorker)}
                >
                  <i className="fas fa-plus"></i> Assign
                </button>
              </div>

              {showAssignWorker && (
                <div className="assign-box">
                  <select 
                    className="form-select"
                    value={selectedWorkerId}
                    onChange={(e) => {
                      setSelectedWorkerId(e.target.value);
                      setForceAssign(false); // Reset force when changing worker
                    }}
                  >
                    <option value="">Select a worker...</option>
                    {unassignedWorkers.map(worker => (
                      <option 
                        key={worker.id} 
                        value={worker.id}
                        style={{ color: worker.isAvailable ? 'inherit' : '#dc3545' }}
                      >
                        {worker.name} {worker.trade_specialty && `(${worker.trade_specialty})`}
                        {!worker.isAvailable && ' ⚠️ Busy'}
                      </option>
                    ))}
                  </select>
                  {selectedWorkerId && !unassignedWorkers.find(w => w.id == selectedWorkerId)?.isAvailable && (
                    <label className="force-assign-label">
                      <input 
                        type="checkbox" 
                        checked={forceAssign} 
                        onChange={(e) => setForceAssign(e.target.checked)}
                      />
                      <span>Force assign (worker has conflicting jobs)</span>
                    </label>
                  )}
                  <div className="assign-buttons">
                    <button className="btn btn-sm btn-secondary" onClick={() => {
                      setShowAssignWorker(false);
                      setForceAssign(false);
                    }}>
                      Cancel
                    </button>
                    <button 
                      className="btn btn-sm btn-primary"
                      onClick={handleAssignWorker}
                      disabled={!selectedWorkerId || assignMutation.isPending}
                    >
                      {assignMutation.isPending ? 'Assigning...' : 'Assign'}
                    </button>
                  </div>
                </div>
              )}

              <div className="workers-list">
                {!assignedWorkers || assignedWorkers.length === 0 ? (
                  <div className="empty-workers">
                    <i className="fas fa-user-plus"></i>
                    <p>No workers assigned</p>
                  </div>
                ) : (
                  assignedWorkers.map(worker => (
                    <div key={worker.id} className="worker-item">
                      <div className="worker-item-avatar">
                        {worker.image_url ? (
                          <img src={worker.image_url} alt={worker.name} />
                        ) : (
                          <i className="fas fa-user"></i>
                        )}
                      </div>
                      <div className="worker-item-info">
                        <span className="worker-name">{worker.name}</span>
                        {worker.trade_specialty && <span className="worker-specialty">{worker.trade_specialty}</span>}
                      </div>
                      <button
                        className="btn-remove"
                        onClick={() => removeMutation.mutate({ jobId, workerId: worker.id })}
                        disabled={removeMutation.isPending}
                        title="Remove worker"
                      >
                        <i className="fas fa-times"></i>
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Invoice Confirmation Modal */}
      <InvoiceConfirmModal
        isOpen={showInvoiceConfirm}
        onClose={() => setShowInvoiceConfirm(false)}
        onConfirm={handleConfirmInvoice}
        job={job}
        invoiceConfig={invoiceConfig}
        isPending={invoiceMutation.isPending}
      />
    </Modal>
  );
}

export default JobDetailModal;
