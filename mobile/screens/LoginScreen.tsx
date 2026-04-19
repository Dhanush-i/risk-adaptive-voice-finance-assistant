import React, { useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  KeyboardAvoidingView, Platform, ActivityIndicator,
} from 'react-native';
import { COLORS } from '../constants/theme';
import { login, register } from '../utils/api';
import { VoiceLines } from '../utils/voiceFeedback';

const DEMO_USER = {
  username: 'demo_user',
  display_name: 'Demo User',
  balance: 24850,
  enrolled: false,
};

export default function LoginScreen({ onLogin }: { onLogin: (user: any) => void }) {
  const [username, setUsername] = useState('');
  const [pin, setPin] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [isRegister, setIsRegister] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    setError('');
    setLoading(true);
    try {
      let data;
      if (isRegister) {
        data = await register(username, displayName, pin);
      } else {
        data = await login(username, pin);
      }
      VoiceLines.loginSuccess(data.user.display_name || data.user.username);
      onLogin(data.user);
    } catch (err: any) {
      setError(err.message || 'Network request failed — try Demo Mode below');
      VoiceLines.loginFailed();
    }
    setLoading(false);
  };

  const handleDemoLogin = async () => {
    VoiceLines.demoMode();
    setLoading(true);
    try {
      // Try logging in first
      const data = await login('demo_user', '1234');
      onLogin({ ...data.user, enrolled: data.user.speaker_enrolled });
    } catch {
      // If user doesn't exist, register it
      try {
        const data = await register('demo_user', 'Demo User', '1234');
        onLogin({ ...data.user, enrolled: data.user.speaker_enrolled ?? false });
      } catch {
        // Offline fallback — no backend transactions will work
        onLogin(DEMO_USER);
      }
    }
    setLoading(false);
  };

  return (
    <KeyboardAvoidingView style={s.container} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <View style={s.card}>
        <Text style={s.logo}>🎙️</Text>
        <Text style={s.title}>VoicePay</Text>
        <Text style={s.subtitle}>Risk-Adaptive Voice Finance</Text>

        <TextInput
          style={s.input}
          placeholder="Username"
          placeholderTextColor={COLORS.textMuted}
          value={username}
          onChangeText={setUsername}
          autoCapitalize="none"
        />
        {isRegister && (
          <TextInput
            style={s.input}
            placeholder="Display Name"
            placeholderTextColor={COLORS.textMuted}
            value={displayName}
            onChangeText={setDisplayName}
          />
        )}
        <TextInput
          style={s.input}
          placeholder="PIN (4-6 digits)"
          placeholderTextColor={COLORS.textMuted}
          value={pin}
          onChangeText={setPin}
          secureTextEntry
          keyboardType="number-pad"
          maxLength={6}
        />

        {error ? <Text style={s.error}>{error}</Text> : null}

        <TouchableOpacity style={s.btn} onPress={handleSubmit} disabled={loading}>
          {loading ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={s.btnText}>{isRegister ? 'Create Account' : 'Sign In'}</Text>
          )}
        </TouchableOpacity>

        <TouchableOpacity onPress={() => setIsRegister(!isRegister)}>
          <Text style={s.toggle}>
            {isRegister ? 'Already have an account? Sign In' : 'New user? Create Account'}
          </Text>
        </TouchableOpacity>

        <View style={s.divider}>
          <View style={s.dividerLine} />
          <Text style={s.dividerText}>OR</Text>
          <View style={s.dividerLine} />
        </View>

        <TouchableOpacity style={s.demoBtn} onPress={handleDemoLogin}>
          <Text style={s.demoBtnText}>🚀 Enter Demo Mode</Text>
        </TouchableOpacity>

        <Text style={s.hint}>Demo mode works offline — no backend needed</Text>
      </View>
    </KeyboardAvoidingView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.bgMain, justifyContent: 'center', padding: 24 },
  card: {
    backgroundColor: COLORS.bgSurface,
    borderRadius: 20,
    padding: 32,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  logo: { fontSize: 48, textAlign: 'center', marginBottom: 8 },
  title: { fontSize: 28, fontWeight: '800', textAlign: 'center', color: COLORS.primary, marginBottom: 4 },
  subtitle: { fontSize: 14, textAlign: 'center', color: COLORS.textMuted, marginBottom: 24 },
  input: {
    backgroundColor: COLORS.bgInput,
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: 12,
    padding: 14,
    color: COLORS.textMain,
    fontSize: 15,
    marginBottom: 12,
  },
  error: {
    color: COLORS.danger,
    fontSize: 13,
    textAlign: 'center',
    marginBottom: 8,
    backgroundColor: 'rgba(248,113,113,0.08)',
    padding: 8,
    borderRadius: 8,
  },
  btn: {
    backgroundColor: COLORS.primary,
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
    marginTop: 8,
  },
  btnText: { color: '#fff', fontWeight: '700', fontSize: 16 },
  toggle: { color: COLORS.primary, textAlign: 'center', marginTop: 16, fontSize: 13 },
  divider: {
    flexDirection: 'row',
    alignItems: 'center',
    marginVertical: 16,
  },
  dividerLine: {
    flex: 1,
    height: 1,
    backgroundColor: COLORS.border,
  },
  dividerText: {
    color: COLORS.textMuted,
    fontSize: 11,
    marginHorizontal: 12,
    fontWeight: '600',
  },
  demoBtn: {
    backgroundColor: 'rgba(139,92,246,0.12)',
    borderWidth: 1,
    borderColor: 'rgba(139,92,246,0.3)',
    borderRadius: 12,
    padding: 14,
    alignItems: 'center',
  },
  demoBtnText: { color: COLORS.primary, fontWeight: '700', fontSize: 15 },
  hint: { color: COLORS.textMuted, textAlign: 'center', marginTop: 12, fontSize: 12 },
});
