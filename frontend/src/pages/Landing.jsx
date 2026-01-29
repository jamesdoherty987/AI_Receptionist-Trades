import { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import DarkVeil from '../components/DarkVeil';
import './Landing.css';

// Animated counter component with intersection observer
function NumberTicker({ end, duration = 2000, suffix = '' }) {
  const [count, setCount] = useState(0);
  const [isVisible, setIsVisible] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
        }
      },
      { threshold: 0.1 }
    );

    if (ref.current) {
      observer.observe(ref.current);
    }

    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!isVisible) return;

    let startTime;
    const animate = (currentTime) => {
      if (!startTime) startTime = currentTime;
      const progress = (currentTime - startTime) / duration;

      if (progress < 1) {
        setCount(Math.floor(end * progress));
        requestAnimationFrame(animate);
      } else {
        setCount(end);
      }
    };

    requestAnimationFrame(animate);
  }, [isVisible, end, duration]);

  return <span ref={ref}>{count.toLocaleString()}{suffix}</span>;
}

// Marquee component for testimonials
function Marquee({ children, direction = 'left', speed = 30, pauseOnHover = true }) {
  return (
    <div className={`marquee-container ${pauseOnHover ? 'pause-on-hover' : ''}`}>
      <div className={`marquee-content ${direction}`} style={{ '--speed': `${speed}s` }}>
        {children}
        {children}
      </div>
    </div>
  );
}

// Review Card for marquee
function ReviewCard({ name, company, image, text, rating }) {
  return (
    <figure className="review-card">
      <div className="review-header">
        <img src={image} alt={name} className="review-avatar" />
        <div className="review-info">
          <figcaption className="review-name">{name}</figcaption>
          <p className="review-company">{company}</p>
        </div>
      </div>
      <div className="review-rating">
        {[...Array(rating)].map((_, i) => (
          <i key={i} className="fas fa-star"></i>
        ))}
      </div>
      <blockquote className="review-text">"{text}"</blockquote>
    </figure>
  );
}

function Landing() {
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  const reviews = [
    {
      name: "Mike O'Brien",
      company: "O'Brien Plumbing",
      image: "https://randomuser.me/api/portraits/men/32.jpg",
      text: "This AI receptionist has completely transformed how we handle calls. We never miss a lead now!",
      rating: 5
    },
    {
      name: "Sarah Thompson",
      company: "Thompson Electrical",
      image: "https://randomuser.me/api/portraits/women/44.jpg",
      text: "The booking system is seamless. Customers love being able to schedule appointments instantly.",
      rating: 5
    },
    {
      name: "James McCarthy",
      company: "McCarthy Roofing",
      image: "https://randomuser.me/api/portraits/men/67.jpg",
      text: "We've seen a 40% increase in booked jobs since using this system. Worth every penny!",
      rating: 5
    },
    {
      name: "Emma Walsh",
      company: "Walsh HVAC",
      image: "https://randomuser.me/api/portraits/women/68.jpg",
      text: "Finally, a system that understands the trades business. My customers love the quick responses.",
      rating: 5
    },
    {
      name: "David Ryan",
      company: "Ryan Carpentry",
      image: "https://randomuser.me/api/portraits/men/52.jpg",
      text: "I can focus on the job knowing calls are being handled professionally. Game changer!",
      rating: 5
    },
    {
      name: "Lisa Brennan",
      company: "Brennan Painting",
      image: "https://randomuser.me/api/portraits/women/33.jpg",
      text: "The AI is so professional, customers don't even realize it's not a real person!",
      rating: 5
    }
  ];

  const firstRow = reviews.slice(0, 3);
  const secondRow = reviews.slice(3);

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

  return (
    <div className="landing">
      {/* Navigation - Light Theme */}
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
        {/* DarkVeil Background Effect */}
        <div className="hero-veil">
          <DarkVeil
            hueShift={0}
            noiseIntensity={0}
            scanlineIntensity={0}
            speed={0.5}
            scanlineFrequency={0}
            warpAmount={0}
          />
        </div>
        <div className="hero-content">
          <div className="hero-badge">
            <span className="badge-dot"></span>
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
              <span className="stat-number">
                <NumberTicker end={10000} suffix="+" />
              </span>
              <span className="stat-label">Calls Handled</span>
            </div>
            <div className="stat-divider"></div>
            <div className="stat">
              <span className="stat-number">
                <NumberTicker end={98} suffix="%" />
              </span>
              <span className="stat-label">Satisfaction</span>
            </div>
            <div className="stat-divider"></div>
            <div className="stat">
              <span className="stat-number">
                <NumberTicker end={40} suffix="%" />
              </span>
              <span className="stat-label">More Bookings</span>
            </div>
          </div>
        </div>
        <div className="hero-visual">
          <div className="phone-mockup">
            <div className="phone-notch"></div>
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
                  <span className="ai-pulse"></span>
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

      {/* Logos Section */}
      <section className="logos-section">
        <div className="section-container">
          <p className="logos-title">Integrates with tools you already use</p>
          <div className="logos-grid">
            <div className="logo-item"><i className="fab fa-google"></i> Google Calendar</div>
            <div className="logo-item"><i className="fas fa-phone-alt"></i> Twilio</div>
            <div className="logo-item"><i className="fab fa-stripe-s"></i> Stripe</div>
            <div className="logo-item"><i className="fas fa-brain"></i> OpenAI</div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="features">
        <div className="section-container">
          <div className="section-header">
            <span className="section-badge">Features</span>
            <h2>Everything you need to <span className="gradient-text">grow your business</span></h2>
            <p>Powerful tools designed specifically for tradespeople like plumbers, electricians, roofers, and more.</p>
          </div>
          <div className="features-grid">
            {features.map((feature, index) => (
              <div 
                key={index} 
                className="feature-card"
              >
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
            <h2>Get started in <span className="gradient-text">3 simple steps</span></h2>
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

      {/* Testimonials Section with Marquee */}
      <section id="testimonials" className="testimonials">
        <div className="section-container">
          <div className="section-header">
            <span className="section-badge">Testimonials</span>
            <h2>Loved by <span className="gradient-text">tradespeople</span> across Ireland</h2>
          </div>
        </div>
        <div className="testimonials-marquee">
          <Marquee direction="left" speed={40}>
            {firstRow.map((review, index) => (
              <ReviewCard key={index} {...review} />
            ))}
          </Marquee>
          <Marquee direction="right" speed={40}>
            {secondRow.map((review, index) => (
              <ReviewCard key={index} {...review} />
            ))}
          </Marquee>
          <div className="marquee-fade marquee-fade-left"></div>
          <div className="marquee-fade marquee-fade-right"></div>
        </div>
      </section>

      {/* Pricing Section */}
      <section id="pricing" className="pricing">
        <div className="section-container">
          <div className="section-header">
            <span className="section-badge">Pricing</span>
            <h2>Simple, <span className="gradient-text">transparent pricing</span></h2>
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
