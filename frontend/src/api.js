// In production (deployed on Railway), frontend & backend are same origin
// VITE_API_URL env var overrides for separate deployments
const BASE = (import.meta.env.VITE_API_URL || '') + '/api/v1';

function getToken() {
  return localStorage.getItem('playto_token');
}

async function request(method, path, body = null, isFormData = false) {
  const headers = {};
  const token = getToken();
  if (token) headers['Authorization'] = `Token ${token}`;
  if (!isFormData) headers['Content-Type'] = 'application/json';

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body ? (isFormData ? body : JSON.stringify(body)) : null,
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = data.error || data.detail || JSON.stringify(data);
    throw new Error(msg);
  }
  return data;
}

export const api = {
  login: (username, password) => request('POST', '/auth/login/', { username, password }),
  register: (data) => request('POST', '/auth/register/', data),
  me: () => request('GET', '/auth/me/'),

  // Merchant
  getMySubmissions: () => request('GET', '/merchant/submissions/'),
  createSubmission: () => request('POST', '/merchant/submissions/', {}),
  getSubmission: (id) => request('GET', `/merchant/submissions/${id}/`),
  updateSubmission: (id, data) => request('PATCH', `/merchant/submissions/${id}/`, data, data instanceof FormData),
  submitKYC: (id) => request('POST', `/merchant/submissions/${id}/submit/`),

  // Reviewer
  getQueue: () => request('GET', '/reviewer/queue/'),
  getAllSubmissions: () => request('GET', '/reviewer/submissions/'),
  getReviewerSubmission: (id) => request('GET', `/reviewer/submissions/${id}/`),
  transitionSubmission: (id, new_state, reason = '') =>
    request('POST', `/reviewer/submissions/${id}/transition/`, { new_state, reason }),
  getMetrics: () => request('GET', '/reviewer/metrics/'),
  updateNotes: (id, reviewer_notes) =>
    request('PATCH', `/reviewer/submissions/${id}/`, { reviewer_notes }),
};
