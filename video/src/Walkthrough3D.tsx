import {
  AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate, spring, Sequence, Audio, staticFile, Img,
} from "remotion";
import React from "react";

const C = {
  bg1: "#030014", bg2: "#0a0025",
  purple: "#7c3aed", purpleLight: "#a78bfa", purpleGlow: "rgba(124,58,237,0.4)",
  cyan: "#06d6a0", cyanGlow: "rgba(6,214,160,0.35)",
  blue: "#3a86ff", blueGlow: "rgba(58,134,255,0.25)",
  pink: "#ff006e", orange: "#ff6b35", gold: "#ffd60a", red: "#ff4757",
  white: "#fff", gray: "#94a3b8", lightGray: "#cbd5e1",
};
const FONT = "'Inter','SF Pro Display',-apple-system,sans-serif";
const S = {
  jobs: staticFile("screenshots/jobs.png"),
  calls: staticFile("screenshots/calls.png"),
  calendar: staticFile("screenshots/calendar.png"),
  employees: staticFile("screenshots/employees.png"),
  customers: staticFile("screenshots/customers.png"),
  services: staticFile("screenshots/services.png"),
  materials: staticFile("screenshots/materials.png"),
};
type SK = keyof typeof S;

// ─── Shared ───
const Stars: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill>
      <div style={{ width: "100%", height: "100%", background: `radial-gradient(ellipse at 50% 30%,${C.bg2},${C.bg1} 70%)` }} />
      {Array.from({ length: 50 }, (_, i) => {
        const seed = i * 137.508;
        return <div key={i} style={{ position: "absolute", left: `${(seed * 7.3) % 100}%`, top: `${((seed * 3.1 + f * 0.15) % 115) - 8}%`, width: 1 + (i % 3), height: 1 + (i % 3), borderRadius: "50%", backgroundColor: i % 2 === 0 ? C.purpleLight : C.cyan, opacity: 0.03 + (i % 5) * 0.02 }} />;
      })}
    </AbsoluteFill>
  );
};

const Orbs: React.FC<{ colors?: string[] }> = ({ colors = [C.purpleGlow, C.cyanGlow] }) => {
  const f = useCurrentFrame();
  return <>{colors.map((c, i) => {
    const a = f * 0.005 + (i * Math.PI * 2) / colors.length;
    return <div key={i} style={{ position: "absolute", width: 400, height: 400, borderRadius: "50%", background: `radial-gradient(circle,${c},transparent 65%)`, left: `${50 + Math.sin(a) * 18}%`, top: `${50 + Math.cos(a * 0.6) * 14}%`, transform: "translate(-50%,-50%)", filter: "blur(60px)", pointerEvents: "none" }} />;
  })}</>;
};

const BigWord: React.FC<{ text: string; delay: number; color?: string; size?: number; x?: number; y?: number }> = ({ text, delay, color = C.white, size = 72, x = 960, y = 540 }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: f - delay, fps, config: { damping: 8, mass: 0.3, stiffness: 200 } });
  const opacity = interpolate(f - delay, [0, 6, 50, 60], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div style={{ position: "absolute", left: x, top: y, transform: `translate(-50%,-50%) scale(${s})`, opacity, zIndex: 100, textAlign: "center" }}>
      <span style={{ fontSize: size, fontWeight: 900, color, textShadow: `0 4px 30px rgba(0,0,0,0.8), 0 0 40px ${color}40`, letterSpacing: -2 }}>{text}</span>
    </div>
  );
};

const Fade: React.FC<{ children: React.ReactNode; dur: number }> = ({ children, dur }) => {
  const f = useCurrentFrame();
  return <AbsoluteFill style={{ opacity: interpolate(f, [0, 10, dur - 10, dur], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }}>{children}</AbsoluteFill>;
};

// Browser chrome wrapper
const Chrome: React.FC<{ children: React.ReactNode; style?: React.CSSProperties }> = ({ children, style }) => (
  <div style={{ borderRadius: 14, overflow: "hidden", border: "1px solid rgba(255,255,255,0.1)", ...style }}>
    <div style={{ height: 32, background: "linear-gradient(180deg,#2a2a3e,#1e1e30)", display: "flex", alignItems: "center", padding: "0 12px", gap: 6, borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
      <div style={{ display: "flex", gap: 5 }}><div style={{ width: 9, height: 9, borderRadius: "50%", background: "#ff5f57" }} /><div style={{ width: 9, height: 9, borderRadius: "50%", background: "#febc2e" }} /><div style={{ width: 9, height: 9, borderRadius: "50%", background: "#28c840" }} /></div>
      <div style={{ flex: 1, height: 20, borderRadius: 5, background: "rgba(255,255,255,0.06)", display: "flex", alignItems: "center", padding: "0 8px", fontSize: 10, color: C.gray }}>🔒 bookedforyou.ie/dashboard</div>
    </div>
    {children}
  </div>
);

// ═══════════════════════════════════════════════════════════
// SCENE 1: INTRO — Logo burst + screens flying past
// ═══════════════════════════════════════════════════════════
const Intro: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const logoS = spring({ frame: f - 5, fps, config: { damping: 6, mass: 0.3, stiffness: 250 } });
  // Screens whooshing past in background
  const allKeys: SK[] = ["jobs", "calls", "calendar", "employees", "customers", "services", "materials"];
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <Orbs colors={[C.purpleGlow, C.cyanGlow, C.blueGlow]} />
      {/* Screens flying past */}
      {allKeys.map((k, i) => {
        const xPos = interpolate(f, [i * 8, i * 8 + 60], [2200, -800], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        const yPos = 150 + i * 100;
        const rot = -5 + i * 2;
        const op = interpolate(f, [i * 8, i * 8 + 10, i * 8 + 50, i * 8 + 60], [0, 0.25, 0.25, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        return <div key={i} style={{ position: "absolute", left: xPos, top: yPos, width: 500, opacity: op, transform: `rotate(${rot}deg)`, borderRadius: 10, overflow: "hidden", boxShadow: `0 10px 40px rgba(0,0,0,0.4)` }}>
          <Img src={S[k]} style={{ width: "100%", display: "block" }} />
        </div>;
      })}
      {/* Logo */}
      <div style={{ textAlign: "center", zIndex: 10, transform: `scale(${logoS})` }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 18, marginBottom: 20 }}>
          <div style={{ width: 80, height: 80, borderRadius: 22, background: `linear-gradient(135deg,${C.purple},${C.cyan})`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 44, boxShadow: `0 0 60px ${C.purpleGlow},0 0 120px ${C.cyanGlow}` }}>⚡</div>
          <span style={{ fontSize: 64, fontWeight: 900, color: C.white, letterSpacing: -2 }}>BookedForYou</span>
        </div>
      </div>
      <BigWord text="Your Dashboard" delay={25} size={56} y={620} color={C.purpleLight} />
      <BigWord text="Let's Go →" delay={50} size={48} y={700} color={C.cyan} />
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════════════
// SCENE 2: JOBS — Swoops in from below, tilts, then zooms into the cards
// ═══════════════════════════════════════════════════════════
const JobsScene: React.FC = () => {
  const f = useCurrentFrame();
  // Screen flies up from below and tilts back
  const entryY = interpolate(f, [0, 30], [600, 0], { extrapolateRight: "clamp", easing: (t) => 1 - Math.pow(1 - t, 3) });
  const tiltX = interpolate(f, [0, 30, 60], [25, 8, 0], { extrapolateRight: "clamp" });
  // Then zooms in
  const zoom = interpolate(f, [60, 100], [0.65, 1.1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const zoomY = interpolate(f, [60, 100], [0, -80], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <Orbs colors={[C.blueGlow, C.purpleGlow]} />
      <div style={{ perspective: 1200, position: "absolute", top: "50%", left: "50%", transform: `translate(-50%, calc(-50% + ${entryY}px + ${zoomY}px))` }}>
        <Chrome style={{ transform: `rotateX(${tiltX}deg) scale(${zoom})`, transformOrigin: "center top", width: 1300, boxShadow: `0 40px 100px rgba(0,0,0,0.6),0 0 50px ${C.blueGlow}` }}>
          <Img src={S.jobs} style={{ width: "100%", display: "block" }} />
        </Chrome>
      </div>
      <BigWord text="📋 JOBS" delay={5} size={90} y={100} color={C.blue} />
      <BigWord text="Track Everything" delay={35} size={52} x={300} y={180} color={C.white} />
      <BigWord text="One-Click Invoice" delay={70} size={44} x={1500} y={900} color={C.cyan} />
    </AbsoluteFill>
  );
};


// ═══════════════════════════════════════════════════════════
// SCENE 3: CALLS — Spins in from the right like a card flip
// ═══════════════════════════════════════════════════════════
const CallsScene: React.FC = () => {
  const f = useCurrentFrame();
  // Card flip from right
  const rotY = interpolate(f, [0, 35], [90, -8], { extrapolateRight: "clamp", easing: (t) => 1 - Math.pow(1 - t, 3) });
  const opacity = interpolate(f, [5, 20], [0, 1], { extrapolateRight: "clamp" });
  // Slow zoom
  const scale = interpolate(f, [35, 120], [0.7, 0.85], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const floatY = Math.sin(f * 0.05) * 5;
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <Orbs colors={[C.cyanGlow, C.blueGlow]} />
      <div style={{ perspective: 1400, position: "absolute", top: `calc(50% + ${floatY}px)`, left: "50%", transform: "translate(-50%,-50%)" }}>
        <Chrome style={{ transform: `rotateY(${rotY}deg) scale(${scale})`, opacity, width: 1300, boxShadow: `0 40px 100px rgba(0,0,0,0.6),0 0 50px ${C.cyanGlow}` }}>
          <Img src={S.calls} style={{ width: "100%", display: "block" }} />
        </Chrome>
      </div>
      <BigWord text="📞 AI CALLS" delay={5} size={88} y={90} color={C.cyan} />
      <BigWord text="Every Call Logged" delay={30} size={48} x={1450} y={200} color={C.white} />
      <BigWord text="Recordings · Transcripts" delay={60} size={40} x={400} y={920} color={C.purpleLight} />
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════════════
// SCENE 4: CALENDAR — Drops from above with bounce, then pans across
// ═══════════════════════════════════════════════════════════
const CalendarScene: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const dropY = spring({ frame: f, fps, config: { damping: 10, mass: 0.6, stiffness: 120 } });
  const yPos = interpolate(dropY, [0, 1], [-500, 0]);
  // Pan across the calendar (translateX)
  const panX = interpolate(f, [40, 140], [0, -200], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const tiltZ = interpolate(f, [0, 30], [-3, 0], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <Orbs colors={[C.purpleGlow, C.blueGlow]} />
      <div style={{ perspective: 1200, position: "absolute", top: `calc(45% + ${yPos}px)`, left: `calc(50% + ${panX}px)`, transform: "translate(-50%,-50%)" }}>
        <Chrome style={{ transform: `rotateZ(${tiltZ}deg) rotateX(5deg)`, width: 1400, boxShadow: `0 40px 100px rgba(0,0,0,0.6),0 0 50px ${C.purpleGlow}` }}>
          <Img src={S.calendar} style={{ width: "100%", display: "block" }} />
        </Chrome>
      </div>
      <BigWord text="📅 CALENDAR" delay={5} size={88} y={80} color={C.purple} />
      <BigWord text="Week · Month · Day" delay={30} size={44} x={350} y={180} color={C.white} />
      <BigWord text="Google Sync ✓" delay={65} size={48} x={1500} y={900} color={C.cyan} />
    </AbsoluteFill>
  );
};


// ═══════════════════════════════════════════════════════════
// SCENE 5: EMPLOYEES — Two screens side by side, sliding in from edges
// ═══════════════════════════════════════════════════════════
const EmployeesScene: React.FC = () => {
  const f = useCurrentFrame();
  // Main screen slides from left
  const leftX = interpolate(f, [0, 30], [-800, 60], { extrapolateRight: "clamp", easing: (t) => 1 - Math.pow(1 - t, 3) });
  // Duplicate zoomed-in version slides from right (showing detail)
  const rightX = interpolate(f, [10, 40], [1920, 980], { extrapolateRight: "clamp", easing: (t) => 1 - Math.pow(1 - t, 3) });
  const rightScale = interpolate(f, [40, 100], [0.55, 0.65], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill>
      <Orbs colors={["rgba(255,107,53,0.25)", C.purpleGlow]} />
      {/* Main screen — tilted left */}
      <div style={{ perspective: 1200, position: "absolute", left: leftX, top: "50%", transform: "translateY(-50%)" }}>
        <Chrome style={{ transform: "rotateY(12deg) rotateX(3deg)", width: 900, boxShadow: `0 30px 80px rgba(0,0,0,0.5),0 0 40px rgba(255,107,53,0.2)` }}>
          <Img src={S.employees} style={{ width: "100%", display: "block" }} />
        </Chrome>
      </div>
      {/* Zoomed detail — tilted right */}
      <div style={{ perspective: 1200, position: "absolute", left: rightX, top: "50%", transform: "translateY(-50%)" }}>
        <Chrome style={{ transform: `rotateY(-8deg) rotateX(2deg) scale(${rightScale})`, width: 900, boxShadow: `0 30px 80px rgba(0,0,0,0.5),0 0 40px ${C.purpleGlow}` }}>
          <Img src={S.employees} style={{ width: "100%", display: "block", transform: "scale(1.8) translate(-15%, -10%)" }} />
        </Chrome>
      </div>
      <BigWord text="👷 TEAM" delay={5} size={90} y={80} color={C.orange} />
      <BigWord text="Assign · Track · Manage" delay={35} size={46} x={960} y={960} color={C.white} />
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════════════
// SCENE 6: CUSTOMERS — Zooms from tiny to full screen (like opening an app)
// ═══════════════════════════════════════════════════════════
const CustomersScene: React.FC = () => {
  const f = useCurrentFrame();
  // Starts as a tiny card in center, expands to fill
  const scale = interpolate(f, [0, 35], [0.08, 0.75], { extrapolateRight: "clamp", easing: (t) => 1 - Math.pow(1 - t, 3) });
  const borderR = interpolate(f, [0, 35], [50, 14], { extrapolateRight: "clamp" });
  // Then tilts slightly
  const tiltY = interpolate(f, [35, 60], [0, -6], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  // Then zooms into the customer cards
  const lateZoom = interpolate(f, [80, 130], [0.75, 1.2], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const lateY = interpolate(f, [80, 130], [0, -100], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const finalScale = f < 80 ? scale : lateZoom;
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <Orbs colors={["rgba(255,0,110,0.2)", C.purpleGlow]} />
      <div style={{ perspective: 1400, position: "absolute", top: `calc(50% + ${lateY}px)`, left: "50%", transform: "translate(-50%,-50%)" }}>
        <Chrome style={{ transform: `rotateY(${tiltY}deg) scale(${finalScale})`, width: 1400, borderRadius: borderR, boxShadow: `0 40px 100px rgba(0,0,0,0.6),0 0 50px rgba(255,0,110,0.2)` }}>
          <Img src={S.customers} style={{ width: "100%", display: "block" }} />
        </Chrome>
      </div>
      <BigWord text="👥 CUSTOMERS" delay={5} size={88} y={80} color={C.pink} />
      <BigWord text="Auto-Saved from Calls" delay={40} size={44} x={350} y={180} color={C.white} />
      <BigWord text="Full History" delay={75} size={52} x={1500} y={900} color={C.cyan} />
    </AbsoluteFill>
  );
};


// ═══════════════════════════════════════════════════════════
// SCENE 7: SERVICES — Rotates in 3D like a spinning card, settles face-on
// ═══════════════════════════════════════════════════════════
const ServicesScene: React.FC = () => {
  const f = useCurrentFrame();
  // Full 3D spin then settle
  const rotY = interpolate(f, [0, 40], [180, 5], { extrapolateRight: "clamp", easing: (t) => 1 - Math.pow(1 - t, 4) });
  const scale = interpolate(f, [0, 40, 80, 130], [0.5, 0.7, 0.7, 0.95], { extrapolateRight: "clamp" });
  const opacity = interpolate(f, [0, 15], [0, 1], { extrapolateRight: "clamp" });
  // Gentle tilt
  const tiltX = interpolate(f, [40, 130], [8, 2 + Math.sin(f * 0.04) * 2], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <Orbs colors={["rgba(255,214,10,0.2)", C.purpleGlow]} />
      <div style={{ perspective: 1600, position: "absolute", top: "50%", left: "50%", transform: "translate(-50%,-50%)" }}>
        <Chrome style={{ transform: `rotateY(${rotY}deg) rotateX(${tiltX}deg) scale(${scale})`, opacity, width: 1300, boxShadow: `0 40px 100px rgba(0,0,0,0.6),0 0 50px rgba(255,214,10,0.2)`, backfaceVisibility: "hidden" }}>
          <Img src={S.services} style={{ width: "100%", display: "block" }} />
        </Chrome>
      </div>
      <BigWord text="🔧 SERVICES" delay={20} size={88} y={80} color={C.gold} />
      <BigWord text="Your Menu" delay={50} size={52} x={300} y={180} color={C.white} />
      <BigWord text="AI Knows Every Price" delay={80} size={42} x={1400} y={920} color={C.cyan} />
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════════════
// SCENE 8: MATERIALS — Slides up as a stack of cards, top one is materials
// ═══════════════════════════════════════════════════════════
const MaterialsScene: React.FC = () => {
  const f = useCurrentFrame();
  // Stack effect — multiple screens stacked with offset
  const stackScreens: SK[] = ["services", "employees", "materials"];
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <Orbs colors={[C.blueGlow, C.cyanGlow]} />
      {stackScreens.map((k, i) => {
        const delay = i * 10;
        const yOff = interpolate(f, [delay, delay + 25], [400, -i * 20], { extrapolateRight: "clamp", easing: (t) => 1 - Math.pow(1 - t, 3) });
        const rot = (i - 1) * 3;
        const sc = 0.6 + i * 0.05;
        const op = i === stackScreens.length - 1 ? 1 : 0.4 - i * 0.1;
        const zIdx = i;
        return (
          <div key={i} style={{ perspective: 1200, position: "absolute", top: `calc(50% + ${yOff}px)`, left: "50%", transform: "translate(-50%,-50%)", zIndex: zIdx }}>
            <Chrome style={{ transform: `rotateZ(${rot}deg) rotateX(5deg) scale(${sc})`, opacity: op, width: 1200, boxShadow: `0 30px 80px rgba(0,0,0,0.5)` }}>
              <Img src={S[k]} style={{ width: "100%", display: "block" }} />
            </Chrome>
          </div>
        );
      })}
      <BigWord text="📦 MATERIALS" delay={15} size={88} y={80} color={C.blue} />
      <BigWord text="Track Costs" delay={45} size={52} x={400} y={920} color={C.white} />
      <BigWord text="Per Job" delay={65} size={52} x={1500} y={920} color={C.cyan} />
    </AbsoluteFill>
  );
};


// ═══════════════════════════════════════════════════════════
// SCENE 9: ALL SCREENS ORBIT — explosive carousel
// ═══════════════════════════════════════════════════════════
const OrbitScene: React.FC = () => {
  const f = useCurrentFrame();
  const screens: { key: SK; icon: string; label: string; color: string }[] = [
    { key: "jobs", icon: "📋", label: "Jobs", color: C.blue },
    { key: "calls", icon: "📞", label: "Calls", color: C.cyan },
    { key: "calendar", icon: "📅", label: "Calendar", color: C.purple },
    { key: "employees", icon: "👷", label: "Employees", color: C.orange },
    { key: "customers", icon: "👥", label: "Customers", color: C.pink },
    { key: "services", icon: "🔧", label: "Services", color: C.gold },
    { key: "materials", icon: "📦", label: "Materials", color: C.blue },
  ];
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <Orbs colors={[C.purpleGlow, C.cyanGlow, C.blueGlow]} />
      {screens.map((s, i) => {
        const angle = (i / screens.length) * Math.PI * 2 + f * 0.01;
        const r = 500;
        const x = 960 + Math.sin(angle) * r;
        const z = Math.cos(angle) * r;
        const y = 540 + Math.sin(angle * 0.5) * 25;
        const sc = interpolate(z, [-r, r], [0.25, 0.5]);
        const op = interpolate(z, [-r, r], [0.25, 1]);
        const appear = interpolate(f, [i * 4, i * 4 + 10], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        return (
          <div key={i} style={{ position: "absolute", left: x - 380, top: y - 230, width: 760, transform: `scale(${sc})`, opacity: op * appear, zIndex: Math.round(z + r), borderRadius: 12, overflow: "hidden", boxShadow: `0 20px 60px rgba(0,0,0,0.5),0 0 20px ${s.color}20`, border: "1px solid rgba(255,255,255,0.08)" }}>
            <div style={{ height: 26, background: "#1e1e30", display: "flex", alignItems: "center", padding: "0 8px", gap: 4 }}>
              <div style={{ display: "flex", gap: 3 }}><div style={{ width: 7, height: 7, borderRadius: "50%", background: "#ff5f57" }} /><div style={{ width: 7, height: 7, borderRadius: "50%", background: "#febc2e" }} /><div style={{ width: 7, height: 7, borderRadius: "50%", background: "#28c840" }} /></div>
            </div>
            <Img src={S[s.key]} style={{ width: "100%", display: "block" }} />
            <div style={{ position: "absolute", bottom: 8, left: 8, background: "rgba(0,0,0,0.75)", borderRadius: 7, padding: "3px 10px", display: "flex", alignItems: "center", gap: 5 }}>
              <span style={{ fontSize: 12 }}>{s.icon}</span>
              <span style={{ fontSize: 11, fontWeight: 700, color: C.white }}>{s.label}</span>
            </div>
          </div>
        );
      })}
      <BigWord text="One Dashboard" delay={10} size={64} y={480} color={C.white} />
      <BigWord text="Every Tool ⚡" delay={25} size={56} y={560} color={C.cyan} />
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════════════
// SCENE 10: FINALE — CTA
// ═══════════════════════════════════════════════════════════
const Finale: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const logoS = spring({ frame: f - 5, fps, config: { damping: 6, mass: 0.3, stiffness: 250 } });
  const btnS = spring({ frame: f - 35, fps, config: { damping: 8, mass: 0.4, stiffness: 200 } });
  const glow = interpolate(Math.sin(f * 0.1), [-1, 1], [0.4, 1]);
  // Burst particles
  const particles = Array.from({ length: 16 }, (_, i) => {
    const angle = (i / 16) * Math.PI * 2;
    const dist = interpolate(f, [0, 25], [0, 180 + (i % 3) * 60], { extrapolateRight: "clamp" });
    const op = interpolate(f, [0, 12, 35], [0, 1, 0], { extrapolateRight: "clamp" });
    return { x: Math.cos(angle) * dist, y: Math.sin(angle) * dist, op, c: i % 3 === 0 ? C.purple : i % 3 === 1 ? C.cyan : C.gold };
  });
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <Orbs colors={[C.purpleGlow, C.cyanGlow]} />
      {particles.map((p, i) => <div key={i} style={{ position: "absolute", left: "50%", top: "50%", transform: `translate(calc(-50% + ${p.x}px),calc(-50% + ${p.y}px))`, width: 7, height: 7, borderRadius: "50%", background: p.c, opacity: p.op, boxShadow: `0 0 10px ${p.c}` }} />)}
      <div style={{ textAlign: "center", zIndex: 2 }}>
        <div style={{ transform: `scale(${logoS})`, marginBottom: 20 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 16 }}>
            <div style={{ width: 72, height: 72, borderRadius: 18, background: `linear-gradient(135deg,${C.purple},${C.cyan})`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 38, boxShadow: `0 0 60px ${C.purpleGlow},0 0 120px ${C.cyanGlow}` }}>⚡</div>
            <span style={{ fontSize: 56, fontWeight: 900, color: C.white, letterSpacing: -2 }}>BookedForYou</span>
          </div>
        </div>
        <BigWord text="Get Started" delay={15} size={64} y={520} color={C.white} />
        <div style={{ position: "absolute", left: "50%", top: 600, transform: `translate(-50%) scale(${btnS})`, zIndex: 10 }}>
          <div style={{ display: "inline-block", background: `linear-gradient(135deg,${C.purple},${C.cyan})`, borderRadius: 20, padding: "22px 58px", boxShadow: `0 0 ${55 * glow}px ${C.purpleGlow},0 0 ${90 * glow}px ${C.cyanGlow}` }}>
            <span style={{ fontSize: 28, fontWeight: 900, color: C.white }}>Get Started →</span>
          </div>
        </div>
        <BigWord text="bookedforyou.ie" delay={45} size={28} y={700} color={C.purpleLight} />
      </div>
    </AbsoluteFill>
  );
};


// ═══════════════════════════════════════════════════════════
// MAIN COMPOSITION — each scene is unique
// ═══════════════════════════════════════════════════════════
export const Walkthrough3D: React.FC = () => {
  const scenes: { component: React.FC; duration: number }[] = [
    { component: Intro, duration: 100 },           // 3.3s — logo + screens flying
    { component: JobsScene, duration: 150 },        // 5s — swoops up, zooms in
    { component: CallsScene, duration: 150 },       // 5s — card flip
    { component: CalendarScene, duration: 165 },    // 5.5s — drops + pans
    { component: EmployeesScene, duration: 135 },     // 4.5s — dual screens
    { component: CustomersScene, duration: 150 },   // 5s — tiny to full zoom
    { component: ServicesScene, duration: 150 },     // 5s — 3D spin
    { component: MaterialsScene, duration: 120 },   // 4s — card stack
    { component: OrbitScene, duration: 180 },       // 6s — carousel
    { component: Finale, duration: 120 },           // 4s — CTA
  ];
  // Total: 1420 frames
  let f = 0;
  return (
    <AbsoluteFill style={{ fontFamily: FONT }}>
      <Audio src={staticFile("music.mp3")} volume={0.3} />
      <Stars />
      {scenes.map((s, i) => {
        const from = f; f += s.duration;
        const Scene = s.component;
        return <Sequence key={i} from={from} durationInFrames={s.duration}><Fade dur={s.duration}><Scene /></Fade></Sequence>;
      })}
    </AbsoluteFill>
  );
};
