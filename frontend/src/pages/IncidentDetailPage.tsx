import React, { useEffect, useMemo, useState } from 'react';
import { ArrowLeft, Check, Minus, X } from 'lucide-react';
import { IncidentTable } from '../components/IncidentTable';
import { EvidencePanel, RemediationPanel } from '../components/EvidenceViews';
import { Badge, Banner, EmptyState, Meter, PageHeader, Panel, RiskBadge, SeverityTag, StateBadge, cx } from '../components/ui';
import { eventErrorCount, eventSignal, Incident } from '../lib/incidents';
import { domainLabel, formatBytes, formatDateTime, formatNumber, formatPct, formatTime, relativeTime } from '../lib/format';
import { hrefFor } from '../lib/routes';
import { api } from '../services/api';
import { AIIncidentDetail, AIStatus, AuditEntry, RemediationProposal, TelemetryEvent } from '../types';
import { CommonPageProps } from './common';

interface Props extends CommonPageProps {
  incidentKey: string;
  incidents: Incident[];
  events: TelemetryEvent[];
  auditLog: AuditEntry[];
  aiStatus: AIStatus | null;
  onRequestApproval: (i: Incident, approve: boolean) => void;
  onChanged?: () => void;
}

type Tab = 'evidence-policy' | 'analysis' | 'plan' | 'evidence' | 'trace';
type StepState = 'done' | 'current' | 'failed' | 'skipped' | 'pending';

interface Step {
  name: string;
  state: StepState;
  meta?: React.ReactNode;
}

const STEP_ICON: Record<StepState, React.ReactNode> = {
  done: <Check size={11} strokeWidth={3} />,
  current: null,
  failed: <X size={11} strokeWidth={3} />,
  skipped: <Minus size={11} strokeWidth={3} color="var(--text-4)" />,
  pending: null,
};

function buildSteps(i: Incident, detail: AIIncidentDetail | null, executions: AuditEntry[], proposal: RemediationProposal | null): Step[] {
  const hasAi = !!i.aiId;
  const approval: Step = (() => {
    switch (i.state) {
      case 'awaiting_approval':
        return { name: 'Approval', state: 'current', meta: 'Waiting for an engineer' };
      case 'approved':
      case 'resolved':
      case 'verification_failed':
      case 'inconclusive':
      case 'execution_failed':
        return { name: 'Approval', state: 'done', meta: proposal?.decision ? `Approved by ${proposal.decision.approver}` : 'Approved' };
      case 'rejected':
        return { name: 'Approval', state: 'failed', meta: proposal?.decision ? `Rejected by ${proposal.decision.approver}` : 'Rejected' };
      case 'blocked':
        return { name: 'Approval', state: 'failed', meta: 'Blocked by policy' };
      case 'expired':
        return { name: 'Approval', state: 'failed', meta: 'Approval expired' };
      case 'auto':
        return { name: 'Approval', state: 'skipped', meta: 'Not required (low risk)' };
      case 'manual':
        return { name: 'Approval', state: 'skipped', meta: 'No automated plan' };
      default:
        return { name: 'Approval', state: 'skipped', meta: 'No remediation proposed' };
    }
  })();

  const execution: Step = (() => {
    if (['rejected', 'manual', 'blocked', 'expired'].includes(i.state)) return { name: 'Execution', state: 'skipped', meta: 'Not executed' };
    if (i.state === 'awaiting_approval') return { name: 'Execution', state: 'pending', meta: 'Blocked by approval gate' };
    if (i.state === 'execution_failed') return { name: 'Execution', state: 'failed', meta: 'Execution failed' };
    if (proposal?.execution) return { name: 'Execution', state: 'done', meta: proposal.execution.simulated ? 'Simulated (no change)' : 'Executed' };
    if (executions.length) return { name: 'Execution', state: 'done', meta: `${executions[0].status || 'recorded'} · ${formatTime(executions[0].ts)}` };
    if (i.state === 'approved' || i.state === 'auto') return { name: 'Execution', state: 'done', meta: 'Dispatched' };
    return { name: 'Execution', state: 'pending' };
  })();

  const resolved = detail?.validation?.resolved;
  const validation: Step = proposal?.verification
    ? proposal.verification.outcome === 'passed'
      ? { name: 'Post-check', state: 'done', meta: 'Passed' }
      : proposal.verification.outcome === 'failed'
        ? { name: 'Post-check', state: 'failed', meta: 'Failed — not resolved' }
        : { name: 'Post-check', state: 'current', meta: 'Inconclusive — not resolved' }
    : !hasAi
      ? { name: 'Post-check', state: execution.state === 'done' ? 'pending' : 'skipped', meta: execution.state === 'done' ? 'Awaiting telemetry' : undefined }
      : resolved === true
        ? { name: 'Post-check', state: 'done', meta: `Resolved · ${formatPct(detail?.validation?.confidence)}` }
        : resolved === false
          ? { name: 'Post-check', state: 'failed', meta: detail?.validation?.residual_risk ? `Residual risk: ${detail.validation.residual_risk}` : 'Not resolved' }
          : { name: 'Post-check', state: 'pending', meta: execution.state === 'done' ? 'Awaiting validation' : undefined };

  return [
    { name: 'Detected', state: 'done', meta: formatTime(i.ts) + ' UTC' },
    {
      name: 'Triaged',
      state: 'done',
      meta: `${i.ruleAction === 'remediate' ? 'Rule breach' : 'Rule ok'} · ML ${i.mlPriority.toFixed(2)}`,
    },
    i.decision.evidence
      ? { name: 'Root cause', state: 'done', meta: `${domainLabel(i.decision.evidence.inference.fault_domain)} · evidence ${i.decision.evidence.confidence.level}` }
      : hasAi
        ? { name: 'Root cause', state: 'done', meta: `${domainLabel(i.faultDomain)} · model ${formatPct(i.confidence)}` }
        : { name: 'Root cause', state: 'skipped', meta: 'Analysis engine disabled' },
    i.playbook
      ? { name: 'Plan', state: 'done', meta: i.playbook }
      : { name: 'Plan', state: 'failed', meta: 'No playbook matched' },
    approval,
    execution,
    validation,
  ];
}

export const IncidentDetailPage: React.FC<Props> = ({ incidentKey, incidents, events, auditLog, loaded, navigate, onRequestApproval, onChanged }) => {
  const incident = incidents.find((i) => i.key === incidentKey);
  const [tab, setTab] = useState<Tab>('evidence-policy');
  const [detail, setDetail] = useState<AIIncidentDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [proposal, setProposal] = useState<RemediationProposal | null>(null);
  const [proposalError, setProposalError] = useState<string | null>(null);

  const aiId = incident?.aiId;
  const aiStatusKey = incident?.state;
  const remediationId = incident?.remediationId;

  useEffect(() => {
    if (!remediationId) return;
    let cancelled = false;
    api
      .getRemediation(remediationId)
      .then((p) => {
        if (!cancelled) {
          setProposal(p);
          setProposalError(null);
        }
      })
      .catch((e: Error) => !cancelled && setProposalError(e.message));
    return () => {
      cancelled = true;
    };
  }, [remediationId, aiStatusKey]);

  useEffect(() => {
    if (!aiId) return;
    let cancelled = false;
    setDetailLoading(true);
    api
      .getAiIncident(aiId)
      .then((d) => {
        if (!cancelled) {
          setDetail(d);
          setDetailError(null);
        }
      })
      .catch((e: Error) => !cancelled && setDetailError(e.message))
      .finally(() => !cancelled && setDetailLoading(false));
    return () => {
      cancelled = true;
    };
  }, [aiId, aiStatusKey]);

  const event = useMemo(
    () => detail?.event ?? events.find((e) => e.event_id && e.event_id === incident?.eventId),
    [detail, events, incident?.eventId],
  );
  const executions = useMemo(
    () => (incident?.eventId ? auditLog.filter((a) => a.event_id === incident.eventId).reverse() : []),
    [auditLog, incident?.eventId],
  );
  const related = useMemo(
    () =>
      incident
        ? incidents.filter((o) => o.key !== incident.key && (o.host === incident.host || o.faultDomain === incident.faultDomain)).slice(0, 6)
        : [],
    [incidents, incident],
  );

  const breadcrumb = (
    <>
      <a href={hrefFor('incidents')}>Incidents</a>
      <span aria-hidden>/</span>
      <span className="mono">{incidentKey}</span>
    </>
  );

  if (!incident) {
    return (
      <>
        <PageHeader breadcrumb={breadcrumb} title={loaded ? 'Incident not found' : 'Loading incident…'} />
        <Panel>
          {loaded ? (
            <EmptyState
              title="This incident is not in the controller's current window"
              description="The controller keeps recent state in memory. The incident may have been cleared by a reset or aged out of the last 200 decisions."
              actions={
                <button className="btn" onClick={() => navigate('incidents')}>
                  <ArrowLeft size={14} /> Back to incidents
                </button>
              }
            />
          ) : (
            <div className="stack">
              <div className="skeleton" style={{ width: '40%' }} />
              <div className="skeleton" style={{ width: '70%' }} />
              <div className="skeleton" style={{ width: '55%' }} />
            </div>
          )}
        </Panel>
      </>
    );
  }

  const steps = buildSteps(incident, detail, executions, proposal);
  const awaiting = incident.state === 'awaiting_approval';
  const trace = detail?.trace ?? [];
  const sources = (detail?.context_sources ?? incident.contextSources ?? []).map((s) => (typeof s === 'string' ? s : JSON.stringify(s)));

  const approvalActions = awaiting ? (
    <>
      <button className="btn btn-danger" onClick={() => onRequestApproval(incident, false)}>
        Reject plan
      </button>
      <button className="btn btn-primary" onClick={() => onRequestApproval(incident, true)}>
        Approve plan
      </button>
    </>
  ) : null;

  return (
    <>
      <PageHeader
        breadcrumb={breadcrumb}
        title={incident.title}
        description={
          <span className="row wrap" style={{ gap: 'var(--sp-3)' }}>
            <SeverityTag severity={incident.severity} />
            <StateBadge state={incident.state} />
            <span className="muted">
              Detected {relativeTime(incident.ts)} · <span className="num">{formatDateTime(incident.ts)}</span>
            </span>
          </span>
        }
        actions={approvalActions}
      />

      {awaiting && (
        <Banner tone="warn" title="Approval required before this plan can run">
          The orchestrator proposed <span className="mono">{incident.playbook || 'a playbook'}</span> at{' '}
          {incident.risk || 'unknown'} risk. Every remediation requires sign-off under the shared remediation policy.
        </Banner>
      )}

      <ol className="steps" aria-label="Incident lifecycle">
        {steps.map((s) => (
          <li key={s.name} className={cx('step', s.state)} aria-current={s.state === 'current' ? 'step' : undefined}>
            <span className="step-icon" aria-hidden>
              {STEP_ICON[s.state]}
            </span>
            <span style={{ minWidth: 0 }}>
              <span className="step-name" style={{ display: 'block' }}>
                {s.name}
              </span>
              {s.meta && (
                <span className="step-meta truncate" style={{ display: 'block' }} title={typeof s.meta === 'string' ? s.meta : undefined}>
                  {s.meta}
                </span>
              )}
            </span>
          </li>
        ))}
      </ol>

      <div className="layout-aside">
        <Panel flush>
          <div className="tabs" role="tablist" aria-label="Incident details">
            {(
              [
                ['evidence-policy', 'Evidence & remediation'],
                ['analysis', 'Root cause'],
                ['plan', 'Remediation plan'],
                ['evidence', 'Diagnostic evidence'],
                ['trace', `Agent trace${trace.length ? ` (${trace.length})` : ''}`],
              ] as [Tab, string][]
            ).map(([id, label]) => (
              <button key={id} role="tab" className="tab" aria-selected={tab === id} onClick={() => setTab(id)}>
                {label}
              </button>
            ))}
          </div>

          <div className="panel-body" role="tabpanel">
            {incident.aiId && detailError && (
              <div style={{ marginBottom: 'var(--sp-4)' }}>
                <Banner tone="crit" title="Could not load the analysis record">
                  {detailError}
                </Banner>
              </div>
            )}
            {incident.aiId && detailLoading && !detail ? (
              <div className="stack">
                <div className="skeleton" style={{ width: '50%' }} />
                <div className="skeleton" style={{ width: '80%' }} />
                <div className="skeleton" style={{ width: '65%' }} />
              </div>
            ) : (
              <>
                {tab === 'evidence-policy' && (
                  <div className="stack">
                    {incident.decision.evidence ? (
                      <EvidencePanel evidence={incident.decision.evidence} />
                    ) : (
                      <EmptyState compact title="No deterministic evidence recorded" description="This decision predates the evidence builder." />
                    )}
                    <div className="section-label">Remediation (shared policy)</div>
                    {proposalError && <Banner tone="crit" title="Could not load the remediation proposal">{proposalError}</Banner>}
                    {proposal ? (
                      <RemediationPanel
                        proposal={proposal}
                        onChanged={(p) => {
                          setProposal(p);
                          onChanged?.();
                        }}
                      />
                    ) : (
                      !remediationId && <EmptyState compact title="No remediation proposed" description="No rule, ML or AI candidate was raised for this event." />
                    )}
                  </div>
                )}
                {tab === 'analysis' && <AnalysisTab incident={incident} detail={detail} sources={sources} />}
                {tab === 'plan' && <PlanTab incident={incident} detail={detail} actions={approvalActions} />}
                {tab === 'evidence' && <EvidenceTab event={event} detail={detail} />}
                {tab === 'trace' &&
                  (trace.length === 0 ? (
                    <EmptyState
                      compact
                      title="No agent trace"
                      description={
                        incident.aiId
                          ? 'The orchestrator did not record any steps for this incident.'
                          : 'This incident was raised by the rules engine / ML triage path; the multi-agent workflow did not run.'
                      }
                    />
                  ) : (
                    <ol className="timeline">
                      {trace.map((t, idx) => {
                        const bad = /error|fail|exception/i.test(t.message);
                        return (
                          <li key={idx} className={cx('timeline-item', bad ? 'crit' : 'ok')}>
                            <span className="timeline-marker" aria-hidden />
                            <div style={{ minWidth: 0 }}>
                              <div className="timeline-head">
                                <span className="timeline-agent">{t.agent}</span>
                                <span className="timeline-time">{formatTime(t.ts)}</span>
                              </div>
                              <div className="timeline-msg">{t.message}</div>
                            </div>
                          </li>
                        );
                      })}
                    </ol>
                  ))}
                {detail?.errors && detail.errors.length > 0 && (
                  <div style={{ marginTop: 'var(--sp-4)' }}>
                    <Banner tone="crit" title={`${detail.errors.length} orchestrator error${detail.errors.length === 1 ? '' : 's'}`}>
                      <ul style={{ paddingLeft: 16 }}>
                        {detail.errors.map((e, i) => (
                          <li key={i} className="mono" style={{ fontSize: 'var(--fs-sm)' }}>
                            {e}
                          </li>
                        ))}
                      </ul>
                    </Banner>
                  </div>
                )}
              </>
            )}
          </div>
        </Panel>

        <div className="stack">
          <Panel title="Triage decision">
            <dl className="kv">
              <dt>Host</dt>
              <dd>
                <a className="mono" href={hrefFor('events', undefined, { host: incident.host })}>
                  {incident.host}
                </a>
              </dd>
              <dt>Event</dt>
              <dd>
                {incident.eventId ? (
                  <a className="mono" href={hrefFor('events', undefined, { event: incident.eventId })}>
                    {incident.eventId}
                  </a>
                ) : (
                  '—'
                )}
              </dd>
              <dt>Rule outcome</dt>
              <dd>
                {incident.ruleAction === 'remediate' ? <Badge tone="crit">Threshold breached</Badge> : <Badge>No breach</Badge>}
              </dd>
              <dt>Rule reason</dt>
              <dd className="mono">{incident.ruleReason || '—'}</dd>
              <dt>Log class</dt>
              <dd className="mono">{incident.logClass || '—'}</dd>
              <dt>ML priority</dt>
              <dd>
                <Meter value={incident.mlPriority} title="XGBoost priority score" />
              </dd>
              <dt>Localization</dt>
              <dd className="mono">{incident.decision.ml_localization || '—'}</dd>
              <dt>Fault domain</dt>
              <dd>{domainLabel(incident.faultDomain)}</dd>
              {incident.aiId && (
                <>
                  <dt>Analysis ID</dt>
                  <dd className="mono" style={{ fontSize: 'var(--fs-sm)' }}>
                    {incident.aiId}
                  </dd>
                  <dt>LLM backend</dt>
                  <dd className="mono">{incident.llmBackend || '—'}</dd>
                </>
              )}
            </dl>
          </Panel>

          <Panel title="Execution history" count={executions.length} flush>
            {executions.length === 0 ? (
              <EmptyState compact title="No playbook runs recorded" description="Runs appear here when the controller triggers a playbook for this event." />
            ) : (
              <div className="component-list">
                {executions.map((a, idx) => (
                  <div className="component-row" key={`${a.ts}-${idx}`}>
                    <div style={{ minWidth: 0 }}>
                      <div className="mono truncate">{a.playbook || '—'}</div>
                      <div className="component-detail truncate">{a.reason}</div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <Badge tone="info">{a.status || 'recorded'}</Badge>
                      <div className="component-detail num">{formatTime(a.ts)}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Panel>

          <Panel title="Related incidents" count={related.length} sub="Same host or fault domain" flush>
            <IncidentTable
              incidents={related}
              navigate={navigate}
              columns={['severity', 'incident', 'detected']}
              empty={<EmptyState compact title="No related incidents" />}
            />
          </Panel>
        </div>
      </div>
    </>
  );
};

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------
const AnalysisTab: React.FC<{ incident: Incident; detail: AIIncidentDetail | null; sources: string[] }> = ({ incident, detail, sources }) => {
  const rca = detail?.rca;
  const plan = detail?.plan;

  if (!incident.aiId) {
    return (
      <div className="stack">
        <Banner title="Raised by the rules engine and ML triage">
          The multi-agent analysis engine was not available when this event was processed, so no root-cause analysis was
          produced. The decision below is based on threshold rules and the triage model.
        </Banner>
        <dl className="kv">
          <dt>Rule reason</dt>
          <dd className="mono">{incident.ruleReason || '—'}</dd>
          <dt>Log classifier</dt>
          <dd className="mono">{incident.logClass || '—'}</dd>
          <dt>ML localization</dt>
          <dd className="mono">{incident.decision.ml_localization || '—'}</dd>
          <dt>Selected playbook</dt>
          <dd className="mono">{incident.playbook || '—'}</dd>
        </dl>
      </div>
    );
  }

  const rootCause = rca?.root_cause ?? incident.rootCause;
  const explanation = rca?.explanation ?? incident.explanation;
  const evidence = rca?.evidence ?? [];

  return (
    <div className="stack">
      <div className="kv-inline">
        <div>
          <span className="k">Fault domain</span>
          <span className="strong">{domainLabel(rca?.fault_domain ?? incident.faultDomain)}</span>
        </div>
        <div>
          <span className="k">Confidence</span>
          <Meter value={rca?.confidence ?? incident.confidence} />
        </div>
        <div>
          <span className="k">Reasoning backend</span>
          <span className="mono">{rca?._backend || incident.llmBackend || '—'}</span>
        </div>
      </div>

      <div>
        <div className="section-label">Root cause</div>
        <p style={{ fontSize: 'var(--fs-lg)' }}>{rootCause || <span className="muted">Not determined</span>}</p>
      </div>

      {explanation && (
        <div>
          <div className="section-label">Explanation</div>
          <p style={{ whiteSpace: 'pre-wrap', color: 'var(--text-2)' }}>{explanation}</p>
        </div>
      )}

      {evidence.length > 0 && (
        <div>
          <div className="section-label">Supporting evidence</div>
          <ul style={{ paddingLeft: 18, display: 'grid', gap: 4 }}>
            {evidence.map((e, i) => (
              <li key={i} className="log-line">
                {e}
              </li>
            ))}
          </ul>
        </div>
      )}

      {plan && (plan.steps?.length || plan.reason) && (
        <div>
          <div className="section-label">Investigation plan</div>
          {plan.reason && <p className="muted" style={{ marginBottom: 'var(--sp-2)' }}>{plan.reason}</p>}
          {plan.steps && (
            <div className="row wrap">
              {plan.steps.map((s, i) => (
                <Badge key={i} mono>
                  {i + 1}. {s}
                </Badge>
              ))}
            </div>
          )}
        </div>
      )}

      <div>
        <div className="section-label">Knowledge sources retrieved</div>
        {sources.length === 0 ? (
          <span className="muted">None</span>
        ) : (
          <ul style={{ listStyle: 'none', display: 'grid', gap: 2 }}>
            {sources.map((s, i) => (
              <li key={i} className="mono" style={{ fontSize: 'var(--fs-sm)' }}>
                {s}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};

const PlanTab: React.FC<{ incident: Incident; detail: AIIncidentDetail | null; actions: React.ReactNode }> = ({ incident, detail, actions }) => {
  const rem = detail?.remediation;
  const val = detail?.validation;
  const extraVars = rem?.extra_vars && Object.keys(rem.extra_vars).length ? rem.extra_vars : null;
  const targets = rem?.targets && rem.targets.length ? rem.targets : null;

  if (!incident.playbook && !rem) {
    return (
      <EmptyState
        compact
        title="No remediation plan"
        description="No playbook matched this fault. It needs manual triage by an engineer."
      />
    );
  }

  return (
    <div className="stack">
      <dl className="kv">
        <dt>Playbook</dt>
        <dd className="mono strong">{rem?.playbook ?? incident.playbook ?? '—'}</dd>
        {rem?.strategy && (
          <>
            <dt>Strategy</dt>
            <dd>{rem.strategy}</dd>
          </>
        )}
        <dt>Risk</dt>
        <dd>
          <RiskBadge risk={rem?.risk ?? incident.risk} />
          {rem?.risk_rationale && <div className="muted" style={{ marginTop: 4 }}>{rem.risk_rationale}</div>}
        </dd>
        <dt>Approval</dt>
        <dd>
          {rem?.requires_human_approval === undefined
            ? incident.aiId
              ? '—'
              : 'Not gated (rules path)'
            : rem.requires_human_approval
              ? 'Required'
              : 'Not required'}
        </dd>
        <dt>Plan status</dt>
        <dd>
          <StateBadge state={incident.state} />
        </dd>
        {rem?.rollback && (
          <>
            <dt>Rollback</dt>
            <dd className="mono">{rem.rollback}</dd>
          </>
        )}
      </dl>

      {targets && (
        <div>
          <div className="section-label">Targets</div>
          <pre className="code code-light">{JSON.stringify(targets, null, 2)}</pre>
        </div>
      )}

      {extraVars && (
        <div>
          <div className="section-label">Extra vars</div>
          <pre className="code code-light">{JSON.stringify(extraVars, null, 2)}</pre>
        </div>
      )}

      {detail?.runbook && (
        <div>
          <div className="section-label">Runbook</div>
          <pre className="code code-light">{detail.runbook}</pre>
        </div>
      )}

      {val && Object.keys(val).length > 0 && (
        <div>
          <div className="section-label">Post-remediation validation</div>
          <dl className="kv">
            <dt>Resolved</dt>
            <dd>
              {val.resolved === true ? <Badge tone="ok">Yes</Badge> : val.resolved === false ? <Badge tone="crit">No</Badge> : <span className="muted">Pending</span>}
            </dd>
            <dt>Confidence</dt>
            <dd>{formatPct(val.confidence)}</dd>
            {val.residual_risk && (
              <>
                <dt>Residual risk</dt>
                <dd>{val.residual_risk}</dd>
              </>
            )}
            {val.recommendation && (
              <>
                <dt>Recommendation</dt>
                <dd>{val.recommendation}</dd>
              </>
            )}
          </dl>
        </div>
      )}

      {actions && (
        <div className="row" style={{ justifyContent: 'flex-end', borderTop: '1px solid var(--border)', paddingTop: 'var(--sp-3)' }}>
          {actions}
        </div>
      )}
    </div>
  );
};

export const EventEvidence: React.FC<{ event: TelemetryEvent }> = ({ event }) => {
  const ifaces = Object.entries(event.ifaces || {});
  const packets = event.sample_packets || [];
  return (
    <div className="stack">
      <div className="kv-inline">
        <div>
          <span className="k">Host</span>
          <span className="mono">{event.host}</span>
        </div>
        <div>
          <span className="k">Event</span>
          <span className="mono">{event.event_id}</span>
        </div>
        <div>
          <span className="k">Collected</span>
          <span className="num">{formatDateTime(event.ts)}</span>
        </div>
        <div>
          <span className="k">Iface errors</span>
          <span className="num">{formatNumber(eventErrorCount(event))}</span>
        </div>
      </div>

      <div>
        <div className="section-label">Interfaces</div>
        {ifaces.length === 0 ? (
          <span className="muted">No interface counters in this event</span>
        ) : (
          <div className="table-wrap" style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)' }}>
            <table className="table">
              <thead>
                <tr>
                  <th>Interface</th>
                  <th className="right">RX</th>
                  <th className="right">TX</th>
                  <th className="right">Err in</th>
                  <th className="right">Err out</th>
                  <th className="right">MTU</th>
                </tr>
              </thead>
              <tbody>
                {ifaces.map(([name, s]) => {
                  const mtuOdd = s.mtu !== undefined && s.mtu !== 1500 && s.mtu !== 9000;
                  return (
                    <tr key={name}>
                      <td className="mono">{name}</td>
                      <td className="right num">{formatBytes(s.rx_bytes)}</td>
                      <td className="right num">{formatBytes(s.tx_bytes)}</td>
                      <td className="right num" style={{ color: s.errin ? 'var(--crit)' : undefined }}>
                        {formatNumber(s.errin)}
                      </td>
                      <td className="right num" style={{ color: s.errout ? 'var(--crit)' : undefined }}>
                        {formatNumber(s.errout)}
                      </td>
                      <td className="right num" style={{ color: mtuOdd ? 'var(--warn)' : undefined }} title={mtuOdd ? 'Non-standard MTU' : undefined}>
                        {formatNumber(s.mtu)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {event.rdma && (
        <div>
          <div className="section-label">RDMA counters</div>
          <div className="kv-inline">
            {(['qp_errors', 'rq_errors', 'srq_errors'] as const).map((k) => (
              <div key={k}>
                <span className="k">{k.replace('_', ' ')}</span>
                <span className="num" style={{ color: Number(event.rdma?.[k]) > 0 ? 'var(--crit)' : undefined }}>
                  {formatNumber(event.rdma?.[k])}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div>
        <div className="section-label">Kernel log (dmesg tail)</div>
        {event.dmesg_tail ? <pre className="code">{event.dmesg_tail}</pre> : <span className="muted">Empty</span>}
      </div>

      {packets.length > 0 && (
        <div>
          <div className="section-label">Sample packets</div>
          <div className="table-wrap" style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)' }}>
            <table className="table">
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Destination</th>
                  <th>Proto</th>
                  <th className="right">Length</th>
                </tr>
              </thead>
              <tbody>
                {packets.map((p, i) => (
                  <tr key={i}>
                    <td className="mono">{p.src || '—'}</td>
                    <td className="mono">{p.dst || '—'}</td>
                    <td className="mono">{p.proto || '—'}</td>
                    <td className="right num">{formatNumber(p.len)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

const EvidenceTab: React.FC<{ event?: TelemetryEvent; detail: AIIncidentDetail | null }> = ({ event, detail }) => {
  const signals = detail?.signals && Object.keys(detail.signals).length ? detail.signals : null;
  if (!event && !signals) {
    return (
      <EmptyState
        compact
        title="Telemetry not available"
        description="The originating event is no longer in the controller's event window."
      />
    );
  }
  return (
    <div className="stack">
      {event && (
        <>
          {eventSignal(event) === 'crit' && (
            <Banner tone="crit" title="Event breached rule thresholds">
              Interface errors ≥ 5 or RDMA QP errors ≥ 1 in this sample.
            </Banner>
          )}
          <EventEvidence event={event} />
        </>
      )}
      {signals && (
        <div>
          <div className="section-label">Signals extracted by the analysis engine</div>
          <pre className="code code-light">{JSON.stringify(signals, null, 2)}</pre>
        </div>
      )}
    </div>
  );
};
