import React, { useState } from 'react';
import { CheckCircle2, Filter, GitBranch, Search, Sliders, Zap } from 'lucide-react';
import { Decision } from '../types';

interface DecisionsPageProps {
  decisions: Decision[];
  onInject: () => void;
}

export const DecisionsPage: React.FC<DecisionsPageProps> = ({ decisions, onInject }) => {
  const [filterAction, setFilterAction] = useState<string>('ALL');
  const [search, setSearch] = useState('');

  const filtered = decisions.filter((d) => {
    if (filterAction === 'REMEDIATE' && !d.remediate) return false;
    if (filterAction === 'OK' && d.remediate) return false;

    if (search) {
      const q = search.toLowerCase();
      const txt = `${d.host} ${d.event_id} ${d.log_class} ${d.rule_reason || ''} ${d.playbook || ''}`.toLowerCase();
      if (!txt.includes(q)) return false;
    }
    return true;
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Page Title */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.4rem',
              padding: '0.15rem 0.5rem',
              backgroundColor: '#131922',
              border: '1px solid #1f2838',
              borderRadius: '2px',
              fontSize: '0.625rem',
              fontFamily: 'var(--font-mono)',
              color: '#38bdf8',
              fontWeight: 600,
              marginBottom: '0.4rem',
            }}
          >
            TRIAGE DECISION MATRIX
          </div>
          <h1 style={{ fontSize: '1.45rem', fontWeight: 800, letterSpacing: '-0.02em', color: '#f8fafc' }}>
            Multi-Engine Triage Decisions
          </h1>
          <p style={{ fontSize: '0.775rem', color: '#94a3b8', marginTop: '0.2rem' }}>
            Combined outcomes from deterministic thresholds, MiniLM transformer log classification, and XGBoost telemetry models.
          </p>
        </div>

        <button onClick={onInject} className="noc-btn noc-btn-cyan-outline" style={{ height: '32px' }}>
          <Zap size={13} />
          Inject Test Event
        </button>
      </div>

      {/* Filter Bar */}
      <div
        className="noc-card"
        style={{
          padding: '0.65rem 0.85rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '0.75rem',
        }}
      >
        <div style={{ display: 'flex', gap: '0.35rem' }}>
          {[
            { id: 'ALL', label: `All (${decisions.length})` },
            { id: 'REMEDIATE', label: `Remediate (${decisions.filter((d) => d.remediate).length})` },
            { id: 'OK', label: `OK (${decisions.filter((d) => !d.remediate).length})` },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setFilterAction(tab.id)}
              style={{
                padding: '0.25rem 0.6rem',
                fontSize: '0.6875rem',
                fontFamily: 'var(--font-mono)',
                borderRadius: '3px',
                border: '1px solid',
                borderColor: filterAction === tab.id ? '#38bdf8' : '#1e2430',
                backgroundColor: filterAction === tab.id ? 'rgba(56, 189, 248, 0.12)' : 'transparent',
                color: filterAction === tab.id ? '#38bdf8' : '#64748b',
                cursor: 'pointer',
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div style={{ position: 'relative', width: '300px' }}>
          <Search
            size={12}
            style={{ position: 'absolute', left: '9px', top: '50%', transform: 'translateY(-50%)', color: '#64748b' }}
          />
          <input
            type="text"
            className="noc-input"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filter host, event ID, rule..."
            style={{ width: '100%', paddingLeft: '28px', height: '28px', fontSize: '0.75rem' }}
          />
        </div>
      </div>

      {/* Decisions Table */}
      <div className="noc-card">
        <div className="noc-table-wrapper">
          <table className="noc-table">
            <thead>
              <tr>
                <th style={{ width: '85px' }}>TIME</th>
                <th style={{ width: '90px' }}>HOST</th>
                <th style={{ width: '130px' }}>EVENT ID</th>
                <th>RULE RESULT</th>
                <th style={{ width: '120px' }}>NLP LOG CLASS</th>
                <th style={{ width: '90px' }}>ML SCORE</th>
                <th style={{ width: '95px' }}>ACTION</th>
                <th style={{ width: '140px' }}>PLAYBOOK</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length > 0 ? (
                filtered.slice().reverse().map((d, idx) => (
                  <tr key={d.event_id || idx}>
                    <td style={{ fontFamily: 'var(--font-mono)', color: '#94a3b8' }}>
                      {d.ts ? d.ts.slice(11, 19) : '--'}
                    </td>
                    <td style={{ fontWeight: 600, color: '#f1f5f9' }}>{d.host || '--'}</td>
                    <td style={{ fontFamily: 'var(--font-mono)', color: '#38bdf8', fontSize: '0.725rem' }}>
                      {d.event_id ? (d.event_id.length > 18 ? `${d.event_id.slice(0, 16)}...` : d.event_id) : '--'}
                    </td>
                    <td>
                      <span
                        className={`noc-badge ${
                          d.rule_action === 'remediate' ? 'noc-badge-crit' : 'noc-badge-ok'
                        }`}
                        style={{ marginRight: '0.4rem' }}
                      >
                        {d.rule_action}
                      </span>
                      <span style={{ fontSize: '0.6875rem', color: '#94a3b8' }}>{d.rule_reason}</span>
                    </td>
                    <td>
                      <span className="noc-badge noc-badge-med">{d.log_class || 'UNKNOWN'}</span>
                    </td>
                    <td>
                      <span
                        style={{
                          fontFamily: 'var(--font-mono)',
                          fontWeight: 700,
                          color: (d.ml_priority || 0) >= 0.85 ? '#f43f5e' : '#10b981',
                        }}
                      >
                        {d.ml_priority !== undefined ? d.ml_priority : '--'}
                      </span>
                    </td>
                    <td>
                      <span className={`noc-badge ${d.remediate ? 'noc-badge-crit' : 'noc-badge-ok'}`}>
                        {d.remediate ? 'REMEDIATE' : 'OK'}
                      </span>
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', color: '#cbd5e1', fontSize: '0.725rem' }}>
                      {d.playbook ? <strong style={{ color: '#38bdf8' }}>{d.playbook}</strong> : <span style={{ color: '#475569' }}>--</span>}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={8} style={{ textAlign: 'center', padding: '2rem', color: '#64748b' }}>
                    No decisions recorded yet. Inject events or load fixtures to begin triage.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
