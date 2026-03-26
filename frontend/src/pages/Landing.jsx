import { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import Tilt from 'react-parallax-tilt';
import DarkVeil from '../components/DarkVeil';
import './Landing.css';

// ---- Word Rotator for hero ----
const HERO_WORDS = ['Never Sleeps', 'Books Jobs', 'Never Misses', 'Saves You Money', 'Works 24/7'];
function WordRotator() {
  const [index, setIndex] = useState(0);
  const [isAnimating, setIsAnimating] = useState(false);
  useEffect(() => {
    const interval = setInterval(() => {
      setIsAnimating(true);
      setTimeout(() => { setIndex(i => (i + 1) % HERO_WORDS.length); setIsAnimating(false); }, 400);
    }, 3000);
    return () => clearInterval(interval);
  }, []);
  return <span className={`word-rotator ${isAnimating ? 'exit' : 'enter'}`}>{HERO_WORDS[index]}</span>;
}

// ---- Animated counter ----
function NumberTicker({ end, duration = 2000, suffix = '' }) {
  const [count, setCount] = useState(0);
  const [isVisible, setIsVisible] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) setIsVisible(true); }, { threshold: 0.1 });
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, []);
  useEffect(() => {
    if (!isVisible) return;
    let start;
    const animate = (t) => {
      if (!start) start = t;
      const p = (t - start) / duration;
      if (p < 1) { setCount(Math.floor(end * p)); requestAnimationFrame(animate); }
      else setCount(end);
    };
    requestAnimationFrame(animate);
  }, [isVisible, end, duration]);
  return <span ref={ref}>{count.toLocaleString()}{suffix}</span>;
}

// ---- Marquee ----
function Marquee({ children, direction = 'left', speed = 30, pauseOnHover = true }) {
  return (
    <div className={`marquee-container ${pauseOnHover ? 'pause-on-hover' : ''}`}>
      <div className={`marquee-content ${direction}`} style={{ '--speed': `${speed}s` }}>{children}{children}</div>
    </div>
  );
}

function ReviewCard({ name, company, image, text, rating }) {
  return (
    <figure className="review-card">
      <div className="review-header">
        <img src={image} alt={name} className="review-avatar" />
        <div className="review-info"><figcaption className="review-name">{name}</figcaption><p className="review-company">{company}</p></div>
      </div>
      <div className="review-rating">{[...Array(rating)].map((_, i) => <i key={i} className="fas fa-star"></i>)}</div>
      <blockquote className="review-text">"{text}"</blockquote>
    </figure>
  );
}

// ---- Live Conversation Transcript ----
const CONVERSATION = [
  { from: 'customer', text: "Hi, I need a plumber for a leaking pipe under my kitchen sink." },
  { from: 'ai', text: "I can definitely help with that. When would suit you best?" },
  { from: 'customer', text: "Tomorrow morning if possible?" },
  { from: 'ai', text: "I have 9:30 AM available tomorrow. Shall I book that in for you?" },
  { from: 'customer', text: "Yes please, that's perfect." },
  { from: 'ai', text: "You're all booked for tomorrow at 9:30 AM. We'll send you a confirmation text shortly." },
];

function LiveTranscript() {
  const [visibleCount, setVisibleCount] = useState(0);
  const [typing, setTyping] = useState(false);
  const containerRef = useRef(null);

  useEffect(() => {
    if (visibleCount >= CONVERSATION.length) {
      // Reset after a pause
      const resetTimer = setTimeout(() => { setVisibleCount(0); }, 4000);
      return () => clearTimeout(resetTimer);
    }
    // Show typing indicator, then reveal message
    setTyping(true);
    const typingDelay = CONVERSATION[visibleCount].from === 'ai' ? 1200 : 800;
    const timer = setTimeout(() => {
      setTyping(false);
      setVisibleCount(c => c + 1);
    }, typingDelay);
    return () => clearTimeout(timer);
  }, [visibleCount]);

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [visibleCount, typing]);

  return (
    <div className="live-transcript" ref={containerRef}>
      {CONVERSATION.slice(0, visibleCount).map((msg, i) => (
        <div key={i} className={`transcript-msg ${msg.from}`}>
          {msg.from === 'ai' && <span className="msg-label"><i className="fas fa-robot"></i> AI</span>}
          <div className="msg-bubble">{msg.text}</div>
        </div>
      ))}
      {typing && visibleCount < CONVERSATION.length && (
        <div className={`transcript-msg ${CONVERSATION[visibleCount].from} typing`}>
          {CONVERSATION[visibleCount].from === 'ai' && <span className="msg-label"><i className="fas fa-robot"></i> AI</span>}
          <div className="msg-bubble typing-dots"><span></span><span></span><span></span></div>
        </div>
      )}
    </div>
  );
}

// ---- Mesh Gradient Canvas Background ----
function MeshGradient() {
  const canvasRef = useRef(null);
  const mouseRef = useRef({ x: 0.5, y: 0.5 });
  const animRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let w, h;
    const resize = () => { w = canvas.width = canvas.offsetWidth; h = canvas.height = canvas.offsetHeight; };
    resize();
    window.addEventListener('resize', resize);

    const blobs = [
      { x: 0.3, y: 0.3, r: 0.35, color: [14, 165, 233], speed: 0.0003 },
      { x: 0.7, y: 0.6, r: 0.3, color: [236, 72, 153], speed: 0.0004 },
      { x: 0.5, y: 0.8, r: 0.25, color: [139, 92, 246], speed: 0.00035 },
      { x: 0.2, y: 0.7, r: 0.2, color: [16, 185, 129], speed: 0.00025 },
    ];

    let t = 0;
    const draw = () => {
      t++;
      ctx.clearRect(0, 0, w, h);
      blobs.forEach((b, i) => {
        const mx = mouseRef.current.x;
        const my = mouseRef.current.y;
        const bx = (b.x + Math.sin(t * b.speed + i) * 0.1 + (mx - 0.5) * 0.05) * w;
        const by = (b.y + Math.cos(t * b.speed * 1.3 + i * 2) * 0.1 + (my - 0.5) * 0.05) * h;
        const br = b.r * Math.min(w, h);
        const grad = ctx.createRadialGradient(bx, by, 0, bx, by, br);
        grad.addColorStop(0, `rgba(${b.color.join(',')}, 0.15)`);
        grad.addColorStop(1, `rgba(${b.color.join(',')}, 0)`);
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, w, h);
      });
      animRef.current = requestAnimationFrame(draw);
    };
    draw();

    const handleMouse = (e) => {
      mouseRef.current = { x: e.clientX / window.innerWidth, y: e.clientY / window.innerHeight };
    };
    window.addEventListener('mousemove', handleMouse);

    return () => {
      cancelAnimationFrame(animRef.current);
      window.removeEventListener('resize', resize);
      window.removeEventListener('mousemove', handleMouse);
    };
  }, []);

  return <canvas ref={canvasRef} className="mesh-gradient-canvas" />;
}

// ---- Dashboard Preview Carousel ----
const DASHBOARD_TABS = [
  { label: 'Jobs', icon: 'fa-briefcase', img: 'https://pub-6d2ed0f2cb5645b68bd219a42aed3749.r2.dev/assets/screenshot-jobs.png' },
  { label: 'Calendar', icon: 'fa-calendar', img: 'https://pub-6d2ed0f2cb5645b68bd219a42aed3749.r2.dev/assets/screenshot-calendar.png' },
  { label: 'Finances', icon: 'fa-chart-line', img: 'https://pub-6d2ed0f2cb5645b68bd219a42aed3749.r2.dev/assets/screenshot-finances.png' },
];

function DashboardPreview() {
  const [activeTab, setActiveTab] = useState(0);
  useEffect(() => {
    const interval = setInterval(() => setActiveTab(t => (t + 1) % DASHBOARD_TABS.length), 5000);
    return () => clearInterval(interval);
  }, []);
  return (
    <div className="dashboard-preview">
      <div className="dp-tabs">
        {DASHBOARD_TABS.map((tab, i) => (
          <button key={i} className={`dp-tab ${activeTab === i ? 'active' : ''}`} onClick={() => setActiveTab(i)}>
            <i className={`fas ${tab.icon}`}></i> {tab.label}
          </button>
        ))}
      </div>
      <div className="dp-screen">
        <img src={DASHBOARD_TABS[activeTab].img} alt={DASHBOARD_TABS[activeTab].label} className="dp-screenshot"
          onError={(e) => { e.target.style.display = 'none'; }} />
        <div className="dp-placeholder">
          <i className={`fas ${DASHBOARD_TABS[activeTab].icon}`}></i>
          <span>{DASHBOARD_TABS[activeTab].label} Dashboard</span>
        </div>
      </div>
    </div>
  );
}

// ---- Main Landing Component ----
function Landing() {
  const CONTACT_EMAIL = 'j.p.enterprisehq@gmail.com';
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const [isMuted, setIsMuted] = useState(true);
  const [showContactModal, setShowContactModal] = useState(false);
  const videoRef = useRef(null);

  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth <= 768);
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    const setVolume = () => { video.volume = 0.3; };
    video.addEventListener('play', setVolume);
    return () => video.removeEventListener('play', setVolume);
  }, []);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) video.play().catch(() => {}); else video.pause(); }, { threshold: 0.25 });
    obs.observe(video);
    return () => obs.disconnect();
  }, []);

  const toggleMute = () => { const v = videoRef.current; if (!v) return; v.muted = !v.muted; setIsMuted(v.muted); };

  const [isCallPlaying, setIsCallPlaying] = useState(false);
  const callAudioRef = useRef(null);
  const toggleDemoCall = () => {
    if (!callAudioRef.current) {
      callAudioRef.current = new Audio('https://pub-6d2ed0f2cb5645b68bd219a42aed3749.r2.dev/assets/demo-call.mp3');
      callAudioRef.current.volume = 0.8;
      callAudioRef.current.addEventListener('ended', () => setIsCallPlaying(false));
    }
    if (isCallPlaying) { callAudioRef.current.pause(); setIsCallPlaying(false); }
    else { callAudioRef.current.play(); setIsCallPlaying(true); }
  };

  const showReviews = false;
  const showPricing = true;
  const showWatchDemo = false;

  const reviews = [
    { name: "Mike O'Brien", company: "O'Brien Plumbing", image: "https://randomuser.me/api/portraits/men/32.jpg", text: "This AI receptionist has completely transformed how we handle calls. We never miss a lead now!", rating: 5 },
    { name: "Sarah Thompson", company: "Thompson Electrical", image: "https://randomuser.me/api/portraits/women/44.jpg", text: "The booking system is seamless. Customers love being able to schedule appointments instantly.", rating: 5 },
    { name: "James McCarthy", company: "McCarthy Roofing", image: "https://randomuser.me/api/portraits/men/67.jpg", text: "We've seen a 40% increase in booked jobs since using this system. Worth every penny!", rating: 5 },
    { name: "Emma Walsh", company: "Walsh HVAC", image: "https://randomuser.me/api/portraits/women/68.jpg", text: "Finally, a system that understands the trades business. My customers love the quick responses.", rating: 5 },
    { name: "David Ryan", company: "Ryan Carpentry", image: "https://randomuser.me/api/portraits/men/52.jpg", text: "I can focus on the job knowing calls are being handled professionally. Game changer!", rating: 5 },
    { name: "Lisa Brennan", company: "Brennan Painting", image: "https://randomuser.me/api/portraits/women/33.jpg", text: "The AI is so professional, customers don't even realize it's not a real person!", rating: 5 },
  ];
  const firstRow = reviews.slice(0, 3);
  const secondRow = reviews.slice(3);

  const features = [
    { icon: "fas fa-phone-volume", title: "24/7 AI Receptionist", description: "Never miss a call again. Our AI answers professionally, day or night, capturing every lead.", size: 'large' },
    { icon: "fas fa-calendar-check", title: "Smart Scheduling", description: "Automatic appointment booking synced with your calendar. No double bookings, no hassle.", size: 'medium' },
    { icon: "fas fa-users", title: "Customer Management", description: "Keep track of all your clients, their job history, and preferences in one place.", size: 'medium' },
    { icon: "fas fa-chart-line", title: "Financial Tracking", description: "Monitor revenue, track payments, and send invoices directly from the dashboard.", size: 'small' },
    { icon: "fas fa-hard-hat", title: "Worker Management", description: "Assign jobs to your team, track their schedules, and prevent conflicts.", size: 'small' },
    { icon: "fas fa-comments", title: "AI Chat Support", description: "Let customers chat with your AI assistant for quotes and information anytime.", size: 'small' },
  ];

  const pricingPlans = [
    { name: "Free Trial", price: "Free", period: "for 14 days", description: "Try everything risk-free", features: ["All features included", "Unlimited AI calls", "Smart scheduling", "Customer management", "Worker management", "Financial tracking", "No credit card required"], cta: "Start Free Trial", highlighted: false },
    { name: "Pro", price: "€99", period: "/month", description: "Full access to grow your business", features: ["All features included", "Unlimited AI calls", "Smart scheduling", "Customer management", "Worker management", "Financial tracking & invoicing", "Priority support"], cta: "Get Started", highlighted: true },
  ];

  return (
    <div className="landing">
      {/* Mesh Gradient Background */}
      <MeshGradient />

      {/* Navigation */}
      <nav className="landing-nav">
        <div className="nav-container">
          <div className="nav-logo"><i className="fas fa-bolt"></i><span>BookedForYou</span></div>
          <button className="mobile-menu-btn" onClick={() => setIsMenuOpen(!isMenuOpen)}>
            <i className={`fas ${isMenuOpen ? 'fa-times' : 'fa-bars'}`}></i>
          </button>
          <div className={`nav-links ${isMenuOpen ? 'open' : ''}`}>
            <a href="#features">Features</a>
            {showReviews && <a href="#testimonials">Testimonials</a>}
            {showPricing && <a href="#pricing">Pricing</a>}
            <Link to="/login" className="nav-link-btn">Log In</Link>
            <Link to="/signup" className="nav-btn-primary">Get Started</Link>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="hero">
        <div className="hero-veil">
          <DarkVeil hueShift={0} noiseIntensity={0} scanlineIntensity={0} speed={0.5} scanlineFrequency={0} warpAmount={0} />
        </div>
        <div className="hero-content">
          <div className="hero-badge"><span className="badge-dot"></span>Leave Answering Your Phone In The Past</div>
          <h1>The Receptionist That<br/><span className="gradient-text"><WordRotator /></span></h1>
          <p className="hero-subtitle">
            Stop missing calls and losing jobs. Let our AI handle your phone calls,
            book appointments, and manage your customers while you focus on what you do best.
          </p>
          <div className="hero-cta">
            <Link to="/signup" className="btn-hero-primary"><i className="fas fa-rocket"></i> Start Free Trial</Link>
            {showWatchDemo && <a href="#demo" className="btn-hero-secondary"><i className="fas fa-play-circle"></i> Watch Demo</a>}
          </div>
          <div className="hero-stats">
            <div className="stat"><span className="stat-number"><NumberTicker end={1000} suffix="+" /></span><span className="stat-label">Calls Tested</span></div>
            <div className="stat-divider"></div>
            <div className="stat"><span className="stat-number"><NumberTicker end={0}/></span><span className="stat-label">Customers Missed</span></div>
            <div className="stat-divider"></div>
            <div className="stat"><span className="stat-number"><NumberTicker end={30} suffix="%" /></span><span className="stat-label">More Bookings</span></div>
          </div>
        </div>
        <div className="hero-visual">
          <div className="hero-video-container">
            <video ref={videoRef} className="hero-video" autoPlay muted loop playsInline controls>
              <source src="https://pub-6d2ed0f2cb5645b68bd219a42aed3749.r2.dev/assets/cinematic-explainer.mp4" type="video/mp4" />
            </video>
            {isMuted && <span className="video-sound-hint" onClick={toggleMute} role="button" tabIndex={0}>🔊 Sound on</span>}
          </div>
        </div>
      </section>

      {/* Features — Bento Grid */}
      <section id="features" className="features">
        <div className="section-container">
          <div className="section-header">
            <span className="section-badge">Features</span>
            <h2>Everything you need to <span className="gradient-text">grow your business</span></h2>
            <p>Powerful tools designed specifically for tradespeople like plumbers, electricians, roofers, and more.</p>
          </div>
          <div className="bento-grid">
            {features.map((f, i) => (
              <div key={i} className={`bento-card bento-${f.size}`} style={{ animationDelay: `${i * 0.08}s` }}>
                <div className="bento-icon"><i className={f.icon}></i></div>
                <h3>{f.title}</h3>
                <p>{f.description}</p>
                {i === 0 && null /* mini demo removed */}
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
            <div className="step"><div className="step-number">1</div><h3>Sign Up</h3><p>Create your account and set up your business profile in under 5 minutes.</p></div>
            <div className="step-connector"></div>
            <div className="step"><div className="step-number">2</div><h3>Connect Your Phone</h3><p>Forward your business calls to your new AI receptionist number.</p></div>
            <div className="step-connector"></div>
            <div className="step"><div className="step-number">3</div><h3>Start Growing</h3><p>Watch your bookings increase as you never miss another call.</p></div>
          </div>
        </div>
      </section>

      {/* Phone Demo Section */}
      <section className="phone-demo-section">
        <div className="section-container">
          <div className="phone-demo-layout">
            <div className="phone-demo-text">
              <span className="section-badge">Hear It In Action</span>
              <h2>Your AI receptionist <span className="gradient-text">answers every call</span></h2>
              <p>While you're on a job, your AI handles incoming calls professionally — booking appointments, answering questions, and never putting a customer on hold.</p>
              <button className="demo-call-btn" onClick={toggleDemoCall}>
                <i className={`fas ${isCallPlaying ? 'fa-pause' : 'fa-play'}`}></i>
                {isCallPlaying ? 'Pause Demo Call' : 'Listen to a Demo Call'}
              </button>
            </div>
            <div className="phone-demo-visual">
              <Tilt tiltMaxAngleX={isMobile ? 8 : 15} tiltMaxAngleY={isMobile ? 8 : 15} perspective={1000} scale={1.02} transitionSpeed={2000} gyroscope={true} className="phone-tilt-wrapper">
                <div className={`iphone-frame ${isCallPlaying ? 'call-active' : ''}`}>
                  <div className="iphone-btn-silent"></div><div className="iphone-btn-vol-up"></div><div className="iphone-btn-vol-down"></div><div className="iphone-btn-power"></div>
                  <div className="iphone-bezel"><div className="iphone-screen">
                    <div className="iphone-status-bar">
                      <span className="status-time">9:41</span>
                      <div className="status-dynamic-island"><div className="island-camera"></div></div>
                      <div className="status-icons"><i className="fas fa-signal"></i><i className="fas fa-wifi"></i><div className="status-battery"><div className="battery-body"><div className="battery-fill"></div></div><div className="battery-nub"></div></div></div>
                    </div>
                    <div className="call-ui">
                      <div className="caller-avatar"><i className="fas fa-phone-alt"></i></div>
                      <div className="caller-info"><span className="caller-name">{isCallPlaying ? "Mary O'Brien" : 'Incoming Call'}</span><span className="caller-number">{isCallPlaying ? '087 654 3210' : 'New Customer'}</span></div>
                      <div className="ai-badge"><span className="ai-pulse"></span>{isCallPlaying ? 'AI Connected' : 'AI Answering...'}</div>
                      <div className="call-wave"><span></span><span></span><span></span><span></span><span></span></div>
                      <div className="call-actions">
                        <div className="call-action-btn"><div className="action-circle"><i className="fas fa-microphone-slash"></i></div><span>mute</span></div>
                        <div className="call-action-btn"><div className="action-circle"><i className="fas fa-th"></i></div><span>keypad</span></div>
                        <div className="call-action-btn"><div className="action-circle"><i className="fas fa-volume-up"></i></div><span>speaker</span></div>
                      </div>
                      <div className="call-end-row"><div className="call-end-btn"><i className="fas fa-phone-alt"></i></div></div>
                    </div>
                    <div className="iphone-home-indicator"></div>
                    <div className="iphone-screen-glare"></div>
                  </div></div>
                </div>
              </Tilt>
            </div>
          </div>
        </div>
      </section>

      {showReviews && (
        <section id="testimonials" className="testimonials">
          <div className="section-container"><div className="section-header"><span className="section-badge">Testimonials</span><h2>Loved by <span className="gradient-text">tradespeople</span> across Ireland</h2></div></div>
          <div className="testimonials-marquee">
            <Marquee direction="left" speed={40}>{firstRow.map((r, i) => <ReviewCard key={i} {...r} />)}</Marquee>
            <Marquee direction="right" speed={40}>{secondRow.map((r, i) => <ReviewCard key={i} {...r} />)}</Marquee>
            <div className="marquee-fade marquee-fade-left"></div><div className="marquee-fade marquee-fade-right"></div>
          </div>
        </section>
      )}

      {showPricing && (
        <section id="pricing" className="pricing">
          <div className="section-container">
            <div className="section-header"><span className="section-badge">Pricing</span><h2>Simple, <span className="gradient-text">transparent pricing</span></h2><p>No hidden fees. Cancel anytime.</p></div>
            <div className="pricing-grid">
              {pricingPlans.map((plan, i) => (
                <div key={i} className={`pricing-card ${plan.highlighted ? 'highlighted' : ''}`}>
                  {plan.highlighted && <div className="popular-badge">Most Popular</div>}
                  <h3>{plan.name}</h3>
                  <div className="price"><span className="amount">{plan.price}</span><span className="period">{plan.period}</span></div>
                  <p className="plan-description">{plan.description}</p>
                  <ul className="plan-features">{plan.features.map((f, j) => <li key={j}><i className="fas fa-check"></i>{f}</li>)}</ul>
                  <Link to="/signup" className={`plan-btn ${plan.highlighted ? 'primary' : 'secondary'}`}>{plan.cta}</Link>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      <section className="cta-section">
        <div className="cta-container">
          <div className="cta-content">
            <h2>Ready to never miss a call again?</h2>
            <p>Join hundreds of tradespeople who are growing their business with BookedForYou.</p>
            <Link to="/signup" className="btn-cta">Get Started Free <i className="fas fa-arrow-right"></i></Link>
          </div>
        </div>
      </section>

      <footer className="landing-footer">
        <div className="footer-container">
          <div className="footer-main">
            <div className="footer-brand">
              <div className="footer-logo"><i className="fas fa-bolt"></i><span>BookedForYou</span></div>
              <p>AI-powered receptionist and business management for tradespeople.</p>
              <div className="social-links"><a href="#"><i className="fab fa-twitter"></i></a><a href="#"><i className="fab fa-linkedin"></i></a><a href="#"><i className="fab fa-facebook"></i></a></div>
            </div>
            <div className="footer-links">
              <div className="footer-column"><h4>Product</h4><a href="#features">Features</a>{showPricing && <a href="#pricing">Pricing</a>}{showReviews && <a href="#testimonials">Testimonials</a>}</div>
              <div className="footer-column"><h4>Company</h4><a href="#">About Us</a><a href="#" onClick={(e) => { e.preventDefault(); setShowContactModal(true); }}>Contact</a></div>
              <div className="footer-column"><h4>Legal</h4><Link to="/privacy">Privacy Policy</Link><Link to="/terms">Terms of Service</Link><Link to="/privacy">Cookie Policy</Link></div>
            </div>
          </div>
          <div className="footer-bottom"><p>&copy; 2026 BookedForYou. All rights reserved.</p></div>
        </div>
      </footer>

      {showContactModal && (
        <div className="contact-modal-overlay" onClick={() => setShowContactModal(false)}>
          <div className="contact-modal" onClick={(e) => e.stopPropagation()}>
            <button className="contact-modal-close" onClick={() => setShowContactModal(false)}><i className="fas fa-times"></i></button>
            <h3>Get in Touch</h3>
            <p>Have a question or need help? Send us an email and we'll get back to you as soon as possible.</p>
            <a href={`mailto:${CONTACT_EMAIL}`} className="contact-email-btn"><i className="fas fa-envelope"></i>{CONTACT_EMAIL}</a>
          </div>
        </div>
      )}
    </div>
  );
}

export default Landing;
