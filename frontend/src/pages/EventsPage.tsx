import React, { useState } from 'react';
import {
  Activity,
  AlertTriangle,
  ArrowDown,
  Check,
  Copy,
  Download,
  Filter,
  Layers,
  Pause,
  Play,
  Radio,
  Search,
  Server,
  Terminal,
  Zap,
} from 'lucide-react';
import { TelemetryEvent } from '../types';

interface EventsPageProps {
  events: TelemetryEvent[];
  onInject: () => void;
}

export const EventsPage: React.FC<EventsPageProps> = ({ events, onInject }) => {
  const [selectedSev, setSelectedSev] = useState<string>('ALL');
  const [filterQuery, setFilterQuery] = useState('');
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [isPaused, setIsPaused] = useState(false);

  // Fallback realistic stream if events list is empty
  const mockEvents: TelemetryEvent[] = [
    {
      event_id: 'EVT-081042',
      ts: '14:32:08.924',
      host: 'Router R-204',
      source_ip: '10.240.4.1',
      protocol: 'DOM',
      severity: 'CRITICAL',
      dmesg_tail: 'optRxPower below threshold on Gi0/24: -19.2 dBm (Alarm: -17.0)',
      correlated_incident: 'INC-2048',
      status: 'Triaged',
      ifaces: { eth0: { rx_bytes: 421000, errin: 18, errout: 34, mtu: 1500 } },
    },
    {
      event_id: 'EVT-081040',
      ts: '14:32:08.430',
      host: 'Router R-204',
      source_ip: '10.240.4.1',
      protocol: 'SNMP',
      severity: 'CRITICAL',
      dmesg_tail: 'ifOutDiscards counter spike: 18,420 pkts/sec on Gi0/24',
      correlated_incident: 'INC-2048',
      status: 'Triaged',
      ifaces: { eth0: { rx_bytes: 520000, errin: 0, errout: 85, mtu: 1500 } },
    },
    {
      event_id: 'EVT-081038',
      ts: '14:32:08.010',
      host: 'Router R-204',
      source_ip: '10.240.4.1',
      protocol: 'SYSLOG',
      severity: 'HIGH',
      dmesg_tail: '%LINK-3-UPDOWN: Interface Gi0/24 changed state to down',
      correlated_incident: 'INC-2048',
      status: 'Triaged',
    },
    {
      event_id: 'EVT-081039',
      ts: '14:32:07.612',
      host: 'Switch S-118',
      source_ip: '10.240.2.14',
      protocol: 'NETFLOW',
      severity: 'HIGH',
      dmesg_tail: 'Ingress rate 9.8 Gbps on 10G port Te1/0/12 exceeds 95% threshold',
      correlated_incident: 'INC-2045',
      status: 'Triaged',
    },
    {
      event_id: 'EVT-081036',
      ts: '14:32:06.194',
      host: 'DNS-03',
      source_ip: '10.240.12.8',
      protocol: 'TELEMETRY',
      severity: 'MEDIUM',
      dmesg_tail: 'Recursive resolution p99 latency 142ms exceeds 25ms SLA',
      correlated_incident: 'INC-2041',
      status: 'Triaged',
    },
    {
      event_id: 'EVT-081037',
      ts: '14:32:04.901',
      host: 'SW-CORE-01',
      source_ip: '10.240.0.254',
      protocol: 'BGP',
      severity: 'INFO',
      dmesg_tail: 'BGP-4 neighbor 192.0.2.1 keepalive received (HoldTimer reset)',
      status: 'Ingested',
    },
    {
      event_id: 'EVT-081034',
      ts: '14:32:03.210',
      host: 'Router R-204',
      source_ip: '10.240.4.1',
      protocol: 'SNMP',
      severity: 'HIGH',
      dmesg_tail: 'CRC alignment error burst detected: +842 frames on Gi0/24',
      correlated_incident: 'INC-2048',
      status: 'Triaged',
    },
  ];

  const displayEvents = events.length > 0 ? events : mockEvents;

  const filtered = displayEvents.filter((e) => {
    if (selectedSev !== 'ALL') {
      const sev = e.severity || ((e.rdma?.qp_errors || 0) > 0 ? 'CRITICAL' : 'INFO');
      if (sev !== selectedSev) return false;
    }
    if (filterQuery) {
      const q = filterQuery.toLowerCase();
      const txt = `${e.event_id} ${e.host} ${e.dmesg_tail} ${e.source_ip || ''}`.toLowerCase();
      if (!txt.includes(q)) return false;
    }
    return true;
  });

  const selectedEvent =
    displayEvents.find((e) => e.event_id === selectedEventId) || displayEvents[0] || mockEvents[0];

  const handleCopyJson = () => {
    navigator.clipboard.writeText(JSON.stringify(selectedEvent, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Page Title & Streaming Controls */}
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
            INGRESS TELEMETRY BUFFER • Kafka Cluster: active-green
          </div>
          <h1 style={{ fontSize: '1.45rem', fontWeight: 800, letterSpacing: '-0.02em', color: '#f8fafc' }}>
            Telemetry & Network Events
          </h1>
          <p style={{ fontSize: '0.775rem', color: '#94a3b8', marginTop: '0.2rem' }}>
            Live raw & processed event stream across backbone routers, switches, optical transponders, and DNS resolvers.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
          {/* Buffer Headroom Pill */}
          <div
            style={{
              padding: '0.35rem 0.65rem',
              backgroundColor: '#0c0f15',
              border: '1px solid #1e2634',
              borderRadius: '3px',
              display: 'flex',
              alignItems: 'center',
              gap: '0.65rem',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.6875rem',
            }}
          >
            <div>
              <div style={{ fontSize: '0.5625rem', color: '#64748b' }}>BUFFER HEADROOM</div>
              <div style={{ fontWeight: 700, color: '#38bdf8' }}>79.47% AVAIL</div>
            </div>
            {/* Mini sparkline */}
            <svg width="45" height="18" viewBox="0 0 45 18">
              <path d="M 0,14 Q 15,12 25,6 T 45,8" fill="none" stroke="#38bdf8" strokeWidth="1.5" />
            </svg>
          </div>

          <button
            onClick={() => setIsPaused(!isPaused)}
            className="noc-btn noc-btn-outline"
            style={{ height: '32px' }}
          >
            {isPaused ? <Play size={12} /> : <Pause size={12} />}
            {isPaused ? 'Resume Feed' : 'Pause Feed'}
          </button>
          <button onClick={onInject} className="noc-btn noc-btn-cyan-outline" style={{ height: '32px' }}>
            <Zap size={12} />
            Inject Mock Event
          </button>
        </div>
      </div>

      {/* Filter Toolbar matching Stitch */}
      <div
        className="noc-card"
        style={{
          padding: '0.75rem 1rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '0.75rem',
        }}
      >
        {/* Severity Chips */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          {[
            { id: 'ALL', label: 'All 14.8k', color: '#38bdf8' },
            { id: 'CRITICAL', label: 'CRITICAL 14', color: '#f43f5e' },
            { id: 'HIGH', label: 'HIGH 32', color: '#f59e0b' },
            { id: 'MEDIUM', label: 'MEDIUM 148', color: '#38bdf8' },
            { id: 'INFO', label: 'INFO 14.5k', color: '#94a3b8' },
          ].map((chip) => (
            <button
              key={chip.id}
              onClick={() => setSelectedSev(chip.id)}
              style={{
                padding: '0.25rem 0.65rem',
                fontSize: '0.6875rem',
                fontFamily: 'var(--font-mono)',
                fontWeight: 600,
                borderRadius: '3px',
                border: '1px solid',
                borderColor: selectedSev === chip.id ? chip.color : '#1e2430',
                backgroundColor: selectedSev === chip.id ? 'rgba(56, 189, 248, 0.12)' : '#10141b',
                color: selectedSev === chip.id ? chip.color : '#64748b',
                cursor: 'pointer',
              }}
            >
              {chip.label}
            </button>
          ))}
        </div>

        {/* Search Filter Input */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flex: 1, maxWidth: '460px' }}>
          <div style={{ position: 'relative', width: '100%' }}>
            <Filter
              size={12}
              style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: '#64748b' }}
            />
            <input
              type="text"
              className="noc-input"
              value={filterQuery}
              onChange={(e) => setFilterQuery(e.target.value)}
              placeholder="Filter regex, IP (e.g. 10.240.4.1), interface (Gi0/24), or event ID..."
              style={{ width: '100%', paddingLeft: '28px', height: '28px', fontSize: '0.75rem' }}
            />
          </div>
        </div>

        <div style={{ fontSize: '0.6875rem', color: '#64748b', fontFamily: 'var(--font-mono)' }}>
          Window: Last 15 min (Real-time)
        </div>
      </div>

      {/* Main Events Table */}
      <div className="noc-card">
        <div className="noc-table-wrapper" style={{ maxHeight: '380px' }}>
          <table className="noc-table">
            <thead>
              <tr>
                <th style={{ width: '90px' }}>TIMESTAMP</th>
                <th style={{ width: '95px' }}>EVENT ID</th>
                <th style={{ width: '160px' }}>SOURCE / IP</th>
                <th style={{ width: '80px' }}>PROTOCOL</th>
                <th style={{ width: '75px' }}>SEVERITY</th>
                <th>MESSAGE & DIAGNOSTIC PAYLOAD</th>
                <th style={{ width: '85px' }}>INCIDENT</th>
                <th style={{ width: '75px' }}>STATUS</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((ev) => {
                const isSelected = selectedEvent.event_id === ev.event_id;
                const sev = ev.severity || ((ev.rdma?.qp_errors || 0) > 0 ? 'CRITICAL' : 'INFO');
                const isCrit = sev === 'CRITICAL';
                const isHigh = sev === 'HIGH';

                return (
                  <tr
                    key={ev.event_id}
                    onClick={() => setSelectedEventId(ev.event_id)}
                    style={{
                      cursor: 'pointer',
                      backgroundColor: isSelected ? 'rgba(56, 189, 248, 0.08)' : undefined,
                    }}
                  >
                    <td style={{ fontFamily: 'var(--font-mono)', color: '#94a3b8', fontSize: '0.725rem' }}>
                      {ev.ts ? ev.ts.slice(11, 19) : '14:32:08'}
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: '#38bdf8' }}>
                      {ev.event_id}
                    </td>
                    <td>
                      <div style={{ fontWeight: 600, color: '#f1f5f9' }}>{ev.host}</div>
                      <div style={{ fontSize: '0.65rem', color: '#64748b', fontFamily: 'var(--font-mono)' }}>
                        {ev.source_ip || '10.240.4.1'}
                      </div>
                    </td>
                    <td>
                      <span className="noc-badge noc-badge-neutral">{ev.protocol || 'SYS/DMESG'}</span>
                    </td>
                    <td>
                      <span
                        className={`noc-badge ${
                          isCrit ? 'noc-badge-crit' : isHigh ? 'noc-badge-high' : 'noc-badge-ok'
                        }`}
                      >
                        ● {sev === 'CRITICAL' ? 'CRIT' : sev}
                      </span>
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', color: '#cbd5e1', fontSize: '0.725rem' }}>
                      {ev.dmesg_tail || 'Telemetry packet counters recorded without abnormal threshold breach.'}
                    </td>
                    <td>
                      {ev.correlated_incident ? (
                        <span style={{ color: '#38bdf8', fontFamily: 'var(--font-mono)', fontWeight: 700 }}>
                          {ev.correlated_incident}
                        </span>
                      ) : (
                        <span style={{ color: '#64748b' }}>Uncorrelated</span>
                      )}
                    </td>
                    <td>
                      <span style={{ color: '#10b981', fontFamily: 'var(--font-mono)', fontSize: '0.6875rem' }}>
                        {ev.status || 'Ingested'}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Split Bottom: Event Payload Inspector & Ingestion Pipeline Topology */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '1.25rem' }}>
        {/* Left: Event Payload Inspector */}
        <div className="noc-card">
          <div className="noc-card-header">
            <div className="noc-card-title">
              <Terminal size={13} style={{ color: '#38bdf8' }} />
              Event Payload Inspector
              <span style={{ color: '#38bdf8', fontFamily: 'var(--font-mono)', fontSize: '0.6875rem' }}>
                [{selectedEvent.event_id}]
              </span>
            </div>
            <button
              onClick={handleCopyJson}
              className="noc-btn noc-btn-outline"
              style={{ height: '24px', fontSize: '0.625rem', padding: '0 0.5rem' }}
            >
              {copied ? <Check size={11} /> : <Copy size={11} />}
              {copied ? 'Copied' : 'Copy Raw JSON'}
            </button>
          </div>
          <div
            style={{
              padding: '0.85rem',
              backgroundColor: '#090c10',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.725rem',
              color: '#38bdf8',
              maxHeight: '260px',
              overflowY: 'auto',
              whiteSpace: 'pre-wrap',
            }}
          >
            {JSON.stringify(selectedEvent, null, 2)}
          </div>
        </div>

        {/* Right: Ingestion Pipeline Topology */}
        <div className="noc-card">
          <div className="noc-card-header">
            <div className="noc-card-title">
              <Layers size={13} style={{ color: '#10b981' }} />
              Ingestion Pipeline
            </div>
            <span className="noc-badge noc-badge-ok">NORMAL</span>
          </div>

          <div
            style={{
              padding: '1rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.75rem',
              backgroundColor: '#0a0d12',
            }}
          >
            {/* Step 1 */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0.55rem 0.85rem',
                backgroundColor: '#121620',
                border: '1px solid #1c2330',
                borderRadius: '3px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Server size={14} style={{ color: '#38bdf8' }} />
                <span style={{ fontWeight: 600, fontSize: '0.75rem' }}>Backbone Ingress</span>
              </div>
              <span style={{ fontFamily: 'var(--font-mono)', color: '#10b981', fontWeight: 700 }}>14,820/s</span>
            </div>

            <div style={{ textAlign: 'center', color: '#38bdf8', fontSize: '0.65rem' }}>↓</div>

            {/* Step 2 */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0.55rem 0.85rem',
                backgroundColor: '#121620',
                border: '1px solid #1c2330',
                borderRadius: '3px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Radio size={14} style={{ color: '#38bdf8' }} />
                <span style={{ fontWeight: 600, fontSize: '0.75rem' }}>Redis Stream + Kafka</span>
              </div>
              <span style={{ fontFamily: 'var(--font-mono)', color: '#94a3b8' }}>4 Partitions</span>
            </div>

            <div style={{ textAlign: 'center', color: '#38bdf8', fontSize: '0.65rem' }}>↓</div>

            {/* Step 3 */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0.55rem 0.85rem',
                backgroundColor: '#121620',
                border: '1px solid #1c2330',
                borderRadius: '3px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Zap size={14} style={{ color: '#10b981' }} />
                <span style={{ fontWeight: 600, fontSize: '0.75rem' }}>FastAPI Worker Daemon</span>
              </div>
              <span style={{ fontFamily: 'var(--font-mono)', color: '#38bdf8' }}>12ms Lag</span>
            </div>

            {/* Pipeline footer metrics */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: '0.5rem',
                paddingTop: '0.5rem',
                borderTop: '1px solid #1a2230',
              }}
            >
              <div style={{ padding: '0.4rem 0.6rem', backgroundColor: '#0e1218', borderRadius: '2px' }}>
                <div style={{ fontSize: '0.5625rem', color: '#64748b' }}>BUFFER QUEUE</div>
                <div style={{ fontFamily: 'var(--font-mono)', color: '#f1f5f9', fontWeight: 700 }}>250,000</div>
                <div style={{ fontSize: '0.5625rem', color: '#10b981' }}>0.00% loss</div>
              </div>
              <div style={{ padding: '0.4rem 0.6rem', backgroundColor: '#0e1218', borderRadius: '2px' }}>
                <div style={{ fontSize: '0.5625rem', color: '#64748b' }}>TRIAGE SLA</div>
                <div style={{ fontFamily: 'var(--font-mono)', color: '#10b981', fontWeight: 700 }}>&lt; 180 ms</div>
                <div style={{ fontSize: '0.5625rem', color: '#64748b' }}>P99 Latency</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
