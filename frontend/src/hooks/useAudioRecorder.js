import { useState, useRef, useCallback, useEffect } from 'react';

export function useAudioRecorder() {
  const [isRecording, setIsRecording] = useState(false);
  const [audioBlob, setAudioBlob] = useState(null);
  
  const mediaRecorder = useRef(null);
  const chunks = useRef([]);
  const audioContext = useRef(null);
  const animationFrameId = useRef(null);
  const recordingStartTime = useRef(null);
  
  // Refs to use inside the animation frame loop
  const stopRecordingRef = useRef(null);
  const isRecordingRef = useRef(false);

  const stopRecording = useCallback(() => {
    isRecordingRef.current = false;
    if (mediaRecorder.current && mediaRecorder.current.state !== 'inactive') {
      mediaRecorder.current.stop();
      setIsRecording(false);
    }
    if (animationFrameId.current) {
      cancelAnimationFrame(animationFrameId.current);
    }
  }, []);

  // Update the ref whenever stopRecording changes
  stopRecordingRef.current = stopRecording;

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder.current = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      chunks.current = [];
      recordingStartTime.current = Date.now();

      // --- Silence Detection Setup ---
      audioContext.current = new (window.AudioContext || window.webkitAudioContext)();
      const analyser = audioContext.current.createAnalyser();
      const source = audioContext.current.createMediaStreamSource(stream);
      source.connect(analyser);
      
      analyser.fftSize = 1024;
      const bufferLength = analyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);
      
      let lastSoundTime = Date.now();
      let hasStartedSpeaking = false;
      let speechFrameCount = 0; // Require multiple consecutive loud frames

      const MAX_RECORDING_MS = 12000;    // Hard cap: 12 seconds
      const SILENCE_AFTER_SPEECH_MS = 2000; // 2s silence after speech
      const NO_SPEECH_TIMEOUT_MS = 6000;   // 6s if user never speaks
      const SPEECH_THRESHOLD_AVG = 25;     // Average volume threshold
      const SPEECH_THRESHOLD_MAX = 90;     // Max frequency threshold
      const SPEECH_CONFIRM_FRAMES = 3;     // Must see 3 loud frames to confirm speech

      const detectSilence = () => {
        if (!isRecordingRef.current) return;
        
        analyser.getByteFrequencyData(dataArray);
        
        // Compute average and max volume
        let sum = 0;
        let maxVol = 0;
        for (let i = 0; i < bufferLength; i++) {
          sum += dataArray[i];
          if (dataArray[i] > maxVol) maxVol = dataArray[i];
        }
        const avgVol = sum / bufferLength;

        const now = Date.now();
        const elapsed = now - recordingStartTime.current;
        
        // Hard cap: stop after MAX_RECORDING_MS regardless
        if (elapsed > MAX_RECORDING_MS) {
          console.log('[Audio] Max recording time reached, auto-stopping.');
          stopRecordingRef.current();
          return;
        }

        // Check if current frame is speech
        const isSpeechFrame = avgVol > SPEECH_THRESHOLD_AVG || maxVol > SPEECH_THRESHOLD_MAX;

        if (isSpeechFrame) {
          speechFrameCount++;
          if (speechFrameCount >= SPEECH_CONFIRM_FRAMES) {
            hasStartedSpeaking = true;
          }
          lastSoundTime = now;
        } else {
          speechFrameCount = Math.max(0, speechFrameCount - 1); // Decay slowly
        }

        // Auto-stop conditions:
        // 1. Started speaking, then quiet for SILENCE_AFTER_SPEECH_MS
        if (hasStartedSpeaking && (now - lastSoundTime > SILENCE_AFTER_SPEECH_MS)) {
          console.log('[Audio] Silence detected after speech, auto-stopping.');
          stopRecordingRef.current();
          return;
        }
        
        // 2. Never spoke for NO_SPEECH_TIMEOUT_MS
        if (!hasStartedSpeaking && elapsed > NO_SPEECH_TIMEOUT_MS) {
          console.log('[Audio] No speech detected, auto-stopping.');
          stopRecordingRef.current();
          return;
        }

        animationFrameId.current = requestAnimationFrame(detectSilence);
      };

      mediaRecorder.current.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.current.push(e.data);
      };

      mediaRecorder.current.onstop = () => {
        const blob = new Blob(chunks.current, { type: 'audio/webm' });
        setAudioBlob(blob);
        stream.getTracks().forEach((t) => t.stop());
        
        if (audioContext.current && audioContext.current.state !== 'closed') {
          audioContext.current.close().catch(console.error);
        }
      };

      mediaRecorder.current.start();
      setIsRecording(true);
      isRecordingRef.current = true;
      
      // Start checking for silence
      detectSilence();
      
    } catch (err) {
      console.error('Mic access denied:', err);
      throw new Error('Microphone access denied. Please allow microphone access.');
    }
  }, []);

  const resetAudio = useCallback(() => {
    setAudioBlob(null);
    chunks.current = [];
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      isRecordingRef.current = false;
      if (animationFrameId.current) cancelAnimationFrame(animationFrameId.current);
      if (audioContext.current && audioContext.current.state !== 'closed') {
        audioContext.current.close().catch(() => {});
      }
    };
  }, []);

  return { isRecording, audioBlob, startRecording, stopRecording, resetAudio };
}
