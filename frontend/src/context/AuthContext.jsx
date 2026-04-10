import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import api from '../services/api';
import { clearSensitiveData } from '../utils/security';
import { queryClient } from '../queryClient';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try {
      const cached = localStorage.getItem('authUser');
      return cached ? JSON.parse(cached) : null;
    } catch { return null; }
  });
  const [subscription, setSubscription] = useState(() => {
    try {
      const cached = localStorage.getItem('authSubscription');
      return cached ? JSON.parse(cached) : null;
    } catch { return null; }
  });
  const [loading, setLoading] = useState(true);
  const [initialized, setInitialized] = useState(false);

  const clearAuth = useCallback(() => {
    setUser(null);
    setSubscription(null);
    localStorage.removeItem('authUser');
    localStorage.removeItem('authSubscription');
    localStorage.removeItem('authToken');
  }, []);

  const checkAuth = useCallback(async () => {
    const token = localStorage.getItem('authToken');
    console.log('[AUTH] checkAuth called, token exists:', !!token);
    
    // Determine if this is a worker session from cached user
    let isWorkerSession = false;
    try {
      const cachedUser = localStorage.getItem('authUser');
      isWorkerSession = cachedUser ? JSON.parse(cachedUser)?.role === 'worker' : false;
    } catch {
      isWorkerSession = false;
    }
    const authEndpoint = isWorkerSession ? '/api/worker/auth/me' : '/api/auth/me';
    
    try {
      const response = await api.get(authEndpoint);
      console.log(`[AUTH] ${authEndpoint} response:`, response.data.authenticated);
      
      if (response.data.authenticated) {
        const userData = isWorkerSession 
          ? { ...response.data.user, role: 'worker' }
          : response.data.user;
        setUser(userData);
        setSubscription(isWorkerSession ? null : (response.data.subscription || null));
        localStorage.setItem('authUser', JSON.stringify(userData));
        if (!isWorkerSession && response.data.subscription) {
          localStorage.setItem('authSubscription', JSON.stringify(response.data.subscription));
        }
      } else {
        console.log('[AUTH] Server returned authenticated: false, clearing auth');
        clearAuth();
      }
    } catch (error) {
      console.log('[AUTH] checkAuth error:', error.response?.status, error.message);
      if (error.response?.status === 401) {
        clearAuth();
      }
    } finally {
      setLoading(false);
      setInitialized(true);
    }
  }, [clearAuth]);

  useEffect(() => {
    checkAuth();
    const interval = setInterval(checkAuth, 60 * 60 * 1000);
    return () => clearInterval(interval);
  }, [checkAuth]);

  const login = async (email, password) => {
    try {
      const response = await api.post('/api/auth/login', { email, password });
      if (response.data.success) {
        // CRITICAL: Clear React Query cache BEFORE setting new user
        // This prevents data leakage from previous user sessions
        queryClient.clear();
        
        const userData = response.data.user;
        setUser(userData);
        localStorage.setItem('authUser', JSON.stringify(userData));

        // Store auth token for cross-origin cookie fallback
        if (response.data.auth_token) {
          localStorage.setItem('authToken', response.data.auth_token);
        }

        if (response.data.subscription) {
          setSubscription(response.data.subscription);
          localStorage.setItem('authSubscription', JSON.stringify(response.data.subscription));
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
        errorMessage = 'Cannot connect to server. Please check your internet connection and try again.';
      }
      return { success: false, error: errorMessage };
    }
  };

  const signup = async (userData) => {
    try {
      const response = await api.post('/api/auth/signup', userData);
      if (response.data.success) {
        // CRITICAL: Clear React Query cache BEFORE setting new user
        // This prevents data leakage from any previous sessions
        queryClient.clear();
        
        const newUser = response.data.user;
        setUser(newUser);
        localStorage.setItem('authUser', JSON.stringify(newUser));

        if (response.data.auth_token) {
          localStorage.setItem('authToken', response.data.auth_token);
        }

        if (newUser.subscription_tier) {
          const sub = {
            tier: newUser.subscription_tier,
            status: newUser.subscription_tier === 'none' ? 'inactive' : 'active',
            is_active: newUser.subscription_tier !== 'none',
            trial_end: newUser.trial_end || null,
            trial_days_remaining: newUser.subscription_tier === 'trial' ? 14 : 0,
          };
          setSubscription(sub);
          localStorage.setItem('authSubscription', JSON.stringify(sub));
        } else {
          // No subscription tier means no active subscription
          const sub = {
            tier: 'none',
            status: 'inactive',
            is_active: false,
            trial_end: null,
            trial_days_remaining: 0,
          };
          setSubscription(sub);
          localStorage.setItem('authSubscription', JSON.stringify(sub));
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
    // Determine if this is a worker session to call the right endpoint
    const isWorkerSession = user?.role === 'worker';
    const logoutEndpoint = isWorkerSession ? '/api/worker/auth/logout' : '/api/auth/logout';
    try {
      await api.post(logoutEndpoint);
    } catch (error) {
      console.error('Logout error:', error.message || error);
    } finally {
      setUser(null);
      setSubscription(null);
      clearSensitiveData();
      // Clear React Query cache to prevent data leakage between users
      queryClient.clear();
    }
  };

  const updateProfile = async (profileData) => {
    try {
      const response = await api.put('/api/auth/profile', profileData);
      if (response.data.success) {
        setUser(response.data.user);
        localStorage.setItem('authUser', JSON.stringify(response.data.user));
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

  // --- Worker auth ---
  const workerLogin = async (email, password) => {
    try {
      const response = await api.post('/api/worker/auth/login', { email, password });
      if (response.data.success) {
        queryClient.clear();
        const userData = { ...response.data.user, role: 'worker' };
        setUser(userData);
        localStorage.setItem('authUser', JSON.stringify(userData));
        if (response.data.auth_token) {
          localStorage.setItem('authToken', response.data.auth_token);
        }
        // Workers don't have subscriptions
        setSubscription(null);
        localStorage.removeItem('authSubscription');
        return { success: true };
      }
      return { success: false, error: response.data.error || 'Login failed' };
    } catch (error) {
      const errorMessage = error.response?.data?.error || 'Login failed. Please try again.';
      return { success: false, error: errorMessage };
    }
  };

  const isWorker = !!user && user.role === 'worker';

  const value = {
    user,
    subscription,
    loading,
    initialized,
    isAuthenticated: !!user,
    isWorker,
    hasActiveSubscription,
    getSubscriptionTier,
    getTrialDaysRemaining,
    login,
    signup,
    logout,
    updateProfile,
    changePassword,
    checkAuth,
    workerLogin
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
