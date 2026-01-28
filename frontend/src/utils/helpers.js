export const formatDate = (date) => {
  if (!date) return '';
  const d = new Date(date);
  return d.toLocaleDateString('en-US', { 
    year: 'numeric', 
    month: 'short', 
    day: 'numeric' 
  });
};

export const formatDateTime = (date) => {
  if (!date) return '';
  const d = new Date(date);
  return d.toLocaleString('en-US', { 
    year: 'numeric', 
    month: 'short', 
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
};

export const formatTime = (date) => {
  if (!date) return '';
  const d = new Date(date);
  return d.toLocaleTimeString('en-US', { 
    hour: '2-digit', 
    minute: '2-digit' 
  });
};

export const formatCurrency = (amount) => {
  if (amount === null || amount === undefined) return '$0.00';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD'
  }).format(amount);
};

export const formatPhone = (phone) => {
  if (!phone) return '';
  const cleaned = phone.replace(/\D/g, '');
  if (cleaned.length === 10) {
    return `(${cleaned.slice(0, 3)}) ${cleaned.slice(3, 6)}-${cleaned.slice(6)}`;
  }
  return phone;
};

export const getStatusColor = (status) => {
  const colors = {
    pending: 'warning',
    scheduled: 'info',
    'in-progress': 'primary',
    completed: 'success',
    cancelled: 'error',
    confirmed: 'success',
    unconfirmed: 'warning',
  };
  return colors[status?.toLowerCase()] || 'secondary';
};

export const getStatusBadgeClass = (status) => {
  const statusLower = status?.toLowerCase();
  if (statusLower === 'completed' || statusLower === 'confirmed') return 'badge-success';
  if (statusLower === 'pending' || statusLower === 'unconfirmed') return 'badge-warning';
  if (statusLower === 'cancelled') return 'badge-error';
  return 'badge-info';
};

export const debounce = (func, wait) => {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
};
