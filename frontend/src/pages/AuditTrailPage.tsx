import React, { useState } from 'react';
import {
  Clock,
  Download,
  FileText,
  Filter,
  Search,
  Shield,
  UserCheck,
} from 'lucide-react';
import { AuditEntry } from '../types';

interface AuditTrailPageProps {
  auditLog: AuditEntry[];
}

export const AuditTrailPage: React.FC<AuditTrailPageProps> = ({ auditLog }) => {
  const [search, setSearch] = useState('');

  // Realistic chronological audit sequence from user request
  const staticAuditTimeline = [
    { time: '14:34:21', event: 'INC-2048', type: 'APPROVAL', actor: 's.vance@noc-eng', desc: 'Remediation approved (AS65001 graceful BGP drain & Gi0/24 optical recalibration)' },
    { time: '14:33:04', event: 'INC-2048', type: 'GATE', actor: 'ApprovalAgent', desc: 'Human approval requested (Lock #POL-OPC-9 enforced on Core Transit link)' },
    { time: '14:32:11', event: 'INC-2048', type: 'PROPOSAL', actor: 'RemediationAgent', desc: 'Remediation proposed: PR-NET-BGP-DRAIN-AND-CYCLE' },
    { time: '14:32:10', event: 'INC-2048', type: 'RCA', actor: 'RcaAgent', desc: 'RCA generated: Optical SFP+ Transceiver diode budget loss (-19.2 dBm)' },
    { time: '14:32:09', event: 'INC-2048', type: 'CLASSIFY', actor: 'TriageModel', desc: 'ML classification completed (Confidence: 94.2%, Class: HARDWARE_PHYSICAL)' },
    { time: '14:32:08', event: 'INC-2048', type: 'DETECTION', actor: 'DetectionAgent', desc: 'INC-2048 detected: Abnormal packet loss spike (34.2%) on Router R-204:Gi0/24' },
  ];

  const liveTimeline = auditLog.map((a) => ({
    time: a.ts ? a.ts.slice(11, 19) : '--',
    event: a.event_id || 'AUDIT-EVT',
    type: 'REMEDIATION',
    actor: 'AnsibleRunner',
    desc: `Remediation executed on ${a.host || 'node'}: ${a.playbook || 'remediate_mtu.yml'} (${a.reason || 'Threshold breach'})`,
  }));

  const combined = [...liveTimeline, ...staticAuditTimeline];

  const filtered = combined.filter((item) => {
    if (search) {
      const q = search.toLowerCase();
      return item.event.toLowerCase().includes(q) || item.desc.toLowerCase().includes(q) || item.actor.toLowerCase().includes(q);
    }
    return true;
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Page Header */}
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
            IMMUTABLE SECURITY & OPERATIONAL LEDGER
          </div>
          <h1 style={{ fontSize: '1.45rem', fontWeight: 800, letterSpacing: '-0.02em', color: '#f8fafc' }}>
            NOC Chronological Audit Trail
          </h1>
          <p style={{ fontSize: '0.775rem', color: '#94a3b8', marginTop: '0.2rem' }}>
            Cryptographically timestamped telemetry events, model triage classifications, human sign-offs, and remediation playbooks.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="noc-btn noc-btn-outline" style={{ height: '32px' }}>
            <Download size={13} />
            Export Audit Ledger
          </button>
        </div>
      </div>

      {/* Search Filter */}
      <div
        className="noc-card"
        style={{
          padding: '0.65rem 0.85rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ position: 'relative', width: '380px' }}>
          <Search
            size={12}
            style={{ position: 'absolute', left: '9px', top: '50%', transform: 'translateY(-50%)', color: '#64748b' }}
          />
          <input
            type="text"
            className="noc-input"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search audit trail, actor, incident..."
            style={{ width: '100%', paddingLeft: '28px', height: '28px', fontSize: '0.75rem' }}
          />
        </div>

        <span style={{ fontSize: '0.6875rem', color: '#64748b', fontFamily: 'var(--font-mono)' }}>
          {filtered.length} Recorded Entries
        </span>
      </div>

      {/* Timeline List */}
      <div className="noc-card">
        <div style={{ padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
          {filtered.map((item, idx) => (
            <div
              key={idx}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '1rem',
                padding: '0.65rem 0.85rem',
                backgroundColor: '#0c0f15',
                border: '1px solid #1a2230',
                borderRadius: '3px',
              }}
            >
              <div
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.75rem',
                  color: '#38bdf8',
                  fontWeight: 700,
                  width: '75px',
                  flexShrink: 0,
                }}
              >
                {item.time}
              </div>

              <div style={{ width: '100px', flexShrink: 0 }}>
                <span
                  className="noc-badge"
                  style={{
                    backgroundColor:
                      item.type === 'APPROVAL'
                        ? 'rgba(16, 185, 129, 0.15)'
                        : item.type === 'GATE'
                        ? 'rgba(245, 158, 11, 0.15)'
                        : 'rgba(56, 189, 248, 0.12)',
                    color:
                      item.type === 'APPROVAL'
                        ? '#10b981'
                        : item.type === 'GATE'
                        ? '#f59e0b'
                        : '#38bdf8',
                    border: `1px solid ${
                      item.type === 'APPROVAL'
                        ? '#10b981'
                        : item.type === 'GATE'
                        ? '#f59e0b'
                        : 'rgba(56, 189, 248, 0.3)'
                    }`,
                  }}
                >
                  {item.type}
                </span>
              </div>

              <div style={{ flex: 1 }}>
                <div style={{ fontSize: '0.775rem', fontWeight: 600, color: '#f1f5f9' }}>
                  {item.desc}
                </div>
                <div
                  style={{
                    fontSize: '0.65rem',
                    color: '#64748b',
                    fontFamily: 'var(--font-mono)',
                    marginTop: '2px',
                    display: 'flex',
                    gap: '1rem',
                  }}
                >
                  <span>Event: <strong style={{ color: '#cbd5e1' }}>{item.event}</strong></span>
                  <span>Actor: <strong style={{ color: '#cbd5e1' }}>{item.actor}</strong></span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
