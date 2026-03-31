import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  Sequence,
  Audio,
  staticFile,
} from "remotion";
import React from "react";

// ─── Colors (matching the real app's dark theme) ───
const C = {
  bg: "#0f1117",
  bgCard: "#1a1d27",
  bgSidebar: "#141720",
  accent: "#6c63ff",
  accentLight: "#8b83ff",
  accentGlow: "rgba(108, 99, 255, 0.35)",
  green: "#00d4aa",
  greenLight: "#34ebc6",
  greenGlow: "rgba(0, 212, 170, 0.3)",
  red: "#ff4757",
  orange: "#ff9f43",
  blue: "#3498ff",
  pink: "#ff6b9d",
  gold: "#ffd60a",
  white: "#ffffff",
  gray: "#8892a4",
  lightGray: "#c5cdd9",
  cardBorder: "rgba(255,255,255,0.08)",
  card: "rgba(255,255,255,0.04)",
};

const FONT = "'Inter', 'SF Pro Display', -apple-system, sans-serif";

// ─── Shared components ───
const StarField: React.FC = () => {
  const frame = useCurrentFrame();
  const stars = Array.from({ length: 60 }, (_, i) => {
    const seed = i * 137.508;
    return {
      x: (seed * 7.3) % 100,
      y: ((seed * 3.1 + frame * (0.2 + (i % 3) * 0.1)) % 120) - 10,
      size: 1 + (i % 3),
      opacity: 0.05 + (i % 5) * 0.04,
    };
  });
  return (
    <AbsoluteFill>
      <div style={{ width: "100%", height: "100%", background: `radial-gradient(ellipse at 50% 30%, #0a0025, ${C.bg} 70%)` }} />
      {stars.map((s, i) => (
        <div key={i} style={{
          position: "absolute", left: `${s.x}%`, top: `${s.y}%`,
          width: s.size, height: s.size, borderRadius: "50%",
          backgroundColor: i % 2 === 0 ? C.accentLight : C.green,
          opacity: s.opacity,
        }} />
      ))}
    </AbsoluteFill>
  );
};

const OrbBlobs: React.FC<{ colors?: string[] }> = ({ colors = [C.accentGlow, C.greenGlow] }) => {
  const frame = useCurrentFrame();
  return (
    <>
      {colors.map((color, i) => {
        const angle = frame * 0.006 + (i * Math.PI * 2) / colors.length;
        const x = 50 + Math.sin(angle) * 20;
        const y = 50 + Math.cos(angle * 0.7) * 15;
        return (
          <div key={i} style={{
            position: "absolute", width: 450, height: 450, borderRadius: "50%",
            background: `radial-gradient(circle, ${color}, transparent 65%)`,
            left: `${x}%`, top: `${y}%`, transform: "translate(-50%, -50%)",
            filter: "blur(60px)", pointerEvents: "none",
          }} />
        );
      })}
    </>
  );
};

const Pop: React.FC<{
  children: React.ReactNode;
  delay?: number;
  direction?: "up" | "down" | "left" | "right" | "scale" | "none";
  style?: React.CSSProperties;
}> = ({ children, delay = 0, direction = "up", style }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame: frame - delay, fps, config: { damping: 12, mass: 0.5, stiffness: 150 } });
  const opacity = interpolate(frame - delay, [0, 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const map: Record<string, string> = {
    up: `translateY(${interpolate(p, [0, 1], [50, 0])}px)`,
    down: `translateY(${interpolate(p, [0, 1], [-50, 0])}px)`,
    left: `translateX(${interpolate(p, [0, 1], [60, 0])}px)`,
    right: `translateX(${interpolate(p, [0, 1], [-60, 0])}px)`,
    scale: `scale(${interpolate(p, [0, 1], [0.4, 1])})`,
    none: "",
  };
  return <div style={{ opacity, transform: map[direction], ...style }}>{children}</div>;
};

const Grad: React.FC<{ children: React.ReactNode; from?: string; to?: string; style?: React.CSSProperties }> = ({
  children, from = C.accent, to = C.green, style,
}) => (
  <span style={{ background: `linear-gradient(135deg, ${from}, ${to})`, WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", ...style }}>{children}</span>
);

const Transition: React.FC<{
  children: React.ReactNode;
  durationInFrames: number;
  fadeIn?: number;
  fadeOut?: number;
}> = ({ children, durationInFrames, fadeIn = 8, fadeOut = 8 }) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(
    frame,
    [0, fadeIn, durationInFrames - fadeOut, durationInFrames],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  return <AbsoluteFill style={{ opacity }}>{children}</AbsoluteFill>;
};


// ═══════════════════════════════════════════════════════════
// SCENE 1: INTRO — "See Your Business Dashboard"
// ═══════════════════════════════════════════════════════════
const DemoIntroScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const logoScale = spring({ frame: frame - 5, fps, config: { damping: 8, mass: 0.3, stiffness: 200 } });
  // Browser window appearing
  const browserScale = spring({ frame: frame - 30, fps, config: { damping: 14, mass: 0.6 } });
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <OrbBlobs colors={[C.accentGlow, C.greenGlow, "rgba(58, 134, 255, 0.2)"]} />
      <div style={{ textAlign: "center", zIndex: 2 }}>
        <div style={{ transform: `scale(${logoScale})`, marginBottom: 20 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 16 }}>
            <div style={{
              width: 64, height: 64, borderRadius: 16,
              background: `linear-gradient(135deg, ${C.accent}, ${C.green})`,
              display: "flex", alignItems: "center", justifyContent: "center", fontSize: 34,
              boxShadow: `0 0 50px ${C.accentGlow}, 0 0 100px ${C.greenGlow}`,
            }}>⚡</div>
            <span style={{ fontSize: 52, fontWeight: 900, color: C.white, letterSpacing: -2 }}>BookedForYou</span>
          </div>
        </div>
        <Pop delay={15} direction="up">
          <h2 style={{ fontSize: 54, fontWeight: 900, color: C.white, margin: "0 0 12px", lineHeight: 1.15 }}>
            Your <Grad>Real Dashboard</Grad>
          </h2>
        </Pop>
        <Pop delay={22} direction="up">
          <p style={{ fontSize: 24, color: C.gray, margin: "0 0 30px" }}>
            Every feature. One screen. Let's take a tour.
          </p>
        </Pop>
        {/* Mini browser chrome preview */}
        <Pop delay={30} direction="scale">
          <div style={{
            transform: `scale(${browserScale})`,
            width: 700, height: 60, borderRadius: "16px 16px 0 0",
            background: C.bgCard, border: `1px solid ${C.cardBorder}`,
            display: "flex", alignItems: "center", padding: "0 20px", gap: 8,
            margin: "0 auto",
            boxShadow: `0 20px 60px rgba(0,0,0,0.5)`,
          }}>
            <div style={{ display: "flex", gap: 6 }}>
              <div style={{ width: 12, height: 12, borderRadius: "50%", background: "#ff5f57" }} />
              <div style={{ width: 12, height: 12, borderRadius: "50%", background: "#febc2e" }} />
              <div style={{ width: 12, height: 12, borderRadius: "50%", background: "#28c840" }} />
            </div>
            <div style={{
              flex: 1, height: 30, borderRadius: 8, background: "rgba(255,255,255,0.06)",
              display: "flex", alignItems: "center", padding: "0 14px",
              fontSize: 14, color: C.gray,
            }}>
              🔒 app.bookedforyou.ie/dashboard
            </div>
          </div>
        </Pop>
      </div>
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════════════
// SCENE 2: JOBS TAB — Animated job cards with status
// ═══════════════════════════════════════════════════════════
const JobsTabScene: React.FC = () => {
  const frame = useCurrentFrame();
  const jobs = [
    { client: "John Murphy", service: "Pipe Repair", time: "10:00 AM", worker: "Mike O'Brien", status: "confirmed", color: C.blue },
    { client: "Sarah O'Connor", service: "Boiler Install", time: "1:00 PM", worker: "Dave Walsh", status: "in_progress", color: C.orange },
    { client: "Emma Wilson", service: "Radiator Flush", time: "3:30 PM", worker: "Mike O'Brien", status: "pending", color: C.accent },
    { client: "Tom Kelly", service: "Emergency Leak", time: "5:00 PM", worker: "Dave Walsh", status: "completed", color: C.green },
    { client: "Lisa Brady", service: "Kitchen Plumbing", time: "Tomorrow 9AM", worker: "Mike O'Brien", status: "confirmed", color: C.blue },
  ];
  const statusLabels: Record<string, { label: string; bg: string; color: string }> = {
    confirmed: { label: "Confirmed", bg: `${C.blue}20`, color: C.blue },
    in_progress: { label: "In Progress", bg: `${C.orange}20`, color: C.orange },
    pending: { label: "Pending", bg: `${C.accent}20`, color: C.accent },
    completed: { label: "Completed", bg: `${C.green}20`, color: C.green },
  };
  // Tab indicator animation
  const tabSlide = interpolate(frame, [0, 15], [0, 1], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <OrbBlobs colors={[C.accentGlow, "rgba(52, 152, 219, 0.2)"]} />
      <div style={{ zIndex: 1, width: "100%", padding: "0 80px" }}>
        <Pop delay={0} direction="up" style={{ textAlign: "center", marginBottom: 30 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 12 }}>
            <span style={{ fontSize: 32 }}>📋</span>
            <h2 style={{ fontSize: 46, fontWeight: 900, color: C.white, margin: 0 }}>
              <Grad from={C.blue} to={C.accent}>Jobs Dashboard</Grad>
            </h2>
          </div>
        </Pop>
        {/* Browser frame */}
        <Pop delay={5} direction="scale">
          <div style={{
            background: C.bgCard, borderRadius: 20, overflow: "hidden",
            border: `1px solid ${C.cardBorder}`,
            boxShadow: `0 30px 80px rgba(0,0,0,0.5), 0 0 40px ${C.accentGlow}`,
            maxWidth: 1000, margin: "0 auto",
          }}>
            {/* Browser chrome */}
            <div style={{ display: "flex", alignItems: "center", padding: "12px 20px", borderBottom: `1px solid ${C.cardBorder}`, gap: 8 }}>
              <div style={{ display: "flex", gap: 6 }}>
                <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#ff5f57" }} />
                <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#febc2e" }} />
                <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#28c840" }} />
              </div>
              <div style={{ flex: 1, height: 26, borderRadius: 6, background: "rgba(255,255,255,0.05)", display: "flex", alignItems: "center", padding: "0 12px", fontSize: 12, color: C.gray }}>
                app.bookedforyou.ie/dashboard
              </div>
            </div>
            {/* Tab bar */}
            <div style={{ display: "flex", gap: 0, padding: "0 20px", borderBottom: `1px solid ${C.cardBorder}`, position: "relative" }}>
              {["Jobs", "Calls", "Calendar", "Workers", "Customers", "Services"].map((tab, i) => (
                <div key={i} style={{
                  padding: "14px 20px", fontSize: 14, fontWeight: i === 0 ? 700 : 500,
                  color: i === 0 ? C.accent : C.gray,
                  position: "relative",
                }}>
                  {tab}
                  {i === 0 && (
                    <div style={{
                      position: "absolute", bottom: 0, left: 0, right: 0, height: 2,
                      background: C.accent, borderRadius: 1,
                      transform: `scaleX(${tabSlide})`,
                    }} />
                  )}
                </div>
              ))}
            </div>
            {/* Job cards */}
            <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 10 }}>
              {/* Header row */}
              <div style={{ display: "grid", gridTemplateColumns: "2fr 2fr 1fr 1.5fr 1fr", padding: "8px 16px", fontSize: 12, fontWeight: 700, color: C.gray, textTransform: "uppercase", letterSpacing: 1 }}>
                <span>Client</span><span>Service</span><span>Time</span><span>Worker</span><span>Status</span>
              </div>
              {jobs.map((job, i) => {
                const delay = 12 + i * 10;
                const opacity = interpolate(frame, [delay, delay + 10], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
                const x = interpolate(frame, [delay, delay + 10], [30, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
                const s = statusLabels[job.status];
                return (
                  <div key={i} style={{
                    opacity, transform: `translateX(${x}px)`,
                    display: "grid", gridTemplateColumns: "2fr 2fr 1fr 1.5fr 1fr",
                    padding: "14px 16px", borderRadius: 12,
                    background: C.card, border: `1px solid ${C.cardBorder}`,
                    alignItems: "center",
                  }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <div style={{ width: 32, height: 32, borderRadius: "50%", background: `${job.color}20`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14, fontWeight: 800, color: job.color }}>
                        {job.client[0]}
                      </div>
                      <span style={{ fontSize: 15, fontWeight: 700, color: C.white }}>{job.client}</span>
                    </div>
                    <span style={{ fontSize: 14, color: C.lightGray }}>{job.service}</span>
                    <span style={{ fontSize: 14, color: C.gray }}>{job.time}</span>
                    <span style={{ fontSize: 14, color: C.lightGray }}>{job.worker}</span>
                    <div style={{ display: "inline-flex", padding: "4px 12px", borderRadius: 8, background: s.bg, fontSize: 12, fontWeight: 700, color: s.color }}>
                      {s.label}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </Pop>
      </div>
    </AbsoluteFill>
  );
};


// ═══════════════════════════════════════════════════════════
// SCENE 3: CALENDAR TAB — Week view with animated bookings
// ═══════════════════════════════════════════════════════════
const CalendarTabScene: React.FC = () => {
  const frame = useCurrentFrame();
  const days = ["Mon 14", "Tue 15", "Wed 16", "Thu 17", "Fri 18"];
  const hours = ["8 AM", "9 AM", "10 AM", "11 AM", "12 PM", "1 PM", "2 PM", "3 PM", "4 PM", "5 PM"];
  const bookings = [
    { day: 0, startRow: 2, span: 2, label: "Pipe Repair", sub: "John M.", color: C.blue },
    { day: 0, startRow: 6, span: 2, label: "Radiator Flush", sub: "Emma W.", color: C.green },
    { day: 1, startRow: 1, span: 3, label: "Boiler Install", sub: "Sarah O.", color: C.accent },
    { day: 1, startRow: 5, span: 2, label: "Tap Fix", sub: "Tom K.", color: C.orange },
    { day: 2, startRow: 0, span: 10, label: "Bathroom Refit Day 1", sub: "Dave R.", color: C.pink },
    { day: 3, startRow: 0, span: 10, label: "Bathroom Refit Day 2", sub: "Dave R.", color: C.pink },
    { day: 4, startRow: 1, span: 2, label: "Emergency Leak", sub: "Mike K.", color: C.red },
    { day: 4, startRow: 4, span: 3, label: "Kitchen Plumbing", sub: "Lisa B.", color: C.blue },
  ];
  // New booking animation
  const newBookingFrame = 90;
  const newOpacity = interpolate(frame, [newBookingFrame, newBookingFrame + 12], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const newScale = interpolate(frame, [newBookingFrame, newBookingFrame + 12], [1.2, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const newGlow = interpolate(Math.sin((frame - newBookingFrame) * 0.15), [-1, 1], [0.3, 0.8]);
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <OrbBlobs colors={["rgba(52, 152, 255, 0.2)", C.greenGlow]} />
      <div style={{ zIndex: 1, width: "100%", padding: "0 60px" }}>
        <Pop delay={0} direction="up" style={{ textAlign: "center", marginBottom: 24 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 12 }}>
            <span style={{ fontSize: 32 }}>📅</span>
            <h2 style={{ fontSize: 46, fontWeight: 900, color: C.white, margin: 0 }}>
              <Grad from={C.blue} to={C.green}>Smart Calendar</Grad>
            </h2>
          </div>
          <p style={{ fontSize: 20, color: C.gray, marginTop: 8 }}>Auto-syncs with Google Calendar. Multi-day jobs. Conflict prevention.</p>
        </Pop>
        <Pop delay={8} direction="scale">
          <div style={{
            background: C.bgCard, borderRadius: 20, overflow: "hidden",
            border: `1px solid ${C.cardBorder}`,
            boxShadow: `0 30px 80px rgba(0,0,0,0.5), 0 0 30px rgba(52,152,255,0.15)`,
            maxWidth: 1050, margin: "0 auto",
          }}>
            {/* Calendar header */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "16px 24px", borderBottom: `1px solid ${C.cardBorder}` }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <span style={{ fontSize: 14, color: C.gray }}>◀</span>
                <span style={{ fontSize: 18, fontWeight: 800, color: C.white }}>April 14 – 18, 2025</span>
                <span style={{ fontSize: 14, color: C.gray }}>▶</span>
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                {["Day", "Week", "Month"].map((v, i) => (
                  <div key={i} style={{
                    padding: "6px 14px", borderRadius: 8, fontSize: 13, fontWeight: 600,
                    background: i === 1 ? C.accent : "transparent",
                    color: i === 1 ? C.white : C.gray,
                  }}>{v}</div>
                ))}
              </div>
            </div>
            {/* Grid */}
            <div style={{ display: "grid", gridTemplateColumns: "60px repeat(5, 1fr)", position: "relative" }}>
              {/* Time labels */}
              <div style={{ display: "flex", flexDirection: "column" }}>
                {hours.map((h, i) => (
                  <div key={i} style={{ height: 40, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, color: C.gray, borderRight: `1px solid ${C.cardBorder}` }}>
                    {h}
                  </div>
                ))}
              </div>
              {/* Day columns */}
              {days.map((day, di) => (
                <div key={di} style={{ position: "relative", borderRight: di < 4 ? `1px solid ${C.cardBorder}` : "none" }}>
                  {/* Day header */}
                  <div style={{
                    position: "absolute", top: -32, left: 0, right: 0, textAlign: "center",
                    fontSize: 13, fontWeight: 700, color: di === 0 ? C.accent : C.lightGray,
                  }}>{day}</div>
                  {/* Hour lines */}
                  {hours.map((_, hi) => (
                    <div key={hi} style={{ height: 40, borderBottom: `1px solid ${C.cardBorder}` }} />
                  ))}
                </div>
              ))}
              {/* Bookings overlay */}
              {bookings.map((b, i) => {
                const delay = 15 + i * 8;
                const opacity = interpolate(frame, [delay, delay + 10], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
                return (
                  <div key={i} style={{
                    position: "absolute",
                    left: `calc(60px + ${b.day} * ((100% - 60px) / 5) + 3px)`,
                    top: `${b.startRow * 40 + 2}px`,
                    width: `calc((100% - 60px) / 5 - 6px)`,
                    height: `${b.span * 40 - 4}px`,
                    background: `${b.color}18`,
                    border: `1px solid ${b.color}44`,
                    borderRadius: 8, padding: "6px 10px",
                    opacity, overflow: "hidden",
                  }}>
                    <p style={{ fontSize: 12, fontWeight: 700, color: b.color, margin: 0 }}>{b.label}</p>
                    <p style={{ fontSize: 10, color: C.gray, margin: 0 }}>{b.sub}</p>
                  </div>
                );
              })}
              {/* NEW booking flying in */}
              <div style={{
                position: "absolute",
                left: `calc(60px + 4 * ((100% - 60px) / 5) + 3px)`,
                top: `${8 * 40 + 2}px`,
                width: `calc((100% - 60px) / 5 - 6px)`,
                height: `${2 * 40 - 4}px`,
                background: `${C.green}22`,
                border: `2px solid ${C.green}`,
                borderRadius: 8, padding: "6px 10px",
                opacity: newOpacity, transform: `scale(${newScale})`,
                boxShadow: `0 0 ${20 * newGlow}px ${C.greenGlow}`,
              }}>
                <p style={{ fontSize: 12, fontWeight: 800, color: C.green, margin: 0 }}>✨ NEW — Drain Clear</p>
                <p style={{ fontSize: 10, color: C.gray, margin: 0 }}>Auto-booked by AI</p>
              </div>
            </div>
            {/* Spacer for day headers */}
            <div style={{ height: 32 }} />
          </div>
        </Pop>
      </div>
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════════════
// SCENE 4: CUSTOMERS TAB — CRM with customer cards
// ═══════════════════════════════════════════════════════════
const CustomersTabScene: React.FC = () => {
  const frame = useCurrentFrame();
  const customers = [
    { name: "John Murphy", phone: "+353 86 XXX XXXX", jobs: 8, spent: "€2,340", lastJob: "Pipe Repair", avatar: "JM", color: C.blue },
    { name: "Sarah O'Connor", phone: "+353 87 XXX XXXX", jobs: 3, spent: "€1,890", lastJob: "Boiler Install", avatar: "SO", color: C.pink },
    { name: "Emma Wilson", phone: "+353 85 XXX XXXX", jobs: 12, spent: "€5,670", lastJob: "Radiator Flush", avatar: "EW", color: C.green },
    { name: "Tom Kelly", phone: "+353 89 XXX XXXX", jobs: 5, spent: "€1,200", lastJob: "Emergency Leak", avatar: "TK", color: C.orange },
    { name: "Lisa Brady", phone: "+353 86 XXX XXXX", jobs: 2, spent: "€480", lastJob: "Kitchen Plumbing", avatar: "LB", color: C.accent },
    { name: "Dave Ryan", phone: "+353 83 XXX XXXX", jobs: 15, spent: "€8,900", lastJob: "Bathroom Refit", avatar: "DR", color: C.gold },
  ];
  // Search bar typing animation
  const searchText = "John Mur";
  const typedChars = Math.min(Math.floor(interpolate(frame, [60, 90], [0, searchText.length], { extrapolateRight: "clamp" })), searchText.length);
  const showCursor = frame > 60 && Math.floor(frame / 8) % 2 === 0;
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <OrbBlobs colors={[C.accentGlow, "rgba(255, 107, 157, 0.2)"]} />
      <div style={{ zIndex: 1, width: "100%", padding: "0 80px" }}>
        <Pop delay={0} direction="up" style={{ textAlign: "center", marginBottom: 24 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 12 }}>
            <span style={{ fontSize: 32 }}>👥</span>
            <h2 style={{ fontSize: 46, fontWeight: 900, color: C.white, margin: 0 }}>
              <Grad from={C.pink} to={C.accent}>Customer CRM</Grad>
            </h2>
          </div>
          <p style={{ fontSize: 20, color: C.gray, marginTop: 8 }}>Auto-saved from every call. Full history at a glance.</p>
        </Pop>
        <Pop delay={5} direction="scale">
          <div style={{
            background: C.bgCard, borderRadius: 20, overflow: "hidden",
            border: `1px solid ${C.cardBorder}`,
            boxShadow: `0 30px 80px rgba(0,0,0,0.5)`,
            maxWidth: 1000, margin: "0 auto",
          }}>
            {/* Search bar */}
            <div style={{ padding: "16px 24px", borderBottom: `1px solid ${C.cardBorder}`, display: "flex", gap: 12, alignItems: "center" }}>
              <div style={{
                flex: 1, height: 40, borderRadius: 10, background: "rgba(255,255,255,0.05)",
                border: `1px solid ${C.cardBorder}`, display: "flex", alignItems: "center", padding: "0 14px", gap: 8,
              }}>
                <span style={{ fontSize: 14, color: C.gray }}>🔍</span>
                <span style={{ fontSize: 15, color: C.white }}>
                  {searchText.slice(0, typedChars)}
                  {showCursor && <span style={{ color: C.accent }}>|</span>}
                </span>
              </div>
              <div style={{ padding: "8px 20px", borderRadius: 10, background: C.accent, fontSize: 14, fontWeight: 700, color: C.white }}>
                + Add Client
              </div>
            </div>
            {/* Customer grid */}
            <div style={{ padding: 20, display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14 }}>
              {customers.map((c, i) => {
                const delay = 10 + i * 8;
                const opacity = interpolate(frame, [delay, delay + 10], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
                const y = interpolate(frame, [delay, delay + 10], [20, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
                // Highlight matching customer when search is active
                const isMatch = typedChars > 3 && c.name.toLowerCase().startsWith(searchText.slice(0, typedChars).toLowerCase());
                return (
                  <div key={i} style={{
                    opacity, transform: `translateY(${y}px)`,
                    background: isMatch ? `${C.accent}12` : C.card,
                    border: `1px solid ${isMatch ? `${C.accent}44` : C.cardBorder}`,
                    borderRadius: 16, padding: 18,
                    boxShadow: isMatch ? `0 0 20px ${C.accentGlow}` : "none",
                  }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14 }}>
                      <div style={{
                        width: 40, height: 40, borderRadius: "50%",
                        background: `${c.color}20`, border: `1px solid ${c.color}44`,
                        display: "flex", alignItems: "center", justifyContent: "center",
                        fontSize: 14, fontWeight: 800, color: c.color,
                      }}>{c.avatar}</div>
                      <div>
                        <p style={{ fontSize: 15, fontWeight: 700, color: C.white, margin: 0 }}>{c.name}</p>
                        <p style={{ fontSize: 12, color: C.gray, margin: 0 }}>{c.phone}</p>
                      </div>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <div style={{ textAlign: "center" }}>
                        <p style={{ fontSize: 18, fontWeight: 800, color: C.white, margin: 0 }}>{c.jobs}</p>
                        <p style={{ fontSize: 11, color: C.gray, margin: 0 }}>Jobs</p>
                      </div>
                      <div style={{ textAlign: "center" }}>
                        <p style={{ fontSize: 18, fontWeight: 800, color: C.green, margin: 0 }}>{c.spent}</p>
                        <p style={{ fontSize: 11, color: C.gray, margin: 0 }}>Revenue</p>
                      </div>
                      <div style={{ textAlign: "center" }}>
                        <p style={{ fontSize: 12, fontWeight: 600, color: C.lightGray, margin: 0 }}>{c.lastJob}</p>
                        <p style={{ fontSize: 11, color: C.gray, margin: 0 }}>Last Job</p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </Pop>
      </div>
    </AbsoluteFill>
  );
};


// ═══════════════════════════════════════════════════════════
// SCENE 5: FINANCES TAB — Revenue charts and invoicing
// ═══════════════════════════════════════════════════════════
const FinancesTabScene: React.FC = () => {
  const frame = useCurrentFrame();
  // Animated bar chart
  const barData = [
    { label: "Mon", value: 450, color: C.accent },
    { label: "Tue", value: 680, color: C.accent },
    { label: "Wed", value: 320, color: C.accent },
    { label: "Thu", value: 890, color: C.green },
    { label: "Fri", value: 560, color: C.accent },
    { label: "Sat", value: 0, color: C.accent },
    { label: "Sun", value: 0, color: C.accent },
  ];
  const maxVal = 890;
  // Revenue counter
  const totalRevenue = Math.floor(interpolate(frame, [20, 60], [0, 12450], { extrapolateRight: "clamp" }));
  const pendingInvoices = Math.floor(interpolate(frame, [30, 50], [0, 3], { extrapolateRight: "clamp" }));
  // Invoice list
  const invoices = [
    { client: "John Murphy", amount: "€280", status: "paid", date: "Apr 14" },
    { client: "Sarah O'Connor", amount: "€1,200", status: "paid", date: "Apr 13" },
    { client: "Emma Wilson", amount: "€180", status: "pending", date: "Apr 12" },
    { client: "Tom Kelly", amount: "€350", status: "overdue", date: "Apr 8" },
  ];
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <OrbBlobs colors={["rgba(255, 214, 10, 0.15)", C.greenGlow]} />
      <div style={{ zIndex: 1, width: "100%", padding: "0 60px" }}>
        <Pop delay={0} direction="up" style={{ textAlign: "center", marginBottom: 24 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 12 }}>
            <span style={{ fontSize: 32 }}>💰</span>
            <h2 style={{ fontSize: 46, fontWeight: 900, color: C.white, margin: 0 }}>
              <Grad from={C.gold} to={C.green}>Revenue & Invoicing</Grad>
            </h2>
          </div>
        </Pop>
        <div style={{ display: "flex", gap: 24, maxWidth: 1100, margin: "0 auto" }}>
          {/* Left: Chart + stats */}
          <Pop delay={5} direction="left" style={{ flex: 1 }}>
            <div style={{
              background: C.bgCard, borderRadius: 20, padding: 24,
              border: `1px solid ${C.cardBorder}`,
              boxShadow: `0 20px 60px rgba(0,0,0,0.4)`,
            }}>
              {/* Stats row */}
              <div style={{ display: "flex", gap: 16, marginBottom: 24 }}>
                {[
                  { label: "This Month", value: `€${totalRevenue.toLocaleString()}`, color: C.green, icon: "📈" },
                  { label: "Pending", value: `${pendingInvoices} invoices`, color: C.orange, icon: "⏳" },
                  { label: "Paid Rate", value: "94%", color: C.accent, icon: "✅" },
                ].map((s, i) => (
                  <div key={i} style={{
                    flex: 1, background: C.card, borderRadius: 14, padding: "16px 14px",
                    border: `1px solid ${C.cardBorder}`,
                  }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                      <span style={{ fontSize: 18 }}>{s.icon}</span>
                      <span style={{ fontSize: 12, color: C.gray, fontWeight: 600 }}>{s.label}</span>
                    </div>
                    <p style={{ fontSize: 24, fontWeight: 900, color: s.color, margin: 0 }}>{s.value}</p>
                  </div>
                ))}
              </div>
              {/* Bar chart */}
              <div style={{ display: "flex", alignItems: "flex-end", gap: 12, height: 180, padding: "0 10px" }}>
                {barData.map((b, i) => {
                  const delay = 20 + i * 6;
                  const barHeight = interpolate(frame, [delay, delay + 15], [0, (b.value / maxVal) * 160], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
                  return (
                    <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
                      <span style={{ fontSize: 11, fontWeight: 700, color: C.lightGray }}>€{b.value}</span>
                      <div style={{
                        width: "100%", height: barHeight, borderRadius: "8px 8px 4px 4px",
                        background: `linear-gradient(180deg, ${b.color}, ${b.color}66)`,
                        boxShadow: barHeight > 0 ? `0 0 12px ${b.color}30` : "none",
                      }} />
                      <span style={{ fontSize: 12, color: C.gray, fontWeight: 600 }}>{b.label}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </Pop>
          {/* Right: Invoice list */}
          <Pop delay={15} direction="right" style={{ width: 380 }}>
            <div style={{
              background: C.bgCard, borderRadius: 20, padding: 24,
              border: `1px solid ${C.cardBorder}`,
              boxShadow: `0 20px 60px rgba(0,0,0,0.4)`,
            }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 18 }}>
                <h3 style={{ fontSize: 18, fontWeight: 800, color: C.white, margin: 0 }}>Recent Invoices</h3>
                <div style={{ padding: "6px 14px", borderRadius: 8, background: C.accent, fontSize: 12, fontWeight: 700, color: C.white }}>
                  + New
                </div>
              </div>
              {invoices.map((inv, i) => {
                const delay = 25 + i * 10;
                const opacity = interpolate(frame, [delay, delay + 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
                const statusColors: Record<string, string> = { paid: C.green, pending: C.orange, overdue: C.red };
                return (
                  <div key={i} style={{
                    opacity, display: "flex", alignItems: "center", justifyContent: "space-between",
                    padding: "12px 0", borderBottom: i < invoices.length - 1 ? `1px solid ${C.cardBorder}` : "none",
                  }}>
                    <div>
                      <p style={{ fontSize: 14, fontWeight: 700, color: C.white, margin: 0 }}>{inv.client}</p>
                      <p style={{ fontSize: 12, color: C.gray, margin: 0 }}>{inv.date}</p>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <p style={{ fontSize: 16, fontWeight: 800, color: C.white, margin: 0 }}>{inv.amount}</p>
                      <span style={{
                        fontSize: 11, fontWeight: 700, color: statusColors[inv.status],
                        textTransform: "uppercase",
                      }}>{inv.status}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </Pop>
        </div>
      </div>
    </AbsoluteFill>
  );
};


// ═══════════════════════════════════════════════════════════
// SCENE 6: WORKERS TAB — Team management
// ═══════════════════════════════════════════════════════════
const WorkersTabScene: React.FC = () => {
  const frame = useCurrentFrame();
  const workers = [
    {
      name: "Mike O'Brien", role: "Lead Plumber", avatar: "MO", color: C.blue,
      schedule: [
        { day: "Mon", jobs: 2, hours: "8AM–4PM" },
        { day: "Tue", jobs: 1, hours: "9AM–1PM" },
        { day: "Wed", jobs: 0, hours: "Off" },
        { day: "Thu", jobs: 3, hours: "8AM–5PM" },
        { day: "Fri", jobs: 2, hours: "8AM–3PM" },
      ],
      services: ["Pipe Repair", "Radiator Flush", "Kitchen Plumbing", "Emergency"],
      jobsThisWeek: 8, hoursThisWeek: 32,
    },
    {
      name: "Dave Walsh", role: "Plumber", avatar: "DW", color: C.green,
      schedule: [
        { day: "Mon", jobs: 1, hours: "10AM–2PM" },
        { day: "Tue", jobs: 2, hours: "8AM–4PM" },
        { day: "Wed", jobs: 1, hours: "8AM–5PM" },
        { day: "Thu", jobs: 1, hours: "8AM–5PM" },
        { day: "Fri", jobs: 1, hours: "9AM–12PM" },
      ],
      services: ["Boiler Install", "Bathroom Refit", "Tap Fix"],
      jobsThisWeek: 6, hoursThisWeek: 28,
    },
  ];
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <OrbBlobs colors={[C.accentGlow, "rgba(0, 212, 170, 0.2)"]} />
      <div style={{ zIndex: 1, width: "100%", padding: "0 60px" }}>
        <Pop delay={0} direction="up" style={{ textAlign: "center", marginBottom: 24 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 12 }}>
            <span style={{ fontSize: 32 }}>👷</span>
            <h2 style={{ fontSize: 46, fontWeight: 900, color: C.white, margin: 0 }}>
              <Grad from={C.accent} to={C.blue}>Worker Management</Grad>
            </h2>
          </div>
          <p style={{ fontSize: 20, color: C.gray, marginTop: 8 }}>Assign jobs, track hours, prevent scheduling conflicts.</p>
        </Pop>
        <div style={{ display: "flex", gap: 24, maxWidth: 1100, margin: "0 auto" }}>
          {workers.map((w, wi) => (
            <Pop key={wi} delay={8 + wi * 15} direction={wi === 0 ? "left" : "right"} style={{ flex: 1 }}>
              <div style={{
                background: C.bgCard, borderRadius: 20, padding: 24,
                border: `1px solid ${C.cardBorder}`,
                boxShadow: `0 20px 60px rgba(0,0,0,0.4)`,
              }}>
                {/* Worker header */}
                <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 20 }}>
                  <div style={{
                    width: 52, height: 52, borderRadius: "50%",
                    background: `${w.color}20`, border: `2px solid ${w.color}`,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: 18, fontWeight: 900, color: w.color,
                  }}>{w.avatar}</div>
                  <div>
                    <p style={{ fontSize: 20, fontWeight: 800, color: C.white, margin: 0 }}>{w.name}</p>
                    <p style={{ fontSize: 14, color: C.gray, margin: 0 }}>{w.role}</p>
                  </div>
                  <div style={{ marginLeft: "auto", display: "flex", gap: 16 }}>
                    <div style={{ textAlign: "center" }}>
                      <p style={{ fontSize: 22, fontWeight: 900, color: w.color, margin: 0 }}>{w.jobsThisWeek}</p>
                      <p style={{ fontSize: 11, color: C.gray, margin: 0 }}>Jobs</p>
                    </div>
                    <div style={{ textAlign: "center" }}>
                      <p style={{ fontSize: 22, fontWeight: 900, color: C.lightGray, margin: 0 }}>{w.hoursThisWeek}h</p>
                      <p style={{ fontSize: 11, color: C.gray, margin: 0 }}>Hours</p>
                    </div>
                  </div>
                </div>
                {/* Weekly schedule */}
                <div style={{ display: "flex", gap: 6, marginBottom: 16 }}>
                  {w.schedule.map((s, si) => {
                    const delay = 20 + wi * 15 + si * 5;
                    const opacity = interpolate(frame, [delay, delay + 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
                    const isOff = s.jobs === 0;
                    return (
                      <div key={si} style={{
                        flex: 1, opacity, textAlign: "center",
                        background: isOff ? "rgba(255,255,255,0.02)" : `${w.color}10`,
                        border: `1px solid ${isOff ? C.cardBorder : `${w.color}33`}`,
                        borderRadius: 10, padding: "10px 4px",
                      }}>
                        <p style={{ fontSize: 12, fontWeight: 700, color: isOff ? C.gray : C.white, margin: 0 }}>{s.day}</p>
                        <p style={{ fontSize: 16, fontWeight: 900, color: isOff ? C.gray : w.color, margin: "4px 0" }}>{isOff ? "—" : s.jobs}</p>
                        <p style={{ fontSize: 10, color: C.gray, margin: 0 }}>{s.hours}</p>
                      </div>
                    );
                  })}
                </div>
                {/* Services */}
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {w.services.map((s, si) => (
                    <div key={si} style={{
                      padding: "4px 12px", borderRadius: 8,
                      background: `${w.color}12`, border: `1px solid ${w.color}33`,
                      fontSize: 12, fontWeight: 600, color: w.color,
                    }}>{s}</div>
                  ))}
                </div>
              </div>
            </Pop>
          ))}
        </div>
      </div>
    </AbsoluteFill>
  );
};


// ═══════════════════════════════════════════════════════════
// SCENE 7: SERVICES TAB — Service menu showcase
// ═══════════════════════════════════════════════════════════
const ServicesTabScene: React.FC = () => {
  const frame = useCurrentFrame();
  const services = [
    { name: "Pipe Repair", duration: "2 hours", price: "€120–€280", icon: "🔧", color: C.blue, callout: false },
    { name: "Boiler Install", duration: "4 hours", price: "€800–€1,200", icon: "🔥", color: C.orange, callout: false },
    { name: "Bathroom Refit", duration: "3–5 days", price: "€3,500–€8,000", icon: "🚿", color: C.pink, callout: false },
    { name: "Radiator Flush", duration: "1.5 hours", price: "€80–€150", icon: "♨️", color: C.green, callout: false },
    { name: "Emergency Callout", duration: "1 hour", price: "€150+", icon: "🚨", color: C.red, callout: true },
    { name: "Kitchen Plumbing", duration: "3 hours", price: "€200–€450", icon: "🍳", color: C.accent, callout: false },
  ];
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <OrbBlobs colors={["rgba(255, 107, 53, 0.15)", C.accentGlow]} />
      <div style={{ zIndex: 1, width: "100%", padding: "0 80px" }}>
        <Pop delay={0} direction="up" style={{ textAlign: "center", marginBottom: 24 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 12 }}>
            <span style={{ fontSize: 32 }}>🔧</span>
            <h2 style={{ fontSize: 46, fontWeight: 900, color: C.white, margin: 0 }}>
              <Grad from={C.orange} to={C.accent}>Services & Pricing</Grad>
            </h2>
          </div>
          <p style={{ fontSize: 20, color: C.gray, marginTop: 8 }}>Your AI knows every service, duration, and price range.</p>
        </Pop>
        <Pop delay={5} direction="scale">
          <div style={{
            display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 18,
            maxWidth: 1000, margin: "0 auto",
          }}>
            {services.map((s, i) => {
              const delay = 12 + i * 8;
              const opacity = interpolate(frame, [delay, delay + 10], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
              const scale = interpolate(frame, [delay, delay + 10], [0.9, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
              return (
                <div key={i} style={{
                  opacity, transform: `scale(${scale})`,
                  background: C.bgCard, borderRadius: 18, padding: 22,
                  border: `1px solid ${s.callout ? `${C.red}44` : C.cardBorder}`,
                  boxShadow: s.callout ? `0 0 20px rgba(255,71,87,0.15)` : `0 10px 30px rgba(0,0,0,0.3)`,
                  position: "relative", overflow: "hidden",
                }}>
                  {s.callout && (
                    <div style={{
                      position: "absolute", top: 12, right: -28,
                      background: C.red, padding: "3px 30px",
                      transform: "rotate(45deg)", fontSize: 10, fontWeight: 800, color: C.white,
                    }}>URGENT</div>
                  )}
                  <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14 }}>
                    <div style={{
                      width: 48, height: 48, borderRadius: 14,
                      background: `${s.color}15`, border: `1px solid ${s.color}33`,
                      display: "flex", alignItems: "center", justifyContent: "center", fontSize: 24,
                    }}>{s.icon}</div>
                    <div>
                      <p style={{ fontSize: 17, fontWeight: 800, color: C.white, margin: 0 }}>{s.name}</p>
                    </div>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                      <p style={{ fontSize: 12, color: C.gray, margin: "0 0 2px" }}>Duration</p>
                      <p style={{ fontSize: 15, fontWeight: 700, color: C.lightGray, margin: 0 }}>{s.duration}</p>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <p style={{ fontSize: 12, color: C.gray, margin: "0 0 2px" }}>Price Range</p>
                      <p style={{ fontSize: 15, fontWeight: 800, color: s.color, margin: 0 }}>{s.price}</p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </Pop>
      </div>
    </AbsoluteFill>
  );
};


// ═══════════════════════════════════════════════════════════
// SCENE 8: CALL LOGS — AI call history with summaries
// ═══════════════════════════════════════════════════════════
const CallLogsScene: React.FC = () => {
  const frame = useCurrentFrame();
  const calls = [
    { caller: "John Murphy", time: "10:23 AM", duration: "2:34", outcome: "Booked", summary: "Pipe repair booked for Thursday 10AM. Customer has burst pipe in kitchen.", color: C.green },
    { caller: "Unknown Caller", time: "10:45 AM", duration: "0:48", outcome: "Spam", summary: "Marketing call detected. No action needed.", color: C.gray },
    { caller: "Sarah O'Connor", time: "11:12 AM", duration: "3:12", outcome: "Rescheduled", summary: "Boiler install moved from Wed to Fri. Customer requested afternoon slot.", color: C.orange },
    { caller: "Emma Wilson", time: "12:30 PM", duration: "1:56", outcome: "Booked", summary: "Emergency radiator flush. Scheduled for today 3:30PM.", color: C.green },
    { caller: "Tom Kelly", time: "2:15 PM", duration: "2:08", outcome: "Quote Sent", summary: "Bathroom refit enquiry. Quote for €5,500 sent via SMS.", color: C.blue },
  ];
  // Expanding detail card
  const expandedIdx = frame > 70 ? 0 : -1;
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <OrbBlobs colors={[C.greenGlow, "rgba(58, 134, 255, 0.2)"]} />
      <div style={{ zIndex: 1, width: "100%", padding: "0 80px" }}>
        <Pop delay={0} direction="up" style={{ textAlign: "center", marginBottom: 24 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 12 }}>
            <span style={{ fontSize: 32 }}>📞</span>
            <h2 style={{ fontSize: 46, fontWeight: 900, color: C.white, margin: 0 }}>
              <Grad from={C.green} to={C.blue}>AI Call Logs</Grad>
            </h2>
          </div>
          <p style={{ fontSize: 20, color: C.gray, marginTop: 8 }}>Every call recorded, summarized, and actionable.</p>
        </Pop>
        <Pop delay={5} direction="scale">
          <div style={{
            background: C.bgCard, borderRadius: 20, overflow: "hidden",
            border: `1px solid ${C.cardBorder}`,
            boxShadow: `0 30px 80px rgba(0,0,0,0.5)`,
            maxWidth: 950, margin: "0 auto",
          }}>
            {/* Header */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "16px 24px", borderBottom: `1px solid ${C.cardBorder}` }}>
              <span style={{ fontSize: 16, fontWeight: 800, color: C.white }}>Today's Calls</span>
              <div style={{ display: "flex", gap: 8 }}>
                <div style={{ padding: "6px 14px", borderRadius: 8, background: `${C.green}15`, fontSize: 13, fontWeight: 700, color: C.green }}>3 Booked</div>
                <div style={{ padding: "6px 14px", borderRadius: 8, background: `${C.orange}15`, fontSize: 13, fontWeight: 700, color: C.orange }}>1 Rescheduled</div>
              </div>
            </div>
            {/* Call rows */}
            <div style={{ padding: "8px 16px" }}>
              {calls.map((call, i) => {
                const delay = 12 + i * 10;
                const opacity = interpolate(frame, [delay, delay + 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
                const isExpanded = expandedIdx === i;
                const expandHeight = isExpanded ? interpolate(frame, [70, 82], [0, 60], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) : 0;
                return (
                  <div key={i} style={{
                    opacity, borderBottom: i < calls.length - 1 ? `1px solid ${C.cardBorder}` : "none",
                    padding: "12px 8px",
                  }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                      <div style={{
                        width: 38, height: 38, borderRadius: "50%",
                        background: `${call.color}15`, border: `1px solid ${call.color}33`,
                        display: "flex", alignItems: "center", justifyContent: "center",
                        fontSize: 16,
                      }}>📞</div>
                      <div style={{ flex: 1 }}>
                        <p style={{ fontSize: 15, fontWeight: 700, color: C.white, margin: 0 }}>{call.caller}</p>
                        <p style={{ fontSize: 12, color: C.gray, margin: 0 }}>{call.time} · {call.duration}</p>
                      </div>
                      <div style={{
                        padding: "4px 14px", borderRadius: 8,
                        background: `${call.color}15`, fontSize: 13, fontWeight: 700, color: call.color,
                      }}>{call.outcome}</div>
                    </div>
                    {/* Expanded AI summary */}
                    <div style={{ height: expandHeight, overflow: "hidden", marginTop: expandHeight > 0 ? 8 : 0 }}>
                      <div style={{
                        background: `${C.accent}08`, border: `1px solid ${C.accent}22`,
                        borderRadius: 10, padding: "10px 14px",
                      }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                          <span style={{ fontSize: 12 }}>🤖</span>
                          <span style={{ fontSize: 12, fontWeight: 700, color: C.accent }}>AI Summary</span>
                        </div>
                        <p style={{ fontSize: 13, color: C.lightGray, margin: 0, lineHeight: 1.5 }}>{call.summary}</p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </Pop>
      </div>
    </AbsoluteFill>
  );
};


// ═══════════════════════════════════════════════════════════
// SCENE 9: DEMO FINALE — CTA
// ═══════════════════════════════════════════════════════════
const DemoFinaleScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const logoScale = spring({ frame: frame - 5, fps, config: { damping: 8, mass: 0.3, stiffness: 200 } });
  const btnScale = spring({ frame: frame - 35, fps, config: { damping: 8, mass: 0.4, stiffness: 200 } });
  const glow = interpolate(Math.sin(frame * 0.1), [-1, 1], [0.4, 1]);
  // Feature badges floating
  const badges = ["📅 Calendar", "👥 CRM", "💰 Invoicing", "👷 Workers", "📞 AI Calls", "🔧 Services"];
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <OrbBlobs colors={[C.accentGlow, C.greenGlow, "rgba(255, 107, 157, 0.15)"]} />
      <div style={{ textAlign: "center", zIndex: 2 }}>
        <div style={{ transform: `scale(${logoScale})`, marginBottom: 20 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 16 }}>
            <div style={{
              width: 68, height: 68, borderRadius: 18,
              background: `linear-gradient(135deg, ${C.accent}, ${C.green})`,
              display: "flex", alignItems: "center", justifyContent: "center", fontSize: 36,
              boxShadow: `0 0 50px ${C.accentGlow}, 0 0 100px ${C.greenGlow}`,
            }}>⚡</div>
            <span style={{ fontSize: 54, fontWeight: 900, color: C.white, letterSpacing: -2 }}>BookedForYou</span>
          </div>
        </div>
        <Pop delay={12} direction="up">
          <h2 style={{ fontSize: 52, fontWeight: 900, color: C.white, margin: "0 0 12px", lineHeight: 1.15 }}>
            Your entire business.
            <br /><Grad>One powerful dashboard.</Grad>
          </h2>
        </Pop>
        {/* Feature badges */}
        <Pop delay={22} direction="up">
          <div style={{ display: "flex", gap: 10, justifyContent: "center", flexWrap: "wrap", maxWidth: 600, margin: "20px auto" }}>
            {badges.map((b, i) => {
              const delay = 25 + i * 4;
              const opacity = interpolate(frame, [delay, delay + 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
              return (
                <div key={i} style={{
                  opacity, padding: "8px 18px", borderRadius: 12,
                  background: C.card, border: `1px solid ${C.cardBorder}`,
                  fontSize: 15, fontWeight: 600, color: C.lightGray,
                }}>{b}</div>
              );
            })}
          </div>
        </Pop>
        <Pop delay={30} direction="up">
          <p style={{ fontSize: 22, color: C.gray, margin: "0 0 30px" }}>
            14-day free trial. No credit card required.
          </p>
        </Pop>
        <Pop delay={35} direction="scale">
          <div style={{
            display: "inline-block",
            background: `linear-gradient(135deg, ${C.accent}, ${C.green})`,
            borderRadius: 18, padding: "20px 54px",
            transform: `scale(${btnScale})`,
            boxShadow: `0 0 ${50 * glow}px ${C.accentGlow}, 0 0 ${80 * glow}px ${C.greenGlow}`,
          }}>
            <span style={{ fontSize: 26, fontWeight: 900, color: C.white }}>Try It Free →</span>
          </div>
        </Pop>
        <Pop delay={45} direction="up">
          <p style={{ fontSize: 22, fontWeight: 700, color: C.accentLight, marginTop: 20 }}>bookedforyou.ie</p>
        </Pop>
      </div>
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════════════
// MAIN COMPOSITION
// ═══════════════════════════════════════════════════════════
export const AppDemoShowcase: React.FC = () => {
  const scenes = [
    { component: DemoIntroScene, duration: 100 },
    { component: JobsTabScene, duration: 165 },
    { component: CalendarTabScene, duration: 165 },
    { component: CustomersTabScene, duration: 165 },
    { component: FinancesTabScene, duration: 150 },
    { component: WorkersTabScene, duration: 150 },
    { component: ServicesTabScene, duration: 135 },
    { component: CallLogsScene, duration: 150 },
    { component: DemoFinaleScene, duration: 120 },
  ];
  let startFrame = 0;
  return (
    <AbsoluteFill style={{ fontFamily: FONT }}>
      <Audio src={staticFile("music.mp3")} volume={0.35} />
      <StarField />
      {scenes.map((scene, i) => {
        const from = startFrame;
        startFrame += scene.duration;
        const Scene = scene.component;
        return (
          <Sequence key={i} from={from} durationInFrames={scene.duration}>
            <Transition durationInFrames={scene.duration}>
              <Scene />
            </Transition>
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
