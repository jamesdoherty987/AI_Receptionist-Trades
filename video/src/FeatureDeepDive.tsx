import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  Sequence,
} from "remotion";
import React from "react";

// ─── Colors ───
const C = {
  bg1: "#030014",
  bg2: "#0a0025",
  purple: "#7c3aed",
  purpleLight: "#a78bfa",
  purpleGlow: "rgba(124, 58, 237, 0.4)",
  cyan: "#06d6a0",
  cyanGlow: "rgba(6, 214, 160, 0.35)",
  orange: "#ff6b35",
  orangeGlow: "rgba(255, 107, 53, 0.3)",
  pink: "#ff006e",
  pinkGlow: "rgba(255, 0, 110, 0.3)",
  blue: "#3a86ff",
  blueGlow: "rgba(58, 134, 255, 0.3)",
  gold: "#ffd60a",
  white: "#ffffff",
  gray: "#94a3b8",
  lightGray: "#cbd5e1",
  card: "rgba(255,255,255,0.05)",
  cardBorder: "rgba(255,255,255,0.08)",
};

// ─── Animated particle background ───
const ParticleBackground: React.FC = () => {
  const frame = useCurrentFrame();
  const particles = Array.from({ length: 30 }, (_, i) => ({
    x: ((i * 137.5) % 100),
    y: ((i * 73.7 + frame * (0.15 + (i % 5) * 0.05)) % 120) - 10,
    size: 2 + (i % 4),
    opacity: 0.15 + (i % 3) * 0.1,
    color: i % 3 === 0 ? C.purple : i % 3 === 1 ? C.cyan : C.blue,
  }));
  const gridOffset = (frame * 0.2) % 80;
  return (
    <AbsoluteFill>
      <div style={{ width: "100%", height: "100%", background: `radial-gradient(ellipse at 50% 0%, ${C.bg2}, ${C.bg1} 70%)` }} />
      <div style={{
        position: "absolute", inset: 0,
        backgroundImage: `linear-gradient(rgba(124,58,237,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(124,58,237,0.04) 1px, transparent 1px)`,
        backgroundSize: "80px 80px", backgroundPosition: `${gridOffset}px ${gridOffset}px`,
      }} />
      {particles.map((p, i) => (
        <div key={i} style={{
          position: "absolute", left: `${p.x}%`, top: `${p.y}%`,
          width: p.size, height: p.size, borderRadius: "50%",
          backgroundColor: p.color, opacity: p.opacity,
          boxShadow: `0 0 ${p.size * 3}px ${p.color}`,
        }} />
      ))}
    </AbsoluteFill>
  );
};

// ─── Animated glow orbs ───
const GlowOrbs: React.FC<{ colors?: string[] }> = ({ colors = [C.purpleGlow, C.cyanGlow] }) => {
  const frame = useCurrentFrame();
  return (
    <>
      {colors.map((color, i) => {
        const x = 30 + Math.sin(frame * 0.02 + i * 2) * 20;
        const y = 20 + Math.cos(frame * 0.015 + i * 3) * 15;
        return (
          <div key={i} style={{
            position: "absolute", width: 600, height: 600, borderRadius: "50%",
            background: `radial-gradient(circle, ${color}, transparent 70%)`,
            left: `${x}%`, top: `${y}%`, transform: "translate(-50%, -50%)",
            filter: "blur(80px)", pointerEvents: "none",
          }} />
        );
      })}
    </>
  );
};

// ─── Spring fade-in ───
const Pop: React.FC<{
  children: React.ReactNode;
  delay?: number;
  direction?: "up" | "down" | "left" | "right" | "scale";
  style?: React.CSSProperties;
}> = ({ children, delay = 0, direction = "up", style }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame: frame - delay, fps, config: { damping: 14, mass: 0.6, stiffness: 120 } });
  const opacity = interpolate(frame - delay, [0, 10], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  let transform = "";
  if (direction === "up") transform = `translateY(${interpolate(p, [0, 1], [50, 0])}px)`;
  else if (direction === "down") transform = `translateY(${interpolate(p, [0, 1], [-50, 0])}px)`;
  else if (direction === "left") transform = `translateX(${interpolate(p, [0, 1], [60, 0])}px)`;
  else if (direction === "right") transform = `translateX(${interpolate(p, [0, 1], [-60, 0])}px)`;
  else if (direction === "scale") transform = `scale(${interpolate(p, [0, 1], [0.5, 1])})`;
  return <div style={{ opacity, transform, ...style }}>{children}</div>;
};

// ─── Glowing badge ───
const Badge: React.FC<{ text: string; color?: string }> = ({ text, color = C.purple }) => (
  <div style={{
    display: "inline-block", padding: "8px 20px", borderRadius: 30,
    background: `${color}22`, border: `1px solid ${color}55`,
    fontSize: 18, fontWeight: 700, color, textTransform: "uppercase", letterSpacing: 3,
  }}>{text}</div>
);

// ─── Gradient text ───
const GradientText: React.FC<{ children: React.ReactNode; from?: string; to?: string; style?: React.CSSProperties }> = ({
  children, from = C.purple, to = C.cyan, style,
}) => (
  <span style={{
    background: `linear-gradient(135deg, ${from}, ${to})`,
    WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", ...style,
  }}>{children}</span>
);




// ═══════════════════════════════════════════════════════════
// SCENE 1: EXPLOSIVE INTRO
// ═══════════════════════════════════════════════════════════
const IntroScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const logoScale = spring({ frame: frame - 5, fps, config: { damping: 8, mass: 0.4, stiffness: 200 } });
  const lineWidth = interpolate(frame, [20, 50], [0, 100], { extrapolateRight: "clamp" });
  const subtitleOpacity = interpolate(frame, [35, 50], [0, 1], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <GlowOrbs colors={[C.purpleGlow, C.cyanGlow, C.blueGlow]} />
      <div style={{ textAlign: "center", zIndex: 1 }}>
        <Pop delay={0} direction="scale">
          <div style={{
            display: "flex", alignItems: "center", justifyContent: "center", gap: 18, marginBottom: 24,
            transform: `scale(${logoScale})`,
          }}>
            <div style={{
              width: 72, height: 72, borderRadius: 18,
              background: `linear-gradient(135deg, ${C.purple}, ${C.cyan})`,
              display: "flex", alignItems: "center", justifyContent: "center", fontSize: 36,
              boxShadow: `0 0 40px ${C.purpleGlow}, 0 0 80px ${C.cyanGlow}`,
            }}>⚡</div>
            <span style={{ fontSize: 56, fontWeight: 900, color: C.white, letterSpacing: -2 }}>BookedForYou</span>
          </div>
        </Pop>
        {/* Animated line */}
        <div style={{ width: 300, height: 3, margin: "0 auto 30px", background: C.cardBorder, borderRadius: 2, overflow: "hidden" }}>
          <div style={{ width: `${lineWidth}%`, height: "100%", background: `linear-gradient(90deg, ${C.purple}, ${C.cyan})`, borderRadius: 2 }} />
        </div>
        <Pop delay={15} direction="up">
          <h1 style={{ fontSize: 72, fontWeight: 900, color: C.white, lineHeight: 1.1, margin: 0 }}>
            Every Feature.
            <br />
            <GradientText>One Platform.</GradientText>
          </h1>
        </Pop>
        <div style={{ opacity: subtitleOpacity, marginTop: 24 }}>
          <p style={{ fontSize: 26, color: C.gray, maxWidth: 650, margin: "0 auto" }}>
            The complete AI receptionist and business management system built for trades
          </p>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════════════
// SCENE 2: AI PHONE RECEPTIONIST (the star feature)
// ═══════════════════════════════════════════════════════════
const AIPhoneScene: React.FC = () => {
  const frame = useCurrentFrame();
  // Conversation bubbles appearing one by one
  const bubbles = [
    { from: "customer", text: "Hi, I need a plumber for a leaking pipe", delay: 25 },
    { from: "ai", text: "I can help with that! Can I get your name?", delay: 50 },
    { from: "customer", text: "It's John Murphy", delay: 75 },
    { from: "ai", text: "That's J-O-H-N M-U-R-P-H-Y, correct?", delay: 95 },
    { from: "customer", text: "Yes, that's right", delay: 115 },
    { from: "ai", text: "I have Thursday at 10am available. Shall I book that?", delay: 130 },
  ];
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <GlowOrbs colors={[C.purpleGlow, C.orangeGlow]} />
      <div style={{ display: "flex", gap: 60, alignItems: "center", zIndex: 1, padding: "0 80px" }}>
        {/* Left: info */}
        <div style={{ flex: 1 }}>
          <Pop delay={0}><Badge text="Core Feature" color={C.orange} /></Pop>
          <Pop delay={8} direction="up">
            <h2 style={{ fontSize: 52, fontWeight: 900, color: C.white, margin: "20px 0 16px", lineHeight: 1.15 }}>
              AI Phone
              <br /><GradientText from={C.orange} to={C.gold}>Receptionist</GradientText>
            </h2>
          </Pop>
          <Pop delay={16} direction="up">
            <p style={{ fontSize: 22, color: C.gray, lineHeight: 1.6, margin: "0 0 24px" }}>
              Powered by GPT-4o with Deepgram speech recognition. Answers calls naturally, handles interruptions, and books jobs — all without human intervention.
            </p>
          </Pop>
          <Pop delay={24} direction="up">
            <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
              {["24/7 Availability", "Natural Conversation", "Unlimited Calls", "Urgency Detection"].map((t, i) => (
                <div key={i} style={{
                  padding: "8px 16px", borderRadius: 10,
                  background: `${C.orange}15`, border: `1px solid ${C.orange}33`,
                  fontSize: 15, color: C.orange, fontWeight: 600,
                }}>{t}</div>
              ))}
            </div>
          </Pop>
        </div>
        {/* Right: chat mockup */}
        <div style={{ width: 440 }}>
          <Pop delay={10} direction="right">
            <div style={{
              background: C.card, border: `1px solid ${C.cardBorder}`, borderRadius: 24,
              padding: 24, backdropFilter: "blur(20px)",
              boxShadow: `0 20px 60px rgba(0,0,0,0.4), 0 0 40px ${C.orangeGlow}`,
            }}>
              {/* Header */}
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20, paddingBottom: 16, borderBottom: `1px solid ${C.cardBorder}` }}>
                <div style={{ width: 40, height: 40, borderRadius: "50%", background: `linear-gradient(135deg, ${C.orange}, ${C.gold})`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20 }}>🤖</div>
                <div>
                  <p style={{ fontSize: 16, fontWeight: 700, color: C.white, margin: 0 }}>AI Receptionist</p>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <div style={{ width: 8, height: 8, borderRadius: "50%", background: C.cyan }} />
                    <p style={{ fontSize: 13, color: C.cyan, margin: 0 }}>Live Call</p>
                  </div>
                </div>
                {/* Sound wave */}
                <div style={{ marginLeft: "auto", display: "flex", gap: 3, alignItems: "center", height: 30 }}>
                  {[0, 1, 2, 3, 4].map(i => (
                    <div key={i} style={{
                      width: 4, borderRadius: 2, background: C.orange,
                      height: 10 + Math.sin(frame * 0.2 + i * 0.8) * 8,
                    }} />
                  ))}
                </div>
              </div>
              {/* Bubbles */}
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {bubbles.map((b, i) => {
                  const opacity = interpolate(frame, [b.delay, b.delay + 10], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
                  const translateY = interpolate(frame, [b.delay, b.delay + 10], [15, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
                  const isAI = b.from === "ai";
                  return (
                    <div key={i} style={{
                      opacity, transform: `translateY(${translateY}px)`,
                      alignSelf: isAI ? "flex-start" : "flex-end",
                      maxWidth: "85%",
                    }}>
                      <div style={{
                        padding: "10px 16px", borderRadius: 14,
                        background: isAI ? `${C.orange}20` : `${C.purple}20`,
                        border: `1px solid ${isAI ? C.orange : C.purple}33`,
                        fontSize: 14, color: C.white, lineHeight: 1.4,
                      }}>{b.text}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          </Pop>
        </div>
      </div>
    </AbsoluteFill>
  );
};


// ═══════════════════════════════════════════════════════════
// SCENE 3: SMART SCHEDULING & CALENDAR
// ═══════════════════════════════════════════════════════════
const CalendarScene: React.FC = () => {
  const frame = useCurrentFrame();
  const days = ["Mon", "Tue", "Wed", "Thu", "Fri"];
  const hours = ["9am", "10am", "11am", "12pm", "1pm", "2pm", "3pm", "4pm"];
  const bookings = [
    { day: 0, hour: 0, span: 2, label: "Pipe Repair", color: C.blue },
    { day: 1, hour: 2, span: 3, label: "Boiler Install", color: C.purple },
    { day: 2, hour: 0, span: 8, label: "Full Bathroom Refit (Multi-Day)", color: C.orange },
    { day: 3, hour: 0, span: 8, label: "Full Bathroom Refit (Day 2)", color: C.orange },
    { day: 4, hour: 1, span: 2, label: "Emergency Leak", color: C.pink },
    { day: 0, hour: 4, span: 2, label: "Radiator Flush", color: C.cyan },
    { day: 4, hour: 4, span: 3, label: "Kitchen Plumbing", color: C.blue },
  ];
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <GlowOrbs colors={[C.blueGlow, C.cyanGlow]} />
      <div style={{ display: "flex", gap: 60, alignItems: "center", zIndex: 1, padding: "0 80px" }}>
        {/* Calendar grid */}
        <div style={{ width: 560 }}>
          <Pop delay={10} direction="left">
            <div style={{
              background: C.card, border: `1px solid ${C.cardBorder}`, borderRadius: 20,
              padding: 24, backdropFilter: "blur(20px)",
              boxShadow: `0 20px 60px rgba(0,0,0,0.4), 0 0 30px ${C.blueGlow}`,
            }}>
              {/* Day headers */}
              <div style={{ display: "grid", gridTemplateColumns: "50px repeat(5, 1fr)", gap: 4, marginBottom: 8 }}>
                <div />
                {days.map((d, i) => (
                  <Pop key={i} delay={15 + i * 3} direction="down">
                    <div style={{ textAlign: "center", fontSize: 14, fontWeight: 700, color: C.lightGray, padding: "6px 0" }}>{d}</div>
                  </Pop>
                ))}
              </div>
              {/* Time grid */}
              <div style={{ display: "grid", gridTemplateColumns: "50px repeat(5, 1fr)", gridTemplateRows: `repeat(${hours.length}, 32px)`, gap: 4, position: "relative" }}>
                {hours.map((h, i) => (
                  <div key={i} style={{ fontSize: 11, color: C.gray, display: "flex", alignItems: "center", gridRow: i + 1, gridColumn: 1 }}>{h}</div>
                ))}
                {/* Booking blocks */}
                {bookings.map((b, i) => {
                  const showDelay = 25 + i * 8;
                  const opacity = interpolate(frame, [showDelay, showDelay + 12], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
                  const scale = interpolate(frame, [showDelay, showDelay + 12], [0.8, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
                  return (
                    <div key={i} style={{
                      gridColumn: b.day + 2, gridRow: `${b.hour + 1} / span ${b.span}`,
                      background: `${b.color}25`, border: `1px solid ${b.color}55`,
                      borderRadius: 8, padding: "4px 8px", fontSize: 11, fontWeight: 600,
                      color: b.color, opacity, transform: `scale(${scale})`,
                      display: "flex", alignItems: "center", overflow: "hidden",
                    }}>{b.label}</div>
                  );
                })}
              </div>
              {/* Google Calendar badge */}
              <Pop delay={70} direction="up">
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 16, justifyContent: "center" }}>
                  <div style={{ fontSize: 18 }}>📅</div>
                  <span style={{ fontSize: 13, color: C.cyan, fontWeight: 600 }}>Synced with Google Calendar</span>
                </div>
              </Pop>
            </div>
          </Pop>
        </div>
        {/* Right: info */}
        <div style={{ flex: 1 }}>
          <Pop delay={0}><Badge text="Scheduling" color={C.blue} /></Pop>
          <Pop delay={8} direction="up">
            <h2 style={{ fontSize: 50, fontWeight: 900, color: C.white, margin: "20px 0 16px", lineHeight: 1.15 }}>
              Smart Calendar
              <br /><GradientText from={C.blue} to={C.cyan}>& Scheduling</GradientText>
            </h2>
          </Pop>
          <Pop delay={16} direction="up">
            <p style={{ fontSize: 21, color: C.gray, lineHeight: 1.6, margin: "0 0 24px" }}>
              Google Calendar integration with real-time availability checking. Handles multi-day jobs, worker schedules, business hours, and prevents double-bookings automatically.
            </p>
          </Pop>
          <Pop delay={24} direction="up">
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {[
                "Multi-day job support (week-long projects)",
                "Worker availability & conflict detection",
                "Business hours enforcement",
                "Emergency / Same-Day / Scheduled / Quote",
                "Bidirectional Google Calendar sync",
              ].map((t, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <div style={{ width: 24, height: 24, borderRadius: 6, background: `${C.cyan}20`, border: `1px solid ${C.cyan}44`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, color: C.cyan }}>✓</div>
                  <span style={{ fontSize: 17, color: C.lightGray }}>{t}</span>
                </div>
              ))}
            </div>
          </Pop>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════════════
// SCENE 4: CUSTOMER MANAGEMENT
// ═══════════════════════════════════════════════════════════
const CustomersScene: React.FC = () => {
  const frame = useCurrentFrame();
  const customers = [
    { name: "John Murphy", phone: "+353 86 XXX XXXX", jobs: 12, status: "Returning" },
    { name: "Sarah O'Brien", phone: "+353 87 XXX XXXX", jobs: 5, status: "Returning" },
    { name: "Mike Kelly", phone: "+353 85 XXX XXXX", jobs: 1, status: "New" },
    { name: "Emma Walsh", phone: "+353 89 XXX XXXX", jobs: 8, status: "Returning" },
  ];
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <GlowOrbs colors={[C.pinkGlow, C.purpleGlow]} />
      <div style={{ display: "flex", gap: 60, alignItems: "center", zIndex: 1, padding: "0 80px" }}>
        <div style={{ flex: 1 }}>
          <Pop delay={0}><Badge text="CRM" color={C.pink} /></Pop>
          <Pop delay={8} direction="up">
            <h2 style={{ fontSize: 50, fontWeight: 900, color: C.white, margin: "20px 0 16px", lineHeight: 1.15 }}>
              Customer
              <br /><GradientText from={C.pink} to={C.purpleLight}>Management</GradientText>
            </h2>
          </Pop>
          <Pop delay={16} direction="up">
            <p style={{ fontSize: 21, color: C.gray, lineHeight: 1.6, margin: "0 0 20px" }}>
              Every caller is automatically saved. The AI recognises returning customers, remembers their details, and never asks for info twice.
            </p>
          </Pop>
          <Pop delay={24} direction="up">
            <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
              {["Auto-capture phone & email", "Address validation", "Job history tracking", "Search & filter"].map((t, i) => (
                <div key={i} style={{ padding: "8px 16px", borderRadius: 10, background: `${C.pink}15`, border: `1px solid ${C.pink}33`, fontSize: 14, color: C.pink, fontWeight: 600 }}>{t}</div>
              ))}
            </div>
          </Pop>
        </div>
        {/* Customer list mockup */}
        <div style={{ width: 440 }}>
          <Pop delay={12} direction="right">
            <div style={{
              background: C.card, border: `1px solid ${C.cardBorder}`, borderRadius: 20,
              padding: 20, backdropFilter: "blur(20px)",
              boxShadow: `0 20px 60px rgba(0,0,0,0.4), 0 0 30px ${C.pinkGlow}`,
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16, padding: "10px 14px", background: "rgba(255,255,255,0.04)", borderRadius: 12, border: `1px solid ${C.cardBorder}` }}>
                <span style={{ fontSize: 16, color: C.gray }}>🔍</span>
                <span style={{ fontSize: 15, color: C.gray }}>Search customers...</span>
              </div>
              {customers.map((c, i) => {
                const delay = 25 + i * 12;
                const opacity = interpolate(frame, [delay, delay + 10], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
                return (
                  <div key={i} style={{
                    opacity, display: "flex", alignItems: "center", gap: 14,
                    padding: "14px 16px", borderRadius: 14,
                    background: i === 0 ? `${C.pink}10` : "transparent",
                    border: `1px solid ${i === 0 ? C.pink + "33" : "transparent"}`,
                    marginBottom: 6,
                  }}>
                    <div style={{ width: 42, height: 42, borderRadius: "50%", background: `linear-gradient(135deg, ${C.pink}40, ${C.purple}40)`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18, color: C.white, fontWeight: 700 }}>
                      {c.name[0]}
                    </div>
                    <div style={{ flex: 1 }}>
                      <p style={{ fontSize: 15, fontWeight: 700, color: C.white, margin: 0 }}>{c.name}</p>
                      <p style={{ fontSize: 12, color: C.gray, margin: "2px 0 0" }}>{c.phone}</p>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <p style={{ fontSize: 13, fontWeight: 700, color: C.lightGray, margin: 0 }}>{c.jobs} jobs</p>
                      <span style={{
                        fontSize: 11, fontWeight: 600, padding: "2px 8px", borderRadius: 6,
                        background: c.status === "New" ? `${C.cyan}20` : `${C.purple}20`,
                        color: c.status === "New" ? C.cyan : C.purpleLight,
                      }}>{c.status}</span>
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
// SCENE 5: FINANCES & INVOICING
// ═══════════════════════════════════════════════════════════
const FinancesScene: React.FC = () => {
  const frame = useCurrentFrame();
  const barData = [
    { label: "Mon", value: 450 },
    { label: "Tue", value: 320 },
    { label: "Wed", value: 680 },
    { label: "Thu", value: 520 },
    { label: "Fri", value: 890 },
  ];
  const maxVal = 890;
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <GlowOrbs colors={[C.cyanGlow, C.blueGlow]} />
      <div style={{ display: "flex", gap: 60, alignItems: "center", zIndex: 1, padding: "0 80px" }}>
        {/* Chart mockup */}
        <div style={{ width: 500 }}>
          <Pop delay={10} direction="left">
            <div style={{
              background: C.card, border: `1px solid ${C.cardBorder}`, borderRadius: 20,
              padding: 28, backdropFilter: "blur(20px)",
              boxShadow: `0 20px 60px rgba(0,0,0,0.4), 0 0 30px ${C.cyanGlow}`,
            }}>
              {/* Revenue cards */}
              <div style={{ display: "flex", gap: 12, marginBottom: 24 }}>
                {[
                  { label: "Total Revenue", value: "€12,450", color: C.white },
                  { label: "Paid", value: "€9,200", color: C.cyan },
                  { label: "Unpaid", value: "€3,250", color: C.orange },
                ].map((c, i) => (
                  <Pop key={i} delay={20 + i * 6} direction="up">
                    <div style={{ flex: 1, padding: "14px 16px", borderRadius: 14, background: "rgba(255,255,255,0.04)", border: `1px solid ${C.cardBorder}` }}>
                      <p style={{ fontSize: 12, color: C.gray, margin: "0 0 4px" }}>{c.label}</p>
                      <p style={{ fontSize: 22, fontWeight: 800, color: c.color, margin: 0 }}>{c.value}</p>
                    </div>
                  </Pop>
                ))}
              </div>
              {/* Bar chart */}
              <div style={{ display: "flex", alignItems: "flex-end", gap: 16, height: 140, padding: "0 10px" }}>
                {barData.map((b, i) => {
                  const barDelay = 40 + i * 6;
                  const barHeight = interpolate(frame, [barDelay, barDelay + 20], [0, (b.value / maxVal) * 120], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
                  return (
                    <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
                      <div style={{
                        width: "100%", height: barHeight, borderRadius: 8,
                        background: `linear-gradient(180deg, ${C.cyan}, ${C.blue})`,
                        boxShadow: `0 0 15px ${C.cyanGlow}`,
                      }} />
                      <span style={{ fontSize: 12, color: C.gray }}>{b.label}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </Pop>
        </div>
        {/* Right: info */}
        <div style={{ flex: 1 }}>
          <Pop delay={0}><Badge text="Finances" color={C.cyan} /></Pop>
          <Pop delay={8} direction="up">
            <h2 style={{ fontSize: 50, fontWeight: 900, color: C.white, margin: "20px 0 16px", lineHeight: 1.15 }}>
              Revenue Tracking
              <br /><GradientText from={C.cyan} to={C.blue}>& Invoicing</GradientText>
            </h2>
          </Pop>
          <Pop delay={16} direction="up">
            <p style={{ fontSize: 21, color: C.gray, lineHeight: 1.6, margin: "0 0 24px" }}>
              Track every euro. See daily and monthly revenue charts, manage paid vs unpaid jobs, and send professional invoices with Stripe payment links.
            </p>
          </Pop>
          <Pop delay={24} direction="up">
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {[
                "Revenue dashboard with charts",
                "One-click invoice sending",
                "Stripe payment link integration",
                "Mark jobs as paid/unpaid",
                "Bank details on invoices",
              ].map((t, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <div style={{ width: 24, height: 24, borderRadius: 6, background: `${C.cyan}20`, border: `1px solid ${C.cyan}44`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, color: C.cyan }}>✓</div>
                  <span style={{ fontSize: 17, color: C.lightGray }}>{t}</span>
                </div>
              ))}
            </div>
          </Pop>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════════════
// SCENE 6: WORKER MANAGEMENT
// ═══════════════════════════════════════════════════════════
const WorkersScene: React.FC = () => {
  const frame = useCurrentFrame();
  const workers = [
    { name: "Paddy O'Brien", role: "Senior Plumber", status: "On Job", hours: "32h", color: C.blue },
    { name: "Sean Kelly", role: "Apprentice", status: "Available", hours: "28h", color: C.cyan },
    { name: "Liam Murphy", role: "Electrician", status: "On Job", hours: "36h", color: C.purple },
  ];
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <GlowOrbs colors={[C.purpleGlow, C.blueGlow]} />
      <div style={{ display: "flex", gap: 60, alignItems: "center", zIndex: 1, padding: "0 80px" }}>
        <div style={{ flex: 1 }}>
          <Pop delay={0}><Badge text="Team" color={C.purple} /></Pop>
          <Pop delay={8} direction="up">
            <h2 style={{ fontSize: 50, fontWeight: 900, color: C.white, margin: "20px 0 16px", lineHeight: 1.15 }}>
              Worker
              <br /><GradientText>Management</GradientText>
            </h2>
          </Pop>
          <Pop delay={16} direction="up">
            <p style={{ fontSize: 21, color: C.gray, lineHeight: 1.6, margin: "0 0 24px" }}>
              Assign jobs to your team, set service restrictions per worker, track weekly hours, and prevent scheduling conflicts. The AI knows who's available.
            </p>
          </Pop>
          <Pop delay={24} direction="up">
            <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
              {["Service restrictions", "Hours tracking", "Auto-assignment", "Conflict prevention"].map((t, i) => (
                <div key={i} style={{ padding: "8px 16px", borderRadius: 10, background: `${C.purple}15`, border: `1px solid ${C.purple}33`, fontSize: 14, color: C.purpleLight, fontWeight: 600 }}>{t}</div>
              ))}
            </div>
          </Pop>
        </div>
        {/* Worker cards */}
        <div style={{ width: 420, display: "flex", flexDirection: "column", gap: 14 }}>
          {workers.map((w, i) => {
            const delay = 15 + i * 12;
            const opacity = interpolate(frame, [delay, delay + 10], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            const translateX = interpolate(frame, [delay, delay + 10], [40, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            return (
              <div key={i} style={{
                opacity, transform: `translateX(${translateX}px)`,
                background: C.card, border: `1px solid ${C.cardBorder}`, borderRadius: 18,
                padding: "18px 22px", display: "flex", alignItems: "center", gap: 16,
                backdropFilter: "blur(20px)", boxShadow: `0 10px 30px rgba(0,0,0,0.3)`,
              }}>
                <div style={{
                  width: 50, height: 50, borderRadius: 14,
                  background: `linear-gradient(135deg, ${w.color}40, ${w.color}20)`,
                  border: `1px solid ${w.color}44`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 22,
                }}>👷</div>
                <div style={{ flex: 1 }}>
                  <p style={{ fontSize: 17, fontWeight: 700, color: C.white, margin: 0 }}>{w.name}</p>
                  <p style={{ fontSize: 13, color: C.gray, margin: "2px 0 0" }}>{w.role}</p>
                </div>
                <div style={{ textAlign: "right" }}>
                  <span style={{
                    fontSize: 12, fontWeight: 700, padding: "4px 10px", borderRadius: 8,
                    background: w.status === "Available" ? `${C.cyan}20` : `${C.orange}20`,
                    color: w.status === "Available" ? C.cyan : C.orange,
                  }}>{w.status}</span>
                  <p style={{ fontSize: 13, color: C.gray, margin: "6px 0 0" }}>{w.hours} this week</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};


// ═══════════════════════════════════════════════════════════
// SCENE 7: SERVICES & SMS REMINDERS
// ═══════════════════════════════════════════════════════════
const ServicesAndSMSScene: React.FC = () => {
  const frame = useCurrentFrame();
  const services = [
    { name: "Emergency Callout", price: "€80", duration: "1 hour", icon: "🚨" },
    { name: "Boiler Service", price: "€120", duration: "2 hours", icon: "🔥" },
    { name: "Full Bathroom Refit", price: "€3,500", duration: "1 week", icon: "🚿" },
    { name: "Pipe Repair", price: "€95", duration: "1.5 hours", icon: "🔧" },
  ];
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <GlowOrbs colors={[C.orangeGlow, C.cyanGlow]} />
      <div style={{ display: "flex", gap: 50, zIndex: 1, padding: "0 80px" }}>
        {/* Services */}
        <div style={{ flex: 1 }}>
          <Pop delay={0}><Badge text="Services" color={C.orange} /></Pop>
          <Pop delay={8} direction="up">
            <h2 style={{ fontSize: 44, fontWeight: 900, color: C.white, margin: "16px 0 20px", lineHeight: 1.15 }}>
              Service Menu
              <br /><GradientText from={C.orange} to={C.gold}>& Pricing</GradientText>
            </h2>
          </Pop>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            {services.map((s, i) => {
              const delay = 18 + i * 10;
              const opacity = interpolate(frame, [delay, delay + 10], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
              return (
                <div key={i} style={{
                  opacity, background: C.card, border: `1px solid ${C.cardBorder}`,
                  borderRadius: 16, padding: "18px 16px", backdropFilter: "blur(20px)",
                }}>
                  <div style={{ fontSize: 28, marginBottom: 8 }}>{s.icon}</div>
                  <p style={{ fontSize: 16, fontWeight: 700, color: C.white, margin: "0 0 4px" }}>{s.name}</p>
                  <p style={{ fontSize: 14, color: C.gray, margin: "0 0 8px" }}>{s.duration}</p>
                  <p style={{ fontSize: 20, fontWeight: 800, color: C.orange, margin: 0 }}>{s.price}</p>
                </div>
              );
            })}
          </div>
        </div>
        {/* SMS Reminders */}
        <div style={{ flex: 1 }}>
          <Pop delay={5}><Badge text="Reminders" color={C.cyan} /></Pop>
          <Pop delay={12} direction="up">
            <h2 style={{ fontSize: 44, fontWeight: 900, color: C.white, margin: "16px 0 20px", lineHeight: 1.15 }}>
              SMS & Email
              <br /><GradientText from={C.cyan} to={C.blue}>Reminders</GradientText>
            </h2>
          </Pop>
          <Pop delay={20} direction="up">
            <p style={{ fontSize: 19, color: C.gray, lineHeight: 1.6, margin: "0 0 20px" }}>
              Automatic reminders sent 24 hours before every appointment. Customers can confirm or reschedule via SMS reply.
            </p>
          </Pop>
          {/* SMS mockup */}
          <Pop delay={30} direction="up">
            <div style={{
              background: C.card, border: `1px solid ${C.cardBorder}`, borderRadius: 18,
              padding: 20, backdropFilter: "blur(20px)",
              boxShadow: `0 10px 40px rgba(0,0,0,0.3)`,
            }}>
              <div style={{ background: `${C.cyan}12`, border: `1px solid ${C.cyan}33`, borderRadius: 14, padding: "14px 18px", marginBottom: 10 }}>
                <p style={{ fontSize: 14, color: C.lightGray, margin: 0, lineHeight: 1.5 }}>
                  📱 Reminder: You have a Pipe Repair appointment tomorrow at 10:00 AM. Reply YES to confirm or RESCHEDULE to change.
                </p>
              </div>
              <Pop delay={50} direction="up">
                <div style={{ background: `${C.purple}12`, border: `1px solid ${C.purple}33`, borderRadius: 14, padding: "14px 18px", alignSelf: "flex-end", marginLeft: "auto", maxWidth: "60%", textAlign: "right" }}>
                  <p style={{ fontSize: 14, color: C.lightGray, margin: 0 }}>YES ✅</p>
                </div>
              </Pop>
            </div>
          </Pop>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════════════
// SCENE 8: ONBOARDING & SETTINGS
// ═══════════════════════════════════════════════════════════
const OnboardingScene: React.FC = () => {
  const frame = useCurrentFrame();
  const steps = [
    { icon: "👑", label: "Subscription", done: true },
    { icon: "📍", label: "Service Area", done: true },
    { icon: "🏢", label: "Company Details", done: true },
    { icon: "🏦", label: "Payment", done: true },
    { icon: "🔧", label: "Services", done: true },
    { icon: "👷", label: "Workers", done: false },
    { icon: "📞", label: "Phone Number", done: false },
  ];
  const activeStep = Math.min(Math.floor(interpolate(frame, [20, 120], [0, 7], { extrapolateRight: "clamp" })), 6);
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <GlowOrbs colors={[C.purpleGlow, C.cyanGlow]} />
      <div style={{ textAlign: "center", zIndex: 1, maxWidth: 1000 }}>
        <Pop delay={0}><Badge text="Setup" color={C.purple} /></Pop>
        <Pop delay={6} direction="up">
          <h2 style={{ fontSize: 50, fontWeight: 900, color: C.white, margin: "20px 0 12px" }}>
            5-Minute <GradientText>Onboarding</GradientText>
          </h2>
        </Pop>
        <Pop delay={12} direction="up">
          <p style={{ fontSize: 22, color: C.gray, margin: "0 0 40px" }}>
            A guided wizard walks you through everything. Set up your business, add services, configure workers, and go live.
          </p>
        </Pop>
        {/* Step progress */}
        <Pop delay={18} direction="up">
          <div style={{
            background: C.card, border: `1px solid ${C.cardBorder}`, borderRadius: 24,
            padding: "36px 40px", backdropFilter: "blur(20px)",
            boxShadow: `0 20px 60px rgba(0,0,0,0.4), 0 0 40px ${C.purpleGlow}`,
          }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
              {steps.map((s, i) => {
                const isActive = i <= activeStep;
                const isCurrent = i === activeStep;
                return (
                  <React.Fragment key={i}>
                    <div style={{
                      display: "flex", flexDirection: "column", alignItems: "center", gap: 8, width: 100,
                    }}>
                      <div style={{
                        width: 52, height: 52, borderRadius: 16,
                        background: isActive ? `linear-gradient(135deg, ${C.purple}, ${C.cyan})` : "rgba(255,255,255,0.06)",
                        border: isCurrent ? `2px solid ${C.cyan}` : `1px solid ${isActive ? "transparent" : C.cardBorder}`,
                        display: "flex", alignItems: "center", justifyContent: "center", fontSize: 24,
                        boxShadow: isCurrent ? `0 0 20px ${C.cyanGlow}` : "none",
                        transition: "all 0.3s",
                      }}>
                        {isActive && i < activeStep ? "✓" : s.icon}
                      </div>
                      <span style={{ fontSize: 12, fontWeight: 600, color: isActive ? C.white : C.gray }}>{s.label}</span>
                    </div>
                    {i < steps.length - 1 && (
                      <div style={{
                        width: 30, height: 3, borderRadius: 2, marginBottom: 24,
                        background: i < activeStep ? `linear-gradient(90deg, ${C.purple}, ${C.cyan})` : C.cardBorder,
                      }} />
                    )}
                  </React.Fragment>
                );
              })}
            </div>
          </div>
        </Pop>
        <Pop delay={60} direction="up">
          <div style={{ display: "flex", justifyContent: "center", gap: 30, marginTop: 30 }}>
            {["Business Hours Config", "AI Toggle On/Off", "Google Calendar Sync", "Company Branding"].map((t, i) => (
              <div key={i} style={{ padding: "10px 18px", borderRadius: 12, background: C.card, border: `1px solid ${C.cardBorder}`, fontSize: 15, color: C.lightGray, fontWeight: 600 }}>{t}</div>
            ))}
          </div>
        </Pop>
      </div>
    </AbsoluteFill>
  );
};


// ═══════════════════════════════════════════════════════════
// SCENE 9: STATS EXPLOSION
// ═══════════════════════════════════════════════════════════
const StatsScene: React.FC = () => {
  const frame = useCurrentFrame();
  const stats = [
    { value: "24/7", label: "Always Available", icon: "🕐", color: C.cyan },
    { value: "€99", label: "Per Month", icon: "💰", color: C.gold },
    { value: "∞", label: "Concurrent Calls", icon: "📞", color: C.purple },
    { value: "0", label: "Missed Calls", icon: "🎯", color: C.pink },
    { value: "30%", label: "More Bookings", icon: "📈", color: C.blue },
    { value: "Full", label: "Accounting Suite", icon: "⚡", color: C.orange },
  ];
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <GlowOrbs colors={[C.purpleGlow, C.cyanGlow, C.orangeGlow]} />
      <div style={{ textAlign: "center", zIndex: 1 }}>
        <Pop delay={0} direction="scale">
          <h2 style={{ fontSize: 56, fontWeight: 900, color: C.white, margin: "0 0 50px" }}>
            By The <GradientText from={C.gold} to={C.orange}>Numbers</GradientText>
          </h2>
        </Pop>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 24, maxWidth: 900, margin: "0 auto" }}>
          {stats.map((s, i) => {
            const delay = 12 + i * 8;
            const scale = spring({ frame: frame - delay, fps: 30, config: { damping: 10, mass: 0.5, stiffness: 180 } });
            return (
              <div key={i} style={{
                transform: `scale(${scale})`,
                background: C.card, border: `1px solid ${C.cardBorder}`, borderRadius: 22,
                padding: "32px 24px", backdropFilter: "blur(20px)",
                boxShadow: `0 0 30px ${s.color}15`,
              }}>
                <div style={{ fontSize: 36, marginBottom: 12 }}>{s.icon}</div>
                <p style={{ fontSize: 44, fontWeight: 900, color: s.color, margin: "0 0 6px", textShadow: `0 0 20px ${s.color}40` }}>{s.value}</p>
                <p style={{ fontSize: 16, color: C.gray, margin: 0, fontWeight: 600 }}>{s.label}</p>
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════════════
// SCENE 10: EXPLOSIVE CTA
// ═══════════════════════════════════════════════════════════
const FinalCTAScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const btnScale = spring({ frame: frame - 35, fps, config: { damping: 8, mass: 0.4, stiffness: 200 } });
  const glow = interpolate(Math.sin(frame * 0.12), [-1, 1], [0.3, 1]);
  // Expanding rings
  const rings = [0, 1, 2].map(i => ({
    scale: interpolate((frame + i * 20) % 60, [0, 60], [0.5, 2.5]),
    opacity: interpolate((frame + i * 20) % 60, [0, 60], [0.4, 0]),
  }));
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <GlowOrbs colors={[C.purpleGlow, C.cyanGlow, C.pinkGlow]} />
      {/* Expanding rings */}
      {rings.map((r, i) => (
        <div key={i} style={{
          position: "absolute", width: 300, height: 300, borderRadius: "50%",
          border: `2px solid ${C.purple}`, transform: `scale(${r.scale})`, opacity: r.opacity,
          top: "50%", left: "50%", marginTop: -150, marginLeft: -150,
        }} />
      ))}
      <div style={{ textAlign: "center", zIndex: 1 }}>
        <Pop delay={0} direction="scale">
          <div style={{
            display: "flex", alignItems: "center", justifyContent: "center", gap: 16, marginBottom: 28,
          }}>
            <div style={{
              width: 64, height: 64, borderRadius: 16,
              background: `linear-gradient(135deg, ${C.purple}, ${C.cyan})`,
              display: "flex", alignItems: "center", justifyContent: "center", fontSize: 32,
              boxShadow: `0 0 50px ${C.purpleGlow}, 0 0 100px ${C.cyanGlow}`,
            }}>⚡</div>
            <span style={{ fontSize: 48, fontWeight: 900, color: C.white, letterSpacing: -1 }}>BookedForYou</span>
          </div>
        </Pop>
        <Pop delay={10} direction="up">
          <h2 style={{ fontSize: 60, fontWeight: 900, color: C.white, margin: "0 0 16px", lineHeight: 1.15 }}>
            Your Business.
            <br /><GradientText from={C.purple} to={C.cyan}>Fully Automated.</GradientText>
          </h2>
        </Pop>
        <Pop delay={20} direction="up">
          <p style={{ fontSize: 24, color: C.gray, margin: "0 0 40px", maxWidth: 600, marginLeft: "auto", marginRight: "auto" }}>
            AI receptionist. Smart scheduling. Invoicing. Worker management. All for €99/month.
          </p>
        </Pop>
        <Pop delay={30} direction="scale">
          <div style={{
            display: "inline-block",
            background: `linear-gradient(135deg, ${C.purple}, ${C.cyan})`,
            borderRadius: 18, padding: "22px 56px",
            transform: `scale(${btnScale})`,
            boxShadow: `0 0 ${50 * glow}px ${C.purpleGlow}, 0 0 ${80 * glow}px ${C.cyanGlow}`,
          }}>
            <span style={{ fontSize: 26, fontWeight: 900, color: C.white }}>
              Get Started →
            </span>
          </div>
        </Pop>
        <Pop delay={45} direction="up">
          <p style={{ fontSize: 18, color: C.gray, marginTop: 20 }}>We handle the setup for you</p>
        </Pop>
        <Pop delay={55} direction="up">
          <p style={{ fontSize: 22, fontWeight: 700, color: C.purpleLight, marginTop: 16 }}>bookedforyou.ie</p>
        </Pop>
      </div>
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════════════
// SCENE TRANSITION
// ═══════════════════════════════════════════════════════════
const Transition: React.FC<{
  children: React.ReactNode;
  durationInFrames: number;
  fadeIn?: number;
  fadeOut?: number;
}> = ({ children, durationInFrames, fadeIn = 10, fadeOut = 10 }) => {
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
// MAIN COMPOSITION
// ═══════════════════════════════════════════════════════════
export const FeatureDeepDive: React.FC = () => {
  const scenes = [
    { component: IntroScene, duration: 120 },          // 4s
    { component: AIPhoneScene, duration: 180 },         // 6s
    { component: CalendarScene, duration: 150 },        // 5s
    { component: CustomersScene, duration: 135 },       // 4.5s
    { component: FinancesScene, duration: 150 },        // 5s
    { component: WorkersScene, duration: 135 },         // 4.5s
    { component: ServicesAndSMSScene, duration: 150 },  // 5s
    { component: OnboardingScene, duration: 150 },      // 5s
    { component: StatsScene, duration: 120 },           // 4s
    { component: FinalCTAScene, duration: 135 },        // 4.5s
  ];

  let startFrame = 0;
  return (
    <AbsoluteFill style={{ fontFamily: "'Inter', 'SF Pro Display', -apple-system, sans-serif" }}>
      <ParticleBackground />
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
