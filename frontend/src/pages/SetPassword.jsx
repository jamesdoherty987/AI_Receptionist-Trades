import { useState } from 'react';
import { Link, useSearchParams, useNavigate } from 'react-router-dom';
import { ownerSetPassword } from '../services/api';
import './Auth.css';

function SetPassword() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token');

  const [formData, setFormData] = useState({ password: '', confirmPassword: '' });
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
    setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (formData.password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }
    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      return;
    }
    const hasUpper = /[A-Z]/.test(formData.password);
    const hasLower = /[a-z]/.test(formData.password);
    const hasDigit = /[0-9]/.test(formData.password);
    if (!hasUpper || !hasLower || !hasDigit) {
      setError('Password must contain at least one uppercase letter, one lowercase letter, and one number');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await ownerSetPassword(token, formData.password);
      if (response.data.success) {
        setSuccess(true);
      } else {
        setError(response.data.error || 'Failed to set password');
      }
    } catch (err) {
      setError(err.response?.data?.error || 'An unexpected error occurred. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="auth-page">
        <div className="auth-bg"><div className="auth-gradient"></div></div>
        <div className="auth-container">
          <Link to="/" className="auth-logo">
            <i className="fas fa-bolt"></i>
            <span>BookedForYou</span>
          </Link>
          <div className="auth-card">
            <div className="auth-header">
              <h1>Invalid link</h1>
              <p>This invite link is invalid or has expired.</p>
            </div>
            <div className="reset-success-info">
              <div className="reset-success-icon" style={{ color: 'var(--error)' }}>
                <i className="fas fa-exclamation-triangle"></i>
              </div>
              <p className="reset-success-text">
                Please contact support for a new invite link.
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-page">
      <div className="auth-bg"><div className="auth-gradient"></div></div>
      <div className="auth-container">
        <Link to="/" className="auth-logo">
          <i className="fas fa-bolt"></i>
          <span>BookedForYou</span>
        </Link>

        <div className="auth-card">
          <div className="auth-header">
            <h1>{success ? 'You\'re all set!' : 'Welcome to BookedForYou'}</h1>
            <p>{success ? 'Your account is ready. You can now log in.' : 'Create a password to access your dashboard.'}</p>
          </div>

          {error && (
            <div className="auth-error">
              <i className="fas fa-exclamation-circle"></i>
              {error}
            </div>
          )}

          {success ? (
            <div className="reset-success-info">
              <div className="reset-success-icon" style={{ color: 'var(--success, #10b981)' }}>
                <i className="fas fa-check-circle"></i>
              </div>
              <p className="reset-success-text">Your password has been set. Everything is ready for you.</p>
              <button
                className="auth-submit"
                onClick={() => navigate('/login')}
                style={{ marginTop: '1rem' }}
              >
                <i className="fas fa-sign-in-alt"></i>
                Go to Login
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="auth-form">
              <div className="form-group">
                <label htmlFor="password">Password</label>
                <input
                  type="password"
                  id="password"
                  name="password"
                  placeholder="At least 8 characters"
                  value={formData.password}
                  onChange={handleChange}
                  required
                  minLength={8}
                  autoFocus
                />
              </div>

              <div className="form-group">
                <label htmlFor="confirmPassword">Confirm password</label>
                <input
                  type="password"
                  id="confirmPassword"
                  name="confirmPassword"
                  placeholder="Re-enter your password"
                  value={formData.confirmPassword}
                  onChange={handleChange}
                  required
                  minLength={8}
                />
              </div>

              <div className="password-requirements">
                <p className={formData.password.length >= 8 ? 'met' : ''}>
                  <i className={`fas ${formData.password.length >= 8 ? 'fa-check-circle' : 'fa-circle'}`}></i>
                  At least 8 characters
                </p>
                <p className={/[A-Z]/.test(formData.password) ? 'met' : ''}>
                  <i className={`fas ${/[A-Z]/.test(formData.password) ? 'fa-check-circle' : 'fa-circle'}`}></i>
                  One uppercase letter
                </p>
                <p className={/[a-z]/.test(formData.password) ? 'met' : ''}>
                  <i className={`fas ${/[a-z]/.test(formData.password) ? 'fa-check-circle' : 'fa-circle'}`}></i>
                  One lowercase letter
                </p>
                <p className={/[0-9]/.test(formData.password) ? 'met' : ''}>
                  <i className={`fas ${/[0-9]/.test(formData.password) ? 'fa-check-circle' : 'fa-circle'}`}></i>
                  One number
                </p>
              </div>

              <button type="submit" className="auth-submit" disabled={loading}>
                {loading ? (
                  <>
                    <div className="spinner-small"></div>
                    Setting password...
                  </>
                ) : (
                  <>
                    <i className="fas fa-lock"></i>
                    Set password
                  </>
                )}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}

export default SetPassword;
