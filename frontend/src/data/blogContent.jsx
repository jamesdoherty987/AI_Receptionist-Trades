import React from 'react';

/* ─── Reusable chart / illustration components ─── */

function BarChart({ data, title, color = '#0ea5e9', unit = '' }) {
  const max = Math.max(...data.map(d => d.value));
  return (
    <div className="blog-chart">
      {title && <p className="blog-chart-title">{title}</p>}
      <svg viewBox="0 0 500 220" className="blog-svg" role="img" aria-label={title || 'Bar chart'}>
        {data.map((d, i) => {
          const barW = 500 / data.length - 16;
          const x = i * (500 / data.length) + 8;
          const h = (d.value / max) * 150;
          return (
            <g key={i}>
              <rect x={x} y={170 - h} width={barW} height={h} rx={6} fill={color} opacity={0.85 - i * 0.05} />
              <text x={x + barW / 2} y={190} textAnchor="middle" fontSize="11" fill="#64748b" fontFamily="Outfit, sans-serif">{d.label}</text>
              <text x={x + barW / 2} y={165 - h} textAnchor="middle" fontSize="12" fill="#0f172a" fontWeight="600" fontFamily="Outfit, sans-serif">{d.value}{unit}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function PieChart({ slices, title }) {
  let cumulative = 0;
  const total = slices.reduce((s, sl) => s + sl.value, 0);
  return (
    <div className="blog-chart">
      {title && <p className="blog-chart-title">{title}</p>}
      <svg viewBox="0 0 300 220" className="blog-svg" role="img" aria-label={title || 'Pie chart'}>
        <g transform="translate(100,110)">
          {slices.map((sl, i) => {
            const pct = sl.value / total;
            const startAngle = cumulative * 2 * Math.PI;
            cumulative += pct;
            const endAngle = cumulative * 2 * Math.PI;
            const r = 80;
            const x1 = Math.cos(startAngle) * r, y1 = Math.sin(startAngle) * r;
            const x2 = Math.cos(endAngle) * r, y2 = Math.sin(endAngle) * r;
            const large = pct > 0.5 ? 1 : 0;
            return <path key={i} d={`M0,0 L${x1},${y1} A${r},${r} 0 ${large},1 ${x2},${y2} Z`} fill={sl.color} opacity={0.85} />;
          })}
        </g>
        <g transform="translate(210, 30)">
          {slices.map((sl, i) => (
            <g key={i} transform={`translate(0, ${i * 24})`}>
              <rect width="14" height="14" rx="3" fill={sl.color} />
              <text x="20" y="12" fontSize="12" fill="#475569" fontFamily="Outfit, sans-serif">{sl.label} ({sl.value}%)</text>
            </g>
          ))}
        </g>
      </svg>
    </div>
  );
}

function ComparisonTable({ rows, headers }) {
  return (
    <div className="blog-table-wrap">
      <table className="blog-table">
        <thead>
          <tr>{headers.map((h, i) => <th key={i}>{h}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>{row.map((cell, j) => <td key={j}>{cell}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function StatCallout({ number, label, color = '#0ea5e9' }) {
  return (
    <div className="blog-stat-callout" style={{ borderLeftColor: color }}>
      <span className="blog-stat-number" style={{ color }}>{number}</span>
      <span className="blog-stat-label">{label}</span>
    </div>
  );
}

function InfoBox({ icon, title, children }) {
  return (
    <div className="blog-info-box">
      <div className="blog-info-header"><i className={icon}></i> {title}</div>
      <div className="blog-info-body">{children}</div>
    </div>
  );
}

function CTA() {
  return (
    <div className="blog-cta-box">
      <h3>Ready to stop missing calls?</h3>
      <p>Try BookedForYou free for 14 days. No credit card required.</p>
      <a href="/signup" className="blog-cta-btn">
        <i className="fas fa-rocket"></i> Get Started Free
      </a>
    </div>
  );
}

/* ─── Article 1: Missed Calls ─── */
function MissedCallsArticle() {
  return (
    <>
      <p>If you're a tradesperson in Ireland, you already know the drill: you're elbow-deep in a job, your phone rings, and by the time you can answer it, the customer has already called someone else. It happens every single day across the country.</p>

      <p>But have you ever sat down and worked out what those missed calls are actually costing you?</p>

      <StatCallout number="40%" label="of calls to trade businesses go unanswered during working hours" />

      <h2>The Numbers Don't Lie</h2>
      <p>Let's do some quick maths. Say you're a plumber charging an average of €200 per job. If you miss just 3 calls a week — and even one of those would have been a booking — that's roughly €800 a month walking out the door. Over a year? Nearly €10,000 in lost revenue.</p>

      <BarChart
        title="Estimated Annual Revenue Lost to Missed Calls"
        data={[
          { label: '1 missed/wk', value: 4800 },
          { label: '2 missed/wk', value: 9600 },
          { label: '3 missed/wk', value: 14400 },
          { label: '5 missed/wk', value: 24000 },
        ]}
        color="#ef4444"
        unit="€"
      />

      <p>And that's being conservative. For electricians and roofers handling bigger jobs, those numbers climb fast.</p>

      <h2>Why Tradespeople Miss So Many Calls</h2>
      <p>It's not laziness — it's the nature of the work. You can't answer the phone when you're:</p>
      <ul>
        <li>Up on a roof in the rain</li>
        <li>Working with live electrics</li>
        <li>Under a sink with both hands full</li>
        <li>Driving between jobs</li>
        <li>On another call already</li>
      </ul>

      <PieChart
        title="When Tradespeople Miss Calls"
        slices={[
          { label: 'On a job', value: 45, color: '#ef4444' },
          { label: 'Driving', value: 20, color: '#f97316' },
          { label: 'On another call', value: 18, color: '#eab308' },
          { label: 'After hours', value: 12, color: '#8b5cf6' },
          { label: 'Other', value: 5, color: '#94a3b8' },
        ]}
      />

      <h2>The Customer's Perspective</h2>
      <p>Here's the thing most tradespeople don't realise: when a customer has a burst pipe or a dodgy fuse box, they're not going to leave a voicemail and wait. They're going to call the next person on Google until someone picks up.</p>

      <InfoBox icon="fas fa-lightbulb" title="Did You Know?">
        <p>85% of customers who can't reach a business on the first call will not call back. They'll simply move on to a competitor.</p>
      </InfoBox>

      <h2>The Fix Doesn't Have to Be Complicated</h2>
      <p>You don't need to hire a full-time receptionist or chain yourself to your phone. An AI receptionist can answer every call professionally, take the customer's details, check your calendar, and book the appointment — all while you're focused on the job in front of you.</p>

      <p>The calls still come in. The difference is, now someone's always there to answer them.</p>

      <CTA />
    </>
  );
}

/* ─── Article 2: AI vs Hiring ─── */
function AIvsHiringArticle() {
  return (
    <>
      <p>At some point, every growing trade business faces the same question: should I hire someone to answer the phones? It's a fair question — but the answer in 2025 might surprise you.</p>

      <h2>What Does a Receptionist Actually Cost?</h2>
      <p>In Ireland, a full-time receptionist will set you back between €28,000 and €35,000 a year in salary alone. But that's just the start.</p>

      <ComparisonTable
        headers={['Expense', 'Human Receptionist', 'AI Receptionist']}
        rows={[
          ['Annual salary / cost', '€28,000 – €35,000', '€1,200 – €3,000'],
          ['Employer PRSI (11.05%)', '€3,100 – €3,900', '€0'],
          ['Holiday cover', '€2,000 – €3,000', '€0'],
          ['Sick days', 'Unpredictable', 'Never sick'],
          ['Training time', '2 – 4 weeks', 'Instant'],
          ['Working hours', '9am – 5pm', '24/7/365'],
          ['Handles multiple calls', 'One at a time', 'Unlimited'],
        ]}
      />

      <StatCallout number="€35,000+" label="total annual cost of a human receptionist including PRSI and overheads" color="#ef4444" />

      <h2>What You Get With Each Option</h2>
      <p>A human receptionist brings warmth and personal touch — no question. But they also bring limitations: they work set hours, take holidays, call in sick, and can only handle one call at a time.</p>

      <p>An AI receptionist doesn't replace the human element entirely. What it does is ensure that every single call gets answered, every time, regardless of when it comes in. At 2am on a Sunday when someone's boiler breaks? Answered. Bank holiday Monday? Answered. Three calls at the same time? All answered.</p>

      <BarChart
        title="Calls Answered Per Day (Busy Period)"
        data={[
          { label: 'You alone', value: 8 },
          { label: 'With voicemail', value: 12 },
          { label: 'Human receptionist', value: 20 },
          { label: 'AI receptionist', value: 40 },
        ]}
        color="#10b981"
      />

      <h2>The Hybrid Approach</h2>
      <p>Some trade businesses use an AI receptionist as the first line of defence and only bring in human help when they've grown to 10+ employees. The AI handles the volume; you handle the relationships.</p>

      <InfoBox icon="fas fa-calculator" title="Quick Maths">
        <p>If an AI receptionist costs €150/month and captures just 2 extra jobs per month at €200 each, it's already paying for itself 2.5x over. Everything beyond that is pure profit.</p>
      </InfoBox>

      <CTA />
    </>
  );
}

/* ─── Article 3: Plumber Bookings ─── */
function PlumberBookingsArticle() {
  return (
    <>
      <p>Competition for plumbing jobs in Ireland is fierce. Whether you're in Dublin, Cork, Galway, or a rural town, the plumber who answers first usually wins the job. Here are 7 practical ways to make sure that's you.</p>

      <h2>1. Answer Every Call — No Exceptions</h2>
      <p>This is the single biggest thing you can do. A customer with a leaking pipe isn't going to wait for a callback. They'll ring the next plumber on the list within 30 seconds.</p>

      <StatCallout number="78%" label="of customers hire the first tradesperson who answers their call" color="#0ea5e9" />

      <p>If you can't answer personally, use a call answering service or AI receptionist to make sure no call goes to voicemail.</p>

      <h2>2. Get Your Google Business Profile Right</h2>
      <p>Most people find plumbers by Googling "plumber near me." If your Google Business Profile isn't set up properly, you're invisible. Make sure you have:</p>
      <ul>
        <li>Accurate business hours</li>
        <li>Your service area clearly defined</li>
        <li>At least 10 photos of your work</li>
        <li>A proper business description with keywords</li>
        <li>Your phone number prominently displayed</li>
      </ul>

      <h2>3. Ask Every Happy Customer for a Review</h2>
      <p>Reviews are the currency of trust online. After every job, send a quick text: "Thanks for choosing us! If you were happy with the work, a Google review would really help us out." Most people are happy to do it — they just need the nudge.</p>

      <BarChart
        title="Impact of Google Reviews on Booking Rate"
        data={[
          { label: '0-5 reviews', value: 12 },
          { label: '5-15 reviews', value: 28 },
          { label: '15-30 reviews', value: 45 },
          { label: '30+ reviews', value: 67 },
        ]}
        color="#0ea5e9"
        unit="%"
      />

      <h2>4. Offer Online Booking</h2>
      <p>Not everyone wants to make a phone call. Some customers — especially younger ones — prefer to book online. Having an automated booking system that checks your availability and confirms appointments instantly gives you an edge over plumbers who still rely on pen and paper.</p>

      <h2>5. Send Appointment Reminders</h2>
      <p>No-shows cost you time and money. A simple SMS reminder the day before an appointment reduces no-shows dramatically. It also makes you look professional and organised.</p>

      <InfoBox icon="fas fa-chart-line" title="The Reminder Effect">
        <p>Businesses that send day-before reminders see up to 35% fewer no-shows. For a plumber doing 5 jobs a day, that could save 1-2 wasted trips per week.</p>
      </InfoBox>

      <h2>6. Specialise and Shout About It</h2>
      <p>If you're great at boiler installations, say so everywhere — your website, your Google profile, your van. Specialists get more targeted enquiries and can charge more than generalists.</p>

      <h2>7. Follow Up on Quotes</h2>
      <p>Sent a quote and heard nothing back? Follow up after 2-3 days. A quick "Hi, just checking if you had any questions about the quote" can convert a maybe into a yes. Most tradespeople never follow up, so this alone sets you apart.</p>

      <CTA />
    </>
  );
}

/* ─── Article 4: Scheduling Nightmares ─── */
function SchedulingArticle() {
  return (
    <>
      <p>You've promised Mrs. Murphy you'll be there at 10am, but you've also got Mr. Kelly booked for 10am across town. Sound familiar? Double bookings are the bane of every tradesperson's existence — and they're almost always preventable.</p>

      <h2>Why Double Bookings Happen</h2>
      <p>It usually comes down to one of these:</p>

      <PieChart
        title="Root Causes of Double Bookings"
        slices={[
          { label: 'Forgot to update calendar', value: 35, color: '#ef4444' },
          { label: 'Verbal booking, no record', value: 25, color: '#f97316' },
          { label: 'Multiple people booking', value: 20, color: '#eab308' },
          { label: 'Underestimated job time', value: 15, color: '#8b5cf6' },
          { label: 'Other', value: 5, color: '#94a3b8' },
        ]}
      />

      <p>The common thread? No single source of truth. When your schedule lives in your head, on scraps of paper, in text messages, and maybe partly in a calendar app, things fall through the cracks.</p>

      <h2>The Real Cost of a Double Booking</h2>
      <p>It's not just the inconvenience. When you double-book:</p>
      <ul>
        <li>One customer gets let down and may never call you again</li>
        <li>You look unprofessional</li>
        <li>You waste time rearranging and apologising</li>
        <li>You might lose a Google review over it</li>
        <li>Your stress levels go through the roof</li>
      </ul>

      <StatCallout number="1 in 4" label="tradespeople report double-booking at least once a month" color="#f97316" />

      <h2>The Simple Fix: One Calendar, One System</h2>
      <p>The solution isn't complicated. You need one place where all bookings live — and everyone who books (you, your partner, your receptionist, your AI) needs to check that same place before confirming anything.</p>

      <ComparisonTable
        headers={['Method', 'Double-Booking Risk', 'Effort']}
        rows={[
          ['Memory / mental notes', 'Very High', 'None (that\'s the problem)'],
          ['Paper diary', 'High', 'Low'],
          ['Phone calendar (personal)', 'Medium', 'Low'],
          ['Shared Google Calendar', 'Low', 'Medium'],
          ['Automated booking system', 'Very Low', 'Set up once'],
        ]}
      />

      <h2>What Automated Scheduling Looks Like</h2>
      <p>With an automated system, when a customer calls to book, the system checks your real-time availability before confirming. If Tuesday at 2pm is taken, it offers the next available slot. No human error, no overlap, no angry customers.</p>

      <p>It also handles the things you forget: sending confirmation texts, day-before reminders, and updating your calendar instantly when something changes.</p>

      <InfoBox icon="fas fa-shield-alt" title="Prevention Over Cure">
        <p>The best scheduling system isn't the one that helps you manage double bookings — it's the one that makes them impossible in the first place.</p>
      </InfoBox>

      <CTA />
    </>
  );
}

/* ─── Article 5: Google Calendar Sync ─── */
function CalendarSyncArticle() {
  return (
    <>
      <p>You probably already use Google Calendar for personal stuff — birthdays, dentist appointments, the match on Saturday. But if you're not using it for your business bookings, you're making life harder than it needs to be.</p>

      <h2>The Problem With Separate Systems</h2>
      <p>Most tradespeople keep their personal calendar on their phone and their work bookings... somewhere else. Maybe a notebook. Maybe a WhatsApp thread. Maybe just in their head. The result? You accidentally book a job during your kid's school play, or you forget about a personal appointment and double-book a customer.</p>

      <BarChart
        title="Time Spent on Scheduling Per Week"
        data={[
          { label: 'Manual (paper)', value: 4.5 },
          { label: 'Phone calendar', value: 3.0 },
          { label: 'Google Cal (manual)', value: 1.5 },
          { label: 'Auto-synced system', value: 0.3 },
        ]}
        color="#8b5cf6"
        unit=" hrs"
      />

      <h2>Why Google Calendar Specifically?</h2>
      <p>It's free, it's on every phone, and it syncs everywhere. But the real power comes when your booking system talks to it directly:</p>
      <ul>
        <li>A customer books through your AI receptionist → it appears in your Google Calendar instantly</li>
        <li>You block out time for a personal errand → your booking system knows you're unavailable</li>
        <li>A job gets cancelled → your calendar updates and that slot opens up for new bookings</li>
        <li>Your employees each have their own calendar → no scheduling conflicts across the team</li>
      </ul>

      <InfoBox icon="fas fa-sync-alt" title="Bidirectional Sync">
        <p>The key word is "bidirectional." Changes in Google Calendar reflect in your booking system, and vice versa. One change, everywhere updated. No manual copying.</p>
      </InfoBox>

      <h2>Real-World Example</h2>
      <p>Say you're an electrician with two employees. On Monday morning, a customer calls at 7:30am wanting an urgent job. Your AI receptionist checks both employees' Google Calendars, finds that Dave is free from 9-11am, and books the job. Dave gets a notification on his phone. The customer gets a confirmation text. You didn't even have to wake up.</p>

      <StatCallout number="2.5 hrs" label="saved per week by tradespeople who use automated calendar sync" color="#8b5cf6" />

      <h2>Getting Started</h2>
      <p>If you're already using Google Calendar, you're halfway there. The next step is connecting it to a booking system that can read and write to it automatically. Once that's set up, you'll wonder how you ever managed without it.</p>

      <CTA />
    </>
  );
}

/* ─── Article 6: Customer Experience ─── */
function CustomerExperienceArticle() {
  return (
    <>
      <p>Think about the last time you called a business and nobody answered. Or you got a grumpy "yeah?" instead of a proper greeting. How did it make you feel about that business? Your customers feel the same way when they call you.</p>

      <h2>The 10-Second Window</h2>
      <p>Research consistently shows that customers form their opinion of a business within the first 10 seconds of a phone call. That's before you've even explained your services or given a quote. The greeting alone sets the tone.</p>

      <BarChart
        title="Customer Trust Level Based on First Phone Interaction"
        data={[
          { label: 'No answer', value: 8 },
          { label: 'Voicemail', value: 22 },
          { label: 'Rushed answer', value: 45 },
          { label: 'Professional greeting', value: 89 },
        ]}
        color="#10b981"
        unit="%"
      />

      <h2>What Customers Actually Want</h2>
      <p>It's simpler than you think. When a customer calls a tradesperson, they want:</p>
      <ol>
        <li>Someone to actually pick up</li>
        <li>A friendly, professional greeting</li>
        <li>To feel like their problem matters</li>
        <li>A clear next step (booking, quote, callback time)</li>
        <li>A confirmation they can trust (text or email)</li>
      </ol>

      <p>That's it. They're not expecting a five-star hotel concierge. They just want to feel like they've called someone reliable.</p>

      <StatCallout number="85%" label="of customers say phone experience influences whether they hire a tradesperson" color="#10b981" />

      <h2>The Voicemail Trap</h2>
      <p>Many tradespeople think voicemail is a safety net. It's not. It's a trapdoor.</p>

      <PieChart
        title="What Customers Do When They Reach Voicemail"
        slices={[
          { label: 'Call a competitor', value: 55, color: '#ef4444' },
          { label: 'Leave a message', value: 25, color: '#10b981' },
          { label: 'Try again later', value: 15, color: '#eab308' },
          { label: 'Send a text', value: 5, color: '#0ea5e9' },
        ]}
      />

      <p>More than half of callers who hit voicemail will immediately call someone else. That's not a safety net — that's a customer delivery service for your competitors.</p>

      <h2>Consistency Is Everything</h2>
      <p>The best trade businesses don't just answer calls well sometimes. They answer every call the same way: professionally, promptly, and with a clear next step. Whether it's 9am on a Monday or 8pm on a Saturday, the experience is the same.</p>

      <InfoBox icon="fas fa-star" title="The Review Connection">
        <p>Customers who have a positive first phone interaction are 3x more likely to leave a 5-star Google review after the job is done. Your phone answering directly impacts your online reputation.</p>
      </InfoBox>

      <p>That consistency is hard to maintain when you're one person doing everything. But it's exactly what an AI receptionist delivers — the same professional greeting, the same helpful booking process, every single time.</p>

      <CTA />
    </>
  );
}

/* ─── Export map ─── */
const blogContentMap = {
  'missed-calls-costing-tradespeople-thousands': MissedCallsArticle,
  'ai-receptionist-vs-hiring-secretary': AIvsHiringArticle,
  'how-plumbers-get-more-bookings': PlumberBookingsArticle,
  'scheduling-nightmares-how-to-fix-them': SchedulingArticle,
  'google-calendar-sync-for-tradespeople': CalendarSyncArticle,
  'customer-experience-trade-business': CustomerExperienceArticle,
};

export default blogContentMap;
