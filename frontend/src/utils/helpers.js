/**
 * Parse a server datetime string as local time (no timezone conversion).
 * The server stores times as "wall clock" times (11am means 11am for the business).
 * JavaScript's new Date() can interpret ISO strings as UTC, causing a 1-hour shift
 * in timezones like IST/BST. This function parses the components directly.
 * @param {string|Date} dateStr - Server datetime string or Date object
 * @returns {Date} - Date object representing the time as-is (local)
 */
export const parseServerDate = (dateStr) => {
  if (!dateStr) return new Date(NaN);
  if (dateStr instanceof Date) return dateStr;
  
  const str = String(dateStr);
  
  // Handle Flask's HTTP date format: "Fri, 25 Apr 2025 08:00:00 GMT"
  // Strip the GMT/timezone suffix and parse components directly as local time
  const httpMatch = str.match(/\w+,\s+(\d{1,2})\s+(\w+)\s+(\d{4})\s+(\d{2}):(\d{2}):(\d{2})/);
  if (httpMatch) {
    const months = { Jan:0, Feb:1, Mar:2, Apr:3, May:4, Jun:5, Jul:6, Aug:7, Sep:8, Oct:9, Nov:10, Dec:11 };
    const day = parseInt(httpMatch[1]);
    const month = months[httpMatch[2]];
    const year = parseInt(httpMatch[3]);
    const hour = parseInt(httpMatch[4]);
    const min = parseInt(httpMatch[5]);
    const sec = parseInt(httpMatch[6]);
    if (month !== undefined) {
      return new Date(year, month, day, hour, min, sec);
    }
  }
  
  // Remove trailing Z or timezone offset — treat as local time
  const cleaned = str.replace(/[Z]$/i, '').replace(/[+-]\d{2}:\d{2}$/, '');
  
  // Parse "YYYY-MM-DDTHH:MM:SS" or "YYYY-MM-DD HH:MM:SS" (with optional fractional seconds)
  const match = cleaned.match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):?(\d{2})?/);
  if (match) {
    return new Date(
      parseInt(match[1]), parseInt(match[2]) - 1, parseInt(match[3]),
      parseInt(match[4]), parseInt(match[5]), parseInt(match[6] || 0)
    );
  }
  
  // Fallback for date-only "YYYY-MM-DD"
  const dateOnly = cleaned.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (dateOnly) {
    return new Date(parseInt(dateOnly[1]), parseInt(dateOnly[2]) - 1, parseInt(dateOnly[3]));
  }
  
  // Last resort — parse but warn
  console.warn(`[parseServerDate] Unrecognized format, using native Date(): "${str}"`);
  return new Date(str);
};

export const formatDate = (date) => {
  if (!date) return '';
  const d = parseServerDate(date);
  return d.toLocaleDateString('en-US', { 
    year: 'numeric', 
    month: 'short', 
    day: 'numeric' 
  });
};

export const formatDateTime = (date) => {
  if (!date) return '';
  const d = parseServerDate(date);
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
  const d = parseServerDate(date);
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

/**
 * Format a price or price range for display.
 * If price_max is set and greater than price, shows "€X - €Y".
 * Otherwise shows the single price.
 */
export const formatPriceRange = (price, priceMax) => {
  const min = parseFloat(price) || 0;
  const max = parseFloat(priceMax) || 0;
  if (max > min) {
    return `${formatCurrency(min)} – ${formatCurrency(max)}`;
  }
  return formatCurrency(min);
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
  if (statusLower === 'completed' || statusLower === 'confirmed' || statusLower === 'paid' || statusLower === 'quote_accepted') return 'badge-success';
  if (statusLower === 'pending' || statusLower === 'unconfirmed') return 'badge-warning';
  if (statusLower === 'cancelled' || statusLower === 'rejected') return 'badge-error';
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
