import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { getPortalData, portalRequestJob, portalUploadJobPhoto, portalUploadJobMedia } from '../services/api';
import { getProxiedMediaUrl } from '../utils/helpers';
import './CustomerPortal.css';

const statusColors = {
  pending: '#f59e0b', confirmed: '#3b82f6', 'in-progress': '#8b5cf6',
  completed: '#10b981', cancelled: '#94a3b8', scheduled: '#3b82f6',
  rejected: '#ef4444',
};

const isVideoUrl = (url) => /\.(mp4|mov|webm|avi)(\?|$)/i.test(url);

const compressImage = (file, maxSizeKB = 300, maxWidth = 800) => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('Failed to read file'));
    reader.onload = (e) => {
      const img = new Image();
      img.onerror = () => reject(new Error('Failed to load image'));
      img.onload = () => {
        const canvas = document.createElement('canvas');
        let width = img.width, height = img.height;
        if (width > maxWidth) { height = (height * maxWidth) / width; width = maxWidth; }
        canvas.width = width; canvas.height = height;
        canvas.getContext('2d').drawImage(img, 0, 0, width, height);
        const targetSize = maxSizeKB * 1024;
        let quality = 0.85;
        let result = canvas.toDataURL('image/jpeg', quality);
        while (result.length > targetSize && quality > 0.1) { quality -= 0.1; result = canvas.toDataURL('image/jpeg', quality); }
        resolve(result);
      };
      img.src = e.target.result;
    };
    reader.readAsDataURL(file);
  });
};

function CustomerPortal() {
  const { token } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [tab, setTab] = useState('jobs');
  const [showRequest, setShowRequest] = useState(false);
  const [reqForm, setReqForm] = useState({ service_type: '', description: '', address: '' });
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [expandedJob, setExpandedJob] = useState(null);
  const [uploadingFor, setUploadingFor] = useState(null);
  const [lightboxPhoto, setLightboxPhoto] = useState(null);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await getPortalData(token);
        setData(res.data);
      } catch {
        setError('This portal link is invalid or has expired.');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [token]);

  const handleRequest = async () => {
    if (!reqForm.service_type.trim()) return;
    setSubmitting(true);
    try {
      await portalRequestJob(token, reqForm);
      setSubmitted(true);
      setShowRequest(false);
      setReqForm({ service_type: '', description: '', address: '' });
    } catch (err) {
      alert(err?.response?.data?.error || 'Failed to submit request. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const handlePhotoUpload = async (jobId, e) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;
    setUploadingFor(jobId);
    try {
      for (const file of files) {
        const isVideo = file.type.startsWith('video/');
        if (isVideo) {
          if (file.size > 50 * 1024 * 1024) { alert('Video must be under 50MB'); continue; }
          await portalUploadJobMedia(token, jobId, file);
        } else if (file.type.startsWith('image/')) {
          if (file.size > 10 * 1024 * 1024) { alert('Image must be under 10MB'); continue; }
          const compressed = await compressImage(file);
          await portalUploadJobPhoto(token, jobId, compressed);
        }
      }
      // Refresh data
      const res = await getPortalData(token);
      setData(res.data);
    } catch (err) {
      alert(err?.response?.data?.error || 'Upload failed. Please try again.');
    } finally {
      setUploadingFor(null);
      // Reset the file input so the same file can be re-selected
      if (e.target) e.target.value = '';
    }
  };

  if (loading) return <div className="portal-page"><div className="portal-card"><div className="portal-spinner"></div><p>Loading your portal...</p></div></div>;
  if (error) return <div className="portal-page"><div className="portal-card"><div className="portal-icon">😕</div><h1>Oops</h1><p>{error}</p></div></div>;
  if (!data) return null;

  const now = new Date();
  const upcoming = (data.jobs || []).filter(j => {
    if (j.status === 'completed' || j.status === 'cancelled' || j.status === 'rejected') return false;
    return j.status === 'in-progress' || new Date(j.appointment_time) >= now;
  });
  const past = (data.jobs || []).filter(j => {
    if (j.status === 'cancelled') return false;
    return j.status === 'completed' || j.status === 'rejected' || (j.status !== 'in-progress' && new Date(j.appointment_time) < now);
  });

  const allMedia = (j) => [...(j.customer_photo_urls || []), ...(j.photo_urls || [])];

  const renderJobCard = (j, isPast = false) => {
    const isExpanded = expandedJob === j.id;
    const media = allMedia(j);
    const customerMedia = j.customer_photo_urls || [];
    const canUpload = !isPast && j.status !== 'completed';

    return (
      <div key={j.id} className={`portal-job-card-wrap ${isPast ? 'past' : ''}`}>
        <div className="portal-job-card" onClick={() => setExpandedJob(isExpanded ? null : j.id)} role="button" tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && setExpandedJob(isExpanded ? null : j.id)}>
          <div className="portal-job-left">
            <span className="portal-job-service">{j.service_type}</span>
            <span className="portal-job-date">
              <i className="fas fa-calendar"></i>
              {new Date(j.appointment_time).toLocaleDateString('en-IE', { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}
            </span>
            {j.address && <span className="portal-job-addr"><i className="fas fa-map-marker-alt"></i> {j.address}</span>}
          </div>
          <div className="portal-job-right">
            <span className="portal-status" style={{ background: `${statusColors[j.status]}15`, color: statusColors[j.status] }}>
              {j.status}
            </span>
            {(j.charge || j.price) > 0 && <span className="portal-job-price">€{Number(j.charge || j.price).toFixed(2)}</span>}
            <i className={`fas fa-chevron-${isExpanded ? 'up' : 'down'} portal-chevron`}></i>
          </div>
        </div>

        {isExpanded && (
          <div className="portal-job-expanded">
            {/* Upload section for active jobs */}
            {canUpload && (
              <div className="portal-upload-section">
                <p className="portal-upload-hint">
                  <i className="fas fa-camera"></i> Upload photos or videos of the issue to help us prepare
                </p>
                <label className="portal-upload-btn" htmlFor={`file-${j.id}`}>
                  {uploadingFor === j.id ? (
                    <><i className="fas fa-spinner fa-spin"></i> Uploading...</>
                  ) : (
                    <><i className="fas fa-plus"></i> Add Photos / Videos</>
                  )}
                </label>
                <input
                  id={`file-${j.id}`}
                  type="file"
                  accept="image/*,video/mp4,video/quicktime,video/webm"
                  multiple
                  onChange={(e) => handlePhotoUpload(j.id, e)}
                  style={{ display: 'none' }}
                  disabled={uploadingFor === j.id}
                />
              </div>
            )}

            {/* Customer's uploaded media */}
            {customerMedia.length > 0 && (
              <div className="portal-media-section">
                <h4><i className="fas fa-images"></i> Your Uploads</h4>
                <div className="portal-media-grid">
                  {customerMedia.map((url, idx) => (
                    <div key={idx} className="portal-media-item" onClick={() => setLightboxPhoto(url)}>
                      {isVideoUrl(url) ? (
                        <>
                          <video src={getProxiedMediaUrl(url)} muted preload="metadata" />
                          <div className="portal-video-badge"><i className="fas fa-play"></i></div>
                        </>
                      ) : (
                        <img src={getProxiedMediaUrl(url)} alt={`Upload ${idx + 1}`} />
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* All media on the job (worker/owner uploads) */}
            {(j.photo_urls || []).length > 0 && (
              <div className="portal-media-section">
                <h4><i className="fas fa-camera"></i> Job Photos</h4>
                <div className="portal-media-grid">
                  {(j.photo_urls || []).map((url, idx) => (
                    <div key={idx} className="portal-media-item" onClick={() => setLightboxPhoto(url)}>
                      {isVideoUrl(url) ? (
                        <>
                          <video src={getProxiedMediaUrl(url)} muted preload="metadata" />
                          <div className="portal-video-badge"><i className="fas fa-play"></i></div>
                        </>
                      ) : (
                        <img src={getProxiedMediaUrl(url)} alt={`Job photo ${idx + 1}`} />
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {media.length === 0 && !canUpload && (
              <p className="portal-no-media">No media for this job</p>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="portal-page">
      <div className="portal-container">
        {/* Header */}
        <div className="portal-header">
          <div className="portal-header-info">
            {data.company_logo ? (
              <img src={getProxiedMediaUrl(data.company_logo)} alt={data.company_name} className="portal-company-logo" />
            ) : (
              <h1>{data.company_name}</h1>
            )}
            <p>Welcome back, {data.client_name}</p>
          </div>
          {data.company_phone && (
            <a href={`tel:${data.company_phone}`} className="portal-call-btn">
              <i className="fas fa-phone"></i> Call Us
            </a>
          )}
        </div>

        {/* Tabs */}
        <div className="portal-tabs">
          <button className={tab === 'jobs' ? 'active' : ''} onClick={() => setTab('jobs')}>
            <i className="fas fa-briefcase"></i> My Jobs
          </button>
          <button className={tab === 'quotes' ? 'active' : ''} onClick={() => setTab('quotes')}>
            <i className="fas fa-file-invoice"></i> Quotes
          </button>
        </div>

        {/* Success banner */}
        {submitted && (
          <div className="portal-success">
            <i className="fas fa-check-circle"></i> Your request has been submitted. We'll be in touch soon.
          </div>
        )}

        {/* Jobs */}
        {tab === 'jobs' && (
          <div className="portal-section">
            <div className="portal-section-head">
              <h2>Upcoming Jobs</h2>
              <button className="portal-req-btn" onClick={() => setShowRequest(true)}>
                <i className="fas fa-plus"></i> Request New Job
              </button>
            </div>
            {upcoming.length === 0 ? (
              <div className="portal-empty"><i className="fas fa-calendar-check"></i><p>No upcoming jobs</p></div>
            ) : (
              <div className="portal-jobs">
                {upcoming.map(j => renderJobCard(j))}
              </div>
            )}

            {past.length > 0 && (
              <>
                <h2 className="portal-past-title">Past Jobs</h2>
                <div className="portal-jobs">
                  {past.slice(0, 10).map(j => renderJobCard(j, true))}
                </div>
              </>
            )}
          </div>
        )}

        {/* Quotes */}
        {tab === 'quotes' && (
          <div className="portal-section">
            <h2>Your Quotes</h2>
            {(data.quotes || []).length === 0 ? (
              <div className="portal-empty"><i className="fas fa-file-invoice"></i><p>No quotes yet</p></div>
            ) : (
              <div className="portal-jobs">
                {(data.quotes || []).map(q => (
                  <div key={q.id} className="portal-job-card">
                    <div className="portal-job-left">
                      <span className="portal-job-service">{q.title || `Quote #${q.quote_number}`}</span>
                      <span className="portal-job-date"><i className="fas fa-calendar"></i> {new Date(q.created_at).toLocaleDateString('en-IE', { day: 'numeric', month: 'short', year: 'numeric' })}</span>
                    </div>
                    <div className="portal-job-right">
                      <span className="portal-status" style={{ background: q.status === 'accepted' ? '#ecfdf5' : '#f1f5f9', color: q.status === 'accepted' ? '#10b981' : '#64748b' }}>{q.status}</span>
                      <span className="portal-job-price">€{Number(q.total || 0).toFixed(2)}</span>
                      {q.accept_token && q.status !== 'accepted' && q.status !== 'converted' && q.status !== 'declined' && (
                        <a href={`/quote/accept/${q.accept_token}`} className="portal-accept-btn">Accept</a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Request Job Modal */}
        {showRequest && (
          <div className="portal-modal-overlay" onClick={() => setShowRequest(false)}>
            <div className="portal-modal" onClick={e => e.stopPropagation()}>
              <h3>Request a New Job</h3>
              <p className="portal-modal-desc">Tell us what you need and we'll get back to you.</p>
              <div className="portal-form-group">
                <label>What do you need?</label>
                <input value={reqForm.service_type} onChange={e => setReqForm({ ...reqForm, service_type: e.target.value })} placeholder="e.g. Boiler repair, Plumbing, Electrical..." />
              </div>
              <div className="portal-form-group">
                <label>Description (optional)</label>
                <textarea value={reqForm.description} onChange={e => setReqForm({ ...reqForm, description: e.target.value })} placeholder="Any details about the job..." rows={3} />
              </div>
              <div className="portal-form-group">
                <label>Address (optional)</label>
                <input value={reqForm.address} onChange={e => setReqForm({ ...reqForm, address: e.target.value })} placeholder="Job address" />
              </div>
              <div className="portal-modal-actions">
                <button className="portal-btn-secondary" onClick={() => setShowRequest(false)}>Cancel</button>
                <button className="portal-btn-primary" onClick={handleRequest} disabled={!reqForm.service_type.trim() || submitting}>
                  {submitting ? 'Submitting...' : 'Submit Request'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Lightbox */}
        {lightboxPhoto && (
          <div className="portal-lightbox" onClick={() => setLightboxPhoto(null)}>
            <button className="portal-lightbox-close" onClick={() => setLightboxPhoto(null)}><i className="fas fa-times"></i></button>
            {isVideoUrl(lightboxPhoto) ? (
              <video src={getProxiedMediaUrl(lightboxPhoto)} controls autoPlay onClick={e => e.stopPropagation()} style={{ maxWidth: '90vw', maxHeight: '90vh', borderRadius: 8 }} />
            ) : (
              <img src={getProxiedMediaUrl(lightboxPhoto)} alt="Full size" onClick={e => e.stopPropagation()} />
            )}
          </div>
        )}

        <div className="portal-footer">
          <p>Powered by <strong>BookedForYou</strong></p>
        </div>
      </div>
    </div>
  );
}

export default CustomerPortal;
