import { useState, useCallback } from 'react';
import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { getCallLogs } from '../../services/api';
import { formatPhone, getProxiedMediaUrl } from '../../utils/helpers';
import './CallLogsTab.css';

const FILTERS = [
  { key: 'all', label: 'All', icon: 'fa-list' },
  { key: 'lost', label: 'Lost Jobs', icon: 'fa-exclamation-triangle' },
  { key: 'booked', label: 'Booked', icon: 'fa-calendar-check' },
  { key: 'cancelled', label: 'Cancelled', icon: 'fa-times-circle' },
  { key: 'rescheduled', label: 'Rescheduled', icon: 'fa-calendar-alt' },
  { key: 'no_booking', label: 'No Booking', icon: 'fa-phone-slash' },
];

const OUTCOME_LABELS = {
  booked: 'Booked', cancelled: 'Cancelled', rescheduled: 'Rescheduled',
  enquiry: 'Enquiry', wrong_number: 'Wrong Number', hung_up: 'Hung Up', no_action: 'No Action',
};

const OUTCOME_ICONS = {
  booked: 'fa-calendar-check', cancelled: 'fa-times-circle', rescheduled: 'fa-calendar-alt',
  enquiry: 'fa-question-circle', wrong_number: 'fa-phone-slash',
  hung_up: 'fa-phone-slash', no_action: 'fa-minus-circle',
};

function formatDuration(seconds) {
  if (!seconds && seconds !== 0) return '—';
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return s > 0 ? `${m}m ${s}s` : `${m}m`;
}

function formatRelativeTime(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  const now = new Date();
  const diffMs = now - d;
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;
  return d.toLocaleDateString('en-IE', { day: 'numeric', month: 'short', year: d.getFullYear() !== now.getFullYear() ? 'numeric' : undefined });
}

function CallLogsTab() {
  const [activeFilter, setActiveFilter] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [page, setPage] = useState(1);
  const [selectedLog, setSelectedLog] = useState(null);

  const { data, isLoading } = useQuery({
    queryKey: ['call-logs', activeFilter, searchTerm, page],
    queryFn: async () => {
      const params = { page, per_page: 50 };
      // Map filter key to API params
      if (activeFilter === 'lost') {
        params.lost_only = 'true';
      } else if (activeFilter === 'no_booking') {
        params.outcome = 'no_booking';
      } else if (activeFilter !== 'all') {
        params.outcome = activeFilter;
      }
      if (searchTerm.trim()) params.search = searchTerm.trim();
      const res = await getCallLogs(params);
      return res.data;
    },
    placeholderData: keepPreviousData,
  });

  const logs = data?.call_logs || [];
  const totalPages = data?.total_pages || 1;
  const total = data?.total || 0;

  const handleFilterChange = useCallback((key) => {
    setActiveFilter(key);
    setPage(1);
  }, []);

  const handleSearch = useCallback((e) => {
    setSearchTerm(e.target.value);
    setPage(1);
  }, []);

  return (
    <div className="call-logs-tab">
      <div className="call-logs-header">
        <h2>Call Logs {total > 0 && <span style={{ fontWeight: 400, fontSize: '0.85rem', color: '#94a3b8' }}>({total})</span>}</h2>
        <div className="call-logs-controls">
          <div className="search-box">
            <i className="fas fa-search"></i>
            <input type="text" placeholder="Search by name, phone, address..." value={searchTerm} onChange={handleSearch} />
          </div>
        </div>
      </div>

      <div className="call-logs-filters">
        {FILTERS.map(f => (
          <button
            key={f.key}
            className={`filter-btn ${activeFilter === f.key ? 'active' : ''} ${f.key === 'lost' ? 'lost-filter' : ''}`}
            onClick={() => handleFilterChange(f.key)}
          >
            <i className={`fas ${f.icon}`}></i> {f.label}
          </button>
        ))}
      </div>

      <div className="call-logs-list">
        {isLoading ? (
          <div className="empty-state"><p>Loading calls...</p></div>
        ) : logs.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">📞</div>
            <p>{searchTerm || activeFilter !== 'all' ? 'No calls match your filters' : 'No calls logged yet'}</p>
          </div>
        ) : (
          logs.map(log => (
            <div key={log.id} className={`call-log-card ${log.is_lost_job ? 'lost-job' : ''}`} onClick={() => setSelectedLog(log)}>
              <div className={`call-log-icon ${log.is_lost_job ? 'lost' : (log.call_outcome || 'no_action')}`}>
                <i className={`fas ${log.is_lost_job ? 'fa-exclamation-triangle' : (OUTCOME_ICONS[log.call_outcome] || 'fa-phone')}`}></i>
              </div>
              <div className="call-log-info">
                <h3>
                  {log.caller_name || formatPhone(log.phone_number) || 'Unknown Caller'}
                  {log.is_lost_job && <span className="lost-job-badge">Lost Job</span>}
                </h3>
                <div className="call-log-meta">
                  {log.phone_number && (
                    <span className="call-log-meta-item"><i className="fas fa-phone"></i> {formatPhone(log.phone_number)}</span>
                  )}
                  {log.address && (
                    <span className="call-log-meta-item"><i className="fas fa-map-marker-alt"></i> {log.address}</span>
                  )}
                  {log.duration_seconds != null && (
                    <span className="call-log-meta-item"><i className="fas fa-clock"></i> {formatDuration(log.duration_seconds)}</span>
                  )}
                  {log.recording_url && (
                    <span className="call-log-meta-item"><i className="fas fa-microphone"></i> Recorded</span>
                  )}
                </div>
                {log.ai_summary && <p className="call-log-summary">{log.ai_summary}</p>}
              </div>
              <div className="call-log-right">
                <span className="call-log-time">{formatRelativeTime(log.created_at)}</span>
                <span className={`call-outcome-badge ${log.call_outcome || 'no_action'}`}>
                  {OUTCOME_LABELS[log.call_outcome] || 'Unknown'}
                </span>
              </div>
            </div>
          ))
        )}
      </div>

      {totalPages > 1 && (
        <div className="call-logs-pagination">
          <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}>
            <i className="fas fa-chevron-left"></i> Prev
          </button>
          <span>Page {page} of {totalPages}</span>
          <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>
            Next <i className="fas fa-chevron-right"></i>
          </button>
        </div>
      )}

      {/* Call Detail Modal */}
      {selectedLog && (
        <div className="call-detail-overlay" onClick={() => setSelectedLog(null)}>
          <div className="call-detail-modal" onClick={e => e.stopPropagation()}>
            <div className="call-detail-header">
              <h3>
                <i className={`fas ${OUTCOME_ICONS[selectedLog.call_outcome] || 'fa-phone'}`} style={{ marginRight: '0.5rem', color: '#6366f1' }}></i>
                Call Details
                {selectedLog.is_lost_job && <span className="lost-job-badge" style={{ marginLeft: '0.5rem' }}>Lost Job</span>}
              </h3>
              <button className="call-detail-close" onClick={() => setSelectedLog(null)}>
                <i className="fas fa-times"></i>
              </button>
            </div>
            <div className="call-detail-body">
              {selectedLog.is_lost_job && selectedLog.lost_job_reason && (
                <div className="lost-job-reason-box">
                  <i className="fas fa-exclamation-triangle"></i>
                  <span>{selectedLog.lost_job_reason}</span>
                </div>
              )}

              <div className="call-detail-grid">
                <div className="call-detail-field">
                  <label>Caller Name</label>
                  <span className={selectedLog.caller_name ? '' : 'empty'}>{selectedLog.caller_name || 'Not provided'}</span>
                </div>
                <div className="call-detail-field">
                  <label>Phone Number</label>
                  <span className={selectedLog.phone_number ? '' : 'empty'}>{selectedLog.phone_number ? formatPhone(selectedLog.phone_number) : 'Unknown'}</span>
                </div>
                <div className="call-detail-field">
                  <label>Address</label>
                  <span className={selectedLog.address ? '' : 'empty'}>{selectedLog.address || 'Not provided'}</span>
                </div>
                <div className="call-detail-field">
                  <label>Eircode</label>
                  <span className={selectedLog.eircode ? '' : 'empty'}>{selectedLog.eircode || 'Not provided'}</span>
                </div>
                <div className="call-detail-field">
                  <label>Duration</label>
                  <span>{formatDuration(selectedLog.duration_seconds)}</span>
                </div>
                <div className="call-detail-field">
                  <label>Outcome</label>
                  <span className={`call-outcome-badge ${selectedLog.call_outcome || 'no_action'}`}>
                    {OUTCOME_LABELS[selectedLog.call_outcome] || 'Unknown'}
                  </span>
                </div>
                <div className="call-detail-field">
                  <label>Date & Time</label>
                  <span>
                    {selectedLog.created_at
                      ? new Date(selectedLog.created_at).toLocaleString('en-IE', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
                      : '—'}
                  </span>
                </div>
              </div>

              <div className="call-detail-section">
                <h4>AI Call Summary</h4>
                {selectedLog.ai_summary
                  ? <p>{selectedLog.ai_summary}</p>
                  : <p style={{ color: '#cbd5e1', fontStyle: 'italic' }}>No summary available — caller may have hung up early</p>
                }
              </div>

              <div className="call-detail-section">
                <h4>Call Recording</h4>
                {selectedLog.recording_url ? (
                  <audio controls preload="none" className="call-recording-player">
                    <source src={getProxiedMediaUrl(selectedLog.recording_url)} type="audio/wav" />
                    Your browser does not support audio playback.
                  </audio>
                ) : (
                  <p style={{ color: '#cbd5e1', fontStyle: 'italic' }}>No recording available</p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default CallLogsTab;
