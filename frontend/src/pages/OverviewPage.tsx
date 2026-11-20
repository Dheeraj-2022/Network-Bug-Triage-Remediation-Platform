import React, { useMemo } from 'react';
import { ArrowRight, Database, Zap } from 'lucide-react';
import { ActivityChart, BarList } from '../components/charts';
import { IncidentTable } from '../components/IncidentTable';
import { Banner, EmptyState, PageHeader, Panel, StatusDot, Tone } from '../components/ui';
import { buildActivity, countBy, HostHealth, Incident, STATE_META } from '../lib/incidents';
import { domainLabel, formatDateTime, formatNumber, relativeTime } from '../lib/format';
import { AIStatus, AuditEntry, Decision, SystemStatus, TelemetryEvent } from '../types';
import { CommonPageProps } from './common';

interface OverviewPageProps extends CommonPageProps {
  status: SystemStatus | null;
  events: TelemetryEvent[];
  decisions: Decision[];
  incidents: Incident[];
  hostHealth: HostHealth[];
  auditLog: AuditEntry[];
  aiStatus: AIStatus | null;
  empty: boolean;
  onRequestApproval: (i: Incident, approve: boolean) => void;
}

const HEALTH_TONE: Record<HostHealth['state'], Tone> = { faulty: 'crit', degraded: 'warn', healthy: 'ok' };

export const OverviewPage: React.FC<OverviewPageProps> = ({
  status,
  decisions,
  incidents,
  hostHealth,
  auditLog,
  aiStatus,
  empty,
  loaded,
  connection,
  navigate,
  onInject,
  onLoadSamples,
  isLoadingSamples,
  onRequestApproval,
}) => {
  const needsAction = incidents.filter((i) => STATE_META[i.state].group === 'action');
  const awaiting = incidents.filter((i) => i.state === 'awaiting_approval');
  const manual = incidents.filter((i) => i.state === 'manual');
  const p1 = needsAction.filter((i) => i.severity === 'P1').length;
  const p2 = needsAction.filter((i) => i.severity === 'P2').length;
  const unhealthy = hostHealth.filter((h) => h.state !== 'healthy');
  const activity = useMemo(() => buildActivity(decisions, 30), [decisions]);
  const domains = useMemo(() => countBy(incidents, (i) => i.faultDomain), [incidents]);
  const recentRuns = auditLog.slice(-6).reverse();
  const queue = incidents.slice(0, 8);
  const modelMsg = (status?.model_status as any)?.message as string | undefined;

  if (empty) {
    return (
      <>
        <PageHeader title="Overview" description="Operational state of hosts, incidents and the triage pipeline." />
        <Panel>
          <EmptyState
            icon={<Database size={28} />}
            title="No telemetry has been ingested"
            description={
              <>
                The controller is running but has not processed any events. Replay the bundled fixtures or inject synthetic
                host telemetry to exercise the rules engine, ML triage and remediation workflow.
              </>
            }
            actions={
              <>
                <button className="btn btn-primary" onClick={onLoadSamples} disabled={isLoadingSamples}>
                  <Database size={14} />
                  {isLoadingSamples ? 'Loading…' : 'Load sample fixtures'}
                </button>
                <button className="btn" onClick={onInject}>
                  <Zap size={14} />
                  Inject synthetic events
                </button>
              </>
            }
          />
        </Panel>
      </>
    );
  }

  const loading = !loaded;

  return (
    <>
      <PageHeader title="Overview" description="Operational state of hosts, incidents and the triage pipeline." />

      {awaiting.length > 0 && (
        <Banner
          tone="warn"
          title={`${awaiting.length} remediation ${awaiting.length === 1 ? 'plan is' : 'plans are'} waiting for approval`}
          actions={
            <>
              {awaiting.length === 1 && (
                <button className="btn btn-sm" onClick={() => onRequestApproval(awaiting[0], true)}>
                  Approve
                </button>
              )}
              <button className="btn btn-sm" onClick={() => navigate('remediation')}>
                Review plans
              </button>
            </>
          }
        >
          Execution is paused by the human-approval gate until an engineer signs off.
          {awaiting.length === 1 && (
            <>
              {' '}
              {awaiting[0].title} · <span className="mono">{awaiting[0].playbook}</span>
            </>
          )}
        </Banner>
      )}

      <div className="stat-strip" role="list">
        <button className="stat" role="listitem" onClick={() => navigate('incidents', undefined, { view: 'action' })}>
          <div className="stat-label">Needs action</div>
          <div className={`stat-value${needsAction.length ? ' crit' : ''}`}>{loading ? '—' : needsAction.length}</div>
          <div className="stat-meta">
            {p1} P1 · {p2} P2 · {manual.length} manual triage
          </div>
        </button>
        <button className="stat" role="listitem" onClick={() => navigate('remediation')}>
          <div className="stat-label">Awaiting approval</div>
          <div className={`stat-value${awaiting.length ? ' warn' : ''}`}>{loading ? '—' : awaiting.length}</div>
          <div className="stat-meta">
            {aiStatus?.enabled ? (aiStatus.require_human_approval ? 'Gate: all plans' : 'Gate: medium/high risk') : 'AI layer disabled'}
          </div>
        </button>
        <button className="stat" role="listitem" onClick={() => navigate('events')}>
          <div className="stat-label">Unhealthy hosts</div>
          <div className={`stat-value${unhealthy.some((h) => h.state === 'faulty') ? ' crit' : unhealthy.length ? ' warn' : ''}`}>
            {loading ? '—' : unhealthy.length}
            <span className="muted" style={{ fontSize: 13, fontWeight: 400 }}> / {hostHealth.length}</span>
          </div>
          <div className="stat-meta">Based on latest telemetry per host</div>
        </button>
        <button className="stat" role="listitem" onClick={() => navigate('events')}>
          <div className="stat-label">Events ingested</div>
          <div className="stat-value">{formatNumber(status?.total_events)}</div>
          <div className="stat-meta">{formatNumber(status?.total_decisions)} triage decisions</div>
        </button>
        <button className="stat" role="listitem" onClick={() => navigate('audit-trail')}>
          <div className="stat-label">Remediations triggered</div>
          <div className="stat-value">{formatNumber(status?.remediations)}</div>
          <div className="stat-meta">Ansible playbooks, dry-run mode</div>
        </button>
      </div>

      <div className="layout-aside">
        <div className="stack">
          <Panel
            title="Incident queue"
            count={incidents.length}
            sub="Ordered by required action, priority, then recency"
            actions={
              <button className="btn btn-sm btn-ghost" onClick={() => navigate('incidents')}>
                All incidents <ArrowRight size={14} />
              </button>
            }
            flush
          >
            <IncidentTable
              incidents={queue}
              navigate={navigate}
              loading={loading}
              empty={
                <EmptyState
                  compact
                  title="No incidents"
                  description="No processed event has breached a rule threshold or been escalated by the analysis engine."
                />
              }
            />
          </Panel>

          <Panel
            title="Triage activity"
            sub={`Decisions per minute, last 30 minutes (UTC)${activity.end < Date.now() - 60_000 ? ` · window ends ${relativeTime(new Date(activity.end).toISOString())}` : ''}`}
            actions={
              <div className="chart-legend">
                <span>
                  <i className="swatch" style={{ background: '#9fb3d9' }} />
                  No action
                </span>
                <span>
                  <i className="swatch" style={{ background: '#c4302b' }} />
                  Flagged for remediation
                </span>
              </div>
            }
          >
            <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 240px', gap: 24 }} className="activity-grid">
              <ActivityChart buckets={activity.buckets} />
              <div>
                <div className="section-label">Incidents by fault domain</div>
                <BarList
                  items={domains.map((d) => ({ key: d.key, label: domainLabel(d.key), count: d.count }))}
                  emptyText="No incidents yet"
                />
              </div>
            </div>
          </Panel>
        </div>

        <div className="stack">
          <Panel
            title="Host health"
            count={hostHealth.length}
            flush
            actions={
              <button className="btn btn-sm btn-ghost" onClick={() => navigate('events')}>
                Telemetry <ArrowRight size={14} />
              </button>
            }
          >
            {hostHealth.length === 0 ? (
              <EmptyState compact title="No hosts reporting" />
            ) : (
              <div className="host-list">
                {hostHealth.slice(0, 8).map((h) => (
                  <a
                    key={h.host}
                    className="host-row"
                    href={`#/telemetry?host=${encodeURIComponent(h.host)}`}
                    style={{ color: 'inherit', textDecoration: 'none' }}
                    title={`Last event ${formatDateTime(h.lastSeen)}`}
                  >
                    <span className={`dot dot-${HEALTH_TONE[h.state]}`} aria-label={h.state} />
                    <span style={{ minWidth: 0 }}>
                      <span className="mono strong">{h.host}</span>
                      <span className="component-detail truncate" style={{ display: 'block' }}>
                        {h.reasons.length ? h.reasons.join(' · ') : 'No error counters'}
                      </span>
                    </span>
                    <span className="muted num" style={{ fontSize: 12, textAlign: 'right' }}>
                      {h.openIncidents > 0 ? (
                        <span style={{ color: 'var(--crit)' }}>{h.openIncidents} open</span>
                      ) : (
                        `${h.events} evts`
                      )}
                    </span>
                  </a>
                ))}
                {hostHealth.length > 8 && (
                  <div className="host-row" style={{ gridTemplateColumns: '1fr' }}>
                    <a href="#/telemetry">+{hostHealth.length - 8} more hosts</a>
                  </div>
                )}
              </div>
            )}
          </Panel>

          <Panel title="Pipeline" flush>
            <div className="component-list">
              <PipelineRow
                name="Rules engine"
                detail="iface errors ≥ 5 · RDMA QP errors ≥ 1"
                tone={connection === 'online' ? 'ok' : 'neutral'}
                state={connection === 'online' ? 'Active' : 'Unknown'}
              />
              <PipelineRow
                name="Triage model"
                detail={status?.model_trained ? 'XGBoost priority classifier' : modelMsg || 'Using fallback priority score'}
                tone={status?.model_trained ? 'ok' : 'warn'}
                state={status ? (status.model_trained ? 'Trained' : 'Not trained') : '—'}
              />
              <PipelineRow
                name="Analysis engine"
                detail={
                  aiStatus?.enabled
                    ? [aiStatus.llm_backend, aiStatus.retriever_backend && `retriever: ${aiStatus.retriever_backend}`].filter(Boolean).join(' · ')
                    : aiStatus?.reason || aiStatus?.error || 'Multi-agent RCA unavailable'
                }
                tone={aiStatus?.enabled ? 'ok' : 'neutral'}
                state={aiStatus?.enabled ? 'Enabled' : 'Disabled'}
              />
              <PipelineRow
                name="Playbook execution"
                detail="API records playbook triggers without applying changes"
                tone="info"
                state="Dry-run"
              />
            </div>
          </Panel>

          <Panel
            title="Recent executions"
            flush
            actions={
              <button className="btn btn-sm btn-ghost" onClick={() => navigate('audit-trail')}>
                Log <ArrowRight size={14} />
              </button>
            }
          >
            {recentRuns.length === 0 ? (
              <EmptyState compact title="No playbooks triggered" />
            ) : (
              <div className="component-list">
                {recentRuns.map((a, idx) => (
                  <div className="component-row" key={`${a.ts}-${idx}`}>
                    <div style={{ minWidth: 0 }}>
                      <div className="mono truncate">{a.playbook || '—'}</div>
                      <div className="component-detail truncate">
                        <span className="mono">{a.host}</span> · {a.reason}
                      </div>
                    </div>
                    <span className="muted num" style={{ fontSize: 12 }} title={formatDateTime(a.ts)}>
                      {relativeTime(a.ts)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Panel>
        </div>
      </div>
    </>
  );
};

const PipelineRow: React.FC<{ name: string; detail: React.ReactNode; tone: Tone; state: string }> = ({ name, detail, tone, state }) => (
  <div className="component-row">
    <div style={{ minWidth: 0 }}>
      <div className="component-name">{name}</div>
      <div className="component-detail truncate">{detail}</div>
    </div>
    <StatusDot tone={tone} label={<span style={{ fontSize: 12 }}>{state}</span>} />
  </div>
);
