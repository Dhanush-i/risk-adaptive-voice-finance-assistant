import { useState, useEffect, useRef } from 'react';

/**
 * QR Scanner Modal — Opens the device camera for QR code scanning.
 *
 * Shows live camera feed and a "Simulate Scan" button for the demo.
 * Falls back gracefully if camera is unavailable (e.g., desktop without webcam).
 * On mobile, prefers the rear camera via facingMode: 'environment'.
 */

const DEMO_UPI_IDS = [
  'ravi@ybl',
  'shop.grocery@paytm',
  'electricboard.tn@sbi',
  'merchant.cafe@okaxis',
];

export default function QRScannerModal({ onClose, onScan }) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const [cameraReady, setCameraReady] = useState(false);
  const [cameraError, setCameraError] = useState(null);
  const [scanning, setScanning] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function startCamera() {
      // Try rear camera first (mobile), then fall back to any camera (desktop)
      const constraints = [
        { video: { facingMode: 'environment' }, audio: false },
        { video: { facingMode: 'user' }, audio: false },
        { video: true, audio: false },
      ];

      let stream = null;
      let lastErr = null;

      for (const constraint of constraints) {
        try {
          stream = await navigator.mediaDevices.getUserMedia(constraint);
          break; // Success — stop trying
        } catch (err) {
          lastErr = err;
          continue; // Try next constraint
        }
      }

      if (cancelled) {
        if (stream) stream.getTracks().forEach((t) => t.stop());
        return;
      }

      if (!stream) {
        // All constraints failed
        setCameraError(
          lastErr?.name === 'NotAllowedError'
            ? 'Camera permission denied. Please allow camera access in your browser settings.'
            : lastErr?.name === 'NotFoundError'
            ? 'No camera found on this device. You can still use "Simulate QR Scan" below.'
            : `Could not access camera: ${lastErr?.message || 'Unknown error'}. You can still simulate a scan below.`
        );
        return;
      }

      streamRef.current = stream;

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play().catch(() => {});
      }

      setCameraReady(true);
    }

    startCamera();

    return () => {
      cancelled = true;
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
      }
    };
  }, []);

  const handleSimulateScan = () => {
    setScanning(true);
    setTimeout(() => {
      const randomUPI = DEMO_UPI_IDS[Math.floor(Math.random() * DEMO_UPI_IDS.length)];
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
      }
      onScan(randomUPI);
    }, 1200);
  };

  const handleClose = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
    }
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && handleClose()}>
      <div className="qr-modal animate-in">
        <div className="qr-header">
          <h2>📷 Scan QR Code</h2>
          <button className="modal-close-btn" onClick={handleClose}>✕</button>
        </div>

        <div className="qr-viewfinder">
          {cameraError ? (
            <div className="qr-error">
              <div className="empty-state-icon">📷</div>
              <p>{cameraError}</p>
            </div>
          ) : !cameraReady ? (
            <div className="qr-error">
              <div className="spinner" />
              <p>Starting camera...</p>
            </div>
          ) : (
            <>
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className="qr-video"
              />
              {cameraReady && !scanning && (
                <div className="qr-overlay">
                  <div className="qr-corners" />
                </div>
              )}
              {scanning && (
                <div className="qr-scanning">
                  <div className="spinner" />
                  <p>Decoding QR...</p>
                </div>
              )}
            </>
          )}
        </div>

        <p className="qr-hint">
          {cameraReady
            ? 'Point your camera at a UPI QR code to scan it.'
            : 'Click "Simulate QR Scan" to test the payment flow.'}
        </p>

        <div className="qr-actions">
          {/* Always show the simulate button — camera or not */}
          {!scanning && (
            <button
              className="btn btn-primary"
              onClick={handleSimulateScan}
              id="simulate-scan-btn"
            >
              {cameraReady ? 'Simulate QR Scan (Demo)' : '📷 Simulate QR Scan'}
            </button>
          )}
          <button
            className="btn btn-ghost"
            onClick={handleClose}
            id="close-scanner-btn"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
