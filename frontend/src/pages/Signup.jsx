import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { validateEmail, validatePassword, sanitizeString } from '../utils/security';
import './Auth.css';

function Signup() {
  const navigate = useNavigate();
  const { signup } = useAuth();
  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState({
    company_name: '',
    owner_name: '',
    email: '',
    phone: '',
    trade_type: '',
    password: '',
    confirm_password: ''
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [passwordFocus, setPasswordFocus] = useState(false);

  const tradeTypes = [
    'Plumbing',
    'Electrical',
    'Roofing',
    'HVAC',
    'Carpentry',
    'Painting',
    'Landscaping',
    'General Contracting',
    'Flooring',
    'Masonry',
    'Other'
  ];

  // Password strength indicators
  const getPasswordStrength = () => {
    const pwd = formData.password;
    return {
      length: pwd.length >= 8,
      uppercase: /[A-Z]/.test(pwd),
      lowercase: /[a-z]/.test(pwd),
      number: /\d/.test(pwd)
    };
  };

  const passwordStrength = getPasswordStrength();

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
    setError('');
  };

  const validateStep1 = () => {
    if (!formData.company_name.trim()) {
      setError('Company name is required');
      return false;
    }
    if (!formData.owner_name.trim()) {
      setError('Your name is required');
      return false;
    }
    if (!formData.trade_type) {
      setError('Please select your trade');
      return false;
    }
    return true;
  };

  const validateStep2 = () => {
    if (!formData.email.trim()) {
      setError('Email is required');
      return false;
    }
    // Use secure email validation
    if (!validateEmail(formData.email)) {
      setError('Please enter a valid email');
      return false;
    }
    // Use secure password validation
    const passwordCheck = validatePassword(formData.password);
    if (!passwordCheck.valid) {
      setError(passwordCheck.message);
      return false;
    }
    if (formData.password !== formData.confirm_password) {
      setError('Passwords do not match');
      return false;
    }
    return true;
  };

  const handleNext = () => {
    if (validateStep1()) {
      setStep(2);
      setError('');
    }
  };

  const handleBack = () => {
    setStep(1);
    setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!validateStep2()) return;

    setLoading(true);
    setError('');

    try {
      // Sanitize inputs before sending to server
      const result = await signup({
        company_name: sanitizeString(formData.company_name),
        owner_name: sanitizeString(formData.owner_name),
        email: formData.email.trim().toLowerCase(),
        phone: formData.phone,
        trade_type: formData.trade_type,
        password: formData.password
      });

      if (result.success) {
        // Navigate directly to dashboard - onboarding wizard will appear there
        navigate('/dashboard');
      } else {
        setError(result.error || 'Registration failed');
      }
    } catch (err) {
      setError('An unexpected error occurred');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-bg">
        <div className="auth-gradient"></div>
      </div>

      <div className="auth-container signup-container">
        <Link to="/" className="auth-logo">
          <i className="fas fa-bolt"></i>
          <span>BookedForYou</span>
        </Link>

        <div className="auth-card">
          <div className="auth-header">
            <h1>Create your account</h1>
            <p>Get started with BookedForYou</p>
          </div>

          {/* Progress Steps */}
          <div className="signup-progress">
            <div className={`progress-step ${step >= 1 ? 'active' : ''}`}>
              <div className="step-circle">1</div>
              <span>Business Info</span>
            </div>
            <div className="progress-line"></div>
            <div className={`progress-step ${step >= 2 ? 'active' : ''}`}>
              <div className="step-circle">2</div>
              <span>Account Setup</span>
            </div>
          </div>

          {error && (
            <div className="auth-error">
              <i className="fas fa-exclamation-circle"></i>
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="auth-form">
            {step === 1 && (
              <>
                <div className="form-group">
                  <label htmlFor="company_name">Business Name</label>
                  <input
                    type="text"
                    id="company_name"
                    name="company_name"
                    placeholder="e.g., Smith's Plumbing"
                    value={formData.company_name}
                    onChange={handleChange}
                    required
                    autoFocus
                    autoComplete="organization"
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="owner_name">Your Name</label>
                  <input
                    type="text"
                    id="owner_name"
                    name="owner_name"
                    placeholder="e.g., John Smith"
                    value={formData.owner_name}
                    onChange={handleChange}
                    required
                    autoComplete="name"
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="trade_type">What type of business?</label>
                  <select
                    id="trade_type"
                    name="trade_type"
                    value={formData.trade_type}
                    onChange={handleChange}
                    required
                  >
                    <option value="">Select your trade</option>
                    {tradeTypes.map((trade) => (
                      <option key={trade} value={trade}>{trade}</option>
                    ))}
                  </select>
                </div>

                <div className="form-group">
                  <label htmlFor="phone">Your Phone Number <span className="optional-label">(optional)</span></label>
                  <input
                    type="tel"
                    id="phone"
                    name="phone"
                    placeholder="e.g., 085 123 4567"
                    value={formData.phone}
                    onChange={handleChange}
                    autoComplete="tel"
                  />
                  <small className="form-hint">We'll use this for call forwarding when AI is disabled</small>
                </div>

                <button type="button" className="auth-submit" onClick={handleNext}>
                  Continue
                  <i className="fas fa-arrow-right"></i>
                </button>
              </>
            )}

            {step === 2 && (
              <>
                <div className="form-group">
                  <label htmlFor="email">Email Address</label>
                  <input
                    type="email"
                    id="email"
                    name="email"
                    placeholder="you@company.com"
                    value={formData.email}
                    onChange={handleChange}
                    required
                    autoComplete="email"
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="password">Password</label>
                  <input
                    type="password"
                    id="password"
                    name="password"
                    placeholder="Create a strong password"
                    value={formData.password}
                    onChange={handleChange}
                    onFocus={() => setPasswordFocus(true)}
                    onBlur={() => setPasswordFocus(false)}
                    required
                    autoComplete="new-password"
                  />
                  {/* Password strength indicators */}
                  {(passwordFocus || formData.password) && (
                    <div className="password-requirements">
                      <p className={passwordStrength.length ? 'met' : ''}>
                        <i className={`fas ${passwordStrength.length ? 'fa-check' : 'fa-circle'}`}></i>
                        At least 8 characters
                      </p>
                      <p className={passwordStrength.uppercase ? 'met' : ''}>
                        <i className={`fas ${passwordStrength.uppercase ? 'fa-check' : 'fa-circle'}`}></i>
                        One uppercase letter
                      </p>
                      <p className={passwordStrength.lowercase ? 'met' : ''}>
                        <i className={`fas ${passwordStrength.lowercase ? 'fa-check' : 'fa-circle'}`}></i>
                        One lowercase letter
                      </p>
                      <p className={passwordStrength.number ? 'met' : ''}>
                        <i className={`fas ${passwordStrength.number ? 'fa-check' : 'fa-circle'}`}></i>
                        One number
                      </p>
                    </div>
                  )}
                </div>

                <div className="form-group">
                  <label htmlFor="confirm_password">Confirm Password</label>
                  <input
                    type="password"
                    id="confirm_password"
                    name="confirm_password"
                    placeholder="Re-enter your password"
                    value={formData.confirm_password}
                    onChange={handleChange}
                    required
                    autoComplete="new-password"
                  />
                  {formData.confirm_password && formData.password !== formData.confirm_password && (
                    <small className="password-mismatch">
                      <i className="fas fa-exclamation-circle"></i> Passwords don't match
                    </small>
                  )}
                  {formData.confirm_password && formData.password === formData.confirm_password && (
                    <small className="password-match">
                      <i className="fas fa-check-circle"></i> Passwords match
                    </small>
                  )}
                </div>

                <div className="form-buttons">
                  <button type="button" className="auth-back" onClick={handleBack}>
                    <i className="fas fa-arrow-left"></i>
                    Back
                  </button>
                  <button type="submit" className="auth-submit" disabled={loading}>
                    {loading ? (
                      <>
                        <span className="spinner-small"></span>
                        Creating account...
                      </>
                    ) : (
                      <>
                        Create account
                        <i className="fas fa-check"></i>
                      </>
                    )}
                  </button>
                </div>
              </>
            )}
          </form>

          <div className="auth-footer">
            <p>
              Already have an account?{' '}
              <Link to="/login">Sign in</Link>
            </p>
          </div>
        </div>

        <p className="auth-terms">
          By creating an account, you agree to our{' '}
          <a href="#">Terms of Service</a> and <a href="#">Privacy Policy</a>
        </p>
      </div>
    </div>
  );
}

export default Signup;
