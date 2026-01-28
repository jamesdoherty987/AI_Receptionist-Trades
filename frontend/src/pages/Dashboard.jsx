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
import { getBookings, getClients, getWorkers, getFinances } from '../services/api';
import './Dashboard.css';

function Dashboard() {
  const { data: bookings, isLoading: loadingBookings } = useQuery({
    queryKey: ['bookings'],
    queryFn: async () => {
      const response = await getBookings();
      return response.data;
    },
  });

  const { data: clients, isLoading: loadingClients } = useQuery({
    queryKey: ['clients'],
    queryFn: async () => {
      const response = await getClients();
      return response.data;
    },
  });

  const { data: workers, isLoading: loadingWorkers } = useQuery({
    queryKey: ['workers'],
    queryFn: async () => {
      const response = await getWorkers();
      return response.data;
    },
  });

  const { data: finances, isLoading: loadingFinances } = useQuery({
    queryKey: ['finances'],
    queryFn: async () => {
      const response = await getFinances();
      return response.data;
    },
  });

  const tabs = [
    {
      label: 'Jobs',
      icon: 'fas fa-briefcase',
      content: loadingBookings ? <LoadingSpinner /> : <JobsTab bookings={bookings || []} />
    },
    {
      label: 'Customers',
      icon: 'fas fa-users',
      content: loadingClients ? <LoadingSpinner /> : <CustomersTab clients={clients || []} bookings={bookings || []} />
    },
    {
      label: 'Workers',
      icon: 'fas fa-hard-hat',
      content: loadingWorkers ? <LoadingSpinner /> : <WorkersTab workers={workers || []} bookings={bookings || []} />
    },
    {
      label: 'Finances',
      icon: 'fas fa-dollar-sign',
      content: loadingFinances ? <LoadingSpinner /> : <FinancesTab finances={finances || {}} />
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
