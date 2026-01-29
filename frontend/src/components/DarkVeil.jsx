import { useEffect, useRef } from 'react';

/**
 * DarkVeil - A canvas-based atmospheric visual effect
 * Creates subtle animated gradients with optional noise and scanline effects
 */
function DarkVeil({
  hueShift = 0,
  noiseIntensity = 0,
  scanlineIntensity = 0,
  speed = 0.5,
  scanlineFrequency = 0,
  warpAmount = 0,
  className = ''
}) {
  const canvasRef = useRef(null);
  const animationRef = useRef(null);
  const timeRef = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    
    const resizeCanvas = () => {
      const rect = canvas.parentElement.getBoundingClientRect();
      canvas.width = rect.width;
      canvas.height = rect.height;
    };

    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);

    const animate = () => {
      timeRef.current += 0.016 * speed;
      const time = timeRef.current;

      // Clear canvas
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Create base gradient with animated colors
      const gradient = ctx.createLinearGradient(
        canvas.width * 0.5 + Math.sin(time * 0.5) * canvas.width * 0.3,
        0,
        canvas.width * 0.5 + Math.cos(time * 0.7) * canvas.width * 0.3,
        canvas.height
      );

      // Calculate hue-shifted colors
      const baseHue1 = (200 + hueShift) % 360; // Blue
      const baseHue2 = (330 + hueShift) % 360; // Pink

      gradient.addColorStop(0, `hsla(${baseHue1}, 70%, 50%, 0.05)`);
      gradient.addColorStop(0.5, `hsla(${(baseHue1 + baseHue2) / 2}, 60%, 40%, 0.08)`);
      gradient.addColorStop(1, `hsla(${baseHue2}, 70%, 50%, 0.05)`);

      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // Add subtle moving shapes
      const numOrbs = 3;
      for (let i = 0; i < numOrbs; i++) {
        const orbX = canvas.width * (0.3 + i * 0.2) + Math.sin(time * (0.3 + i * 0.1)) * 50 * (1 + warpAmount);
        const orbY = canvas.height * (0.4 + i * 0.1) + Math.cos(time * (0.4 + i * 0.15)) * 30 * (1 + warpAmount);
        const orbRadius = 150 + Math.sin(time * 0.5 + i) * 50;
        
        const orbGradient = ctx.createRadialGradient(
          orbX, orbY, 0,
          orbX, orbY, orbRadius
        );
        
        const orbHue = (baseHue1 + i * 40 + hueShift) % 360;
        orbGradient.addColorStop(0, `hsla(${orbHue}, 60%, 50%, 0.06)`);
        orbGradient.addColorStop(0.5, `hsla(${orbHue}, 50%, 40%, 0.03)`);
        orbGradient.addColorStop(1, 'hsla(0, 0%, 0%, 0)');
        
        ctx.fillStyle = orbGradient;
        ctx.fillRect(0, 0, canvas.width, canvas.height);
      }

      // Add noise effect if intensity > 0
      if (noiseIntensity > 0) {
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const data = imageData.data;
        for (let i = 0; i < data.length; i += 4) {
          const noise = (Math.random() - 0.5) * noiseIntensity * 50;
          data[i] = Math.min(255, Math.max(0, data[i] + noise));
          data[i + 1] = Math.min(255, Math.max(0, data[i + 1] + noise));
          data[i + 2] = Math.min(255, Math.max(0, data[i + 2] + noise));
        }
        ctx.putImageData(imageData, 0, 0);
      }

      // Add scanline effect if intensity > 0
      if (scanlineIntensity > 0 && scanlineFrequency > 0) {
        ctx.fillStyle = `rgba(0, 0, 0, ${scanlineIntensity * 0.1})`;
        const lineSpacing = Math.max(2, 8 - scanlineFrequency);
        for (let y = 0; y < canvas.height; y += lineSpacing) {
          ctx.fillRect(0, y, canvas.width, 1);
        }
      }

      animationRef.current = requestAnimationFrame(animate);
    };

    animate();

    return () => {
      window.removeEventListener('resize', resizeCanvas);
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [hueShift, noiseIntensity, scanlineIntensity, speed, scanlineFrequency, warpAmount]);

  return (
    <canvas
      ref={canvasRef}
      className={`dark-veil ${className}`}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
        zIndex: 0
      }}
    />
  );
}

export default DarkVeil;

