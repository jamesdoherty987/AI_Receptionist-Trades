import { BrowserRouter as Router, Routes, Route, Navigate, useParams } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClient } from './queryClient'
import { useEffect } from 'react'
import { ToastProvider } from './components/Toast'
import { AuthProvider, useAuth } from './context/AuthContext'

// Pages
import Landing from './pages/Landing'
import Login from './pages/Login'
import Signup from './pages/Signup'
import Dashboard from './pages/Dashboard'
import Settings from './pages/Settings'
import Account from './pages/Account'
import SettingsMenu from './pages/SettingsMenu'
import ForgotPassword from './pages/ForgotPassword'
import ResetPassword from './pages/ResetPassword'
import PrivacyPolicy from './pages/PrivacyPolicy'
import TermsOfService from './pages/TermsOfService'
import WorkerLogin from './pages/WorkerLogin'
import WorkerSetPassword from './pages/WorkerSetPassword'
import SetPassword from './pages/SetPassword'
import AdminPanel from './pages/AdminPanel'
import WorkerForgotPassword from './pages/WorkerForgotPassword'
import WorkerResetPassword from './pages/WorkerResetPassword'
import WorkerDashboard from './pages/WorkerDashboard'
import Blog from './pages/Blog'
import BlogPost from './pages/BlogPost'
import InstallApp from './pages/InstallApp'
import ReviewPage from './pages/ReviewPage'

// Loading component
import LoadingSpinner from './components/LoadingSpinner'

// PWA
import PWAInstallPrompt from './components/PWAInstallPrompt'
import { isStandalone } from './components/PWAInstallPrompt'

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

// Payment redirect — bypasses SPA to hit Flask backend
function PayRedirect() {
  const { id } = useParams();
  useEffect(() => {
    // Use the API base URL to reach the backend
    // In production: VITE_API_URL points to the Render backend
    // In dev: empty string means same origin
    const apiUrl = import.meta.env.VITE_API_URL || '';
    const target = `${apiUrl}/api/pay/${id}`;
    console.log('[PAY] Redirecting to:', target);
    window.location.replace(target);
  }, [id]);
  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f8fafc' }}>
      <div style={{ textAlign: 'center', padding: '2rem' }}>
        <div style={{ width: 48, height: 48, borderRadius: '50%', background: 'linear-gradient(135deg, #6366f1, #4f46e5)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 1rem', color: 'white', fontSize: '1.2rem' }}>💳</div>
        <p style={{ color: '#1e293b', fontWeight: 600, fontSize: '1.1rem', margin: '0 0 0.5rem' }}>Redirecting to payment...</p>
        <p style={{ color: '#94a3b8', fontSize: '0.85rem' }}>You'll be taken to our secure payment page.</p>
      </div>
    </div>
  );
}

function AppRoutes() {
  return (
    <Routes>
      {/* Public routes — PWA goes straight to login, browser gets landing */}
      <Route path="/" element={isStandalone() ? <Navigate to="/login" replace /> : <Landing />} />
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
      <Route 
        path="/set-password" 
        element={<SetPassword />} 
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
      <Route 
        path="/account" 
        element={
          <ProtectedRoute requireSubscription={false}>
            <Account />
          </ProtectedRoute>
        } 
      />

      {/* Public pages */}
      <Route path="/privacy" element={<PrivacyPolicy />} />
      <Route path="/terms" element={<TermsOfService />} />
      <Route path="/blog" element={<Blog />} />
      <Route path="/blog/:slug" element={<BlogPost />} />
      <Route path="/install" element={<InstallApp />} />
      <Route path="/review/:token" element={<ReviewPage />} />

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

      {/* Admin Panel — obscure route, self-authenticating */}
      <Route path="/bfy-ops" element={<AdminPanel />} />

      {/* Payment links — force full page reload to hit Flask backend */}
      <Route path="/pay/:id" element={<PayRedirect />} />

      {/* Catch all - redirect to login */}
      <Route path="*" element={<Navigate to="/login" replace />} />
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
            <PWAInstallPrompt />
          </Router>
        </AuthProvider>
      </ToastProvider>
    </QueryClientProvider>
  )
}

export default App
