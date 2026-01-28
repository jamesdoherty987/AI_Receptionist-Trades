import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getClient, updateClient, getBookings, addClientNote } from '../../services/api';
import Modal from './Modal';
import { useToast } from '../Toast';
import { formatPhone, formatDateTime, getStatusBadgeClass, formatCurrency } from '../../utils/helpers';
import './CustomerDetailModal.css';

function CustomerDetailModal({ isOpen, onClose, clientId }) {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [isEditing, setIsEditing] = useState(false);
  const [editData, setEditData] = useState({});
  const [newNote, setNewNote] = useState('');

  const { data: client, isLoading: loadingClient } = useQuery({
    queryKey: ['client', clientId],
    queryFn: async () => {
      const response = await getClient(clientId);
      return response.data;
    },
    enabled: isOpen && !!clientId
  });

  const { data: allBookings } = useQuery({
    queryKey: ['bookings'],
    queryFn: async () => {
      const response = await getBookings();
      return response.data;
    },
    enabled: isOpen && !!clientId
  });

  const clientBookings = allBookings?.filter(
    booking => booking.client_id === clientId || 
               booking.customer_name === client?.name ||
               booking.phone === client?.phone
  ) || [];

  const updateMutation = useMutation({
    mutationFn: (data) => updateClient(clientId, data),
    onSuccess: () => {
      queryClient.invalidateQueries(['client', clientId]);
      queryClient.invalidateQueries(['clients']);
      setIsEditing(false);
      addToast('Customer updated successfully!', 'success');
    },
    onError: (error) => {
      addToast('Error updating customer: ' + (error.response?.data?.error || error.message), 'error');
    }
  });

  const noteMutation = useMutation({
    mutationFn: (note) => addClientNote(clientId, note),
    onSuccess: () => {
      queryClient.invalidateQueries(['client', clientId]);
      setNewNote('');
      addToast('Note added!', 'success');
    },
    onError: (error) => {
      addToast('Error adding note', 'error');
    }
  });

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
    updateMutation.mutate(editData);
  };

  const handleAddNote = () => {
    if (newNote.trim()) {
      noteMutation.mutate(newNote);
    }
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

  if (!client) return null;

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
              <button className="btn btn-secondary" onClick={handleEditStart}>
                <i className="fas fa-edit"></i> Edit Customer
              </button>
            )}
          </div>
        </div>

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
              <h3><i className="fas fa-sticky-note"></i> Notes</h3>
              {client.notes && (
                <div className="existing-note">
                  <p>{client.notes}</p>
                </div>
              )}
              <div className="add-note">
                <textarea
                  className="form-input"
                  placeholder="Add a note about this customer..."
                  value={newNote}
                  onChange={(e) => setNewNote(e.target.value)}
                  rows={2}
                />
                <button 
                  className="btn btn-primary btn-sm"
                  onClick={handleAddNote}
                  disabled={!newNote.trim() || noteMutation.isPending}
                >
                  {noteMutation.isPending ? 'Adding...' : 'Add Note'}
                </button>
              </div>
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
