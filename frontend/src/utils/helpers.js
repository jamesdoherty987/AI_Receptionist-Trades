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
  if (amount === null || amount === undefined) return '€0.00';
  return new Intl.NumberFormat('en-IE', {
    style: 'currency',
    currency: 'EUR'
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
    paid: 'success',
    cancelled: 'error',
    confirmed: 'success',
    unconfirmed: 'warning',
  };
  return colors[status?.toLowerCase()] || 'secondary';
};

export const getStatusBadgeClass = (status) => {
  const statusLower = status?.toLowerCase();
  if (statusLower === 'completed' || statusLower === 'confirmed' || statusLower === 'paid') return 'badge-success';
  if (statusLower === 'pending' || statusLower === 'unconfirmed') return 'badge-warning';
  if (statusLower === 'cancelled') return 'badge-error';
  if (statusLower === 'in-progress') return 'badge-primary';
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

/**
 * Get proxied image URL to avoid CORS/ad-blocker issues with R2 storage.
 * If the URL is from R2, routes it through our proxy endpoint.
 * @param {string} url - The original image URL
 * @returns {string} - The proxied URL or original if not R2
 */
export const getProxiedImageUrl = (url) => {
  if (!url) return '';
  
  // Check if it's an R2 URL that needs proxying
  if (url.includes('r2.dev') || url.includes('r2.cloudflarestorage.com')) {
    // Use the proxy endpoint
    const apiBase = import.meta.env.VITE_API_URL || '';
    return `${apiBase}/api/image-proxy?url=${encodeURIComponent(url)}`;
  }
  
  // Return original URL for non-R2 images (base64, other CDNs, etc.)
  return url;
};

/**
 * Get proxied media URL for audio files from R2 storage.
 * Routes through our media-proxy endpoint to add CORS headers.
 * @param {string} url - The original audio/media URL
 * @returns {string} - The proxied URL or original if not R2
 */
export const getProxiedMediaUrl = (url) => {
  if (!url) return '';
  
  if (url.includes('r2.dev') || url.includes('r2.cloudflarestorage.com')) {
    const apiBase = import.meta.env.VITE_API_URL || '';
    return `${apiBase}/api/media-proxy?url=${encodeURIComponent(url)}`;
  }
  
  return url;
};
