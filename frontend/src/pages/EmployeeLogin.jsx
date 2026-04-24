import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { validateEmail, rateLimiter } from '../utils/security';
import { isStandalone } from '../components/PWAInstallPrompt';
import './Auth.css';

function EmployeeLogin() {
  const navigate = useNavigate();
  const { employeeLogin } = useAuth();
  const [formData, setFormData] = useState({ email: '', password: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
    setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!rateLimiter.isAllowed('employee-login', 10, 60000)) {
      setError('Too many login attempts. Please wait a moment.');
      return;
    }

    if (!validateEmail(formData.email)) {
      setError('Please enter a valid email address');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const result = await employeeLogin(formData.email, formData.password);
      if (result.success) {
        navigate('/employee/dashboard');
      } else {
        setError(result.error || 'Login failed. Please try again.');
      }
    } catch (err) {
      setError('An unexpected error occurred. Please try again.');
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
            <h1>Employee Portal</h1>
            <p>Sign in to view your jobs and schedule</p>
          </div>

          {error && (
            <div className="auth-error">
              <i className="fas fa-exclamation-circle"></i>
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="auth-form">
            <div className="form-group">
              <label htmlFor="email">Email address</label>
              <input
                type="email"
                id="email"
                name="email"
                placeholder="you@example.com"
                value={formData.email}
                onChange={handleChange}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="password">Password</label>
              <input
                type="password"
                id="password"
                name="password"
                placeholder="Enter your password"
                value={formData.password}
                onChange={handleChange}
                required
              />
            </div>

            <button type="submit" className="auth-submit" disabled={loading}>
              {loading ? (
                <>
                  <span className="spinner-small"></span>
                  Signing in...
                </>
              ) : (
                <>
                  Sign in
                  <i className="fas fa-arrow-right"></i>
                </>
              )}
            </button>
          </form>

          <div className="auth-footer">
            <p>
              <Link to="/employee/forgot-password">Forgot your password?</Link>
            </p>
            <p style={{ marginTop: '0.5rem' }}>
              Business owner? <Link to="/login">Owner login</Link>
            </p>
          </div>

          {!isStandalone() && (
            <Link to="/install" className="install-app-link">
              <i className="fas fa-mobile-screen-button"></i>
              Install as App
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}

export default EmployeeLogin;
