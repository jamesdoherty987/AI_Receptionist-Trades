import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ToastProvider } from './components/Toast'
import { AuthProvider, useAuth } from './context/AuthContext'

// Pages
import Landing from './pages/Landing'
import Login from './pages/Login'
import Signup from './pages/Signup'
import Dashboard from './pages/Dashboard'
import Settings from './pages/Settings'
import SettingsMenu from './pages/SettingsMenu'

// Loading component
import LoadingSpinner from './components/LoadingSpinner'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 5 * 60 * 1000, // 5 minutes
    },
  },
})

// Protected Route component - requires authentication
function ProtectedRoute({ children, requireSubscription = false }) {
  const { isAuthenticated, hasActiveSubscription, loading, initialized } = useAuth();

  if (!initialized || loading) {
    return (
      <div style={{ 
        minHeight: '100vh', 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center',
        background: '#f8fafc'
      }}>
        <LoadingSpinner />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  // If subscription is required and user doesn't have one, redirect to settings
  if (requireSubscription && !hasActiveSubscription()) {
    return <Navigate to="/settings?subscription=required" replace />;
  }

  return children;
}

// Public Route component (redirects to dashboard if already logged in)
function PublicRoute({ children }) {
  const { isAuthenticated, loading, initialized } = useAuth();

  if (!initialized || loading) {
    return (
      <div style={{ 
        minHeight: '100vh', 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center',
        background: '#f8fafc'
      }}>
        <LoadingSpinner />
      </div>
    );
  }

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  return children;
}

function AppRoutes() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/" element={<Landing />} />
      <Route 
        path="/login" 
        element={
          <PublicRoute>
            <Login />
          </PublicRoute>
        } 
      />
      <Route 
        path="/signup" 
        element={
          <PublicRoute>
            <Signup />
          </PublicRoute>
        } 
      />

      {/* Protected routes - allow viewing without subscription but show upgrade prompts */}
      <Route 
        path="/dashboard" 
        element={
          <ProtectedRoute requireSubscription={false}>
            <Dashboard />
          </ProtectedRoute>
        } 
      />
      {/* Settings page accessible without subscription (for managing subscription) */}
      <Route 
        path="/settings" 
        element={
          <ProtectedRoute requireSubscription={false}>
            <Settings />
          </ProtectedRoute>
        } 
      />
      <Route 
        path="/settings/menu" 
        element={
          <ProtectedRoute requireSubscription={false}>
            <SettingsMenu />
          </ProtectedRoute>
        } 
      />

      {/* Catch all - redirect to landing */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <AuthProvider>
          <Router>
            <AppRoutes />
          </Router>
        </AuthProvider>
      </ToastProvider>
    </QueryClientProvider>
  )
}

export default App
