/**
 * Pipeline Visualizer — Shows only stages that actually ran.
 * For non-payment intents (check_balance, transaction_history, scan_qr),
 * only STT + SV + Intent stages appear. No empty Fraud/Auth rows.
 */

const STAGE_META = {
  stt: { icon: '🎙️', label: 'Speech Recognition' },
  speaker_verification: { icon: '🔐', label: 'Speaker Verification' },
  intent_classification: { icon: '🧠', label: 'Intent Classification' },
  fraud_detection: { icon: '🛡️', label: 'Fraud Detection' },
  auth_decision: { icon: '✅', label: 'Auth Decision' },
};

const ALL_STAGES = ['stt', 'speaker_verification', 'intent_classification', 'fraud_detection', 'auth_decision'];

export default function PipelineVisualizer({ stages, loading }) {
  // Determine which stages to display:
  // If we have completed stages, show those + the next one if loading.
  // Don't show stages that will never appear (for non-payment intents).
  const completedKeys = stages.map((s) => s.stage);
  const lastCompleted = completedKeys[completedKeys.length - 1];

  // Figure out how many stages to show
  let visibleStages;
  if (!loading && stages.length > 0) {
    // Pipeline done — only show stages that actually have data
    visibleStages = ALL_STAGES.filter((key) => completedKeys.includes(key));
  } else if (loading && stages.length === 0) {
    // Just started — show first stage as active
    visibleStages = ['stt'];
  } else if (loading) {
    // In progress — show completed + next stage as loading
    const lastIndex = ALL_STAGES.indexOf(lastCompleted);
    const nextIndex = lastIndex + 1;
    visibleStages = ALL_STAGES.slice(0, nextIndex + 1);
  } else {
    visibleStages = [];
  }

  if (visibleStages.length === 0 && !loading) {
    return (
      <div className="pipeline-container">
        <div className="empty-state" style={{ padding: '2rem 0' }}>
          <div className="empty-state-icon">🎙️</div>
          <p>Speak or type a command to see the pipeline in action.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="pipeline-container">
      {visibleStages.map((stageKey, i) => {
        const meta = STAGE_META[stageKey];
        const result = stages.find((s) => s.stage === stageKey);
        const isDone = !!result;
        const isActive = loading && !isDone && i === visibleStages.length - 1;
        const isSuccess = isDone && result.success;
        const isError = isDone && !result.success;

        let className = 'pipeline-stage animate-in';
        if (isActive) className += ' active';
        else if (isSuccess) className += ' success';
        else if (isError) className += ' error';

        return (
          <div key={stageKey} className={className} style={{ animationDelay: `${i * 0.08}s` }}>
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
  if (!data) return '—';
  switch (stage) {
    case 'stt':
      return `"${data.transcript}" (${(data.confidence * 100).toFixed(0)}% conf)`;
    case 'speaker_verification':
      return data.verified
        ? `✅ Verified (${(data.similarity_score * 100).toFixed(0)}% match)`
        : data.note === 'text_input_override'
        ? '⏭️ Bypassed (text input)'
        : data.note === 'no_audio_for_sv'
        ? '⏭️ Skipped (text input)'
        : `❌ Not verified (${((data.similarity_score || 0) * 100).toFixed(0)}%)`;
    case 'intent_classification': {
      const ent = data.entities || {};
      let s = `${data.intent} (${(data.confidence * 100).toFixed(0)}%)`;
      if (ent.amount) s += ` • ₹${ent.amount}`;
      if (ent.recipient) {
        s += ` → ${ent.recipient}`;
        if (data.contact_found === false) s += ' ⚠️ unknown';
      }
      if (ent.bill_type) s += ` • ${ent.bill_type}`;
      return s;
    }
    case 'fraud_detection':
      return `Risk: ${data.risk_tier} (${((data.risk_score || 0) * 100).toFixed(0)}%) ${data.anomaly_flags?.length ? '⚠️ ' + data.anomaly_flags.length + ' flags' : ''}`;
    case 'auth_decision':
      return data.proceed ? `${data.auth_required} → Proceed` : `🚫 Blocked`;
    default:
      return JSON.stringify(data).slice(0, 80);
  }
}
