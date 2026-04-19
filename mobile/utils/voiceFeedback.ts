/**
 * VoiceFeedback — Premium TTS for VoicePay Mobile
 * =================================================
 * Uses expo-speech with optimized voice settings.
 * Selects the best available female voice on the device.
 */
import * as Speech from 'expo-speech';

// ── Voice Config ────────────────────────────────────────
// Rate 0.9 = slightly slower for clarity, pitch 1.0 = natural
const TTS_OPTIONS: Speech.SpeechOptions = {
  language: 'en-US',
  pitch: 1.0,
  rate: 0.88,
};

// Try to find a female voice on the device
let voiceSelected = false;

async function selectVoice() {
  if (voiceSelected) return;
  try {
    const voices = await Speech.getAvailableVoicesAsync();
    // Priority: look for these keywords in voice identifiers
    const preferred = [
      'female', 'zira', 'samantha', 'karen', 'moira',
      'victoria', 'fiona', 'susan', 'hazel',
    ];
    for (const keyword of preferred) {
      const match = voices.find(v =>
        (v.name || v.identifier || '').toLowerCase().includes(keyword) &&
        (v.language || '').startsWith('en')
      );
      if (match) {
        TTS_OPTIONS.voice = match.identifier;
        voiceSelected = true;
        console.log(`[VoicePay TTS] Selected: ${match.name || match.identifier}`);
        return;
      }
    }
    // Fallback: any English voice
    const english = voices.find(v => (v.language || '').startsWith('en'));
    if (english) {
      TTS_OPTIONS.voice = english.identifier;
      voiceSelected = true;
    }
  } catch {
    // Voice enumeration not available — use defaults
  }
}

// Fire voice selection on import
selectVoice();

// ── Core Speak Function ─────────────────────────────────
export function speak(text: string) {
  Speech.stop();
  Speech.speak(text, TTS_OPTIONS);
}

export function stopSpeaking() {
  Speech.stop();
}

// ── Voice Lines (30+) ───────────────────────────────────

export const VoiceLines = {

  // ═══ Authentication ═══
  loginSuccess: (name: string) =>
    speak(`Welcome back, ${name}. Your voice assistant is ready.`),

  loginFailed: () =>
    speak('Login failed. Please check your credentials and try again.'),

  demoMode: () =>
    speak('Entering demo mode. All features available offline.'),

  logout: (name: string) =>
    speak(`Goodbye, ${name}. Have a great day.`),

  // ═══ Voice Recording ═══
  recordingStarted: () =>
    speak('Listening.'),

  recordingStopped: () =>
    speak('Processing your command.'),

  recordingFailed: () =>
    speak('Could not access microphone. Please check permissions.'),

  // ═══ Balance ═══
  balanceResult: (amount: number) =>
    speak(`Your current balance is ${Number(amount).toLocaleString()} rupees.`),

  balanceFetchError: () =>
    speak('Unable to fetch your balance right now.'),

  // ═══ Transaction History ═══
  showingHistory: () =>
    speak('Showing your recent transactions.'),

  noTransactions: () =>
    speak('You have no transactions yet.'),

  transactionsFetched: (count: number) =>
    speak(`Found ${count} recent transaction${count !== 1 ? 's' : ''}.`),

  // ═══ Payment Flow ═══
  paymentLowRisk: (amount: number, recipient: string) =>
    speak(`Sending ${amount} rupees to ${recipient}. Please enter your PIN to confirm.`),

  paymentMediumRisk: (amount: number, recipient: string) =>
    speak(`Medium risk detected for ${amount} rupees to ${recipient}. Voice re-verification required.`),

  paymentBlocked: () =>
    speak('Transaction blocked due to high risk. Please try a smaller amount or contact support.'),

  paymentSuccess: (amount: number, recipient: string) =>
    speak(`Payment of ${amount} rupees to ${recipient} completed successfully.`),

  paymentCancelled: () =>
    speak('Payment has been cancelled.'),

  // ═══ PIN ═══
  pinRequired: () =>
    speak('Please enter your four digit PIN.'),

  pinSuccess: () =>
    speak('PIN verified. Please confirm your payment.'),

  pinFailed: () =>
    speak('Incorrect PIN. Please try again.'),

  // ═══ Contact System ═══
  unknownRecipient: (name: string) =>
    speak(`${name} is not in your contacts. You can scan their QR code to pay.`),

  contactFound: (name: string) =>
    speak(`Contact found. Sending to ${name}.`),

  // ═══ QR Scanner ═══
  qrScannerOpened: () =>
    speak('QR scanner is ready. Point your camera at the code.'),

  qrScanned: (name: string, amount: number) =>
    speak(`QR code scanned. ${amount} rupees to ${name}. Enter your PIN to confirm.`),

  qrPaymentDone: (amount: number, name: string) =>
    speak(`QR payment of ${amount} rupees to ${name} completed.`),

  // ═══ Voice Enrollment ═══
  enrollStart: () =>
    speak('Voice enrollment started. Please say the phrase shown on your screen clearly.'),

  enrollSampleRecorded: (n: number, total: number) =>
    speak(`Sample ${n} of ${total} recorded.${n < total ? ' Please record the next sample.' : ' All samples collected.'}`),

  enrollSuccess: () =>
    speak('Your voice ID has been registered. You can now use voice verification for payments.'),

  enrollFailed: () =>
    speak('Voice enrollment failed. Please try recording again in a quiet environment.'),

  // ═══ Errors ═══
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
};
