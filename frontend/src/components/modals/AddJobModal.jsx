import { useState, useMemo, useRef, useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { createBooking, getClients } from '../../services/api';
import Modal from './Modal';
import { useToast } from '../Toast';
import AddClientModal from './AddClientModal';
import './AddJobModal.css';

function AddJobModal({ isOpen, onClose }) {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [formData, setFormData] = useState({
    client_id: '',
    appointment_time: '',
    service_type: '',
    job_address: '',
    eircode: '',
    property_type: '',
    estimated_charge: '',
    notes: ''
  });
  const [clientSearch, setClientSearch] = useState('');
  const [selectedQuickDate, setSelectedQuickDate] = useState('');
  const [showClientDropdown, setShowClientDropdown] = useState(false);
  const [selectedClientName, setSelectedClientName] = useState('');
  const [isAddClientModalOpen, setIsAddClientModalOpen] = useState(false);
  const [waitingForNewClient, setWaitingForNewClient] = useState(false);
  const dropdownRef = useRef(null);
  const inputRef = useRef(null);
  const previousClientsLengthRef = useRef(0);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setShowClientDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const { data: clients } = useQuery({
    queryKey: ['clients'],
    queryFn: async () => {
      const response = await getClients();
      return response.data;
    },
    enabled: isOpen
  });

  const filteredClients = useMemo(() => {
    if (!clients) return [];
    if (!clientSearch.trim()) return clients;
    
    const term = clientSearch.toLowerCase();
    return clients.filter(client =>
      client.name?.toLowerCase().includes(term) ||
      client.phone?.includes(clientSearch) ||
      client.email?.toLowerCase().includes(term)
    );
  }, [clients, clientSearch]);

  const mutation = useMutation({
    mutationFn: createBooking,
    onSuccess: () => {
      queryClient.invalidateQueries(['bookings']);
      onClose();
      resetForm();
      addToast('Job created successfully!', 'success');
    },
    onError: (error) => {
      addToast('Error creating job: ' + (error.response?.data?.error || error.message), 'error');
    }
  });

  const resetForm = () => {
    setFormData({
      client_id: '',
      appointment_time: '',
      service_type: '',
      job_address: '',
      eircode: '',
      property_type: '',
      estimated_charge: '',
      notes: ''
    });
    setClientSearch('');
    setSelectedQuickDate('');
    setSelectedClientName('');
    setShowClientDropdown(false);
    setWaitingForNewClient(false);
  };

  const handleSelectClient = (client) => {
    setFormData(prev => ({ ...prev, client_id: client.id }));
    setSelectedClientName(client.name);
    setClientSearch('');
    setShowClientDropdown(false);
  };

  const handleClientSearchFocus = () => {
    setShowClientDropdown(true);
  };

  const handleClientSearchChange = (e) => {
    setClientSearch(e.target.value);
    setShowClientDropdown(true);
    // If user is typing, clear the selection unless they've selected
    if (!e.target.value && !formData.client_id) {
      setSelectedClientName('');
    }
  };

  const clearClientSelection = () => {
    setFormData(prev => ({ ...prev, client_id: '' }));
    setSelectedClientName('');
    setClientSearch('');
    inputRef.current?.focus();
  };

  const handleOpenAddClientModal = () => {
    setShowClientDropdown(false);
    setWaitingForNewClient(true);
    setIsAddClientModalOpen(true);
  };

  const handleCloseAddClientModal = () => {
    setIsAddClientModalOpen(false);
    // Refetch clients to get the newly added customer
    queryClient.invalidateQueries(['clients']);
  };

  // Track previous clients length to detect new additions
  useEffect(() => {
    if (clients) {
      previousClientsLengthRef.current = clients.length;
    }
  }, [clients]);

  // When a new client is added, auto-select them
  useEffect(() => {
    if (waitingForNewClient && clients && clients.length > previousClientsLengthRef.current) {
      // A new client was added - select the most recent one
      const sortedClients = [...clients].sort((a, b) => {
        // Assuming clients have an id or created_at field
        // Most recent will have the highest id
        return (b.id || 0) - (a.id || 0);
      });
      const newestClient = sortedClients[0];
      
      if (newestClient) {
        handleSelectClient(newestClient);
        addToast(`Customer "${newestClient.name}" selected`, 'success');
      }
      
      setWaitingForNewClient(false);
      previousClientsLengthRef.current = clients.length;
    }
  }, [clients, waitingForNewClient, addToast]);

  // Reset form when modal is closed
  useEffect(() => {
    if (!isOpen) {
      setWaitingForNewClient(false);
    }
  }, [isOpen]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!formData.client_id || !formData.appointment_time || !formData.service_type) {
      addToast('Please fill in all required fields', 'warning');
      return;
    }
    mutation.mutate(formData);
  };

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const setQuickDate = (type) => {
    setSelectedQuickDate(type);
    const now = new Date();
    let date, time;

    switch (type) {
      case 'today':
        date = now.toISOString().split('T')[0];
        time = '09:00';
        break;
      case 'tomorrow':
        now.setDate(now.getDate() + 1);
        date = now.toISOString().split('T')[0];
        time = '09:00';
        break;
      case 'nextWeek':
        now.setDate(now.getDate() + 7);
        date = now.toISOString().split('T')[0];
        time = '09:00';
        break;
      default:
        return;
    }

    setFormData(prev => ({
      ...prev,
      appointment_time: `${date}T${time}`
    }));
  };

  return (
    <>
    <Modal isOpen={isOpen} onClose={onClose} title="Add New Job" size="large">
      <form onSubmit={handleSubmit} className="form">
        <div className="form-group">
          <label className="form-label">Customer *</label>
          <div className="customer-search-container" ref={dropdownRef}>
            {selectedClientName ? (
              <div className="selected-customer">
                <div className="selected-customer-info">
                  <i className="fas fa-user-check"></i>
                  <span className="selected-name">{selectedClientName}</span>
                </div>
                <button 
                  type="button" 
                  className="clear-selection-btn"
                  onClick={clearClientSelection}
                >
                  <i className="fas fa-times"></i>
                </button>
              </div>
            ) : (
              <div className="customer-search-input-wrapper">
                <i className="fas fa-search search-icon"></i>
                <input
                  ref={inputRef}
                  type="text"
                  className="form-input customer-search-input"
                  placeholder="Search by name, phone, or email..."
                  value={clientSearch}
                  onChange={handleClientSearchChange}
                  onFocus={handleClientSearchFocus}
                  autoComplete="off"
                />
              </div>
            )}
            
            {showClientDropdown && !selectedClientName && (
              <div className="customer-dropdown">
                {filteredClients.length === 0 ? (
                  <div className="dropdown-empty">
                    <i className="fas fa-user-slash"></i>
                    <p>No customers found</p>
                    <small>Try a different search term or add a new customer</small>
                    <button 
                      type="button"
                      className="btn-add-customer-inline"
                      onClick={handleOpenAddClientModal}
                    >
                      <i className="fas fa-user-plus"></i> Add New Customer
                    </button>
                  </div>
                ) : (
                  <>
                    <ul className="customer-list">
                      {filteredClients.slice(0, 8).map(client => (
                        <li 
                          key={client.id}
                          className="customer-option"
                          onClick={() => handleSelectClient(client)}
                        >
                          <div className="customer-option-avatar">
                            {client.name?.charAt(0).toUpperCase() || '?'}
                          </div>
                          <div className="customer-option-details">
                            <span className="customer-option-name">{client.name}</span>
                            <span className="customer-option-contact">
                              {client.phone && <span><i className="fas fa-phone"></i> {client.phone}</span>}
                              {client.email && <span><i className="fas fa-envelope"></i> {client.email}</span>}
                            </span>
                          </div>
                        </li>
                      ))}
                      {filteredClients.length > 8 && (
                        <li className="dropdown-more">
                          +{filteredClients.length - 8} more results
                        </li>
                      )}
                    </ul>
                    <div className="dropdown-footer">
                      <button 
                        type="button"
                        className="btn-add-customer-footer"
                        onClick={handleOpenAddClientModal}
                      >
                        <i className="fas fa-user-plus"></i> Add New Customer
                      </button>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
          <small className="form-hint">
            <i className="fas fa-info-circle"></i> Type to search or select from the list
          </small>
        </div>

        <div className="form-group">
          <label className="form-label">Date & Time *</label>
          <div className="quick-date-buttons">
            <button 
              type="button" 
              className={`quick-date-btn ${selectedQuickDate === 'today' ? 'active' : ''}`}
              onClick={() => setQuickDate('today')}
            >
              Today
            </button>
            <button 
              type="button" 
              className={`quick-date-btn ${selectedQuickDate === 'tomorrow' ? 'active' : ''}`}
              onClick={() => setQuickDate('tomorrow')}
            >
              Tomorrow
            </button>
            <button 
              type="button" 
              className={`quick-date-btn ${selectedQuickDate === 'nextWeek' ? 'active' : ''}`}
              onClick={() => setQuickDate('nextWeek')}
            >
              Next Week
            </button>
          </div>
          <input
            type="datetime-local"
            name="appointment_time"
            className="form-input"
            value={formData.appointment_time}
            onChange={handleChange}
            required
          />
        </div>

        <div className="form-group">
          <label className="form-label">Service Type *</label>
          <input
            type="text"
            name="service_type"
            className="form-input"
            value={formData.service_type}
            onChange={handleChange}
            placeholder="e.g., Plumbing repair, Electrical work"
            required
          />
        </div>

        <div className="form-grid">
          <div className="form-group">
            <label className="form-label">Property Type</label>
            <input
              type="text"
              name="property_type"
              className="form-input"
              value={formData.property_type}
              onChange={handleChange}
              placeholder="e.g., House, Apartment"
            />
          </div>

          <div className="form-group">
            <label className="form-label">Eircode</label>
            <input
              type="text"
              name="eircode"
              className="form-input"
              value={formData.eircode}
              onChange={handleChange}
            />
          </div>
        </div>

        <div className="form-group">
          <label className="form-label">Job Address</label>
          <textarea
            name="job_address"
            className="form-textarea"
            value={formData.job_address}
            onChange={handleChange}
            rows="2"
            placeholder="If different from customer's address"
          />
        </div>

        <div className="form-group">
          <label className="form-label">Estimated Charge (€)</label>
          <input
            type="number"
            name="estimated_charge"
            className="form-input"
            value={formData.estimated_charge}
            onChange={handleChange}
            step="0.01"
            min="0"
            placeholder="0.00"
          />
        </div>

        <div className="form-group">
          <label className="form-label">Notes</label>
          <textarea
            name="notes"
            className="form-textarea"
            value={formData.notes}
            onChange={handleChange}
            rows="3"
            placeholder="Additional details about the job"
          />
        </div>

        <div className="form-actions">
          <button 
            type="button" 
            className="btn btn-secondary"
            onClick={onClose}
            disabled={mutation.isPending}
          >
            Cancel
          </button>
          <button 
            type="submit" 
            className="btn btn-primary"
            disabled={mutation.isPending}
          >
            {mutation.isPending ? 'Creating...' : 'Create Job'}
          </button>
        </div>
      </form>
    </Modal>
    <AddClientModal 
      isOpen={isAddClientModalOpen}
      onClose={handleCloseAddClientModal}
    />
    </>
  );
}

export default AddJobModal;
