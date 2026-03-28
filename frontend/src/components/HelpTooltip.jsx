import { useState, useRef, useEffect, useCallback } from 'react';
import './HelpTooltip.css';

function HelpTooltip({ text }) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0 });
  const btnRef = useRef(null);
  const bubbleRef = useRef(null);

  const updatePosition = useCallback(() => {
    if (!btnRef.current) return;
    const rect = btnRef.current.getBoundingClientRect();
    setPos({
      top: rect.bottom + 6,
      left: rect.left + rect.width / 2,
    });
  }, []);

  useEffect(() => {
    if (!open) return;
    updatePosition();

    const handleClickOutside = (e) => {
      if (
        btnRef.current && !btnRef.current.contains(e.target) &&
        bubbleRef.current && !bubbleRef.current.contains(e.target)
      ) {
        setOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    window.addEventListener('scroll', updatePosition, true);
    window.addEventListener('resize', updatePosition);

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      window.removeEventListener('scroll', updatePosition, true);
      window.removeEventListener('resize', updatePosition);
    };
  }, [open, updatePosition]);

  return (
    <span className="help-tooltip-wrapper">
      <button
        type="button"
        className="help-tooltip-btn"
        ref={btnRef}
        onClick={() => setOpen(!open)}
        aria-label="More info"
      >
        <i className="fas fa-question-circle"></i>
      </button>
      {open && (
        <span
          className="help-tooltip-bubble"
          ref={bubbleRef}
          role="tooltip"
          style={{ top: pos.top, left: pos.left }}
        >
          {text}
        </span>
      )}
    </span>
  );
}

export default HelpTooltip;
