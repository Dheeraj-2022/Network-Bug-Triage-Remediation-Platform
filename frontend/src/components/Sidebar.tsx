import React from 'react';
import {
  Activity,
  AlertOctagon,
  Cpu,
  FileText,
  GitBranch,
  Layers,
  LayoutDashboard,
  LogOut,
  Radio,
  Server,
  Wrench,
} from 'lucide-react';
import { PageId, SystemStatus } from '../types';

interface SidebarProps {
  currentPage: PageId;
  onNavigate: (page: PageId) => void;
  status: SystemStatus | null;
  activeIncidentsCount: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentPage,
  onNavigate,
  status,
  activeIncidentsCount,
}) => {
  const navItems: { id: PageId; label: string; icon: React.ReactNode; badge?: string; badgeColor?: string }[] = [
    {
      id: 'overview',
      label: 'Overview',
      icon: <LayoutDashboard size={16} />,
    },
    {
      id: 'events',
      label: 'Events',
      icon: <Radio size={16} />,
      badge: `${(status?.total_events || 0) > 0 ? `${status?.total_events}` : '14.8k/s'}`,
      badgeColor: 'rgba(56, 189, 248, 0.15)',
    },
    {
      id: 'incidents',
      label: 'Incidents',
      icon: <AlertOctagon size={16} />,
      badge: `${activeIncidentsCount} Active`,
      badgeColor: 'rgba(244, 63, 94, 0.2)',
    },
    {
      id: 'decisions',
      label: 'Decisions',
      icon: <GitBranch size={16} />,
      badge: status?.total_decisions ? `${status.total_decisions}` : undefined,
    },
    {
      id: 'remediation',
      label: 'Remediation',
      icon: <Wrench size={16} />,
      badge: '2 Pending',
      badgeColor: 'rgba(245, 158, 11, 0.2)',
    },
    {
      id: 'ai-analysis',
      label: 'AI Analysis',
      icon: <Cpu size={16} />,
    },
    {
      id: 'audit-trail',
      label: 'Audit Trail',
      icon: <FileText size={16} />,
    },
  ];

  return (
    <aside
      style={{
        width: '240px',
        backgroundColor: '#0c0f15',
        borderRight: '1px solid #1c222e',
        display: 'flex',
        flexDirection: 'column',
        flexShrink: 0,
        height: '100vh',
      }}
    >
      {/* Brand Header */}
      <div
        style={{
          padding: '1.1rem 1.15rem',
          borderBottom: '1px solid #1c222e',
          display: 'flex',
          alignItems: 'center',
          gap: '0.65rem',
        }}
      >
        <div
          style={{
            width: '26px',
            height: '26px',
            backgroundColor: '#18202d',
            border: '1px solid #38bdf8',
            borderRadius: '4px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#38bdf8',
          }}
        >
          <Activity size={15} />
        </div>
        <div>
          <div style={{ fontSize: '0.85rem', fontWeight: 700, letterSpacing: '0.04em', color: '#f1f5f9' }}>
            NETWORK TRIAGE
          </div>
          <div
            style={{
              fontSize: '0.625rem',
              color: '#64748b',
              fontFamily: 'var(--font-mono)',
              letterSpacing: '0.05em',
            }}
          >
            NOC FABRIC v2.4-PROD
          </div>
        </div>
      </div>

      {/* Navigation Links */}
      <nav style={{ padding: '0.85rem 0.65rem', flex: 1, display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
        <div
          style={{
            padding: '0.35rem 0.6rem',
            fontSize: '0.625rem',
            fontWeight: 700,
            color: '#475569',
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
            fontFamily: 'var(--font-mono)',
          }}
        >
          Navigation
        </div>

        {navItems.map((item) => {
          const isActive = currentPage === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0.45rem 0.65rem',
                borderRadius: '3px',
                border: 'none',
                background: isActive ? '#161d28' : 'transparent',
                color: isActive ? '#38bdf8' : '#94a3b8',
                cursor: 'pointer',
                textAlign: 'left',
                width: '100%',
                transition: 'all 0.12s ease',
                borderLeft: isActive ? '2px solid #38bdf8' : '2px solid transparent',
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  e.currentTarget.style.backgroundColor = '#111620';
                  e.currentTarget.style.color = '#e2e8f0';
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  e.currentTarget.style.backgroundColor = 'transparent';
                  e.currentTarget.style.color = '#94a3b8';
                }
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', fontSize: '0.8125rem', fontWeight: isActive ? 600 : 500 }}>
                <span style={{ color: isActive ? '#38bdf8' : '#64748b' }}>{item.icon}</span>
                <span>{item.label}</span>
              </div>
              {item.badge && (
                <span
                  style={{
                    fontSize: '0.625rem',
                    fontFamily: 'var(--font-mono)',
                    padding: '0.1rem 0.4rem',
                    borderRadius: '2px',
                    backgroundColor: item.badgeColor || '#1c222e',
                    color: item.badgeColor?.includes('244') ? '#f43f5e' : item.badgeColor?.includes('245') ? '#f59e0b' : '#38bdf8',
                    fontWeight: 600,
                  }}
                >
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* System Status & User Footer */}
      <div style={{ padding: '0.85rem', borderTop: '1px solid #1c222e', backgroundColor: '#090c10' }}>
        <div style={{ marginBottom: '0.75rem', display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.6875rem' }}>
            <span style={{ color: '#64748b' }}>System API</span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: '#10b981', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
              <span className="status-pulse-dot pulse-green" />
              Operational
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.6875rem' }}>
            <span style={{ color: '#64748b' }}>Engine Latency</span>
            <span style={{ color: '#94a3b8', fontFamily: 'var(--font-mono)' }}>12ms</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.6875rem' }}>
            <span style={{ color: '#64748b' }}>Models Online</span>
            <span style={{ color: '#38bdf8', fontFamily: 'var(--font-mono)' }}>
              {status?.model_trained ? 'Active (XGB+NLP)' : 'Rules+Heuristic'}
            </span>
          </div>
        </div>

        {/* User Badge */}
        <div
          style={{
            padding: '0.5rem',
            backgroundColor: '#12161f',
            border: '1px solid #1e2430',
            borderRadius: '3px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <div
              style={{
                width: '24px',
                height: '24px',
                borderRadius: '3px',
                backgroundColor: '#1e293b',
                color: '#38bdf8',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '0.6875rem',
                fontWeight: 700,
                fontFamily: 'var(--font-mono)',
              }}
            >
              SV
            </div>
            <div>
              <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#e2e8f0', lineHeight: 1.1 }}>
                s.vance@noc-eng
              </div>
              <div style={{ fontSize: '0.625rem', color: '#64748b' }}>Tier 3 On-Call</div>
            </div>
          </div>
          <button
            title="Sign out / Session"
            style={{
              background: 'none',
              border: 'none',
              color: '#64748b',
              cursor: 'pointer',
              display: 'flex',
              padding: '0.2rem',
            }}
          >
            <LogOut size={13} />
          </button>
        </div>
      </div>
    </aside>
  );
};
