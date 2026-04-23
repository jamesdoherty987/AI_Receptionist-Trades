import { useQuery } from '@tanstack/react-query';
import { useIndustry } from '../../context/IndustryContext';
import { getCompanyReviews } from '../../services/api';
import './ReviewsTab.css';

function ReviewsTab() {
  const { terminology } = useIndustry();
  const { data, isLoading } = useQuery({
    queryKey: ['reviews'],
    queryFn: async () => (await getCompanyReviews()).data,
  });

  const reviews = data?.reviews || [];
  const submitted = reviews.filter(r => r.submitted_at);
  const pending = reviews.filter(r => !r.submitted_at);
  const avgRating = submitted.length > 0
    ? (submitted.reduce((s, r) => s + r.rating, 0) / submitted.length).toFixed(1)
    : null;

  if (isLoading) {
    return <div className="reviews-loading"><div className="reviews-spinner"></div></div>;
  }

  return (
    <div className="reviews-tab">
      {/* Stats bar */}
      <div className="reviews-stats">
        <div className="reviews-stat-card">
          <div className="stat-icon"><i className="fas fa-star" style={{ color: '#f59e0b' }}></i></div>
          <div className="stat-info">
            <span className="stat-value">{avgRating || '—'}</span>
            <span className="stat-label">Avg Rating</span>
          </div>
        </div>
        <div className="reviews-stat-card">
          <div className="stat-icon"><i className="fas fa-check-circle" style={{ color: '#10b981' }}></i></div>
          <div className="stat-info">
            <span className="stat-value">{submitted.length}</span>
            <span className="stat-label">Reviews</span>
          </div>
        </div>
        <div className="reviews-stat-card">
          <div className="stat-icon"><i className="fas fa-clock" style={{ color: '#f59e0b' }}></i></div>
          <div className="stat-info">
            <span className="stat-value">{pending.length}</span>
            <span className="stat-label">Pending</span>
          </div>
        </div>
        <div className="reviews-stat-card">
          <div className="stat-icon"><i className="fas fa-envelope" style={{ color: '#3b82f6' }}></i></div>
          <div className="stat-info">
            <span className="stat-value">{reviews.length}</span>
            <span className="stat-label">Sent</span>
          </div>
        </div>
      </div>

      {/* Rating breakdown */}
      {submitted.length > 0 && (
        <div className="reviews-breakdown">
          {[5,4,3,2,1].map(star => {
            const count = submitted.filter(r => r.rating === star).length;
            const pct = submitted.length > 0 ? (count / submitted.length * 100) : 0;
            return (
              <div key={star} className="breakdown-row">
                <span className="breakdown-label">{star} <i className="fas fa-star" style={{ color: '#f59e0b', fontSize: '0.7rem' }}></i></span>
                <div className="breakdown-bar"><div className="breakdown-fill" style={{ width: `${pct}%` }}></div></div>
                <span className="breakdown-count">{count}</span>
              </div>
            );
          })}
        </div>
      )}

      {/* Reviews list */}
      {reviews.length === 0 ? (
        <div className="reviews-empty">
          <i className="fas fa-star"></i>
          <h3>No reviews yet</h3>
          <p>When you complete jobs for customers with email addresses, they'll receive a satisfaction survey. Their responses will appear here.</p>
        </div>
      ) : (
        <div className="reviews-list">
          {reviews.map(review => (
            <div key={review.id} className={`review-item ${review.submitted_at ? 'submitted' : 'pending'}`}>
              <div className="review-item-header">
                <div className="review-item-left">
                  <span className="review-customer">{review.customer_name || terminology.client}</span>
                  <span className="review-service">{review.service_type || terminology.job}</span>
                </div>
                <div className="review-item-right">
                  {review.submitted_at ? (
                    <div className="review-item-stars">
                      {[1,2,3,4,5].map(s => (
                        <span key={s} style={{ color: s <= review.rating ? '#f59e0b' : '#e5e7eb', fontSize: '1rem' }}>★</span>
                      ))}
                    </div>
                  ) : (
                    <span className="review-pending-badge"><i className="fas fa-clock"></i> Awaiting</span>
                  )}
                </div>
              </div>
              {review.review_text && (
                <p className="review-item-text">"{review.review_text}"</p>
              )}
              <div className="review-item-footer">
                {review.submitted_at && (
                  <span className="review-date">
                    Reviewed {new Date(review.submitted_at).toLocaleDateString('en-IE', { month: 'short', day: 'numeric', year: 'numeric' })}
                  </span>
                )}
                {!review.submitted_at && review.email_sent_at && (
                  <span className="review-date">
                    Sent {new Date(review.email_sent_at).toLocaleDateString('en-IE', { month: 'short', day: 'numeric' })}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default ReviewsTab;
