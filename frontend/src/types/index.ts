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
}

export interface AuditEntry {
  ts: string;
  event_id?: string;
  host?: string;
  playbook?: string | null;
  reason?: string;
  status?: string;
}

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
  | 'events'
  | 'incidents'
  | 'incident-detail'
  | 'decisions'
  | 'remediation'
  | 'ai-analysis'
  | 'audit-trail';
