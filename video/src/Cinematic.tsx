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

const FONT = "'Inter', 'SF Pro Display', -apple-system, sans-serif";

// ─── Cinematic background with moving stars ───
const StarField: React.FC = () => {
  const frame = useCurrentFrame();
  const stars = Array.from({ length: 80 }, (_, i) => {
    const seed = i * 137.508;
    return {
      x: (seed * 7.3) % 100,
      y: ((seed * 3.1 + frame * (0.3 + (i % 4) * 0.15)) % 130) - 15,
      size: 1 + (i % 3) * 1.2,
      opacity: 0.1 + (i % 5) * 0.08,
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

// ─── Orbiting glow blobs ───
const OrbBlobs: React.FC<{ colors?: string[]; speed?: number }> = ({ colors = [C.purpleGlow, C.cyanGlow, C.blueGlow], speed = 1 }) => {
  const frame = useCurrentFrame();
  return (
    <>
      {colors.map((color, i) => {
        const angle = frame * 0.008 * speed + (i * Math.PI * 2) / colors.length;
        const x = 50 + Math.sin(angle) * 25;
        const y = 50 + Math.cos(angle * 0.7) * 20;
        return (
          <div key={i} style={{
            position: "absolute", width: 500, height: 500, borderRadius: "50%",
            background: `radial-gradient(circle, ${color}, transparent 65%)`,
            left: `${x}%`, top: `${y}%`, transform: "translate(-50%, -50%)",
            filter: "blur(70px)", pointerEvents: "none",
          }} />
        );
      })}
    </>
  );
};

// ─── Spring pop-in ───
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
    up: `translateY(${interpolate(p, [0, 1], [60, 0])}px)`,
    down: `translateY(${interpolate(p, [0, 1], [-60, 0])}px)`,
    left: `translateX(${interpolate(p, [0, 1], [80, 0])}px)`,
    right: `translateX(${interpolate(p, [0, 1], [-80, 0])}px)`,
    scale: `scale(${interpolate(p, [0, 1], [0.3, 1])})`,
    none: "",
  };
  return <div style={{ opacity, transform: map[direction], ...style }}>{children}</div>;
};

// ─── Gradient text ───
const Grad: React.FC<{ children: React.ReactNode; from?: string; to?: string; style?: React.CSSProperties }> = ({
  children, from = C.purple, to = C.cyan, style,
}) => (
  <span style={{ background: `linear-gradient(135deg, ${from}, ${to})`, WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", ...style }}>{children}</span>
);

// (Typewriter available for future use)


// ═══════════════════════════════════════════════════════════
// SCENE 1: CINEMATIC OPEN — zoom through space into logo
// ═══════════════════════════════════════════════════════════
const CinematicOpen: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  // Zoom effect — starts zoomed out, rushes in
  const zoom = interpolate(frame, [0, 40], [3, 1], { extrapolateRight: "clamp", easing: (t) => 1 - Math.pow(1 - t, 3) });
  const bgOpacity = interpolate(frame, [0, 20], [0, 1], { extrapolateRight: "clamp" });
  const logoScale = spring({ frame: frame - 25, fps, config: { damping: 8, mass: 0.3, stiffness: 200 } });
  // Shockwave ring
  const ringScale = interpolate(frame, [30, 70], [0, 4], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const ringOpacity = interpolate(frame, [30, 70], [0.6, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <div style={{ opacity: bgOpacity, transform: `scale(${zoom})`, width: "100%", height: "100%", position: "absolute" }}>
        <OrbBlobs colors={[C.purpleGlow, C.cyanGlow, C.pinkGlow]} speed={2} />
      </div>
      {/* Shockwave */}
      <div style={{
        position: "absolute", width: 200, height: 200, borderRadius: "50%",
        border: `3px solid ${C.cyan}`, transform: `scale(${ringScale})`, opacity: ringOpacity,
      }} />
      <div style={{
        position: "absolute", width: 200, height: 200, borderRadius: "50%",
        border: `2px solid ${C.purple}`, transform: `scale(${ringScale * 0.8})`, opacity: ringOpacity * 0.7,
      }} />
      <div style={{ textAlign: "center", zIndex: 2, transform: `scale(${logoScale})` }}>
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "center", gap: 18, marginBottom: 20,
        }}>
          <div style={{
            width: 80, height: 80, borderRadius: 20,
            background: `linear-gradient(135deg, ${C.purple}, ${C.cyan})`,
            display: "flex", alignItems: "center", justifyContent: "center", fontSize: 42,
            boxShadow: `0 0 60px ${C.purpleGlow}, 0 0 120px ${C.cyanGlow}`,
          }}>⚡</div>
          <span style={{ fontSize: 64, fontWeight: 900, color: C.white, letterSpacing: -2 }}>BookedForYou</span>
        </div>
      </div>
      <Pop delay={45} direction="up" style={{ position: "absolute", bottom: 180, zIndex: 2 }}>
        <p style={{ fontSize: 28, color: C.gray, textAlign: "center" }}>
          The AI receptionist that <Grad>never sleeps</Grad>
        </p>
      </Pop>
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════════════
// SCENE 2: THE PROBLEM — dramatic missed calls
// ═══════════════════════════════════════════════════════════
const MissedCallsScene: React.FC = () => {
  const frame = useCurrentFrame();
  // Phone vibrating
  const shake = Math.sin(frame * 1.2) * (frame < 60 ? 4 : 0);
  // Missed call counter
  const missedCount = Math.min(Math.floor(interpolate(frame, [10, 80], [0, 12], { extrapolateRight: "clamp" })), 12);
  // Red flash
  const redFlash = interpolate(Math.sin(frame * 0.3), [-1, 1], [0, 0.15]);
  // Revenue counter
  const lostRevenue = Math.floor(interpolate(frame, [40, 100], [0, 4800], { extrapolateRight: "clamp" }));
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <OrbBlobs colors={["rgba(255,0,0,0.15)", C.orangeGlow]} />
      {/* Red overlay flash */}
      <div style={{ position: "absolute", inset: 0, background: `rgba(255,0,50,${redFlash})`, zIndex: 0 }} />
      <div style={{ display: "flex", gap: 80, alignItems: "center", zIndex: 1, padding: "0 100px" }}>
        {/* Phone with missed calls */}
        <Pop delay={0} direction="scale">
          <div style={{
            width: 260, height: 460, borderRadius: 36,
            background: "linear-gradient(180deg, #1a1a3e, #0f0c29)",
            border: `2px solid rgba(255,50,50,0.3)`,
            transform: `rotate(${shake}deg)`,
            boxShadow: `0 20px 60px rgba(0,0,0,0.5), 0 0 40px rgba(255,50,50,0.2)`,
            display: "flex", flexDirection: "column", alignItems: "center",
            justifyContent: "center", padding: 24, position: "relative",
            overflow: "hidden",
          }}>
            <div style={{ position: "absolute", top: 12, width: 70, height: 5, borderRadius: 3, background: "rgba(255,255,255,0.1)" }} />
            {/* Missed call notifications stacking */}
            <div style={{ display: "flex", flexDirection: "column", gap: 6, width: "100%" }}>
              {Array.from({ length: Math.min(missedCount, 5) }, (_, i) => (
                <div key={i} style={{
                  background: "rgba(255,50,50,0.15)", border: "1px solid rgba(255,50,50,0.3)",
                  borderRadius: 12, padding: "8px 12px", display: "flex", alignItems: "center", gap: 8,
                }}>
                  <span style={{ fontSize: 16 }}>📵</span>
                  <div>
                    <p style={{ fontSize: 12, fontWeight: 700, color: "#ff6b6b", margin: 0 }}>Missed Call</p>
                    <p style={{ fontSize: 10, color: C.gray, margin: 0 }}>{`${9 + i}:${15 + i * 7} AM`}</p>
                  </div>
                </div>
              ))}
            </div>
            {/* Badge */}
            {missedCount > 0 && (
              <div style={{
                position: "absolute", top: 30, right: 20,
                width: 36, height: 36, borderRadius: "50%",
                background: "#ff3333", display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 16, fontWeight: 900, color: C.white,
                boxShadow: "0 0 20px rgba(255,50,50,0.6)",
              }}>{missedCount}</div>
            )}
          </div>
        </Pop>
        {/* Right side — dramatic text */}
        <div style={{ flex: 1 }}>
          <Pop delay={5} direction="up">
            <p style={{ fontSize: 20, fontWeight: 700, color: "#ff6b6b", textTransform: "uppercase", letterSpacing: 4, marginBottom: 12 }}>
              Right Now
            </p>
          </Pop>
          <Pop delay={12} direction="up">
            <h2 style={{ fontSize: 56, fontWeight: 900, color: C.white, margin: "0 0 20px", lineHeight: 1.1 }}>
              You're <span style={{ color: "#ff6b6b" }}>losing money</span>
              <br />every time you miss a call
            </h2>
          </Pop>
          <Pop delay={25} direction="up">
            <div style={{
              display: "inline-flex", alignItems: "center", gap: 12,
              background: "rgba(255,50,50,0.1)", border: "1px solid rgba(255,50,50,0.3)",
              borderRadius: 16, padding: "16px 28px",
            }}>
              <span style={{ fontSize: 36 }}>💸</span>
              <div>
                <p style={{ fontSize: 14, color: C.gray, margin: 0 }}>Estimated lost revenue</p>
                <p style={{ fontSize: 36, fontWeight: 900, color: "#ff6b6b", margin: 0 }}>€{lostRevenue.toLocaleString()}</p>
              </div>
            </div>
          </Pop>
          <Pop delay={40} direction="up">
            <p style={{ fontSize: 20, color: C.gray, marginTop: 24, lineHeight: 1.6 }}>
              While you're on a job, under a sink, or up a ladder — your phone keeps ringing. And every unanswered call walks straight to your competitor.
            </p>
          </Pop>
        </div>
      </div>
    </AbsoluteFill>
  );
};


// ═══════════════════════════════════════════════════════════
// SCENE 3: THE SOLUTION — phone answers itself (epic reveal)
// ═══════════════════════════════════════════════════════════
const PhoneAnswersScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  // Phone slides to center and transforms
  const phoneScale = spring({ frame: frame - 5, fps, config: { damping: 10, mass: 0.5 } });
  // Pulse rings expanding outward
  const rings = [0, 1, 2, 3].map(i => ({
    scale: interpolate((frame + i * 15) % 60, [0, 60], [1, 3]),
    opacity: interpolate((frame + i * 15) % 60, [0, 60], [0.5, 0]),
  }));
  // Sound wave bars
  const bars = Array.from({ length: 12 }, (_, i) => ({
    height: 15 + Math.sin(frame * 0.25 + i * 0.6) * 12,
  }));
  // AI text appearing
  const showAI = frame > 40;
  const aiTextOpacity = interpolate(frame, [40, 55], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <OrbBlobs colors={[C.purpleGlow, C.cyanGlow]} speed={1.5} />
      {/* Pulse rings */}
      {rings.map((r, i) => (
        <div key={i} style={{
          position: "absolute", width: 280, height: 280, borderRadius: "50%",
          border: `2px solid ${C.cyan}`, transform: `scale(${r.scale})`, opacity: r.opacity,
        }} />
      ))}
      <div style={{ textAlign: "center", zIndex: 2 }}>
        {/* Phone */}
        <div style={{
          width: 280, height: 500, borderRadius: 40, margin: "0 auto",
          background: "linear-gradient(180deg, #1a1a3e, #0f0c29)",
          border: `2px solid ${C.cyan}44`,
          transform: `scale(${phoneScale})`,
          boxShadow: `0 20px 80px rgba(0,0,0,0.5), 0 0 60px ${C.cyanGlow}, 0 0 120px ${C.purpleGlow}`,
          display: "flex", flexDirection: "column", alignItems: "center",
          justifyContent: "center", padding: 28, position: "relative",
        }}>
          <div style={{ position: "absolute", top: 14, width: 80, height: 6, borderRadius: 3, background: "rgba(255,255,255,0.12)" }} />
          {/* Incoming call UI */}
          <div style={{
            width: 70, height: 70, borderRadius: "50%",
            background: `linear-gradient(135deg, ${C.purple}, ${C.cyan})`,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 32, marginBottom: 14,
            boxShadow: `0 0 30px ${C.cyanGlow}`,
          }}>📞</div>
          <p style={{ fontSize: 20, fontWeight: 800, color: C.white, margin: "0 0 4px" }}>Incoming Call</p>
          <p style={{ fontSize: 14, color: C.gray, margin: "0 0 20px" }}>+353 86 XXX XXXX</p>
          {/* Sound wave */}
          <div style={{ display: "flex", gap: 3, alignItems: "center", height: 40, marginBottom: 16 }}>
            {bars.map((b, i) => (
              <div key={i} style={{
                width: 4, height: b.height, borderRadius: 2,
                background: `linear-gradient(180deg, ${C.cyan}, ${C.purple})`,
              }} />
            ))}
          </div>
          {/* AI Answering badge */}
          {showAI && (
            <div style={{
              opacity: aiTextOpacity,
              background: `linear-gradient(135deg, ${C.purple}, ${C.cyan})`,
              borderRadius: 24, padding: "10px 24px",
              display: "flex", alignItems: "center", gap: 8,
              boxShadow: `0 0 20px ${C.purpleGlow}`,
            }}>
              <div style={{
                width: 10, height: 10, borderRadius: "50%", background: C.cyan,
                boxShadow: `0 0 10px ${C.cyan}`,
                transform: `scale(${interpolate(Math.sin(frame * 0.15), [-1, 1], [0.7, 1.3])})`,
              }} />
              <span style={{ fontSize: 15, fontWeight: 800, color: C.white }}>AI Answering</span>
            </div>
          )}
        </div>
        {/* Text below */}
        <Pop delay={50} direction="up" style={{ marginTop: 30 }}>
          <h2 style={{ fontSize: 44, fontWeight: 900, color: C.white, margin: 0 }}>
            Now it <Grad>answers itself</Grad>
          </h2>
        </Pop>
      </div>
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════════════
// SCENE 4: LIVE CONVERSATION — cinematic chat flow
// ═══════════════════════════════════════════════════════════
const LiveConversationScene: React.FC = () => {
  const frame = useCurrentFrame();
  const messages = [
    { from: "ai", text: "Good morning! O'Brien Plumbing, how can I help?", delay: 5 },
    { from: "customer", text: "Hi, I've got a burst pipe in my kitchen", delay: 30 },
    { from: "ai", text: "A burst pipe — I'll get that sorted for you. Can I get your name?", delay: 55 },
    { from: "customer", text: "John Murphy", delay: 78 },
    { from: "ai", text: "That's J-O-H-N M-U-R-P-H-Y, correct?", delay: 95 },
    { from: "customer", text: "Yes that's right", delay: 112 },
    { from: "ai", text: "I have Thursday at 10am — it's a 2 hour job. Shall I book that in?", delay: 128 },
    { from: "customer", text: "Perfect, book it", delay: 150 },
    { from: "ai", text: "All booked! You'll get a reminder text tomorrow. Anything else?", delay: 165 },
  ];
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <OrbBlobs colors={[C.orangeGlow, C.purpleGlow]} />
      <div style={{ display: "flex", gap: 60, alignItems: "center", zIndex: 1, padding: "0 80px", width: "100%" }}>
        {/* Left: conversation */}
        <div style={{ flex: 1, maxWidth: 550 }}>
          <Pop delay={0} direction="left">
            <div style={{
              background: C.card, border: `1px solid ${C.cardBorder}`, borderRadius: 28,
              padding: 28, backdropFilter: "blur(20px)", height: 520, overflow: "hidden",
              boxShadow: `0 20px 60px rgba(0,0,0,0.4), 0 0 40px ${C.purpleGlow}`,
            }}>
              {/* Header */}
              <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 20, paddingBottom: 16, borderBottom: `1px solid ${C.cardBorder}` }}>
                <div style={{
                  width: 44, height: 44, borderRadius: "50%",
                  background: `linear-gradient(135deg, ${C.purple}, ${C.cyan})`,
                  display: "flex", alignItems: "center", justifyContent: "center", fontSize: 22,
                  boxShadow: `0 0 15px ${C.purpleGlow}`,
                }}>🤖</div>
                <div>
                  <p style={{ fontSize: 17, fontWeight: 800, color: C.white, margin: 0 }}>AI Receptionist</p>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <div style={{ width: 8, height: 8, borderRadius: "50%", background: C.cyan, boxShadow: `0 0 8px ${C.cyan}` }} />
                    <p style={{ fontSize: 13, color: C.cyan, margin: 0, fontWeight: 600 }}>Live Call — 2:34</p>
                  </div>
                </div>
                {/* Waveform */}
                <div style={{ marginLeft: "auto", display: "flex", gap: 2, alignItems: "center" }}>
                  {Array.from({ length: 8 }, (_, i) => (
                    <div key={i} style={{
                      width: 3, borderRadius: 2,
                      background: `linear-gradient(180deg, ${C.cyan}, ${C.purple})`,
                      height: 8 + Math.sin(frame * 0.2 + i * 0.7) * 8,
                    }} />
                  ))}
                </div>
              </div>
              {/* Messages */}
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {messages.map((m, i) => {
                  const opacity = interpolate(frame, [m.delay, m.delay + 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
                  const y = interpolate(frame, [m.delay, m.delay + 8], [12, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
                  const isAI = m.from === "ai";
                  return (
                    <div key={i} style={{ opacity, transform: `translateY(${y}px)`, alignSelf: isAI ? "flex-start" : "flex-end", maxWidth: "82%" }}>
                      <div style={{
                        padding: "10px 16px", borderRadius: isAI ? "16px 16px 16px 4px" : "16px 16px 4px 16px",
                        background: isAI ? `${C.purple}18` : `${C.cyan}15`,
                        border: `1px solid ${isAI ? C.purple : C.cyan}25`,
                        fontSize: 14, color: C.white, lineHeight: 1.5,
                      }}>{m.text}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          </Pop>
        </div>
        {/* Right: feature callouts */}
        <div style={{ flex: 1 }}>
          <Pop delay={10} direction="right">
            <h2 style={{ fontSize: 48, fontWeight: 900, color: C.white, margin: "0 0 24px", lineHeight: 1.15 }}>
              Natural <Grad from={C.orange} to={C.gold}>Conversations</Grad>
            </h2>
          </Pop>
          {[
            { icon: "🧠", text: "GPT-4o powered intelligence", delay: 30 },
            { icon: "🎤", text: "Deepgram speech recognition", delay: 45 },
            { icon: "🗣️", text: "Natural text-to-speech", delay: 60 },
            { icon: "✋", text: "Handles interruptions gracefully", delay: 75 },
            { icon: "📋", text: "Spells back names for accuracy", delay: 90 },
            { icon: "🔍", text: "Recognises returning customers", delay: 105 },
            { icon: "🚨", text: "Detects emergency vs scheduled", delay: 120 },
          ].map((item, i) => (
            <Pop key={i} delay={item.delay} direction="left">
              <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 14 }}>
                <div style={{
                  width: 44, height: 44, borderRadius: 12,
                  background: C.card, border: `1px solid ${C.cardBorder}`,
                  display: "flex", alignItems: "center", justifyContent: "center", fontSize: 22,
                }}>{item.icon}</div>
                <span style={{ fontSize: 19, color: C.lightGray, fontWeight: 600 }}>{item.text}</span>
              </div>
            </Pop>
          ))}
        </div>
      </div>
    </AbsoluteFill>
  );
};


// ═══════════════════════════════════════════════════════════
// SCENE 5: FEATURE ORBIT — icons orbiting around center
// ═══════════════════════════════════════════════════════════
const FeatureOrbitScene: React.FC = () => {
  const frame = useCurrentFrame();
  const features = [
    { icon: "📅", label: "Smart Calendar", color: C.blue },
    { icon: "👥", label: "Customer CRM", color: C.pink },
    { icon: "💰", label: "Invoicing", color: C.gold },
    { icon: "👷", label: "Employees", color: C.purple },
    { icon: "📱", label: "SMS Reminders", color: C.cyan },
    { icon: "🔧", label: "Services", color: C.orange },
    { icon: "📊", label: "Analytics", color: C.blue },
    { icon: "⚙️", label: "Settings", color: C.purpleLight },
  ];
  const centerPulse = interpolate(Math.sin(frame * 0.08), [-1, 1], [0.95, 1.05]);
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <OrbBlobs colors={[C.purpleGlow, C.cyanGlow, C.blueGlow]} speed={0.5} />
      <div style={{ position: "relative", width: 700, height: 700, zIndex: 1 }}>
        {/* Center logo */}
        <div style={{
          position: "absolute", top: "50%", left: "50%",
          transform: `translate(-50%, -50%) scale(${centerPulse})`,
          width: 120, height: 120, borderRadius: 30,
          background: `linear-gradient(135deg, ${C.purple}, ${C.cyan})`,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 52, boxShadow: `0 0 60px ${C.purpleGlow}, 0 0 120px ${C.cyanGlow}`,
          zIndex: 2,
        }}>⚡</div>
        {/* Orbit ring */}
        <div style={{
          position: "absolute", top: "50%", left: "50%",
          width: 500, height: 500, borderRadius: "50%",
          border: `1px solid ${C.cardBorder}`,
          transform: "translate(-50%, -50%)",
        }} />
        {/* Orbiting features */}
        {features.map((f, i) => {
          const angle = (i / features.length) * Math.PI * 2 + frame * 0.012;
          const radius = 250;
          const x = Math.cos(angle) * radius;
          const y = Math.sin(angle) * radius;
          const appearDelay = 10 + i * 6;
          const opacity = interpolate(frame, [appearDelay, appearDelay + 15], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          // Connection line
          const lineOpacity = opacity * 0.3;
          return (
            <React.Fragment key={i}>
              {/* Line from center to icon */}
              <svg style={{ position: "absolute", top: 0, left: 0, width: 700, height: 700, pointerEvents: "none" }}>
                <line
                  x1={350} y1={350}
                  x2={350 + x} y2={350 + y}
                  stroke={f.color} strokeWidth={1} opacity={lineOpacity}
                  strokeDasharray="4 4"
                />
              </svg>
              <div style={{
                position: "absolute",
                top: 350 + y - 35, left: 350 + x - 35,
                width: 70, height: 70, borderRadius: 20,
                background: C.card, border: `1px solid ${f.color}44`,
                display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
                opacity, backdropFilter: "blur(10px)",
                boxShadow: `0 0 20px ${f.color}20`,
              }}>
                <span style={{ fontSize: 28 }}>{f.icon}</span>
              </div>
              {/* Label */}
              <div style={{
                position: "absolute",
                top: 350 + y + 40, left: 350 + x - 50,
                width: 100, textAlign: "center", opacity,
              }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: f.color }}>{f.label}</span>
              </div>
            </React.Fragment>
          );
        })}
      </div>
      {/* Title */}
      <Pop delay={0} direction="up" style={{ position: "absolute", bottom: 80, zIndex: 2 }}>
        <h2 style={{ fontSize: 44, fontWeight: 900, color: C.white, textAlign: "center" }}>
          One platform. <Grad>Every tool you need.</Grad>
        </h2>
      </Pop>
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════════════
// SCENE 6: CALENDAR ZOOM — animated booking slots
// ═══════════════════════════════════════════════════════════
const CalendarZoomScene: React.FC = () => {
  const frame = useCurrentFrame();
  const days = ["Mon", "Tue", "Wed", "Thu", "Fri"];
  const slots = [
    { day: 0, row: 0, h: 2, label: "Pipe Repair — John M.", color: C.blue },
    { day: 1, row: 1, h: 3, label: "Boiler Install — Sarah O.", color: C.purple },
    { day: 2, row: 0, h: 4, label: "Bathroom Refit Day 1", color: C.orange },
    { day: 3, row: 0, h: 4, label: "Bathroom Refit Day 2", color: C.orange },
    { day: 4, row: 0, h: 2, label: "Emergency Leak — Mike K.", color: C.pink },
    { day: 0, row: 3, h: 2, label: "Radiator Flush — Emma W.", color: C.cyan },
    { day: 4, row: 3, h: 2, label: "Kitchen Plumbing — Dave R.", color: C.blue },
  ];
  // New booking flying in
  const newBookingOpacity = interpolate(frame, [80, 95], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const newBookingScale = interpolate(frame, [80, 95], [1.3, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <OrbBlobs colors={[C.blueGlow, C.cyanGlow]} />
      <div style={{ zIndex: 1, textAlign: "center" }}>
        <Pop delay={0} direction="up">
          <h2 style={{ fontSize: 48, fontWeight: 900, color: C.white, margin: "0 0 30px" }}>
            Your week, <Grad from={C.blue} to={C.cyan}>fully booked</Grad>
          </h2>
        </Pop>
        <Pop delay={8} direction="scale">
          <div style={{
            background: C.card, border: `1px solid ${C.cardBorder}`, borderRadius: 24,
            padding: 28, backdropFilter: "blur(20px)", display: "inline-block",
            boxShadow: `0 20px 80px rgba(0,0,0,0.4), 0 0 40px ${C.blueGlow}`,
          }}>
            {/* Day headers */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 160px)", gap: 8, marginBottom: 12 }}>
              {days.map((d, i) => (
                <div key={i} style={{ textAlign: "center", fontSize: 16, fontWeight: 800, color: C.lightGray, padding: "8px 0" }}>{d}</div>
              ))}
            </div>
            {/* Slot grid */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 160px)", gridTemplateRows: "repeat(5, 44px)", gap: 8, position: "relative" }}>
              {slots.map((s, i) => {
                const delay = 18 + i * 8;
                const opacity = interpolate(frame, [delay, delay + 12], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
                return (
                  <div key={i} style={{
                    gridColumn: s.day + 1, gridRow: `${s.row + 1} / span ${s.h}`,
                    background: `${s.color}20`, border: `1px solid ${s.color}44`,
                    borderRadius: 12, padding: "8px 12px", fontSize: 13, fontWeight: 700,
                    color: s.color, opacity, display: "flex", alignItems: "center",
                    boxShadow: `0 0 15px ${s.color}15`,
                  }}>{s.label}</div>
                );
              })}
              {/* New booking appearing with glow */}
              <div style={{
                gridColumn: 2, gridRow: "5 / span 1",
                background: `${C.cyan}25`, border: `2px solid ${C.cyan}`,
                borderRadius: 12, padding: "8px 12px", fontSize: 13, fontWeight: 800,
                color: C.cyan, opacity: newBookingOpacity,
                transform: `scale(${newBookingScale})`,
                boxShadow: `0 0 25px ${C.cyanGlow}`,
                display: "flex", alignItems: "center", gap: 6,
              }}>
                ✨ NEW — Tap Repair — Lisa B.
              </div>
            </div>
          </div>
        </Pop>
        <Pop delay={90} direction="up" style={{ marginTop: 20 }}>
          <div style={{ display: "flex", justifyContent: "center", gap: 20 }}>
            {["Google Calendar Sync", "Multi-day Jobs", "Employee Schedules", "No Double Bookings"].map((t, i) => (
              <div key={i} style={{ padding: "8px 16px", borderRadius: 10, background: `${C.blue}15`, border: `1px solid ${C.blue}33`, fontSize: 14, color: C.blue, fontWeight: 600 }}>{t}</div>
            ))}
          </div>
        </Pop>
      </div>
    </AbsoluteFill>
  );
};


// ═══════════════════════════════════════════════════════════
// SCENE 7: DASHBOARD MONTAGE — rapid feature showcase
// ═══════════════════════════════════════════════════════════
const DashboardMontageScene: React.FC = () => {
  const frame = useCurrentFrame();
  // Cards fly in from different directions in sequence
  const panels = [
    {
      title: "Customer CRM", icon: "👥", color: C.pink, delay: 0, dir: "left" as const,
      items: ["Auto-saved from calls", "Phone & email capture", "Job history per client", "Returning customer detection"],
    },
    {
      title: "Revenue & Invoicing", icon: "💰", color: C.gold, delay: 30, dir: "right" as const,
      items: ["Daily/monthly charts", "Stripe payment links", "One-click invoices", "Paid vs unpaid tracking"],
    },
    {
      title: "Employee Management", icon: "👷", color: C.purple, delay: 60, dir: "left" as const,
      items: ["Assign jobs to team", "Service restrictions", "Weekly hours tracking", "Conflict prevention"],
    },
    {
      title: "Services & Pricing", icon: "🔧", color: C.orange, delay: 90, dir: "right" as const,
      items: ["Custom service menu", "Duration & pricing", "Image uploads", "Callout services"],
    },
  ];
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <OrbBlobs colors={[C.purpleGlow, C.pinkGlow, C.orangeGlow]} speed={0.8} />
      <div style={{ zIndex: 1, padding: "0 80px", width: "100%" }}>
        <Pop delay={0} direction="up" style={{ textAlign: "center", marginBottom: 40 }}>
          <h2 style={{ fontSize: 48, fontWeight: 900, color: C.white, margin: 0 }}>
            Your entire business. <Grad from={C.pink} to={C.gold}>One dashboard.</Grad>
          </h2>
        </Pop>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
          {panels.map((p, i) => (
            <Pop key={i} delay={p.delay + 10} direction={p.dir}>
              <div style={{
                background: C.card, border: `1px solid ${p.color}22`,
                borderRadius: 22, padding: "28px 28px", backdropFilter: "blur(20px)",
                boxShadow: `0 10px 40px rgba(0,0,0,0.3), 0 0 20px ${p.color}10`,
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 18 }}>
                  <div style={{
                    width: 48, height: 48, borderRadius: 14,
                    background: `${p.color}20`, border: `1px solid ${p.color}44`,
                    display: "flex", alignItems: "center", justifyContent: "center", fontSize: 24,
                  }}>{p.icon}</div>
                  <span style={{ fontSize: 22, fontWeight: 800, color: C.white }}>{p.title}</span>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  {p.items.map((item, j) => {
                    const itemDelay = p.delay + 18 + j * 5;
                    const opacity = interpolate(frame, [itemDelay, itemDelay + 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
                    return (
                      <div key={j} style={{ display: "flex", alignItems: "center", gap: 10, opacity }}>
                        <div style={{ width: 6, height: 6, borderRadius: "50%", background: p.color, boxShadow: `0 0 8px ${p.color}` }} />
                        <span style={{ fontSize: 16, color: C.lightGray }}>{item}</span>
                      </div>
                    );
                  })}
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
// SCENE 8: SMS REMINDER — phone notification animation
// ═══════════════════════════════════════════════════════════
const SMSReminderScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  // Phone slides up
  const phoneY = spring({ frame: frame - 5, fps, config: { damping: 14, mass: 0.6 } });
  // Notification drops in
  const notifY = spring({ frame: frame - 30, fps, config: { damping: 10, mass: 0.4, stiffness: 180 } });
  // Reply appears
  const replyOpacity = interpolate(frame, [80, 95], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  // Checkmark
  const checkScale = spring({ frame: frame - 100, fps, config: { damping: 8, mass: 0.3, stiffness: 200 } });
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <OrbBlobs colors={[C.cyanGlow, C.blueGlow]} />
      <div style={{ display: "flex", gap: 80, alignItems: "center", zIndex: 1, padding: "0 100px" }}>
        {/* Phone with SMS */}
        <div style={{ transform: `translateY(${interpolate(phoneY, [0, 1], [80, 0])}px)` }}>
          <div style={{
            width: 280, height: 500, borderRadius: 40,
            background: "linear-gradient(180deg, #1a1a3e, #0f0c29)",
            border: `2px solid ${C.cyan}33`,
            boxShadow: `0 20px 80px rgba(0,0,0,0.5), 0 0 40px ${C.cyanGlow}`,
            display: "flex", flexDirection: "column", padding: 24, position: "relative",
          }}>
            <div style={{ position: "absolute", top: 14, left: "50%", transform: "translateX(-50%)", width: 80, height: 6, borderRadius: 3, background: "rgba(255,255,255,0.12)" }} />
            <div style={{ marginTop: 30, flex: 1, display: "flex", flexDirection: "column", gap: 12 }}>
              {/* SMS notification */}
              <div style={{
                transform: `translateY(${interpolate(notifY, [0, 1], [-30, 0])}px)`,
                opacity: interpolate(notifY, [0, 1], [0, 1]),
                background: `${C.cyan}12`, border: `1px solid ${C.cyan}33`,
                borderRadius: "18px 18px 18px 4px", padding: "14px 18px",
              }}>
                <p style={{ fontSize: 11, color: C.cyan, fontWeight: 700, margin: "0 0 6px" }}>📱 BookedForYou</p>
                <p style={{ fontSize: 13, color: C.lightGray, margin: 0, lineHeight: 1.5 }}>
                  Hi John! Reminder: Pipe Repair tomorrow at 10:00 AM with O'Brien Plumbing. Reply YES to confirm or RESCHEDULE to change.
                </p>
              </div>
              {/* Customer reply */}
              <div style={{
                opacity: replyOpacity, alignSelf: "flex-end",
                background: `${C.purple}20`, border: `1px solid ${C.purple}33`,
                borderRadius: "18px 18px 4px 18px", padding: "12px 18px",
              }}>
                <p style={{ fontSize: 14, color: C.white, margin: 0, fontWeight: 700 }}>YES ✅</p>
              </div>
              {/* Confirmed */}
              <div style={{
                transform: `scale(${checkScale})`, alignSelf: "flex-start",
                background: `${C.cyan}15`, border: `1px solid ${C.cyan}44`,
                borderRadius: "18px 18px 18px 4px", padding: "12px 18px",
              }}>
                <p style={{ fontSize: 13, color: C.cyan, margin: 0, fontWeight: 700 }}>✅ Appointment confirmed! See you tomorrow.</p>
              </div>
            </div>
          </div>
        </div>
        {/* Right side */}
        <div style={{ flex: 1 }}>
          <Pop delay={5} direction="right">
            <h2 style={{ fontSize: 50, fontWeight: 900, color: C.white, margin: "0 0 20px", lineHeight: 1.15 }}>
              Automatic
              <br /><Grad from={C.cyan} to={C.blue}>SMS Reminders</Grad>
            </h2>
          </Pop>
          <Pop delay={15} direction="right">
            <p style={{ fontSize: 22, color: C.gray, lineHeight: 1.6, margin: "0 0 30px" }}>
              24 hours before every job, your customer gets a text. They confirm with a simple reply. No-shows drop. Professionalism goes up.
            </p>
          </Pop>
          <Pop delay={30} direction="right">
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {[
                { icon: "⏰", text: "Sent automatically 24hrs before" },
                { icon: "💬", text: "Confirm or reschedule via reply" },
                { icon: "📧", text: "Email reminders too" },
                { icon: "🔄", text: "Handles reschedule requests" },
              ].map((item, i) => (
                <Pop key={i} delay={40 + i * 10} direction="left">
                  <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                    <div style={{
                      width: 44, height: 44, borderRadius: 12,
                      background: `${C.cyan}15`, border: `1px solid ${C.cyan}33`,
                      display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20,
                    }}>{item.icon}</div>
                    <span style={{ fontSize: 19, color: C.lightGray, fontWeight: 600 }}>{item.text}</span>
                  </div>
                </Pop>
              ))}
            </div>
          </Pop>
        </div>
      </div>
    </AbsoluteFill>
  );
};


// ═══════════════════════════════════════════════════════════
// SCENE 9: ACCOUNTING — invoicing, P&L, expenses
// ═══════════════════════════════════════════════════════════
const AccountingScene: React.FC = () => {
  const frame = useCurrentFrame();
  // Animated revenue counter
  const revenue = Math.floor(interpolate(frame, [20, 80], [0, 14280], { extrapolateRight: "clamp" }));
  const expenses = Math.floor(interpolate(frame, [30, 80], [0, 4120], { extrapolateRight: "clamp" }));
  const profit = revenue - expenses;
  // Invoice items appearing
  const invoices = [
    { client: "John Murphy", amount: "€280", status: "Paid", color: C.cyan, delay: 25 },
    { client: "Sarah O'Connor", amount: "€1,200", status: "Sent", color: C.gold, delay: 40 },
    { client: "Emma Walsh", amount: "€450", status: "Paid", color: C.cyan, delay: 55 },
    { client: "Tom Kelly", amount: "€3,500", status: "Overdue", color: C.orange, delay: 70 },
  ];
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <OrbBlobs colors={[C.purpleGlow, C.cyanGlow, "rgba(255,214,10,0.2)"]} speed={0.8} />
      <div style={{ display: "flex", gap: 60, alignItems: "center", zIndex: 1, padding: "0 80px", width: "100%" }}>
        {/* Left: P&L summary */}
        <div style={{ flex: 1 }}>
          <Pop delay={0} direction="up">
            <h2 style={{ fontSize: 48, fontWeight: 900, color: C.white, margin: "0 0 24px", lineHeight: 1.15 }}>
              Built-in <Grad from={C.gold} to={C.orange}>Accounting</Grad>
            </h2>
          </Pop>
          <Pop delay={10} direction="left">
            <div style={{
              background: C.card, border: `1px solid ${C.cardBorder}`, borderRadius: 22, padding: 24,
              backdropFilter: "blur(20px)", marginBottom: 20,
              boxShadow: `0 10px 40px rgba(0,0,0,0.3)`,
            }}>
              <p style={{ fontSize: 16, fontWeight: 700, color: C.gray, margin: "0 0 16px", textTransform: "uppercase", letterSpacing: 2 }}>Profit & Loss — This Month</p>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
                <span style={{ fontSize: 18, color: C.lightGray }}>Revenue</span>
                <span style={{ fontSize: 22, fontWeight: 900, color: C.cyan, fontFamily: "monospace" }}>€{revenue.toLocaleString()}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
                <span style={{ fontSize: 18, color: C.lightGray }}>Expenses</span>
                <span style={{ fontSize: 22, fontWeight: 900, color: C.orange, fontFamily: "monospace" }}>-€{expenses.toLocaleString()}</span>
              </div>
              <div style={{ height: 1, background: C.cardBorder, margin: "8px 0" }} />
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ fontSize: 20, fontWeight: 800, color: C.white }}>Net Profit</span>
                <span style={{ fontSize: 28, fontWeight: 900, color: C.cyan, fontFamily: "monospace", textShadow: `0 0 20px ${C.cyanGlow}` }}>€{profit.toLocaleString()}</span>
              </div>
            </div>
          </Pop>
          {[
            { icon: "🧾", text: "One-click invoicing", delay: 30 },
            { icon: "📊", text: "Profit & loss reports", delay: 40 },
            { icon: "💳", text: "Stripe payment links", delay: 50 },
            { icon: "📈", text: "Expense tracking", delay: 60 },
            { icon: "⏳", text: "Aging receivables", delay: 70 },
          ].map((item, i) => (
            <Pop key={i} delay={item.delay} direction="left">
              <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 14 }}>
                <div style={{
                  width: 44, height: 44, borderRadius: 12,
                  background: C.card, border: `1px solid ${C.cardBorder}`,
                  display: "flex", alignItems: "center", justifyContent: "center", fontSize: 22,
                }}>{item.icon}</div>
                <span style={{ fontSize: 19, color: C.lightGray, fontWeight: 600 }}>{item.text}</span>
              </div>
            </Pop>
          ))}
        </div>
        {/* Right: Invoice list */}
        <Pop delay={15} direction="right" style={{ flex: 1 }}>
          <div style={{
            background: C.card, border: `1px solid ${C.cardBorder}`, borderRadius: 22, padding: 24,
            backdropFilter: "blur(20px)",
            boxShadow: `0 20px 60px rgba(0,0,0,0.4), 0 0 40px ${C.purpleGlow}`,
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20, paddingBottom: 14, borderBottom: `1px solid ${C.cardBorder}` }}>
              <div style={{
                width: 40, height: 40, borderRadius: "50%",
                background: `linear-gradient(135deg, ${C.gold}, ${C.orange})`,
                display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20,
              }}>🧾</div>
              <span style={{ fontSize: 18, fontWeight: 800, color: C.white }}>Recent Invoices</span>
            </div>
            {invoices.map((inv, i) => {
              const opacity = interpolate(frame, [inv.delay, inv.delay + 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
              const y = interpolate(frame, [inv.delay, inv.delay + 8], [12, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
              return (
                <div key={i} style={{ opacity, transform: `translateY(${y}px)`, display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 0", borderBottom: i < invoices.length - 1 ? `1px solid ${C.cardBorder}` : "none" }}>
                  <div>
                    <p style={{ fontSize: 16, fontWeight: 700, color: C.white, margin: 0 }}>{inv.client}</p>
                    <p style={{ fontSize: 13, color: C.gray, margin: 0 }}>{inv.amount}</p>
                  </div>
                  <span style={{ fontSize: 13, fontWeight: 700, color: inv.color, padding: "4px 12px", borderRadius: 8, background: `${inv.color}15`, border: `1px solid ${inv.color}33` }}>{inv.status}</span>
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
// SCENE 10: STATS EXPLOSION — numbers flying in
// ═══════════════════════════════════════════════════════════
const StatsExplosionScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const stats = [
    { value: "24/7", sub: "Always On", icon: "🕐", color: C.cyan },
    { value: "€0", sub: "Missed Revenue", icon: "💰", color: C.gold },
    { value: "∞", sub: "Concurrent Calls", icon: "📞", color: C.purple },
    { value: "0", sub: "Missed Calls", icon: "🎯", color: C.pink },
  ];
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <OrbBlobs colors={[C.purpleGlow, C.cyanGlow, C.pinkGlow, "rgba(255,214,10,0.2)"]} speed={1.5} />
      <div style={{ zIndex: 1, textAlign: "center" }}>
        <Pop delay={0} direction="up">
          <h2 style={{ fontSize: 48, fontWeight: 900, color: C.white, margin: "0 0 40px" }}>
            By The <Grad from={C.gold} to={C.orange}>Numbers</Grad>
          </h2>
        </Pop>
        {/* 2x2 grid */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 28, maxWidth: 700, margin: "0 auto" }}>
          {stats.map((s, i) => {
            const delay = 8 + i * 10;
            const scale = spring({ frame: frame - delay, fps, config: { damping: 10, mass: 0.4, stiffness: 180 } });
            return (
              <div key={i} style={{
                transform: `scale(${scale})`, textAlign: "center",
                background: C.card, border: `1px solid ${s.color}33`,
                borderRadius: 22, padding: "32px 28px", backdropFilter: "blur(20px)",
                boxShadow: `0 0 30px ${s.color}20`,
              }}>
                <div style={{ fontSize: 36, marginBottom: 10 }}>{s.icon}</div>
                <p style={{ fontSize: 52, fontWeight: 900, color: s.color, margin: "0 0 6px", textShadow: `0 0 25px ${s.color}50` }}>{s.value}</p>
                <p style={{ fontSize: 18, color: C.gray, margin: 0, fontWeight: 600 }}>{s.sub}</p>
              </div>
            );
          })}
        </div>
        {/* Tagline below */}
        <Pop delay={50} direction="up">
          <p style={{ fontSize: 22, color: C.gray, marginTop: 30, fontWeight: 600 }}>
            Everything you need. Nothing you don't.
          </p>
        </Pop>
      </div>
    </AbsoluteFill>
  );
};


// ═══════════════════════════════════════════════════════════
// SCENE 11: EXPLOSIVE FINALE
// ═══════════════════════════════════════════════════════════
const ExplosiveFinale: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const logoScale = spring({ frame: frame - 5, fps, config: { damping: 6, mass: 0.3, stiffness: 250 } });
  const btnScale = spring({ frame: frame - 40, fps, config: { damping: 8, mass: 0.4, stiffness: 200 } });
  const glow = interpolate(Math.sin(frame * 0.1), [-1, 1], [0.4, 1]);
  // Burst particles
  const burstParticles = Array.from({ length: 20 }, (_, i) => {
    const angle = (i / 20) * Math.PI * 2;
    const dist = interpolate(frame, [0, 30], [0, 200 + (i % 3) * 80], { extrapolateRight: "clamp" });
    const opacity = interpolate(frame, [0, 15, 40], [0, 1, 0], { extrapolateRight: "clamp" });
    return { x: Math.cos(angle) * dist, y: Math.sin(angle) * dist, opacity, color: i % 3 === 0 ? C.purple : i % 3 === 1 ? C.cyan : C.gold };
  });
  // Expanding rings
  const rings = [0, 1, 2].map(i => ({
    scale: interpolate((frame + i * 20) % 70, [0, 70], [0.3, 3]),
    opacity: interpolate((frame + i * 20) % 70, [0, 70], [0.5, 0]),
  }));
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <OrbBlobs colors={[C.purpleGlow, C.cyanGlow, C.pinkGlow]} speed={2} />
      {/* Burst particles */}
      {burstParticles.map((p, i) => (
        <div key={i} style={{
          position: "absolute", left: "50%", top: "50%",
          transform: `translate(calc(-50% + ${p.x}px), calc(-50% + ${p.y}px))`,
          width: 8, height: 8, borderRadius: "50%",
          background: p.color, opacity: p.opacity,
          boxShadow: `0 0 12px ${p.color}`,
        }} />
      ))}
      {/* Rings */}
      {rings.map((r, i) => (
        <div key={i} style={{
          position: "absolute", width: 200, height: 200, borderRadius: "50%",
          border: `2px solid ${i === 0 ? C.purple : i === 1 ? C.cyan : C.gold}`,
          transform: `scale(${r.scale})`, opacity: r.opacity,
        }} />
      ))}
      <div style={{ textAlign: "center", zIndex: 2 }}>
        {/* Logo */}
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "center", gap: 18, marginBottom: 24,
          transform: `scale(${logoScale})`,
        }}>
          <div style={{
            width: 72, height: 72, borderRadius: 18,
            background: `linear-gradient(135deg, ${C.purple}, ${C.cyan})`,
            display: "flex", alignItems: "center", justifyContent: "center", fontSize: 38,
            boxShadow: `0 0 60px ${C.purpleGlow}, 0 0 120px ${C.cyanGlow}`,
          }}>⚡</div>
          <span style={{ fontSize: 56, fontWeight: 900, color: C.white, letterSpacing: -2 }}>BookedForYou</span>
        </div>
        <Pop delay={15} direction="up">
          <h2 style={{ fontSize: 58, fontWeight: 900, color: C.white, margin: "0 0 12px", lineHeight: 1.15 }}>
            Stop missing calls.
            <br /><Grad>Start growing.</Grad>
          </h2>
        </Pop>
        <Pop delay={25} direction="up">
          <p style={{ fontSize: 24, color: C.gray, margin: "0 0 36px" }}>
            Every call answered. Every job booked. Every invoice sent.
          </p>
        </Pop>
        <Pop delay={35} direction="scale">
          <div style={{
            display: "inline-block",
            background: `linear-gradient(135deg, ${C.purple}, ${C.cyan})`,
            borderRadius: 20, padding: "22px 60px",
            transform: `scale(${btnScale})`,
            boxShadow: `0 0 ${60 * glow}px ${C.purpleGlow}, 0 0 ${100 * glow}px ${C.cyanGlow}`,
          }}>
            <span style={{ fontSize: 28, fontWeight: 900, color: C.white }}>
              Get Started →
            </span>
          </div>
        </Pop>
        <Pop delay={50} direction="up">
          <p style={{ fontSize: 24, fontWeight: 700, color: C.purpleLight, marginTop: 24 }}>bookedforyou.ie</p>
        </Pop>
      </div>
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════════════
// TRANSITION
// ═══════════════════════════════════════════════════════════
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
// MAIN COMPOSITION
// ═══════════════════════════════════════════════════════════
export const CinematicVideo: React.FC = () => {
  const scenes = [
    { component: CinematicOpen, duration: 100 },          // 3.3s — zoom-in logo reveal
    { component: MissedCallsScene, duration: 150 },        // 5s — dramatic missed calls
    { component: PhoneAnswersScene, duration: 120 },        // 4s — phone answers itself
    { component: LiveConversationScene, duration: 210 },    // 7s — full conversation
    { component: FeatureOrbitScene, duration: 135 },        // 4.5s — orbiting features
    { component: CalendarZoomScene, duration: 150 },        // 5s — calendar filling up
    { component: DashboardMontageScene, duration: 165 },    // 5.5s — 4-panel dashboard
    { component: SMSReminderScene, duration: 150 },         // 5s — SMS flow
    { component: AccountingScene, duration: 150 },          // 5s — accounting & invoicing
    { component: StatsExplosionScene, duration: 120 },      // 4s — stats flying in
    { component: ExplosiveFinale, duration: 135 },          // 4.5s — CTA
  ];

  let startFrame = 0;

  return (
    <AbsoluteFill style={{ fontFamily: FONT }}>
      <Audio src={staticFile("music.mp3")} volume={0.4} />
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
