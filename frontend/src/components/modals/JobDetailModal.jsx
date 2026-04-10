import { useState, useEffect, useRef, useMemo } from 'react';
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
  getBusinessSettings,
  uploadJobPhoto,
  deleteJobPhoto,
  uploadJobMedia,
  getJobMaterials,
  addJobMaterial,
  deleteJobMaterial,
  getMaterials,
  getServicesMenu,
  getPackages,
  getJobTasks,
  createJobTask,
  updateJobTask,
  deleteJobTask,
  generatePOFromJob,
  getBookingReview
} from '../../services/api';
import Modal from './Modal';
import InvoiceConfirmModal from './InvoiceConfirmModal';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../Toast';
import { formatDateTime, getStatusBadgeClass, formatCurrency, formatPhone, getProxiedMediaUrl } from '../../utils/helpers';
import { DURATION_OPTIONS_GROUPED, formatDuration } from '../../utils/durationOptions';
import HelpTooltip from '../HelpTooltip';
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
  const [uploadingPhoto, setUploadingPhoto] = useState(false);
  const [lightboxPhoto, setLightboxPhoto] = useState(null);
  const photoInputRef = useRef(null);

  // Materials state
  const [showAddMaterial, setShowAddMaterial] = useState(false);
  const [materialSearch, setMaterialSearch] = useState('');
  const [customMaterial, setCustomMaterial] = useState({ name: '', unit_price: '', quantity: '1', unit: 'each' });
  const [showServiceDetail, setShowServiceDetail] = useState(false);

  // Sub-tasks state
  const [showAddTask, setShowAddTask] = useState(false);
  const [newTask, setNewTask] = useState({ title: '', description: '', estimated_cost: '' });

  const { data: job, isLoading } = useQuery({
    queryKey: ['booking', jobId],
    queryFn: async () => {
      const response = await getBooking(jobId);
      return response.data;
    },
    enabled: isOpen && !!jobId,
    staleTime: 30 * 1000,
    gcTime: 5 * 60 * 1000
  });

  const { data: invoiceConfig } = useQuery({
    queryKey: ['invoice-config'],
    queryFn: async () => {
      const response = await getInvoiceConfig();
      return response.data;
    },
    enabled: isOpen,
    staleTime: 60 * 1000,
    gcTime: 5 * 60 * 1000
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
    staleTime: 30 * 1000,
    gcTime: 5 * 60 * 1000
  });

  const { data: workersAvailability } = useQuery({
    queryKey: ['available-workers', jobId],
    queryFn: async () => {
      const response = await getAvailableWorkersForJob(jobId);
      return response.data;
    },
    enabled: showAssignWorker && !!jobId,
    staleTime: 30 * 1000,
    gcTime: 5 * 60 * 1000
  });

  const { data: allWorkers } = useQuery({
    queryKey: ['workers'],
    queryFn: async () => {
      const response = await getWorkers();
      return response.data;
    },
    enabled: showAssignWorker && !workersAvailability,
    staleTime: 60 * 1000,
    gcTime: 10 * 60 * 1000
  });

  const { data: jobMaterialsData } = useQuery({
    queryKey: ['job-materials', jobId],
    queryFn: async () => { const r = await getJobMaterials(jobId); return r.data; },
    enabled: isOpen && !!jobId,
    staleTime: 30 * 1000,
  });

  const { data: materialsCatalog } = useQuery({
    queryKey: ['materials'],
    queryFn: async () => { const r = await getMaterials(); return r.data; },
    enabled: isOpen && showAddMaterial,
    staleTime: 60 * 1000,
  });

  // Sub-tasks
  const { data: jobTasks = [] } = useQuery({
    queryKey: ['job-tasks', jobId],
    queryFn: async () => (await getJobTasks(jobId)).data,
    enabled: isOpen && !!jobId,
    staleTime: 30 * 1000,
  });

  // Review
  const { data: reviewData } = useQuery({
    queryKey: ['booking-review', jobId],
    queryFn: async () => (await getBookingReview(jobId)).data,
    enabled: isOpen && !!jobId,
    staleTime: 30 * 1000,
  });

  const createTaskMut = useMutation({
    mutationFn: (data) => createJobTask(jobId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['job-tasks', jobId] });
      setShowAddTask(false);
      setNewTask({ title: '', description: '', estimated_cost: '' });
      addToast('Task added', 'success');
    },
    onError: () => addToast('Failed to add task', 'error'),
  });

  const updateTaskMut = useMutation({
    mutationFn: ({ taskId, data }) => updateJobTask(jobId, taskId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['job-tasks', jobId] });
    },
  });

  const deleteTaskMut = useMutation({
    mutationFn: (taskId) => deleteJobTask(jobId, taskId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['job-tasks', jobId] });
      addToast('Task removed', 'success');
    },
  });

  const generatePOMut = useMutation({
    mutationFn: () => generatePOFromJob(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['purchase-orders'] });
      addToast('Purchase order created from job materials', 'success');
    },
    onError: (e) => addToast(e.response?.data?.error || 'Failed to generate PO', 'error'),
  });

  const { data: servicesMenu } = useQuery({
    queryKey: ['services-menu'],
    queryFn: async () => { const r = await getServicesMenu(); return r.data; },
    enabled: isOpen && !!job,
    staleTime: 60 * 1000,
  });

  const { data: packagesRaw } = useQuery({
    queryKey: ['packages'],
    queryFn: async () => { const r = await getPackages(); return r.data; },
    enabled: isOpen && !!job,
    staleTime: 60 * 1000,
  });

  const matchedServiceOrPackage = useMemo(() => {
    if (!job) return null;
    const serviceType = (job.service_type || job.service || '').toLowerCase().trim();
    if (!serviceType) return null;
    const allServices = servicesMenu?.services || [];
    const allPackages = packagesRaw?.packages || packagesRaw || [];
    const svc = allServices.find(s => s.name?.toLowerCase().trim() === serviceType);
    if (svc) return { type: 'service', data: svc };
    const pkg = allPackages.find(p => p.name?.toLowerCase().trim() === serviceType);
    if (pkg) return { type: 'package', data: pkg };
    return null;
  }, [job, servicesMenu, packagesRaw]);

  const addMaterialMut = useMutation({
    mutationFn: (data) => addJobMaterial(jobId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['job-materials', jobId] });
      setShowAddMaterial(false);
      setMaterialSearch('');
      setCustomMaterial({ name: '', unit_price: '', quantity: '1', unit: 'each' });
      addToast('Material added', 'success');
    },
    onError: () => addToast('Failed to add material', 'error'),
  });

  const removeMaterialMut = useMutation({
    mutationFn: (itemId) => deleteJobMaterial(jobId, itemId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['job-materials', jobId] });
      addToast('Material removed', 'success');
    },
    onError: () => addToast('Failed to remove', 'error'),
  });

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
        estimated_charge: (job.estimated_charge || job.charge) ? Math.round(parseFloat(job.estimated_charge || job.charge) * 100) / 100 : '',
        estimated_charge_max: job.estimated_charge_max ? Math.round(parseFloat(job.estimated_charge_max) * 100) / 100 : '',
        duration_minutes: job.duration_minutes || 60,
        notes: job.notes || ''
      });
    }
  }, [job]);

  useEffect(() => {
    if (!isOpen) {
      setIsEditing(false);
      setShowAddMaterial(false);
      setShowServiceDetail(false);
      setShowAddTask(false);
      setMaterialSearch('');
      setCustomMaterial({ name: '', unit_price: '', quantity: '1', unit: 'each' });
      setNewTask({ title: '', description: '', estimated_cost: '' });
    }
  }, [isOpen]);

  const editMutation = useMutation({
    mutationFn: (data) => updateBooking(jobId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['booking', jobId] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['bookings'] });
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
      await queryClient.cancelQueries({ queryKey: ['booking', jobId] });
      const previousJob = queryClient.getQueryData(['booking', jobId]);
      queryClient.setQueryData(['booking', jobId], (old) => ({ ...old, status }));
      return { previousJob };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['booking', jobId] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['bookings'] });
      addToast('Status updated successfully!', 'success');
    },
    onError: (error, variables, context) => {
      if (context?.previousJob) {
        queryClient.setQueryData(['booking', jobId], context.previousJob);
      }
      addToast('Failed to update status', 'error');
    }
  });

  const assignMutation = useMutation({
    mutationFn: ({ jobId, workerId, force }) => assignWorkerToJob(jobId, { worker_id: workerId, force }),
    onMutate: async ({ workerId }) => {
      await queryClient.cancelQueries({ queryKey: ['job-workers', jobId] });
      const previousWorkers = queryClient.getQueryData(['job-workers', jobId]);
      const availabilityData = queryClient.getQueryData(['available-workers', jobId]);
      const allWorkersData = queryClient.getQueryData(['workers']);
      const workerToAdd = availabilityData?.available?.find(w => w.id === workerId) 
        || availabilityData?.busy?.find(w => w.id === workerId)
        || allWorkersData?.find(w => w.id === workerId);
      if (workerToAdd) {
        queryClient.setQueryData(['job-workers', jobId], (old = []) => [...old, workerToAdd]);
      }
      return { previousWorkers };
    },
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['job-workers', jobId] });
      queryClient.invalidateQueries({ queryKey: ['available-workers', jobId] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['bookings'] });
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
      if (context?.previousWorkers) {
        queryClient.setQueryData(['job-workers', jobId], context.previousWorkers);
      }
      const errorData = error.response?.data;
      if (error.response?.status === 409 && errorData?.can_force) {
        const conflictMsg = errorData.conflicts?.map(c => `${c.time} - ${c.service}`).join(', ');
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
      await queryClient.cancelQueries({ queryKey: ['job-workers', jobId] });
      const previousWorkers = queryClient.getQueryData(['job-workers', jobId]);
      queryClient.setQueryData(['job-workers', jobId], (old = []) => old.filter(w => w.id !== workerId));
      return { previousWorkers };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['job-workers', jobId] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['bookings'] });
      addToast('Worker removed', 'success');
    },
    onError: (error, variables, context) => {
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
      addToast(error.response?.data?.error || 'Failed to send invoice', 'error');
    }
  });

  const photoUploadMutation = useMutation({
    mutationFn: (data) => {
      if (typeof data === 'string') return uploadJobPhoto(jobId, data);
      return uploadJobMedia(jobId, data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['booking', jobId] });
      addToast('Media uploaded', 'success');
      setUploadingPhoto(false);
    },
    onError: (error) => {
      addToast(error.response?.data?.error || 'Failed to upload', 'error');
      setUploadingPhoto(false);
    }
  });

  const photoDeleteMutation = useMutation({
    mutationFn: (photoUrl) => deleteJobPhoto(jobId, photoUrl),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['booking', jobId] });
      addToast('Photo removed', 'success');
    },
    onError: () => addToast('Failed to remove photo', 'error'),
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
    if (invoiceConfig && !invoiceConfig.can_send_invoice) {
      const warnings = invoiceConfig.warnings || [];
      addToast(warnings[0] || 'Invoice service is not configured. Please check your settings.', 'error');
      return;
    }
    if (!businessSettings?.bank_iban && !businessSettings?.bank_account_holder) {
      addToast('Your payment details are missing. Add them in Settings so your invoices include bank info.', 'warning');
    }
    setShowInvoiceConfirm(true);
  };

  const handleConfirmInvoice = (editedData) => {
    setInvoiceData(editedData);
    invoiceMutation.mutate({ jobId, invoiceData: editedData });
  };

  const isVideoUrl = (url) => /\.(mp4|mov|webm|avi)(\?|$)/i.test(url);

  const handlePhotoSelect = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const isVideo = file.type.startsWith('video/');
    const isImage = file.type.startsWith('image/');
    if (!isImage && !isVideo) { addToast('Please select an image or video file', 'warning'); return; }
    const maxSize = isVideo ? 50 * 1024 * 1024 : 10 * 1024 * 1024;
    if (file.size > maxSize) { addToast(`File must be under ${isVideo ? '50' : '10'}MB`, 'warning'); return; }
    setUploadingPhoto(true);
    if (isVideo) {
      photoUploadMutation.mutate(file);
    } else {
      const canvas = document.createElement('canvas');
      const img = new Image();
      const reader = new FileReader();
      reader.onerror = () => { addToast('Failed to read file', 'error'); setUploadingPhoto(false); };
      reader.onload = (ev) => {
        img.onerror = () => { addToast('Failed to load image', 'error'); setUploadingPhoto(false); };
        img.onload = () => {
          let w = img.width, h = img.height;
          const maxW = 1200;
          if (w > maxW) { h = (h * maxW) / w; w = maxW; }
          canvas.width = w; canvas.height = h;
          canvas.getContext('2d').drawImage(img, 0, 0, w, h);
          let quality = 0.8;
          let result = canvas.toDataURL('image/jpeg', quality);
          while (result.length > 400 * 1024 && quality > 0.2) { quality -= 0.1; result = canvas.toDataURL('image/jpeg', quality); }
          photoUploadMutation.mutate(result);
        };
        img.src = ev.target.result;
      };
      reader.readAsDataURL(file);
    }
    if (photoInputRef.current) photoInputRef.current.value = '';
  };

  const handleDeletePhoto = (photoUrl) => { if (window.confirm('Remove this photo?')) photoDeleteMutation.mutate(photoUrl); };

  const handleStatusChange = (newStatus) => {
    statusMutation.mutate({ id: jobId, status: newStatus });
    document.querySelectorAll('.status-dropdown-menu.show, .status-dropdown-backdrop.show').forEach(el => el.classList.remove('show'));
  };

  const handleAssignWorker = () => {
    if (!selectedWorkerId) { addToast('Please select a worker', 'warning'); return; }
    assignMutation.mutate({ jobId, workerId: selectedWorkerId, force: forceAssign });
  };

  const handleEditChange = (e) => {
    const { name, value } = e.target;
    setEditFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSaveEdit = () => {
    if (!editFormData.appointment_time || !editFormData.service_type) { addToast('Please fill in required fields', 'warning'); return; }
    editMutation.mutate(editFormData);
  };

  const handleCancelEdit = () => {
    if (job) {
      const appointmentDate = job.appointment_time ? new Date(job.appointment_time) : null;
      const formattedDateTime = appointmentDate ? appointmentDate.toISOString().slice(0, 16) : '';
      setEditFormData({
        customer_name: job.customer_name || '', phone: job.phone || job.phone_number || '',
        email: job.email || '', appointment_time: formattedDateTime,
        service_type: job.service_type || job.service || '', property_type: job.property_type || '',
        job_address: job.job_address || job.address || '', eircode: job.eircode || '',
        estimated_charge: (job.estimated_charge || job.charge) ? Math.round(parseFloat(job.estimated_charge || job.charge) * 100) / 100 : '',
        estimated_charge_max: job.estimated_charge_max ? Math.round(parseFloat(job.estimated_charge_max) * 100) / 100 : '',
        duration_minutes: job.duration_minutes || 60, notes: job.notes || ''
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

  const getUnassignedWorkers = () => {
    const assignedIds = new Set(assignedWorkers?.map(w => w.id) || []);
    if (workersAvailability) {
      const available = (workersAvailability.available || []).filter(w => !assignedIds.has(w.id)).map(w => ({ ...w, isAvailable: true }));
      const busy = (workersAvailability.busy || []).filter(w => !assignedIds.has(w.id)).map(w => ({ ...w, isAvailable: false }));
      return [...available, ...busy];
    }
    return (allWorkers || []).filter(w => !assignedIds.has(w.id)).map(w => ({ ...w, isAvailable: true }));
  };
  const unassignedWorkers = getUnassignedWorkers();

  const getDirectionsUrl = () => {
    const address = job.job_address || job.address;
    const eircode = job.eircode;
    let destination = '';
    if (address && eircode) destination = `${address}, ${eircode}`;
    else if (eircode) destination = eircode;
    else if (address) destination = address;
    if (destination) return `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(destination)}`;
    return null;
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={job.service_type || job.service || 'Job Details'} size="xlarge">
      <div className="job-detail-modal">
        {/* Header: Name + Status + Actions */}
        <div className="job-modal-header">
          <div className="job-modal-title">
            <h2>{job.customer_name}</h2>
            <span className={`badge badge-lg ${getStatusBadgeClass(job.status)}`}>{job.status}</span>
          </div>
          <div className="job-modal-actions">
            {!isEditing ? (
              <>
                <button className="btn btn-edit" onClick={() => setIsEditing(true)}>
                  <i className="fas fa-pen"></i> Edit
                </button>
                {!!(job.estimated_charge || job.charge) && showInvoiceButtons && (
                  <button
                    className={`btn btn-invoice ${(invoiceConfig && !invoiceConfig.can_send_invoice) || !isSubscriptionActive ? 'btn-disabled' : ''}`}
                    onClick={handleSendInvoice}
                    disabled={invoiceMutation.isPending || (invoiceConfig && !invoiceConfig.can_send_invoice)}
                    title={!isSubscriptionActive ? 'Subscription required' : invoiceConfig && !invoiceConfig.can_send_invoice ? (invoiceConfig.warnings?.[0] || 'Not configured') : `Send invoice via ${invoiceConfig?.service_name || 'email'}`}
                  >
                    <i className={`fas ${invoiceMutation.isPending ? 'fa-spinner fa-spin' : !isSubscriptionActive ? 'fa-lock' : 'fa-file-invoice-dollar'}`}></i>
                    {invoiceMutation.isPending ? 'Sending...' : 'Invoice'}
                  </button>
                )}
                {getDirectionsUrl() && (
                  <a href={getDirectionsUrl()} target="_blank" rel="noopener noreferrer" className="btn btn-success">
                    <i className="fas fa-directions"></i> Directions
                  </a>
                )}
                <div className="status-dropdown">
                  <button className="btn btn-secondary" disabled={statusMutation.isPending}
                    onClick={(e) => {
                      e.stopPropagation();
                      const menu = e.currentTarget.nextElementSibling;
                      const backdrop = menu?.nextElementSibling;
                      if (menu) menu.classList.toggle('show');
                      if (backdrop) backdrop.classList.toggle('show');
                    }}>
                    {statusMutation.isPending ? <><i className="fas fa-spinner fa-spin"></i> Updating...</> : <>Status <i className="fas fa-chevron-down"></i></>}
                  </button>
                  <div className="status-dropdown-menu">
                    {[
                      { key: 'pending', icon: 'fa-clock', color: '#f59e0b', label: 'Pending' },
                      { key: 'scheduled', icon: 'fa-calendar-check', color: '#3b82f6', label: 'Scheduled' },
                      { key: 'in-progress', icon: 'fa-wrench', color: '#8b5cf6', label: 'In Progress' },
                      { key: 'completed', icon: 'fa-check-circle', color: '#22c55e', label: 'Completed' },
                      { key: 'paid', icon: 'fa-money-check-alt', color: '#10b981', label: 'Paid' },
                      { key: 'cancelled', icon: 'fa-times-circle', color: '#ef4444', label: 'Cancelled' },
                    ].map(s => (
                      <button key={s.key} onClick={() => handleStatusChange(s.key)} className={job.status === s.key ? 'active' : ''}>
                        <i className={`fas ${s.icon}`} style={{ color: s.color }}></i> {s.label}
                      </button>
                    ))}
                  </div>
                  <div className="status-dropdown-backdrop" onClick={(e) => {
                    e.stopPropagation();
                    e.currentTarget.previousElementSibling?.classList.remove('show');
                    e.currentTarget.classList.remove('show');
                  }}></div>
                </div>
              </>
            ) : (
              <>
                <button className="btn btn-secondary" onClick={handleCancelEdit} disabled={editMutation.isPending}>Cancel</button>
                <button className="btn btn-primary" onClick={handleSaveEdit} disabled={editMutation.isPending}>
                  <i className={`fas ${editMutation.isPending ? 'fa-spinner fa-spin' : 'fa-check'}`}></i>
                  {editMutation.isPending ? 'Saving...' : 'Save'}
                </button>
              </>
            )}
          </div>
        </div>

        {/* Two Column Layout */}
        <div className="job-modal-grid">
          {/* Left Column */}
          <div className="job-modal-column">
            {/* Job Details */}
            <div className="info-card">
              <h3><i className="fas fa-briefcase"></i> Job Details</h3>
              {isEditing ? (
                <div className="edit-form">
                  <div className="edit-row">
                    <div className="edit-field">
                      <label className="edit-label">Date & Time *</label>
                      <input type="datetime-local" name="appointment_time" className="edit-input" value={editFormData.appointment_time} onChange={handleEditChange} required />
                    </div>
                    <div className="edit-field">
                      <label className="edit-label">Service *</label>
                      <input type="text" name="service_type" className="edit-input" value={editFormData.service_type} onChange={handleEditChange} placeholder="e.g., Plumbing repair" required />
                    </div>
                  </div>
                  <div className="edit-row">
                    <div className="edit-field">
                      <label className="edit-label">Property Type <HelpTooltip text="The type of property — e.g. house, apartment, office." /></label>
                      <input type="text" name="property_type" className="edit-input" value={editFormData.property_type} onChange={handleEditChange} placeholder="e.g., House" />
                    </div>
                    <div className="edit-field">
                      <label className="edit-label">Charge (€) <HelpTooltip text="The price for this job. Use both fields for a price range." /></label>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <input type="number" name="estimated_charge" className="edit-input" value={editFormData.estimated_charge} onChange={handleEditChange} step="0.01" min="0" placeholder="Min" style={{ flex: 1 }} />
                        <span style={{ fontSize: '0.75rem', color: '#9ca3af' }}>to</span>
                        <input type="number" name="estimated_charge_max" className="edit-input" value={editFormData.estimated_charge_max || ''} onChange={handleEditChange} step="0.01" min="0" placeholder="Max (opt)" style={{ flex: 1 }} />
                      </div>
                    </div>
                  </div>
                  <div className="edit-row">
                    <div className="edit-field">
                      <label className="edit-label">Duration</label>
                      <select name="duration_minutes" className="edit-input" value={editFormData.duration_minutes || 60} onChange={handleEditChange}>
                        {Object.entries(DURATION_OPTIONS_GROUPED).map(([group, options]) => (
                          <optgroup key={group} label={group}>
                            {options.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                          </optgroup>
                        ))}
                      </select>
                    </div>
                    <div className="edit-field">
                      <label className="edit-label">Eircode <HelpTooltip text="Irish postal code for the job location." /></label>
                      <input type="text" name="eircode" className="edit-input" value={editFormData.eircode} onChange={handleEditChange} placeholder="e.g., D01 X2Y3" />
                    </div>
                  </div>
                  <div className="edit-row">
                    <div className="edit-field full-width">
                      <label className="edit-label">Job Address</label>
                      <input type="text" name="job_address" className="edit-input" value={editFormData.job_address} onChange={handleEditChange} placeholder="Job location address" />
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
                        {job.duration_minutes && <span style={{ marginLeft: 6, color: '#9ca3af', fontSize: '0.85em' }}>({formatDuration(job.duration_minutes)})</span>}
                      </span>
                    </div>
                    <div className="info-cell">
                      <span className="info-label">Service</span>
                      {matchedServiceOrPackage ? (
                        <button
                          className={`jdm-service-link jdm-service-link-${matchedServiceOrPackage.type}`}
                          onClick={() => setShowServiceDetail(!showServiceDetail)}
                        >
                          <i className={`fas ${matchedServiceOrPackage.type === 'package' ? 'fa-box' : 'fa-wrench'}`}></i>
                          {job.service_type || job.service}
                          <i className={`fas fa-chevron-${showServiceDetail ? 'up' : 'down'} jdm-chevron`}></i>
                        </button>
                      ) : (
                        <span className="info-value">{job.service_type || job.service || 'N/A'}</span>
                      )}
                    </div>
                  </div>
                  {showServiceDetail && matchedServiceOrPackage && (
                    <div className="jdm-service-detail">
                      {matchedServiceOrPackage.data.image_url && (
                        <img src={matchedServiceOrPackage.data.image_url} alt={matchedServiceOrPackage.data.name} className="jdm-service-detail-img" />
                      )}
                      <div className="jdm-service-detail-grid">
                        {matchedServiceOrPackage.type === 'service' ? (
                          <>
                            {matchedServiceOrPackage.data.description && (
                              <p className="jdm-sd-desc">{matchedServiceOrPackage.data.description}</p>
                            )}
                            {matchedServiceOrPackage.data.price > 0 && (
                              <div className="jdm-sd-item">
                                <span className="jdm-sd-label">Price</span>
                                <span className="jdm-sd-value">
                                  €{parseFloat(matchedServiceOrPackage.data.price).toFixed(2)}
                                  {matchedServiceOrPackage.data.price_max && parseFloat(matchedServiceOrPackage.data.price_max) > parseFloat(matchedServiceOrPackage.data.price) && ` – €${parseFloat(matchedServiceOrPackage.data.price_max).toFixed(2)}`}
                                </span>
                              </div>
                            )}
                            {matchedServiceOrPackage.data.duration_minutes > 0 && (
                              <div className="jdm-sd-item">
                                <span className="jdm-sd-label">Duration</span>
                                <span className="jdm-sd-value">{formatDuration(matchedServiceOrPackage.data.duration_minutes)}</span>
                              </div>
                            )}
                            {matchedServiceOrPackage.data.workers_required > 1 && (
                              <div className="jdm-sd-item">
                                <span className="jdm-sd-label">Workers needed</span>
                                <span className="jdm-sd-value">{matchedServiceOrPackage.data.workers_required}</span>
                              </div>
                            )}
                            {matchedServiceOrPackage.data.requires_callout && (
                              <div className="jdm-sd-badge"><i className="fas fa-phone-alt"></i> Requires callout</div>
                            )}
                            {matchedServiceOrPackage.data.requires_quote && (
                              <div className="jdm-sd-badge"><i className="fas fa-file-invoice"></i> Requires quote</div>
                            )}
                          </>
                        ) : (
                          <>
                            {matchedServiceOrPackage.data.description && (
                              <p className="jdm-sd-desc">{matchedServiceOrPackage.data.description}</p>
                            )}
                            {matchedServiceOrPackage.data.services?.length > 0 && (
                              <div className="jdm-sd-services">
                                <span className="jdm-sd-label">Services</span>
                                <div className="jdm-sd-service-flow">
                                  {[...matchedServiceOrPackage.data.services]
                                    .sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0))
                                    .map((s, i) => (
                                      <span key={s.id || i} className="jdm-sd-step">
                                        {i > 0 && <i className="fas fa-arrow-right jdm-sd-arrow"></i>}
                                        {s.name}
                                      </span>
                                    ))}
                                </div>
                              </div>
                            )}
                            {(matchedServiceOrPackage.data.total_price > 0 || matchedServiceOrPackage.data.price_override > 0) && (
                              <div className="jdm-sd-item">
                                <span className="jdm-sd-label">Package price</span>
                                <span className="jdm-sd-value">€{parseFloat(matchedServiceOrPackage.data.price_override || matchedServiceOrPackage.data.total_price).toFixed(2)}</span>
                              </div>
                            )}
                            {(matchedServiceOrPackage.data.total_duration_minutes > 0 || matchedServiceOrPackage.data.duration_override > 0) && (
                              <div className="jdm-sd-item">
                                <span className="jdm-sd-label">Total duration</span>
                                <span className="jdm-sd-value">{formatDuration(matchedServiceOrPackage.data.duration_override || matchedServiceOrPackage.data.total_duration_minutes)}</span>
                              </div>
                            )}
                            {matchedServiceOrPackage.data.use_when_uncertain && (
                              <div className="jdm-sd-badge"><i className="fas fa-search"></i> Requires investigation</div>
                            )}
                          </>
                        )}
                      </div>
                    </div>
                  )}
                  <div className="info-row">
                    {job.property_type && (
                      <div className="info-cell">
                        <span className="info-label">Property</span>
                        <span className="info-value">{job.property_type}</span>
                      </div>
                    )}
                    {!!(job.estimated_charge || job.charge) && (
                      <div className="info-cell">
                        <span className="info-label">Charge</span>
                        <span className="info-value price">
                          {job.estimated_charge_max && parseFloat(job.estimated_charge_max) > parseFloat(job.estimated_charge || job.charge)
                            ? `${formatCurrency(job.estimated_charge || job.charge)} – ${formatCurrency(job.estimated_charge_max)}`
                            : formatCurrency(job.estimated_charge || job.charge)}
                        </span>
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
                          <div style={{ marginTop: 4 }}>
                            <audio controls preload="metadata" src={getProxiedMediaUrl(job.address_audio_url)} style={{ height: 28, width: '100%', maxWidth: 280 }} />
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
                  {(job.job_started_at || job.actual_duration_minutes) && (
                    <div className="info-row">
                      {job.job_started_at && (
                        <div className="info-cell">
                          <span className="info-label">Started</span>
                          <span className="info-value">{new Date(job.job_started_at).toLocaleString('en-IE', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
                        </div>
                      )}
                      {job.job_completed_at && (
                        <div className="info-cell">
                          <span className="info-label">Finished</span>
                          <span className="info-value">{new Date(job.job_completed_at).toLocaleString('en-IE', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
                        </div>
                      )}
                      {job.actual_duration_minutes && (
                        <div className="info-cell">
                          <span className="info-label">Actual Time</span>
                          <span className="info-value">{job.actual_duration_minutes >= 60 ? `${Math.floor(job.actual_duration_minutes / 60)}h ${job.actual_duration_minutes % 60}m` : `${job.actual_duration_minutes}m`}</span>
                        </div>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Profit Summary */}
            {jobMaterialsData?.materials?.length > 0 && !!(job.estimated_charge || job.charge) && (() => {
              const charge = parseFloat(job.estimated_charge || job.charge || 0);
              const matCost = parseFloat(jobMaterialsData?.total_cost || 0);
              const profit = charge - matCost;
              const margin = charge > 0 ? (profit / charge * 100) : 0;
              return (
                <div className={`info-card profit-card ${profit >= 0 ? 'positive' : 'negative'}`}>
                  <h3><i className="fas fa-chart-line"></i> Job Profit</h3>
                  <div className="info-row">
                    <div className="info-cell">
                      <span className="info-label">Charged</span>
                      <span className="info-value">{formatCurrency(charge)}</span>
                    </div>
                    <div className="info-cell">
                      <span className="info-label">Materials</span>
                      <span className="info-value" style={{ color: '#ef4444' }}>-{formatCurrency(matCost)}</span>
                    </div>
                    <div className="info-cell">
                      <span className="info-label">Profit</span>
                      <span className="info-value" style={{ color: profit >= 0 ? '#16a34a' : '#ef4444', fontWeight: 700, fontSize: '1rem' }}>
                        {formatCurrency(profit)}
                        <span style={{ fontSize: '0.75rem', fontWeight: 500, marginLeft: 4 }}>({margin.toFixed(0)}%)</span>
                      </span>
                    </div>
                  </div>
                </div>
              );
            })()}

            {/* Customer */}
            <div className="info-card">
              <h3><i className="fas fa-user"></i> Customer</h3>
              {isEditing ? (
                <div className="edit-form">
                  <div className="edit-row">
                    <div className="edit-field">
                      <label className="edit-label">Name</label>
                      <input type="text" name="customer_name" className="edit-input" value={editFormData.customer_name} onChange={handleEditChange} placeholder="Customer name" />
                    </div>
                    <div className="edit-field">
                      <label className="edit-label">Phone</label>
                      <input type="tel" name="phone" className="edit-input" value={editFormData.phone} onChange={handleEditChange} placeholder="Phone number" />
                    </div>
                  </div>
                  <div className="edit-row">
                    <div className="edit-field full-width">
                      <label className="edit-label">Email</label>
                      <input type="email" name="email" className="edit-input" value={editFormData.email} onChange={handleEditChange} placeholder="Email address" />
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
                          <a href={`tel:${job.phone || job.phone_number}`} className="link">{formatPhone(job.phone || job.phone_number)}</a>
                        ) : 'N/A'}
                      </span>
                    </div>
                  </div>
                  {job.email && (
                    <div className="info-row">
                      <div className="info-cell">
                        <span className="info-label">Email</span>
                        <span className="info-value"><a href={`mailto:${job.email}`} className="link">{job.email}</a></span>
                      </div>
                    </div>
                  )}
                  {(job.customer_address || job.job_address || job.address) && (
                    <div className="info-row full">
                      <div className="info-cell">
                        <span className="info-label">Address</span>
                        <span className="info-value">{job.customer_address || job.job_address || job.address}{job.eircode && ` (${job.eircode})`}</span>
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
                <textarea name="notes" className="edit-textarea" value={editFormData.notes} onChange={handleEditChange} rows="3" placeholder="Additional notes..." />
              ) : (
                <p className="notes-text">{job.notes || 'No notes'}</p>
              )}
            </div>
          </div>

          {/* Right Column */}
          <div className="job-modal-column">
            {/* Workers */}
            <div className="info-card workers-card">
              <div className="card-header-row">
                <h3><i className="fas fa-hard-hat"></i> Workers</h3>
                <button className="btn btn-sm btn-primary" onClick={() => setShowAssignWorker(!showAssignWorker)}>
                  <i className="fas fa-plus"></i> Assign
                </button>
              </div>
              {showAssignWorker && (
                <div className="assign-box">
                  <select className="form-select" value={selectedWorkerId} onChange={(e) => { setSelectedWorkerId(e.target.value); setForceAssign(false); }}>
                    <option value="">Select a worker...</option>
                    {unassignedWorkers.map(worker => (
                      <option key={worker.id} value={worker.id} style={{ color: worker.isAvailable ? 'inherit' : '#dc3545' }}>
                        {worker.name} {worker.trade_specialty && `(${worker.trade_specialty})`}{!worker.isAvailable && ' ⚠️ Busy'}
                      </option>
                    ))}
                  </select>
                  {selectedWorkerId && !unassignedWorkers.find(w => w.id == selectedWorkerId)?.isAvailable && (
                    <label className="force-assign-label">
                      <input type="checkbox" checked={forceAssign} onChange={(e) => setForceAssign(e.target.checked)} />
                      <span>Force assign (worker has conflicting jobs)</span>
                    </label>
                  )}
                  <div className="assign-buttons">
                    <button className="btn btn-sm btn-secondary" onClick={() => { setShowAssignWorker(false); setForceAssign(false); }}>Cancel</button>
                    <button className="btn btn-sm btn-primary" onClick={handleAssignWorker} disabled={!selectedWorkerId || assignMutation.isPending}>
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
                        {worker.image_url ? <img src={worker.image_url} alt={worker.name} /> : <i className="fas fa-user"></i>}
                      </div>
                      <div className="worker-item-info">
                        <span className="worker-name">{worker.name}</span>
                        {worker.trade_specialty && <span className="worker-specialty">{worker.trade_specialty}</span>}
                      </div>
                      <button className="btn-remove" onClick={() => removeMutation.mutate({ jobId, workerId: worker.id })} disabled={removeMutation.isPending} title="Remove worker">
                        <i className="fas fa-times"></i>
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Materials */}
            <div className="info-card">
              <div className="card-header-row">
                <h3><i className="fas fa-cubes"></i> Materials</h3>
                <button className="btn btn-sm btn-primary" onClick={() => setShowAddMaterial(!showAddMaterial)}>
                  <i className="fas fa-plus"></i> Add
                </button>
              </div>
              {showAddMaterial && (
                <div className="assign-box" style={{ marginBottom: '0.5rem' }}>
                  <input type="text" className="form-select" placeholder="Search materials catalog..." value={materialSearch} onChange={e => setMaterialSearch(e.target.value)} autoFocus />
                  {materialSearch && materialsCatalog?.materials?.length > 0 && (
                    <div className="jm-catalog-results">
                      {materialsCatalog.materials
                        .filter(m => m.name.toLowerCase().includes(materialSearch.toLowerCase()))
                        .slice(0, 6)
                        .map(m => (
                          <button key={m.id} className="jm-catalog-item" onClick={() => {
                            addMaterialMut.mutate({ material_id: m.id, name: m.name, unit_price: m.unit_price, unit: m.unit || 'each', quantity: 1, added_by: 'owner' });
                          }}>
                            <span className="jm-cat-name">{m.name}</span>
                            <span className="jm-cat-price">€{parseFloat(m.unit_price).toFixed(2)}/{m.unit || 'each'}</span>
                          </button>
                        ))}
                    </div>
                  )}
                  <div className="jm-custom-label">Or add custom:</div>
                  <div className="jm-custom-row">
                    <input type="text" placeholder="Name" value={customMaterial.name} onChange={e => setCustomMaterial({...customMaterial, name: e.target.value})} className="form-select" style={{ flex: 2 }} />
                    <input type="number" placeholder="€" value={customMaterial.unit_price} min="0" step="0.01" onChange={e => setCustomMaterial({...customMaterial, unit_price: e.target.value})} className="form-select" style={{ flex: 1 }} />
                    <input type="number" placeholder="Qty" value={customMaterial.quantity} min="0.01" step="1" onChange={e => setCustomMaterial({...customMaterial, quantity: e.target.value})} className="form-select" style={{ flex: 0.7 }} />
                  </div>
                  <div className="assign-buttons">
                    <button className="btn btn-sm btn-secondary" onClick={() => setShowAddMaterial(false)}>Cancel</button>
                    <button className="btn btn-sm btn-primary" disabled={!customMaterial.name.trim() || addMaterialMut.isPending}
                      onClick={() => addMaterialMut.mutate({ name: customMaterial.name, unit_price: parseFloat(customMaterial.unit_price) || 0, quantity: parseFloat(customMaterial.quantity) || 1, unit: customMaterial.unit, added_by: 'owner' })}>
                      {addMaterialMut.isPending ? 'Adding...' : 'Add'}
                    </button>
                  </div>
                </div>
              )}
              {jobMaterialsData?.materials?.length > 0 ? (
                <div className="jm-list">
                  {jobMaterialsData.materials.map(item => (
                    <div key={item.id} className="jm-item">
                      <div className="jm-item-info">
                        <span className="jm-item-name">{item.name}</span>
                        <span className="jm-item-detail">{item.quantity} × €{parseFloat(item.unit_price).toFixed(2)}{item.added_by && <span className="jm-added-by"> · {item.added_by}</span>}</span>
                      </div>
                      <span className="jm-item-total">€{parseFloat(item.total_cost).toFixed(2)}</span>
                      <button className="btn-remove" onClick={() => removeMaterialMut.mutate(item.id)} disabled={removeMaterialMut.isPending} title="Remove"><i className="fas fa-times"></i></button>
                    </div>
                  ))}
                  <div className="jm-total">
                    <span>Total</span>
                    <span className="jm-total-amount">€{parseFloat(jobMaterialsData.total_cost).toFixed(2)}</span>
                  </div>
                  <button className="btn btn-sm btn-secondary" style={{ marginTop: '0.4rem', fontSize: '0.72rem' }}
                    onClick={() => generatePOMut.mutate()} disabled={generatePOMut.isPending}>
                    <i className={`fas ${generatePOMut.isPending ? 'fa-spinner fa-spin' : 'fa-file-export'}`}></i>
                    {generatePOMut.isPending ? 'Creating...' : 'Generate Purchase Order'}
                  </button>
                </div>
              ) : (
                <div className="empty-workers"><i className="fas fa-cubes"></i><p>No materials logged</p></div>
              )}
            </div>

            {/* Sub-Tasks / Task Breakdown */}
            <div className="info-card">
              <div className="card-header-row">
                <h3><i className="fas fa-tasks"></i> Tasks</h3>
                <button className="btn btn-sm btn-primary" onClick={() => setShowAddTask(!showAddTask)}>
                  <i className="fas fa-plus"></i> Add
                </button>
              </div>
              {showAddTask && (
                <div className="assign-box" style={{ marginBottom: '0.5rem' }}>
                  <input type="text" className="form-select" placeholder="Task title *" value={newTask.title}
                    onChange={e => setNewTask({ ...newTask, title: e.target.value })} autoFocus />
                  <input type="text" className="form-select" placeholder="Description (optional)" value={newTask.description}
                    onChange={e => setNewTask({ ...newTask, description: e.target.value })} />
                  <input type="number" className="form-select" placeholder="Est. cost €" min="0" step="0.01" value={newTask.estimated_cost}
                    onChange={e => setNewTask({ ...newTask, estimated_cost: e.target.value })} />
                  <div className="assign-buttons">
                    <button className="btn btn-sm btn-secondary" onClick={() => setShowAddTask(false)}>Cancel</button>
                    <button className="btn btn-sm btn-primary" disabled={!newTask.title.trim() || createTaskMut.isPending}
                      onClick={() => createTaskMut.mutate(newTask)}>
                      {createTaskMut.isPending ? 'Adding...' : 'Add Task'}
                    </button>
                  </div>
                </div>
              )}
              {jobTasks.length > 0 ? (
                <div className="jm-list">
                  {jobTasks.map(task => (
                    <div key={task.id} className="jm-item" style={{ alignItems: 'flex-start' }}>
                      <button className="jdm-task-check" title={task.status === 'completed' ? 'Mark pending' : 'Mark complete'}
                        onClick={() => updateTaskMut.mutate({ taskId: task.id, data: { status: task.status === 'completed' ? 'pending' : 'completed' } })}>
                        <i className={`fas ${task.status === 'completed' ? 'fa-check-circle' : 'fa-circle'}`}
                          style={{ color: task.status === 'completed' ? '#10b981' : '#cbd5e1' }}></i>
                      </button>
                      <div className="jm-item-info" style={{ flex: 1 }}>
                        <span className="jm-item-name" style={{ textDecoration: task.status === 'completed' ? 'line-through' : 'none', opacity: task.status === 'completed' ? 0.6 : 1 }}>
                          {task.title}
                        </span>
                        {task.description && <span className="jm-item-detail">{task.description}</span>}
                      </div>
                      {task.estimated_cost > 0 && (
                        <span className="jm-item-total" style={{ fontSize: '0.78rem' }}>€{parseFloat(task.estimated_cost).toFixed(2)}</span>
                      )}
                      <button className="btn-remove" onClick={() => deleteTaskMut.mutate(task.id)} title="Remove">
                        <i className="fas fa-times"></i>
                      </button>
                    </div>
                  ))}
                  {jobTasks.some(t => t.estimated_cost > 0) && (
                    <div className="jm-total">
                      <span>Est. Total</span>
                      <span className="jm-total-amount">€{jobTasks.reduce((s, t) => s + (t.estimated_cost || 0), 0).toFixed(2)}</span>
                    </div>
                  )}
                  <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.3rem', fontSize: '0.7rem', color: '#94a3b8' }}>
                    <span>{jobTasks.filter(t => t.status === 'completed').length}/{jobTasks.length} completed</span>
                  </div>
                </div>
              ) : (
                <div className="empty-workers"><i className="fas fa-tasks"></i><p>No tasks yet. Break this job into smaller tasks.</p></div>
              )}
            </div>

            {/* Photos & Videos */}
            <div className="info-card">
              <div className="card-header-row">
                <h3><i className="fas fa-camera"></i> Media</h3>
                <button className="btn btn-sm btn-primary" onClick={() => photoInputRef.current?.click()} disabled={uploadingPhoto}>
                  {uploadingPhoto ? <i className="fas fa-spinner fa-spin"></i> : <i className="fas fa-plus"></i>}
                  {uploadingPhoto ? ' Uploading...' : ' Add'}
                </button>
                <input ref={photoInputRef} type="file" accept="image/*,video/mp4,video/quicktime,video/webm" onChange={handlePhotoSelect} style={{ display: 'none' }} />
              </div>
              {job.photo_urls && job.photo_urls.length > 0 ? (
                <div className="job-photos-grid">
                  {job.photo_urls.map((url, idx) => (
                    <div key={idx} className="job-photo-item">
                      {isVideoUrl(url) ? (
                        <>
                          <video src={getProxiedMediaUrl(url)} muted preload="metadata" onClick={() => setLightboxPhoto(url)} />
                          <div className="video-play-badge" onClick={() => setLightboxPhoto(url)}><i className="fas fa-play"></i></div>
                        </>
                      ) : (
                        <img src={getProxiedMediaUrl(url)} alt={`Job photo ${idx + 1}`} onClick={() => setLightboxPhoto(url)} />
                      )}
                      <button className="job-photo-delete" onClick={() => handleDeletePhoto(url)} disabled={photoDeleteMutation.isPending} title="Remove"><i className="fas fa-trash"></i></button>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="empty-workers"><i className="fas fa-image"></i><p>No media yet</p></div>
              )}
            </div>

            {/* Customer Review */}
            {reviewData?.review && (
              <div className="info-card">
                <h3><i className="fas fa-star" style={{ color: '#f59e0b' }}></i> Customer Review</h3>
                {reviewData.review.submitted_at ? (
                  <div className="review-display">
                    <div className="review-stars">
                      {[1,2,3,4,5].map(s => (
                        <span key={s} style={{ color: s <= reviewData.review.rating ? '#f59e0b' : '#d1d5db', fontSize: '1.3rem' }}>★</span>
                      ))}
                      <span style={{ marginLeft: 8, fontSize: '0.85rem', color: '#6b7280', fontWeight: 600 }}>
                        {reviewData.review.rating}/5
                      </span>
                    </div>
                    {reviewData.review.review_text && (
                      <p style={{ color: '#374151', fontSize: '0.88rem', lineHeight: 1.6, margin: '10px 0 0', fontStyle: 'italic' }}>
                        "{reviewData.review.review_text}"
                      </p>
                    )}
                    <p style={{ color: '#9ca3af', fontSize: '0.75rem', margin: '8px 0 0' }}>
                      Submitted {new Date(reviewData.review.submitted_at).toLocaleDateString('en-IE', { month: 'short', day: 'numeric', year: 'numeric' })}
                    </p>
                  </div>
                ) : (
                  <div className="review-pending">
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#6b7280', fontSize: '0.85rem' }}>
                      <i className="fas fa-clock" style={{ color: '#f59e0b' }}></i>
                      <span>Survey sent{reviewData.review.email_sent_at ? ` on ${new Date(reviewData.review.email_sent_at).toLocaleDateString('en-IE', { month: 'short', day: 'numeric' })}` : ''} — awaiting response</span>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Lightbox */}
        {lightboxPhoto && (
          <div className="job-photo-lightbox" onClick={() => setLightboxPhoto(null)}>
            <button className="lightbox-close" onClick={() => setLightboxPhoto(null)}><i className="fas fa-times"></i></button>
            {isVideoUrl(lightboxPhoto) ? (
              <video src={getProxiedMediaUrl(lightboxPhoto)} controls autoPlay onClick={(e) => e.stopPropagation()} style={{ maxWidth: '90vw', maxHeight: '90vh', borderRadius: 8 }} />
            ) : (
              <img src={getProxiedMediaUrl(lightboxPhoto)} alt="Job photo full size" onClick={(e) => e.stopPropagation()} />
            )}
          </div>
        )}
      </div>

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
