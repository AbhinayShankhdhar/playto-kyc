import { useState, useEffect } from 'react';
import { api } from './api';

// ── Helpers ──────────────────────────────────────────────────────────────────

const STATE_COLORS = {
  draft: 'bg-gray-100 text-gray-700',
  submitted: 'bg-blue-100 text-blue-700',
  under_review: 'bg-yellow-100 text-yellow-700',
  approved: 'bg-green-100 text-green-700',
  rejected: 'bg-red-100 text-red-700',
  more_info_requested: 'bg-orange-100 text-orange-700',
};

const STATE_LABELS = {
  draft: 'Draft',
  submitted: 'Submitted',
  under_review: 'Under Review',
  approved: 'Approved',
  rejected: 'Rejected',
  more_info_requested: 'More Info Requested',
};

function Badge({ state }) {
  return (
    <span className={`px-2 py-1 rounded-full text-xs font-semibold ${STATE_COLORS[state] || 'bg-gray-100 text-gray-600'}`}>
      {STATE_LABELS[state] || state}
    </span>
  );
}

function Spinner() {
  return <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />;
}

function Alert({ type, message, onClose }) {
  const colors = type === 'error'
    ? 'bg-red-50 border-red-200 text-red-700'
    : 'bg-green-50 border-green-200 text-green-700';
  return (
    <div className={`border rounded-lg p-3 flex items-start gap-2 text-sm ${colors}`}>
      <span className="flex-1">{message}</span>
      {onClose && <button onClick={onClose} className="ml-2 opacity-60 hover:opacity-100">✕</button>}
    </div>
  );
}

// ── Auth Screen ───────────────────────────────────────────────────────────────

function AuthScreen({ onLogin }) {
  const [mode, setMode] = useState('login');
  const [form, setForm] = useState({ username: '', password: '', role: 'merchant' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      let data;
      if (mode === 'login') {
        data = await api.login(form.username, form.password);
      } else {
        data = await api.register(form);
      }
      localStorage.setItem('token', data.token);
      onLogin(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-600 to-indigo-700 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-8">
        <div className="text-center mb-8">
          <div className="w-14 h-14 bg-blue-600 rounded-2xl flex items-center justify-center mx-auto mb-3">
            <span className="text-white text-2xl font-bold">P</span>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Playto Pay</h1>
          <p className="text-gray-500 text-sm mt-1">KYC Onboarding Portal</p>
        </div>

        <div className="flex bg-gray-100 rounded-xl p-1 mb-6">
          {['login', 'register'].map(m => (
            <button key={m} onClick={() => setMode(m)}
              className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${mode === m ? 'bg-white text-blue-600 shadow' : 'text-gray-500 hover:text-gray-700'}`}>
              {m === 'login' ? 'Login' : 'Register'}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Username</label>
            <input className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={form.username} onChange={e => set('username', e.target.value)} required placeholder="Enter username" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <input type="password" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={form.password} onChange={e => set('password', e.target.value)} required placeholder="Enter password" />
          </div>
          {mode === 'register' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Register as</label>
              <select className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={form.role} onChange={e => set('role', e.target.value)}>
                <option value="merchant">Merchant</option>
                <option value="reviewer">Reviewer</option>
              </select>
            </div>
          )}

          {error && <Alert type="error" message={error} onClose={() => setError('')} />}

          <button type="submit" disabled={loading}
            className="w-full bg-blue-600 text-white py-2.5 rounded-lg font-medium hover:bg-blue-700 transition-colors disabled:opacity-60 flex items-center justify-center gap-2">
            {loading && <Spinner />}
            {mode === 'login' ? 'Sign In' : 'Create Account'}
          </button>
        </form>

        <div className="mt-6 p-4 bg-gray-50 rounded-xl text-xs text-gray-500">
          <p className="font-semibold mb-2 text-gray-700">🔑 Demo Credentials</p>
          <div className="space-y-1">
            <p><strong>Reviewer:</strong> reviewer1 / reviewer123</p>
            <p><strong>Merchant (draft):</strong> merchant_arjun / merchant123</p>
            <p><strong>Merchant (under review):</strong> merchant_priya / merchant123</p>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Merchant KYC Form ─────────────────────────────────────────────────────────

function KYCForm({ submission, onSave, onSubmit }) {
  const [step, setStep] = useState(1);
  const [form, setForm] = useState({
    full_name: submission?.full_name || '',
    email: submission?.email || '',
    phone: submission?.phone || '',
    business_name: submission?.business_name || '',
    business_type: submission?.business_type || '',
    expected_monthly_volume: submission?.expected_monthly_volume || '',
  });
  const [files, setFiles] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));
  const isReadOnly = !['draft', 'more_info_requested'].includes(submission?.state);

  async function saveStep() {
    setLoading(true);
    setError('');
    try {
      const fd = new FormData();
      Object.entries(form).forEach(([k, v]) => v && fd.append(k, v));
      Object.entries(files).forEach(([k, v]) => v && fd.append(k, v));
      await onSave(submission.id, fd);
      setSuccess('Progress saved!');
      setTimeout(() => setSuccess(''), 2000);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit() {
    setLoading(true);
    setError('');
    try {
      const fd = new FormData();
      Object.entries(form).forEach(([k, v]) => v && fd.append(k, v));
      Object.entries(files).forEach(([k, v]) => v && fd.append(k, v));
      await onSave(submission.id, fd);
      await onSubmit(submission.id);
      setSuccess('KYC submitted successfully!');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function FileInput({ name, label, existing }) {
    return (
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
        {existing && !files[name] && (
          <p className="text-xs text-green-600 mb-1">✓ Already uploaded</p>
        )}
        <input type="file" accept=".pdf,.jpg,.jpeg,.png" disabled={isReadOnly}
          onChange={e => setFiles(f => ({ ...f, [name]: e.target.files[0] }))}
          className="w-full text-sm text-gray-500 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:bg-blue-50 file:text-blue-600 file:text-sm file:font-medium hover:file:bg-blue-100 disabled:opacity-50" />
        <p className="text-xs text-gray-400 mt-1">PDF, JPG, PNG — max 5 MB</p>
      </div>
    );
  }

  const steps = ['Personal', 'Business', 'Documents'];

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100">
      {/* Step indicator */}
      <div className="p-6 border-b border-gray-100">
        <div className="flex items-center gap-2">
          {steps.map((s, i) => (
            <div key={i} className="flex items-center gap-2">
              <button onClick={() => setStep(i + 1)}
                className={`w-7 h-7 rounded-full text-xs font-bold flex items-center justify-center transition-colors ${step === i + 1 ? 'bg-blue-600 text-white' : step > i + 1 ? 'bg-green-500 text-white' : 'bg-gray-100 text-gray-400'}`}>
                {step > i + 1 ? '✓' : i + 1}
              </button>
              <span className={`text-sm ${step === i + 1 ? 'text-gray-900 font-medium' : 'text-gray-400'}`}>{s}</span>
              {i < steps.length - 1 && <div className={`flex-1 h-px w-8 ${step > i + 1 ? 'bg-green-400' : 'bg-gray-200'}`} />}
            </div>
          ))}
        </div>
        {isReadOnly && (
          <div className="mt-3 text-xs text-amber-600 bg-amber-50 rounded-lg px-3 py-2">
            ℹ️ Submission is in <strong>{STATE_LABELS[submission?.state]}</strong> state — editing is disabled.
          </div>
        )}
      </div>

      <div className="p-6 space-y-5">
        {step === 1 && (
          <>
            <h3 className="font-semibold text-gray-900">Personal Details</h3>
            {[['full_name', 'Full Name', 'text', 'Arjun Sharma'], ['email', 'Email', 'email', 'you@example.com'], ['phone', 'Phone', 'tel', '+91 98765 43210']].map(([k, l, t, p]) => (
              <div key={k}>
                <label className="block text-sm font-medium text-gray-700 mb-1">{l}</label>
                <input type={t} placeholder={p} disabled={isReadOnly} value={form[k]} onChange={e => set(k, e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-500" />
              </div>
            ))}
          </>
        )}

        {step === 2 && (
          <>
            <h3 className="font-semibold text-gray-900">Business Details</h3>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Business Name</label>
              <input placeholder="Acme Digital Studio" disabled={isReadOnly} value={form.business_name} onChange={e => set('business_name', e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Business Type</label>
              <select disabled={isReadOnly} value={form.business_type} onChange={e => set('business_type', e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50">
                <option value="">Select type</option>
                {[['freelancer', 'Freelancer'], ['agency', 'Agency'], ['ecommerce', 'E-commerce'], ['saas', 'SaaS'], ['other', 'Other']].map(([v, l]) => (
                  <option key={v} value={v}>{l}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Expected Monthly Volume (USD)</label>
              <input type="number" placeholder="5000" disabled={isReadOnly} value={form.expected_monthly_volume} onChange={e => set('expected_monthly_volume', e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50" />
            </div>
          </>
        )}

        {step === 3 && (
          <>
            <h3 className="font-semibold text-gray-900">Document Upload</h3>
            <FileInput name="pan_document" label="PAN Card" existing={submission?.pan_document} />
            <FileInput name="aadhaar_document" label="Aadhaar Card" existing={submission?.aadhaar_document} />
            <FileInput name="bank_statement" label="Bank Statement (last 3 months)" existing={submission?.bank_statement} />
          </>
        )}

        {error && <Alert type="error" message={error} onClose={() => setError('')} />}
        {success && <Alert type="success" message={success} />}

        <div className="flex gap-3 pt-2">
          {step > 1 && <button onClick={() => setStep(s => s - 1)} className="px-4 py-2 border border-gray-200 rounded-lg text-sm text-gray-600 hover:bg-gray-50">← Back</button>}
          {!isReadOnly && (
            <button onClick={saveStep} disabled={loading}
              className="px-4 py-2 border border-blue-200 text-blue-600 rounded-lg text-sm hover:bg-blue-50 flex items-center gap-2">
              {loading && <Spinner />} Save Progress
            </button>
          )}
          {step < 3 && <button onClick={() => setStep(s => s + 1)} className="ml-auto px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">Next →</button>}
          {step === 3 && !isReadOnly && (
            <button onClick={handleSubmit} disabled={loading}
              className="ml-auto px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 flex items-center gap-2">
              {loading && <Spinner />} Submit KYC ✓
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Merchant Dashboard ────────────────────────────────────────────────────────

function MerchantDashboard({ user }) {
  const [submissions, setSubmissions] = useState([]);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { loadSubmissions(); }, []);

  async function loadSubmissions() {
    setLoading(true);
    try {
      const data = await api.getMySubmissions();
      setSubmissions(data);
      if (data.length > 0 && !selected) setSelected(data[0]);
    } catch (e) {}
    setLoading(false);
  }

  async function createNew() {
    try {
      const sub = await api.createSubmission();
      setSubmissions(s => [...s, sub]);
      setSelected(sub);
    } catch (e) {}
  }

  async function handleSave(id, fd) {
    const updated = await api.updateSubmission(id, fd);
    setSubmissions(s => s.map(x => x.id === id ? updated : x));
    setSelected(updated);
    return updated;
  }

  async function handleSubmit(id) {
    const updated = await api.submitKYC(id);
    setSubmissions(s => s.map(x => x.id === id ? updated : x));
    setSelected(updated);
  }

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-900">My KYC Application</h2>
          <p className="text-sm text-gray-500 mt-0.5">Complete your verification to start collecting payments</p>
        </div>
        <button onClick={createNew} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">+ New Application</button>
      </div>

      {submissions.length > 1 && (
        <div className="flex gap-2 flex-wrap">
          {submissions.map(s => (
            <button key={s.id} onClick={() => setSelected(s)}
              className={`px-3 py-1.5 rounded-lg text-sm flex items-center gap-2 border ${selected?.id === s.id ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-gray-300'}`}>
              KYC #{s.id} <Badge state={s.state} />
            </button>
          ))}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-16"><Spinner /></div>
      ) : submissions.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-2xl border border-gray-100">
          <div className="text-4xl mb-3">📋</div>
          <p className="text-gray-600 font-medium">No KYC application yet</p>
          <p className="text-gray-400 text-sm mt-1 mb-4">Start your verification to collect international payments</p>
          <button onClick={createNew} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">Start KYC Application</button>
        </div>
      ) : selected ? (
        <>
          <div className="bg-white rounded-2xl border border-gray-100 p-4 flex items-center gap-4">
            <div className="flex-1">
              <p className="text-sm text-gray-500">Application #{selected.id}</p>
              <p className="font-medium text-gray-900 mt-0.5">Status: <Badge state={selected.state} /></p>
            </div>
            {selected.state === 'more_info_requested' && selected.reviewer_notes && (
              <div className="bg-orange-50 border border-orange-200 rounded-lg px-3 py-2 text-sm text-orange-700 max-w-xs">
                <p className="font-semibold">Reviewer notes:</p>
                <p>{selected.reviewer_notes}</p>
              </div>
            )}
          </div>
          <KYCForm submission={selected} onSave={handleSave} onSubmit={handleSubmit} />
        </>
      ) : null}
    </div>
  );
}

// ── Reviewer Dashboard ────────────────────────────────────────────────────────

function ReviewerDashboard({ user }) {
  const [queue, setQueue] = useState([]);
  const [selected, setSelected] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [view, setView] = useState('queue'); // queue | all

  useEffect(() => { loadAll(); }, []);

  async function loadAll() {
    setLoading(true);
    try {
      const [q, m] = await Promise.all([api.getQueue(), api.getMetrics()]);
      setQueue(q);
      setMetrics(m);
    } catch (e) {}
    setLoading(false);
  }

  async function doTransition(new_state) {
    setActionLoading(true);
    setError('');
    try {
      const updated = await api.transitionSubmission(selected.id, new_state, reason);
      setQueue(q => q.filter(x => x.id !== updated.id).concat(
        ['submitted', 'under_review', 'more_info_requested'].includes(updated.state) ? [updated] : []
      ));
      setSelected(updated);
      setSuccess(`Moved to ${STATE_LABELS[new_state]}`);
      setReason('');
      loadAll();
    } catch (err) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  }

  const ALLOWED_FROM = {
    submitted: ['under_review'],
    under_review: ['approved', 'rejected', 'more_info_requested'],
    more_info_requested: ['submitted'],
  };

  const ACTION_LABELS = {
    under_review: { label: 'Take Under Review', color: 'bg-yellow-500 hover:bg-yellow-600' },
    approved: { label: '✓ Approve', color: 'bg-green-600 hover:bg-green-700' },
    rejected: { label: '✗ Reject', color: 'bg-red-600 hover:bg-red-700' },
    more_info_requested: { label: '↩ Request More Info', color: 'bg-orange-500 hover:bg-orange-600' },
    submitted: { label: '↩ Return to Queue', color: 'bg-blue-500 hover:bg-blue-600' },
  };

  return (
    <div className="max-w-6xl mx-auto p-6">
      {/* Metrics */}
      {metrics && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          {[
            { label: 'In Queue', value: metrics.in_queue, icon: '📋', color: 'text-blue-600' },
            { label: 'Avg Hours in Queue', value: metrics.avg_hours_in_queue ?? 'N/A', icon: '⏱', color: 'text-yellow-600' },
            { label: 'Approval Rate (7d)', value: `${metrics.approval_rate_7d}%`, icon: '✅', color: 'text-green-600' },
            { label: 'At Risk (>24h)', value: metrics.at_risk_count, icon: '⚠️', color: 'text-red-600' },
          ].map(m => (
            <div key={m.label} className="bg-white rounded-xl border border-gray-100 p-4">
              <p className="text-xs text-gray-500 mb-1">{m.label}</p>
              <p className={`text-2xl font-bold ${m.color}`}>{m.value}</p>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-5 gap-6">
        {/* Queue list */}
        <div className="md:col-span-2 bg-white rounded-2xl border border-gray-100">
          <div className="p-4 border-b border-gray-100">
            <h3 className="font-semibold text-gray-900">Review Queue</h3>
            <p className="text-xs text-gray-400 mt-0.5">Oldest first</p>
          </div>
          {loading ? (
            <div className="flex justify-center py-8"><Spinner /></div>
          ) : queue.length === 0 ? (
            <div className="text-center py-8 text-gray-400 text-sm">Queue is empty 🎉</div>
          ) : (
            <div className="divide-y divide-gray-50">
              {queue.map(s => (
                <button key={s.id} onClick={() => { setSelected(s); setError(''); setSuccess(''); }}
                  className={`w-full p-4 text-left hover:bg-gray-50 transition-colors ${selected?.id === s.id ? 'bg-blue-50' : ''}`}>
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="font-medium text-sm text-gray-900">#{s.id} — {s.merchant_username}</p>
                      <p className="text-xs text-gray-500 mt-0.5">{s.business_name || 'No business name'}</p>
                    </div>
                    <div className="flex flex-col items-end gap-1">
                      <Badge state={s.state} />
                      {s.is_at_risk && <span className="text-xs text-red-600 font-medium">⚠ AT RISK</span>}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Detail panel */}
        <div className="md:col-span-3">
          {!selected ? (
            <div className="bg-white rounded-2xl border border-gray-100 flex items-center justify-center h-64">
              <p className="text-gray-400 text-sm">Select a submission to review</p>
            </div>
          ) : (
            <div className="bg-white rounded-2xl border border-gray-100">
              <div className="p-5 border-b border-gray-100">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-semibold text-gray-900">KYC #{selected.id}</h3>
                    <p className="text-xs text-gray-400 mt-0.5">Submitted by {selected.merchant_username}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    {selected.is_at_risk && <span className="text-xs text-red-600 bg-red-50 px-2 py-1 rounded-full font-medium">⚠ SLA At Risk</span>}
                    <Badge state={selected.state} />
                  </div>
                </div>
              </div>

              <div className="p-5 space-y-4">
                {/* Personal */}
                <div>
                  <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Personal</p>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    {[['Name', selected.full_name], ['Email', selected.email], ['Phone', selected.phone]].map(([l, v]) => (
                      <div key={l}><span className="text-gray-500">{l}:</span> <span className="text-gray-900">{v || '—'}</span></div>
                    ))}
                  </div>
                </div>

                {/* Business */}
                <div>
                  <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Business</p>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    {[['Business', selected.business_name], ['Type', selected.business_type], ['Volume', selected.expected_monthly_volume ? `$${selected.expected_monthly_volume}/mo` : '—']].map(([l, v]) => (
                      <div key={l}><span className="text-gray-500">{l}:</span> <span className="text-gray-900">{v || '—'}</span></div>
                    ))}
                  </div>
                </div>

                {/* Documents */}
                <div>
                  <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Documents</p>
                  <div className="flex gap-2 flex-wrap text-sm">
                    {[['PAN', selected.pan_document], ['Aadhaar', selected.aadhaar_document], ['Bank Statement', selected.bank_statement]].map(([l, v]) => (
                      <span key={l} className={`px-2 py-1 rounded-lg text-xs ${v ? 'bg-green-50 text-green-700' : 'bg-gray-50 text-gray-400'}`}>
                        {v ? '✓' : '✗'} {l}
                      </span>
                    ))}
                  </div>
                </div>

                {selected.reviewer_notes && (
                  <div className="bg-gray-50 rounded-lg p-3 text-sm">
                    <p className="text-xs font-semibold text-gray-400 mb-1">Reviewer Notes</p>
                    <p className="text-gray-700">{selected.reviewer_notes}</p>
                  </div>
                )}

                {/* Actions */}
                {ALLOWED_FROM[selected.state] && (
                  <div className="border-t border-gray-100 pt-4">
                    <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Actions</p>
                    <textarea value={reason} onChange={e => setReason(e.target.value)} placeholder="Reason / notes (optional)"
                      className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 mb-3 resize-none" rows={2} />

                    {error && <Alert type="error" message={error} onClose={() => setError('')} />}
                    {success && <Alert type="success" message={success} />}

                    <div className="flex gap-2 flex-wrap">
                      {ALLOWED_FROM[selected.state]?.map(ns => (
                        <button key={ns} onClick={() => doTransition(ns)} disabled={actionLoading}
                          className={`px-4 py-2 text-white text-sm rounded-lg font-medium transition-colors disabled:opacity-60 flex items-center gap-2 ${ACTION_LABELS[ns]?.color}`}>
                          {actionLoading && <Spinner />} {ACTION_LABELS[ns]?.label}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Root App ──────────────────────────────────────────────────────────────────

export default function App() {
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      api.me().then(setUser).catch(() => localStorage.removeItem('token')).finally(() => setChecking(false));
    } else {
      setChecking(false);
    }
  }, []);

  function handleLogin(data) {
    setUser(data);
  }

  function handleLogout() {
    localStorage.removeItem('token');
    setUser(null);
  }

  if (checking) {
    return <div className="min-h-screen flex items-center justify-center"><Spinner /></div>;
  }

  if (!user) return <AuthScreen onLogin={handleLogin} />;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navbar */}
      <nav className="bg-white border-b border-gray-100 px-6 py-3.5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
            <span className="text-white text-sm font-bold">P</span>
          </div>
          <div>
            <span className="font-bold text-gray-900 text-sm">Playto Pay</span>
            <span className="text-gray-400 text-xs ml-2">KYC Portal</span>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right">
            <p className="text-sm font-medium text-gray-900">{user.username}</p>
            <p className="text-xs text-gray-400 capitalize">{user.role}</p>
          </div>
          <button onClick={handleLogout} className="text-xs text-gray-400 hover:text-gray-600 border border-gray-200 px-3 py-1.5 rounded-lg hover:bg-gray-50 transition-colors">
            Logout
          </button>
        </div>
      </nav>

      {/* Main */}
      <main className="py-6">
        {user.role === 'merchant' ? (
          <MerchantDashboard user={user} />
        ) : (
          <ReviewerDashboard user={user} />
        )}
      </main>
    </div>
  );
}
