import {
  AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate, spring, Sequence,
} from "remotion";
import React from "react";

const C = {
  bg1: "#030014", bg2: "#0a0025",
  purple: "#7c3aed", purpleLight: "#a78bfa", purpleGlow: "rgba(124,58,237,0.4)",
  cyan: "#06d6a0", cyanGlow: "rgba(6,214,160,0.35)",
  blue: "#3a86ff", blueGlow: "rgba(58,134,255,0.25)", pink: "#ff006e", orange: "#ff6b35", gold: "#ffd60a", red: "#ff4757",
  white: "#fff", gray: "#94a3b8", lightGray: "#cbd5e1",
};
const F = "'Inter','SF Pro Display',-apple-system,sans-serif";

const BG: React.FC = () => {
  const f = useCurrentFrame();
  return <AbsoluteFill>
    <div style={{ width: "100%", height: "100%", background: `radial-gradient(ellipse at 50% 20%,${C.bg2},${C.bg1} 70%)` }} />
    {Array.from({ length: 25 }, (_, i) => {
      const seed = i * 137.508;
      return <div key={i} style={{ position: "absolute", left: `${(seed * 7.3) % 100}%`, top: `${((seed * 3.1 + f * 0.2) % 120) - 10}%`, width: 1 + (i % 3), height: 1 + (i % 3), borderRadius: "50%", backgroundColor: i % 2 === 0 ? C.purpleLight : C.cyan, opacity: 0.04 + (i % 4) * 0.02 }} />;
    })}
  </AbsoluteFill>;
};

const Orbs: React.FC<{ colors?: string[] }> = ({ colors = [C.purpleGlow, C.cyanGlow] }) => {
  const f = useCurrentFrame();
  return <>{colors.map((c, i) => {
    const a = f * 0.008 + (i * Math.PI * 2) / colors.length;
    return <div key={i} style={{ position: "absolute", width: 350, height: 350, borderRadius: "50%", background: `radial-gradient(circle,${c},transparent 65%)`, left: `${50 + Math.sin(a) * 20}%`, top: `${40 + Math.cos(a * 0.6) * 20}%`, transform: "translate(-50%,-50%)", filter: "blur(50px)", pointerEvents: "none" }} />;
  })}</>;
};

const Boom: React.FC<{ text: string; delay: number; color?: string; size?: number; dur?: number }> = ({ text, delay, color = C.white, size = 72, dur = 70 }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: f - delay, fps, config: { damping: 6, mass: 0.3, stiffness: 250 } });
  const op = interpolate(f - delay, [0, 5, dur - 10, dur], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return <div style={{ opacity: op, transform: `scale(${s})`, textAlign: "center" }}><span style={{ fontSize: size, fontWeight: 900, color, textShadow: `0 4px 30px rgba(0,0,0,0.8),0 0 40px ${color}40`, letterSpacing: -2, lineHeight: 1.1, display: "block" }}>{text}</span></div>;
};

const Pop: React.FC<{ children: React.ReactNode; delay?: number; scale?: boolean; style?: React.CSSProperties }> = ({ children, delay = 0, scale, style }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame: f - delay, fps, config: { damping: 10, mass: 0.4, stiffness: 180 } });
  const op = interpolate(f - delay, [0, 6], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const t = scale ? `scale(${interpolate(p, [0, 1], [0.3, 1])})` : `translateY(${interpolate(p, [0, 1], [40, 0])}px)`;
  return <div style={{ opacity: op, transform: t, ...style }}>{children}</div>;
};

const Fade: React.FC<{ children: React.ReactNode; dur: number }> = ({ children, dur }) => {
  const f = useCurrentFrame();
  return <AbsoluteFill style={{ opacity: interpolate(f, [0, 8, dur - 8, dur], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }}>{children}</AbsoluteFill>;
};

const Logo: React.FC<{ size?: number }> = ({ size = 48 }) => (
  <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 10 }}>
    <div style={{ width: size, height: size, borderRadius: size * 0.26, background: `linear-gradient(135deg,${C.purple},${C.cyan})`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: size * 0.55, boxShadow: `0 0 ${size}px ${C.purpleGlow}` }}>⚡</div>
    <span style={{ fontSize: size * 0.65, fontWeight: 900, color: C.white, letterSpacing: -1 }}>BookedForYou</span>
  </div>
);

// ═══════════════════════════════════════════════════════════
// VIDEO 15: "Storytime: 3AM Emergency" (VERTICAL ~25s)
// Narrative with animated scenes — night sky, phone rings, AI saves the day
// ═══════════════════════════════════════════════════════════

const NightSky: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill>
      <div style={{ width: "100%", height: "100%", background: "linear-gradient(180deg,#0a0a2e 0%,#1a1a3e 40%,#0f1b3d 100%)" }} />
      {/* Moon */}
      <div style={{ position: "absolute", top: 280, right: 100, width: 70, height: 70, borderRadius: "50%", background: "#fef3c7", boxShadow: "0 0 40px rgba(254,243,199,0.4),0 0 80px rgba(254,243,199,0.2)" }} />
      {/* Stars */}
      {Array.from({ length: 40 }, (_, i) => {
        const seed = i * 97.3;
        const twinkle = interpolate(Math.sin(f * 0.1 + i), [-1, 1], [0.2, 0.8]);
        return <div key={i} style={{ position: "absolute", left: `${(seed * 3.7) % 100}%`, top: `${8 + (seed * 2.1) % 45}%`, width: 2, height: 2, borderRadius: "50%", background: "#fff", opacity: twinkle }} />;
      })}
    </AbsoluteFill>
  );
};

const V15_S1: React.FC = () => {
  const f = useCurrentFrame();
  const clockPulse = interpolate(Math.sin(f * 0.15), [-1, 1], [0.9, 1.1]);
  return (
    <AbsoluteFill>
      <NightSky />
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", padding: "0 50px", zIndex: 2 }}>
        <Boom text="Storytime 📖" delay={0} size={44} color={C.gray} dur={90} />
        <Pop delay={12} scale>
          <div style={{ transform: `scale(${clockPulse})`, margin: "16px 0" }}>
            <span style={{ fontSize: 100 }}>🕐</span>
          </div>
        </Pop>
        <Boom text="3:00 AM" delay={15} size={72} color="#fef3c7" dur={80} />
        <Boom text="Sunday night" delay={30} size={40} color={C.gray} dur={65} />
        <Boom text="You're asleep 😴" delay={50} size={48} dur={45} />
      </div>
    </AbsoluteFill>
  );
};

const V15_S2: React.FC = () => {
  const f = useCurrentFrame();
  const shake = f > 10 && f < 50 ? Math.sin(f * 2) * 5 : 0;
  return (
    <AbsoluteFill>
      <NightSky />
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", padding: "0 50px", zIndex: 2 }}>
        <Boom text="A pipe bursts 💦" delay={0} size={48} color={C.blue} dur={90} />
        <Boom text="at a customer's house" delay={15} size={36} color={C.gray} dur={75} />
        <Pop delay={25} scale>
          <div style={{ transform: `rotate(${shake}deg)`, margin: "20px 0" }}>
            <span style={{ fontSize: 80 }}>📱</span>
          </div>
        </Pop>
        <Boom text="They call you" delay={30} size={48} dur={60} />
        <Boom text="Ring... ring... ring..." delay={50} size={36} color={C.red} dur={40} />
        <Boom text="You don't hear it 😴" delay={65} size={40} color={C.gray} dur={25} />
      </div>
    </AbsoluteFill>
  );
};

const V15_S3: React.FC = () => {
  const f = useCurrentFrame();
  const bars = Array.from({ length: 10 }, (_, i) => ({ h: 10 + Math.sin(f * 0.3 + i * 0.6) * 8 }));
  return (
    <AbsoluteFill>
      <NightSky />
      <Orbs colors={[C.cyanGlow, C.purpleGlow]} />
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", padding: "0 50px", zIndex: 2 }}>
        <Boom text="But you have" delay={0} size={44} color={C.gray} dur={100} />
        <Pop delay={10} scale>
          <div style={{ width: 80, height: 80, borderRadius: "50%", background: `linear-gradient(135deg,${C.purple},${C.cyan})`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 40, margin: "12px auto", boxShadow: `0 0 40px ${C.cyanGlow}` }}>🤖</div>
        </Pop>
        <Boom text="BookedForYou ⚡" delay={15} size={48} color={C.cyan} dur={85} />
        {/* Waveform */}
        <Pop delay={30} scale>
          <div style={{ display: "flex", gap: 4, justifyContent: "center", alignItems: "center", height: 40, margin: "12px 0" }}>
            {bars.map((b, i) => <div key={i} style={{ width: 5, height: b.h, borderRadius: 3, background: `linear-gradient(180deg,${C.cyan},${C.purple})` }} />)}
          </div>
        </Pop>
        <Boom text="AI answers instantly" delay={35} size={40} dur={65} />
        <Boom text='"Emergency pipe burst"' delay={55} size={32} color={C.purpleLight} dur={45} />
        <Boom text="Booked for 7 AM ✅" delay={72} size={44} color={C.cyan} dur={28} />
      </div>
    </AbsoluteFill>
  );
};

const V15_S4: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 40px" }}>
    <BG /><Orbs colors={[C.cyanGlow, C.purpleGlow]} />
    <div style={{ textAlign: "center", zIndex: 2 }}>
      <Boom text="You wake up to:" delay={0} size={48} color={C.gray} dur={100} />
      <Pop delay={15}>
        <div style={{ margin: "20px 0", background: "rgba(255,255,255,0.04)", border: `1px solid ${C.cyan}22`, borderRadius: 22, padding: "24px 24px", textAlign: "left" }}>
          {[
            { icon: "✅", text: "Emergency job booked for 7 AM", delay: 20 },
            { icon: "👤", text: "Customer details saved", delay: 30 },
            { icon: "💬", text: "Confirmation SMS sent", delay: 40 },
            { icon: "📍", text: "Address captured & verified", delay: 50 },
            { icon: "⏰", text: "Reminder scheduled", delay: 60 },
          ].map((item, i) => (
            <Pop key={i} delay={item.delay}>
              <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 16 }}>
                <span style={{ fontSize: 28 }}>{item.icon}</span>
                <span style={{ fontSize: 24, fontWeight: 600, color: C.white }}>{item.text}</span>
              </div>
            </Pop>
          ))}
        </div>
      </Pop>
      <Boom text="All while you slept 😎" delay={75} size={46} color={C.cyan} dur={25} />
    </div>
  </AbsoluteFill>
);

const V15_CTA: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 50px" }}>
    <BG /><Orbs colors={[C.purpleGlow, C.cyanGlow]} />
    <div style={{ textAlign: "center", zIndex: 2 }}>
      <Pop delay={0} scale><Logo size={48} /></Pop>
      <Boom text="Your AI never sleeps" delay={12} size={44} color={C.cyan} />
      <Boom text="Try free for 14 days" delay={28} size={36} color={C.gray} />
      <Pop delay={42} style={{ marginTop: 8 }}><span style={{ fontSize: 18, color: C.gray }}>bookedforyou.ie</span></Pop>
    </div>
  </AbsoluteFill>
);

export const Social15_Storytime: React.FC = () => {
  const scenes = [{ c: V15_S1, d: 110 }, { c: V15_S2, d: 110 }, { c: V15_S3, d: 130 }, { c: V15_S4, d: 120 }, { c: V15_CTA, d: 80 }];
  let s = 0;
  return <AbsoluteFill style={{ fontFamily: F }}>{scenes.map((sc, i) => { const from = s; s += sc.d; const Sc = sc.c; return <Sequence key={i} from={from} durationInFrames={sc.d}><Fade dur={sc.d}><Sc /></Fade></Sequence>; })}</AbsoluteFill>;
};


// ═══════════════════════════════════════════════════════════
// VIDEO 16: "The Math" (VERTICAL ~20s) — Calculator breakdown
// Shows the math of missed calls adding up over a year
// ═══════════════════════════════════════════════════════════

const CalcLine: React.FC<{ left: string; right: string; delay: number; color?: string; bold?: boolean; big?: boolean }> = ({ left, right, delay, color = C.white, bold, big }) => {
  const f = useCurrentFrame();
  const op = interpolate(f, [delay, delay + 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const x = interpolate(f, [delay, delay + 8], [30, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div style={{ opacity: op, transform: `translateX(${x}px)`, display: "flex", justifyContent: "space-between", alignItems: "center", padding: big ? "14px 0" : "10px 0", borderBottom: big ? "none" : "1px solid rgba(255,255,255,0.06)" }}>
      <span style={{ fontSize: big ? 22 : 18, fontWeight: bold ? 800 : 500, color: bold ? color : C.lightGray }}>{left}</span>
      <span style={{ fontSize: big ? 32 : 20, fontWeight: bold ? 900 : 600, color, fontFamily: "monospace" }}>{right}</span>
    </div>
  );
};

const V16_S1: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 40px" }}>
    <BG /><Orbs colors={["rgba(255,50,50,0.15)", C.purpleGlow]} />
    <div style={{ textAlign: "center", zIndex: 2 }}>
      <Boom text="Let's do the math 🧮" delay={0} size={48} dur={80} />
      <Boom text="How much are you" delay={15} size={40} color={C.gray} dur={65} />
      <Boom text="actually losing?" delay={25} size={48} color={C.red} dur={55} />
    </div>
  </AbsoluteFill>
);

const V16_S2: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: "center", padding: "0 40px" }}>
    <BG /><Orbs colors={["rgba(255,50,50,0.15)", C.purpleGlow]} />
    <div style={{ zIndex: 2 }}>
      <Boom text="Per Week 📊" delay={0} size={40} color={C.gray} dur={130} />
      <div style={{ marginTop: 16, background: "rgba(255,255,255,0.03)", borderRadius: 18, padding: "16px 20px" }}>
        <CalcLine left="Missed calls/day" right="~3" delay={10} />
        <CalcLine left="× 5 work days" right="= 15 calls" delay={25} />
        <CalcLine left="Conversion rate" right="~40%" delay={40} />
        <CalcLine left="Lost jobs/week" right="= 6 jobs" delay={55} color={C.orange} bold />
        <CalcLine left="Avg job value" right="€250" delay={70} />
        <CalcLine left="Lost revenue/week" right="€1,500" delay={85} color={C.red} bold big />
      </div>
    </div>
  </AbsoluteFill>
);

const V16_S3: React.FC = () => {
  const f = useCurrentFrame();
  const yearLoss = Math.floor(interpolate(f, [20, 60], [0, 78000], { extrapolateRight: "clamp" }));
  return (
    <AbsoluteFill style={{ justifyContent: "center", padding: "0 40px" }}>
      <BG /><Orbs colors={["rgba(255,50,50,0.2)", C.purpleGlow]} />
      <div style={{ zIndex: 2 }}>
        <Boom text="Per Year 📅" delay={0} size={40} color={C.gray} dur={120} />
        <div style={{ marginTop: 16, background: "rgba(255,255,255,0.03)", borderRadius: 18, padding: "16px 20px" }}>
          <CalcLine left="€1,500 × 52 weeks" right="" delay={10} />
          <div style={{ textAlign: "center", padding: "20px 0" }}>
            <Pop delay={20} scale>
              <span style={{ fontSize: 80, fontWeight: 900, color: C.red, fontFamily: "monospace", textShadow: `0 0 40px rgba(255,71,87,0.4)` }}>€{yearLoss.toLocaleString()}</span>
            </Pop>
            <Boom text="lost per year" delay={25} size={28} color={C.gray} dur={85} />
          </div>
          <CalcLine left="BookedForYou cost" right="€1,188/yr" delay={60} color={C.cyan} bold />
          <CalcLine left="ROI" right="6,468%" delay={75} color={C.cyan} bold big />
        </div>
        <Boom text="🤯" delay={85} size={80} dur={30} />
      </div>
    </AbsoluteFill>
  );
};

const V16_CTA: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 50px" }}>
    <BG /><Orbs colors={[C.cyanGlow, C.purpleGlow]} />
    <div style={{ textAlign: "center", zIndex: 2 }}>
      <Boom text="€78,000 lost" delay={0} size={44} color={C.red} />
      <Boom text="or €99/mo to fix it" delay={15} size={44} color={C.cyan} />
      <Pop delay={30} scale><Logo size={44} /></Pop>
      <Pop delay={38} style={{ marginTop: 8 }}><span style={{ fontSize: 16, color: C.gray }}>bookedforyou.ie</span></Pop>
    </div>
  </AbsoluteFill>
);

export const Social16_TheMath: React.FC = () => {
  const scenes = [{ c: V16_S1, d: 90 }, { c: V16_S2, d: 130 }, { c: V16_S3, d: 130 }, { c: V16_CTA, d: 70 }];
  let s = 0;
  return <AbsoluteFill style={{ fontFamily: F }}>{scenes.map((sc, i) => { const from = s; s += sc.d; const Sc = sc.c; return <Sequence key={i} from={from} durationInFrames={sc.d}><Fade dur={sc.d}><Sc /></Fade></Sequence>; })}</AbsoluteFill>;
};


// ═══════════════════════════════════════════════════════════
// VIDEO 17: "Swipe Right" (VERTICAL ~20s) — Dating app parody
// Swiping through "receptionist profiles"
// ═══════════════════════════════════════════════════════════

const ProfileCard: React.FC<{ emoji: string; name: string; traits: { icon: string; text: string; bad?: boolean }[]; swiped: "left" | "right" | null; delay: number }> = ({ emoji, name, traits, swiped, delay }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const entryS = spring({ frame: f - delay, fps, config: { damping: 12, mass: 0.5 } });
  const entryOp = interpolate(f - delay, [0, 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  // Swipe animation
  const swipeDelay = delay + 60;
  const swipeX = swiped ? interpolate(f, [swipeDelay, swipeDelay + 12], [0, swiped === "left" ? -600 : 600], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) : 0;
  const swipeRot = swiped ? interpolate(f, [swipeDelay, swipeDelay + 12], [0, swiped === "left" ? -20 : 20], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) : 0;
  const swipeOp = swiped ? interpolate(f, [swipeDelay, swipeDelay + 12], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) : 1;
  return (
    <div style={{ opacity: entryOp * swipeOp, transform: `translateY(${interpolate(entryS, [0, 1], [50, 0])}px) translateX(${swipeX}px) rotate(${swipeRot}deg)`, position: "absolute", left: 30, right: 30, top: 370, bottom: 120 }}>
      <div style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 32, padding: "40px 28px", textAlign: "center", height: "100%", display: "flex", flexDirection: "column", justifyContent: "center" }}>
        <div style={{ fontSize: 100, marginBottom: 16 }}>{emoji}</div>
        <div style={{ fontSize: 36, fontWeight: 800, color: C.white, marginBottom: 24 }}>{name}</div>
        {traits.map((t, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 12, justifyContent: "center", marginBottom: 16 }}>
            <span style={{ fontSize: 26 }}>{t.icon}</span>
            <span style={{ fontSize: 22, fontWeight: 600, color: t.bad ? "#ff8a8a" : C.cyan }}>{t.text}</span>
          </div>
        ))}
        {/* Swipe buttons */}
        <div style={{ display: "flex", justifyContent: "center", gap: 40, marginTop: 28 }}>
          <div style={{ width: 68, height: 68, borderRadius: "50%", background: swiped === "left" ? C.red : "rgba(255,71,87,0.1)", border: `2px solid ${C.red}44`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 30 }}>✗</div>
          <div style={{ width: 68, height: 68, borderRadius: "50%", background: swiped === "right" ? C.cyan : `${C.cyan}15`, border: `2px solid ${C.cyan}44`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 30 }}>♥</div>
        </div>
      </div>
      {/* Swipe label */}
      {swiped && f > swipeDelay - 5 && (
        <div style={{ position: "absolute", top: 50, left: swiped === "right" ? 24 : "auto", right: swiped === "left" ? 24 : "auto", transform: "rotate(-15deg)", padding: "10px 24px", borderRadius: 12, border: `3px solid ${swiped === "right" ? C.cyan : C.red}`, fontSize: 34, fontWeight: 900, color: swiped === "right" ? C.cyan : C.red, opacity: interpolate(f, [swipeDelay - 5, swipeDelay], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }}>
          {swiped === "right" ? "MATCH ♥" : "NOPE ✗"}
        </div>
      )}
    </div>
  );
};

const V17_S1: React.FC = () => (
  <AbsoluteFill>
    <BG /><Orbs colors={["rgba(255,0,110,0.15)", C.purpleGlow]} />
    <div style={{ position: "absolute", top: 260, left: 0, right: 0, textAlign: "center", zIndex: 10 }}>
      <Boom text="Hiring a receptionist?" delay={0} size={42} color={C.gray} dur={90} />
      <Boom text="Swipe right 💕" delay={12} size={50} color={C.pink} dur={78} />
    </div>
    <ProfileCard emoji="👤" name="Human Receptionist" traits={[
      { icon: "💰", text: "€2,500/month", bad: true },
      { icon: "🕐", text: "9-5 only", bad: true },
      { icon: "🤒", text: "Takes sick days", bad: true },
      { icon: "📞", text: "1 call at a time", bad: true },
    ]} swiped="left" delay={20} />
  </AbsoluteFill>
);

const V17_S2: React.FC = () => (
  <AbsoluteFill>
    <BG /><Orbs colors={[C.cyanGlow, C.purpleGlow]} />
    <div style={{ position: "absolute", top: 260, left: 0, right: 0, textAlign: "center", zIndex: 10 }}>
      <Boom text="Next profile..." delay={0} size={42} color={C.gray} dur={100} />
    </div>
    <ProfileCard emoji="🤖" name="AI Receptionist" traits={[
      { icon: "💰", text: "€99/month" },
      { icon: "🕐", text: "24/7/365" },
      { icon: "💪", text: "Never sick" },
      { icon: "📞", text: "Unlimited calls" },
    ]} swiped="right" delay={15} />
  </AbsoluteFill>
);

const V17_Match: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const heartS = spring({ frame: f - 10, fps, config: { damping: 5, mass: 0.3, stiffness: 300 } });
  // Confetti
  const confetti = Array.from({ length: 20 }, (_, i) => ({
    x: interpolate(f, [10, 40], [540, 540 + (Math.sin(i * 1.3) * 400)], { extrapolateRight: "clamp" }),
    y: interpolate(f, [10, 60], [800, 200 + i * 50], { extrapolateRight: "clamp" }),
    op: interpolate(f, [10, 15, 50, 60], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
    color: [C.cyan, C.purple, C.gold, C.pink][i % 4],
    rot: f * (3 + i),
  }));
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 50px" }}>
      <BG /><Orbs colors={[C.cyanGlow, "rgba(255,0,110,0.2)"]} />
      {confetti.map((c, i) => <div key={i} style={{ position: "absolute", left: c.x, top: c.y, width: 10, height: 10, borderRadius: i % 2 === 0 ? "50%" : 2, background: c.color, opacity: c.op, transform: `rotate(${c.rot}deg)` }} />)}
      <div style={{ textAlign: "center", zIndex: 2 }}>
        <div style={{ transform: `scale(${heartS})` }}>
          <span style={{ fontSize: 120, display: "block" }}>💕</span>
        </div>
        <Boom text="IT'S A MATCH!" delay={5} size={52} color={C.pink} />
        <Pop delay={25} scale><Logo size={44} /></Pop>
        <Boom text="Your perfect receptionist" delay={30} size={36} color={C.gray} />
        <Pop delay={48} style={{ marginTop: 8 }}><span style={{ fontSize: 16, color: C.gray }}>bookedforyou.ie</span></Pop>
      </div>
    </AbsoluteFill>
  );
};

export const Social17_SwipeRight: React.FC = () => {
  const scenes = [{ c: V17_S1, d: 120 }, { c: V17_S2, d: 120 }, { c: V17_Match, d: 100 }];
  let s = 0;
  return <AbsoluteFill style={{ fontFamily: F }}>{scenes.map((sc, i) => { const from = s; s += sc.d; const Sc = sc.c; return <Sequence key={i} from={from} durationInFrames={sc.d}><Fade dur={sc.d}><Sc /></Fade></Sequence>; })}</AbsoluteFill>;
};


// ═══════════════════════════════════════════════════════════
// VIDEO 18: "War Room" (LANDSCAPE ~25s) — Mission control dashboard
// Live metrics updating, calls coming in, jobs being booked
// ═══════════════════════════════════════════════════════════

const MetricCard: React.FC<{ icon: string; label: string; value: string; color: string; x: number; y: number; delay: number }> = ({ icon, label, value, color, x, y, delay }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: f - delay, fps, config: { damping: 10, mass: 0.4 } });
  const op = interpolate(f - delay, [0, 6], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const pulse = interpolate(Math.sin(f * 0.08 + delay), [-1, 1], [0.98, 1.02]);
  return (
    <div style={{ position: "absolute", left: x, top: y, opacity: op, transform: `scale(${interpolate(s, [0, 1], [0.5, 1]) * pulse})`, width: 220 }}>
      <div style={{ background: "rgba(255,255,255,0.03)", border: `1px solid ${color}33`, borderRadius: 16, padding: "16px 18px", boxShadow: `0 0 20px ${color}10` }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
          <span style={{ fontSize: 20 }}>{icon}</span>
          <span style={{ fontSize: 13, color: C.gray, fontWeight: 600 }}>{label}</span>
        </div>
        <div style={{ fontSize: 32, fontWeight: 900, color, fontFamily: "monospace" }}>{value}</div>
      </div>
    </div>
  );
};

const LiveFeed: React.FC<{ events: { time: string; text: string; color: string; delay: number }[] }> = ({ events }) => {
  const f = useCurrentFrame();
  return (
    <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 16, padding: "14px 18px", width: 420, maxHeight: 500, overflow: "hidden" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12, paddingBottom: 10, borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
        <div style={{ width: 8, height: 8, borderRadius: "50%", background: C.cyan, boxShadow: `0 0 8px ${C.cyan}`, transform: `scale(${interpolate(Math.sin(f * 0.15), [-1, 1], [0.7, 1.3])})` }} />
        <span style={{ fontSize: 14, fontWeight: 800, color: C.white }}>Live Activity Feed</span>
      </div>
      {events.map((e, i) => {
        const op = interpolate(f, [e.delay, e.delay + 6], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        const y = interpolate(f, [e.delay, e.delay + 6], [12, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        return (
          <div key={i} style={{ opacity: op, transform: `translateY(${y}px)`, display: "flex", gap: 10, marginBottom: 8, padding: "6px 0" }}>
            <span style={{ fontSize: 12, color: C.gray, fontFamily: "monospace", flexShrink: 0 }}>{e.time}</span>
            <span style={{ fontSize: 13, fontWeight: 600, color: e.color }}>{e.text}</span>
          </div>
        );
      })}
    </div>
  );
};

const L7_WarRoom: React.FC = () => {
  const f = useCurrentFrame();
  const callsToday = Math.min(Math.floor(interpolate(f, [20, 300], [0, 12], { extrapolateRight: "clamp" })), 12);
  const jobsBooked = Math.min(Math.floor(interpolate(f, [40, 300], [0, 8], { extrapolateRight: "clamp" })), 8);
  const revenue = Math.floor(interpolate(f, [40, 300], [0, 3240], { extrapolateRight: "clamp" }));
  return (
    <AbsoluteFill>
      <BG /><Orbs colors={[C.cyanGlow, C.purpleGlow, "rgba(58,134,255,0.15)"]} />
      {/* Title */}
      <div style={{ position: "absolute", top: 24, left: 40, zIndex: 20, display: "flex", alignItems: "center", gap: 12 }}>
        <Pop delay={0} scale><Logo size={36} /></Pop>
        <Pop delay={5}>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <div style={{ width: 8, height: 8, borderRadius: "50%", background: C.cyan, boxShadow: `0 0 8px ${C.cyan}`, transform: `scale(${interpolate(Math.sin(f * 0.15), [-1, 1], [0.7, 1.3])})` }} />
            <span style={{ fontSize: 14, fontWeight: 700, color: C.cyan }}>LIVE</span>
          </div>
        </Pop>
      </div>
      {/* Metric cards */}
      <MetricCard icon="📞" label="Calls Today" value={`${callsToday}`} color={C.cyan} x={40} y={90} delay={10} />
      <MetricCard icon="📅" label="Jobs Booked" value={`${jobsBooked}`} color={C.blue} x={280} y={90} delay={18} />
      <MetricCard icon="💰" label="Revenue" value={`€${revenue.toLocaleString()}`} color={C.gold} x={520} y={90} delay={26} />
      <MetricCard icon="🎯" label="Missed Calls" value="0" color={C.purple} x={760} y={90} delay={34} />
      {/* Uptime */}
      <MetricCard icon="⚡" label="AI Uptime" value="99.9%" color={C.cyan} x={1000} y={90} delay={42} />
      <MetricCard icon="⏱️" label="Avg Response" value="0.8s" color={C.purple} x={1240} y={90} delay={50} />
      {/* Status bar */}
      <div style={{ position: "absolute", top: 90, right: 40, zIndex: 20 }}>
        <Pop delay={8}>
          <div style={{ background: `${C.cyan}15`, border: `1px solid ${C.cyan}33`, borderRadius: 10, padding: "8px 16px", display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 14, fontWeight: 700, color: C.cyan }}>All Systems Operational ✓</span>
          </div>
        </Pop>
      </div>
      {/* Live feed */}
      <div style={{ position: "absolute", left: 40, top: 240, zIndex: 10 }}>
        <Pop delay={15}>
          <LiveFeed events={[
            { time: "09:12", text: "📞 Call answered — John Murphy (Pipe Repair)", color: C.cyan, delay: 30 },
            { time: "09:15", text: "✅ Job booked — Thu 10AM with Mike", color: C.blue, delay: 50 },
            { time: "09:15", text: "💬 SMS confirmation sent", color: C.gold, delay: 60 },
            { time: "09:34", text: "📞 Call answered — Sarah O'Connor (Quote)", color: C.cyan, delay: 80 },
            { time: "09:36", text: "📋 Quote sent via SMS — €800-€1,200", color: C.purple, delay: 95 },
            { time: "10:02", text: "📞 Call answered — Emergency leak", color: C.orange, delay: 120 },
            { time: "10:03", text: "🚨 Emergency booked — Today 11AM", color: C.red, delay: 135 },
            { time: "10:03", text: "👷 Mike notified of emergency", color: C.blue, delay: 145 },
            { time: "10:45", text: "📞 Spam call detected & filtered", color: C.gray, delay: 170 },
            { time: "11:12", text: "📞 Call answered — Boiler service enquiry", color: C.cyan, delay: 195 },
            { time: "11:14", text: "✅ Job booked — Fri 2PM with Dave", color: C.blue, delay: 210 },
            { time: "11:30", text: "⏰ Reminder sent — Tomorrow's jobs", color: C.gold, delay: 240 },
          ]} />
        </Pop>
      </div>
      {/* Right side: mini charts */}
      <div style={{ position: "absolute", right: 40, top: 240, zIndex: 10, width: 440 }}>
        <Pop delay={20}>
          <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 16, padding: "18px", marginBottom: 16 }}>
            <div style={{ fontSize: 14, fontWeight: 800, color: C.white, marginBottom: 12 }}>Today's Bookings</div>
            <div style={{ display: "flex", alignItems: "flex-end", gap: 8, height: 100 }}>
              {["8AM", "9AM", "10AM", "11AM", "12PM", "1PM", "2PM", "3PM"].map((h, i) => {
                const barH = interpolate(f, [40 + i * 15, 55 + i * 15], [0, [20, 60, 80, 40, 0, 30, 50, 20][i]], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
                return (
                  <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
                    <div style={{ width: "100%", height: barH, borderRadius: "4px 4px 2px 2px", background: `linear-gradient(180deg,${C.cyan},${C.purple})`, boxShadow: barH > 0 ? `0 0 8px ${C.cyanGlow}` : "none" }} />
                    <span style={{ fontSize: 9, color: C.gray }}>{h}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </Pop>
        <Pop delay={30}>
          <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 16, padding: "18px" }}>
            <div style={{ fontSize: 14, fontWeight: 800, color: C.white, marginBottom: 12 }}>Worker Status</div>
            {[
              { name: "Mike O'Brien", status: "On Job", color: C.orange, icon: "🔧" },
              { name: "Dave Walsh", status: "Available", color: C.cyan, icon: "✅" },
              { name: "Sarah Kelly", status: "En Route", color: C.blue, icon: "🚗" },
            ].map((w, i) => (
              <Pop key={i} delay={50 + i * 15}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
                  <span style={{ fontSize: 18 }}>{w.icon}</span>
                  <span style={{ fontSize: 14, fontWeight: 600, color: C.white, flex: 1 }}>{w.name}</span>
                  <span style={{ fontSize: 12, fontWeight: 700, color: w.color, padding: "3px 10px", borderRadius: 6, background: `${w.color}15` }}>{w.status}</span>
                </div>
              </Pop>
            ))}
          </div>
        </Pop>
      </div>
    </AbsoluteFill>
  );
};

const L7_CTA: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
    <BG /><Orbs colors={[C.purpleGlow, C.cyanGlow]} />
    <div style={{ textAlign: "center", zIndex: 2 }}>
      <Boom text="Your business." delay={0} size={52} />
      <Boom text="On autopilot. ⚡" delay={12} size={48} color={C.cyan} />
      <Pop delay={28} scale><Logo size={56} /></Pop>
      <Pop delay={35} style={{ marginTop: 8 }}><span style={{ fontSize: 20, color: C.gray }}>bookedforyou.ie — Try free for 14 days</span></Pop>
    </div>
  </AbsoluteFill>
);

export const Landscape7_WarRoom: React.FC = () => {
  const scenes = [{ c: L7_WarRoom, d: 320 }, { c: L7_CTA, d: 80 }];
  let s = 0;
  return <AbsoluteFill style={{ fontFamily: F }}>{scenes.map((sc, i) => { const from = s; s += sc.d; const Sc = sc.c; return <Sequence key={i} from={from} durationInFrames={sc.d}><Fade dur={sc.d}><Sc /></Fade></Sequence>; })}</AbsoluteFill>;
};


// ═══════════════════════════════════════════════════════════
// VIDEO 19: "Year in Review" (LANDSCAPE ~25s) — Spotify Wrapped style
// Animated annual stats with colorful reveals
// ═══════════════════════════════════════════════════════════

const WrappedSlide: React.FC<{ bg: string; children: React.ReactNode }> = ({ bg, children }) => (
  <AbsoluteFill style={{ background: bg, justifyContent: "center", alignItems: "center", padding: "0 80px" }}>
    {children}
  </AbsoluteFill>
);

const L8_S1: React.FC = () => (
  <WrappedSlide bg="linear-gradient(135deg,#1a0a3e,#0a2540)">
    <Orbs colors={[C.purpleGlow, C.cyanGlow]} />
    <div style={{ textAlign: "center", zIndex: 2 }}>
      <Pop delay={0} scale><Logo size={56} /></Pop>
      <Boom text="Your 2025" delay={12} size={64} dur={80} />
      <Boom text="Year in Review ✨" delay={25} size={48} color={C.purpleLight} dur={65} />
    </div>
  </WrappedSlide>
);

const L8_S2: React.FC = () => {
  const f = useCurrentFrame();
  const calls = Math.floor(interpolate(f, [15, 50], [0, 2847], { extrapolateRight: "clamp" }));
  return (
    <WrappedSlide bg="linear-gradient(135deg,#0a2540,#1a3a5c)">
      <Orbs colors={[C.cyanGlow, C.blueGlow]} />
      <div style={{ textAlign: "center", zIndex: 2 }}>
        <Boom text="Your AI answered" delay={0} size={36} color={C.gray} dur={90} />
        <Pop delay={12} scale>
          <span style={{ fontSize: 140, fontWeight: 900, color: C.cyan, fontFamily: "monospace", textShadow: `0 0 60px ${C.cyanGlow}`, letterSpacing: -4, display: "block" }}>{calls.toLocaleString()}</span>
        </Pop>
        <Boom text="phone calls" delay={15} size={44} dur={75} />
        <Boom text="That's 8 calls per day 📞" delay={50} size={32} color={C.purpleLight} dur={40} />
      </div>
    </WrappedSlide>
  );
};

const L8_S3: React.FC = () => {
  const f = useCurrentFrame();
  const revenue = Math.floor(interpolate(f, [15, 50], [0, 142800], { extrapolateRight: "clamp" }));
  return (
    <WrappedSlide bg="linear-gradient(135deg,#1a3a1a,#0a2a1a)">
      <Orbs colors={["rgba(255,214,10,0.2)", C.cyanGlow]} />
      <div style={{ textAlign: "center", zIndex: 2 }}>
        <Boom text="Total revenue booked" delay={0} size={36} color={C.gray} dur={90} />
        <Pop delay={12} scale>
          <span style={{ fontSize: 120, fontWeight: 900, color: C.gold, fontFamily: "monospace", textShadow: `0 0 60px rgba(255,214,10,0.4)`, letterSpacing: -4, display: "block" }}>€{revenue.toLocaleString()}</span>
        </Pop>
        <Boom text="All booked by AI 🤖" delay={50} size={32} color={C.cyan} dur={40} />
      </div>
    </WrappedSlide>
  );
};

const L8_S4: React.FC = () => (
  <WrappedSlide bg="linear-gradient(135deg,#2a1a3e,#1a0a2e)">
    <Orbs colors={[C.purpleGlow, "rgba(255,0,110,0.2)"]} />
    <div style={{ textAlign: "center", zIndex: 2 }}>
      <Boom text="Your top stats" delay={0} size={40} color={C.gray} dur={120} />
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 30, marginTop: 24, maxWidth: 900 }}>
        {[
          { value: "0", label: "Missed Calls", icon: "🎯", color: C.cyan, delay: 15 },
          { value: "1,247", label: "Jobs Booked", icon: "📅", color: C.blue, delay: 25 },
          { value: "98%", label: "Customer Satisfaction", icon: "⭐", color: C.gold, delay: 35 },
          { value: "4,200", label: "SMS Reminders Sent", icon: "💬", color: C.purple, delay: 45 },
          { value: "12", label: "No-Shows Prevented", icon: "🛡️", color: C.orange, delay: 55 },
          { value: "€99/mo", label: "Total Cost", icon: "💰", color: C.cyan, delay: 65 },
        ].map((s, i) => (
          <Pop key={i} delay={s.delay} scale>
            <div style={{ background: "rgba(255,255,255,0.04)", border: `1px solid ${s.color}33`, borderRadius: 20, padding: "20px 16px", textAlign: "center" }}>
              <span style={{ fontSize: 28 }}>{s.icon}</span>
              <div style={{ fontSize: 36, fontWeight: 900, color: s.color, margin: "6px 0 4px", fontFamily: "monospace" }}>{s.value}</div>
              <div style={{ fontSize: 14, color: C.gray, fontWeight: 600 }}>{s.label}</div>
            </div>
          </Pop>
        ))}
      </div>
    </div>
  </WrappedSlide>
);

const L8_CTA: React.FC = () => (
  <WrappedSlide bg={`linear-gradient(135deg,${C.bg2},${C.bg1})`}>
    <Orbs colors={[C.purpleGlow, C.cyanGlow]} />
    <div style={{ textAlign: "center", zIndex: 2 }}>
      <Boom text="Make 2025 your year" delay={0} size={48} />
      <Pop delay={15} scale><Logo size={56} /></Pop>
      <Boom text="Get started today" delay={22} size={36} color={C.cyan} />
      <Pop delay={38} style={{ marginTop: 8 }}><span style={{ fontSize: 22, color: C.gray }}>bookedforyou.ie</span></Pop>
    </div>
  </WrappedSlide>
);

export const Landscape8_YearReview: React.FC = () => {
  const scenes = [{ c: L8_S1, d: 100 }, { c: L8_S2, d: 100 }, { c: L8_S3, d: 100 }, { c: L8_S4, d: 140 }, { c: L8_CTA, d: 80 }];
  let s = 0;
  return <AbsoluteFill style={{ fontFamily: F }}>{scenes.map((sc, i) => { const from = s; s += sc.d; const Sc = sc.c; return <Sequence key={i} from={from} durationInFrames={sc.d}><Fade dur={sc.d}><Sc /></Fade></Sequence>; })}</AbsoluteFill>;
};
