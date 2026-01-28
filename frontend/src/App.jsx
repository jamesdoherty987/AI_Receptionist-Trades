import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ToastProvider } from './components/Toast'
import Dashboard from './pages/Dashboard'
import Settings from './pages/Settings'
import SettingsMenu from './pages/SettingsMenu'
import SettingsDeveloper from './pages/SettingsDeveloper'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 5 * 60 * 1000, // 5 minutes
    },
  },
})

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <Router>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/dashboard" element={<Navigate to="/" replace />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/settings/menu" element={<SettingsMenu />} />
            <Route path="/settings/developer" element={<SettingsDeveloper />} />
          </Routes>
        </Router>
      </ToastProvider>
    </QueryClientProvider>
  )
}

export default App
