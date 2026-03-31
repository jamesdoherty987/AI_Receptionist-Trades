import { useState, useEffect, useRef, useCallback } from 'react';
import { Link } from 'react-router-dom';
import Tilt from 'react-parallax-tilt';
import DarkVeil from '../components/DarkVeil';
import './Landing.css';

// ---- Scroll Reveal Hook ----
function useScrollReveal(threshold = 0.1) {
  const ref = useRef(null);
  const [isVisible, setIsVisible] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) { setIsVisible(true); obs.unobserve(el); }
    }, { threshold });
    obs.observe(el);
    return () => obs.disconnect();
  }, [threshold]);
  return [ref, isVisible];
}

// ---- Section Reveal Wrapper ----
function SectionReveal({ children, className = '', id, ...props }) {
  const [ref, isVisible] = useScrollReveal(0.08);
  return (
    <section ref={ref} id={id} className={`${className} scroll-reveal ${isVisible ? 'revealed' : ''}`} {...props}>
      {children}
    </section>
  );
}

// ---- Spotlight Card (mouse-tracking glow + border beam) ----
function SpotlightCard({ children, className = '', ...props }) {
  const cardRef = useRef(null);
  const handleMouseMove = useCallback((e) => {
    const card = cardRef.current;
    if (!card) return;
    const rect = card.getBoundingClientRect();
    card.style.setProperty('--mouse-x', `${e.clientX - rect.left}px`);
    card.style.setProperty('--mouse-y', `${e.clientY - rect.top}px`);
  }, []);
  return (
    <div ref={cardRef} className={`spotlight-card ${className}`} onMouseMove={handleMouseMove} {...props}>
      <div className="spotlight-glow" />
      <div className="border-beam" />
      {children}
    </div>
  );
}

// ---- Typewriter Effect ----
function Typewriter({ text, speed = 35, delay = 800 }) {
  const [displayed, setDisplayed] = useState('');
  const [started, setStarted] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setStarted(true), delay);
    return () => clearTimeout(t);
  }, [delay]);
  useEffect(() => {
    if (!started) return;
    if (displayed.length >= text.length) return;
    const t = setTimeout(() => setDisplayed(text.slice(0, displayed.length + 1)), speed);
    return () => clearTimeout(t);
  }, [started, displayed, text, speed]);
  return <>{displayed}<span className="typewriter-cursor">|</span></>;
}

// ---- Parallax Layer (scroll-based offset) ----
function ParallaxLayer({ children, speed = 0.1, className = '' }) {
  const ref = useRef(null);
  useEffect(() => {
    let ticking = false;
    const handleScroll = () => {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(() => {
        if (ref.current) {
          const y = window.scrollY * speed;
          ref.current.style.transform = `translateY(${y}px)`;
        }
        ticking = false;
      });
    };
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, [speed]);
  return <div ref={ref} className={className}>{children}</div>;
}

// ---- Before/After Comparison ----
const COMPARISON_DATA = [
  { metric: 'Missed Calls', before: '5-10 per week', after: '0', icon: 'fa-phone-slash' },
  { metric: 'Booking Rate', before: '~40%', after: '90%+', icon: 'fa-calendar-check' },
  { metric: 'Response Time', before: 'Minutes to hours', after: 'Instant', icon: 'fa-bolt' },
  { metric: 'After-Hours Coverage', before: 'None', after: '24/7', icon: 'fa-moon' },
  { metric: 'Admin Time / Week', before: '10+ hours', after: '~2 hours', icon: 'fa-clock' },
  { metric: 'Customer Satisfaction', before: 'Hit or miss', after: 'Consistently high', icon: 'fa-smile' },
];

function BeforeAfterComparison() {
  const [showAfter, setShowAfter] = useState(false);
  const [ref, isVisible] = useScrollReveal(0.2);

  useEffect(() => {
    if (isVisible) {
      const t = setTimeout(() => setShowAfter(true), 1200);
      return () => clearTimeout(t);
    }
  }, [isVisible]);

  return (
    <div ref={ref} className="comparison-toggle-wrapper">
      <div className="comparison-switch">
        <button className={`comp-btn ${!showAfter ? 'active' : ''}`} onClick={() => setShowAfter(false)}>
          <i className="fas fa-times-circle"></i> Before
        </button>
        <button className={`comp-btn ${showAfter ? 'active' : ''}`} onClick={() => setShowAfter(true)}>
          <i className="fas fa-check-circle"></i> After
        </button>
      </div>
      <div className="comparison-cards">
        {COMPARISON_DATA.map((item, i) => (
          <div key={i} className={`comp-card ${showAfter ? 'show-after' : 'show-before'}`} style={{ transitionDelay: `${i * 0.06}s` }}>
            <div className="comp-icon"><i className={`fas ${item.icon}`}></i></div>
            <div className="comp-metric">{item.metric}</div>
            <div className="comp-value">{showAfter ? item.after : item.before}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---- Word Rotator for hero ----
const HERO_WORDS = ['Never Sleeps', 'Books Jobs', 'Never Misses', 'Saves You Money', 'Works 24/7'];
function WordRotator() {
  const [index, setIndex] = useState(0);
  const [isAnimating, setIsAnimating] = useState(false);
  useEffect(() => {
    const interval = setInterval(() => {
      setIsAnimating(true);
      setTimeout(() => { setIndex(i => (i + 1) % HERO_WORDS.length); setIsAnimating(false); }, 250);
    }, 1800);
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

// ---- Mini Bento Animations ----

// 1. Mini Calendar (Smart Scheduling)
function MiniCalendar() {
  const [filledSlot, setFilledSlot] = useState(-1);
  useEffect(() => {
    let i = 0;
    const interval = setInterval(() => {
      setFilledSlot(i);
      i = (i + 1) % 4;
    }, 1500);
    return () => clearInterval(interval);
  }, []);
  const slots = ['9:00 AM', '10:30 AM', '1:00 PM', '3:30 PM'];
  return (
    <div className="mini-cal">
      <div className="mini-cal-header"><span>Tue, Jan 14</span></div>
      {slots.map((s, i) => (
        <div key={i} className={`mini-cal-slot ${i === filledSlot ? 'filling' : ''} ${i < filledSlot ? 'filled' : ''}`}>
          <span className="mini-cal-time">{s}</span>
          <span className="mini-cal-label">{i === filledSlot ? 'Booking...' : i < filledSlot ? 'Booked' : 'Available'}</span>
        </div>
      ))}
    </div>
  );
}

// 2. Mini Contact Stack (Customer Management)
function MiniContactStack() {
  const [phase, setPhase] = useState(0);
  const [aiTyping, setAiTyping] = useState(false);
  const [aiText, setAiText] = useState('');

  const contacts = [
    {
      name: "Sarah M.", color: '#0ea5e9', jobs: 12, revenue: '€3,240', tag: 'VIP',
      lastJob: 'Boiler repair', daysAgo: 6, nextAction: 'Annual service',
      aiNote: "Sarah's last job was a boiler repair 6 days ago. Since then, she's requested a quote for radiator installation — her annual service is due in 2 weeks.",
    },
    {
      name: "James K.", color: '#ec4899', jobs: 5, revenue: '€1,870', tag: 'New',
      lastJob: 'Pipe fitting', daysAgo: 3, nextAction: 'Follow up',
      aiNote: "James' last job was a pipe fitting 3 days ago. Since then, he's been quoted €4,200 for a full bathroom renovation — recommend a follow-up call.",
    },
    {
      name: "Emma W.", color: '#8b5cf6', jobs: 8, revenue: '€2,560', tag: 'Loyal',
      lastJob: 'Rewire', daysAgo: 12, nextAction: 'Send invoice',
      aiNote: "Emma's last job was an electrical rewire 12 days ago. Since then, she's referred 3 new customers and left a 5-star review. Invoice still pending.",
    },
  ];

  const activities = [
    { icon: 'fa-phone', text: 'AI answered call — Sarah M.', time: '2m ago', color: '#0ea5e9' },
    { icon: 'fa-calendar-check', text: 'Auto-booked — James K.', time: '15m', color: '#10b981' },
    { icon: 'fa-star', text: 'New 5★ review — Emma W.', time: '1h', color: '#f59e0b' },
  ];

  useEffect(() => {
    const interval = setInterval(() => {
      setPhase(p => (p + 1) % contacts.length);
    }, 4500);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    setAiTyping(true);
    setAiText('');
    const note = contacts[phase].aiNote;
    let i = 0;
    let charInterval = null;
    const typeTimer = setTimeout(() => {
      charInterval = setInterval(() => {
        if (i < note.length) { setAiText(note.slice(0, i + 1)); i++; }
        else { clearInterval(charInterval); charInterval = null; setAiTyping(false); }
      }, 18);
    }, 500);
    return () => {
      clearTimeout(typeTimer);
      if (charInterval) clearInterval(charInterval);
    };
  }, [phase]);

  const c = contacts[phase];

  return (
    <div className="mini-crm">
      {/* Profile card with transition */}
      <div className="crm-profile-card" key={phase}>
        <div className="crm-profile-header">
          <div className="crm-avatar-wrap">
            <div className="crm-avatar" style={{ background: `linear-gradient(135deg, ${c.color}, ${c.color}dd)` }}>{c.name[0]}</div>
            <div className="crm-avatar-status"></div>
          </div>
          <div className="crm-profile-meta">
            <div className="crm-name-row">
              <span className="crm-name">{c.name}</span>
              <span className={`crm-tag crm-tag-${c.tag.toLowerCase()}`}>{c.tag}</span>
            </div>
            <span className="crm-subtitle">Last job: {c.lastJob} · {c.daysAgo}d ago</span>
          </div>
        </div>
        <div className="crm-stats-row">
          <div className="crm-stat">
            <span className="crm-stat-val">{c.jobs}</span>
            <span className="crm-stat-lbl">Jobs</span>
            <div className="crm-stat-bar"><div className="crm-stat-bar-fill" style={{ width: `${(c.jobs / 15) * 100}%`, background: c.color }}></div></div>
          </div>
          <div className="crm-stat">
            <span className="crm-stat-val">{c.revenue}</span>
            <span className="crm-stat-lbl">Revenue</span>
          </div>
          <div className="crm-stat crm-stat-action">
            <span className="crm-stat-val">{c.nextAction}</span>
            <span className="crm-stat-lbl">Next</span>
          </div>
        </div>
      </div>

      {/* AI insight — narrative style */}
      <div className="crm-ai-bar">
        <div className="crm-ai-header">
          <div className="crm-ai-icon"><i className="fas fa-brain"></i><span className="crm-ai-icon-ring"></span></div>
          <span className="crm-ai-label">AI Insight</span>
          <span className="crm-ai-badge">LIVE</span>
        </div>
        <div className="crm-ai-body">
          <span className="crm-ai-text">{aiText}{aiTyping && <span className="crm-ai-cursor"></span>}</span>
        </div>
      </div>

      {/* Compact activity feed */}
      <div className="crm-activity-feed">
        {activities.map((a, i) => (
          <div key={i} className="crm-activity-item" style={{ animationDelay: `${i * 0.1}s` }}>
            <div className="crm-activity-dot" style={{ background: a.color }}><i className={`fas ${a.icon}`}></i></div>
            <span className="crm-activity-text">{a.text}</span>
            <span className="crm-activity-time">{a.time}</span>
          </div>
        ))}
      </div>

      {/* Dots */}
      <div className="crm-dots">
        {contacts.map((ct, i) => (
          <div key={i} className={`crm-dot ${i === phase ? 'active' : ''}`} style={{ '--dot-color': ct.color }} />
        ))}
      </div>
    </div>
  );
}

// 3. Mini Chart (Financial Tracking) — wide layout for full-width bento card
function MiniChart() {
  const [drawn, setDrawn] = useState(false);
  const [ref, isVisible] = useScrollReveal(0.3);
  useEffect(() => { if (isVisible) setDrawn(true); }, [isVisible]);

  // Revenue line
  const revenue = [20, 35, 28, 45, 40, 58, 52, 70, 65, 82, 78, 95];
  const rW = 280, rH = 50, rPx = rW / (revenue.length - 1);
  const rD = revenue.map((p, i) => `${i === 0 ? 'M' : 'L'}${i * rPx},${rH - (p / 100) * rH}`).join(' ');
  const areaD = rD + ` L${rW},${rH} L0,${rH} Z`;

  // Jobs bar chart
  const jobs = [4, 7, 5, 9, 6, 11, 8, 12];
  const maxJ = Math.max(...jobs);

  return (
    <div ref={ref} className="mini-chart-wide">
      <div className="mini-chart-stats">
        <div className="mini-chart-stat">
          <span className="mini-chart-stat-value">€12,480</span>
          <span className="mini-chart-stat-label">Revenue (MTD)</span>
        </div>
        <div className="mini-chart-stat">
          <span className="mini-chart-stat-value green">+42%</span>
          <span className="mini-chart-stat-label">vs last month</span>
        </div>
        <div className="mini-chart-stat">
          <span className="mini-chart-stat-value">62</span>
          <span className="mini-chart-stat-label">Jobs completed</span>
        </div>
      </div>
      <div className="mini-chart-graphs">
        <div className="mini-chart-graph">
          <span className="mini-chart-graph-label">Revenue</span>
          <svg viewBox={`0 0 ${rW} ${rH}`} className={`mini-chart-svg-wide ${drawn ? 'drawn' : ''}`} preserveAspectRatio="none">
            <defs>
              <linearGradient id="chartGrad" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="#0ea5e9" />
                <stop offset="100%" stopColor="#10b981" />
              </linearGradient>
              <linearGradient id="chartArea" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#0ea5e9" stopOpacity="0.15" />
                <stop offset="100%" stopColor="#0ea5e9" stopOpacity="0" />
              </linearGradient>
            </defs>
            <path d={areaD} fill="url(#chartArea)" />
            <path d={rD} fill="none" stroke="url(#chartGrad)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
        <div className="mini-chart-graph">
          <span className="mini-chart-graph-label">Jobs / week</span>
          <div className="mini-bar-chart">
            {jobs.map((j, i) => (
              <div key={i} className={`mini-bar ${drawn ? 'grown' : ''}`} style={{ height: `${(j / maxJ) * 100}%`, transitionDelay: `${i * 0.08}s` }}>
                <span className="mini-bar-val">{j}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// 4. Mini Worker Dispatch Board (Worker Management)
function MiniWorkerSchedule() {
  const [step, setStep] = useState(-1);
  const workers = [
    { name: 'Mike', initials: 'M', color: '#0ea5e9', icon: 'fa-wrench' },
    { name: 'Sarah', initials: 'S', color: '#ec4899', icon: 'fa-toolbox' },
    { name: 'James', initials: 'J', color: '#8b5cf6', icon: 'fa-hard-hat' },
  ];
  const jobs = [
    { label: 'Pipe repair', time: '9am', worker: 0 },
    { label: 'Drain clean', time: '10am', worker: 1 },
    { label: 'Radiator install', time: '11am', worker: 2 },
    { label: 'Boiler service', time: '2pm', worker: 0 },
  ];

  useEffect(() => {
    let i = -1;
    const interval = setInterval(() => {
      i++;
      if (i > jobs.length) { i = -1; setStep(-1); return; }
      setStep(i);
    }, 1100);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="dispatch-board">
      <div className="dispatch-workers">
        {workers.map((w, wi) => {
          const active = jobs.some((j, ji) => j.worker === wi && ji <= step);
          const pinging = jobs.some((j, ji) => j.worker === wi && ji === step);
          return (
            <div key={wi} className={`dispatch-avatar ${active ? 'active' : ''} ${pinging ? 'ping' : ''}`}>
              <div className="dispatch-avatar-circle" style={{ background: w.color }}>
                <i className={`fas ${w.icon}`}></i>
              </div>
              <span className="dispatch-avatar-name">{w.name}</span>
              {active && <span className="dispatch-status-dot"></span>}
            </div>
          );
        })}
      </div>
      <div className="dispatch-feed">
        {jobs.map((job, ji) => (
          <div key={ji} className={`dispatch-job ${ji <= step ? 'dispatched' : ''} ${ji === step ? 'latest' : ''}`}>
            <div className="dispatch-job-line" style={{ background: workers[job.worker].color }}></div>
            <div className="dispatch-job-content">
              <span className="dispatch-job-label">{job.label}</span>
              <span className="dispatch-job-meta">
                <i className="far fa-clock"></i> {job.time} · {workers[job.worker].name}
              </span>
            </div>
            <div className={`dispatch-job-badge ${ji <= step ? 'show' : ''}`} style={{ background: workers[job.worker].color }}>
              <i className="fas fa-check"></i>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// 5. Mini Materials List (Materials & Invoicing)
function MiniMaterials() {
  const [checked, setChecked] = useState([]);
  const items = [
    { name: 'Copper pipe 15mm', cost: '€12.50' },
    { name: 'Solder fittings x4', cost: '€8.00' },
    { name: 'PTFE tape', cost: '€2.50' },
    { name: 'Labour (1.5hrs)', cost: '€120.00' },
  ];
  useEffect(() => {
    let i = 0;
    const interval = setInterval(() => {
      setChecked(prev => {
        if (prev.length >= items.length) return [];
        return [...prev, i % items.length];
      });
      i++;
    }, 1200);
    return () => clearInterval(interval);
  }, []);
  return (
    <div className="mini-materials">
      {items.map((item, i) => (
        <div key={i} className={`mini-mat-row ${checked.includes(i) ? 'checked' : ''}`}>
          <div className="mini-mat-check"><i className={`fas ${checked.includes(i) ? 'fa-check-circle' : 'fa-circle'}`}></i></div>
          <span className="mini-mat-name">{item.name}</span>
          <span className="mini-mat-cost">{item.cost}</span>
        </div>
      ))}
      <div className="mini-mat-total">
        <span>Total</span>
        <span>€143.00</span>
      </div>
    </div>
  );
}

// 5b. Mini Chat Widget (kept but unused)
function MiniChatWidget() {
  const msgs = [
    { from: 'user', text: 'How much for a boiler service?' },
    { from: 'ai', text: 'A standard boiler service is €120. Want to book?' },
    { from: 'user', text: 'Yes please!' },
  ];
  const [count, setCount] = useState(0);
  const [typing, setTyping] = useState(false);
  useEffect(() => {
    if (count >= msgs.length) {
      const t = setTimeout(() => setCount(0), 3000);
      return () => clearTimeout(t);
    }
    setTyping(true);
    const t = setTimeout(() => { setTyping(false); setCount(c => c + 1); }, msgs[count].from === 'ai' ? 1000 : 700);
    return () => clearTimeout(t);
  }, [count]);
  return (
    <div className="mini-chat">
      {msgs.slice(0, count).map((m, i) => (
        <div key={i} className={`mini-chat-msg ${m.from}`}>{m.text}</div>
      ))}
      {typing && count < msgs.length && (
        <div className={`mini-chat-msg ${msgs[count].from} typing`}>
          <span className="mini-typing-dot"></span><span className="mini-typing-dot"></span><span className="mini-typing-dot"></span>
        </div>
      )}
    </div>
  );
}

// ---- Integration Flow Diagram ----
function IntegrationFlow() {
  const nodes = [
    { icon: 'fa-phone-alt', label: 'Phone Call', color: '#0ea5e9' },
    { icon: 'fa-robot', label: 'AI Receptionist', color: '#8b5cf6' },
    { icon: 'fa-calendar-check', label: 'Calendar', color: '#10b981' },
    { icon: 'fa-sms', label: 'SMS Confirmation', color: '#ec4899' },
  ];
  return (
    <div className="integration-flow">
      {nodes.map((node, i) => (
        <div key={i} className="flow-step-wrapper">
          <div className="flow-node" style={{ '--node-color': node.color }}>
            <div className="flow-node-icon"><i className={`fas ${node.icon}`}></i></div>
            <span className="flow-node-label">{node.label}</span>
          </div>
          {i < nodes.length - 1 && (
            <div className="flow-beam">
              <div className="flow-beam-track"></div>
              <div className="flow-beam-particle" style={{ animationDelay: `${i * 0.6}s` }}></div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// ---- Live Conversation Transcript (used in bento) ----
const CONVERSATION = [
  { from: 'customer', text: "Hi, I've got a leaking pipe under my kitchen sink." },
  { from: 'ai', text: "No problem, I can get that sorted for you. Is it a steady drip or more of a burst?" },
  { from: 'customer', text: "It's a steady drip, been going on a couple of days." },
  { from: 'ai', text: "Grand, that sounds like a pipe repair. That's usually about an hour and a half. Can I get your name please?" },
  { from: 'customer', text: "Yeah, it's John Murphy." },
  { from: 'ai', text: "That's J-O-H-N M-U-R-P-H-Y, correct?" },
  { from: 'customer', text: "That's right." },
  { from: 'ai', text: "Lovely. Is 0-8-5-1-2-3-4-5-6-7 a good number for you?" },
  { from: 'customer', text: "Yep, that's me." },
  { from: 'ai', text: "Grand. Do you have your eircode handy?" },
  { from: 'customer', text: "Yeah, V94 AB12." },
  { from: 'ai', text: "That's V-9-4-A-B-1-2. I have Tuesday and Thursday available this week. Which suits you better?" },
  { from: 'customer', text: "Thursday works." },
  { from: 'ai', text: "Brilliant. So that's John Murphy on Thursday for a leaking pipe repair. We'll send you a confirmation text shortly." },
];

function LiveTranscript() {
  const [visibleCount, setVisibleCount] = useState(0);
  const [typing, setTyping] = useState(false);
  const containerRef = useRef(null);
  useEffect(() => {
    if (visibleCount >= CONVERSATION.length) {
      const t = setTimeout(() => setVisibleCount(0), 3000);
      return () => clearTimeout(t);
    }
    setTyping(true);
    const delay = CONVERSATION[visibleCount].from === 'ai' ? 1000 : 600;
    const t = setTimeout(() => { setTyping(false); setVisibleCount(c => c + 1); }, delay);
    return () => clearTimeout(t);
  }, [visibleCount]);
  useEffect(() => {
    if (containerRef.current) containerRef.current.scrollTop = containerRef.current.scrollHeight;
  }, [visibleCount, typing]);
  return (
    <div className="mini-transcript" ref={containerRef}>
      {CONVERSATION.slice(0, visibleCount).map((msg, i) => (
        <div key={i} className={`mini-t-msg ${msg.from}`}>
          <div className="mini-t-bubble">{msg.text}</div>
        </div>
      ))}
      {typing && visibleCount < CONVERSATION.length && (
        <div className={`mini-t-msg ${CONVERSATION[visibleCount].from} typing`}>
          <div className="mini-t-bubble"><span className="mini-typing-dot"></span><span className="mini-typing-dot"></span><span className="mini-typing-dot"></span></div>
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


// ---- Phone with Reels + Call Demo ----
const CDN_BASE = 'https://pub-6d2ed0f2cb5645b68bd219a42aed3749.r2.dev/assets';
const LOCAL_BASE = '/assets';
const ASSET_BASE = import.meta.env.DEV ? LOCAL_BASE : CDN_BASE;

const REEL_VIDEOS = [
  `${ASSET_BASE}/social-17-swipe-right.mp4`,
  `${ASSET_BASE}/social-15-storytime.mp4`,
  `${ASSET_BASE}/social-4-listicle.mp4`,
];

function PhoneWithReels({ isCallPlaying, toggleDemoCall, isMobile }) {
  const [currentReel, setCurrentReel] = useState(0);
  const [nextReel, setNextReel] = useState(null);
  const [showCallUI, setShowCallUI] = useState(false);
  const [liked, setLiked] = useState(false);
  const [likeCount, setLikeCount] = useState(4200);
  const [commentCount, setCommentCount] = useState(128);
  const [shared, setShared] = useState(false);
  const [heartBurst, setHeartBurst] = useState(false);
  const [isVisible, setIsVisible] = useState(false);
  const videoRefs = useRef([]);
  const progressFillRefs = useRef([]);
  const rafRef = useRef(null);
  const phoneRef = useRef(null);
  const pausedByScrollRef = useRef(false);

  // Live clock in Ireland timezone
  const [clockTime, setClockTime] = useState(() =>
    new Date().toLocaleTimeString('en-IE', { hour: 'numeric', minute: '2-digit', timeZone: 'Europe/Dublin' })
  );
  useEffect(() => {
    const tick = () => setClockTime(
      new Date().toLocaleTimeString('en-IE', { hour: 'numeric', minute: '2-digit', timeZone: 'Europe/Dublin' })
    );
    const interval = setInterval(tick, 30000);
    return () => clearInterval(interval);
  }, []);

  // Track visibility with IntersectionObserver
  useEffect(() => {
    const el = phoneRef.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([entry]) => setIsVisible(entry.isIntersecting),
      { threshold: 0.25 }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  // Pause/resume when visibility changes
  useEffect(() => {
    const vid = videoRefs.current[currentReel];
    if (!isVisible) {
      if (vid && !vid.paused) {
        vid.pause();
        pausedByScrollRef.current = true;
      }
    } else if (pausedByScrollRef.current) {
      pausedByScrollRef.current = false;
      if (vid && vid.paused) {
        vid.play().catch(() => {});
      }
    }
  }, [isVisible]);

  // Animate progress bars by reading directly from the video element
  useEffect(() => {
    const animate = () => {
      REEL_VIDEOS.forEach((_, i) => {
        const fill = progressFillRefs.current[i];
        if (!fill) return;
        const vid = videoRefs.current[i];
        if (i === currentReel && nextReel === null && vid && vid.duration && isFinite(vid.duration) && !vid.paused) {
          fill.style.width = `${(vid.currentTime / vid.duration) * 100}%`;
        } else if (i < currentReel || (i === currentReel && nextReel !== null)) {
          fill.style.width = '100%';
        } else if (i > currentReel) {
          fill.style.width = '0%';
        }
      });
      rafRef.current = requestAnimationFrame(animate);
    };
    rafRef.current = requestAnimationFrame(animate);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, [currentReel, nextReel]);

  // Play the current reel when it's ready and we're not in call mode
  useEffect(() => {
    if (isCallPlaying || showCallUI || nextReel !== null || !isVisible || pausedByScrollRef.current) return;
    const vid = videoRefs.current[currentReel];
    if (!vid) return;
    // Don't restart if already playing (e.g. resumed by scroll)
    if (!vid.paused) return;

    const playVideo = () => {
      vid.currentTime = 0;
      vid.play().catch(() => {});
    };

    if (vid.readyState >= 3) {
      playVideo();
    } else {
      const onReady = () => playVideo();
      vid.addEventListener('canplay', onReady, { once: true });
      vid.load();
      return () => vid.removeEventListener('canplay', onReady);
    }
  }, [currentReel, isCallPlaying, showCallUI, nextReel, isVisible]);

  // Listen for video ended to trigger swipe
  useEffect(() => {
    if (isCallPlaying || showCallUI) return;
    const vid = videoRefs.current[currentReel];
    if (!vid) return;

    const onEnded = () => {
      const next = (currentReel + 1) % REEL_VIDEOS.length;
      // Preload next video
      const nextVid = videoRefs.current[next];
      if (nextVid) { nextVid.currentTime = 0; nextVid.load(); }
      // Start swipe transition
      setNextReel(next);
      // After animation completes, commit the switch
      setTimeout(() => {
        setCurrentReel(next);
        setNextReel(null);
      }, 700);
    };

    vid.addEventListener('ended', onEnded);
    return () => vid.removeEventListener('ended', onEnded);
  }, [currentReel, isCallPlaying, showCallUI]);

  // Fallback: if video doesn't end after a reasonable time, advance anyway
  useEffect(() => {
    if (isCallPlaying || showCallUI || nextReel !== null) return;
    const fallback = setTimeout(() => {
      const vid = videoRefs.current[currentReel];
      if (vid && (vid.paused || !vid.duration || vid.currentTime === 0)) {
        const next = (currentReel + 1) % REEL_VIDEOS.length;
        setNextReel(next);
        setTimeout(() => { setCurrentReel(next); setNextReel(null); }, 700);
      }
    }, 15000);
    return () => clearTimeout(fallback);
  }, [currentReel, isCallPlaying, showCallUI, nextReel]);

  // When call starts, transition to call UI
  useEffect(() => {
    if (isCallPlaying) {
      setShowCallUI(true);
      videoRefs.current.forEach(v => { if (v) v.pause(); });
    }
  }, [isCallPlaying]);

  // When call stops, go back to reels
  useEffect(() => {
    if (!isCallPlaying && showCallUI) {
      const t = setTimeout(() => { setShowCallUI(false); }, 600);
      return () => clearTimeout(t);
    }
  }, [isCallPlaying, showCallUI]);

  return (
    <div ref={phoneRef} className={`iphone-frame ${showCallUI ? 'call-active' : ''}`}>
      <div className="iphone-btn-silent"></div>
      <div className="iphone-btn-vol-up"></div>
      <div className="iphone-btn-vol-down"></div>
      <div className="iphone-btn-power"></div>
      <div className="iphone-bezel">
        <div className="iphone-screen">
          <div className="iphone-status-bar">
            <span className="status-time">{clockTime}</span>
            <div className="status-dynamic-island"><div className="island-camera"></div></div>
            <div className="status-icons">
              <i className="fas fa-signal"></i>
              <i className="fas fa-wifi"></i>
              <div className="status-battery"><div className="battery-body"><div className="battery-fill"></div></div><div className="battery-nub"></div></div>
            </div>
          </div>

          {/* Reels layer */}
          <div className={`reels-container ${showCallUI ? 'reels-hidden' : ''}`}>
            <div className="reels-viewport">
              {REEL_VIDEOS.map((src, i) => {
                let className = 'reel-video';
                let style = {};
                if (nextReel !== null) {
                  // During swipe: current slides up, next slides in from below
                  if (i === currentReel) {
                    className += ' reel-swipe-out';
                    style = { opacity: 1, zIndex: 2 };
                  } else if (i === nextReel) {
                    className += ' reel-swipe-in';
                    style = { opacity: 1, zIndex: 1 };
                  }
                } else if (i === currentReel) {
                  className += ' reel-active';
                }
                return (
                  <video
                    key={i}
                    ref={el => { videoRefs.current[i] = el; }}
                    className={className}
                    style={style}
                    src={src}
                    muted
                    playsInline
                    preload="metadata"
                  />
                );
              })}
            </div>
            {/* Reel UI overlay — TikTok style */}
            <div className="reel-overlay">
              <div className="reel-sidebar">
                <div className={`reel-sidebar-btn ${liked ? 'reel-liked' : ''}`} onClick={() => {
                  if (!liked) { setLikeCount(c => c + 1); setHeartBurst(true); setTimeout(() => setHeartBurst(false), 600); }
                  else { setLikeCount(c => c - 1); }
                  setLiked(l => !l);
                }}>
                  <i className={`fas fa-heart ${heartBurst ? 'reel-heart-pop' : ''}`}></i>
                  <span>{likeCount >= 1000 ? `${(likeCount / 1000).toFixed(1)}K` : likeCount}</span>
                </div>
                <div className="reel-sidebar-btn" onClick={() => setCommentCount(c => c + 1)}>
                  <i className="fas fa-comment"></i>
                  <span>{commentCount}</span>
                </div>
                <div className={`reel-sidebar-btn ${shared ? 'reel-shared' : ''}`} onClick={() => { navigator.clipboard.writeText('https://bookedforyou.ie').catch(() => {}); setShared(true); setTimeout(() => setShared(false), 1500); }}>
                  <i className={`fas fa-share ${shared ? 'reel-share-fly' : ''}`}></i>
                  <span>{shared ? 'Copied!' : 'Share'}</span>
                </div>
              </div>
              <div className="reel-bottom">
                <span className="reel-username">@bookedforyou</span>
                <span className="reel-caption">AI receptionist for tradespeople 🔧</span>
              </div>
              <div className="reel-progress">
                {REEL_VIDEOS.map((_, i) => (
                  <div key={i} className="reel-progress-bar">
                    <div
                      ref={el => { progressFillRefs.current[i] = el; }}
                      className="reel-progress-fill"
                    ></div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Call UI layer */}
          <div className={`call-ui ${showCallUI ? 'call-ui-visible' : 'call-ui-hidden'}`}>
            <div className="caller-avatar"><i className="fas fa-phone-alt"></i></div>
            <div className="caller-info">
              <span className="caller-name">{isCallPlaying ? "Mary O'Brien" : 'Incoming Call'}</span>
              <span className="caller-number">{isCallPlaying ? '087 654 3210' : 'New Customer'}</span>
            </div>
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
        </div>
      </div>
    </div>
  );
}


// ---- Main Landing Component ----
function Landing() {
  const CONTACT_EMAIL = 'contact@bookedforyou.ie';
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const [isMuted, setIsMuted] = useState(true);
  const [showContactModal, setShowContactModal] = useState(false);
  const [navScrolled, setNavScrolled] = useState(false);
  const videoRef = useRef(null);

  // Glassmorphism nav — track scroll position for enhanced blur
  useEffect(() => {
    const handleScroll = () => setNavScrolled(window.scrollY > 40);
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

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
      callAudioRef.current = new Audio(`${ASSET_BASE}/demo-call.mp3`);
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
    { icon: "fas fa-hard-hat", title: "Worker Management", description: "Assign jobs to your team, track their schedules, and prevent conflicts.", size: 'small' },
    { icon: "fas fa-boxes", title: "Materials & Invoicing", description: "Track materials, costs, and send professional invoices directly from the dashboard.", size: 'small' },
    { icon: "fas fa-chart-line", title: "Financial Tracking", description: "Monitor revenue, track payments, and see your business performance at a glance.", size: 'small' },
  ];

  const pricingPlans = [
    { name: "Free Trial", price: "Free", period: "for 14 days", description: "Try everything risk-free", features: ["All features included", "Unlimited AI calls", "Smart scheduling", "Customer management", "Worker management", "Financial tracking", "No credit card required"], cta: "Start Free Trial", highlighted: false, link: "/signup" },
    { name: "Pro", price: "Custom", period: "pricing", description: "Tailored to your business size", features: ["All features included", "Unlimited AI calls", "Smart scheduling", "Customer management", "Worker management", "Financial tracking & invoicing", "Priority support"], cta: "Contact Us for Pricing", highlighted: true, link: "mailto:contact@bookedforyou.ie?subject=Pro Plan Pricing Enquiry" },
  ];

  const BENTO_TINTS = [
    'bento-tint-blue',    // AI Receptionist
    'bento-tint-green',   // Smart Scheduling
    'bento-tint-purple',  // Customer Management
    'bento-tint-pink',    // Worker Management
    'bento-tint-orange',  // Materials & Invoicing
    'bento-tint-violet',  // Financial Tracking
  ];

  const bentoMiniDemos = [
    <LiveTranscript />,
    <MiniCalendar />,
    <MiniContactStack />,
    <MiniWorkerSchedule />,
    <MiniMaterials />,
    <MiniChart />,
  ];

  const heroSubtitle = "Stop missing calls and losing jobs. Let our AI handle your phone calls, book appointments, and manage your customers while you focus on what you do best.";

  return (
    <div className="landing">
      <MeshGradient />

      {/* Glassmorphism Navigation */}
      <nav className={`landing-nav ${navScrolled ? 'nav-scrolled' : ''}`}>
        <div className="nav-container">
          <div className="nav-logo"><i className="fas fa-bolt"></i><span>BookedForYou</span></div>
          <button className="mobile-menu-btn" onClick={() => setIsMenuOpen(!isMenuOpen)}>
            <i className={`fas ${isMenuOpen ? 'fa-times' : 'fa-bars'}`}></i>
          </button>
          <div className={`nav-links ${isMenuOpen ? 'open' : ''}`}>
            <a href="#features">Features</a>
            <a href="#comparison">Compare</a>
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
          <h1>The Receptionist That<br/><span className="gradient-text"><WordRotator /></span></h1>
          <p className="hero-subtitle">
            <Typewriter text={heroSubtitle} speed={30} delay={600} />
          </p>
          <div className="hero-cta">
            <Link to="/signup" className="btn-hero-primary"><i className="fas fa-rocket"></i> Start Free Trial</Link>
            {showWatchDemo && <a href="#demo" className="btn-hero-secondary"><i className="fas fa-play-circle"></i> Watch Demo</a>}
          </div>
          <ParallaxLayer speed={-0.04} className="hero-stats-parallax">
            <div className="hero-stats">
              <div className="stat"><span className="stat-number"><NumberTicker end={1000} suffix="+" /></span><span className="stat-label">Calls Tested</span></div>
              <div className="stat-divider"></div>
              <div className="stat"><span className="stat-number"><NumberTicker end={0}/></span><span className="stat-label">Customers Missed</span></div>
              <div className="stat-divider"></div>
              <div className="stat"><span className="stat-number"><NumberTicker end={30} suffix="%" /></span><span className="stat-label">More Bookings</span></div>
            </div>
          </ParallaxLayer>
        </div>
        <div className="hero-visual">
          <div className="hero-video-container">
            <video ref={videoRef} className="hero-video" autoPlay muted loop playsInline controls>
              <source src={`${ASSET_BASE}/cinematic-explainer.mp4`} type="video/mp4" />
            </video>
            {isMuted && <span className="video-sound-hint" onClick={toggleMute} role="button" tabIndex={0}>🔊 Sound on</span>}
          </div>
        </div>
      </section>

      {/* Features — Bento Grid */}
      <SectionReveal id="features" className="features">
        <div className="section-container">
          <div className="section-header">
            <h2>Everything you need to <span className="gradient-text">grow your business</span></h2>
            <p>Powerful tools designed specifically for tradespeople like plumbers, electricians, roofers, and more.</p>
          </div>
          <div className="bento-grid">
            {features.map((f, i) => (
              <Tilt key={i} tiltMaxAngleX={8} tiltMaxAngleY={8} perspective={1200} scale={1.02} transitionSpeed={1500} gyroscope={false} className="bento-tilt-wrapper">
                <SpotlightCard className={`bento-card bento-${f.size} ${BENTO_TINTS[i]}`}>
                  <div className="bento-icon icon-morph"><i className={f.icon}></i></div>
                  <h3>{f.title}</h3>
                  <p>{f.description}</p>
                  <div className="bento-mini-demo">{bentoMiniDemos[i]}</div>
                </SpotlightCard>
              </Tilt>
            ))}
          </div>
        </div>
      </SectionReveal>

      {/* How It Works — Animated Connectors */}
      <SectionReveal className="how-it-works">
        <div className="section-container">
          <div className="section-header">
            <h2 style={{ textAlign: 'center' }}>Get started in <span className="gradient-text">3 simple steps</span></h2>
          </div>
          <div className="steps">
            <div className="step reveal-child" style={{ transitionDelay: '0.1s' }}><div className="step-number">1</div><h3>Sign Up</h3><p>Create your account and set up your business profile in under 5 minutes.</p></div>
            <div className="step-connector reveal-child" style={{ transitionDelay: '0.25s' }}><div className="connector-beam"></div></div>
            <div className="step reveal-child" style={{ transitionDelay: '0.35s' }}><div className="step-number">2</div><h3>Connect Your Phone</h3><p>Forward your business calls to your new AI receptionist number.</p></div>
            <div className="step-connector reveal-child" style={{ transitionDelay: '0.5s' }}><div className="connector-beam"></div></div>
            <div className="step reveal-child" style={{ transitionDelay: '0.6s' }}><div className="step-number">3</div><h3>Start Growing</h3><p>Watch your bookings increase as you never miss another call.</p></div>
          </div>
        </div>
      </SectionReveal>

      {/* Integration Flow Diagram */}
      <SectionReveal className="integration-section">
        <div className="section-container">
          <div className="section-header">
            <h2 style={{ textAlign: 'center' }}>See how it all <span className="gradient-text">connects</span></h2>
            <p style={{ textAlign: 'center' }}>From incoming call to confirmed booking — fully automated.</p>
          </div>
          <IntegrationFlow />
        </div>
      </SectionReveal>

      {/* Before vs After Comparison */}
      <SectionReveal id="comparison" className="comparison-section">
        <div className="section-container">
          <div className="section-header">
            <h2 style={{ textAlign: 'center' }}>See the <span className="gradient-text">impact</span> on your business</h2>
            <p style={{ textAlign: 'center' }}>Real results from switching to an AI receptionist.</p>
          </div>
          <BeforeAfterComparison />
        </div>
      </SectionReveal>

      {/* Phone Demo Section */}
      <SectionReveal className="phone-demo-section">
        <div className="section-container">
          <div className="phone-demo-layout">
            <div className="phone-demo-text">
              <h2>Your AI receptionist <span className="gradient-text">answers every call</span></h2>
              <p>While you're on a job, your AI handles incoming calls professionally - booking appointments, answering questions, and never putting a customer on hold.</p>
              <button className="demo-call-btn" onClick={toggleDemoCall}>
                <i className={`fas ${isCallPlaying ? 'fa-pause' : 'fa-play'}`}></i>
                {isCallPlaying ? 'Pause Demo Call' : 'Listen to a Demo Call'}
              </button>
            </div>
            <div className="phone-demo-visual">
              <Tilt tiltMaxAngleX={isMobile ? 8 : 15} tiltMaxAngleY={isMobile ? 8 : 15} perspective={1000} scale={1.02} transitionSpeed={2000} gyroscope={false} className="phone-tilt-wrapper">
                <PhoneWithReels isCallPlaying={isCallPlaying} toggleDemoCall={toggleDemoCall} isMobile={isMobile} />
              </Tilt>
            </div>
          </div>
        </div>
      </SectionReveal>

      {showReviews && (
        <section id="testimonials" className="testimonials">
          <div className="section-container"><div className="section-header"><h2>Loved by <span className="gradient-text">tradespeople</span> across Ireland</h2></div></div>
          <div className="testimonials-marquee">
            <Marquee direction="left" speed={40}>{firstRow.map((r, i) => <ReviewCard key={i} {...r} />)}</Marquee>
            <Marquee direction="right" speed={40}>{secondRow.map((r, i) => <ReviewCard key={i} {...r} />)}</Marquee>
            <div className="marquee-fade marquee-fade-left"></div><div className="marquee-fade marquee-fade-right"></div>
          </div>
        </section>
      )}

      {showPricing && (
        <SectionReveal id="pricing" className="pricing">
          <div className="section-container">
            <div className="section-header">
              <h2 style={{ textAlign: 'center' }}>Simple, <span className="gradient-text">flexible pricing</span></h2>
              <p style={{ textAlign: 'center' }}>Start free. Scale as you grow.</p>
            </div>
            <div className="pricing-grid">
              {pricingPlans.map((plan, i) => (
                <SpotlightCard key={i} className={`pricing-card ${plan.highlighted ? 'highlighted' : ''} reveal-child`} style={{ transitionDelay: `${i * 0.15}s` }}>
                  {plan.highlighted && <div className="popular-badge">Most Popular</div>}
                  <h3>{plan.name}</h3>
                  <div className="price"><span className="amount">{plan.price}</span><span className="period">{plan.period}</span></div>
                  <p className="plan-description">{plan.description}</p>
                  <ul className="plan-features">{plan.features.map((f, j) => <li key={j}><i className="fas fa-check"></i>{f}</li>)}</ul>
                  {plan.link?.startsWith('mailto:') ? (
                    <a href={plan.link} className={`plan-btn ${plan.highlighted ? 'primary' : 'secondary'}`}>{plan.cta}</a>
                  ) : (
                    <Link to={plan.link || '/signup'} className={`plan-btn ${plan.highlighted ? 'primary' : 'secondary'}`}>{plan.cta}</Link>
                  )}
                </SpotlightCard>
              ))}
            </div>
          </div>
        </SectionReveal>
      )}

      {/* Aurora CTA Section */}
      <SectionReveal className="cta-section">
        <div className="cta-container aurora-bg">
          <div className="aurora-layer"></div>
          <div className="aurora-layer aurora-layer-2"></div>
          <div className="cta-content">
            <h2>Ready to never miss a call again?</h2>
            <p>Join hundreds of tradespeople who are growing their business with BookedForYou.</p>
            <Link to="/signup" className="btn-cta">Get Started Free <i className="fas fa-arrow-right"></i></Link>
          </div>
        </div>
      </SectionReveal>

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
              <div className="footer-column"><h4>Legal</h4><Link to="/privacy" onClick={() => window.scrollTo(0, 0)}>Privacy Policy</Link><Link to="/terms" onClick={() => window.scrollTo(0, 0)}>Terms of Service</Link><Link to="/privacy" onClick={() => window.scrollTo(0, 0)}>Cookie Policy</Link></div>
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
