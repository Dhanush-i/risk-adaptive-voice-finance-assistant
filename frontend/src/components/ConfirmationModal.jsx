import { useState, useEffect, useRef } from 'react';

/**
 * Transaction Confirmation Modal
 * Shows recipient, amount, risk badge with a countdown timer.
 * Only proceeds after countdown or explicit "Confirm Now" click.
 */
export default function ConfirmationModal({
  transactionId,
  amount,
  recipient,
  riskTier,
  riskScore,
  onConfirm,
  onCancel,
  countdownSeconds = 5,
}) {
  const [secondsLeft, setSecondsLeft] = useState(countdownSeconds);
  const [confirmed, setConfirmed] = useState(false);
  const timerRef = useRef(null);

  useEffect(() => {
    timerRef.current = setInterval(() => {
      setSecondsLeft((prev) => {
        if (prev <= 1) {
          clearInterval(timerRef.current);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timerRef.current);
  }, []);

  // Auto-confirm when countdown hits 0 (user didn't cancel)
  useEffect(() => {
    if (secondsLeft === 0 && !confirmed) {
      setConfirmed(true);
      onConfirm();
    }
  }, [secondsLeft, confirmed, onConfirm]);

  const handleConfirmNow = () => {
    clearInterval(timerRef.current);
    setConfirmed(true);
    onConfirm();
  };

  const handleCancel = () => {
    clearInterval(timerRef.current);
    onCancel();
  };

  const riskColor =
    riskTier === 'Low' ? '#22c55e' : riskTier === 'Medium' ? '#f59e0b' : '#ef4444';

  const progress = ((countdownSeconds - secondsLeft) / countdownSeconds) * 100;

  return (
    <div className="confirmation-overlay">
      <div className="confirmation-modal animate-in">
        <div className="confirmation-header">
          <h2>Confirm Payment</h2>
          <div className="countdown-ring" style={{ '--progress': `${progress}%`, '--ring-color': riskColor }}>
            <span className="countdown-number">{secondsLeft}</span>
          </div>
        </div>

        <div className="confirmation-details">
          <div className="confirmation-row">
            <span className="confirmation-label">Recipient</span>
            <span className="confirmation-value">{recipient || 'Unknown'}</span>
          </div>
          <div className="confirmation-row">
            <span className="confirmation-label">Amount</span>
            <span className="confirmation-value confirmation-amount">₹{amount?.toLocaleString()}</span>
          </div>
          <div className="confirmation-row">
            <span className="confirmation-label">Risk Level</span>
            <span className="risk-badge" style={{ backgroundColor: riskColor + '22', color: riskColor, borderColor: riskColor }}>
              {riskTier} ({Math.round((riskScore || 0) * 100)}%)
            </span>
          </div>
        </div>

        {!confirmed && (
          <div className="confirmation-actions">
            <button className="btn btn-cancel" onClick={handleCancel} id="confirm-cancel-btn">
              Cancel
            </button>
            <button className="btn btn-primary" onClick={handleConfirmNow} id="confirm-now-btn">
              Confirm Now
            </button>
          </div>
        )}

        {confirmed && (
          <div className="confirmation-processing">
            <div className="spinner" />
            <span>Processing payment...</span>
          </div>
        )}
      </div>
    </div>
  );
}
