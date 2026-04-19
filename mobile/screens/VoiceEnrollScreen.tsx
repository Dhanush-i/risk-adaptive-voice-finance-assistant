import React, { useState, useRef } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, Alert, ActivityIndicator,
  ScrollView,
} from 'react-native';
import { Audio } from 'expo-av';
import { COLORS } from '../constants/theme';
import { enrollSpeaker } from '../utils/api';
import { VoiceLines } from '../utils/voiceFeedback';

const REQUIRED_SAMPLES = 3;
const PROMPTS = [
  '🗣️ Say: "My voice is my password"',
  '🗣️ Say: "Please verify my identity"',
  '🗣️ Say: "I authorize this transaction"',
];

export default function VoiceEnrollScreen({ route, navigation }: any) {
  const user = route?.params?.user;
  const [recordings, setRecordings] = useState<string[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const [enrolling, setEnrolling] = useState(false);
  const [enrolled, setEnrolled] = useState(false);
  const recordingRef = useRef<Audio.Recording | null>(null);

  const currentStep = recordings.length;

  const startRecording = async () => {
    try {
      const perm = await Audio.requestPermissionsAsync();
      if (!perm.granted) {
        Alert.alert('Permission', 'Microphone access is required');
        return;
      }
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });
      const { recording } = await Audio.Recording.createAsync(
        Audio.RecordingOptionsPresets.HIGH_QUALITY
      );
      recordingRef.current = recording;
      setIsRecording(true);

      // Auto-stop after 5 seconds
      setTimeout(async () => {
        if (recordingRef.current) {
          await stopRecording();
        }
      }, 5000);
    } catch (e: any) {
      Alert.alert('Error', e.message);
    }
  };

  const stopRecording = async () => {
    setIsRecording(false);
    const recording = recordingRef.current;
    if (!recording) return;
    try {
      await recording.stopAndUnloadAsync();
    } catch { /* already stopped */ }
    const uri = recording.getURI();
    recordingRef.current = null;
    if (uri) {
      const newRecordings = [...recordings, uri];
      setRecordings(newRecordings);
      VoiceLines.enrollSampleRecorded(newRecordings.length, REQUIRED_SAMPLES);
    }
  };

  const handleEnroll = async () => {
    if (recordings.length < REQUIRED_SAMPLES) return;
    setEnrolling(true);
    try {
      await enrollSpeaker(recordings, user?.username || 'demo_user');
      setEnrolled(true);
      VoiceLines.enrollSuccess();
      Alert.alert(
        '✅ Voice ID Registered',
        'Your voice profile has been saved successfully!',
        [{ text: 'Done', onPress: () => navigation.goBack() }]
      );
    } catch (err: any) {
      Alert.alert('Error', err.message || 'Enrollment failed. Please try again.');
      VoiceLines.enrollFailed();
    }
    setEnrolling(false);
  };

  const resetRecordings = () => {
    setRecordings([]);
    setEnrolled(false);
  };

  return (
    <ScrollView style={s.container} contentContainerStyle={s.content}>
      <TouchableOpacity style={s.backBtn} onPress={() => navigation.goBack()}>
        <Text style={s.backText}>← Back</Text>
      </TouchableOpacity>

      <Text style={s.icon}>🔐</Text>
      <Text style={s.title}>Voice ID Enrollment</Text>
      <Text style={s.subtitle}>
        Record {REQUIRED_SAMPLES} voice samples to register your voiceprint for secure payments.
      </Text>

      {/* Progress Dots */}
      <View style={s.progress}>
        {Array.from({ length: REQUIRED_SAMPLES }).map((_, i) => (
          <View
            key={i}
            style={[
              s.dot,
              i < currentStep ? s.dotDone : i === currentStep ? s.dotActive : s.dotPending,
            ]}
          >
            <Text style={s.dotText}>
              {i < currentStep ? '✓' : i + 1}
            </Text>
          </View>
        ))}
      </View>

      {/* Current Prompt */}
      {currentStep < REQUIRED_SAMPLES && !enrolled && (
        <View style={s.promptCard}>
          <Text style={s.promptText}>
            {PROMPTS[currentStep]}
          </Text>
          <Text style={s.promptHint}>
            Sample {currentStep + 1} of {REQUIRED_SAMPLES}
          </Text>
        </View>
      )}

      {/* Record Button */}
      {currentStep < REQUIRED_SAMPLES && !enrolled && (
        <TouchableOpacity
          style={[s.recordBtn, isRecording && s.recordBtnActive]}
          onPress={isRecording ? stopRecording : startRecording}
        >
          <Text style={s.recordIcon}>{isRecording ? '⏹️' : '🎙️'}</Text>
          <Text style={s.recordLabel}>
            {isRecording ? 'Recording... (auto-stops in 5s)' : 'Tap to Record'}
          </Text>
        </TouchableOpacity>
      )}

      {/* Enroll Button — shown when all samples recorded */}
      {currentStep >= REQUIRED_SAMPLES && !enrolled && (
        <View style={s.enrollSection}>
          <Text style={s.enrollReady}>✅ All {REQUIRED_SAMPLES} samples recorded!</Text>
          <TouchableOpacity
            style={s.enrollBtn}
            onPress={handleEnroll}
            disabled={enrolling}
          >
            {enrolling ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={s.enrollBtnText}>Register Voice ID</Text>
            )}
          </TouchableOpacity>
          <TouchableOpacity onPress={resetRecordings} style={s.resetBtn}>
            <Text style={s.resetText}>🔄 Re-record all samples</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Success State */}
      {enrolled && (
        <View style={s.successCard}>
          <Text style={s.successIcon}>🎉</Text>
          <Text style={s.successTitle}>Voice ID Registered!</Text>
          <Text style={s.successSub}>
            Your voice will now be used to verify your identity during payments.
          </Text>
        </View>
      )}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.bgMain },
  content: { padding: 24, paddingTop: 50, alignItems: 'center' },
  backBtn: { alignSelf: 'flex-start', marginBottom: 20 },
  backText: { color: COLORS.textMuted, fontSize: 15 },
  icon: { fontSize: 56, marginBottom: 8 },
  title: { fontSize: 24, fontWeight: '800', color: COLORS.textMain, marginBottom: 6, textAlign: 'center' },
  subtitle: { fontSize: 14, color: COLORS.textSecondary, textAlign: 'center', marginBottom: 24, lineHeight: 20 },
  progress: { flexDirection: 'row', gap: 16, marginBottom: 24 },
  dot: {
    width: 40, height: 40, borderRadius: 20,
    justifyContent: 'center', alignItems: 'center',
  },
  dotDone: { backgroundColor: COLORS.success },
  dotActive: { backgroundColor: COLORS.primary },
  dotPending: { backgroundColor: COLORS.bgCard, borderWidth: 1, borderColor: COLORS.border },
  dotText: { color: '#fff', fontWeight: '700', fontSize: 14 },
  promptCard: {
    backgroundColor: COLORS.bgSurface, borderRadius: 16, padding: 20,
    width: '100%', borderWidth: 1, borderColor: COLORS.border, alignItems: 'center',
    marginBottom: 20,
  },
  promptText: { fontSize: 18, fontWeight: '600', color: COLORS.textMain, textAlign: 'center' },
  promptHint: { fontSize: 12, color: COLORS.textMuted, marginTop: 8 },
  recordBtn: {
    width: 120, height: 120, borderRadius: 60,
    backgroundColor: COLORS.primary, justifyContent: 'center', alignItems: 'center',
    shadowColor: COLORS.primary, shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.4, shadowRadius: 16, elevation: 8, marginVertical: 20,
  },
  recordBtnActive: { backgroundColor: COLORS.danger },
  recordIcon: { fontSize: 36 },
  recordLabel: { fontSize: 11, color: '#fff', fontWeight: '600', marginTop: 4, textAlign: 'center' },
  enrollSection: { alignItems: 'center', width: '100%', marginTop: 16 },
  enrollReady: { fontSize: 16, fontWeight: '600', color: COLORS.success, marginBottom: 16 },
  enrollBtn: {
    backgroundColor: COLORS.primary, borderRadius: 12, padding: 16,
    alignItems: 'center', width: '100%',
  },
  enrollBtnText: { color: '#fff', fontWeight: '700', fontSize: 16 },
  resetBtn: { marginTop: 12 },
  resetText: { color: COLORS.textMuted, fontSize: 13 },
  successCard: {
    backgroundColor: COLORS.bgSurface, borderRadius: 16, padding: 24,
    width: '100%', alignItems: 'center', borderWidth: 1, borderColor: 'rgba(52,211,153,0.2)',
    marginTop: 20,
  },
  successIcon: { fontSize: 48, marginBottom: 8 },
  successTitle: { fontSize: 20, fontWeight: '800', color: COLORS.success, marginBottom: 6 },
  successSub: { fontSize: 14, color: COLORS.textSecondary, textAlign: 'center', lineHeight: 20 },
});
