import { createContext, useContext, useState, useEffect } from 'react';
import api from '../services/api';
import { clearSensitiveData } from '../utils/security';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [subscription, setSubscription] = useState(null);
  const [loading, setLoading] = useState(true);
  const [initialized, setInitialized] = useState(false);

  // Check if user is already logged in on mount
  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    try {
      // Check localStorage first for instant load
      const cachedUser = localStorage.getItem('authUser');
      const cachedSubscription = localStorage.getItem('authSubscription');
      if (cachedUser) {
        try {
          const parsedUser = JSON.parse(cachedUser);
          setUser(parsedUser);
          if (cachedSubscription) {
            setSubscription(JSON.parse(cachedSubscription));
          }
        } catch (e) {
          localStorage.removeItem('authUser');
          localStorage.removeItem('authSubscription');
        }
      }

      // Verify with server
      const response = await api.get('/api/auth/me');
      if (response.data.authenticated) {
        setUser(response.data.user);
        setSubscription(response.data.subscription || null);
        localStorage.setItem('authUser', JSON.stringify(response.data.user));
        if (response.data.subscription) {
          localStorage.setItem('authSubscription', JSON.stringify(response.data.subscription));
        }
      } else {
        setUser(null);
        setSubscription(null);
        localStorage.removeItem('authUser');
        localStorage.removeItem('authSubscription');
      }
    } catch (error) {
      setUser(null);
      setSubscription(null);
      localStorage.removeItem('authUser');
      localStorage.removeItem('authSubscription');
    } finally {
      setLoading(false);
      setInitialized(true);
    }
  };

  const login = async (email, password) => {
    try {
      const response = await api.post('/api/auth/login', { email, password });
      if (response.data.success) {
        setUser(response.data.user);
        localStorage.setItem('authUser', JSON.stringify(response.data.user));
        // Fetch subscription info after login
        await checkAuth();
        return { success: true };
      }
      return { success: false, error: response.data.error };
    } catch (error) {
      const errorMessage = error.response?.data?.error || 'Login failed';
      return { success: false, error: errorMessage };
    }
  };

  const signup = async (userData) => {
    try {
      const response = await api.post('/api/auth/signup', userData);
      if (response.data.success) {
        setUser(response.data.user);
        localStorage.setItem('authUser', JSON.stringify(response.data.user));
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
      // Clear all sensitive data from storage
      clearSensitiveData();
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

  // Check if subscription is active (trial or paid)
  // Returns true during loading to prevent false redirects
  const hasActiveSubscription = () => {
    if (!initialized || loading) return true; // Assume active during loading
    if (!subscription) return false;
    return subscription.is_active === true;
  };

  // Get subscription tier
  const getSubscriptionTier = () => {
    return subscription?.tier || 'none';
  };

  // Get trial days remaining
  const getTrialDaysRemaining = () => {
    return subscription?.trial_days_remaining || 0;
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

