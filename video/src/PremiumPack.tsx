/**
 * PremiumPack — five vertical (1080x1920) marketing videos with
 * visual languages explicitly *not* reused from SocialPack*.tsx.
 *
 * 1. Kinetic_Typography     — word-by-word rhythmic color fields
 * 2. Voicemail_LiveTrans    — iOS-style voicemail / live AI transcription
 * 3. Noir_Split             — cinematic split-screen call (owner ↔ AI)
 * 4. Whiteboard_Annotated   — hand-drawn marker annotations on mockups
 * 5. Liquid_Blob_Close      — morphing liquid-gradient close card
 */

import {
  AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate, Sequence, Easing,
} from "remotion";
import React from "react";

// Shared palette for this pack — intentionally different from SocialPack.
const PC = {
  inkDark:  "#0b0b0e",
  paper:    "#faf6ef",
  cream:    "#f1ead8",
  coral:    "#ff5a3c",
  mint:     "#2ed3a0",
  violet:   "#6d4bff",
  yolk:     "#ffc640",
  navy:     "#0b1f44",
  steel:    "#b0b7c3",
  muted:    "#5b5e66",
  amber:    "#f59e0b",
  iosBlue:  "#007aff",
  iosGrey:  "#8e8e93",
  iosBgTop: "#1a1b20",
};
const DISPLAY = "'Inter','Helvetica Neue',Helvetica,Arial,sans-serif";
const SERIF   = "'Times New Roman','Times',Georgia,serif";
const MONO    = "'SF Mono','JetBrains Mono',Menlo,Consolas,monospace";

// ─── helpers (local) ───────────────────────────────────────

const SceneFade: React.FC<{ children: React.ReactNode; dur: number; hold?: number }> =
  ({ children, dur, hold = 8 }) => {
    const f = useCurrentFrame();
    const op = interpolate(f, [0, hold, dur - hold, dur], [0, 1, 1, 0],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    return <AbsoluteFill style={{ opacity: op }}>{children}</AbsoluteFill>;
  };

const Rise: React.FC<{ children: React.ReactNode; delay?: number; from?: number; dur?: number; style?: React.CSSProperties }> =
  ({ children, delay = 0, from = 30, dur = 14, style }) => {
    const f = useCurrentFrame();
    const p = interpolate(f - delay, [0, dur], [0, 1],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
    return (
      <div style={{ opacity: p, transform: `translateY(${(1 - p) * from}px)`, ...style }}>
        {children}
      </div>
    );
  };

const Mark: React.FC<{ size?: number; dark?: boolean; color?: string }> = ({ size = 42, dark, color }) => (
  <div style={{ display: "flex", alignItems: "center", gap: 10, fontFamily: DISPLAY }}>
    <div style={{
      width: size, height: size, borderRadius: size * 0.24,
      background: color ?? (dark ? "#fff" : PC.inkDark),
      color: color ? "#fff" : (dark ? PC.inkDark : "#fff"),
      display: "flex", alignItems: "center", justifyContent: "center",
      fontFamily: SERIF, fontWeight: 800, fontSize: size * 0.58,
    }}>B</div>
    <span style={{ fontSize: size * 0.6, fontWeight: 800, letterSpacing: -0.4, color: dark ? "#fff" : PC.inkDark }}>
      BookedForYou
    </span>
  </div>
);

// ═══════════════════════════════════════════════════════════
//  VIDEO 1 — Kinetic Typography
//  Rhythmic full-bleed color fields, giant set-type
// ═══════════════════════════════════════════════════════════

const Beat: React.FC<{
  bg: string; fg: string; children: React.ReactNode;
  from: number; dur: number;
}> = ({ bg, fg, children, from, dur }) => {
  const f = useCurrentFrame();
  const show = f >= from && f <= from + dur;
  const op = interpolate(f, [from, from + 3, from + dur - 3, from + dur], [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  if (!show) return null;
  return (
    <AbsoluteFill style={{ background: bg, color: fg, opacity: op, display: "flex", alignItems: "center", justifyContent: "center", padding: "0 60px", fontFamily: DISPLAY }}>
      {children}
    </AbsoluteFill>
  );
};

const Word: React.FC<{
  text: string; from: number; dur: number;
  size?: number; color?: string;
  align?: "left" | "center" | "right";
  italic?: boolean; serif?: boolean;
  x?: number; y?: number; rotate?: number;
}> = ({ text, from, dur, size = 180, color = PC.inkDark, align = "center", italic, serif, x = 0, y = 0, rotate = 0 }) => {
  const f = useCurrentFrame();
  const inWin = f >= from && f <= from + dur;
  if (!inWin) return null;
  const p = interpolate(f - from, [0, 5], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const o = interpolate(f - from, [0, 3, dur - 4, dur], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div style={{
      position: "absolute", inset: 0,
      display: "flex", alignItems: "center",
      justifyContent: align === "left" ? "flex-start" : align === "right" ? "flex-end" : "center",
      padding: "0 60px",
    }}>
      <span style={{
        fontFamily: serif ? SERIF : DISPLAY,
        fontSize: size, fontWeight: serif ? 700 : 900,
        letterSpacing: -6, lineHeight: 0.92,
        color, opacity: o,
        fontStyle: italic ? "italic" : "normal",
        transform: `translate(${x}px, ${y + (1 - p) * 28}px) rotate(${rotate}deg)`,
        textAlign: align, whiteSpace: "pre-wrap",
      }}>
        {text}
      </span>
    </div>
  );
};

const StrikeLine: React.FC<{ from: number; color?: string; y?: number }> = ({ from, color = PC.coral, y = 900 }) => {
  const f = useCurrentFrame();
  const p = interpolate(f - from, [0, 8], [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
  return (
    <svg width="100%" height="40" viewBox="0 0 1080 40"
      style={{ position: "absolute", left: 0, top: y, pointerEvents: "none" }}>
      <line x1="80" y1="20" x2={80 + (1080 - 160) * p} y2="20"
        stroke={color} strokeWidth="14" strokeLinecap="round" />
    </svg>
  );
};

export const Kinetic_Typography: React.FC = () => {
  // Timeline (frames, 30fps). Total ~12s => 360 frames
  const blocks: Array<{ bg: string; fg: string; from: number; dur: number; body: React.ReactNode }> = [
    {
      bg: PC.paper, fg: PC.inkDark, from: 0, dur: 70,
      body: (
        <>
          <Word text="YOU"      from={2}  dur={20} size={340} color={PC.inkDark} />
          <Word text="CAN'T"    from={22} dur={20} size={340} color={PC.coral} italic serif />
          <Word text="ANSWER"   from={42} dur={26} size={260} color={PC.inkDark} />
        </>
      ),
    },
    {
      bg: PC.inkDark, fg: PC.paper, from: 70, dur: 60,
      body: (
        <>
          <Word text="EVERY"   from={72} dur={20} size={320} color={PC.yolk} />
          <Word text="SINGLE" from={92} dur={20} size={320} color={PC.paper} />
          <Word text="CALL."  from={112} dur={18} size={360} color={PC.paper} />
        </>
      ),
    },
    {
      bg: PC.coral, fg: "#fff", from: 130, dur: 52,
      body: (
        <>
          <Word text="VOICEMAIL" from={132} dur={48} size={230} color="#fff" serif italic />
          <StrikeLine from={152} color={PC.inkDark} y={1080} />
          <Word text="IS THE" from={166} dur={16} size={110} color="#fff" y={260} />
          <Word text="PROBLEM" from={168} dur={20} size={170} color="#fff" y={400} />
        </>
      ),
    },
    {
      bg: PC.cream, fg: PC.inkDark, from: 182, dur: 60,
      body: (
        <>
          <Word text="WE" from={184} dur={16} size={400} color={PC.violet} />
          <Word text="BUILT" from={200} dur={16} size={320} color={PC.inkDark} />
          <Word text="A VOICE" from={216} dur={16} size={240} color={PC.inkDark} y={-80} />
          <Word text="FOR IT." from={218} dur={20} size={260} color={PC.coral} y={140} serif italic />
        </>
      ),
    },
    {
      bg: PC.navy, fg: "#fff", from: 242, dur: 60,
      body: (
        <>
          <Word text="ANSWERS" from={244} dur={18} size={260} color={PC.mint} />
          <Word text="BOOKS"   from={262} dur={18} size={260} color={PC.yolk} />
          <Word text="TEXTS"   from={280} dur={18} size={260} color="#fff" />
          <Word text="SLEEPS NEVER." from={298} dur={16} size={120} color={PC.steel} y={280} italic serif />
        </>
      ),
    },
    {
      bg: PC.paper, fg: PC.inkDark, from: 302, dur: 58,
      body: (
        <div style={{ textAlign: "center", width: "100%" }}>
          <Rise delay={306 - 302}>
            <div style={{ fontFamily: SERIF, fontStyle: "italic", fontSize: 80, color: PC.muted, letterSpacing: -1 }}>
              it's called
            </div>
          </Rise>
          <Rise delay={312 - 302} from={50}>
            <div style={{ fontFamily: DISPLAY, fontSize: 160, color: PC.inkDark, fontWeight: 900, letterSpacing: -6, lineHeight: 1, marginTop: 14 }}>
              BookedForYou
            </div>
          </Rise>
          <Rise delay={330 - 302}>
            <div style={{ marginTop: 36, fontFamily: DISPLAY, fontSize: 34, color: PC.inkDark, fontWeight: 600 }}>
              Start free at <span style={{ color: PC.coral }}>bookedforyou.ie</span>
            </div>
          </Rise>
        </div>
      ),
    },
  ];
  return (
    <AbsoluteFill style={{ fontFamily: DISPLAY }}>
      {blocks.map((b, i) => (
        <Beat key={i} bg={b.bg} fg={b.fg} from={b.from} dur={b.dur}>{b.body}</Beat>
      ))}
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════════════
//  VIDEO 2 — Voicemail / Live AI Transcription (iOS style)
// ═══════════════════════════════════════════════════════════

const IOStatusBar: React.FC<{ dark?: boolean }> = ({ dark }) => {
  const color = dark ? "#fff" : PC.inkDark;
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "16px 42px 0", fontFamily: DISPLAY, fontSize: 26, fontWeight: 700, color }}>
      <span>9:41</span>
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <svg width="28" height="14" viewBox="0 0 28 14"><path d="M2 12 L4 9 M7 12 L10 6 M13 12 L17 3 M20 12 L25 0" stroke={color} strokeWidth={2.5} strokeLinecap="round" fill="none" /></svg>
        <span style={{ fontSize: 20, fontWeight: 700 }}>LTE</span>
        <svg width="38" height="18" viewBox="0 0 38 18"><rect x="1" y="2" width="30" height="14" rx="3" stroke={color} fill="none" strokeWidth={1.5} /><rect x="3" y="4" width="24" height="10" fill={color} /><rect x="32" y="6" width="3" height="6" fill={color} /></svg>
      </div>
    </div>
  );
};

const WaveBars: React.FC<{ count?: number; color?: string; activeUntil?: number }> =
  ({ count = 50, color = PC.iosBlue, activeUntil = 9999 }) => {
    const f = useCurrentFrame();
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 3, height: 70 }}>
        {Array.from({ length: count }).map((_, i) => {
          const phase = i * 0.4 + f * 0.2;
          const amp = f < activeUntil ? 0.35 + 0.65 * Math.abs(Math.sin(phase * 1.2) * Math.cos(phase * 0.7)) : 0.05;
          return <div key={i} style={{ width: 4, height: 70 * amp, background: color, borderRadius: 2, opacity: 0.9 }} />;
        })}
      </div>
    );
  };

const V2_Scene1: React.FC = () => {
  const f = useCurrentFrame();
  const ringShake = Math.sin(f * 1.4) * 4;
  return (
    <AbsoluteFill style={{ background: "linear-gradient(180deg,#0a0b12,#02030a)", fontFamily: DISPLAY }}>
      {/* City lights backdrop */}
      {Array.from({ length: 60 }).map((_, i) => {
        const s = (i * 71) % 1080, t = (i * 43) % 1920;
        return <div key={i} style={{ position: "absolute", left: s, top: t, width: 2, height: 2, background: i % 3 === 0 ? "#ffd166" : "#9ec6ff", borderRadius: "50%", opacity: 0.3 + (i % 4) * 0.1 }} />;
      })}
      <IOStatusBar dark />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "0 60px" }}>
        <Rise delay={2}>
          <div style={{ fontSize: 32, color: PC.iosGrey, letterSpacing: 1, marginBottom: 16, fontWeight: 600 }}>incoming call · 02:14 AM</div>
        </Rise>
        <Rise delay={6} from={40}>
          <div style={{
            width: 340, height: 340, borderRadius: "50%",
            background: "linear-gradient(135deg,#2a2d35,#0f1116)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontFamily: DISPLAY, fontSize: 140, fontWeight: 800, color: "#fff",
            border: "3px solid rgba(255,255,255,0.1)",
            transform: `rotate(${ringShake}deg) scale(${1 + Math.abs(Math.sin(f * 0.2)) * 0.02})`,
            boxShadow: "0 0 80px rgba(255,90,60,0.25)",
          }}>
            M
          </div>
        </Rise>
        <Rise delay={18}>
          <div style={{ fontSize: 64, color: "#fff", fontWeight: 700, marginTop: 28, letterSpacing: -1 }}>Maria&nbsp;J.</div>
        </Rise>
        <Rise delay={24}>
          <div style={{ fontSize: 28, color: PC.iosGrey, marginTop: 4 }}>mobile · unknown number</div>
        </Rise>
        <Rise delay={32} style={{ marginTop: 80 }}>
          <div style={{ display: "flex", gap: 80 }}>
            <div style={{ width: 140, height: 140, borderRadius: "50%", background: "#ff3b30", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 60, color: "#fff" }}>✕</div>
            <div style={{ width: 140, height: 140, borderRadius: "50%", background: PC.mint, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 60, color: "#fff" }}>✓</div>
          </div>
        </Rise>
        <Rise delay={46}>
          <div style={{ marginTop: 50, padding: "12px 28px", borderRadius: 20, background: "rgba(45,211,160,0.12)", border: "1px solid rgba(45,211,160,0.4)", color: PC.mint, fontWeight: 700, fontSize: 28, letterSpacing: 0.5 }}>
            Auto-answered by your AI
          </div>
        </Rise>
      </div>
    </AbsoluteFill>
  );
};

/** live transcription line reveal typed char-by-char */
const LiveLine: React.FC<{ who: "caller" | "ai"; text: string; delay: number; cps?: number }> =
  ({ who, text, delay, cps = 42 }) => {
    const f = useCurrentFrame();
    const { fps } = useVideoConfig();
    const n = Math.max(0, Math.min(text.length, Math.floor(((f - delay) / fps) * cps)));
    const appear = interpolate(f - delay, [0, 10], [0, 1],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    return (
      <div style={{
        opacity: appear,
        transform: `translateY(${(1 - appear) * 20}px)`,
        alignSelf: who === "ai" ? "flex-start" : "flex-end",
        maxWidth: "82%", marginBottom: 18,
      }}>
        <div style={{ fontSize: 22, fontWeight: 700, color: who === "ai" ? PC.mint : PC.iosBlue, marginBottom: 6, letterSpacing: 1, textTransform: "uppercase" }}>
          {who === "ai" ? "BookedForYou AI" : "Maria · caller"}
        </div>
        <div style={{
          background: who === "ai" ? "rgba(45,211,160,0.12)" : "rgba(0,122,255,0.12)",
          border: `1px solid ${who === "ai" ? "rgba(45,211,160,0.4)" : "rgba(0,122,255,0.4)"}`,
          borderRadius: 22, padding: "18px 24px",
          color: "#fff", fontSize: 32, lineHeight: 1.35, fontWeight: 500,
        }}>
          {text.slice(0, n)}
          {n < text.length && <span style={{ display: "inline-block", width: 3, height: 26, background: "#fff", marginLeft: 2, verticalAlign: "middle", opacity: Math.floor(f / 8) % 2 }} />}
        </div>
      </div>
    );
  };

const V2_Scene2: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: "linear-gradient(180deg,#0a0b12,#02030a)", fontFamily: DISPLAY }}>
      <IOStatusBar dark />
      <div style={{ padding: "20px 42px 0" }}>
        <Rise delay={2}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div>
              <div style={{ fontSize: 30, fontWeight: 700, color: "#fff" }}>Maria J.</div>
              <div style={{ fontSize: 22, color: PC.iosGrey }}>on call · 00:14</div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ width: 10, height: 10, borderRadius: "50%", background: PC.mint, boxShadow: `0 0 10px ${PC.mint}`, opacity: 0.6 + 0.4 * Math.sin(f * 0.3) }} />
              <span style={{ color: PC.mint, fontWeight: 700, fontSize: 22 }}>LIVE · AI HANDLING</span>
            </div>
          </div>
        </Rise>
        <Rise delay={8} style={{ marginTop: 18, display: "flex", justifyContent: "center" }}>
          <WaveBars color={PC.mint} />
        </Rise>
      </div>
      <div style={{ flex: 1, padding: "40px 42px 30px", display: "flex", flexDirection: "column", overflow: "hidden" }}>
        <LiveLine who="caller" delay={20}  text="Hi, my kitchen sink is leaking and I need someone tonight if possible." />
        <LiveLine who="ai"     delay={80}  text="I can book you. Earliest emergency slot is 11:30 PM tonight — shall I confirm?" />
        <LiveLine who="caller" delay={150} text="Yes please, that's brilliant. 12 Ashfield Road, Dublin 6." />
        <LiveLine who="ai"     delay={210} text="Confirmed. Technician Mike is on the way. You'll get an SMS in 30 seconds." />
      </div>
      <div style={{ padding: "20px 42px 50px" }}>
        <Rise delay={260}>
          <div style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 20, padding: "18px 22px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <div style={{ fontSize: 20, color: PC.iosGrey, letterSpacing: 1, textTransform: "uppercase" }}>Outcome</div>
              <div style={{ fontSize: 30, color: "#fff", fontWeight: 700, marginTop: 2 }}>Emergency booked · €320 · 23:30</div>
            </div>
            <div style={{ padding: "10px 18px", borderRadius: 12, background: PC.mint, color: PC.inkDark, fontWeight: 800, fontSize: 20 }}>
              ✓ Saved
            </div>
          </div>
        </Rise>
      </div>
    </AbsoluteFill>
  );
};

const V2_Scene3: React.FC = () => (
  <AbsoluteFill style={{ background: PC.paper, justifyContent: "center", alignItems: "center", padding: "0 60px", fontFamily: DISPLAY }}>
    <Rise delay={0}>
      <div style={{ fontSize: 28, color: PC.muted, letterSpacing: 4, textTransform: "uppercase", fontWeight: 700 }}>
        At 2:14 AM, while you slept
      </div>
    </Rise>
    <Rise delay={10} from={40}>
      <div style={{ fontSize: 130, fontWeight: 900, color: PC.inkDark, letterSpacing: -6, lineHeight: 0.95, textAlign: "center", marginTop: 18 }}>
        one more job<br/>just got&nbsp;saved.
      </div>
    </Rise>
    <Rise delay={34} style={{ marginTop: 40 }}>
      <Mark size={46} />
    </Rise>
    <Rise delay={44} style={{ marginTop: 14 }}>
      <div style={{ fontSize: 28, color: PC.muted }}>Free 14-day trial · bookedforyou.ie</div>
    </Rise>
  </AbsoluteFill>
);

export const Voicemail_LiveTrans: React.FC = () => {
  const scenes = [
    { c: V2_Scene1, d: 180 },
    { c: V2_Scene2, d: 320 },
    { c: V2_Scene3, d: 150 },
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


// ═══════════════════════════════════════════════════════════
//  VIDEO 3 — Noir_Split
//  Cinematic split-screen phone call, subtitle captions
// ═══════════════════════════════════════════════════════════

const Vignette: React.FC<{ strength?: number }> = ({ strength = 0.6 }) => (
  <AbsoluteFill style={{ pointerEvents: "none", background: `radial-gradient(ellipse at center, rgba(0,0,0,0) 40%, rgba(0,0,0,${strength}) 100%)` }} />
);

const FilmGrain: React.FC<{ opacity?: number }> = ({ opacity = 0.3 }) => {
  const f = useCurrentFrame();
  return (
    <svg width="100%" height="100%" style={{ position: "absolute", inset: 0, opacity, mixBlendMode: "overlay", pointerEvents: "none" }}>
      <filter id="grainP">
        <feTurbulence type="fractalNoise" baseFrequency={1.2} seed={f % 12} />
        <feColorMatrix values="0 0 0 0 0.5  0 0 0 0 0.5  0 0 0 0 0.5  0 0 0 0.8 0" />
      </filter>
      <rect width="100%" height="100%" filter="url(#grainP)" />
    </svg>
  );
};

/** Subtitle track at bottom */
const Subtitle: React.FC<{ text: string; from: number; dur: number; speaker?: string; color?: string }> =
  ({ text, from, dur, speaker, color = "#fff" }) => {
    const f = useCurrentFrame();
    if (f < from || f > from + dur) return null;
    const op = interpolate(f - from, [0, 6, dur - 6, dur], [0, 1, 1, 0],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    return (
      <div style={{
        position: "absolute", left: 80, right: 80, bottom: 120,
        textAlign: "center", opacity: op,
        textShadow: "0 3px 10px rgba(0,0,0,0.9)",
      }}>
        {speaker && <div style={{ fontFamily: DISPLAY, fontSize: 22, fontWeight: 700, letterSpacing: 3, color: PC.yolk, marginBottom: 8, textTransform: "uppercase" }}>
          {speaker}
        </div>}
        <div style={{ fontFamily: SERIF, fontStyle: "italic", fontSize: 42, fontWeight: 500, color, lineHeight: 1.2, letterSpacing: -0.3 }}>
          {text}
        </div>
      </div>
    );
  };

/** half-screen scene with tint */
const NoirHalf: React.FC<{
  tint: string; shadow: string; label: string; caption: string;
  emoji: React.ReactNode; dim?: boolean; breathe?: boolean;
}> = ({ tint, shadow, label, caption, emoji, dim, breathe }) => {
  const f = useCurrentFrame();
  const b = breathe ? 1 + Math.sin(f * 0.05) * 0.008 : 1;
  return (
    <div style={{
      height: "100%", display: "flex", flexDirection: "column",
      justifyContent: "center", alignItems: "center",
      background: `linear-gradient(180deg, ${tint} 0%, ${shadow} 100%)`,
      position: "relative", overflow: "hidden",
      filter: dim ? "brightness(0.7) saturate(0.8)" : "none",
      transform: `scale(${b})`,
    }}>
      {/* barn-door light shafts */}
      {Array.from({ length: 8 }).map((_, i) => (
        <div key={i} style={{
          position: "absolute", top: -200, bottom: -200,
          left: `${10 + i * 14}%`, width: 2,
          background: "rgba(255,255,255,0.04)",
          transform: "rotate(18deg)",
        }} />
      ))}
      <div style={{ fontSize: 260, lineHeight: 1 }}>{emoji}</div>
      <div style={{ marginTop: 26, fontFamily: DISPLAY, fontSize: 24, color: "rgba(255,255,255,0.7)", letterSpacing: 6, textTransform: "uppercase", fontWeight: 800 }}>
        {label}
      </div>
      <div style={{ marginTop: 6, fontFamily: SERIF, fontStyle: "italic", fontSize: 26, color: "rgba(255,255,255,0.55)" }}>
        {caption}
      </div>
    </div>
  );
};

const V3_Scene1: React.FC = () => (
  <AbsoluteFill>
    {/* title card */}
    <div style={{ height: "100%", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", background: "#060a10", padding: "0 60px" }}>
      <Rise delay={2}>
        <div style={{ fontFamily: DISPLAY, fontSize: 26, letterSpacing: 8, textTransform: "uppercase", color: PC.yolk, fontWeight: 800 }}>
          A short film
        </div>
      </Rise>
      <Rise delay={10} from={40}>
        <div style={{ fontFamily: SERIF, fontSize: 150, color: "#fff", letterSpacing: -5, lineHeight: 0.95, textAlign: "center", marginTop: 28, fontWeight: 700 }}>
          The&nbsp;Call.
        </div>
      </Rise>
      <Rise delay={36}>
        <div style={{ marginTop: 28, fontFamily: SERIF, fontStyle: "italic", fontSize: 32, color: "rgba(255,255,255,0.5)", textAlign: "center", maxWidth: 800 }}>
          A customer in trouble. An owner off the clock.<br />
          And the thing in between.
        </div>
      </Rise>
      <Vignette strength={0.7} />
      <FilmGrain />
    </div>
  </AbsoluteFill>
);

const V3_Scene2: React.FC = () => (
  <AbsoluteFill>
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ flex: 1 }}>
        <NoirHalf
          tint="#101322" shadow="#040610"
          label="Customer · 2:14 AM"
          caption="Their kitchen's flooding."
          emoji="📞" breathe
        />
      </div>
      <div style={{ height: 2, background: "#000" }} />
      <div style={{ flex: 1 }}>
        <NoirHalf
          tint="#3a1c0c" shadow="#130703"
          label="You · asleep"
          caption="You don't hear it."
          emoji="😴" dim
        />
      </div>
    </div>
    <Subtitle text='"Hi, is anyone there? I really need help…"' speaker="Customer" from={6} dur={90} />
    <Subtitle text="ring... ring... ring..." from={100} dur={50} color="rgba(255,255,255,0.6)" />
    <Vignette />
    <FilmGrain />
  </AbsoluteFill>
);

const V3_Scene3: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill>
      <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
        <div style={{ flex: 1 }}>
          <NoirHalf
            tint="#101322" shadow="#040610"
            label="Customer"
            caption="Picks up on the first ring."
            emoji="📞" breathe
          />
        </div>
        <div style={{ height: 2, background: "#000" }} />
        <div style={{ flex: 1, position: "relative", overflow: "hidden" }}>
          <NoirHalf
            tint="#0a3a2c" shadow="#021410"
            label="BookedForYou AI"
            caption="Calm. Awake. Already routing."
            emoji="⬤"
          />
          {/* waveform across the center */}
          <div style={{ position: "absolute", left: 0, right: 0, bottom: 120, display: "flex", justifyContent: "center" }}>
            <div style={{ opacity: interpolate(f, [6, 20], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }}>
              <WaveBars color={PC.mint} count={30} />
            </div>
          </div>
        </div>
      </div>
      <Subtitle text='"Booking you for 7 AM. Tech en route."' speaker="AI" from={10} dur={120} color={PC.mint} />
      <Vignette strength={0.5} />
      <FilmGrain />
    </AbsoluteFill>
  );
};

const V3_Scene4: React.FC = () => (
  <AbsoluteFill style={{ background: "#040610" }}>
    <FilmGrain opacity={0.25} />
    <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "0 60px" }}>
      <Rise delay={0}>
        <div style={{ fontFamily: DISPLAY, fontSize: 24, letterSpacing: 6, color: PC.yolk, fontWeight: 800, textTransform: "uppercase" }}>
          The next morning ·
        </div>
      </Rise>
      <Rise delay={10} from={40}>
        <div style={{ fontFamily: SERIF, fontSize: 130, color: "#fff", letterSpacing: -4, lineHeight: 0.95, textAlign: "center", marginTop: 20, fontWeight: 700 }}>
          You wake up to<br/><span style={{ color: PC.mint }}>a booked job.</span>
        </div>
      </Rise>
      <Rise delay={32} style={{ marginTop: 40 }}>
        <Mark dark size={46} />
      </Rise>
      <Rise delay={42} style={{ marginTop: 14 }}>
        <div style={{ color: "rgba(255,255,255,0.5)", fontSize: 28 }}>bookedforyou.ie · 14-day trial</div>
      </Rise>
    </div>
    <Vignette strength={0.8} />
  </AbsoluteFill>
);

export const Noir_Split: React.FC = () => {
  const scenes = [
    { c: V3_Scene1, d: 130 },
    { c: V3_Scene2, d: 180 },
    { c: V3_Scene3, d: 170 },
    { c: V3_Scene4, d: 140 },
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

// ═══════════════════════════════════════════════════════════
//  VIDEO 4 — Whiteboard_Annotated
//  Clean UI mockups with hand-drawn marker annotations
// ═══════════════════════════════════════════════════════════

/** SVG stroke that draws in over time */
const DrawPath: React.FC<{
  d: string; delay: number; dur?: number; color?: string; width?: number; dash?: string;
}> = ({ d, delay, dur = 30, color = PC.coral, width = 5, dash }) => {
  const f = useCurrentFrame();
  // approximate path length with bounding guesses; set a big number then unhide
  const totalLen = 2000;
  const p = interpolate(f - delay, [0, dur], [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
  return (
    <path d={d} stroke={color} strokeWidth={width} fill="none"
      strokeLinecap="round" strokeLinejoin="round"
      strokeDasharray={dash ?? `${totalLen}`}
      strokeDashoffset={dash ? 0 : totalLen * (1 - p)}
      opacity={dash ? interpolate(f - delay, [0, 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) : 1}
      style={{ filter: "url(#markerRough)" }}
    />
  );
};

/** handwritten-style annotation label */
const Scribble: React.FC<{ x: number; y: number; text: string; delay: number; color?: string; size?: number; rotate?: number }> =
  ({ x, y, text, delay, color = PC.coral, size = 28, rotate = -4 }) => {
    const f = useCurrentFrame();
    const op = interpolate(f - delay, [0, 12], [0, 1],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    return (
      <div style={{
        position: "absolute", left: x, top: y, opacity: op,
        transform: `translate(${(1 - op) * -10}px,0) rotate(${rotate}deg)`,
        fontFamily: "'Caveat','Comic Sans MS',cursive",
        fontSize: size, fontWeight: 700, color,
        textShadow: "0 1px 0 rgba(0,0,0,0.06)",
      }}>
        {text}
      </div>
    );
  };

/** mock small phone */
const MiniPhone: React.FC<{ x: number; y: number; children: React.ReactNode }> = ({ x, y, children }) => (
  <div style={{
    position: "absolute", left: x, top: y,
    width: 380, height: 780,
    background: "#111", borderRadius: 46,
    padding: 10,
    boxShadow: "0 30px 60px rgba(18,22,33,0.18), 0 4px 12px rgba(18,22,33,0.12)",
  }}>
    <div style={{ width: "100%", height: "100%", borderRadius: 38, background: "#fff", overflow: "hidden", position: "relative" }}>
      <div style={{ height: 32, background: "#fff", display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0 18px 0 22px", fontFamily: DISPLAY, fontSize: 13, fontWeight: 700, color: PC.inkDark }}>
        <span>9:41</span>
        <span>●●●</span>
      </div>
      {children}
    </div>
  </div>
);

const V4_Scene1: React.FC = () => (
  <AbsoluteFill style={{ background: PC.cream, fontFamily: DISPLAY }}>
    {/* Paper lines */}
    {Array.from({ length: 28 }).map((_, i) => (
      <div key={i} style={{ position: "absolute", left: 0, right: 0, top: 120 + i * 64, height: 1, background: "rgba(30,30,30,0.05)" }} />
    ))}
    {/* defs for a rough marker filter */}
    <svg width="0" height="0" style={{ position: "absolute" }}>
      <defs>
        <filter id="markerRough">
          <feTurbulence type="fractalNoise" baseFrequency="0.06" numOctaves="2" seed="2" />
          <feDisplacementMap in="SourceGraphic" scale="3" />
        </filter>
      </defs>
    </svg>

    <div style={{ padding: "80px 60px 0" }}>
      <Rise delay={2}>
        <div style={{ fontSize: 22, color: PC.muted, letterSpacing: 4, fontWeight: 700, textTransform: "uppercase" }}>
          How the flow works ·
        </div>
      </Rise>
      <Rise delay={10} from={30}>
        <div style={{ fontFamily: SERIF, fontSize: 100, fontWeight: 700, color: PC.inkDark, letterSpacing: -3, lineHeight: 0.95, marginTop: 8 }}>
          From one lost<br/>call to one<br/>booked&nbsp;job.
        </div>
      </Rise>
    </div>
    {/* corner doodles */}
    <svg width="100%" height="100%" style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
      <DrawPath d="M 920 120 Q 990 200, 970 320 T 980 540" delay={30} color={PC.coral} width={6} />
      <DrawPath d="M 960 540 l -16 -8 l 10 20 l 10 -18" delay={60} color={PC.coral} width={6} />
    </svg>
    <Scribble x={800} y={640} delay={70} text="→ let's follow one" color={PC.coral} size={38} rotate={-2} />
  </AbsoluteFill>
);

const V4_Scene2: React.FC = () => (
  <AbsoluteFill style={{ background: PC.cream }}>
    <svg width="0" height="0" style={{ position: "absolute" }}>
      <defs>
        <filter id="markerRough">
          <feTurbulence type="fractalNoise" baseFrequency="0.06" numOctaves="2" seed="3" />
          <feDisplacementMap in="SourceGraphic" scale="3" />
        </filter>
      </defs>
    </svg>
    <MiniPhone x={350} y={480}>
      <div style={{ padding: 22, fontFamily: DISPLAY }}>
        <div style={{ textAlign: "center", color: PC.iosGrey, fontSize: 16, fontWeight: 600, letterSpacing: 1 }}>incoming · 14:02</div>
        <div style={{ textAlign: "center", margin: "16px 0 8px" }}>
          <div style={{ width: 160, height: 160, borderRadius: "50%", background: "#111", color: "#fff", fontSize: 70, fontWeight: 800, display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto" }}>S</div>
        </div>
        <div style={{ textAlign: "center", fontSize: 32, fontWeight: 700, color: PC.inkDark }}>Sarah O'C.</div>
        <div style={{ textAlign: "center", fontSize: 16, color: PC.iosGrey, marginTop: 4 }}>+353 86 ···· · possible customer</div>
        <div style={{ marginTop: 28, background: "rgba(45,211,160,0.14)", borderRadius: 16, padding: "12px 14px", display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: PC.mint }} />
          <span style={{ color: PC.mint, fontWeight: 800, fontSize: 14 }}>AI picking up…</span>
        </div>
        <div style={{ marginTop: 220, textAlign: "center", color: PC.iosGrey, fontSize: 14 }}>
          tap to listen in · hold to take over
        </div>
      </div>
    </MiniPhone>

    {/* Annotations */}
    <svg width="100%" height="100%" style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
      <DrawPath d="M 120 120 L 300 300" delay={20} color={PC.coral} />
      {/* circle around Sarah name */}
      <DrawPath d="M 700 800 Q 800 770, 880 800 Q 960 830, 920 870 Q 780 910, 680 870 Q 620 830, 700 800 Z" delay={35} color={PC.violet} width={5} />
      {/* arrow to AI pill */}
      <DrawPath d="M 200 1400 Q 330 1360, 430 1330" delay={65} color={PC.coral} />
      <DrawPath d="M 430 1330 l -20 -4 l 18 14 l 6 -22" delay={95} color={PC.coral} width={6} />
    </svg>
    <Scribble x={70} y={80} text="1. Call comes in" color={PC.coral} size={44} rotate={-3} delay={0} />
    <Scribble x={40} y={1330} text="picked up in <1s" color={PC.coral} size={36} rotate={-2} delay={60} />
    <Scribble x={950} y={760} text="could be a job!" color={PC.violet} size={34} rotate={4} delay={45} />
  </AbsoluteFill>
);

const V4_Scene3: React.FC = () => (
  <AbsoluteFill style={{ background: PC.cream }}>
    <svg width="0" height="0" style={{ position: "absolute" }}>
      <defs>
        <filter id="markerRough">
          <feTurbulence type="fractalNoise" baseFrequency="0.06" numOctaves="2" seed="4" />
          <feDisplacementMap in="SourceGraphic" scale="3" />
        </filter>
      </defs>
    </svg>
    <MiniPhone x={350} y={480}>
      <div style={{ padding: 22, fontFamily: DISPLAY }}>
        <div style={{ color: PC.iosGrey, fontSize: 14, fontWeight: 700, letterSpacing: 1, textTransform: "uppercase" }}>Live transcript</div>
        <div style={{ marginTop: 12 }}>
          <div style={{ background: "#f2f3f6", padding: "10px 14px", borderRadius: 16, fontSize: 17, color: PC.inkDark, marginBottom: 8 }}>
            Hi, I'd like to book a deep clean for Thursday if possible.
          </div>
          <div style={{ background: "rgba(45,211,160,0.14)", padding: "10px 14px", borderRadius: 16, fontSize: 17, color: PC.inkDark, marginBottom: 8 }}>
            Absolutely — 10:30 or 14:00?
          </div>
          <div style={{ background: "#f2f3f6", padding: "10px 14px", borderRadius: 16, fontSize: 17, color: PC.inkDark, marginBottom: 8 }}>
            14:00 works great.
          </div>
          <div style={{ background: "rgba(45,211,160,0.14)", padding: "10px 14px", borderRadius: 16, fontSize: 17, color: PC.inkDark }}>
            Done. Confirmation sent. Anything else?
          </div>
        </div>
        <div style={{ marginTop: 16, background: "#fff3e0", border: "1px solid #ffd99b", borderRadius: 12, padding: "10px 14px" }}>
          <div style={{ fontSize: 13, color: PC.amber, fontWeight: 800, letterSpacing: 1, textTransform: "uppercase" }}>Booking captured</div>
          <div style={{ fontSize: 16, color: PC.inkDark, marginTop: 4 }}>Thu 14:00 · Deep clean · Sarah</div>
        </div>
      </div>
    </MiniPhone>

    <svg width="100%" height="100%" style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
      <DrawPath d="M 120 120 L 300 280" delay={20} color={PC.coral} />
      <DrawPath d="M 880 930 Q 990 930, 1030 860" delay={50} color={PC.violet} />
      <DrawPath d="M 1030 860 l -18 -4 l 14 16 l 10 -18" delay={80} color={PC.violet} width={6} />
      <DrawPath d="M 860 1280 Q 930 1300, 1020 1240" delay={110} color={PC.coral} />
    </svg>
    <Scribble x={70} y={80} text="2. AI talks · books it" color={PC.coral} size={44} rotate={-3} delay={0} />
    <Scribble x={960} y={820} text="picks the time" color={PC.violet} size={30} rotate={-4} delay={60} />
    <Scribble x={960} y={1200} text="job on the calendar" color={PC.coral} size={30} rotate={3} delay={100} />
  </AbsoluteFill>
);

const V4_Scene4: React.FC = () => (
  <AbsoluteFill style={{ background: PC.cream }}>
    <svg width="0" height="0" style={{ position: "absolute" }}>
      <defs>
        <filter id="markerRough">
          <feTurbulence type="fractalNoise" baseFrequency="0.06" numOctaves="2" seed="5" />
          <feDisplacementMap in="SourceGraphic" scale="3" />
        </filter>
      </defs>
    </svg>
    <div style={{ padding: "80px 60px 0" }}>
      <Rise delay={0}>
        <div style={{ fontSize: 22, color: PC.muted, letterSpacing: 4, fontWeight: 700, textTransform: "uppercase" }}>
          3. Your morning ·
        </div>
      </Rise>
      <Rise delay={8} from={30}>
        <div style={{ fontFamily: SERIF, fontSize: 110, fontWeight: 700, color: PC.inkDark, letterSpacing: -3, lineHeight: 0.95, marginTop: 8 }}>
          Open the app.<br/>It's already<br/><span style={{ color: PC.coral }}>done.</span>
        </div>
      </Rise>
      <Rise delay={28} style={{ marginTop: 40 }}>
        <div style={{ background: "#fff", borderRadius: 20, padding: "22px 26px", border: `2px solid ${PC.inkDark}`, boxShadow: `6px 6px 0 ${PC.inkDark}` }}>
          {[
            { t: "09:12 AM", n: "Call · Sarah · booked Thu 14:00", c: PC.mint },
            { t: "10:34 AM", n: "Call · John · quote sent via SMS", c: PC.violet },
            { t: "14:02 PM", n: "Call · emergency · dispatched", c: PC.coral },
            { t: "—",        n: "Missed: 0   ·   Saved: 9 hrs", c: PC.inkDark },
          ].map((r, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", padding: "12px 0", borderBottom: i < 3 ? "1px dashed rgba(0,0,0,0.15)" : "none" }}>
              <span style={{ width: 4, height: 24, background: r.c, borderRadius: 2, marginRight: 14 }} />
              <span style={{ fontFamily: MONO, fontSize: 18, color: PC.muted, width: 120 }}>{r.t}</span>
              <span style={{ fontSize: 22, fontWeight: 600, color: PC.inkDark }}>{r.n}</span>
            </div>
          ))}
        </div>
      </Rise>
    </div>
    <svg width="100%" height="100%" style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
      <DrawPath d="M 80 1450 Q 400 1420, 700 1470" delay={80} color={PC.coral} width={7} />
    </svg>
    <Scribble x={200} y={1490} text="← this is what 'booked for you' feels like" color={PC.coral} size={34} rotate={-1} delay={105} />
    <div style={{ position: "absolute", bottom: 60, left: 0, right: 0, display: "flex", justifyContent: "center" }}>
      <Rise delay={130}><Mark size={42} /></Rise>
    </div>
    <div style={{ position: "absolute", bottom: 20, left: 0, right: 0, textAlign: "center" }}>
      <Rise delay={140}><span style={{ fontFamily: MONO, fontSize: 22, color: PC.muted }}>bookedforyou.ie</span></Rise>
    </div>
  </AbsoluteFill>
);

export const Whiteboard_Annotated: React.FC = () => {
  const scenes = [
    { c: V4_Scene1, d: 150 },
    { c: V4_Scene2, d: 200 },
    { c: V4_Scene3, d: 220 },
    { c: V4_Scene4, d: 200 },
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

// ═══════════════════════════════════════════════════════════
//  VIDEO 5 — Liquid_Blob_Close (vertical 15s)
//  Morphing liquid gradient blob using CSS goo filter.
//  Pure brand flex close card.
// ═══════════════════════════════════════════════════════════

const Blob: React.FC<{ r?: number; x: number; y: number; c1: string; c2: string; seed?: number; delay?: number }> =
  ({ r = 320, x, y, c1, c2, seed = 0, delay = 0 }) => {
    const f = useCurrentFrame();
    const t = (f + seed * 37) * 0.03;
    const bx = x + Math.sin(t) * 60;
    const by = y + Math.cos(t * 0.7) * 40;
    const sc = 1 + Math.sin(t * 0.8) * 0.08;
    const op = interpolate(f - delay, [0, 20], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    return (
      <div style={{
        position: "absolute",
        width: r * 2, height: r * 2, borderRadius: "50%",
        left: bx, top: by, transform: `translate(-50%,-50%) scale(${sc})`,
        background: `radial-gradient(circle at 40% 40%, ${c1} 0%, ${c2} 60%, transparent 75%)`,
        filter: "blur(20px)", opacity: op, mixBlendMode: "screen",
      }} />
    );
  };

const V5_Scene1: React.FC = () => (
  <AbsoluteFill style={{ background: "#050713" }}>
    {/* goo filter */}
    <svg width="0" height="0" style={{ position: "absolute" }}>
      <defs>
        <filter id="goo">
          <feGaussianBlur in="SourceGraphic" stdDeviation="30" />
          <feColorMatrix values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 20 -10" />
        </filter>
      </defs>
    </svg>
    <AbsoluteFill style={{ filter: "url(#goo)" }}>
      <Blob x={300}  y={500}  c1="#ff5a3c" c2="#6d4bff" seed={0} delay={0}  />
      <Blob x={760}  y={700}  c1="#2ed3a0" c2="#007aff" seed={1} delay={6}  />
      <Blob x={540}  y={1200} c1="#ffc640" c2="#ff5a3c" seed={2} delay={12} />
      <Blob x={200}  y={1500} c1="#6d4bff" c2="#2ed3a0" seed={3} delay={18} />
      <Blob x={880}  y={1400} c1="#ff5a3c" c2="#ffc640" seed={4} delay={24} />
    </AbsoluteFill>
    {/* caption */}
    <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", padding: "0 60px" }}>
      <Rise delay={10}>
        <div style={{ fontFamily: DISPLAY, fontSize: 26, color: "rgba(255,255,255,0.65)", letterSpacing: 6, textTransform: "uppercase", fontWeight: 800 }}>
          Stop losing calls ·
        </div>
      </Rise>
      <Rise delay={20} from={50}>
        <div style={{ fontFamily: SERIF, fontSize: 200, color: "#fff", letterSpacing: -8, lineHeight: 0.9, textAlign: "center", marginTop: 18, fontWeight: 700, textShadow: "0 8px 40px rgba(0,0,0,0.5)" }}>
          Hand the<br/>phone over.
        </div>
      </Rise>
      <Rise delay={48} style={{ marginTop: 60 }}>
        <Mark dark size={58} />
      </Rise>
      <Rise delay={60} style={{ marginTop: 24 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
          <div style={{ padding: "16px 34px", background: "#fff", color: PC.inkDark, borderRadius: 14, fontFamily: DISPLAY, fontSize: 28, fontWeight: 800 }}>
            Start free trial
          </div>
          <span style={{ fontFamily: MONO, color: "rgba(255,255,255,0.7)", fontSize: 22 }}>bookedforyou.ie</span>
        </div>
      </Rise>
    </div>
  </AbsoluteFill>
);

export const Liquid_Blob_Close: React.FC = () => {
  return (
    <AbsoluteFill>
      <Sequence durationInFrames={450}>
        <SceneFade dur={450}><V5_Scene1 /></SceneFade>
      </Sequence>
    </AbsoluteFill>
  );
};
