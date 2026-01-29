import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import './Landing.css';

function Landing() {
  const navigate = useNavigate();
  const [activeTestimonial, setActiveTestimonial] = useState(0);
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  const testimonials = [
    {
      name: "Mike O'Brien",
      company: "O'Brien Plumbing",
      image: "https://randomuser.me/api/portraits/men/32.jpg",
      text: "This AI receptionist has completely transformed how we handle calls. We never miss a lead now, even when we're knee-deep in a job. It's like having a full-time receptionist for a fraction of the cost.",
      rating: 5
    },
    {
      name: "Sarah Thompson",
      company: "Thompson Electrical",
      image: "https://randomuser.me/api/portraits/women/44.jpg",
      text: "The booking system is seamless. Customers love being able to schedule appointments instantly, and I love that my calendar stays organized without me lifting a finger.",
      rating: 5
    },
    {
      name: "James McCarthy",
      company: "McCarthy Roofing",
      image: "https://randomuser.me/api/portraits/men/67.jpg",
      text: "We've seen a 40% increase in booked jobs since using this system. The AI handles everything professionally - from quotes to scheduling. Worth every penny!",
      rating: 5
    }
  ];

  const features = [
    {
      icon: "fas fa-phone-volume",
      title: "24/7 AI Receptionist",
      description: "Never miss a call again. Our AI answers professionally, day or night, capturing every lead."
    },
    {
      icon: "fas fa-calendar-check",
      title: "Smart Scheduling",
      description: "Automatic appointment booking synced with your calendar. No double bookings, no hassle."
    },
    {
      icon: "fas fa-users",
      title: "Customer Management",
      description: "Keep track of all your clients, their job history, and preferences in one place."
    },
    {
      icon: "fas fa-chart-line",
      title: "Financial Tracking",
      description: "Monitor revenue, track payments, and send invoices directly from the dashboard."
    },
    {
      icon: "fas fa-hard-hat",
      title: "Worker Management",
      description: "Assign jobs to your team, track their schedules, and prevent conflicts."
    },
    {
      icon: "fas fa-comments",
      title: "AI Chat Support",
      description: "Let customers chat with your AI assistant for quotes and information anytime."
    }
  ];

  const pricingPlans = [
    {
      name: "Starter",
      price: "Free",
      period: "",
      description: "Perfect for solo tradespeople",
      features: [
        "AI receptionist (50 calls/month)",
        "Basic scheduling",
        "Customer database",
        "Email support"
      ],
      cta: "Start Free",
      highlighted: false
    },
    {
      name: "Professional",
      price: "€49",
      period: "/month",
      description: "For growing businesses",
      features: [
        "Unlimited AI calls",
        "Advanced scheduling",
        "Worker management (up to 5)",
        "Financial tracking",
        "Priority support",
        "Custom AI voice"
      ],
      cta: "Start Trial",
      highlighted: true
    },
    {
      name: "Enterprise",
      price: "€149",
      period: "/month",
      description: "For larger operations",
      features: [
        "Everything in Professional",
        "Unlimited workers",
        "API access",
        "Custom integrations",
        "Dedicated account manager",
        "SLA guarantee"
      ],
      cta: "Contact Sales",
      highlighted: false
    }
  ];

  useEffect(() => {
    const interval = setInterval(() => {
      setActiveTestimonial((prev) => (prev + 1) % testimonials.length);
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="landing">
      {/* Navigation */}
      <nav className="landing-nav">
        <div className="nav-container">
          <div className="nav-logo">
            <i className="fas fa-bolt"></i>
            <span>TradesAI</span>
          </div>
          
          <button className="mobile-menu-btn" onClick={() => setIsMenuOpen(!isMenuOpen)}>
            <i className={`fas ${isMenuOpen ? 'fa-times' : 'fa-bars'}`}></i>
          </button>

          <div className={`nav-links ${isMenuOpen ? 'open' : ''}`}>
            <a href="#features">Features</a>
            <a href="#testimonials">Testimonials</a>
            <a href="#pricing">Pricing</a>
            <Link to="/login" className="nav-link-btn">Log In</Link>
            <Link to="/signup" className="nav-btn-primary">Get Started</Link>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="hero">
        <div className="hero-bg">
          <div className="hero-gradient"></div>
          <div className="hero-grid"></div>
        </div>
        <div className="hero-content">
          <div className="hero-badge">
            <i className="fas fa-star"></i>
            Trusted by 500+ tradespeople across Ireland
          </div>
          <h1>
            Your AI Receptionist
            <span className="gradient-text"> Never Sleeps</span>
          </h1>
          <p className="hero-subtitle">
            Stop missing calls and losing jobs. Let our AI handle your phone calls, 
            book appointments, and manage your customers while you focus on what you do best.
          </p>
          <div className="hero-cta">
            <Link to="/signup" className="btn-hero-primary">
              <i className="fas fa-rocket"></i>
              Start Free Trial
            </Link>
            <a href="#demo" className="btn-hero-secondary">
              <i className="fas fa-play-circle"></i>
              Watch Demo
            </a>
          </div>
          <div className="hero-stats">
            <div className="stat">
              <span className="stat-number">10,000+</span>
              <span className="stat-label">Calls Handled</span>
            </div>
            <div className="stat-divider"></div>
            <div className="stat">
              <span className="stat-number">98%</span>
              <span className="stat-label">Customer Satisfaction</span>
            </div>
            <div className="stat-divider"></div>
            <div className="stat">
              <span className="stat-number">40%</span>
              <span className="stat-label">More Bookings</span>
            </div>
          </div>
        </div>
        <div className="hero-visual">
          <div className="phone-mockup">
            <div className="phone-screen">
              <div className="call-ui">
                <div className="caller-avatar">
                  <i className="fas fa-user"></i>
                </div>
                <div className="caller-info">
                  <span className="caller-name">Incoming Call</span>
                  <span className="caller-number">+353 86 XXX XXXX</span>
                </div>
                <div className="ai-badge">
                  <i className="fas fa-robot"></i> AI Answering
                </div>
                <div className="call-wave">
                  <span></span><span></span><span></span><span></span><span></span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="features">
        <div className="section-container">
          <div className="section-header">
            <span className="section-badge">Features</span>
            <h2>Everything you need to grow your trade business</h2>
            <p>Powerful tools designed specifically for tradespeople like plumbers, electricians, roofers, and more.</p>
          </div>
          <div className="features-grid">
            {features.map((feature, index) => (
              <div key={index} className="feature-card" style={{ animationDelay: `${index * 0.1}s` }}>
                <div className="feature-icon">
                  <i className={feature.icon}></i>
                </div>
                <h3>{feature.title}</h3>
                <p>{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="how-it-works">
        <div className="section-container">
          <div className="section-header">
            <span className="section-badge">How It Works</span>
            <h2>Get started in minutes</h2>
          </div>
          <div className="steps">
            <div className="step">
              <div className="step-number">1</div>
              <h3>Sign Up</h3>
              <p>Create your account and set up your business profile in under 5 minutes.</p>
            </div>
            <div className="step-connector"></div>
            <div className="step">
              <div className="step-number">2</div>
              <h3>Connect Your Phone</h3>
              <p>Forward your business calls to your new AI receptionist number.</p>
            </div>
            <div className="step-connector"></div>
            <div className="step">
              <div className="step-number">3</div>
              <h3>Start Growing</h3>
              <p>Watch your bookings increase as you never miss another call.</p>
            </div>
          </div>
        </div>
      </section>

      {/* Testimonials Section */}
      <section id="testimonials" className="testimonials">
        <div className="section-container">
          <div className="section-header">
            <span className="section-badge">Testimonials</span>
            <h2>Loved by tradespeople across Ireland</h2>
          </div>
          <div className="testimonial-showcase">
            <div className="testimonial-cards">
              {testimonials.map((testimonial, index) => (
                <div 
                  key={index} 
                  className={`testimonial-card ${index === activeTestimonial ? 'active' : ''}`}
                >
                  <div className="testimonial-rating">
                    {[...Array(testimonial.rating)].map((_, i) => (
                      <i key={i} className="fas fa-star"></i>
                    ))}
                  </div>
                  <p className="testimonial-text">"{testimonial.text}"</p>
                  <div className="testimonial-author">
                    <img src={testimonial.image} alt={testimonial.name} />
                    <div>
                      <span className="author-name">{testimonial.name}</span>
                      <span className="author-company">{testimonial.company}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <div className="testimonial-dots">
              {testimonials.map((_, index) => (
                <button
                  key={index}
                  className={`dot ${index === activeTestimonial ? 'active' : ''}`}
                  onClick={() => setActiveTestimonial(index)}
                />
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section id="pricing" className="pricing">
        <div className="section-container">
          <div className="section-header">
            <span className="section-badge">Pricing</span>
            <h2>Simple, transparent pricing</h2>
            <p>No hidden fees. Cancel anytime.</p>
          </div>
          <div className="pricing-grid">
            {pricingPlans.map((plan, index) => (
              <div key={index} className={`pricing-card ${plan.highlighted ? 'highlighted' : ''}`}>
                {plan.highlighted && <div className="popular-badge">Most Popular</div>}
                <h3>{plan.name}</h3>
                <div className="price">
                  <span className="amount">{plan.price}</span>
                  <span className="period">{plan.period}</span>
                </div>
                <p className="plan-description">{plan.description}</p>
                <ul className="plan-features">
                  {plan.features.map((feature, i) => (
                    <li key={i}>
                      <i className="fas fa-check"></i>
                      {feature}
                    </li>
                  ))}
                </ul>
                <Link 
                  to="/signup" 
                  className={`plan-btn ${plan.highlighted ? 'primary' : 'secondary'}`}
                >
                  {plan.cta}
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="cta-section">
        <div className="cta-container">
          <div className="cta-content">
            <h2>Ready to never miss a call again?</h2>
            <p>Join hundreds of tradespeople who are growing their business with TradesAI.</p>
            <Link to="/signup" className="btn-cta">
              Get Started Free
              <i className="fas fa-arrow-right"></i>
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="landing-footer">
        <div className="footer-container">
          <div className="footer-main">
            <div className="footer-brand">
              <div className="footer-logo">
                <i className="fas fa-bolt"></i>
                <span>TradesAI</span>
              </div>
              <p>AI-powered receptionist and business management for tradespeople.</p>
              <div className="social-links">
                <a href="#"><i className="fab fa-twitter"></i></a>
                <a href="#"><i className="fab fa-linkedin"></i></a>
                <a href="#"><i className="fab fa-facebook"></i></a>
              </div>
            </div>
            <div className="footer-links">
              <div className="footer-column">
                <h4>Product</h4>
                <a href="#features">Features</a>
                <a href="#pricing">Pricing</a>
                <a href="#testimonials">Testimonials</a>
              </div>
              <div className="footer-column">
                <h4>Company</h4>
                <a href="#">About Us</a>
                <a href="#">Careers</a>
                <a href="#">Contact</a>
              </div>
              <div className="footer-column">
                <h4>Legal</h4>
                <a href="#">Privacy Policy</a>
                <a href="#">Terms of Service</a>
                <a href="#">Cookie Policy</a>
              </div>
            </div>
          </div>
          <div className="footer-bottom">
            <p>&copy; 2026 TradesAI. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default Landing;

