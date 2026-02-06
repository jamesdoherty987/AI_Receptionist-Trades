import { useQuery } from '@tanstack/react-query';
import Header from '../components/Header';
import Tabs from '../components/Tabs';
import LoadingSpinner from '../components/LoadingSpinner';
import JobsTab from '../components/dashboard/JobsTab';
import CustomersTab from '../components/dashboard/CustomersTab';
import WorkersTab from '../components/dashboard/WorkersTab';
import FinancesTab from '../components/dashboard/FinancesTab';
import CalendarTab from '../components/dashboard/CalendarTab';
import ChatTab from '../components/dashboard/ChatTab';
import ServicesTab from '../components/dashboard/ServicesTab';
import { getDashboardData } from '../services/api';
import './Dashboard.css';

function Dashboard() {
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
  const finances = dashboardData?.finances || {};

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
      content: isLoading ? <LoadingSpinner /> : <FinancesTab finances={finances} />
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
    {
      label: 'AI Chat',
      icon: 'fas fa-comments',
      content: <ChatTab />
    }
  ];

  return (
    <div className="dashboard">
      <Header />
      <main className="dashboard-main">
        <div className="container">
          <div className="dashboard-header">
            <h1>Dashboard</h1>
          </div>
          <Tabs tabs={tabs} defaultTab={0} />
        </div>
      </main>
    </div>
  );
}

export default Dashboard;
