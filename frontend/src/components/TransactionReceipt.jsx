import { useState, useEffect } from 'react';
import { getTransactionDetail } from '../utils/api';

/**
 * TransactionReceipt — Shows full details after a payment completes.
 * Displayed automatically after successful Razorpay checkout.
 */
export default function TransactionReceipt({ transactionId, onGoHome }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!transactionId) return;
    setLoading(true);
    getTransactionDetail(transactionId)
      .then((data) => {
        setDetail(data.transaction);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [transactionId]);

  if (loading) {
    return (
      <div className="receipt-page">
        <div className="receipt-card animate-in">
          <div className="empty-state">
            <div className="spinner" style={{ margin: '0 auto' }} />
            <p style={{ marginTop: '1rem', color: 'var(--text-muted)' }}>Loading receipt...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="receipt-page">
        <div className="receipt-card animate-in">
          <div className="empty-state">
            <div className="empty-state-icon">❌</div>
            <p>{error || 'Transaction not found'}</p>
          </div>
          <button className="btn btn-primary" style={{ width: '100%', marginTop: '1.5rem' }} onClick={onGoHome}>
            ← Back to Home
          </button>
        </div>
      </div>
    );
  }

  const isPaid = detail.payment_status === 'captured' || detail.status === 'completed';
  const isFailed = detail.status === 'failed' || detail.status === 'blocked';

  return (
    <div className="receipt-page">
      <div className="receipt-card animate-in">
        {/* Status Header */}
        <div className={`receipt-status ${isPaid ? 'success' : isFailed ? 'failed' : 'pending'}`}>
          <div className="receipt-status-icon">
            {isPaid ? '✅' : isFailed ? '❌' : '⏳'}
          </div>
          <h2 className="receipt-status-title">
            {isPaid ? 'Payment Successful' : isFailed ? 'Payment Failed' : 'Payment Processing'}
          </h2>
          <p className="receipt-status-subtitle">
            Transaction #{detail.id}
          </p>
        </div>

        {/* Amount */}
        <div className="receipt-amount">
          ₹{(detail.amount_inr || 0).toLocaleString('en-IN')}
        </div>

        {/* Details Grid */}
        <div className="receipt-details">
          {detail.recipient && (
            <div className="receipt-row">
              <span className="receipt-label">To</span>
              <span className="receipt-value">{detail.recipient}</span>
            </div>
          )}
          <div className="receipt-row">
            <span className="receipt-label">Intent</span>
            <span className="receipt-value">
              {detail.intent?.replace(/_/g, ' ')?.replace(/\b\w/g, (c) => c.toUpperCase())}
            </span>
          </div>
          <div className="receipt-row">
            <span className="receipt-label">Risk Tier</span>
            <span className="receipt-value">
              <span className={`badge badge-${detail.risk_tier === 'Low' ? 'success' : detail.risk_tier === 'Medium' ? 'warning' : 'danger'}`}>
                {detail.risk_tier} ({((detail.risk_score || 0) * 100).toFixed(0)}%)
              </span>
            </span>
          </div>
          <div className="receipt-row">
            <span className="receipt-label">Auth Method</span>
            <span className="receipt-value">{detail.auth_method || '—'}</span>
          </div>
          {detail.sv_similarity > 0 && (
            <div className="receipt-row">
              <span className="receipt-label">Voice Match</span>
              <span className="receipt-value">
                {detail.sv_verified ? '✅' : '❌'} {((detail.sv_similarity || 0) * 100).toFixed(0)}%
              </span>
            </div>
          )}
          {detail.transcript && (
            <div className="receipt-row">
              <span className="receipt-label">Transcript</span>
              <span className="receipt-value receipt-transcript">"{detail.transcript}"</span>
            </div>
          )}
          {detail.razorpay_payment_id && (
            <div className="receipt-row">
              <span className="receipt-label">Payment ID</span>
              <span className="receipt-value" style={{ fontSize: 'var(--font-xs)', wordBreak: 'break-all' }}>
                {detail.razorpay_payment_id}
              </span>
            </div>
          )}
          <div className="receipt-row">
            <span className="receipt-label">Date</span>
            <span className="receipt-value">
              {detail.created_at ? new Date(detail.created_at).toLocaleString('en-IN') : '—'}
            </span>
          </div>
          <div className="receipt-row">
            <span className="receipt-label">Status</span>
            <span className="receipt-value">
              <span className={`badge ${isPaid ? 'badge-success' : isFailed ? 'badge-danger' : 'badge-info'}`}>
                {detail.status}
              </span>
            </span>
          </div>
        </div>

        {/* Actions */}
        <div className="receipt-actions">
          <button
            className="btn btn-primary"
            style={{ width: '100%' }}
            onClick={onGoHome}
            id="receipt-home-btn"
          >
            ← Back to Home
          </button>
        </div>
      </div>
    </div>
  );
}
