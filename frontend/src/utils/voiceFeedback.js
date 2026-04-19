/**
 * VoiceFeedback — Premium TTS for VoicePay Web
 * =============================================
 * Uses Web Speech API with automatic female voice selection.
 * Falls back gracefully if no preferred voice is found.
 */

let selectedVoice = null;
let voicesLoaded = false;

// ── Voice Selection ─────────────────────────────────────
// Priority list: best female voices across platforms
const PREFERRED_VOICES = [
  'Microsoft Zira',           // Windows — clear female
  'Google UK English Female', // Chrome — very natural
  'Samantha',                 // macOS/iOS — Apple's best
  'Karen',                    // macOS — Australian female
  'Moira',                    // macOS — Irish female
  'Fiona',                    // macOS — Scottish female
  'Victoria',                 // macOS — American female
  'Google US English',        // Chrome fallback
  'Microsoft Hazel',          // Windows UK female
  'Microsoft Susan',          // Windows UK female
];

function loadVoices() {
  const voices = window.speechSynthesis?.getVoices() || [];
  if (voices.length === 0) return;
  voicesLoaded = true;

  // Try preferred voices first
  for (const pref of PREFERRED_VOICES) {
    const match = voices.find(v =>
      v.name.toLowerCase().includes(pref.toLowerCase())
    );
    if (match) {
      selectedVoice = match;
      console.log(`[VoicePay TTS] Selected voice: ${match.name} (${match.lang})`);
      return;
    }
  }

  // Fallback: find any English female voice
  const femaleFallback = voices.find(v =>
    v.lang.startsWith('en') &&
    (v.name.toLowerCase().includes('female') ||
      v.name.toLowerCase().includes('woman') ||
      v.name.toLowerCase().includes('zira') ||
      v.name.toLowerCase().includes('samantha'))
  );
  if (femaleFallback) {
    selectedVoice = femaleFallback;
    console.log(`[VoicePay TTS] Fallback voice: ${femaleFallback.name}`);
    return;
  }

  // Last resort: any English voice
  const anyEnglish = voices.find(v => v.lang.startsWith('en'));
  if (anyEnglish) {
    selectedVoice = anyEnglish;
    console.log(`[VoicePay TTS] Using: ${anyEnglish.name}`);
  }
}

// Load voices (Chrome fires event async, Firefox/Safari sync)
if (typeof window !== 'undefined' && window.speechSynthesis) {
  loadVoices();
  window.speechSynthesis.onvoiceschanged = loadVoices;
}

// ── Core Speak Function ─────────────────────────────────
export function speak(text) {
  if (!window.speechSynthesis) return;
  window.speechSynthesis.cancel(); // Stop any ongoing speech

  if (!voicesLoaded) loadVoices(); // Retry loading if not ready

  const utterance = new SpeechSynthesisUtterance(text);
  if (selectedVoice) utterance.voice = selectedVoice;
  utterance.lang = 'en-US';
  utterance.pitch = 1.0;
  utterance.rate = 0.92;   // Slightly slower than default for clarity
  utterance.volume = 1.0;
  window.speechSynthesis.speak(utterance);
}

export function stopSpeaking() {
  if (window.speechSynthesis) window.speechSynthesis.cancel();
}

// ── Voice Lines (30+) ───────────────────────────────────

export const VoiceLines = {

  // ═══ Authentication ═══
  loginSuccess: (name) =>
    speak(`Welcome, ${name}. Your voice finance assistant is ready.`),

  loginFailed: () =>
    speak('Login failed. Please check your credentials and try again.'),

  registerSuccess: (name) =>
    speak(`Account created successfully. Welcome, ${name}.`),

  logout: (name) =>
    speak(`Goodbye, ${name}. Have a great day.`),

  sessionRestored: (name) =>
    speak(`Welcome back, ${name}. Session restored.`),

  // ═══ Voice Recording ═══
  recordingStarted: () =>
    speak('Listening.'),

  recordingStopped: () =>
    speak('Processing your command.'),

  recordingFailed: () =>
    speak('Could not access microphone. Please check permissions.'),

  // ═══ Balance ═══
  balanceResult: (amount) =>
    speak(`Your current balance is ${Number(amount).toLocaleString()} rupees.`),

  balanceFetchError: () =>
    speak('Unable to fetch your balance right now. Please try again later.'),

  // ═══ Transaction History ═══
  showingHistory: () =>
    speak('Showing your recent transactions.'),

  noTransactions: () =>
    speak('You have no transactions yet.'),

  transactionsFetched: (count) =>
    speak(`Found ${count} recent transaction${count !== 1 ? 's' : ''}.`),

  // ═══ Payment Flow ═══
  paymentPinOnly: (amount, recipient) =>
    speak(`Sending ${amount} rupees to ${recipient}. Please enter your PIN to confirm.`),

  paymentStepUp: (amount, recipient) =>
    speak(`Medium risk detected for ${amount} rupees to ${recipient}. Voice re-verification required before PIN entry.`),

  paymentBlocked: () =>
    speak('This transaction has been blocked due to high risk. Please try a smaller amount or contact support.'),

  paymentSuccess: (amount, recipient) =>
    speak(`Payment of ${amount} rupees to ${recipient} completed successfully.`),

  paymentCancelled: () =>
    speak('Payment has been cancelled.'),

  paymentProcessing: () =>
    speak('Processing your payment. Please wait.'),

  // ═══ PIN ═══
  pinRequired: () =>
    speak('Please enter your four digit PIN.'),

  pinSuccess: () =>
    speak('PIN verified successfully. Please confirm your payment.'),

  pinFailed: () =>
    speak('Incorrect PIN. Please try again.'),

  // ═══ Contact System ═══
  unknownRecipient: (name) =>
    speak(`${name} is not in your contacts. You can scan their QR code to pay.`),

  contactFound: (name) =>
    speak(`Contact found. Sending to ${name}.`),

  // ═══ QR Scanner ═══
  qrScannerOpened: () =>
    speak('QR scanner is ready. Point your camera at the code.'),

  qrScanned: (name, amount) =>
    speak(`QR code scanned. ${amount} rupees to ${name}. Enter your PIN to confirm.`),

  qrPaymentDone: (amount, name) =>
    speak(`QR payment of ${amount} rupees to ${name} completed.`),

  // ═══ Voice Enrollment ═══
  enrollStart: () =>
    speak('Voice enrollment started. Please say the phrase shown on your screen clearly.'),

  enrollSampleRecorded: (n, total) =>
    speak(`Sample ${n} of ${total} recorded.${n < total ? ' Please record the next sample.' : 'Your Voice profile has been saved.'}`),

  enrollSuccess: () =>
    speak('Your voice ID has been registered. You can now use voice verification for payments.'),

  enrollFailed: () =>
    speak('Voice enrollment failed. Please try recording again in a quiet environment.'),

  // ═══ Step-Up Auth ═══
  stepUpRequired: () =>
    speak('Additional voice verification required. Please speak to re-confirm your identity.'),

  stepUpSuccess: () =>
    speak('Voice re-verified. You may now enter your PIN.'),

  stepUpFailed: () =>
    speak('Voice verification failed. Transaction cannot proceed.'),

  // ═══ Errors & Clarification ═══
  networkError: () =>
    speak('Network error. Please check your internet connection.'),

  notUnderstood: () =>
    speak("Sorry, I didn't catch that. Try saying something like, send 500 rupees to Rahul."),

  outOfScope: () =>
    speak("That doesn't seem like a financial command. You can ask me to send money, check balance, or view transactions."),

  serverError: () =>
    speak('Something went wrong on our end. Please try again.'),

  maxRetriesReached: () =>
    speak('Unable to understand after multiple attempts. Please type your command instead.'),

  // ═══ Misc ═══
  welcomeBack: () =>
    speak('Welcome to VoicePay. Your AI powered voice finance assistant.'),

  featureComingSoon: () =>
    speak('This feature is coming soon.'),
};
