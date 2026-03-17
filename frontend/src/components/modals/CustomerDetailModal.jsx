import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getClient, updateClient, deleteClient, getBookings, addClientNote } from '../../services/api';
import Modal from './Modal';
import { useToast } from '../Toast';
import { formatPhone, formatDateTime, getStatusBadgeClass, formatCurrency, getProxiedMediaUrl } from '../../utils/helpers';
import './CustomerDetailModal.css';

function CustomerDetailModal({ isOpen, onClose, clientId }) {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [isEditing, setIsEditing] = useState(false);
  const [editData, setEditData] = useState({});
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [newNote, setNewNote] = useState('');
  const [isAddingNote, setIsAddingNote] = useState(false);

  // Handle escape key to close delete confirmation
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && showDeleteConfirm) {
        setShowDeleteConfirm(false);
      }
    };
    if (showDeleteConfirm) {
      document.addEventListener('keydown', handleEscape);
    }
    return () => document.removeEventListener('keydown', handleEscape);
  }, [showDeleteConfirm]);

  // Reset state when modal closes
  useEffect(() => {
    if (!isOpen) {
      setIsEditing(false);
      setEditData({});
      setShowDeleteConfirm(false);
      setNewNote('');
      setIsAddingNote(false);
    }
  }, [isOpen]);

  const { data: client, isLoading: loadingClient } = useQuery({
    queryKey: ['client', clientId],
    queryFn: async () => {
      const response = await getClient(clientId);
      return response.data;
    },
    enabled: isOpen && !!clientId,
    staleTime: 30 * 1000, // 30 seconds
    gcTime: 5 * 60 * 1000, // 5 minutes (renamed from cacheTime in v5)
    placeholderData: (previousData) => previousData, // Keep previous data while refetching
  });

  const { data: allBookings } = useQuery({
    queryKey: ['bookings'],
    queryFn: async () => {
      const response = await getBookings();
      return response.data;
    },
    enabled: isOpen && !!clientId,
    staleTime: 60 * 1000, // 1 minute
    gcTime: 10 * 60 * 1000, // 10 minutes
    placeholderData: (previousData) => previousData,
  });

  // Use == for comparison to handle potential type mismatches (string vs number)
  const clientBookings = allBookings?.filter(
    booking => booking.client_id == clientId
  ) || [];

  const updateMutation = useMutation({
    mutationFn: (data) => updateClient(clientId, data),
    onMutate: async (data) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['client', clientId] });
      
      // Snapshot previous value
      const previousClient = queryClient.getQueryData(['client', clientId]);
      
      // Optimistically update
      if (previousClient) {
        queryClient.setQueryData(['client', clientId], {
          ...previousClient,
          ...data
        });
      }
      
      return { previousClient };
    },
    onSuccess: () => {
      queryClient.refetchQueries({ queryKey: ['client', clientId] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      setIsEditing(false);
      addToast('Customer updated successfully!', 'success');
    },
    onError: (error, variables, context) => {
      // Rollback on error
      if (context?.previousClient) {
        queryClient.setQueryData(['client', clientId], context.previousClient);
      }
      addToast('Error updating customer: ' + (error.response?.data?.error || error.message), 'error');
    }
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteClient(clientId),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['clients'] });
      setShowDeleteConfirm(false);
      onClose();
      const bookingsDeleted = response.data?.bookings_deleted || 0;
      addToast(`Customer deleted${bookingsDeleted > 0 ? ` (${bookingsDeleted} job${bookingsDeleted !== 1 ? 's' : ''} also removed)` : ''}`, 'success');
    },
    onError: (error) => {
      setShowDeleteConfirm(false);
      addToast('Error deleting customer: ' + (error.response?.data?.error || error.message), 'error');
    }
  });

  const noteMutation = useMutation({
    mutationFn: (note) => addClientNote(clientId, note),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['client', clientId] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      setNewNote('');
      setIsAddingNote(false);
      addToast('Note added successfully!', 'success');
    },
    onError: (error) => {
      addToast('Error adding note: ' + (error.response?.data?.error || error.message), 'error');
    }
  });

  const handleAddNote = () => {
    const trimmedNote = newNote.trim();
    if (!trimmedNote) {
      addToast('Please enter a note', 'warning');
      return;
    }
    noteMutation.mutate(trimmedNote);
  };

  const handleDelete = () => {
    setShowDeleteConfirm(true);
  };

  const confirmDelete = () => {
    deleteMutation.mutate();
  };

  const handleEditStart = () => {
    setEditData({
      name: client.name || '',
      phone: client.phone || '',
      email: client.email || '',
      address: client.address || '',
      eircode: client.eircode || ''
    });
    setIsEditing(true);
  };

  const handleEditSave = () => {
    // Validate required field
    if (!editData.name || !editData.name.trim()) {
      addToast('Customer name is required', 'warning');
      return;
    }
    updateMutation.mutate(editData);
  };

  if (loadingClient) {
    return (
      <Modal isOpen={isOpen} onClose={onClose} title="Customer Details" size="xlarge">
        <div className="modal-loading">
          <div className="loading-spinner"></div>
          <p>Loading customer details...</p>
        </div>
      </Modal>
    );
  }

  if (!client) {
    return (
      <Modal isOpen={isOpen} onClose={onClose} title="Customer Details" size="xlarge">
        <div className="modal-loading">
          <p>Customer not found</p>
        </div>
      </Modal>
    );
  }

  const totalBookings = clientBookings.length;
  const completedBookings = clientBookings.filter(b => b.status === 'completed').length;
  const totalSpent = clientBookings
    .filter(b => b.status === 'completed')
    .reduce((sum, b) => sum + (parseFloat(b.estimated_charge || b.charge || 0)), 0);

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Customer Details" size="xlarge">
      <div className="customer-detail-modal">
        {/* Header */}
        <div className="customer-modal-header">
          <div className="customer-modal-avatar">
            <i className="fas fa-user"></i>
          </div>
          <div className="customer-modal-info">
            {isEditing ? (
              <input
                type="text"
                className="form-input name-input"
                value={editData.name}
                onChange={(e) => setEditData({...editData, name: e.target.value})}
                placeholder="Customer Name"
              />
            ) : (
              <h2>{client.name}</h2>
            )}
            <div className="stats-row">
              <div className="stat-badge">
                <i className="fas fa-calendar-check"></i>
                <span>{totalBookings} Bookings</span>
              </div>
              <div className="stat-badge completed">
                <i className="fas fa-check-circle"></i>
                <span>{completedBookings} Completed</span>
              </div>
              {totalSpent > 0 && (
                <div className="stat-badge spent">
                  <i className="fas fa-euro-sign"></i>
                  <span>{formatCurrency(totalSpent)}</span>
                </div>
              )}
            </div>
          </div>
          <div className="customer-modal-actions">
            {isEditing ? (
              <>
                <button className="btn btn-secondary" onClick={() => setIsEditing(false)}>Cancel</button>
                <button 
                  className="btn btn-primary"
                  onClick={handleEditSave}
                  disabled={updateMutation.isPending}
                >
                  {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
                </button>
              </>
            ) : (
              <>
                <button className="btn btn-secondary" onClick={handleEditStart}>
                  <i className="fas fa-edit"></i> Edit
                </button>
                <button 
                  className="btn btn-danger"
                  onClick={handleDelete}
                  disabled={deleteMutation.isPending}
                >
                  <i className="fas fa-trash"></i> Delete
                </button>
              </>
            )}
          </div>
        </div>

        {/* Delete Confirmation */}
        {showDeleteConfirm && (
          <div className="delete-confirm-overlay">
            <div className="delete-confirm-dialog">
              <div className="delete-confirm-icon">
                <i className="fas fa-exclamation-triangle"></i>
              </div>
              <h3>Delete Customer?</h3>
              <p className="delete-warning">
                This will permanently delete <strong>{client.name}</strong> and all their associated data.
              </p>
              {totalBookings > 0 && (
                <p className="delete-cascade-warning">
                  <i className="fas fa-exclamation-circle"></i>
                  <strong>{totalBookings} job{totalBookings !== 1 ? 's' : ''}</strong> will also be deleted.
                </p>
              )}
              <div className="delete-confirm-actions">
                <button className="btn btn-secondary" onClick={() => setShowDeleteConfirm(false)}>
                  Cancel
                </button>
                <button 
                  className="btn btn-danger" 
                  onClick={confirmDelete}
                  disabled={deleteMutation.isPending}
                >
                  {deleteMutation.isPending ? 'Deleting...' : 'Delete Customer'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Content Grid */}
        <div className="customer-modal-grid">
          {/* Left Column */}
          <div className="customer-modal-column">
            {/* Contact Info */}
            <div className="info-card">
              <h3><i className="fas fa-address-card"></i> Contact Information</h3>
              {isEditing ? (
                <div className="edit-form">
                  <div className="form-row">
                    <div className="form-group">
                      <label>Phone</label>
                      <input
                        type="tel"
                        className="form-input"
                        value={editData.phone}
                        onChange={(e) => setEditData({...editData, phone: e.target.value})}
                        placeholder="Phone number"
                      />
                    </div>
                    <div className="form-group">
                      <label>Email</label>
                      <input
                        type="email"
                        className="form-input"
                        value={editData.email}
                        onChange={(e) => setEditData({...editData, email: e.target.value})}
                        placeholder="Email address"
                      />
                    </div>
                  </div>
                  <div className="form-row">
                    <div className="form-group flex-2">
                      <label>Address</label>
                      <input
                        type="text"
                        className="form-input"
                        value={editData.address}
                        onChange={(e) => setEditData({...editData, address: e.target.value})}
                        placeholder="Street address"
                      />
                    </div>
                    <div className="form-group">
                      <label>Eircode</label>
                      <input
                        type="text"
                        className="form-input"
                        value={editData.eircode}
                        onChange={(e) => setEditData({...editData, eircode: e.target.value})}
                        placeholder="Eircode"
                      />
                    </div>
                  </div>
                </div>
              ) : (
                <>
                  <div className="info-row">
                    <div className="info-cell">
                      <span className="info-label">Phone</span>
                      <span className="info-value">
                        {client.phone ? (
                          <a href={`tel:${client.phone}`} className="link">{formatPhone(client.phone)}</a>
                        ) : <span className="not-provided">Not provided</span>}
                      </span>
                    </div>
                    <div className="info-cell">
                      <span className="info-label">Email</span>
                      <span className="info-value">
                        {client.email ? (
                          <a href={`mailto:${client.email}`} className="link">{client.email}</a>
                        ) : <span className="not-provided">Not provided</span>}
                      </span>
                    </div>
                  </div>
                  <div className="info-row">
                    <div className="info-cell flex-2">
                      <span className="info-label">Address</span>
                      <span className="info-value">{client.address || <span className="not-provided">Not provided</span>}</span>
                    </div>
                    <div className="info-cell">
                      <span className="info-label">Eircode</span>
                      <span className="info-value">{client.eircode || <span className="not-provided">Not provided</span>}</span>
                    </div>
                  </div>
                </>
              )}
            </div>

            {/* Notes */}
            <div className="info-card">
              <div className="notes-header">
                <h3><i className="fas fa-sticky-note"></i> Notes</h3>
                {!isAddingNote && (
                  <button 
                    className="btn btn-sm btn-secondary"
                    onClick={() => setIsAddingNote(true)}
                  >
                    <i className="fas fa-plus"></i> Add Note
                  </button>
                )}
              </div>
              
              {isAddingNote && (
                <div className="add-note">
                  <textarea
                    className="form-input"
                    placeholder="Enter your note here..."
                    value={newNote}
                    onChange={(e) => setNewNote(e.target.value)}
                    rows={3}
                    autoFocus
                  />
                  <div className="add-note-actions">
                    <button 
                      className="btn btn-sm btn-secondary"
                      onClick={() => {
                        setIsAddingNote(false);
                        setNewNote('');
                      }}
                    >
                      Cancel
                    </button>
                    <button 
                      className="btn btn-sm btn-primary"
                      onClick={handleAddNote}
                      disabled={noteMutation.isPending || !newNote.trim()}
                    >
                      {noteMutation.isPending ? 'Saving...' : 'Save Note'}
                    </button>
                  </div>
                </div>
              )}
              
              {client.notes ? (
                <div className="existing-note">
                  <p>{client.notes}</p>
                </div>
              ) : !isAddingNote && (
                <div className="empty-notes">
                  <p>No notes yet</p>
                </div>
              )}
            </div>
          </div>

          {/* Right Column - Booking History */}
          <div className="customer-modal-column">
            <div className="info-card bookings-card">
              <h3><i className="fas fa-history"></i> Booking History ({totalBookings})</h3>
              <div className="bookings-list">
                {clientBookings.length === 0 ? (
                  <div className="empty-bookings">
                    <i className="fas fa-calendar-times"></i>
                    <p>No bookings yet</p>
                  </div>
                ) : (
                  clientBookings
                    .sort((a, b) => new Date(b.appointment_time) - new Date(a.appointment_time))
                    .slice(0, 8)
                    .map(booking => (
                      <div key={booking.id} className="booking-item">
                        <div className="booking-item-main">
                          <span className="booking-service">{booking.service_type || booking.service || 'Service'}</span>
                          <span className={`badge badge-sm ${getStatusBadgeClass(booking.status)}`}>
                            {booking.status}
                          </span>
                        </div>
                        <div className="booking-item-meta">
                          <span className="booking-date">
                            <i className="fas fa-calendar"></i>
                            {formatDateTime(booking.appointment_time)}
                          </span>
                          {booking.address_audio_url && (
                            <button 
                              className="btn-audio-inline"
                              onClick={(e) => {
                                e.stopPropagation();
                                const audio = new Audio(getProxiedMediaUrl(booking.address_audio_url));
                                audio.play();
                              }}
                              title="Listen to address"
                              style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#3b82f6', padding: '2px 6px', fontSize: '0.85em' }}
                            >
                              <i className="fas fa-volume-up"></i>
                            </button>
                          )}
                          {(booking.estimated_charge || booking.charge) && (
                            <span className="booking-price">{formatCurrency(booking.estimated_charge || booking.charge)}</span>
                          )}
                        </div>
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

export default CustomerDetailModal;
