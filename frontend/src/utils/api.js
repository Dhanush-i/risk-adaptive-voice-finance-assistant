const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

export async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'API error');
  }
  return res.json();
}

export async function apiPost(path, body, isForm = false) {
  const options = { method: 'POST' };
  if (isForm) {
    options.body = body; // FormData
  } else {
    options.headers = { 'Content-Type': 'application/json' };
    options.body = JSON.stringify(body);
  }
  const res = await fetch(`${API_BASE}${path}`, options);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'API error');
  }
  return res.json();
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
  form.append('audio', audioBlob, 'recording.wav');
  form.append('user_id', userId);
  return apiPost('/api/v1/voice/process', form, true);
}

export function enrollSpeaker(audioBlobs, userId) {
  const form = new FormData();
  form.append('user_id', userId);
  audioBlobs.forEach((blob, i) => form.append('audio_files', blob, `enroll_${i}.wav`));
  return apiPost('/api/v1/voice/enroll', form, true);
}

export function verifySpeaker(audioBlob, userId) {
  const form = new FormData();
  form.append('audio', audioBlob, 'verify.wav');
  form.append('user_id', userId);
  return apiPost('/api/v1/voice/verify', form, true);
}

export const verifyPin = (userId, pin, transactionId) =>
  apiPost('/api/v1/payments/verify-pin', { user_id: userId, pin, transaction_id: transactionId });

export function createOrder(transactionId, userId) {
  const form = new URLSearchParams();
  form.append('transaction_id', transactionId);
  form.append('user_id', userId);
  return fetch(`${API_BASE}/api/v1/payments/create-order?transaction_id=${transactionId}&user_id=${userId}`, {
    method: 'POST',
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
