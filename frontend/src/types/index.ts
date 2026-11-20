/**
 * Types mirroring the FastAPI contracts in schemas.py / api/service.py.
 */

export interface ModelStatus {
  trained: boolean;
  message: string;
}

export interface SystemStatus {
  total_events: number;
  total_decisions: number;
  remediations: number;
  model_trained: boolean;
  model_status: ModelStatus | Record<string, any>;
  ai_incidents: number;
}

export interface IfaceStats {
  rx_bytes?: number;
  tx_bytes?: number;
  errin?: number;
  errout?: number;
  mtu?: number;
}

export interface RdmaStats {
  qp_errors?: number;
  rq_errors?: number;
  srq_errors?: number;
}

export interface PacketSample {
  src?: string;
  dst?: string;
  len?: number;
  proto?: string;
}

export interface TelemetryEvent {
  event_id: string;
  host: string;
  ts: string;
  ifaces?: Record<string, IfaceStats>;
  rdma?: RdmaStats;
  dmesg_tail?: string;
  sample_packets?: PacketSample[];
  simulated?: boolean;
  scenario_id?: string;
  source?: string;
  role?: string;
}

export interface DecisionAI {
  incident_id?: string;
  llm_backend?: string;
  fault_domain?: string;
  root_cause?: string;
  confidence?: number;
  ai_playbook?: string;
  risk?: string;
  status?: string;
  context_sources?: any[];
}

export interface Decision {
  ts: string;
  host?: string;
  event_id?: string;
  rule_action?: string;
  rule_reason?: string;
  log_class?: string;
  ml_priority?: number;
  ml_localization?: string;
  remediate: boolean;
  playbook?: string | null;
  ai?: DecisionAI | null;
  simulated?: boolean;
  scenario_id?: string | null;
  remediation_id?: string | null;
  remediation?: RemediationSummary | null;
  evidence?: Evidence | null;
}

export interface AuditEntry {
  ts: string;
  event_id?: string;
  host?: string;
  playbook?: string | null;
  reason?: string;
  status?: string;
  remediation_id?: string | null;
  mode?: string | null;
  scenario_id?: string | null;
}

// ---------------------------------------------------------------------------
// Deterministic evidence (controller/evidence.py)
// ---------------------------------------------------------------------------
export interface EvidenceSource {
  type: 'telemetry' | 'topology' | 'config' | 'log' | string;
  ref?: string | null;
  host?: string | null;
  ts?: string | null;
  simulated?: boolean;
  topology_id?: string;
  origin?: string;
  compared_with?: string;
}

export interface EvidenceFact {
  id: string;
  kind: 'telemetry' | 'config' | 'topology' | 'log' | string;
  statement: string;
  source: EvidenceSource;
  entity?: string;
  attribute?: string;
  value?: unknown;
  tags?: string[];
}

export interface PeerResolution {
  resolved: boolean;
  reason?: string;
  entity_id?: string;
  device?: string;
  port?: string;
  configured_mtu?: number | null;
  shared?: boolean;
  note?: string;
}

export interface LocalizedInterface {
  name: string;
  resolved: boolean;
  entity_id?: string | null;
  driver?: string | null;
  peer: PeerResolution;
}

export interface PathHop {
  entity_id: string;
  kind?: string | null;
  name?: string | null;
  device?: string | null;
}

export interface TopologyPath {
  id: string;
  required_mtu?: number | null;
  purpose?: string | null;
  hops: PathHop[];
}

export interface MtuCheck {
  host: string;
  iface: string;
  expected: number | null;
  observed: number | null;
  status: 'mismatch' | 'match' | 'unavailable';
  reason: string;
  facts: string[];
}

export interface CounterObservation {
  entity: string;
  counter: string;
  before: number | null;
  after: number;
  delta: number | null;
  window_s: number | null;
  fact: string;
}

export interface ChangeCorrelation {
  change_id: string;
  ts: string;
  entity: string;
  attribute: string;
  old_value?: unknown;
  new_value?: unknown;
  summary?: string;
  actor?: string;
  age_s: number | null;
  relevance: 'relevant' | 'possibly_related' | 'unrelated' | 'unknown';
  relevance_score: number;
  factors: string[];
}

export interface ScopeEntry {
  entity_id: string;
  label: string;
  reason: string;
}

export interface Evidence {
  version: number;
  simulated: boolean;
  event_id?: string;
  observed_facts: EvidenceFact[];
  localization: {
    status: 'resolved' | 'partial' | 'unresolved' | 'host_only';
    host: { name?: string; resolved: boolean; entity_id?: string | null; topology_id?: string | null; simulated_topology?: boolean };
    interfaces: LocalizedInterface[];
    paths: TopologyPath[];
  };
  mtu_checks: MtuCheck[];
  counters: CounterObservation[];
  log_lines: { line_no: number; text: string; tags: string[]; fact: string }[];
  inference: {
    method: string;
    fault_domain: string;
    status: 'confirmed' | 'suspected' | 'undetermined';
    statement: string;
    reasoning: { step: string; because: string[] }[];
  };
  confidence: {
    level: 'high' | 'medium' | 'low';
    checks: { name: string; passed: boolean; detail: string }[];
    supporting_checks: number;
    total_checks: number;
    limitations: string[];
    note: string;
  };
  scope: { direct: ScopeEntry[]; blast_radius: ScopeEntry[] };
  change_correlation: { items: ChangeCorrelation[]; note: string; window_s: number };
  remediation_hint?: { action: string; targets: { host: string; iface: string }[]; desired_mtu: number } | null;
  model_explanation?: {
    label: string;
    backend?: string;
    fault_domain?: string;
    root_cause?: string;
    explanation?: string;
    model_reported_confidence?: number;
    note: string;
  } | null;
  model_signals?: LogAnomalySignal[];
}

// ---------------------------------------------------------------------------
// Shared remediation policy (controller/remediation)
// ---------------------------------------------------------------------------
export type RemediationStatus =
  | 'pending_approval'
  | 'blocked'
  | 'rejected'
  | 'expired'
  | 'approved'
  | 'executing'
  | 'execution_failed'
  | 'verifying'
  | 'verification_failed'
  | 'verification_inconclusive'
  | 'resolved'
  | 'completed';

export interface RemediationSummary {
  id: string;
  status: RemediationStatus;
  action?: string | null;
  playbook?: string | null;
  targets?: Record<string, any>[] | null;
  risk?: string | null;
  mode?: string;
  requires_approval: boolean;
  block_reason?: string | null;
  outcome?: string | null;
  recommenders?: string[];
}

export interface RemediationPreview {
  action: string;
  description: string;
  playbook: string;
  mode: string;
  simulated: boolean;
  targets: Record<string, any>[];
  limit: string[];
  params: Record<string, any>;
  extra_vars: Record<string, any>;
  changes_state: boolean;
  risk: string;
  risk_rationale: string;
  requires_approval: boolean;
  shared_infrastructure_changed: boolean;
  blast_radius: ScopeEntry[];
  rollback: string;
  post_check: string;
  command_preview: string;
  ignored_inputs: string[];
}

export interface VerificationCheck {
  name: string;
  target: string;
  expected: unknown;
  observed: unknown;
  status: 'pass' | 'fail' | 'inconclusive';
  sources: string[];
}

export interface RemediationAudit {
  seq: number;
  ts: string;
  proposal_id: string | null;
  scenario_id: string | null;
  kind: string;
  actor: string | null;
  detail: Record<string, any>;
}

export interface RemediationProposal {
  id: string;
  created_at: string;
  expires_at: string;
  status: RemediationStatus;
  source: string;
  incident_ref?: string | null;
  event_id?: string | null;
  host?: string | null;
  scenario_id?: string | null;
  simulated_evidence: boolean;
  mode: string;
  recommenders: string[];
  candidates_considered: { recommender?: string; requested?: string; accepted: boolean; reason: string }[];
  block_reason?: string | null;
  preview?: RemediationPreview | null;
  preview_digest?: string | null;
  diagnosis: { fault_domain?: string; status?: string; statement?: string; confidence?: string };
  decision?: { approved: boolean; approver: string; ts: string; reason?: string | null } | null;
  execution?: { ok: boolean; mode: string; simulated: boolean; detail: string; ts?: string; phases: any[] } | null;
  verification?: {
    outcome: 'passed' | 'failed' | 'inconclusive' | 'not_applicable';
    checks: VerificationCheck[];
    samples_used: string[];
    summary: string;
    note?: string;
    simulated_samples?: boolean;
    ts?: string;
  } | null;
  audit?: RemediationAudit[];
}

export interface TopologyNode {
  id: string;
  kind: 'host' | 'interface' | 'switch' | 'switch_port';
  name: string;
  host?: string;
  switch?: string;
  intended_mtu?: number;
  peer?: string | null;
  shared?: boolean;
}

export interface TopologyView {
  topology_id: string;
  label?: string;
  simulated: boolean;
  source?: string;
  nodes: TopologyNode[];
  links: { a: string; b: string; kind: string }[];
  paths: { id: string; hops: string[]; required_mtu?: number; purpose?: string; endpoints?: string[] }[];
}

export interface DemoState {
  scenario_id: string;
  title: string;
  simulated: true;
  disclaimer: string;
  story: string[];
  scenario_clock: string;
  loaded: boolean;
  post_check_variant: 'pass' | 'fail' | 'inconclusive' | null;
  variants: string[];
  topology: TopologyView | null;
  changes: Record<string, any>[];
  events: TelemetryEvent[];
  decision: Decision | null;
  proposal: RemediationProposal | null;
  audit: RemediationAudit[];
}

export interface AuthInfo {
  api_key_required: boolean;
  remediation_mode: string;
  note: string;
}

export interface LogAnomalySignal {
  label: 'model-generated';
  model: string;
  trained_on: string;
  max_score: number;
  threshold: number;
  flagged: boolean;
  top_line: string;
  lines: { line: string; score: number }[];
  note: string;
}

export interface ModelInfo {
  runtime_status: string;
  used_at_runtime: boolean;
  card: Record<string, any> | null;
}

export type ModelsResponse = Record<string, ModelInfo>;

export interface AIStatus {
  enabled: boolean;
  llm_backend?: string;
  llm_impl?: string | null;
  executor?: string;
  uses_llm?: boolean;
  vertex_model?: string | null;
  retriever_backend?: string | null;
  require_human_approval?: boolean;
  memory?: {
    conversations?: number;
    fault_domains?: number;
    hosts_tracked?: number;
    incidents?: number;
  } | null;
  metrics?: {
    avg_latency_seconds?: Record<string, number>;
    counters?: Record<string, number>;
    prometheus?: boolean;
  };
  reason?: string;
  error?: string;
}

export interface AIIncident {
  incident_id: string;
  ts?: string;
  host?: string;
  event_id?: string;
  llm_backend?: string;
  fault_domain?: string;
  root_cause?: string;
  confidence?: number;
  explanation?: string;
  playbook?: string;
  risk?: string;
  status?: string;
  requires_human_approval?: boolean;
  context_sources?: any[];
  remediation_id?: string | null;
  simulated?: boolean;
}

export interface TraceStep {
  ts: string;
  agent: string;
  message: string;
  data?: any;
}

/** Full orchestrator result returned by GET /api/ai/incident/{id}. */
export interface AIIncidentDetail {
  ts?: string;
  incident_id: string;
  event?: TelemetryEvent;
  host?: string;
  event_id?: string;
  llm_backend?: string;
  plan?: { escalate?: boolean; steps?: string[]; reason?: string };
  signals?: Record<string, any>;
  runbook?: string | null;
  rca?: {
    root_cause?: string;
    fault_domain?: string;
    confidence?: number;
    evidence?: string[];
    explanation?: string;
    _backend?: string;
    [k: string]: any;
  };
  remediation?: {
    playbook?: string | null;
    strategy?: string;
    extra_vars?: Record<string, any>;
    risk?: string;
    risk_rationale?: string;
    requires_human_approval?: boolean;
    rollback?: string;
    targets?: Record<string, any>[];
    status?: string;
    [k: string]: any;
  };
  validation?: {
    resolved?: boolean | null;
    confidence?: number;
    residual_risk?: string;
    recommendation?: string;
    [k: string]: any;
  };
  context_sources?: string[];
  trace?: TraceStep[];
  errors?: string[];
}

export type PageId =
  | 'overview'
  | 'demo'
  | 'events'
  | 'incidents'
  | 'incident-detail'
  | 'decisions'
  | 'remediation'
  | 'ai-analysis'
  | 'audit-trail';
