import React, { useState, useEffect } from 'react';
import { useAudioRecorder } from '../hooks/useAudioRecorder';
import { enrollSpeaker } from '../utils/api';
import { VoiceLines } from '../utils/voiceFeedback';

const PHRASES = [
  "My voice is my secure password.",
  "Transfer five hundred rupees to Rahul.",
  "Authentication required for this transaction."
];

export default function VoiceEnrollment({ userId, isEnrolled, onComplete, onCancel }) {
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
      VoiceLines.enrollSampleRecorded(step + 1, 3);
      setStep(step + 1);
    } else {
      // Finished 3 phrases, submit to backend
      setStep(3);
      setLoading(true);
      try {
        await enrollSpeaker(newBlobs, userId);
        setLoading(false);
        VoiceLines.enrollSuccess();
        if (onComplete) onComplete();
      } catch (e) {
        setError(e.message || 'Enrollment failed');
        VoiceLines.enrollFailed();
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

  const handleCancel = () => {
    // Stop any active recording
    if (isRecording) {
      stopRecording();
    }
    resetAudio();
    if (onCancel) onCancel();
  };

  return (
    <div className="enrollment-page">
      <div className="enrollment-card animate-in">
        {/* Enrolled status badge */}
        <div className="enrollment-status">
          {isEnrolled ? (
            <span className="badge badge-success">✅ Voice Enrolled</span>
          ) : (
            <span className="badge badge-warning">⚠️ Not Enrolled</span>
          )}
        </div>

        <h2 className="section-title" style={{ textAlign: 'center' }}>Voice Enrollment</h2>
        <p className="section-subtitle" style={{ textAlign: 'center' }}>
          {isEnrolled
            ? 'Your voice is already enrolled. Re-enroll to update your voice profile.'
            : 'Read 3 phrases aloud to create your unique voice profile.'}
        </p>

        {step < 3 ? (
          <>
            {/* Progress indicator */}
            <div className="enrollment-progress">
              {PHRASES.map((_, i) => (
                <div
                  key={i}
                  className={`enrollment-dot ${i < step ? 'done' : i === step ? 'active' : ''}`}
                />
              ))}
            </div>

            {/* Current phrase */}
            <div className="enrollment-phrase-card">
              <div className="enrollment-step-label">Phrase {step + 1} of 3</div>
              <p className="enrollment-phrase">"{PHRASES[step]}"</p>
            </div>

            {/* Mic */}
            <div className="mic-container" style={{ marginTop: '1.5rem' }}>
              <button
                className={`mic-btn ${isRecording ? 'recording' : ''}`}
                onClick={handleRecordClick}
                disabled={loading}
                id="enroll-mic-btn"
              >
                <span className="mic-icon">{isRecording ? '⏹️' : '🎙️'}</span>
                {isRecording && <div className="mic-pulse" />}
              </button>
            </div>

            <p className="mic-label" style={{ textAlign: 'center' }}>
              {isRecording ? 'Listening... stops automatically when done' : 'Tap to start recording'}
            </p>
          </>
        ) : (
          <div style={{ textAlign: 'center', padding: '2rem 0' }}>
            {loading ? (
              <>
                <div className="spinner" style={{ margin: '0 auto', width: '40px', height: '40px', marginBottom: '1rem' }} />
                <p style={{ color: 'var(--text-muted)' }}>Generating voice print...</p>
              </>
            ) : null}
          </div>
        )}

        {error && (
          <div className="login-error" style={{ marginTop: '1rem' }}>
            {error}
          </div>
        )}

        {/* Cancel button — always visible and always works */}
        <button
          className="btn btn-ghost"
          style={{ width: '100%', marginTop: '1.5rem' }}
          onClick={handleCancel}
          id="enroll-cancel-btn"
        >
          ← Back to Pay
        </button>
      </div>
    </div>
  );
}
