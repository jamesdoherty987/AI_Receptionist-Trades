import React, { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { formatCurrency } from '../../utils/helpers';
import { useIndustry } from '../../context/IndustryContext';
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

const PERIOD_OPTIONS = [
  { key: '7d', label: '7 Days', days: 7 },
  { key: '30d', label: '30 Days', days: 30 },
  { key: '90d', label: '90 Days', days: 90 },
  { key: '6m', label: '6 Months', days: 183 },
  { key: '1y', label: '1 Year', days: 365 },
  { key: 'all', label: 'All Time', days: null },
];

const WIDGET_KEYS = [
  { key: 'overviewCards', icon: 'fa-th-large' },
  { key: 'statsCards', icon: 'fa-chart-pie' },
  { key: 'bookingActivity', icon: 'fa-chart-bar' },
  { key: 'revenueTrend', icon: 'fa-chart-line' },
  { key: 'clientGrowth', icon: 'fa-user-plus' },
  { key: 'servicePopularity', icon: 'fa-star' },
  { key: 'employeeLeaderboard', icon: 'fa-trophy' },
  { key: 'heatmap', icon: 'fa-fire' },
  { key: 'cancellationTrend', icon: 'fa-times-circle' },
  { key: 'durationDistribution', icon: 'fa-clock' },
  { key: 'reviewsSummary', icon: 'fa-star' },
  { key: 'callAnalytics', icon: 'fa-phone-alt' },
  { key: 'leadFunnel', icon: 'fa-filter' },
  { key: 'completionRate', icon: 'fa-check-circle' },
  { key: 'employeeUtilization', icon: 'fa-hard-hat' },
];

function getWidgetLabels(t) {
  return {
    overviewCards: 'Overview',
    statsCards: 'Quick Stats',
    bookingActivity: `${t.job || 'Job'} Activity`,
    revenueTrend: 'Revenue Trend',
    clientGrowth: `New ${t.clients || 'Clients'}`,
    servicePopularity: `${t.service || 'Service'} Popularity`,
    employeeLeaderboard: `${t.employee || 'Employee'} Leaderboard`,
    heatmap: 'Busiest Hours',
    cancellationTrend: 'Cancellation Trend',
    durationDistribution: `${t.job || 'Job'} Duration`,
    reviewsSummary: 'Customer Reviews',
    callAnalytics: 'Call Analytics',
    leadFunnel: 'Lead Funnel',
    completionRate: 'Completion Rate',
    employeeUtilization: `${t.employee || 'Employee'} Utilization`,
  };
}

function InsightsTab({ bookings = [], clients = [], employees = [], reviews: reviewsData }) {
  const { terminology } = useIndustry();
  const [period, setPeriod] = useState('6m');
  const [showCustomize, setShowCustomize] = useState(false);

  const widgetLabels = useMemo(() => getWidgetLabels(terminology), [terminology]);
  const WIDGET_DEFS = useMemo(() => WIDGET_KEYS.map(w => ({ ...w, label: widgetLabels[w.key] || w.key })), [widgetLabels]);

  // Widget visibility (persisted)
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

  // Widget order (persisted)
  const [widgetOrder, setWidgetOrder] = useState(() => {
    try { const saved = localStorage.getItem('insights_widget_order'); return saved ? JSON.parse(saved) : null; } catch { return null; }
  });

  const orderedWidgets = useMemo(() => {
    const ordered = widgetOrder
      ? widgetOrder.map(k => WIDGET_DEFS.find(w => w.key === k)).filter(Boolean)
      : [...WIDGET_DEFS];
    const keys = new Set(ordered.map(w => w.key));
    WIDGET_DEFS.forEach(w => { if (!keys.has(w.key)) ordered.push(w); });
    return ordered;
  }, [widgetOrder, WIDGET_DEFS]);

  const toggleSection = (key) => {
    const next = { ...showSections, [key]: !showSections[key] };
    setShowSections(next);
    localStorage.setItem('insights_visible_sections', JSON.stringify(next));
  };

  const moveWidget = (key, dir) => {
    const keys = orderedWidgets.map(w => w.key);
    const idx = keys.indexOf(key);
    if (idx < 0) return;
    const newIdx = idx + dir;
    if (newIdx < 0 || newIdx >= keys.length) return;
    [keys[idx], keys[newIdx]] = [keys[newIdx], keys[idx]];
    setWidgetOrder(keys);
    localStorage.setItem('insights_widget_order', JSON.stringify(keys));
  };

  // ── Time period filter ──
  const periodDays = PERIOD_OPTIONS.find(p => p.key === period)?.days;
  const cutoffDate = useMemo(() => {
    if (!periodDays) return null;
    const d = new Date();
    d.setDate(d.getDate() - periodDays);
    d.setHours(0, 0, 0, 0);
    return d;
  }, [periodDays]);

  const filteredBookings = useMemo(() => {
    if (!cutoffDate) return bookings;
    return bookings.filter(b => {
      if (!b.appointment_time) return false;
      const d = new Date(b.appointment_time);
      return !isNaN(d) && d >= cutoffDate;
    });
  }, [bookings, cutoffDate]);

  const filteredClients = useMemo(() => {
    if (!cutoffDate) return clients;
    return clients.filter(c => {
      if (!c.created_at) return true; // include clients without dates
      const d = new Date(c.created_at);
      return !isNaN(d) && d >= cutoffDate;
    });
  }, [clients, cutoffDate]);

  // Fetch call logs
  const { data: callLogsData } = useQuery({
    queryKey: ['call-logs-insights'],
    queryFn: async () => (await getCallLogs({ per_page: 200 })).data,
    staleTime: 5 * 60 * 1000,
  });
  const callLogs = useMemo(() => {
    const logs = callLogsData?.call_logs || [];
    if (!cutoffDate) return logs;
    return logs.filter(c => { const d = new Date(c.created_at); return !isNaN(d) && d >= cutoffDate; });
  }, [callLogsData, cutoffDate]);

  // Fetch leads
  const { data: leadsRaw } = useQuery({
    queryKey: ['leads'],
    queryFn: async () => (await getLeads()).data,
    staleTime: 5 * 60 * 1000,
  });
  const leads = leadsRaw?.leads || [];


  // ── Compute all stats from filtered data ──
  const stats = useMemo(() => {
    const now = new Date();
    const nonCancelled = filteredBookings.filter(b => b.status !== 'cancelled');
    const cancelled = filteredBookings.filter(b => b.status === 'cancelled');
    const cancellationRate = filteredBookings.length > 0 ? (cancelled.length / filteredBookings.length) * 100 : 0;

    // Busiest day
    const dayCount = [0, 0, 0, 0, 0, 0, 0];
    nonCancelled.forEach(b => { if (b.appointment_time) { const d = new Date(b.appointment_time); if (!isNaN(d)) dayCount[d.getDay()]++; } });
    const busiestDayIdx = dayCount.indexOf(Math.max(...dayCount));
    const busiestDay = Math.max(...dayCount) > 0 ? DAY_NAMES[busiestDayIdx] : '—';

    // Monthly buckets — dynamic based on period
    const monthCount = periodDays ? Math.min(Math.ceil(periodDays / 30), 12) : 12;
    const monthlyJobs = {};
    const monthlyRevenue = {};
    const monthlyCancellations = {};
    const monthlyTotal = {};
    const clientGrowth = {};
    for (let i = monthCount - 1; i >= 0; i--) {
      const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
      monthlyJobs[key] = 0;
      monthlyRevenue[key] = 0;
      monthlyCancellations[key] = 0;
      monthlyTotal[key] = 0;
      clientGrowth[key] = 0;
    }

    nonCancelled.forEach(b => {
      if (!b.appointment_time) return;
      const d = new Date(b.appointment_time);
      if (isNaN(d)) return;
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
      if (key in monthlyJobs) monthlyJobs[key]++;
      if (key in monthlyRevenue) monthlyRevenue[key] += parseFloat(b.charge || b.estimated_charge || 0);
    });

    filteredBookings.forEach(b => {
      if (!b.appointment_time) return;
      const d = new Date(b.appointment_time);
      if (isNaN(d)) return;
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
      if (key in monthlyTotal) {
        monthlyTotal[key]++;
        if (b.status === 'cancelled') monthlyCancellations[key]++;
      }
    });

    filteredClients.forEach(c => {
      if (!c.created_at) return;
      const d = new Date(c.created_at);
      if (isNaN(d)) return;
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
      if (key in clientGrowth) clientGrowth[key]++;
    });

    const toChartData = (obj) => Object.entries(obj).map(([month, value]) => {
      const [y, m] = month.split('-');
      return { month, label: new Date(+y, +m - 1).toLocaleDateString('en-IE', { month: 'short' }), value };
    });

    const activityData = toChartData(monthlyJobs);
    const revenueTrendData = toChartData(monthlyRevenue);
    const clientGrowthData = toChartData(clientGrowth);
    const cancellationTrendData = Object.entries(monthlyCancellations).map(([month, cancelled]) => {
      const [y, m] = month.split('-');
      const total = monthlyTotal[month] || 1;
      return { month, label: new Date(+y, +m - 1).toLocaleDateString('en-IE', { month: 'short' }), value: Math.round((cancelled / total) * 100) };
    });

    // Employee leaderboard
    const employeeStats = {};
    employees.forEach(w => { employeeStats[w.id] = { name: w.name, jobs: 0, revenue: 0 }; });
    nonCancelled.forEach(b => { (b.assigned_employee_ids || []).forEach(wid => { if (employeeStats[wid]) { employeeStats[wid].jobs++; employeeStats[wid].revenue += parseFloat(b.charge || b.estimated_charge || 0); } }); });
    const employeeLeaderboard = Object.values(employeeStats).filter(w => w.jobs > 0).sort((a, b) => b.jobs - a.jobs).slice(0, 6);

    // Heatmap
    const heatmap = Array.from({ length: 7 }, () => new Array(24).fill(0));
    nonCancelled.forEach(b => { if (b.appointment_time) { const d = new Date(b.appointment_time); if (!isNaN(d)) heatmap[d.getDay()][d.getHours()]++; } });
    const heatmapMax = Math.max(1, ...heatmap.flat());

    // Repeat rate
    const clientJobCount = {};
    nonCancelled.forEach(b => { if (b.client_id) clientJobCount[b.client_id] = (clientJobCount[b.client_id] || 0) + 1; });
    const clientsWithJobs = Object.keys(clientJobCount).length;
    const repeatClients = Object.values(clientJobCount).filter(c => c > 1).length;
    const repeatRate = clientsWithJobs > 0 ? (repeatClients / clientsWithJobs) * 100 : 0;

    // Avg duration, lead time
    const durations = nonCancelled.map(b => b.duration_minutes).filter(d => d && d > 0 && d < 1440);
    const avgDurationMins = durations.length > 0 ? durations.reduce((s, d) => s + d, 0) / durations.length : 0;
    const leadTimes = nonCancelled.filter(b => b.created_at && b.appointment_time).map(b => (new Date(b.appointment_time) - new Date(b.created_at)) / 86400000).filter(d => d >= 0 && d < 365);
    const avgLeadDays = leadTimes.length > 0 ? leadTimes.reduce((s, d) => s + d, 0) / leadTimes.length : 0;

    // Service popularity
    const serviceCount = {};
    nonCancelled.forEach(b => { const svc = b.service_type || b.service || 'Other'; serviceCount[svc] = (serviceCount[svc] || 0) + 1; });
    const servicePopularity = Object.entries(serviceCount).map(([name, count]) => ({ name, count })).sort((a, b) => b.count - a.count);

    // Duration distribution
    const durationBuckets = { '< 1h': 0, '1-2h': 0, '2-4h': 0, '4-8h': 0, 'Full day': 0 };
    nonCancelled.forEach(b => { const d = b.duration_minutes; if (!d || d <= 0) return; if (d < 60) durationBuckets['< 1h']++; else if (d <= 120) durationBuckets['1-2h']++; else if (d <= 240) durationBuckets['2-4h']++; else if (d <= 480) durationBuckets['4-8h']++; else durationBuckets['Full day']++; });
    const durationDistData = Object.entries(durationBuckets).map(([label, count]) => ({ label, value: count }));

    // MoM comparisons
    const actKeys = Object.keys(monthlyJobs);
    const curKey = actKeys[actKeys.length - 1];
    const prevKey = actKeys[actKeys.length - 2];
    const curJobs = monthlyJobs[curKey] || 0;
    const prevJobs = monthlyJobs[prevKey] || 0;
    const jobsMoM = prevJobs > 0 ? ((curJobs - prevJobs) / prevJobs) * 100 : null;
    const curRev = monthlyRevenue[curKey] || 0;
    const prevRev = monthlyRevenue[prevKey] || 0;
    const revenueMoM = prevRev > 0 ? ((curRev - prevRev) / prevRev) * 100 : null;
    const curClients = clientGrowth[curKey] || 0;
    const prevClients = clientGrowth[prevKey] || 0;
    const clientsMoM = prevClients > 0 ? ((curClients - prevClients) / prevClients) * 100 : null;

    const totalRevenue = nonCancelled.reduce((s, b) => s + parseFloat(b.charge || b.estimated_charge || 0), 0);
    const avgRevenuePerJob = nonCancelled.length > 0 ? totalRevenue / nonCancelled.length : 0;
    const completed = nonCancelled.filter(b => b.status === 'completed').length;
    const completionRate = nonCancelled.length > 0 ? (completed / nonCancelled.length) * 100 : 0;

    // Employee utilization
    const employeeUtilization = employees.map(w => {
      const ej = nonCancelled.filter(b => (b.assigned_employee_ids || []).includes(w.id));
      const totalMins = ej.reduce((s, b) => s + (b.duration_minutes || 0), 0);
      const workedHours = totalMins / 60;
      return { name: w.name, workedHours, utilization: Math.min((workedHours / 176) * 100, 100) };
    }).filter(w => w.workedHours > 0).sort((a, b) => b.utilization - a.utilization);

    // CLV
    const revenuePerClient = {};
    nonCancelled.forEach(b => { if (b.client_id) revenuePerClient[b.client_id] = (revenuePerClient[b.client_id] || 0) + parseFloat(b.charge || b.estimated_charge || 0); });
    const clvValues = Object.values(revenuePerClient);
    const avgCLV = clvValues.length > 0 ? clvValues.reduce((s, v) => s + v, 0) / clvValues.length : 0;

    return {
      totalClients: filteredClients.length, totalJobs: nonCancelled.length, cancellationRate, busiestDay,
      activityData, revenueTrendData, clientGrowthData, cancellationTrendData, durationDistData,
      employeeLeaderboard, heatmap, heatmapMax, repeatRate, avgDurationMins, avgLeadDays,
      servicePopularity, jobsMoM, revenueMoM, clientsMoM, avgRevenuePerJob, completionRate,
      employeeUtilization, avgCLV,
    };
  }, [filteredBookings, filteredClients, employees, periodDays]);

  // Call analytics
  const callStats = useMemo(() => {
    if (callLogs.length === 0) return null;
    const totalCalls = callLogs.length;
    const avgDuration = callLogs.reduce((s, c) => s + (c.duration_seconds || 0), 0) / totalCalls;
    const booked = callLogs.filter(c => c.call_outcome === 'booked').length;
    const conversionRate = totalCalls > 0 ? (booked / totalCalls) * 100 : 0;
    const lostJobs = callLogs.filter(c => c.is_lost_job).length;
    const outcomes = {};
    callLogs.forEach(c => { const o = c.call_outcome || 'no_action'; outcomes[o] = (outcomes[o] || 0) + 1; });
    return { totalCalls, avgDuration, conversionRate, lostJobs, outcomes };
  }, [callLogs]);

  // Lead funnel
  const leadFunnelStats = useMemo(() => {
    if (leads.length === 0) return null;
    const stages = ['new', 'contacted', 'qualified', 'proposal', 'won', 'lost'];
    const stageCounts = {};
    stages.forEach(s => { stageCounts[s] = 0; });
    leads.forEach(l => { const s = l.stage || 'new'; stageCounts[s] = (stageCounts[s] || 0) + 1; });
    const wonLeads = stageCounts['won'] || 0;
    return { stageCounts, stages, totalLeads: leads.length, wonLeads, overallConversion: leads.length > 0 ? (wonLeads / leads.length) * 100 : 0 };
  }, [leads]);


  // ── Render ──
  const visibleCount = WIDGET_KEYS.filter(w => showSections[w.key]).length;

  return (
    <div className="insights-tab">
      {/* Header with period filter + customize */}
      <div className="ins-header">
        <div className="ins-period-bar">
          {PERIOD_OPTIONS.map(p => (
            <button key={p.key} className={`ins-period-btn ${period === p.key ? 'active' : ''}`}
              onClick={() => setPeriod(p.key)}>{p.label}</button>
          ))}
        </div>
        <button className={`ins-customize-btn ${showCustomize ? 'active' : ''}`}
          onClick={() => setShowCustomize(!showCustomize)}>
          <i className={`fas ${showCustomize ? 'fa-times' : 'fa-sliders-h'}`}></i>
          <span>{showCustomize ? 'Done' : 'Customize'}</span>
          <span className="ins-customize-count">{visibleCount}/{WIDGET_KEYS.length}</span>
        </button>
      </div>

      {/* Customize Panel */}
      {showCustomize && (
        <div className="ins-customize-panel">
          {orderedWidgets.map((w, idx) => (
            <div key={w.key} className={`ins-widget-row ${showSections[w.key] ? 'active' : ''}`}>
              <div className="ins-widget-arrows">
                <button onClick={() => moveWidget(w.key, -1)} disabled={idx === 0}><i className="fas fa-chevron-up"></i></button>
                <button onClick={() => moveWidget(w.key, 1)} disabled={idx === orderedWidgets.length - 1}><i className="fas fa-chevron-down"></i></button>
              </div>
              <button className="ins-widget-name" onClick={() => toggleSection(w.key)}>
                <i className={`fas ${w.icon}`}></i>
                <span>{w.label}</span>
                <i className={`fas ${showSections[w.key] ? 'fa-toggle-on' : 'fa-toggle-off'}`} style={{ marginLeft: 'auto', fontSize: '1rem', color: showSections[w.key] ? '#6366f1' : '#cbd5e1' }}></i>
              </button>
            </div>
          ))}
        </div>
      )}

      {/* ═══ WIDGETS ═══ */}
      {orderedWidgets.filter(w => showSections[w.key]).map(w => {
        switch (w.key) {
          case 'overviewCards': return (
            <div key={w.key} className="ins-kpi-row">
              <KpiCard icon="fa-briefcase" color="#6366f1" value={stats.totalJobs} label={`Total ${terminology.jobs || 'Jobs'}`} mom={stats.jobsMoM} />
              <KpiCard icon="fa-users" color="#3b82f6" value={stats.totalClients} label={terminology.clients || 'Clients'} mom={stats.clientsMoM} />
              <KpiCard icon="fa-times-circle" color={stats.cancellationRate > 15 ? '#ef4444' : '#6366f1'} value={`${stats.cancellationRate.toFixed(1)}%`} label="Cancellation Rate" />
              <KpiCard icon="fa-fire" color="#f59e0b" value={stats.busiestDay} label="Busiest Day" />
            </div>
          );
          case 'statsCards': return (
            <div key={w.key} className="ins-kpi-row">
              <KpiCard icon="fa-redo" color={stats.repeatRate >= 30 ? '#10b981' : '#f59e0b'} value={`${stats.repeatRate.toFixed(0)}%`} label="Repeat Customers" />
              <KpiCard icon="fa-receipt" color="#10b981" value={formatCurrency(stats.avgRevenuePerJob)} label="Avg Ticket" mom={stats.revenueMoM} />
              <KpiCard icon="fa-gem" color="#8b5cf6" value={formatCurrency(stats.avgCLV)} label={`Avg ${terminology.client || 'Client'} Value`} />
              <KpiCard icon="fa-calendar-check" color="#0ea5e9" value={stats.avgLeadDays < 1 ? 'Same day' : `${Math.round(stats.avgLeadDays)}d`} label="Avg Lead Time" />
            </div>
          );
          case 'bookingActivity': return (
            <div key={w.key} className="ins-card">
              <h3><i className="fas fa-chart-bar"></i> {terminology.job || 'Job'} Activity</h3>
              <BarChart data={stats.activityData} color="#6366f1" />
            </div>
          );
          case 'revenueTrend': return (
            <div key={w.key} className="ins-card">
              <h3><i className="fas fa-euro-sign"></i> Revenue Trend</h3>
              <AreaChart data={stats.revenueTrendData} color="#10b981" formatValue={formatCurrency} />
            </div>
          );
          case 'clientGrowth': return (
            <div key={w.key} className="ins-card">
              <h3><i className="fas fa-user-plus"></i> New {terminology.clients || 'Clients'}</h3>
              <BarChart data={stats.clientGrowthData} color="#10b981" />
            </div>
          );
          case 'servicePopularity': return (
            <div key={w.key} className="ins-card">
              <h3><i className="fas fa-concierge-bell"></i> Service Popularity</h3>
              {stats.servicePopularity.length === 0 ? <EmptyState icon="fa-list" text="No services booked yet" /> : (
                <div className="ins-h-bars">
                  {stats.servicePopularity.slice(0, 6).map((svc, i) => {
                    const max = stats.servicePopularity[0]?.count || 1;
                    return (
                      <div key={i} className="ins-h-bar-row">
                        <div className="ins-h-bar-label">{svc.name}</div>
                        <div className="ins-h-bar-track"><div className="ins-h-bar-fill" style={{ width: `${Math.max((svc.count / max) * 100, 4)}%`, background: 'linear-gradient(90deg, #c084fc, #8b5cf6)' }} /></div>
                        <div className="ins-h-bar-val" style={{ color: '#8b5cf6' }}>{svc.count}</div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
          case 'employeeLeaderboard': return (
            <div key={w.key} className="ins-card">
              <h3><i className="fas fa-trophy"></i> {terminology.employee || 'Employee'} Leaderboard</h3>
              {stats.employeeLeaderboard.length === 0 ? <EmptyState icon="fa-hard-hat" text={`Assign ${(terminology.employees || 'employees').toLowerCase()} to ${(terminology.jobs || 'jobs').toLowerCase()} to see stats`} /> : (
                <div className="leaderboard">
                  {stats.employeeLeaderboard.map((emp, i) => (
                    <div key={i} className="leaderboard-row">
                      <div className="leaderboard-rank" data-rank={i + 1}>{i + 1}</div>
                      <div className="leaderboard-info">
                        <div className="leaderboard-name">{emp.name}</div>
                        <div className="leaderboard-meta">{emp.jobs} {emp.jobs !== 1 ? (terminology.jobs || 'jobs').toLowerCase() : (terminology.job || 'job').toLowerCase()} · {formatCurrency(emp.revenue)}</div>
                      </div>
                      <div className="leaderboard-bar-track"><div className="leaderboard-bar-fill" style={{ width: `${(emp.jobs / stats.employeeLeaderboard[0].jobs) * 100}%` }} /></div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
          case 'heatmap': return (
            <div key={w.key} className="ins-card ins-card-wide">
              <h3><i className="fas fa-clock"></i> Busiest Hours</h3>
              {stats.totalJobs === 0 ? <EmptyState icon="fa-calendar-alt" text={`Book some ${(terminology.jobs || 'jobs').toLowerCase()} to see patterns`} /> : (
                <div className="heatmap-container">
                  <div className="heatmap-grid" style={{ gridTemplateColumns: `36px repeat(12, 1fr)` }}>
                    <div className="heatmap-corner"></div>
                    {HOUR_LABELS.filter((_, i) => i % 2 === 0).map((h, i) => (<div key={i} className="heatmap-hour-label">{h}</div>))}
                    {[1, 2, 3, 4, 5, 6, 0].map(dayIdx => (
                      <React.Fragment key={dayIdx}>
                        <div className="heatmap-day-label">{DAY_NAMES[dayIdx]}</div>
                        {Array.from({ length: 12 }, (_, hi) => {
                          const hour = hi * 2;
                          const val = stats.heatmap[dayIdx][hour] + stats.heatmap[dayIdx][hour + 1];
                          const intensity = val / (stats.heatmapMax * 2);
                          return (<div key={hi} className="heatmap-cell" style={{ backgroundColor: val === 0 ? '#f8fafc' : `rgba(99, 102, 241, ${0.15 + intensity * 0.75})` }} title={`${DAY_NAMES[dayIdx]} ${HOUR_LABELS[hour]}–${HOUR_LABELS[hour + 2] || '12a'}: ${val}`} />);
                        })}
                      </React.Fragment>
                    ))}
                  </div>
                  <div className="heatmap-legend">
                    <span>Less</span>
                    {[0, 0.25, 0.5, 0.75, 1].map((v, i) => (<div key={i} className="heatmap-legend-cell" style={{ backgroundColor: v === 0 ? '#f8fafc' : `rgba(99, 102, 241, ${0.15 + v * 0.75})` }} />))}
                    <span>More</span>
                  </div>
                </div>
              )}
            </div>
          );
          case 'cancellationTrend': return (
            <div key={w.key} className="ins-card">
              <h3><i className="fas fa-times-circle"></i> Cancellation Trend</h3>
              <BarChart data={stats.cancellationTrendData} color="#ef4444" suffix="%" />
            </div>
          );
          case 'durationDistribution': return (
            <div key={w.key} className="ins-card">
              <h3><i className="fas fa-hourglass-half"></i> {terminology.job || 'Job'} Duration</h3>
              <BarChart data={stats.durationDistData} color="#10b981" />
            </div>
          );
          case 'callAnalytics': return (
            <div key={w.key} className="ins-card">
              <h3><i className="fas fa-phone-alt"></i> Call Analytics</h3>
              {!callStats ? <EmptyState icon="fa-phone" text="No call data yet" /> : (
                <>
                  <div className="call-stats-grid">
                    <div className="call-stat-item"><div className="call-stat-value">{callStats.totalCalls}</div><div className="call-stat-label">Total Calls</div></div>
                    <div className="call-stat-item"><div className="call-stat-value">{callStats.avgDuration >= 60 ? `${(callStats.avgDuration / 60).toFixed(1)}m` : `${Math.round(callStats.avgDuration)}s`}</div><div className="call-stat-label">Avg Duration</div></div>
                    <div className="call-stat-item"><div className="call-stat-value" style={{ color: callStats.conversionRate >= 50 ? '#10b981' : '#f59e0b' }}>{callStats.conversionRate.toFixed(0)}%</div><div className="call-stat-label">Booking Rate</div></div>
                    <div className="call-stat-item"><div className="call-stat-value" style={{ color: callStats.lostJobs > 0 ? '#ef4444' : '#94a3b8' }}>{callStats.lostJobs}</div><div className="call-stat-label">Lost Jobs</div></div>
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
          );
          case 'completionRate': return (
            <div key={w.key} className="ins-card">
              <h3><i className="fas fa-check-circle"></i> {terminology.job || 'Job'} Completion</h3>
              <div className="completion-ring-container">
                <div className="completion-ring">
                  <svg viewBox="0 0 100 100">
                    <circle cx="50" cy="50" r="42" fill="none" stroke="#f1f5f9" strokeWidth="8" />
                    <circle cx="50" cy="50" r="42" fill="none" stroke={stats.completionRate >= 80 ? '#10b981' : stats.completionRate >= 50 ? '#f59e0b' : '#ef4444'} strokeWidth="8" strokeDasharray={`${stats.completionRate * 2.64} 264`} strokeLinecap="round" transform="rotate(-90 50 50)" style={{ transition: 'stroke-dasharray 0.6s ease' }} />
                  </svg>
                  <div className="completion-ring-text"><div className="completion-ring-value">{stats.completionRate.toFixed(0)}%</div><div className="completion-ring-label">Completed</div></div>
                </div>
                <div className="completion-details">
                  <div className="completion-detail-row"><span className="completion-dot" style={{ background: '#10b981' }}></span><span>Completed</span><span className="completion-detail-count">{filteredBookings.filter(b => b.status === 'completed').length}</span></div>
                  <div className="completion-detail-row"><span className="completion-dot" style={{ background: '#3b82f6' }}></span><span>Scheduled</span><span className="completion-detail-count">{filteredBookings.filter(b => b.status === 'scheduled' || b.status === 'confirmed').length}</span></div>
                  <div className="completion-detail-row"><span className="completion-dot" style={{ background: '#f59e0b' }}></span><span>In Progress</span><span className="completion-detail-count">{filteredBookings.filter(b => b.status === 'in-progress').length}</span></div>
                  <div className="completion-detail-row"><span className="completion-dot" style={{ background: '#ef4444' }}></span><span>Cancelled</span><span className="completion-detail-count">{filteredBookings.filter(b => b.status === 'cancelled').length}</span></div>
                </div>
              </div>
            </div>
          );
          case 'leadFunnel': return (
            <div key={w.key} className="ins-card ins-card-wide">
              <h3><i className="fas fa-filter"></i> Lead Funnel</h3>
              {!leadFunnelStats ? <EmptyState icon="fa-filter" text="No leads in your pipeline yet" /> : (
                <div className="lead-funnel">
                  <div className="funnel-summary"><span className="funnel-total">{leadFunnelStats.totalLeads} leads</span><span className="funnel-conversion">{leadFunnelStats.overallConversion.toFixed(0)}% conversion</span></div>
                  <div className="funnel-stages">
                    {leadFunnelStats.stages.map(stage => {
                      const count = leadFunnelStats.stageCounts[stage] || 0;
                      const pct = leadFunnelStats.totalLeads > 0 ? (count / leadFunnelStats.totalLeads) * 100 : 0;
                      const colors = { new: '#3b82f6', contacted: '#8b5cf6', qualified: '#f59e0b', proposal: '#ec4899', won: '#10b981', lost: '#ef4444' };
                      return (
                        <div key={stage} className="funnel-stage-row">
                          <div className="funnel-stage-label"><span className="funnel-stage-dot" style={{ background: colors[stage] || '#94a3b8' }}></span>{stage.charAt(0).toUpperCase() + stage.slice(1)}</div>
                          <div className="funnel-stage-track"><div className="funnel-stage-fill" style={{ width: `${Math.max(pct, count > 0 ? 4 : 0)}%`, background: colors[stage] || '#94a3b8' }} /></div>
                          <div className="funnel-stage-count">{count}</div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          );
          case 'employeeUtilization': return (
            <div key={w.key} className="ins-card">
              <h3><i className="fas fa-hard-hat"></i> {terminology.employee || 'Employee'} Utilization</h3>
              {stats.employeeUtilization.length === 0 ? <EmptyState icon="fa-hard-hat" text={`No ${(terminology.employee || 'employee').toLowerCase()} hours logged yet`} /> : (
                <div className="utilization-list">
                  {stats.employeeUtilization.slice(0, 6).map((emp, i) => (
                    <div key={i} className="utilization-row">
                      <div className="utilization-name">{emp.name}</div>
                      <div className="utilization-bar-track"><div className="utilization-bar-fill" style={{ width: `${emp.utilization}%`, background: emp.utilization >= 80 ? '#10b981' : emp.utilization >= 50 ? '#f59e0b' : '#ef4444' }} /></div>
                      <div className="utilization-pct">{emp.utilization.toFixed(0)}%</div>
                      <div className="utilization-hours">{emp.workedHours.toFixed(0)}h</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
          case 'reviewsSummary': {
            const reviews = reviewsData?.reviews || [];
            const submitted = reviews.filter(r => r.submitted_at);
            const avgRating = submitted.length > 0 ? (submitted.reduce((s, r) => s + r.rating, 0) / submitted.length).toFixed(1) : null;
            return (
              <div key={w.key} className="ins-card">
                <h3><i className="fas fa-star" style={{ color: '#f59e0b' }}></i> Customer Reviews</h3>
                {submitted.length === 0 ? <EmptyState icon="fa-star" text="No reviews submitted yet" /> : (
                  <div className="ins-reviews">
                    <div className="ins-reviews-score">
                      <div className="ins-reviews-num">{avgRating}</div>
                      <div className="ins-reviews-stars">{[1,2,3,4,5].map(s => (<span key={s} style={{ color: s <= Math.round(parseFloat(avgRating)) ? '#f59e0b' : '#e5e7eb' }}>★</span>))}</div>
                      <div className="ins-reviews-count">{submitted.length} review{submitted.length !== 1 ? 's' : ''}</div>
                    </div>
                    <div className="ins-reviews-bars">
                      {[5,4,3,2,1].map(star => {
                        const count = submitted.filter(r => r.rating === star).length;
                        const pct = (count / submitted.length * 100);
                        return (
                          <div key={star} className="ins-reviews-bar-row">
                            <span className="ins-reviews-star-num">{star}</span>
                            <div className="ins-reviews-bar-track"><div className="ins-reviews-bar-fill" style={{ width: `${pct}%` }} /></div>
                            <span className="ins-reviews-bar-count">{count}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            );
          }
          default: return null;
        }
      })}
    </div>
  );
}


/* ── Reusable Components ── */

function KpiCard({ icon, color, value, label, mom }) {
  return (
    <div className="ins-kpi">
      <div className="ins-kpi-icon" style={{ background: `${color}15` }}>
        <i className={`fas ${icon}`} style={{ color }}></i>
      </div>
      <div className="ins-kpi-body">
        <span className="ins-kpi-value">
          {value}
          {mom != null && <span className={`ins-mom ${mom >= 0 ? 'up' : 'down'}`}>{mom >= 0 ? '↑' : '↓'}{Math.abs(mom).toFixed(0)}%</span>}
        </span>
        <span className="ins-kpi-label">{label}</span>
      </div>
    </div>
  );
}

function EmptyState({ icon, text }) {
  return (
    <div className="ins-empty">
      <i className={`fas ${icon}`}></i>
      <p>{text}</p>
    </div>
  );
}

function BarChart({ data, color = '#6366f1', suffix = '', formatValue }) {
  const max = Math.max(1, ...data.map(d => d.value));
  return (
    <div className="ins-bar-chart">
      {data.map((d, i) => (
        <div key={i} className="ins-bar-col">
          <div className="ins-bar-wrapper">
            <div className="ins-bar-fill" style={{ height: `${(d.value / max) * 100}%`, background: `linear-gradient(180deg, ${color}99, ${color})` }} />
          </div>
          <span className="ins-bar-val" style={{ color }}>{formatValue ? formatValue(d.value) : `${d.value}${suffix}`}</span>
          <span className="ins-bar-label">{d.label}</span>
        </div>
      ))}
    </div>
  );
}

function AreaChart({ data, color = '#6366f1', formatValue }) {
  if (!data || data.length === 0) return <EmptyState icon="fa-chart-line" text="No data yet" />;

  const max = Math.max(1, ...data.map(d => d.value));
  const padding = { top: 12, right: 12, bottom: 6, left: 12 };
  const width = 600, height = 160;
  const chartW = width - padding.left - padding.right;
  const chartH = height - padding.top - padding.bottom;

  const points = data.map((item, i) => {
    const x = data.length === 1 ? width / 2 : padding.left + (i / (data.length - 1)) * chartW;
    const y = padding.top + chartH - (max > 0 ? (item.value / max) * chartH * 0.85 : 0);
    return { x, y, ...item };
  });

  if (points.length === 1) {
    return (
      <div className="ins-area-chart">
        <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="xMidYMid meet">
          <circle cx={points[0].x} cy={points[0].y} r="4" fill={color} />
        </svg>
        <div className="ins-area-labels">
          <div className="ins-area-label" style={{ left: '50%' }}>
            <span style={{ color }}>{formatValue ? formatValue(points[0].value) : points[0].value}</span>
            <span>{points[0].label}</span>
          </div>
        </div>
      </div>
    );
  }

  // Build smooth path
  let linePath = `M${points[0].x},${points[0].y}`;
  for (let i = 0; i < points.length - 1; i++) {
    const cp = (points[i + 1].x - points[i].x) / 3;
    linePath += ` C${points[i].x + cp},${points[i].y} ${points[i + 1].x - cp},${points[i + 1].y} ${points[i + 1].x},${points[i + 1].y}`;
  }
  const bottomY = padding.top + chartH;
  const areaPath = `${linePath} L${points[points.length - 1].x},${bottomY} L${points[0].x},${bottomY} Z`;

  const step = Math.max(1, Math.ceil(points.length / 8));
  const labelIndices = new Set();
  for (let i = 0; i < points.length; i += step) labelIndices.add(i);
  labelIndices.add(points.length - 1);

  return (
    <div className="ins-area-chart">
      <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="xMidYMid meet">
        <defs>
          <linearGradient id={`areaGrad-${color.replace('#','')}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.15" />
            <stop offset="100%" stopColor={color} stopOpacity="0.01" />
          </linearGradient>
        </defs>
        {[0.25, 0.5, 0.75].map((pct, i) => (
          <line key={i} x1={padding.left} y1={padding.top + chartH * (1 - pct * 0.85)} x2={width - padding.right} y2={padding.top + chartH * (1 - pct * 0.85)} stroke="#f1f5f9" strokeWidth="0.7" />
        ))}
        <path d={areaPath} fill={`url(#areaGrad-${color.replace('#','')})`} />
        <path d={linePath} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        {points.filter((_, i) => labelIndices.has(i)).map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r="3" fill="white" stroke={color} strokeWidth="1.5" />
        ))}
      </svg>
      <div className="ins-area-labels">
        {points.filter((_, i) => labelIndices.has(i)).map((p, i) => (
          <div key={i} className="ins-area-label" style={{ left: `${(p.x / width) * 100}%` }}>
            <span style={{ color }}>{formatValue ? formatValue(p.value) : p.value}</span>
            <span>{p.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default InsightsTab;
