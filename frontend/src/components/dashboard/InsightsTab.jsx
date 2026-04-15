import { useMemo, useState } from 'react';
import { formatCurrency } from '../../utils/helpers';
import './InsightsTab.css';

const DAY_NAMES = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const HOUR_LABELS = Array.from({ length: 24 }, (_, i) => {
  if (i === 0) return '12a';
  if (i < 12) return `${i}a`;
  if (i === 12) return '12p';
  return `${i - 12}p`;
});

function InsightsTab({ bookings = [], clients = [], workers = [], reviews: reviewsData }) {
  // Graph visibility toggles (persisted in localStorage)
  const [showSections, setShowSections] = useState(() => {
    try {
      const saved = localStorage.getItem('insights_visible_sections');
      return saved ? JSON.parse(saved) : {
        overviewCards: true, statsCards: true, bookingActivity: true,
        clientGrowth: true, servicePopularity: true, workerLeaderboard: true, heatmap: true,
        revenueTrend: true, cancellationTrend: false, durationDistribution: false, reviewsSummary: true
      };
    } catch { return { overviewCards: true, statsCards: true, bookingActivity: true, clientGrowth: true, servicePopularity: true, workerLeaderboard: true, heatmap: true, revenueTrend: true, cancellationTrend: false, durationDistribution: false, reviewsSummary: true }; }
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
    { key: 'workerLeaderboard', label: 'Worker Leaderboard', icon: 'fa-trophy' },
    { key: 'heatmap', label: 'Busiest Hours', icon: 'fa-fire' },
    { key: 'cancellationTrend', label: 'Cancellation Trend', icon: 'fa-times-circle' },
    { key: 'durationDistribution', label: 'Job Duration', icon: 'fa-clock' },
    { key: 'reviewsSummary', label: 'Customer Reviews', icon: 'fa-star' },
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

    // Worker leaderboard
    const workerStats = {};
    workers.forEach(w => {
      workerStats[w.id] = { name: w.name, jobs: 0, revenue: 0 };
    });
    nonCancelled.forEach(b => {
      const ids = b.assigned_worker_ids || [];
      ids.forEach(wid => {
        if (workerStats[wid]) {
          workerStats[wid].jobs++;
          workerStats[wid].revenue += parseFloat(b.charge || b.estimated_charge || 0);
        }
      });
    });
    const workerLeaderboard = Object.values(workerStats)
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

    return {
      totalClients: clients.length,
      totalJobs: nonCancelled.length,
      cancellationRate,
      busiestDay,
      activityData,
      workerLeaderboard,
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
    };
  }, [bookings, clients, workers]);

  const maxActivity = Math.max(1, ...stats.activityData.map(d => d.count));
  const maxClientGrowth = Math.max(1, ...stats.clientGrowthData.map(d => d.count));
  const maxRevenueTrend = Math.max(1, ...stats.revenueTrendData.map(d => d.revenue));
  const maxDurationDist = Math.max(1, ...stats.durationDistData.map(d => d.count));

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
            <div className="overview-value">{stats.totalJobs}</div>
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
          <div className="overview-icon" style={{ background: 'rgba(139, 92, 246, 0.1)' }}>
            <i className="fas fa-hourglass-half" style={{ color: '#8b5cf6' }}></i>
          </div>
          <div className="overview-content">
            <div className="overview-value">{stats.avgDurationMins >= 60 ? `${(stats.avgDurationMins / 60).toFixed(1)}h` : `${Math.round(stats.avgDurationMins)}m`}</div>
            <div className="overview-label">Avg Job Duration</div>
          </div>
        </div>
        <div className="overview-card">
          <div className="overview-icon" style={{ background: 'rgba(14, 165, 233, 0.1)' }}>
            <i className="fas fa-calendar-check" style={{ color: '#0ea5e9' }}></i>
          </div>
          <div className="overview-content">
            <div className="overview-value">{stats.avgLeadDays < 1 ? 'Same day' : `${Math.round(stats.avgLeadDays)}d`}</div>
            <div className="overview-label">Avg Lead Time</div>
          </div>
        </div>
        <div className="overview-card">
          <div className="overview-icon" style={{ background: 'rgba(236, 72, 153, 0.1)' }}>
            <i className="fas fa-star" style={{ color: '#ec4899' }}></i>
          </div>
          <div className="overview-content">
            <div className="overview-value" style={{ fontSize: stats.servicePopularity[0]?.name?.length > 10 ? '0.95rem' : undefined }}>{stats.servicePopularity[0]?.name || '—'}</div>
            <div className="overview-label">Top Service</div>
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

      {/* Service Popularity + Worker Leaderboard */}
      {(showSections.servicePopularity || showSections.workerLeaderboard) && (
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

        {/* Worker Leaderboard */}
        {showSections.workerLeaderboard && (
        <div className="insights-card">
          <h3><i className="fas fa-trophy"></i> Worker Leaderboard</h3>
          {stats.workerLeaderboard.length === 0 ? (
            <div className="insights-empty">
              <i className="fas fa-hard-hat"></i>
              <p>Assign workers to jobs to see stats</p>
            </div>
          ) : (
            <div className="leaderboard">
              {stats.workerLeaderboard.map((w, i) => (
                <div key={i} className="leaderboard-row">
                  <div className="leaderboard-rank" data-rank={i + 1}>{i + 1}</div>
                  <div className="leaderboard-info">
                    <div className="leaderboard-name">{w.name}</div>
                    <div className="leaderboard-meta">{w.jobs} job{w.jobs !== 1 ? 's' : ''} · {formatCurrency(w.revenue)}</div>
                  </div>
                  <div className="leaderboard-bar-track">
                    <div
                      className="leaderboard-bar-fill"
                      style={{ width: `${(w.jobs / stats.workerLeaderboard[0].jobs) * 100}%` }}
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
                <>
                  <div key={`label-${dayIdx}`} className="heatmap-day-label">{DAY_NAMES[dayIdx]}</div>
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
                </>
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
