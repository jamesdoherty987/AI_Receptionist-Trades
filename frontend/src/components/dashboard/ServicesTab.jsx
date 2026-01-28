import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  getServicesMenu, 
  createService,
  updateService,
  deleteService,
  getBusinessHours,
  updateBusinessHours
} from '../../services/api';
import LoadingSpinner from '../LoadingSpinner';
import { useToast } from '../Toast';
import ImageUpload from '../ImageUpload';
import { formatCurrency } from '../../utils/helpers';
import './ServicesTab.css';

function ServicesTab() {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [editingService, setEditingService] = useState(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newService, setNewService] = useState({ name: '', price: '', duration: '', image_url: '' });

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
      return response.data;
    },
  });

  const createMutation = useMutation({
    mutationFn: createService,
    onSuccess: () => {
      queryClient.invalidateQueries(['services-menu']);
      setNewService({ name: '', price: '', duration: '', image_url: '' });
      setShowAddForm(false);
      addToast('Service added successfully!', 'success');
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => updateService(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries(['services-menu']);
      setEditingService(null);
      addToast('Service updated successfully!', 'success');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteService,
    onSuccess: () => {
      queryClient.invalidateQueries(['services-menu']);
      addToast('Service deleted', 'success');
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

  if (loadingMenu) {
    return <LoadingSpinner message="Loading services..." />;
  }

  const services = menu?.services || [];

  return (
    <div className="services-tab">
      {/* Header */}
      <div className="services-header">
        <div>
          <h2>Services Menu</h2>
          <p className="services-subtitle">Manage your business services and pricing</p>
        </div>
        <button 
          className="btn btn-primary"
          onClick={() => setShowAddForm(!showAddForm)}
        >
          <i className="fas fa-plus"></i> Add Service
        </button>
      </div>

      {/* Add Service Form */}
      {showAddForm && (
        <div className="service-form-card">
          <h3>Add New Service</h3>
          <form onSubmit={handleAddService} className="service-form">
            <div className="form-row">
              <div className="form-group">
                <label htmlFor="name">Service Name *</label>
                <input
                  type="text"
                  id="name"
                  className="form-input"
                  value={newService.name}
                  onChange={(e) => setNewService({...newService, name: e.target.value})}
                  placeholder="e.g., Emergency Plumbing"
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="price">Price (€)</label>
                <input
                  type="number"
                  id="price"
                  className="form-input"
                  value={newService.price}
                  onChange={(e) => setNewService({...newService, price: e.target.value})}
                  placeholder="0.00"
                  step="0.01"
                />
              </div>
              <div className="form-group">
                <label htmlFor="duration">Duration (mins)</label>
                <input
                  type="number"
                  id="duration"
                  className="form-input"
                  value={newService.duration}
                  onChange={(e) => setNewService({...newService, duration: e.target.value})}
                  placeholder="60"
                />
              </div>
            </div>
            <div className="form-group">
              <label htmlFor="image_url">Service Image (optional)</label>
              <ImageUpload
                value={newService.image_url}
                onChange={(value) => setNewService({...newService, image_url: value})}
                placeholder="Upload Service Image"
              />
            </div>
            <div className="form-actions">
              <button 
                type="button" 
                className="btn btn-secondary"
                onClick={() => {
                  setShowAddForm(false);
                  setNewService({ name: '', price: '', duration: '', image_url: '' });
                }}
              >
                Cancel
              </button>
              <button 
                type="submit" 
                className="btn btn-primary"
                disabled={createMutation.isPending}
              >
                {createMutation.isPending ? 'Adding...' : 'Add Service'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Services List */}
      <div className="services-grid">
        {services.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">🔧</div>
            <p>No services added yet</p>
            <button className="btn btn-primary" onClick={() => setShowAddForm(true)}>
              <i className="fas fa-plus"></i> Add Your First Service
            </button>
          </div>
        ) : (
          services.map((service) => (
            <div key={service.id} className="service-card">
              {editingService?.id === service.id ? (
                <div className="service-edit-form">
                  <div className="edit-form-row">
                    <input
                      type="text"
                      className="form-input"
                      value={editingService.name}
                      onChange={(e) => setEditingService({...editingService, name: e.target.value})}
                      placeholder="Service Name"
                    />
                  </div>
                  <div className="edit-form-row two-cols">
                    <input
                      type="number"
                      className="form-input"
                      value={editingService.price || ''}
                      onChange={(e) => setEditingService({...editingService, price: e.target.value})}
                      placeholder="Price (€)"
                      step="0.01"
                    />
                    <input
                      type="number"
                      className="form-input"
                      value={editingService.duration || ''}
                      onChange={(e) => setEditingService({...editingService, duration: e.target.value})}
                      placeholder="Duration (mins)"
                    />
                  </div>
                  <div className="edit-form-row">
                    <ImageUpload
                      value={editingService.image_url || ''}
                      onChange={(value) => setEditingService({...editingService, image_url: value})}
                      placeholder="Upload Service Image"
                    />
                  </div>
                  <div className="service-edit-actions">
                    <button 
                      className="btn btn-sm btn-secondary"
                      onClick={() => setEditingService(null)}
                    >
                      Cancel
                    </button>
                    <button 
                      className="btn btn-sm btn-primary"
                      onClick={() => handleUpdateService(editingService)}
                      disabled={updateMutation.isPending}
                    >
                      {updateMutation.isPending ? 'Saving...' : 'Save'}
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <div className="service-icon">
                    {service.image_url ? (
                      <img src={service.image_url} alt={service.name} className="service-icon-img" />
                    ) : (
                      <i className="fas fa-wrench"></i>
                    )}
                  </div>
                  <div className="service-info">
                    <h3>{service.name}</h3>
                    <div className="service-details">
                      {service.price && (
                        <span className="service-price">
                          <i className="fas fa-euro-sign"></i>
                          {formatCurrency(service.price)}
                        </span>
                      )}
                      {service.duration && (
                        <span className="service-duration">
                          <i className="fas fa-clock"></i>
                          {service.duration} mins
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="service-actions">
                    <button
                      className="btn-icon"
                      onClick={() => setEditingService(service)}
                      title="Edit service"
                    >
                      <i className="fas fa-edit"></i>
                    </button>
                    <button
                      className="btn-icon btn-icon-danger"
                      onClick={() => handleDeleteService(service.id)}
                      title="Delete service"
                      disabled={deleteMutation.isPending}
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
  );
}

export default ServicesTab;
