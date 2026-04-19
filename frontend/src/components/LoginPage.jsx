import { useState } from 'react';

export default function LoginPage({ onLogin }) {
  const [username, setUsername] = useState('');
  const [pin, setPin] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [isRegister, setIsRegister] = useState(false);
  const [displayName, setDisplayName] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await onLogin(username, pin, isRegister ? displayName : null);
    } catch (err) {
      setError(err.message || 'Authentication failed');
    }
    setLoading(false);
  };

  return (
    <div className="login-overlay">
      <div className="login-card animate-in">
        <div className="login-header">
          <span className="login-logo">🎙️</span>
          <h1 className="login-title">VoicePay</h1>
          <p className="login-subtitle">Risk-Adaptive Voice Finance Assistant</p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          <div className="login-field">
            <label htmlFor="login-username">Username</label>
            <input
              id="login-username"
              type="text"
              placeholder="Enter username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoFocus
              disabled={loading}
            />
          </div>

          {isRegister && (
            <div className="login-field">
              <label htmlFor="login-display-name">Display Name</label>
              <input
                id="login-display-name"
                type="text"
                placeholder="Your display name"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                required
                disabled={loading}
              />
            </div>
          )}

          <div className="login-field">
            <label htmlFor="login-pin">PIN</label>
            <input
              id="login-pin"
              type="password"
              placeholder="Enter 4-6 digit PIN"
              value={pin}
              onChange={(e) => setPin(e.target.value)}
              required
              minLength={4}
              maxLength={6}
              disabled={loading}
            />
          </div>

          {error && <div className="login-error">{error}</div>}

          <button
            type="submit"
            className="btn btn-primary login-btn"
            disabled={loading || !username.trim() || !pin.trim() || (isRegister && !displayName.trim())}
          >
            {loading ? <div className="spinner" /> : isRegister ? 'Create Account' : 'Sign In'}
          </button>
        </form>

        <div className="login-toggle">
          {isRegister ? (
            <span>
              Already have an account?{' '}
              <button className="link-btn" onClick={() => setIsRegister(false)}>Sign In</button>
            </span>
          ) : (
            <span>
              New user?{' '}
              <button className="link-btn" onClick={() => setIsRegister(true)}>Create Account</button>
            </span>
          )}
        </div>

        <div className="login-demo-hint">
          <span>Demo: username <strong>demo_user</strong> / PIN <strong>1234</strong></span>
        </div>
      </div>
    </div>
  );
}
