import React, { useState } from 'react';
import {
  AlertOctagon,
  ArrowRight,
  CheckCircle2,
  ExternalLink,
  Filter,
  Search,
  Shield,
  ShieldAlert,
} from 'lucide-react';
import { CorrelatedIncident, Decision, PageId } from '../types';

interface IncidentsPageProps {
  decisions: Decision[];
  onNavigate: (page: PageId, incidentId?: string) => void;
}

export const IncidentsPage: React.FC<IncidentsPageProps> = ({ decisions, onNavigate }) => {
  const [filter, setFilter] = useState<string>('ALL');
  const [search, setSearch] = useState('');

  // Realistic incident fixtures
  const incidents: CorrelatedIncident[] = [
    {
      id: 'INC-2048',
      title: 'Packet Loss Spike on Core Uplink (Router R-204)',
      severity: 'CRITICAL',
      status: 'Action Req.',
      source: 'Router R-204 (10.240.4.1)',
      targetInterface: 'GigabitEthernet0/24',
      lossMetric: 'Loss: 34.2% peak (Threshold: 0.5%)',
      mlConfidence: 94,
      timestamp: '4m ago',
      detectedTime: '14:32:08 UTC',
      affectedHost: 'r-204-edge.transit.iad',
    },
    {
      id: 'INC-2045',
      title: 'Interface Saturation & Buffer Drops (Switch S-118)',
      severity: 'HIGH',
      status: 'RCA Ready',
      source: 'Switch S-118 (10.240.2.14)',
      targetInterface: 'port Tel/0/12',
      queueMetric: 'Queue depth: 98% (Taildrop burst)',
      mlConfidence: 89,
      timestamp: '10m ago',
      detectedTime: '14:26:15 UTC',
      affectedHost: 'sw-118-leaf.rack-04',
    },
    {
      id: 'INC-2041',
      title: 'DNS Recursive Latency Degraded (DNS-03)',
      severity: 'MED',
      status: 'Monitoring',
      source: 'Resolver DNS-03 (10.240.12.8)',
      targetInterface: '10.240.12.8',
      lossMetric: 'Query response 142ms vs 12ms baseline',
      mlConfidence: 81,
      timestamp: '16m ago',
      detectedTime: '14:18:50 UTC',
      affectedHost: 'dns-03.infra.internal',
    },
    {
      id: 'INC-2039',
      title: 'BGP Route Table Convergence Anomaly',
      severity: 'HIGH',
      status: 'Resolved',
      source: 'Border-GW-01 (10.240.0.1)',
      targetInterface: 'BGP Peering Session 65000',
      lossMetric: 'Flap dampened; 14 prefix updates withdrawn',
      mlConfidence: 96,
      timestamp: '45m ago',
      detectedTime: '13:48:10 UTC',
      affectedHost: 'bgw-01.transit.sjc',
    },
  ];

  // Map any backend decisions flagged for remediation
  const backendCases: CorrelatedIncident[] = decisions
    .filter((d) => d.remediate)
    .map((d, i) => ({
      id: `INC-LIVE-${i + 1}`,
      title: `Remediation Trigger: ${d.log_class || 'FAULT'} on ${d.host}`,
      severity: 'CRITICAL',
      status: 'Action Req.',
      source: d.host || 'node',
      targetInterface: d.playbook || 'remediate_mtu.yml',
      lossMetric: d.rule_reason || 'ML threshold triggered',
      mlConfidence: Math.round((d.ml_priority || 0.9) * 100),
      timestamp: 'Just now',
      detectedTime: d.ts.slice(11, 19) + ' UTC',
      affectedHost: d.host || 'node',
    }));

  const allIncidents = [...backendCases, ...incidents];

  const filtered = allIncidents.filter((inc) => {
    if (filter === 'CRITICAL' && inc.severity !== 'CRITICAL') return false;
    if (filter === 'HIGH' && inc.severity !== 'HIGH') return false;
    if (filter === 'ACTION' && inc.status !== 'Action Req.') return false;
    if (filter === 'RESOLVED' && inc.status !== 'Resolved') return false;

    if (search) {
      const q = search.toLowerCase();
      return (
        inc.id.toLowerCase().includes(q) ||
        inc.title.toLowerCase().includes(q) ||
        inc.source.toLowerCase().includes(q)
      );
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
            TOPOLOGICAL INCIDENT AGGREGATOR
          </div>
          <h1 style={{ fontSize: '1.45rem', fontWeight: 800, letterSpacing: '-0.02em', color: '#f8fafc' }}>
            Active & Historical Incidents
          </h1>
          <p style={{ fontSize: '0.775rem', color: '#94a3b8', marginTop: '0.2rem' }}>
            Correlated multi-vector anomaly cases across backbone links, switches, and application clusters.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <span className="noc-badge noc-badge-crit">{allIncidents.length} TOTAL CASES</span>
        </div>
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
            { id: 'ALL', label: `All (${allIncidents.length})` },
            { id: 'CRITICAL', label: 'Critical' },
            { id: 'HIGH', label: 'High' },
            { id: 'ACTION', label: 'Action Required' },
            { id: 'RESOLVED', label: 'Resolved' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setFilter(tab.id)}
              style={{
                padding: '0.25rem 0.6rem',
                fontSize: '0.6875rem',
                fontFamily: 'var(--font-mono)',
                borderRadius: '3px',
                border: '1px solid',
                borderColor: filter === tab.id ? '#38bdf8' : '#1e2430',
                backgroundColor: filter === tab.id ? 'rgba(56, 189, 248, 0.12)' : 'transparent',
                color: filter === tab.id ? '#38bdf8' : '#64748b',
                cursor: 'pointer',
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div style={{ position: 'relative', width: '320px' }}>
          <Search
            size={12}
            style={{ position: 'absolute', left: '9px', top: '50%', transform: 'translateY(-50%)', color: '#64748b' }}
          />
          <input
            type="text"
            className="noc-input"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search incident ID, host, title..."
            style={{ width: '100%', paddingLeft: '28px', height: '28px', fontSize: '0.75rem' }}
          />
        </div>
      </div>

      {/* Incidents Table */}
      <div className="noc-card">
        <div className="noc-table-wrapper">
          <table className="noc-table">
            <thead>
              <tr>
                <th style={{ width: '75px' }}>SEVERITY</th>
                <th style={{ width: '100px' }}>INCIDENT</th>
                <th>CONTEXT & IDENTIFIER</th>
                <th style={{ width: '180px' }}>AFFECTED HOST</th>
                <th style={{ width: '110px' }}>DETECTED</th>
                <th style={{ width: '120px' }}>STATUS</th>
                <th style={{ width: '85px' }}>CONFIDENCE</th>
                <th style={{ width: '110px', textAlign: 'right' }}>ACTION</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((inc) => {
                const isCrit = inc.severity === 'CRITICAL';
                const isHigh = inc.severity === 'HIGH';

                return (
                  <tr key={inc.id}>
                    <td>
                      <span className={`noc-badge ${isCrit ? 'noc-badge-crit' : isHigh ? 'noc-badge-high' : 'noc-badge-med'}`}>
                        ● {inc.severity}
                      </span>
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: '#38bdf8' }}>
                      {inc.id}
                    </td>
                    <td>
                      <div style={{ fontWeight: 600, color: '#f8fafc' }}>{inc.title}</div>
                      <div style={{ fontSize: '0.6875rem', color: '#94a3b8', fontFamily: 'var(--font-mono)', marginTop: '2px' }}>
                        {inc.lossMetric || inc.queueMetric}
                      </div>
                    </td>
                    <td>
                      <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: '#cbd5e1' }}>
                        {inc.affectedHost}
                      </div>
                      <div style={{ fontSize: '0.65rem', color: '#64748b' }}>{inc.source}</div>
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', color: '#94a3b8', fontSize: '0.725rem' }}>
                      {inc.detectedTime}
                    </td>
                    <td>
                      <span
                        className="noc-badge"
                        style={{
                          backgroundColor:
                            inc.status === 'Action Req.'
                              ? 'rgba(245, 158, 11, 0.15)'
                              : inc.status === 'Resolved'
                              ? 'rgba(16, 185, 129, 0.15)'
                              : 'rgba(56, 189, 248, 0.15)',
                          color:
                            inc.status === 'Action Req.'
                              ? '#f59e0b'
                              : inc.status === 'Resolved'
                              ? '#10b981'
                              : '#38bdf8',
                          borderColor:
                            inc.status === 'Action Req.'
                              ? '#f59e0b'
                              : inc.status === 'Resolved'
                              ? '#10b981'
                              : '#38bdf8',
                        }}
                      >
                        {inc.status}
                      </span>
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: inc.mlConfidence > 90 ? '#10b981' : '#38bdf8' }}>
                      {inc.mlConfidence}%
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <button
                        onClick={() => onNavigate('incident-detail', inc.id)}
                        className="noc-btn noc-btn-cyan-outline"
                        style={{ padding: '0.25rem 0.65rem', fontSize: '0.6875rem' }}
                      >
                        Investigate
                        <ExternalLink size={10} />
                      </button>
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
