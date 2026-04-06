import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClient } from './queryClient'
import { ToastProvider } from './components/Toast'
import { AuthProvider, useAuth } from './context/AuthContext'

// Pages
import Landing from './pages/Landing'
import Login from './pages/Login'
import Signup from './pages/Signup'
import Dashboard from './pages/Dashboard'
import Settings from './pages/Settings'
import SettingsMenu from './pages/SettingsMenu'
import ForgotPassword from './pages/ForgotPassword'
import ResetPassword from './pages/ResetPassword'
import PrivacyPolicy from './pages/PrivacyPolicy'
import TermsOfService from './pages/TermsOfService'
import WorkerLogin from './pages/WorkerLogin'
import WorkerSetPassword from './pages/WorkerSetPassword'
import WorkerForgotPassword from './pages/WorkerForgotPassword'
import WorkerResetPassword from './pages/WorkerResetPassword'
import WorkerDashboard from './pages/WorkerDashboard'

// Loading component
import LoadingSpinner from './components/LoadingSpinner'

// Protected Route component - requires authentication
function ProtectedRoute({ children, requireSubscription = false }) {
  const { isAuthenticated, isWorker, hasActiveSubscription, loading, initialized } = useAuth();

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

  // Workers shouldn't access owner routes
  if (isWorker) {
    return <Navigate to="/worker/dashboard" replace />;
  }

  // If subscription is required and user doesn't have one, redirect to settings
  if (requireSubscription && !hasActiveSubscription()) {
    return <Navigate to="/settings?subscription=required" replace />;
  }

  return children;
}

// Public Route component (redirects to dashboard if already logged in)
function PublicRoute({ children }) {
  const { isAuthenticated, isWorker, loading, initialized } = useAuth();

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
    return <Navigate to={isWorker ? "/worker/dashboard" : "/dashboard"} replace />;
  }

  return children;
}

// Worker Protected Route - requires worker authentication
function WorkerRoute({ children }) {
  const { isAuthenticated, isWorker, loading, initialized } = useAuth();

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

  if (!isAuthenticated || !isWorker) {
    return <Navigate to="/worker/login" replace />;
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
      <Route 
        path="/forgot-password" 
        element={
          <PublicRoute>
            <ForgotPassword />
          </PublicRoute>
        } 
      />
      <Route 
        path="/reset-password" 
        element={
          <PublicRoute>
            <ResetPassword />
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

      {/* Public pages */}
      <Route path="/privacy" element={<PrivacyPolicy />} />
      <Route path="/terms" element={<TermsOfService />} />

      {/* Worker Portal routes */}
      <Route path="/worker/login" element={<WorkerLogin />} />
      <Route path="/worker/set-password" element={<WorkerSetPassword />} />
      <Route path="/worker/forgot-password" element={<WorkerForgotPassword />} />
      <Route path="/worker/reset-password" element={<WorkerResetPassword />} />
      <Route 
        path="/worker/dashboard" 
        element={
          <WorkerRoute>
            <WorkerDashboard />
          </WorkerRoute>
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
