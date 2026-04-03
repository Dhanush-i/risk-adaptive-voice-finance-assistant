import { useState } from 'react';

export default function PinPad({ amount, recipient, onSubmit, onCancel, loading }) {
  const [pin, setPin] = useState('');
  const [error, setError] = useState('');

  const handleKey = (digit) => {
    if (pin.length < 4) {
      setPin((p) => p + digit);
      setError('');
    }
  };

  const handleBackspace = () => {
    setPin((p) => p.slice(0, -1));
    setError('');
  };

  const handleSubmit = async () => {
    if (pin.length < 4) {
      setError('Enter 4-digit PIN');
      return;
    }
    try {
      await onSubmit(pin);
    } catch (e) {
      setError(e.message || 'Invalid PIN');
      setPin('');
    }
  };

  return (
    <div className="pin-overlay" onClick={(e) => e.target === e.currentTarget && onCancel()}>
      <div className="pin-modal animate-in">
        {/* Header */}
        <div style={{ marginBottom: '0.25rem' }}>
          <div style={{ fontSize: '2rem', marginBottom: '0.75rem' }}>🔒</div>
          <div className="pin-title">Confirm Payment</div>
        </div>

        {recipient && (
          <div style={{ color: 'var(--text-muted)', fontSize: 'var(--font-sm)', marginBottom: '0.35rem' }}>
            Sending to <strong style={{ color: 'var(--text-main)' }}>{recipient}</strong>
          </div>
        )}
        <div className="pin-amount">₹{amount}</div>

        {/* PIN Dots */}
        <div className="pin-dots">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className={`pin-dot ${i < pin.length ? 'filled' : ''}`} />
          ))}
        </div>

        {/* Error */}
        {error && (
          <div style={{
            color: 'var(--danger)',
            fontSize: 'var(--font-xs)',
            marginBottom: '1rem',
            background: 'var(--danger-bg)',
            padding: '0.5rem 1rem',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--danger-border)',
          }}>
            {error}
          </div>
        )}

        {/* Keypad */}
        <div className="pin-keypad">
          {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((n) => (
            <button key={n} className="pin-key" onClick={() => handleKey(String(n))} disabled={loading}>
              {n}
            </button>
          ))}
          <button className="pin-key backspace" onClick={handleBackspace} disabled={loading}>
            ←
          </button>
          <button className="pin-key" onClick={() => handleKey('0')} disabled={loading}>
            0
          </button>
          <button className="pin-key submit" onClick={handleSubmit} disabled={loading || pin.length < 4}>
            {loading ? <div className="spinner" /> : '→'}
          </button>
        </div>

        {/* Cancel */}
        <button
          onClick={onCancel}
          style={{
            marginTop: '1.5rem',
            background: 'none',
            border: 'none',
            color: 'var(--text-muted)',
            cursor: 'pointer',
            fontFamily: 'inherit',
            fontSize: 'var(--font-sm)',
            transition: 'color 0.2s',
          }}
          onMouseEnter={(e) => e.target.style.color = 'var(--text-main)'}
          onMouseLeave={(e) => e.target.style.color = 'var(--text-muted)'}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
