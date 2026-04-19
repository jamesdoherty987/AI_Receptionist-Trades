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
  getGoogleCalendarStatus,
  connectGoogleCalendar,
  disconnectGoogleCalendar,
  syncGoogleCalendar,
  getAccountingStatus,
  connectXero,
  disconnectXero,
  connectQuickBooks,
  disconnectQuickBooks,
  setAccountingProvider,
  getReviewAutomationSettings,
  updateReviewAutomationSettings
} from '../services/api';
import './Settings.css';

// Global flag to remove Stripe Connect from UI
const REMOVE_STRIPE_CONNECT = false;

function Settings() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { checkAuth, subscription: authSubscription } = useAuth();
  
  // Determine if user has AI features based on plan
  const currentPlan = authSubscription?.plan || 'pro';
  const currentTier = authSubscription?.tier || 'none';
  const hasAIFeatures = currentPlan === 'pro' || currentTier === 'trial';
  const [searchParams] = useSearchParams();
  const [formData, setFormData] = useState({});
  const isManagedAccount = formData.easy_setup === false;
  const [saveMessage, setSaveMessage] = useState('');
  const [showPhoneModal, setShowPhoneModal] = useState(false);
  const [activeTab, setActiveTab] = useState('business');
  const [gcalConnecting, setGcalConnecting] = useState(false);
  const [gcalSyncing, setGcalSyncing] = useState(false);
  const [workerWarning, setWorkerWarning] = useState('');
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  // Accounting integration state
  const [acctConnecting, setAcctConnecting] = useState(false);
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
  // Per-day schedule config
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
      setActiveTab('billing');
      window.history.replaceState({}, '', '/settings');
    }
    
    const gcalParam = searchParams.get('gcal');
    if (gcalParam === 'connected') {
      setActiveTab('integrations');
      queryClient.invalidateQueries({ queryKey: ['gcal-status'] });
      setSaveMessage('Google Calendar connected successfully!');
      window.history.replaceState({}, '', '/settings');
      setTimeout(() => setSaveMessage(''), 5000);
    } else if (gcalParam === 'error') {
      setActiveTab('integrations');
      setSaveMessage('Failed to connect Google Calendar. Please try again.');
      window.history.replaceState({}, '', '/settings');
      setTimeout(() => setSaveMessage(''), 5000);
    }

    const acctParam = searchParams.get('accounting');
    if (acctParam === 'xero_connected' || acctParam === 'quickbooks_connected') {
      setActiveTab('integrations');
      queryClient.invalidateQueries({ queryKey: ['accounting-status'] });
      queryClient.invalidateQueries({ queryKey: ['business-settings'] });
      const name = acctParam === 'xero_connected' ? 'Xero' : 'QuickBooks';
      setSaveMessage(`${name} connected successfully!`);
      window.history.replaceState({}, '', '/settings');
      setTimeout(() => setSaveMessage(''), 5000);
    } else if (acctParam === 'error') {
      setActiveTab('integrations');
      setSaveMessage('Failed to connect accounting app. Please try again.');
      window.history.replaceState({}, '', '/settings');
      setTimeout(() => setSaveMessage(''), 5000);
    }
    
    if (subscriptionStatus === 'success') {
      console.log('[SUBSCRIPTION] ========== CHECKOUT SUCCESS ==========');
      setSaveMessage('Subscription activated successfully! Welcome to BookedForYou.');
      setActiveTab('billing');
      window.history.replaceState({}, '', '/settings');
      
      const pollSubscription = async (attempts = 0) => {
        console.log(`[SUBSCRIPTION] Poll attempt ${attempts + 1}/15`);
        if (isCancelled) {
          console.log('[SUBSCRIPTION] Polling cancelled');
          return;
        }
        
        try {
          console.log('[SUBSCRIPTION] Calling syncSubscription...');
          const syncResponse = await syncSubscription();
          console.log('[SUBSCRIPTION] Sync response:', syncResponse.data);
          
          if (syncResponse.data.subscription?.tier === 'pro') {
            console.log('[SUBSCRIPTION] SUCCESS! Tier is now pro');
            await checkAuth();
            queryClient.invalidateQueries({ queryKey: ['subscription-status'] });
            return;
          } else {
            console.log('[SUBSCRIPTION] Tier is still:', syncResponse.data.subscription?.tier);
          }
        } catch (error) {
          console.log('[SUBSCRIPTION] Sync error:', error.response?.data || error.message);
        }
        
        if (isCancelled) return;
        
        console.log('[SUBSCRIPTION] Calling checkAuth...');
        await checkAuth();
        queryClient.invalidateQueries({ queryKey: ['subscription-status'] });
        
        await new Promise(resolve => setTimeout(resolve, 500));
        
        if (isCancelled) return;
        
        const cachedData = queryClient.getQueryData(['subscription-status']);
        const authSub = JSON.parse(localStorage.getItem('authSubscription') || '{}');
        
        console.log('[SUBSCRIPTION] Cached data tier:', cachedData?.tier);
        console.log('[SUBSCRIPTION] Auth session tier:', authSub.tier);
        
        const isPro = cachedData?.tier === 'pro' || authSub.tier === 'pro';
        
        if (!isPro && attempts < 15) {
          const delay = 1000 + (attempts * 500);
          console.log(`[SUBSCRIPTION] Not pro yet, retrying in ${delay}ms...`);
          pollTimeoutId = setTimeout(() => pollSubscription(attempts + 1), delay);
        } else if (isPro) {
          console.log('[SUBSCRIPTION] SUCCESS! Subscription is now pro');
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
      setActiveTab('billing');
      window.history.replaceState({}, '', '/settings');
      setTimeout(() => setSaveMessage(''), 5000);
    } else if (subscriptionStatus === 'required') {
      setSaveMessage('Your trial has expired. Please subscribe to continue using BookedForYou.');
      setActiveTab('billing');
      window.history.replaceState({}, '', '/settings');
    }
    
    return () => {
      isCancelled = true;
      if (pollTimeoutId) {
        clearTimeout(pollTimeoutId);
      }
    };
  }, [searchParams, checkAuth, queryClient]);

  // Auto-open billing tab for users with no active subscription
  useEffect(() => {
    if (!authSubscription) return;
    const tier = authSubscription.tier;
    const isActive = authSubscription.is_active;
    if ((tier === 'none' || (tier === 'expired') || (!isActive && tier !== 'trial')) && activeTab === 'business') {
      const tabParam = searchParams.get('tab');
      const subscriptionParam = searchParams.get('subscription');
      if (!tabParam && !subscriptionParam) {
        setActiveTab('billing');
      }
    }
  }, [authSubscription, searchParams]);

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
    staleTime: 0,
    refetchOnMount: true,
  });

  const parseBusinessHours = (hoursString) => {
    if (!hoursString) return;
    
    const timeMatch = hoursString.match(/(\d+)\s*(AM|PM)\s*-\s*(\d+)\s*(AM|PM)/i);
    const daysMatch = hoursString.match(/(Mon-Sat|Mon-Fri|Mon-Sun|Monday-Saturday|Monday-Friday|Monday-Sunday|Daily|[\w\s,-]+?)(?:\s*\(|$)/i);
    const emergencyMatch = hoursString.match(/emergency/i);
    
    if (timeMatch) {
      const daysText = daysMatch ? daysMatch[1].trim().toLowerCase() : 'mon-sat';
      const days = {
        monday: false, tuesday: false, wednesday: false, thursday: false,
        friday: false, saturday: false, sunday: false
      };
      
      if (daysText.includes('daily') || daysText.includes('mon-sun') || daysText.includes('monday-sunday')) {
        Object.keys(days).forEach(day => days[day] = true);
      } else if (daysText.includes('mon-sat') || daysText.includes('monday-saturday')) {
        days.monday = days.tuesday = days.wednesday = days.thursday = days.friday = days.saturday = true;
      } else if (daysText.includes('mon-fri') || daysText.includes('monday-friday')) {
        days.monday = days.tuesday = days.wednesday = days.thursday = days.friday = true;
      } else {
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

  useEffect(() => {
    if (settings) {
      setFormData(settings);
      setHasUnsavedChanges(false);
      if (settings.business_hours) {
        parseBusinessHours(settings.business_hours);
      }
      try {
        const parsed = typeof settings.bypass_numbers === 'string' 
          ? JSON.parse(settings.bypass_numbers || '[]') 
          : (settings.bypass_numbers || []);
        setBypassNumbers(Array.isArray(parsed) ? parsed : []);
      } catch { setBypassNumbers([]); }
    }
  }, [settings]);

  useEffect(() => {
    window.__settingsUnsavedChanges = hasUnsavedChanges;
    return () => { window.__settingsUnsavedChanges = false; };
  }, [hasUnsavedChanges]);

  useEffect(() => {
    if (!hasUnsavedChanges) return;
    const handler = (e) => {
      e.preventDefault();
      e.returnValue = '';
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [hasUnsavedChanges]);

  useEffect(() => {
    if (!hasUnsavedChanges) return;
    const handler = (e) => {
      window.history.pushState(null, '', window.location.href);
      if (!window.confirm('You have unsaved changes. Are you sure you want to leave?')) {
        return;
      }
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

  const { data: acctStatus, refetch: refetchAcctStatus } = useQuery({
    queryKey: ['accounting-status'],
    queryFn: async () => {
      const response = await getAccountingStatus();
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

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    setHasUnsavedChanges(true);
  };

  const handleHoursChange = (field, value) => {
    setHoursConfig(prev => ({ ...prev, [field]: value }));
    setHasUnsavedChanges(true);
  };

  const handleDayToggle = (day) => {
    setHoursConfig(prev => ({
      ...prev,
      days: { ...prev.days, [day]: !prev.days[day] }
    }));
    setHasUnsavedChanges(true);
  };

  const formatBusinessHours = () => {
    const { startHour, startPeriod, endHour, endPeriod, days, emergencyAvailable } = hoursConfig;
    const dayNames = {
      monday: 'Mon', tuesday: 'Tue', wednesday: 'Wed', thursday: 'Thu',
      friday: 'Fri', saturday: 'Sat', sunday: 'Sun'
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
      const needsOverride = hasSchedule && aiManuallyEnabled && !isWithinSchedule;
      toggleMutation.mutate({ enabled: true, override: needsOverride });
    } else {
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
            setDaySchedules(prev => {
              const updated = { ...prev };
              Object.keys(updated).forEach(d => { updated[d] = { ...updated[d], enabled: false }; });
              return updated;
            });
          }
        }
      } catch { /* ignore parse errors */ }
    } else if (aiStatus && !aiStatus.ai_schedule) {
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

  const buildSlotsFromDaySchedules = () => {
    const dayOrder = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday'];
    const enabledDays = dayOrder.filter(d => daySchedules[d].enabled);
    if (enabledDays.length === 0) return [];
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

  const hasSchedule = aiSchedule.slots.length > 0 && aiSchedule.enabled;
  const isWithinSchedule = (() => {
    if (!hasSchedule) return true;
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

  const aiManuallyEnabled = aiStatus?.enabled || false;
  const aiOverrideActive = aiStatus?.ai_schedule_override || false;
  const aiEffectivelyOn = aiManuallyEnabled && (!hasSchedule || isWithinSchedule || aiOverrideActive);

  const handlePhoneConfigSuccess = (phoneNumber) => {
    queryClient.invalidateQueries({ queryKey: ['business-settings'] });
    setSaveMessage('Phone number configured successfully!');
    setTimeout(() => setSaveMessage(''), 3000);
  };

  const handleConnectGoogleCalendar = async () => {
    setGcalConnecting(true);
    try {
      const response = await connectGoogleCalendar();
      const { auth_url } = response.data;
      const popup = window.open(auth_url, 'google-calendar-auth', 'width=600,height=700,scrollbars=yes');
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
      setSaveMessage('Google Calendar disconnected.');
      setTimeout(() => setSaveMessage(''), 3000);
    } catch (error) {
      setSaveMessage('Failed to disconnect Google Calendar.');
      setTimeout(() => setSaveMessage(''), 5000);
    }
  };

  const handleSyncGoogleCalendar = async () => {
    setGcalSyncing(true);
    try {
      const response = await syncGoogleCalendar();
      const data = response.data;
      let msg = 'Google Calendar synced!';
      if (data.imported !== undefined || data.exported !== undefined) {
        msg = `Synced! ${data.imported || 0} imported, ${data.exported || 0} exported.`;
      }
      setSaveMessage(msg);
      setTimeout(() => setSaveMessage(''), 4000);
      queryClient.invalidateQueries({ queryKey: ['gcal-status'] });
    } catch (error) {
      setSaveMessage('Failed to sync Google Calendar.');
      setTimeout(() => setSaveMessage(''), 5000);
    } finally {
      setGcalSyncing(false);
    }
  };

  const handleConnectAccounting = async (provider) => {
    setAcctConnecting(true);
    try {
      let response;
      if (provider === 'xero') {
        response = await connectXero();
      } else {
        response = await connectQuickBooks();
      }
      const { auth_url } = response.data;
      if (auth_url) {
        window.location.href = auth_url;
      }
    } catch (error) {
      const errorMsg = error?.response?.data?.error || `Failed to connect ${provider}`;
      setSaveMessage(errorMsg);
      setTimeout(() => setSaveMessage(''), 5000);
      setAcctConnecting(false);
    }
  };

  const handleDisconnectAccounting = async () => {
    const provider = acctStatus?.provider;
    const name = provider === 'xero' ? 'Xero' : 'QuickBooks';
    if (!window.confirm(`Are you sure you want to disconnect ${name}?`)) return;
    try {
      if (provider === 'xero') await disconnectXero();
      else await disconnectQuickBooks();
      refetchAcctStatus();
      queryClient.invalidateQueries({ queryKey: ['business-settings'] });
      setSaveMessage(`${name} disconnected.`);
      setTimeout(() => setSaveMessage(''), 3000);
    } catch (error) {
      setSaveMessage(`Failed to disconnect ${name}.`);
      setTimeout(() => setSaveMessage(''), 5000);
    }
  };

  const handleDisableBuiltinAccounting = async () => {
    const newVal = formData.accounting_provider === 'disabled' ? null : 'disabled';
    try {
      await setAccountingProvider(newVal);
      queryClient.invalidateQueries({ queryKey: ['business-settings'] });
      setFormData(prev => ({ ...prev, accounting_provider: newVal }));
      setSaveMessage(newVal === 'disabled' ? 'Built-in accounting disabled.' : 'Built-in accounting re-enabled.');
      setTimeout(() => setSaveMessage(''), 3000);
    } catch (error) {
      setSaveMessage('Failed to update accounting setting.');
      setTimeout(() => setSaveMessage(''), 5000);
    }
  };

  if (isLoading) {
    return (
      <div className="settings-page">
        <Header title="Business Settings" />
        <LoadingSpinner />
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
            <p className="settings-subtitle">Manage your business, billing, and integrations</p>
          </div>

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

          {/* Setup Progress Card */}
          {hasAIFeatures && settings && !settings.twilio_phone_number && (
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

          {/* ═══ Settings Tabs ═══ */}
          <div className="settings-tabs">
            <button 
              className={`settings-tab ${activeTab === 'business' ? 'active' : ''}`}
              onClick={() => setActiveTab('business')}
            >
              <i className="fas fa-building"></i>
              <span className="settings-tab-text">Business</span>
            </button>
            <button 
              className={`settings-tab ${activeTab === 'integrations' ? 'active' : ''}`}
              onClick={() => setActiveTab('integrations')}
            >
              <i className="fas fa-plug"></i>
              <span className="settings-tab-text">Integrations</span>
            </button>
            <button 
              className={`settings-tab ${activeTab === 'billing' ? 'active' : ''}`}
              onClick={() => setActiveTab('billing')}
            >
              <i className="fas fa-credit-card"></i>
              <span className="settings-tab-text">Plan & Billing</span>
            </button>
          </div>

          {/* ═══ BUSINESS TAB ═══ */}
          {activeTab === 'business' && (
            <>
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
                        <input type="text" id="business_name" name="business_name" value={formData.business_name || ''} onChange={handleChange} required />
                      </div>
                      <div className="form-group">
                        <label htmlFor="business_type">Business Type</label>
                        <input type="text" id="business_type" name="business_type" value={formData.business_type || ''} onChange={handleChange} placeholder="e.g., Plumbing, HVAC, Electrical" />
                      </div>
                      <div className="form-group full-width">
                        <label>Business Hours</label>
                        <div className="hours-config">
                          <div className="time-row">
                            <div className="time-selector">
                              <label className="time-label">Start Time</label>
                              <div className="time-inputs">
                                <select value={hoursConfig.startHour} onChange={(e) => handleHoursChange('startHour', e.target.value)} className="hour-select">
                                  {[...Array(12)].map((_, i) => (<option key={i + 1} value={i + 1}>{i + 1}</option>))}
                                </select>
                                <select value={hoursConfig.startPeriod} onChange={(e) => handleHoursChange('startPeriod', e.target.value)} className="period-select">
                                  <option value="AM">AM</option>
                                  <option value="PM">PM</option>
                                </select>
                              </div>
                            </div>
                            <span className="time-separator">to</span>
                            <div className="time-selector">
                              <label className="time-label">End Time</label>
                              <div className="time-inputs">
                                <select value={hoursConfig.endHour} onChange={(e) => handleHoursChange('endHour', e.target.value)} className="hour-select">
                                  {[...Array(12)].map((_, i) => (<option key={i + 1} value={i + 1}>{i + 1}</option>))}
                                </select>
                                <select value={hoursConfig.endPeriod} onChange={(e) => handleHoursChange('endPeriod', e.target.value)} className="period-select">
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
                                { key: 'monday', label: 'Mon' }, { key: 'tuesday', label: 'Tue' },
                                { key: 'wednesday', label: 'Wed' }, { key: 'thursday', label: 'Thu' },
                                { key: 'friday', label: 'Fri' }, { key: 'saturday', label: 'Sat' },
                                { key: 'sunday', label: 'Sun' }
                              ].map(day => (
                                <label key={day.key} className="day-checkbox">
                                  <input type="checkbox" checked={hoursConfig.days[day.key]} onChange={() => handleDayToggle(day.key)} />
                                  <span>{day.label}</span>
                                </label>
                              ))}
                            </div>
                          </div>
                          <div className="emergency-checkbox">
                            <label>
                              <input type="checkbox" checked={hoursConfig.emergencyAvailable} onChange={(e) => handleHoursChange('emergencyAvailable', e.target.checked)} />
                              <span>24/7 emergency available</span>
                            </label>
                          </div>
                        </div>
                        <small className="form-help">Preview: {formatBusinessHours()}</small>
                      </div>
                      <div className="form-group">
                        <label htmlFor="business_phone">Business Phone *</label>
                        <input type="tel" id="business_phone" name="business_phone" value={formData.business_phone || ''} onChange={handleChange} required placeholder="e.g., 085 123 4567" />
                        <small className="form-help">Main contact number. Also used for call transfers and when AI is disabled.</small>
                      </div>
                      <div className="form-group">
                        <label htmlFor="business_email">Business Email</label>
                        <input type="email" id="business_email" name="business_email" value={formData.business_email || ''} onChange={handleChange} />
                      </div>
                      <div className="form-group full-width">
                        <label htmlFor="business_address">Business Address</label>
                        <input type="text" id="business_address" name="business_address" value={formData.business_address || ''} onChange={handleChange} />
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
                          <input type="tel" id="twilio_phone_number" name="twilio_phone_number" value={formData.twilio_phone_number || 'Not assigned'} readOnly disabled style={{ backgroundColor: 'var(--bg-tertiary)', cursor: 'not-allowed' }} />
                          {!formData.twilio_phone_number && (
                            <button type="button" className="btn btn-primary" onClick={() => setShowPhoneModal(true)} style={{ marginLeft: '1rem' }}>
                              <i className="fas fa-phone"></i> Configure Phone
                            </button>
                          )}
                        </div>
                        <small className="form-help">
                          {formData.twilio_phone_number ? 'This is your dedicated phone number. It cannot be changed once assigned.' : 'You need to configure a phone number to receive calls.'}
                        </small>
                      </div>
                    </div>
                  </div>

                  <div className="form-section">
                    <div className="form-section-header">
                      <i className="fas fa-info-circle" style={{ color: '#4a90d9' }}></i>
                      <h3>Company Details for AI Receptionist</h3>
                    </div>
                    <p className="section-description">
                      {isManagedAccount
                        ? 'Your AI receptionist details were configured during setup. To change the AI context, contact us.'
                        : 'Give your AI receptionist context about your business. This information helps it answer customer questions more accurately — things like where to park, your company history, specific policies, certifications, or any other details callers might ask about.'}
                    </p>
                    <div className="form-grid">
                      <div className="form-group full-width">
                        <label htmlFor="coverage_area">Coverage Area / Service Area <HelpTooltip text="The geographic area you serve. Your AI receptionist uses this to tell callers if you cover their location." /></label>
                        <input type="text" id="coverage_area" name="coverage_area" value={formData.coverage_area || ''} onChange={handleChange} placeholder="e.g., Limerick and surrounding counties, Dublin city and suburbs, Nationwide" />
                        <small className="form-help">Where do you provide services? The AI will use this to answer questions about your service area.</small>
                      </div>
                      <div className="form-group full-width">
                        <label htmlFor="company_context">Additional Company Context &amp; Details <HelpTooltip text="Anything your AI receptionist should know — parking info, warranties, certifications, policies. Write it like you're briefing a new receptionist." /></label>
                        {isManagedAccount ? (
                          <div className="managed-field-readonly">
                            <div className="managed-field-value" style={{ whiteSpace: 'pre-wrap' }}>{formData.company_context || 'Not set'}</div>
                            <a href="mailto:contact@bookedforyou.ie?subject=Update AI Receptionist Details&body=I'd like to update my AI receptionist details:" className="managed-change-link">
                              <i className="fas fa-envelope"></i> Request Change
                            </a>
                          </div>
                        ) : (
                          <textarea id="company_context" name="company_context" value={formData.company_context || ''} onChange={handleChange} rows={8}
                            placeholder={"Example:\n- Free parking available in the car park behind the building\n- We've been in business since 2005, family-run company\n- All our technicians are fully insured and certified\n- We offer a 12-month warranty on all work\n- Please have the area clear before our team arrives"}
                            style={{ minHeight: '160px', resize: 'vertical', lineHeight: '1.5' }}
                          />
                        )}
                        {!isManagedAccount && (
                          <small className="form-help">This information is injected into the AI receptionist's knowledge. Write anything you'd want a real receptionist to know about your business.</small>
                        )}
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
                      <small className="form-help">Upload your company logo. It will appear in the header and on invoices. Images are automatically optimized.</small>
                    </div>
                  </div>
                </form>
              </div>

              {/* Floating Save Button */}
              <div className="floating-save-container">
                {hasUnsavedChanges && (
                  <div className="unsaved-changes-hint">
                    <i className="fas fa-exclamation-circle"></i>
                    You have unsaved changes
                  </div>
                )}
                <button type="button" className="btn btn-primary floating-save-btn" disabled={saveMutation.isPending} onClick={handleSubmit}>
                  <i className="fas fa-save"></i>
                  {saveMutation.isPending ? 'Saving...' : 'Save Settings'}
                </button>
              </div>
            </>
          )}

          {/* ═══ INTEGRATIONS TAB ═══ */}
          {activeTab === 'integrations' && (
            <>
              {/* AI Receptionist */}
              {hasAIFeatures ? (
              <>
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
                    <input type="checkbox" checked={aiEffectivelyOn} onChange={handleToggleAI} disabled={toggleMutation.isPending || scheduleSaving} />
                    <span className="toggle-slider"></span>
                  </label>
                </div>
                <div className="toggle-status">
                  <span className={`status-badge ${aiEffectivelyOn ? (aiOverrideActive && hasSchedule && !isWithinSchedule ? 'override' : 'active') : hasSchedule && !isWithinSchedule ? 'scheduled' : 'inactive'}`}>
                    {aiEffectivelyOn ? (aiOverrideActive && hasSchedule && !isWithinSchedule ? 'Override' : 'Active') : hasSchedule && !isWithinSchedule ? 'Scheduled' : 'Inactive'}
                  </span>
                  {hasSchedule && aiManuallyEnabled && !isWithinSchedule && !aiOverrideActive && (
                    <span className="schedule-status-hint"><i className="far fa-clock"></i> Outside scheduled hours</span>
                  )}
                  {hasSchedule && !isWithinSchedule && aiOverrideActive && (
                    <span className="schedule-status-hint override"><i className="fas fa-hand-paper"></i> Manually overriding schedule</span>
                  )}
                  {hasSchedule && !aiManuallyEnabled && isWithinSchedule && (
                    <span className="schedule-status-hint override"><i className="fas fa-hand-paper"></i> Manually turned off — schedule paused</span>
                  )}
                  {hasSchedule && !aiManuallyEnabled && !isWithinSchedule && (
                    <span className="schedule-status-hint"><i className="far fa-clock"></i> Outside scheduled hours</span>
                  )}
                  {aiStatus?.business_phone && (
                    <span className="fallback-info"><i className="fas fa-phone"></i> Fallback: {aiStatus.business_phone}</span>
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
                          <span className="ai-schedule-times">{formatScheduleSummary(aiSchedule)?.join(' · ')}</span>
                        </div>
                      </div>
                      <div className="ai-schedule-summary-actions">
                        <button type="button" className="ai-schedule-edit-btn" onClick={() => setShowScheduleEditor(true)}>
                          <i className="fas fa-pen"></i> Edit
                        </button>
                        <button type="button" className="ai-schedule-reset-btn-sm" onClick={handleClearSchedule} disabled={scheduleSaving} title="Reset to Default (Always On)">
                          <i className="fas fa-undo"></i>
                        </button>
                      </div>
                    </div>
                  ) : !showScheduleEditor ? (
                    <button type="button" className="ai-schedule-set-btn" onClick={() => setShowScheduleEditor(true)}>
                      <i className="far fa-clock"></i> Set Schedule
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
                          { key: 'monday', label: 'Monday' }, { key: 'tuesday', label: 'Tuesday' },
                          { key: 'wednesday', label: 'Wednesday' }, { key: 'thursday', label: 'Thursday' },
                          { key: 'friday', label: 'Friday' }, { key: 'saturday', label: 'Saturday' },
                          { key: 'sunday', label: 'Sunday' }
                        ].map((day) => (
                          <div key={day.key} className={`ai-schedule-day-row ${daySchedules[day.key].enabled ? 'active' : ''}`}>
                            <label className="ai-schedule-day-toggle">
                              <input type="checkbox" checked={daySchedules[day.key].enabled} onChange={() => handleDayScheduleToggle(day.key)} />
                              <span className="ai-schedule-day-name">{day.label}</span>
                            </label>
                            {daySchedules[day.key].enabled && (
                              <div className="ai-schedule-day-times">
                                <select value={daySchedules[day.key].startHour} onChange={e => handleDayTimeChange(day.key, 'startHour', e.target.value)}>
                                  {[...Array(12)].map((_, i) => (<option key={i+1} value={String(i+1)}>{i+1}</option>))}
                                </select>
                                <select value={daySchedules[day.key].startPeriod} onChange={e => handleDayTimeChange(day.key, 'startPeriod', e.target.value)}>
                                  <option value="AM">AM</option><option value="PM">PM</option>
                                </select>
                                <span className="ai-schedule-time-sep">–</span>
                                <select value={daySchedules[day.key].endHour} onChange={e => handleDayTimeChange(day.key, 'endHour', e.target.value)}>
                                  {[...Array(12)].map((_, i) => (<option key={i+1} value={String(i+1)}>{i+1}</option>))}
                                </select>
                                <select value={daySchedules[day.key].endPeriod} onChange={e => handleDayTimeChange(day.key, 'endPeriod', e.target.value)}>
                                  <option value="AM">AM</option><option value="PM">PM</option>
                                </select>
                              </div>
                            )}
                            {!daySchedules[day.key].enabled && <span className="ai-schedule-day-off">Off</span>}
                          </div>
                        ))}
                      </div>
                      <div className="ai-schedule-editor-actions">
                        {hasSchedule && (
                          <button type="button" className="ai-schedule-reset-btn" onClick={handleClearSchedule} disabled={scheduleSaving}>
                            <i className="fas fa-undo"></i> Reset to Default (Always On)
                          </button>
                        )}
                        <div className="ai-schedule-editor-actions-right">
                          <button type="button" className="btn btn-secondary btn-sm" onClick={() => {
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
                          }}>Cancel</button>
                          <button type="button" className="btn btn-primary btn-sm" onClick={handleSaveSchedule} disabled={scheduleSaving}>
                            {scheduleSaving ? 'Saving...' : 'Save Schedule'}
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Bypass Numbers */}
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
                  <input type="text" placeholder="Name (e.g. John)" value={newBypassName} onChange={(e) => setNewBypassName(e.target.value)} className="bypass-input bypass-name"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        if (newBypassPhone.trim()) {
                          const phone = newBypassPhone.trim();
                          const isDuplicate = bypassNumbers.some(b => b.phone.replace(/[\s\-\(\)\+]/g, '') === phone.replace(/[\s\-\(\)\+]/g, ''));
                          if (!isDuplicate) { setBypassNumbers(prev => [...prev, { name: newBypassName.trim(), phone }]); setNewBypassName(''); setNewBypassPhone(''); setHasUnsavedChanges(true); }
                        }
                      }
                    }}
                  />
                  <input type="tel" placeholder="Phone number" value={newBypassPhone} onChange={(e) => setNewBypassPhone(e.target.value)} className="bypass-input bypass-phone"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        if (newBypassPhone.trim()) {
                          const phone = newBypassPhone.trim();
                          const isDuplicate = bypassNumbers.some(b => b.phone.replace(/[\s\-\(\)\+]/g, '') === phone.replace(/[\s\-\(\)\+]/g, ''));
                          if (!isDuplicate) { setBypassNumbers(prev => [...prev, { name: newBypassName.trim(), phone }]); setNewBypassName(''); setNewBypassPhone(''); setHasUnsavedChanges(true); }
                        }
                      }
                    }}
                  />
                  <button type="button" className="btn btn-primary btn-sm" disabled={!newBypassPhone.trim()}
                    onClick={() => {
                      if (newBypassPhone.trim()) {
                        const phone = newBypassPhone.trim();
                        const isDuplicate = bypassNumbers.some(b => b.phone.replace(/[\s\-\(\)\+]/g, '') === phone.replace(/[\s\-\(\)\+]/g, ''));
                        if (isDuplicate) return;
                        setBypassNumbers(prev => [...prev, { name: newBypassName.trim(), phone }]);
                        setNewBypassName(''); setNewBypassPhone(''); setHasUnsavedChanges(true);
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
                            <input type="text" value={editBypassName} onChange={(e) => setEditBypassName(e.target.value)} className="bypass-input bypass-name" placeholder="Name"
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') { e.preventDefault(); if (editBypassPhone.trim()) { setBypassNumbers(prev => prev.map((b, i) => i === idx ? { name: editBypassName.trim(), phone: editBypassPhone.trim() } : b)); setEditingBypassIdx(null); setHasUnsavedChanges(true); } }
                                else if (e.key === 'Escape') { setEditingBypassIdx(null); }
                              }}
                            />
                            <input type="tel" value={editBypassPhone} onChange={(e) => setEditBypassPhone(e.target.value)} className="bypass-input bypass-phone" placeholder="Phone number" autoFocus
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') { e.preventDefault(); if (editBypassPhone.trim()) { setBypassNumbers(prev => prev.map((b, i) => i === idx ? { name: editBypassName.trim(), phone: editBypassPhone.trim() } : b)); setEditingBypassIdx(null); setHasUnsavedChanges(true); } }
                                else if (e.key === 'Escape') { setEditingBypassIdx(null); }
                              }}
                            />
                            <button type="button" className="bypass-action-btn bypass-save-btn" title="Save" disabled={!editBypassPhone.trim()}
                              onClick={() => { if (editBypassPhone.trim()) { setBypassNumbers(prev => prev.map((b, i) => i === idx ? { name: editBypassName.trim(), phone: editBypassPhone.trim() } : b)); setEditingBypassIdx(null); setHasUnsavedChanges(true); } }}
                            ><i className="fas fa-check"></i></button>
                            <button type="button" className="bypass-action-btn bypass-cancel-btn" title="Cancel" onClick={() => setEditingBypassIdx(null)}><i className="fas fa-times"></i></button>
                          </>
                        ) : (
                          <>
                            <div className="bypass-entry-info">
                              <span className="bypass-entry-name">{entry.name || 'No name'}</span>
                              <span className="bypass-entry-phone">{entry.phone}</span>
                            </div>
                            <div className="bypass-entry-actions">
                              <button type="button" className="bypass-action-btn bypass-edit-btn" title="Edit"
                                onClick={() => { setEditingBypassIdx(idx); setEditBypassName(entry.name || ''); setEditBypassPhone(entry.phone || ''); }}
                              ><i className="fas fa-pen"></i></button>
                              <button type="button" className="bypass-action-btn bypass-remove-btn" title="Remove"
                                onClick={() => { setBypassNumbers(prev => prev.filter((_, i) => i !== idx)); setHasUnsavedChanges(true); }}
                              ><i className="fas fa-times"></i></button>
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
              </>
              ) : (
              <div className="ai-toggle-card" style={{ textAlign: 'center' }}>
                <div className="toggle-content" style={{ flexDirection: 'column', alignItems: 'center', gap: '1rem' }}>
                  <div className="toggle-info" style={{ textAlign: 'center' }}>
                    <h3><i className="fas fa-robot"></i> AI Receptionist</h3>
                    <p>Upgrade to the Pro plan to unlock the AI receptionist, smart scheduling, and a dedicated phone number.</p>
                  </div>
                  <button className="btn btn-primary" onClick={() => setActiveTab('billing')}>
                    <i className="fas fa-rocket"></i> Upgrade to Pro
                  </button>
                </div>
              </div>
              )}

              {/* Google Calendar */}
              <div className="settings-card">
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
                        <div className="gcal-status-label">{gcalStatus?.connected ? 'Connected' : 'Not connected'}</div>
                        {gcalStatus?.connected && gcalStatus?.calendar_email && (
                          <div className="gcal-status-email">{gcalStatus.calendar_email}</div>
                        )}
                      </div>
                    </div>
                    {gcalStatus?.connected ? (
                      <div className="gcal-actions">
                        <button type="button" className="btn btn-primary" onClick={handleSyncGoogleCalendar} disabled={gcalSyncing}>
                          <i className={`fas ${gcalSyncing ? 'fa-spinner fa-spin' : 'fa-sync'}`}></i> {gcalSyncing ? 'Syncing...' : 'Sync Now'}
                        </button>
                        <button type="button" className="btn btn-secondary" onClick={handleDisconnectGoogleCalendar}>
                          <i className="fas fa-unlink"></i> Disconnect
                        </button>
                      </div>
                    ) : (
                      <button type="button" className="btn btn-primary" onClick={handleConnectGoogleCalendar} disabled={gcalConnecting}>
                        <i className="fab fa-google"></i> {gcalConnecting ? 'Connecting...' : 'Connect Google Calendar'}
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
                          <input type="checkbox" checked={formData.gcal_invite_workers || false}
                            onChange={(e) => { setFormData(prev => ({ ...prev, gcal_invite_workers: e.target.checked })); setHasUnsavedChanges(true); }} />
                          <span className="toggle-slider"></span>
                        </label>
                      </div>
                    </div>
                  )}
                </div>

                {/* Accounting */}
                <div className="form-section">
                  <div className="form-section-header">
                    <i className="fas fa-calculator" style={{ color: '#059669' }}></i>
                    <h3>Accounting</h3>
                  </div>
                  <p className="section-description">
                    Connect Xero or QuickBooks to sync invoices, expenses, and contacts. Or disable the built-in accounting if you manage finances elsewhere.
                  </p>
                  {acctStatus?.connected && (acctStatus.provider === 'xero' || acctStatus.provider === 'quickbooks') && (
                    <div className="gcal-status-card connected">
                      <div className="gcal-status-info">
                        <i className="fas fa-check-circle gcal-status-icon connected"></i>
                        <div>
                          <div className="gcal-status-label">Connected to {acctStatus.provider === 'xero' ? 'Xero' : 'QuickBooks'}</div>
                          <div className="gcal-status-email">
                            {acctStatus.org_name || acctStatus.company_name || ''}
                            {acctStatus.last_sync && (<> · Last synced {new Date(acctStatus.last_sync).toLocaleDateString()}</>)}
                          </div>
                        </div>
                      </div>
                      <div className="gcal-actions">
                        <button type="button" className="btn btn-secondary" onClick={handleDisconnectAccounting}>
                          <i className="fas fa-unlink"></i> Disconnect
                        </button>
                      </div>
                    </div>
                  )}
                  {!acctStatus?.connected && formData.accounting_provider !== 'disabled' && (
                    <div className="acct-connect-options">
                      <button type="button" className="acct-connect-btn xero" onClick={() => handleConnectAccounting('xero')} disabled={acctConnecting}>
                        <div className="acct-connect-btn-icon">
                          <svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M4.21 11.09l3.54-5.3a.5.5 0 01.83 0l3.54 5.3M4.21 12.91l3.54 5.3a.5.5 0 00.83 0l3.54-5.3M12.88 11.09l3.54-5.3a.5.5 0 01.83 0l3.54 5.3M12.88 12.91l3.54 5.3a.5.5 0 00.83 0l3.54-5.3" stroke="#13b5ea" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/></svg>
                        </div>
                        <div className="acct-connect-btn-text">
                          <span className="acct-connect-btn-name">Connect Xero</span>
                          <span className="acct-connect-btn-desc">Cloud accounting for small business</span>
                        </div>
                        {acctConnecting && <i className="fas fa-spinner fa-spin"></i>}
                      </button>
                      <button type="button" className="acct-connect-btn quickbooks" onClick={() => handleConnectAccounting('quickbooks')} disabled={acctConnecting}>
                        <div className="acct-connect-btn-icon">
                          <svg width="22" height="22" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="#2ca01c" strokeWidth="1.8"/><path d="M8 9.5v5a2.5 2.5 0 005 0M11 14.5v-5a2.5 2.5 0 015 0" stroke="#2ca01c" strokeWidth="1.8" strokeLinecap="round"/></svg>
                        </div>
                        <div className="acct-connect-btn-text">
                          <span className="acct-connect-btn-name">Connect QuickBooks</span>
                          <span className="acct-connect-btn-desc">Accounting &amp; invoicing by Intuit</span>
                        </div>
                        {acctConnecting && <i className="fas fa-spinner fa-spin"></i>}
                      </button>
                    </div>
                  )}
                  {!acctStatus?.connected && (
                    <div className="toggle-rows" style={{ marginTop: '1rem' }}>
                      <div className="toggle-row">
                        <div className="toggle-row-info">
                          <div className="toggle-row-label">Disable Built-in Accounting</div>
                          <div className="toggle-row-desc">Turn off the Finances tab and all built-in accounting features. Use this if you manage finances in a separate app.</div>
                        </div>
                        <label className="toggle-switch">
                          <input type="checkbox" checked={formData.accounting_provider === 'disabled'} onChange={handleDisableBuiltinAccounting} />
                          <span className="toggle-slider"></span>
                        </label>
                      </div>
                    </div>
                  )}
                  {formData.accounting_provider === 'disabled' && !acctStatus?.connected && (
                    <div className="gcal-help-text" style={{ marginTop: '0.5rem' }}>
                      <i className="fas fa-info-circle"></i>
                      <span>Built-in accounting is disabled. The Finances tab is hidden from your dashboard. Toggle this off or connect Xero/QuickBooks to re-enable.</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Dashboard Features & Notifications */}
              <div className="settings-card">
                <div className="form-section">
                  <div className="form-section-header">
                    <i className="fas fa-sliders-h" style={{ color: '#6366f1' }}></i>
                    <h3>Dashboard Features</h3>
                  </div>
                  <p className="section-description">Choose which features to show on your dashboard.</p>
                  <div className="toggle-rows">
                    <div className="toggle-row">
                      <div className="toggle-row-info">
                        <div className="toggle-row-label">Finances Tab{formData.accounting_provider === 'disabled' ? ' (accounting disabled)' : ''}</div>
                        <div className="toggle-row-desc">Show the Finances tab on the dashboard</div>
                      </div>
                      <label className="toggle-switch">
                        <input type="checkbox" checked={formData.show_finances_tab !== false && formData.accounting_provider !== 'disabled'}
                          onChange={(e) => { setFormData(prev => ({ ...prev, show_finances_tab: e.target.checked })); setHasUnsavedChanges(true); }}
                          disabled={formData.accounting_provider === 'disabled'} />
                        <span className="toggle-slider"></span>
                      </label>
                    </div>
                    <div className="toggle-row">
                      <div className="toggle-row-info">
                        <div className="toggle-row-label">Insights Tab</div>
                        <div className="toggle-row-desc">Show the Insights tab with business analytics</div>
                      </div>
                      <label className="toggle-switch">
                        <input type="checkbox" checked={formData.show_insights_tab !== false}
                          onChange={(e) => { setFormData(prev => ({ ...prev, show_insights_tab: e.target.checked })); setHasUnsavedChanges(true); }} />
                        <span className="toggle-slider"></span>
                      </label>
                    </div>
                    <div className="toggle-row">
                      <div className="toggle-row-info">
                        <div className="toggle-row-label">Send Invoice Buttons</div>
                        <div className="toggle-row-desc">Show invoice buttons on jobs and finances</div>
                      </div>
                      <label className="toggle-switch">
                        <input type="checkbox" checked={formData.show_invoice_buttons !== false}
                          onChange={(e) => { setFormData(prev => ({ ...prev, show_invoice_buttons: e.target.checked })); setHasUnsavedChanges(true); }} />
                        <span className="toggle-slider"></span>
                      </label>
                    </div>
                  </div>
                </div>

                <div className="form-section">
                  <div className="form-section-header">
                    <i className="fas fa-bell" style={{ color: '#f59e0b' }}></i>
                    <h3>Notifications</h3>
                  </div>
                  <p className="section-description">Configure automated emails and SMS sent to your customers.</p>
                  <div className="toggle-rows">
                    <div className="toggle-row">
                      <div className="toggle-row-info">
                        <div className="toggle-row-label">Customer Review Emails</div>
                        <div className="toggle-row-desc">Send a satisfaction survey email when a job is completed</div>
                      </div>
                      <label className="toggle-switch">
                        <input type="checkbox" checked={formData.send_review_emails !== false}
                          onChange={(e) => { setFormData(prev => ({ ...prev, send_review_emails: e.target.checked })); setHasUnsavedChanges(true); }} />
                        <span className="toggle-slider"></span>
                      </label>
                    </div>
                    <div className="toggle-row">
                      <div className="toggle-row-info">
                        <div className="toggle-row-label">Booking Confirmation SMS</div>
                        <div className="toggle-row-desc">Send an SMS to the customer when a booking is confirmed</div>
                      </div>
                      <label className="toggle-switch">
                        <input type="checkbox" checked={formData.send_confirmation_sms !== false}
                          onChange={(e) => { setFormData(prev => ({ ...prev, send_confirmation_sms: e.target.checked })); setHasUnsavedChanges(true); }} />
                        <span className="toggle-slider"></span>
                      </label>
                    </div>
                  </div>
                </div>
              </div>

              {/* Review Automation */}
              <ReviewAutomationSettings />

              {/* Floating Save Button for integrations tab (bypass numbers need save) */}
              {hasUnsavedChanges && (
                <div className="floating-save-container">
                  <div className="unsaved-changes-hint">
                    <i className="fas fa-exclamation-circle"></i>
                    You have unsaved changes
                  </div>
                  <button type="button" className="btn btn-primary floating-save-btn" disabled={saveMutation.isPending} onClick={handleSubmit}>
                    <i className="fas fa-save"></i>
                    {saveMutation.isPending ? 'Saving...' : 'Save Settings'}
                  </button>
                </div>
              )}
            </>
          )}

          {/* ═══ PLAN & BILLING TAB ═══ */}
          {activeTab === 'billing' && (
            <div className="settings-tab-content">
              <div className="billing-section-group">
                <div className="billing-section-header">
                  <i className="fas fa-crown" style={{ color: '#f59e0b' }}></i>
                  <div>
                    <h3>Your Plan</h3>
                    <p>Manage your subscription and billing details</p>
                  </div>
                </div>
                <SubscriptionManager />
              </div>

              {!hideStripeConnect && (
                <div className="billing-section-group" style={{ marginTop: '1.5rem' }}>
                  <div className="billing-section-header">
                    <i className="fas fa-money-bill-wave" style={{ color: '#10b981' }}></i>
                    <div>
                      <h3>Receive Payments</h3>
                      <p>Set up how you get paid by your customers</p>
                    </div>
                  </div>
                  <PaymentSetup />
                </div>
              )}
            </div>
          )}

        </div>
      </main>

      <PhoneConfigModal
        isOpen={showPhoneModal}
        onClose={() => setShowPhoneModal(false)}
        onSuccess={handlePhoneConfigSuccess}
        allowSkip={false}
      />
    </div>
  );
}

function ReviewAutomationSettings() {
  const queryClient = useQueryClient();
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [urlError, setUrlError] = useState('');
  const [form, setForm] = useState({
    review_auto_send: true,
    review_delay_hours: 24,
    review_google_url: '',
    google_review_threshold: 4,
  });

  const { data, isLoading } = useQuery({
    queryKey: ['review-automation'],
    queryFn: async () => (await getReviewAutomationSettings()).data,
  });

  useEffect(() => {
    if (data) setForm({
      review_auto_send: data.review_auto_send ?? true,
      review_delay_hours: data.review_delay_hours ?? 24,
      review_google_url: data.review_google_url || '',
      google_review_threshold: data.google_review_threshold ?? 4,
    });
  }, [data]);

  const validateGoogleUrl = (url) => {
    if (!url) { setUrlError(''); return true; }
    try {
      const parsed = new URL(url);
      if (!['http:', 'https:'].includes(parsed.protocol)) {
        setUrlError('URL must start with http:// or https://');
        return false;
      }
      setUrlError('');
      return true;
    } catch {
      setUrlError('Please enter a valid URL');
      return false;
    }
  };

  const handleGoogleUrlChange = (e) => {
    const url = e.target.value;
    setForm({ ...form, review_google_url: url });
    if (urlError) validateGoogleUrl(url);
  };

  const handleSave = async () => {
    if (form.review_auto_send && form.review_google_url && !validateGoogleUrl(form.review_google_url)) return;
    setSaving(true);
    try {
      await updateReviewAutomationSettings(form);
      queryClient.invalidateQueries({ queryKey: ['review-automation'] });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch { /* ignore */ }
    finally { setSaving(false); }
  };

  if (isLoading) return <div className="review-loading">Loading...</div>;

  return (
    <>
      <div className="settings-card">
        <div className="form-section">
          <div className="form-section-header">
            <i className="fas fa-star" style={{ color: '#f59e0b' }}></i>
            <h3>Post-Job Review Automation</h3>
          </div>
          <p className="section-description">Automatically request reviews after jobs are completed. Happy customers get directed to leave a Google review.</p>

          <div className="toggle-rows">
            <div className="toggle-row">
              <div className="toggle-row-info">
                <div className="toggle-row-label">Auto-send review requests</div>
                <div className="toggle-row-desc">{form.review_auto_send ? 'Enabled — reviews sent automatically' : 'Disabled — reviews are not sent'}</div>
              </div>
              <label className="toggle-switch">
                <input type="checkbox" checked={form.review_auto_send}
                  onChange={() => setForm({ ...form, review_auto_send: !form.review_auto_send })} />
                <span className="toggle-slider"></span>
              </label>
            </div>
          </div>

          {form.review_auto_send && (
            <div className="form-grid" style={{ marginTop: '1.25rem' }}>
              <div className="form-group">
                <label>Send review request after</label>
                <select value={form.review_delay_hours}
                  onChange={e => setForm({ ...form, review_delay_hours: parseInt(e.target.value) })}>
                  <option value="1">1 hour</option>
                  <option value="4">4 hours</option>
                  <option value="24">1 day</option>
                  <option value="48">2 days</option>
                  <option value="72">3 days</option>
                  <option value="168">1 week</option>
                </select>
              </div>

              <div className="form-group">
                <label>Google review redirect threshold</label>
                <select value={form.google_review_threshold}
                  onChange={e => setForm({ ...form, google_review_threshold: parseInt(e.target.value) })}>
                  <option value="3">3+ stars</option>
                  <option value="4">4+ stars (recommended)</option>
                  <option value="5">5 stars only</option>
                </select>
                <small className="form-help">Only happy customers get directed to Google — lower ratings stay internal</small>
              </div>

              <div className="form-group full-width">
                <label>Google Reviews URL</label>
                <input type="url" className={urlError ? 'review-input-error' : ''}
                  placeholder="https://g.page/r/your-business/review"
                  value={form.review_google_url}
                  onChange={handleGoogleUrlChange}
                  onBlur={() => validateGoogleUrl(form.review_google_url)} />
                {urlError && <small className="form-help" style={{ color: '#ef4444' }}><i className="fas fa-exclamation-circle"></i> {urlError}</small>}
                <small className="form-help">Customers who rate {form.google_review_threshold}+ stars will be prompted to leave a Google review</small>
              </div>
            </div>
          )}

          <div className="review-save-row">
            <button type="button" className="btn btn-primary" onClick={handleSave} disabled={saving}>
              <i className={`fas ${saving ? 'fa-spinner fa-spin' : 'fa-save'}`}></i> {saving ? 'Saving...' : 'Save Review Settings'}
            </button>
            {saved && <span className="review-saved-badge"><i className="fas fa-check-circle"></i> Saved</span>}
          </div>
        </div>

        <div className="form-section">
          <div className="form-section-header">
            <i className="fas fa-info-circle" style={{ color: 'var(--accent-blue)' }}></i>
            <h3>How it works</h3>
          </div>
          <div className="review-steps">
            <div className="review-step">
              <span className="review-step-num">1</span>
              <span className="review-step-text">Job is marked as completed</span>
            </div>
            <div className="review-step-connector"></div>
            <div className="review-step">
              <span className="review-step-num">2</span>
              <span className="review-step-text">After the delay, customer receives a review request via email</span>
            </div>
            <div className="review-step-connector"></div>
            <div className="review-step">
              <span className="review-step-num">3</span>
              <span className="review-step-text">Customer rates their experience (1-5 stars)</span>
            </div>
            <div className="review-step-connector"></div>
            <div className="review-step happy">
              <span className="review-step-num happy">4</span>
              <span className="review-step-text">Happy customers ({form.google_review_threshold}+ stars) are redirected to your Google Reviews page</span>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

export default Settings;
