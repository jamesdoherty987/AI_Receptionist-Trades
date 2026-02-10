import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import api from '../services/api';
import { clearSensitiveData } from '../utils/security';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  // Initialize state from sessionStorage immediately to avoid flash
  const [user, setUser] = useState(() => {
    try {
      const cached = sessionStorage.getItem('authUser');
      return cached ? JSON.parse(cached) : null;
    } catch { return null; }
  });
  const [subscription, setSubscription] = useState(() => {
    try {
      const cached = sessionStorage.getItem('authSubscription');
      return cached ? JSON.parse(cached) : null;
    } catch { return null; }
  });
  const [loading, setLoading] = useState(true);
  const [initialized, setInitialized] = useState(false);

  const clearAuth = useCallback(() => {
    setUser(null);
    setSubscription(null);
    sessionStorage.removeItem('authUser');
    sessionStorage.removeItem('authSubscription');
  }, []);

  // Verify session with server. Only clears auth if server explicitly
  // says "not authenticated" — network errors don't log you out.
  const checkAuth = useCallback(async () => {
    try {
      const response = await api.get('/api/auth/me');
      if (response.data.authenticated) {
        setUser(response.data.user);
        setSubscription(response.data.subscription || null);
        sessionStorage.setItem('authUser', JSON.stringify(response.data.user));
        if (response.data.subscription) {
          sessionStorage.setItem('authSubscription', JSON.stringify(response.data.subscription));
        }
      } else {
        // Server explicitly said not authenticated — clear state
        clearAuth();
      }
    } catch (error) {
      // Network error or server down — don't wipe auth state.
      // Only clear if we got a definitive 401 response.
      if (error.response?.status === 401) {
        clearAuth();
      }
      // Otherwise keep existing sessionStorage state — user stays logged in
    } finally {
      setLoading(false);
      setInitialized(true);
    }
  }, [clearAuth]);

  // Check auth on mount and refresh subscription hourly
  useEffect(() => {
    checkAuth();
    const interval = setInterval(checkAuth, 60 * 60 * 1000);
    return () => clearInterval(interval);
  }, [checkAuth]);

  const login = async (email, password) => {
    try {
      const response = await api.post('/api/auth/login', { email, password });
      if (response.data.success) {
        const userData = response.data.user;
        setUser(userData);
        sessionStorage.setItem('authUser', JSON.stringify(userData));

        // Use subscription from login response directly — no second API call needed
        if (response.data.subscription) {
          setSubscription(response.data.subscription);
          sessionStorage.setItem('authSubscription', JSON.stringify(response.data.subscription));
        }

        return { success: true };
      }
      return { success: false, error: response.data.error || 'Login failed' };
    } catch (error) {
      let errorMessage = 'Login failed. Please try again.';
      if (error.response?.data?.error) {
        errorMessage = error.response.data.error;
      } else if (error.response?.status === 401) {
        errorMessage = 'Invalid email or password. Please check your credentials.';
      } else if (error.response?.status === 429) {
        errorMessage = 'Too many login attempts. Please wait before trying again.';
      } else if (error.response?.status === 500) {
        errorMessage = 'Server error. Please try again later.';
      } else if (error.request && !error.response) {
        errorMessage = 'Cannot connect to server. Please check your connection.';
      }
      return { success: false, error: errorMessage };
    }
  };

  const signup = async (userData) => {
    try {
      const response = await api.post('/api/auth/signup', userData);
      if (response.data.success) {
        const newUser = response.data.user;
        setUser(newUser);
        sessionStorage.setItem('authUser', JSON.stringify(newUser));

        // Build subscription from the signup response data
        if (newUser.subscription_tier) {
          const sub = {
            tier: newUser.subscription_tier,
            status: 'active',
            is_active: true,
            trial_end: newUser.trial_end || null,
            trial_days_remaining: 14,
          };
          setSubscription(sub);
          sessionStorage.setItem('authSubscription', JSON.stringify(sub));
        }

        return { success: true };
      }
      return { success: false, error: response.data.error };
    } catch (error) {
      const errorMessage = error.response?.data?.error || 'Registration failed';
      return { success: false, error: errorMessage };
    }
  };

  const logout = async () => {
    try {
      await api.post('/api/auth/logout');
    } catch (error) {
      console.error('Logout error:', error.message || error);
    } finally {
      setUser(null);
      setSubscription(null);
      clearSensitiveData();
    }
  };

  const updateProfile = async (profileData) => {
    try {
      const response = await api.put('/api/auth/profile', profileData);
      if (response.data.success) {
        setUser(response.data.user);
        sessionStorage.setItem('authUser', JSON.stringify(response.data.user));
        return { success: true };
      }
      return { success: false, error: response.data.error };
    } catch (error) {
      const errorMessage = error.response?.data?.error || 'Update failed';
      return { success: false, error: errorMessage };
    }
  };

  const changePassword = async (currentPassword, newPassword) => {
    try {
      const response = await api.post('/api/auth/change-password', {
        current_password: currentPassword,
        new_password: newPassword
      });
      if (response.data.success) {
        return { success: true };
      }
      return { success: false, error: response.data.error };
    } catch (error) {
      const errorMessage = error.response?.data?.error || 'Password change failed';
      return { success: false, error: errorMessage };
    }
  };

  // Returns true during loading to prevent false redirects
  const hasActiveSubscription = () => {
    if (!initialized || loading) return true;
    if (!subscription) return false;
    return subscription.is_active === true;
  };

  const getSubscriptionTier = () => {
    return subscription?.tier || 'none';
  };

  const getTrialDaysRemaining = () => {
    if (!subscription) return 0;
    if (subscription.trial_days_remaining !== undefined && subscription.trial_days_remaining !== null) {
      return subscription.trial_days_remaining;
    }
    if (subscription.trial_end) {
      const now = new Date();
      const end = new Date(subscription.trial_end);
      const diffMs = end - now;
      if (diffMs <= 0) return 0;
      return Math.ceil(diffMs / (1000 * 60 * 60 * 24));
    }
    return 0;
  };

  const value = {
    user,
    subscription,
    loading,
    initialized,
    isAuthenticated: !!user,
    hasActiveSubscription,
    getSubscriptionTier,
    getTrialDaysRemaining,
    login,
    signup,
    logout,
    updateProfile,
    changePassword,
    checkAuth
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

export default AuthContext;
