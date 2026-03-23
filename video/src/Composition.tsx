import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  Sequence,
  Easing,
} from "remotion";

// ─── Color palette ───
const COLORS = {
  bg: "#0a0a1a",
  bgGradient1: "#0f0c29",
  bgGradient2: "#1a1a3e",
  accent: "#6c63ff",
  accentLight: "#8b83ff",
  accentGlow: "rgba(108, 99, 255, 0.3)",
  green: "#00d4aa",
  greenGlow: "rgba(0, 212, 170, 0.3)",
  white: "#ffffff",
  gray: "#a0a0b8",
  cardBg: "rgba(255,255,255,0.06)",
  cardBorder: "rgba(255,255,255,0.1)",
};

// ─── Animated background grid ───
const GridBackground: React.FC = () => {
  const frame = useCurrentFrame();
  const offset = (frame * 0.3) % 60;
  return (
    <AbsoluteFill>
      <div
        style={{
          width: "100%",
          height: "100%",
          background: `linear-gradient(135deg, ${COLORS.bgGradient1}, ${COLORS.bgGradient2})`,
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage: `
            linear-gradient(rgba(108,99,255,0.07) 1px, transparent 1px),
            linear-gradient(90deg, rgba(108,99,255,0.07) 1px, transparent 1px)
          `,
          backgroundSize: "60px 60px",
          backgroundPosition: `${offset}px ${offset}px`,
        }}
      />
      {/* Glow orbs */}
      <div
        style={{
          position: "absolute",
          width: 500,
          height: 500,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${COLORS.accentGlow}, transparent 70%)`,
          top: -100,
          right: -100,
          filter: "blur(60px)",
        }}
      />
      <div
        style={{
          position: "absolute",
          width: 400,
          height: 400,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${COLORS.greenGlow}, transparent 70%)`,
          bottom: -100,
          left: -50,
          filter: "blur(60px)",
        }}
      />
    </AbsoluteFill>
  );
};

// ─── Fade-in text helper ───
const FadeIn: React.FC<{
  children: React.ReactNode;
  delay?: number;
  duration?: number;
  direction?: "up" | "down" | "left" | "right" | "none";
  style?: React.CSSProperties;
}> = ({ children, delay = 0, duration = 15, direction = "up", style }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const progress = spring({ frame: frame - delay, fps, config: { damping: 20, mass: 0.8 } });
  const opacity = interpolate(frame - delay, [0, duration], [0, 1], { extrapolateRight: "clamp", extrapolateLeft: "clamp" });
  const offsets = { up: [30, 0], down: [-30, 0], left: [40, 0], right: [-40, 0], none: [0, 0] };
  const [from, to] = offsets[direction];
  const translate = interpolate(progress, [0, 1], [from, to]);
  const axis = direction === "left" || direction === "right" ? "X" : "Y";
  return (
    <div style={{ opacity, transform: direction === "none" ? undefined : `translate${axis}(${translate}px)`, ...style }}>
      {children}
    </div>
  );
};

// ─── Pulsing dot ───
const PulsingDot: React.FC<{ color?: string }> = ({ color = COLORS.green }) => {
  const frame = useCurrentFrame();
  const scale = interpolate(Math.sin(frame * 0.15), [-1, 1], [0.8, 1.2]);
  return (
    <div style={{ width: 12, height: 12, borderRadius: "50%", backgroundColor: color, transform: `scale(${scale})`, boxShadow: `0 0 12px ${color}` }} />
  );
};

// ─── Scene 1: Hero / Intro ───
const HeroScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const logoScale = spring({ frame, fps, config: { damping: 12 } });
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <div style={{ textAlign: "center" }}>
        <FadeIn delay={0} direction="none">
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 16, marginBottom: 30, transform: `scale(${logoScale})` }}>
            <div style={{ width: 56, height: 56, borderRadius: 14, background: `linear-gradient(135deg, ${COLORS.accent}, ${COLORS.green})`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 28 }}>
              ⚡
            </div>
            <span style={{ fontSize: 48, fontWeight: 800, color: COLORS.white, letterSpacing: -1 }}>BookedForYou</span>
          </div>
        </FadeIn>
        <FadeIn delay={12} direction="up">
          <h1 style={{ fontSize: 64, fontWeight: 800, color: COLORS.white, lineHeight: 1.15, margin: 0, maxWidth: 900 }}>
            The Receptionist That{" "}
            <span style={{ background: `linear-gradient(135deg, ${COLORS.accent}, ${COLORS.green})`, WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
              Never Sleeps
            </span>
          </h1>
        </FadeIn>
        <FadeIn delay={24} direction="up">
          <p style={{ fontSize: 26, color: COLORS.gray, marginTop: 24, maxWidth: 700, margin: "24px auto 0", lineHeight: 1.5 }}>
            AI-powered phone receptionist for trades businesses.
            <br />
            Answer calls. Book jobs. Grow your business.
          </p>
        </FadeIn>
      </div>
    </AbsoluteFill>
  );
};


// ─── Scene 2: The Problem ───
const ProblemScene: React.FC = () => {
  const frame = useCurrentFrame();
  const items = [
    { icon: "📵", text: "Missed calls = lost revenue" },
    { icon: "😩", text: "Can't answer while on a job" },
    { icon: "💸", text: "Real receptionists cost €2,500+/mo" },
  ];
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <div style={{ textAlign: "center", maxWidth: 900 }}>
        <FadeIn delay={0} direction="up">
          <p style={{ fontSize: 20, color: COLORS.accent, fontWeight: 600, textTransform: "uppercase", letterSpacing: 3, marginBottom: 12 }}>The Problem</p>
        </FadeIn>
        <FadeIn delay={6} direction="up">
          <h2 style={{ fontSize: 52, fontWeight: 800, color: COLORS.white, margin: "0 0 50px" }}>
            Every missed call is a{" "}
            <span style={{ color: "#ff6b6b" }}>missed job</span>
          </h2>
        </FadeIn>
        <div style={{ display: "flex", gap: 30, justifyContent: "center" }}>
          {items.map((item, i) => (
            <FadeIn key={i} delay={18 + i * 10} direction="up">
              <div style={{
                background: COLORS.cardBg,
                border: `1px solid ${COLORS.cardBorder}`,
                borderRadius: 20,
                padding: "36px 32px",
                width: 240,
                backdropFilter: "blur(10px)",
              }}>
                <div style={{ fontSize: 44, marginBottom: 16 }}>{item.icon}</div>
                <p style={{ fontSize: 20, color: COLORS.white, fontWeight: 600, lineHeight: 1.4, margin: 0 }}>{item.text}</p>
              </div>
            </FadeIn>
          ))}
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ─── Scene 3: Phone ringing animation ───
const PhoneScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const phoneScale = spring({ frame: frame - 5, fps, config: { damping: 10, mass: 0.6 } });
  const ring = Math.sin(frame * 0.4) * 3;
  const badgeOpacity = interpolate(frame, [40, 55], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const waveScale = interpolate(frame, [45, 90], [0.8, 1.5], { extrapolateRight: "clamp" });
  const waveOpacity = interpolate(frame, [45, 90], [0.6, 0], { extrapolateRight: "clamp" });

  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <div style={{ textAlign: "center" }}>
        <FadeIn delay={0} direction="none">
          <div style={{
            width: 280,
            height: 500,
            borderRadius: 40,
            background: "linear-gradient(180deg, #1a1a3e, #0f0c29)",
            border: `2px solid ${COLORS.cardBorder}`,
            margin: "0 auto",
            position: "relative",
            transform: `scale(${phoneScale}) rotate(${ring}deg)`,
            boxShadow: `0 20px 60px rgba(0,0,0,0.5), 0 0 40px ${COLORS.accentGlow}`,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: 30,
          }}>
            {/* Notch */}
            <div style={{ position: "absolute", top: 12, width: 80, height: 6, borderRadius: 3, background: "rgba(255,255,255,0.15)" }} />
            {/* Caller avatar */}
            <div style={{
              width: 80, height: 80, borderRadius: "50%",
              background: `linear-gradient(135deg, ${COLORS.accent}, ${COLORS.green})`,
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 36, marginBottom: 16,
            }}>👤</div>
            <p style={{ color: COLORS.white, fontSize: 22, fontWeight: 700, margin: "0 0 4px" }}>Incoming Call</p>
            <p style={{ color: COLORS.gray, fontSize: 16, margin: "0 0 24px" }}>+353 86 XXX XXXX</p>
            {/* AI badge */}
            <div style={{
              opacity: badgeOpacity,
              background: `linear-gradient(135deg, ${COLORS.accent}, ${COLORS.green})`,
              borderRadius: 30, padding: "10px 24px",
              display: "flex", alignItems: "center", gap: 10,
            }}>
              <PulsingDot />
              <span style={{ color: COLORS.white, fontSize: 16, fontWeight: 700 }}>🤖 AI Answering</span>
            </div>
            {/* Sound wave rings */}
            <div style={{
              position: "absolute", width: 320, height: 320, borderRadius: "50%",
              border: `2px solid ${COLORS.accent}`,
              opacity: waveOpacity, transform: `scale(${waveScale})`,
              top: "50%", left: "50%", marginTop: -160, marginLeft: -160,
            }} />
          </div>
        </FadeIn>
      </div>
    </AbsoluteFill>
  );
};


// ─── Scene 4: Features showcase ───
const FeaturesScene: React.FC = () => {
  const features = [
    { icon: "📞", title: "24/7 AI Receptionist", desc: "Answers every call professionally" },
    { icon: "📅", title: "Smart Scheduling", desc: "Auto-books with calendar sync" },
    { icon: "👥", title: "Customer Management", desc: "Track clients & job history" },
    { icon: "💰", title: "Invoicing & Payments", desc: "Send invoices, track revenue" },
    { icon: "👷", title: "Worker Management", desc: "Assign jobs, prevent conflicts" },
    { icon: "💬", title: "SMS Reminders", desc: "Automatic 24hr reminders" },
  ];
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <div style={{ textAlign: "center", maxWidth: 1050 }}>
        <FadeIn delay={0} direction="up">
          <p style={{ fontSize: 20, color: COLORS.accent, fontWeight: 600, textTransform: "uppercase", letterSpacing: 3, marginBottom: 12 }}>Features</p>
        </FadeIn>
        <FadeIn delay={6} direction="up">
          <h2 style={{ fontSize: 48, fontWeight: 800, color: COLORS.white, margin: "0 0 50px" }}>
            Everything you need to{" "}
            <span style={{ background: `linear-gradient(135deg, ${COLORS.accent}, ${COLORS.green})`, WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
              grow your business
            </span>
          </h2>
        </FadeIn>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 24 }}>
          {features.map((f, i) => (
            <FadeIn key={i} delay={15 + i * 8} direction="up">
              <div style={{
                background: COLORS.cardBg,
                border: `1px solid ${COLORS.cardBorder}`,
                borderRadius: 18,
                padding: "28px 24px",
                textAlign: "left",
                backdropFilter: "blur(10px)",
              }}>
                <div style={{ fontSize: 32, marginBottom: 12 }}>{f.icon}</div>
                <p style={{ fontSize: 20, fontWeight: 700, color: COLORS.white, margin: "0 0 6px" }}>{f.title}</p>
                <p style={{ fontSize: 16, color: COLORS.gray, margin: 0, lineHeight: 1.4 }}>{f.desc}</p>
              </div>
            </FadeIn>
          ))}
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ─── Scene 5: How it works ───
const HowItWorksScene: React.FC = () => {
  const frame = useCurrentFrame();
  const steps = [
    { num: "1", title: "Sign Up", desc: "Set up your profile in 5 minutes" },
    { num: "2", title: "Connect Phone", desc: "Forward calls to your AI number" },
    { num: "3", title: "Start Growing", desc: "Never miss a call again" },
  ];
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <div style={{ textAlign: "center", maxWidth: 950 }}>
        <FadeIn delay={0} direction="up">
          <p style={{ fontSize: 20, color: COLORS.accent, fontWeight: 600, textTransform: "uppercase", letterSpacing: 3, marginBottom: 12 }}>How It Works</p>
        </FadeIn>
        <FadeIn delay={6} direction="up">
          <h2 style={{ fontSize: 48, fontWeight: 800, color: COLORS.white, margin: "0 0 60px" }}>
            Get started in{" "}
            <span style={{ background: `linear-gradient(135deg, ${COLORS.accent}, ${COLORS.green})`, WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
              3 simple steps
            </span>
          </h2>
        </FadeIn>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 20 }}>
          {steps.map((s, i) => {
            const lineProgress = interpolate(frame, [30 + i * 15, 45 + i * 15], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            return (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 20 }}>
                <FadeIn delay={15 + i * 15} direction="up">
                  <div style={{ textAlign: "center", width: 220 }}>
                    <div style={{
                      width: 70, height: 70, borderRadius: "50%",
                      background: `linear-gradient(135deg, ${COLORS.accent}, ${COLORS.green})`,
                      display: "flex", alignItems: "center", justifyContent: "center",
                      fontSize: 32, fontWeight: 800, color: COLORS.white,
                      margin: "0 auto 16px",
                      boxShadow: `0 0 30px ${COLORS.accentGlow}`,
                    }}>{s.num}</div>
                    <p style={{ fontSize: 22, fontWeight: 700, color: COLORS.white, margin: "0 0 6px" }}>{s.title}</p>
                    <p style={{ fontSize: 16, color: COLORS.gray, margin: 0 }}>{s.desc}</p>
                  </div>
                </FadeIn>
                {i < 2 && (
                  <div style={{ width: 80, height: 3, background: COLORS.cardBorder, borderRadius: 2, overflow: "hidden" }}>
                    <div style={{ width: `${lineProgress * 100}%`, height: "100%", background: `linear-gradient(90deg, ${COLORS.accent}, ${COLORS.green})`, borderRadius: 2 }} />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};


// ─── Scene 6: Comparison ───
const ComparisonScene: React.FC = () => {
  const rows = [
    { label: "Availability", human: "9-5 weekdays", ai: "24/7, 365 days" },
    { label: "Monthly Cost", human: "€2,500+", ai: "€99" },
    { label: "Sick Days", human: "20+ days/year", ai: "Never" },
    { label: "Concurrent Calls", human: "One at a time", ai: "Unlimited" },
    { label: "Booking", human: "Manual", ai: "Automatic" },
  ];
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <div style={{ textAlign: "center", maxWidth: 850 }}>
        <FadeIn delay={0} direction="up">
          <p style={{ fontSize: 20, color: COLORS.accent, fontWeight: 600, textTransform: "uppercase", letterSpacing: 3, marginBottom: 12 }}>Why Switch?</p>
        </FadeIn>
        <FadeIn delay={6} direction="up">
          <h2 style={{ fontSize: 44, fontWeight: 800, color: COLORS.white, margin: "0 0 40px" }}>
            Real Receptionist vs{" "}
            <span style={{ background: `linear-gradient(135deg, ${COLORS.accent}, ${COLORS.green})`, WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
              AI Receptionist
            </span>
          </h2>
        </FadeIn>
        <div style={{ background: COLORS.cardBg, border: `1px solid ${COLORS.cardBorder}`, borderRadius: 20, overflow: "hidden", backdropFilter: "blur(10px)" }}>
          {/* Header */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", padding: "18px 30px", borderBottom: `1px solid ${COLORS.cardBorder}` }}>
            <div style={{ textAlign: "left", fontSize: 16, fontWeight: 600, color: COLORS.gray }}>Feature</div>
            <div style={{ fontSize: 16, fontWeight: 600, color: COLORS.gray }}>👤 Human</div>
            <div style={{ fontSize: 16, fontWeight: 600, color: COLORS.green }}>🤖 AI</div>
          </div>
          {rows.map((r, i) => (
            <FadeIn key={i} delay={15 + i * 8} direction="left" style={{ borderBottom: i < rows.length - 1 ? `1px solid ${COLORS.cardBorder}` : "none" }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", padding: "16px 30px" }}>
                <div style={{ textAlign: "left", fontSize: 18, fontWeight: 600, color: COLORS.white }}>{r.label}</div>
                <div style={{ fontSize: 17, color: "#ff6b6b" }}>{r.human}</div>
                <div style={{ fontSize: 17, color: COLORS.green, fontWeight: 700 }}>✓ {r.ai}</div>
              </div>
            </FadeIn>
          ))}
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ─── Scene 7: CTA / Outro ───
const CTAScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const btnScale = spring({ frame: frame - 30, fps, config: { damping: 8, mass: 0.5 } });
  const glow = interpolate(Math.sin(frame * 0.1), [-1, 1], [0.4, 1]);
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <div style={{ textAlign: "center" }}>
        <FadeIn delay={0} direction="up">
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 14, marginBottom: 30 }}>
            <div style={{ width: 48, height: 48, borderRadius: 12, background: `linear-gradient(135deg, ${COLORS.accent}, ${COLORS.green})`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 24 }}>⚡</div>
            <span style={{ fontSize: 36, fontWeight: 800, color: COLORS.white }}>BookedForYou</span>
          </div>
        </FadeIn>
        <FadeIn delay={8} direction="up">
          <h2 style={{ fontSize: 56, fontWeight: 800, color: COLORS.white, margin: "0 0 16px", lineHeight: 1.2 }}>
            Ready to never miss
            <br />a call again?
          </h2>
        </FadeIn>
        <FadeIn delay={16} direction="up">
          <p style={{ fontSize: 24, color: COLORS.gray, margin: "0 0 40px" }}>
            Start your free 14-day trial. No credit card required.
          </p>
        </FadeIn>
        <FadeIn delay={24} direction="up">
          <div style={{
            display: "inline-block",
            background: `linear-gradient(135deg, ${COLORS.accent}, ${COLORS.green})`,
            borderRadius: 16, padding: "20px 50px",
            transform: `scale(${btnScale})`,
            boxShadow: `0 0 ${40 * glow}px ${COLORS.accentGlow}`,
          }}>
            <span style={{ fontSize: 24, fontWeight: 800, color: COLORS.white }}>
              Get Started Free →
            </span>
          </div>
        </FadeIn>
        <FadeIn delay={35} direction="up">
          <p style={{ fontSize: 18, color: COLORS.gray, marginTop: 30 }}>
            bookedforyou.ie
          </p>
        </FadeIn>
      </div>
    </AbsoluteFill>
  );
};

// ─── Scene transition: crossfade ───
const SceneTransition: React.FC<{
  children: React.ReactNode;
  durationInFrames: number;
  fadeIn?: number;
  fadeOut?: number;
}> = ({ children, durationInFrames, fadeIn = 12, fadeOut = 12 }) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(
    frame,
    [0, fadeIn, durationInFrames - fadeOut, durationInFrames],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  return <AbsoluteFill style={{ opacity }}>{children}</AbsoluteFill>;
};

// ─── Main Composition ───
export const MyComposition: React.FC = () => {
  // Scene durations in frames (30fps)
  const scenes = [
    { component: HeroScene, duration: 120 },       // 4s
    { component: ProblemScene, duration: 120 },     // 4s
    { component: PhoneScene, duration: 105 },       // 3.5s
    { component: FeaturesScene, duration: 150 },    // 5s
    { component: HowItWorksScene, duration: 120 },  // 4s
    { component: ComparisonScene, duration: 135 },  // 4.5s
    { component: CTAScene, duration: 120 },         // 4s
  ];

  let startFrame = 0;
  return (
    <AbsoluteFill style={{ fontFamily: "'Inter', 'SF Pro Display', -apple-system, sans-serif" }}>
      <GridBackground />
      {scenes.map((scene, i) => {
        const from = startFrame;
        startFrame += scene.duration;
        const Scene = scene.component;
        return (
          <Sequence key={i} from={from} durationInFrames={scene.duration}>
            <SceneTransition durationInFrames={scene.duration}>
              <Scene />
            </SceneTransition>
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
