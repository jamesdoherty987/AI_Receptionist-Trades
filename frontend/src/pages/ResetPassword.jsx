import { useState } from 'react';
import { Link, useSearchParams, useNavigate } from 'react-router-dom';
import { resetPassword } from '../services/api';
import './Auth.css';

function ResetPassword() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token');
  
  const [formData, setFormData] = useState({
    password: '',
    confirmPassword: ''
  });
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
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
      const response = await resetPassword(token, formData.password);
      if (response.data.success) {
        setSuccess(true);
      } else {
        setError(response.data.error || 'Failed to reset password');
      }
    } catch (err) {
      if (err.response?.data?.error) {
        setError(err.response.data.error);
      } else if (err.response?.status === 429) {
        setError('Too many attempts. Please try again later.');
      } else {
        setError('An unexpected error occurred. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  // No token provided
  if (!token) {
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
              <h1>Invalid link</h1>
              <p>This password reset link is invalid or has expired.</p>
            </div>
            
            <div className="reset-success-info">
              <div className="reset-success-icon" style={{ color: 'var(--error)' }}>
                <i className="fas fa-exclamation-triangle"></i>
              </div>
              <p className="reset-success-text">
                Please request a new password reset link.
              </p>
              <Link to="/forgot-password" className="auth-submit" style={{ display: 'flex', textDecoration: 'none', marginTop: '1rem' }}>
                <i className="fas fa-redo"></i>
                Request new link
              </Link>
            </div>

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
            <h1>{success ? 'Password reset!' : 'Set new password'}</h1>
            <p>
              {success 
                ? 'Your password has been successfully updated.' 
                : 'Enter your new password below.'}
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
              <div className="reset-success-icon" style={{ color: 'var(--success, #10b981)' }}>
                <i className="fas fa-check-circle"></i>
              </div>
              <p className="reset-success-text">
                You can now log in with your new password.
              </p>
              <button 
                className="auth-submit" 
                onClick={() => navigate('/login')}
                style={{ marginTop: '1rem' }}
              >
                <i className="fas fa-sign-in-alt"></i>
                Go to login
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="auth-form">
              <div className="form-group">
                <label htmlFor="password">New password</label>
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
                <label htmlFor="confirmPassword">Confirm new password</label>
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
                    Resetting...
                  </>
                ) : (
                  <>
                    <i className="fas fa-lock"></i>
                    Reset password
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

export default ResetPassword;
