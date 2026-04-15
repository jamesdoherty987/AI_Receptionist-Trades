import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { getReviewByToken, submitReview } from '../services/api';
import './ReviewPage.css';

function ReviewPage() {
  const { token } = useParams();
  const [review, setReview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [rating, setRating] = useState(0);
  const [hoverRating, setHoverRating] = useState(0);
  const [reviewText, setReviewText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [alreadyDone, setAlreadyDone] = useState(false);
  const [googleUrl, setGoogleUrl] = useState(null);

  useEffect(() => {
    const fetchReview = async () => {
      try {
        const res = await getReviewByToken(token);
        if (res.data.already_submitted) {
          setAlreadyDone(true);
        } else {
          setReview(res.data);
        }
      } catch {
        setError('This review link is invalid or has expired.');
      } finally {
        setLoading(false);
      }
    };
    fetchReview();
  }, [token]);

  const handleSubmit = async () => {
    if (!rating) return;
    setSubmitting(true);
    try {
      const res = await submitReview(token, { rating, review_text: reviewText });
      setSubmitted(true);
      if (res.data?.google_review_url) {
        setGoogleUrl(res.data.google_review_url);
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to submit review. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="review-page">
        <div className="review-card">
          <div className="review-loading"><div className="review-spinner"></div><p>Loading...</p></div>
        </div>
      </div>
    );
  }

  if (alreadyDone) {
    return (
      <div className="review-page">
        <div className="review-card">
          <div className="review-done-icon">💚</div>
          <h1>Already Reviewed</h1>
          <p className="review-subtitle">You've already submitted your feedback. Thank you!</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="review-page">
        <div className="review-card">
          <div className="review-done-icon">😕</div>
          <h1>Oops</h1>
          <p className="review-subtitle">{error}</p>
        </div>
      </div>
    );
  }

  if (submitted) {
    return (
      <div className="review-page">
        <div className="review-card submitted">
          <div className="review-done-icon">🎉</div>
          <h1>Thank You!</h1>
          <p className="review-subtitle">
            Your feedback means a lot to {review?.company_name || 'us'}. We appreciate you taking the time!
          </p>
          <div className="submitted-stars">
            {[1,2,3,4,5].map(s => (
              <span key={s} className={`star ${s <= rating ? 'filled' : ''}`}>★</span>
            ))}
          </div>
          {googleUrl && (
            <div className="review-google-prompt">
              <p>Glad you had a great experience! Would you mind sharing it on Google too?</p>
              <a href={googleUrl} target="_blank" rel="noopener noreferrer" className="review-google-btn">
                <i className="fab fa-google"></i> Leave a Google Review
              </a>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="review-page">
      <div className="review-card">
        <div className="review-header-icon">✅</div>
        <h1>How did we do?</h1>
        {review?.company_name && <p className="review-company">{review.company_name}</p>}
        <p className="review-subtitle">
          Hi {review?.customer_name || 'there'}! Your <strong>{review?.service_type || 'job'}</strong> is complete.
          We'd love your feedback.
        </p>

        <div className="star-rating" role="radiogroup" aria-label="Rating">
          {[1,2,3,4,5].map(s => (
            <button
              key={s}
              className={`star-btn ${s <= (hoverRating || rating) ? 'active' : ''}`}
              onClick={() => setRating(s)}
              onMouseEnter={() => setHoverRating(s)}
              onMouseLeave={() => setHoverRating(0)}
              aria-label={`${s} star${s > 1 ? 's' : ''}`}
              role="radio"
              aria-checked={rating === s}
            >
              ★
            </button>
          ))}
        </div>
        {rating > 0 && (
          <p className="rating-label">
            {['', 'Poor', 'Fair', 'Good', 'Great', 'Excellent'][rating]}
          </p>
        )}

        <textarea
          className="review-textarea"
          placeholder="Tell us more about your experience (optional)"
          value={reviewText}
          onChange={e => setReviewText(e.target.value)}
          rows={4}
          maxLength={1000}
        />

        <button
          className="review-submit-btn"
          onClick={handleSubmit}
          disabled={!rating || submitting}
        >
          {submitting ? 'Submitting...' : 'Submit Review'}
        </button>
      </div>
    </div>
  );
}

export default ReviewPage;
