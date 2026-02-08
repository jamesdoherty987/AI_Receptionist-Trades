import { useState } from 'react';
import { Link } from 'react-router-dom';
import { forgotPassword } from '../services/api';
import { validateEmail, rateLimiter } from '../utils/security';
import './Auth.css';

function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!rateLimiter.isAllowed('forgot-password', 3, 60000)) {
      setError('Too many attempts. Please wait a moment.');
      return;
    }
    
    if (!validateEmail(email)) {
      setError('Please enter a valid email address');
      return;
    }
    
    setLoading(true);
    setError('');

    try {
      const response = await forgotPassword(email);
      if (response.data.success) {
        setSuccess(true);
      } else {
        setError(response.data.error || 'Something went wrong');
      }
    } catch (err) {
      // Still show success to prevent email enumeration
      if (err.response?.status === 429) {
        setError('Too many attempts. Please try again later.');
      } else {
        setSuccess(true);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-bg">
        <div className="auth-gradient"></div>
      </div>

      <div className="auth-container">
        <Link to="/" className="auth-logo">
          <i className="fas fa-bolt"></i>
          <span>BookedForYou</span>
        </Link>

        <div className="auth-card">
          <div className="auth-header">
            <h1>{success ? 'Check your email' : 'Forgot password?'}</h1>
            <p>
              {success 
                ? "We've sent you a link to reset your password." 
                : "Enter your email and we'll send you a reset link."}
            </p>
          </div>

          {error && (
            <div className="auth-error">
              <i className="fas fa-exclamation-circle"></i>
              {error}
            </div>
          )}

          {success ? (
            <div className="reset-success-info">
              <div className="reset-success-icon">
                <i className="fas fa-envelope-open-text"></i>
              </div>
              <p className="reset-success-text">
                If an account exists for <strong>{email}</strong>, you'll receive an email with instructions to reset your password.
              </p>
              <p className="reset-success-hint">
                Didn't receive the email? Check your spam folder or try again.
              </p>
              <button 
                className="auth-submit" 
                onClick={() => { setSuccess(false); setEmail(''); }}
                style={{ marginTop: '1rem' }}
              >
                <i className="fas fa-redo"></i>
                Try again
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="auth-form">
              <div className="form-group">
                <label htmlFor="email">Email address</label>
                <input
                  type="email"
                  id="email"
                  name="email"
                  placeholder="you@company.com"
                  value={email}
                  onChange={(e) => { setEmail(e.target.value); setError(''); }}
                  required
                  autoFocus
                />
              </div>

              <button type="submit" className="auth-submit" disabled={loading}>
                {loading ? (
                  <>
                    <div className="spinner-small"></div>
                    Sending...
                  </>
                ) : (
                  <>
                    <i className="fas fa-paper-plane"></i>
                    Send reset link
                  </>
                )}
              </button>
            </form>
          )}

          <div className="auth-footer">
            <p>
              Remember your password? <Link to="/login">Sign in</Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ForgotPassword;
