import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { validateEmail, rateLimiter } from '../utils/security';
import './Auth.css';

function Login() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [formData, setFormData] = useState({
    email: '',
    password: ''
  });
  const [error, setError] = useState('');
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
    
    // Client-side rate limiting to prevent rapid-fire login attempts
    if (!rateLimiter.isAllowed('login', 5, 60000)) {
      setError('Too many login attempts. Please wait a moment before trying again.');
      return;
    }
    
    // Validate email format before sending
    if (!validateEmail(formData.email)) {
      setError('Please enter a valid email address');
      return;
    }
    
    setLoading(true);
    setError('');

    try {
      const result = await login(formData.email, formData.password);
      if (result.success) {
        navigate('/dashboard');
      } else {
        // Show more helpful error messages
        let errorMessage = result.error || 'Login failed. Please try again.';
        
        // Add helpful hints based on error code
        if (result.error?.includes('Invalid email or password')) {
          errorMessage = 'Invalid email or password. Please check your credentials and try again.';
        } else if (result.error?.includes('Too many failed attempts')) {
          errorMessage = 'Too many failed login attempts. Please wait 15 minutes before trying again.';
        } else if (result.error?.includes('temporarily locked')) {
          errorMessage = 'Your account has been temporarily locked for security. Please wait 15 minutes.';
        }
        
        setError(errorMessage);
      }
    } catch (err) {
      console.error('Login error:', err);
      
      // Provide more specific error messages based on the error
      if (err.response) {
        // Server responded with an error
        const serverError = err.response.data?.error || err.response.data?.message;
        if (serverError) {
          setError(serverError);
        } else if (err.response.status === 401) {
          setError('Invalid email or password. Please check your credentials.');
        } else if (err.response.status === 429) {
          setError('Too many login attempts. Please wait before trying again.');
        } else if (err.response.status === 500) {
          setError('Server error. Please try again later or contact support.');
        } else {
          setError(`Login failed (${err.response.status}). Please try again.`);
        }
      } else if (err.request) {
        // Request was made but no response received
        setError('Cannot connect to server. Please check your internet connection and try again.');
      } else {
        // Something else happened
        setError('An unexpected error occurred. Please try again.');
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
        <div className="auth-top-row">
          <Link to="/" className="auth-back-btn">
            <i className="fas fa-arrow-left"></i> Back
          </Link>
          <Link to="/" className="auth-logo">
            <i className="fas fa-bolt"></i>
            <span>BookedForYou</span>
          </Link>
        </div>

        <div className="auth-card">
          <div className="auth-header">
            <h1>Welcome back</h1>
            <p>Sign in to your account to continue</p>
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
                placeholder="you@company.com"
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

            <div className="form-row">
              <label className="checkbox-label">
                <input type="checkbox" />
                <span>Remember me</span>
              </label>
              <Link to="/forgot-password" className="forgot-link">
                Forgot password?
              </Link>
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
              Don't have an account?{' '}
              <Link to="/signup">Create account</Link>
            </p>
          </div>

          <Link to="/worker/login" className="worker-portal-btn">
            <i className="fas fa-hard-hat"></i>
            Worker Portal Login
            <i className="fas fa-arrow-right"></i>
          </Link>
        </div>

        <p className="auth-terms">
          By signing in, you agree to our{' '}
          <a href="#">Terms of Service</a> and <a href="#">Privacy Policy</a>
        </p>
      </div>
    </div>
  );
}

export default Login;
