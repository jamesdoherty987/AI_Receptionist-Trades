/**
 * Security utilities for the frontend
 * Provides input validation, sanitization, and security helpers
 */

/**
 * Sanitize a string to prevent XSS attacks
 * @param {string} input - The input string to sanitize
 * @returns {string} Sanitized string
 */
export const sanitizeString = (input) => {
  if (!input || typeof input !== 'string') return '';
  
  return input
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;')
    .trim();
};

/**
 * Validate email format
 * @param {string} email - Email to validate
 * @returns {boolean} True if valid email format
 */
export const validateEmail = (email) => {
  if (!email || typeof email !== 'string') return false;
  const pattern = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
  return pattern.test(email.toLowerCase().trim());
};

/**
 * Validate phone number format
 * @param {string} phone - Phone number to validate
 * @returns {boolean} True if valid phone format
 */
export const validatePhone = (phone) => {
  if (!phone || typeof phone !== 'string') return false;
  const cleaned = phone.replace(/[\s\-\(\)\.]/g, '');
  const pattern = /^\+?[0-9]{10,15}$/;
  return pattern.test(cleaned);
};

/**
 * Validate password strength
 * @param {string} password - Password to validate
 * @returns {{ valid: boolean, message: string }} Validation result
 */
export const validatePassword = (password) => {
  if (!password) {
    return { valid: false, message: 'Password is required' };
  }
  
  if (password.length < 8) {
    return { valid: false, message: 'Password must be at least 8 characters' };
  }
  
  if (password.length > 128) {
    return { valid: false, message: 'Password is too long' };
  }
  
  const hasUpper = /[A-Z]/.test(password);
  const hasLower = /[a-z]/.test(password);
  const hasDigit = /[0-9]/.test(password);
  
  if (!hasUpper || !hasLower || !hasDigit) {
    return { 
      valid: false, 
      message: 'Password must contain at least one uppercase letter, one lowercase letter, and one number' 
    };
  }
  
  return { valid: true, message: '' };
};

/**
 * Sanitize and validate form data
 * @param {Object} data - Form data object
 * @param {Array} requiredFields - List of required field names
 * @returns {{ valid: boolean, errors: Object, sanitized: Object }}
 */
export const validateFormData = (data, requiredFields = []) => {
  const errors = {};
  const sanitized = {};
  
  // Check required fields
  for (const field of requiredFields) {
    if (!data[field] || (typeof data[field] === 'string' && !data[field].trim())) {
      errors[field] = `${field.replace(/_/g, ' ')} is required`;
    }
  }
  
  // Sanitize all string fields
  for (const [key, value] of Object.entries(data)) {
    if (typeof value === 'string') {
      sanitized[key] = sanitizeString(value);
    } else {
      sanitized[key] = value;
    }
  }
  
  return {
    valid: Object.keys(errors).length === 0,
    errors,
    sanitized
  };
};

/**
 * Secure local storage wrapper that validates data before storage
 * @param {string} key - Storage key
 * @param {*} value - Value to store
 */
export const secureStore = (key, value) => {
  try {
    // Don't store sensitive data in localStorage
    const sensitiveKeys = ['password', 'token', 'secret', 'api_key'];
    if (sensitiveKeys.some(sensitive => key.toLowerCase().includes(sensitive))) {
      console.warn(`Security warning: Avoid storing sensitive data (${key}) in localStorage`);
    }
    
    localStorage.setItem(key, JSON.stringify(value));
  } catch (error) {
    console.error('Failed to store data:', error);
  }
};

/**
 * Secure local storage retrieval
 * @param {string} key - Storage key
 * @returns {*} Retrieved value or null
 */
export const secureRetrieve = (key) => {
  try {
    const item = localStorage.getItem(key);
    return item ? JSON.parse(item) : null;
  } catch (error) {
    console.error('Failed to retrieve data:', error);
    return null;
  }
};

/**
 * Safely clear sensitive data from storage
 */
export const clearSensitiveData = () => {
  try {
    // Clear authentication data
    localStorage.removeItem('authUser');
    localStorage.removeItem('authToken');
    sessionStorage.clear();
  } catch (error) {
    console.error('Failed to clear sensitive data:', error);
  }
};

/**
 * Rate limiter for frontend actions
 */
class ClientRateLimiter {
  constructor() {
    this.actions = new Map();
  }
  
  /**
   * Check if action is allowed
   * @param {string} action - Action identifier
   * @param {number} limit - Max actions per window
   * @param {number} windowMs - Time window in milliseconds
   * @returns {boolean} True if action is allowed
   */
  isAllowed(action, limit = 10, windowMs = 60000) {
    const now = Date.now();
    const key = action;
    
    if (!this.actions.has(key)) {
      this.actions.set(key, []);
    }
    
    const timestamps = this.actions.get(key);
    const windowStart = now - windowMs;
    
    // Remove old timestamps
    const validTimestamps = timestamps.filter(t => t > windowStart);
    
    if (validTimestamps.length >= limit) {
      return false;
    }
    
    validTimestamps.push(now);
    this.actions.set(key, validTimestamps);
    return true;
  }
  
  /**
   * Reset rate limit for an action
   * @param {string} action - Action identifier
   */
  reset(action) {
    this.actions.delete(action);
  }
}

export const rateLimiter = new ClientRateLimiter();

/**
 * Mask sensitive information for display
 * @param {string} value - Value to mask
 * @param {number} visibleChars - Number of characters to show at start
 * @returns {string} Masked value
 */
export const maskSensitiveInfo = (value, visibleChars = 4) => {
  if (!value || typeof value !== 'string') return '';
  if (value.length <= visibleChars) return '****';
  return value.substring(0, visibleChars) + '****' + value.slice(-2);
};

/**
 * Validate URL to prevent open redirect vulnerabilities
 * @param {string} url - URL to validate
 * @param {Array} allowedHosts - List of allowed host names
 * @returns {boolean} True if URL is safe
 */
export const isSafeUrl = (url, allowedHosts = []) => {
  if (!url) return false;
  
  try {
    const parsed = new URL(url, window.location.origin);
    
    // Only allow http and https protocols
    if (!['http:', 'https:'].includes(parsed.protocol)) {
      return false;
    }
    
    // If allowedHosts is empty, allow same-origin URLs
    if (allowedHosts.length === 0) {
      return parsed.origin === window.location.origin;
    }
    
    return allowedHosts.includes(parsed.hostname);
  } catch (error) {
    return false;
  }
};
