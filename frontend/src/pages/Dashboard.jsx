import { useState, useEffect, useCallback, useMemo, lazy, Suspense } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import Header from '../components/Header';
import Tabs from '../components/Tabs';
import LoadingSpinner from '../components/LoadingSpinner';
import OnboardingWizard from '../components/dashboard/OnboardingWizard';
import { isStandalone } from '../components/PWAInstallPrompt';
import { getDashboardData, getBusinessSettings, getUnseenCallCount, getCompanyReviews, getLeads, getUnreadMessageCounts } from '../services/api';
import './Dashboard.css';

// Lazy-load tab components — only loaded when the tab is actually rendered
const JobsTab = lazy(() => import('../components/dashboard/JobsTab'));
const CrmTab = lazy(() => import('../components/dashboard/CrmTab'));
const WorkersTab = lazy(() => import('../components/dashboard/WorkersTab'));
const FinancesTab = lazy(() => import('../components/dashboard/FinancesTab'));
const CalendarTab = lazy(() => import('../components/dashboard/CalendarTab'));
const ChatTab = lazy(() => import('../components/dashboard/ChatTab'));
const ServicesTab = lazy(() => import('../components/dashboard/ServicesTab'));
const MaterialsTab = lazy(() => import('../components/dashboard/MaterialsTab'));
const InsightsTab = lazy(() => import('../components/dashboard/InsightsTab'));
const CallLogsTab = lazy(() => import('../components/dashboard/CallLogsTab'));

function Dashboard() {
  const { user, subscription } = useAuth();
  const location = useLocation();
  const nav = useNavigate();
  const userKey = user?.email || 'default';
  
  // Determine if user has AI features (pro plan or trial gets full access)
  const currentPlan = subscription?.plan || 'pro';
  const currentTier = subscription?.tier || 'none';
  const isSubscriptionActive = subscription?.is_active === true;
  const hasAIFeatures = currentPlan === 'pro' && isSubscriptionActive;

  // Onboarding dismissed state — initialized from localStorage, then synced with backend
  const [onboardingDismissed, setOnboardingDismissed] = useState(
    () => localStorage.getItem(`onboarding_complete_${userKey}`) === 'true'
  );

  // Re-sync when userKey changes (e.g. from 'default' to actual email)
  useEffect(() => {
    setOnboardingDismissed(localStorage.getItem(`onboarding_complete_${userKey}`) === 'true');
  }, [userKey]);

  const handleOnboardingComplete = useCallback(() => {
    localStorage.setItem(`onboarding_complete_${userKey}`, 'true');
    setOnboardingDismissed(true);
  }, [userKey]);

  // Check if user needs onboarding
  const { data: settings } = useQuery({
    queryKey: ['business-settings'],
    queryFn: async () => {
      const response = await getBusinessSettings();
      return response.data;
    },
  });

  // Determine if onboarding wizard should show — computed from settings, never flashes
  const showOnboarding = useMemo(() => {
    // Global env kill switch
    if (import.meta.env.VITE_SHOW_SETUP_WIZARD === 'false') return false;
    // Don't show until settings have loaded (prevents flash)
    if (!settings) return false;
    // Managed accounts (easy_setup=false) never see the wizard
    if (settings.easy_setup === false) return false;
    // Already completed on backend
    if (settings.setup_wizard_complete) return false;
    // Already dismissed locally
    if (onboardingDismissed) return false;
    // PWA standalone mode — skip wizard
    if (isStandalone()) return false;
    return true;
  }, [settings, onboardingDismissed]);

  // Scroll to top when dashboard loads
  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  // Use single batched API call instead of 4 separate requests
  const { data: dashboardData, isLoading } = useQuery({
    queryKey: ['dashboard'],
    queryFn: async () => {
      const response = await getDashboardData();
      return response.data.data;
    },
    staleTime: 60000,
    gcTime: 10 * 60 * 1000,
  });

  const bookings = dashboardData?.bookings || [];
  const clients = dashboardData?.clients || [];
  const workers = dashboardData?.workers || [];

  // Controlled tab state for notification navigation
  const [activeTab, setActiveTab] = useState(0);
  
  // Mobile nav menu state — shared between Header (hamburger) and Tabs (slide-out)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const handleMenuToggle = useCallback((val) => {
    setMobileMenuOpen(typeof val === 'function' ? val : val);
  }, []);

  // --- Unseen call count badge ---
  const [callsLastSeen, setCallsLastSeen] = useState(
    () => localStorage.getItem(`calls_last_seen_${userKey}`) || new Date(0).toISOString()
  );
  const [unseenCalls, setUnseenCalls] = useState(0);

  // Re-sync callsLastSeen when userKey changes (e.g. from 'default' to actual email)
  useEffect(() => {
    setCallsLastSeen(localStorage.getItem(`calls_last_seen_${userKey}`) || new Date(0).toISOString());
  }, [userKey]);

  const { data: unseenData } = useQuery({
    queryKey: ['unseen-calls', callsLastSeen],
    queryFn: async () => {
      const res = await getUnseenCallCount(callsLastSeen);
      return res.data;
    },
    refetchInterval: 60000,
  });

  useEffect(() => {
    if (unseenData) setUnseenCalls(unseenData.count || 0);
  }, [unseenData]);

  // Fetch reviews for InsightsTab widget
  const { data: reviewsData } = useQuery({
    queryKey: ['reviews'],
    queryFn: async () => (await getCompanyReviews()).data,
  });

  // Fetch leads for CRM badge (overdue follow-ups)
  const { data: leadsData } = useQuery({
    queryKey: ['leads'],
    queryFn: async () => (await getLeads()).data,
  });
  const overdueLeads = useMemo(() => {
    const now = new Date();
    return (leadsData?.leads || []).filter(l =>
      l.follow_up_date && new Date(l.follow_up_date) < now && l.stage !== 'won' && l.stage !== 'lost'
    ).length;
  }, [leadsData]);

  // Badge counts for tabs
  const jobBadges = useMemo(() => {
    const now = new Date();
    // Overdue = scheduled jobs with appointment_time in the past
    const overdue = bookings.filter(b => {
      if (b.status === 'completed' || b.status === 'cancelled') return false;
      const appt = new Date(b.appointment_time);
      return appt < now && b.status !== 'in-progress';
    }).length;
    return overdue;
  }, [bookings]);

  const unpaidCount = useMemo(() => {
    return bookings.filter(b =>
      b.status === 'completed' && b.payment_status !== 'paid'
    ).length;
  }, [bookings]);

  // Unread worker messages for Workers tab badge
  const { data: unreadMsgData } = useQuery({
    queryKey: ['unread-message-counts'],
    queryFn: async () => (await getUnreadMessageCounts()).data,
    refetchInterval: 60000,
  });
  const totalUnreadMessages = useMemo(() => {
    const counts = unreadMsgData?.counts;
    if (!counts || typeof counts !== 'object') return 0;
    return Object.values(counts).reduce((sum, c) => sum + (c || 0), 0);
  }, [unreadMsgData]);

  const tabFallback = <LoadingSpinner />;

  const tabs = useMemo(() => [
    // Day-to-day
    {
      label: 'Jobs',
      icon: 'fas fa-briefcase',
      group: 'Day-to-Day',
      badge: jobBadges,
      content: isLoading ? <LoadingSpinner /> : <Suspense fallback={tabFallback}><JobsTab bookings={bookings} showInvoiceButtons={settings?.show_invoice_buttons !== false} /></Suspense>
    },
    ...(hasAIFeatures ? [{
      label: 'Calls',
      icon: 'fas fa-phone-alt',
      group: 'Day-to-Day',
      badge: unseenCalls,
      content: <Suspense fallback={tabFallback}><CallLogsTab /></Suspense>
    }] : []),
    {
      label: 'Calendar',
      icon: 'fas fa-calendar',
      group: 'Day-to-Day',
      content: <Suspense fallback={tabFallback}><CalendarTab /></Suspense>
    },
    // Team & Clients
    {
      label: 'Workers',
      icon: 'fas fa-hard-hat',
      group: 'Team & Clients',
      badge: totalUnreadMessages,
      content: isLoading ? <LoadingSpinner /> : <Suspense fallback={tabFallback}><WorkersTab workers={workers} bookings={bookings} /></Suspense>
    },
    {
      label: 'CRM',
      icon: 'fas fa-address-book',
      group: 'Team & Clients',
      badge: overdueLeads,
      content: isLoading ? <LoadingSpinner /> : <Suspense fallback={tabFallback}><CrmTab clients={clients} bookings={bookings} /></Suspense>
    },
    // Setup
    {
      label: 'Services',
      icon: 'fas fa-concierge-bell',
      group: 'Setup',
      content: <Suspense fallback={tabFallback}><ServicesTab /></Suspense>
    },
    {
      label: 'Materials',
      icon: 'fas fa-cubes',
      group: 'Setup',
      content: <Suspense fallback={tabFallback}><MaterialsTab /></Suspense>
    },
    // Reports
    ...(settings?.show_finances_tab !== false && settings?.accounting_provider !== 'disabled' ? [{
      label: 'Finances',
      icon: 'fas fa-dollar-sign',
      group: 'Reports',
      badge: unpaidCount,
      content: <Suspense fallback={tabFallback}><FinancesTab showInvoiceButtons={settings?.show_invoice_buttons !== false} /></Suspense>
    }] : []),
    ...(settings?.show_insights_tab !== false ? [{
      label: 'Insights',
      icon: 'fas fa-chart-pie',
      group: 'Reports',
      content: isLoading ? <LoadingSpinner /> : <Suspense fallback={tabFallback}><InsightsTab bookings={bookings} clients={clients} workers={workers} reviews={reviewsData} /></Suspense>
    }] : []),
    // Dev tools
    ...(import.meta.env.VITE_ENABLE_TEST_CHAT === 'true' ? [{
      label: 'AI Chat',
      icon: 'fas fa-comments',
      group: 'Dev Tools',
      content: <Suspense fallback={tabFallback}><ChatTab /></Suspense>
    }] : [])
  ], [isLoading, bookings, clients, workers, settings, unseenCalls, hasAIFeatures, reviewsData, overdueLeads, jobBadges, totalUnreadMessages, unpaidCount]);

  // Clear unseen call badge when user views the Calls tab
  const handleTabChange = useCallback((idx) => {
    setActiveTab(idx);
    if (tabs[idx]?.label === 'Calls') {
      const now = new Date().toISOString();
      setCallsLastSeen(now);
      localStorage.setItem(`calls_last_seen_${userKey}`, now);
      setUnseenCalls(0);
    }
  }, [tabs, userKey]);

  // Mark onboarding steps as visited when user navigates to the corresponding tab
  useEffect(() => {
    if (tabs.length === 0) return;
    const label = tabs[activeTab]?.label;
    if (label === 'Services') localStorage.setItem(`services_setup_visited_${userKey}`, 'true');
    if (label === 'Workers') localStorage.setItem(`workers_setup_visited_${userKey}`, 'true');
    if (label === 'Materials') localStorage.setItem(`materials_setup_visited_${userKey}`, 'true');
  }, [activeTab, tabs, userKey]);

  // Map notification types to tab labels for navigation
  const handleNotificationNavigate = useCallback((notif) => {
    const typeToLabel = {
      'new_booking': 'Jobs',
      'cancelled': 'Jobs',
      'completed': 'Jobs',
      'rescheduled': 'Jobs',
      'time_off_request': 'Workers',
      'new_message': 'Workers',
    };
    const targetLabel = typeToLabel[notif.type];
    if (targetLabel) {
      const idx = tabs.findIndex(t => t.label === targetLabel);
      if (idx !== -1) handleTabChange(idx);
    }
  }, [tabs, handleTabChange]);

  // Handle notification navigation from other pages (e.g. Settings → Dashboard)
  useEffect(() => {
    const notif = location.state?.notificationNav;
    if (notif && tabs.length > 0) {
      handleNotificationNavigate(notif);
      // Clear the state so it doesn't re-trigger on re-renders
      nav(location.pathname, { replace: true, state: {} });
    }
  }, [location.state, tabs, handleNotificationNavigate, nav, location.pathname]);

  return (
    <div className="dashboard">
      <Header onNotificationNavigate={handleNotificationNavigate} mobileMenuOpen={mobileMenuOpen} onMenuToggle={handleMenuToggle} />
      <main className="dashboard-main">
        <div className="container">
          {/* Onboarding Wizard — only for self-service accounts that haven't completed setup */}
          {showOnboarding && (
            <OnboardingWizard onComplete={handleOnboardingComplete} />
          )}
          
          <Tabs tabs={tabs} defaultTab={0} activeTab={activeTab} onTabChange={handleTabChange} menuOpen={mobileMenuOpen} onMenuToggle={handleMenuToggle} />
        </div>
      </main>
    </div>
  );
}

export default Dashboard;
