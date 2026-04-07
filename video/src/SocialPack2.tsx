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
  iMessageBlue: "#007AFF", iMessageGray: "#E9E9EB", iMessageBg: "#fff",
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

const Boom: React.FC<{ text: string; delay: number; color?: string; size?: number }> = ({ text, delay, color = C.white, size = 72 }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: f - delay, fps, config: { damping: 6, mass: 0.3, stiffness: 250 } });
  const op = interpolate(f - delay, [0, 5, 55, 65], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
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
// VIDEO 6: "iMessage Story" (VERTICAL) — Notification-style
// Shows iPhone notifications popping in like a real phone
// ═══════════════════════════════════════════════════════════

const IMessageBubble: React.FC<{ text: string; from: "me" | "them"; delay: number }> = ({ text, from, delay }) => {
  const f = useCurrentFrame();
  const op = interpolate(f, [delay, delay + 6], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const y = interpolate(f, [delay, delay + 6], [15, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const isMe = from === "me";
  return (
    <div style={{ opacity: op, transform: `translateY(${y}px)`, alignSelf: isMe ? "flex-end" : "flex-start", maxWidth: "80%" }}>
      <div style={{
        padding: "10px 16px", fontSize: 16, lineHeight: 1.4,
        borderRadius: isMe ? "18px 18px 4px 18px" : "18px 18px 18px 4px",
        background: isMe ? C.iMessageBlue : C.iMessageGray,
        color: isMe ? C.white : "#1a1a1a",
        fontWeight: 500,
      }}>{text}</div>
    </div>
  );
};

const Notification: React.FC<{ title: string; body: string; icon: string; delay: number }> = ({ title, body, icon, delay }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const slideIn = spring({ frame: f - delay, fps, config: { damping: 14, mass: 0.5 } });
  const y = interpolate(slideIn, [0, 1], [-80, 0]);
  const op = interpolate(f - delay, [0, 5, 50, 58], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div style={{ opacity: op, transform: `translateY(${y}px)`, width: "100%", padding: "0 20px", position: "absolute", top: 60, zIndex: 100 }}>
      <div style={{
        background: "rgba(255,255,255,0.95)", borderRadius: 16, padding: "12px 16px",
        display: "flex", gap: 12, alignItems: "center",
        boxShadow: "0 8px 30px rgba(0,0,0,0.15)",
        backdropFilter: "blur(20px)",
      }}>
        <div style={{ width: 40, height: 40, borderRadius: 10, background: `linear-gradient(135deg,${C.purple},${C.cyan})`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20, flexShrink: 0 }}>{icon}</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: "#1a1a1a" }}>{title}</div>
          <div style={{ fontSize: 12, color: "#666", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{body}</div>
        </div>
        <div style={{ fontSize: 11, color: "#999", flexShrink: 0 }}>now</div>
      </div>
    </div>
  );
};

const V6_Messages: React.FC = () => {
  return (
    <AbsoluteFill style={{ background: "#f2f2f7" }}>
      {/* Status bar */}
      <div style={{ display: "flex", justifyContent: "space-between", padding: "14px 24px 0", fontSize: 14, fontWeight: 600, color: "#1a1a1a" }}>
        <span>9:41</span>
        <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
          <span style={{ fontSize: 12 }}>📶</span>
          <span style={{ fontSize: 12 }}>🔋</span>
        </div>
      </div>
      {/* Chat header */}
      <div style={{ textAlign: "center", padding: "16px 0 12px", borderBottom: "1px solid #e0e0e0" }}>
        <div style={{ width: 44, height: 44, borderRadius: "50%", background: `linear-gradient(135deg,${C.purple},${C.cyan})`, margin: "0 auto 6px", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 22 }}>⚡</div>
        <div style={{ fontSize: 16, fontWeight: 700, color: "#1a1a1a" }}>BookedForYou AI</div>
        <div style={{ fontSize: 12, color: "#8e8e93" }}>Your AI Receptionist</div>
      </div>
      {/* Messages */}
      <div style={{ flex: 1, padding: "16px 16px", display: "flex", flexDirection: "column", gap: 8 }}>
        <IMessageBubble from="them" text="📞 New call answered!" delay={10} />
        <IMessageBubble from="them" text="Customer: John Murphy — burst pipe emergency" delay={30} />
        <IMessageBubble from="them" text="✅ Booked: Thursday 10 AM with Mike" delay={55} />
        <IMessageBubble from="them" text="💬 SMS confirmation sent to customer" delay={80} />
        <IMessageBubble from="them" text="⏰ 24hr reminder scheduled" delay={100} />
        <IMessageBubble from="me" text="Perfect 👍" delay={125} />
        <IMessageBubble from="them" text="📞 Another call coming in..." delay={150} />
        <IMessageBubble from="them" text="Sarah O'Connor — boiler service quote" delay={170} />
        <IMessageBubble from="them" text="✅ Quote sent via SMS: €800-€1,200" delay={195} />
        <IMessageBubble from="me" text="This thing is unreal 🤯" delay={220} />
      </div>
      {/* Notifications sliding in */}
      <Notification title="BookedForYou" body="New booking: John Murphy — Pipe Repair, Thu 10AM" icon="⚡" delay={55} />
      <Notification title="BookedForYou" body="Quote sent to Sarah O'Connor — Boiler Service" icon="⚡" delay={195} />
    </AbsoluteFill>
  );
};

const V6_CTA: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 50px" }}>
    <Orbs colors={[C.purpleGlow, C.cyanGlow]} />
    <BG />
    <div style={{ textAlign: "center", zIndex: 2 }}>
      <Pop delay={0} scale><Logo size={44} /></Pop>
      <Boom text="While you work" delay={10} size={44} color={C.gray} />
      <Boom text="AI handles calls" delay={22} size={52} color={C.cyan} />
      <Pop delay={35} style={{ marginTop: 12 }}><span style={{ fontSize: 18, color: C.gray }}>bookedforyou.ie</span></Pop>
    </div>
  </AbsoluteFill>
);

export const Social6_IMessage: React.FC = () => {
  const scenes = [{ c: V6_Messages, d: 260 }, { c: V6_CTA, d: 70 }];
  let s = 0;
  return (
    <AbsoluteFill style={{ fontFamily: F }}>
      {scenes.map((sc, i) => { const from = s; s += sc.d; const Sc = sc.c; return <Sequence key={i} from={from} durationInFrames={sc.d}><Fade dur={sc.d}><Sc /></Fade></Sequence>; })}
    </AbsoluteFill>
  );
};


// ═══════════════════════════════════════════════════════════
// VIDEO 7: "Before / After" (VERTICAL) — Split screen drama
// Left/top = chaos, right/bottom = calm with AI
// ═══════════════════════════════════════════════════════════

const BeforePanel: React.FC<{ items: { icon: string; text: string; delay: number }[] }> = ({ items }) => {
  const f = useCurrentFrame();
  return (
    <div style={{ flex: 1, background: "linear-gradient(180deg,#1a0a0a,#2a0a0a)", padding: "30px 24px", display: "flex", flexDirection: "column", justifyContent: "center", position: "relative", overflow: "hidden" }}>
      {/* Red scan line */}
      <div style={{ position: "absolute", top: `${(f * 2) % 120}%`, left: 0, right: 0, height: 2, background: "rgba(255,50,50,0.3)" }} />
      <div style={{ textAlign: "center", marginBottom: 20 }}>
        <span style={{ fontSize: 16, fontWeight: 800, color: C.red, textTransform: "uppercase", letterSpacing: 3 }}>❌ WITHOUT AI</span>
      </div>
      {items.map((item, i) => {
        const op = interpolate(f, [item.delay, item.delay + 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        return (
          <div key={i} style={{ opacity: op, display: "flex", alignItems: "center", gap: 12, marginBottom: 14, padding: "10px 14px", background: "rgba(255,50,50,0.08)", borderRadius: 12, border: "1px solid rgba(255,50,50,0.15)" }}>
            <span style={{ fontSize: 24 }}>{item.icon}</span>
            <span style={{ fontSize: 17, fontWeight: 600, color: "#ff8a8a" }}>{item.text}</span>
          </div>
        );
      })}
    </div>
  );
};

const AfterPanel: React.FC<{ items: { icon: string; text: string; delay: number }[] }> = ({ items }) => {
  const f = useCurrentFrame();
  return (
    <div style={{ flex: 1, background: "linear-gradient(180deg,#0a1a1a,#0a2a1a)", padding: "30px 24px", display: "flex", flexDirection: "column", justifyContent: "center", position: "relative", overflow: "hidden" }}>
      {/* Green scan line */}
      <div style={{ position: "absolute", top: `${(f * 1.5) % 120}%`, left: 0, right: 0, height: 2, background: `rgba(6,214,160,0.2)` }} />
      <div style={{ textAlign: "center", marginBottom: 20 }}>
        <span style={{ fontSize: 16, fontWeight: 800, color: C.cyan, textTransform: "uppercase", letterSpacing: 3 }}>✅ WITH AI</span>
      </div>
      {items.map((item, i) => {
        const op = interpolate(f, [item.delay, item.delay + 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        return (
          <div key={i} style={{ opacity: op, display: "flex", alignItems: "center", gap: 12, marginBottom: 14, padding: "10px 14px", background: `rgba(6,214,160,0.06)`, borderRadius: 12, border: `1px solid rgba(6,214,160,0.15)` }}>
            <span style={{ fontSize: 24 }}>{item.icon}</span>
            <span style={{ fontSize: 17, fontWeight: 600, color: C.cyan }}>{item.text}</span>
          </div>
        );
      })}
    </div>
  );
};

const V7_Split: React.FC = () => (
  <AbsoluteFill style={{ display: "flex", flexDirection: "column" }}>
    <BeforePanel items={[
      { icon: "📵", text: "5 missed calls today", delay: 10 },
      { icon: "💸", text: "€400 lost revenue", delay: 25 },
      { icon: "😤", text: "Customers went to competitor", delay: 40 },
      { icon: "📋", text: "No records of who called", delay: 55 },
      { icon: "🤯", text: "Stressed & overwhelmed", delay: 70 },
    ]} />
    {/* Divider */}
    <div style={{ height: 4, background: `linear-gradient(90deg,${C.red},${C.purple},${C.cyan})` }} />
    <AfterPanel items={[
      { icon: "📞", text: "Every call answered 24/7", delay: 15 },
      { icon: "📅", text: "Jobs auto-booked", delay: 30 },
      { icon: "💬", text: "SMS reminders sent", delay: 45 },
      { icon: "👥", text: "Customer CRM auto-filled", delay: 60 },
      { icon: "😎", text: "You just focus on the work", delay: 75 },
    ]} />
  </AbsoluteFill>
);

const V7_CTA: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 50px" }}>
    <BG /><Orbs colors={[C.purpleGlow, C.cyanGlow]} />
    <div style={{ textAlign: "center", zIndex: 2 }}>
      <Boom text="Which one" delay={0} size={48} color={C.gray} />
      <Boom text="are you?" delay={10} size={60} color={C.white} />
      <Pop delay={25} scale><Logo size={40} /></Pop>
      <Pop delay={32} style={{ marginTop: 8 }}><span style={{ fontSize: 16, color: C.gray }}>bookedforyou.ie</span></Pop>
    </div>
  </AbsoluteFill>
);

export const Social7_BeforeAfter: React.FC = () => {
  const scenes = [{ c: V7_Split, d: 130 }, { c: V7_CTA, d: 70 }];
  let s = 0;
  return (
    <AbsoluteFill style={{ fontFamily: F }}>
      {scenes.map((sc, i) => { const from = s; s += sc.d; const Sc = sc.c; return <Sequence key={i} from={from} durationInFrames={sc.d}><Fade dur={sc.d}><Sc /></Fade></Sequence>; })}
    </AbsoluteFill>
  );
};


// ═══════════════════════════════════════════════════════════
// VIDEO 8: "Fake Reviews" (VERTICAL) — Star ratings flying in
// ═══════════════════════════════════════════════════════════

const ReviewCard: React.FC<{ name: string; trade: string; text: string; stars: number; delay: number }> = ({ name, trade, text, stars, delay }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: f - delay, fps, config: { damping: 12, mass: 0.5 } });
  const op = interpolate(f - delay, [0, 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const y = interpolate(s, [0, 1], [60, 0]);
  return (
    <div style={{ opacity: op, transform: `translateY(${y}px)`, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 18, padding: "18px 20px", marginBottom: 14 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
        <div style={{ width: 38, height: 38, borderRadius: "50%", background: `linear-gradient(135deg,${C.purple},${C.cyan})`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16, fontWeight: 800, color: C.white }}>{name[0]}</div>
        <div>
          <div style={{ fontSize: 15, fontWeight: 700, color: C.white }}>{name}</div>
          <div style={{ fontSize: 12, color: C.gray }}>{trade}</div>
        </div>
      </div>
      <div style={{ marginBottom: 8 }}>{Array.from({ length: stars }, (_, i) => <span key={i} style={{ fontSize: 18, color: "#fbbf24" }}>★</span>)}</div>
      <div style={{ fontSize: 15, color: C.lightGray, lineHeight: 1.5, fontStyle: "italic" }}>"{text}"</div>
    </div>
  );
};

const V8_Reviews: React.FC = () => (
  <AbsoluteFill style={{ padding: "80px 30px 30px" }}>
    <BG /><Orbs colors={[C.purpleGlow, "rgba(251,191,36,0.15)"]} />
    <div style={{ zIndex: 2, position: "relative" }}>
      <Boom text="What tradespeople" delay={0} size={36} color={C.gray} />
      <Boom text="are saying ⭐" delay={10} size={44} color={C.gold} />
      <div style={{ marginTop: 20 }}>
        <ReviewCard name="Mike O'Brien" trade="Plumber, Dublin" text="Haven't missed a call in 3 months. Customers think I hired a real receptionist." stars={5} delay={25} />
        <ReviewCard name="Sarah Kelly" trade="Electrician, Cork" text="Set it up in 5 minutes. It booked 3 jobs on the first day." stars={5} delay={50} />
        <ReviewCard name="Dave Walsh" trade="Builder, Galway" text="The SMS reminders alone saved me from 4 no-shows last month." stars={5} delay={75} />
        <ReviewCard name="Emma Ryan" trade="Painter, Limerick" text="€99/mo vs hiring someone? No brainer. Best investment I've made." stars={5} delay={100} />
      </div>
    </div>
  </AbsoluteFill>
);

const V8_CTA: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 50px" }}>
    <BG /><Orbs colors={[C.purpleGlow, C.cyanGlow]} />
    <div style={{ textAlign: "center", zIndex: 2 }}>
      <Pop delay={0} scale><Logo size={44} /></Pop>
      <Boom text="Join 100+ trades" delay={10} size={40} color={C.gray} />
      <Boom text="Try free for 14 days" delay={22} size={44} color={C.cyan} />
      <Pop delay={35} style={{ marginTop: 8 }}><span style={{ fontSize: 16, color: C.gray }}>bookedforyou.ie</span></Pop>
    </div>
  </AbsoluteFill>
);

export const Social8_Reviews: React.FC = () => {
  const scenes = [{ c: V8_Reviews, d: 170 }, { c: V8_CTA, d: 70 }];
  let s = 0;
  return (
    <AbsoluteFill style={{ fontFamily: F }}>
      {scenes.map((sc, i) => { const from = s; s += sc.d; const Sc = sc.c; return <Sequence key={i} from={from} durationInFrames={sc.d}><Fade dur={sc.d}><Sc /></Fade></Sequence>; })}
    </AbsoluteFill>
  );
};


// ═══════════════════════════════════════════════════════════
// VIDEO 9: "How It Works in 60s" (LANDSCAPE) — Flow diagram style
// Icons connected by animated lines, fast-paced
// ═══════════════════════════════════════════════════════════

const FlowNode: React.FC<{ icon: string; label: string; x: number; y: number; delay: number; color: string }> = ({ icon, label, x, y, delay, color }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: f - delay, fps, config: { damping: 8, mass: 0.3, stiffness: 200 } });
  const op = interpolate(f - delay, [0, 6], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div style={{ position: "absolute", left: x, top: y, transform: `translate(-50%,-50%) scale(${s})`, opacity: op, textAlign: "center", zIndex: 10 }}>
      <div style={{ width: 80, height: 80, borderRadius: 22, background: `${color}15`, border: `2px solid ${color}44`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 36, margin: "0 auto 8px", boxShadow: `0 0 25px ${color}20` }}>{icon}</div>
      <span style={{ fontSize: 16, fontWeight: 800, color: C.white }}>{label}</span>
    </div>
  );
};

const FlowLine: React.FC<{ x1: number; y1: number; x2: number; y2: number; delay: number; color: string }> = ({ x1, y1, x2, y2, delay, color }) => {
  const f = useCurrentFrame();
  const progress = interpolate(f, [delay, delay + 15], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <svg style={{ position: "absolute", top: 0, left: 0, width: 1920, height: 1080, pointerEvents: "none", zIndex: 5 }}>
      <line x1={x1} y1={y1} x2={x1 + (x2 - x1) * progress} y2={y1 + (y2 - y1) * progress} stroke={color} strokeWidth={3} strokeDasharray="8 4" opacity={0.6} />
      {progress > 0.9 && <circle cx={x2} cy={y2} r={6} fill={color} opacity={0.8}><animate attributeName="r" values="4;8;4" dur="1s" repeatCount="indefinite" /></circle>}
    </svg>
  );
};

const L1_Flow: React.FC = () => (
  <AbsoluteFill>
    <BG /><Orbs colors={[C.purpleGlow, C.cyanGlow, "rgba(58,134,255,0.2)"]} />
    {/* Title */}
    <div style={{ position: "absolute", top: 40, left: 0, right: 0, textAlign: "center", zIndex: 20 }}>
      <Boom text="How It Works ⚡" delay={0} size={52} color={C.white} />
    </div>
    {/* Flow: Customer → Phone → AI → Calendar → SMS → Done */}
    <FlowNode icon="👤" label="Customer Calls" x={180} y={450} delay={15} color={C.orange} />
    <FlowLine x1={230} y1={450} x2={430} y2={450} delay={25} color={C.orange} />
    <FlowNode icon="📞" label="Phone Rings" x={480} y={450} delay={30} color={C.blue} />
    <FlowLine x1={530} y1={450} x2={730} y2={450} delay={40} color={C.blue} />
    <FlowNode icon="🤖" label="AI Answers" x={780} y={450} delay={45} color={C.purple} />
    <FlowLine x1={830} y1={450} x2={1030} y2={350} delay={55} color={C.purple} />
    <FlowLine x1={830} y1={450} x2={1030} y2={550} delay={55} color={C.purple} />
    <FlowNode icon="📅" label="Job Booked" x={1080} y={350} delay={60} color={C.cyan} />
    <FlowNode icon="👤" label="CRM Updated" x={1080} y={550} delay={65} color={C.pink} />
    <FlowLine x1={1130} y1={350} x2={1380} y2={450} delay={72} color={C.cyan} />
    <FlowLine x1={1130} y1={550} x2={1380} y2={450} delay={72} color={C.pink} />
    <FlowNode icon="💬" label="SMS Sent" x={1430} y={450} delay={78} color={C.gold} />
    <FlowLine x1={1480} y1={450} x2={1700} y2={450} delay={88} color={C.gold} />
    <FlowNode icon="✅" label="Done!" x={1750} y={450} delay={92} color={C.cyan} />
    {/* Bottom text */}
    <div style={{ position: "absolute", bottom: 60, left: 0, right: 0, textAlign: "center", zIndex: 20 }}>
      <Boom text="Zero human effort. Every time." delay={100} size={36} color={C.gray} />
    </div>
  </AbsoluteFill>
);

const L1_CTA: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
    <BG /><Orbs colors={[C.purpleGlow, C.cyanGlow]} />
    <div style={{ textAlign: "center", zIndex: 2 }}>
      <Pop delay={0} scale><Logo size={56} /></Pop>
      <Boom text="Try it free for 14 days" delay={12} size={44} color={C.cyan} />
      <Pop delay={25} style={{ marginTop: 8 }}><span style={{ fontSize: 22, color: C.gray }}>bookedforyou.ie</span></Pop>
    </div>
  </AbsoluteFill>
);

export const Landscape1_HowItWorks: React.FC = () => {
  const scenes = [{ c: L1_Flow, d: 160 }, { c: L1_CTA, d: 70 }];
  let s = 0;
  return (
    <AbsoluteFill style={{ fontFamily: F }}>
      {scenes.map((sc, i) => { const from = s; s += sc.d; const Sc = sc.c; return <Sequence key={i} from={from} durationInFrames={sc.d}><Fade dur={sc.d}><Sc /></Fade></Sequence>; })}
    </AbsoluteFill>
  );
};


// ═══════════════════════════════════════════════════════════
// VIDEO 10: "Stats That Sell" (LANDSCAPE) — Big animated counters
// Numbers counting up with dramatic reveals
// ═══════════════════════════════════════════════════════════

const Counter: React.FC<{ end: number; prefix?: string; suffix?: string; delay: number; color: string; size?: number }> = ({ end, prefix = "", suffix = "", delay, color, size = 100 }) => {
  const f = useCurrentFrame();
  const val = Math.floor(interpolate(f, [delay, delay + 30], [0, end], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }));
  const op = interpolate(f - delay, [0, 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div style={{ opacity: op, textAlign: "center" }}>
      <span style={{ fontSize: size, fontWeight: 900, color, textShadow: `0 0 40px ${color}40`, letterSpacing: -3, fontFamily: "monospace" }}>{prefix}{val.toLocaleString()}{suffix}</span>
    </div>
  );
};

const L2_S1: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
    <BG /><Orbs colors={["rgba(255,50,50,0.2)", C.purpleGlow]} />
    <div style={{ textAlign: "center", zIndex: 2 }}>
      <Boom text="The average tradesperson" delay={0} size={36} color={C.gray} />
      <Boom text="misses" delay={12} size={44} />
      <Counter end={23} delay={22} color={C.red} size={140} />
      <Boom text="calls per week" delay={22} size={40} color={C.gray} />
    </div>
  </AbsoluteFill>
);

const L2_S2: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
    <BG /><Orbs colors={["rgba(255,50,50,0.15)", C.purpleGlow]} />
    <div style={{ textAlign: "center", zIndex: 2 }}>
      <Boom text="That's" delay={0} size={40} color={C.gray} />
      <Counter end={57600} prefix="€" delay={10} color={C.red} size={120} />
      <Boom text="lost per year 💸" delay={10} size={40} color={C.gray} />
    </div>
  </AbsoluteFill>
);

const L2_S3: React.FC = () => {
  const f = useCurrentFrame();
  const stats = [
    { icon: "📞", label: "Calls Answered", value: "24/7", color: C.cyan, delay: 5 },
    { icon: "💰", label: "Monthly Cost", value: "€99", color: C.gold, delay: 15 },
    { icon: "⏱️", label: "Setup Time", value: "5 min", color: C.purple, delay: 25 },
    { icon: "🎯", label: "Missed Calls", value: "Zero", color: C.cyan, delay: 35 },
  ];
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <BG /><Orbs colors={[C.cyanGlow, C.purpleGlow]} />
      <div style={{ zIndex: 2 }}>
        <Boom text="With BookedForYou ⚡" delay={0} size={44} color={C.white} />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24, marginTop: 30, maxWidth: 800 }}>
          {stats.map((s, i) => {
            const op = interpolate(f, [s.delay, s.delay + 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            const { fps } = useVideoConfig();
            const sc = spring({ frame: f - s.delay, fps, config: { damping: 10, mass: 0.4 } });
            return (
              <div key={i} style={{ opacity: op, transform: `scale(${sc})`, background: "rgba(255,255,255,0.04)", border: `1px solid ${s.color}33`, borderRadius: 20, padding: "24px 20px", textAlign: "center" }}>
                <span style={{ fontSize: 36 }}>{s.icon}</span>
                <div style={{ fontSize: 44, fontWeight: 900, color: s.color, margin: "8px 0 4px", textShadow: `0 0 20px ${s.color}30` }}>{s.value}</div>
                <div style={{ fontSize: 16, color: C.gray, fontWeight: 600 }}>{s.label}</div>
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};

const L2_CTA: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const btnS = spring({ frame: f - 20, fps, config: { damping: 8, mass: 0.4 } });
  const glow = interpolate(Math.sin(f * 0.12), [-1, 1], [0.4, 1]);
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <BG /><Orbs colors={[C.purpleGlow, C.cyanGlow]} />
      <div style={{ textAlign: "center", zIndex: 2 }}>
        <Pop delay={0} scale><Logo size={56} /></Pop>
        <Boom text="Stop losing money" delay={8} size={48} />
        <Pop delay={18} scale style={{ marginTop: 16 }}>
          <div style={{ display: "inline-block", background: `linear-gradient(135deg,${C.purple},${C.cyan})`, borderRadius: 18, padding: "18px 50px", transform: `scale(${btnS})`, boxShadow: `0 0 ${50 * glow}px ${C.purpleGlow}` }}>
            <span style={{ fontSize: 26, fontWeight: 900, color: C.white }}>Get Started →</span>
          </div>
        </Pop>
        <Pop delay={30} style={{ marginTop: 10 }}><span style={{ fontSize: 20, color: C.gray }}>bookedforyou.ie</span></Pop>
      </div>
    </AbsoluteFill>
  );
};

export const Landscape2_Stats: React.FC = () => {
  const scenes = [{ c: L2_S1, d: 80 }, { c: L2_S2, d: 70 }, { c: L2_S3, d: 90 }, { c: L2_CTA, d: 70 }];
  let s = 0;
  return (
    <AbsoluteFill style={{ fontFamily: F }}>
      {scenes.map((sc, i) => { const from = s; s += sc.d; const Sc = sc.c; return <Sequence key={i} from={from} durationInFrames={sc.d}><Fade dur={sc.d}><Sc /></Fade></Sequence>; })}
    </AbsoluteFill>
  );
};
