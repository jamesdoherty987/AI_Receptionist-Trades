import { useState, useEffect } from 'react';
import './Modal.css';
import './PhoneConfigModal.css';
import api from '../../services/api';
import LoadingSpinner from '../LoadingSpinner';

function PhoneConfigModal({ isOpen, onClose, onSuccess, allowSkip = false }) {
  const [availableNumbers, setAvailableNumbers] = useState([]);
  const [selectedNumber, setSelectedNumber] = useState('');
  const [loading, setLoading] = useState(true);
  const [assigning, setAssigning] = useState(false);
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  useEffect(() => {
    if (isOpen) {
      fetchAvailableNumbers();
    }
  }, [isOpen]);

  const fetchAvailableNumbers = async () => {
    setLoading(true);
    setError('');
    
    try {
      const response = await api.get('/api/phone-numbers/available');
      if (response.data.success) {
        setAvailableNumbers(response.data.numbers);
        if (response.data.numbers.length === 0) {
          setError('No phone numbers available at this time. Please contact support.');
        }
      } else {
        setError(response.data.error || 'Failed to load phone numbers');
      }
    } catch (err) {
      console.error('Error fetching numbers:', err);
      const errorMsg = err.response?.data?.error || err.message || 'Failed to load available phone numbers';
      setError(`Error: ${errorMsg}`);
    } finally {
      setLoading(false);
    }
  };

  const handleAssign = async () => {
    if (!selectedNumber) {
      setError('Please select a phone number');
      return;
    }

    setAssigning(true);
    setError('');

    try {
      const response = await api.post('/api/phone-numbers/assign', {
        phone_number: selectedNumber
      });

      if (response.data.success) {
        setSuccessMessage('Phone number assigned successfully!');
        
        // Wait a moment to show success, then call callback
        setTimeout(() => {
          if (onSuccess) {
            onSuccess(selectedNumber);
          }
          onClose();
        }, 1500);
      }
    } catch (err) {
      const errorMsg = err.response?.data?.error || 'Failed to assign phone number';
      setError(errorMsg);
    } finally {
      setAssigning(false);
    }
  };

  const handleSkip = () => {
    if (allowSkip) {
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <>
      <div className="modal-overlay" onClick={allowSkip ? handleSkip : null}>
        <div className="modal-container modal-medium phone-config-modal" onClick={(e) => e.stopPropagation()}>
          <div className="modal-header">
            <h2 className="modal-title"><i className="fas fa-phone"></i> Configure Phone Calls</h2>
            {allowSkip && (
              <button className="modal-close" onClick={handleSkip}>
                <i className="fas fa-times"></i>
              </button>
            )}
          </div>

          <div className="modal-content">
            <p className="modal-description">
              Choose a phone number for your business. This number will be used for all incoming customer calls.
              Once assigned, this number will be permanently yours.
            </p>

            {loading ? (
              <div className="loading-container">
                <LoadingSpinner />
                <p>Loading available numbers...</p>
              </div>
            ) : error && availableNumbers.length === 0 ? (
              <div className="error-message">
                <i className="fas fa-exclamation-circle"></i>
                <p>{error}</p>
              </div>
            ) : (
              <>
                <div className="phone-numbers-list">
                  {availableNumbers.map((number) => (
                    <div
                      key={number.phone_number}
                      className={`phone-number-item ${selectedNumber === number.phone_number ? 'selected' : ''}`}
                      onClick={() => setSelectedNumber(number.phone_number)}
                    >
                      <div className="phone-number-radio">
                        {selectedNumber === number.phone_number ? (
                          <i className="fas fa-check-circle"></i>
                        ) : (
                          <i className="far fa-circle"></i>
                        )}
                      </div>
                      <div className="phone-number-details">
                        <span className="phone-number-text">{number.phone_number}</span>
                      </div>
                    </div>
                  ))}
                </div>

                {error && (
                  <div className="error-banner">
                    <i className="fas fa-exclamation-triangle"></i>
                    {error}
                  </div>
                )}
              </>
            )}

            {successMessage && (
              <div className="success-banner">
                <i className="fas fa-check-circle"></i>
                {successMessage}
              </div>
            )}
          </div>

          <div className="modal-footer">
            {allowSkip && (
              <button
                className="btn btn-secondary"
                onClick={handleSkip}
                disabled={assigning}
              >
                Skip for Now
              </button>
            )}
            <button
              className="btn btn-primary"
              onClick={handleAssign}
              disabled={!selectedNumber || assigning || availableNumbers.length === 0}
            >
              {assigning ? (
                <>
                  <LoadingSpinner size="small" />
                  Assigning...
                </>
              ) : (
                <>
                  <i className="fas fa-check"></i>
                  Confirm & Assign
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

export default PhoneConfigModal;
