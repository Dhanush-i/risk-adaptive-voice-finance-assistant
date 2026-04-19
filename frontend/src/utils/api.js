const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

// --- Token Management ---
let _authToken = null;

export function setAuthToken(token) {
  _authToken = token;
}

export function getAuthToken() {
  return _authToken;
}

export function clearAuthToken() {
  _authToken = null;
}

// --- Core Request Helpers ---

function authHeaders(extraHeaders = {}) {
  const headers = { ...extraHeaders };
  if (_authToken) {
    headers['Authorization'] = `Bearer ${_authToken}`;
  }
  return headers;
}

export async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: authHeaders(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'API error');
  }
  return res.json();
}

export async function apiPost(path, body, isForm = false) {
  const options = { method: 'POST' };
  if (isForm) {
    options.headers = authHeaders();
    options.body = body; // FormData — browser sets Content-Type
  } else {
    options.headers = authHeaders({ 'Content-Type': 'application/json' });
    options.body = JSON.stringify(body);
  }
  const res = await fetch(`${API_BASE}${path}`, options);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'API error');
  }
  return res.json();
}

// --- Auth ---

export async function login(username, pin) {
  const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, pin }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Login failed');
  }
  const data = await res.json();
  setAuthToken(data.token);
  return data;
}

export async function register(username, displayName, pin) {
  const res = await fetch(`${API_BASE}/api/v1/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, display_name: displayName, pin }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Registration failed');
  }
  const data = await res.json();
  setAuthToken(data.token);
  return data;
}

// --- API Functions ---

export const getUser = (username) => apiGet(`/api/v1/users/${username}`);
export const getBalance = (username) => apiGet(`/api/v1/users/${username}/balance`);
export const getTransactions = (username, limit = 20) =>
  apiGet(`/api/v1/transactions/?username=${username}&limit=${limit}`);
export const getTransactionDetail = (id) => apiGet(`/api/v1/transactions/${id}`);

export function processTextCommand(text, userId, svOverride = true) {
  const form = new FormData();
  form.append('text', text);
  form.append('user_id', userId);
  form.append('sv_override', svOverride.toString());
  return apiPost('/api/v1/voice/process-text', form, true);
}

export function processVoiceCommand(audioBlob, userId) {
  const form = new FormData();
  form.append('audio', audioBlob, 'recording.webm');
  form.append('user_id', userId);
  return apiPost('/api/v1/voice/process', form, true);
}

/**
 * Process a voice command with SSE streaming.
 * Calls onStage(stageResult) as each pipeline stage completes in real-time.
 * Returns the final response.
 */
export async function processVoiceCommandSSE(audioBlob, userId, onStage) {
  const form = new FormData();
  form.append('audio', audioBlob, 'recording.webm');
  form.append('user_id', userId);

  const res = await fetch(`${API_BASE}/api/v1/voice/process-stream`, {
    method: 'POST',
    headers: authHeaders(),
    body: form,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'SSE processing failed');
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let finalResult = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // Parse SSE events from buffer
    const lines = buffer.split('\n');
    buffer = lines.pop(); // Keep incomplete line in buffer

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const data = JSON.parse(line.slice(6));
          if (data.is_final) {
            finalResult = data;
          } else if (onStage) {
            onStage(data);
          }
        } catch (e) {
          console.warn('[SSE] Failed to parse event:', line);
        }
      }
    }
  }

  return finalResult;
}

export function enrollSpeaker(audioBlobs, userId) {
  const form = new FormData();
  form.append('user_id', userId);
  audioBlobs.forEach((blob, i) => form.append('audio_files', blob, `enroll_${i}.webm`));
  return apiPost('/api/v1/voice/enroll', form, true);
}

export function verifySpeaker(audioBlob, userId) {
  const form = new FormData();
  form.append('audio', audioBlob, 'verify.webm');
  form.append('user_id', userId);
  return apiPost('/api/v1/voice/verify', form, true);
}

export const verifyPin = (userId, pin, transactionId) =>
  apiPost('/api/v1/payments/verify-pin', { user_id: userId, pin, transaction_id: transactionId });

export function createOrder(transactionId, userId) {
  return fetch(`${API_BASE}/api/v1/payments/create-order?transaction_id=${transactionId}&user_id=${userId}`, {
    method: 'POST',
    headers: authHeaders(),
  }).then(r => {
    if (!r.ok) return r.json().then(e => { throw new Error(e.detail); });
    return r.json();
  });
}

export const verifyPayment = (data) => apiPost('/api/v1/payments/verify-payment', data);

// --- Razorpay Checkout ---
export function openRazorpayCheckout(orderData, onSuccess, onFailure) {
  const options = {
    key: orderData.key_id,
    amount: orderData.amount_paise,
    currency: 'INR',
    name: 'VoicePay',
    description: `Payment to ${orderData.recipient || 'recipient'}`,
    order_id: orderData.order_id,
    prefill: {
      name: orderData.user_display_name || 'User',
    },
    theme: {
      color: '#6366f1',
      backdrop_color: 'rgba(10, 10, 18, 0.8)',
    },
    handler: function (response) {
      onSuccess({
        razorpay_order_id: response.razorpay_order_id,
        razorpay_payment_id: response.razorpay_payment_id,
        razorpay_signature: response.razorpay_signature,
      });
    },
    modal: {
      ondismiss: function () {
        onFailure('Payment cancelled by user');
      },
    },
  };

  const rzp = new window.Razorpay(options);
  rzp.on('payment.failed', function (response) {
    onFailure(response.error?.description || 'Payment failed');
  });
  rzp.open();
}
