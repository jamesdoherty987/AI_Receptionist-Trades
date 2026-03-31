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
  red: "#ff4757",
  gold: "#ffd60a",
  white: "#ffffff",
  gray: "#94a3b8",
  lightGray: "#cbd5e1",
  card: "rgba(255,255,255,0.05)",
  cardBorder: "rgba(255,255,255,0.08)",
};

const FONT = "'Inter', 'SF Pro Display', -apple-system, sans-serif";

// ─── Background ───
const VerticalBg: React.FC = () => {
  const frame = useCurrentFrame();
  const stars = Array.from({ length: 40 }, (_, i) => {
    const seed = i * 137.508;
    return {
      x: (seed * 7.3) % 100,
      y: ((seed * 3.1 + frame * (0.4 + (i % 3) * 0.2)) % 130) - 15,
      size: 1 + (i % 3),
      opacity: 0.06 + (i % 4) * 0.04,
    };
  });
  return (
    <AbsoluteFill>
      <div style={{ width: "100%", height: "100%", background: `radial-gradient(ellipse at 50% 20%, ${C.bg2}, ${C.bg1} 70%)` }} />
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
        const angle = frame * 0.01 + (i * Math.PI * 2) / colors.length;
        const x = 50 + Math.sin(angle) * 20;
        const y = 40 + Math.cos(angle * 0.6) * 25;
        return (
          <div key={i} style={{
            position: "absolute", width: 400, height: 400, borderRadius: "50%",
            background: `radial-gradient(circle, ${color}, transparent 65%)`,
            left: `${x}%`, top: `${y}%`, transform: "translate(-50%, -50%)",
            filter: "blur(50px)", pointerEvents: "none",
          }} />
        );
      })}
    </>
  );
};

const Pop: React.FC<{
  children: React.ReactNode;
  delay?: number;
  direction?: "up" | "down" | "scale" | "none";
  style?: React.CSSProperties;
}> = ({ children, delay = 0, direction = "up", style }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame: frame - delay, fps, config: { damping: 10, mass: 0.4, stiffness: 180 } });
  const opacity = interpolate(frame - delay, [0, 6], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const map: Record<string, string> = {
    up: `translateY(${interpolate(p, [0, 1], [50, 0])}px)`,
    down: `translateY(${interpolate(p, [0, 1], [-50, 0])}px)`,
    scale: `scale(${interpolate(p, [0, 1], [0.3, 1])})`,
    none: "",
  };
  return <div style={{ opacity, transform: map[direction], ...style }}>{children}</div>;
};

const Grad: React.FC<{ children: React.ReactNode; from?: string; to?: string }> = ({
  children, from = C.purple, to = C.cyan,
}) => (
  <span style={{ background: `linear-gradient(135deg, ${from}, ${to})`, WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>{children}</span>
);

const Transition: React.FC<{
  children: React.ReactNode;
  durationInFrames: number;
}> = ({ children, durationInFrames }) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 6, durationInFrames - 6, durationInFrames], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return <AbsoluteFill style={{ opacity }}>{children}</AbsoluteFill>;
};


// ═══════════════════════════════════════════════════════════
// SCENE 1: HOOK — "Still answering your own phone?" (2s)
// ═══════════════════════════════════════════════════════════
const HookScene: React.FC = () => {
  const frame = useCurrentFrame();
  const shake = frame < 40 ? Math.sin(frame * 1.5) * 4 : 0;
  const missedCount = Math.min(Math.floor(interpolate(frame, [5, 40], [0, 7], { extrapolateRight: "clamp" })), 7);
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 60px" }}>
      <Orbs colors={["rgba(255,50,50,0.2)", C.purpleGlow]} />
      <div style={{ textAlign: "center", zIndex: 1 }}>
        {/* Phone with missed calls */}
        <Pop delay={0} direction="scale">
          <div style={{
            width: 220, height: 380, borderRadius: 32, margin: "0 auto 40px",
            background: "linear-gradient(180deg, #1a1a3e, #0f0c29)",
            border: `2px solid rgba(255,50,50,0.3)`,
            transform: `rotate(${shake}deg)`,
            boxShadow: `0 20px 60px rgba(0,0,0,0.5), 0 0 30px rgba(255,50,50,0.15)`,
            display: "flex", flexDirection: "column", alignItems: "center",
            justifyContent: "center", padding: 20, position: "relative",
          }}>
            <div style={{ position: "absolute", top: 10, width: 60, height: 5, borderRadius: 3, background: "rgba(255,255,255,0.1)" }} />
            {Array.from({ length: Math.min(missedCount, 4) }, (_, i) => (
              <div key={i} style={{
                width: "100%", marginBottom: 6,
                background: "rgba(255,50,50,0.12)", border: "1px solid rgba(255,50,50,0.25)",
                borderRadius: 10, padding: "8px 10px", display: "flex", alignItems: "center", gap: 6,
              }}>
                <span style={{ fontSize: 14 }}>📵</span>
                <div>
                  <p style={{ fontSize: 11, fontWeight: 700, color: "#ff6b6b", margin: 0 }}>Missed Call</p>
                  <p style={{ fontSize: 9, color: C.gray, margin: 0 }}>{`${9 + i}:${15 + i * 12} AM`}</p>
                </div>
              </div>
            ))}
            {missedCount > 0 && (
              <div style={{
                position: "absolute", top: 24, right: 16,
                width: 32, height: 32, borderRadius: "50%",
                background: "#ff3333", display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 14, fontWeight: 900, color: C.white,
                boxShadow: "0 0 15px rgba(255,50,50,0.5)",
              }}>{missedCount}</div>
            )}
          </div>
        </Pop>
        <Pop delay={8} direction="up">
          <h2 style={{ fontSize: 52, fontWeight: 900, color: C.white, margin: 0, lineHeight: 1.15 }}>
            Still answering
            <br />your <span style={{ color: "#ff6b6b" }}>own phone?</span>
          </h2>
        </Pop>
      </div>
    </AbsoluteFill>
  );
};


// ═══════════════════════════════════════════════════════════
// SCENE 2: SOLUTION — AI answers (3s)
// ═══════════════════════════════════════════════════════════
const SolutionScene: React.FC = () => {
  const frame = useCurrentFrame();
  const bars = Array.from({ length: 10 }, (_, i) => ({
    height: 12 + Math.sin(frame * 0.3 + i * 0.7) * 10,
  }));
  // Chat messages
  const msgs = [
    { from: "ai", text: "Good morning! How can I help?", delay: 20 },
    { from: "cust", text: "I need a plumber ASAP", delay: 40 },
    { from: "ai", text: "I have Thursday 10AM — shall I book?", delay: 55 },
    { from: "cust", text: "Perfect!", delay: 70 },
    { from: "ai", text: "✅ All booked! Reminder sent.", delay: 80 },
  ];
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 50px" }}>
      <Orbs colors={[C.purpleGlow, C.cyanGlow]} />
      <div style={{ textAlign: "center", zIndex: 1, width: "100%" }}>
        <Pop delay={0} direction="up">
          <h2 style={{ fontSize: 44, fontWeight: 900, color: C.white, margin: "0 0 24px", lineHeight: 1.15 }}>
            Meet your <Grad>AI receptionist</Grad>
          </h2>
        </Pop>
        {/* Chat window */}
        <Pop delay={5} direction="scale">
          <div style={{
            background: C.card, border: `1px solid ${C.cardBorder}`, borderRadius: 24,
            padding: 20, backdropFilter: "blur(20px)", width: "100%",
            boxShadow: `0 20px 60px rgba(0,0,0,0.4), 0 0 30px ${C.purpleGlow}`,
          }}>
            {/* Header */}
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16, paddingBottom: 12, borderBottom: `1px solid ${C.cardBorder}` }}>
              <div style={{
                width: 36, height: 36, borderRadius: "50%",
                background: `linear-gradient(135deg, ${C.purple}, ${C.cyan})`,
                display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18,
              }}>🤖</div>
              <div>
                <p style={{ fontSize: 15, fontWeight: 800, color: C.white, margin: 0 }}>AI Receptionist</p>
                <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <div style={{ width: 6, height: 6, borderRadius: "50%", background: C.cyan, boxShadow: `0 0 6px ${C.cyan}` }} />
                  <p style={{ fontSize: 11, color: C.cyan, margin: 0, fontWeight: 600 }}>Live</p>
                </div>
              </div>
              <div style={{ marginLeft: "auto", display: "flex", gap: 2, alignItems: "center" }}>
                {bars.map((b, i) => (
                  <div key={i} style={{
                    width: 3, borderRadius: 2, height: b.height,
                    background: `linear-gradient(180deg, ${C.cyan}, ${C.purple})`,
                  }} />
                ))}
              </div>
            </div>
            {/* Messages */}
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {msgs.map((m, i) => {
                const opacity = interpolate(frame, [m.delay, m.delay + 6], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
                const y = interpolate(frame, [m.delay, m.delay + 6], [10, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
                const isAI = m.from === "ai";
                return (
                  <div key={i} style={{ opacity, transform: `translateY(${y}px)`, alignSelf: isAI ? "flex-start" : "flex-end", maxWidth: "85%" }}>
                    <div style={{
                      padding: "10px 14px", borderRadius: isAI ? "14px 14px 14px 4px" : "14px 14px 4px 14px",
                      background: isAI ? `${C.purple}18` : `${C.cyan}15`,
                      border: `1px solid ${isAI ? C.purple : C.cyan}25`,
                      fontSize: 14, color: C.white, lineHeight: 1.4,
                    }}>{m.text}</div>
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
// SCENE 3: FEATURES — Quick feature flash (3s)
// ═══════════════════════════════════════════════════════════
const FeaturesFlashScene: React.FC = () => {
  const frame = useCurrentFrame();
  const features = [
    { icon: "📞", label: "24/7 AI Calls", color: C.cyan },
    { icon: "📅", label: "Auto Booking", color: C.purple },
    { icon: "💬", label: "SMS Reminders", color: "#3498ff" },
    { icon: "👥", label: "Customer CRM", color: "#ff6b9d" },
    { icon: "💰", label: "Invoicing", color: C.gold },
    { icon: "👷", label: "Team Mgmt", color: "#ff9f43" },
  ];
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 50px" }}>
      <Orbs colors={[C.purpleGlow, C.cyanGlow, "rgba(255,214,10,0.15)"]} />
      <div style={{ textAlign: "center", zIndex: 1, width: "100%" }}>
        <Pop delay={0} direction="up">
          <h2 style={{ fontSize: 44, fontWeight: 900, color: C.white, margin: "0 0 30px", lineHeight: 1.15 }}>
            Everything in <Grad>one app</Grad>
          </h2>
        </Pop>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
          {features.map((f, i) => {
            const delay = 8 + i * 6;
            const scale = interpolate(frame, [delay, delay + 8], [0.5, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            const opacity = interpolate(frame, [delay, delay + 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            return (
              <div key={i} style={{
                opacity, transform: `scale(${scale})`,
                background: C.card, border: `1px solid ${f.color}33`,
                borderRadius: 18, padding: "20px 16px",
                display: "flex", alignItems: "center", gap: 12,
                boxShadow: `0 0 15px ${f.color}15`,
              }}>
                <div style={{
                  width: 48, height: 48, borderRadius: 14,
                  background: `${f.color}15`, border: `1px solid ${f.color}33`,
                  display: "flex", alignItems: "center", justifyContent: "center", fontSize: 24,
                }}>{f.icon}</div>
                <span style={{ fontSize: 17, fontWeight: 700, color: C.white }}>{f.label}</span>
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════════════
// SCENE 4: STATS + CTA (3s)
// ═══════════════════════════════════════════════════════════
const StatsCTAScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const btnScale = spring({ frame: frame - 40, fps, config: { damping: 8, mass: 0.4, stiffness: 200 } });
  const glow = interpolate(Math.sin(frame * 0.12), [-1, 1], [0.4, 1]);
  const stats = [
    { value: "24/7", label: "Always On", color: C.cyan },
    { value: "€99", label: "Per Month", color: C.gold },
    { value: "0", label: "Missed Calls", color: C.purple },
  ];
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 50px" }}>
      <Orbs colors={[C.purpleGlow, C.cyanGlow]} />
      <div style={{ textAlign: "center", zIndex: 1, width: "100%" }}>
        {/* Logo */}
        <Pop delay={0} direction="scale">
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 12, marginBottom: 24 }}>
            <div style={{
              width: 52, height: 52, borderRadius: 14,
              background: `linear-gradient(135deg, ${C.purple}, ${C.cyan})`,
              display: "flex", alignItems: "center", justifyContent: "center", fontSize: 28,
              boxShadow: `0 0 40px ${C.purpleGlow}`,
            }}>⚡</div>
            <span style={{ fontSize: 40, fontWeight: 900, color: C.white, letterSpacing: -1 }}>BookedForYou</span>
          </div>
        </Pop>
        {/* Stats */}
        <div style={{ display: "flex", gap: 14, marginBottom: 30 }}>
          {stats.map((s, i) => {
            const delay = 8 + i * 8;
            const scale = spring({ frame: frame - delay, fps, config: { damping: 10, mass: 0.4 } });
            return (
              <div key={i} style={{
                flex: 1, transform: `scale(${scale})`,
                background: C.card, border: `1px solid ${s.color}33`,
                borderRadius: 18, padding: "20px 12px",
              }}>
                <p style={{ fontSize: 36, fontWeight: 900, color: s.color, margin: "0 0 4px", textShadow: `0 0 20px ${s.color}40` }}>{s.value}</p>
                <p style={{ fontSize: 13, color: C.gray, margin: 0, fontWeight: 600 }}>{s.label}</p>
              </div>
            );
          })}
        </div>
        <Pop delay={30} direction="up">
          <h2 style={{ fontSize: 38, fontWeight: 900, color: C.white, margin: "0 0 24px", lineHeight: 1.2 }}>
            Stop missing calls.
            <br /><Grad>Start growing.</Grad>
          </h2>
        </Pop>
        <Pop delay={38} direction="scale">
          <div style={{
            display: "inline-block",
            background: `linear-gradient(135deg, ${C.purple}, ${C.cyan})`,
            borderRadius: 18, padding: "18px 48px",
            transform: `scale(${btnScale})`,
            boxShadow: `0 0 ${40 * glow}px ${C.purpleGlow}, 0 0 ${70 * glow}px ${C.cyanGlow}`,
          }}>
            <span style={{ fontSize: 22, fontWeight: 900, color: C.white }}>Try Free for 14 Days →</span>
          </div>
        </Pop>
        <Pop delay={48} direction="up">
          <p style={{ fontSize: 18, fontWeight: 700, color: C.purpleLight, marginTop: 16 }}>bookedforyou.ie</p>
        </Pop>
      </div>
    </AbsoluteFill>
  );
};


// ═══════════════════════════════════════════════════════════
// MAIN COMPOSITION — 15 seconds at 30fps = 450 frames
// ═══════════════════════════════════════════════════════════
export const SocialClip: React.FC = () => {
  const scenes = [
    { component: HookScene, duration: 90 },        // 3s — hook
    { component: SolutionScene, duration: 120 },    // 4s — AI chat
    { component: FeaturesFlashScene, duration: 105 },// 3.5s — features
    { component: StatsCTAScene, duration: 135 },    // 4.5s — stats + CTA
  ];
  let startFrame = 0;
  return (
    <AbsoluteFill style={{ fontFamily: FONT }}>
      <VerticalBg />
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
