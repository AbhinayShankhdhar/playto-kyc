import React, { useState, useEffect } from 'react';
import { useAuth } from '../utils/AuthContext';
import api from '../utils/api';

const STATE_LABELS = {
  draft: { label: 'Draft', color: 'bg-gray-100 text-gray-600' },
  submitted: { label: 'Submitted', color: 'bg-blue-100 text-blue-700' },
  under_review: { label: 'Under Review', color: 'bg-yellow-100 text-yellow-700' },
  approved: { label: '✓ Approved', color: 'bg-green-100 text-green-700' },
  rejected: { label: '✗ Rejected', color: 'bg-red-100 text-red-700' },
  more_info_requested: { label: 'More Info', color: 'bg-orange-100 text-orange-700' },
};

const REVIEWER_ACTIONS = {
  submitted: [{ label: 'Start Review', state: 'under_review', style: 'bg-yellow-500 hover:bg-yellow-600 text-white' }],
  under_review: [
    { label: '✓ Approve', state: 'approved', style: 'bg-green-600 hover:bg-green-700 text-white' },
    { label: '✗ Reject', state: 'rejected', style: 'bg-red-600 hover:bg-red-700 text-white' },
    { label: '? Request More Info', state: 'more_info_requested', style: 'bg-orange-500 hover:bg-orange-600 text-white' },
  ],
  more_info_requested: [{ label: 'Start Review Again', state: 'under_review', style: 'bg-yellow-500 hover:bg-yellow-600 text-white' }],
};

export default function ReviewerDashboard() {
  const { user, logout } = useAuth();
  const [queue, setQueue] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [selected, setSelected] = useState(null);
  const [note, setNote] = useState('');
  const [transitioning, setTransitioning] = useState(false);
  const [msg, setMsg] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    fetchAll();
  }, []);

  const fetchAll = async () => {
    const [qRes, mRes] = await Promise.all([
      api.get('/reviewer/queue/'),
      api.get('/reviewer/metrics/'),
    ]);
    setQueue(qRes.data);
    setMetrics(mRes.data);
  };

  const selectSubmission = async (sub) => {
    const res = await api.get(`/reviewer/submissions/${sub.id}/`);
    setSelected(res.data);
    setNote('');
    setMsg(''); setError('');
  };

  const doTransition = async (newState) => {
    setTransitioning(true);
    setError('');
    try {
      const res = await api.post(`/reviewer/submissions/${selected.id}/transition/`, {
        new_state: newState,
        reviewer_note: note,
      });
      setSelected(res.data);
      setMsg(`Status updated to: ${newState}`);
      await fetchAll();
    } catch (e) {
      setError(e.response?.data?.message || 'Transition failed.');
    } finally {
      setTransitioning(false);
    }
  };

  const MetricCard = ({ label, value, sub, accent }) => (
    <div className={`bg-white rounded-xl border ${accent ? 'border-red-300' : 'border-gray-200'} p-4`}>
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className={`text-2xl font-bold ${accent ? 'text-red-600' : 'text-gray-900'}`}>{value ?? '—'}</div>
      {sub && <div className="text-xs text-gray-400 mt-0.5">{sub}</div>}
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-blue-600 font-bold text-lg">Playto Pay</span>
          <span className="text-gray-400">|</span>
          <span className="text-sm text-gray-600">Reviewer Dashboard</span>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-sm text-gray-600">Hi, {user?.username}</span>
          <button onClick={logout} className="text-sm text-red-500 hover:underline">Logout</button>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-4 py-8">
        {/* Metrics */}
        {metrics && (
          <div className="grid grid-cols-4 gap-4 mb-8">
            <MetricCard label="In Queue" value={metrics.submissions_in_queue} />
            <MetricCard
              label="Avg. Time in Queue"
              value={metrics.average_time_in_queue_hours != null ? `${metrics.average_time_in_queue_hours}h` : null}
            />
            <MetricCard
              label="Approval Rate (7d)"
              value={metrics.approval_rate_last_7_days_pct != null ? `${metrics.approval_rate_last_7_days_pct}%` : 'N/A'}
            />
            <MetricCard
              label="⚠ SLA At Risk"
              value={metrics.at_risk_count}
              sub=">24h in queue"
              accent={metrics.at_risk_count > 0}
            />
          </div>
        )}

        <div className="flex gap-6">
          {/* Queue */}
          <div className="w-72 shrink-0">
            <h2 className="font-semibold text-gray-800 text-sm mb-3">Review Queue (oldest first)</h2>
            <div className="space-y-2">
              {queue.map((s) => {
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
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="text-sm font-medium text-gray-800">
                          {s.business_name || s.merchant_username}
                        </div>
                        <div className="text-xs text-gray-400 mt-0.5">@{s.merchant_username}</div>
                      </div>
                      {s.is_sla_at_risk && (
                        <span className="text-xs bg-red-100 text-red-600 px-1.5 py-0.5 rounded font-semibold shrink-0">SLA ⚠</span>
                      )}
                    </div>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium mt-2 inline-block ${st.color}`}>
                      {st.label}
                    </span>
                    {s.submitted_at && (
                      <div className="text-xs text-gray-400 mt-1">
                        Submitted: {new Date(s.submitted_at).toLocaleDateString()}
                      </div>
                    )}
                  </div>
                );
              })}
              {queue.length === 0 && (
                <div className="text-sm text-gray-400 text-center py-8">Queue is empty 🎉</div>
              )}
            </div>
          </div>

          {/* Detail panel */}
          {selected ? (
            <div className="flex-1 bg-white rounded-2xl border border-gray-200 p-6">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">
                    {selected.business_name || `KYC #${selected.id}`}
                  </h2>
                  <span className={`text-xs px-2 py-1 rounded-full font-medium ${STATE_LABELS[selected.state]?.color}`}>
                    {STATE_LABELS[selected.state]?.label}
                  </span>
                  {selected.is_sla_at_risk && (
                    <span className="ml-2 text-xs bg-red-100 text-red-600 px-2 py-1 rounded-full font-semibold">
                      ⚠ SLA At Risk
                    </span>
                  )}
                </div>
              </div>

              {msg && <div className="mb-4 bg-green-50 border border-green-200 text-green-700 rounded-lg px-4 py-2 text-sm">{msg}</div>}
              {error && <div className="mb-4 bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-2 text-sm">{error}</div>}

              <div className="grid grid-cols-2 gap-6 mb-6">
                <div>
                  <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Personal</h3>
                  <dl className="space-y-2">
                    {[
                      ['Name', selected.full_name],
                      ['Email', selected.email],
                      ['Phone', selected.phone],
                    ].map(([k, v]) => (
                      <div key={k} className="flex gap-2 text-sm">
                        <dt className="text-gray-500 w-16 shrink-0">{k}</dt>
                        <dd className="text-gray-900">{v || '—'}</dd>
                      </div>
                    ))}
                  </dl>
                </div>
                <div>
                  <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Business</h3>
                  <dl className="space-y-2">
                    {[
                      ['Name', selected.business_name],
                      ['Type', selected.business_type],
                      ['Volume', selected.monthly_volume_usd ? `$${Number(selected.monthly_volume_usd).toLocaleString()}/mo` : null],
                    ].map(([k, v]) => (
                      <div key={k} className="flex gap-2 text-sm">
                        <dt className="text-gray-500 w-16 shrink-0">{k}</dt>
                        <dd className="text-gray-900">{v || '—'}</dd>
                      </div>
                    ))}
                  </dl>
                </div>
              </div>

              {/* Documents */}
              <div className="mb-6">
                <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Documents</h3>
                {selected.documents?.length > 0 ? (
                  <div className="grid grid-cols-3 gap-3">
                    {selected.documents.map((doc) => (
                      <a
                        key={doc.id}
                        href={doc.file}
                        target="_blank"
                        rel="noreferrer"
                        className="border border-gray-200 rounded-lg p-3 text-center hover:bg-gray-50 transition"
                      >
                        <div className="text-2xl mb-1">📄</div>
                        <div className="text-xs font-medium text-gray-700 capitalize">
                          {doc.doc_type.replace('_', ' ')}
                        </div>
                        <div className="text-xs text-gray-400 truncate">{doc.original_filename}</div>
                      </a>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-gray-400">No documents uploaded.</p>
                )}
              </div>

              {/* Previous reviewer note */}
              {selected.reviewer_note && (
                <div className="mb-4 bg-orange-50 border border-orange-200 rounded-lg px-4 py-3 text-sm text-orange-800">
                  <strong>Previous note:</strong> {selected.reviewer_note}
                </div>
              )}

              {/* Action zone */}
              {REVIEWER_ACTIONS[selected.state] && (
                <div className="border-t border-gray-100 pt-4">
                  <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Actions</h3>
                  <textarea
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    placeholder="Add a note (required for rejection/more info)"
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mb-3 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                    rows={2}
                  />
                  <div className="flex gap-2 flex-wrap">
                    {REVIEWER_ACTIONS[selected.state].map((action) => (
                      <button
                        key={action.state}
                        onClick={() => doTransition(action.state)}
                        disabled={transitioning}
                        className={`px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50 transition ${action.style}`}
                      >
                        {transitioning ? '…' : action.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {['approved', 'rejected'].includes(selected.state) && (
                <div className="border-t border-gray-100 pt-4 text-sm text-gray-400">
                  This submission is in a terminal state. No further actions available.
                </div>
              )}
            </div>
          ) : (
            <div className="flex-1 bg-white rounded-2xl border border-gray-200 flex items-center justify-center">
              <div className="text-center text-gray-400">
                <div className="text-4xl mb-3">👆</div>
                <p className="text-sm">Select a submission from the queue to review</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
