/**
 * EditorialPack — five landscape marketing videos with a
 * visual language intentionally different from everything in
 * SocialPack*.tsx.  No radial space-orbs, no emoji-as-visual.
 *
 * 1. Editorial_Headline   — Newsprint editorial feature
 * 2. SplitFlap_Metrics    — Airport split-flap board live stats
 * 3. IsoCity_CallFunnel   — Isometric city, call arcs, dashboard
 * 4. MacApp_Cursor        — Photoreal mac-window with cursor demo
 * 5. Newsroom_Breaking    — Cable-news chyron "industry shift"
 */

import {
  AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate, spring, Sequence, Easing,
} from "remotion";
import React from "react";

// ──────────────────────────────────────────────────────────
//  Shared palette (editorial, not "space gradient")
// ──────────────────────────────────────────────────────────
const P = {
  paper:  "#f4efe6",
  paperDk:"#ebe3d2",
  ink:    "#0b0b0d",
  muted:  "#6b665c",
  rule:   "#1a1a1a",
  accent: "#c8412a",         // vermilion ink
  accent2:"#1d4e89",         // navy
  gold:   "#b48a2c",
  steel:  "#cfd4da",
  // "studio" palette for iso/mac scenes
  studioBg:"#f1f2f4",
  studioTop:"#ffffff",
  studioShadow:"rgba(18,22,33,0.12)",
  brand:  "#0b5cff",
  brandDk:"#0a3fb0",
  green:  "#16a34a",
  red:    "#dc2626",
};

const SERIF  = "'Times New Roman','Times',Georgia,serif";
const SANS   = "'Inter','Helvetica Neue',Helvetica,Arial,sans-serif";
const MONO   = "'JetBrains Mono','SF Mono',Menlo,Consolas,monospace";

// ──────────────────────────────────────────────────────────
//  Small utilities (local; do not import from SocialPack)
// ──────────────────────────────────────────────────────────

/** slides up + fades in, then holds. */
const Enter: React.FC<{
  children: React.ReactNode; delay?: number; from?: number;
  dur?: number; style?: React.CSSProperties; ease?: (t: number)=>number;
}> = ({ children, delay = 0, from = 24, dur = 14, style, ease = Easing.out(Easing.cubic) }) => {
  const f = useCurrentFrame();
  const p = interpolate(f - delay, [0, dur], [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
  return (
    <div style={{ opacity: p, transform: `translateY(${(1 - p) * from}px)`, ...style }}>
      {children}
    </div>
  );
};

/** crossfade wrapper for a scene */
const SceneFade: React.FC<{ children: React.ReactNode; dur: number; hold?: number }> =
  ({ children, dur, hold = 10 }) => {
    const f = useCurrentFrame();
    const op = interpolate(f, [0, hold, dur - hold, dur], [0, 1, 1, 0],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    return <AbsoluteFill style={{ opacity: op }}>{children}</AbsoluteFill>;
  };

/** Wordmark — clean, no emoji */
const Wordmark: React.FC<{ color?: string; size?: number; onDark?: boolean }> =
  ({ color = P.ink, size = 22, onDark }) => (
    <div style={{ display: "flex", alignItems: "center", gap: 10, fontFamily: SANS }}>
      <div style={{
        width: size * 1.2, height: size * 1.2, borderRadius: 6,
        background: onDark ? "#fff" : P.ink,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontFamily: SERIF, fontWeight: 700, fontSize: size * 0.95,
        color: onDark ? P.ink : "#fff", letterSpacing: -0.5,
      }}>B</div>
      <span style={{ fontSize: size * 0.95, fontWeight: 700, color, letterSpacing: -0.4 }}>
        BookedForYou
      </span>
    </div>
  );

// Paper grain — subtle SVG noise
const PaperGrain: React.FC<{ opacity?: number }> = ({ opacity = 0.18 }) => (
  <svg width="100%" height="100%" style={{ position: "absolute", inset: 0, opacity, mixBlendMode: "multiply" }}>
    <filter id="grain">
      <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" stitchTiles="stitch" />
      <feColorMatrix values="0 0 0 0 0.05  0 0 0 0 0.05  0 0 0 0 0.05  0 0 0 0.5 0" />
    </filter>
    <rect width="100%" height="100%" filter="url(#grain)" />
  </svg>
);

/** SVG stroke-draw underline with hand-drawn wobble */
const InkUnderline: React.FC<{
  width?: number; delay?: number; color?: string; thick?: number; dur?: number;
}> = ({ width = 260, delay = 0, color = P.accent, thick = 6, dur = 18 }) => {
  const f = useCurrentFrame();
  const p = interpolate(f - delay, [0, dur], [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
  const dash = width * 1.05;
  return (
    <svg width={width} height="18" viewBox={`0 0 ${width} 18`} style={{ display: "block" }}>
      <path
        d={`M 4 12 Q ${width * 0.25} ${4 + Math.sin(delay) * 3}, ${width * 0.5} 10 T ${width - 6} 9`}
        stroke={color} strokeWidth={thick} strokeLinecap="round" fill="none"
        strokeDasharray={dash} strokeDashoffset={dash * (1 - p)}
      />
    </svg>
  );
};

// ──────────────────────────────────────────────────────────
//  VIDEO 1 — Editorial_Headline
//  "Newsprint feature" about the shift to AI receptionists
// ──────────────────────────────────────────────────────────

const Masthead: React.FC<{ delay?: number }> = ({ delay = 0 }) => {
  const f = useCurrentFrame();
  const op = interpolate(f - delay, [0, 12], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div style={{ opacity: op, borderBottom: `2px solid ${P.rule}`, padding: "24px 80px 16px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontFamily: SANS, fontSize: 13, color: P.muted, letterSpacing: 1.2, textTransform: "uppercase" }}>
        <span>Vol. XII · No. 47</span>
        <span>The Trades Review</span>
        <span>Thursday Edition</span>
      </div>
      <div style={{ textAlign: "center", fontFamily: SERIF, fontSize: 92, fontWeight: 700, letterSpacing: -2, lineHeight: 1, marginTop: 10, color: P.ink }}>
        THE&nbsp;TRADES&nbsp;REVIEW
      </div>
    </div>
  );
};

const TypedSerif: React.FC<{ text: string; delay: number; size?: number; cps?: number; color?: string; italic?: boolean }> =
  ({ text, delay, size = 28, cps = 45, color = P.ink, italic }) => {
    const f = useCurrentFrame();
    const { fps } = useVideoConfig();
    const n = Math.max(0, Math.min(text.length, Math.floor(((f - delay) / fps) * cps)));
    const shown = text.slice(0, n);
    const caret = (f - delay) >= 0 && n < text.length;
    return (
      <span style={{ fontFamily: SERIF, fontSize: size, lineHeight: 1.25, color, fontStyle: italic ? "italic" : "normal" }}>
        {shown}
        {caret && <span style={{ display: "inline-block", width: 3, height: size * 0.9, background: color, verticalAlign: "middle", marginLeft: 2, opacity: Math.floor(f / 10) % 2 }} />}
      </span>
    );
  };

const Ed_Scene1: React.FC = () => {
  return (
    <AbsoluteFill style={{ background: P.paper }}>
      <PaperGrain />
      <Masthead delay={0} />
      <div style={{ padding: "40px 120px 0" }}>
        {/* Kicker */}
        <Enter delay={14}>
          <div style={{ display: "flex", alignItems: "center", gap: 16, fontFamily: SANS, fontSize: 14, letterSpacing: 2, textTransform: "uppercase", color: P.accent, fontWeight: 700 }}>
            <span>Industry Feature</span>
            <div style={{ flex: 0, width: 60, height: 2, background: P.accent }} />
            <span style={{ color: P.muted }}>8 min read</span>
          </div>
        </Enter>
        {/* Headline */}
        <Enter delay={22} from={40}>
          <h1 style={{ fontFamily: SERIF, fontSize: 112, lineHeight: 1.0, letterSpacing: -3, margin: "20px 0 6px", color: P.ink, fontWeight: 700 }}>
            The quiet end of the<br/>
            missed&nbsp;call.
          </h1>
        </Enter>
        <Enter delay={40}>
          <div style={{ marginTop: -4, marginLeft: 4 }}>
            <InkUnderline width={520} delay={46} color={P.accent} thick={8} dur={22} />
          </div>
        </Enter>
        <Enter delay={56}>
          <p style={{ fontFamily: SERIF, fontStyle: "italic", fontSize: 30, color: P.muted, maxWidth: 1100, marginTop: 30, lineHeight: 1.35 }}>
            Across Ireland and the UK, plumbers, electricians and salons are
            handing the phone to an AI — and quietly reclaiming their evenings.
          </p>
        </Enter>
      </div>
    </AbsoluteFill>
  );
};

const PullQuote: React.FC<{ quote: string; attr: string; delay: number }> = ({ quote, attr, delay }) => (
  <Enter delay={delay} from={30}>
    <div style={{ borderLeft: `6px solid ${P.accent}`, padding: "6px 28px", margin: "0 60px" }}>
      <div style={{ fontFamily: SERIF, fontSize: 58, lineHeight: 1.1, color: P.ink, letterSpacing: -1 }}>
        &ldquo;{quote}&rdquo;
      </div>
      <div style={{ fontFamily: SANS, fontSize: 16, letterSpacing: 2, textTransform: "uppercase", color: P.muted, marginTop: 18 }}>
        — {attr}
      </div>
    </div>
  </Enter>
);

const Ed_Scene2: React.FC = () => (
  <AbsoluteFill style={{ background: P.paper, padding: "80px 60px", justifyContent: "center" }}>
    <PaperGrain opacity={0.14} />
    <PullQuote
      quote="I used to lose three jobs a week to voicemail. Now I lose none — and I sleep."
      attr="Martin C., Plumber · Dublin"
      delay={6}
    />
  </AbsoluteFill>
);

/** Two-column body paragraphs */
const Ed_Scene3: React.FC = () => {
  const col = {
    fontFamily: SERIF, fontSize: 22, lineHeight: 1.55, color: P.ink,
    columnWidth: 420, columnGap: 40, textAlign: "justify" as const,
  };
  return (
    <AbsoluteFill style={{ background: P.paper, padding: "70px 110px" }}>
      <PaperGrain opacity={0.14} />
      <Enter delay={0}>
        <div style={{ fontFamily: SANS, fontSize: 13, letterSpacing: 2, textTransform: "uppercase", color: P.muted, marginBottom: 14 }}>
          By Staff · Filed from Dublin
        </div>
      </Enter>
      <Enter delay={8} from={40}>
        <h2 style={{ fontFamily: SERIF, fontSize: 68, lineHeight: 1.05, color: P.ink, letterSpacing: -1.5, margin: "0 0 26px", fontWeight: 700 }}>
          A receptionist that never sleeps, never forgets, never gossips.
        </h2>
      </Enter>
      <Enter delay={22}>
        <p style={col}>
          <span style={{ fontFamily: SERIF, fontSize: 74, lineHeight: 0.8, float: "left", padding: "10px 8px 0 0", color: P.accent }}>T</span>
          he numbers are unkind. A mid-sized trades business misses roughly fifteen
          calls a week. At a forty-per-cent conversion rate and an average ticket
          of €250, that is €1,500 walking out the door, every week. Over a year,
          nearly €78,000 — enough to hire a full-time employee, or a small van,
          or an extended family holiday that will now not be taken. The
          alternative, until recently, was an answering service or a cousin. Both
          tend to be expensive, forgetful, or both. <br/><br/>
          Booked&nbsp;For&nbsp;You, a Dublin-built platform, answers every call in
          under a second, takes the booking, syncs the calendar, sends the
          reminder, and forwards the emergencies. It does not call in sick. It
          does not have opinions about the customer. It costs less than a good
          dinner a week.
        </p>
      </Enter>
    </AbsoluteFill>
  );
};

const Ed_Scene4: React.FC = () => {
  const f = useCurrentFrame();
  const stats = [
    { label: "Calls answered",   target: 100, suffix: "%", col: P.accent  },
    { label: "Jobs recovered",   target: 312,  suffix: "/yr", col: P.accent2 },
    { label: "Average response", target: 0.8,  suffix: "s", col: P.gold    },
    { label: "Cost of missing",  target: 78000, suffix: " €", col: P.ink   },
  ];
  return (
    <AbsoluteFill style={{ background: P.paper, padding: "90px 120px" }}>
      <PaperGrain opacity={0.12} />
      <Enter delay={0}>
        <div style={{ fontFamily: SANS, fontSize: 13, letterSpacing: 2, textTransform: "uppercase", color: P.muted, marginBottom: 8 }}>
          By the Numbers
        </div>
      </Enter>
      <Enter delay={8} from={40}>
        <h3 style={{ fontFamily: SERIF, fontSize: 54, color: P.ink, margin: "0 0 40px", letterSpacing: -1 }}>
          What the switch looks like.
        </h3>
      </Enter>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 48, marginTop: 12 }}>
        {stats.map((s, i) => {
          const d = 20 + i * 8;
          const pr = interpolate(f - d, [0, 46], [0, 1],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
          const n = s.target * pr;
          const display = s.target >= 1000 ? Math.round(n).toLocaleString() :
            (s.target < 10 ? n.toFixed(1) : Math.round(n).toString());
          return (
            <Enter key={i} delay={d}>
              <div style={{ borderTop: `3px solid ${s.col}`, paddingTop: 18 }}>
                <div style={{ fontFamily: SERIF, fontSize: 96, fontWeight: 700, color: s.col, letterSpacing: -3, lineHeight: 1 }}>
                  {display}<span style={{ fontFamily: SANS, fontSize: 28, marginLeft: 6, color: P.ink, fontWeight: 600 }}>{s.suffix}</span>
                </div>
                <div style={{ fontFamily: SANS, fontSize: 16, color: P.muted, marginTop: 8, letterSpacing: 0.3 }}>
                  {s.label}
                </div>
              </div>
            </Enter>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

const Ed_Scene5: React.FC = () => (
  <AbsoluteFill style={{ background: P.paper, padding: "0 120px", justifyContent: "center" }}>
    <PaperGrain />
    <Enter delay={0}>
      <div style={{ fontFamily: SANS, fontSize: 13, letterSpacing: 3, textTransform: "uppercase", color: P.muted, marginBottom: 30 }}>
        Continued on page A4 ·
      </div>
    </Enter>
    <Enter delay={10} from={40}>
      <div style={{ fontFamily: SERIF, fontSize: 120, lineHeight: 0.95, color: P.ink, letterSpacing: -3, fontWeight: 700 }}>
        Hand the phone over.
      </div>
    </Enter>
    <Enter delay={24}>
      <div style={{ marginTop: 12 }}>
        <InkUnderline width={720} color={P.accent} thick={10} delay={28} dur={26} />
      </div>
    </Enter>
    <Enter delay={40}>
      <TypedSerif text="14-day trial. No card. Cancel in a click." delay={40} size={32} color={P.muted} italic />
    </Enter>
    <Enter delay={72} style={{ marginTop: 36 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 28 }}>
        <Wordmark size={28} />
        <span style={{ fontFamily: MONO, fontSize: 18, color: P.muted }}>bookedforyou.ie</span>
      </div>
    </Enter>
  </AbsoluteFill>
);

export const Editorial_Headline: React.FC = () => {
  const scenes = [
    { c: Ed_Scene1, d: 170 },
    { c: Ed_Scene2, d: 140 },
    { c: Ed_Scene3, d: 200 },
    { c: Ed_Scene4, d: 200 },
    { c: Ed_Scene5, d: 180 },
  ];
  let s = 0;
  return (
    <AbsoluteFill>
      {scenes.map((sc, i) => {
        const from = s; s += sc.d; const Sc = sc.c;
        return (
          <Sequence key={i} from={from} durationInFrames={sc.d}>
            <SceneFade dur={sc.d}><Sc /></SceneFade>
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};

// ──────────────────────────────────────────────────────────
//  VIDEO 2 — SplitFlap_Metrics
//  Airport-style split-flap board that flips to reveal stats
// ──────────────────────────────────────────────────────────

const FlapChar: React.FC<{ target: string; delay: number; speed?: number }> = ({ target, delay, speed = 2 }) => {
  const f = useCurrentFrame();
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:/.-€% ";
  const idxTarget = Math.max(0, chars.indexOf(target.toUpperCase()));
  const elapsed = Math.max(0, f - delay);
  const flips = Math.min(idxTarget, Math.floor(elapsed / speed));
  const flipT = Math.min(1, (elapsed - flips * speed) / speed);
  const curr = chars[Math.min(flips, idxTarget)];
  const next = chars[Math.min(flips + 1, idxTarget)] ?? curr;
  const done = flips >= idxTarget;
  const shown = done ? target : curr;
  const flipDeg = done ? 0 : flipT * 90;

  return (
    <div style={{
      width: 44, height: 64, margin: "0 2px",
      background: "#141618", color: "#f7d77a",
      border: "1px solid #2a2d33",
      borderRadius: 4, position: "relative",
      fontFamily: MONO, fontWeight: 800, fontSize: 44, lineHeight: "64px",
      textAlign: "center",
      boxShadow: "inset 0 1px 0 rgba(255,255,255,0.05), 0 2px 0 #000",
      overflow: "hidden",
      textTransform: "uppercase",
    }}>
      {/* Center divider */}
      <div style={{ position: "absolute", left: 0, right: 0, top: "50%", height: 1, background: "#000", zIndex: 3 }} />
      {/* Top half (flipping) */}
      <div style={{
        position: "absolute", inset: 0, height: "50%", overflow: "hidden",
        transformOrigin: "bottom",
        transform: `perspective(220px) rotateX(-${flipDeg}deg)`,
        background: "#141618",
        borderBottom: "1px solid #000",
        zIndex: 2,
      }}>
        <span style={{ position: "absolute", top: 0, left: 0, right: 0, textAlign: "center" }}>{next}</span>
      </div>
      {/* Bottom half (static, shows previous) */}
      <div style={{
        position: "absolute", left: 0, right: 0, bottom: 0, height: "50%", overflow: "hidden",
        zIndex: 1,
      }}>
        <span style={{ position: "absolute", bottom: 0, left: 0, right: 0, textAlign: "center", lineHeight: "64px", height: 64, top: -32 }}>
          {shown}
        </span>
      </div>
    </div>
  );
};

const FlapRow: React.FC<{ label: string; value: string; status: string; delay: number; statusColor?: string }> =
  ({ label, value, status, delay, statusColor = "#00d98f" }) => {
    const f = useCurrentFrame();
    const enter = interpolate(f - delay, [0, 12], [0, 1],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    return (
      <div style={{ opacity: enter, display: "grid", gridTemplateColumns: "320px 1fr 240px", alignItems: "center", gap: 24, padding: "10px 24px", borderBottom: "1px solid #1c1f24" }}>
        <div style={{ fontFamily: MONO, fontSize: 22, color: "#cdd4de", letterSpacing: 1 }}>
          {label.toUpperCase()}
        </div>
        <div style={{ display: "flex" }}>
          {value.split("").map((ch, i) => (
            <FlapChar key={i} target={ch} delay={delay + 8 + i * 2} speed={2} />
          ))}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10, justifyContent: "flex-end" }}>
          <span style={{ width: 10, height: 10, borderRadius: "50%", background: statusColor, boxShadow: `0 0 10px ${statusColor}` , opacity: 0.6 + 0.4 * Math.sin(f * 0.2) }} />
          <span style={{ fontFamily: MONO, fontSize: 18, color: statusColor, letterSpacing: 1 }}>
            {status}
          </span>
        </div>
      </div>
    );
  };

export const SplitFlap_Metrics: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: "#0a0b0d", fontFamily: SANS }}>
      {/* terminal-room vignette */}
      <AbsoluteFill style={{ background: "radial-gradient(ellipse at 50% 40%, rgba(28,36,48,0.6), transparent 70%)" }} />
      {/* ceiling bar */}
      <div style={{ position: "absolute", top: 40, left: 60, right: 60, height: 8, background: "linear-gradient(180deg,#23262c,#0d0f12)", borderRadius: 3 }} />
      {/* Header */}
      <div style={{ position: "absolute", top: 72, left: 60, right: 60, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Enter delay={0}>
          <div style={{ fontFamily: MONO, fontSize: 22, color: "#f7d77a", letterSpacing: 3 }}>
            BOOKED-FOR-YOU · LIVE OPS
          </div>
        </Enter>
        <Enter delay={6}>
          <div style={{ display: "flex", gap: 18, alignItems: "center" }}>
            <div style={{ fontFamily: MONO, fontSize: 18, color: "#8892a0" }}>
              {new Date(2000 + f).toISOString().slice(11, 19)} UTC
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "4px 10px", border: "1px solid #2a7a4e", borderRadius: 4 }}>
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#00d98f", boxShadow: "0 0 8px #00d98f" }} />
              <span style={{ fontFamily: MONO, fontSize: 14, color: "#00d98f" }}>ONLINE</span>
            </div>
          </div>
        </Enter>
      </div>

      {/* Column headers */}
      <div style={{ position: "absolute", top: 130, left: 60, right: 60, display: "grid", gridTemplateColumns: "320px 1fr 240px", gap: 24, padding: "0 24px", color: "#58606e", fontFamily: MONO, fontSize: 14, letterSpacing: 2 }}>
        <div>METRIC</div>
        <div>VALUE</div>
        <div style={{ textAlign: "right" }}>STATUS</div>
      </div>

      {/* Flap rows */}
      <div style={{ position: "absolute", top: 164, left: 60, right: 60, background: "#0e1013", border: "1px solid #1c1f24", borderRadius: 8, overflow: "hidden" }}>
        <FlapRow delay={20}  label="Calls answered today"  value="47/47"         status="ON TIME" />
        <FlapRow delay={60}  label="Average response"      value="0.8 SEC"       status="AHEAD"  />
        <FlapRow delay={100} label="Jobs booked this week" value="€14,280"       status="BOARDING" statusColor="#7abfff" />
        <FlapRow delay={140} label="Missed calls"          value="0"             status="CLEARED" />
        <FlapRow delay={180} label="AI uptime"             value="99.98%"        status="NOMINAL" />
        <FlapRow delay={220} label="Next reminder batch"   value="17:00"         status="QUEUED"  statusColor="#f7d77a" />
      </div>

      {/* Lower "announcement" strip */}
      <div style={{ position: "absolute", bottom: 80, left: 60, right: 60 }}>
        <Enter delay={260}>
          <div style={{ background: "linear-gradient(180deg,#141618,#0d0f12)", border: "1px solid #1c1f24", borderRadius: 8, padding: "22px 28px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <div style={{ fontFamily: MONO, fontSize: 13, color: "#8892a0", letterSpacing: 2 }}>ANNOUNCEMENT</div>
              <div style={{ fontFamily: MONO, fontSize: 28, color: "#f7d77a", marginTop: 6, letterSpacing: 1 }}>
                Every call, every lead, every booking — logged.
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontFamily: MONO, fontSize: 13, color: "#8892a0", letterSpacing: 2 }}>GATE</div>
              <div style={{ fontFamily: MONO, fontSize: 28, color: "#00d98f" }}>B — 14-DAY TRIAL</div>
            </div>
          </div>
        </Enter>
      </div>

      {/* Bottom wordmark */}
      <div style={{ position: "absolute", bottom: 28, left: 60 }}>
        <Enter delay={290}><Wordmark size={20} onDark color="#fff" /></Enter>
      </div>
      <div style={{ position: "absolute", bottom: 30, right: 60 }}>
        <Enter delay={295}>
          <span style={{ fontFamily: MONO, fontSize: 16, color: "#8892a0" }}>bookedforyou.ie</span>
        </Enter>
      </div>
    </AbsoluteFill>
  );
};

// ──────────────────────────────────────────────────────────
//  VIDEO 3 — IsoCity_CallFunnel
//  Isometric city; calls travel along arcs into one hub
// ──────────────────────────────────────────────────────────

const IsoBuilding: React.FC<{ x: number; y: number; w: number; h: number; d?: number; fill?: string; top?: string; delay?: number }> =
  ({ x, y, w, h, d = 40, fill = "#dfe3ea", top = "#eef1f5", delay = 0 }) => {
    const f = useCurrentFrame();
    const s = spring({ frame: f - delay, fps: 30, config: { damping: 14, mass: 0.6, stiffness: 120 } });
    const hh = h * s;
    const ty = y + (h - hh);
    // isometric projection: 30° / 30°
    const iso = (px: number, py: number) => {
      const ix = (px - py) * Math.cos(Math.PI / 6);
      const iy = (px + py) * Math.sin(Math.PI / 6);
      return `${ix},${iy}`;
    };
    const front = `${iso(x, ty + hh)} ${iso(x + w, ty + hh)} ${iso(x + w, ty + hh - d)} ${iso(x, ty + hh - d)}`;
    const side  = `${iso(x + w, ty)} ${iso(x + w, ty + hh)} ${iso(x + w, ty + hh - d)} ${iso(x + w, ty - d)}`;
    const topP  = `${iso(x, ty)} ${iso(x + w, ty)} ${iso(x + w, ty - d)} ${iso(x, ty - d)}`;
    return (
      <g opacity={s}>
        <polygon points={front} fill={fill} stroke="#b8bfcb" strokeWidth={0.5} />
        <polygon points={side}  fill="#c9cfd9" stroke="#a9b0bd" strokeWidth={0.5} />
        <polygon points={topP}  fill={top}    stroke="#b8bfcb" strokeWidth={0.5} />
        {/* windows */}
        {Array.from({ length: Math.max(1, Math.floor(hh / 22)) }).map((_, i) => {
          const wy = ty + 10 + i * 22;
          if (wy > ty + hh - 12) return null;
          return (
            <g key={i}>
              <polygon
                points={`${iso(x + 4, wy)} ${iso(x + w - 4, wy)} ${iso(x + w - 4, wy + 10)} ${iso(x + 4, wy + 10)}`}
                fill={(i + x) % 3 === 0 ? "#ffd86b" : "rgba(40,58,90,0.65)"} opacity={0.9}
              />
            </g>
          );
        })}
      </g>
    );
  };

const CallArc: React.FC<{
  x1: number; y1: number; x2: number; y2: number; delay: number; color?: string;
}> = ({ x1, y1, x2, y2, delay, color = P.brand }) => {
  const f = useCurrentFrame();
  const p = interpolate(f - delay, [0, 36], [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.inOut(Easing.cubic) });
  const fade = interpolate(f - delay, [0, 8, 36, 44], [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  // bezier control point arcs above
  const cx = (x1 + x2) / 2, cy = Math.min(y1, y2) - 140;
  const t = p;
  // quadratic bezier point
  const bx = (1 - t) * (1 - t) * x1 + 2 * (1 - t) * t * cx + t * t * x2;
  const by = (1 - t) * (1 - t) * y1 + 2 * (1 - t) * t * cy + t * t * y2;
  // dashed trailing path
  const d = `M ${x1} ${y1} Q ${cx} ${cy} ${x2} ${y2}`;
  const totalLen = 600;
  return (
    <g opacity={fade}>
      <path d={d} stroke={color} strokeWidth={2} strokeDasharray="4 6" fill="none" opacity={0.35} />
      <path d={d} stroke={color} strokeWidth={3} fill="none"
        strokeDasharray={totalLen}
        strokeDashoffset={totalLen * (1 - p)}
        strokeLinecap="round" />
      <circle cx={bx} cy={by} r={9} fill="#fff" stroke={color} strokeWidth={3} />
      <text x={bx} y={by + 4} textAnchor="middle" fontFamily={MONO} fontSize={10} fill={color} fontWeight={700}>
        ☎
      </text>
    </g>
  );
};

const CentralHub: React.FC<{ x: number; y: number; delay: number }> = ({ x, y, delay }) => {
  const f = useCurrentFrame();
  const pulse = interpolate((f - delay) % 36, [0, 36], [0, 1]);
  const ring = 1 - pulse;
  const s = spring({ frame: f - delay, fps: 30, config: { damping: 12, mass: 0.5 } });
  return (
    <g transform={`translate(${x},${y}) scale(${s})`}>
      <circle r={90 + pulse * 90} fill="none" stroke={P.brand} strokeWidth={2} opacity={ring * 0.5} />
      <circle r={60 + pulse * 40} fill="none" stroke={P.brand} strokeWidth={2} opacity={ring * 0.6} />
      <circle r={54} fill="#fff" stroke={P.brand} strokeWidth={3} />
      <circle r={42} fill={P.brand} />
      <text y={8} textAnchor="middle" fontFamily={SANS} fontSize={36} fontWeight={800} fill="#fff">
        B
      </text>
    </g>
  );
};

export const IsoCity_CallFunnel: React.FC = () => {
  const f = useCurrentFrame();
  // centered iso viewBox
  return (
    <AbsoluteFill style={{ background: "linear-gradient(180deg,#eaf0f8 0%,#dfe7f2 70%,#cbd5e3 100%)", fontFamily: SANS }}>
      {/* sun */}
      <div style={{ position: "absolute", top: 80, right: 160, width: 180, height: 180, borderRadius: "50%", background: "radial-gradient(circle,#fff4c4 0%,rgba(255,244,196,0) 70%)" }} />
      {/* headline */}
      <div style={{ position: "absolute", top: 60, left: 80, zIndex: 10 }}>
        <Enter delay={0}>
          <div style={{ fontSize: 16, color: P.accent2, fontWeight: 700, letterSpacing: 3, textTransform: "uppercase" }}>
            One city. Every call.
          </div>
        </Enter>
        <Enter delay={8} from={30}>
          <h2 style={{ fontFamily: SERIF, fontSize: 72, lineHeight: 1.0, letterSpacing: -2, color: P.ink, margin: "6px 0 0", fontWeight: 700 }}>
            Every phone ringing in<br/> your region — routed here.
          </h2>
        </Enter>
      </div>

      <svg
        width="100%" height="100%" viewBox="-900 -600 1800 1200"
        style={{ position: "absolute", inset: 0 }}
      >
        {/* ground grid */}
        <g opacity={0.3}>
          {Array.from({ length: 40 }).map((_, i) => {
            const g = i - 20;
            return (
              <g key={i}>
                <line
                  x1={(g * 60 - -1000) * Math.cos(Math.PI / 6)} y1={(g * 60 + -1000) * Math.sin(Math.PI / 6)}
                  x2={(g * 60 - 1000) * Math.cos(Math.PI / 6)} y2={(g * 60 + 1000) * Math.sin(Math.PI / 6)}
                  stroke="#b8c3d3" strokeWidth={0.5}
                />
                <line
                  x1={(-1000 - g * 60) * Math.cos(Math.PI / 6)} y1={(-1000 + g * 60) * Math.sin(Math.PI / 6)}
                  x2={(1000 - g * 60) * Math.cos(Math.PI / 6)} y2={(1000 + g * 60) * Math.sin(Math.PI / 6)}
                  stroke="#b8c3d3" strokeWidth={0.5}
                />
              </g>
            );
          })}
        </g>

        {/* A ring of buildings (sorted so far ones draw first) */}
        {[
          { x: -260, y: -120, w: 110, h: 150, d: 22 },
          { x: -180, y: -300, w: 90,  h: 220, d: 18 },
          { x:  -60, y: -240, w: 120, h: 260, d: 22 },
          { x:  100, y: -280, w: 110, h: 190, d: 20 },
          { x:  220, y: -140, w: 120, h: 160, d: 22 },
          { x:  200, y:   80, w: 90,  h: 130, d: 18 },
          { x:   80, y:  160, w: 110, h: 140, d: 20 },
          { x:  -80, y:  200, w: 100, h: 120, d: 18 },
          { x: -220, y:  100, w: 120, h: 170, d: 20 },
          { x: -360, y:    0, w: 100, h: 200, d: 20 },
        ].sort((a, b) => (a.x + a.y) - (b.x + b.y)).map((b, i) => (
          <IsoBuilding key={i} {...b} delay={10 + i * 4} />
        ))}

        {/* Central hub at origin */}
        <CentralHub x={0} y={0} delay={80} />

        {/* Call arcs fired from buildings toward hub */}
        {[
          { from: [-260, -120], delay: 110 },
          { from: [-180, -300], delay: 140 },
          { from: [-60,  -240], delay: 170 },
          { from: [100,  -280], delay: 200 },
          { from: [220,  -140], delay: 230 },
          { from: [200,    80], delay: 260 },
          { from: [80,    160], delay: 290 },
          { from: [-80,   200], delay: 320 },
          { from: [-220,  100], delay: 350 },
          { from: [-360,    0], delay: 380 },
        ].map((c, i) => {
          const iso = (px: number, py: number) => ({
            x: (px - py) * Math.cos(Math.PI / 6),
            y: (px + py) * Math.sin(Math.PI / 6),
          });
          const start = iso(c.from[0] + 50, c.from[1] + 20);
          return (
            <CallArc key={i}
              x1={start.x} y1={start.y - 40}
              x2={0} y2={-20}
              delay={c.delay}
              color={i % 2 === 0 ? P.brand : P.accent}
            />
          );
        })}
      </svg>

      {/* Bottom KPI pill */}
      <div style={{ position: "absolute", bottom: 52, left: 80, display: "flex", gap: 24, alignItems: "center" }}>
        <Enter delay={380}>
          <div style={{
            background: "#fff", borderRadius: 14, padding: "14px 22px",
            boxShadow: `0 20px 40px ${P.studioShadow}`,
            display: "flex", alignItems: "center", gap: 24,
          }}>
            <div>
              <div style={{ fontSize: 12, color: P.muted, letterSpacing: 2, textTransform: "uppercase" }}>Answered today</div>
              <div style={{ fontSize: 36, fontWeight: 800, color: P.ink, fontFamily: SANS, fontVariantNumeric: "tabular-nums" }}>
                {Math.min(Math.floor(interpolate(f, [100, 420], [0, 1284])), 1284).toLocaleString()}
              </div>
            </div>
            <div style={{ width: 1, height: 40, background: "#e1e4ea" }} />
            <div>
              <div style={{ fontSize: 12, color: P.muted, letterSpacing: 2, textTransform: "uppercase" }}>Missed</div>
              <div style={{ fontSize: 36, fontWeight: 800, color: P.green, fontFamily: SANS, fontVariantNumeric: "tabular-nums" }}>
                0
              </div>
            </div>
          </div>
        </Enter>
      </div>
      <div style={{ position: "absolute", bottom: 60, right: 80, textAlign: "right" }}>
        <Enter delay={400}><Wordmark size={24} /></Enter>
        <Enter delay={410} style={{ marginTop: 6 }}>
          <span style={{ fontFamily: MONO, fontSize: 14, color: P.muted }}>bookedforyou.ie</span>
        </Enter>
      </div>
    </AbsoluteFill>
  );
};


// ──────────────────────────────────────────────────────────
//  VIDEO 4 — MacApp_Cursor
//  Photoreal macOS window, animated cursor navigating the UI.
// ──────────────────────────────────────────────────────────

const MacChrome: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <div style={{
    width: 1500, height: 880, borderRadius: 14, overflow: "hidden",
    background: "#fff",
    boxShadow: `0 50px 120px rgba(11,15,26,0.35), 0 8px 24px rgba(11,15,26,0.18)`,
    border: `1px solid rgba(11,15,26,0.08)`,
  }}>
    <div style={{
      height: 40, background: "linear-gradient(180deg,#f4f5f7,#e5e7eb)",
      borderBottom: "1px solid #d9dde3",
      display: "flex", alignItems: "center", padding: "0 14px", gap: 8,
    }}>
      <span style={{ width: 12, height: 12, borderRadius: "50%", background: "#ff5f57" }} />
      <span style={{ width: 12, height: 12, borderRadius: "50%", background: "#febc2e" }} />
      <span style={{ width: 12, height: 12, borderRadius: "50%", background: "#28c840" }} />
      <span style={{ flex: 1, textAlign: "center", fontFamily: SANS, fontSize: 13, color: "#4b5563", fontWeight: 600 }}>
        {title}
      </span>
      <span style={{ width: 58 }} />
    </div>
    <div style={{ height: 840, background: "#fafbfd", position: "relative" }}>
      {children}
    </div>
  </div>
);

/** cursor with click ripple */
const Cursor: React.FC<{ path: Array<{ x: number; y: number; hold?: number; click?: boolean }> }> = ({ path }) => {
  const f = useCurrentFrame();
  // build timeline
  let t = 0;
  const waypoints: Array<{ x: number; y: number; start: number; end: number; click: boolean }> = [];
  for (let i = 0; i < path.length - 1; i++) {
    const a = path[i], b = path[i + 1];
    const moveLen = 18;
    waypoints.push({ x: a.x, y: a.y, start: t, end: t + moveLen, click: !!a.click });
    t += moveLen + (a.hold ?? 0);
    if (i === path.length - 2) {
      waypoints.push({ x: b.x, y: b.y, start: t, end: t, click: !!b.click });
    }
  }
  // interpolate position
  let cx = path[0].x, cy = path[0].y;
  for (let i = 0; i < waypoints.length - 1; i++) {
    const a = waypoints[i], b = waypoints[i + 1];
    if (f >= a.start && f <= b.start) {
      const p = interpolate(f, [a.start, b.start], [0, 1],
        { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.inOut(Easing.cubic) });
      cx = a.x + (b.x - a.x) * p;
      cy = a.y + (b.y - a.y) * p;
    } else if (f > b.start) {
      cx = b.x; cy = b.y;
    }
  }
  // click ripples
  const clickMoments = waypoints.filter((w) => w.click);
  return (
    <>
      {clickMoments.map((c, i) => {
        const rp = interpolate(f - c.start, [0, 20], [0, 1],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
        const op = interpolate(f - c.start, [0, 6, 20], [0, 0.8, 0],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        return (
          <div key={i} style={{
            position: "absolute", left: c.x, top: c.y,
            transform: `translate(-50%,-50%) scale(${rp * 2.6})`,
            width: 32, height: 32, borderRadius: "50%",
            border: `3px solid ${P.brand}`,
            opacity: op, pointerEvents: "none",
          }} />
        );
      })}
      {/* cursor SVG */}
      <svg width={24} height={28} viewBox="0 0 24 28"
        style={{ position: "absolute", left: cx, top: cy, transform: "translate(-2px,-2px)", filter: "drop-shadow(0 2px 4px rgba(0,0,0,0.25))" }}>
        <path d="M2 2 L2 22 L8 16 L12 24 L15 22 L11 14 L20 14 Z" fill="#fff" stroke="#000" strokeWidth={1.5} strokeLinejoin="round" />
      </svg>
    </>
  );
};

const AppSidebar: React.FC<{ active: number }> = ({ active }) => {
  const items = ["Dashboard", "Calls", "Calendar", "Jobs", "CRM", "Invoices", "Settings"];
  return (
    <div style={{ width: 220, height: "100%", background: "#f2f4f8", borderRight: "1px solid #e5e8ee", padding: "20px 12px", fontFamily: SANS }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "4px 10px 18px" }}>
        <div style={{ width: 26, height: 26, borderRadius: 6, background: P.ink, color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: SERIF, fontWeight: 800 }}>B</div>
        <span style={{ fontSize: 14, fontWeight: 700, color: P.ink }}>BookedForYou</span>
      </div>
      {items.map((it, i) => (
        <div key={i} style={{
          padding: "10px 12px", borderRadius: 8, marginBottom: 4,
          background: i === active ? "#fff" : "transparent",
          boxShadow: i === active ? "0 1px 2px rgba(0,0,0,0.06)" : "none",
          color: i === active ? P.ink : "#5c6573",
          fontWeight: i === active ? 700 : 500,
          fontSize: 14,
        }}>
          {it}
        </div>
      ))}
    </div>
  );
};

const StatTile: React.FC<{ label: string; value: string; delta?: string; color?: string }> =
  ({ label, value, delta, color = P.ink }) => (
  <div style={{ background: "#fff", border: "1px solid #e5e8ee", borderRadius: 10, padding: "16px 18px", flex: 1 }}>
    <div style={{ fontSize: 12, color: P.muted, letterSpacing: 1, textTransform: "uppercase" }}>{label}</div>
    <div style={{ fontSize: 30, fontWeight: 800, color, fontVariantNumeric: "tabular-nums" }}>{value}</div>
    {delta && <div style={{ fontSize: 12, color: P.green, fontWeight: 600, marginTop: 2 }}>{delta}</div>}
  </div>
);

/** fake chart */
const MiniBars: React.FC<{ data: number[]; color: string }> = ({ data, color }) => {
  const f = useCurrentFrame();
  const max = Math.max(...data);
  return (
    <div style={{ height: 140, display: "flex", alignItems: "flex-end", gap: 6, padding: "8px 4px" }}>
      {data.map((v, i) => {
        const g = interpolate(f, [20 + i * 2, 40 + i * 2], [0, v / max],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        return <div key={i} style={{ flex: 1, height: `${g * 100}%`, background: color, borderRadius: 3, opacity: 0.85 }} />;
      })}
    </div>
  );
};

const DashboardUI: React.FC<{ highlight?: "cal"|"newjob"|null }> = ({ highlight }) => {
  const f = useCurrentFrame();
  return (
    <div style={{ display: "flex", height: "100%", fontFamily: SANS }}>
      <AppSidebar active={0} />
      <div style={{ flex: 1, padding: "22px 28px", overflow: "hidden" }}>
        {/* Top bar */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18 }}>
          <div>
            <div style={{ fontSize: 22, fontWeight: 800, color: P.ink }}>Good morning, Mike</div>
            <div style={{ fontSize: 13, color: P.muted }}>Thursday · 30 Apr 2026</div>
          </div>
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <div style={{ padding: "8px 14px", background: "#eef3ff", color: P.brand, borderRadius: 8, fontSize: 13, fontWeight: 700 }}>
              AI answering 24/7
            </div>
            <div style={{
              padding: "8px 14px", background: highlight === "newjob" ? P.brand : P.ink, color: "#fff",
              borderRadius: 8, fontSize: 13, fontWeight: 700,
              boxShadow: highlight === "newjob" ? `0 0 0 3px ${P.brand}33` : "none",
            }}>
              + New job
            </div>
          </div>
        </div>
        {/* KPI row */}
        <div style={{ display: "flex", gap: 14, marginBottom: 18 }}>
          <StatTile label="Calls today" value={`${Math.min(Math.floor(interpolate(f, [0, 120], [0, 14])), 14)}`} delta="+22%" color={P.brand} />
          <StatTile label="Jobs booked" value={`${Math.min(Math.floor(interpolate(f, [0, 140], [0, 9])), 9)}`} delta="+4 vs yest" />
          <StatTile label="Revenue (wk)" value={`€${Math.min(Math.floor(interpolate(f, [0, 160], [0, 14280])), 14280).toLocaleString()}`} delta="+€1,920" color={P.green} />
          <StatTile label="Missed" value="0" color={P.green} />
        </div>
        {/* Chart + Calendar preview */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
          <div style={{ background: "#fff", border: "1px solid #e5e8ee", borderRadius: 10, padding: "14px 16px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: P.ink }}>Calls (last 7d)</span>
              <span style={{ fontSize: 12, color: P.muted }}>Auto-refreshing</span>
            </div>
            <MiniBars data={[8, 11, 7, 13, 9, 14, 12]} color={P.brand} />
          </div>
          <div style={{
            background: "#fff", border: `1px solid ${highlight === "cal" ? P.brand : "#e5e8ee"}`,
            borderRadius: 10, padding: "14px 16px",
            boxShadow: highlight === "cal" ? `0 0 0 4px ${P.brand}22` : "none",
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: P.ink }}>Today's schedule</span>
              <span style={{ fontSize: 12, color: P.muted }}>4 jobs · 0 gaps</span>
            </div>
            <div style={{ marginTop: 8 }}>
              {[
                { t: "09:00", n: "Pipe repair · M. Byrne", c: P.brand },
                { t: "10:30", n: "Quote visit · Sarah O'C.", c: P.accent2 },
                { t: "12:00", n: "Emergency · Henry St.", c: "#d9534f" },
                { t: "14:00", n: "Boiler service · D. Nolan", c: P.green },
              ].map((j, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, padding: "7px 0", borderBottom: i < 3 ? "1px solid #f0f2f6" : "none" }}>
                  <span style={{ width: 4, height: 26, background: j.c, borderRadius: 2 }} />
                  <span style={{ fontFamily: MONO, fontSize: 12, color: P.muted, width: 54 }}>{j.t}</span>
                  <span style={{ fontSize: 13, color: P.ink, fontWeight: 500 }}>{j.n}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const Tooltip: React.FC<{ x: number; y: number; text: string; delay: number }> = ({ x, y, text, delay }) => {
  const f = useCurrentFrame();
  const s = spring({ frame: f - delay, fps: 30, config: { damping: 14, mass: 0.3, stiffness: 180 } });
  const op = interpolate(f - delay, [0, 8, 60, 70], [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div style={{
      position: "absolute", left: x, top: y,
      transform: `translate(-50%,-100%) scale(${s})`,
      opacity: op,
      background: P.ink, color: "#fff",
      padding: "8px 14px", borderRadius: 8,
      fontFamily: SANS, fontSize: 13, fontWeight: 600,
      whiteSpace: "nowrap",
      boxShadow: "0 8px 20px rgba(0,0,0,0.25)",
    }}>
      {text}
      <div style={{ position: "absolute", bottom: -5, left: "50%", transform: "translateX(-50%) rotate(45deg)", width: 10, height: 10, background: P.ink }} />
    </div>
  );
};

const Mac_Scene1: React.FC = () => {
  return (
    <AbsoluteFill style={{ background: "linear-gradient(180deg,#e8ecf3 0%,#c8d0dd 100%)", justifyContent: "center", alignItems: "center" }}>
      {/* backdrop dots */}
      <div style={{ position: "absolute", inset: 0, backgroundImage: "radial-gradient(#b8c0cf 1px,transparent 1px)", backgroundSize: "22px 22px", opacity: 0.35 }} />
      <Enter delay={0}>
        <MacChrome title="app.bookedforyou.ie">
          <DashboardUI highlight={null} />
          {/* Cursor scripted moves */}
          <Cursor path={[
            { x: 40,  y: 40, hold: 10 },
            { x: 780, y: 280, hold: 30, click: true },
            { x: 1200, y: 70, hold: 40, click: true },
          ]} />
          <Tooltip x={1210} y={66} text="Click + to log a new job in one shortcut" delay={70} />
        </MacChrome>
      </Enter>
      <div style={{ position: "absolute", top: 60, left: 80 }}>
        <Enter delay={4}>
          <div style={{ fontFamily: SANS, fontSize: 14, color: P.muted, letterSpacing: 2, textTransform: "uppercase", fontWeight: 700 }}>
            Product · The dashboard
          </div>
        </Enter>
        <Enter delay={10} from={30}>
          <h2 style={{ fontFamily: SERIF, fontSize: 58, lineHeight: 1.0, letterSpacing: -2, color: P.ink, margin: "6px 0 0", fontWeight: 700 }}>
            Your business,<br /> in one window.
          </h2>
        </Enter>
      </div>
    </AbsoluteFill>
  );
};

const Mac_Scene2: React.FC = () => {
  return (
    <AbsoluteFill style={{ background: "linear-gradient(180deg,#e8ecf3 0%,#c8d0dd 100%)", justifyContent: "center", alignItems: "center" }}>
      <div style={{ position: "absolute", inset: 0, backgroundImage: "radial-gradient(#b8c0cf 1px,transparent 1px)", backgroundSize: "22px 22px", opacity: 0.35 }} />
      <Enter delay={0}>
        <MacChrome title="app.bookedforyou.ie / calls">
          <div style={{ display: "flex", height: "100%", fontFamily: SANS }}>
            <AppSidebar active={1} />
            <div style={{ flex: 1, padding: "22px 28px" }}>
              <div style={{ fontSize: 22, fontWeight: 800, color: P.ink, marginBottom: 4 }}>Live calls</div>
              <div style={{ fontSize: 13, color: P.muted, marginBottom: 16 }}>
                The AI is on every line. You get the transcript, summary and outcome.
              </div>
              {[
                { t: "09:12", n: "John Murphy", topic: "Pipe repair · booked Thu 10:00", ok: true },
                { t: "09:34", n: "Sarah O'Connor", topic: "Quote: bathroom reno · SMS sent", ok: true },
                { t: "10:02", n: "Henry St. (emergency)", topic: "Booked today 11:00 · owner paged", ok: true },
                { t: "10:45", n: "+353 1 555 ….", topic: "Spam filtered — no action", ok: false },
                { t: "11:12", n: "Dave Nolan", topic: "Boiler service · Fri 14:00", ok: true },
              ].map((r, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", padding: "12px 14px",
                  borderRadius: 10, marginBottom: 8, background: "#fff", border: "1px solid #e5e8ee" }}>
                  <span style={{ width: 10, height: 10, borderRadius: "50%", background: r.ok ? P.green : "#b8bfcb", marginRight: 14 }} />
                  <span style={{ fontFamily: MONO, fontSize: 13, color: P.muted, width: 60 }}>{r.t}</span>
                  <span style={{ fontSize: 14, fontWeight: 700, color: P.ink, width: 220 }}>{r.n}</span>
                  <span style={{ fontSize: 13, color: "#5c6573", flex: 1 }}>{r.topic}</span>
                  <span style={{ fontSize: 12, color: r.ok ? P.green : P.muted, fontWeight: 700, textTransform: "uppercase", letterSpacing: 1 }}>
                    {r.ok ? "Booked" : "Filtered"}
                  </span>
                </div>
              ))}
            </div>
          </div>
          <Cursor path={[
            { x: 600, y: 500, hold: 6 },
            { x: 620, y: 190, hold: 20, click: true },
            { x: 620, y: 260, hold: 20, click: true },
            { x: 620, y: 340, hold: 30 },
          ]} />
          <Tooltip x={620} y={180} text="Every call, transcribed and categorised automatically." delay={50} />
        </MacChrome>
      </Enter>
    </AbsoluteFill>
  );
};

const Mac_Scene3: React.FC = () => (
  <AbsoluteFill style={{ background: "linear-gradient(180deg,#0b1020 0%,#060914 100%)", justifyContent: "center", alignItems: "center" }}>
    <Enter delay={0} from={40}>
      <div style={{ textAlign: "center" }}>
        <div style={{ fontFamily: SANS, fontSize: 14, color: "#9aa4b8", letterSpacing: 3, textTransform: "uppercase", fontWeight: 700, marginBottom: 18 }}>
          Everything runs here ·
        </div>
        <h2 style={{ fontFamily: SERIF, fontSize: 96, lineHeight: 1.0, letterSpacing: -3, color: "#fff", margin: 0, fontWeight: 700 }}>
          One app. Zero missed.
        </h2>
        <Enter delay={22}>
          <div style={{ marginTop: 26, display: "flex", justifyContent: "center", gap: 16, alignItems: "center" }}>
            <div style={{ padding: "14px 26px", background: P.brand, borderRadius: 10, color: "#fff", fontFamily: SANS, fontSize: 18, fontWeight: 700 }}>
              Start free trial
            </div>
            <span style={{ fontFamily: MONO, color: "#9aa4b8", fontSize: 16 }}>bookedforyou.ie</span>
          </div>
        </Enter>
      </div>
    </Enter>
  </AbsoluteFill>
);

export const MacApp_Cursor: React.FC = () => {
  const scenes = [
    { c: Mac_Scene1, d: 260 },
    { c: Mac_Scene2, d: 280 },
    { c: Mac_Scene3, d: 160 },
  ];
  let s = 0;
  return (
    <AbsoluteFill>
      {scenes.map((sc, i) => {
        const from = s; s += sc.d; const Sc = sc.c;
        return (
          <Sequence key={i} from={from} durationInFrames={sc.d}>
            <SceneFade dur={sc.d}><Sc /></SceneFade>
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};

// ──────────────────────────────────────────────────────────
//  VIDEO 5 — Newsroom_Breaking
//  Cable-news chyron + ticker + lower-thirds
// ──────────────────────────────────────────────────────────

const Chyron: React.FC = () => (
  <div style={{
    position: "absolute", left: 0, right: 0, bottom: 120,
    background: "linear-gradient(90deg,#a9121c,#6e0a11)",
    color: "#fff", display: "flex", alignItems: "stretch",
    borderTop: "3px solid #fff",
    boxShadow: "0 -6px 20px rgba(0,0,0,0.3)",
  }}>
    <div style={{ background: "#fff", color: "#a9121c", padding: "0 28px", display: "flex", alignItems: "center", fontFamily: SANS, fontWeight: 900, fontSize: 26, letterSpacing: 2 }}>
      BREAKING
    </div>
    <div style={{ padding: "18px 26px", display: "flex", alignItems: "center", fontFamily: SERIF, fontSize: 36, fontWeight: 700, letterSpacing: -0.5 }}>
      Irish trades are quietly switching receptionists — and nobody's calling back.
    </div>
  </div>
);

const Ticker: React.FC<{ items: string[]; speed?: number }> = ({ items, speed = 120 }) => {
  const f = useCurrentFrame();
  const feed = items.concat(items).concat(items).join("   •   ");
  return (
    <div style={{
      position: "absolute", left: 0, right: 0, bottom: 70, height: 50,
      background: "#0c0c0f", color: "#fff",
      fontFamily: SANS, fontSize: 20, fontWeight: 600, letterSpacing: 0.4,
      display: "flex", alignItems: "center", overflow: "hidden",
      borderTop: "1px solid #2a2d33", borderBottom: "1px solid #2a2d33",
    }}>
      <div style={{ background: "#e1b700", color: "#0c0c0f", fontWeight: 900, padding: "0 18px", alignSelf: "stretch", display: "flex", alignItems: "center", letterSpacing: 2, fontSize: 16 }}>
        LIVE
      </div>
      <div style={{ paddingLeft: 20, whiteSpace: "nowrap", transform: `translateX(${-((f * speed) / 30) % 3000}px)` }}>
        {feed}
      </div>
    </div>
  );
};

const LowerThird: React.FC<{ name: string; title: string; delay: number }> = ({ name, title, delay }) => {
  const f = useCurrentFrame();
  const x = interpolate(f - delay, [0, 16], [-400, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
  const op = interpolate(f - delay, [0, 10], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div style={{
      position: "absolute", left: 60, bottom: 220, opacity: op,
      transform: `translateX(${x}px)`,
      minWidth: 520,
    }}>
      <div style={{ background: "#a9121c", color: "#fff", padding: "10px 22px", fontFamily: SANS, fontWeight: 900, fontSize: 30, letterSpacing: -0.5 }}>
        {name.toUpperCase()}
      </div>
      <div style={{ background: "#fff", color: "#0c0c0f", padding: "8px 22px", fontFamily: SANS, fontSize: 18, fontWeight: 600, letterSpacing: 0.5 }}>
        {title}
      </div>
    </div>
  );
};

const ClockStamp: React.FC = () => {
  const f = useCurrentFrame();
  const min = Math.floor(f / 30) % 60;
  return (
    <div style={{ position: "absolute", top: 22, right: 26, display: "flex", alignItems: "center", gap: 8, color: "#fff", fontFamily: MONO, fontSize: 14 }}>
      <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#e63946", boxShadow: "0 0 10px #e63946", opacity: 0.7 + 0.3 * Math.sin(f * 0.3) }} />
      <span>LIVE</span>
      <span style={{ color: "#b8bfcb" }}>· DUB · 09:{String(min).padStart(2, "0")}</span>
    </div>
  );
};

const NetLogo: React.FC = () => (
  <div style={{
    position: "absolute", top: 18, left: 30,
    fontFamily: SERIF, fontSize: 26, fontWeight: 800, color: "#fff",
    letterSpacing: 1, textShadow: "0 2px 6px rgba(0,0,0,0.4)",
  }}>
    <span style={{ color: "#ffd166" }}>TBN</span>
    <span style={{ color: "#fff", opacity: 0.9, marginLeft: 8, fontSize: 14, fontWeight: 600, letterSpacing: 3, textTransform: "uppercase" }}>
      Trades Business Network
    </span>
  </div>
);

/** Fake studio backdrop with colored "lights" */
const StudioBG: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill>
      <div style={{ width: "100%", height: "100%", background: "linear-gradient(180deg,#10151e 0%,#070a12 100%)" }} />
      {/* soft studio glow */}
      <div style={{
        position: "absolute", top: "40%", left: "50%",
        width: 1400, height: 500, transform: "translate(-50%,-50%)",
        background: `radial-gradient(ellipse at center,
          rgba(230,57,70,0.25) 0%,
          rgba(29,78,137,0.18) 40%,
          transparent 70%)`,
        filter: "blur(40px)",
      }} />
      {/* thin vertical "studio blinds" */}
      {Array.from({ length: 20 }).map((_, i) => (
        <div key={i} style={{
          position: "absolute",
          left: `${(i * 5 + (f * 0.04) % 5)}%`,
          top: 0, bottom: 0, width: 1,
          background: "rgba(255,255,255,0.04)",
        }} />
      ))}
    </AbsoluteFill>
  );
};

/** Big animated stat card like a news graphic */
const NewsStatCard: React.FC<{ big: string; cap: string; delay: number; x: number; y: number; color: string }> =
  ({ big, cap, delay, x, y, color }) => {
    const f = useCurrentFrame();
    const s = spring({ frame: f - delay, fps: 30, config: { damping: 13, mass: 0.5, stiffness: 140 } });
    const op = interpolate(f - delay, [0, 10], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    return (
      <div style={{
        position: "absolute", left: x, top: y, opacity: op,
        transform: `translateY(${(1 - s) * 40}px) scale(${0.8 + s * 0.2})`,
        width: 380,
        background: "linear-gradient(180deg,rgba(255,255,255,0.08),rgba(255,255,255,0.02))",
        border: "1px solid rgba(255,255,255,0.18)",
        borderLeft: `6px solid ${color}`,
        padding: "22px 26px", backdropFilter: "blur(10px)",
      }}>
        <div style={{ fontFamily: SERIF, fontSize: 76, lineHeight: 1, letterSpacing: -2, color: "#fff", fontWeight: 700 }}>
          {big}
        </div>
        <div style={{ fontFamily: SANS, fontSize: 16, color: "#dde3ec", marginTop: 8, letterSpacing: 0.4 }}>
          {cap}
        </div>
      </div>
    );
  };

const News_Scene1: React.FC = () => (
  <AbsoluteFill>
    <StudioBG />
    <NetLogo />
    <ClockStamp />
    {/* Big "breaking" slash */}
    <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <Enter delay={4} from={80}>
        <div style={{ textAlign: "center" }}>
          <div style={{ display: "inline-block", background: "#a9121c", color: "#fff", padding: "10px 28px", fontFamily: SANS, fontSize: 22, fontWeight: 900, letterSpacing: 6, borderRadius: 4 }}>
            BREAKING NEWS
          </div>
          <h1 style={{ fontFamily: SERIF, fontSize: 112, lineHeight: 1.0, letterSpacing: -3, color: "#fff", margin: "28px 0 0", fontWeight: 700 }}>
            Tradespeople across<br/>Ireland just… stopped<br/>missing&nbsp;calls.
          </h1>
        </div>
      </Enter>
    </div>
    <Ticker items={[
      "BookedForYou reports 47 mins saved per operator per day",
      "Missed calls down 100% for AI-enabled trades",
      "Average trade recovers €78k/yr previously lost to voicemail",
      "Trial signups up across Dublin, Cork, Galway this week",
    ]} />
    <Chyron />
  </AbsoluteFill>
);

const News_Scene2: React.FC = () => (
  <AbsoluteFill>
    <StudioBG />
    <NetLogo />
    <ClockStamp />
    <NewsStatCard x={120} y={140}  big="100%"   cap="of inbound calls answered · first ring" delay={6}   color="#ffd166" />
    <NewsStatCard x={520} y={240}  big="0.8s"   cap="average AI response time · field tested" delay={22}  color="#2a9d8f" />
    <NewsStatCard x={920} y={160}  big="€78k"   cap="recovered per year · median trades operator" delay={38}  color="#e63946" />
    <NewsStatCard x={340} y={480}  big="312"    cap="jobs/year saved from voicemail graveyard" delay={54}  color="#4cc9f0" />
    <NewsStatCard x={820} y={520}  big="24/7"   cap="live · doesn't call in sick, doesn't complain" delay={70}  color="#c77dff" />
    <LowerThird name="Correspondent" title="Field report · trades sector · Dublin-Cork corridor" delay={20} />
    <Ticker items={[
      "Emergency callouts auto-booked and dispatched in under 90 seconds",
      "Owners report full nights of sleep for first time in years",
      "Finance teams flag unexpected line item: 'refunded weekends'",
    ]} />
    <Chyron />
  </AbsoluteFill>
);

const News_Scene3: React.FC = () => (
  <AbsoluteFill>
    <StudioBG />
    <NetLogo />
    <ClockStamp />
    <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", padding: "0 80px" }}>
      <Enter delay={0} from={40}>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontFamily: SANS, fontSize: 16, color: "#ffd166", letterSpacing: 4, fontWeight: 700, textTransform: "uppercase" }}>
            Developing story ·
          </div>
          <h1 style={{ fontFamily: SERIF, fontSize: 100, letterSpacing: -3, color: "#fff", margin: "14px 0 0", lineHeight: 1.0, fontWeight: 700 }}>
            Hand the phone over.<br />
            <span style={{ color: "#ffd166" }}>Before your competitor does.</span>
          </h1>
          <Enter delay={30} style={{ marginTop: 36 }}>
            <div style={{ display: "flex", justifyContent: "center", gap: 18, alignItems: "center" }}>
              <div style={{ padding: "16px 30px", background: "#fff", color: "#0c0c0f", fontFamily: SANS, fontWeight: 800, fontSize: 20, borderRadius: 6 }}>
                Start 14-day trial
              </div>
              <span style={{ color: "#cdd4de", fontFamily: MONO, fontSize: 18 }}>bookedforyou.ie</span>
            </div>
          </Enter>
        </div>
      </Enter>
    </div>
    <Ticker items={[
      "This is a paid message from BookedForYou",
      "No credit card · cancel anytime · your calendar stays yours",
      "Built in Dublin for trades, salons, restaurants, clinics",
    ]} />
  </AbsoluteFill>
);

export const Newsroom_Breaking: React.FC = () => {
  const scenes = [
    { c: News_Scene1, d: 200 },
    { c: News_Scene2, d: 260 },
    { c: News_Scene3, d: 200 },
  ];
  let s = 0;
  return (
    <AbsoluteFill>
      {scenes.map((sc, i) => {
        const from = s; s += sc.d; const Sc = sc.c;
        return (
          <Sequence key={i} from={from} durationInFrames={sc.d}>
            <SceneFade dur={sc.d}><Sc /></SceneFade>
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
