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
  remediationMode?: string | null;
  onRequestApproval: (i: Incident, approve: boolean) => void;
}

const DISPATCHED = new Set(['approved', 'auto', 'dry_run', 'resolved', 'inconclusive', 'verification_failed', 'execution_failed']);

export const RemediationPage: React.FC<Props> = ({ incidents, auditLog, remediationMode, loaded, navigate, onRequestApproval }) => {
  const awaiting = useMemo(() => incidents.filter((i) => i.state === 'awaiting_approval'), [incidents]);
  const inFlight = useMemo(() => incidents.filter((i) => DISPATCHED.has(i.state)), [incidents]);
  const manual = useMemo(() => incidents.filter((i) => i.state === 'manual' || i.state === 'blocked'), [incidents]);
  const rejected = useMemo(() => incidents.filter((i) => i.state === 'rejected' || i.state === 'expired'), [incidents]);
  const recentRuns = auditLog.slice(-10).reverse();

  const policy = 'Every remediation (rules, ML or AI) is validated by the shared policy and requires engineer approval';

  return (
    <>
      <PageHeader
        title="Remediation Gate"
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
          <div className="stat-meta">Approved; see state for post-check outcome</div>
        </div>
        <div className="stat">
          <div className="stat-label">Manual triage</div>
          <div className={`stat-value${manual.length ? ' crit' : ''}`}>{loaded ? manual.length : '—'}</div>
          <div className="stat-meta">No plan passed the policy</div>
        </div>
        <div className="stat">
          <div className="stat-label">Rejected</div>
          <div className="stat-value">{loaded ? rejected.length : '—'}</div>
          <div className="stat-meta">Declined or expired</div>
        </div>
        <div className="stat stat-wide">
          <div className="stat-label">Approval policy</div>
          <div style={{ marginTop: 4 }}>{policy}</div>
          <div className="stat-meta">
            Execution mode: {remediationMode === 'ansible' ? 'REAL Ansible (operator opt-in)' : remediationMode === 'simulate' ? 'simulation (no infrastructure change)' : '—'}
          </div>
        </div>
      </div>

      <Panel
        title="Approval required"
        count={awaiting.length}
        sub="Highest priority first. Approving runs the previewed action in its bound mode, then the post-check."
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
            <Panel title="Manual triage" count={manual.length} sub="No candidate passed the shared remediation policy" flush>
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
