import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../utils/AuthContext';
import api from '../utils/api';

const STATE_LABELS = {
  draft: { label: 'Draft', color: 'bg-gray-100 text-gray-700' },
  submitted: { label: 'Submitted', color: 'bg-blue-100 text-blue-700' },
  under_review: { label: 'Under Review', color: 'bg-yellow-100 text-yellow-700' },
  approved: { label: '✓ Approved', color: 'bg-green-100 text-green-700' },
  rejected: { label: '✗ Rejected', color: 'bg-red-100 text-red-700' },
  more_info_requested: { label: 'More Info Needed', color: 'bg-orange-100 text-orange-700' },
};

const DOC_TYPES = [
  { key: 'pan', label: 'PAN Card' },
  { key: 'aadhaar', label: 'Aadhaar' },
  { key: 'bank_statement', label: 'Bank Statement' },
];

export default function MerchantDashboard() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [submissions, setSubmissions] = useState([]);
  const [selected, setSelected] = useState(null);
  const [step, setStep] = useState(1);
  const [form, setForm] = useState({
    full_name: '', email: '', phone: '',
    business_name: '', business_type: 'agency', monthly_volume_usd: '',
  });
  const [docs, setDocs] = useState({});
  const [uploading, setUploading] = useState({});
  const [saving, setSaving] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [msg, setMsg] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    fetchSubmissions();
  }, []);

  const fetchSubmissions = async () => {
    const res = await api.get('/submissions/');
    setSubmissions(res.data);
  };

  const selectSubmission = (sub) => {
    setSelected(sub);
    setForm({
      full_name: sub.full_name || '',
      email: sub.email || '',
      phone: sub.phone || '',
      business_name: sub.business_name || '',
      business_type: sub.business_type || 'agency',
      monthly_volume_usd: sub.monthly_volume_usd || '',
    });
    setStep(1);
    setMsg(''); setError('');
  };

  const newSubmission = async () => {
    const res = await api.post('/submissions/', {});
    await fetchSubmissions();
    selectSubmission(res.data);
  };

  const saveStep = async () => {
    if (!selected) return;
    const editable = ['draft', 'more_info_requested'];
    if (!editable.includes(selected.state)) return;
    setSaving(true);
    try {
      const res = await api.patch(`/submissions/${selected.id}/`, form);
      setSelected(res.data);
      setMsg('Progress saved!');
      setTimeout(() => setMsg(''), 2000);
    } catch (e) {
      setError(e.response?.data?.message || 'Save failed.');
    } finally {
      setSaving(false);
    }
  };

  const uploadDoc = async (docType, file) => {
    if (!file || !selected) return;
    setUploading({ ...uploading, [docType]: true });
    setError('');
    try {
      const fd = new FormData();
      fd.append('file', file);
      await api.post(`/submissions/${selected.id}/documents/${docType}/`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setDocs({ ...docs, [docType]: file.name });
      setMsg(`${docType.toUpperCase()} uploaded!`);
      setTimeout(() => setMsg(''), 2000);
      // Refresh to get updated documents list
      const res = await api.get(`/submissions/${selected.id}/`);
      setSelected(res.data);
    } catch (e) {
      setError(e.response?.data?.message || `Upload failed for ${docType}.`);
    } finally {
      setUploading({ ...uploading, [docType]: false });
    }
  };

  const submitKYC = async () => {
    setSubmitting(true);
    setError('');
    try {
      await saveStep();
      const res = await api.post(`/submissions/${selected.id}/submit/`);
      setSelected(res.data);
      await fetchSubmissions();
      setMsg('KYC submitted for review!');
    } catch (e) {
      setError(e.response?.data?.message || 'Submission failed.');
    } finally {
      setSubmitting(false);
    }
  };

  const canEdit = selected && ['draft', 'more_info_requested'].includes(selected.state);
  const canSubmit = canEdit;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-blue-600 font-bold text-lg">Playto Pay</span>
          <span className="text-gray-400">|</span>
          <span className="text-sm text-gray-600">Merchant KYC Portal</span>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-sm text-gray-600">Hi, {user?.username}</span>
          <button onClick={logout} className="text-sm text-red-500 hover:underline">Logout</button>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-4 py-8 flex gap-6">
        {/* Sidebar: submissions list */}
        <div className="w-64 shrink-0">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-gray-800 text-sm">My Applications</h2>
            <button
              onClick={newSubmission}
              className="text-xs bg-blue-600 text-white px-3 py-1 rounded-full hover:bg-blue-700"
            >+ New</button>
          </div>
          <div className="space-y-2">
            {submissions.map((s) => {
              const st = STATE_LABELS[s.state] || {};
              return (
                <div
                  key={s.id}
                  onClick={() => selectSubmission(s)}
                  className={`cursor-pointer rounded-xl border p-3 transition ${
                    selected?.id === s.id
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 bg-white hover:bg-gray-50'
                  }`}
                >
                  <div className="text-sm font-medium text-gray-800 truncate">
                    {s.business_name || `KYC #${s.id}`}
                  </div>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium mt-1 inline-block ${st.color}`}>
                    {st.label}
                  </span>
                  {s.is_sla_at_risk && (
                    <span className="ml-2 text-xs text-red-600 font-semibold">⚠ SLA Risk</span>
                  )}
                </div>
              );
            })}
            {submissions.length === 0 && (
              <div className="text-sm text-gray-400 text-center py-8">
                No applications yet.<br />Click "+ New" to start.
              </div>
            )}
          </div>
        </div>

        {/* Main content */}
        {selected ? (
          <div className="flex-1 bg-white rounded-2xl border border-gray-200 p-6">
            {/* Status bar */}
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">
                  {selected.business_name || `KYC Application #${selected.id}`}
                </h2>
                <span className={`text-xs px-2 py-1 rounded-full font-medium ${STATE_LABELS[selected.state]?.color}`}>
                  {STATE_LABELS[selected.state]?.label}
                </span>
              </div>
              {selected.reviewer_note && (
                <div className="bg-orange-50 border border-orange-200 rounded-lg px-4 py-2 text-sm text-orange-700 max-w-xs">
                  <strong>Reviewer note:</strong> {selected.reviewer_note}
                </div>
              )}
            </div>

            {/* Step tabs */}
            <div className="flex gap-1 mb-6 bg-gray-100 p-1 rounded-lg">
              {['Personal Details', 'Business Details', 'Documents'].map((label, i) => (
                <button
                  key={i}
                  onClick={() => setStep(i + 1)}
                  className={`flex-1 text-sm py-2 rounded-md font-medium transition ${
                    step === i + 1
                      ? 'bg-white shadow text-blue-600'
                      : 'text-gray-500 hover:text-gray-700'
                  }`}
                >
                  {i + 1}. {label}
                </button>
              ))}
            </div>

            {/* Messages */}
            {msg && <div className="mb-4 bg-green-50 border border-green-200 text-green-700 rounded-lg px-4 py-2 text-sm">{msg}</div>}
            {error && <div className="mb-4 bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-2 text-sm">{error}</div>}

            {/* Step 1: Personal */}
            {step === 1 && (
              <div className="space-y-4">
                {[
                  { label: 'Full Name', name: 'full_name', type: 'text' },
                  { label: 'Email', name: 'email', type: 'email' },
                  { label: 'Phone', name: 'phone', type: 'text' },
                ].map(({ label, name, type }) => (
                  <div key={name}>
                    <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
                    <input
                      type={type}
                      value={form[name]}
                      onChange={(e) => setForm({ ...form, [name]: e.target.value })}
                      disabled={!canEdit}
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-500"
                    />
                  </div>
                ))}
              </div>
            )}

            {/* Step 2: Business */}
            {step === 2 && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Business Name</label>
                  <input
                    value={form.business_name}
                    onChange={(e) => setForm({ ...form, business_name: e.target.value })}
                    disabled={!canEdit}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Business Type</label>
                  <select
                    value={form.business_type}
                    onChange={(e) => setForm({ ...form, business_type: e.target.value })}
                    disabled={!canEdit}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50"
                  >
                    {['agency', 'freelancer', 'ecommerce', 'saas', 'other'].map((t) => (
                      <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Expected Monthly Volume (USD)</label>
                  <input
                    type="number"
                    value={form.monthly_volume_usd}
                    onChange={(e) => setForm({ ...form, monthly_volume_usd: e.target.value })}
                    disabled={!canEdit}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50"
                  />
                </div>
              </div>
            )}

            {/* Step 3: Documents */}
            {step === 3 && (
              <div className="space-y-4">
                {DOC_TYPES.map(({ key, label }) => {
                  const existing = selected.documents?.find((d) => d.doc_type === key);
                  return (
                    <div key={key} className="border border-gray-200 rounded-xl p-4">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-gray-700">{label}</span>
                        {existing && (
                          <span className="text-xs text-green-600 font-medium">✓ Uploaded: {existing.original_filename}</span>
                        )}
                      </div>
                      {canEdit && (
                        <label className="block">
                          <span className="sr-only">Upload {label}</span>
                          <input
                            type="file"
                            accept=".pdf,.jpg,.jpeg,.png"
                            disabled={uploading[key]}
                            onChange={(e) => uploadDoc(key, e.target.files[0])}
                            className="block w-full text-sm text-gray-500 file:mr-3 file:py-1.5 file:px-4 file:rounded-full file:border-0 file:text-xs file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                          />
                          <p className="text-xs text-gray-400 mt-1">PDF, JPG or PNG — max 5 MB</p>
                          {uploading[key] && <p className="text-xs text-blue-500 mt-1">Uploading…</p>}
                        </label>
                      )}
                      {!canEdit && !existing && (
                        <p className="text-xs text-gray-400">No document uploaded.</p>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {/* Action buttons */}
            {canEdit && (
              <div className="flex gap-3 mt-6 pt-4 border-t border-gray-100">
                <button
                  onClick={saveStep} disabled={saving}
                  className="flex-1 border border-gray-300 text-gray-700 py-2.5 rounded-lg text-sm font-medium hover:bg-gray-50 disabled:opacity-50"
                >
                  {saving ? 'Saving…' : 'Save Progress'}
                </button>
                <button
                  onClick={submitKYC} disabled={submitting}
                  className="flex-1 bg-blue-600 text-white py-2.5 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
                >
                  {submitting ? 'Submitting…' : 'Submit for Review →'}
                </button>
              </div>
            )}
          </div>
        ) : (
          <div className="flex-1 bg-white rounded-2xl border border-gray-200 flex items-center justify-center">
            <div className="text-center text-gray-400">
              <div className="text-4xl mb-3">📋</div>
              <p className="text-sm">Select an application or create a new one</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
