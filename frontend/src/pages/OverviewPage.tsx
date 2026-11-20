import React, { useMemo } from 'react';
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Cpu,
  Database,
  Eye,
  Lock,
  Mic,
  Server,
  ShieldCheck,
  Zap,
} from 'lucide-react';
import { ActivityChart, BarList } from '../components/charts';
import { IncidentTable } from '../components/IncidentTable';
import { Badge, EmptyState, Panel, StatusDot, Tone } from '../components/ui';
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
  remediationMode?: string;
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
  remediationMode,
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
  const availPct = hostHealth.length > 0 ? Math.round(((hostHealth.length - unhealthy.length) / hostHealth.length) * 100) : null;
  const activity = useMemo(() => buildActivity(decisions, 30), [decisions]);
  const domains = useMemo(() => countBy(incidents, (i) => i.faultDomain), [incidents]);
  const recentRuns = auditLog.slice(-6).reverse();
  const queue = incidents.slice(0, 8);
  const modelMsg = (status?.model_status as any)?.message as string | undefined;
  const modeLabel = (remediationMode || 'simulate').toUpperCase();
  const loading = !loaded;

  if (empty) {
    return (
      <>
        <div className="page-header">
          <div>
            <div className="eyebrow">FLIGHT DISPATCH LEDGER · NETRESOLVE AI OPERATIONS</div>
            <h1 className="page-title">OVERVIEW &amp; INCIDENT COCKPIT</h1>
          </div>
          <div className="page-actions">
            <button className="btn" onClick={() => navigate('voice')}>
              <Mic size={14} /> Open Voice Ops
            </button>
            <button className="btn btn-primary" onClick={() => navigate('demo')}>
              Load Two-Host MTU Demo
            </button>
          </div>
        </div>
        <Panel>
          <EmptyState
            icon={<Database size={28} />}
            title="No telemetry has been ingested"
            description={
              <>
                The controller is connected, but no host telemetry has arrived yet. Load the deterministic Two-Host MTU Demo,
                replay bundled sample fixtures, or inject synthetic telemetry to exercise rules, XGBoost triage, AI RCA, and
                the human-approval remediation gate.
              </>
            }
            actions={
              <>
                <button className="btn btn-primary" onClick={() => navigate('demo')}>
                  Load Two-Host MTU Demo
                </button>
                <button className="btn" onClick={onLoadSamples} disabled={isLoadingSamples}>
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

  return (
    <>
      <div className="page-header">
        <div>
          <div className="eyebrow">FLIGHT DISPATCH LEDGER · {connection === 'online' ? 'CONTROLLER ONLINE' : 'CONTROLLER OFFLINE'}</div>
          <h1 className="page-title">OVERVIEW &amp; INCIDENT COCKPIT</h1>
        </div>
        <div className="page-actions">
          <span className="status-chip">
            <Activity size={11} />
            TELEMETRY EVENTS: {formatNumber(status?.total_events)}
          </span>
          <span className="status-chip ok">
            <CheckCircle2 size={11} />
            DETERMINISTIC GATE: STRICT
          </span>
        </div>
      </div>

      {/* 4-Column Numbered Industrial KPI Strip */}
      <div className="nr-kpi-grid" role="list">
        <button
          className={`nr-kpi-card${needsAction.length > 0 ? ' crit' : ' ok'}`}
          role="listitem"
          onClick={() => navigate('incidents', undefined, { view: 'action' })}
        >
          <div className="nr-kpi-head">
            <span>01 / CRITICAL ATTENTION</span>
            <AlertTriangle size={13} />
          </div>
          <div className="nr-kpi-value">
            {loading ? '—' : String(needsAction.length).padStart(2, '0')}
            <span>Active Breaches</span>
          </div>
          <div className="nr-kpi-foot">
            <span>{p1} P1 · {p2} P2 · {manual.length} Manual</span>
            <Badge tone={needsAction.length > 0 ? 'crit' : 'ok'}>{needsAction.length > 0 ? 'ESCALATED' : 'NOMINAL'}</Badge>
          </div>
        </button>

        <button
          className={`nr-kpi-card${awaiting.length > 0 ? ' warn' : ''}`}
          role="listitem"
          onClick={() => navigate('remediation')}
        >
          <div className="nr-kpi-head">
            <span>02 / REMEDIATION GATE</span>
            <Lock size={13} />
          </div>
          <div className="nr-kpi-value">
            {loading ? '—' : String(awaiting.length).padStart(2, '0')}
            <span>Plans Awaiting Ack</span>
          </div>
          <div className="nr-kpi-foot">
            <span className="truncate">
              {awaiting[0] ? `${awaiting[0].remediationId || awaiting[0].key} on ${awaiting[0].host}` : 'No pending proposals'}
            </span>
            <Badge tone={awaiting.length > 0 ? 'warn' : 'neutral'}>{awaiting.length > 0 ? 'PENDING' : 'CLEAR'}</Badge>
          </div>
        </button>

        <button
          className={`nr-kpi-card${unhealthy.some((h) => h.state === 'faulty') ? ' crit' : unhealthy.length > 0 ? ' warn' : ' ok'}`}
          role="listitem"
          onClick={() => navigate('events')}
        >
          <div className="nr-kpi-head">
            <span>03 / CLUSTER FABRIC</span>
            <Server size={13} />
          </div>
          <div className="nr-kpi-value">
            {loading ? '—' : `${unhealthy.length} / ${hostHealth.length}`}
            <span>Unhealthy Nodes</span>
          </div>
          <div className="nr-kpi-foot">
            <span className="truncate">
              {unhealthy.length > 0 ? unhealthy.slice(0, 2).map((h) => `${h.host} [${h.state.toUpperCase()}]`).join(' · ') : 'All reporting hosts nominal'}
            </span>
            {availPct !== null && <Badge tone={availPct < 100 ? 'crit' : 'ok'}>{availPct}% AVAIL</Badge>}
          </div>
        </button>

        <button
          className="nr-kpi-card"
          role="listitem"
          onClick={() => navigate('decisions')}
        >
          <div className="nr-kpi-head">
            <span>04 / PIPELINE TELEMETRY</span>
            <Activity size={13} />
          </div>
          <div className="nr-kpi-value">
            {formatNumber(status?.total_events)}
            <span>Events</span>
          </div>
          <div className="nr-kpi-foot">
            <span>{formatNumber(status?.total_decisions)} Decisions · {formatNumber(status?.remediations)} Runs</span>
            <Badge tone="ok">{modeLabel === 'SIMULATE' ? 'SIMULATED' : modeLabel}</Badge>
          </div>
        </button>
      </div>

      {/* Human Approval Attention Bar */}
      {awaiting.length > 0 && (
        <div className="nr-gate-bar" role="status">
          <div style={{ minWidth: 0, flex: 1 }}>
            <div className="row" style={{ gap: 8, marginBottom: 4, flexWrap: 'wrap' }}>
              <Badge tone="warn">APPROVAL REQUIRED</Badge>
              {awaiting[0].remediationId && (
                <span className="mono" style={{ fontSize: 11, color: 'var(--text-2)' }}>
                  PLAN-ID: {awaiting[0].remediationId}
                </span>
              )}
              <span className="mono" style={{ fontSize: 11, color: 'var(--text-2)' }}>
                Target: <strong>{awaiting[0].host}</strong>
              </span>
            </div>
            <div style={{ fontSize: 13, fontWeight: 600, color: '#171614' }}>
              {awaiting.length} remediation {awaiting.length === 1 ? 'plan' : 'plans'} waiting for human verification:{' '}
              <span className="mono" style={{ background: '#ffffff', padding: '2px 7px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--warn-border)' }}>
                {awaiting[0].playbook || awaiting[0].title}
              </span>
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-2)', marginTop: 3 }}>
              {awaiting[0].explanation || awaiting[0].rootCause || 'Execution is paused at the RemediationPolicy gate until an authorized operator approves.'}
            </div>
          </div>
          <div className="row" style={{ gap: 8 }}>
            <button className="btn btn-sm" onClick={() => navigate('incident-detail', awaiting[0].key)}>
              <Eye size={13} /> INSPECT
            </button>
            <button className="btn btn-sm btn-primary" onClick={() => onRequestApproval(awaiting[0], true)}>
              <ShieldCheck size={13} /> AUTHORIZE &amp; EXECUTE
            </button>
          </div>
        </div>
      )}

      {/* Main Split Grid: Left (Queue + Triage Activity) / Right (Host Matrix + Autonomous Pipeline + Audit Log) */}
      <div className="layout-aside">
        <div className="stack">
          <Panel
            title="Active Incident Triage Queue"
            count={incidents.length}
            sub="Ordered by required human action, severity, and recency"
            actions={
              <button className="btn btn-sm" onClick={() => navigate('incidents')}>
                ALL INCIDENTS <ArrowRight size={13} />
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
                  title="No active incidents"
                  description="No processed telemetry event has breached deterministic thresholds or triggered escalation."
                />
              }
            />
          </Panel>

          <Panel
            title="Triage Activity & Fault Domain Breakdown"
            sub={`Decisions per minute, trailing 30m (UTC)${activity.end < Date.now() - 60_000 ? ` · window ends ${relativeTime(new Date(activity.end).toISOString())}` : ''}`}
            actions={
              <div className="chart-legend">
                <span>
                  <i className="swatch" style={{ background: '#cfc9be' }} />
                  No Action
                </span>
                <span>
                  <i className="swatch" style={{ background: '#b83b2a' }} />
                  Remediation Flagged
                </span>
              </div>
            }
          >
            <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 240px', gap: 24 }} className="activity-grid">
              <ActivityChart buckets={activity.buckets} />
              <div>
                <div className="eyebrow" style={{ marginBottom: 10 }}>ROOT CAUSE DISTRIBUTION</div>
                <BarList
                  items={domains.map((d) => ({ key: d.key, label: domainLabel(d.key), count: d.count }))}
                  emptyText="No incidents recorded"
                />
              </div>
            </div>
          </Panel>
        </div>

        <div className="stack">
          <Panel
            title="Host Matrix"
            count={hostHealth.length}
            flush
            actions={
              <button className="btn btn-sm btn-ghost" onClick={() => navigate('events')}>
                TELEMETRY <ArrowRight size={12} />
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
                    style={{
                      color: 'inherit',
                      textDecoration: 'none',
                      background: h.state === 'faulty' ? 'var(--crit-bg)' : undefined,
                    }}
                    title={`Last event ${formatDateTime(h.lastSeen)}`}
                  >
                    <span className={`dot dot-${HEALTH_TONE[h.state]}`} aria-label={h.state} />
                    <span style={{ minWidth: 0 }}>
                      <span className="mono strong">{h.host}</span>
                      <span className="component-detail truncate" style={{ display: 'block' }}>
                        {h.reasons.length ? h.reasons.join(' · ') : 'Healthy telemetry stream'}
                      </span>
                    </span>
                    <Badge tone={HEALTH_TONE[h.state]}>
                      {h.state === 'faulty' ? 'FAULT' : h.state === 'degraded' ? 'WARN' : 'NOMINAL'}
                    </Badge>
                  </a>
                ))}
              </div>
            )}
          </Panel>

          <Panel
            title="Autonomous Pipeline"
            actions={<span className="mono" style={{ fontSize: 10, color: 'var(--ok)' }}>{connection === 'online' ? 'ENGINES LIVE' : 'OFFLINE'}</span>}
            flush
          >
            <div className="component-list">
              <PipelineRow
                name="1. Deterministic Rule Engine"
                detail="iface errin+errout ≥ 5 · RDMA QP errors ≥ 1"
                tone={connection === 'online' ? 'ok' : 'neutral'}
                state={connection === 'online' ? 'ACTIVE' : 'OFFLINE'}
              />
              <PipelineRow
                name="2. XGBoost Triage Model"
                detail={status?.model_trained ? 'Trained priority & localization classifier' : modelMsg || 'Fallback heuristic priority score'}
                tone={status?.model_trained ? 'ok' : 'warn'}
                state={status ? (status.model_trained ? 'TRAINED' : 'FALLBACK') : '—'}
              />
              <PipelineRow
                name="3. Analysis & RCA Engine"
                detail={
                  aiStatus?.enabled
                    ? [aiStatus.llm_backend, aiStatus.retriever_backend && `RAG: ${aiStatus.retriever_backend}`].filter(Boolean).join(' · ')
                    : aiStatus?.reason || 'Offline / disabled'
                }
                tone={aiStatus?.enabled ? (aiStatus.uses_llm ? 'ok' : 'warn') : 'neutral'}
                state={aiStatus?.enabled ? (aiStatus.uses_llm ? 'GEMINI' : 'HEURISTIC') : 'DISABLED'}
              />
              <PipelineRow
                name="4. Playbook Execution Gate"
                detail="RemediationPolicy human approval + deterministic post-check"
                tone={modeLabel === 'ANSIBLE' ? 'crit' : 'warn'}
                state={modeLabel === 'SIMULATE' ? 'SIMULATED' : modeLabel}
              />
            </div>
          </Panel>

          <Panel
            title="Execution Audit Log"
            flush
            actions={
              <button className="btn btn-sm btn-ghost" onClick={() => navigate('audit-trail')}>
                VIEW ALL <ArrowRight size={12} />
              </button>
            }
          >
            {recentRuns.length === 0 ? (
              <EmptyState compact title="No playbooks executed" />
            ) : (
              <div className="component-list">
                {recentRuns.map((a, idx) => (
                  <div className="component-row" key={`${a.ts}-${idx}`}>
                    <div style={{ minWidth: 0 }}>
                      <div className="mono strong truncate" style={{ fontSize: 11 }}>{a.playbook || '—'}</div>
                      <div className="component-detail truncate">
                        <span className="mono">{a.host}</span> · {a.reason || a.status}
                      </div>
                    </div>
                    <span className="muted mono" style={{ fontSize: 10 }} title={formatDateTime(a.ts)}>
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
      <div className="component-name" style={{ fontSize: 12, fontWeight: 600 }}>{name}</div>
      <div className="component-detail truncate" style={{ fontSize: 11 }}>{detail}</div>
    </div>
    <Badge tone={tone}>{state}</Badge>
  </div>
);
