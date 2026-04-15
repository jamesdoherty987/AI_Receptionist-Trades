import { useEffect, useRef, useState } from 'react';

const FACES = [
  { icon: 'fa-phone-alt', label: 'AI Calls', stat: '24/7', color: '#0ea5e9' },
  { icon: 'fa-calendar-check', label: 'Smart Booking', stat: '90%', color: '#10b981' },
  { icon: 'fa-users', label: 'Customer CRM', stat: '360°', color: '#8b5cf6' },
  { icon: 'fa-file-invoice-dollar', label: 'Auto Invoicing', stat: '0 min', color: '#f59e0b' },
];

const ROTATIONS = [
  'rotateY(0deg)',
  'rotateY(-90deg)',
  'rotateY(-180deg)',
  'rotateY(-270deg)',
];

export default function FloatingCube({ onFaceChange }) {
  const [currentFace, setCurrentFace] = useState(0);
  const intervalRef = useRef(null);

  useEffect(() => {
    intervalRef.current = setInterval(() => {
      setCurrentFace((prev) => {
        const next = (prev + 1) % FACES.length;
        onFaceChange?.(next);
        return next;
      });
    }, 1600);
    return () => clearInterval(intervalRef.current);
  }, [onFaceChange]);

  return (
    <>
      <div className="prism-ambient" />
      <div className="prism-scene" style={{ perspective: '800px' }}>
        <div
          className="prism-cube"
          style={{ transform: ROTATIONS[currentFace] }}
        >
          {FACES.map((face, i) => (
            <div key={i} className={`prism-face prism-face-${i}`}>
              <div className="prism-face-content">
                <div
                  className="prism-face-icon-wrap"
                  style={{ background: `linear-gradient(135deg, ${face.color}, ${face.color}cc)` }}
                >
                  <i className={`fas ${face.icon}`} style={{ color: '#fff', fontSize: '1.5rem' }} />
                </div>
                <span className="prism-face-stat" style={{ color: face.color }}>
                  {face.stat}
                </span>
                <span className="prism-face-label">{face.label}</span>
              </div>
              <div className="prism-face-shimmer" />
            </div>
          ))}
        </div>
      </div>
      {/* Reflection */}
      <div
        className="prism-reflection prism-scene"
        style={{ perspective: '800px' }}
      >
        <div
          className="prism-cube"
          style={{ transform: ROTATIONS[currentFace] }}
        >
          {FACES.map((face, i) => (
            <div key={i} className={`prism-face prism-face-${i}`}>
              <div className="prism-face-content">
                <div
                  className="prism-face-icon-wrap"
                  style={{ background: `linear-gradient(135deg, ${face.color}, ${face.color}cc)` }}
                >
                  <i className={`fas ${face.icon}`} style={{ color: '#fff', fontSize: '1.5rem' }} />
                </div>
                <span className="prism-face-stat" style={{ color: face.color }}>
                  {face.stat}
                </span>
                <span className="prism-face-label">{face.label}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
