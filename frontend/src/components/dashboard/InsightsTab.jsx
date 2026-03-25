import { useMemo } from 'react';
import { formatCurrency } from '../../utils/helpers';
import './InsightsTab.css';

const DAY_NAMES = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const HOUR_LABELS = Array.from({ length: 24 }, (_, i) => {
  if (i === 0) return '12a';
  if (i < 12) return `${i}a`;
  if (i === 12) return '12p';
  return `${i - 12}p`;
});

function InsightsTab({ bookings = [], clients = [], workers = [] }) {
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
    };
  }, [bookings, clients, workers]);

  const maxActivity = Math.max(1, ...stats.activityData.map(d => d.count));
  const maxClientGrowth = Math.max(1, ...stats.clientGrowthData.map(d => d.count));

  return (
    <div className="insights-tab">
      {/* Overview Cards */}
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

      {/* Second row of stats */}
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

      {/* Two-column layout: Activity + Client Growth */}
      <div className="insights-charts-row">
        {/* Booking Activity */}
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

        {/* Client Growth */}
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
      </div>

      {/* Service Popularity + Worker Leaderboard */}
      <div className="insights-charts-row">
        {/* Service Popularity */}
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

        {/* Worker Leaderboard */}
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
      </div>

      {/* Busiest Hours Heatmap — full width */}
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
    </div>
  );
}

export default InsightsTab;
