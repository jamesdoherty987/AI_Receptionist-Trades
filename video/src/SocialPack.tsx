import {
  AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate, spring, Sequence,
} from "remotion";
import React from "react";

// ─── Shared ───
const C = {
  bg1: "#030014", bg2: "#0a0025",
  purple: "#7c3aed", purpleLight: "#a78bfa", purpleGlow: "rgba(124,58,237,0.4)",
  cyan: "#06d6a0", cyanGlow: "rgba(6,214,160,0.35)",
  blue: "#3a86ff", pink: "#ff006e", orange: "#ff6b35", gold: "#ffd60a", red: "#ff4757",
  white: "#fff", gray: "#94a3b8", lightGray: "#cbd5e1",
};
const F = "'Inter','SF Pro Display',-apple-system,sans-serif";

const BG: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill>
      <div style={{ width: "100%", height: "100%", background: `radial-gradient(ellipse at 50% 20%,${C.bg2},${C.bg1} 70%)` }} />
      {Array.from({ length: 30 }, (_, i) => {
        const seed = i * 137.508;
        return <div key={i} style={{ position: "absolute", left: `${(seed * 7.3) % 100}%`, top: `${((seed * 3.1 + f * 0.2) % 120) - 10}%`, width: 1 + (i % 3), height: 1 + (i % 3), borderRadius: "50%", backgroundColor: i % 2 === 0 ? C.purpleLight : C.cyan, opacity: 0.05 + (i % 4) * 0.03 }} />;
      })}
    </AbsoluteFill>
  );
};

const Orbs: React.FC<{ colors?: string[] }> = ({ colors = [C.purpleGlow, C.cyanGlow] }) => {
  const f = useCurrentFrame();
  return <>{colors.map((c, i) => {
    const a = f * 0.008 + (i * Math.PI * 2) / colors.length;
    return <div key={i} style={{ position: "absolute", width: 350, height: 350, borderRadius: "50%", background: `radial-gradient(circle,${c},transparent 65%)`, left: `${50 + Math.sin(a) * 20}%`, top: `${40 + Math.cos(a * 0.6) * 20}%`, transform: "translate(-50%,-50%)", filter: "blur(50px)", pointerEvents: "none" }} />;
  })}</>;
};

// Pop-in text with spring
const Pop: React.FC<{ children: React.ReactNode; delay?: number; scale?: boolean; style?: React.CSSProperties }> = ({ children, delay = 0, scale, style }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame: f - delay, fps, config: { damping: 10, mass: 0.4, stiffness: 180 } });
  const op = interpolate(f - delay, [0, 6], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const t = scale ? `scale(${interpolate(p, [0, 1], [0.3, 1])})` : `translateY(${interpolate(p, [0, 1], [40, 0])}px)`;
  return <div style={{ opacity: op, transform: t, ...style }}>{children}</div>;
};

// Big explosive text
const Boom: React.FC<{ text: string; delay: number; color?: string; size?: number }> = ({ text, delay, color = C.white, size = 72 }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: f - delay, fps, config: { damping: 6, mass: 0.3, stiffness: 250 } });
  const op = interpolate(f - delay, [0, 5, 55, 65], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div style={{ opacity: op, transform: `scale(${s})`, textAlign: "center" }}>
      <span style={{ fontSize: size, fontWeight: 900, color, textShadow: `0 4px 30px rgba(0,0,0,0.8), 0 0 40px ${color}40`, letterSpacing: -2, lineHeight: 1.1, display: "block" }}>{text}</span>
    </div>
  );
};

const Fade: React.FC<{ children: React.ReactNode; dur: number }> = ({ children, dur }) => {
  const f = useCurrentFrame();
  return <AbsoluteFill style={{ opacity: interpolate(f, [0, 6, dur - 6, dur], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }}>{children}</AbsoluteFill>;
};

const Logo: React.FC<{ size?: number }> = ({ size = 52 }) => (
  <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 12 }}>
    <div style={{ width: size, height: size, borderRadius: size * 0.26, background: `linear-gradient(135deg,${C.purple},${C.cyan})`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: size * 0.55, boxShadow: `0 0 ${size}px ${C.purpleGlow}` }}>⚡</div>
    <span style={{ fontSize: size * 0.7, fontWeight: 900, color: C.white, letterSpacing: -1 }}>BookedForYou</span>
  </div>
);

// ═══════════════════════════════════════════════════════════
// VIDEO 1: "POV: You're a plumber" (Funny/Relatable) — 12s
// Hook → Problem → Solution → CTA
// ═══════════════════════════════════════════════════════════

const V1_Hook: React.FC = () => {
  const f = useCurrentFrame();
  const shake = f < 50 ? Math.sin(f * 1.8) * 5 : 0;
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 60px" }}>
      <Orbs colors={["rgba(255,50,50,0.2)", C.purpleGlow]} />
      <div style={{ textAlign: "center" }}>
        <Boom text="POV:" delay={0} size={48} color={C.gray} />
        <Boom text="You're a plumber" delay={8} size={56} color={C.white} />
        {/* Phone vibrating */}
        <Pop delay={20} scale style={{ marginTop: 30 }}>
          <div style={{
            width: 180, height: 320, borderRadius: 28, margin: "0 auto",
            background: "linear-gradient(180deg,#1a1a3e,#0f0c29)",
            border: "2px solid rgba(255,50,50,0.3)",
            transform: `rotate(${shake}deg)`,
            boxShadow: "0 20px 60px rgba(0,0,0,0.5),0 0 30px rgba(255,50,50,0.15)",
            display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 16,
          }}>
            <div style={{ position: "absolute", top: 8, width: 50, height: 4, borderRadius: 2, background: "rgba(255,255,255,0.1)" }} />
            {/* Missed calls stacking */}
            {Array.from({ length: Math.min(Math.floor(interpolate(f, [25, 60], [0, 5], { extrapolateRight: "clamp" })), 5) }, (_, i) => (
              <div key={i} style={{
                width: "100%", marginBottom: 5,
                background: "rgba(255,50,50,0.12)", border: "1px solid rgba(255,50,50,0.25)",
                borderRadius: 8, padding: "6px 8px", display: "flex", alignItems: "center", gap: 5,
              }}>
                <span style={{ fontSize: 12 }}>📵</span>
                <span style={{ fontSize: 10, fontWeight: 700, color: "#ff6b6b" }}>Missed Call</span>
              </div>
            ))}
          </div>
        </Pop>
        <Boom text="🔴 5 missed calls" delay={55} size={40} color={C.red} />
      </div>
    </AbsoluteFill>
  );
};

const V1_Problem: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 60px" }}>
    <Orbs colors={["rgba(255,50,50,0.15)", "rgba(255,107,53,0.15)"]} />
    <div style={{ textAlign: "center" }}>
      <Boom text="You're under" delay={0} size={52} />
      <Boom text="a sink 🔧" delay={10} size={64} color={C.orange} />
      <Boom text="Hands covered" delay={25} size={44} color={C.gray} />
      <Boom text="in grease" delay={32} size={52} />
      <Boom text="Phone won't" delay={50} size={44} color={C.gray} />
      <Boom text="stop ringing 📱" delay={58} size={52} color={C.red} />
    </div>
  </AbsoluteFill>
);

const V1_Solution: React.FC = () => {
  const f = useCurrentFrame();
  const bars = Array.from({ length: 8 }, (_, i) => ({ h: 10 + Math.sin(f * 0.3 + i * 0.7) * 8 }));
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 60px" }}>
      <Orbs colors={[C.cyanGlow, C.purpleGlow]} />
      <div style={{ textAlign: "center" }}>
        <Boom text="What if your phone" delay={0} size={40} color={C.gray} />
        <Boom text="answered itself? 🤖" delay={12} size={52} color={C.cyan} />
        {/* AI waveform */}
        <Pop delay={25} scale style={{ marginTop: 30 }}>
          <div style={{ display: "flex", gap: 4, justifyContent: "center", alignItems: "center", height: 50 }}>
            {bars.map((b, i) => <div key={i} style={{ width: 5, height: b.h, borderRadius: 3, background: `linear-gr
adient(180deg,${C.cyan},${C.purple})` }} />)}
          </div>
        </Pop>
        <Boom text="Booked the job ✅" delay={45} size={48} color={C.cyan} />
        <Boom text="Sent the reminder 💬" delay={60} size={40} color={C.purpleLight} />
      </div>
    </AbsoluteFill>
  );
};

const V1_CTA: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const btnS = spring({ frame: f - 30, fps, config: { damping: 8, mass: 0.4, stiffness: 200 } });
  const glow = interpolate(Math.sin(f * 0.12), [-1, 1], [0.4, 1]);
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 60px" }}>
      <Orbs colors={[C.purpleGlow, C.cyanGlow]} />
      <div style={{ textAlign: "center" }}>
        <Pop delay={0} scale><Logo size={48} /></Pop>
        <Boom text="Never miss" delay={10} size={52} />
        <Boom text="a call again" delay={18} size={56} color={C.cyan} />
        <Pop delay={28} scale style={{ marginTop: 20 }}>
          <div style={{ display: "inline-block", background: `linear-gradient(135deg,${C.purple},${C.cyan})`, borderRadius: 16, padding: "16px 40px", transform: `scale(${btnS})`, boxShadow: `0 0 ${40 * glow}px ${C.purpleGlow}` }}>
            <span style={{ fontSize: 22, fontWeight: 900, color: C.white }}>Try Free →</span>
          </div>
        </Pop>
        <Pop delay={40} style={{ marginTop: 12 }}>
          <span style={{ fontSize: 16, color: C.gray }}>bookedforyou.ie</span>
        </Pop>
      </div>
    </AbsoluteFill>
  );
};

export const Social1_POV: React.FC = () => {
  const scenes = [
    { c: V1_Hook, d: 90 }, { c: V1_Problem, d: 90 }, { c: V1_Solution, d: 90 }, { c: V1_CTA, d: 80 },
  ];
  let s = 0;
  return (
    <AbsoluteFill style={{ fontFamily: F }}><BG />
      {scenes.map((sc, i) => { const from = s; s += sc.d; const Sc = sc.c; return <Sequence key={i} from={from} durationInFrames={sc.d}><Fade dur={sc.d}><Sc /></Fade></Sequence>; })}
    </AbsoluteFill>
  );
};


// ═══════════════════════════════════════════════════════════
// VIDEO 2: "€2,500/mo vs €99/mo" (Comparison/Shock) — 12s
// ═══════════════════════════════════════════════════════════

const V2_S1: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 50px" }}>
    <Orbs colors={["rgba(255,50,50,0.2)", C.purpleGlow]} />
    <div style={{ textAlign: "center" }}>
      <Boom text="A receptionist" delay={0} size={44} color={C.gray} />
      <Boom text="costs you" delay={10} size={48} />
      <Pop delay={22} scale>
        <div style={{ marginTop: 10 }}>
          <span style={{ fontSize: 120, fontWeight: 900, color: C.red, textShadow: `0 0 40px rgba(255,71,87,0.4)`, letterSpacing: -4 }}>€2,500</span>
          <div style={{ fontSize: 28, color: C.gray, fontWeight: 600 }}>per month</div>
        </div>
      </Pop>
      <Boom text="😬" delay={45} size={80} />
    </div>
  </AbsoluteFill>
);

const V2_S2: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 50px" }}>
    <Orbs colors={[C.cyanGlow, C.purpleGlow]} />
    <div style={{ textAlign: "center" }}>
      <Boom text="Our AI" delay={0} size={44} color={C.gray} />
      <Boom text="receptionist?" delay={8} size={48} />
      <Pop delay={20} scale>
        <div style={{ marginTop: 10 }}>
          <span style={{ fontSize: 140, fontWeight: 900, color: C.cyan, textShadow: `0 0 50px ${C.cyanGlow}`, letterSpacing: -4 }}>€99</span>
          <div style={{ fontSize: 28, color: C.gray, fontWeight: 600 }}>per month</div>
        </div>
      </Pop>
      <Boom text="🤯" delay={42} size={80} />
    </div>
  </AbsoluteFill>
);

const V2_S3: React.FC = () => {
  const f = useCurrentFrame();
  const rows = [
    { label: "Availability", old: "9-5", ai: "24/7 ✓", delay: 5 },
    { label: "Sick Days", old: "20+/yr", ai: "Never ✓", delay: 15 },
    { label: "Concurrent", old: "1 call", ai: "Unlimited ✓", delay: 25 },
    { label: "Booking", old: "Manual", ai: "Automatic ✓", delay: 35 },
  ];
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 50px" }}>
      <Orbs colors={[C.purpleGlow, C.cyanGlow]} />
      <div style={{ width: "100%" }}>
        <Boom text="Plus..." delay={0} size={44} color={C.gray} />
        <div style={{ marginTop: 20 }}>
          {rows.map((r, i) => {
            const op = interpolate(f, [r.delay, r.delay + 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            return (
              <div key={i} style={{ opacity: op, display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 0", borderBottom: i < rows.length - 1 ? "1px solid rgba(255,255,255,0.08)" : "none" }}>
                <span style={{ fontSize: 20, fontWeight: 700, color: C.white }}>{r.label}</span>
                <span style={{ fontSize: 18, color: "#ff6b6b", textDecoration: "line-through" }}>{r.old}</span>
                <span style={{ fontSize: 20, fontWeight: 800, color: C.cyan }}>{r.ai}</span>
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};

const V2_CTA: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const btnS = spring({ frame: f - 25, fps, config: { damping: 8, mass: 0.4 } });
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 60px" }}>
      <Orbs colors={[C.purpleGlow, C.cyanGlow]} />
      <div style={{ textAlign: "center" }}>
        <Pop delay={0} scale><Logo size={44} /></Pop>
        <Boom text="Save €28,000/yr" delay={10} size={48} color={C.cyan} />
        <Pop delay={22} scale style={{ marginTop: 16 }}>
          <div style={{ display: "inline-block", background: `linear-gradient(135deg,${C.purple},${C.cyan})`, borderRadius: 16, padding: "16px 40px", transform: `scale(${btnS})` }}>
            <span style={{ fontSize: 22, fontWeight: 900, color: C.white }}>Get Started →</span>
          </div>
        </Pop>
      </div>
    </AbsoluteFill>
  );
};

export const Social2_Price: React.FC = () => {
  const scenes = [{ c: V2_S1, d: 80 }, { c: V2_S2, d: 75 }, { c: V2_S3, d: 90 }, { c: V2_CTA, d: 70 }];
  let s = 0;
  return (
    <AbsoluteFill style={{ fontFamily: F }}><BG />
      {scenes.map((sc, i) => { const from = s; s += sc.d; const Sc = sc.c; return <Sequence key={i} from={from} durationInFrames={sc.d}><Fade dur={sc.d}><Sc /></Fade></Sequence>; })}
    </AbsoluteFill>
  );
};


// ═══════════════════════════════════════════════════════════
// VIDEO 3: "Watch AI book a job in 60 seconds" (Demo) — 15s
// Live conversation simulation
// ═══════════════════════════════════════════════════════════

const V3_Convo: React.FC = () => {
  const f = useCurrentFrame();
  const msgs = [
    { from: "ai", text: "Good morning! O'Brien Plumbing, how can I help?", delay: 15 },
    { from: "cust", text: "I've got a burst pipe!", delay: 45 },
    { from: "ai", text: "I'll get that sorted. Can I get your name?", delay: 70 },
    { from: "cust", text: "John Murphy", delay: 95 },
    { from: "ai", text: "Thursday 10 AM work for you?", delay: 115 },
    { from: "cust", text: "Perfect!", delay: 140 },
    { from: "ai", text: "✅ All booked! Reminder sent.", delay: 155 },
  ];
  const bars = Array.from({ length: 10 }, (_, i) => ({ h: 10 + Math.sin(f * 0.3 + i * 0.6) * 8 }));
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 40px" }}>
      <Orbs colors={[C.purpleGlow, C.cyanGlow]} />
      <div style={{ width: "100%" }}>
        <Boom text="Watch this 👀" delay={0} size={44} color={C.gray} />
        {/* Chat window */}
        <Pop delay={8} scale>
          <div style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 20, padding: 18, marginTop: 16 }}>
            {/* Header */}
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14, paddingBottom: 10, borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
              <div style={{ width: 36, height: 36, borderRadius: "50%", background: `linear-gradient(135deg,${C.purple},${C.cyan})`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18 }}>🤖</div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 800, color: C.white }}>AI Receptionist</div>
                <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <div style={{ width: 6, height: 6, borderRadius: "50%", background: C.cyan, boxShadow: `0 0 6px ${C.cyan}` }} />
                  <span style={{ fontSize: 11, color: C.cyan, fontWeight: 600 }}>Live Call</span>
                </div>
              </div>
              <div style={{ marginLeft: "auto", display: "flex", gap: 2, alignItems: "center" }}>
                {bars.map((b, i) => <div key={i} style={{ width: 3, borderRadius: 2, height: b.h, background: `linear-gradient(180deg,${C.cyan},${C.purple})` }} />)}
              </div>
            </div>
            {/* Messages */}
            <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
              {msgs.map((m, i) => {
                const op = interpolate(f, [m.delay, m.delay + 6], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
                const y = interpolate(f, [m.delay, m.delay + 6], [8, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
                const isAI = m.from === "ai";
                return (
                  <div key={i} style={{ opacity: op, transform: `translateY(${y}px)`, alignSelf: isAI ? "flex-start" : "flex-end", maxWidth: "85%" }}>
                    <div style={{ padding: "9px 13px", borderRadius: isAI ? "14px 14px 14px 4px" : "14px 14px 4px 14px", background: isAI ? `${C.purple}18` : `${C.cyan}12`, border: `1px solid ${isAI ? C.purple : C.cyan}22`, fontSize: 13, color: C.white, lineHeight: 1.4 }}>{m.text}</div>
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

const V3_Result: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const checkS = spring({ frame: f - 5, fps, config: { damping: 6, mass: 0.3, stiffness: 250 } });
  const actions = [
    { icon: "📅", text: "Calendar updated", delay: 15 },
    { icon: "👤", text: "Customer saved", delay: 25 },
    { icon: "💬", text: "SMS confirmation sent", delay: 35 },
    { icon: "⏰", text: "Reminder scheduled", delay: 45 },
  ];
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 50px" }}>
      <Orbs colors={[C.cyanGlow, C.purpleGlow]} />
      <div style={{ textAlign: "center" }}>
        <div style={{ transform: `scale(${checkS})`, marginBottom: 16 }}>
          <div style={{ width: 80, height: 80, borderRadius: "50%", background: `linear-gradient(135deg,${C.cyan},${C.purple})`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 40, margin: "0 auto", boxShadow: `0 0 40px ${C.cyanGlow}` }}>✅</div>
        </div>
        <Boom text="Job Booked!" delay={5} size={52} color={C.cyan} />
        <div style={{ marginTop: 20, textAlign: "left" }}>
          {actions.map((a, i) => {
            const op = interpolate(f, [a.delay, a.delay + 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            return (
              <div key={i} style={{ opacity: op, display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
                <span style={{ fontSize: 24 }}>{a.icon}</span>
                <span style={{ fontSize: 20, fontWeight: 700, color: C.white }}>{a.text}</span>
              </div>
            );
          })}
        </div>
        <Boom text="Zero human effort" delay={55} size={36} color={C.gray} />
      </div>
    </AbsoluteFill>
  );
};

const V3_CTA: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 60px" }}>
    <Orbs colors={[C.purpleGlow, C.cyanGlow]} />
    <div style={{ textAlign: "center" }}>
      <Pop delay={0} scale><Logo size={44} /></Pop>
      <Boom text="Your AI receptionist" delay={10} size={40} color={C.gray} />
      <Boom text="is ready" delay={20} size={52} color={C.cyan} />
      <Pop delay={30} style={{ marginTop: 12 }}><span style={{ fontSize: 18, color: C.gray }}>bookedforyou.ie</span></Pop>
    </div>
  </AbsoluteFill>
);

export const Social3_Demo: React.FC = () => {
  const scenes = [{ c: V3_Convo, d: 200 }, { c: V3_Result, d: 100 }, { c: V3_CTA, d: 60 }];
  let s = 0;
  return (
    <AbsoluteFill style={{ fontFamily: F }}><BG />
      {scenes.map((sc, i) => { const from = s; s += sc.d; const Sc = sc.c; return <Sequence key={i} from={from} durationInFrames={sc.d}><Fade dur={sc.d}><Sc /></Fade></Sequence>; })}
    </AbsoluteFill>
  );
};


// ═══════════════════════════════════════════════════════════
// VIDEO 4: "3 things your receptionist can't do" (Listicle) — 12s
// ═══════════════════════════════════════════════════════════

const V4_S1: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 50px" }}>
    <Orbs colors={["rgba(255,50,50,0.15)", C.purpleGlow]} />
    <div style={{ textAlign: "center" }}>
      <Boom text="3 things" delay={0} size={62} />
      <Boom text="your receptionist" delay={10} size={52} color={C.gray} />
      <Boom text="CAN'T do 🚫" delay={22} size={70} color={C.red} />
    </div>
  </AbsoluteFill>
);

const V4_Item: React.FC<{ num: string; text: string; emoji: string; color: string }> = ({ num, text, emoji, color }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const numS = spring({ frame: f - 5, fps, config: { damping: 6, mass: 0.3, stiffness: 250 } });
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 50px" }}>
      <Orbs colors={[`${color}30`, C.purpleGlow]} />
      <div style={{ textAlign: "center" }}>
        <div style={{ transform: `scale(${numS})`, marginBottom: 20 }}>
          <div style={{ width: 100, height: 100, borderRadius: "50%", background: `linear-gradient(135deg,${color},${C.purple})`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 52, fontWeight: 900, color: C.white, margin: "0 auto", boxShadow: `0 0 40px ${color}40` }}>{num}</div>
        </div>
        <Boom text={emoji} delay={10} size={82} />
        <Boom text={text} delay={20} size={52} color={C.white} />
      </div>
    </AbsoluteFill>
  );
};

const V4_But: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 50px" }}>
    <Orbs colors={[C.cyanGlow, C.purpleGlow]} />
    <div style={{ textAlign: "center" }}>
      <Boom text="But our AI?" delay={0} size={56} color={C.gray} />
      <Boom text="Does ALL of it" delay={15} size={66} color={C.cyan} />
      <Boom text="24/7 ⚡" delay={30} size={82} color={C.white} />
      <Pop delay={45} scale><Logo size={44} /></Pop>
      <Pop delay={52} style={{ marginTop: 8 }}><span style={{ fontSize: 18, color: C.gray }}>bookedforyou.ie</span></Pop>
    </div>
  </AbsoluteFill>
);

export const Social4_Listicle: React.FC = () => {
  const scenes = [
    { c: V4_S1, d: 60 },
    { c: () => <V4_Item num="1" text="Answer 5 calls at once" emoji="📞📞📞📞📞" color={C.blue} />, d: 70 },
    { c: () => <V4_Item num="2" text="Work at 3 AM on a Sunday" emoji="🌙" color={C.purple} />, d: 70 },
    { c: () => <V4_Item num="3" text="Never take a sick day" emoji="🤒 → 🤖" color={C.orange} />, d: 70 },
    { c: V4_But, d: 80 },
  ];
  let s = 0;
  return (
    <AbsoluteFill style={{ fontFamily: F }}><BG />
      {scenes.map((sc, i) => { const from = s; s += sc.d; const Sc = sc.c; return <Sequence key={i} from={from} durationInFrames={sc.d}><Fade dur={sc.d}><Sc /></Fade></Sequence>; })}
    </AbsoluteFill>
  );
};


// ═══════════════════════════════════════════════════════════
// VIDEO 5: "Setup speedrun" (Satisfying/Fast) — 10s
// Shows the 7-step setup flying through
// ═══════════════════════════════════════════════════════════

const V5_Go: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 50px" }}>
    <Orbs colors={[C.cyanGlow, C.purpleGlow]} />
    <div style={{ textAlign: "center" }}>
      <Boom text="Setup speedrun 🏃" delay={0} size={48} color={C.white} />
      <Boom text="5 minutes" delay={15} size={64} color={C.cyan} />
      <Boom text="Ready?" delay={30} size={52} color={C.gray} />
      <Boom text="GO →" delay={42} size={80} color={C.gold} />
    </div>
  </AbsoluteFill>
);

const V5_Steps: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const steps = [
    { icon: "👑", label: "Subscribe", color: C.gold },
    { icon: "📍", label: "Service Area", color: C.blue },
    { icon: "🏢", label: "Company Info", color: C.purple },
    { icon: "💳", label: "Payment", color: C.cyan },
    { icon: "🔧", label: "Services", color: C.orange },
    { icon: "👷", label: "Add Workers", color: C.pink },
    { icon: "📞", label: "Go Live!", color: C.cyan },
  ];
  // Progress bar
  const progress = interpolate(f, [0, 150], [0, 100], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 40px" }}>
      <Orbs colors={[C.purpleGlow, C.cyanGlow]} />
      <div style={{ width: "100%" }}>
        {/* Progress bar */}
        <div style={{ width: "100%", height: 8, background: "rgba(255,255,255,0.06)", borderRadius: 4, marginBottom: 30, overflow: "hidden" }}>
          <div style={{ width: `${progress}%`, height: "100%", borderRadius: 4, background: `linear-gradient(90deg,${C.purple},${C.cyan})`, boxShadow: `0 0 15px ${C.cyanGlow}` }} />
        </div>
        {/* Steps */}
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {steps.map((s, i) => {
            const stepProgress = progress / 100 * steps.length;
            const isComplete = i < stepProgress;
            const isCurrent = i >= stepProgress - 1 && i < stepProgress;
            const spr = spring({ frame: f - i * 18, fps, config: { damping: 10, mass: 0.4, stiffness: 180 } });
            const op = interpolate(f, [i * 18, i * 18 + 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            return (
              <div key={i} style={{ opacity: op, transform: `translateX(${interpolate(spr, [0, 1], [60, 0])}px)`, display: "flex", alignItems: "center", gap: 14 }}>
                <div style={{
                  width: 52, height: 52, borderRadius: 16, flexShrink: 0,
                  background: isComplete ? `linear-gradient(135deg,${C.purple},${C.cyan})` : "rgba(255,255,255,0.04)",
                  border: isCurrent ? `2px solid ${C.cyan}` : `1px solid ${isComplete ? "transparent" : "rgba(255,255,255,0.08)"}`,
                  display: "flex", alignItems: "center", justifyContent: "center", fontSize: 24,
                  boxShadow: isCurrent ? `0 0 20px ${C.cyanGlow}` : isComplete ? `0 0 12px ${C.purpleGlow}` : "none",
                }}>
                  {isComplete && !isCurrent ? "✓" : s.icon}
                </div>
                <span style={{ fontSize: 20, fontWeight: 700, color: isComplete ? C.white : C.gray }}>{s.label}</span>
                {isCurrent && <div style={{ marginLeft: "auto", width: 10, height: 10, borderRadius: "50%", background: C.cyan, boxShadow: `0 0 8px ${C.cyan}`, transform: `scale(${interpolate(Math.sin(f * 0.15), [-1, 1], [0.7, 1.3])})` }} />}
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};

const V5_Done: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const boomS = spring({ frame: f - 5, fps, config: { damping: 6, mass: 0.3, stiffness: 250 } });
  // Burst particles
  const particles = Array.from({ length: 12 }, (_, i) => {
    const angle = (i / 12) * Math.PI * 2;
    const dist = interpolate(f, [0, 20], [0, 150 + (i % 3) * 40], { extrapolateRight: "clamp" });
    const op = interpolate(f, [0, 10, 30], [0, 1, 0], { extrapolateRight: "clamp" });
    return { x: Math.cos(angle) * dist, y: Math.sin(angle) * dist, op, c: i % 3 === 0 ? C.purple : i % 3 === 1 ? C.cyan : C.gold };
  });
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 50px" }}>
      <Orbs colors={[C.cyanGlow, C.purpleGlow]} />
      {particles.map((p, i) => <div key={i} style={{ position: "absolute", left: "50%", top: "45%", transform: `translate(calc(-50% + ${p.x}px),calc(-50% + ${p.y}px))`, width: 6, height: 6, borderRadius: "50%", background: p.c, opacity: p.op, boxShadow: `0 0 8px ${p.c}` }} />)}
      <div style={{ textAlign: "center", transform: `scale(${boomS})` }}>
        <Boom text="🎉 YOU'RE LIVE!" delay={0} size={56} color={C.cyan} />
        <Boom text="5 minutes" delay={15} size={44} color={C.gray} />
        <Boom text="That's it." delay={28} size={48} color={C.white} />
        <Pop delay={40} scale><Logo size={40} /></Pop>
        <Pop delay={48} style={{ marginTop: 8 }}><span style={{ fontSize: 16, color: C.gray }}>bookedforyou.ie</span></Pop>
      </div>
    </AbsoluteFill>
  );
};

export const Social5_Speedrun: React.FC = () => {
  const scenes = [{ c: V5_Go, d: 70 }, { c: V5_Steps, d: 170 }, { c: V5_Done, d: 80 }];
  let s = 0;
  return (
    <AbsoluteFill style={{ fontFamily: F }}><BG />
      {scenes.map((sc, i) => { const from = s; s += sc.d; const Sc = sc.c; return <Sequence key={i} from={from} durationInFrames={sc.d}><Fade dur={sc.d}><Sc /></Fade></Sequence>; })}
    </AbsoluteFill>
  );
};
