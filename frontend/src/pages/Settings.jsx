import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import Header from '../components/Header';
import LoadingSpinner from '../components/LoadingSpinner';
import ImageUpload from '../components/ImageUpload';
import HelpTooltip from '../components/HelpTooltip';
import PhoneConfigModal from '../components/modals/PhoneConfigModal';
import SubscriptionManager from '../components/dashboard/SubscriptionManager';
import PaymentSetup from '../components/dashboard/PaymentSetup';
import { 
  getBusinessSettings, 
  updateBusinessSettings,
  getAIReceptionistStatus,
  toggleAIReceptionist,
  updateAISchedule,
  syncSubscription,
  deleteAccount,
  getGoogleCalendarStatus,
  connectGoogleCalendar,
  disconnectGoogleCalendar,
  syncGoogleCalendar
} from '../services/api';
import './Settings.css';

// Global flag to remove Stripe Connect from UI
const REMOVE_STRIPE_CONNECT = true;

function Settings() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { checkAuth, logout } = useAuth();
  const [searchParams] = useSearchParams();
  const [formData, setFormData] = useState({});
  const [saveMessage, setSaveMessage] = useState('');
  const [showPhoneModal, setShowPhoneModal] = useState(false);
  const [activeTab, setActiveTab] = useState('business');
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteConfirmation, setDeleteConfirmation] = useState('');
  const [deleteError, setDeleteError] = useState('');
  const [gcalConnecting, setGcalConnecting] = useState(false);
  const [gcalSyncing, setGcalSyncing] = useState(false);
  const [workerWarning, setWorkerWarning] = useState('');
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  // Bypass numbers state
  const [bypassNumbers, setBypassNumbers] = useState([]);
  const [newBypassName, setNewBypassName] = useState('');
  const [newBypassPhone, setNewBypassPhone] = useState('');
  const [editingBypassIdx, setEditingBypassIdx] = useState(null);
  const [editBypassName, setEditBypassName] = useState('');
  const [editBypassPhone, setEditBypassPhone] = useState('');
  // Flag to hide Stripe Connect component
  const hideStripeConnect = REMOVE_STRIPE_CONNECT;
  // AI schedule state
  const [showScheduleEditor, setShowScheduleEditor] = useState(false);
  const [aiSchedule, setAiSchedule] = useState({ enabled: false, slots: [], timezone: 'Europe/Dublin' });
  const [scheduleSaving, setScheduleSaving] = useState(false);
  // Per-day schedule config: { monday: { enabled: true, startHour: '9', startPeriod: 'AM', endHour: '5', endPeriod: 'PM' }, ... }
  const [daySchedules, setDaySchedules] = useState(() => {
    const days = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday'];
    const init = {};
    days.forEach(d => { init[d] = { enabled: false, startHour: '9', startPeriod: 'AM', endHour: '5', endPeriod: 'PM' }; });
    return init;
  });
  
  // Handle subscription redirect messages and tab param
  useEffect(() => {
    const subscriptionStatus = searchParams.get('subscription');
    const tabParam = searchParams.get('tab');
    let pollTimeoutId = null;
    let isCancelled = false;
    
    if (tabParam === 'subscription') {
      setActiveTab('subscription');
      window.history.replaceState({}, '', '/settings');
    }
    
    const gcalParam = searchParams.get('gcal');
    if (gcalParam === 'connected') {
      setActiveTab('business');
      queryClient.invalidateQueries({ queryKey: ['gcal-status'] });
      setSaveMessage('Google Calendar connected successfully!');
      window.history.replaceState({}, '', '/settings');
      setTimeout(() => setSaveMessage(''), 5000);
    } else if (gcalParam === 'error') {
      setActiveTab('business');
      setSaveMessage('Failed to connect Google Calendar. Please try again.');
      window.history.replaceState({}, '', '/settings');
      setTimeout(() => setSaveMessage(''), 5000);
    }
    
    if (subscriptionStatus === 'success') {
      console.log('[SUBSCRIPTION] ========== CHECKOUT SUCCESS ==========');
      setSaveMessage('Subscription activated successfully! Welcome to BookedForYou Pro.');
      setActiveTab('subscription');
      // Clear the URL parameter
      window.history.replaceState({}, '', '/settings');
      
      // Poll for subscription update (webhook may take a moment to process)
      const pollSubscription = async (attempts = 0) => {
        console.log(`[SUBSCRIPTION] Poll attempt ${attempts + 1}/15`);
        if (isCancelled) {
          console.log('[SUBSCRIPTION] Polling cancelled');
          return;
        }
        
        try {
          // Try to sync from Stripe directly (bypasses webhook delay)
          console.log('[SUBSCRIPTION] Calling syncSubscription...');
          const syncResponse = await syncSubscription();
          console.log('[SUBSCRIPTION] Sync response:', syncResponse.data);
          
          if (syncResponse.data.subscription?.tier === 'pro') {
            console.log('[SUBSCRIPTION] SUCCESS! Tier is now pro');
            // Refresh auth state and query cache
            await checkAuth();
            queryClient.invalidateQueries({ queryKey: ['subscription-status'] });
            return; // Success - stop polling
          } else {
            console.log('[SUBSCRIPTION] Tier is still:', syncResponse.data.subscription?.tier);
          }
        } catch (error) {
          console.log('[SUBSCRIPTION] Sync error:', error.response?.data || error.message);
          // Sync may fail - continue polling
        }
        
        if (isCancelled) return;
        
        // Also refresh auth state
        console.log('[SUBSCRIPTION] Calling checkAuth...');
        await checkAuth();
        queryClient.invalidateQueries({ queryKey: ['subscription-status'] });
        
        // Wait a moment for the query to refetch
        await new Promise(resolve => setTimeout(resolve, 500));
        
        if (isCancelled) return;
        
        // Get fresh subscription data from the query cache
        const cachedData = queryClient.getQueryData(['subscription-status']);
        const authSub = JSON.parse(localStorage.getItem('authSubscription') || '{}');
        
        console.log('[SUBSCRIPTION] Cached data tier:', cachedData?.tier);
        console.log('[SUBSCRIPTION] Auth session tier:', authSub.tier);
        
        // Check if subscription is now pro from either source
        const isPro = cachedData?.tier === 'pro' || authSub.tier === 'pro';
        
        if (!isPro && attempts < 15) {
          // Exponential backoff: 1s, 1.5s, 2s, 2.5s, etc. up to 15 attempts (~30s total)
          const delay = 1000 + (attempts * 500);
          console.log(`[SUBSCRIPTION] Not pro yet, retrying in ${delay}ms...`);
          pollTimeoutId = setTimeout(() => pollSubscription(attempts + 1), delay);
        } else if (isPro) {
          console.log('[SUBSCRIPTION] SUCCESS! Subscription is now pro');
          // Final refresh to ensure everything is in sync
          queryClient.invalidateQueries({ queryKey: ['subscription-status'] });
          await checkAuth();
        } else {
          console.log('[SUBSCRIPTION] FAILED: Max attempts reached, tier still not pro');
          setSaveMessage('Payment received! Your subscription is being activated. Please click the refresh button if the status doesn\'t update shortly.');
        }
      };
      pollSubscription();
      
      setTimeout(() => setSaveMessage(''), 8000);
    } else if (subscriptionStatus === 'cancelled') {
      setSaveMessage('Checkout was cancelled. You can try again when ready.');
      setActiveTab('subscription');
      window.history.replaceState({}, '', '/settings');
      setTimeout(() => setSaveMessage(''), 5000);
    } else if (subscriptionStatus === 'required') {
      setSaveMessage('Your trial has expired. Please subscribe to continue using BookedForYou.');
      setActiveTab('subscription');
      window.history.replaceState({}, '', '/settings');
    }
    
    // Cleanup function to cancel polling on unmount
    return () => {
      isCancelled = true;
      if (pollTimeoutId) {
        clearTimeout(pollTimeoutId);
      }
    };
  }, [searchParams, checkAuth, queryClient]);
  
  // Business hours breakdown state
  const [hoursConfig, setHoursConfig] = useState({
    startHour: '8',
    startPeriod: 'AM',
    endHour: '6',
    endPeriod: 'PM',
    days: {
      monday: true,
      tuesday: true,
      wednesday: true,
      thursday: true,
      friday: true,
      saturday: true,
      sunday: false
    },
    emergencyAvailable: true
  });

  const { data: settings, isLoading } = useQuery({
    queryKey: ['business-settings'],
    queryFn: async () => {
      const response = await getBusinessSettings();
      return response.data;
    },
    staleTime: 0, // Always fetch fresh data
    refetchOnMount: true,
  });

  // Parse business hours string into components
  const parseBusinessHours = (hoursString) => {
    if (!hoursString) return;
    
    // Parse format: "8 AM - 6 PM Mon-Sat (24/7 emergency available)"
    const timeMatch = hoursString.match(/(\d+)\s*(AM|PM)\s*-\s*(\d+)\s*(AM|PM)/i);
    const daysMatch = hoursString.match(/(Mon-Sat|Mon-Fri|Mon-Sun|Monday-Saturday|Monday-Friday|Monday-Sunday|Daily|[\w\s,-]+?)(?:\s*\(|$)/i);
    const emergencyMatch = hoursString.match(/emergency/i);
    
    if (timeMatch) {
      // Parse which days are selected
      const daysText = daysMatch ? daysMatch[1].trim().toLowerCase() : 'mon-sat';
      const days = {
        monday: false,
        tuesday: false,
        wednesday: false,
        thursday: false,
        friday: false,
        saturday: false,
        sunday: false
      };
      
      if (daysText.includes('daily') || daysText.includes('mon-sun') || daysText.includes('monday-sunday')) {
        Object.keys(days).forEach(day => days[day] = true);
      } else if (daysText.includes('mon-sat') || daysText.includes('monday-saturday')) {
        days.monday = days.tuesday = days.wednesday = days.thursday = days.friday = days.saturday = true;
      } else if (daysText.includes('mon-fri') || daysText.includes('monday-friday')) {
        days.monday = days.tuesday = days.wednesday = days.thursday = days.friday = true;
      } else {
        // Parse individual days
        if (daysText.includes('mon')) days.monday = true;
        if (daysText.includes('tue')) days.tuesday = true;
        if (daysText.includes('wed')) days.wednesday = true;
        if (daysText.includes('thu')) days.thursday = true;
        if (daysText.includes('fri')) days.friday = true;
        if (daysText.includes('sat')) days.saturday = true;
        if (daysText.includes('sun')) days.sunday = true;
      }
      
      setHoursConfig({
        startHour: timeMatch[1],
        startPeriod: timeMatch[2].toUpperCase(),
        endHour: timeMatch[3],
        endPeriod: timeMatch[4].toUpperCase(),
        days,
        emergencyAvailable: !!emergencyMatch
      });
    }
  };

  // Update formData when settings data changes
  useEffect(() => {
    if (settings) {
      setFormData(settings);
      setHasUnsavedChanges(false);
      if (settings.business_hours) {
        parseBusinessHours(settings.business_hours);
      }
      // Parse bypass numbers
      try {
        const parsed = typeof settings.bypass_numbers === 'string' 
          ? JSON.parse(settings.bypass_numbers || '[]') 
          : (settings.bypass_numbers || []);
        setBypassNumbers(Array.isArray(parsed) ? parsed : []);
      } catch { setBypassNumbers([]); }
    }
  }, [settings]);

  // Expose unsaved changes flag globally so Header can check it
  useEffect(() => {
    window.__settingsUnsavedChanges = hasUnsavedChanges;
    return () => { window.__settingsUnsavedChanges = false; };
  }, [hasUnsavedChanges]);

  // Warn on browser tab close / refresh with unsaved changes
  useEffect(() => {
    if (!hasUnsavedChanges) return;
    const handler = (e) => {
      e.preventDefault();
      e.returnValue = '';
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [hasUnsavedChanges]);

  // Block in-app navigation with unsaved changes via popstate (browser back button)
  useEffect(() => {
    if (!hasUnsavedChanges) return;
    const handler = (e) => {
      // Push state back so the user stays on the page
      window.history.pushState(null, '', window.location.href);
      if (!window.confirm('You have unsaved changes. Are you sure you want to leave?')) {
        return;
      }
      // User confirmed — actually navigate back
      setHasUnsavedChanges(false);
      window.history.back();
    };
    window.history.pushState(null, '', window.location.href);
    window.addEventListener('popstate', handler);
    return () => window.removeEventListener('popstate', handler);
  }, [hasUnsavedChanges]);

  const { data: aiStatus } = useQuery({
    queryKey: ['ai-status'],
    queryFn: async () => {
      const response = await getAIReceptionistStatus();
      return response.data;
    },
  });

  const { data: gcalStatus, refetch: refetchGcalStatus } = useQuery({
    queryKey: ['gcal-status'],
    queryFn: async () => {
      const response = await getGoogleCalendarStatus();
      return response.data;
    },
  });

  const saveMutation = useMutation({
    mutationFn: updateBusinessSettings,
    onSuccess: async () => {
      queryClient.invalidateQueries({ queryKey: ['business-settings'] });
      await checkAuth();
      setHasUnsavedChanges(false);
      setSaveMessage('Settings saved successfully!');
      setTimeout(() => setSaveMessage(''), 3000);
    },
    onError: (error) => {
      const errorMsg = error?.response?.data?.error || 'Error saving settings';
      setSaveMessage(errorMsg);
      setTimeout(() => setSaveMessage(''), 5000);
    },
  });

  const toggleMutation = useMutation({
    mutationFn: ({ enabled, override }) => toggleAIReceptionist(enabled, override),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['ai-status'] });
      const status = response.data?.enabled ? 'enabled' : 'disabled';
      setSaveMessage(`AI Receptionist ${status} successfully!`);
      setTimeout(() => setSaveMessage(''), 3000);
    },
    onError: (error) => {
      const errorMsg = error?.response?.data?.error || 'Failed to toggle AI Receptionist';
      setSaveMessage(errorMsg);
      setTimeout(() => setSaveMessage(''), 5000);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (confirmation) => deleteAccount(confirmation),
    onSuccess: () => {
      // Clear all auth state and redirect to home
      logout();
      navigate('/');
    },
    onError: (error) => {
      const errorMsg = error?.response?.data?.error || 'Failed to delete account';
      setDeleteError(errorMsg);
    },
  });

  const handleDeleteAccount = () => {
    setDeleteError('');
    if (deleteConfirmation.toLowerCase() !== 'delete account') {
      setDeleteError("Please type 'delete account' to confirm");
      return;
    }
    deleteMutation.mutate(deleteConfirmation);
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
    setHasUnsavedChanges(true);
  };

  const handleHoursChange = (field, value) => {
    setHoursConfig(prev => ({
      ...prev,
      [field]: value
    }));
    setHasUnsavedChanges(true);
  };

  const handleDayToggle = (day) => {
    setHoursConfig(prev => ({
      ...prev,
      days: {
        ...prev.days,
        [day]: !prev.days[day]
      }
    }));
    setHasUnsavedChanges(true);
  };

  const formatBusinessHours = () => {
    const { startHour, startPeriod, endHour, endPeriod, days, emergencyAvailable } = hoursConfig;
    
    // Format days string
    const dayNames = {
      monday: 'Mon',
      tuesday: 'Tue',
      wednesday: 'Wed',
      thursday: 'Thu',
      friday: 'Fri',
      saturday: 'Sat',
      sunday: 'Sun'
    };
    
    const selectedDays = Object.keys(days).filter(day => days[day]);
    let daysText = '';
    
    if (selectedDays.length === 7) {
      daysText = 'Daily';
    } else if (selectedDays.length === 6 && !days.sunday) {
      daysText = 'Mon-Sat';
    } else if (selectedDays.length === 5 && !days.saturday && !days.sunday) {
      daysText = 'Mon-Fri';
    } else if (selectedDays.length > 0) {
      daysText = selectedDays.map(day => dayNames[day]).join(', ');
    } else {
      daysText = 'No days selected';
    }
    
    let formatted = `${startHour} ${startPeriod} - ${endHour} ${endPeriod} ${daysText}`;
    if (emergencyAvailable) {
      formatted += ' (24/7 emergency available)';
    }
    return formatted;
  };

  const handleSubmit = (e) => {
    if (e) e.preventDefault();
    const updatedData = {
      ...formData,
      business_hours: formatBusinessHours(),
      bypass_numbers: JSON.stringify(bypassNumbers),
    };
    saveMutation.mutate(updatedData);
  };

  const handleToggleAI = () => {
    if (!aiEffectivelyOn) {
      // Turning ON
      const needsOverride = hasSchedule && aiManuallyEnabled && !isWithinSchedule;
      toggleMutation.mutate({ enabled: true, override: needsOverride });
    } else {
      // Turning OFF — also clear any override
      toggleMutation.mutate({ enabled: false, override: false });
    }
  };

  // Parse AI schedule from server
  useEffect(() => {
    if (aiStatus?.ai_schedule) {
      try {
        const parsed = typeof aiStatus.ai_schedule === 'string' 
          ? JSON.parse(aiStatus.ai_schedule) 
          : aiStatus.ai_schedule;
        if (parsed && typeof parsed === 'object') {
          setAiSchedule(parsed);
          // Convert slots to per-day config
          if (parsed.slots?.length) {
            setDaySchedules(prev => {
              const updated = { ...prev };
              Object.keys(updated).forEach(d => { updated[d] = { ...updated[d], enabled: false }; });
              parsed.slots.forEach(slot => {
                const start = minutesToTime(slot.startMinutes);
                const end = minutesToTime(slot.endMinutes);
                (slot.days || []).forEach(day => {
                  const key = day.toLowerCase();
                  if (updated[key]) {
                    updated[key] = { enabled: true, startHour: start.hour, startPeriod: start.period, endHour: end.hour, endPeriod: end.period };
                  }
                });
              });
              return updated;
            });
          } else {
            // Schedule object exists but no slots — reset
            setDaySchedules(prev => {
              const updated = { ...prev };
              Object.keys(updated).forEach(d => { updated[d] = { ...updated[d], enabled: false }; });
              return updated;
            });
          }
        }
      } catch { /* ignore parse errors */ }
    } else if (aiStatus && !aiStatus.ai_schedule) {
      // Schedule was cleared on server — reset local state
      setAiSchedule({ enabled: false, slots: [], timezone: 'Europe/Dublin' });
      setDaySchedules(prev => {
        const updated = { ...prev };
        Object.keys(updated).forEach(d => { updated[d] = { ...updated[d], enabled: false }; });
        return updated;
      });
    }
  }, [aiStatus]);

  const timeToMinutes = (hour, period) => {
    let h = parseInt(hour);
    if (period === 'PM' && h !== 12) h += 12;
    if (period === 'AM' && h === 12) h = 0;
    return h * 60;
  };

  const minutesToTime = (mins) => {
    let h = Math.floor(mins / 60);
    const period = h >= 12 ? 'PM' : 'AM';
    if (h > 12) h -= 12;
    if (h === 0) h = 12;
    return { hour: String(h), period };
  };

  const handleDayScheduleToggle = (day) => {
    setDaySchedules(prev => ({
      ...prev,
      [day]: { ...prev[day], enabled: !prev[day].enabled }
    }));
  };

  const handleDayTimeChange = (day, field, value) => {
    setDaySchedules(prev => ({
      ...prev,
      [day]: { ...prev[day], [field]: value }
    }));
  };

  // Build slots from per-day config (groups days with same times)
  const buildSlotsFromDaySchedules = () => {
    const dayOrder = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday'];
    const enabledDays = dayOrder.filter(d => daySchedules[d].enabled);
    if (enabledDays.length === 0) return [];
    
    // Group by time
    const groups = {};
    enabledDays.forEach(d => {
      const cfg = daySchedules[d];
      const key = `${cfg.startHour}-${cfg.startPeriod}-${cfg.endHour}-${cfg.endPeriod}`;
      if (!groups[key]) groups[key] = { days: [], cfg };
      groups[key].days.push(d);
    });
    
    return Object.values(groups).map(g => ({
      days: g.days,
      startMinutes: timeToMinutes(g.cfg.startHour, g.cfg.startPeriod),
      endMinutes: timeToMinutes(g.cfg.endHour, g.cfg.endPeriod),
    }));
  };

  const handleSaveSchedule = async () => {
    // Validate all enabled days have valid times
    const dayOrder = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday'];
    const enabledDays = dayOrder.filter(d => daySchedules[d].enabled);
    
    for (const d of enabledDays) {
      const cfg = daySchedules[d];
      const startMins = timeToMinutes(cfg.startHour, cfg.startPeriod);
      const endMins = timeToMinutes(cfg.endHour, cfg.endPeriod);
      if (endMins <= startMins) {
        const dayLabel = d.charAt(0).toUpperCase() + d.slice(1);
        setSaveMessage(`${dayLabel}: end time must be after start time`);
        setTimeout(() => setSaveMessage(''), 4000);
        return;
      }
    }
    
    setScheduleSaving(true);
    try {
      const slots = buildSlotsFromDaySchedules();
      const scheduleObj = { enabled: slots.length > 0, slots, timezone: 'Europe/Dublin' };
      const scheduleData = slots.length > 0 ? JSON.stringify(scheduleObj) : '';
      // Always enable AI when saving a schedule — the schedule controls on/off from here
      await updateAISchedule(true, scheduleData);
      setAiSchedule(scheduleObj);
      queryClient.invalidateQueries({ queryKey: ['ai-status'] });
      setSaveMessage('AI schedule saved!');
      setTimeout(() => setSaveMessage(''), 3000);
      setShowScheduleEditor(false);
    } catch (error) {
      const errorMsg = error?.response?.data?.error || 'Failed to save AI schedule';
      setSaveMessage(errorMsg);
      setTimeout(() => setSaveMessage(''), 5000);
    } finally {
      setScheduleSaving(false);
    }
  };

  const handleClearSchedule = async () => {
    setScheduleSaving(true);
    try {
      // Clear schedule and enable AI — back to always-on default
      await updateAISchedule(true, '');
      setAiSchedule({ enabled: false, slots: [], timezone: 'Europe/Dublin' });
      setDaySchedules(prev => {
        const updated = { ...prev };
        Object.keys(updated).forEach(d => { updated[d] = { ...updated[d], enabled: false }; });
        return updated;
      });
      queryClient.invalidateQueries({ queryKey: ['ai-status'] });
      setSaveMessage('Schedule cleared — AI is now always on');
      setTimeout(() => setSaveMessage(''), 3000);
      setShowScheduleEditor(false);
    } catch (error) {
      setSaveMessage('Failed to clear schedule');
      setTimeout(() => setSaveMessage(''), 5000);
    } finally {
      setScheduleSaving(false);
    }
  };

  const formatScheduleSummary = (schedule) => {
    if (!schedule?.slots?.length) return null;
    
    const dayOrder = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
    const dayAbbrev = { monday: 'Mon', tuesday: 'Tue', wednesday: 'Wed', thursday: 'Thu', friday: 'Fri', saturday: 'Sat', sunday: 'Sun' };
    
    return schedule.slots.map(slot => {
      const sortedDays = [...slot.days].sort((a, b) => dayOrder.indexOf(a) - dayOrder.indexOf(b));
      const start = minutesToTime(slot.startMinutes);
      const end = minutesToTime(slot.endMinutes);
      const timeStr = `${start.hour} ${start.period} – ${end.hour} ${end.period}`;
      
      const allWeekdays = ['monday','tuesday','wednesday','thursday','friday'];
      const allWeekend = ['saturday','sunday'];
      const allDays = [...allWeekdays, ...allWeekend];
      
      const isWeekdays = allWeekdays.every(d => sortedDays.includes(d)) && sortedDays.length === 5;
      const isWeekend = allWeekend.every(d => sortedDays.includes(d)) && sortedDays.length === 2;
      const isDaily = allDays.every(d => sortedDays.includes(d));
      
      const formatDayRange = (days) => {
        if (isDaily) return 'Daily';
        if (isWeekdays) return 'Weekdays';
        if (isWeekend) return 'Weekends';
        
        const indices = days.map(d => dayOrder.indexOf(d)).sort((a, b) => a - b);
        const isConsecutive = indices.every((val, i) => i === 0 || val === indices[i - 1] + 1);
        
        if (isConsecutive && days.length >= 2) {
          return `${dayAbbrev[days[0]]}–${dayAbbrev[days[days.length - 1]]}`;
        }
        return days.map(d => dayAbbrev[d]).join(', ');
      };
      
      return `${formatDayRange(sortedDays)} ${timeStr}`;
    });
  };

  // Check if we're currently within the schedule (for display purposes)
  const hasSchedule = aiSchedule.slots.length > 0 && aiSchedule.enabled;
  const isWithinSchedule = (() => {
    if (!hasSchedule) return true; // No schedule = always on
    const now = new Date();
    const dayNames = ['sunday','monday','tuesday','wednesday','thursday','friday','saturday'];
    const currentDay = dayNames[now.getDay()];
    const currentMinutes = now.getHours() * 60 + now.getMinutes();
    
    for (const slot of aiSchedule.slots) {
      if (slot.days.map(d => d.toLowerCase()).includes(currentDay)) {
        if (slot.startMinutes <= currentMinutes && currentMinutes < slot.endMinutes) {
          return true;
        }
      }
    }
    return false;
  })();

  // Determine the effective AI state for display
  const aiManuallyEnabled = aiStatus?.enabled || false;
  const aiOverrideActive = aiStatus?.ai_schedule_override || false;
  const aiEffectivelyOn = aiManuallyEnabled && (!hasSchedule || isWithinSchedule || aiOverrideActive);

  const handlePhoneConfigSuccess = (phoneNumber) => {
    // Refresh settings to show the new phone number
    queryClient.invalidateQueries({ queryKey: ['business-settings'] });
    setSaveMessage('Phone number configured successfully!');
    setTimeout(() => setSaveMessage(''), 3000);
  };

  const handleConnectGoogleCalendar = async () => {
    setGcalConnecting(true);
    try {
      const response = await connectGoogleCalendar();
      const { auth_url } = response.data;
      // Open Google OAuth in a popup
      const popup = window.open(auth_url, 'google-calendar-auth', 'width=600,height=700,scrollbars=yes');
      
      // Listen for the callback message
      const handleMessage = (event) => {
        if (event.data === 'google-calendar-connected') {
          window.removeEventListener('message', handleMessage);
          if (popup) popup.close();
          refetchGcalStatus();
          setSaveMessage('Google Calendar connected successfully!');
          setTimeout(() => setSaveMessage(''), 3000);
          setGcalConnecting(false);
        }
      };
      window.addEventListener('message', handleMessage);
      
      // Also poll in case popup message doesn't work (e.g. cross-origin)
      const pollInterval = setInterval(() => {
        if (popup && popup.closed) {
          clearInterval(pollInterval);
          window.removeEventListener('message', handleMessage);
          refetchGcalStatus();
          setGcalConnecting(false);
        }
      }, 1000);
    } catch (error) {
      const errorMsg = error?.response?.data?.error || 'Failed to start Google Calendar connection';
      setSaveMessage(errorMsg);
      setTimeout(() => setSaveMessage(''), 5000);
      setGcalConnecting(false);
    }
  };

  const handleDisconnectGoogleCalendar = async () => {
    if (!window.confirm('Are you sure you want to disconnect Google Calendar? Bookings will still be saved in the app, but will no longer sync to Google Calendar.')) {
      return;
    }
    try {
      await disconnectGoogleCalendar();
      refetchGcalStatus();
      setSaveMessage('Google Calendar disconnected');
      setTimeout(() => setSaveMessage(''), 3000);
    } catch (error) {
      setSaveMessage('Failed to disconnect Google Calendar');
      setTimeout(() => setSaveMessage(''), 5000);
    }
  };

  const handleSyncGoogleCalendar = async () => {
    setGcalSyncing(true);
    try {
      const response = await syncGoogleCalendar();
      const { message, push_created, push_updated, pull_imported, errors, jobs_without_workers } = response.data;

      // Build a friendly summary
      const parts = [];
      if (push_created) parts.push(`${push_created} added`);
      if (push_updated) parts.push(`${push_updated} updated`);
      if (pull_imported) parts.push(`${pull_imported} imported`);
      if (!push_created && !push_updated && !pull_imported) parts.push('Already in sync');
      if (errors) parts.push(`${errors} failed`);

      let summary = `✅ Sync complete — ${parts.join(', ')}`;
      setSaveMessage(summary);
      if (jobs_without_workers > 0) {
        setWorkerWarning(`${jobs_without_workers} job${jobs_without_workers > 1 ? 's' : ''} without a worker assigned`);
      } else {
        setWorkerWarning('');
      }
      setTimeout(() => { setSaveMessage(''); setWorkerWarning(''); }, jobs_without_workers > 0 ? 10000 : 6000);
    } catch (error) {
      const errorMsg = error?.response?.data?.error || 'Failed to sync calendars';
      setSaveMessage(`❌ ${errorMsg}`);
      setTimeout(() => setSaveMessage(''), 6000);
    } finally {
      setGcalSyncing(false);
    }
  };

  if (isLoading) {
    return (
      <div className="settings-page">
        <Header title="Business Settings" />
        <div className="container">
          <LoadingSpinner message="Loading settings..." />
        </div>
      </div>
    );
  }

  return (
    <div className="settings-page">
      <Header title="Business Settings" />
      <main className="settings-main">
        <div className="container">
          <div className="settings-header">
            <h1>Settings</h1>
            <p className="settings-subtitle">Manage your subscription and business information</p>
          </div>

          {/* Navigation Buttons */}
          <div className="settings-nav">
            <button 
              className="btn btn-secondary"
              onClick={() => {
                if (hasUnsavedChanges && !window.confirm('You have unsaved changes. Are you sure you want to leave?')) {
                  return;
                }
                navigate('/dashboard');
              }}
            >
              <i className="fas fa-arrow-left"></i>
              Back to Dashboard
            </button>
          </div>
          
          {/* Success/Error Message */}
          {(saveMessage || workerWarning) && (
            <div className="settings-message-row">
              {saveMessage && (
                <div className={`settings-message ${saveMessage.includes('cancelled') || saveMessage.includes('Error') || saveMessage.includes('Failed') ? 'warning' : 'success'}`}>
                  <i className={`fas ${saveMessage.includes('cancelled') || saveMessage.includes('Error') || saveMessage.includes('Failed') ? 'fa-exclamation-circle' : 'fa-check-circle'}`}></i>
                  {saveMessage}
                </div>
              )}
              {workerWarning && (
                <div className="settings-message warning">
                  <i className="fas fa-exclamation-triangle"></i>
                  {workerWarning}
                </div>
              )}
            </div>
          )}

          {/* Setup Progress Card - show only when AI phone number is not configured */}
          {settings && !settings.twilio_phone_number && (
            <div className="setup-progress-card">
              <div className="setup-progress-header">
                <div className="setup-progress-title">
                  <i className="fas fa-phone"></i>
                  <div>
                    <h3>Configure AI Phone Number</h3>
                    <p>Set up your AI receptionist phone number to start receiving calls</p>
                  </div>
                </div>
              </div>
              <div className="setup-checklist">
                <div className="setup-item">
                  <div className="setup-item-icon">
                    <i className="far fa-circle"></i>
                  </div>
                  <div className="setup-item-content">
                    <span className="setup-item-title">AI phone number</span>
                    <button 
                      className="setup-item-action"
                      onClick={() => {
                        setActiveTab('business');
                        setShowPhoneModal(true);
                      }}
                    >
                      Configure
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Settings Tabs */}
          <div className="settings-tabs">
            <button 
              className={`settings-tab ${activeTab === 'subscription' ? 'active' : ''}`}
              onClick={() => setActiveTab('subscription')}
            >
              <i className="fas fa-credit-card"></i>
              <span className="settings-tab-text">Subscription</span>
            </button>
            <button 
              className={`settings-tab ${activeTab === 'payments' ? 'active' : ''}`}
              onClick={() => setActiveTab('payments')}
            >
              <i className="fab fa-stripe-s"></i>
              <span className="settings-tab-text">Payments</span>
            </button>
            <button 
              className={`settings-tab ${activeTab === 'business' ? 'active' : ''}`}
              onClick={() => setActiveTab('business')}
            >
              <i className="fas fa-building"></i>
              <span className="settings-tab-text">Business</span>
            </button>
          </div>

          {/* Subscription Tab */}
          {activeTab === 'subscription' && (
            <div className="settings-tab-content">
              <SubscriptionManager />
            </div>
          )}

          {/* Receive Payments Tab */}
          {activeTab === 'payments' && (
            <div className="settings-tab-content">
                <PaymentSetup />
            </div>
          )}

          {/* Business Settings Tab */}
          {activeTab === 'business' && (
            <>
              {/* AI Receptionist Toggle */}
              <div className="ai-toggle-card">
                <div className="toggle-content">
                  <div className="toggle-info">
                    <h3>
                      <i className="fas fa-robot"></i>
                      AI Receptionist
                    </h3>
                    <p>
                      {!aiManuallyEnabled && hasSchedule && isWithinSchedule
                        ? 'Manually turned off — schedule paused'
                        : !aiManuallyEnabled && !hasSchedule
                          ? 'Calls are being forwarded to your fallback number'
                          : hasSchedule && !isWithinSchedule && !aiOverrideActive
                            ? 'Currently off — outside scheduled hours'
                            : hasSchedule && !isWithinSchedule && aiOverrideActive
                              ? 'AI is on — manually overriding schedule'
                              : 'AI is currently handling your calls'}
                    </p>
                  </div>
                  <label className="toggle-switch">
                    <input
                      type="checkbox"
                      checked={aiEffectivelyOn}
                      onChange={handleToggleAI}
                      disabled={toggleMutation.isPending || scheduleSaving}
                    />
                    <span className="toggle-slider"></span>
                  </label>
                </div>
                <div className="toggle-status">
                  <span className={`status-badge ${aiEffectivelyOn ? (aiOverrideActive && hasSchedule && !isWithinSchedule ? 'override' : 'active') : hasSchedule && !isWithinSchedule ? 'scheduled' : 'inactive'}`}>
                    {aiEffectivelyOn ? (aiOverrideActive && hasSchedule && !isWithinSchedule ? 'Override' : 'Active') : hasSchedule && !isWithinSchedule ? 'Scheduled' : 'Inactive'}
                  </span>
                  {hasSchedule && aiManuallyEnabled && !isWithinSchedule && !aiOverrideActive && (
                    <span className="schedule-status-hint">
                      <i className="far fa-clock"></i>
                      Outside scheduled hours
                    </span>
                  )}
                  {hasSchedule && !isWithinSchedule && aiOverrideActive && (
                    <span className="schedule-status-hint override">
                      <i className="fas fa-hand-paper"></i>
                      Manually overriding schedule
                    </span>
                  )}
                  {hasSchedule && !aiManuallyEnabled && isWithinSchedule && (
                    <span className="schedule-status-hint override">
                      <i className="fas fa-hand-paper"></i>
                      Manually turned off — schedule paused
                    </span>
                  )}
                  {hasSchedule && !aiManuallyEnabled && !isWithinSchedule && (
                    <span className="schedule-status-hint">
                      <i className="far fa-clock"></i>
                      Outside scheduled hours
                    </span>
                  )}
                  {aiStatus?.business_phone && (
                    <span className="fallback-info">
                      <i className="fas fa-phone"></i>
                      Fallback: {aiStatus.business_phone}
                    </span>
                  )}
                </div>

                {/* AI Schedule */}
                <div className="ai-schedule-section">
                  {hasSchedule && !showScheduleEditor ? (
                    <div className="ai-schedule-summary">
                      <div className="ai-schedule-summary-left">
                        <i className="far fa-clock"></i>
                        <div className="ai-schedule-summary-text">
                          <span className="ai-schedule-label">Active hours</span>
                          <span className="ai-schedule-times">
                            {formatScheduleSummary(aiSchedule)?.join(' · ')}
                          </span>
                        </div>
                      </div>
                      <div className="ai-schedule-summary-actions">
                        <button 
                          type="button" 
                          className="ai-schedule-edit-btn"
                          onClick={() => setShowScheduleEditor(true)}
                        >
                          <i className="fas fa-pen"></i>
                          Edit
                        </button>
                        <button 
                          type="button" 
                          className="ai-schedule-reset-btn-sm"
                          onClick={handleClearSchedule}
                          disabled={scheduleSaving}
                          title="Reset to Default (Always On)"
                        >
                          <i className="fas fa-undo"></i>
                        </button>
                      </div>
                    </div>
                  ) : !showScheduleEditor ? (
                    <button 
                      type="button" 
                      className="ai-schedule-set-btn"
                      onClick={() => setShowScheduleEditor(true)}
                    >
                      <i className="far fa-clock"></i>
                      Set Schedule
                    </button>
                  ) : null}

                  {showScheduleEditor && (
                    <div className="ai-schedule-editor">
                      <div className="ai-schedule-editor-header">
                        <div>
                          <span>Active hours</span>
                          <small>Set when the AI receptionist answers calls. Outside these hours, calls go to your phone.</small>
                        </div>
                      </div>

                      <div className="ai-schedule-day-list">
                        {[
                          { key: 'monday', label: 'Monday' },
                          { key: 'tuesday', label: 'Tuesday' },
                          { key: 'wednesday', label: 'Wednesday' },
                          { key: 'thursday', label: 'Thursday' },
                          { key: 'friday', label: 'Friday' },
                          { key: 'saturday', label: 'Saturday' },
                          { key: 'sunday', label: 'Sunday' }
                        ].map((day, idx) => (
                          <div key={day.key} className={`ai-schedule-day-row ${daySchedules[day.key].enabled ? 'active' : ''}`}>
                            <label className="ai-schedule-day-toggle">
                              <input
                                type="checkbox"
                                checked={daySchedules[day.key].enabled}
                                onChange={() => handleDayScheduleToggle(day.key)}
                              />
                              <span className="ai-schedule-day-name">{day.label}</span>
                            </label>
                            {daySchedules[day.key].enabled && (
                              <div className="ai-schedule-day-times">
                                <select value={daySchedules[day.key].startHour} onChange={e => handleDayTimeChange(day.key, 'startHour', e.target.value)}>
                                  {[...Array(12)].map((_, i) => (
                                    <option key={i+1} value={String(i+1)}>{i+1}</option>
                                  ))}
                                </select>
                                <select value={daySchedules[day.key].startPeriod} onChange={e => handleDayTimeChange(day.key, 'startPeriod', e.target.value)}>
                                  <option value="AM">AM</option>
                                  <option value="PM">PM</option>
                                </select>
                                <span className="ai-schedule-time-sep">–</span>
                                <select value={daySchedules[day.key].endHour} onChange={e => handleDayTimeChange(day.key, 'endHour', e.target.value)}>
                                  {[...Array(12)].map((_, i) => (
                                    <option key={i+1} value={String(i+1)}>{i+1}</option>
                                  ))}
                                </select>
                                <select value={daySchedules[day.key].endPeriod} onChange={e => handleDayTimeChange(day.key, 'endPeriod', e.target.value)}>
                                  <option value="AM">AM</option>
                                  <option value="PM">PM</option>
                                </select>
                              </div>
                            )}
                            {!daySchedules[day.key].enabled && (
                              <span className="ai-schedule-day-off">Off</span>
                            )}
                          </div>
                        ))}
                      </div>

                      <div className="ai-schedule-editor-actions">
                        {hasSchedule && (
                          <button 
                            type="button" 
                            className="ai-schedule-reset-btn"
                            onClick={handleClearSchedule}
                            disabled={scheduleSaving}
                          >
                            <i className="fas fa-undo"></i>
                            Reset to Default (Always On)
                          </button>
                        )}
                        <div className="ai-schedule-editor-actions-right">
                          <button 
                            type="button" 
                            className="btn btn-secondary btn-sm"
                            onClick={() => {
                              // Reset to server state
                              if (aiStatus?.ai_schedule) {
                                try {
                                  const parsed = typeof aiStatus.ai_schedule === 'string' ? JSON.parse(aiStatus.ai_schedule) : aiStatus.ai_schedule;
                                  const sched = parsed || { enabled: false, slots: [], timezone: 'Europe/Dublin' };
                                  setAiSchedule(sched);
                                  setDaySchedules(prev => {
                                    const updated = { ...prev };
                                    Object.keys(updated).forEach(d => { updated[d] = { ...updated[d], enabled: false }; });
                                    if (sched.slots?.length) {
                                      sched.slots.forEach(slot => {
                                        const start = minutesToTime(slot.startMinutes);
                                        const end = minutesToTime(slot.endMinutes);
                                        (slot.days || []).forEach(day => {
                                          const k = day.toLowerCase();
                                          if (updated[k]) updated[k] = { enabled: true, startHour: start.hour, startPeriod: start.period, endHour: end.hour, endPeriod: end.period };
                                        });
                                      });
                                    }
                                    return updated;
                                  });
                                } catch {
                                  setAiSchedule({ enabled: false, slots: [], timezone: 'Europe/Dublin' });
                                }
                              } else {
                                setAiSchedule({ enabled: false, slots: [], timezone: 'Europe/Dublin' });
                                setDaySchedules(prev => {
                                  const updated = { ...prev };
                                  Object.keys(updated).forEach(d => { updated[d] = { ...updated[d], enabled: false }; });
                                  return updated;
                                });
                              }
                              setShowScheduleEditor(false);
                            }}
                          >
                            Cancel
                          </button>
                          <button 
                            type="button" 
                            className="btn btn-primary btn-sm"
                            onClick={handleSaveSchedule}
                            disabled={scheduleSaving}
                          >
                            {scheduleSaving ? 'Saving...' : 'Save Schedule'}
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Bypass Numbers - Always Forward to Fallback */}
              <div className="bypass-numbers-section">
                <div className="form-section-header">
                  <i className="fas fa-phone-slash" style={{ color: '#ef4444' }}></i>
                  <h3>Always Forward Numbers</h3>
                </div>
                <p className="section-description">
                  Calls from these numbers will always be forwarded directly to your business phone, bypassing the AI receptionist entirely.
                </p>
                <small className="form-help" style={{ display: 'block', marginBottom: '0.75rem' }}>
                  Any format works — 085 123 4567, 353851234567, or +353 85 123 4567.
                </small>
                <div className="bypass-add-row">
                  <input
                    type="text"
                    placeholder="Name (e.g. John)"
                    value={newBypassName}
                    onChange={(e) => setNewBypassName(e.target.value)}
                    className="bypass-input bypass-name"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        if (newBypassPhone.trim()) {
                          const phone = newBypassPhone.trim();
                          const isDuplicate = bypassNumbers.some(b => b.phone.replace(/[\s\-\(\)\+]/g, '') === phone.replace(/[\s\-\(\)\+]/g, ''));
                          if (!isDuplicate) {
                            setBypassNumbers(prev => [...prev, { name: newBypassName.trim(), phone }]);
                            setNewBypassName('');
                            setNewBypassPhone('');
                            setHasUnsavedChanges(true);
                          }
                        }
                      }
                    }}
                  />
                  <input
                    type="tel"
                    placeholder="Phone number"
                    value={newBypassPhone}
                    onChange={(e) => setNewBypassPhone(e.target.value)}
                    className="bypass-input bypass-phone"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        if (newBypassPhone.trim()) {
                          const phone = newBypassPhone.trim();
                          const isDuplicate = bypassNumbers.some(b => b.phone.replace(/[\s\-\(\)\+]/g, '') === phone.replace(/[\s\-\(\)\+]/g, ''));
                          if (!isDuplicate) {
                            setBypassNumbers(prev => [...prev, { name: newBypassName.trim(), phone }]);
                            setNewBypassName('');
                            setNewBypassPhone('');
                            setHasUnsavedChanges(true);
                          }
                        }
                      }
                    }}
                  />
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    disabled={!newBypassPhone.trim()}
                    onClick={() => {
                      if (newBypassPhone.trim()) {
                        const phone = newBypassPhone.trim();
                        const isDuplicate = bypassNumbers.some(b => b.phone.replace(/[\s\-\(\)\+]/g, '') === phone.replace(/[\s\-\(\)\+]/g, ''));
                        if (isDuplicate) return;
                        setBypassNumbers(prev => [...prev, { name: newBypassName.trim(), phone }]);
                        setNewBypassName('');
                        setNewBypassPhone('');
                        setHasUnsavedChanges(true);
                      }
                    }}
                  >
                    <i className="fas fa-plus"></i> Add
                  </button>
                </div>
                {bypassNumbers.length > 0 && (
                  <div className="bypass-list">
                    {bypassNumbers.map((entry, idx) => (
                      <div key={idx} className="bypass-entry">
                        {editingBypassIdx === idx ? (
                          <>
                            <input
                              type="text"
                              value={editBypassName}
                              onChange={(e) => setEditBypassName(e.target.value)}
                              className="bypass-input bypass-name"
                              placeholder="Name"
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') {
                                  e.preventDefault();
                                  if (editBypassPhone.trim()) {
                                    setBypassNumbers(prev => prev.map((b, i) => i === idx ? { name: editBypassName.trim(), phone: editBypassPhone.trim() } : b));
                                    setEditingBypassIdx(null);
                                    setHasUnsavedChanges(true);
                                  }
                                } else if (e.key === 'Escape') {
                                  setEditingBypassIdx(null);
                                }
                              }}
                            />
                            <input
                              type="tel"
                              value={editBypassPhone}
                              onChange={(e) => setEditBypassPhone(e.target.value)}
                              className="bypass-input bypass-phone"
                              placeholder="Phone number"
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') {
                                  e.preventDefault();
                                  if (editBypassPhone.trim()) {
                                    setBypassNumbers(prev => prev.map((b, i) => i === idx ? { name: editBypassName.trim(), phone: editBypassPhone.trim() } : b));
                                    setEditingBypassIdx(null);
                                    setHasUnsavedChanges(true);
                                  }
                                } else if (e.key === 'Escape') {
                                  setEditingBypassIdx(null);
                                }
                              }}
                              autoFocus
                            />
                            <button
                              type="button"
                              className="bypass-action-btn bypass-save-btn"
                              title="Save"
                              disabled={!editBypassPhone.trim()}
                              onClick={() => {
                                if (editBypassPhone.trim()) {
                                  setBypassNumbers(prev => prev.map((b, i) => i === idx ? { name: editBypassName.trim(), phone: editBypassPhone.trim() } : b));
                                  setEditingBypassIdx(null);
                                  setHasUnsavedChanges(true);
                                }
                              }}
                            >
                              <i className="fas fa-check"></i>
                            </button>
                            <button
                              type="button"
                              className="bypass-action-btn bypass-cancel-btn"
                              title="Cancel"
                              onClick={() => setEditingBypassIdx(null)}
                            >
                              <i className="fas fa-times"></i>
                            </button>
                          </>
                        ) : (
                          <>
                            <div className="bypass-entry-info">
                              <span className="bypass-entry-name">{entry.name || 'No name'}</span>
                              <span className="bypass-entry-phone">{entry.phone}</span>
                            </div>
                            <div className="bypass-entry-actions">
                              <button
                                type="button"
                                className="bypass-action-btn bypass-edit-btn"
                                title="Edit"
                                onClick={() => {
                                  setEditingBypassIdx(idx);
                                  setEditBypassName(entry.name || '');
                                  setEditBypassPhone(entry.phone || '');
                                }}
                              >
                                <i className="fas fa-pen"></i>
                              </button>
                              <button
                                type="button"
                                className="bypass-action-btn bypass-remove-btn"
                                title="Remove"
                                onClick={() => {
                                  setBypassNumbers(prev => prev.filter((_, i) => i !== idx));
                                  setHasUnsavedChanges(true);
                                }}
                              >
                                <i className="fas fa-times"></i>
                              </button>
                            </div>
                          </>
                        )}
                      </div>
                    ))}
                  </div>
                )}
                {bypassNumbers.length === 0 && (
                  <p className="bypass-empty">No bypass numbers configured. All calls go through the AI receptionist.</p>
                )}
              </div>

              {/* Settings Form */}
              <div className="settings-card">
                <form onSubmit={handleSubmit}>
                  <div className="form-section">
                    <div className="form-section-header">
                      <i className="fas fa-building" style={{ color: 'var(--accent-blue)' }}></i>
                      <h3>Business Information</h3>
                    </div>
                <div className="form-grid">
                  <div className="form-group">
                    <label htmlFor="business_name">Business Name *</label>
                    <input
                      type="text"
                      id="business_name"
                      name="business_name"
                      value={formData.business_name || ''}
                      onChange={handleChange}
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="business_type">Business Type</label>
                    <input
                      type="text"
                      id="business_type"
                      name="business_type"
                      value={formData.business_type || ''}
                      onChange={handleChange}
                      placeholder="e.g., Plumbing, HVAC, Electrical"
                    />
                  </div>
                  <div className="form-group full-width">
                    <label>Business Hours</label>
                    <div className="hours-config">
                      <div className="time-row">
                        <div className="time-selector">
                          <label className="time-label">Start Time</label>
                          <div className="time-inputs">
                            <select
                              value={hoursConfig.startHour}
                              onChange={(e) => handleHoursChange('startHour', e.target.value)}
                              className="hour-select"
                            >
                              {[...Array(12)].map((_, i) => (
                                <option key={i + 1} value={i + 1}>{i + 1}</option>
                              ))}
                            </select>
                            <select
                              value={hoursConfig.startPeriod}
                              onChange={(e) => handleHoursChange('startPeriod', e.target.value)}
                              className="period-select"
                            >
                              <option value="AM">AM</option>
                              <option value="PM">PM</option>
                            </select>
                          </div>
                        </div>
                        
                        <span className="time-separator">to</span>
                        
                        <div className="time-selector">
                          <label className="time-label">End Time</label>
                          <div className="time-inputs">
                            <select
                              value={hoursConfig.endHour}
                              onChange={(e) => handleHoursChange('endHour', e.target.value)}
                              className="hour-select"
                            >
                              {[...Array(12)].map((_, i) => (
                                <option key={i + 1} value={i + 1}>{i + 1}</option>
                              ))}
                            </select>
                            <select
                              value={hoursConfig.endPeriod}
                              onChange={(e) => handleHoursChange('endPeriod', e.target.value)}
                              className="period-select"
                            >
                              <option value="AM">AM</option>
                              <option value="PM">PM</option>
                            </select>
                          </div>
                        </div>
                      </div>
                      
                      <div className="days-selector">
                        <label className="time-label">Days Open</label>
                        <div className="days-checkboxes">
                          {[
                            { key: 'monday', label: 'Mon' },
                            { key: 'tuesday', label: 'Tue' },
                            { key: 'wednesday', label: 'Wed' },
                            { key: 'thursday', label: 'Thu' },
                            { key: 'friday', label: 'Fri' },
                            { key: 'saturday', label: 'Sat' },
                            { key: 'sunday', label: 'Sun' }
                          ].map(day => (
                            <label key={day.key} className="day-checkbox">
                              <input
                                type="checkbox"
                                checked={hoursConfig.days[day.key]}
                                onChange={() => handleDayToggle(day.key)}
                              />
                              <span>{day.label}</span>
                            </label>
                          ))}
                        </div>
                      </div>
                      
                      <div className="emergency-checkbox">
                        <label>
                          <input
                            type="checkbox"
                            checked={hoursConfig.emergencyAvailable}
                            onChange={(e) => handleHoursChange('emergencyAvailable', e.target.checked)}
                          />
                          <span>24/7 emergency available</span>
                        </label>
                      </div>
                    </div>
                    <small className="form-help">
                      Preview: {formatBusinessHours()}
                    </small>
                  </div>
                  <div className="form-group">
                    <label htmlFor="business_phone">Business Phone *</label>
                    <input
                      type="tel"
                      id="business_phone"
                      name="business_phone"
                      value={formData.business_phone || ''}
                      onChange={handleChange}
                      required
                      placeholder="e.g., 085 123 4567"
                    />
                    <small className="form-help">
                      Main contact number. Also used for call transfers and when AI is disabled.
                    </small>
                  </div>
                  <div className="form-group">
                    <label htmlFor="business_email">Business Email</label>
                    <input
                      type="email"
                      id="business_email"
                      name="business_email"
                      value={formData.business_email || ''}
                      onChange={handleChange}
                    />
                  </div>
                  <div className="form-group full-width">
                    <label htmlFor="business_address">Business Address</label>
                    <input
                      type="text"
                      id="business_address"
                      name="business_address"
                      value={formData.business_address || ''}
                      onChange={handleChange}
                    />
                  </div>
                </div>
              </div>

              <div className="form-section">
                <div className="form-section-header">
                  <i className="fas fa-phone-alt" style={{ color: '#10b981' }}></i>
                  <h3>Phone Configuration</h3>
                </div>
                <p className="section-description">
                  Your assigned phone number for receiving calls. {!formData.twilio_phone_number ? 'Click the button below to select your number.' : 'This number is permanently assigned to your account.'}
                </p>
                <div className="form-grid">
                  <div className="form-group full-width">
                    <label htmlFor="twilio_phone_number">Assigned Phone Number</label>
                    <div className="phone-number-display">
                      <input
                        type="tel"
                        id="twilio_phone_number"
                        name="twilio_phone_number"
                        value={formData.twilio_phone_number || 'Not assigned'}
                        readOnly
                        disabled
                        style={{ backgroundColor: 'var(--bg-tertiary)', cursor: 'not-allowed' }}
                      />
                      {!formData.twilio_phone_number && (
                        <button
                          type="button"
                          className="btn btn-primary"
                          onClick={() => setShowPhoneModal(true)}
                          style={{ marginLeft: '1rem' }}
                        >
                          <i className="fas fa-phone"></i>
                          Configure Phone
                        </button>
                      )}
                    </div>
                    <small className="form-help">
                      {formData.twilio_phone_number 
                        ? 'This is your dedicated phone number. It cannot be changed once assigned.'
                        : 'You need to configure a phone number to receive calls.'}
                    </small>
                  </div>
                </div>
              </div>

              {/* Google Calendar Integration */}
              <div className="form-section">
                <div className="form-section-header">
                  <i className="fab fa-google" style={{ color: '#4285f4' }}></i>
                  <h3>Google Calendar</h3>
                </div>
                <p className="section-description">
                  Connect your Google Calendar to keep both calendars in sync.
                  {' '}Bookings made by the AI receptionist appear in Google Calendar, and existing Google Calendar events are imported here.
                </p>
                <div className={`gcal-status-card ${gcalStatus?.connected ? 'connected' : 'disconnected'}`}>
                  <div className="gcal-status-info">
                    <i className={`fas ${gcalStatus?.connected ? 'fa-check-circle' : 'fa-circle'} gcal-status-icon ${gcalStatus?.connected ? 'connected' : 'disconnected'}`}></i>
                    <div>
                      <div className="gcal-status-label">
                        {gcalStatus?.connected ? 'Connected' : 'Not connected'}
                      </div>
                      {gcalStatus?.connected && gcalStatus?.calendar_email && (
                        <div className="gcal-status-email">{gcalStatus.calendar_email}</div>
                      )}
                    </div>
                  </div>
                  {gcalStatus?.connected ? (
                    <div className="gcal-actions">
                      <button
                        type="button"
                        className="btn btn-primary"
                        onClick={handleSyncGoogleCalendar}
                        disabled={gcalSyncing}
                      >
                        <i className={`fas ${gcalSyncing ? 'fa-spinner fa-spin' : 'fa-sync'}`}></i>
                        {gcalSyncing ? 'Syncing...' : 'Sync Now'}
                      </button>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={handleDisconnectGoogleCalendar}
                      >
                        <i className="fas fa-unlink"></i>
                        Disconnect
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={handleConnectGoogleCalendar}
                      disabled={gcalConnecting}
                    >
                      <i className="fab fa-google"></i>
                      {gcalConnecting ? 'Connecting...' : 'Connect Google Calendar'}
                    </button>
                  )}
                </div>
                {!gcalStatus?.connected && (
                  <div className="gcal-help-text">
                    <i className="fas fa-info-circle"></i>
                    <span>Google will show a "Google hasn't verified this app" warning. Click <strong>Advanced</strong>, then <strong>Go to ai-receptionist-backend... (unsafe)</strong> to continue. This is normal for new apps awaiting verification.</span>
                  </div>
                )}
                {gcalStatus?.connected && (
                  <div className="toggle-rows" style={{ marginTop: '0.75rem' }}>
                    <div className="toggle-row">
                      <div className="toggle-row-info">
                        <div className="toggle-row-label">Invite Workers to Calendar Events</div>
                        <div className="toggle-row-desc">Workers with email addresses will receive Google Calendar invites for their assigned jobs</div>
                      </div>
                      <label className="toggle-switch">
                        <input
                          type="checkbox"
                          checked={formData.gcal_invite_workers || false}
                          onChange={(e) => { setFormData(prev => ({ ...prev, gcal_invite_workers: e.target.checked })); setHasUnsavedChanges(true); }}
                        />
                        <span className="toggle-slider"></span>
                      </label>
                    </div>
                  </div>
                )}
              </div>

              {/* Dashboard Feature Toggles */}
              <div className="form-section">
                <div className="form-section-header">
                  <i className="fas fa-sliders-h" style={{ color: '#6366f1' }}></i>
                  <h3>Dashboard Features</h3>
                </div>
                <p className="section-description">
                  Choose which features to show on your dashboard.
                </p>
                <div className="toggle-rows">
                  <div className="toggle-row">
                    <div className="toggle-row-info">
                      <div className="toggle-row-label">Finances Tab</div>
                      <div className="toggle-row-desc">Show the Finances tab on the dashboard</div>
                    </div>
                    <label className="toggle-switch">
                      <input
                        type="checkbox"
                        checked={formData.show_finances_tab !== false}
                        onChange={(e) => { setFormData(prev => ({ ...prev, show_finances_tab: e.target.checked })); setHasUnsavedChanges(true); }}
                      />
                      <span className="toggle-slider"></span>
                    </label>
                  </div>
                  <div className="toggle-row">
                    <div className="toggle-row-info">
                      <div className="toggle-row-label">Insights Tab</div>
                      <div className="toggle-row-desc">Show the Insights tab with business analytics</div>
                    </div>
                    <label className="toggle-switch">
                      <input
                        type="checkbox"
                        checked={formData.show_insights_tab !== false}
                        onChange={(e) => { setFormData(prev => ({ ...prev, show_insights_tab: e.target.checked })); setHasUnsavedChanges(true); }}
                      />
                      <span className="toggle-slider"></span>
                    </label>
                  </div>
                  <div className="toggle-row">
                    <div className="toggle-row-info">
                      <div className="toggle-row-label">Send Invoice Buttons</div>
                      <div className="toggle-row-desc">Show invoice buttons on jobs and finances</div>
                    </div>
                    <label className="toggle-switch">
                      <input
                        type="checkbox"
                        checked={formData.show_invoice_buttons !== false}
                        onChange={(e) => { setFormData(prev => ({ ...prev, show_invoice_buttons: e.target.checked })); setHasUnsavedChanges(true); }}
                      />
                      <span className="toggle-slider"></span>
                    </label>
                  </div>
                  <div className="toggle-row">
                    <div className="toggle-row-info">
                      <div className="toggle-row-label">Booking Confirmation SMS</div>
                      <div className="toggle-row-desc">Send an SMS to the customer when a booking is confirmed</div>
                    </div>
                    <label className="toggle-switch">
                      <input
                        type="checkbox"
                        checked={formData.send_confirmation_sms !== false}
                        onChange={(e) => { setFormData(prev => ({ ...prev, send_confirmation_sms: e.target.checked })); setHasUnsavedChanges(true); }}
                      />
                      <span className="toggle-slider"></span>
                    </label>
                  </div>
                  <div className="toggle-row">
                    <div className="toggle-row-info">
                      <div className="toggle-row-label">Day-Before Reminder SMS</div>
                      <div className="toggle-row-desc">Send a reminder SMS to the customer the day before their appointment</div>
                    </div>
                    <label className="toggle-switch">
                      <input
                        type="checkbox"
                        checked={formData.send_reminder_sms !== false}
                        onChange={(e) => { setFormData(prev => ({ ...prev, send_reminder_sms: e.target.checked })); setHasUnsavedChanges(true); }}
                      />
                      <span className="toggle-slider"></span>
                    </label>
                  </div>
                </div>
              </div>

              <div className="form-section">
                <div className="form-section-header">
                  <i className="fas fa-info-circle" style={{ color: '#4a90d9' }}></i>
                  <h3>Company Details for AI Receptionist</h3>
                </div>
                <p className="section-description">
                  Give your AI receptionist context about your business. This information helps it answer customer questions 
                  more accurately — things like where to park, your company history, specific policies, 
                  certifications, or any other details callers might ask about.
                </p>
                <div className="form-grid">
                  <div className="form-group full-width">
                    <label htmlFor="coverage_area">Coverage Area / Service Area <HelpTooltip text="The geographic area you serve. Your AI receptionist uses this to tell callers if you cover their location." /></label>
                    <input
                      type="text"
                      id="coverage_area"
                      name="coverage_area"
                      value={formData.coverage_area || ''}
                      onChange={handleChange}
                      placeholder="e.g., Limerick and surrounding counties, Dublin city and suburbs, Nationwide"
                    />
                    <small className="form-help">
                      Where do you provide services? The AI will use this to answer questions about your service area.
                    </small>
                  </div>
                  <div className="form-group full-width">
                    <label htmlFor="company_context">Additional Company Context &amp; Details <HelpTooltip text="Anything your AI receptionist should know — parking info, warranties, certifications, policies. Write it like you're briefing a new receptionist." /></label>
                    <textarea
                      id="company_context"
                      name="company_context"
                      value={formData.company_context || ''}
                      onChange={handleChange}
                      rows={8}
                      placeholder={"Example:\n- Free parking available in the car park behind the building\n- We've been in business since 2005, family-run company\n- All our technicians are fully insured and certified\n- We offer a 12-month warranty on all work\n- Please have the area clear before our team arrives"}
                      style={{ minHeight: '160px', resize: 'vertical', lineHeight: '1.5' }}
                    />
                    <small className="form-help">
                      This information is injected into the AI receptionist's knowledge. Write anything you'd want a real receptionist to know about your business.
                    </small>
                  </div>
                </div>
              </div>

              <div className="form-section">
                <div className="form-section-header">
                  <i className="fas fa-image" style={{ color: '#f59e0b' }}></i>
                  <h3>Business Logo</h3>
                </div>
                <div className="logo-upload-section">
                  <ImageUpload
                    value={formData.logo_url}
                    onChange={(value) => { setFormData(prev => ({ ...prev, logo_url: value })); setHasUnsavedChanges(true); }}
                    placeholder="Upload Your Company Logo"
                  />
                  <small className="form-help">
                    Upload your company logo. It will appear in the header and on invoices. Images are automatically optimized.
                  </small>
                </div>
              </div>

              {/* Fallback settings section removed - business phone is now used for everything */}
            </form>
          </div>

          {/* Danger Zone - Delete Account */}
          <div className="settings-card danger-zone">
            <div className="form-section">
              <div className="form-section-header">
                <i className="fas fa-exclamation-triangle" style={{ color: '#dc2626' }}></i>
                <h3>Danger Zone</h3>
              </div>
              <p className="section-description">
                Permanently delete your account and all associated data. This action cannot be undone.
              </p>
              <button 
                type="button"
                className="btn btn-danger"
                onClick={() => setShowDeleteModal(true)}
              >
                <i className="fas fa-trash-alt"></i>
                Delete Account
              </button>
            </div>
          </div>
          
          {/* Floating Save Button */}
          <div className="floating-save-container">
            {hasUnsavedChanges && (
              <div className="unsaved-changes-hint">
                <i className="fas fa-exclamation-circle"></i>
                You have unsaved changes
              </div>
            )}
            <button 
              type="button"
              className="btn btn-primary floating-save-btn"
              disabled={saveMutation.isPending}
              onClick={handleSubmit}
            >
              <i className="fas fa-save"></i>
              {saveMutation.isPending ? 'Saving...' : 'Save Settings'}
            </button>
          </div>
            </>
          )}
        </div>
      </main>

      {/* Phone Configuration Modal */}
      <PhoneConfigModal
        isOpen={showPhoneModal}
        onClose={() => setShowPhoneModal(false)}
        onSuccess={handlePhoneConfigSuccess}
        allowSkip={false}
      />

      {/* Delete Account Confirmation Modal */}
      {showDeleteModal && (
        <div className="modal-overlay" onClick={() => {
          setShowDeleteModal(false);
          setDeleteConfirmation('');
          setDeleteError('');
        }}>
          <div className="modal-content delete-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>
                <i className="fas fa-exclamation-triangle" style={{ color: '#dc2626', marginRight: '10px' }}></i>
                Delete Account
              </h2>
              <button className="modal-close" onClick={() => {
                setShowDeleteModal(false);
                setDeleteConfirmation('');
                setDeleteError('');
              }}>
                <i className="fas fa-times"></i>
              </button>
            </div>
            <div className="modal-body">
              <div className="delete-warning">
                <p><strong>This action is permanent and cannot be undone.</strong></p>
                <p>Deleting your account will remove:</p>
                <ul>
                  <li>All your business information</li>
                  <li>All customers and their data</li>
                  <li>All jobs and bookings</li>
                  <li>All workers</li>
                  <li>All services</li>
                  <li>Your subscription (if active)</li>
                </ul>
              </div>
              <div className="delete-confirm-input">
                <label>Type <strong>delete account</strong> to confirm:</label>
                <input
                  type="text"
                  value={deleteConfirmation}
                  onChange={(e) => setDeleteConfirmation(e.target.value)}
                  placeholder="delete account"
                  autoComplete="off"
                />
              </div>
              {deleteError && (
                <div className="delete-error">
                  <i className="fas fa-exclamation-circle"></i>
                  {deleteError}
                </div>
              )}
            </div>
            <div className="modal-footer">
              <button 
                className="btn btn-secondary" 
                onClick={() => {
                  setShowDeleteModal(false);
                  setDeleteConfirmation('');
                  setDeleteError('');
                }}
              >
                Cancel
              </button>
              <button 
                className="btn btn-danger"
                onClick={handleDeleteAccount}
                disabled={deleteMutation.isPending || deleteConfirmation.toLowerCase() !== 'delete account'}
              >
                {deleteMutation.isPending ? (
                  <>
                    <i className="fas fa-spinner fa-spin"></i>
                    Deleting...
                  </>
                ) : (
                  <>
                    <i className="fas fa-trash-alt"></i>
                    Delete My Account
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Settings;
