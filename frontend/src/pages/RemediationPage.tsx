import React, { useMemo } from 'react';
import { ArrowRight } from 'lucide-react';
import { IncidentTable } from '../components/IncidentTable';
import { EmptyState, PageHeader, Panel } from '../components/ui';
import { Incident } from '../lib/incidents';
import { formatTime, relativeTime } from '../lib/format';
import { AIStatus, AuditEntry } from '../types';
import { CommonPageProps } from './common';

interface Props extends CommonPageProps {
  incidents: Incident[];
  aiStatus: AIStatus | null;
  auditLog: AuditEntry[];
  onRequestApproval: (i: Incident, approve: boolean) => void;
}

export const RemediationPage: React.FC<Props> = ({ incidents, aiStatus, auditLog, loaded, navigate, onRequestApproval }) => {
  const awaiting = useMemo(() => incidents.filter((i) => i.state === 'awaiting_approval'), [incidents]);
  const inFlight = useMemo(() => incidents.filter((i) => i.state === 'approved' || i.state === 'auto' || i.state === 'dry_run'), [incidents]);
  const manual = useMemo(() => incidents.filter((i) => i.state === 'manual'), [incidents]);
  const rejected = useMemo(() => incidents.filter((i) => i.state === 'rejected'), [incidents]);
  const recentRuns = auditLog.slice(-10).reverse();

  const policy = !aiStatus
    ? '—'
    : !aiStatus.enabled
      ? 'Analysis engine disabled — rule-triggered playbooks run without a gate'
      : aiStatus.require_human_approval
        ? 'Every plan requires engineer approval'
        : 'Medium and high-risk plans require engineer approval; low-risk plans run automatically';

  return (
    <>
      <PageHeader
        title="Remediation"
        description="Plans proposed for open incidents, the approval gate, and what has been dispatched."
      />

      <div className="stat-strip">
        <div className="stat">
          <div className="stat-label">Approval required</div>
          <div className={`stat-value${awaiting.length ? ' warn' : ''}`}>{loaded ? awaiting.length : '—'}</div>
          <div className="stat-meta">Blocked until signed off</div>
        </div>
        <div className="stat">
          <div className="stat-label">Dispatched</div>
          <div className="stat-value">{loaded ? inFlight.length : '—'}</div>
          <div className="stat-meta">Approved, auto or rule-triggered</div>
        </div>
        <div className="stat">
          <div className="stat-label">Manual triage</div>
          <div className={`stat-value${manual.length ? ' crit' : ''}`}>{loaded ? manual.length : '—'}</div>
          <div className="stat-meta">No automated plan available</div>
        </div>
        <div className="stat">
          <div className="stat-label">Rejected</div>
          <div className="stat-value">{loaded ? rejected.length : '—'}</div>
          <div className="stat-meta">Plans declined by an engineer</div>
        </div>
        <div className="stat" style={{ gridColumn: 'span 2' }}>
          <div className="stat-label">Approval policy</div>
          <div style={{ marginTop: 4 }}>{policy}</div>
          <div className="stat-meta">Executor: {aiStatus?.executor || 'dry-run'}</div>
        </div>
      </div>

      <Panel
        title="Approval required"
        count={awaiting.length}
        sub="Highest priority first. Approving resumes the orchestrator: execution, then validation."
        className={awaiting.length ? 'attention' : undefined}
        flush
      >
        <IncidentTable
          incidents={awaiting}
          navigate={navigate}
          loading={!loaded}
          columns={['severity', 'incident', 'host', 'playbook', 'risk', 'confidence', 'detected']}
          actions={(i) => (
            <>
              <button className="btn btn-sm btn-danger" onClick={() => onRequestApproval(i, false)}>
                Reject
              </button>
              <button className="btn btn-sm btn-primary" onClick={() => onRequestApproval(i, true)}>
                Approve
              </button>
            </>
          )}
          empty={<EmptyState compact title="Nothing is waiting for approval" description="New plans that exceed the risk threshold will appear here." />}
        />
      </Panel>

      <div className="layout-aside">
        <div className="stack">
          <Panel title="Dispatched plans" count={inFlight.length} flush>
            <IncidentTable
              incidents={inFlight}
              navigate={navigate}
              loading={!loaded}
              columns={['severity', 'incident', 'state', 'playbook', 'risk', 'detected']}
              empty={<EmptyState compact title="No plans dispatched" />}
            />
          </Panel>

          {manual.length > 0 && (
            <Panel title="Manual triage" count={manual.length} sub="The analysis engine found no safe automated action" flush>
              <IncidentTable incidents={manual} navigate={navigate} columns={['severity', 'incident', 'host', 'confidence', 'detected']} />
            </Panel>
          )}

          {rejected.length > 0 && (
            <Panel title="Rejected" count={rejected.length} flush>
              <IncidentTable incidents={rejected} navigate={navigate} columns={['severity', 'incident', 'host', 'playbook', 'detected']} />
            </Panel>
          )}
        </div>

        <Panel
          title="Recent executions"
          flush
          actions={
            <button className="btn btn-sm btn-ghost" onClick={() => navigate('audit-trail')}>
              Execution log <ArrowRight size={14} />
            </button>
          }
        >
          {recentRuns.length === 0 ? (
            <EmptyState compact title="No playbooks triggered yet" />
          ) : (
            <div className="component-list">
              {recentRuns.map((a, idx) => (
                <div className="component-row" key={`${a.ts}-${idx}`}>
                  <div style={{ minWidth: 0 }}>
                    <div className="mono truncate">{a.playbook || '—'}</div>
                    <div className="component-detail truncate">
                      <span className="mono">{a.host}</span> · {a.status || 'recorded'}
                    </div>
                  </div>
                  <span className="muted num" style={{ fontSize: 'var(--fs-sm)' }} title={`${formatTime(a.ts)} UTC`}>
                    {relativeTime(a.ts)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>
    </>
  );
};
