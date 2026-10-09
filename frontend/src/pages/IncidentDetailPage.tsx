import React, { useState } from 'react';
import {
  Activity,
  AlertOctagon,
  AlertTriangle,
  ArrowLeft,
  Check,
  CheckCircle2,
  Clock,
  Code,
  Copy,
  Cpu,
  ExternalLink,
  Layers,
  Lock,
  Play,
  RotateCcw,
  Server,
  Shield,
  ShieldAlert,
  Terminal,
  UserCheck,
  X,
  Zap,
} from 'lucide-react';
import { PageId } from '../types';

interface IncidentDetailPageProps {
  incidentId: string;
  onBack: () => void;
  onApprove: (incidentId: string, approved: boolean) => void;
  isApproving: boolean;
}

export const IncidentDetailPage: React.FC<IncidentDetailPageProps> = ({
  incidentId,
  onBack,
  onApprove,
  isApproving,
}) => {
  const [approvalStatus, setApprovalStatus] = useState<'pending' | 'approved' | 'rejected'>('pending');
  const [copiedPayload, setCopiedPayload] = useState(false);

  const handleAction = (approved: boolean) => {
    setApprovalStatus(approved ? 'approved' : 'rejected');
    onApprove(incidentId, approved);
  };

  const cliPayload = `router bgp 65001
 neighbor 62.115.148.1 route-map RM-DRAIN-OUT out
interface GigabitEthernet0/24
 shutdown
# Awaiting signature to dispatch SSH payload...`;

  const copyCliPayload = () => {
    navigator.clipboard.writeText(cliPayload);
    setCopiedPayload(true);
    setTimeout(() => setCopiedPayload(false), 2000);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Top Breadcrumb & Utilities */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
          <button
            onClick={onBack}
            className="noc-btn noc-btn-outline"
            style={{ height: '28px', padding: '0 0.65rem' }}
          >
            <ArrowLeft size={13} />
            Back to Active Incidents
          </button>
          <span style={{ color: '#475569', fontSize: '0.75rem' }}>/</span>
          <span style={{ color: '#94a3b8', fontSize: '0.75rem', fontFamily: 'var(--font-mono)' }}>
            CORE ROUTING US-EAST
          </span>
          <span style={{ color: '#475569', fontSize: '0.75rem' }}>/</span>
          <span style={{ color: '#38bdf8', fontSize: '0.75rem', fontFamily: 'var(--font-mono)', fontWeight: 700 }}>
            {incidentId}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <button className="noc-btn noc-btn-outline" style={{ height: '28px', fontSize: '0.6875rem' }}>
            <Terminal size={12} />
            SSH Console R-204
          </button>
          <button className="noc-btn noc-btn-outline" style={{ height: '28px', fontSize: '0.6875rem' }}>
            Export PCAP & Logs
          </button>
        </div>
      </div>

      {/* Incident Header & Metadata Badges */}
      <div className="noc-card" style={{ padding: '1.15rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.55rem', marginBottom: '0.55rem' }}>
          <span className="noc-badge noc-badge-crit">● CRITICAL</span>
          <span
            className="noc-badge"
            style={{
              backgroundColor:
                approvalStatus === 'approved'
                  ? 'rgba(16, 185, 129, 0.15)'
                  : approvalStatus === 'rejected'
                  ? 'rgba(244, 63, 94, 0.15)'
                  : 'rgba(245, 158, 11, 0.15)',
              color:
                approvalStatus === 'approved' ? '#10b981' : approvalStatus === 'rejected' ? '#f43f5e' : '#f59e0b',
              border: `1px solid ${
                approvalStatus === 'approved' ? '#10b981' : approvalStatus === 'rejected' ? '#f43f5e' : '#f59e0b'
              }`,
            }}
          >
            ● {approvalStatus === 'approved' ? 'REMEDIATION APPROVED' : approvalStatus === 'rejected' ? 'REMEDIATION REJECTED' : 'AWAITING HUMAN APPROVAL'}
          </span>
          <span style={{ fontSize: '0.6875rem', color: '#64748b', fontFamily: 'var(--font-mono)' }}>
            ID: <strong style={{ color: '#cbd5e1' }}>{incidentId}</strong>
          </span>
          <span style={{ fontSize: '0.6875rem', color: '#64748b', fontFamily: 'var(--font-mono)' }}>
            Target: <strong style={{ color: '#cbd5e1' }}>Router R-204 (10.240.4.1)</strong>
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '1rem' }}>
          <div>
            <h1 style={{ fontSize: '1.45rem', fontWeight: 800, color: '#f8fafc', letterSpacing: '-0.02em' }}>
              {incidentId} — Packet Loss Spike on Core Uplink (Router R-204)
            </h1>
          </div>

          {/* KPI Strip */}
          <div style={{ display: 'flex', gap: '0.85rem', flexShrink: 0 }}>
            <div
              style={{
                padding: '0.35rem 0.65rem',
                backgroundColor: '#0c1017',
                border: '1px solid #1e2636',
                borderRadius: '3px',
                textAlign: 'right',
              }}
            >
              <div style={{ fontSize: '0.5625rem', color: '#64748b', fontFamily: 'var(--font-mono)' }}>TRIAGE CONFIDENCE</div>
              <div style={{ fontSize: '1.05rem', fontWeight: 800, color: '#10b981', fontFamily: 'var(--font-mono)' }}>
                94.2%
              </div>
            </div>

            <div
              style={{
                padding: '0.35rem 0.65rem',
                backgroundColor: '#0c1017',
                border: '1px solid #1e2636',
                borderRadius: '3px',
                textAlign: 'right',
              }}
            >
              <div style={{ fontSize: '0.5625rem', color: '#64748b', fontFamily: 'var(--font-mono)' }}>PACKET LOSS PEAK</div>
              <div style={{ fontSize: '1.05rem', fontWeight: 800, color: '#f43f5e', fontFamily: 'var(--font-mono)' }}>
                34.2%
              </div>
            </div>

            <div
              style={{
                padding: '0.35rem 0.65rem',
                backgroundColor: '#0c1017',
                border: '1px solid #1e2636',
                borderRadius: '3px',
                textAlign: 'right',
              }}
            >
              <div style={{ fontSize: '0.5625rem', color: '#64748b', fontFamily: 'var(--font-mono)' }}>DETECTED</div>
              <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#cbd5e1', fontFamily: 'var(--font-mono)', marginTop: '2px' }}>
                14:32:08 UTC
              </div>
            </div>
          </div>
        </div>

        {/* Metadata pills */}
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: '1.25rem',
            paddingTop: '0.85rem',
            marginTop: '0.85rem',
            borderTop: '1px solid #1a2230',
            fontSize: '0.6875rem',
            color: '#94a3b8',
            fontFamily: 'var(--font-mono)',
          }}
        >
          <div>Service Route: <strong style={{ color: '#e2e8f0' }}>Core Backbone Transit</strong></div>
          <div>ASN / Location: <strong style={{ color: '#e2e8f0' }}>ASN 16185 • US-EAST PoP</strong></div>
          <div>Affected Interface: <strong style={{ color: '#38bdf8' }}>Gi0/24 (Tier-1 Telia)</strong></div>
          <div>Host OS / Platform: <strong style={{ color: '#e2e8f0' }}>Arista EOS - 4.28.5M</strong></div>
          <div>Egress Blast Radius: <strong style={{ color: '#f59e0b' }}>1.4 Tbps Transit</strong></div>
          <div>Assigned Responder: <strong style={{ color: '#10b981' }}>s.vance (Tier-3 On-Call)</strong></div>
        </div>
      </div>

      {/* INCIDENT TIMELINE STAGES */}
      <div className="noc-card" style={{ padding: '0.85rem 1rem' }}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(6, 1fr)',
            gap: '0.5rem',
            position: 'relative',
          }}
        >
          {[
            { step: '1. Detected', time: '14:32:08 UTC', done: true },
            { step: '2. Triaged', time: '14:32:09 UTC', done: true },
            { step: '3. Root Cause ID', time: '14:32:10 UTC', done: true },
            { step: '4. Plan Proposed', time: '14:32:11 UTC', done: true },
            {
              step: '5. Awaiting Approval',
              time: approvalStatus === 'approved' ? 'APPROVED' : 'ACTION REQUIRED',
              active: approvalStatus === 'pending',
              done: approvalStatus === 'approved',
            },
            {
              step: '6. Execution / Resolved',
              time: approvalStatus === 'approved' ? 'Dispatched' : 'Staged',
              done: approvalStatus === 'approved',
            },
          ].map((s, idx) => (
            <div
              key={s.step}
              style={{
                padding: '0.45rem 0.65rem',
                backgroundColor: s.active ? '#1c1815' : s.done ? '#0f1718' : '#0c0f15',
                border: `1px solid ${
                  s.active ? '#f59e0b' : s.done ? '#10b981' : '#1e2430'
                }`,
                borderRadius: '3px',
              }}
            >
              <div
                style={{
                  fontSize: '0.625rem',
                  fontFamily: 'var(--font-mono)',
                  color: s.active ? '#f59e0b' : s.done ? '#10b981' : '#64748b',
                  fontWeight: 700,
                }}
              >
                {s.done ? '✓ ' : s.active ? '● ' : ''}
                {s.step}
              </div>
              <div
                style={{
                  fontSize: '0.625rem',
                  color: s.active ? '#f59e0b' : '#94a3b8',
                  marginTop: '2px',
                  fontFamily: 'var(--font-mono)',
                }}
              >
                {s.time}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* HUMAN APPROVAL GATE - Prominent Alert Box */}
      <div
        className="noc-card"
        style={{
          border: '1px solid #f59e0b',
          backgroundColor: '#12100d',
          padding: '1.15rem 1.25rem',
          boxShadow: '0 4px 20px rgba(245, 158, 11, 0.08)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '1.5rem' }}>
          <div style={{ display: 'flex', gap: '0.85rem' }}>
            <div
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '4px',
                backgroundColor: 'rgba(245, 158, 11, 0.15)',
                border: '1px solid #f59e0b',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#f59e0b',
                flexShrink: 0,
              }}
            >
              <ShieldAlert size={20} />
            </div>

            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
                <span style={{ fontSize: '0.875rem', fontWeight: 800, color: '#f8fafc', letterSpacing: '-0.01em' }}>
                  Human Approval Gate Required
                </span>
                <span
                  style={{
                    padding: '0.1rem 0.4rem',
                    backgroundColor: 'rgba(245, 158, 11, 0.2)',
                    color: '#f59e0b',
                    fontSize: '0.625rem',
                    fontFamily: 'var(--font-mono)',
                    fontWeight: 700,
                    borderRadius: '2px',
                  }}
                >
                  LOCK: POLICY #POL-OPC-9
                </span>
              </div>

              <p style={{ fontSize: '0.775rem', color: '#cbd5e1', lineHeight: 1.5, maxWidth: '850px' }}>
                Autonomous execution is blocked for Tier-1 core uplinks. You are signing off on an automated graceful BGP drain (<strong style={{ color: '#f59e0b' }}>AS65001-B: graceful-shutdown</strong>) to peer 62.115.148.1, live route shift to backup <strong style={{ color: '#38bdf8' }}>Gi0/25</strong>, and optical transceiver reset on <strong style={{ color: '#f43f5e' }}>Gi0/24</strong>.
              </p>

              <div
                style={{
                  display: 'flex',
                  gap: '1.25rem',
                  marginTop: '0.65rem',
                  fontSize: '0.6875rem',
                  color: '#94a3b8',
                  fontFamily: 'var(--font-mono)',
                }}
              >
                <span>Pre-check: <strong style={{ color: '#10b981' }}>PASS</strong></span>
                <span>Capacity Headroom: <strong style={{ color: '#10b981' }}>52% (41% used)</strong></span>
                <span>Estimated Outage Loss: <strong style={{ color: '#10b981' }}>0 pkts</strong></span>
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', flexShrink: 0 }}>
            {approvalStatus === 'pending' ? (
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button
                  onClick={() => handleAction(true)}
                  disabled={isApproving}
                  className="noc-btn noc-btn-primary"
                  style={{ height: '34px', padding: '0 1rem' }}
                >
                  <Check size={14} />
                  {isApproving ? 'Submitting...' : 'Approve Remediation (Drain & Recalibrate)'}
                </button>
                <button
                  onClick={() => handleAction(false)}
                  disabled={isApproving}
                  className="noc-btn noc-btn-danger"
                  style={{ height: '34px', padding: '0 0.85rem' }}
                >
                  <X size={14} />
                  Reject
                </button>
                <button className="noc-btn noc-btn-outline" style={{ height: '34px' }}>
                  Request Peer Review
                </button>
              </div>
            ) : (
              <div
                style={{
                  padding: '0.45rem 0.85rem',
                  borderRadius: '3px',
                  backgroundColor: approvalStatus === 'approved' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(244, 63, 94, 0.15)',
                  border: `1px solid ${approvalStatus === 'approved' ? '#10b981' : '#f43f5e'}`,
                  color: approvalStatus === 'approved' ? '#10b981' : '#f43f5e',
                  fontWeight: 700,
                  fontSize: '0.75rem',
                  fontFamily: 'var(--font-mono)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                }}
              >
                {approvalStatus === 'approved' ? <CheckCircle2 size={16} /> : <AlertOctagon size={16} />}
                Remediation plan {approvalStatus} by engineer
              </div>
            )}
          </div>
        </div>
      </div>

      {/* TWO COLUMN INVESTIGATION LAYOUT */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '1.25rem' }}>
        {/* LEFT COLUMN: Telemetry, Triage Breakdown, RCA, Correlated Signals */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* 1. Incident Telemetry & Detection Vector */}
          <div className="noc-card">
            <div className="noc-card-header">
              <div className="noc-card-title">
                <Activity size={13} style={{ color: '#38bdf8' }} />
                Incident Telemetry & Detection Vector
              </div>
              <span style={{ fontSize: '0.625rem', fontFamily: 'var(--font-mono)', color: '#64748b' }}>
                SAMPLING RATE: 100ms
              </span>
            </div>

            <div style={{ padding: '0.9rem' }}>
              <p style={{ fontSize: '0.775rem', color: '#cbd5e1', lineHeight: 1.5, marginBottom: '0.75rem' }}>
                At 14:32:08 UTC, <strong style={{ color: '#38bdf8' }}>Router R-204</strong> reported a sudden, severe burst of packet loss peaking at <strong style={{ color: '#f43f5e' }}>34.2%</strong> across interface <strong style={{ color: '#f1f5f9' }}>GigabitEthernet0/24</strong> connecting to transit provider Tier-1 Telia. Concurrently, queue buffer discards rose by 820% with back-to-back CRC frame check errors. The anomaly was correlated across 14 syslog triggers and SNMP traps within 800ms of inception.
              </p>

              {/* Loss % vs Optical Rx dBm SVG graph */}
              <div style={{ backgroundColor: '#090c10', border: '1px solid #1c222e', borderRadius: '3px', padding: '0.75rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.625rem', fontFamily: 'var(--font-mono)', color: '#64748b', marginBottom: '0.4rem' }}>
                  <span>TELEMETRY: Gi0/24 PACKET LOSS RATE (%) & OPTICAL RX LEVEL (dBm)</span>
                  <div style={{ display: 'flex', gap: '0.75rem' }}>
                    <span style={{ color: '#f43f5e' }}>● Loss %</span>
                    <span style={{ color: '#38bdf8' }}>● Optical Rx (dBm)</span>
                  </div>
                </div>

                <div style={{ position: 'relative', height: '110px', width: '100%' }}>
                  <svg viewBox="0 0 500 110" preserveAspectRatio="none" style={{ width: '100%', height: '100%' }}>
                    {/* Grid lines */}
                    <line x1="0" y1="20" x2="500" y2="20" stroke="#1c2432" strokeWidth="1" strokeDasharray="2 2" />
                    <line x1="0" y1="55" x2="500" y2="55" stroke="#1c2432" strokeWidth="1" strokeDasharray="2 2" />
                    <line x1="0" y1="90" x2="500" y2="90" stroke="#1c2432" strokeWidth="1" strokeDasharray="2 2" />

                    {/* Critical threshold text */}
                    <text x="5" y="16" fill="#f43f5e" fontSize="9" fontFamily="var(--font-mono)">SLA Breach Threshold [15%]</text>

                    {/* Optical Rx level (dropping down) */}
                    <path
                      d="M 0,30 L 150,32 L 250,35 L 290,92 L 340,95 L 420,96 L 500,94"
                      fill="none"
                      stroke="#38bdf8"
                      strokeWidth="2"
                    />

                    {/* Loss rate curve (spiking up) */}
                    <path
                      d="M 0,102 L 150,100 L 250,98 L 290,18 L 330,12 L 420,15 L 500,20"
                      fill="none"
                      stroke="#f43f5e"
                      strokeWidth="2.5"
                    />

                    {/* Anomaly trigger marker */}
                    <circle cx="290" cy="18" r="4" fill="#f43f5e" stroke="#000" strokeWidth="2" />
                    <text x="300" y="22" fill="#f43f5e" fontSize="9" fontFamily="var(--font-mono)" fontWeight="bold">34.2% PKT LOSS PEAK</text>
                  </svg>
                </div>
              </div>
            </div>
          </div>

          {/* 2. Triage Engine Breakdown */}
          <div className="noc-card">
            <div className="noc-card-header">
              <div className="noc-card-title">
                <Cpu size={13} style={{ color: '#38bdf8' }} />
                Triage Engine Breakdown
              </div>
              <span className="noc-badge noc-badge-crit">DECISION: LINK PHYSICAL FAILURE</span>
            </div>

            <div style={{ padding: '0.85rem', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
              <div style={{ padding: '0.65rem', backgroundColor: '#0c0f15', border: '1px solid #1a2230', borderRadius: '3px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.2rem' }}>
                  <span style={{ fontSize: '0.625rem', color: '#64748b', fontFamily: 'var(--font-mono)' }}>Deterministic Engine</span>
                  <span className="noc-badge noc-badge-crit">TRIGGERED</span>
                </div>
                <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#f1f5f9' }}>Rule #NET-402</div>
                <div style={{ fontSize: '0.6875rem', color: '#94a3b8', marginTop: '0.2rem' }}>
                  Packet loss &gt; 15% on designated transit uplink within a sliding 30-second window.
                </div>
                <div style={{ fontSize: '0.625rem', fontFamily: 'var(--font-mono)', color: '#f43f5e', marginTop: '0.35rem' }}>
                  Observed: 34.2% | Delta: +33.7%
                </div>
              </div>

              <div style={{ padding: '0.65rem', backgroundColor: '#0c0f15', border: '1px solid #1a2230', borderRadius: '3px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.2rem' }}>
                  <span style={{ fontSize: '0.625rem', color: '#64748b', fontFamily: 'var(--font-mono)' }}>Telemetry ML Model (v3.2)</span>
                  <span className="noc-badge noc-badge-ok">94.2% CONFIDENCE</span>
                </div>
                <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#f1f5f9' }}>Transceiver Degradation</div>
                <div style={{ fontSize: '0.6875rem', color: '#94a3b8', marginTop: '0.2rem' }}>
                  Cluster pattern matches optical attenuator drift / transceiver diode burnout profile.
                </div>
                <div style={{ fontSize: '0.625rem', fontFamily: 'var(--font-mono)', color: '#10b981', marginTop: '0.35rem' }}>
                  Class: HARDWARE_PHYSICAL | P(True) = 0.942
                </div>
              </div>

              <div style={{ padding: '0.65rem', backgroundColor: '#0c0f15', border: '1px solid #1a2230', borderRadius: '3px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.2rem' }}>
                  <span style={{ fontSize: '0.625rem', color: '#64748b', fontFamily: 'var(--font-mono)' }}>Syslog NLP Parser</span>
                  <span className="noc-badge noc-badge-med">PARSED 14 LOGS</span>
                </div>
                <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#f1f5f9' }}>PHY_ERR: Transceiver Optical Rx</div>
                <div style={{ fontSize: '0.6875rem', color: '#94a3b8', marginTop: '0.2rem' }}>
                  "Transceiver optical Rx power degraded below -18.4 dBm safety baseline."
                </div>
                <div style={{ fontSize: '0.625rem', fontFamily: 'var(--font-mono)', color: '#38bdf8', marginTop: '0.35rem' }}>
                  Severity: ALERT | Source: R-204:Gi0/24
                </div>
              </div>

              <div style={{ padding: '0.65rem', backgroundColor: '#0c0f15', border: '1px solid #1a2230', borderRadius: '3px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.2rem' }}>
                  <span style={{ fontSize: '0.625rem', color: '#64748b', fontFamily: 'var(--font-mono)' }}>Orchestrator Synthesis</span>
                  <span className="noc-badge noc-badge-high">SYNTHESIZED</span>
                </div>
                <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#f1f5f9' }}>Urgent Core Physical Link Failure</div>
                <div style={{ fontSize: '0.6875rem', color: '#94a3b8', marginTop: '0.2rem' }}>
                  Remediation playbook identified: PR-NET-BGP-DRAIN-AND-CYCLE.
                </div>
                <div style={{ fontSize: '0.625rem', fontFamily: 'var(--font-mono)', color: '#f59e0b', marginTop: '0.35rem' }}>
                  Escalation: TIER 3 | Auto-Action: Gated
                </div>
              </div>
            </div>
          </div>

          {/* 3. Root Cause Analysis (RCA Engine) */}
          <div className="noc-card">
            <div className="noc-card-header">
              <div className="noc-card-title">
                <ShieldAlert size={13} style={{ color: '#f43f5e' }} />
                Root Cause Analysis (RCA Engine)
              </div>
            </div>

            <div style={{ padding: '0.85rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div style={{ padding: '0.75rem', backgroundColor: '#131015', border: '1px solid #2e1d25', borderRadius: '3px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', marginBottom: '0.3rem' }}>
                  <span style={{ padding: '0.1rem 0.35rem', backgroundColor: '#f43f5e', color: '#fff', fontSize: '0.625rem', fontFamily: 'var(--font-mono)', fontWeight: 700, borderRadius: '2px' }}>
                    1
                  </span>
                  <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#f8fafc' }}>PRIMARY SUSPECT</span>
                </div>
                <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#f43f5e', marginBottom: '0.25rem' }}>
                  Optical SFP+ Transceiver (Tx/Rx Optical Budget Loss)
                </div>
                <p style={{ fontSize: '0.725rem', color: '#cbd5e1', lineHeight: 1.45 }}>
                  Continuous Digital Optical Monitoring (DOM) indicates Rx optical power on GigabitEthernet0/24 plunged to <strong style={{ color: '#f43f5e' }}>-19.2 dBm</strong> (standard operational window is -6.0 to -11.0 dBm). The link layer is experiencing physical photodiode saturation failures causing bit transposition and continuous Frame Check Sequence (FCS) drop.
                </p>
              </div>

              <div style={{ padding: '0.75rem', backgroundColor: '#12151d', border: '1px solid #1e2638', borderRadius: '3px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', marginBottom: '0.3rem' }}>
                  <span style={{ padding: '0.1rem 0.35rem', backgroundColor: '#38bdf8', color: '#000', fontSize: '0.625rem', fontFamily: 'var(--font-mono)', fontWeight: 700, borderRadius: '2px' }}>
                    2
                  </span>
                  <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#f8fafc' }}>SECONDARY CASCADING IMPACT</span>
                </div>
                <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#38bdf8', marginBottom: '0.25rem' }}>
                  Downstream BGP Keepalive Jitter & Imminent Session Flap
                </div>
                <p style={{ fontSize: '0.725rem', color: '#cbd5e1', lineHeight: 1.45 }}>
                  Due to the 34.2% drop rate, BGP keepalive packets between Router R-204 and Telia upstream peer (62.115.148.1) were dropped 2 consecutive cycles. If the hold timer (15s remaining) expires before graceful drain, routes will withdraw abruptly, generating global BGP route recalculation churn across 4 upstream routers.
                </p>
              </div>

              <div style={{ padding: '0.75rem', backgroundColor: '#11151c', border: '1px solid #1b2332', borderRadius: '3px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', marginBottom: '0.3rem' }}>
                  <span style={{ padding: '0.1rem 0.35rem', backgroundColor: '#f59e0b', color: '#000', fontSize: '0.625rem', fontFamily: 'var(--font-mono)', fontWeight: 700, borderRadius: '2px' }}>
                    3
                  </span>
                  <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#f8fafc' }}>BLAST RADIUS CALCULATION</span>
                </div>
                <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#f59e0b', marginBottom: '0.25rem' }}>
                  1.4 Tbps Egress Traffic at Immediate Blackhole Risk
                </div>
                <p style={{ fontSize: '0.725rem', color: '#cbd5e1', lineHeight: 1.45 }}>
                  Transit route paths currently egressing through Gi0/24 encompass key European destination prefixes (AS1299, AS2350). Active traffic shifting to redundant physical member <strong style={{ color: '#38bdf8' }}>GigabitEthernet0/25</strong> preserves 100% of egress paths with 0 packet drops if drained gracefully.
                </p>
              </div>
            </div>
          </div>

          {/* 4. Correlated Evidence Signals */}
          <div className="noc-card">
            <div className="noc-card-header">
              <div className="noc-card-title">
                <Terminal size={13} style={{ color: '#38bdf8' }} />
                Correlated Evidence Signals
              </div>
              <span style={{ fontSize: '0.625rem', fontFamily: 'var(--font-mono)', color: '#64748b' }}>
                4 HIGH-PRIORITY ARTIFACTS
              </span>
            </div>

            <div className="noc-table-wrapper">
              <table className="noc-table">
                <thead>
                  <tr>
                    <th>TIMESTAMP (UTC)</th>
                    <th>METRIC / TELEMETRY KEY</th>
                    <th>OBSERVED VALUE</th>
                    <th>NOMINAL THRESHOLD</th>
                    <th>SIGNAL ORIGIN</th>
                    <th>STATE</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    { time: '14:32:08.112', key: 'ifOutDiscards', val: '18,420 pkts/s', nom: '< 50 pkts/s', origin: 'SNMP Trap', state: 'CRIT' },
                    { time: '14:32:08.150', key: 'optRxPower', val: '-19.2 dBm', nom: '> -11.0 dBm', origin: 'DOM Telemetry', state: 'CRIT' },
                    { time: '14:32:08.340', key: 'BGP_NBR_HOLDTIME', val: '400ms (Timer: 6s)', nom: 'Keepalive drop', origin: 'Syslog Event', state: 'WARN' },
                    { time: '14:32:08.922', key: 'PING_PROBE_RTT', val: '412ms (34% loss)', nom: '< 9% loss', origin: 'Active Probe', state: 'CRIT' },
                  ].map((row, idx) => (
                    <tr key={idx}>
                      <td style={{ fontFamily: 'var(--font-mono)', color: '#94a3b8' }}>{row.time}</td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: '#38bdf8' }}>{row.key}</td>
                      <td style={{ fontFamily: 'var(--font-mono)', color: '#f43f5e', fontWeight: 700 }}>{row.val}</td>
                      <td style={{ fontFamily: 'var(--font-mono)', color: '#64748b' }}>{row.nom}</td>
                      <td>{row.origin}</td>
                      <td>
                        <span className={`noc-badge ${row.state === 'CRIT' ? 'noc-badge-crit' : 'noc-badge-high'}`}>
                          ● {row.state}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: Remediation Plan & Agent Execution Trace */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Remediation Plan */}
          <div className="noc-card">
            <div className="noc-card-header">
              <div className="noc-card-title">
                <Shield size={13} style={{ color: '#10b981' }} />
                Remediation Plan
              </div>
              <span className="noc-badge noc-badge-ok">READY</span>
            </div>

            <div style={{ padding: '0.9rem' }}>
              <p style={{ fontSize: '0.725rem', color: '#94a3b8', marginBottom: '0.75rem' }}>
                Plan generated by Remediation Agent v2.2. Sequential execution ensures zero-packet-drop transit failover.
              </p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                <div style={{ padding: '0.65rem', backgroundColor: '#0c0f15', border: '1px solid #1a2230', borderRadius: '3px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', marginBottom: '0.2rem' }}>
                    <span style={{ padding: '0.05rem 0.35rem', backgroundColor: '#38bdf8', color: '#000', fontSize: '0.625rem', fontFamily: 'var(--font-mono)', fontWeight: 700, borderRadius: '2px' }}>
                      1
                    </span>
                    <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#f1f5f9' }}>Graceful BGP Drain</span>
                  </div>
                  <div style={{ fontSize: '0.6875rem', color: '#94a3b8' }}>
                    Apply BGP Community <strong style={{ color: '#38bdf8' }}>65001:0</strong> (graceful-shutdown) to peer 62.115.148.1 to depress MED.
                  </div>
                </div>

                <div style={{ padding: '0.65rem', backgroundColor: '#0c0f15', border: '1px solid #1a2230', borderRadius: '3px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', marginBottom: '0.2rem' }}>
                    <span style={{ padding: '0.05rem 0.35rem', backgroundColor: '#38bdf8', color: '#000', fontSize: '0.625rem', fontFamily: 'var(--font-mono)', fontWeight: 700, borderRadius: '2px' }}>
                      2
                    </span>
                    <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#f1f5f9' }}>Dynamic Traffic Shift</span>
                  </div>
                  <div style={{ fontSize: '0.6875rem', color: '#94a3b8' }}>
                    Shift all egress transit flow over backup link <strong style={{ color: '#38bdf8' }}>GigabitEthernet0/25</strong>.
                  </div>
                </div>

                <div style={{ padding: '0.65rem', backgroundColor: '#0c0f15', border: '1px solid #1a2230', borderRadius: '3px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', marginBottom: '0.2rem' }}>
                    <span style={{ padding: '0.05rem 0.35rem', backgroundColor: '#38bdf8', color: '#000', fontSize: '0.625rem', fontFamily: 'var(--font-mono)', fontWeight: 700, borderRadius: '2px' }}>
                      3
                    </span>
                    <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#f1f5f9' }}>Optic Reset & Calibration</span>
                  </div>
                  <div style={{ fontSize: '0.6875rem', color: '#94a3b8' }}>
                    Execute interface admin-down on Gi0/24, trigger laser recalibration cycle, and monitor DOM.
                  </div>
                </div>
              </div>

              {/* CLI Payload Preview */}
              <div style={{ marginTop: '0.85rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
                  <span style={{ fontSize: '0.625rem', fontFamily: 'var(--font-mono)', color: '#64748b', fontWeight: 700 }}>
                    STAGED CLI PAYLOAD PREVIEW
                  </span>
                  <button
                    onClick={copyCliPayload}
                    className="noc-btn noc-btn-outline"
                    style={{ height: '20px', padding: '0 0.45rem', fontSize: '0.5625rem' }}
                  >
                    {copiedPayload ? <Check size={10} /> : <Copy size={10} />}
                    {copiedPayload ? 'Copied' : 'Copy'}
                  </button>
                </div>
                <pre
                  style={{
                    padding: '0.65rem',
                    backgroundColor: '#090c10',
                    border: '1px solid #1a2230',
                    borderRadius: '3px',
                    fontFamily: 'var(--font-mono)',
                    fontSize: '0.6875rem',
                    color: '#38bdf8',
                    overflowX: 'auto',
                  }}
                >
                  {cliPayload}
                </pre>
              </div>

              <div style={{ marginTop: '0.85rem' }}>
                <button
                  onClick={() => handleAction(true)}
                  disabled={isApproving || approvalStatus === 'approved'}
                  className="noc-btn noc-btn-primary"
                  style={{ width: '100%', height: '32px' }}
                >
                  <Play size={13} />
                  {approvalStatus === 'approved' ? 'Payload Dispatched' : 'Approve & Dispatch Payload'}
                </button>
              </div>
            </div>
          </div>

          {/* Agent Execution Trace */}
          <div className="noc-card">
            <div className="noc-card-header">
              <div className="noc-card-title">
                <Activity size={13} style={{ color: '#38bdf8' }} />
                Agent Execution Trace
              </div>
              <span style={{ fontSize: '0.625rem', color: '#10b981', fontFamily: 'var(--font-mono)' }}>6 NODES</span>
            </div>

            <div
              style={{
                padding: '0.85rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.65rem',
                backgroundColor: '#090c10',
              }}
            >
              {[
                {
                  agent: 'Detection Agent',
                  time: '14:32:08',
                  desc: 'Identified abnormal packet loss spike (34.2%) via sliding time-series threshold anomaly.',
                },
                {
                  agent: 'Triage Agent',
                  time: '14:32:09',
                  desc: 'Classified incident as Physical Layer Optical Transit Degradation (P=0.942).',
                },
                {
                  agent: 'Retriever Agent',
                  time: '14:32:09',
                  desc: 'Matched runbook RB-OPT-SFP-DRAIN-AND-CYCLE and hardware vendor errata.',
                },
                {
                  agent: 'RCA Agent',
                  time: '14:32:10',
                  desc: 'Correlated optical Rx power plunge (-19.2 dBm) with buffer discards and transit route table.',
                },
                {
                  agent: 'Remediation Agent',
                  time: '14:32:11',
                  desc: 'Synthesized 3-step zero-drop BGP drain and interface recalibration sequence.',
                },
                {
                  agent: 'Approval Agent',
                  time: '14:32:12',
                  desc: 'Staged execution plan; locked automated execution pending human engineer signature.',
                },
              ].map((step, idx) => (
                <div
                  key={step.agent}
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '0.65rem',
                    borderBottom: idx < 5 ? '1px solid #141a24' : 'none',
                    paddingBottom: '0.55rem',
                  }}
                >
                  <div
                    style={{
                      width: '7px',
                      height: '7px',
                      borderRadius: '50%',
                      backgroundColor: idx === 5 ? '#f59e0b' : '#10b981',
                      marginTop: '4px',
                      flexShrink: 0,
                    }}
                  />
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#f1f5f9' }}>
                        {step.agent}
                      </span>
                      <span style={{ fontSize: '0.625rem', fontFamily: 'var(--font-mono)', color: '#64748b' }}>
                        {step.time}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.6875rem', color: '#94a3b8', marginTop: '2px', lineHeight: 1.35 }}>
                      {step.desc}
                    </div>
                  </div>
                </div>
              ))}

              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  paddingTop: '0.45rem',
                  borderTop: '1px solid #141a24',
                  fontSize: '0.625rem',
                  color: '#64748b',
                  fontFamily: 'var(--font-mono)',
                }}
              >
                <span>Audit Hash: 0x9b4a...c71c</span>
                <span style={{ color: '#38bdf8', cursor: 'pointer' }}>View Ledger</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
