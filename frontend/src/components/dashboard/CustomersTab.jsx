import { useState, useMemo } from 'react';
import { useAuth } from '../../context/AuthContext';
import { formatPhone } from '../../utils/helpers';
import { useToast } from '../Toast';
import AddClientModal from '../modals/AddClientModal';
import CustomerDetailModal from '../modals/CustomerDetailModal';
import './CustomersTab.css';
import './SharedDashboard.css';

function CustomersTab({ clients, bookings = [] }) {
  const { hasActiveSubscription } = useAuth();
  const isSubscriptionActive = hasActiveSubscription();
  const { addToast } = useToast();
  const [searchTerm, setSearchTerm] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedClientId, setSelectedClientId] = useState(null);

  const handleAddClick = () => {
    if (!isSubscriptionActive) {
      addToast('Please upgrade your plan to add customers', 'warning');
      return;
    }
    setShowAddModal(true);
  };

  // Calculate booking counts for each client
  // Use == for comparison to handle potential type mismatches (string vs number)
  const clientsWithBookings = useMemo(() => {
    return clients.map(client => {
      const clientBookings = bookings.filter(b => b.client_id == client.id);
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
      <div className="tab-page-header">
        <div>
          <h2>Customer Directory</h2>
          <p className="tab-page-subtitle">{clients.length} customer{clients.length !== 1 ? 's' : ''}</p>
        </div>
        <div className="tab-page-controls">
          <div className="dash-search">
            <i className="fas fa-search"></i>
            <input
              type="text"
              placeholder="Search customers..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
            {searchTerm && <button className="dash-search-clear" onClick={() => setSearchTerm('')}><i className="fas fa-times"></i></button>}
          </div>
          <button 
            className="btn-add" 
            onClick={handleAddClick}
          >
            <i className={`fas ${isSubscriptionActive ? 'fa-plus' : 'fa-lock'}`}></i> Add Customer
          </button>
        </div>
      </div>

      <div className="customers-list">
        {filteredClients.length === 0 ? (
          <div className="dash-empty">
            <span className="dash-empty-icon">👥</span>
            <h3>{searchTerm ? 'No matches' : 'No customers yet'}</h3>
            <p>{searchTerm ? 'Try a different search term' : 'Customers will appear here as they book jobs'}</p>
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
      {showAddModal && <AddClientModal 
        isOpen={showAddModal} 
        onClose={() => setShowAddModal(false)} 
      />}
      {!!selectedClientId && <CustomerDetailModal
        isOpen={!!selectedClientId}
        onClose={() => setSelectedClientId(null)}
        clientId={selectedClientId}
      />}
    </div>
  );
}

export default CustomersTab;
