import { useState, useRef, useEffect } from 'react';
import './HelpTooltip.css';

function HelpTooltip({ text }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return;
    const handleClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open]);

  return (
    <span className="help-tooltip-wrapper" ref={ref}>
      <button
        type="button"
        className="help-tooltip-btn"
        onClick={() => setOpen(!open)}
        aria-label="More info"
      >
        <i className="fas fa-question-circle"></i>
      </button>
      {open && (
        <span className="help-tooltip-bubble" role="tooltip">
          {text}
        </span>
      )}
    </span>
  );
}

export default HelpTooltip;
