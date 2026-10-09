/**
 * Centralized API client for Network Triage FastAPI backend.
 * Uses VITE_API_BASE_URL (defaults to http://127.0.0.1:8000).
 */

import {
  AIIncident,
  AIStatus,
  AuditEntry,
  Decision,
  SystemStatus,
  TelemetryEvent,
} from '../types';

const BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');

async function fetchJson<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
  try {
    const res = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(options?.headers || {}),
      },
    });

    if (!res.ok) {
      let errMsg = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const errJson = await res.json();
        if (errJson.detail) {
          errMsg = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail);
        } else if (errJson.error) {
          errMsg = errJson.error;
        }
      } catch {
        // Fall back to status text
      }
      throw new Error(errMsg);
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
  getAiIncident: (id: string) => fetchJson<any>(`/api/ai/incident/${id}`),

  approveAiIncident: (incident_id: string, approved: boolean) =>
    fetchJson<{ ok: boolean; status: string; incident_id: string; validation?: any }>('/api/ai/approve', {
      method: 'POST',
      body: JSON.stringify({ incident_id, approved }),
    }),

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
