import React, { useState, useEffect } from 'react';
import { useAudioRecorder } from '../hooks/useAudioRecorder';
import { verifySpeaker } from '../utils/api';

const MAX_ATTEMPTS = 3;

export default function StepUpAuth({ userId, onSuccess, onCancel }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [attempts, setAttempts] = useState(0);

  const phrase = "I authorize this protected transaction.";

  const { isRecording, audioBlob, startRecording, stopRecording, resetAudio } = useAudioRecorder();

  useEffect(() => {
    if (audioBlob) {
      handleVerification(audioBlob);
    }
  }, [audioBlob]);

  const handleVerification = async (blob) => {
    setLoading(true);
    try {
      const result = await verifySpeaker(blob, userId);
      setLoading(false);
      resetAudio();

      if (result.verified) {
        onSuccess();
      } else {
        const newAttempts = attempts + 1;
        setAttempts(newAttempts);

        if (newAttempts >= MAX_ATTEMPTS) {
          setError(`Voice verification failed ${MAX_ATTEMPTS} times. Transaction cancelled for security.`);
          setTimeout(() => onCancel(), 2500);
        } else {
          setError(
            `Voice mismatch (${(result.similarity_score * 100).toFixed(0)}% similarity). ` +
            `${MAX_ATTEMPTS - newAttempts} attempt${MAX_ATTEMPTS - newAttempts > 1 ? 's' : ''} remaining.`
          );
        }
      }
    } catch (e) {
      setError(e.message || 'Verification failed');
      setLoading(false);
      resetAudio();
    }
  };

  const handleRecordClick = async () => {
    if (attempts >= MAX_ATTEMPTS) return;
    if (isRecording) {
      stopRecording();
    } else {
      setError(null);
      await startRecording();
    }
  };

  const isLocked = attempts >= MAX_ATTEMPTS;

  return (
    <div className="pin-overlay">
      <div className="pin-modal animate-in" style={{ border: '1px solid var(--warning)', maxWidth: '420px' }}>
        <div style={{ textAlign: 'center', marginBottom: '0.75rem' }}>
          <span style={{ fontSize: '2.5rem' }}>{isLocked ? '🔒' : '⚠️'}</span>
        </div>
        <h2 style={{ marginBottom: '5px', textAlign: 'center', fontSize: 'var(--font-xl)' }}>
          {isLocked ? 'Transaction Cancelled' : 'Security Step-Up Required'}
        </h2>

        {!isLocked && (
          <div style={{ color: 'var(--warning)', fontSize: 'var(--font-xs)', marginBottom: '1rem', textAlign: 'center' }}>
            <strong>Reason:</strong> Transaction flagged as Medium Risk by Fraud Engine.
          </div>
        )}

        {!isLocked ? (
          <>
            <p style={{ textAlign: 'center', color: 'var(--text-muted)', marginBottom: 'var(--space-lg)', fontSize: 'var(--font-sm)' }}>
              This transaction requires voice re-confirmation. Please read the phrase below.
            </p>

            <div style={{
              background: 'rgba(255,255,255,0.03)', borderRadius: 'var(--radius)',
              padding: '1rem 1.25rem', textAlign: 'center', marginBottom: 'var(--space-lg)',
              border: '1px solid var(--border-hover)'
            }}>
              <p style={{ fontSize: '1.1rem', fontWeight: 700, letterSpacing: '-0.01em' }}>"{phrase}"</p>
            </div>

            {/* Attempt counter */}
            <div style={{
              display: 'flex', justifyContent: 'center', gap: '0.4rem', marginBottom: 'var(--space-md)'
            }}>
              {[...Array(MAX_ATTEMPTS)].map((_, i) => (
                <div key={i} style={{
                  width: '8px', height: '8px', borderRadius: '50%',
                  background: i < attempts ? 'var(--danger)' : 'rgba(255,255,255,0.1)',
                  transition: 'background 0.3s',
                }} />
              ))}
            </div>

            {loading ? (
              <div style={{ textAlign: 'center', padding: 'var(--space-lg) 0' }}>
                <div className="spinner" style={{ margin: '0 auto', width: '28px', height: '28px', marginBottom: 'var(--space-md)' }} />
                <p style={{ color: 'var(--text-muted)', fontSize: 'var(--font-sm)' }}>Analyzing voice print...</p>
              </div>
            ) : (
              <>
                <div className="mic-container" style={{ margin: 'var(--space-lg) auto', height: '100px' }}>
                  <button
                    className={`mic-btn ${isRecording ? 'recording' : ''}`}
                    onClick={handleRecordClick}
                    style={{ width: '72px', height: '72px', minWidth: '72px', minHeight: '72px', fontSize: '1.5rem' }}
                  >
                    {isRecording ? '⏹' : '🎙️'}
                  </button>
                </div>

                <p style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: 'var(--font-sm)' }}>
                  {isRecording ? 'Listening...' : 'Click to verify voice'}
                </p>
              </>
            )}
          </>
        ) : (
          <p style={{ textAlign: 'center', color: 'var(--text-muted)', marginTop: '1rem', fontSize: 'var(--font-sm)' }}>
            Too many failed voice verification attempts. Redirecting...
          </p>
        )}

        {error && (
          <div style={{
            marginTop: 'var(--space-md)',
            padding: '0.6rem 1rem',
            borderRadius: 'var(--radius-sm)',
            fontSize: 'var(--font-xs)',
            background: isLocked ? 'var(--danger-bg)' : 'var(--warning-bg)',
            color: isLocked ? 'var(--danger)' : 'var(--warning)',
            border: `1px solid ${isLocked ? 'var(--danger-border)' : 'var(--warning-border)'}`,
            textAlign: 'center',
          }}>
            {error}
          </div>
        )}

        {!isLocked && (
          <button
            className="btn btn-secondary"
            style={{ width: '100%', marginTop: 'var(--space-lg)' }}
            onClick={onCancel}
            disabled={loading}
          >
            Cancel Payment
          </button>
        )}
      </div>
    </div>
  );
}
