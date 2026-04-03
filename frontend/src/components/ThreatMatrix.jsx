import React from 'react';

export default function ThreatMatrix({ authDecision }) {
  if (!authDecision || !authDecision.details) return null;

  const { risk_tier, details } = authDecision;
  const { risk_score, anomaly_flags } = details;

  const getRiskColor = (tier) => {
    switch (tier?.toLowerCase()) {
      case 'low': return 'var(--success)';
      case 'medium': return 'var(--warning)';
      case 'high': return 'var(--danger)';
      default: return 'var(--text-muted)';
    }
  };

  const getRiskBadge = (tier) => {
    switch (tier?.toLowerCase()) {
      case 'low': return 'badge-success';
      case 'medium': return 'badge-warning';
      case 'high': return 'badge-danger';
      default: return 'badge-info';
    }
  };

  const riskColor = getRiskColor(risk_tier);
  const percentage = Math.min(100, Math.max(0, (risk_score || 0) * 100));

  return (
    <div className="threat-matrix">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
        <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: 'var(--font-sm)', fontWeight: 600 }}>
          <span style={{ fontSize: '1rem' }}>🔍</span> Explainable AI Insight
        </h3>
        <span className={`badge ${getRiskBadge(risk_tier)}`}>
          {risk_tier} RISK
        </span>
      </div>

      {/* Risk Score Bar */}
      <div style={{ marginBottom: '1.25rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--font-xs)', color: 'var(--text-muted)', marginBottom: '0.4rem' }}>
          <span>Threat Confidence Score</span>
          <span style={{ fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>{percentage.toFixed(1)}%</span>
        </div>
        <div style={{ height: '6px', background: 'rgba(255,255,255,0.04)', borderRadius: '3px', overflow: 'hidden' }}>
          <div style={{
            height: '100%',
            width: `${percentage}%`,
            background: `linear-gradient(90deg, ${riskColor}, ${riskColor}aa)`,
            borderRadius: '3px',
            transition: 'width 0.8s cubic-bezier(0.16, 1, 0.3, 1)',
          }} />
        </div>
      </div>

      {/* Anomaly Flags */}
      <div>
        <h4 style={{ margin: '0 0 0.6rem 0', fontSize: 'var(--font-xs)', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          Detected Anomalies
        </h4>
        {anomaly_flags && anomaly_flags.length > 0 ? (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
            {anomaly_flags.map((flag, i) => {
              const isSpoof = flag.includes('SPOOF');
              const isSV = flag.includes('SV_MISMATCH');

              let icon = '⚡';
              let badgeCls = 'badge-warning';
              if (isSpoof) { icon = '🤖'; badgeCls = 'badge-danger'; }
              if (isSV) { icon = '🗣️'; badgeCls = 'badge-danger'; }

              return (
                <span key={i} className={`badge ${badgeCls}`}>
                  {icon} {flag}
                </span>
              );
            })}
          </div>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <span className="badge badge-success">✅ No anomalies detected</span>
          </div>
        )}
      </div>
    </div>
  );
}
