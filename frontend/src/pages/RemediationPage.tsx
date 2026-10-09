import React, { useState } from 'react';
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  FileCode,
  Play,
  RotateCcw,
  Search,
  Shield,
  ShieldAlert,
  Terminal,
  Wrench,
  X,
} from 'lucide-react';
import { AIIncident, AuditEntry } from '../types';

interface RemediationPageProps {
  auditLog: AuditEntry[];
  aiIncidents: AIIncident[];
  onApprove: (incidentId: string, approved: boolean) => void;
  isApproving: boolean;
}

export const RemediationPage: React.FC<RemediationPageProps> = ({
  auditLog,
  aiIncidents,
  onApprove,
  isApproving,
}) => {
  const [filterStatus, setFilterStatus] = useState<string>('ALL');

  // Realistic remediation items
  const staticRemediations = [
    {
      id: 'REM-1048',
      incidentId: 'INC-2048',
      host: 'r-204-edge.transit.iad',
      playbook: 'remediate_mtu.yml & bgp_drain.yml',
      reason: 'Physical optical loss on Gi0/24 with BGP peer flap risk',
      risk: 'HIGH',
      status: 'AWAITING APPROVAL',
      execution: 'Dry-run (Safety gated)',
      ts: '14:32:11',
    },
    {
      id: 'REM-1045',
      incidentId: 'INC-2045',
      host: 'sw-118-leaf.rack-04',
      playbook: 'rebalance_buffer.yml',
      reason: 'Taildrop buffer saturation on Te1/0/12',
      risk: 'MEDIUM',
      status: 'APPROVED',
      execution: 'Ansible Dispatch',
      ts: '14:26:30',
    },
    {
      id: 'REM-1039',
      incidentId: 'INC-2039',
      host: 'bgw-01.transit.sjc',
      playbook: 'restart_driver.yml',
      reason: 'Kernel driver oops detected in RDMA QP stack',
      risk: 'LOW',
      status: 'EXECUTED',
      execution: 'Completed (0 drop)',
      ts: '13:49:02',
    },
  ];

  // Combine with live audit records from backend
  const liveRemediations = auditLog.map((a, idx) => ({
    id: `REM-LIVE-${idx + 1}`,
    incidentId: a.event_id || 'INC-LIVE',
    host: a.host || 'node',
    playbook: a.playbook || 'remediate_mtu.yml',
    reason: a.reason || 'Threshold breach',
    risk: 'MEDIUM',
    status: 'EXECUTED',
    execution: a.status || 'dry-run (UI mode)',
    ts: a.ts ? a.ts.slice(11, 19) : '--',
  }));

  const allItems = [...liveRemediations, ...staticRemediations];

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
            ANSIBLE AUTOMATION PLAYBOOKS
          </div>
          <h1 style={{ fontSize: '1.45rem', fontWeight: 800, letterSpacing: '-0.02em', color: '#f8fafc' }}>
            Remediation & Playbook Orchestration
          </h1>
          <p style={{ fontSize: '0.775rem', color: '#94a3b8', marginTop: '0.2rem' }}>
            Safe, automated Ansible remediations (MTU alignment, BGP graceful drain, driver reload) governed by human-in-the-loop policies.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <span className="noc-badge noc-badge-ok">SAFETY GUARDRAILS ACTIVE</span>
        </div>
      </div>

      {/* KPI Cards Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.75rem' }}>
        <div className="noc-card" style={{ padding: '0.85rem' }}>
          <div style={{ fontSize: '0.6875rem', color: '#94a3b8' }}>Total Remediations Triggered</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 800, color: '#f1f5f9', fontFamily: 'var(--font-mono)', margin: '0.2rem 0' }}>
            {allItems.length}
          </div>
          <div style={{ fontSize: '0.6875rem', color: '#64748b' }}>Platform lifetime</div>
        </div>

        <div className="noc-card" style={{ padding: '0.85rem', borderColor: '#2b2316' }}>
          <div style={{ fontSize: '0.6875rem', color: '#94a3b8' }}>Awaiting Human Gate</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 800, color: '#f59e0b', fontFamily: 'var(--font-mono)', margin: '0.2rem 0' }}>
            1 <span style={{ fontSize: '0.75rem', color: '#94a3b8', fontWeight: 400 }}>Action Blocked</span>
          </div>
          <div style={{ fontSize: '0.6875rem', color: '#f59e0b' }}>Tier-1 transit link policy</div>
        </div>

        <div className="noc-card" style={{ padding: '0.85rem' }}>
          <div style={{ fontSize: '0.6875rem', color: '#94a3b8' }}>Auto-Resolved</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 800, color: '#10b981', fontFamily: 'var(--font-mono)', margin: '0.2rem 0' }}>
            47 <span style={{ fontSize: '0.75rem', color: '#94a3b8', fontWeight: 400 }}>Clean runs</span>
          </div>
          <div style={{ fontSize: '0.6875rem', color: '#64748b' }}>98.2% automated MTTR</div>
        </div>

        <div className="noc-card" style={{ padding: '0.85rem' }}>
          <div style={{ fontSize: '0.6875rem', color: '#94a3b8' }}>Playbook Repertoire</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 800, color: '#38bdf8', fontFamily: 'var(--font-mono)', margin: '0.2rem 0' }}>
            3 Verified
          </div>
          <div style={{ fontSize: '0.6875rem', color: '#64748b' }}>MTU, Driver, BGP Drain</div>
        </div>
      </div>

      {/* Remediation Items Table */}
      <div className="noc-card">
        <div className="noc-card-header">
          <div className="noc-card-title">
            <Wrench size={13} style={{ color: '#38bdf8' }} />
            Active & Executed Remediation Plans
          </div>
        </div>

        <div className="noc-table-wrapper">
          <table className="noc-table">
            <thead>
              <tr>
                <th style={{ width: '80px' }}>TIME</th>
                <th style={{ width: '100px' }}>INCIDENT</th>
                <th style={{ width: '140px' }}>AFFECTED TARGET</th>
                <th style={{ width: '180px' }}>RECOMMENDED ACTION / PLAYBOOK</th>
                <th>REMEDIATION REASON</th>
                <th style={{ width: '75px' }}>RISK</th>
                <th style={{ width: '130px' }}>STATUS</th>
                <th style={{ width: '130px', textAlign: 'right' }}>APPROVAL ACTION</th>
              </tr>
            </thead>
            <tbody>
              {allItems.map((rem) => {
                const isPending = rem.status === 'AWAITING APPROVAL';
                const isExecuted = rem.status === 'EXECUTED';
                const isApproved = rem.status === 'APPROVED';

                return (
                  <tr key={rem.id}>
                    <td style={{ fontFamily: 'var(--font-mono)', color: '#94a3b8' }}>{rem.ts}</td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: '#38bdf8' }}>
                      {rem.incidentId}
                    </td>
                    <td>
                      <div style={{ fontWeight: 600, color: '#f1f5f9' }}>{rem.host}</div>
                    </td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                        <FileCode size={12} style={{ color: '#38bdf8' }} />
                        <span style={{ fontFamily: 'var(--font-mono)', color: '#cbd5e1', fontWeight: 600 }}>
                          {rem.playbook}
                        </span>
                      </div>
                    </td>
                    <td style={{ fontSize: '0.725rem', color: '#94a3b8' }}>{rem.reason}</td>
                    <td>
                      <span
                        className={`noc-badge ${
                          rem.risk === 'HIGH' ? 'noc-badge-crit' : rem.risk === 'MEDIUM' ? 'noc-badge-high' : 'noc-badge-ok'
                        }`}
                      >
                        {rem.risk}
                      </span>
                    </td>
                    <td>
                      <span
                        className="noc-badge"
                        style={{
                          backgroundColor: isPending ? 'rgba(245, 158, 11, 0.15)' : isApproved ? 'rgba(56, 189, 248, 0.15)' : 'rgba(16, 185, 129, 0.15)',
                          color: isPending ? '#f59e0b' : isApproved ? '#38bdf8' : '#10b981',
                          borderColor: isPending ? '#f59e0b' : isApproved ? '#38bdf8' : '#10b981',
                        }}
                      >
                        ● {rem.status}
                      </span>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      {isPending ? (
                        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.35rem' }}>
                          <button
                            onClick={() => onApprove(rem.incidentId, true)}
                            disabled={isApproving}
                            className="noc-btn noc-btn-primary"
                            style={{ padding: '0.2rem 0.5rem', fontSize: '0.625rem' }}
                          >
                            <Check size={11} /> Approve
                          </button>
                          <button
                            onClick={() => onApprove(rem.incidentId, false)}
                            disabled={isApproving}
                            className="noc-btn noc-btn-danger"
                            style={{ padding: '0.2rem 0.5rem', fontSize: '0.625rem' }}
                          >
                            <X size={11} />
                          </button>
                        </div>
                      ) : (
                        <span style={{ color: '#64748b', fontSize: '0.6875rem', fontFamily: 'var(--font-mono)' }}>
                          {rem.execution}
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
