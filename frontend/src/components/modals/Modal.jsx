import { useEffect } from 'react';
import './Modal.css';

function Modal({ isOpen, onClose, title, children, size = 'medium' }) {
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
      document.body.classList.add('modal-open');
    } else {
      // Only restore scroll if no other modals are open
      const openModals = document.querySelectorAll('.modal-overlay');
      if (openModals.length === 0) {
        document.body.style.overflow = 'unset';
        document.body.classList.remove('modal-open');
      }
    }
    
    return () => {
      const openModals = document.querySelectorAll('.modal-overlay');
      if (openModals.length === 0) {
        document.body.style.overflow = 'unset';
        document.body.classList.remove('modal-open');
      }
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div 
        className={`modal-container modal-${size}`} 
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h2 className="modal-title">{title}</h2>
          <button className="modal-close" onClick={onClose}>
            &times;
          </button>
        </div>
        <div className="modal-content">
          {children}
        </div>
      </div>
    </div>
  );
}

export default Modal;
