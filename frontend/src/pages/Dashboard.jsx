import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import Header from '../components/Header';
import Tabs from '../components/Tabs';
import LoadingSpinner from '../components/LoadingSpinner';
import TrialBanner from '../components/dashboard/TrialBanner';
import OnboardingWizard from '../components/dashboard/OnboardingWizard';
import JobsTab from '../components/dashboard/JobsTab';
import CustomersTab from '../components/dashboard/CustomersTab';
import WorkersTab from '../components/dashboard/WorkersTab';
import FinancesTab from '../components/dashboard/FinancesTab';
import CalendarTab from '../components/dashboard/CalendarTab';
import ChatTab from '../components/dashboard/ChatTab';
import ServicesTab from '../components/dashboard/ServicesTab';
import { getDashboardData, getBusinessSettings } from '../services/api';
import './Dashboard.css';

function Dashboard() {
  const [showOnboarding, setShowOnboarding] = useState(false);

  // Check if user needs onboarding
  const { data: settings } = useQuery({
    queryKey: ['business-settings'],
    queryFn: async () => {
      const response = await getBusinessSettings();
      return response.data;
    },
  });

  // Show onboarding wizard for new users who haven't completed setup
  useEffect(() => {
    const onboardingComplete = localStorage.getItem('onboarding_complete');
    
    // Show onboarding if:
    // 1. User hasn't dismissed/completed onboarding before
    // 2. AND settings are loaded
    // 3. AND business name or phone is missing (indicates new user)
    if (!onboardingComplete && settings !== undefined) {
      const needsSetup = !settings?.business_name || !settings?.business_phone;
      if (needsSetup) {
        setShowOnboarding(true);
      }
    }
  }, [settings]);

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
  });

  const bookings = dashboardData?.bookings || [];
  const clients = dashboardData?.clients || [];
  const workers = dashboardData?.workers || [];

  const tabs = [
    {
      label: 'Jobs',
      icon: 'fas fa-briefcase',
      content: isLoading ? <LoadingSpinner /> : <JobsTab bookings={bookings} />
    },
    {
      label: 'Customers',
      icon: 'fas fa-users',
      content: isLoading ? <LoadingSpinner /> : <CustomersTab clients={clients} bookings={bookings} />
    },
    {
      label: 'Workers',
      icon: 'fas fa-hard-hat',
      content: isLoading ? <LoadingSpinner /> : <WorkersTab workers={workers} bookings={bookings} />
    },
    {
      label: 'Finances',
      icon: 'fas fa-dollar-sign',
      content: <FinancesTab />
    },
    {
      label: 'Services',
      icon: 'fas fa-concierge-bell',
      content: <ServicesTab />
    },
    {
      label: 'Calendar',
      icon: 'fas fa-calendar',
      content: <CalendarTab />
    },
    // Test Chat tab - only show in development (controlled by VITE_ENABLE_TEST_CHAT)
    ...(import.meta.env.VITE_ENABLE_TEST_CHAT === 'true' ? [{
      label: 'AI Chat',
      icon: 'fas fa-comments',
      content: <ChatTab />
    }] : [])
  ];

  const handleOnboardingComplete = () => {
    localStorage.setItem('onboarding_complete', 'true');
    setShowOnboarding(false);
  };

  const handleOnboardingDismiss = () => {
    localStorage.setItem('onboarding_complete', 'true');
    setShowOnboarding(false);
  };

  return (
    <div className="dashboard">
      <Header />
      <main className="dashboard-main">
        <div className="container">
          <TrialBanner />
          <div className="dashboard-header">
            <h1>Dashboard</h1>
          </div>
          <Tabs tabs={tabs} defaultTab={0} />
        </div>
      </main>

      {/* Onboarding Wizard for new users */}
      {showOnboarding && (
        <OnboardingWizard 
          onComplete={handleOnboardingComplete}
          onDismiss={handleOnboardingDismiss}
        />
      )}
    </div>
  );
}

export default Dashboard;
