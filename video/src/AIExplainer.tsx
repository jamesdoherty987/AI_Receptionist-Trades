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
  orangeGlow: "rgba(255, 107, 53, 0.25)",
  pink: "#ff006e",
  blue: "#3a86ff",
  blueGlow: "rgba(58, 134, 255, 0.25)",
  gold: "#ffd60a",
  red: "#ff4757",
  white: "#ffffff",
  gray: "#94a3b8",
  lightGray: "#cbd5e1",
  card: "rgba(255,255,255,0.05)",
  cardBorder: "rgba(255,255,255,0.08)",
};

const FONT = "'Inter', 'SF Pro Display', -apple-system, sans-serif";

const StarField: React.FC = () => {
  const frame = useCurrentFrame();
  const stars = Array.from({ length: 70 }, (_, i) => {
    const seed = i * 137.508;
    return {
      x: (seed * 7.3) % 100,
      y: ((seed * 3.1 + frame * (0.25 + (i % 4) * 0.12)) % 125) - 12,
      size: 1 + (i % 3) * 1.1,
      opacity: 0.06 + (i % 5) * 0.05,
    };
  });
  return (
    <AbsoluteFill>
      <div style={{ width: "100%", height: "100%", background: `radial-gradient(ellipse at 50% 30%, ${C.bg2}, ${C.bg1} 70%)` }} />
      {stars.map((s, i) => (
        <div key={i} style={{
          position: "absolute", left: `${s.x}%`, top: `${s.y}%`,
          width: s.size, height: s.size, borderRadius: "50%",
          backgroundColor: i % 2 === 0 ? C.purpleLight : C.cyan,
          opacity: s.opacity,
        }} />
      ))}
    </AbsoluteFill>
  );
};

const Orbs: React.FC<{ colors?: string[] }> = ({ colors = [C.purpleGlow, C.cyanGlow] }) => {
  const frame = useCurrentFrame();
  return (
    <>
      {colors.map((color, i) => {
        const angle = frame * 0.007 + (i * Math.PI * 2) / colors.length;
        const x = 50 + Math.sin(angle) * 22;
        const y = 50 + Math.cos(angle * 0.7) * 18;
        return (
          <div key={i} style={{
            position: "absolute", width: 480, height: 480, borderRadius: "50%",
            background: `radial-gradient(circle, ${color}, transparent 65%)`,
            left: `${x}%`, top: `${y}%`, transform: "translate(-50%, -50%)",
            filter: "blur(65px)", pointerEvents: "none",
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
    up: `translateY(${interpolate(p, [0, 1], [55, 0])}px)`,
    down: `translateY(${interpolate(p, [0, 1], [-55, 0])}px)`,
    left: `translateX(${interpolate(p, [0, 1], [70, 0])}px)`,
    right: `translateX(${interpolate(p, [0, 1], [-70, 0])}px)`,
    scale: `scale(${interpolate(p, [0, 1], [0.3, 1])})`,
    none: "",
  };
  return <div style={{ opacity, transform: map[direction], ...style }}>{children}</div>;
};

const Grad: React.FC<{ children: React.ReactNode; from?: string; to?: string; style?: React.CSSProperties }> = ({
  children, from = C.purple, to = C.cyan, style,
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
// SCENE 1: "How It Works" — Title card
// ═══════════════════════════════════════════════════════════
const HowItWorksIntro: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const logoScale = spring({ frame: frame - 5, fps, config: { damping: 8, mass: 0.3, stiffness: 200 } });
  // Animated connection lines
  const lineProgress = interpolate(frame, [30, 70], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const nodes = [
    { icon: "📞", label: "Customer Calls", x: 200, y: 420 },
    { icon: "🤖", label: "AI Answers", x: 960, y: 420 },
    { icon: "📅", label: "Job Booked", x: 1720, y: 420 },
  ];
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <Orbs colors={[C.purpleGlow, C.cyanGlow, C.blueGlow]} />
      <div style={{ textAlign: "center", zIndex: 2 }}>
        <div style={{ transform: `scale(${logoScale})`, marginBottom: 16 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 16 }}>
            <div style={{
              width: 68, height: 68, borderRadius: 18,
              background: `linear-gradient(135deg, ${C.purple}, ${C.cyan})`,
              display: "flex", alignItems: "center", justifyContent: "center", fontSize: 36,
              boxShadow: `0 0 50px ${C.purpleGlow}, 0 0 100px ${C.cyanGlow}`,
            }}>⚡</div>
            <span style={{ fontSize: 54, fontWeight: 900, color: C.white, letterSpacing: -2 }}>BookedForYou</span>
          </div>
        </div>
        <Pop delay={12} direction="up">
          <h2 style={{ fontSize: 56, fontWeight: 900, color: C.white, margin: "0 0 8px" }}>
            How <Grad>AI Booking</Grad> Works
          </h2>
        </Pop>
        <Pop delay={18} direction="up">
          <p style={{ fontSize: 24, color: C.gray, margin: "0 0 50px" }}>
            From phone call to booked job in under 3 minutes
          </p>
        </Pop>
        {/* Flow diagram */}
        <div style={{ position: "relative", width: 1920, height: 120, left: "50%", transform: "translateX(-50%)" }}>
          {/* Connection lines */}
          <svg style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%", pointerEvents: "none" }}>
            <line x1={nodes[0].x + 40} y1={50} x2={nodes[0].x + 40 + (nodes[1].x - nodes[0].x) * lineProgress} y2={50}
              stroke={C.cyan} strokeWidth={3} opacity={0.6} strokeDasharray="8 4" />
            {lineProgress > 0.5 && (
              <line x1={nodes[1].x + 40} y1={50} x2={nodes[1].x + 40 + (nodes[2].x - nodes[1].x) * Math.max(0, (lineProgress - 0.5) * 2)} y2={50}
                stroke={C.purple} strokeWidth={3} opacity={0.6} strokeDasharray="8 4" />
            )}
          </svg>
          {nodes.map((n, i) => (
            <Pop key={i} delay={25 + i * 12} direction="scale" style={{ position: "absolute", left: n.x - 40, top: 10 }}>
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
                <div style={{
                  width: 80, height: 80, borderRadius: 22,
                  background: C.card, border: `1px solid ${C.cardBorder}`,
                  display: "flex", alignItems: "center", justifyContent: "center", fontSize: 36,
                  boxShadow: `0 0 20px ${i === 1 ? C.cyanGlow : C.purpleGlow}`,
                }}>{n.icon}</div>
                <span style={{ fontSize: 15, fontWeight: 700, color: C.lightGray }}>{n.label}</span>
              </div>
            </Pop>
          ))}
        </div>
      </div>
    </AbsoluteFill>
  );
};


// ═══════════════════════════════════════════════════════════
// SCENE 2: STEP 1 — Customer calls, phone rings
// ═══════════════════════════════════════════════════════════
const Step1CustomerCalls: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const phoneScale = spring({ frame: frame - 5, fps, config: { damping: 10, mass: 0.5 } });
  const ring = frame < 50 ? Math.sin(frame * 1.2) * 3 : 0;
  // Pulse rings
  const rings = [0, 1, 2].map(i => ({
    scale: interpolate((frame + i * 18) % 55, [0, 55], [1, 2.5]),
    opacity: interpolate((frame + i * 18) % 55, [0, 55], [0.5, 0]),
  }));
  // Call forwarding arrow
  const arrowProgress = interpolate(frame, [50, 80], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <Orbs colors={[C.orangeGlow, C.purpleGlow]} />
      <div style={{ display: "flex", gap: 60, alignItems: "center", zIndex: 1, padding: "0 100px" }}>
        {/* Left: Customer's phone */}
        <div style={{ flex: 1, textAlign: "center" }}>
          <Pop delay={0} direction="up">
            <div style={{
              display: "inline-flex", padding: "6px 18px", borderRadius: 10,
              background: `${C.orange}15`, border: `1px solid ${C.orange}33`,
              fontSize: 14, fontWeight: 700, color: C.orange, marginBottom: 16,
            }}>Step 1</div>
          </Pop>
          <Pop delay={5} direction="up">
            <h2 style={{ fontSize: 44, fontWeight: 900, color: C.white, margin: "0 0 24px" }}>
              Customer <Grad from={C.orange} to={C.gold}>Calls You</Grad>
            </h2>
          </Pop>
          <Pop delay={10} direction="scale">
            <div style={{ position: "relative", display: "inline-block" }}>
              {rings.map((r, i) => (
                <div key={i} style={{
                  position: "absolute", width: 200, height: 200, borderRadius: "50%",
                  border: `2px solid ${C.orange}`, transform: `scale(${r.scale})`, opacity: r.opacity,
                  top: "50%", left: "50%", marginTop: -100, marginLeft: -100,
                }} />
              ))}
              <div style={{
                width: 200, height: 340, borderRadius: 32,
                background: "linear-gradient(180deg, #1a1a3e, #0f0c29)",
                border: `2px solid ${C.orange}44`,
                transform: `scale(${phoneScale}) rotate(${ring}deg)`,
                boxShadow: `0 20px 60px rgba(0,0,0,0.5), 0 0 30px ${C.orangeGlow}`,
                display: "flex", flexDirection: "column", alignItems: "center",
                justifyContent: "center", padding: 20, margin: "0 auto",
              }}>
                <div style={{ position: "absolute", top: 10, width: 60, height: 5, borderRadius: 3, background: "rgba(255,255,255,0.1)" }} />
                <span style={{ fontSize: 48, marginBottom: 10 }}>📱</span>
                <p style={{ fontSize: 16, fontWeight: 800, color: C.white, margin: "0 0 4px" }}>Calling...</p>
                <p style={{ fontSize: 13, color: C.gray, margin: 0 }}>Your Business</p>
              </div>
            </div>
          </Pop>
        </div>
        {/* Arrow */}
        <div style={{ width: 120, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div style={{
            width: `${arrowProgress * 100}%`, height: 4, borderRadius: 2,
            background: `linear-gradient(90deg, ${C.orange}, ${C.cyan})`,
            position: "relative",
          }}>
            {arrowProgress > 0.8 && (
              <div style={{
                position: "absolute", right: -8, top: -6,
                width: 0, height: 0,
                borderTop: "8px solid transparent",
                borderBottom: "8px solid transparent",
                borderLeft: `12px solid ${C.cyan}`,
              }} />
            )}
          </div>
        </div>
        {/* Right: AI picks up */}
        <div style={{ flex: 1, textAlign: "center" }}>
          <Pop delay={50} direction="right">
            <div style={{
              width: 200, height: 340, borderRadius: 32, margin: "0 auto",
              background: "linear-gradient(180deg, #1a1a3e, #0f0c29)",
              border: `2px solid ${C.cyan}44`,
              boxShadow: `0 20px 60px rgba(0,0,0,0.5), 0 0 40px ${C.cyanGlow}`,
              display: "flex", flexDirection: "column", alignItems: "center",
              justifyContent: "center", padding: 20,
            }}>
              <div style={{ position: "absolute", top: 10, width: 60, height: 5, borderRadius: 3, background: "rgba(255,255,255,0.1)" }} />
              <div style={{
                width: 60, height: 60, borderRadius: "50%",
                background: `linear-gradient(135deg, ${C.purple}, ${C.cyan})`,
                display: "flex", alignItems: "center", justifyContent: "center", fontSize: 28,
                boxShadow: `0 0 25px ${C.cyanGlow}`,
                marginBottom: 10,
              }}>🤖</div>
              <p style={{ fontSize: 16, fontWeight: 800, color: C.cyan, margin: "0 0 4px" }}>AI Answers</p>
              <p style={{ fontSize: 13, color: C.gray, margin: 0 }}>Instantly</p>
              {/* Sound wave */}
              <div style={{ display: "flex", gap: 2, alignItems: "center", height: 30, marginTop: 12 }}>
                {Array.from({ length: 8 }, (_, i) => (
                  <div key={i} style={{
                    width: 3, borderRadius: 2,
                    height: 8 + Math.sin(frame * 0.25 + i * 0.6) * 8,
                    background: `linear-gradient(180deg, ${C.cyan}, ${C.purple})`,
                  }} />
                ))}
              </div>
            </div>
          </Pop>
          <Pop delay={60} direction="up">
            <p style={{ fontSize: 18, color: C.gray, marginTop: 16 }}>
              Call forwarded to your <span style={{ color: C.cyan, fontWeight: 700 }}>AI number</span>
            </p>
          </Pop>
        </div>
      </div>
    </AbsoluteFill>
  );
};


// ═══════════════════════════════════════════════════════════
// SCENE 3: STEP 2 — AI has the conversation
// ═══════════════════════════════════════════════════════════
const Step2AIConverses: React.FC = () => {
  const frame = useCurrentFrame();
  const messages = [
    { from: "ai", text: "Good morning! O'Brien Plumbing, how can I help you today?", delay: 8 },
    { from: "cust", text: "Hi, I've got a burst pipe in my kitchen — water everywhere!", delay: 30 },
    { from: "ai", text: "I'm sorry to hear that! Let me get an emergency callout booked for you right away. Can I get your name?", delay: 52 },
    { from: "cust", text: "John Murphy", delay: 75 },
    { from: "ai", text: "That's J-O-H-N M-U-R-P-H-Y — is that correct?", delay: 90 },
    { from: "cust", text: "Yes, that's right", delay: 108 },
    { from: "ai", text: "And what's the best address for the job?", delay: 120 },
    { from: "cust", text: "42 Oak Street, Dublin 6", delay: 138 },
    { from: "ai", text: "I have Mike available Thursday at 10 AM for a 2-hour emergency callout. Shall I book that in?", delay: 155 },
    { from: "cust", text: "Yes please, book it!", delay: 178 },
  ];
  // AI processing indicators
  const techStack = [
    { icon: "🧠", label: "GPT-4o", sublabel: "Understanding intent", delay: 15 },
    { icon: "🎤", label: "Deepgram", sublabel: "Speech-to-text", delay: 35 },
    { icon: "🗣️", label: "TTS Engine", sublabel: "Natural voice", delay: 55 },
    { icon: "📅", label: "Calendar API", sublabel: "Checking availability", delay: 100 },
    { icon: "👤", label: "CRM Lookup", sublabel: "Customer matching", delay: 70 },
  ];
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <Orbs colors={[C.purpleGlow, C.cyanGlow, C.blueGlow]} />
      <div style={{ display: "flex", gap: 40, alignItems: "flex-start", zIndex: 1, padding: "40px 60px", width: "100%" }}>
        {/* Left: Chat */}
        <Pop delay={0} direction="left" style={{ flex: 1, maxWidth: 580 }}>
          <div style={{
            background: C.card, border: `1px solid ${C.cardBorder}`, borderRadius: 24,
            padding: 24, backdropFilter: "blur(20px)", height: 580, overflow: "hidden",
            boxShadow: `0 20px 60px rgba(0,0,0,0.4), 0 0 30px ${C.purpleGlow}`,
          }}>
            <div style={{
              display: "inline-flex", padding: "5px 14px", borderRadius: 8,
              background: `${C.purple}15`, border: `1px solid ${C.purple}33`,
              fontSize: 13, fontWeight: 700, color: C.purple, marginBottom: 14,
            }}>Step 2 — AI Conversation</div>
            {/* Header */}
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16, paddingBottom: 12, borderBottom: `1px solid ${C.cardBorder}` }}>
              <div style={{
                width: 40, height: 40, borderRadius: "50%",
                background: `linear-gradient(135deg, ${C.purple}, ${C.cyan})`,
                display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20,
                boxShadow: `0 0 12px ${C.purpleGlow}`,
              }}>🤖</div>
              <div>
                <p style={{ fontSize: 15, fontWeight: 800, color: C.white, margin: 0 }}>AI Receptionist</p>
                <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                  <div style={{ width: 7, height: 7, borderRadius: "50%", background: C.cyan, boxShadow: `0 0 6px ${C.cyan}` }} />
                  <p style={{ fontSize: 12, color: C.cyan, margin: 0, fontWeight: 600 }}>Live Call</p>
                </div>
              </div>
              <div style={{ marginLeft: "auto", display: "flex", gap: 2, alignItems: "center" }}>
                {Array.from({ length: 8 }, (_, i) => (
                  <div key={i} style={{
                    width: 3, borderRadius: 2,
                    background: `linear-gradient(180deg, ${C.cyan}, ${C.purple})`,
                    height: 6 + Math.sin(frame * 0.2 + i * 0.7) * 7,
                  }} />
                ))}
              </div>
            </div>
            {/* Messages */}
            <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
              {messages.map((m, i) => {
                const opacity = interpolate(frame, [m.delay, m.delay + 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
                const y = interpolate(frame, [m.delay, m.delay + 8], [10, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
                const isAI = m.from === "ai";
                return (
                  <div key={i} style={{ opacity, transform: `translateY(${y}px)`, alignSelf: isAI ? "flex-start" : "flex-end", maxWidth: "82%" }}>
                    <div style={{
                      padding: "9px 14px", borderRadius: isAI ? "14px 14px 14px 4px" : "14px 14px 4px 14px",
                      background: isAI ? `${C.purple}15` : `${C.cyan}12`,
                      border: `1px solid ${isAI ? C.purple : C.cyan}22`,
                      fontSize: 13, color: C.white, lineHeight: 1.45,
                    }}>{m.text}</div>
                  </div>
                );
              })}
            </div>
          </div>
        </Pop>
        {/* Right: Tech stack */}
        <div style={{ flex: 1 }}>
          <Pop delay={5} direction="right">
            <h2 style={{ fontSize: 42, fontWeight: 900, color: C.white, margin: "0 0 8px", lineHeight: 1.15 }}>
              Powered by <Grad>AI Intelligence</Grad>
            </h2>
            <p style={{ fontSize: 18, color: C.gray, margin: "0 0 28px", lineHeight: 1.5 }}>
              Multiple AI systems work together in real-time to understand, respond, and take action.
            </p>
          </Pop>
          {techStack.map((t, i) => (
            <Pop key={i} delay={t.delay} direction="left">
              <div style={{
                display: "flex", alignItems: "center", gap: 16, marginBottom: 16,
                background: C.card, border: `1px solid ${C.cardBorder}`,
                borderRadius: 16, padding: "14px 18px",
                boxShadow: `0 4px 20px rgba(0,0,0,0.2)`,
              }}>
                <div style={{
                  width: 50, height: 50, borderRadius: 14,
                  background: `${C.purple}12`, border: `1px solid ${C.purple}22`,
                  display: "flex", alignItems: "center", justifyContent: "center", fontSize: 24,
                }}>{t.icon}</div>
                <div>
                  <p style={{ fontSize: 17, fontWeight: 800, color: C.white, margin: 0 }}>{t.label}</p>
                  <p style={{ fontSize: 14, color: C.gray, margin: 0 }}>{t.sublabel}</p>
                </div>
                {/* Active indicator */}
                <div style={{
                  marginLeft: "auto", width: 10, height: 10, borderRadius: "50%",
                  background: C.cyan, boxShadow: `0 0 8px ${C.cyan}`,
                  transform: `scale(${interpolate(Math.sin(frame * 0.15 + i), [-1, 1], [0.7, 1.3])})`,
                }} />
              </div>
            </Pop>
          ))}
        </div>
      </div>
    </AbsoluteFill>
  );
};


// ═══════════════════════════════════════════════════════════
// SCENE 4: STEP 3 — Booking confirmed, everything auto-happens
// ═══════════════════════════════════════════════════════════
const Step3BookingConfirmed: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  // Checkmark animation
  const checkScale = spring({ frame: frame - 5, fps, config: { damping: 6, mass: 0.3, stiffness: 250 } });
  // Cascade of automated actions
  const actions = [
    { icon: "📅", title: "Calendar Updated", desc: "Job added to Thursday 10 AM slot", color: C.blue, delay: 20 },
    { icon: "👤", title: "Customer Saved", desc: "John Murphy added to CRM with phone & address", color: C.pink, delay: 35 },
    { icon: "👷", title: "Worker Assigned", desc: "Mike O'Brien notified of new job", color: C.purple, delay: 50 },
    { icon: "💬", title: "SMS Confirmation", desc: "Customer receives booking confirmation text", color: C.cyan, delay: 65 },
    { icon: "⏰", title: "Reminder Scheduled", desc: "24-hour reminder queued for Wednesday", color: C.orange, delay: 80 },
    { icon: "📊", title: "Revenue Tracked", desc: "€150 emergency callout logged to finances", color: C.gold, delay: 95 },
  ];
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <Orbs colors={[C.cyanGlow, C.purpleGlow, C.blueGlow]} />
      <div style={{ zIndex: 1, width: "100%", padding: "0 60px" }}>
        {/* Big checkmark */}
        <div style={{ textAlign: "center", marginBottom: 30 }}>
          <Pop delay={0} direction="scale">
            <div style={{
              display: "inline-flex", alignItems: "center", gap: 16,
              transform: `scale(${checkScale})`,
            }}>
              <div style={{
                width: 72, height: 72, borderRadius: "50%",
                background: `linear-gradient(135deg, ${C.cyan}, ${C.purple})`,
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 36, boxShadow: `0 0 40px ${C.cyanGlow}, 0 0 80px ${C.purpleGlow}`,
              }}>✅</div>
              <div style={{ textAlign: "left" }}>
                <div style={{
                  display: "inline-flex", padding: "4px 14px", borderRadius: 8,
                  background: `${C.cyan}15`, border: `1px solid ${C.cyan}33`,
                  fontSize: 13, fontWeight: 700, color: C.cyan, marginBottom: 4,
                }}>Step 3</div>
                <h2 style={{ fontSize: 44, fontWeight: 900, color: C.white, margin: 0 }}>
                  <Grad from={C.cyan} to={C.purple}>Booking Confirmed!</Grad>
                </h2>
              </div>
            </div>
          </Pop>
          <Pop delay={8} direction="up">
            <p style={{ fontSize: 20, color: C.gray, marginTop: 8 }}>
              Everything happens automatically — zero manual work
            </p>
          </Pop>
        </div>
        {/* Action cascade */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16, maxWidth: 1100, margin: "0 auto" }}>
          {actions.map((a, i) => {
            const opacity = interpolate(frame, [a.delay, a.delay + 10], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            const y = interpolate(frame, [a.delay, a.delay + 10], [25, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            return (
              <div key={i} style={{
                opacity, transform: `translateY(${y}px)`,
                background: C.card, border: `1px solid ${a.color}22`,
                borderRadius: 18, padding: "18px 18px",
                boxShadow: `0 0 15px ${a.color}10`,
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
                  <div style={{
                    width: 42, height: 42, borderRadius: 12,
                    background: `${a.color}15`, border: `1px solid ${a.color}33`,
                    display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20,
                  }}>{a.icon}</div>
                  <span style={{ fontSize: 16, fontWeight: 800, color: C.white }}>{a.title}</span>
                </div>
                <p style={{ fontSize: 14, color: C.gray, margin: 0, lineHeight: 1.4 }}>{a.desc}</p>
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};


// ═══════════════════════════════════════════════════════════
// SCENE 5: STEP 4 — SMS reminder flow
// ═══════════════════════════════════════════════════════════
const Step4SMSReminder: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const phoneY = spring({ frame: frame - 5, fps, config: { damping: 14, mass: 0.6 } });
  const notifDrop = spring({ frame: frame - 25, fps, config: { damping: 10, mass: 0.4, stiffness: 180 } });
  const replyOpacity = interpolate(frame, [70, 82], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const confirmScale = spring({ frame: frame - 90, fps, config: { damping: 8, mass: 0.3, stiffness: 200 } });
  // Timeline
  const timeline = [
    { time: "Day of Booking", event: "Confirmation SMS sent", icon: "✅", done: frame > 10 },
    { time: "24 Hours Before", event: "Reminder SMS sent", icon: "⏰", done: frame > 30 },
    { time: "Customer Replies", event: "YES — Confirmed", icon: "💬", done: frame > 75 },
    { time: "Job Day", event: "Worker arrives on time", icon: "👷", done: frame > 95 },
  ];
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <Orbs colors={[C.cyanGlow, C.blueGlow]} />
      <div style={{ display: "flex", gap: 60, alignItems: "center", zIndex: 1, padding: "0 80px" }}>
        {/* Phone with SMS */}
        <Pop delay={0} direction="left" style={{ transform: `translateY(${interpolate(phoneY, [0, 1], [60, 0])}px)` }}>
          <div style={{
            width: 260, height: 460, borderRadius: 36,
            background: "linear-gradient(180deg, #1a1a3e, #0f0c29)",
            border: `2px solid ${C.cyan}33`,
            boxShadow: `0 20px 70px rgba(0,0,0,0.5), 0 0 35px ${C.cyanGlow}`,
            display: "flex", flexDirection: "column", padding: 22, position: "relative",
          }}>
            <div style={{ position: "absolute", top: 12, left: "50%", transform: "translateX(-50%)", width: 70, height: 5, borderRadius: 3, background: "rgba(255,255,255,0.1)" }} />
            <div style={{ marginTop: 28, flex: 1, display: "flex", flexDirection: "column", gap: 10 }}>
              {/* SMS notification */}
              <div style={{
                transform: `translateY(${interpolate(notifDrop, [0, 1], [-25, 0])}px)`,
                opacity: interpolate(notifDrop, [0, 1], [0, 1]),
                background: `${C.cyan}10`, border: `1px solid ${C.cyan}30`,
                borderRadius: "16px 16px 16px 4px", padding: "12px 16px",
              }}>
                <p style={{ fontSize: 10, color: C.cyan, fontWeight: 700, margin: "0 0 5px" }}>📱 BookedForYou</p>
                <p style={{ fontSize: 12, color: C.lightGray, margin: 0, lineHeight: 1.5 }}>
                  Hi John! Reminder: Emergency Pipe Repair tomorrow at 10:00 AM with O'Brien Plumbing. Reply YES to confirm or RESCHEDULE to change.
                </p>
              </div>
              {/* Reply */}
              <div style={{
                opacity: replyOpacity, alignSelf: "flex-end",
                background: `${C.purple}18`, border: `1px solid ${C.purple}30`,
                borderRadius: "16px 16px 4px 16px", padding: "10px 16px",
              }}>
                <p style={{ fontSize: 13, color: C.white, margin: 0, fontWeight: 700 }}>YES ✅</p>
              </div>
              {/* Confirmed */}
              <div style={{
                transform: `scale(${confirmScale})`, alignSelf: "flex-start",
                background: `${C.cyan}12`, border: `1px solid ${C.cyan}40`,
                borderRadius: "16px 16px 16px 4px", padding: "10px 16px",
              }}>
                <p style={{ fontSize: 12, color: C.cyan, margin: 0, fontWeight: 700 }}>✅ Confirmed! See you tomorrow at 10 AM.</p>
              </div>
            </div>
          </div>
        </Pop>
        {/* Right: Timeline */}
        <div style={{ flex: 1 }}>
          <Pop delay={0} direction="right">
            <div style={{
              display: "inline-flex", padding: "5px 14px", borderRadius: 8,
              background: `${C.cyan}15`, border: `1px solid ${C.cyan}33`,
              fontSize: 13, fontWeight: 700, color: C.cyan, marginBottom: 12,
            }}>Step 4</div>
            <h2 style={{ fontSize: 44, fontWeight: 900, color: C.white, margin: "0 0 8px", lineHeight: 1.15 }}>
              Automatic <Grad from={C.cyan} to={C.blue}>Follow-Up</Grad>
            </h2>
            <p style={{ fontSize: 18, color: C.gray, margin: "0 0 28px" }}>
              SMS reminders reduce no-shows by 80%
            </p>
          </Pop>
          {/* Timeline */}
          <div style={{ position: "relative", paddingLeft: 30 }}>
            {/* Vertical line */}
            <div style={{
              position: "absolute", left: 14, top: 0, bottom: 0, width: 2,
              background: C.cardBorder,
            }} />
            {timeline.map((t, i) => {
              const delay = 10 + i * 20;
              const opacity = interpolate(frame, [delay, delay + 10], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
              return (
                <div key={i} style={{ opacity, display: "flex", alignItems: "flex-start", gap: 16, marginBottom: 22, position: "relative" }}>
                  <div style={{
                    width: 30, height: 30, borderRadius: "50%",
                    background: t.done ? `linear-gradient(135deg, ${C.purple}, ${C.cyan})` : C.card,
                    border: `2px solid ${t.done ? "transparent" : C.cardBorder}`,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: 14, position: "absolute", left: -16,
                    boxShadow: t.done ? `0 0 12px ${C.cyanGlow}` : "none",
                  }}>{t.done ? "✓" : ""}</div>
                  <div style={{ marginLeft: 24 }}>
                    <p style={{ fontSize: 13, fontWeight: 700, color: C.cyan, margin: "0 0 2px" }}>{t.time}</p>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontSize: 16 }}>{t.icon}</span>
                      <p style={{ fontSize: 17, fontWeight: 700, color: C.white, margin: 0 }}>{t.event}</p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};


// ═══════════════════════════════════════════════════════════
// SCENE 6: WHAT MAKES IT SPECIAL — differentiators
// ═══════════════════════════════════════════════════════════
const WhatMakesItSpecial: React.FC = () => {
  const frame = useCurrentFrame();
  const differentiators = [
    {
      icon: "🔄", title: "Handles Rescheduling", color: C.blue,
      desc: "Customer wants to change? AI checks availability and rebooks — no human needed.",
    },
    {
      icon: "🚨", title: "Emergency Detection", color: C.red,
      desc: "Detects urgent vs scheduled jobs. Prioritizes emergencies automatically.",
    },
    {
      icon: "🔍", title: "Returning Customers", color: C.purple,
      desc: "Recognizes repeat callers by phone number. Greets them by name.",
    },
    {
      icon: "📍", title: "Address Verification", color: C.orange,
      desc: "Captures and verifies addresses. Spells back names for accuracy.",
    },
    {
      icon: "👷", title: "Smart Worker Assignment", color: C.cyan,
      desc: "Assigns the right worker based on skills, availability, and location.",
    },
    {
      icon: "🛡️", title: "Conflict Prevention", color: C.gold,
      desc: "Never double-books. Respects time-off, working hours, and travel time.",
    },
  ];
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <Orbs colors={[C.purpleGlow, C.orangeGlow, C.cyanGlow]} />
      <div style={{ zIndex: 1, width: "100%", padding: "0 60px" }}>
        <Pop delay={0} direction="up" style={{ textAlign: "center", marginBottom: 30 }}>
          <h2 style={{ fontSize: 48, fontWeight: 900, color: C.white, margin: "0 0 8px" }}>
            Not Just a <Grad from={C.orange} to={C.pink}>Voicemail</Grad>
          </h2>
          <p style={{ fontSize: 22, color: C.gray }}>
            A fully intelligent receptionist that thinks, decides, and acts.
          </p>
        </Pop>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 18, maxWidth: 1100, margin: "0 auto" }}>
          {differentiators.map((d, i) => {
            const delay = 12 + i * 10;
            const opacity = interpolate(frame, [delay, delay + 10], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            const y = interpolate(frame, [delay, delay + 10], [30, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            return (
              <div key={i} style={{
                opacity, transform: `translateY(${y}px)`,
                background: C.card, border: `1px solid ${d.color}22`,
                borderRadius: 20, padding: "22px 20px",
                boxShadow: `0 0 15px ${d.color}10`,
              }}>
                <div style={{
                  width: 52, height: 52, borderRadius: 16,
                  background: `${d.color}12`, border: `1px solid ${d.color}33`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 26, marginBottom: 14,
                }}>{d.icon}</div>
                <p style={{ fontSize: 18, fontWeight: 800, color: C.white, margin: "0 0 6px" }}>{d.title}</p>
                <p style={{ fontSize: 14, color: C.gray, margin: 0, lineHeight: 1.5 }}>{d.desc}</p>
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};


// ═══════════════════════════════════════════════════════════
// SCENE 7: FINALE — CTA
// ═══════════════════════════════════════════════════════════
const ExplainerFinale: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const logoScale = spring({ frame: frame - 5, fps, config: { damping: 6, mass: 0.3, stiffness: 250 } });
  const btnScale = spring({ frame: frame - 40, fps, config: { damping: 8, mass: 0.4, stiffness: 200 } });
  const glow = interpolate(Math.sin(frame * 0.1), [-1, 1], [0.4, 1]);
  // Burst particles
  const particles = Array.from({ length: 16 }, (_, i) => {
    const angle = (i / 16) * Math.PI * 2;
    const dist = interpolate(frame, [0, 25], [0, 180 + (i % 3) * 60], { extrapolateRight: "clamp" });
    const opacity = interpolate(frame, [0, 12, 35], [0, 1, 0], { extrapolateRight: "clamp" });
    return { x: Math.cos(angle) * dist, y: Math.sin(angle) * dist, opacity, color: i % 3 === 0 ? C.purple : i % 3 === 1 ? C.cyan : C.gold };
  });
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <Orbs colors={[C.purpleGlow, C.cyanGlow, "rgba(255,0,110,0.15)"]} />
      {/* Particles */}
      {particles.map((p, i) => (
        <div key={i} style={{
          position: "absolute", left: "50%", top: "50%",
          transform: `translate(calc(-50% + ${p.x}px), calc(-50% + ${p.y}px))`,
          width: 7, height: 7, borderRadius: "50%",
          background: p.color, opacity: p.opacity,
          boxShadow: `0 0 10px ${p.color}`,
        }} />
      ))}
      <div style={{ textAlign: "center", zIndex: 2 }}>
        <div style={{ transform: `scale(${logoScale})`, marginBottom: 20 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 16 }}>
            <div style={{
              width: 72, height: 72, borderRadius: 18,
              background: `linear-gradient(135deg, ${C.purple}, ${C.cyan})`,
              display: "flex", alignItems: "center", justifyContent: "center", fontSize: 38,
              boxShadow: `0 0 50px ${C.purpleGlow}, 0 0 100px ${C.cyanGlow}`,
            }}>⚡</div>
            <span style={{ fontSize: 56, fontWeight: 900, color: C.white, letterSpacing: -2 }}>BookedForYou</span>
          </div>
        </div>
        <Pop delay={12} direction="up">
          <h2 style={{ fontSize: 54, fontWeight: 900, color: C.white, margin: "0 0 12px", lineHeight: 1.15 }}>
            Your AI receptionist is
            <br /><Grad>ready to work</Grad>
          </h2>
        </Pop>
        {/* Flow summary */}
        <Pop delay={22} direction="up">
          <div style={{ display: "flex", gap: 14, justifyContent: "center", margin: "20px 0 28px" }}>
            {[
              { icon: "📞", label: "Call Comes In" },
              { icon: "→", label: "" },
              { icon: "🤖", label: "AI Answers" },
              { icon: "→", label: "" },
              { icon: "📅", label: "Job Booked" },
              { icon: "→", label: "" },
              { icon: "💬", label: "SMS Sent" },
            ].map((s, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 14 }}>
                {s.icon === "→" ? (
                  <span style={{ fontSize: 20, color: C.gray }}>→</span>
                ) : (
                  <div style={{ textAlign: "center" }}>
                    <div style={{
                      width: 48, height: 48, borderRadius: 14,
                      background: C.card, border: `1px solid ${C.cardBorder}`,
                      display: "flex", alignItems: "center", justifyContent: "center", fontSize: 22,
                      margin: "0 auto 4px",
                    }}>{s.icon}</div>
                    <span style={{ fontSize: 12, fontWeight: 600, color: C.gray }}>{s.label}</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </Pop>
        <Pop delay={30} direction="up">
          <p style={{ fontSize: 22, color: C.gray, margin: "0 0 28px" }}>
            We handle the setup. You handle the business.
          </p>
        </Pop>
        <Pop delay={38} direction="scale">
          <div style={{
            display: "inline-block",
            background: `linear-gradient(135deg, ${C.purple}, ${C.cyan})`,
            borderRadius: 20, padding: "22px 58px",
            transform: `scale(${btnScale})`,
            boxShadow: `0 0 ${55 * glow}px ${C.purpleGlow}, 0 0 ${90 * glow}px ${C.cyanGlow}`,
          }}>
            <span style={{ fontSize: 28, fontWeight: 900, color: C.white }}>Get Started →</span>
          </div>
        </Pop>
        <Pop delay={50} direction="up">
          <p style={{ fontSize: 22, fontWeight: 700, color: C.purpleLight, marginTop: 20 }}>bookedforyou.ie</p>
        </Pop>
      </div>
    </AbsoluteFill>
  );
};


// ═══════════════════════════════════════════════════════════
// MAIN COMPOSITION
// ═══════════════════════════════════════════════════════════
export const AIExplainer: React.FC = () => {
  const scenes = [
    { component: HowItWorksIntro, duration: 120 },        // 4s — title + flow diagram
    { component: Step1CustomerCalls, duration: 135 },      // 4.5s — phone rings, AI picks up
    { component: Step2AIConverses, duration: 240 },        // 8s — full conversation + tech stack
    { component: Step3BookingConfirmed, duration: 165 },   // 5.5s — confirmation cascade
    { component: Step4SMSReminder, duration: 150 },        // 5s — SMS reminder flow
    { component: WhatMakesItSpecial, duration: 150 },      // 5s — differentiators
    { component: ExplainerFinale, duration: 135 },         // 4.5s — CTA
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
