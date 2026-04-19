import { useState, useEffect, useCallback } from 'react';
import { useAudioRecorder } from './hooks/useAudioRecorder';
import PipelineVisualizer from './components/PipelineVisualizer';
import TransactionHistory from './components/TransactionHistory';
import VoiceEnrollment from './components/VoiceEnrollment';
import ThreatMatrix from './components/ThreatMatrix';
import PinPad from './components/PinPad';
import StepUpAuth from './components/StepUpAuth';
import LoginPage from './components/LoginPage';
import ConfirmationModal from './components/ConfirmationModal';
import ContactsList from './components/ContactsList';
import QRScannerModal from './components/QRScannerModal';
import TransactionReceipt from './components/TransactionReceipt';
import { VoiceLines, speak, stopSpeaking } from './utils/voiceFeedback';
import {
  login, register, setAuthToken, clearAuthToken,
  getBalance,
  processTextCommand, processVoiceCommand, processVoiceCommandSSE,
  verifyPin, createOrder,
  openRazorpayCheckout, verifyPayment,
} from './utils/api';

// --- Sample commands for reviewers ---
const SAMPLE_COMMANDS = [
  { text: 'Send 500 rupees to Rahul', icon: '💸' },
  { text: 'Check my balance', icon: '💰' },
  { text: 'Show my recent transactions', icon: '📋' },
  { text: 'Pay electricity bill of 1200', icon: '⚡' },
  { text: 'Transfer 200 to Priya', icon: '🔄' },
  { text: 'Open QR scanner', icon: '📷' },
  { text: 'Send 1000 to Dhanush', icon: '💳' },
  { text: 'Pay water bill of 800', icon: '💧' },
];

function App() {
  // --- Auth State (persisted to localStorage) ---
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);

  // --- UI State ---
  const [balance, setBalance] = useState(null);
  const [textInput, setTextInput] = useState('');
  const [pipelineStages, setPipelineStages] = useState([]);
  const [pipelineLoading, setPipelineLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState('info');
  const [view, setView] = useState('main'); // main, history, enroll, contacts, receipt
  const [receiptTxnId, setReceiptTxnId] = useState(null);
  const [showBalancePopup, setShowBalancePopup] = useState(false);

  // --- Transaction Flow ---
  const [currentTransaction, setCurrentTransaction] = useState(null);
  const [authDecision, setAuthDecision] = useState(null);
  const [showPinPad, setShowPinPad] = useState(false);
  const [showStepUp, setShowStepUp] = useState(false);
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [showQRScanner, setShowQRScanner] = useState(false);

  // --- Error Recovery ---
  const [retryCount, setRetryCount] = useState(0);
  const MAX_RETRIES = 3;

  const { isRecording, audioBlob, startRecording, stopRecording, resetAudio } = useAudioRecorder();

  // --- Restore session from localStorage on mount ---
  useEffect(() => {
    try {
      const savedToken = localStorage.getItem('voicepay_token');
      const savedUser = localStorage.getItem('voicepay_user');
      if (savedToken && savedUser) {
        setAuthToken(savedToken);
        setUser(JSON.parse(savedUser));
        setIsAuthenticated(true);
      }
    } catch {
      localStorage.removeItem('voicepay_token');
      localStorage.removeItem('voicepay_user');
    }
  }, []);

  // --- Auth Handlers ---
  const handleLogin = useCallback(async (username, pin, displayName) => {
    let data;
    if (displayName) {
      data = await register(username, displayName, pin);
    } else {
      data = await login(username, pin);
    }
    // Persist to localStorage so refresh doesn't lose session
    setAuthToken(data.token);
    localStorage.setItem('voicepay_token', data.token);
    localStorage.setItem('voicepay_user', JSON.stringify(data.user));
    setUser(data.user);
    setIsAuthenticated(true);
    VoiceLines.loginSuccess(data.user.display_name || data.user.username);
    showMsg(`Welcome, ${data.user.display_name}!`, 'success');
  }, []);

  const handleLogout = useCallback(() => {
    clearAuthToken();
    localStorage.removeItem('voicepay_token');
    localStorage.removeItem('voicepay_user');
    VoiceLines.logout(user?.display_name || 'User');
    setUser(null);
    setIsAuthenticated(false);
    setBalance(null);
    setPipelineStages([]);
    setCurrentTransaction(null);
    setAuthDecision(null);
    setShowPinPad(false);
    setShowStepUp(false);
    setShowConfirmation(false);
    setView('main');
  }, []);

  // --- Load balance on auth + check enrollment ---
  useEffect(() => {
    if (isAuthenticated && user) {
      getBalance(user.username)
        .then((data) => setBalance(data.balance))
        .catch(() => {});

      // Prompt voice enrollment for new accounts
      if (user.speaker_enrolled === false) {
        setTimeout(() => {
          speak('I noticed you haven\'t set up your voice profile yet. Let\'s do that now for secure payments.');
          setView('enroll');
        }, 2000);
      }
    }
  }, [isAuthenticated, user]);

  // --- Message Helper ---
  const showMsg = (text, type = 'info') => {
    setMessage(text);
    setMessageType(type);
    if (type !== 'error') {
      setTimeout(() => setMessage(''), 5000);
    }
  };

  // --- Voice Processing with SSE ---
  useEffect(() => {
    if (!audioBlob || !isAuthenticated) return;

    const processAudio = async () => {
      setPipelineLoading(true);
      setPipelineStages([]);
      setMessage('');
      setAuthDecision(null);
      setCurrentTransaction(null);

      try {
        const finalResult = await processVoiceCommandSSE(
          audioBlob,
          user.username,
          (stageEvent) => {
            setPipelineStages((prev) => [
              ...prev,
              {
                stage: stageEvent.stage,
                success: stageEvent.success,
                data: stageEvent.data,
                duration_ms: stageEvent.duration_ms,
              },
            ]);
          }
        );

        if (!finalResult) {
          showMsg('No response from server', 'error');
          return;
        }

        if (finalResult.data?.status === 'clarify') {
          VoiceLines.notUnderstood();
          setRetryCount((prev) => prev + 1);
          if (retryCount + 1 >= MAX_RETRIES) {
          VoiceLines.maxRetriesReached();
            showMsg('Unable to understand after 3 attempts. Please type your command instead.', 'error');
          } else {
            showMsg(finalResult.data.message || 'Please try again', 'info');
            setTimeout(() => {
              resetAudio();
              startRecording().catch(() => {});
            }, 1500);
          }
          return;
        }

        // Handle non-payment intents (info responses)
        if (finalResult.data?.status === 'info_response') {
          handleInfoResponse(finalResult.data);
          return;
        }

        // Handle unknown recipient
        if (finalResult.data?.status === 'unknown_recipient') {
          VoiceLines.unknownRecipient(finalResult.data.recipient || 'This person');
          showMsg(finalResult.data.message || 'Contact not found. Scan QR instead?', 'warning');
          setShowQRScanner(true);
          return;
        }

        setRetryCount(0);

        const txnId = finalResult.data?.transaction_id;
        const authDec = finalResult.data?.auth_decision;

        if (txnId) setCurrentTransaction({ id: txnId });
        if (authDec) {
          setAuthDecision(authDec);
          handleAuthDecision(authDec);
        }
      } catch (err) {
        console.warn('[App] SSE failed, falling back to batch:', err.message);
        try {
          const result = await processVoiceCommand(audioBlob, user.username);
          handleBatchResult(result);
        } catch (batchErr) {
          showMsg(`Error: ${batchErr.message}`, 'error');
          VoiceLines.networkError();
        }
      } finally {
        setPipelineLoading(false);
        resetAudio();
      }
    };

    processAudio();
  }, [audioBlob]);

  // --- Text Command Processing ---
  const handleTextSubmit = async (e) => {
    e.preventDefault();
    if (!textInput.trim()) return;

    setPipelineLoading(true);
    setPipelineStages([]);
    setMessage('');
    setAuthDecision(null);
    setCurrentTransaction(null);
    setRetryCount(0);

    try {
      const result = await processTextCommand(textInput, user.username);
      handleBatchResult(result);
    } catch (err) {
      showMsg(`Error: ${err.message}`, 'error');
    } finally {
      setPipelineLoading(false);
      setTextInput('');
    }
  };

  // Quick-fill a sample command
  const handleSampleClick = (text) => {
    setTextInput(text);
  };

  // --- Handle non-payment intent responses ---
  const handleInfoResponse = (data) => {
    // Clear pipeline loading since this is a terminal response
    setPipelineLoading(false);
    // Keep stages visible briefly, then clear after message shows
    setTimeout(() => setPipelineStages([]), 300);

    const intent = data.intent;
    if (intent === 'check_balance') {
      getBalance(user.username).then((b) => {
        setBalance(b.balance);
        VoiceLines.balanceResult(b.balance);
        setShowBalancePopup(true);
        // Auto-close after 6 seconds
        setTimeout(() => setShowBalancePopup(false), 6000);
      }).catch(() => { VoiceLines.networkError(); showMsg('Could not fetch balance', 'error'); });
    } else if (intent === 'transaction_history') {
      VoiceLines.showingHistory();
      showMsg('📋 Switching to transaction history...', 'info');
      setTimeout(() => setView('history'), 500);
    } else if (intent === 'scan_qr') {
      VoiceLines.qrScannerOpened();
      showMsg('📷 Opening QR scanner...', 'info');
      setShowQRScanner(true);
    }
  };

  // --- Handle batch pipeline result ---
  const handleBatchResult = (result) => {
    if (result.stages) {
      setPipelineStages(result.stages);
    }

    if (result.status === 'clarify') {
      VoiceLines.notUnderstood();
      showMsg(result.message || 'Please try again', 'info');
      return;
    }

    // Handle non-payment intents
    if (result.status === 'info_response') {
      handleInfoResponse(result);
      return;
    }

    // Handle unknown recipient — prompt QR scan
    if (result.status === 'unknown_recipient') {
      VoiceLines.unknownRecipient(result.recipient || 'This person');
      showMsg(result.message || 'Contact not found. Scan QR instead?', 'warning');
      setShowQRScanner(true);
      return;
    }

    if (result.transaction_id) {
      setCurrentTransaction({ id: result.transaction_id });
    }

    // Check for unknown contact — prompt QR
    const intentStage = result.stages?.find((s) => s.stage === 'intent_classification');
    if (intentStage?.data?.prompt_qr) {
      const recipientName = intentStage.data.entities?.recipient || 'This person';
      VoiceLines.unknownRecipient(recipientName);
      showMsg(
        `Contact "${recipientName}" not found. Would you like to scan a QR code instead?`,
        'warning'
      );
    }

    if (result.auth_decision) {
      setAuthDecision(result.auth_decision);
      handleAuthDecision(result.auth_decision);
    }
  };

  // --- Auth Decision Handler ---
  const handleAuthDecision = (decision) => {
    if (!decision.proceed) {
      VoiceLines.paymentBlocked();
      showMsg(decision.message || 'Transaction blocked', 'error');
      return;
    }

    const method = decision.auth_required;
    if (method === 'pin_only') {
      // Try to get amount/recipient from pipeline stages for spoken feedback
      const intentStage = pipelineStages.find((s) => s.stage === 'intent_classification');
      const amount = intentStage?.data?.entities?.amount || 0;
      const recipient = intentStage?.data?.entities?.recipient || 'recipient';
      VoiceLines.paymentPinOnly(amount, recipient);
      setShowPinPad(true);
    } else if (method === 'step_up') {
      const intentStage = pipelineStages.find((s) => s.stage === 'intent_classification');
      const amount = intentStage?.data?.entities?.amount || 0;
      const recipient = intentStage?.data?.entities?.recipient || 'recipient';
      VoiceLines.paymentStepUp(amount, recipient);
      setShowStepUp(true);
    }
  };

  // --- PIN Verification ---
  const handlePinSubmit = async (pin) => {
    try {
      const result = await verifyPin(user.username, pin, currentTransaction.id);
      if (result.success) {
        setShowPinPad(false);
        VoiceLines.pinSuccess();
        showMsg('PIN verified! Confirm your payment.', 'success');

        const lastIntent = pipelineStages.find((s) => s.stage === 'intent_classification');
        const lastFraud = pipelineStages.find((s) => s.stage === 'fraud_detection');
        setCurrentTransaction((prev) => ({
          ...prev,
          amount: lastIntent?.data?.entities?.amount || 0,
          recipient: lastIntent?.data?.entities?.recipient || 'Unknown',
          riskTier: lastFraud?.data?.risk_tier || 'Low',
          riskScore: lastFraud?.data?.risk_score || 0,
        }));
        setShowConfirmation(true);
      } else {
        showMsg(result.message || 'Invalid PIN', 'error');
        VoiceLines.pinFailed();
      }
    } catch (err) {
      showMsg(`PIN error: ${err.message}`, 'error');
    }
  };

  // --- Step-Up Auth Complete ---
  const handleStepUpComplete = () => {
    setShowStepUp(false);
    setShowPinPad(true);
    VoiceLines.stepUpSuccess();
    showMsg('Voice re-verified! Enter your PIN.', 'success');
  };

  // --- Confirmation Modal Handlers ---
  const handleConfirmPayment = async () => {
    setShowConfirmation(false);
    try {
      const orderData = await createOrder(currentTransaction.id, user.username);
      VoiceLines.paymentProcessing();
      showMsg('Opening payment gateway...', 'info');

      openRazorpayCheckout(
        orderData,
        async (paymentData) => {
          try {
            const result = await verifyPayment(paymentData);
            if (result.success) {
              // Redirect to receipt page
              getBalance(user.username).then((data) => setBalance(data.balance)).catch(() => {});
              VoiceLines.paymentSuccess(
                currentTransaction.amount || 0,
                currentTransaction.recipient || 'Merchant'
              );
              setReceiptTxnId(currentTransaction.id);
              setView('receipt');
              setPipelineStages([]);
              setMessage('');
            } else {
              showMsg(result.message || 'Payment failed', 'error');
            }
          } catch (err) {
            showMsg(`Verification error: ${err.message}`, 'error');
          }
        },
        (error) => {
          VoiceLines.paymentCancelled();
          showMsg(`Payment cancelled: ${error}`, 'error');
        }
      );
    } catch (err) {
      showMsg(`Order error: ${err.message}`, 'error');
    }
  };

  const handleCancelPayment = () => {
    setShowConfirmation(false);
    setCurrentTransaction(null);
    VoiceLines.paymentCancelled();
    showMsg('Payment cancelled.', 'info');
  };

  // --- Render ---
  if (!isAuthenticated) {
    return <LoginPage onLogin={handleLogin} />;
  }

  return (
    <div className="app">
      {/* Header */}
      <header className="app-header">
        <div className="header-left" onClick={() => { setView('main'); setMessage(''); }} style={{ cursor: 'pointer' }} title="Go to Home">
          <span className="app-logo">🎙️</span>
          <h1 className="app-title">VoicePay</h1>
        </div>
        <div className="header-center">
          <nav className="nav-tabs">
            <button
              className={`nav-tab ${view === 'main' ? 'active' : ''}`}
              onClick={() => setView('main')}
            >
              💳 Pay
            </button>
            <button
              className={`nav-tab ${view === 'history' ? 'active' : ''}`}
              onClick={() => setView('history')}
            >
              📋 History
            </button>
            <button
              className={`nav-tab ${view === 'contacts' ? 'active' : ''}`}
              onClick={() => setView('contacts')}
            >
              👥 Contacts
            </button>
            <button
              className={`nav-tab ${view === 'enroll' ? 'active' : ''}`}
              onClick={() => setView('enroll')}
            >
              🔐 Voice ID
            </button>
          </nav>
        </div>
        <div className="header-right">
          <div className="user-badge">
            <span className="user-avatar">{user?.display_name?.[0]?.toUpperCase() || 'U'}</span>
            <span className="user-name">{user?.display_name}</span>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={handleLogout} id="logout-btn">
            Logout
          </button>
        </div>
      </header>

      {/* Messages */}
      {message && (
        <div className={`message-bar message-${messageType} animate-in`}>
          <span>{message}</span>
          <button className="message-close" onClick={() => setMessage('')}>×</button>
        </div>
      )}

      {/* Main Content */}
      <main className="app-main">
        {view === 'main' && (
          <div className="main-grid">
            {/* Voice/Text Input */}
            <section className="card input-section">
              <h2 className="section-title">Make a Payment</h2>
              <p className="section-subtitle">Speak or type your command</p>

              {/* Mic Button */}
              <div className="mic-container">
                <button
                  className={`mic-btn ${isRecording ? 'recording' : ''} ${pipelineLoading ? 'disabled' : ''}`}
                  onClick={() => {
                    if (isRecording) {
                      stopSpeaking();
                      stopRecording();
                      VoiceLines.recordingStopped();
                    } else {
                      startRecording();
                    }
                  }}
                  disabled={pipelineLoading}
                  id="mic-button"
                >
                  <span className="mic-icon">{isRecording ? '⏹️' : '🎙️'}</span>
                  {isRecording && <div className="mic-pulse" />}
                </button>
                <span className="mic-label">
                  {isRecording
                    ? 'Listening... (auto-stops on silence)'
                    : pipelineLoading
                    ? 'Processing...'
                    : retryCount > 0 && retryCount < MAX_RETRIES
                    ? `Retry ${retryCount}/${MAX_RETRIES} — Tap to speak`
                    : 'Tap to speak'}
                </span>
              </div>

              {/* Text Fallback */}
              <form className="text-input-form" onSubmit={handleTextSubmit}>
                <input
                  type="text"
                  placeholder='e.g. "Send 500 rupees to Rahul"'
                  value={textInput}
                  onChange={(e) => setTextInput(e.target.value)}
                  disabled={pipelineLoading}
                  id="text-command-input"
                />
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={pipelineLoading || !textInput.trim()}
                  id="send-text-btn"
                >
                  Send
                </button>
              </form>

              {/* Try These Commands */}
              <div className="sample-commands">
                <p className="sample-label">Try these commands:</p>
                <div className="sample-chips">
                  {SAMPLE_COMMANDS.map((cmd) => (
                    <button
                      key={cmd.text}
                      className="sample-chip"
                      onClick={() => handleSampleClick(cmd.text)}
                      disabled={pipelineLoading}
                    >
                      <span>{cmd.icon}</span> {cmd.text}
                    </button>
                  ))}
                </div>
              </div>
            </section>

            {/* Pipeline Visualization */}
            <section className="card pipeline-section">
              <h2 className="section-title">Pipeline Status</h2>
              <PipelineVisualizer stages={pipelineStages} loading={pipelineLoading} />
            </section>

            {/* Threat Matrix */}
            {pipelineStages.some((s) => s.stage === 'fraud_detection') && (
              <section className="card threat-section">
                <h2 className="section-title">Threat Analysis</h2>
                <ThreatMatrix
                  fraudData={pipelineStages.find((s) => s.stage === 'fraud_detection')?.data}
                  svData={pipelineStages.find((s) => s.stage === 'speaker_verification')?.data}
                />
              </section>
            )}
          </div>
        )}

        {view === 'history' && (
          <TransactionHistory username={user?.username} />
        )}

        {view === 'contacts' && (
          <ContactsList />
        )}

        {view === 'receipt' && receiptTxnId && (
          <TransactionReceipt
            transactionId={receiptTxnId}
            onGoHome={() => {
              setView('main');
              setCurrentTransaction(null);
              setReceiptTxnId(null);
              setPipelineStages([]);
            }}
          />
        )}

        {view === 'enroll' && (
          <VoiceEnrollment
            userId={user?.username}
            isEnrolled={user?.speaker_enrolled}
            onComplete={() => {
              setUser((prev) => ({ ...prev, speaker_enrolled: true }));
              localStorage.setItem('voicepay_user', JSON.stringify({ ...user, speaker_enrolled: true }));
              showMsg('Voice profile enrolled successfully!', 'success');
              setView('main');
            }}
            onCancel={() => setView('main')}
          />
        )}
      </main>

      {/* Modals */}
      {showPinPad && (
        <PinPad
          onSubmit={handlePinSubmit}
          onCancel={() => setShowPinPad(false)}
        />
      )}

      {showStepUp && (
        <StepUpAuth
          userId={user?.username}
          onSuccess={handleStepUpComplete}
          onCancel={() => {
            setShowStepUp(false);
            showMsg('Step-up verification cancelled.', 'info');
          }}
        />
      )}

      {showConfirmation && currentTransaction && (
        <ConfirmationModal
          transactionId={currentTransaction.id}
          amount={currentTransaction.amount}
          recipient={currentTransaction.recipient}
          riskTier={currentTransaction.riskTier}
          riskScore={currentTransaction.riskScore}
          onConfirm={handleConfirmPayment}
          onCancel={handleCancelPayment}
        />
      )}

      {showQRScanner && (
        <QRScannerModal
          onClose={() => setShowQRScanner(false)}
          onScan={(upiId) => {
            setShowQRScanner(false);
            // Trigger a real payment flow via the text command pipeline
            const qrCommand = `Send payment to ${upiId}`;
            setTextInput(qrCommand);
            showMsg(`QR scanned: ${upiId}. Type amount and send, or submit now.`, 'success');
          }}
        />
      )}

      {/* Balance Popup */}
      {showBalancePopup && (
        <div className="balance-popup-overlay" onClick={() => setShowBalancePopup(false)}>
          <div className="balance-popup animate-in" onClick={(e) => e.stopPropagation()}>
            <button className="balance-popup-close" onClick={() => setShowBalancePopup(false)}>×</button>
            <div className="balance-popup-icon">💰</div>
            <h3 className="balance-popup-title">Account Balance</h3>
            <div className="balance-popup-amount">
              ₹{balance !== null ? balance.toLocaleString('en-IN') : '...'}
            </div>
            <div className="balance-popup-details">
              <div className="balance-popup-row">
                <span>Account Holder</span>
                <span>{user?.display_name || user?.username}</span>
              </div>
              <div className="balance-popup-row">
                <span>Username</span>
                <span>@{user?.username}</span>
              </div>
              <div className="balance-popup-row">
                <span>Voice ID</span>
                <span>{user?.speaker_enrolled ? '✅ Enrolled' : '⚠️ Not enrolled'}</span>
              </div>
              <div className="balance-popup-row">
                <span>Account Type</span>
                <span>Savings</span>
              </div>
            </div>
            <div className="balance-popup-timer">Auto-closes in a few seconds</div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
