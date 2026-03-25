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

      {/* Two-column layout: Worker Leaderboard + Heatmap */}
      <div className="insights-charts-row">
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

        {/* Busiest Hours Heatmap */}
        <div className="insights-card">
          <h3><i className="fas fa-clock"></i> Busiest Hours</h3>
          {stats.totalJobs === 0 ? (
            <div className="insights-empty">
              <i className="fas fa-calendar-alt"></i>
              <p>Book some jobs to see patterns</p>
            </div>
          ) : (
            <div className="heatmap-container">
              <div className="heatmap-grid">
                {/* Header row */}
                <div className="heatmap-corner"></div>
                {HOUR_LABELS.filter((_, i) => i % 2 === 0).map((h, i) => (
                  <div key={i} className="heatmap-hour-label">{h}</div>
                ))}
                {/* Day rows */}
                {[1, 2, 3, 4, 5, 6, 0].map(dayIdx => (
                  <div key={dayIdx} className="heatmap-row">
                    <div className="heatmap-day-label">{DAY_NAMES[dayIdx]}</div>
                    {Array.from({ length: 12 }, (_, hi) => {
                      const hour = hi * 2;
                      const val = stats.heatmap[dayIdx][hour] + stats.heatmap[dayIdx][hour + 1];
                      const intensity = val / (stats.heatmapMax * 2);
                      return (
                        <div
                          key={hi}
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
                  </div>
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
    </div>
  );
}

export default InsightsTab;
