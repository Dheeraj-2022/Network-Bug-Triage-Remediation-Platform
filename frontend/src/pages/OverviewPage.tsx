import React, { useState } from 'react';
import {
  Activity,
  AlertOctagon,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Clock,
  Cpu,
  Database,
  ExternalLink,
  Filter,
  HardDrive,
  Layers,
  Radio,
  Server,
  Shield,
  ShieldAlert,
  Sliders,
  Terminal,
  Zap,
} from 'lucide-react';
import { CorrelatedIncident, Decision, PageId, SystemStatus, TelemetryEvent } from '../types';

interface OverviewPageProps {
  status: SystemStatus | null;
  events: TelemetryEvent[];
  decisions: Decision[];
  onNavigate: (page: PageId, incidentId?: string) => void;
  onInject: () => void;
  onLoadSamples: () => void;
}

export const OverviewPage: React.FC<OverviewPageProps> = ({
  status,
  events,
  decisions,
  onNavigate,
  onInject,
  onLoadSamples,
}) => {
  const [filterTab, setFilterTab] = useState<'all' | 'critical' | 'investigating' | 'rca'>('all');
  const [sortOrder, setSortOrder] = useState<'sev_desc' | 'time_desc'>('sev_desc');

  // Correlated incidents dataset matching the Stitch reference
  const baseIncidents: CorrelatedIncident[] = [
    {
      id: 'INC-2048',
      title: 'Packet Loss Spike on Core Uplink',
      severity: 'CRITICAL',
      status: 'Investigating',
      source: 'Router R-204',
      targetInterface: 'GigabitEthernet0/24',
      lossMetric: 'Loss: 18.4% (Threshold: 0.5%)',
      mlConfidence: 94,
      timestamp: '2m ago',
      detectedTime: '14:32:08 UTC',
      affectedHost: 'r-204-edge.transit.iad',
    },
    {
      id: 'INC-2045',
      title: 'Interface Saturation & Buffer Drops',
      severity: 'HIGH',
      status: 'RCA Ready',
      source: 'Switch S-118',
      targetInterface: 'port Tel/0/12',
      queueMetric: 'Queue depth: 98% (Taildrop burst)',
      mlConfidence: 89,
      timestamp: '8m ago',
      detectedTime: '14:26:15 UTC',
      affectedHost: 'sw-118-leaf.rack-04',
    },
    {
      id: 'INC-2041',
      title: 'DNS Recursive Latency Degraded',
      severity: 'MED',
      status: 'Monitoring',
      source: 'Resolver DNS-03',
      targetInterface: '10.240.12.8',
      lossMetric: 'Query response 142ms vs 12ms baseline',
      mlConfidence: 81,
      timestamp: '14m ago',
      detectedTime: '14:18:50 UTC',
      affectedHost: 'dns-03.infra.internal',
    },
  ];

  // Augment with recent backend decisions that triggered remediations
  const backendIncidents: CorrelatedIncident[] = decisions
    .filter((d) => d.remediate)
    .slice(-3)
    .map((d, idx) => ({
      id: `INC-LIVE-${idx + 101}`,
      title: `${d.log_class || 'HARDWARE_ANOMALY'} on ${d.host || 'node'}`,
      severity: d.rule_action === 'remediate' ? 'CRITICAL' : 'HIGH',
      status: 'Action Req.',
      source: d.host || 'host',
      targetInterface: d.playbook ? `Playbook: ${d.playbook}` : 'eth0',
      lossMetric: `Rule: ${d.rule_reason || 'Threshold breach'}`,
      mlConfidence: Math.round((d.ml_priority || 0.85) * 100),
      timestamp: 'Just now',
      detectedTime: d.ts.slice(11, 19) + ' UTC',
      affectedHost: d.host || 'node',
    }));

  const allIncidents = [...backendIncidents, ...baseIncidents];

  const filteredIncidents = allIncidents.filter((inc) => {
    if (filterTab === 'critical') return inc.severity === 'CRITICAL';
    if (filterTab === 'investigating') return inc.status === 'Investigating';
    if (filterTab === 'rca') return inc.status === 'RCA Ready';
    return true;
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Hero Header matching Stitch */}
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
              letterSpacing: '0.06em',
              fontWeight: 600,
              marginBottom: '0.4rem',
            }}
          >
            <Server size={11} />
            AUTONOMOUS NOC FABRIC / CLUSTER_ID #US-E1-ALPHA
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.75rem' }}>
            <h1 style={{ fontSize: '1.45rem', fontWeight: 800, letterSpacing: '-0.02em', color: '#f8fafc' }}>
              Network Triage
            </h1>
            <span style={{ fontSize: '0.875rem', fontWeight: 600, color: '#10b981', fontFamily: 'var(--font-mono)' }}>
              Detect. Diagnose. Resolve.
            </span>
          </div>
          <p style={{ fontSize: '0.775rem', color: '#94a3b8', marginTop: '0.2rem', maxWidth: '780px' }}>
            Real-time telemetry ingestion, topological root-cause correlation, and human-in-the-loop automated remediation orchestrator.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <button onClick={onLoadSamples} className="noc-btn noc-btn-outline" style={{ height: '30px' }}>
            <Database size={12} />
            Load Sample Events
          </button>
          <button onClick={onInject} className="noc-btn noc-btn-cyan-outline" style={{ height: '30px' }}>
            <Zap size={12} />
            Inject Telemetry Event
          </button>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              padding: '0.35rem 0.65rem',
              backgroundColor: '#0f141c',
              border: '1px solid #1e2634',
              borderRadius: '3px',
              fontSize: '0.6875rem',
              fontFamily: 'var(--font-mono)',
              color: '#10b981',
            }}
          >
            <span className="status-pulse-dot pulse-green" />
            Live Stream: Active 14.8k/s
          </div>
        </div>
      </div>

      {/* TRIAGE PIPELINE EXECUTION PLANE */}
      <div className="noc-card">
        <div className="noc-card-header">
          <div className="noc-card-title">
            <Layers size={13} style={{ color: '#38bdf8' }} />
            TRIAGE PIPELINE EXECUTION PLANE
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', fontSize: '0.6875rem', fontFamily: 'var(--font-mono)' }}>
            <span style={{ color: '#64748b' }}>PIPELINE LATENCY: <strong style={{ color: '#38bdf8' }}>16.4ms</strong></span>
            <span style={{ color: '#10b981', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
              <span className="status-pulse-dot pulse-green" />
              STATUS: SYNCHRONIZED
            </span>
          </div>
        </div>

        <div
          style={{
            padding: '1rem 1.25rem',
            display: 'grid',
            gridTemplateColumns: 'repeat(5, 1fr)',
            gap: '0.75rem',
            backgroundColor: '#0c0f15',
          }}
        >
          {/* Stage 1 */}
          <div style={{ padding: '0.75rem', backgroundColor: '#11151e', border: '1px solid #1a2230', borderRadius: '3px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
              <span style={{ fontSize: '0.625rem', fontFamily: 'var(--font-mono)', color: '#38bdf8', fontWeight: 700 }}>
                01 // TELEMETRY
              </span>
              <span style={{ fontSize: '0.625rem', color: '#64748b', fontFamily: 'var(--font-mono)' }}>P99: 4.2ms</span>
            </div>
            <div style={{ fontSize: '1.15rem', fontWeight: 800, color: '#f1f5f9', fontFamily: 'var(--font-mono)' }}>
              14,820 <span style={{ fontSize: '0.6875rem', color: '#64748b', fontWeight: 400 }}>eps</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '0.35rem', fontSize: '0.625rem' }}>
              <span style={{ color: '#94a3b8' }}>Ingress Flow</span>
              <span style={{ color: '#10b981', fontWeight: 600 }}>Normal</span>
            </div>
          </div>

          {/* Stage 2 */}
          <div style={{ padding: '0.75rem', backgroundColor: '#11151e', border: '1px solid #1a2230', borderRadius: '3px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
              <span style={{ fontSize: '0.625rem', fontFamily: 'var(--font-mono)', color: '#38bdf8', fontWeight: 700 }}>
                02 // DETECTION
              </span>
              <span style={{ fontSize: '0.625rem', color: '#f59e0b', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>18 Alerting</span>
            </div>
            <div style={{ fontSize: '1rem', fontWeight: 700, color: '#f1f5f9', whiteSpace: 'nowrap' }}>
              Rules + Anomaly
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '0.35rem', fontSize: '0.625rem' }}>
              <span style={{ color: '#94a3b8' }}>Evaluators</span>
              <span style={{ color: '#38bdf8', fontFamily: 'var(--font-mono)' }}>142 Active</span>
            </div>
          </div>

          {/* Stage 3 */}
          <div style={{ padding: '0.75rem', backgroundColor: '#11151e', border: '1px solid #1a2230', borderRadius: '3px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
              <span style={{ fontSize: '0.625rem', fontFamily: 'var(--font-mono)', color: '#38bdf8', fontWeight: 700 }}>
                03 // TRIAGE
              </span>
              <span style={{ fontSize: '0.625rem', color: '#f43f5e', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>3 Active</span>
            </div>
            <div style={{ fontSize: '1rem', fontWeight: 700, color: '#f1f5f9', whiteSpace: 'nowrap' }}>
              ML + NLP Sorter
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '0.35rem', fontSize: '0.625rem' }}>
              <span style={{ color: '#94a3b8' }}>Correlation</span>
              <span style={{ color: '#10b981', fontFamily: 'var(--font-mono)' }}>100% Synced</span>
            </div>
          </div>

          {/* Stage 4 */}
          <div style={{ padding: '0.75rem', backgroundColor: '#11151e', border: '1px solid #1a2230', borderRadius: '3px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
              <span style={{ fontSize: '0.625rem', fontFamily: 'var(--font-mono)', color: '#38bdf8', fontWeight: 700 }}>
                04 // ROOT CAUSE
              </span>
              <span style={{ fontSize: '0.625rem', color: '#10b981', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>2 Diagnosed</span>
            </div>
            <div style={{ fontSize: '1rem', fontWeight: 700, color: '#f1f5f9', whiteSpace: 'nowrap' }}>
              Topo Graph RCA
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '0.35rem', fontSize: '0.625rem' }}>
              <span style={{ color: '#94a3b8' }}>Avg Confidence</span>
              <span style={{ color: '#38bdf8', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>91.5%</span>
            </div>
          </div>

          {/* Stage 5 */}
          <div style={{ padding: '0.75rem', backgroundColor: '#11151e', border: '1px solid #1a2230', borderRadius: '3px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
              <span style={{ fontSize: '0.625rem', fontFamily: 'var(--font-mono)', color: '#38bdf8', fontWeight: 700 }}>
                05 // REMEDIATION
              </span>
              <span style={{ fontSize: '0.625rem', color: '#f59e0b', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>1 Run / 2 Hold</span>
            </div>
            <div style={{ fontSize: '1rem', fontWeight: 700, color: '#f1f5f9', whiteSpace: 'nowrap' }}>
              Ansible Automation
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '0.35rem', fontSize: '0.625rem' }}>
              <span style={{ color: '#94a3b8' }}>Guardrail</span>
              <span style={{ color: '#38bdf8', fontFamily: 'var(--font-mono)', fontWeight: 700 }}>HITL Active</span>
            </div>
          </div>
        </div>
      </div>

      {/* COMPACT KPI CARDS ROW */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '0.75rem' }}>
        {/* Card 1: Active Incidents */}
        <div className="noc-card" style={{ padding: '0.9rem', borderColor: '#261b24' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <span style={{ fontSize: '0.6875rem', fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Active Incidents
            </span>
            <AlertOctagon size={14} style={{ color: '#f43f5e' }} />
          </div>
          <div style={{ fontSize: '1.65rem', fontWeight: 800, color: '#f43f5e', fontFamily: 'var(--font-mono)', margin: '0.2rem 0' }}>
            {allIncidents.length}
            <span style={{ fontSize: '0.6875rem', color: '#94a3b8', fontWeight: 500, marginLeft: '0.4rem' }}>
              2 Crit • 1 High
            </span>
          </div>
          <div style={{ fontSize: '0.6875rem', color: '#64748b' }}>Total unmitigated events</div>
        </div>

        {/* Card 2: Events Received */}
        <div className="noc-card" style={{ padding: '0.9rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <span style={{ fontSize: '0.6875rem', fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Events Received (1H)
            </span>
            <Activity size={14} style={{ color: '#10b981' }} />
          </div>
          <div style={{ fontSize: '1.65rem', fontWeight: 800, color: '#f1f5f9', fontFamily: 'var(--font-mono)', margin: '0.2rem 0' }}>
            {status?.total_events ? `${status.total_events + 1429810}` : '1,429,810'}
            <span style={{ fontSize: '0.6875rem', color: '#10b981', fontWeight: 600, marginLeft: '0.4rem' }}>+4.2%</span>
          </div>
          <div style={{ fontSize: '0.6875rem', color: '#64748b' }}>Avg ingress 397/s</div>
        </div>

        {/* Card 3: Critical Hardware */}
        <div className="noc-card" style={{ padding: '0.9rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <span style={{ fontSize: '0.6875rem', fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Critical Hardware
            </span>
            <Server size={14} style={{ color: '#f59e0b' }} />
          </div>
          <div style={{ fontSize: '1.65rem', fontWeight: 800, color: '#f59e0b', fontFamily: 'var(--font-mono)', margin: '0.2rem 0' }}>
            2 <span style={{ fontSize: '0.75rem', color: '#94a3b8', fontWeight: 400 }}>Affected</span>
          </div>
          <div style={{ fontSize: '0.6875rem', color: '#64748b' }}>Router R-204, Switch S-118</div>
        </div>

        {/* Card 4: Pending Approval */}
        <div className="noc-card" style={{ padding: '0.9rem', borderColor: '#2b2316' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <span style={{ fontSize: '0.6875rem', fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Pending Approval
            </span>
            <ShieldAlert size={14} style={{ color: '#f59e0b' }} />
          </div>
          <div style={{ fontSize: '1.65rem', fontWeight: 800, color: '#f59e0b', fontFamily: 'var(--font-mono)', margin: '0.2rem 0' }}>
            2 <span style={{ fontSize: '0.75rem', color: '#94a3b8', fontWeight: 400 }}>Action Req.</span>
          </div>
          <div style={{ fontSize: '0.6875rem', color: '#64748b' }}>Gi0/24 reset, BGP drain</div>
        </div>

        {/* Card 5: Resolved Today */}
        <div className="noc-card" style={{ padding: '0.9rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <span style={{ fontSize: '0.6875rem', fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Resolved Today
            </span>
            <CheckCircle2 size={14} style={{ color: '#10b981' }} />
          </div>
          <div style={{ fontSize: '1.65rem', fontWeight: 800, color: '#10b981', fontFamily: 'var(--font-mono)', margin: '0.2rem 0' }}>
            47 <span style={{ fontSize: '0.6875rem', color: '#64748b', fontWeight: 400 }}>MTTR: 3.4m</span>
          </div>
          <div style={{ fontSize: '0.6875rem', color: '#64748b' }}>98.2% automated closure</div>
        </div>
      </div>

      {/* MAIN TWO-COLUMN SPLIT */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: '1.25rem' }}>
        {/* LEFT COLUMN: Active Correlated Incidents & Sparkline */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div className="noc-card">
            {/* Table Header & Controls */}
            <div className="noc-card-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <span className="noc-card-title">
                  <AlertOctagon size={14} style={{ color: '#f43f5e' }} />
                  Active Correlated Incidents
                </span>
                <span className="noc-badge noc-badge-crit">{allIncidents.length} Active</span>
              </div>

              {/* Filter Tabs */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                {(['all', 'critical', 'investigating', 'rca'] as const).map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setFilterTab(tab)}
                    style={{
                      padding: '0.2rem 0.55rem',
                      fontSize: '0.6875rem',
                      fontFamily: 'var(--font-mono)',
                      borderRadius: '2px',
                      border: '1px solid',
                      borderColor: filterTab === tab ? '#38bdf8' : '#1e2430',
                      backgroundColor: filterTab === tab ? 'rgba(56, 189, 248, 0.12)' : 'transparent',
                      color: filterTab === tab ? '#38bdf8' : '#64748b',
                      cursor: 'pointer',
                      textTransform: 'capitalize',
                    }}
                  >
                    {tab === 'all' ? `All (${allIncidents.length})` : tab === 'critical' ? 'Critical (2)' : tab === 'investigating' ? 'Investigating (1)' : 'RCA Ready (2)'}
                  </button>
                ))}
              </div>
            </div>

            {/* Incidents Table */}
            <div className="noc-table-wrapper">
              <table className="noc-table">
                <thead>
                  <tr>
                    <th style={{ width: '65px' }}>SEV</th>
                    <th>INCIDENT IDENTIFIER & CONTEXT</th>
                    <th style={{ width: '120px' }}>STATUS</th>
                    <th style={{ width: '75px' }}>ML CONF</th>
                    <th style={{ width: '70px' }}>TIME</th>
                    <th style={{ width: '100px', textAlign: 'right' }}>ACTION</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredIncidents.map((incident) => {
                    const isCrit = incident.severity === 'CRITICAL';
                    const isHigh = incident.severity === 'HIGH';

                    return (
                      <tr key={incident.id}>
                        <td>
                          <span
                            className={`noc-badge ${
                              isCrit ? 'noc-badge-crit' : isHigh ? 'noc-badge-high' : 'noc-badge-med'
                            }`}
                          >
                            ● {incident.severity === 'CRITICAL' ? 'CRIT' : incident.severity}
                          </span>
                        </td>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem' }}>
                            <span
                              style={{
                                fontFamily: 'var(--font-mono)',
                                fontWeight: 700,
                                color: '#38bdf8',
                                fontSize: '0.75rem',
                              }}
                            >
                              {incident.id}
                            </span>
                            <span style={{ fontWeight: 600, color: '#f1f5f9' }}>{incident.title}</span>
                          </div>
                          <div
                            style={{
                              fontSize: '0.6875rem',
                              color: '#94a3b8',
                              marginTop: '2px',
                              display: 'flex',
                              gap: '0.75rem',
                              fontFamily: 'var(--font-mono)',
                            }}
                          >
                            <span>
                              {incident.source} :: <strong style={{ color: '#cbd5e1' }}>{incident.targetInterface}</strong>
                            </span>
                            <span style={{ color: '#f59e0b' }}>
                              {incident.lossMetric || incident.queueMetric}
                            </span>
                          </div>
                        </td>
                        <td>
                          <span
                            className="noc-badge"
                            style={{
                              backgroundColor:
                                incident.status === 'Investigating'
                                  ? 'rgba(56, 189, 248, 0.12)'
                                  : incident.status === 'RCA Ready'
                                  ? 'rgba(16, 185, 129, 0.12)'
                                  : 'rgba(245, 158, 11, 0.12)',
                              color:
                                incident.status === 'Investigating'
                                  ? '#38bdf8'
                                  : incident.status === 'RCA Ready'
                                  ? '#10b981'
                                  : '#f59e0b',
                              borderColor:
                                incident.status === 'Investigating'
                                  ? 'rgba(56, 189, 248, 0.3)'
                                  : incident.status === 'RCA Ready'
                                  ? 'rgba(16, 185, 129, 0.3)'
                                  : 'rgba(245, 158, 11, 0.3)',
                            }}
                          >
                            {incident.status}
                          </span>
                        </td>
                        <td>
                          <span
                            style={{
                              fontFamily: 'var(--font-mono)',
                              fontWeight: 700,
                              color: incident.mlConfidence > 90 ? '#10b981' : '#38bdf8',
                            }}
                          >
                            {incident.mlConfidence}%
                          </span>
                        </td>
                        <td>
                          <span style={{ color: '#64748b', fontFamily: 'var(--font-mono)', fontSize: '0.6875rem' }}>
                            {incident.timestamp}
                          </span>
                        </td>
                        <td style={{ textAlign: 'right' }}>
                          <button
                            onClick={() => onNavigate('incident-detail', incident.id)}
                            className={`noc-btn ${
                              incident.id === 'INC-2048' ? 'noc-btn-primary' : 'noc-btn-outline'
                            }`}
                            style={{ padding: '0.25rem 0.6rem', fontSize: '0.6875rem' }}
                          >
                            {incident.id === 'INC-2048' ? 'Investigate' : incident.status === 'RCA Ready' ? 'Review RCA' : 'Details'}
                            <ExternalLink size={10} />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Sparkline / Anomaly Telemetry Card */}
            <div
              style={{
                padding: '0.85rem 1rem',
                borderTop: '1px solid #1c222e',
                backgroundColor: '#0c0f14',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.4rem',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span
                  style={{
                    fontSize: '0.625rem',
                    fontFamily: 'var(--font-mono)',
                    color: '#64748b',
                    fontWeight: 700,
                    letterSpacing: '0.06em',
                  }}
                >
                  AGGREGATED UPLINK ERROR BURST TELEMETRY (LAST 15M)
                </span>
                <span style={{ fontSize: '0.625rem', fontFamily: 'var(--font-mono)', color: '#38bdf8' }}>
                  Live Samples: 300
                </span>
              </div>

              {/* Realistic SVG Telemetry Sparkline */}
              <div style={{ position: 'relative', height: '64px', width: '100%', margin: '0.35rem 0' }}>
                <svg
                  viewBox="0 0 700 64"
                  preserveAspectRatio="none"
                  style={{ width: '100%', height: '100%', display: 'block' }}
                >
                  <defs>
                    <linearGradient id="telemetryGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.25" />
                      <stop offset="100%" stopColor="#38bdf8" stopOpacity="0" />
                    </linearGradient>
                  </defs>
                  {/* Subtle threshold line */}
                  <line x1="0" y1="20" x2="700" y2="20" stroke="#f43f5e" strokeWidth="1" strokeDasharray="3 3" opacity="0.4" />
                  {/* Area fill */}
                  <path
                    d="M 0,55 Q 120,53 220,56 T 380,50 T 450,28 T 510,14 T 540,16 T 600,48 T 700,52 L 700,64 L 0,64 Z"
                    fill="url(#telemetryGrad)"
                  />
                  {/* Main sparkline */}
                  <path
                    d="M 0,55 Q 120,53 220,56 T 380,50 T 450,28 T 510,14 T 540,16 T 600,48 T 700,52"
                    fill="none"
                    stroke="#38bdf8"
                    strokeWidth="2"
                  />
                  {/* Anomaly trigger circles */}
                  <circle cx="510" cy="14" r="4" fill="#f43f5e" stroke="#0b0f15" strokeWidth="2" />
                  <circle cx="540" cy="16" r="4" fill="#f43f5e" stroke="#0b0f15" strokeWidth="2" />
                </svg>
              </div>

              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  fontSize: '0.625rem',
                  color: '#64748b',
                  fontFamily: 'var(--font-mono)',
                }}
              >
                <span>T - 15m</span>
                <span style={{ color: '#f43f5e', fontWeight: 600 }}>
                  ▲ Correlated Anomaly Window: INC-2048
                </span>
                <span>NOW (T - 0s)</span>
              </div>
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: Pipeline & Engine Status */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* System Pipeline Status */}
          <div className="noc-card">
            <div className="noc-card-header">
              <div className="noc-card-title">
                <Activity size={13} style={{ color: '#10b981' }} />
                System Pipeline Status
              </div>
              <span className="noc-badge noc-badge-ok">100%</span>
            </div>

            <div style={{ padding: '0.9rem' }}>
              <div style={{ marginBottom: '0.85rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.6875rem', marginBottom: '0.35rem' }}>
                  <span style={{ color: '#94a3b8' }}>Ingress Triage Efficiency</span>
                  <span style={{ color: '#10b981', fontFamily: 'var(--font-mono)', fontWeight: 700 }}>100%</span>
                </div>
                <div style={{ height: '5px', backgroundColor: '#161d28', borderRadius: '2px', overflow: 'hidden' }}>
                  <div style={{ width: '100%', height: '100%', backgroundColor: '#10b981' }} />
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.55rem', fontSize: '0.75rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #1a2230', paddingBottom: '0.35rem' }}>
                  <span style={{ color: '#64748b' }}>Events Ingested:</span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                    {status?.total_events ? status.total_events + 1429810 : '1,429,810'}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #1a2230', paddingBottom: '0.35rem' }}>
                  <span style={{ color: '#64748b' }}>Triaged Events:</span>
                  <span style={{ fontFamily: 'var(--font-mono)', color: '#38bdf8' }}>1,429,810 (100%)</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #1a2230', paddingBottom: '0.35rem' }}>
                  <span style={{ color: '#64748b' }}>RCA Running:</span>
                  <span style={{ fontFamily: 'var(--font-mono)', color: '#10b981' }}>1 active worker</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #1a2230', paddingBottom: '0.35rem' }}>
                  <span style={{ color: '#64748b' }}>Awaiting Human Approval:</span>
                  <span style={{ fontFamily: 'var(--font-mono)', color: '#f59e0b', fontWeight: 700 }}>2 actions blocked</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '0.2rem' }}>
                  <span style={{ color: '#64748b' }}>Automatically Remediated:</span>
                  <span style={{ fontFamily: 'var(--font-mono)', color: '#94a3b8' }}>0 (Guard enforced)</span>
                </div>
              </div>

              {/* Zero-impact safety banner */}
              <div
                style={{
                  marginTop: '0.85rem',
                  padding: '0.6rem 0.75rem',
                  backgroundColor: 'rgba(56, 189, 248, 0.08)',
                  border: '1px solid rgba(56, 189, 248, 0.25)',
                  borderRadius: '3px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  fontSize: '0.6875rem',
                  color: '#94a3b8',
                }}
              >
                <Shield size={14} style={{ color: '#38bdf8', flexShrink: 0 }} />
                <span>Zero-impact safety active. All route flips require credentialed signature.</span>
              </div>
            </div>
          </div>

          {/* Model & Engine Status */}
          <div className="noc-card">
            <div className="noc-card-header">
              <div className="noc-card-title">
                <Cpu size={13} style={{ color: '#38bdf8' }} />
                Model & Engine Status
              </div>
              <span className="noc-badge noc-badge-ok">4 Online</span>
            </div>

            <div style={{ padding: '0.85rem', display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
              {/* Engine item 1 */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem' }}>
                  <span style={{ fontWeight: 600, color: '#f1f5f9' }}>● Rule Engine</span>
                  <span style={{ fontFamily: 'var(--font-mono)', color: '#10b981', fontSize: '0.6875rem' }}>0.4ms avg</span>
                </div>
                <div style={{ fontSize: '0.6875rem', color: '#64748b' }}>142 active rules • deterministic</div>
              </div>

              {/* Engine item 2 */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem' }}>
                  <span style={{ fontWeight: 600, color: '#f1f5f9' }}>● ML Model (XGBoost)</span>
                  <span style={{ fontFamily: 'var(--font-mono)', color: '#38bdf8', fontSize: '0.6875rem' }}>v3.2.1</span>
                </div>
                <div style={{ fontSize: '0.6875rem', color: '#64748b' }}>
                  {status?.model_trained ? 'Trained • 100% validation accuracy' : '94.2% validation accuracy'}
                </div>
              </div>

              {/* Engine item 3 */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem' }}>
                  <span style={{ fontWeight: 600, color: '#f1f5f9' }}>● NLP Model (MiniLM-L6)</span>
                  <span style={{ fontFamily: 'var(--font-mono)', color: '#10b981', fontSize: '0.6875rem' }}>Online</span>
                </div>
                <div style={{ fontSize: '0.6875rem', color: '#64748b' }}>NER & Syslog semantic triage</div>
              </div>

              {/* Engine item 4 */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem' }}>
                  <span style={{ fontWeight: 600, color: '#f1f5f9' }}>● LLM Multi-Agent RCA</span>
                  <span style={{ fontFamily: 'var(--font-mono)', color: '#38bdf8', fontSize: '0.6875rem' }}>18ms</span>
                </div>
                <div style={{ fontSize: '0.6875rem', color: '#64748b' }}>Gemini / Vertex AI hybrid reasoner</div>
              </div>

              {/* HITL Policy indicator */}
              <div
                style={{
                  marginTop: '0.35rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0.45rem 0.65rem',
                  backgroundColor: '#0c0f15',
                  borderRadius: '2px',
                  border: '1px solid #1c2330',
                }}
              >
                <span style={{ fontSize: '0.6875rem', color: '#94a3b8', fontWeight: 600 }}>HITL Policy:</span>
                <span className="noc-badge noc-badge-med" style={{ letterSpacing: '0.08em' }}>ENFORCED</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* BOTTOM: LIVE INGRESS EVENT STREAM */}
      <div className="noc-card">
        <div className="noc-card-header">
          <div className="noc-card-title">
            <Terminal size={13} style={{ color: '#38bdf8' }} />
            Live Ingress Event Stream
            <span style={{ color: '#64748b', fontWeight: 400, textTransform: 'none', marginLeft: '0.4rem', fontSize: '0.6875rem' }}>
              (Last 5 flagged system captures)
            </span>
          </div>
          <div style={{ fontSize: '0.6875rem', color: '#64748b', fontFamily: 'var(--font-mono)' }}>
            CHANNEL: <strong style={{ color: '#cbd5e1' }}>/dev/syslog-k8s-mesh</strong>
          </div>
        </div>

        <div
          style={{
            padding: '0.75rem 1rem',
            backgroundColor: '#080a0e',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.4rem',
            fontFamily: 'var(--font-mono)',
            fontSize: '0.725rem',
          }}
        >
          {events.length > 0 ? (
            events.slice(-5).reverse().map((ev, i) => (
              <div
                key={ev.event_id || i}
                style={{
                  display: 'flex',
                  alignItems: 'baseline',
                  justifyContent: 'space-between',
                  padding: '0.25rem 0',
                  borderBottom: i < 4 ? '1px solid #131720' : 'none',
                }}
              >
                <div style={{ display: 'flex', gap: '0.65rem' }}>
                  <span style={{ color: (ev.rdma?.qp_errors || 0) > 0 ? '#f43f5e' : '#38bdf8', fontWeight: 700 }}>
                    [{(ev.rdma?.qp_errors || 0) > 0 ? 'RDMA_ERROR' : (ev.ifaces?.eth0?.errin || 0) > 0 ? 'IFACE_DROP' : 'TELEMETRY'}]
                  </span>
                  <span style={{ color: '#64748b' }}>{ev.ts ? ev.ts.slice(11, 19) : '14:02:19'}</span>
                  <span style={{ color: '#cbd5e1' }}>
                    {ev.dmesg_tail || `Host ${ev.host} pushed telemetry payload: rx_bytes=${ev.ifaces?.eth0?.rx_bytes || 1200}`}
                  </span>
                </div>
                <div style={{ display: 'flex', gap: '0.75rem' }}>
                  <span style={{ color: '#64748b' }}>NODE: {ev.host}</span>
                  <span style={{ color: (ev.rdma?.qp_errors || 0) > 0 ? '#f43f5e' : '#10b981', fontWeight: 700 }}>
                    {(ev.rdma?.qp_errors || 0) > 0 ? 'CRITICAL' : 'OK'}
                  </span>
                </div>
              </div>
            ))
          ) : (
            <>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.2rem 0', borderBottom: '1px solid #131720' }}>
                <div style={{ display: 'flex', gap: '0.65rem' }}>
                  <span style={{ color: '#f43f5e', fontWeight: 700 }}>[BGP_FLAP]</span>
                  <span style={{ color: '#64748b' }}>14:02:19.421</span>
                  <span style={{ color: '#cbd5e1' }}>AS65001 peer 198.51.100.1 state transition ESTABLISHED -&gt; IDLE (HoldTimerExpired)</span>
                </div>
                <div style={{ display: 'flex', gap: '0.75rem' }}>
                  <span style={{ color: '#64748b' }}>NODE: core-cr-01</span>
                  <span style={{ color: '#f43f5e', fontWeight: 700 }}>CRITICAL</span>
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.2rem 0', borderBottom: '1px solid #131720' }}>
                <div style={{ display: 'flex', gap: '0.65rem' }}>
                  <span style={{ color: '#f59e0b', fontWeight: 700 }}>[CRC_ERR]</span>
                  <span style={{ color: '#64748b' }}>14:02:18.890</span>
                  <span style={{ color: '#cbd5e1' }}>Router R-204 port Gi0/24 FCS error counter incremented +842 frames/sec</span>
                </div>
                <div style={{ display: 'flex', gap: '0.75rem' }}>
                  <span style={{ color: '#64748b' }}>NODE: r-204-edge</span>
                  <span style={{ color: '#f59e0b', fontWeight: 700 }}>WARNING</span>
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.2rem 0' }}>
                <div style={{ display: 'flex', gap: '0.65rem' }}>
                  <span style={{ color: '#38bdf8', fontWeight: 700 }}>[MTU_MISMATCH]</span>
                  <span style={{ color: '#64748b' }}>14:02:15.104</span>
                  <span style={{ color: '#cbd5e1' }}>OSPF Hello dropped on VLAN-402: Packet size 1500 exceeds MTU 1492</span>
                </div>
                <div style={{ display: 'flex', gap: '0.75rem' }}>
                  <span style={{ color: '#64748b' }}>NODE: dis-sw-04</span>
                  <span style={{ color: '#38bdf8', fontWeight: 700 }}>INFO</span>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
