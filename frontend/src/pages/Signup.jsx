import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import PhoneConfigModal from '../components/modals/PhoneConfigModal';
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
  const [showPhoneModal, setShowPhoneModal] = useState(false);

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
    if (!formData.email.includes('@')) {
      setError('Please enter a valid email');
      return false;
    }
    if (formData.password.length < 8) {
      setError('Password must be at least 8 characters');
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
      const result = await signup({
        company_name: formData.company_name,
        owner_name: formData.owner_name,
        email: formData.email,
        phone: formData.phone,
        trade_type: formData.trade_type,
        password: formData.password
      });

      if (result.success) {
        // Show phone configuration modal after successful signup
        setShowPhoneModal(true);
      } else {
        setError(result.error || 'Registration failed');
      }
    } catch (err) {
      setError('An unexpected error occurred');
    } finally {
      setLoading(false);
    }
  };

  const handlePhoneConfigComplete = () => {
    // Navigate to dashboard after phone is configured or skipped
    navigate('/dashboard');
  };

  return (
    <div className="auth-page">
      <div className="auth-bg">
        <div className="auth-gradient"></div>
      </div>

      <div className="auth-container signup-container">
        <Link to="/" className="auth-logo">
          <i className="fas fa-bolt"></i>
          <span>TradesAI</span>
        </Link>

        <div className="auth-card">
          <div className="auth-header">
            <h1>Create your account</h1>
            <p>Start your free trial today</p>
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
                  <label htmlFor="company_name">Company Name</label>
                  <input
                    type="text"
                    id="company_name"
                    name="company_name"
                    placeholder="Your business name"
                    value={formData.company_name}
                    onChange={handleChange}
                    required
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="owner_name">Your Name</label>
                  <input
                    type="text"
                    id="owner_name"
                    name="owner_name"
                    placeholder="Full name"
                    value={formData.owner_name}
                    onChange={handleChange}
                    required
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="trade_type">Your Trade</label>
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
                  <label htmlFor="phone">Phone Number (Optional)</label>
                  <input
                    type="tel"
                    id="phone"
                    name="phone"
                    placeholder="+353 86 XXX XXXX"
                    value={formData.phone}
                    onChange={handleChange}
                  />
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
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="password">Password</label>
                  <input
                    type="password"
                    id="password"
                    name="password"
                    placeholder="Min. 8 characters"
                    value={formData.password}
                    onChange={handleChange}
                    required
                  />
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
                  />
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

      {/* Phone Configuration Modal */}
      <PhoneConfigModal
        isOpen={showPhoneModal}
        onClose={handlePhoneConfigComplete}
        onSuccess={handlePhoneConfigComplete}
        allowSkip={true}
      />
    </div>
  );
}

export default Signup;
