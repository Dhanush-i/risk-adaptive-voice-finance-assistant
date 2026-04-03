import { useState, useEffect, useCallback } from 'react';
import PipelineVisualizer from './components/PipelineVisualizer';
import PinPad from './components/PinPad';
import TransactionHistory from './components/TransactionHistory';
import VoiceEnrollment from './components/VoiceEnrollment';
import StepUpAuth from './components/StepUpAuth';
import BalanceDisplay from './components/BalanceDisplay';
import ThreatMatrix from './components/ThreatMatrix';
import { useAudioRecorder } from './hooks/useAudioRecorder';
import {
  getUser, getBalance, processTextCommand, processVoiceCommand,
  verifyPin, createOrder, verifyPayment, openRazorpayCheckout,
} from './utils/api';
import './index.css';

export default function App() {
  // Fixed User ID
  const USER_ID = 'demo_user';

  // State
  const [page, setPage] = useState('home');
  const [user, setUser] = useState(null);
  const [balance, setBalance] = useState(0);

  // Voice/Text input
  const [textInput, setTextInput] = useState('');
  const [processing, setProcessing] = useState(false);
  const [pipelineResult, setPipelineResult] = useState(null);
  const [stages, setStages] = useState([]);
  const [statusMessage, setStatusMessage] = useState('');

  // PIN & Payment
  const [showPin, setShowPin] = useState(false);
  const [showStepUp, setShowStepUp] = useState(false);
  const [showEnrollment, setShowEnrollment] = useState(false);
  const [showBalance, setShowBalance] = useState(false);
  const [pinLoading, setPinLoading] = useState(false);
  const [paymentStatus, setPaymentStatus] = useState(null); // null, 'success', 'failed'
  const [paymentMessage, setPaymentMessage] = useState('');

  // Refresh key for transaction list
  const [refreshKey, setRefreshKey] = useState(0);

  // Audio recorder
  const { isRecording, audioBlob, startRecording, stopRecording, resetAudio } = useAudioRecorder();

  const loadUser = useCallback(async () => {
    try {
      const u = await getUser(USER_ID);
      setUser(u);
      const b = await getBalance(USER_ID);
      setBalance(b.balance);
    } catch (e) {
      console.error('Failed to load user:', e);
    }
  }, []);

  // Reload data for the fixed user
  useEffect(() => {
    loadUser();
  }, [loadUser, refreshKey]);

  // Auto-process audio when recording stops
  useEffect(() => {
    if (audioBlob && !processing) {
      handleVoiceProcess(audioBlob);
    }
  }, [audioBlob]);

  const resetPipeline = () => {
    setPipelineResult(null);
    setStages([]);
    setStatusMessage('');
    setShowPin(false);
    setShowStepUp(false);
    setShowBalance(false);
    setPaymentStatus(null);
    setPaymentMessage('');
    resetAudio();
  };

  // --- Voice Processing ---
  const handleMicClick = async () => {
    if (isRecording) {
      stopRecording();
    } else {
      resetPipeline();
      try {
        await startRecording();
      } catch (e) {
        setStatusMessage(e.message);
      }
    }
  };

  const handleVoiceProcess = async (blob) => {
    setProcessing(true);
    setPage('home');
    setStatusMessage('Processing voice command...');

    try {
      const result = await processVoiceCommand(blob, USER_ID);
      handlePipelineResult(result);
    } catch (e) {
      setStatusMessage(`Error: ${e.message}`);
    }
    setProcessing(false);
  };

  // --- Text Processing ---
  const handleTextSubmit = async (e) => {
    e.preventDefault();
    if (!textInput.trim() || processing) return;

    resetPipeline();
    setProcessing(true);
    setStatusMessage('Processing command...');

    try {
      const result = await processTextCommand(textInput, USER_ID);
      handlePipelineResult(result);
      setTextInput('');
    } catch (e) {
      setStatusMessage(`Error: ${e.message}`);
    }
    setProcessing(false);
  };

  const handlePipelineResult = (result) => {
    setPipelineResult(result);
    setStages(result.stages || []);

    const auth = result.auth_decision;
    const intent = result.stages?.find((s) => s.stage === 'intent_classification')?.data?.intent;

    if (intent === 'transaction_history') {
      setPage('history');
      return;
    }

    if (intent === 'check_balance') {
      setShowBalance(true);
      return;
    }

    if (auth?.proceed) {
      setStatusMessage('');
      // Show appropriate auth UI for payment intents
      if (intent === 'send_money' || intent === 'pay_bill') {
        if (auth.auth_required === 'step_up') {
          setShowStepUp(true);
        } else {
          setShowPin(true);
        }
      } else {
        setStatusMessage(auth.message);
      }
    } else {
      setStatusMessage(auth?.message || 'Transaction blocked.');
    }
  };

  // --- PIN Verification & Payment ---
  const handlePinSubmit = async (pin) => {
    setPinLoading(true);
    try {
      const pinResult = await verifyPin(USER_ID, pin, pipelineResult.transaction_id);
      if (!pinResult.success) {
        throw new Error(pinResult.message || 'Invalid PIN');
      }

      setShowPin(false);
      setStatusMessage('PIN verified! Creating payment...');

      // Create Razorpay order
      try {
        const order = await createOrder(pipelineResult.transaction_id, USER_ID);
        setStatusMessage('Opening Razorpay Checkout...');

        // Open Razorpay checkout
        openRazorpayCheckout(
          order,
          async (paymentData) => {
            // Payment success — verify on server
            setStatusMessage('Verifying payment...');
            try {
              const verification = await verifyPayment(paymentData);
              if (verification.success) {
                setPaymentStatus('success');
                setPaymentMessage(`Payment of ₹${verification.amount_inr} completed! 🎉`);
                
                // Cashback Reward (₹1-₹5)
                const reward = Math.floor(Math.random() * 5) + 1;
                setTimeout(() => {
                  setPaymentMessage(prev => prev + ` \nPlus ₹${reward} Voice Cashback earned! 🎊`);
                  loadUser(); // Refresh balance
                }, 1500);

                setRefreshKey((k) => k + 1);
              } else {
                setPaymentStatus('failed');
                setPaymentMessage(verification.message);
              }
            } catch (e) {
              setPaymentStatus('failed');
              setPaymentMessage(`Verification error: ${e.message}`);
            }
          },
          (errorMsg) => {
            setPaymentStatus('failed');
            setPaymentMessage(errorMsg || 'Payment cancelled');
          }
        );
      } catch (e) {
        setStatusMessage(`Razorpay error: ${e.message}`);
        setPaymentStatus('failed');
        setPaymentMessage(e.message);
      }
    } catch (e) {
      setPinLoading(false);
      throw e; // Let PinPad handle the error
    }
    setPinLoading(false);
  };

  // --- Get transaction amount & recipient from pipeline result ---
  const getAmount = () => {
    const intentStage = pipelineResult?.stages?.find((s) => s.stage === 'intent_classification');
    return intentStage?.data?.entities?.amount || 0;
  };

  const getRecipient = () => {
    const intentStage = pipelineResult?.stages?.find((s) => s.stage === 'intent_classification');
    return intentStage?.data?.entities?.recipient || '';
  };

  return (
    <div className="app-layout">
      {/* Header Profile Bar */}
      <header className="app-header">
        <div className="app-logo">
          <span className="app-logo-icon">🎙️</span> VoicePay
        </div>

        <nav className="app-nav">
          <button
            className={`app-nav-btn ${page === 'home' ? 'active' : ''}`}
            onClick={() => setPage('home')}
          >
            🏠 Home
          </button>
          <button
            className={`app-nav-btn ${page === 'history' ? 'active' : ''}`}
            onClick={() => setPage('history')}
          >
            📋 History
          </button>
        </nav>

        {user && (
          <div className="user-bar">
            <div>
              <div className="user-name">{user.display_name}</div>
              <div className="user-balance">₹{balance.toLocaleString('en-IN')}</div>
            </div>
            <div className="user-avatar" onClick={() => setShowEnrollment(true)} style={{ cursor: 'pointer', background: user.speaker_enrolled ? 'var(--primary)' : 'var(--warning)' }} title={user.speaker_enrolled ? 'Voice Profile Active' : 'Click to Enroll Voice'}>
              {user.display_name?.charAt(0).toUpperCase()}
            </div>
          </div>
        )}
      </header>

      {/* Main Content */}
      <main className="app-main">
        {page === 'home' && (
          <>
            {/* Hero / Voice Section */}
            <section className="voice-section animate-in">
              <h1 className="voice-title">
                Pay with your <span>Voice</span>
              </h1>
              <p className="voice-subtitle">
                Speak a command or type below. Your voice is verified, intent classified,
                and fraud checked — all in milliseconds.
              </p>

              {/* Mic Button */}
              <div className="mic-container">
                <button
                  id="mic-button"
                  className={`mic-btn ${isRecording ? 'recording' : ''}`}
                  onClick={handleMicClick}
                  disabled={processing}
                >
                  {isRecording ? '⏹' : processing ? <div className="spinner" /> : '🎙️'}
                </button>
                <div className="mic-ring" />
                <div className="mic-ring" />
                <div className="mic-ring" />
              </div>

              <p style={{ color: 'var(--text-muted)', fontSize: 'var(--font-sm)' }}>
                {isRecording
                  ? 'Listening... Click to stop'
                  : processing
                  ? 'Processing...'
                  : 'Click to speak a command'}
              </p>

              {/* Text Input Fallback */}
              <form className="text-input-section" onSubmit={handleTextSubmit}>
                <input
                  id="text-command-input"
                  className="text-input"
                  type="text"
                  placeholder='Or type: "send 5 rupees to rahul"'
                  value={textInput}
                  onChange={(e) => setTextInput(e.target.value)}
                  disabled={processing}
                />
                <button className="btn btn-primary" type="submit" disabled={processing || !textInput.trim()}>
                  Send
                </button>
              </form>
            </section>

            {/* Pipeline Results */}
            {stages.length > 0 && (
              <section className="animate-in" style={{ marginBottom: 'var(--space-xl)' }}>
                <h2 style={{ fontSize: 'var(--font-xl)', fontWeight: 700, marginBottom: 'var(--space-lg)', textAlign: 'center' }}>
                  Pipeline Results
                </h2>
                <PipelineVisualizer stages={stages} loading={processing} />
                {!processing && pipelineResult?.auth_decision && (
                  <ThreatMatrix authDecision={pipelineResult.auth_decision} />
                )}
              </section>
            )}

            {/* Auth Result / Status */}
            {statusMessage && !showPin && !showStepUp && !showBalance && !paymentStatus && (
              <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 'var(--space-xl)' }}>
                <div
                  className={`auth-panel ${
                    pipelineResult?.auth_decision?.proceed
                      ? pipelineResult?.auth_decision?.auth_required === 'step_up'
                        ? 'stepup'
                        : 'proceed'
                      : 'blocked'
                  }`}
                >
                  <div className="auth-icon">
                    {pipelineResult?.auth_decision?.proceed ? (
                      pipelineResult?.auth_decision?.auth_required === 'step_up' ? '⚠️' : '✅'
                    ) : (
                      '🚫'
                    )}
                  </div>
                  <div className="auth-message">{statusMessage}</div>
                  <button className="btn btn-secondary" onClick={resetPipeline}>
                    New Command
                  </button>
                </div>
              </div>
            )}

            {/* Payment Status */}
            {paymentStatus && (
              <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 'var(--space-xl)' }}>
                <div className={`auth-panel ${paymentStatus === 'success' ? 'proceed' : 'blocked'}`}>
                  <div className="auth-icon">{paymentStatus === 'success' ? '🎉' : '❌'}</div>
                  <div className="auth-title">
                    {paymentStatus === 'success' ? 'Payment Successful!' : 'Payment Failed'}
                  </div>
                  <div className="auth-message">{paymentMessage}</div>
                  <button className="btn btn-primary" onClick={resetPipeline}>
                    New Command
                  </button>
                </div>
              </div>
            )}

            {/* Dashboard Stats */}
            {!stages.length && (
              <div className="dashboard-grid animate-in animate-in-delay-1">
                <div className="stat-card">
                  <div className="stat-label">Available Balance</div>
                  <div className="stat-value gradient">₹{balance.toLocaleString('en-IN')}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Account Status</div>
                  <div className="stat-value" style={{ color: 'var(--success)' }}>Active</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Voice Enrolled</div>
                  <div className="stat-value" style={{ color: user?.speaker_enrolled ? 'var(--success)' : 'var(--warning)' }}>
                    {user?.speaker_enrolled ? 'Yes' : 'No'}
                  </div>
                </div>
              </div>
            )}

            {/* Quick Commands */}
            {!stages.length && (
              <div className="card animate-in animate-in-delay-2">
                <div className="card-header">
                  <div className="card-title">Try These Commands</div>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '1rem' }}>
                  {[
                    { text: 'send 5 rupees to rahul', icon: '💸' },
                    { text: 'check my balance', icon: '💰' },
                    { text: 'show recent transactions', icon: '📋' },
                    { text: 'pay electricity bill of 10 rupees', icon: '🧾' },
                  ].map((cmd) => (
                    <button
                      key={cmd.text}
                      className="txn-item"
                      style={{ justifyContent: 'flex-start', cursor: 'pointer' }}
                      onClick={() => {
                        setTextInput(cmd.text);
                        // Auto submit
                        resetPipeline();
                        setProcessing(true);
                        processTextCommand(cmd.text, USER_ID).then((r) => {
                          handlePipelineResult(r);
                          setProcessing(false);
                        }).catch((e) => {
                          setStatusMessage(`Error: ${e.message}`);
                          setProcessing(false);
                        });
                      }}
                    >
                      <span style={{ fontSize: '1.5rem' }}>{cmd.icon}</span>
                      <span style={{ fontSize: '1rem', color: 'var(--text-main)', fontWeight: '500' }}>
                        "{cmd.text}"
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {page === 'history' && (
          <div className="animate-in">
            <TransactionHistory username={USER_ID} refreshKey={refreshKey} />
          </div>
        )}
      </main>

      {/* PIN Pad Modal */}
      {showPin && (
        <PinPad
          amount={getAmount()}
          recipient={getRecipient()}
          onSubmit={handlePinSubmit}
          onCancel={() => {
            setShowPin(false);
            setStatusMessage('Payment cancelled.');
          }}
          loading={pinLoading}
        />
      )}

      {/* StepUp Auth Modal */}
      {showStepUp && (
        <StepUpAuth
          userId={USER_ID}
          onSuccess={() => {
            setShowStepUp(false);
            setShowPin(true); // Proceed to PIN after successful voice step-up
          }}
          onCancel={() => {
            setShowStepUp(false);
            setStatusMessage('Voice step-up auth cancelled.');
          }}
        />
      )}

      {/* Voice Enrollment Modal */}
      {showEnrollment && (
        <VoiceEnrollment
          userId={USER_ID}
          onComplete={() => {
            setShowEnrollment(false);
            loadUser(); // Refresh user state to show enrolled status
            setStatusMessage('Voice profile successfully created!');
          }}
          onCancel={() => setShowEnrollment(false)}
        />
      )}

      {/* Balance Display Modal */}
      {showBalance && (
        <BalanceDisplay
          balance={balance}
          onDismiss={() => {
            setShowBalance(false);
            resetPipeline();
          }}
        />
      )}
    </div>
  );
}
