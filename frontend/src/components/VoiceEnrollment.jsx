import React, { useState, useEffect } from 'react';
import { useAudioRecorder } from '../hooks/useAudioRecorder';
import { enrollSpeaker } from '../utils/api';

const PHRASES = [
  "My voice is my secure password.",
  "Transfer five hundred rupees to Rahul.",
  "Authentication required for this transaction."
];

export default function VoiceEnrollment({ userId, onComplete, onCancel }) {
  const [step, setStep] = useState(0); // 0, 1, 2 = recording phrases, 3 = submitting
  const [blobs, setBlobs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const { isRecording, audioBlob, startRecording, stopRecording, resetAudio } = useAudioRecorder();

  // Watch for audio completion from hook
  useEffect(() => {
    if (audioBlob) {
      handleNextPhase(audioBlob);
    }
  }, [audioBlob]);

  const handleNextPhase = async (blob) => {
    const newBlobs = [...blobs, blob];
    setBlobs(newBlobs);
    resetAudio();

    if (step < 2) {
      setStep(step + 1);
    } else {
      // Finished 3 phrases, submit to backend
      setStep(3);
      setLoading(true);
      try {
        await enrollSpeaker(newBlobs, userId);
        setLoading(false);
        onComplete();
      } catch (e) {
        setError(e.message || 'Enrollment failed');
        setLoading(false);
        setStep(0);
        setBlobs([]);
      }
    }
  };

  const handleRecordClick = async () => {
    if (isRecording) {
      stopRecording();
    } else {
      setError(null);
      await startRecording();
    }
  };

  return (
    <div className="pin-overlay">
      <div className="pin-modal animate-in">
        <h2 style={{ marginBottom: '5px', textAlign: 'center' }}>Voice Enrollment</h2>
        
        {step < 3 ? (
          <>
            <p style={{ textAlign: 'center', color: 'var(--text-muted)', marginBottom: 'var(--space-lg)' }}>
              Read the phrases aloud to lock your account with your voice. ({step + 1}/3)
            </p>

            <div style={{
              background: 'rgba(255,255,255,0.05)', borderRadius: '12px',
              padding: '1.5rem', textAlign: 'center', margin: '1.5rem 0 2rem 0',
              border: '1px solid var(--border)'
            }}>
              <p style={{ fontSize: '1.25rem', fontWeight: '600', color: 'var(--text-main)' }}>"{PHRASES[step]}"</p>
            </div>

            <div className="mic-container">
              <button
                className={`mic-btn ${isRecording ? 'recording' : ''}`}
                onClick={handleRecordClick}
              >
                {isRecording ? '⏹' : '🎙️'}
              </button>
            </div>

            <p style={{ textAlign: 'center', color: 'var(--text-secondary)' }}>
              {isRecording ? 'Listening...' : 'Click to start recording'}
            </p>
          </>
        ) : (
          <div style={{ textAlign: 'center', padding: 'var(--space-xl) 0' }}>
            {loading ? (
              <>
                <div className="spinner" style={{ margin: '0 auto', width: '40px', height: '40px', marginBottom: 'var(--space-md)' }} />
                <p>Generating Voice Print...</p>
              </>
            ) : null}
          </div>
        )}

        {error && <div className="error-message">{error}</div>}

        <button 
          className="btn btn-secondary" 
          style={{ width: '100%', marginTop: 'var(--space-lg)' }} 
          onClick={onCancel}
          disabled={loading}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
