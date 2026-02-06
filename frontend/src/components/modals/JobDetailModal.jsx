import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  getBooking, 
  getWorkers, 
  updateBooking,
  assignWorkerToJob,
  removeWorkerFromJob,
  getJobWorkers,
  sendInvoice
} from '../../services/api';
import Modal from './Modal';
import { useToast } from '../Toast';
import { formatDateTime, getStatusBadgeClass, formatCurrency, formatPhone } from '../../utils/helpers';
import './JobDetailModal.css';

function JobDetailModal({ isOpen, onClose, jobId }) {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [showAssignWorker, setShowAssignWorker] = useState(false);
  const [selectedWorkerId, setSelectedWorkerId] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [editFormData, setEditFormData] = useState({});

  const { data: job, isLoading } = useQuery({
    queryKey: ['booking', jobId],
    queryFn: async () => {
      const response = await getBooking(jobId);
      return response.data;
    },
    enabled: isOpen && !!jobId
  });

  const { data: assignedWorkers } = useQuery({
    queryKey: ['job-workers', jobId],
    queryFn: async () => {
      const response = await getJobWorkers(jobId);
      return response.data;
    },
    enabled: isOpen && !!jobId
  });

  const { data: allWorkers } = useQuery({
    queryKey: ['workers'],
    queryFn: async () => {
      const response = await getWorkers();
      return response.data;
    },
    enabled: showAssignWorker
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
      queryClient.invalidateQueries(['booking', jobId]);
      queryClient.invalidateQueries(['bookings']);
      setIsEditing(false);
      addToast('Job updated successfully!', 'success');
    },
    onError: (error) => {
      addToast('Failed to update job: ' + (error.response?.data?.error || error.message), 'error');
    }
  });

  const statusMutation = useMutation({
    mutationFn: ({ id, status }) => updateBooking(id, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries(['booking', jobId]);
      queryClient.invalidateQueries(['bookings']);
      addToast('Status updated successfully!', 'success');
    },
    onError: () => {
      addToast('Failed to update status', 'error');
    }
  });

  const assignMutation = useMutation({
    mutationFn: ({ jobId, workerId }) => assignWorkerToJob(jobId, { worker_id: workerId }),
    onSuccess: () => {
      queryClient.invalidateQueries(['job-workers', jobId]);
      queryClient.invalidateQueries(['bookings']);
      setShowAssignWorker(false);
      setSelectedWorkerId('');
      addToast('Worker assigned successfully!', 'success');
    },
    onError: () => {
      addToast('Failed to assign worker', 'error');
    }
  });

  const removeMutation = useMutation({
    mutationFn: ({ jobId, workerId }) => removeWorkerFromJob(jobId, { worker_id: workerId }),
    onSuccess: () => {
      queryClient.invalidateQueries(['job-workers', jobId]);
      queryClient.invalidateQueries(['bookings']);
      addToast('Worker removed', 'success');
    }
  });

  const invoiceMutation = useMutation({
    mutationFn: (jobId) => sendInvoice(jobId),
    onSuccess: (response) => {
      const data = response.data;
      addToast(`Invoice sent to ${data.sent_to}!`, 'success');
    },
    onError: (error) => {
      const message = error.response?.data?.error || 'Failed to send invoice';
      addToast(message, 'error');
    }
  });

  const handleSendInvoice = () => {
    if (!job.estimated_charge && !job.charge) {
      addToast('Cannot send invoice: No charge amount set', 'warning');
      return;
    }
    invoiceMutation.mutate(jobId);
  };

  const handleStatusChange = (newStatus) => {
    statusMutation.mutate({ id: jobId, status: newStatus });
  };

  const handleAssignWorker = () => {
    if (!selectedWorkerId) {
      addToast('Please select a worker', 'warning');
      return;
    }
    assignMutation.mutate({ jobId, workerId: selectedWorkerId });
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

  const availableWorkers = allWorkers?.filter(
    w => !assignedWorkers?.some(aw => aw.id === w.id)
  ) || [];

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
                {(job.estimated_charge || job.charge) && (
                  <button 
                    className="btn btn-invoice"
                    onClick={handleSendInvoice}
                    disabled={invoiceMutation.isPending}
                  >
                    <i className={`fas ${invoiceMutation.isPending ? 'fa-spinner fa-spin' : 'fa-file-invoice-dollar'}`}></i>
                    {invoiceMutation.isPending ? 'Sending...' : 'Send Invoice'}
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
                  <button className="btn btn-secondary">
                    Change Status <i className="fas fa-chevron-down"></i>
                  </button>
                  <div className="status-dropdown-menu">
                    <button onClick={() => handleStatusChange('pending')}>Pending</button>
                    <button onClick={() => handleStatusChange('scheduled')}>Scheduled</button>
                    <button onClick={() => handleStatusChange('in-progress')}>In Progress</button>
                    <button onClick={() => handleStatusChange('completed')}>Completed</button>
                    <button onClick={() => handleStatusChange('cancelled')}>Cancelled</button>
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
                  <div className="edit-row">
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
                </div>
              ) : (
                <>
                  <div className="info-row">
                    <div className="info-cell">
                      <span className="info-label">Date & Time</span>
                      <span className="info-value">{formatDateTime(job.appointment_time)}</span>
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
                  {(job.job_address || job.address) && (
                    <div className="info-row full">
                      <div className="info-cell">
                        <span className="info-label">Address</span>
                        <span className="info-value">{job.job_address || job.address} {job.eircode && `(${job.eircode})`}</span>
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
                    onChange={(e) => setSelectedWorkerId(e.target.value)}
                  >
                    <option value="">Select a worker...</option>
                    {availableWorkers.map(worker => (
                      <option key={worker.id} value={worker.id}>
                        {worker.name} {worker.specialty && `(${worker.specialty})`}
                      </option>
                    ))}
                  </select>
                  <div className="assign-buttons">
                    <button className="btn btn-sm btn-secondary" onClick={() => setShowAssignWorker(false)}>
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
                        {worker.specialty && <span className="worker-specialty">{worker.specialty}</span>}
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
    </Modal>
  );
}

export default JobDetailModal;
