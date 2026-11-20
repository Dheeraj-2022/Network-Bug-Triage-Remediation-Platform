import React from 'react';
import {
  Activity,
  AlertTriangle,
  Cpu,
  GitBranch,
  LayoutGrid,
  Mic,
  ScrollText,
  ShieldCheck,
  ArrowLeftRight,
} from 'lucide-react';
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

export const Sidebar: React.FC<SidebarProps> = ({
  currentPage,
  onNavigate,
  counts,
  connection,
  modelTrained,
  aiBackend,
}) => {
  const groups: { label: string; items: Item[] }[] = [
    {
      label: 'Operations',
      items: [
        { id: 'overview', label: 'Incident Cockpit', icon: <LayoutGrid size={15} /> },
        { id: 'demo', label: 'Two-Host MTU Demo', icon: <ArrowLeftRight size={15} /> },
        { id: 'voice', label: 'Voice Operations', icon: <Mic size={15} /> },
        { id: 'incidents', label: 'Incident Queue & RCA', icon: <AlertTriangle size={15} />, count: counts.openIncidents },
        {
          id: 'remediation',
          label: 'Remediation Gate',
          icon: <ShieldCheck size={15} />,
          count: counts.awaitingApproval,
          attention: counts.awaitingApproval > 0,
        },
      ],
    },
    {
      label: 'Pipeline',
      items: [
        { id: 'events', label: 'Telemetry Events', icon: <Activity size={15} />, count: counts.events },
        { id: 'decisions', label: 'Triage Decisions', icon: <GitBranch size={15} />, count: counts.decisions },
        { id: 'ai-analysis', label: 'Multi-Agent Analysis', icon: <Cpu size={15} /> },
      ],
    },
    {
      label: 'Records',
      items: [{ id: 'audit-trail', label: 'Execution & Audit Log', icon: <ScrollText size={15} />, count: counts.executions }],
    },
  ];

  const active = currentPage === 'incident-detail' ? 'incidents' : currentPage;

  return (
    <aside className="sidebar" aria-label="Primary">
      <div className="sidebar-brand">
        <span className="brand-mark" aria-hidden>
          <LayoutGrid size={13} />
        </span>
        <span className="brand-name">NetResolve AI</span>
        <span className="brand-ver">V2.4</span>
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
          <span>CTR:</span>
          <span className="val" style={{ color: connection === 'online' ? 'var(--ok)' : connection === 'offline' ? 'var(--crit)' : 'var(--text-2)' }}>
            {connection === 'online' ? 'ACTIVE' : connection === 'offline' ? 'OFFLINE' : 'SYNCING'}
          </span>
        </div>
        <div className="row">
          <span>API:</span>
          <span className="val truncate" title={API_BASE_URL} style={{ maxWidth: 132 }}>
            {API_BASE_URL.replace(/^https?:\/\//, '')}
          </span>
        </div>
        <div className="row">
          <span>XGB:</span>
          <span className="val" style={{ color: modelTrained ? 'var(--ok)' : 'var(--warn)' }}>
            {modelTrained === undefined ? '—' : modelTrained ? 'TRAINED' : 'FALLBACK'}
          </span>
        </div>
        <div className="row">
          <span>AI:</span>
          <span className="val truncate" style={{ maxWidth: 132 }}>
            {(aiBackend || 'DISABLED').toUpperCase()}
          </span>
        </div>
      </div>
    </aside>
  );
};
