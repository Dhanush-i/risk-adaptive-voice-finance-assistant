import { useState } from 'react';

const STAGE_META = {
  stt: { icon: '🎙️', label: 'Speech Recognition' },
  speaker_verification: { icon: '🔐', label: 'Speaker Verification' },
  intent_classification: { icon: '🧠', label: 'Intent Classification' },
  fraud_detection: { icon: '🛡️', label: 'Fraud Detection' },
  auth_decision: { icon: '✅', label: 'Auth Decision' },
};

export default function PipelineVisualizer({ stages, loading }) {
  const allStages = ['stt', 'speaker_verification', 'intent_classification', 'fraud_detection', 'auth_decision'];

  const completedStages = stages.map((s) => s.stage);
  const currentIndex = completedStages.length;

  return (
    <div className="pipeline-container">
      {allStages.map((stageKey, i) => {
        const meta = STAGE_META[stageKey];
        const result = stages.find((s) => s.stage === stageKey);
        const isActive = loading && i === currentIndex;
        const isDone = !!result;
        const isSuccess = isDone && result.success;
        const isError = isDone && !result.success;

        let className = 'pipeline-stage';
        if (isActive) className += ' active';
        else if (isSuccess) className += ' success';
        else if (isError) className += ' error';

        return (
          <div key={stageKey} className={className} style={{ animationDelay: `${i * 0.1}s` }}>
            <div className="stage-icon">
              {isActive ? (
                <div className="spinner" />
              ) : isSuccess ? (
                '✓'
              ) : isError ? (
                '✗'
              ) : (
                meta.icon
              )}
            </div>
            <div className="stage-content">
              <div className="stage-name">{meta.label}</div>
              <div className="stage-detail">
                {isActive && 'Processing...'}
                {isSuccess && formatStageResult(stageKey, result.data)}
                {isError && (result.data?.error || 'Failed')}
                {!isActive && !isDone && '—'}
              </div>
            </div>
            {isDone && result.duration_ms > 0 && (
              <span className="stage-time">{result.duration_ms.toFixed(0)}ms</span>
            )}
          </div>
        );
      })}
    </div>
  );
}

function formatStageResult(stage, data) {
  switch (stage) {
    case 'stt':
      return `"${data.transcript}" (${(data.confidence * 100).toFixed(0)}% conf)`;
    case 'speaker_verification':
      return data.verified
        ? `✅ Verified (${(data.similarity_score * 100).toFixed(0)}% match)`
        : data.note === 'text_input_override'
        ? '⏭️ Bypassed (text input)'
        : `❌ Not verified (${(data.similarity_score * 100).toFixed(0)}%)`;
    case 'intent_classification': {
      const ent = data.entities || {};
      let s = `${data.intent} (${(data.confidence * 100).toFixed(0)}%)`;
      if (ent.amount) s += ` • ₹${ent.amount}`;
      if (ent.recipient) s += ` → ${ent.recipient}`;
      if (ent.bill_type) s += ` • ${ent.bill_type}`;
      return s;
    }
    case 'fraud_detection':
      return `Risk: ${data.risk_tier} (${(data.risk_score * 100).toFixed(0)}%) ${data.anomaly_flags?.length ? '⚠️ ' + data.anomaly_flags.length + ' flags' : ''}`;
    case 'auth_decision':
      return data.proceed ? `${data.auth_required} → Proceed` : `🚫 Blocked`;
    default:
      return JSON.stringify(data).slice(0, 80);
  }
}
