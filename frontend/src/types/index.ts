/**
 * Core type definitions for Network Triage NOC Frontend.
 * Aligns with FastAPI backend schemas and Stitch UI design specifications.
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
  // UI enrichment fields
  severity?: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';
  protocol?: string;
  source_ip?: string;
  status?: string;
  correlated_incident?: string;
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
  ai?: {
    incident_id?: string;
    llm_backend?: string;
    fault_domain?: string;
    root_cause?: string;
    confidence?: number;
    ai_playbook?: string;
    risk?: string;
    status?: string;
    context_sources?: any[];
  };
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
  uses_llm?: boolean;
  vertex_model?: string;
  retriever_backend?: string;
  require_human_approval?: boolean;
  memory?: {
    conversations?: number;
    fault_domains?: number;
    hosts_tracked?: number;
    incidents?: number;
  };
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

export interface CorrelatedIncident {
  id: string;
  title: string;
  severity: 'CRITICAL' | 'HIGH' | 'MED' | 'LOW';
  status: 'Investigating' | 'RCA Ready' | 'Action Req.' | 'Monitoring' | 'Resolved';
  source: string;
  targetInterface: string;
  mlConfidence: number;
  timestamp: string;
  lossMetric?: string;
  queueMetric?: string;
  detectedTime: string;
  affectedHost: string;
}

export interface IncidentEvidenceSignal {
  timestamp: string;
  metric: string;
  observed: string;
  nominal: string;
  origin: string;
  state: 'CRIT' | 'WARN' | 'NORMAL';
}

export interface IncidentAgentTraceItem {
  agent: string;
  timestamp: string;
  action: string;
  detail: string;
  status: 'completed' | 'active' | 'pending';
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
