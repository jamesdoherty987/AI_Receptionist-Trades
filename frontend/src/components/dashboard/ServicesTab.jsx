import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../../context/AuthContext';
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
  const { hasActiveSubscription } = useAuth();
  const isSubscriptionActive = hasActiveSubscription();
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
    onMutate: async (newServiceData) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries(['services-menu']);
      
      // Snapshot previous value
      const previousMenu = queryClient.getQueryData(['services-menu']);
      
      // Optimistically add new service with temporary ID
      const tempService = {
        ...newServiceData,
        id: `temp-${Date.now()}`,
        price: parseFloat(newServiceData.price) || 0,
        duration: parseInt(newServiceData.duration) || 0
      };
      
      queryClient.setQueryData(['services-menu'], (old) => ({
        ...old,
        services: [...(old?.services || []), tempService]
      }));
      
      // Clear form immediately
      setNewService({ name: '', price: '', duration: '', image_url: '' });
      setShowAddForm(false);
      
      return { previousMenu };
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['services-menu']);
      addToast('Service added successfully!', 'success');
    },
    onError: (error, variables, context) => {
      // Rollback on error
      if (context?.previousMenu) {
        queryClient.setQueryData(['services-menu'], context.previousMenu);
      }
      setShowAddForm(true);
      setNewService(variables);
      addToast('Failed to add service', 'error');
    }
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => updateService(id, data),
    onMutate: async ({ id, data }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries(['services-menu']);
      
      // Snapshot previous value
      const previousMenu = queryClient.getQueryData(['services-menu']);
      
      // Optimistically update
      queryClient.setQueryData(['services-menu'], (old) => ({
        ...old,
        services: old?.services?.map(s => 
          s.id === id ? { ...s, ...data } : s
        ) || []
      }));
      
      setEditingService(null);
      
      return { previousMenu };
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['services-menu']);
      addToast('Service updated successfully!', 'success');
    },
    onError: (error, variables, context) => {
      // Rollback on error
      if (context?.previousMenu) {
        queryClient.setQueryData(['services-menu'], context.previousMenu);
      }
      addToast('Failed to update service', 'error');
    }
  });

  const deleteMutation = useMutation({
    mutationFn: deleteService,
    onMutate: async (serviceId) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries(['services-menu']);
      
      // Snapshot previous value
      const previousMenu = queryClient.getQueryData(['services-menu']);
      
      // Optimistically remove service
      queryClient.setQueryData(['services-menu'], (old) => ({
        ...old,
        services: old?.services?.filter(s => s.id !== serviceId) || []
      }));
      
      return { previousMenu };
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['services-menu']);
      addToast('Service deleted', 'success');
    },
    onError: (error, variables, context) => {
      // Rollback on error
      if (context?.previousMenu) {
        queryClient.setQueryData(['services-menu'], context.previousMenu);
      }
      addToast('Failed to delete service', 'error');
    }
  });

  const handleAddService = (e) => {
    e.preventDefault();
    if (newService.name.trim()) {
      // Convert duration to duration_minutes for backend
      const serviceData = {
        ...newService,
        duration_minutes: parseInt(newService.duration) || 60
      };
      createMutation.mutate(serviceData);
    }
  };

  const handleUpdateService = (service) => {
    // Convert duration to duration_minutes for backend
    const serviceData = {
      ...service,
      duration_minutes: parseInt(service.duration) || service.duration_minutes || 60
    };
    updateMutation.mutate({ id: service.id, data: serviceData });
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
        <div className="services-controls">
          <button 
            className="btn btn-primary"
            onClick={() => setShowAddForm(!showAddForm)}
            disabled={!isSubscriptionActive}
            title={!isSubscriptionActive ? 'Subscribe to add services' : ''}
          >
            <i className="fas fa-plus"></i> Add Service
          </button>
          {!isSubscriptionActive && (
            <Link to="/settings?tab=subscription" className="btn btn-secondary btn-sm" style={{ marginLeft: '8px' }}>
              <i className="fas fa-lock"></i> Subscribe
            </Link>
          )}
        </div>
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
                <label htmlFor="price">Typical Price (€)</label>
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
                <label htmlFor="duration">Usual Duration</label>
                <select
                  id="duration"
                  className="form-input"
                  value={newService.duration}
                  onChange={(e) => setNewService({...newService, duration: e.target.value})}
                >
                  <option value="">Select duration...</option>
                  <option value="30">30 mins</option>
                  <option value="60">1 hour</option>
                  <option value="90">1.5 hours</option>
                  <option value="120">2 hours</option>
                  <option value="150">2.5 hours</option>
                  <option value="180">3 hours</option>
                  <option value="240">4 hours</option>
                  <option value="300">5 hours</option>
                  <option value="360">6 hours</option>
                  <option value="480">8 hours</option>
                </select>
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
                    <select
                      className="form-input"
                      value={editingService.duration_minutes || editingService.duration || '60'}
                      onChange={(e) => setEditingService({...editingService, duration_minutes: e.target.value, duration: e.target.value})}
                    >
                      <option value="30">30 mins</option>
                      <option value="60">1 hour</option>
                      <option value="90">1.5 hours</option>
                      <option value="120">2 hours</option>
                      <option value="150">2.5 hours</option>
                      <option value="180">3 hours</option>
                      <option value="240">4 hours</option>
                      <option value="300">5 hours</option>
                      <option value="360">6 hours</option>
                      <option value="480">8 hours</option>
                    </select>
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
                          {formatCurrency(service.price)}
                        </span>
                      )}
                      {(service.duration_minutes || service.duration) && (
                        <span className="service-duration">
                          <i className="fas fa-clock"></i>
                          {service.duration_minutes || service.duration} mins
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
