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
  floor: "#1a1a2e", pipe: "#4a5568", water: "#60a5fa",
};
const F = "'Inter','SF Pro Display',-apple-system,sans-serif";

const BG: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill>
      <div style={{ width: "100%", height: "100%", background: `radial-gradient(ellipse at 50% 20%,${C.bg2},${C.bg1} 70%)` }} />
      {Array.from({ length: 25 }, (_, i) => {
        const seed = i * 137.508;
        return <div key={i} style={{ position: "absolute", left: `${(seed * 7.3) % 100}%`, top: `${((seed * 3.1 + f * 0.2) % 120) - 10}%`, width: 1 + (i % 3), height: 1 + (i % 3), borderRadius: "50%", backgroundColor: i % 2 === 0 ? C.purpleLight : C.cyan, opacity: 0.04 + (i % 4) * 0.02 }} />;
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
// VIDEO 9: "Plumber Under the Sink" (VERTICAL) — Animated scene
// Stick figure plumber working, phone rings, hands dirty, AI saves the day
// ═══════════════════════════════════════════════════════════

// Animated stick figure plumber
const StickPlumber: React.FC<{ working: boolean }> = ({ working }) => {
  const f = useCurrentFrame();
  const armAngle = working ? Math.sin(f * 0.15) * 20 : 0;
  const bodyBob = working ? Math.sin(f * 0.1) * 3 : 0;
  return (
    <svg width="200" height="280" viewBox="0 0 200 280">
      {/* Hard hat */}
      <ellipse cx="100" cy="42" rx="32" ry="12" fill={C.gold} />
      <rect x="68" y="30" width="64" height="14" rx="4" fill={C.gold} />
      {/* Head */}
      <circle cx="100" cy="60" r="24" fill="#fbbf24" stroke="#d97706" strokeWidth="2" />
      {/* Eyes */}
      <circle cx="90" cy="56" r="3" fill="#1a1a1a" />
      <circle cx="110" cy="56" r="3" fill="#1a1a1a" />
      {/* Smile */}
      <path d="M88 68 Q100 78 112 68" fill="none" stroke="#1a1a1a" strokeWidth="2" strokeLinecap="round" />
      {/* Body */}
      <g transform={`translate(0,${bodyBob})`}>
        {/* Torso - overalls */}
        <rect x="78" y="84" width="44" height="60" rx="6" fill={C.blue} />
        <rect x="88" y="84" width="24" height="20" rx="3" fill="#2563eb" />
        {/* Overall straps */}
        <line x1="85" y1="84" x2="90" y2="100" stroke="#1d4ed8" strokeWidth="3" />
        <line x1="115" y1="84" x2="110" y2="100" stroke="#1d4ed8" strokeWidth="3" />
        {/* Arms */}
        <g transform={`rotate(${-30 + armAngle}, 78, 90)`}>
          <line x1="78" y1="90" x2="45" y2="130" stroke="#fbbf24" strokeWidth="8" strokeLinecap="round" />
          {/* Wrench in hand */}
          {working && <g transform="translate(35,125) rotate(-45)">
            <rect x="0" y="0" width="8" height="30" rx="2" fill="#718096" />
            <circle cx="4" cy="0" r="8" fill="none" stroke="#718096" strokeWidth="3" />
          </g>}
        </g>
        <g transform={`rotate(${30 - armAngle}, 122, 90)`}>
          <line x1="122" y1="90" x2="155" y2="130" stroke="#fbbf24" strokeWidth="8" strokeLinecap="round" />
        </g>
        {/* Legs */}
        <line x1="90" y1="144" x2="80" y2="210" stroke={C.blue} strokeWidth="10" strokeLinecap="round" />
        <line x1="110" y1="144" x2="120" y2="210" stroke={C.blue} strokeWidth="10" strokeLinecap="round" />
        {/* Boots */}
        <rect x="68" y="205" width="24" height="14" rx="5" fill="#4a5568" />
        <rect x="108" y="205" width="24" height="14" rx="5" fill="#4a5568" />
      </g>
    </svg>
  );
};

// Animated ringing phone
const RingingPhone: React.FC<{ ringing: boolean; answered?: boolean }> = ({ ringing, answered }) => {
  const f = useCurrentFrame();
  const shake = ringing ? Math.sin(f * 2) * 6 : 0;
  const ringOpacity = ringing ? interpolate(Math.sin(f * 0.3), [-1, 1], [0.3, 0.8]) : 0;
  return (
    <div style={{ position: "relative", display: "inline-block" }}>
      {/* Ring waves */}
      {ringing && [0, 1, 2].map(i => (
        <div key={i} style={{
          position: "absolute", top: "50%", left: "50%",
          width: 80 + i * 30, height: 80 + i * 30,
          borderRadius: "50%", border: `2px solid ${answered ? C.cyan : C.red}`,
          transform: `translate(-50%,-50%) scale(${interpolate((f + i * 10) % 30, [0, 30], [0.8, 1.5])})`,
          opacity: ringOpacity * interpolate((f + i * 10) % 30, [0, 30], [0.6, 0]),
        }} />
      ))}
      <div style={{ transform: `rotate(${shake}deg)`, fontSize: 64 }}>
        {answered ? "🤖" : "📱"}
      </div>
    </div>
  );
};

const V9_Scene1: React.FC = () => {
  const f = useCurrentFrame();
  const phoneRinging = f > 30;
  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", padding: "0 40px 120px" }}>
      <BG />
      {/* Scene: kitchen counter / sink area */}
      <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: 300, background: "linear-gradient(180deg,transparent,rgba(26,26,46,0.8))" }} />
      {/* Sink shape */}
      <div style={{ position: "absolute", bottom: 200, left: "50%", transform: "translateX(-50%)", width: 300, height: 80, borderRadius: "0 0 40px 40px", background: "#2d3748", border: "3px solid #4a5568", borderTop: "none" }} />
      {/* Pipes */}
      <div style={{ position: "absolute", bottom: 120, left: "50%", transform: "translateX(-50%)", width: 8, height: 80, background: C.pipe }} />
      {/* Water drip */}
      {f > 10 && <div style={{ position: "absolute", bottom: 120 - (f % 20) * 3, left: "50%", transform: "translateX(-50%)", width: 6, height: 10, borderRadius: "50%", background: C.water, opacity: interpolate(f % 20, [0, 20], [0.8, 0]) }} />}
      {/* Plumber */}
      <div style={{ position: "absolute", bottom: 80, left: "50%", transform: "translateX(-50%)", zIndex: 5 }}>
        <StickPlumber working />
      </div>
      {/* Phone ringing above */}
      {phoneRinging && (
        <div style={{ position: "absolute", top: 200, right: 80, zIndex: 10 }}>
          <RingingPhone ringing />
        </div>
      )}
      {/* Text */}
      <div style={{ position: "absolute", top: 80, left: 0, right: 0, zIndex: 20, padding: "0 40px" }}>
        <Boom text="You're fixing" delay={0} size={48} color={C.gray} dur={80} />
        <Boom text="a burst pipe 🔧" delay={10} size={52} dur={80} />
        {phoneRinging && <Boom text="Phone won't stop 📱" delay={35} size={44} color={C.red} dur={50} />}
      </div>
    </AbsoluteFill>
  );
};

const V9_Scene2: React.FC = () => {
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 40px" }}>
      <BG /><Orbs colors={[C.cyanGlow, C.purpleGlow]} />
      <div style={{ textAlign: "center", zIndex: 2 }}>
        <Boom text="But wait..." delay={0} size={48} color={C.gray} />
        <Pop delay={15} scale>
          <div style={{ margin: "20px 0" }}>
            <RingingPhone ringing answered />
          </div>
        </Pop>
        <Boom text="AI picks up! 🤖" delay={20} size={56} color={C.cyan} />
        {/* Chat bubbles */}
        <Pop delay={40} style={{ marginTop: 20 }}>
          <div style={{ background: `${C.purple}15`, border: `1px solid ${C.purple}30`, borderRadius: "16px 16px 16px 4px", padding: "10px 16px", textAlign: "left", maxWidth: 350, margin: "0 auto 8px" }}>
            <span style={{ fontSize: 15, color: C.white }}>"Good morning! How can I help?"</span>
          </div>
        </Pop>
        <Pop delay={55} style={{ marginTop: 4 }}>
          <div style={{ background: `${C.cyan}12`, border: `1px solid ${C.cyan}25`, borderRadius: "16px 16px 4px 16px", padding: "10px 16px", textAlign: "right", maxWidth: 300, marginLeft: "auto" }}>
            <span style={{ fontSize: 15, color: C.white }}>"I need a plumber ASAP!"</span>
          </div>
        </Pop>
        <Pop delay={70} style={{ marginTop: 4 }}>
          <div style={{ background: `${C.purple}15`, border: `1px solid ${C.purple}30`, borderRadius: "16px 16px 16px 4px", padding: "10px 16px", textAlign: "left", maxWidth: 350, margin: "0 auto" }}>
            <span style={{ fontSize: 15, color: C.white }}>"✅ Booked for Thursday 10AM!"</span>
          </div>
        </Pop>
      </div>
    </AbsoluteFill>
  );
};

const V9_Scene3: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 40px" }}>
    <BG /><Orbs colors={[C.cyanGlow, C.purpleGlow]} />
    <div style={{ textAlign: "center", zIndex: 2 }}>
      <Boom text="You didn't even" delay={0} size={44} color={C.gray} />
      <Boom text="touch your phone 🙌" delay={12} size={52} />
      <Pop delay={28} scale><Logo size={44} /></Pop>
      <Boom text="AI handles it all" delay={35} size={40} color={C.cyan} />
      <Pop delay={48} style={{ marginTop: 8 }}><span style={{ fontSize: 16, color: C.gray }}>bookedforyou.ie</span></Pop>
    </div>
  </AbsoluteFill>
);

export const Social9_PlumberScene: React.FC = () => {
  const scenes = [{ c: V9_Scene1, d: 110 }, { c: V9_Scene2, d: 110 }, { c: V9_Scene3, d: 80 }];
  let s = 0;
  return (
    <AbsoluteFill style={{ fontFamily: F }}>
      {scenes.map((sc, i) => { const from = s; s += sc.d; const Sc = sc.c; return <Sequence key={i} from={from} durationInFrames={sc.d}><Fade dur={sc.d}><Sc /></Fade></Sequence>; })}
    </AbsoluteFill>
  );
};


// ═══════════════════════════════════════════════════════════
// VIDEO 10: "The Competitor Steals Your Customer" (VERTICAL)
// Dramatic story: missed call → customer calls competitor → you lose
// ═══════════════════════════════════════════════════════════

const V10_S1: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 50px" }}>
      <BG /><Orbs colors={["rgba(255,50,50,0.2)", C.purpleGlow]} />
      <div style={{ textAlign: "center", zIndex: 2 }}>
        <Boom text="Monday 9:15 AM" delay={0} size={36} color={C.gray} />
        <Pop delay={10} scale>
          <div style={{ margin: "20px 0" }}><RingingPhone ringing={f > 12} /></div>
        </Pop>
        <Boom text="Customer calls you" delay={15} size={48} />
        <Boom text="You're on a job..." delay={35} size={40} color={C.gray} />
        <Pop delay={50} scale>
          <div style={{ fontSize: 80, marginTop: 10 }}>🔧😓</div>
        </Pop>
        <Boom text="Can't answer" delay={55} size={52} color={C.red} />
      </div>
    </AbsoluteFill>
  );
};

const V10_S2: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 50px" }}>
    <BG /><Orbs colors={["rgba(255,50,50,0.3)", "rgba(255,107,53,0.2)"]} />
    <div style={{ textAlign: "center", zIndex: 2 }}>
      <Boom text="Customer thinks:" delay={0} size={40} color={C.gray} />
      <Pop delay={12} scale>
        <div style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 20, padding: "20px 24px", margin: "16px 0", maxWidth: 400 }}>
          <span style={{ fontSize: 22, color: C.white, fontStyle: "italic", lineHeight: 1.5 }}>"Hmm, no answer... let me try that other plumber I saw on Google"</span>
        </div>
      </Pop>
      <Boom text="They call your" delay={40} size={44} />
      <Boom text="COMPETITOR 😱" delay={50} size={60} color={C.red} />
    </div>
  </AbsoluteFill>
);

const V10_S3: React.FC = () => {
  const f = useCurrentFrame();
  const moneyFly = Array.from({ length: 6 }, (_, i) => ({
    x: interpolate(f, [i * 5, i * 5 + 30], [0, (i % 2 === 0 ? 1 : -1) * (100 + i * 30)], { extrapolateRight: "clamp" }),
    y: interpolate(f, [i * 5, i * 5 + 30], [0, -200 - i * 40], { extrapolateRight: "clamp" }),
    op: interpolate(f, [i * 5, i * 5 + 5, i * 5 + 25, i * 5 + 30], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
  }));
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 50px" }}>
      <BG /><Orbs colors={["rgba(255,50,50,0.2)", C.purpleGlow]} />
      {/* Flying money */}
      {moneyFly.map((m, i) => (
        <div key={i} style={{ position: "absolute", left: `calc(50% + ${m.x}px)`, top: `calc(50% + ${m.y}px)`, fontSize: 40, opacity: m.op, transform: `rotate(${i * 30}deg)` }}>💸</div>
      ))}
      <div style={{ textAlign: "center", zIndex: 2 }}>
        <Boom text="You just lost" delay={0} size={48} />
        <Boom text="€350" delay={12} size={100} color={C.red} />
        <Boom text="from ONE missed call" delay={25} size={36} color={C.gray} />
      </div>
    </AbsoluteFill>
  );
};

const V10_S4: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 50px" }}>
    <BG /><Orbs colors={[C.cyanGlow, C.purpleGlow]} />
    <div style={{ textAlign: "center", zIndex: 2 }}>
      <Boom text="Or..." delay={0} size={56} color={C.gray} />
      <Pop delay={15} scale><div style={{ fontSize: 80, margin: "10px 0" }}>🤖</div></Pop>
      <Boom text="AI answers in" delay={20} size={44} />
      <Boom text="0.5 seconds" delay={30} size={60} color={C.cyan} />
      <Boom text="Books the job ✅" delay={48} size={44} color={C.cyan} />
      <Boom text="Customer never leaves" delay={60} size={36} color={C.gray} />
      <Pop delay={75} scale><Logo size={40} /></Pop>
      <Pop delay={82} style={{ marginTop: 8 }}><span style={{ fontSize: 16, color: C.gray }}>bookedforyou.ie</span></Pop>
    </div>
  </AbsoluteFill>
);

export const Social10_Competitor: React.FC = () => {
  const scenes = [{ c: V10_S1, d: 100 }, { c: V10_S2, d: 90 }, { c: V10_S3, d: 70 }, { c: V10_S4, d: 110 }];
  let s = 0;
  return (
    <AbsoluteFill style={{ fontFamily: F }}>
      {scenes.map((sc, i) => { const from = s; s += sc.d; const Sc = sc.c; return <Sequence key={i} from={from} durationInFrames={sc.d}><Fade dur={sc.d}><Sc /></Fade></Sequence>; })}
    </AbsoluteFill>
  );
};


// ═══════════════════════════════════════════════════════════
// VIDEO 11: "Money Counter" (VERTICAL) — Revenue ticking up
// Animated cash register / revenue counter showing AI-booked jobs
// ═══════════════════════════════════════════════════════════

const V11_Counter: React.FC = () => {
  const f = useCurrentFrame();
  // Jobs booked counter
  const jobs = Math.min(Math.floor(interpolate(f, [20, 200], [0, 47], { extrapolateRight: "clamp" })), 47);
  const revenue = Math.floor(interpolate(f, [20, 200], [0, 18400], { extrapolateRight: "clamp" }));
  // Individual job notifications popping
  const jobNotifs = [
    { name: "Pipe Repair", amount: 280, delay: 30 },
    { name: "Boiler Service", amount: 450, delay: 55 },
    { name: "Emergency Leak", amount: 180, delay: 80 },
    { name: "Bathroom Refit", amount: 3500, delay: 105 },
    { name: "Radiator Flush", amount: 120, delay: 130 },
    { name: "Kitchen Plumbing", amount: 350, delay: 155 },
  ];
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 40px" }}>
      <BG /><Orbs colors={[C.cyanGlow, "rgba(255,214,10,0.2)"]} />
      <div style={{ textAlign: "center", zIndex: 2, width: "100%" }}>
        <Boom text="This month's" delay={0} size={40} color={C.gray} dur={220} />
        <Boom text="AI-booked revenue 💰" delay={10} size={44} dur={210} />
        {/* Big counter */}
        <div style={{ margin: "20px 0", fontFamily: "monospace" }}>
          <span style={{ fontSize: 100, fontWeight: 900, color: C.cyan, textShadow: `0 0 50px ${C.cyanGlow}`, letterSpacing: -3 }}>€{revenue.toLocaleString()}</span>
        </div>
        <div style={{ display: "flex", justifyContent: "center", gap: 30, marginBottom: 20 }}>
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: 44, fontWeight: 900, color: C.gold }}>{jobs}</div>
            <div style={{ fontSize: 14, color: C.gray, fontWeight: 600 }}>Jobs Booked</div>
          </div>
          <div style={{ width: 1, background: "rgba(255,255,255,0.1)" }} />
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: 44, fontWeight: 900, color: C.purple }}>0</div>
            <div style={{ fontSize: 14, color: C.gray, fontWeight: 600 }}>Missed Calls</div>
          </div>
        </div>
        {/* Job notifications */}
        <div style={{ display: "flex", flexDirection: "column", gap: 6, maxWidth: 400, margin: "0 auto" }}>
          {jobNotifs.map((j, i) => {
            const op = interpolate(f, [j.delay, j.delay + 6, j.delay + 30, j.delay + 36], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            const x = interpolate(f, [j.delay, j.delay + 6], [50, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            return (
              <div key={i} style={{ opacity: op, transform: `translateX(${x}px)`, display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 14px", background: `${C.cyan}08`, border: `1px solid ${C.cyan}20`, borderRadius: 10 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 14 }}>✅</span>
                  <span style={{ fontSize: 14, fontWeight: 600, color: C.white }}>{j.name}</span>
                </div>
                <span style={{ fontSize: 16, fontWeight: 800, color: C.cyan }}>+€{j.amount}</span>
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};

const V11_CTA: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 50px" }}>
    <BG /><Orbs colors={[C.purpleGlow, C.cyanGlow]} />
    <div style={{ textAlign: "center", zIndex: 2 }}>
      <Pop delay={0} scale><Logo size={44} /></Pop>
      <Boom text="Your revenue on" delay={10} size={40} color={C.gray} />
      <Boom text="autopilot 🚀" delay={20} size={52} color={C.cyan} />
      <Pop delay={35} style={{ marginTop: 8 }}><span style={{ fontSize: 16, color: C.gray }}>bookedforyou.ie</span></Pop>
    </div>
  </AbsoluteFill>
);

export const Social11_MoneyCounter: React.FC = () => {
  const scenes = [{ c: V11_Counter, d: 230 }, { c: V11_CTA, d: 70 }];
  let s = 0;
  return (
    <AbsoluteFill style={{ fontFamily: F }}>
      {scenes.map((sc, i) => { const from = s; s += sc.d; const Sc = sc.c; return <Sequence key={i} from={from} durationInFrames={sc.d}><Fade dur={sc.d}><Sc /></Fade></Sequence>; })}
    </AbsoluteFill>
  );
};


// ═══════════════════════════════════════════════════════════
// VIDEO 12: "A Day With BookedForYou" (LANDSCAPE) — Animated timeline
// 8AM to 6PM showing AI handling calls throughout the day
// ═══════════════════════════════════════════════════════════

const TimelineEvent: React.FC<{ time: string; icon: string; text: string; color: string; x: number; delay: number }> = ({ time, icon, text, color, x, delay }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: f - delay, fps, config: { damping: 10, mass: 0.4, stiffness: 180 } });
  const op = interpolate(f - delay, [0, 6], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div style={{ position: "absolute", left: x, top: 380, transform: `translateX(-50%) translateY(${interpolate(s, [0, 1], [30, 0])}px)`, opacity: op, textAlign: "center", width: 160 }}>
      {/* Connector to timeline */}
      <div style={{ width: 2, height: 30, background: `${color}44`, margin: "0 auto 8px" }} />
      <div style={{ width: 56, height: 56, borderRadius: 16, background: `${color}15`, border: `2px solid ${color}44`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 28, margin: "0 auto 8px", boxShadow: `0 0 20px ${color}20` }}>{icon}</div>
      <div style={{ fontSize: 13, fontWeight: 800, color }}>{time}</div>
      <div style={{ fontSize: 13, fontWeight: 600, color: C.white, marginTop: 4, lineHeight: 1.3 }}>{text}</div>
    </div>
  );
};

const L3_Timeline: React.FC = () => {
  const f = useCurrentFrame();
  // Timeline bar progress
  const progress = interpolate(f, [10, 200], [0, 100], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const events = [
    { time: "8:15 AM", icon: "📞", text: "Emergency leak call answered", color: C.red, x: 140, delay: 20 },
    { time: "9:30 AM", icon: "📅", text: "Boiler service booked", color: C.blue, x: 380, delay: 45 },
    { time: "11:00 AM", icon: "💬", text: "SMS reminder sent", color: C.gold, x: 620, delay: 70 },
    { time: "1:15 PM", icon: "📞", text: "Quote request handled", color: C.purple, x: 860, delay: 95 },
    { time: "3:00 PM", icon: "📅", text: "Bathroom refit booked", color: C.cyan, x: 1100, delay: 120 },
    { time: "4:30 PM", icon: "🔄", text: "Reschedule handled", color: C.orange, x: 1340, delay: 145 },
    { time: "5:45 PM", icon: "📞", text: "After-hours call answered", color: C.pink, x: 1580, delay: 170 },
  ];
  return (
    <AbsoluteFill>
      <BG /><Orbs colors={[C.purpleGlow, C.cyanGlow, "rgba(58,134,255,0.15)"]} />
      {/* Title */}
      <div style={{ position: "absolute", top: 40, left: 0, right: 0, textAlign: "center", zIndex: 20 }}>
        <Boom text="A Day With BookedForYou ⚡" delay={0} size={44} color={C.white} dur={220} />
        <Pop delay={8}><span style={{ fontSize: 20, color: C.gray }}>While you're on the tools, AI handles everything</span></Pop>
      </div>
      {/* Timeline bar */}
      <div style={{ position: "absolute", top: 360, left: 100, right: 100, height: 6, background: "rgba(255,255,255,0.06)", borderRadius: 3, zIndex: 10 }}>
        <div style={{ width: `${progress}%`, height: "100%", borderRadius: 3, background: `linear-gradient(90deg,${C.purple},${C.cyan})`, boxShadow: `0 0 15px ${C.cyanGlow}` }} />
        {/* Moving dot */}
        <div style={{ position: "absolute", left: `${progress}%`, top: -5, width: 16, height: 16, borderRadius: "50%", background: C.cyan, boxShadow: `0 0 12px ${C.cyan}`, transform: "translateX(-50%)" }} />
      </div>
      {/* Time labels */}
      <div style={{ position: "absolute", top: 335, left: 100, fontSize: 12, color: C.gray, fontWeight: 700 }}>8 AM</div>
      <div style={{ position: "absolute", top: 335, right: 100, fontSize: 12, color: C.gray, fontWeight: 700 }}>6 PM</div>
      {/* Events */}
      {events.map((e, i) => <TimelineEvent key={i} {...e} />)}
      {/* Bottom stats */}
      <div style={{ position: "absolute", bottom: 50, left: 0, right: 0, display: "flex", justifyContent: "center", gap: 40, zIndex: 20 }}>
        {[
          { label: "Calls Answered", value: "7", color: C.cyan },
          { label: "Jobs Booked", value: "4", color: C.gold },
          { label: "Revenue", value: "€2,180", color: C.cyan },
          { label: "Your Effort", value: "Zero", color: C.purple },
        ].map((s, i) => (
          <Pop key={i} delay={180 + i * 8}>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: 32, fontWeight: 900, color: s.color }}>{s.value}</div>
              <div style={{ fontSize: 13, color: C.gray, fontWeight: 600 }}>{s.label}</div>
            </div>
          </Pop>
        ))}
      </div>
    </AbsoluteFill>
  );
};

const L3_CTA: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
    <BG /><Orbs colors={[C.purpleGlow, C.cyanGlow]} />
    <div style={{ textAlign: "center", zIndex: 2 }}>
      <Pop delay={0} scale><Logo size={56} /></Pop>
      <Boom text="Your business runs itself" delay={10} size={44} color={C.cyan} />
      <Pop delay={25} style={{ marginTop: 8 }}><span style={{ fontSize: 20, color: C.gray }}>bookedforyou.ie — Try free for 14 days</span></Pop>
    </div>
  </AbsoluteFill>
);

export const Landscape3_DayTimeline: React.FC = () => {
  const scenes = [{ c: L3_Timeline, d: 240 }, { c: L3_CTA, d: 70 }];
  let s = 0;
  return (
    <AbsoluteFill style={{ fontFamily: F }}>
      {scenes.map((sc, i) => { const from = s; s += sc.d; const Sc = sc.c; return <Sequence key={i} from={from} durationInFrames={sc.d}><Fade dur={sc.d}><Sc /></Fade></Sequence>; })}
    </AbsoluteFill>
  );
};


// ═══════════════════════════════════════════════════════════
// VIDEO 13: "The Phone That Never Stops" (LANDSCAPE)
// Animated phones ringing, jobs stacking up, all handled by AI
// ═══════════════════════════════════════════════════════════

const L4_Phones: React.FC = () => {
  const f = useCurrentFrame();
  // Multiple phones ringing across the screen
  const phones = [
    { x: 200, y: 300, delay: 10, name: "John M.", job: "Pipe Repair", amount: "€280" },
    { x: 500, y: 400, delay: 30, name: "Sarah O.", job: "Boiler Install", amount: "€1,200" },
    { x: 800, y: 280, delay: 50, name: "Emma W.", job: "Emergency Leak", amount: "€180" },
    { x: 1100, y: 420, delay: 70, name: "Tom K.", job: "Radiator Flush", amount: "€120" },
    { x: 1400, y: 320, delay: 90, name: "Lisa B.", job: "Kitchen Plumb", amount: "€350" },
    { x: 1700, y: 380, delay: 110, name: "Dave R.", job: "Bathroom Refit", amount: "€3,500" },
  ];
  // Total revenue counter
  const totalRev = Math.floor(interpolate(f, [10, 160], [0, 5630], { extrapolateRight: "clamp" }));
  return (
    <AbsoluteFill>
      <BG /><Orbs colors={[C.cyanGlow, C.purpleGlow, "rgba(255,214,10,0.15)"]} />
      {/* Title */}
      <div style={{ position: "absolute", top: 30, left: 0, right: 0, textAlign: "center", zIndex: 20 }}>
        <Boom text="📞 Calls keep coming..." delay={0} size={44} dur={180} />
      </div>
      {/* Phones */}
      {phones.map((p, i) => {
        const op = interpolate(f, [p.delay, p.delay + 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        const shake = f > p.delay && f < p.delay + 20 ? Math.sin((f - p.delay) * 2) * 4 : 0;
        const answered = f > p.delay + 20;
        const booked = f > p.delay + 35;
        return (
          <div key={i} style={{ position: "absolute", left: p.x, top: p.y, transform: `translate(-50%,-50%) rotate(${shake}deg)`, opacity: op, textAlign: "center", zIndex: 10 }}>
            {/* Ring waves */}
            {!answered && f > p.delay && [0, 1].map(j => (
              <div key={j} style={{
                position: "absolute", top: "50%", left: "50%",
                width: 60 + j * 20, height: 60 + j * 20, borderRadius: "50%",
                border: `2px solid ${C.orange}`,
                transform: `translate(-50%,-50%) scale(${interpolate((f - p.delay + j * 8) % 20, [0, 20], [0.8, 1.4])})`,
                opacity: interpolate((f - p.delay + j * 8) % 20, [0, 20], [0.5, 0]),
              }} />
            ))}
            <div style={{ fontSize: 44, marginBottom: 6 }}>{answered ? (booked ? "✅" : "🤖") : "📱"}</div>
            <div style={{ fontSize: 13, fontWeight: 700, color: C.white }}>{p.name}</div>
            <div style={{ fontSize: 12, color: C.gray }}>{p.job}</div>
            {booked && <div style={{ fontSize: 14, fontWeight: 800, color: C.cyan, marginTop: 4 }}>{p.amount}</div>}
          </div>
        );
      })}
      {/* Revenue counter bottom */}
      <div style={{ position: "absolute", bottom: 60, left: 0, right: 0, textAlign: "center", zIndex: 20 }}>
        <Pop delay={30}>
          <div style={{ display: "inline-flex", alignItems: "center", gap: 16, background: "rgba(0,0,0,0.6)", borderRadius: 16, padding: "12px 30px", backdropFilter: "blur(10px)", border: `1px solid ${C.cyan}33` }}>
            <span style={{ fontSize: 18, color: C.gray, fontWeight: 600 }}>AI Revenue Today:</span>
            <span style={{ fontSize: 36, fontWeight: 900, color: C.cyan, fontFamily: "monospace" }}>€{totalRev.toLocaleString()}</span>
          </div>
        </Pop>
      </div>
    </AbsoluteFill>
  );
};

const L4_CTA: React.FC = () => (
  <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
    <BG /><Orbs colors={[C.purpleGlow, C.cyanGlow]} />
    <div style={{ textAlign: "center", zIndex: 2 }}>
      <Boom text="6 calls. 6 bookings." delay={0} size={48} />
      <Boom text="€5,630 revenue." delay={12} size={44} color={C.cyan} />
      <Boom text="Zero effort." delay={25} size={40} color={C.gray} />
      <Pop delay={38} scale><Logo size={52} /></Pop>
      <Pop delay={45} style={{ marginTop: 8 }}><span style={{ fontSize: 20, color: C.gray }}>bookedforyou.ie</span></Pop>
    </div>
  </AbsoluteFill>
);

export const Landscape4_PhoneStorm: React.FC = () => {
  const scenes = [{ c: L4_Phones, d: 200 }, { c: L4_CTA, d: 80 }];
  let s = 0;
  return (
    <AbsoluteFill style={{ fontFamily: F }}>
      {scenes.map((sc, i) => { const from = s; s += sc.d; const Sc = sc.c; return <Sequence key={i} from={from} durationInFrames={sc.d}><Fade dur={sc.d}><Sc /></Fade></Sequence>; })}
    </AbsoluteFill>
  );
};
