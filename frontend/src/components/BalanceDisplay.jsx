import React from 'react';

export default function BalanceDisplay({ balance, onDismiss }) {
  return (
    <div className="pin-overlay">
      <div className="pin-modal animate-in" style={{ textAlign: 'center' }}>
        <div style={{ fontSize: '3rem', marginBottom: 'var(--space-md)' }}>💰</div>
        <h2 style={{ marginBottom: 'var(--space-md)' }}>Your Balance</h2>
        
        <div className="stat-value gradient" style={{ fontSize: '3rem', marginBottom: 'var(--space-xl)' }}>
          ₹{balance.toLocaleString('en-IN')}
        </div>

        <button 
          className="btn btn-primary" 
          style={{ width: '100%' }} 
          onClick={onDismiss}
        >
          Done
        </button>
      </div>
    </div>
  );
}
