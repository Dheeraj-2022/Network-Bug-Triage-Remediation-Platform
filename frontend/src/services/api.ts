/**
 * Centralized API client for Network Triage FastAPI backend.
 * Uses VITE_API_BASE_URL (defaults to http://127.0.0.1:8000).
 *
 * Never put secrets in VITE_* variables: they are compiled into the public bundle.
 * If the backend sets NBT_API_KEY, the operator types the key at runtime; it is kept
 * in sessionStorage for this tab only.
 */

import {
  AIIncident,
  AIIncidentDetail,
  AIStatus,
  AuditEntry,
  AuthInfo,
  Decision,
  DemoState,
  RemediationProposal,
  SystemStatus,
  TelemetryEvent,
} from '../types';

const BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
export const API_BASE_URL = BASE_URL;

const KEY_STORAGE = 'nbt_api_key';
export const apiKey = {
  get: () => sessionStorage.getItem(KEY_STORAGE) || '',
  set: (value: string) => (value ? sessionStorage.setItem(KEY_STORAGE, value) : sessionStorage.removeItem(KEY_STORAGE)),
};

export class ApiError extends Error {
  status: number;
  body: any;
  constructor(message: string, status: number, body: any) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

async function fetchJson<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
  const key = apiKey.get();
  try {
    const res = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(key ? { 'X-API-Key': key } : {}),
        ...(options?.headers || {}),
      },
    });

    if (!res.ok) {
      let errMsg = `HTTP ${res.status}: ${res.statusText}`;
      let body: any = null;
      try {
        body = await res.json();
        if (body.detail) {
          errMsg = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
        } else if (body.error) {
          errMsg = body.error;
        }
      } catch {
        // Fall back to status text
      }
      throw new ApiError(errMsg, res.status, body);
    }

    return (await res.json()) as T;
  } catch (err: any) {
    if (err.name === 'TypeError' && err.message.includes('fetch')) {
      throw new Error(`Unable to connect to Network Triage API at ${BASE_URL}. Verify backend is running.`);
    }
    throw err;
  }
}

export const api = {
  // Status & Telemetry
  getStatus: () => fetchJson<SystemStatus>('/api/status'),
  getEvents: (limit: number = 50) => fetchJson<TelemetryEvent[]>(`/api/events?limit=${limit}`),
  getDecisions: (limit: number = 50) => fetchJson<Decision[]>(`/api/decisions?limit=${limit}`),
  getAudit: (limit: number = 50) => fetchJson<AuditEntry[]>(`/api/audit?limit=${limit}`),

  // Actions
  injectEvents: (count: number = 5, injectErrors: boolean = true) =>
    fetchJson<{ injected: number; decisions: Decision[] }>('/api/inject', {
      method: 'POST',
      body: JSON.stringify({ count, inject_errors: injectErrors }),
    }),

  processEvent: (event: Partial<TelemetryEvent>) =>
    fetchJson<Decision>('/api/process', {
      method: 'POST',
      body: JSON.stringify(event),
    }),

  loadSampleEvents: () =>
    fetchJson<{ loaded: number; decisions: Decision[] }>('/api/load_sample_events', {
      method: 'POST',
    }),

  // AI Multi-Agent
  getAiStatus: () => fetchJson<AIStatus>('/api/ai/status'),
  getAiIncidents: (limit: number = 50) => fetchJson<AIIncident[]>(`/api/ai/incidents?limit=${limit}`),
  getAiIncident: (id: string) => fetchJson<AIIncidentDetail>(`/api/ai/incident/${encodeURIComponent(id)}`),

  approveAiIncident: (incident_id: string, approved: boolean, approver?: string) =>
    fetchJson<{ ok: boolean; status: string; incident_id: string; remediation_id?: string; validation?: any }>('/api/ai/approve', {
      method: 'POST',
      body: JSON.stringify({ incident_id, approved, ...(approver ? { approver } : {}) }),
    }),

  // Shared remediation policy
  getAuth: () => fetchJson<AuthInfo>('/api/auth'),
  getRemediation: (id: string) => fetchJson<RemediationProposal>(`/api/remediations/${encodeURIComponent(id)}`),
  decideRemediation: (id: string, body: { approved: boolean; approver: string; preview_digest?: string | null; reason?: string }) =>
    fetchJson<RemediationProposal>(`/api/remediations/${encodeURIComponent(id)}/decision`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  verifyRemediation: (id: string) =>
    fetchJson<RemediationProposal>(`/api/remediations/${encodeURIComponent(id)}/verify`, { method: 'POST' }),

  // Deterministic demo (simulated)
  getDemo: () => fetchJson<DemoState>('/api/demo/mtu-two-host'),
  loadDemo: (postCheck: 'pass' | 'fail' | 'inconclusive') =>
    fetchJson<DemoState>('/api/demo/mtu-two-host/load', {
      method: 'POST',
      body: JSON.stringify({ post_check: postCheck }),
    }),
  resetDemo: () => fetchJson<{ ok: boolean }>('/api/demo/mtu-two-host/reset', { method: 'POST' }),

  // Engine Maintenance
  trainModel: () =>
    fetchJson<{ ok: boolean; message?: string; error?: string }>('/api/train', {
      method: 'POST',
    }),

  clearState: () =>
    fetchJson<{ ok: boolean }>('/api/clear', {
      method: 'POST',
    }),
};
