import { useState, useRef, useCallback, useEffect } from 'react';

export function useAudioRecorder() {
  const [isRecording, setIsRecording] = useState(false);
  const [audioBlob, setAudioBlob] = useState(null);
  
  const mediaRecorder = useRef(null);
  const chunks = useRef([]);
  const audioContext = useRef(null);
  const animationFrameId = useRef(null);
  
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

      // --- Silence Detection Setup ---
      audioContext.current = new (window.AudioContext || window.webkitAudioContext)();
      const analyser = audioContext.current.createAnalyser();
      const source = audioContext.current.createMediaStreamSource(stream);
      source.connect(analyser);
      
      analyser.fftSize = 512;
      const bufferLength = analyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);
      
      let lastSoundTime = Date.now();
      let hasStartedSpeaking = false;

      const detectSilence = () => {
        if (!isRecordingRef.current) return;
        
        analyser.getByteFrequencyData(dataArray);
        
        let sum = 0;
        for (let i = 0; i < bufferLength; i++) {
          sum += dataArray[i];
        }
        const averageVolume = sum / bufferLength;

        const now = Date.now();
        
        // Define a threshold indicating speech vs background noise
        if (averageVolume > 10) { 
          hasStartedSpeaking = true;
          lastSoundTime = now;
        }

        // Auto-stop logic:
        // 1. If they started speaking and paused for 2.5s
        if (hasStartedSpeaking && (now - lastSoundTime > 2500)) {
          stopRecordingRef.current();
          return;
        }
        
        // 2. Timeout if they never spoke for 8s
        if (!hasStartedSpeaking && (now - lastSoundTime > 8000)) {
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
