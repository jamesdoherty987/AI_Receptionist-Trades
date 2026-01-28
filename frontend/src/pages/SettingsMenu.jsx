import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import Header from '../components/Header';
import LoadingSpinner from '../components/LoadingSpinner';
import { 
  getServicesMenu, 
  updateServicesMenu,
  createService,
  updateService,
  deleteService,
  getBusinessHours,
  updateBusinessHours
} from '../services/api';
import './SettingsMenu.css';

function SettingsMenu() {
  const queryClient = useQueryClient();
  const [editingService, setEditingService] = useState(null);
  const [newService, setNewService] = useState({ name: '', price: '', duration: '' });
  const [businessHours, setBusinessHours] = useState({});
  const [saveMessage, setSaveMessage] = useState('');

  const { data: menu, isLoading: loadingMenu } = useQuery({
    queryKey: ['services-menu'],
    queryFn: async () => {
      const response = await getServicesMenu();
      return response.data;
    },
  });

  const { data: hours, isLoading: loadingHours } = useQuery({
    queryKey: ['business-hours'],
    queryFn: async () => {
      const response = await getBusinessHours();
      setBusinessHours(response.data);
      return response.data;
    },
  });

  const createMutation = useMutation({
    mutationFn: createService,
    onSuccess: () => {
      queryClient.invalidateQueries(['services-menu']);
      setNewService({ name: '', price: '', duration: '' });
      setSaveMessage('Service added successfully!');
      setTimeout(() => setSaveMessage(''), 3000);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => updateService(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries(['services-menu']);
      setEditingService(null);
      setSaveMessage('Service updated successfully!');
      setTimeout(() => setSaveMessage(''), 3000);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteService,
    onSuccess: () => {
      queryClient.invalidateQueries(['services-menu']);
      setSaveMessage('Service deleted successfully!');
      setTimeout(() => setSaveMessage(''), 3000);
    },
  });

  const hourssMutation = useMutation({
    mutationFn: updateBusinessHours,
    onSuccess: () => {
      queryClient.invalidateQueries(['business-hours']);
      setSaveMessage('Business hours updated successfully!');
      setTimeout(() => setSaveMessage(''), 3000);
    },
  });

  const handleAddService = (e) => {
    e.preventDefault();
    if (newService.name.trim()) {
      createMutation.mutate(newService);
    }
  };

  const handleUpdateService = (service) => {
    updateMutation.mutate({ id: service.id, data: service });
  };

  const handleDeleteService = (id) => {
    if (window.confirm('Are you sure you want to delete this service?')) {
      deleteMutation.mutate(id);
    }
  };

  const handleSaveHours = (e) => {
    e.preventDefault();
    hoursMutation.mutate(businessHours);
  };

  if (loadingMenu || loadingHours) {
    return (
      <div className="settings-menu-page">
        <Header title="Services Menu" />
        <div className="container">
          <LoadingSpinner message="Loading services..." />
        </div>
      </div>
    );
  }

  return (
    <div className="settings-menu-page">
      <Header title="Services Menu" />
      <main className="settings-main">
        <div className="container">
          <div className="settings-header">
            <h1>Services & Menu Settings</h1>
            <p className="settings-subtitle">Configure your services and business hours</p>
          </div>

          <div className="settings-nav">
            <Link to="/settings" className="btn btn-secondary">
              <i className="fas fa-arrow-left"></i>
              Back to Settings
            </Link>
          </div>

          {saveMessage && (
            <div className="alert alert-success">
              {saveMessage}
            </div>
          )}

          {/* Add New Service */}
          <div className="settings-card">
            <h3><i className="fas fa-plus"></i> Add New Service</h3>
            <form onSubmit={handleAddService} className="service-form">
              <div className="form-row">
                <input
                  type="text"
                  placeholder="Service Name"
                  value={newService.name}
                  onChange={(e) => setNewService({ ...newService, name: e.target.value })}
                  required
                />
                <input
                  type="number"
                  placeholder="Price"
                  value={newService.price}
                  onChange={(e) => setNewService({ ...newService, price: e.target.value })}
                />
                <input
                  type="text"
                  placeholder="Duration (e.g., 1 hour)"
                  value={newService.duration}
                  onChange={(e) => setNewService({ ...newService, duration: e.target.value })}
                />
                <button type="submit" className="btn btn-primary" disabled={createMutation.isPending}>
                  <i className="fas fa-plus"></i>
                  Add Service
                </button>
              </div>
            </form>
          </div>

          {/* Services List */}
          <div className="settings-card">
            <h3><i className="fas fa-list"></i> Current Services</h3>
            <div className="services-list">
              {!menu || menu.length === 0 ? (
                <div className="empty-state">
                  <div className="empty-state-icon">📋</div>
                  <p>No services configured yet</p>
                </div>
              ) : (
                menu.map((service) => (
                  <div key={service.id} className="service-item">
                    {editingService?.id === service.id ? (
                      <div className="service-edit-form">
                        <input
                          type="text"
                          value={editingService.name}
                          onChange={(e) => setEditingService({ ...editingService, name: e.target.value })}
                        />
                        <input
                          type="number"
                          value={editingService.price}
                          onChange={(e) => setEditingService({ ...editingService, price: e.target.value })}
                        />
                        <input
                          type="text"
                          value={editingService.duration}
                          onChange={(e) => setEditingService({ ...editingService, duration: e.target.value })}
                        />
                        <div className="service-actions">
                          <button 
                            className="btn btn-success btn-sm"
                            onClick={() => handleUpdateService(editingService)}
                          >
                            <i className="fas fa-check"></i>
                          </button>
                          <button 
                            className="btn btn-secondary btn-sm"
                            onClick={() => setEditingService(null)}
                          >
                            <i className="fas fa-times"></i>
                          </button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <div className="service-info">
                          <h4>{service.name}</h4>
                          <div className="service-details">
                            {service.price && <span className="service-price">${service.price}</span>}
                            {service.duration && <span className="service-duration">{service.duration}</span>}
                          </div>
                        </div>
                        <div className="service-actions">
                          <button 
                            className="btn btn-secondary btn-sm"
                            onClick={() => setEditingService(service)}
                          >
                            <i className="fas fa-edit"></i>
                          </button>
                          <button 
                            className="btn btn-danger btn-sm"
                            onClick={() => handleDeleteService(service.id)}
                          >
                            <i className="fas fa-trash"></i>
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Business Hours */}
          <div className="settings-card">
            <h3><i className="fas fa-clock"></i> Business Hours</h3>
            <form onSubmit={handleSaveHours}>
              <div className="hours-grid">
                {['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'].map((day) => (
                  <div key={day} className="hours-row">
                    <label className="day-label">{day}</label>
                    <input
                      type="time"
                      value={businessHours[`${day.toLowerCase()}_open`] || ''}
                      onChange={(e) => setBusinessHours({ ...businessHours, [`${day.toLowerCase()}_open`]: e.target.value })}
                    />
                    <span className="time-separator">to</span>
                    <input
                      type="time"
                      value={businessHours[`${day.toLowerCase()}_close`] || ''}
                      onChange={(e) => setBusinessHours({ ...businessHours, [`${day.toLowerCase()}_close`]: e.target.value })}
                    />
                    <label className="closed-checkbox">
                      <input
                        type="checkbox"
                        checked={businessHours[`${day.toLowerCase()}_closed`] || false}
                        onChange={(e) => setBusinessHours({ ...businessHours, [`${day.toLowerCase()}_closed`]: e.target.checked })}
                      />
                      Closed
                    </label>
                  </div>
                ))}
              </div>
              <div className="form-actions">
                <button type="submit" className="btn btn-primary" disabled={hoursMutation.isPending}>
                  <i className="fas fa-save"></i>
                  {hoursMutation.isPending ? 'Saving...' : 'Save Business Hours'}
                </button>
              </div>
            </form>
          </div>
        </div>
      </main>
    </div>
  );
}

export default SettingsMenu;
