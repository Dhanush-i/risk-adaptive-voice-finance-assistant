import { API_BASE_URL } from '../constants/theme';

let authToken: string | null = null;

export function setToken(token: string) { authToken = token; }
export function clearToken() { authToken = null; }

function headers(extra: Record<string, string> = {}) {
  const h: Record<string, string> = { ...extra };
  if (authToken) h['Authorization'] = `Bearer ${authToken}`;
  return h;
}

async function apiGet(path: string) {
  const res = await fetch(`${API_BASE_URL}${path}`, { headers: headers() });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'API error');
  }
  return res.json();
}

async function apiPost(path: string, body: any, isForm = false) {
  const opts: RequestInit = { method: 'POST' };
  if (isForm) {
    opts.headers = headers();
    opts.body = body;
  } else {
    opts.headers = headers({ 'Content-Type': 'application/json' });
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(`${API_BASE_URL}${path}`, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'API error');
  }
  return res.json();
}

export async function login(username: string, pin: string) {
  const res = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, pin }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Login failed' }));
    throw new Error(err.detail);
  }
  const data = await res.json();
  setToken(data.token);
  return data;
}

export async function register(username: string, displayName: string, pin: string) {
  const res = await fetch(`${API_BASE_URL}/api/v1/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, display_name: displayName, pin }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Registration failed' }));
    throw new Error(err.detail);
  }
  const data = await res.json();
  setToken(data.token);
  return data;
}

export const getBalance = (username: string) => apiGet(`/api/v1/users/${username}/balance`);
export const getTransactions = (username: string, limit = 20) =>
  apiGet(`/api/v1/transactions/?username=${username}&limit=${limit}`);

export function processVoiceCommand(audioUri: string, userId: string) {
  const form = new FormData();
  form.append('audio', { uri: audioUri, name: 'recording.wav', type: 'audio/wav' } as any);
  form.append('user_id', userId);
  return apiPost('/api/v1/voice/process', form, true);
}

export function processTextCommand(text: string, userId: string) {
  const form = new FormData();
  form.append('text', text);
  form.append('user_id', userId);
  form.append('sv_override', 'true');
  return apiPost('/api/v1/voice/process-text', form, true);
}

export function enrollSpeaker(audioUris: string[], userId: string) {
  const form = new FormData();
  form.append('user_id', userId);
  audioUris.forEach((uri, i) =>
    form.append('audio_files', { uri, name: `enroll_${i}.wav`, type: 'audio/wav' } as any)
  );
  return apiPost('/api/v1/voice/enroll', form, true);
}

export const verifyPin = (userId: string, pin: string, transactionId: number) =>
  apiPost('/api/v1/payments/verify-pin', { user_id: userId, pin, transaction_id: transactionId });

export const createOrder = (transactionId: number, username: string) =>
  apiPost('/api/v1/payments/create-order', { transaction_id: transactionId, username });

export const verifySpeaker = (audioUri: string, userId: string) => {
  const form = new FormData();
  form.append('audio', { uri: audioUri, name: 'verify.wav', type: 'audio/wav' } as any);
  form.append('user_id', userId);
  return apiPost('/api/v1/voice/verify', form, true);
};
