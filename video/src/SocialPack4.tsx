import {
  AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate, spring, Sequence,
} from "remotion";
import React from "react";

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

const Boom: React.FC<{ text: string; delay: number; color?: string; size?: number; dur?: number }> = ({ text, delay, color = C.white, size = 72, dur = 60 }) => {
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
  return <AbsoluteFill style={{ opacity: interpolate(f, [0, 6, dur - 6, dur], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }}>{children}</AbsoluteFill>;
};

const Logo: React.FC<{ size?: number }> = ({ size = 48 }) => (
  <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 10 }}>
    <div style={{ width: size, height: size, borderRadius: size * 0.26, background: `linear-gradient(135deg,${C.purple},${C.cyan})`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: size * 0.55, boxShadow: `0 0 ${size}px ${C.purpleGlow}` }}>⚡</div>
    <span style={{ fontSize: size * 0.65, fontWeight: 900, color: C.white, letterSpacing: -1 }}>BookedForYou</span>
  </div>
);

// ═══════════════════════════════════════════════════════════
// VIDEO 12: "Would You Rather" (VERTICAL) — Poll-style
// Two options side by side, one gets selected
// ═══════════════════════════════════════════════════════════

const PollOption: React.FC<{ emoji: string; title: string; items: string[]; color: string; selected: boolean; side: "left" | "right"; delay: number }> = ({ emoji, title, items, color, selected, side, delay }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: f - delay, fps, config: { damping: 12, mass: 0.5 } });
  const op = interpolate(f - delay, [0, 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const selScale = selected ? interpolate(f, [120, 135], [1, 1.05], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) : interpolate(f, [120, 135], [1, 0.9], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const selOp = selected ? 1 : interpolate(f, [120, 135], [1, 0.4], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div style={{ flex: 1, opacity: op * selOp, transform: `translateX(${interpolate(s, [0, 1], [side === "left" ? -40 : 40, 0])}px) scale(${selScale})`, padding: "0 8px" }}>
      <div style={{ background: `${color}08`, border: `2px solid ${selected ? color : `${color}33`}`, borderRadius: 24, padding: "24px 18px", textAlign: "center", boxShadow: selected ? `0 0 30px ${color}30` : "none" }}>
        <div style={{ fontSize: 56, marginBottom: 10 }}>{emoji}</div>
        <div style={{ fontSize: 22, fontWeight: 800, color: selected ? color : C.white, marginBottom: 14 }}>{title}</div>
        {items.map((item, i) => (
          <div key={i} style={{ fontSize: 15, color: C.lightGray, marginBottom: 8, display: "flex", alignItems: "center", gap: 8, justifyContent: "center" }}>
            <span style={{ color: selected ? C.cyan : C.red }}>{selected ? "✓" : "✗"}</span>
            <span>{item}</span>
          </div>
        ))}
        {/* Vote bar */}
        {f > 120 && (
          <div style={{ marginTop: 14, height: 8, background: "rgba(255,255,255,0.06)", borderRadius: 4, overflow: "hidden" }}>
            <div style={{ width: selected ? "87%" : "13%", height: "100%", background: color, borderRadius: 4, transition: "width 0.3s" }} />
          </div>
        )}
        {f > 120 && <div style={{ fontSize: 24, fontWeight: 900, color, marginTop: 8 }}>{selected ? "87%" : "13%"}</div>}
      </div>
    </div>
  );
};

const V12_Poll: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: "center", padding: "0 20px" }}>
    <BG /><Orbs colors={[C.purpleGlow, "rgba(255,50,50,0.15)"]} />
    <div style={{ zIndex: 2 }}>
      <Boom text="Would you rather? 🤔" delay={0} size={40} color={C.gray} dur={160} />
      <div style={{ display: "flex", gap: 12, marginTop: 16 }}>
        <PollOption emoji="👤" title="Human Receptionist" items={["€2,500/month", "9-5 only", "Sick days", "1 call at a time"]} color={C.red} selected={false} side="left" delay={15} />
        <PollOption emoji="🤖" title="AI Receptionist" items={["€99/month", "24/7/365", "Never sick", "Unlimited calls"]} color={C.cyan} selected side="right" delay={25} />
      </div>
    </div>
  </AbsoluteFill>
);

const V12_CTA: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 50px" }}>
    <BG /><Orbs colors={[C.cyanGlow, C.purpleGlow]} />
    <div style={{ textAlign: "center", zIndex: 2 }}>
      <Boom text="87% chose AI 🤖" delay={0} size={48} color={C.cyan} />
      <Pop delay={15} scale><Logo size={44} /></Pop>
      <Pop delay={22} style={{ marginTop: 8 }}><span style={{ fontSize: 16, color: C.gray }}>bookedforyou.ie</span></Pop>
    </div>
  </AbsoluteFill>
);

export const Social12_WouldYouRather: React.FC = () => {
  const scenes = [{ c: V12_Poll, d: 170 }, { c: V12_CTA, d: 60 }];
  let s = 0;
  return <AbsoluteFill style={{ fontFamily: F }}>{scenes.map((sc, i) => { const from = s; s += sc.d; const Sc = sc.c; return <Sequence key={i} from={from} durationInFrames={sc.d}><Fade dur={sc.d}><Sc /></Fade></Sequence>; })}</AbsoluteFill>;
};


// ═══════════════════════════════════════════════════════════
// VIDEO 13: "Guess the Price" (VERTICAL) — Game show reveal
// ═══════════════════════════════════════════════════════════

const V13_S1: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 50px" }}>
    <BG /><Orbs colors={[C.purpleGlow, "rgba(255,214,10,0.2)"]} />
    <div style={{ textAlign: "center", zIndex: 2 }}>
      <Boom text="🎯 GUESS THE PRICE" delay={0} size={44} color={C.gold} />
      <Pop delay={15} scale>
        <div style={{ margin: "20px 0", background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 24, padding: "24px 20px" }}>
          <div style={{ fontSize: 20, color: C.gray, marginBottom: 8 }}>An AI that...</div>
          <div style={{ fontSize: 18, color: C.white, fontWeight: 600, lineHeight: 1.6 }}>
            📞 Answers all your calls<br />
            📅 Books jobs automatically<br />
            💬 Sends SMS reminders<br />
            👥 Saves customer details<br />
            👷 Assigns workers<br />
            💰 Tracks revenue<br />
            🔧 Knows all your services
          </div>
        </div>
      </Pop>
      <Boom text="How much? 🤔" delay={50} size={48} />
    </div>
  </AbsoluteFill>
);

const V13_S2: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  // Wrong guesses crossing out
  const guesses = [
    { amount: "€500/mo", delay: 5 },
    { amount: "€300/mo", delay: 20 },
    { amount: "€200/mo", delay: 35 },
  ];
  const revealDelay = 55;
  const revealS = spring({ frame: f - revealDelay, fps, config: { damping: 6, mass: 0.3, stiffness: 250 } });
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 50px" }}>
      <BG /><Orbs colors={[C.cyanGlow, C.purpleGlow]} />
      <div style={{ textAlign: "center", zIndex: 2 }}>
        {guesses.map((g, i) => {
          const op = interpolate(f, [g.delay, g.delay + 6, g.delay + 12, g.delay + 18], [0, 1, 1, 0.3], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          return (
            <div key={i} style={{ opacity: op, marginBottom: 10 }}>
              <span style={{ fontSize: 44, fontWeight: 900, color: C.red, textDecoration: f > g.delay + 10 ? "line-through" : "none" }}>{g.amount}</span>
              {f > g.delay + 10 && <span style={{ fontSize: 28, marginLeft: 12 }}>❌</span>}
            </div>
          );
        })}
        {f > revealDelay && (
          <div style={{ transform: `scale(${revealS})`, marginTop: 20 }}>
            <div style={{ fontSize: 28, color: C.gray, marginBottom: 8 }}>Actually...</div>
            <span style={{ fontSize: 120, fontWeight: 900, color: C.cyan, textShadow: `0 0 50px ${C.cyanGlow}`, letterSpacing: -4 }}>€99</span>
            <div style={{ fontSize: 24, color: C.gray }}>per month</div>
            <div style={{ fontSize: 48, marginTop: 10 }}>🤯</div>
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};

const V13_CTA: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 50px" }}>
    <BG /><Orbs colors={[C.cyanGlow, C.purpleGlow]} />
    <div style={{ textAlign: "center", zIndex: 2 }}>
      <Pop delay={0} scale><Logo size={44} /></Pop>
      <Boom text="€99. That's it." delay={10} size={48} color={C.cyan} />
      <Boom text="Try free for 14 days" delay={25} size={36} color={C.gray} />
      <Pop delay={38} style={{ marginTop: 8 }}><span style={{ fontSize: 16, color: C.gray }}>bookedforyou.ie</span></Pop>
    </div>
  </AbsoluteFill>
);

export const Social13_GuessPrice: React.FC = () => {
  const scenes = [{ c: V13_S1, d: 100 }, { c: V13_S2, d: 120 }, { c: V13_CTA, d: 60 }];
  let s = 0;
  return <AbsoluteFill style={{ fontFamily: F }}>{scenes.map((sc, i) => { const from = s; s += sc.d; const Sc = sc.c; return <Sequence key={i} from={from} durationInFrames={sc.d}><Fade dur={sc.d}><Sc /></Fade></Sequence>; })}</AbsoluteFill>;
};


// ═══════════════════════════════════════════════════════════
// VIDEO 14: "Your Week" (VERTICAL) — Calendar comparison
// Left: chaotic week without AI, Right: organized week with AI
// ═══════════════════════════════════════════════════════════

const WeekDay: React.FC<{ day: string; withAI: { icon: string; text: string; color: string }; withoutAI: { icon: string; text: string }; delay: number; showAI: boolean }> = ({ day, withAI, withoutAI, delay, showAI }) => {
  const f = useCurrentFrame();
  const op = interpolate(f, [delay, delay + 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const x = interpolate(f, [delay, delay + 8], [30, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div style={{ opacity: op, transform: `translateX(${x}px)`, display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
      <div style={{ width: 50, fontSize: 14, fontWeight: 800, color: C.gray, flexShrink: 0 }}>{day}</div>
      {!showAI ? (
        <div style={{ flex: 1, padding: "10px 14px", background: "rgba(255,50,50,0.06)", border: "1px solid rgba(255,50,50,0.15)", borderRadius: 12, display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 18 }}>{withoutAI.icon}</span>
          <span style={{ fontSize: 14, color: "#ff8a8a", fontWeight: 600 }}>{withoutAI.text}</span>
        </div>
      ) : (
        <div style={{ flex: 1, padding: "10px 14px", background: `${withAI.color}08`, border: `1px solid ${withAI.color}22`, borderRadius: 12, display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 18 }}>{withAI.icon}</span>
          <span style={{ fontSize: 14, color: withAI.color, fontWeight: 600 }}>{withAI.text}</span>
        </div>
      )}
    </div>
  );
};

const weekData = [
  { day: "MON", withoutAI: { icon: "📵", text: "3 missed calls" }, withAI: { icon: "✅", text: "3 jobs booked", color: C.cyan } },
  { day: "TUE", withoutAI: { icon: "😤", text: "Customer complained" }, withAI: { icon: "💬", text: "Reminders sent", color: C.blue } },
  { day: "WED", withoutAI: { icon: "🚫", text: "No-show (no reminder)" }, withAI: { icon: "📅", text: "Calendar synced", color: C.purple } },
  { day: "THU", withoutAI: { icon: "💸", text: "Lost €800 job" }, withAI: { icon: "💰", text: "€800 job booked", color: C.gold } },
  { day: "FRI", withoutAI: { icon: "📝", text: "Forgot to invoice" }, withAI: { icon: "📋", text: "Invoice sent", color: C.cyan } },
  { day: "SAT", withoutAI: { icon: "📵", text: "Emergency missed" }, withAI: { icon: "🚨", text: "Emergency handled", color: C.orange } },
  { day: "SUN", withoutAI: { icon: "😩", text: "Stressed about Monday" }, withAI: { icon: "😎", text: "Relaxing. AI's got it.", color: C.cyan } },
];

const V14_Without: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: "center", padding: "0 30px" }}>
    <BG /><Orbs colors={["rgba(255,50,50,0.15)", C.purpleGlow]} />
    <div style={{ zIndex: 2 }}>
      <Boom text="Your week" delay={0} size={44} color={C.gray} dur={120} />
      <Boom text="WITHOUT AI ❌" delay={10} size={48} color={C.red} dur={110} />
      <div style={{ marginTop: 16 }}>
        {weekData.map((d, i) => <WeekDay key={i} {...d} delay={20 + i * 10} showAI={false} />)}
      </div>
    </div>
  </AbsoluteFill>
);

const V14_With: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: "center", padding: "0 30px" }}>
    <BG /><Orbs colors={[C.cyanGlow, C.purpleGlow]} />
    <div style={{ zIndex: 2 }}>
      <Boom text="Your week" delay={0} size={44} color={C.gray} dur={120} />
      <Boom text="WITH AI ✅" delay={10} size={48} color={C.cyan} dur={110} />
      <div style={{ marginTop: 16 }}>
        {weekData.map((d, i) => <WeekDay key={i} {...d} delay={20 + i * 10} showAI />)}
      </div>
    </div>
  </AbsoluteFill>
);

const V14_CTA: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 50px" }}>
    <BG /><Orbs colors={[C.cyanGlow, C.purpleGlow]} />
    <div style={{ textAlign: "center", zIndex: 2 }}>
      <Boom text="Which week" delay={0} size={48} />
      <Boom text="do you want? 🤔" delay={10} size={44} color={C.gray} />
      <Pop delay={25} scale><Logo size={44} /></Pop>
      <Pop delay={32} style={{ marginTop: 8 }}><span style={{ fontSize: 16, color: C.gray }}>bookedforyou.ie</span></Pop>
    </div>
  </AbsoluteFill>
);

export const Social14_YourWeek: React.FC = () => {
  const scenes = [{ c: V14_Without, d: 120 }, { c: V14_With, d: 120 }, { c: V14_CTA, d: 70 }];
  let s = 0;
  return <AbsoluteFill style={{ fontFamily: F }}>{scenes.map((sc, i) => { const from = s; s += sc.d; const Sc = sc.c; return <Sequence key={i} from={from} durationInFrames={sc.d}><Fade dur={sc.d}><Sc /></Fade></Sequence>; })}</AbsoluteFill>;
};


// ═══════════════════════════════════════════════════════════
// VIDEO 15: "Domino Effect" (LANDSCAPE) — Chain reaction of losses
// One missed call → customer leaves → bad review → lost referrals → €€€ gone
// ═══════════════════════════════════════════════════════════

const Domino: React.FC<{ icon: string; text: string; amount: string; x: number; delay: number; color: string }> = ({ icon, text, amount, x, delay, color }) => {
  const f = useCurrentFrame();
  // Domino falls (rotates from standing to fallen)
  const fallAngle = interpolate(f, [delay, delay + 12], [0, 90], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: (t) => t * t });
  const op = interpolate(f - delay, [0, 5], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const isFallen = f > delay + 12;
  return (
    <div style={{ position: "absolute", left: x, top: 340, transform: `translateX(-50%)`, opacity: op, zIndex: 10 }}>
      {/* Domino piece */}
      <div style={{ width: 100, height: 160, borderRadius: 12, background: isFallen ? `${color}15` : "rgba(255,255,255,0.06)", border: `2px solid ${isFallen ? color : "rgba(255,255,255,0.1)"}`, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 8, transform: `rotateZ(${fallAngle}deg)`, transformOrigin: "bottom center", boxShadow: isFallen ? `0 0 20px ${color}20` : "none" }}>
        <span style={{ fontSize: 32 }}>{icon}</span>
        <span style={{ fontSize: 12, fontWeight: 700, color: isFallen ? color : C.white, textAlign: "center", padding: "0 6px" }}>{text}</span>
      </div>
      {/* Amount below */}
      {isFallen && <div style={{ textAlign: "center", marginTop: 8, fontSize: 18, fontWeight: 900, color }}>{amount}</div>}
    </div>
  );
};

const L5_Dominoes: React.FC = () => {
  const f = useCurrentFrame();
  // Chain: missed call → customer leaves → bad review → lost referrals → competitor wins → revenue gone
  const dominoes = [
    { icon: "📵", text: "Missed Call", amount: "-1 customer", x: 200, delay: 15, color: C.red },
    { icon: "🚶", text: "Customer Leaves", amount: "-€350", x: 440, delay: 30, color: C.orange },
    { icon: "⭐", text: "Bad Review", amount: "-reputation", x: 680, delay: 45, color: C.gold },
    { icon: "🔗", text: "Lost Referrals", amount: "-3 jobs", x: 920, delay: 60, color: C.pink },
    { icon: "🏆", text: "Competitor Wins", amount: "+their revenue", x: 1160, delay: 75, color: C.purple },
    { icon: "💸", text: "Revenue Gone", amount: "-€4,200/yr", x: 1400, delay: 90, color: C.red },
  ];
  // Connection lines
  const totalLoss = Math.floor(interpolate(f, [90, 130], [0, 4200], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }));
  return (
    <AbsoluteFill>
      <BG /><Orbs colors={["rgba(255,50,50,0.15)", C.purpleGlow, "rgba(255,107,53,0.1)"]} />
      <div style={{ position: "absolute", top: 40, left: 0, right: 0, textAlign: "center", zIndex: 20 }}>
        <Boom text="One missed call starts a chain reaction 💥" delay={0} size={38} dur={160} />
      </div>
      {/* Arrow connections */}
      <svg style={{ position: "absolute", top: 0, left: 0, width: 1920, height: 1080, pointerEvents: "none", zIndex: 5 }}>
        {dominoes.slice(0, -1).map((d, i) => {
          const next = dominoes[i + 1];
          const lineOp = interpolate(f, [d.delay + 10, d.delay + 15], [0, 0.4], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          return <line key={i} x1={d.x + 50} y1={420} x2={next.x - 50} y2={420} stroke={C.red} strokeWidth={2} strokeDasharray="6 4" opacity={lineOp} />;
        })}
      </svg>
      {dominoes.map((d, i) => <Domino key={i} {...d} />)}
      {/* Total loss counter */}
      <div style={{ position: "absolute", bottom: 80, left: 0, right: 0, textAlign: "center", zIndex: 20 }}>
        {f > 90 && <Boom text={`Total annual loss: €${totalLoss.toLocaleString()}`} delay={90} size={36} color={C.red} dur={80} />}
        {f > 110 && <Boom text="From just ONE missed call." delay={115} size={28} color={C.gray} dur={50} />}
      </div>
    </AbsoluteFill>
  );
};

const L5_Fix: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
    <BG /><Orbs colors={[C.cyanGlow, C.purpleGlow]} />
    <div style={{ textAlign: "center", zIndex: 2 }}>
      <Boom text="Or just..." delay={0} size={48} color={C.gray} />
      <Boom text="never miss a call 🤖" delay={12} size={52} color={C.cyan} />
      <Pop delay={28} scale><Logo size={56} /></Pop>
      <Pop delay={35} style={{ marginTop: 8 }}><span style={{ fontSize: 20, color: C.gray }}>bookedforyou.ie</span></Pop>
    </div>
  </AbsoluteFill>
);

export const Landscape5_Domino: React.FC = () => {
  const scenes = [{ c: L5_Dominoes, d: 180 }, { c: L5_Fix, d: 70 }];
  let s = 0;
  return <AbsoluteFill style={{ fontFamily: F }}>{scenes.map((sc, i) => { const from = s; s += sc.d; const Sc = sc.c; return <Sequence key={i} from={from} durationInFrames={sc.d}><Fade dur={sc.d}><Sc /></Fade></Sequence>; })}</AbsoluteFill>;
};


// ═══════════════════════════════════════════════════════════
// VIDEO 16: "Feature Bingo" (LANDSCAPE) — Satisfying bingo card
// Features stamp in one by one, then BINGO!
// ═══════════════════════════════════════════════════════════

const BingoCell: React.FC<{ icon: string; label: string; stamped: boolean; delay: number }> = ({ icon, label, stamped, delay }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const stampS = spring({ frame: f - delay, fps, config: { damping: 6, mass: 0.3, stiffness: 300 } });
  const isStamped = f > delay;
  return (
    <div style={{ background: isStamped ? `${C.cyan}10` : "rgba(255,255,255,0.03)", border: `2px solid ${isStamped ? `${C.cyan}44` : "rgba(255,255,255,0.06)"}`, borderRadius: 14, padding: "14px 8px", textAlign: "center", position: "relative", overflow: "hidden", boxShadow: isStamped ? `0 0 15px ${C.cyanGlow}` : "none" }}>
      <div style={{ fontSize: 30, marginBottom: 4 }}>{icon}</div>
      <div style={{ fontSize: 12, fontWeight: 700, color: isStamped ? C.cyan : C.gray }}>{label}</div>
      {/* Stamp overlay */}
      {isStamped && (
        <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", transform: `scale(${stampS}) rotate(-12deg)` }}>
          <span style={{ fontSize: 48, opacity: 0.3 }}>✅</span>
        </div>
      )}
    </div>
  );
};

const L6_Bingo: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const cells = [
    { icon: "📞", label: "AI Calls", delay: 20 },
    { icon: "📅", label: "Auto Book", delay: 35 },
    { icon: "💬", label: "SMS", delay: 50 },
    { icon: "👥", label: "CRM", delay: 65 },
    { icon: "👷", label: "Workers", delay: 80 },
    { icon: "💰", label: "Invoicing", delay: 95 },
    { icon: "🔧", label: "Services", delay: 110 },
    { icon: "📊", label: "Analytics", delay: 125 },
    { icon: "⚡", label: "24/7", delay: 140 },
  ];
  // BINGO text after all stamped
  const bingoS = spring({ frame: f - 155, fps, config: { damping: 5, mass: 0.3, stiffness: 300 } });
  const bingoOp = interpolate(f, [155, 160], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <BG /><Orbs colors={[C.cyanGlow, C.purpleGlow, "rgba(255,214,10,0.15)"]} />
      <div style={{ zIndex: 2, textAlign: "center" }}>
        <Boom text="Feature Bingo 🎯" delay={0} size={44} dur={180} />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 160px)", gap: 12, marginTop: 20, justifyContent: "center" }}>
          {cells.map((c, i) => <BingoCell key={i} {...c} stamped={f > c.delay} />)}
        </div>
        {/* BINGO overlay */}
        {f > 155 && (
          <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", zIndex: 20 }}>
            <div style={{ transform: `scale(${bingoS}) rotate(-8deg)`, opacity: bingoOp }}>
              <span style={{ fontSize: 140, fontWeight: 900, color: C.gold, textShadow: `0 0 60px ${C.gold}40, 0 8px 30px rgba(0,0,0,0.5)`, letterSpacing: 10 }}>BINGO!</span>
            </div>
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};

const L6_CTA: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
    <BG /><Orbs colors={[C.purpleGlow, C.cyanGlow]} />
    <div style={{ textAlign: "center", zIndex: 2 }}>
      <Boom text="All features. One app." delay={0} size={48} />
      <Pop delay={15} scale><Logo size={56} /></Pop>
      <Pop delay={22} style={{ marginTop: 8 }}><span style={{ fontSize: 20, color: C.gray }}>bookedforyou.ie — Try free</span></Pop>
    </div>
  </AbsoluteFill>
);

export const Landscape6_Bingo: React.FC = () => {
  const scenes = [{ c: L6_Bingo, d: 200 }, { c: L6_CTA, d: 60 }];
  let s = 0;
  return <AbsoluteFill style={{ fontFamily: F }}>{scenes.map((sc, i) => { const from = s; s += sc.d; const Sc = sc.c; return <Sequence key={i} from={from} durationInFrames={sc.d}><Fade dur={sc.d}><Sc /></Fade></Sequence>; })}</AbsoluteFill>;
};
