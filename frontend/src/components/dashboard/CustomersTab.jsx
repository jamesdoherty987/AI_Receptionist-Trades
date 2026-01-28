import { useState, useMemo } from 'react';
import { formatPhone } from '../../utils/helpers';
import AddClientModal from '../modals/AddClientModal';
import CustomerDetailModal from '../modals/CustomerDetailModal';
import './CustomersTab.css';

function CustomersTab({ clients, bookings = [] }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedClientId, setSelectedClientId] = useState(null);

  // Calculate booking counts for each client
  const clientsWithBookings = useMemo(() => {
    return clients.map(client => {
      const clientBookings = bookings.filter(
        b => b.client_id === client.id || 
             b.customer_name === client.name ||
             b.phone === client.phone
      );
      return {
        ...client,
        total_bookings: clientBookings.length
      };
    });
  }, [clients, bookings]);

  const filteredClients = useMemo(() => {
    if (!searchTerm.trim()) return clientsWithBookings;

    const term = searchTerm.toLowerCase();
    return clientsWithBookings.filter(client =>
      client.name?.toLowerCase().includes(term) ||
      client.phone?.includes(term) ||
      client.email?.toLowerCase().includes(term)
    );
  }, [clientsWithBookings, searchTerm]);

  return (
    <div className="customers-tab">
      <div className="customers-header">
        <h2>Customer Directory</h2>
        <div className="customers-controls">
          <div className="search-box">
            <i className="fas fa-search"></i>
            <input
              type="text"
              placeholder="Search customers..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          <button className="btn btn-primary btn-sm" onClick={() => setShowAddModal(true)}>
            <i className="fas fa-plus"></i> Add Customer
          </button>
        </div>
      </div>

      <div className="customers-list">
        {filteredClients.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">👥</div>
            <p>No customers found</p>
          </div>
        ) : (
          filteredClients.map((client) => (
            <div 
              key={client.id} 
              className="customer-card"
              onClick={() => setSelectedClientId(client.id)}
              style={{ cursor: 'pointer' }}
            >
              <div className="customer-avatar">
                <i className="fas fa-user"></i>
              </div>
              <div className="customer-info">
                <h3>{client.name}</h3>
                <div className="customer-details">
                  {client.phone && (
                    <div className="customer-detail">
                      <i className="fas fa-phone"></i>
                      <span>{formatPhone(client.phone)}</span>
                    </div>
                  )}
                  {client.email && (
                    <div className="customer-detail">
                      <i className="fas fa-envelope"></i>
                      <span>{client.email}</span>
                    </div>
                  )}
                </div>
                {client.notes && (
                  <div className="customer-notes">
                    <i className="fas fa-sticky-note"></i>
                    <span>{client.notes}</span>
                  </div>
                )}
              </div>
              <div className="customer-stats">
                <div className="stat-item">
                  <div className="stat-number">{client.total_bookings || 0}</div>
                  <div className="stat-text">Bookings</div>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Modals */}
      <AddClientModal 
        isOpen={showAddModal} 
        onClose={() => setShowAddModal(false)} 
      />
      <CustomerDetailModal
        isOpen={!!selectedClientId}
        onClose={() => setSelectedClientId(null)}
        clientId={selectedClientId}
      />
    </div>
  );
}

export default CustomersTab;
