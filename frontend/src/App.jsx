import { BrowserRouter as Router, Routes, Route, Navigate, useParams } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClient } from './queryClient'
import { useEffect, lazy, Suspense } from 'react'
import { ToastProvider } from './components/Toast'
import { AuthProvider, useAuth } from './context/AuthContext'
import { IndustryProvider } from './context/IndustryContext'

// Loading component (keep eager — used as fallback)
import LoadingSpinner from './components/LoadingSpinner'

// Critical-path pages (eager — needed immediately)
import Login from './pages/Login'
import Signup from './pages/Signup'
import Landing from './pages/Landing'

// Lazy-loaded pages (code-split into separate chunks)
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Settings = lazy(() => import('./pages/Settings'))
const Account = lazy(() => import('./pages/Account'))
const SettingsMenu = lazy(() => import('./pages/SettingsMenu'))
const ForgotPassword = lazy(() => import('./pages/ForgotPassword'))
const ResetPassword = lazy(() => import('./pages/ResetPassword'))
const PrivacyPolicy = lazy(() => import('./pages/PrivacyPolicy'))
const TermsOfService = lazy(() => import('./pages/TermsOfService'))
const EmployeeLogin = lazy(() => import('./pages/EmployeeLogin'))
const EmployeeSetPassword = lazy(() => import('./pages/EmployeeSetPassword'))
const SetPassword = lazy(() => import('./pages/SetPassword'))
const AdminPanel = lazy(() => import('./pages/AdminPanel'))
const EmployeeForgotPassword = lazy(() => import('./pages/EmployeeForgotPassword'))
const EmployeeResetPassword = lazy(() => import('./pages/EmployeeResetPassword'))
const EmployeeDashboard = lazy(() => import('./pages/EmployeeDashboard'))
const Blog = lazy(() => import('./pages/Blog'))
const BlogPost = lazy(() => import('./pages/BlogPost'))
const InstallApp = lazy(() => import('./pages/InstallApp'))
const ReviewPage = lazy(() => import('./pages/ReviewPage'))
const CustomerPortal = lazy(() => import('./pages/CustomerPortal'))
const QuoteAccept = lazy(() => import('./pages/QuoteAccept'))

// PWA
import PWAInstallPrompt from './components/PWAInstallPrompt'
import { isStandalone } from './components/PWAInstallPrompt'

// Protected Route component - requires authentication
function ProtectedRoute({ children, requireSubscription = false }) {
  const { isAuthenticated, isEmployee, hasActiveSubscription, loading, initialized } = useAuth();

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

  // Employees shouldn't access owner routes
  if (isEmployee) {
    return <Navigate to="/employee/dashboard" replace />;
  }

  // If subscription is required and user doesn't have one, redirect to settings
  if (requireSubscription && !hasActiveSubscription()) {
    return <Navigate to="/settings?subscription=required" replace />;
  }

  return children;
}

// Public Route component (redirects to dashboard if already logged in)
function PublicRoute({ children }) {
  const { isAuthenticated, isEmployee, loading, initialized } = useAuth();

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
    return <Navigate to={isEmployee ? "/employee/dashboard" : "/dashboard"} replace />;
  }

  return children;
}

// Employee Protected Route - requires employee authentication
function EmployeeRoute({ children }) {
  const { isAuthenticated, isEmployee, loading, initialized } = useAuth();

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

  if (!isAuthenticated || !isEmployee) {
    return <Navigate to="/employee/login" replace />;
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
  const suspenseFallback = (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f8fafc' }}>
      <LoadingSpinner />
    </div>
  );

  return (
    <Suspense fallback={suspenseFallback}>
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
      <Route path="/portal/:token" element={<CustomerPortal />} />
      <Route path="/quote/accept/:token" element={<QuoteAccept />} />

      {/* Employee Portal routes */}
      <Route path="/employee/login" element={<EmployeeLogin />} />
      <Route path="/employee/set-password" element={<EmployeeSetPassword />} />
      <Route path="/employee/forgot-password" element={<EmployeeForgotPassword />} />
      <Route path="/employee/reset-password" element={<EmployeeResetPassword />} />
      <Route 
        path="/employee/dashboard" 
        element={
          <EmployeeRoute>
            <EmployeeDashboard />
          </EmployeeRoute>
        } 
      />

      {/* Admin Panel — obscure route, self-authenticating */}
      <Route path="/bfy-ops" element={<AdminPanel />} />

      {/* Payment links — force full page reload to hit Flask backend */}
      <Route path="/pay/:id" element={<PayRedirect />} />

      {/* Catch all - redirect to login */}
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
    </Suspense>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <AuthProvider>
          <IndustryProvider>
            <Router>
              <AppRoutes />
              <PWAInstallPrompt />
            </Router>
          </IndustryProvider>
        </AuthProvider>
      </ToastProvider>
    </QueryClientProvider>
  )
}

export default App
