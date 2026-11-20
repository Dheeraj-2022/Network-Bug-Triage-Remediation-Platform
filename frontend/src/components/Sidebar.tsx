import React from 'react';
import { Activity, AlertOctagon, Cpu, FlaskConical, GitBranch, LayoutDashboard, ScrollText, Waypoints, Wrench } from 'lucide-react';
import { PageId } from '../types';
import { API_BASE_URL } from '../services/api';

export interface NavCounts {
  openIncidents: number;
  awaitingApproval: number;
  events: number;
  decisions: number;
  executions: number;
}

interface SidebarProps {
  currentPage: PageId;
  onNavigate: (page: PageId) => void;
  counts: NavCounts;
  connection: 'connecting' | 'online' | 'offline';
  modelTrained?: boolean;
  aiBackend?: string | null;
}

type Item = { id: PageId; label: string; icon: React.ReactNode; count?: number; attention?: boolean };

export const Sidebar: React.FC<SidebarProps> = ({ currentPage, onNavigate, counts, connection, modelTrained, aiBackend }) => {
  const groups: { label: string; items: Item[] }[] = [
    {
      label: 'Operations',
      items: [
        { id: 'overview', label: 'Overview', icon: <LayoutDashboard size={16} /> },
        { id: 'demo', label: 'MTU demo (simulated)', icon: <FlaskConical size={16} /> },
        { id: 'incidents', label: 'Incidents', icon: <AlertOctagon size={16} />, count: counts.openIncidents },
        {
          id: 'remediation',
          label: 'Remediation',
          icon: <Wrench size={16} />,
          count: counts.awaitingApproval,
          attention: counts.awaitingApproval > 0,
        },
      ],
    },
    {
      label: 'Pipeline',
      items: [
        { id: 'events', label: 'Telemetry', icon: <Activity size={16} />, count: counts.events },
        { id: 'decisions', label: 'Triage decisions', icon: <GitBranch size={16} />, count: counts.decisions },
        { id: 'ai-analysis', label: 'Analysis engine', icon: <Cpu size={16} /> },
      ],
    },
    {
      label: 'Records',
      items: [{ id: 'audit-trail', label: 'Execution log', icon: <ScrollText size={16} />, count: counts.executions }],
    },
  ];

  const active = currentPage === 'incident-detail' ? 'incidents' : currentPage;
  const connTone = connection === 'online' ? 'dot-ok' : connection === 'offline' ? 'dot-crit' : 'dot-neutral';

  return (
    <aside className="sidebar" aria-label="Primary">
      <div className="sidebar-brand">
        <span className="brand-mark" aria-hidden>
          <Waypoints size={14} />
        </span>
        <div className="brand-text">
          <div className="brand-name">Network Triage</div>
          <div className="brand-sub">Fault triage &amp; remediation</div>
        </div>
      </div>

      <nav className="sidebar-nav">
        {groups.map((g) => (
          <div className="nav-group" key={g.label}>
            <div className="nav-group-label">{g.label}</div>
            {g.items.map((item) => (
              <button
                key={item.id}
                className="nav-item"
                aria-current={active === item.id ? 'page' : undefined}
                onClick={() => onNavigate(item.id)}
                title={item.label}
              >
                {item.icon}
                <span className="nav-label">{item.label}</span>
                {item.count !== undefined && item.count > 0 && (
                  <span className={`nav-count${item.attention ? ' attention' : ''}`}>{item.count}</span>
                )}
              </button>
            ))}
          </div>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="row">
          <span>Controller</span>
          <span className="status" style={{ fontSize: 11 }}>
            <span className={`dot ${connTone}`} aria-hidden />
            <span className="val" style={{ fontFamily: 'inherit' }}>
              {connection === 'online' ? 'Connected' : connection === 'offline' ? 'Unreachable' : 'Connecting'}
            </span>
          </span>
        </div>
        <div className="row">
          <span>API</span>
          <span className="val" title={API_BASE_URL}>
            {API_BASE_URL.replace(/^https?:\/\//, '')}
          </span>
        </div>
        <div className="row">
          <span>Triage model</span>
          <span className="val">{modelTrained === undefined ? '—' : modelTrained ? 'trained' : 'fallback'}</span>
        </div>
        <div className="row">
          <span>AI layer</span>
          <span className="val">{aiBackend || 'disabled'}</span>
        </div>
      </div>
    </aside>
  );
};
