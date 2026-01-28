import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  getBooking, 
  getWorkers, 
  updateBooking,
  assignWorkerToJob,
  removeWorkerFromJob,
  getJobWorkers
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
    let destination = eircode || address || '';
    if (destination) {
      return `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(destination)}`;
    }
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
          </div>
        </div>

        {/* Two Column Layout */}
        <div className="job-modal-grid">
          {/* Left Column - Job & Customer Info */}
          <div className="job-modal-column">
            {/* Job Details Card */}
            <div className="info-card">
              <h3><i className="fas fa-briefcase"></i> Job Details</h3>
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
            </div>

            {/* Customer Details Card */}
            <div className="info-card">
              <h3><i className="fas fa-user"></i> Customer</h3>
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
            </div>

            {/* Notes */}
            {job.notes && (
              <div className="info-card">
                <h3><i className="fas fa-sticky-note"></i> Notes</h3>
                <p className="notes-text">{job.notes}</p>
              </div>
            )}
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
