import React, { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { formatCurrency } from '../../utils/helpers';
import { getCallLogs, getLeads } from '../../services/api';
import './InsightsTab.css';
import './SharedDashboard.css';

const DAY_NAMES = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const HOUR_LABELS = Array.from({ length: 24 }, (_, i) => {
  if (i === 0) return '12a';
  if (i < 12) return `${i}a`;
  if (i === 12) return '12p';
  return `${i - 12}p`;
});

function InsightsTab({ bookings = [], clients = [], employees = [], reviews: reviewsData }) {
  // Graph visibility toggles (persisted in localStorage)
  const [showSections, setShowSections] = useState(() => {
    try {
      const saved = localStorage.getItem('insights_visible_sections');
      return saved ? JSON.parse(saved) : {
        overviewCards: true, statsCards: true, bookingActivity: true,
        clientGrowth: true, servicePopularity: true, employeeLeaderboard: true, heatmap: true,
        revenueTrend: true, cancellationTrend: false, durationDistribution: false, reviewsSummary: true,
        callAnalytics: true, leadFunnel: true, completionRate: true, employeeUtilization: false
      };
    } catch { return { overviewCards: true, statsCards: true, bookingActivity: true, clientGrowth: true, servicePopularity: true, employeeLeaderboard: true, heatmap: true, revenueTrend: true, cancellationTrend: false, durationDistribution: false, reviewsSummary: true, callAnalytics: true, leadFunnel: true, completionRate: true, employeeUtilization: false }; }
  });
  const [showSectionPicker, setShowSectionPicker] = useState(false);

  // Widget order (persisted)
  const [widgetOrder, setWidgetOrder] = useState(() => {
    try {
      const saved = localStorage.getItem('insights_widget_order');
      return saved ? JSON.parse(saved) : null;
    } catch { return null; }
  });

  const WIDGET_DEFS = [
    { key: 'overviewCards', label: 'Overview Cards', icon: 'fa-th-large' },
    { key: 'statsCards', label: 'Quick Stats', icon: 'fa-chart-pie' },
    { key: 'bookingActivity', label: 'Booking Activity', icon: 'fa-chart-bar' },
    { key: 'revenueTrend', label: 'Revenue Trend', icon: 'fa-chart-line' },
    { key: 'clientGrowth', label: 'Client Growth', icon: 'fa-user-plus' },
    { key: 'servicePopularity', label: 'Service Popularity', icon: 'fa-star' },
    { key: 'employeeLeaderboard', label: 'Employee Leaderboard', icon: 'fa-trophy' },
    { key: 'heatmap', label: 'Busiest Hours', icon: 'fa-fire' },
    { key: 'cancellationTrend', label: 'Cancellation Trend', icon: 'fa-times-circle' },
    { key: 'durationDistribution', label: 'Job Duration', icon: 'fa-clock' },
    { key: 'reviewsSummary', label: 'Customer Reviews', icon: 'fa-star' },
    { key: 'callAnalytics', label: 'Call Analytics', icon: 'fa-phone-alt' },
    { key: 'leadFunnel', label: 'Lead Funnel', icon: 'fa-filter' },
    { key: 'completionRate', label: 'Completion Rate', icon: 'fa-check-circle' },
    { key: 'employeeUtilization', label: 'Employee Utilization', icon: 'fa-hard-hat' },
  ];

  const orderedWidgets = widgetOrder
    ? widgetOrder.map(k => WIDGET_DEFS.find(w => w.key === k)).filter(Boolean)
    : WIDGET_DEFS;
  // Add any new widgets not in saved order
  const orderedKeys = new Set(orderedWidgets.map(w => w.key));
  WIDGET_DEFS.forEach(w => { if (!orderedKeys.has(w.key)) orderedWidgets.push(w); });

  const toggleSection = (key) => {
    const next = { ...showSections, [key]: !showSections[key] };
    setShowSections(next);
    localStorage.setItem('insights_visible_sections', JSON.stringify(next));
  };

  const moveWidget = (key, direction) => {
    const keys = orderedWidgets.map(w => w.key);
    const idx = keys.indexOf(key);
    if (idx < 0) return;
    const newIdx = idx + direction;
    if (newIdx < 0 || newIdx >= keys.length) return;
    [keys[idx], keys[newIdx]] = [keys[newIdx], keys[idx]];
    setWidgetOrder(keys);
    localStorage.setItem('insights_widget_order', JSON.stringify(keys));
  };

  // Fetch call logs for call analytics widget
  const { data: callLogsData } = useQuery({
    queryKey: ['call-logs-insights'],
    queryFn: async () => {
      const res = await getCallLogs({ per_page: 100 });
      return res.data;
    },
    staleTime: 5 * 60 * 1000,
  });
  const callLogs = callLogsData?.call_logs || [];

  // Fetch leads for funnel widget
  const { data: leadsRaw } = useQuery({
    queryKey: ['leads'],
    queryFn: async () => (await getLeads()).data,
    staleTime: 5 * 60 * 1000,
  });
  const leads = leadsRaw?.leads || [];

  const stats = useMemo(() => {
    const now = new Date();
    const nonCancelled = bookings.filter(b => b.status !== 'cancelled');
    const cancelled = bookings.filter(b => b.status === 'cancelled');
    const cancellationRate = bookings.length > 0 ? (cancelled.length / bookings.length) * 100 : 0;

    // Busiest day of week
    const dayCount = [0, 0, 0, 0, 0, 0, 0];
    nonCancelled.forEach(b => {
      if (b.appointment_time) {
        const d = new Date(b.appointment_time);
        if (!isNaN(d)) dayCount[d.getDay()]++;
      }
    });
    const busiestDayIdx = dayCount.indexOf(Math.max(...dayCount));
    const busiestDay = Math.max(...dayCount) > 0 ? DAY_NAMES[busiestDayIdx] : '—';

    // Jobs per month (last 6 months) for activity chart
    const monthlyJobs = {};
    for (let i = 5; i >= 0; i--) {
      const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
      monthlyJobs[key] = 0;
    }
    nonCancelled.forEach(b => {
      if (b.appointment_time) {
        const d = new Date(b.appointment_time);
        if (!isNaN(d)) {
          const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
          if (key in monthlyJobs) monthlyJobs[key]++;
        }
      }
    });
    const activityData = Object.entries(monthlyJobs).map(([month, count]) => {
      const [y, m] = month.split('-');
      const label = new Date(+y, +m - 1).toLocaleDateString('en-IE', { month: 'short' });
      return { month, label, count };
    });

    // Employee leaderboard
    const employeeStats = {};
    employees.forEach(w => {
      employeeStats[w.id] = { name: w.name, jobs: 0, revenue: 0 };
    });
    nonCancelled.forEach(b => {
      const ids = b.assigned_employee_ids || [];
      ids.forEach(wid => {
        if (employeeStats[wid]) {
          employeeStats[wid].jobs++;
          employeeStats[wid].revenue += parseFloat(b.charge || b.estimated_charge || 0);
        }
      });
    });
    const employeeLeaderboard = Object.values(employeeStats)
      .filter(w => w.jobs > 0)
      .sort((a, b) => b.jobs - a.jobs)
      .slice(0, 6);

    // Heatmap: day of week × hour
    const heatmap = Array.from({ length: 7 }, () => new Array(24).fill(0));
    nonCancelled.forEach(b => {
      if (b.appointment_time) {
        const d = new Date(b.appointment_time);
        if (!isNaN(d)) {
          heatmap[d.getDay()][d.getHours()]++;
        }
      }
    });
    const heatmapMax = Math.max(1, ...heatmap.flat());

    // New clients per month (last 6 months)
    const clientGrowth = {};
    for (let i = 5; i >= 0; i--) {
      const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
      clientGrowth[key] = 0;
    }
    clients.forEach(c => {
      if (c.created_at) {
        const d = new Date(c.created_at);
        if (!isNaN(d)) {
          const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
          if (key in clientGrowth) clientGrowth[key]++;
        }
      }
    });
    const clientGrowthData = Object.entries(clientGrowth).map(([month, count]) => {
      const [y, m] = month.split('-');
      const label = new Date(+y, +m - 1).toLocaleDateString('en-IE', { month: 'short' });
      return { month, label, count };
    });

    // Repeat customer rate
    const clientJobCount = {};
    nonCancelled.forEach(b => {
      const cid = b.client_id;
      if (cid) clientJobCount[cid] = (clientJobCount[cid] || 0) + 1;
    });
    const clientsWithJobs = Object.keys(clientJobCount).length;
    const repeatClients = Object.values(clientJobCount).filter(c => c > 1).length;
    const repeatRate = clientsWithJobs > 0 ? (repeatClients / clientsWithJobs) * 100 : 0;

    // Average job duration (in hours)
    const durations = nonCancelled
      .map(b => b.duration_minutes)
      .filter(d => d && d > 0 && d < 1440); // exclude full-day defaults
    const avgDurationMins = durations.length > 0 ? durations.reduce((s, d) => s + d, 0) / durations.length : 0;

    // Booking lead time — how far in advance jobs are booked (days between created_at and appointment_time)
    const leadTimes = nonCancelled
      .filter(b => b.created_at && b.appointment_time)
      .map(b => {
        const created = new Date(b.created_at);
        const appt = new Date(b.appointment_time);
        return (appt - created) / (1000 * 60 * 60 * 24);
      })
      .filter(d => d >= 0 && d < 365);
    const avgLeadDays = leadTimes.length > 0 ? leadTimes.reduce((s, d) => s + d, 0) / leadTimes.length : 0;

    // Service popularity (by job count, not revenue)
    const serviceCount = {};
    nonCancelled.forEach(b => {
      const svc = b.service_type || b.service || 'Other';
      serviceCount[svc] = (serviceCount[svc] || 0) + 1;
    });
    const servicePopularity = Object.entries(serviceCount)
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count);

    // Revenue trend (last 6 months)
    const monthlyRevenue = {};
    for (let i = 5; i >= 0; i--) {
      const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
      monthlyRevenue[key] = 0;
    }
    nonCancelled.forEach(b => {
      if (b.appointment_time && (b.charge || b.estimated_charge)) {
        const d = new Date(b.appointment_time);
        if (!isNaN(d)) {
          const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
          if (key in monthlyRevenue) monthlyRevenue[key] += parseFloat(b.charge || b.estimated_charge || 0);
        }
      }
    });
    const revenueTrendData = Object.entries(monthlyRevenue).map(([month, revenue]) => {
      const [y, m] = month.split('-');
      const label = new Date(+y, +m - 1).toLocaleDateString('en-IE', { month: 'short' });
      return { month, label, revenue };
    });

    // Cancellation trend (last 6 months)
    const monthlyCancellations = {};
    const monthlyTotal = {};
    for (let i = 5; i >= 0; i--) {
      const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
      monthlyCancellations[key] = 0;
      monthlyTotal[key] = 0;
    }
    bookings.forEach(b => {
      if (b.appointment_time) {
        const d = new Date(b.appointment_time);
        if (!isNaN(d)) {
          const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
          if (key in monthlyTotal) {
            monthlyTotal[key]++;
            if (b.status === 'cancelled') monthlyCancellations[key]++;
          }
        }
      }
    });
    const cancellationTrendData = Object.entries(monthlyCancellations).map(([month, cancelled]) => {
      const [y, m] = month.split('-');
      const label = new Date(+y, +m - 1).toLocaleDateString('en-IE', { month: 'short' });
      const total = monthlyTotal[month] || 1;
      return { month, label, cancelled, total, rate: Math.round((cancelled / total) * 100) };
    });

    // Duration distribution
    const durationBuckets = { '< 1h': 0, '1-2h': 0, '2-4h': 0, '4-8h': 0, 'Full day': 0 };
    nonCancelled.forEach(b => {
      const d = b.duration_minutes;
      if (!d || d <= 0) return;
      if (d < 60) durationBuckets['< 1h']++;
      else if (d <= 120) durationBuckets['1-2h']++;
      else if (d <= 240) durationBuckets['2-4h']++;
      else if (d <= 480) durationBuckets['4-8h']++;
      else durationBuckets['Full day']++;
    });
    const durationDistData = Object.entries(durationBuckets).map(([label, count]) => ({ label, count }));

    // ===== Month-over-Month comparisons =====
    const activityKeys = Object.keys(monthlyJobs);
    const curMonthKey = activityKeys[activityKeys.length - 1];
    const prevMonthKey = activityKeys[activityKeys.length - 2];
    const curMonthJobs = monthlyJobs[curMonthKey] || 0;
    const prevMonthJobs = monthlyJobs[prevMonthKey] || 0;
    const jobsMoM = prevMonthJobs > 0 ? ((curMonthJobs - prevMonthJobs) / prevMonthJobs) * 100 : null;

    const curMonthRevenue = monthlyRevenue[curMonthKey] || 0;
    const prevMonthRevenue = monthlyRevenue[prevMonthKey] || 0;
    const revenueMoM = prevMonthRevenue > 0 ? ((curMonthRevenue - prevMonthRevenue) / prevMonthRevenue) * 100 : null;

    const curMonthClients = clientGrowth[curMonthKey] || 0;
    const prevMonthClients = clientGrowth[prevMonthKey] || 0;
    const clientsMoM = prevMonthClients > 0 ? ((curMonthClients - prevMonthClients) / prevMonthClients) * 100 : null;

    // ===== Avg Revenue per Job =====
    const totalRevenue = nonCancelled.reduce((s, b) => s + parseFloat(b.charge || b.estimated_charge || 0), 0);
    const avgRevenuePerJob = nonCancelled.length > 0 ? totalRevenue / nonCancelled.length : 0;

    // ===== Completion Rate =====
    const completed = nonCancelled.filter(b => b.status === 'completed').length;
    const completionRate = nonCancelled.length > 0 ? (completed / nonCancelled.length) * 100 : 0;

    // ===== Employee Utilization =====
    const employeeUtilization = employees.map(w => {
      const employeeJobs = nonCancelled.filter(b => (b.assigned_employee_ids || []).includes(w.id));
      const totalMins = employeeJobs.reduce((s, b) => s + (b.duration_minutes || 0), 0);
      // Assume 8h/day, 22 days/month = 176h available per month, show last month
      const availableHours = 176;
      const workedHours = totalMins / 60;
      return { name: w.name, workedHours, utilization: availableHours > 0 ? Math.min((workedHours / availableHours) * 100, 100) : 0 };
    }).filter(w => w.workedHours > 0).sort((a, b) => b.utilization - a.utilization);

    // ===== Customer Lifetime Value =====
    const revenuePerClient = {};
    nonCancelled.forEach(b => {
      const cid = b.client_id;
      if (cid) revenuePerClient[cid] = (revenuePerClient[cid] || 0) + parseFloat(b.charge || b.estimated_charge || 0);
    });
    const clvValues = Object.values(revenuePerClient);
    const avgCLV = clvValues.length > 0 ? clvValues.reduce((s, v) => s + v, 0) / clvValues.length : 0;

    return {
      totalClients: clients.length,
      totalJobs: nonCancelled.length,
      cancellationRate,
      busiestDay,
      activityData,
      employeeLeaderboard,
      heatmap,
      heatmapMax,
      clientGrowthData,
      repeatRate,
      avgDurationMins,
      avgLeadDays,
      servicePopularity,
      revenueTrendData,
      cancellationTrendData,
      durationDistData,
      jobsMoM,
      revenueMoM,
      clientsMoM,
      avgRevenuePerJob,
      completionRate,
      employeeUtilization,
      avgCLV,
    };
  }, [bookings, clients, employees]);

  const maxActivity = Math.max(1, ...stats.activityData.map(d => d.count));
  const maxClientGrowth = Math.max(1, ...stats.clientGrowthData.map(d => d.count));
  const maxRevenueTrend = Math.max(1, ...stats.revenueTrendData.map(d => d.revenue));
  const maxDurationDist = Math.max(1, ...stats.durationDistData.map(d => d.count));

  // ===== Call Analytics computed stats =====
  const callStats = useMemo(() => {
    if (callLogs.length === 0) return null;
    const totalCalls = callLogs.length;
    const avgDuration = callLogs.reduce((s, c) => s + (c.duration_seconds || 0), 0) / totalCalls;
    const booked = callLogs.filter(c => c.call_outcome === 'booked').length;
    const conversionRate = totalCalls > 0 ? (booked / totalCalls) * 100 : 0;
    const lostJobs = callLogs.filter(c => c.is_lost_job).length;
    // Outcome breakdown
    const outcomes = {};
    callLogs.forEach(c => {
      const o = c.call_outcome || 'no_action';
      outcomes[o] = (outcomes[o] || 0) + 1;
    });
    return { totalCalls, avgDuration, conversionRate, lostJobs, outcomes };
  }, [callLogs]);

  // ===== Lead Funnel computed stats =====
  const leadFunnelStats = useMemo(() => {
    if (leads.length === 0) return null;
    const stages = ['new', 'contacted', 'qualified', 'proposal', 'won', 'lost'];
    const stageCounts = {};
    stages.forEach(s => { stageCounts[s] = 0; });
    leads.forEach(l => {
      const s = l.stage || 'new';
      if (s in stageCounts) stageCounts[s]++;
      else stageCounts[s] = (stageCounts[s] || 0) + 1;
    });
    const totalLeads = leads.length;
    const wonLeads = stageCounts['won'] || 0;
    const overallConversion = totalLeads > 0 ? (wonLeads / totalLeads) * 100 : 0;
    return { stageCounts, stages, totalLeads, wonLeads, overallConversion };
  }, [leads]);

  return (
    <div className="insights-tab">
      {/* Page Header */}
      <div className="tab-page-header">
        <div>
          <h2 className="tab-page-title">Insights</h2>
          <p className="tab-page-subtitle">Business analytics and performance metrics</p>
        </div>
        <div className="tab-page-actions">
          <button className="fin-section-toggle-btn" onClick={() => setShowSectionPicker(!showSectionPicker)}>
            <i className={`fas ${showSectionPicker ? 'fa-times' : 'fa-sliders-h'}`}></i>
            {showSectionPicker ? 'Done' : 'Customize'}
          </button>
        </div>
      </div>

      {/* Section Visibility Toggle */}
      {showSectionPicker && (
      <div className="fin-section-toggle-bar">
        <div className="insights-widget-picker">
          {orderedWidgets.map((w, idx) => (
            <div key={w.key} className={`insights-widget-item ${showSections[w.key] ? 'active' : ''}`}>
              <div className="insights-widget-reorder">
                <button className="insights-reorder-btn" onClick={() => moveWidget(w.key, -1)} disabled={idx === 0} title="Move up">
                  <i className="fas fa-chevron-up"></i>
                </button>
                <button className="insights-reorder-btn" onClick={() => moveWidget(w.key, 1)} disabled={idx === orderedWidgets.length - 1} title="Move down">
                  <i className="fas fa-chevron-down"></i>
                </button>
              </div>
              <button className="insights-widget-toggle" onClick={() => toggleSection(w.key)}>
                <i className={`fas ${w.icon}`}></i>
                <span>{w.label}</span>
                <i className={`fas ${showSections[w.key] ? 'fa-eye' : 'fa-eye-slash'}`} style={{ marginLeft: 'auto', opacity: 0.5 }}></i>
              </button>
            </div>
          ))}
        </div>
      </div>
      )}

      {/* Overview Cards */}
      {showSections.overviewCards && (
      <div className="insights-overview">
        <div className="overview-card">
          <div className="overview-icon" style={{ background: 'rgba(59, 130, 246, 0.1)' }}>
            <i className="fas fa-users" style={{ color: '#3b82f6' }}></i>
          </div>
          <div className="overview-content">
            <div className="overview-value">{stats.totalClients}</div>
            <div className="overview-label">Total Clients</div>
          </div>
        </div>
        <div className="overview-card">
          <div className="overview-icon" style={{ background: 'rgba(16, 185, 129, 0.1)' }}>
            <i className="fas fa-briefcase" style={{ color: '#10b981' }}></i>
          </div>
          <div className="overview-content">
            <div className="overview-value">{stats.totalJobs}{stats.jobsMoM != null && <span className={`mom-badge ${stats.jobsMoM >= 0 ? 'up' : 'down'}`}>{stats.jobsMoM >= 0 ? '↑' : '↓'}{Math.abs(stats.jobsMoM).toFixed(0)}%</span>}</div>
            <div className="overview-label">Total Jobs</div>
          </div>
        </div>
        <div className="overview-card">
          <div className="overview-icon" style={{ background: stats.cancellationRate > 15 ? 'rgba(239, 68, 68, 0.1)' : 'rgba(99, 102, 241, 0.1)' }}>
            <i className="fas fa-times-circle" style={{ color: stats.cancellationRate > 15 ? '#ef4444' : '#6366f1' }}></i>
          </div>
          <div className="overview-content">
            <div className="overview-value">{stats.cancellationRate.toFixed(1)}%</div>
            <div className="overview-label">Cancellation Rate</div>
          </div>
        </div>
        <div className="overview-card">
          <div className="overview-icon" style={{ background: 'rgba(245, 158, 11, 0.1)' }}>
            <i className="fas fa-fire" style={{ color: '#f59e0b' }}></i>
          </div>
          <div className="overview-content">
            <div className="overview-value">{stats.busiestDay}</div>
            <div className="overview-label">Busiest Day</div>
          </div>
        </div>
      </div>
      )}

      {/* Second row of stats */}
      {showSections.statsCards && (
      <div className="insights-overview">
        <div className="overview-card">
          <div className="overview-icon" style={{ background: stats.repeatRate >= 30 ? 'rgba(16, 185, 129, 0.1)' : 'rgba(245, 158, 11, 0.1)' }}>
            <i className="fas fa-redo" style={{ color: stats.repeatRate >= 30 ? '#10b981' : '#f59e0b' }}></i>
          </div>
          <div className="overview-content">
            <div className="overview-value">{stats.repeatRate.toFixed(0)}%</div>
            <div className="overview-label">Repeat Customers</div>
          </div>
        </div>
        <div className="overview-card">
          <div className="overview-icon" style={{ background: 'rgba(16, 185, 129, 0.1)' }}>
            <i className="fas fa-receipt" style={{ color: '#10b981' }}></i>
          </div>
          <div className="overview-content">
            <div className="overview-value">{formatCurrency(stats.avgRevenuePerJob)}{stats.revenueMoM != null && <span className={`mom-badge ${stats.revenueMoM >= 0 ? 'up' : 'down'}`}>{stats.revenueMoM >= 0 ? '↑' : '↓'}{Math.abs(stats.revenueMoM).toFixed(0)}%</span>}</div>
            <div className="overview-label">Avg Ticket Size</div>
          </div>
        </div>
        <div className="overview-card">
          <div className="overview-icon" style={{ background: 'rgba(139, 92, 246, 0.1)' }}>
            <i className="fas fa-gem" style={{ color: '#8b5cf6' }}></i>
          </div>
          <div className="overview-content">
            <div className="overview-value">{formatCurrency(stats.avgCLV)}</div>
            <div className="overview-label">Avg Client Value</div>
          </div>
        </div>
        <div className="overview-card">
          <div className="overview-icon" style={{ background: 'rgba(14, 165, 233, 0.1)' }}>
            <i className="fas fa-calendar-check" style={{ color: '#0ea5e9' }}></i>
          </div>
          <div className="overview-content">
            <div className="overview-value">{stats.avgLeadDays < 1 ? 'Same day' : `${Math.round(stats.avgLeadDays)}d`}{stats.clientsMoM != null && <span className={`mom-badge ${stats.clientsMoM >= 0 ? 'up' : 'down'}`}>{stats.clientsMoM >= 0 ? '↑' : '↓'}{Math.abs(stats.clientsMoM).toFixed(0)}%</span>}</div>
            <div className="overview-label">Avg Lead Time</div>
          </div>
        </div>
      </div>
      )}

      {/* Two-column layout: Activity + Client Growth */}
      {(showSections.bookingActivity || showSections.clientGrowth) && (
      <div className="insights-charts-row">
        {/* Booking Activity */}
        {showSections.bookingActivity && (
        <div className="insights-card">
          <h3><i className="fas fa-chart-bar"></i> Booking Activity</h3>
          <div className="bar-chart">
            {stats.activityData.map((d, i) => (
              <div key={i} className="bar-col">
                <div className="bar-wrapper">
                  <div
                    className="bar-fill"
                    style={{ height: `${(d.count / maxActivity) * 100}%` }}
                  />
                </div>
                <span className="bar-count">{d.count}</span>
                <span className="bar-label">{d.label}</span>
              </div>
            ))}
          </div>
        </div>
        )}

        {/* Client Growth */}
        {showSections.clientGrowth && (
        <div className="insights-card">
          <h3><i className="fas fa-user-plus"></i> New Clients</h3>
          <div className="bar-chart">
            {stats.clientGrowthData.map((d, i) => (
              <div key={i} className="bar-col">
                <div className="bar-wrapper">
                  <div
                    className="bar-fill bar-fill-green"
                    style={{ height: `${(d.count / maxClientGrowth) * 100}%` }}
                  />
                </div>
                <span className="bar-count">{d.count}</span>
                <span className="bar-label">{d.label}</span>
              </div>
            ))}
          </div>
        </div>
        )}
      </div>
      )}

      {/* Service Popularity + Employee Leaderboard */}
      {(showSections.servicePopularity || showSections.employeeLeaderboard) && (
      <div className="insights-charts-row">
        {/* Service Popularity */}
        {showSections.servicePopularity && (
        <div className="insights-card">
          <h3><i className="fas fa-concierge-bell"></i> Service Popularity</h3>
          {stats.servicePopularity.length === 0 ? (
            <div className="insights-empty">
              <i className="fas fa-list"></i>
              <p>No services booked yet</p>
            </div>
          ) : (
            <div className="service-popularity">
              {stats.servicePopularity.slice(0, 6).map((svc, i) => {
                const maxCount = stats.servicePopularity[0]?.count || 1;
                const pct = (svc.count / maxCount) * 100;
                return (
                  <div key={i} className="service-pop-row">
                    <div className="service-pop-label">{svc.name}</div>
                    <div className="service-pop-track">
                      <div className="service-pop-fill" style={{ width: `${Math.max(pct, 4)}%` }} />
                    </div>
                    <div className="service-pop-count">{svc.count}</div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
        )}

        {/* Employee Leaderboard */}
        {showSections.employeeLeaderboard && (
        <div className="insights-card">
          <h3><i className="fas fa-trophy"></i> Employee Leaderboard</h3>
          {stats.employeeLeaderboard.length === 0 ? (
            <div className="insights-empty">
              <i className="fas fa-hard-hat"></i>
              <p>Assign employees to jobs to see stats</p>
            </div>
          ) : (
            <div className="leaderboard">
              {stats.employeeLeaderboard.map((w, i) => (
                <div key={i} className="leaderboard-row">
                  <div className="leaderboard-rank" data-rank={i + 1}>{i + 1}</div>
                  <div className="leaderboard-info">
                    <div className="leaderboard-name">{w.name}</div>
                    <div className="leaderboard-meta">{w.jobs} job{w.jobs !== 1 ? 's' : ''} · {formatCurrency(w.revenue)}</div>
                  </div>
                  <div className="leaderboard-bar-track">
                    <div
                      className="leaderboard-bar-fill"
                      style={{ width: `${(w.jobs / stats.employeeLeaderboard[0].jobs) * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        )}
      </div>
      )}

      {/* Revenue Trend */}
      {showSections.revenueTrend && (
      <div className="insights-card">
        <h3><i className="fas fa-euro-sign"></i> Revenue Trend</h3>
        <div className="bar-chart">
          {stats.revenueTrendData.map((d, i) => (
            <div key={i} className="bar-col">
              <div className="bar-wrapper">
                <div className="bar-fill" style={{ height: `${(d.revenue / maxRevenueTrend) * 100}%`, background: 'linear-gradient(180deg, #10b981, #059669)' }} />
              </div>
              <span className="bar-count" style={{ color: '#10b981' }}>{formatCurrency(d.revenue)}</span>
              <span className="bar-label">{d.label}</span>
            </div>
          ))}
        </div>
      </div>
      )}

      {/* Cancellation Trend + Duration Distribution */}
      {(showSections.cancellationTrend || showSections.durationDistribution) && (
      <div className="insights-charts-row">
        {showSections.cancellationTrend && (
        <div className="insights-card">
          <h3><i className="fas fa-times-circle"></i> Cancellation Trend</h3>
          <div className="bar-chart">
            {stats.cancellationTrendData.map((d, i) => (
              <div key={i} className="bar-col">
                <div className="bar-wrapper">
                  <div className="bar-fill" style={{ height: `${Math.max(d.rate, d.cancelled > 0 ? 5 : 0)}%`, background: '#ef4444' }} />
                </div>
                <span className="bar-count" style={{ color: d.rate > 15 ? '#ef4444' : '#94a3b8' }}>{d.rate}%</span>
                <span className="bar-label">{d.label}</span>
              </div>
            ))}
          </div>
        </div>
        )}

        {showSections.durationDistribution && (
        <div className="insights-card">
          <h3><i className="fas fa-hourglass-half"></i> Job Duration Distribution</h3>
          <div className="bar-chart">
            {stats.durationDistData.map((d, i) => (
              <div key={i} className="bar-col">
                <div className="bar-wrapper">
                  <div className="bar-fill bar-fill-green" style={{ height: `${(d.count / maxDurationDist) * 100}%` }} />
                </div>
                <span className="bar-count">{d.count}</span>
                <span className="bar-label">{d.label}</span>
              </div>
            ))}
          </div>
        </div>
        )}
      </div>
      )}

      {/* Busiest Hours Heatmap — full width */}
      {showSections.heatmap && (
      <div className="insights-card">
        <h3><i className="fas fa-clock"></i> Busiest Hours</h3>
        {stats.totalJobs === 0 ? (
          <div className="insights-empty">
            <i className="fas fa-calendar-alt"></i>
            <p>Book some jobs to see patterns</p>
          </div>
        ) : (
          <div className="heatmap-container">
            <div className="heatmap-grid" style={{ gridTemplateColumns: `36px repeat(12, 1fr)` }}>
              {/* Header row: empty corner + hour labels */}
              <div className="heatmap-corner"></div>
              {HOUR_LABELS.filter((_, i) => i % 2 === 0).map((h, i) => (
                <div key={i} className="heatmap-hour-label">{h}</div>
              ))}
              {/* Day rows: label + cells — all flat in the grid */}
              {[1, 2, 3, 4, 5, 6, 0].map(dayIdx => (
                <React.Fragment key={`day-${dayIdx}`}>
                  <div className="heatmap-day-label">{DAY_NAMES[dayIdx]}</div>
                  {Array.from({ length: 12 }, (_, hi) => {
                    const hour = hi * 2;
                    const val = stats.heatmap[dayIdx][hour] + stats.heatmap[dayIdx][hour + 1];
                    const intensity = val / (stats.heatmapMax * 2);
                    return (
                      <div
                        key={`${dayIdx}-${hi}`}
                        className="heatmap-cell"
                        style={{
                          backgroundColor: val === 0
                            ? '#f8fafc'
                            : `rgba(99, 102, 241, ${0.15 + intensity * 0.75})`
                        }}
                        title={`${DAY_NAMES[dayIdx]} ${HOUR_LABELS[hour]}–${HOUR_LABELS[hour + 2] || '12a'}: ${val} booking${val !== 1 ? 's' : ''}`}
                      />
                    );
                  })}
                </React.Fragment>
              ))}
            </div>
            <div className="heatmap-legend">
              <span>Less</span>
              {[0, 0.25, 0.5, 0.75, 1].map((v, i) => (
                <div key={i} className="heatmap-legend-cell" style={{
                  backgroundColor: v === 0 ? '#f8fafc' : `rgba(99, 102, 241, ${0.15 + v * 0.75})`
                }} />
              ))}
              <span>More</span>
            </div>
          </div>
        )}
      </div>
      )}

      {/* Call Analytics Widget */}
      {showSections.callAnalytics && (
      <div className="insights-charts-row">
        <div className="insights-card">
          <h3><i className="fas fa-phone-alt"></i> Call Analytics</h3>
          {!callStats ? (
            <div className="insights-empty">
              <i className="fas fa-phone"></i>
              <p>No call data yet</p>
            </div>
          ) : (
            <>
              <div className="call-stats-grid">
                <div className="call-stat-item">
                  <div className="call-stat-value">{callStats.totalCalls}</div>
                  <div className="call-stat-label">Total Calls</div>
                </div>
                <div className="call-stat-item">
                  <div className="call-stat-value">{callStats.avgDuration >= 60 ? `${(callStats.avgDuration / 60).toFixed(1)}m` : `${Math.round(callStats.avgDuration)}s`}</div>
                  <div className="call-stat-label">Avg Duration</div>
                </div>
                <div className="call-stat-item">
                  <div className="call-stat-value" style={{ color: callStats.conversionRate >= 50 ? '#10b981' : '#f59e0b' }}>{callStats.conversionRate.toFixed(0)}%</div>
                  <div className="call-stat-label">Booking Rate</div>
                </div>
                <div className="call-stat-item">
                  <div className="call-stat-value" style={{ color: callStats.lostJobs > 0 ? '#ef4444' : '#94a3b8' }}>{callStats.lostJobs}</div>
                  <div className="call-stat-label">Lost Jobs</div>
                </div>
              </div>
              <div className="call-outcomes-bar">
                {Object.entries(callStats.outcomes).sort((a, b) => b[1] - a[1]).map(([outcome, count]) => (
                  <div key={outcome} className="call-outcome-segment" style={{ flex: count }} title={`${outcome}: ${count}`}>
                    <span className={`call-outcome-dot ${outcome}`}></span>
                    <span className="call-outcome-text">{outcome.replace(/_/g, ' ')} ({count})</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Completion Rate Widget */}
        {showSections.completionRate && (
        <div className="insights-card">
          <h3><i className="fas fa-check-circle"></i> Job Completion</h3>
          <div className="completion-ring-container">
            <div className="completion-ring">
              <svg viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="42" fill="none" stroke="#f1f5f9" strokeWidth="8" />
                <circle cx="50" cy="50" r="42" fill="none" stroke={stats.completionRate >= 80 ? '#10b981' : stats.completionRate >= 50 ? '#f59e0b' : '#ef4444'} strokeWidth="8" strokeDasharray={`${stats.completionRate * 2.64} 264`} strokeLinecap="round" transform="rotate(-90 50 50)" style={{ transition: 'stroke-dasharray 0.6s ease' }} />
              </svg>
              <div className="completion-ring-text">
                <div className="completion-ring-value">{stats.completionRate.toFixed(0)}%</div>
                <div className="completion-ring-label">Completed</div>
              </div>
            </div>
            <div className="completion-details">
              <div className="completion-detail-row">
                <span className="completion-dot" style={{ background: '#10b981' }}></span>
                <span>Completed</span>
                <span className="completion-detail-count">{bookings.filter(b => b.status === 'completed').length}</span>
              </div>
              <div className="completion-detail-row">
                <span className="completion-dot" style={{ background: '#3b82f6' }}></span>
                <span>Scheduled</span>
                <span className="completion-detail-count">{bookings.filter(b => b.status === 'scheduled' || b.status === 'confirmed').length}</span>
              </div>
              <div className="completion-detail-row">
                <span className="completion-dot" style={{ background: '#f59e0b' }}></span>
                <span>In Progress</span>
                <span className="completion-detail-count">{bookings.filter(b => b.status === 'in-progress').length}</span>
              </div>
              <div className="completion-detail-row">
                <span className="completion-dot" style={{ background: '#ef4444' }}></span>
                <span>Cancelled</span>
                <span className="completion-detail-count">{bookings.filter(b => b.status === 'cancelled').length}</span>
              </div>
            </div>
          </div>
        </div>
        )}
      </div>
      )}

      {/* Lead Funnel Widget */}
      {showSections.leadFunnel && (
      <div className="insights-card">
        <h3><i className="fas fa-filter"></i> Lead Funnel</h3>
        {!leadFunnelStats ? (
          <div className="insights-empty">
            <i className="fas fa-filter"></i>
            <p>No leads in your pipeline yet</p>
          </div>
        ) : (
          <div className="lead-funnel">
            <div className="funnel-summary">
              <span className="funnel-total">{leadFunnelStats.totalLeads} leads</span>
              <span className="funnel-conversion">{leadFunnelStats.overallConversion.toFixed(0)}% conversion</span>
            </div>
            <div className="funnel-stages">
              {leadFunnelStats.stages.map((stage, i) => {
                const count = leadFunnelStats.stageCounts[stage] || 0;
                const pct = leadFunnelStats.totalLeads > 0 ? (count / leadFunnelStats.totalLeads) * 100 : 0;
                const stageColors = { new: '#3b82f6', contacted: '#8b5cf6', qualified: '#f59e0b', proposal: '#ec4899', won: '#10b981', lost: '#ef4444' };
                return (
                  <div key={stage} className="funnel-stage-row">
                    <div className="funnel-stage-label">
                      <span className="funnel-stage-dot" style={{ background: stageColors[stage] || '#94a3b8' }}></span>
                      {stage.charAt(0).toUpperCase() + stage.slice(1)}
                    </div>
                    <div className="funnel-stage-track">
                      <div className="funnel-stage-fill" style={{ width: `${Math.max(pct, count > 0 ? 4 : 0)}%`, background: stageColors[stage] || '#94a3b8' }} />
                    </div>
                    <div className="funnel-stage-count">{count}</div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
      )}

      {/* Employee Utilization Widget */}
      {showSections.employeeUtilization && (
      <div className="insights-card">
        <h3><i className="fas fa-hard-hat"></i> Employee Utilization</h3>
        {stats.employeeUtilization.length === 0 ? (
          <div className="insights-empty">
            <i className="fas fa-hard-hat"></i>
            <p>No employee hours logged yet</p>
          </div>
        ) : (
          <div className="utilization-list">
            {stats.employeeUtilization.slice(0, 6).map((w, i) => (
              <div key={i} className="utilization-row">
                <div className="utilization-name">{w.name}</div>
                <div className="utilization-bar-track">
                  <div className="utilization-bar-fill" style={{ width: `${w.utilization}%`, background: w.utilization >= 80 ? '#10b981' : w.utilization >= 50 ? '#f59e0b' : '#ef4444' }} />
                </div>
                <div className="utilization-pct">{w.utilization.toFixed(0)}%</div>
                <div className="utilization-hours">{w.workedHours.toFixed(0)}h</div>
              </div>
            ))}
          </div>
        )}
      </div>
      )}

      {/* Customer Reviews Summary Widget */}
      {showSections.reviewsSummary && (() => {
        const reviews = reviewsData?.reviews || [];
        const submitted = reviews.filter(r => r.submitted_at);
        const avgRating = submitted.length > 0
          ? (submitted.reduce((s, r) => s + r.rating, 0) / submitted.length).toFixed(1)
          : null;
        return (
          <div className="insights-card">
            <h3><i className="fas fa-star" style={{ color: '#f59e0b' }}></i> Customer Reviews</h3>
            {submitted.length === 0 ? (
              <div className="insights-empty">
                <i className="fas fa-star"></i>
                <p>No reviews submitted yet</p>
              </div>
            ) : (
              <div style={{ display: 'flex', gap: '24px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
                <div style={{ textAlign: 'center', minWidth: '80px' }}>
                  <div style={{ fontSize: '2.2rem', fontWeight: 700, color: '#1e293b', lineHeight: 1 }}>{avgRating}</div>
                  <div style={{ display: 'flex', justifyContent: 'center', gap: '2px', margin: '6px 0' }}>
                    {[1,2,3,4,5].map(s => (
                      <span key={s} style={{ color: s <= Math.round(parseFloat(avgRating)) ? '#f59e0b' : '#e5e7eb', fontSize: '1rem' }}>★</span>
                    ))}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>{submitted.length} review{submitted.length !== 1 ? 's' : ''}</div>
                </div>
                <div style={{ flex: 1, minWidth: '200px' }}>
                  {[5,4,3,2,1].map(star => {
                    const count = submitted.filter(r => r.rating === star).length;
                    const pct = (count / submitted.length * 100);
                    return (
                      <div key={star} style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                        <span style={{ width: '16px', fontSize: '0.78rem', fontWeight: 600, color: '#475569', textAlign: 'right' }}>{star}</span>
                        <div style={{ flex: 1, height: '6px', background: '#f1f5f9', borderRadius: '3px', overflow: 'hidden' }}>
                          <div style={{ height: '100%', width: `${pct}%`, background: '#f59e0b', borderRadius: '3px', transition: 'width 0.4s' }} />
                        </div>
                        <span style={{ width: '20px', fontSize: '0.72rem', color: '#94a3b8' }}>{count}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        );
      })()}
    </div>
  );
}

export default InsightsTab;
