/**
 * Derives operational views (incidents, host health, activity) from the raw
 * backend collections. Nothing here invents data: every field is computed
 * from /api/decisions, /api/events, /api/ai/incidents.
 */
import { AIIncident, Decision, TelemetryEvent } from '../types';
import { domainLabel, parseTs } from './format';

export type Severity = 'P1' | 'P2' | 'P3' | 'P4';

export type IncidentState =
  | 'awaiting_approval'
  | 'manual'
  | 'approved'
  | 'auto'
  | 'dry_run'
  | 'rejected'
  | 'blocked'
  | 'expired'
  | 'execution_failed'
  | 'verification_failed'
  | 'inconclusive'
  | 'resolved';

export interface Incident {
  key: string;
  aiId?: string;
  eventId?: string;
  remediationId?: string;
  simulated: boolean;
  host: string;
  ts: string;
  title: string;
  faultDomain: string;
  severity: Severity;
  state: IncidentState;
  confidence?: number;
  mlPriority: number;
  ruleAction?: string;
  ruleReason?: string;
  logClass?: string;
  playbook?: string | null;
  risk?: string;
  rootCause?: string;
  explanation?: string;
  llmBackend?: string;
  contextSources: any[];
  decision: Decision;
  ai?: AIIncident;
}

export const SEVERITY_ORDER: Record<Severity, number> = { P1: 0, P2: 1, P3: 2, P4: 3 };

export const SEVERITY_HELP =
  'Priority is derived from the XGBoost priority score and the rule-engine outcome: ' +
  'P1 ≥ 0.85 or kernel panic · P2 rule threshold breached or ≥ 0.60 · P3 ≥ 0.30 · P4 otherwise.';

export const STATE_META: Record<IncidentState, { label: string; tone: 'crit' | 'warn' | 'ok' | 'info' | 'neutral'; group: 'action' | 'active' | 'closed' }> = {
  awaiting_approval: { label: 'Approval required', tone: 'warn', group: 'action' },
  manual: { label: 'Manual triage', tone: 'crit', group: 'action' },
  approved: { label: 'Approved', tone: 'info', group: 'active' },
  auto: { label: 'Auto-remediation', tone: 'info', group: 'active' },
  dry_run: { label: 'Playbook dry-run', tone: 'neutral', group: 'active' },
  rejected: { label: 'Plan rejected', tone: 'neutral', group: 'closed' },
  blocked: { label: 'Blocked by policy', tone: 'crit', group: 'action' },
  expired: { label: 'Approval expired', tone: 'neutral', group: 'closed' },
  execution_failed: { label: 'Execution failed', tone: 'crit', group: 'action' },
  verification_failed: { label: 'Post-check failed', tone: 'crit', group: 'action' },
  inconclusive: { label: 'Post-check inconclusive', tone: 'warn', group: 'action' },
  resolved: { label: 'Resolved (verified)', tone: 'ok', group: 'closed' },
};

/** The shared remediation policy is authoritative whenever a proposal exists. */
export function stateFromPolicy(status?: string | null): IncidentState | undefined {
  switch (status) {
    case 'pending_approval':
      return 'awaiting_approval';
    case 'blocked':
      return 'blocked';
    case 'rejected':
      return 'rejected';
    case 'expired':
      return 'expired';
    case 'approved':
    case 'executing':
    case 'verifying':
      return 'approved';
    case 'execution_failed':
      return 'execution_failed';
    case 'verification_failed':
      return 'verification_failed';
    case 'verification_inconclusive':
      return 'inconclusive';
    case 'resolved':
    case 'completed':
      return 'resolved';
    default:
      return undefined;
  }
}

export function severityFor(mlPriority: number, ruleAction?: string, domain?: string): Severity {
  if (mlPriority >= 0.85 || domain === 'KERNEL_PANIC') return 'P1';
  if (ruleAction === 'remediate' || mlPriority >= 0.6) return 'P2';
  if (mlPriority >= 0.3) return 'P3';
  return 'P4';
}

function stateFor(aiStatus: string | undefined, hasAi: boolean): IncidentState {
  switch (aiStatus) {
    case 'pending_approval':
      return 'awaiting_approval';
    case 'approved':
      return 'approved';
    case 'rejected':
      return 'rejected';
    case 'auto':
      return 'auto';
    case 'no_action':
      return 'manual';
    default:
      return hasAi ? 'manual' : 'dry_run';
  }
}

function domainFromRule(reason?: string): string | undefined {
  const r = (reason || '').toLowerCase();
  if (r.includes('rdma')) return 'RDMA_ERROR';
  if (r.includes('mtu')) return 'MTU_MISMATCH';
  if (r.includes('iface')) return 'DRIVER_FAULT';
  return undefined;
}

/** Latest AI record per incident id (approvals append a new record server-side). */
export function latestAiById(aiIncidents: AIIncident[]): Map<string, AIIncident> {
  const map = new Map<string, AIIncident>();
  for (const inc of aiIncidents) {
    if (inc.incident_id) map.set(inc.incident_id, inc);
  }
  return map;
}

export function buildIncidents(decisions: Decision[], aiIncidents: AIIncident[]): Incident[] {
  const aiMap = latestAiById(aiIncidents);
  const out: Incident[] = [];
  const seen = new Set<string>();

  for (const d of decisions) {
    const escalated = !!d.ai?.fault_domain;
    if (!d.remediate && !escalated) continue;

    const aiId = d.ai?.incident_id;
    const key = aiId || `inc-${d.event_id ?? d.ts}`;
    if (seen.has(key)) continue;
    seen.add(key);

    const ai = aiId ? aiMap.get(aiId) : undefined;
    const evidenceDomain = d.evidence?.inference?.fault_domain;
    const faultDomain =
      (evidenceDomain && evidenceDomain !== 'UNKNOWN' ? evidenceDomain : undefined) ||
      ai?.fault_domain ||
      d.ai?.fault_domain ||
      (d.log_class && d.log_class !== 'UNKNOWN' ? d.log_class : undefined) ||
      domainFromRule(d.rule_reason) ||
      'UNKNOWN';
    const mlPriority = d.ml_priority ?? 0;
    const host = d.host || ai?.host || 'unknown-host';

    out.push({
      key,
      aiId,
      eventId: d.event_id,
      remediationId: d.remediation_id ?? undefined,
      simulated: !!d.simulated,
      host,
      ts: d.ts,
      title: `${domainLabel(faultDomain)} on ${host}${d.simulated ? ' (simulated)' : ''}`,
      faultDomain,
      severity: severityFor(mlPriority, d.rule_action, faultDomain),
      state: stateFromPolicy(d.remediation?.status) ?? stateFor(ai?.status ?? d.ai?.status, !!aiId),
      confidence: ai?.confidence ?? d.ai?.confidence,
      mlPriority,
      ruleAction: d.rule_action,
      ruleReason: d.rule_reason,
      logClass: d.log_class,
      playbook: d.remediation?.playbook ?? ai?.playbook ?? d.ai?.ai_playbook ?? d.playbook,
      risk: d.remediation?.risk ?? ai?.risk ?? d.ai?.risk ?? undefined,
      rootCause: ai?.root_cause ?? d.ai?.root_cause,
      explanation: ai?.explanation,
      llmBackend: ai?.llm_backend ?? d.ai?.llm_backend,
      contextSources: ai?.context_sources ?? d.ai?.context_sources ?? [],
      decision: d,
      ai,
    });
  }

  return out.sort(compareIncidents);
}

export function compareIncidents(a: Incident, b: Incident): number {
  const ga = STATE_META[a.state].group === 'action' ? 0 : STATE_META[a.state].group === 'active' ? 1 : 2;
  const gb = STATE_META[b.state].group === 'action' ? 0 : STATE_META[b.state].group === 'active' ? 1 : 2;
  if (ga !== gb) return ga - gb;
  const s = SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity];
  if (s !== 0) return s;
  return (parseTs(b.ts)?.getTime() ?? 0) - (parseTs(a.ts)?.getTime() ?? 0);
}

// ---------------------------------------------------------------------------
// Host health
// ---------------------------------------------------------------------------
export type HealthState = 'faulty' | 'degraded' | 'healthy';

export interface HostHealth {
  host: string;
  state: HealthState;
  reasons: string[];
  lastSeen: string;
  ifaceErrors: number;
  qpErrors: number;
  events: number;
  openIncidents: number;
}

export function eventErrorCount(ev: TelemetryEvent): number {
  return Object.values(ev.ifaces || {}).reduce(
    (sum, s) => sum + (Number(s.errin) || 0) + (Number(s.errout) || 0),
    0,
  );
}

export function eventMtuAnomaly(ev: TelemetryEvent): boolean {
  return Object.values(ev.ifaces || {}).some((s) => s.mtu !== undefined && s.mtu !== 1500 && s.mtu !== 9000);
}

/** Mirrors rules_engine.py thresholds (iface errors ≥ 5, RDMA QP errors ≥ 1). */
export function eventSignal(ev: TelemetryEvent): 'crit' | 'warn' | 'ok' {
  const errs = eventErrorCount(ev);
  const qp = Number(ev.rdma?.qp_errors) || 0;
  if (errs >= 5 || qp >= 1) return 'crit';
  if (errs > 0 || eventMtuAnomaly(ev) || /error|oops|mismatch|fail|panic|reset/i.test(ev.dmesg_tail || '')) return 'warn';
  return 'ok';
}

export function buildHostHealth(events: TelemetryEvent[], incidents: Incident[]): HostHealth[] {
  const latest = new Map<string, TelemetryEvent>();
  const counts = new Map<string, number>();
  for (const ev of events) {
    if (!ev.host) continue;
    counts.set(ev.host, (counts.get(ev.host) || 0) + 1);
    const prev = latest.get(ev.host);
    if (!prev || (parseTs(ev.ts)?.getTime() ?? 0) >= (parseTs(prev.ts)?.getTime() ?? 0)) latest.set(ev.host, ev);
  }

  const openByHost = new Map<string, number>();
  for (const inc of incidents) {
    if (STATE_META[inc.state].group === 'action') openByHost.set(inc.host, (openByHost.get(inc.host) || 0) + 1);
  }

  const rows: HostHealth[] = [];
  for (const [host, ev] of latest) {
    const errs = eventErrorCount(ev);
    const qp = Number(ev.rdma?.qp_errors) || 0;
    const reasons: string[] = [];
    if (errs > 0) reasons.push(`${errs} iface errors`);
    if (qp > 0) reasons.push(`${qp} RDMA QP errors`);
    if (eventMtuAnomaly(ev)) reasons.push('non-standard MTU');
    const signal = eventSignal(ev);
    if (signal !== 'ok' && reasons.length === 0 && ev.dmesg_tail) reasons.push(ev.dmesg_tail.slice(0, 60));
    const open = openByHost.get(host) || 0;
    const state: HealthState = signal === 'crit' ? 'faulty' : signal === 'warn' || open > 0 ? 'degraded' : 'healthy';
    rows.push({
      host,
      state,
      reasons,
      lastSeen: ev.ts,
      ifaceErrors: errs,
      qpErrors: qp,
      events: counts.get(host) || 0,
      openIncidents: open,
    });
  }

  const order: Record<HealthState, number> = { faulty: 0, degraded: 1, healthy: 2 };
  return rows.sort((a, b) => order[a.state] - order[b.state] || a.host.localeCompare(b.host));
}

// ---------------------------------------------------------------------------
// Activity time series (decisions processed per minute)
// ---------------------------------------------------------------------------
export interface ActivityBucket {
  start: number;
  total: number;
  flagged: number;
}

export function buildActivity(decisions: Decision[], minutes = 30, now = Date.now()): { buckets: ActivityBucket[]; end: number } {
  const times = decisions
    .map((d) => ({ t: parseTs(d.ts)?.getTime(), flagged: d.remediate }))
    .filter((x): x is { t: number; flagged: boolean } => typeof x.t === 'number');

  const step = 60_000;
  let end = Math.ceil(now / step) * step;
  const windowStart = end - minutes * step;
  // If nothing landed in the live window, anchor the window on the latest decision instead.
  if (times.length && !times.some((x) => x.t >= windowStart)) {
    end = Math.ceil(Math.max(...times.map((x) => x.t)) / step) * step;
  }
  const start = end - minutes * step;
  const buckets: ActivityBucket[] = Array.from({ length: minutes }, (_, i) => ({ start: start + i * step, total: 0, flagged: 0 }));
  for (const x of times) {
    if (x.t < start || x.t >= end) continue;
    const idx = Math.floor((x.t - start) / step);
    buckets[idx].total += 1;
    if (x.flagged) buckets[idx].flagged += 1;
  }
  return { buckets, end };
}

export function countBy<T>(items: T[], key: (t: T) => string | undefined): { key: string; count: number }[] {
  const m = new Map<string, number>();
  for (const it of items) {
    const k = key(it);
    if (!k) continue;
    m.set(k, (m.get(k) || 0) + 1);
  }
  return [...m.entries()].map(([k, count]) => ({ key: k, count })).sort((a, b) => b.count - a.count);
}
