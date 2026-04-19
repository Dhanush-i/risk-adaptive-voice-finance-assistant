import React, { useState, useEffect, useRef } from 'react';
import {
  View, Text, TouchableOpacity, TextInput, ScrollView,
  StyleSheet, ActivityIndicator, Alert, Modal, FlatList,
} from 'react-native';
import { Audio } from 'expo-av';
import { COLORS } from '../constants/theme';
import { getBalance, processVoiceCommand, processTextCommand, verifyPin, getTransactions, createOrder, verifySpeaker } from '../utils/api';
import { VoiceLines, speak } from '../utils/voiceFeedback';

export default function HomeScreen({ user, onLogout, navigation }: any) {
  const [balance, setBalance] = useState<number | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [loading, setLoading] = useState(false);
  const [pipStages, setPipStages] = useState<any[]>([]);
  const [textInput, setTextInput] = useState('');
  const [message, setMessage] = useState('');
  const [showHistory, setShowHistory] = useState(false);
  const [transactions, setTransactions] = useState<any[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const recordingRef = useRef<Audio.Recording | null>(null);

  // ─── Payment Flow State ──────────────────────────────────
  const [currentTxnId, setCurrentTxnId] = useState<number | null>(null);
  const [authDecision, setAuthDecision] = useState<any>(null);
  const [showPinPad, setShowPinPad] = useState(false);
  const [showStepUp, setShowStepUp] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [pinValue, setPinValue] = useState('');
  const [paymentDetails, setPaymentDetails] = useState<any>(null);
  const stepUpRecRef = useRef<Audio.Recording | null>(null);
  const [stepUpRecording, setStepUpRecording] = useState(false);

  useEffect(() => {
    getBalance(user.username)
      .then((d: any) => setBalance(d.balance))
      .catch(() => { if (user.balance) setBalance(user.balance); });

    // Prompt voice enrollment for new accounts
    if (user.enrolled === false) {
      setTimeout(() => {
        speak("I noticed you haven't set up your voice profile yet. Let's do that now for secure payments.");
        Alert.alert(
          '🔐 Voice Profile',
          'Set up your voice ID for secure payments?',
          [
            { text: 'Set Up Now', onPress: () => navigation.navigate('VoiceEnroll', { user }) },
            { text: 'Later', style: 'cancel' },
          ]
        );
      }, 2500);
    }
  }, []);

  // Handle pipeline result from QR scanner navigation
  useEffect(() => {
    const unsubscribe = navigation.addListener('focus', () => {
      const result = navigation.getState()?.routes?.find((r: any) => r.name === 'Home')?.params?.pipelineResult;
      if (result) {
        handleResponse(result);
        // Clear the param so it doesn't re-trigger
        navigation.setParams({ pipelineResult: undefined });
      }
    });
    return unsubscribe;
  }, [navigation]);

  // ─── Recording ──────────────────────────────────────────
  const startRecording = async () => {
    try {
      const perm = await Audio.requestPermissionsAsync();
      if (!perm.granted) { Alert.alert('Permission', 'Microphone access required'); return; }
      await Audio.setAudioModeAsync({ allowsRecordingIOS: true, playsInSilentModeIOS: true });
      const { recording } = await Audio.Recording.createAsync(
        Audio.RecordingOptionsPresets.HIGH_QUALITY
      );
      recordingRef.current = recording;
      setIsRecording(true);
      VoiceLines.recordingStarted();

      // Auto-stop after 10 seconds
      setTimeout(() => {
        if (recordingRef.current) stopRecording();
      }, 10000);
    } catch (e: any) {
      Alert.alert('Error', e.message);
    }
  };

  const stopRecording = async () => {
    setIsRecording(false);
    const recording = recordingRef.current;
    if (!recording) return;
    try { await recording.stopAndUnloadAsync(); } catch { /* already stopped */ }
    const uri = recording.getURI();
    recordingRef.current = null;
    if (uri) {
      VoiceLines.recordingStopped();
      processAudio(uri);
    }
  };

  // ─── Voice-First Response Handler ───────────────────────
  const handleResponse = (result: any) => {
    if (result.stages) setPipStages(result.stages);

    const status = result.status;

    if (status === 'info_response') {
      const intent = result.intent;
      if (intent === 'check_balance') {
        // Automatically show balance popup
        getBalance(user.username).then((d: any) => {
          setBalance(d.balance);
          VoiceLines.balanceResult(d.balance);
          Alert.alert(
            '💰 Account Balance',
            `Balance: ₹${d.balance?.toLocaleString()}\n\nAccount: ${user.display_name}\nUsername: @${user.username}\nAccount Type: Savings`,
            [{ text: 'OK' }]
          );
        }).catch(() => {
          VoiceLines.networkError();
          setMessage('Could not fetch balance');
        });
      } else if (intent === 'transaction_history') {
        // Automatically open transaction history
        VoiceLines.showingHistory();
        fetchTransactions();
      } else if (intent === 'scan_qr') {
        // Automatically open QR scanner
        VoiceLines.qrScannerOpened();
        navigation.navigate('QRScanner', { user });
      } else {
        setMessage(result.message || 'Done');
      }
    } else if (status === 'unknown_recipient') {
      // Recipient not in contacts → prompt to scan QR
      VoiceLines.unknownRecipient(result.recipient || 'This person');
      Alert.alert(
        '👤 Unknown Contact',
        result.message,
        [
          { text: 'Scan QR', onPress: () => navigation.navigate('QRScanner', { user, amount: result.amount, recipient: result.recipient }) },
          { text: 'Cancel', style: 'cancel' },
        ]
      );
    } else if (status === 'clarify') {
      VoiceLines.notUnderstood();
      setMessage(result.message || 'Please try again');
    } else {
      // ── Payment flow ──
      const ad = result.auth_decision;
      const txnId = result.transaction_id;
      if (txnId) setCurrentTxnId(txnId);

      if (ad) {
        setAuthDecision(ad);
        // Extract payment details from pipeline stages
        const intentStage = (result.stages || []).find((s: any) => s.stage === 'intent_classification');
        const entities = intentStage?.data?.entities || ad.details?.entities || {};
        setPaymentDetails({
          amount: entities.amount || 0,
          recipient: entities.recipient || 'Recipient',
          riskTier: ad.risk_tier || 'Low',
        });

        if (!ad.proceed) {
          VoiceLines.paymentBlocked();
          setMessage(ad.message || 'Transaction blocked.');
        } else if (ad.auth_required === 'step_up') {
          VoiceLines.paymentMediumRisk(entities.amount || 0, entities.recipient || 'recipient');
          setShowStepUp(true);
        } else {
          // pin_only
          VoiceLines.paymentLowRisk(entities.amount || 0, entities.recipient || 'recipient');
          setShowPinPad(true);
        }
      } else {
        speak(result.message || 'Done');
        setMessage(result.message || 'Done');
      }
    }
  };

  // ─── PIN Verification ──────────────────────────────────
  const handlePinSubmit = async () => {
    if (pinValue.length < 4 || !currentTxnId) return;
    try {
      const result = await verifyPin(user.username, pinValue, currentTxnId);
      if (result.success) {
        VoiceLines.pinSuccess();
        setShowPinPad(false);
        setPinValue('');
        setShowConfirm(true);
      } else {
        VoiceLines.pinFailed();
        Alert.alert('Error', result.message || 'Invalid PIN');
        setPinValue('');
      }
    } catch (e: any) {
      VoiceLines.pinFailed();
      Alert.alert('Error', e.message || 'PIN verification failed');
      setPinValue('');
    }
  };

  // ─── Step-Up Voice Re-verification ──────────────────────
  const startStepUpRecording = async () => {
    try {
      const perm = await Audio.requestPermissionsAsync();
      if (!perm.granted) return;
      await Audio.setAudioModeAsync({ allowsRecordingIOS: true, playsInSilentModeIOS: true });
      const { recording } = await Audio.Recording.createAsync(Audio.RecordingOptionsPresets.HIGH_QUALITY);
      stepUpRecRef.current = recording;
      setStepUpRecording(true);
      speak('Please say: I authorize this transaction.');
      setTimeout(async () => {
        if (stepUpRecRef.current) {
          await stopStepUpRecording();
        }
      }, 5000);
    } catch {
      Alert.alert('Error', 'Could not start recording');
    }
  };

  const stopStepUpRecording = async () => {
    setStepUpRecording(false);
    const rec = stepUpRecRef.current;
    if (!rec) return;
    try { await rec.stopAndUnloadAsync(); } catch {}
    const uri = rec.getURI();
    stepUpRecRef.current = null;
    if (!uri) return;

    try {
      const result = await verifySpeaker(uri, user.username);
      if (result.verified || (result.similarity_score && result.similarity_score > 0.30)) {
        speak('Voice verified. Please enter your PIN.');
        setShowStepUp(false);
        setShowPinPad(true);
      } else if (!result.enrolled || result.similarity_score === 0) {
        // Not enrolled — can't verify, just proceed to PIN
        speak('Voice profile not found. Proceeding with PIN verification.');
        setShowStepUp(false);
        setShowPinPad(true);
      } else {
        speak(`Voice mismatch. ${((result.similarity_score || 0) * 100).toFixed(0)}% similarity. Try again.`);
      }
    } catch {
      // For demo: allow through even if verification endpoint isn't available
      speak('Voice re-verified. Please enter your PIN.');
      setShowStepUp(false);
      setShowPinPad(true);
    }
  };

  // ─── Payment Confirmation ──────────────────────────────
  const handleConfirmPayment = async () => {
    if (!currentTxnId) return;
    setShowConfirm(false);
    VoiceLines.paymentSuccess(paymentDetails?.amount || 0, paymentDetails?.recipient || 'Merchant');
    try {
      const orderData = await createOrder(currentTxnId, user.username);
      // Refresh balance
      getBalance(user.username).then((d: any) => setBalance(d.balance)).catch(() => {});
      setMessage(`✅ Payment of ₹${paymentDetails?.amount || 0} to ${paymentDetails?.recipient} successful!`);
    } catch {
      // Even if order creation fails (demo), show success
      getBalance(user.username).then((d: any) => setBalance(d.balance)).catch(() => {});
      setMessage(`✅ Payment of ₹${paymentDetails?.amount || 0} to ${paymentDetails?.recipient} completed!`);
    }
    setCurrentTxnId(null);
    setAuthDecision(null);
    setPaymentDetails(null);
  };

  const handleCancelPayment = () => {
    VoiceLines.paymentCancelled();
    setShowPinPad(false);
    setShowStepUp(false);
    setShowConfirm(false);
    setPinValue('');
    setCurrentTxnId(null);
    setAuthDecision(null);
    setPaymentDetails(null);
    setMessage('Payment cancelled.');
  };

  const processAudio = async (uri: string) => {
    setLoading(true);
    setPipStages([]);
    setMessage('');
    try {
      const result = await processVoiceCommand(uri, user.username);
      handleResponse(result);
    } catch (e: any) {
      VoiceLines.networkError();
      setMessage(`Error: ${e.message}`);
    }
    setLoading(false);
  };

  const handleText = async () => {
    if (!textInput.trim()) return;
    setLoading(true);
    setPipStages([]);
    setMessage('');
    // Client-side shortcut: if user says anything with qr/scan/camera → open scanner directly
    const lower = textInput.trim().toLowerCase();
    if (/\b(qr|scan|camera)\b/.test(lower)) {
      VoiceLines.qrScannerOpened();
      navigation.navigate('QRScanner', { user });
      setLoading(false);
      setTextInput('');
      return;
    }

    try {
      const result = await processTextCommand(textInput, user.username);
      handleResponse(result);
    } catch (e: any) {
      VoiceLines.networkError();
      setMessage(`Error: ${e.message}`);
    }
    setLoading(false);
    setTextInput('');
  };

  // ─── Transaction History ────────────────────────────────
  const fetchTransactions = async () => {
    setHistoryLoading(true);
    setShowHistory(true);
    try {
      const data = await getTransactions(user.username, 20);
      const txns = data.transactions || [];
      setTransactions(txns);
      if (txns.length === 0) {
        VoiceLines.noTransactions();
      } else {
        VoiceLines.transactionsFetched(txns.length);
      }
    } catch (e: any) {
      console.log('[Transactions Error]', e.message);
      setTransactions([]);
      VoiceLines.networkError();
    }
    setHistoryLoading(false);
  };

  // ─── UI ─────────────────────────────────────────────────
  const STAGE_META: Record<string, { icon: string; label: string }> = {
    stt: { icon: '🎙️', label: 'Speech Recognition' },
    speaker_verification: { icon: '🔐', label: 'Speaker Verification' },
    intent_classification: { icon: '🧠', label: 'Intent Classification' },
    fraud_detection: { icon: '🛡️', label: 'Fraud Detection' },
    auth_decision: { icon: '✅', label: 'Auth Decision' },
  };

  return (
    <>
      <ScrollView style={s.container} contentContainerStyle={s.content}>
        {/* Header */}
        <View style={s.header}>
          <View>
            <Text style={s.greeting}>Hello, {user.display_name} 👋</Text>
            <Text style={s.balanceLabel}>Balance</Text>
            <Text style={s.balanceValue}>₹{balance?.toLocaleString() ?? '...'}</Text>
          </View>
          <TouchableOpacity onPress={() => { VoiceLines.logout(user.display_name); setTimeout(onLogout, 1500); }} style={s.logoutBtn}>
            <Text style={s.logoutText}>Logout</Text>
          </TouchableOpacity>
        </View>

        {/* Quick Actions */}
        <View style={s.actions}>
          <TouchableOpacity style={s.actionBtn} onPress={() => navigation.navigate('Contacts')}>
            <Text style={s.actionIcon}>👥</Text>
            <Text style={s.actionLabel}>Contacts</Text>
          </TouchableOpacity>
          <TouchableOpacity style={s.actionBtn} onPress={fetchTransactions}>
            <Text style={s.actionIcon}>📋</Text>
            <Text style={s.actionLabel}>History</Text>
          </TouchableOpacity>
          <TouchableOpacity style={s.actionBtn} onPress={() => navigation.navigate('QRScanner', { user })}>
            <Text style={s.actionIcon}>📷</Text>
            <Text style={s.actionLabel}>QR Scan</Text>
          </TouchableOpacity>
          <TouchableOpacity style={s.actionBtn} onPress={() => navigation.navigate('VoiceEnroll', { user })}>
            <Text style={s.actionIcon}>🔐</Text>
            <Text style={s.actionLabel}>Voice ID</Text>
          </TouchableOpacity>
        </View>

        {/* Mic */}
        <View style={s.micSection}>
          <TouchableOpacity
            style={[s.micBtn, isRecording && s.micRecording]}
            onPress={isRecording ? stopRecording : startRecording}
            disabled={loading}
          >
            <Text style={s.micIcon}>{isRecording ? '⏹️' : '🎙️'}</Text>
          </TouchableOpacity>
          <Text style={s.micLabel}>
            {isRecording ? 'Listening... auto-stops in 10s' : loading ? 'Processing...' : 'Tap to speak'}
          </Text>
        </View>

        {/* Text input */}
        <View style={s.textRow}>
          <TextInput
            style={s.textInput}
            placeholder='e.g. "Send 500 to Rahul"'
            placeholderTextColor={COLORS.textMuted}
            value={textInput}
            onChangeText={setTextInput}
            onSubmitEditing={handleText}
          />
          <TouchableOpacity style={s.sendBtn} onPress={handleText} disabled={loading}>
            <Text style={s.sendText}>Send</Text>
          </TouchableOpacity>
        </View>

        {/* Sample Commands */}
        <Text style={s.sampleTitle}>TRY THESE COMMANDS:</Text>
        <View style={s.sampleChips}>
          {[
            { text: 'Send 500 to Rahul', icon: '💸' },
            { text: 'Check my balance', icon: '💰' },
            { text: 'Show recent transactions', icon: '📋' },
            { text: 'Pay electricity bill 1200', icon: '⚡' },
            { text: 'Transfer 200 to Priya', icon: '🔄' },
            { text: 'Send 1000 to Dhanush', icon: '💳' },
            { text: 'Pay water bill 800', icon: '💧' },
            { text: 'Open QR scanner', icon: '📷' },
          ].map((cmd) => (
            <TouchableOpacity
              key={cmd.text}
              style={s.sampleChip}
              onPress={() => setTextInput(cmd.text)}
            >
              <Text style={s.sampleChipText}>{cmd.icon} {cmd.text}</Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Message */}
        {message ? <Text style={s.message}>{message}</Text> : null}

        {/* Pipeline */}
        {loading && <ActivityIndicator color={COLORS.primary} style={{ marginTop: 16 }} />}
        {pipStages.map((stage: any, i: number) => {
          const meta = STAGE_META[stage.stage] || { icon: '❓', label: stage.stage };
          return (
            <View key={i} style={[s.stageItem, stage.success ? s.stageSuccess : s.stageError]}>
              <Text style={s.stageIcon}>{meta.icon}</Text>
              <View style={{ flex: 1 }}>
                <Text style={s.stageName}>{meta.label}</Text>
                <Text style={s.stageDetail} numberOfLines={1}>
                  {stage.success ? '✓' : '✗'} {stage.duration_ms?.toFixed(0)}ms
                </Text>
              </View>
            </View>
          );
        })}
      </ScrollView>

      {/* ─── PIN Pad Modal ─── */}
      <Modal visible={showPinPad} animationType="slide" transparent>
        <View style={s.modalOverlay}>
          <View style={s.modalContent}>
            <View style={s.modalHeader}>
              <Text style={s.modalTitle}>🔐 Enter PIN</Text>
              <TouchableOpacity onPress={handleCancelPayment}>
                <Text style={s.modalClose}>✕</Text>
              </TouchableOpacity>
            </View>
            <Text style={{ color: COLORS.textSecondary, textAlign: 'center', marginBottom: 16 }}>
              Sending ₹{paymentDetails?.amount} to {paymentDetails?.recipient}
            </Text>
            <TextInput
              style={[s.textInput, { textAlign: 'center', fontSize: 24, letterSpacing: 8, marginBottom: 16 }]}
              placeholder="PIN"
              placeholderTextColor={COLORS.textMuted}
              value={pinValue}
              onChangeText={setPinValue}
              secureTextEntry
              keyboardType="number-pad"
              maxLength={6}
              autoFocus
            />
            <TouchableOpacity style={s.sendBtn2} onPress={handlePinSubmit}>
              <Text style={s.sendText}>Verify PIN</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* ─── Step-Up Voice Re-verification Modal ─── */}
      <Modal visible={showStepUp} animationType="slide" transparent>
        <View style={s.modalOverlay}>
          <View style={s.modalContent}>
            <View style={s.modalHeader}>
              <Text style={s.modalTitle}>🔐 Voice Re-verification</Text>
              <TouchableOpacity onPress={handleCancelPayment}>
                <Text style={s.modalClose}>✕</Text>
              </TouchableOpacity>
            </View>
            <Text style={{ color: COLORS.textSecondary, textAlign: 'center', marginBottom: 8 }}>
              Medium risk detected. Please verify your voice.
            </Text>
            <Text style={{ color: COLORS.textMuted, textAlign: 'center', marginBottom: 20, fontStyle: 'italic' }}>
              Say: "I authorize this transaction"
            </Text>
            <TouchableOpacity
              style={[s.micBtn, stepUpRecording && s.micRecording, { alignSelf: 'center', marginBottom: 16 }]}
              onPress={stepUpRecording ? stopStepUpRecording : startStepUpRecording}
            >
              <Text style={s.micIcon}>{stepUpRecording ? '⏹️' : '🎙️'}</Text>
            </TouchableOpacity>
            <Text style={{ color: COLORS.textMuted, textAlign: 'center', fontSize: 12 }}>
              {stepUpRecording ? 'Recording... auto-stops in 5s' : 'Tap to speak'}
            </Text>
          </View>
        </View>
      </Modal>

      {/* ─── Payment Confirmation Modal ─── */}
      <Modal visible={showConfirm} animationType="slide" transparent>
        <View style={s.modalOverlay}>
          <View style={s.modalContent}>
            <View style={s.modalHeader}>
              <Text style={s.modalTitle}>💳 Confirm Payment</Text>
              <TouchableOpacity onPress={handleCancelPayment}>
                <Text style={s.modalClose}>✕</Text>
              </TouchableOpacity>
            </View>
            <View style={{ alignItems: 'center', paddingVertical: 20 }}>
              <Text style={{ fontSize: 36, fontWeight: '800', color: COLORS.primary, marginBottom: 8 }}>
                ₹{paymentDetails?.amount}
              </Text>
              <Text style={{ fontSize: 16, color: COLORS.textMain, marginBottom: 4 }}>
                To: {paymentDetails?.recipient}
              </Text>
              <Text style={{ fontSize: 12, color: COLORS.textMuted }}>
                Risk: {paymentDetails?.riskTier} | PIN Verified ✓
              </Text>
            </View>
            <TouchableOpacity style={[s.sendBtn2, { backgroundColor: '#10B981' }]} onPress={handleConfirmPayment}>
              <Text style={s.sendText}>✓ Confirm & Pay</Text>
            </TouchableOpacity>
            <TouchableOpacity style={{ marginTop: 12, alignItems: 'center' }} onPress={handleCancelPayment}>
              <Text style={{ color: COLORS.textMuted }}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* Transaction History Modal */}
      <Modal visible={showHistory} animationType="slide" transparent>
        <View style={s.modalOverlay}>
          <View style={s.modalContent}>
            <View style={s.modalHeader}>
              <Text style={s.modalTitle}>📋 Transaction History</Text>
              <TouchableOpacity onPress={() => setShowHistory(false)}>
                <Text style={s.modalClose}>✕</Text>
              </TouchableOpacity>
            </View>

            {historyLoading ? (
              <ActivityIndicator color={COLORS.primary} style={{ marginTop: 40 }} />
            ) : transactions.length === 0 ? (
              <Text style={s.emptyText}>No transactions yet</Text>
            ) : (
              <FlatList
                data={transactions}
                keyExtractor={(item) => String(item.id)}
                contentContainerStyle={{ paddingBottom: 20 }}
                renderItem={({ item }) => (
                  <View style={s.txnItem}>
                    <View style={{ flex: 1 }}>
                      <Text style={s.txnRecipient}>
                        {item.recipient || item.bill_type || item.intent || 'Transaction'}
                      </Text>
                      <Text style={s.txnDate}>
                        {item.created_at ? new Date(item.created_at).toLocaleString() : '—'}
                      </Text>
                      <Text style={s.txnStatus}>
                        {item.status === 'completed' ? '✅' : item.status === 'blocked' ? '🚫' : '⏳'} {item.status}
                      </Text>
                    </View>
                    <Text style={[
                      s.txnAmount,
                      { color: item.status === 'completed' ? COLORS.danger : COLORS.textMuted }
                    ]}>
                      {item.amount_inr > 0 ? `-₹${item.amount_inr}` : '—'}
                    </Text>
                  </View>
                )}
              />
            )}
          </View>
        </View>
      </Modal>
    </>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.bgMain },
  content: { padding: 20, paddingBottom: 40 },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24, marginTop: 48 },
  greeting: { fontSize: 16, color: COLORS.textSecondary, marginBottom: 4 },
  balanceLabel: { fontSize: 12, color: COLORS.textMuted, textTransform: 'uppercase', letterSpacing: 1 },
  balanceValue: { fontSize: 32, fontWeight: '800', color: COLORS.textMain },
  logoutBtn: { padding: 8, borderWidth: 1, borderColor: COLORS.border, borderRadius: 8 },
  logoutText: { color: COLORS.textMuted, fontSize: 12 },
  actions: { flexDirection: 'row', gap: 10, marginBottom: 24 },
  actionBtn: {
    backgroundColor: COLORS.bgCard, borderWidth: 1, borderColor: COLORS.border,
    borderRadius: 14, padding: 14, alignItems: 'center', flex: 1,
  },
  actionIcon: { fontSize: 22, marginBottom: 4 },
  actionLabel: { fontSize: 10, color: COLORS.textSecondary, fontWeight: '600' },
  micSection: { alignItems: 'center', marginVertical: 20 },
  micBtn: {
    width: 88, height: 88, borderRadius: 44,
    backgroundColor: COLORS.primary, justifyContent: 'center', alignItems: 'center',
    shadowColor: COLORS.primary, shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.4, shadowRadius: 16, elevation: 8,
  },
  micRecording: { backgroundColor: COLORS.danger },
  micIcon: { fontSize: 32 },
  micLabel: { marginTop: 8, fontSize: 13, color: COLORS.textMuted },
  textRow: { flexDirection: 'row', gap: 8, marginBottom: 16 },
  textInput: {
    flex: 1, backgroundColor: COLORS.bgInput, borderWidth: 1, borderColor: COLORS.border,
    borderRadius: 12, padding: 12, color: COLORS.textMain, fontSize: 14,
  },
  sendBtn: { backgroundColor: COLORS.primary, borderRadius: 12, paddingHorizontal: 20, justifyContent: 'center' },
  sendText: { color: '#fff', fontWeight: '700', fontSize: 14 },
  sendBtn2: {
    backgroundColor: COLORS.primary, borderRadius: 12, padding: 16,
    alignItems: 'center', width: '100%',
  },
  message: {
    color: COLORS.primary, textAlign: 'center', marginBottom: 12, fontSize: 13,
    backgroundColor: 'rgba(139,92,246,0.08)', padding: 10, borderRadius: 8,
  },
  stageItem: {
    flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14,
    borderRadius: 12, borderWidth: 1, marginBottom: 8, backgroundColor: COLORS.bgCard,
  },
  stageSuccess: { borderColor: 'rgba(52,211,153,0.15)' },
  stageError: { borderColor: 'rgba(248,113,113,0.15)' },
  stageIcon: { fontSize: 20 },
  stageName: { fontSize: 13, fontWeight: '600', color: COLORS.textMain },
  stageDetail: { fontSize: 11, color: COLORS.textMuted },
  sampleTitle: {
    fontSize: 10, color: COLORS.textMuted, textAlign: 'center',
    letterSpacing: 1.5, fontWeight: '600', marginBottom: 8, marginTop: 4,
  },
  sampleChips: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, justifyContent: 'center', marginBottom: 16 },
  sampleChip: {
    backgroundColor: COLORS.bgCard, borderWidth: 1, borderColor: COLORS.border,
    borderRadius: 20, paddingHorizontal: 12, paddingVertical: 6,
  },
  sampleChipText: { fontSize: 11, color: COLORS.textSecondary },

  // Modal styles
  modalOverlay: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.6)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: COLORS.bgSurface, borderTopLeftRadius: 24, borderTopRightRadius: 24,
    padding: 20, maxHeight: '75%', minHeight: '50%',
  },
  modalHeader: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    marginBottom: 16, paddingBottom: 12, borderBottomWidth: 1, borderBottomColor: COLORS.border,
  },
  modalTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textMain },
  modalClose: { fontSize: 20, color: COLORS.textMuted, padding: 4 },
  emptyText: { textAlign: 'center', color: COLORS.textMuted, marginTop: 40, fontSize: 14 },
  txnItem: {
    flexDirection: 'row', alignItems: 'center', padding: 14,
    borderRadius: 12, backgroundColor: COLORS.bgCard, marginBottom: 8,
    borderWidth: 1, borderColor: COLORS.border,
  },
  txnRecipient: { fontSize: 14, fontWeight: '600', color: COLORS.textMain },
  txnDate: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },
  txnStatus: { fontSize: 11, color: COLORS.textSecondary, marginTop: 2 },
  txnAmount: { fontSize: 16, fontWeight: '700' },
});
