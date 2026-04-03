import { useState, useEffect } from 'react';
import { getTransactions, getTransactionDetail } from '../utils/api';

const INTENT_ICONS = {
  send_money: '💸',
  check_balance: '💰',
  transaction_history: '📋',
  pay_bill: '🧾',
};

export default function TransactionHistory({ username, refreshKey }) {
  const [transactions, setTransactions] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selectedTxn, setSelectedTxn] = useState(null);
  const [detail, setDetail] = useState(null);

  useEffect(() => {
    loadTransactions();
  }, [username, refreshKey]);

  const loadTransactions = async () => {
    setLoading(true);
    try {
      const data = await getTransactions(username, 20);
      setTransactions(data.transactions);
      setTotal(data.total);
    } catch (e) {
      console.error('Failed to load transactions:', e);
    }
    setLoading(false);
  };

  const showDetail = async (txnId) => {
    try {
      const data = await getTransactionDetail(txnId);
      setDetail(data);
      setSelectedTxn(txnId);
    } catch (e) {
      console.error('Failed to load detail:', e);
    }
  };

  const getStatusBadge = (status) => {
    const map = {
      completed: { cls: 'badge-success', text: '✓ Completed' },
      processing: { cls: 'badge-info', text: '⏳ Processing' },
      initiated: { cls: 'badge-info', text: '• Initiated' },
      blocked: { cls: 'badge-danger', text: '✗ Blocked' },
      failed: { cls: 'badge-danger', text: '✗ Failed' },
    };
    const m = map[status] || { cls: 'badge-info', text: status };
    return <span className={`badge ${m.cls}`}>{m.text}</span>;
  };

  if (loading) {
    return (
      <div className="card">
        <div className="card-header">
          <div className="card-title">Transaction History</div>
        </div>
        <div className="empty-state">
          <div className="spinner" style={{ margin: '0 auto' }} />
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="card">
        <div className="card-header">
          <div>
            <div className="card-title">Transaction History</div>
            <div className="card-subtitle">{total} total transactions</div>
          </div>
          <button className="btn btn-secondary" onClick={loadTransactions}>
            ↻ Refresh
          </button>
        </div>

        {transactions.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">📭</div>
            <p>No transactions yet. Try a voice command!</p>
          </div>
        ) : (
          <div className="txn-list">
            {transactions.map((txn) => {
              const icon = INTENT_ICONS[txn.intent] || '💳';
              const iconClass = txn.status === 'blocked' ? 'blocked' : txn.intent?.replace('_', '') || 'send';

              return (
                <div key={txn.id} className="txn-item" onClick={() => showDetail(txn.id)}>
                  <div className={`txn-icon ${iconClass}`}>{icon}</div>
                  <div className="txn-info">
                    <div className="txn-title">
                      {txn.intent?.replace(/_/g, ' ')?.replace(/\b\w/g, (c) => c.toUpperCase()) || 'Unknown'}
                    </div>
                    <div className="txn-desc">
                      {txn.recipient ? `To ${txn.recipient}` : txn.transcript?.slice(0, 40) || '—'}
                      {' • '}
                      {new Date(txn.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </div>
                  </div>
                  <div>
                    {txn.amount_inr > 0 && (
                      <div className="txn-amount">₹{txn.amount_inr}</div>
                    )}
                    <div className="txn-status">{getStatusBadge(txn.status)}</div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Detail Modal */}
      {selectedTxn && detail && (
        <div className="detail-overlay" onClick={(e) => e.target === e.currentTarget && setSelectedTxn(null)}>
          <div className="detail-modal">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
              <h2 style={{ fontSize: 'var(--font-xl)', fontWeight: 700 }}>Transaction #{detail.transaction.id}</h2>
              <button
                onClick={() => setSelectedTxn(null)}
                style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '1.5rem' }}
              >
                ✕
              </button>
            </div>

            <div className="detail-row">
              <span className="detail-label">Transcript</span>
              <span className="detail-value">"{detail.transaction.transcript}"</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Intent</span>
              <span className="detail-value">{detail.transaction.intent} ({(detail.transaction.intent_confidence * 100).toFixed(0)}%)</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Amount</span>
              <span className="detail-value" style={{ fontSize: 'var(--font-lg)' }}>₹{detail.transaction.amount_inr}</span>
            </div>
            {detail.transaction.recipient && (
              <div className="detail-row">
                <span className="detail-label">Recipient</span>
                <span className="detail-value">{detail.transaction.recipient}</span>
              </div>
            )}
            <div className="detail-row">
              <span className="detail-label">Risk</span>
              <span className="detail-value">
                <span className={`badge badge-${detail.transaction.risk_tier === 'Low' ? 'success' : detail.transaction.risk_tier === 'Medium' ? 'warning' : 'danger'}`}>
                  {detail.transaction.risk_tier} ({(detail.transaction.risk_score * 100).toFixed(0)}%)
                </span>
              </span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Auth Method</span>
              <span className="detail-value">{detail.transaction.auth_method}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Status</span>
              <span className="detail-value">{getStatusBadge(detail.transaction.status)}</span>
            </div>
            {detail.transaction.razorpay_payment_id && (
              <div className="detail-row">
                <span className="detail-label">Payment ID</span>
                <span className="detail-value" style={{ fontSize: 'var(--font-xs)' }}>
                  {detail.transaction.razorpay_payment_id}
                </span>
              </div>
            )}

            {/* Audit Trail */}
            {detail.audit_trail?.length > 0 && (
              <>
                <h3 style={{ fontSize: 'var(--font-sm)', fontWeight: 600, marginTop: '1.5rem', marginBottom: '0.75rem', color: 'var(--text-secondary)' }}>
                  Audit Trail
                </h3>
                {detail.audit_trail.map((log, i) => (
                  <div key={i} className="detail-row" style={{ fontSize: 'var(--font-xs)' }}>
                    <span className="detail-label">{log.event_type}</span>
                    <span className="detail-value" style={{ color: log.severity === 'warning' ? 'var(--warning)' : 'var(--text-secondary)' }}>
                      {log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : '—'}
                    </span>
                  </div>
                ))}
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}
