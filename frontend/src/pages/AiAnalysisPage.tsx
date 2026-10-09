import React, { useState } from 'react';
import {
  Activity,
  Check,
  CheckCircle2,
  Code,
  Cpu,
  Database,
  ExternalLink,
  Layers,
  Search,
  Server,
  Shield,
  Terminal,
  X,
  Zap,
} from 'lucide-react';
import { AIIncident, AIStatus } from '../types';

interface AiAnalysisPageProps {
  aiStatus: AIStatus | null;
  aiIncidents: AIIncident[];
  onApprove: (incidentId: string, approved: boolean) => void;
  isApproving: boolean;
}

export const AiAnalysisPage: React.FC<AiAnalysisPageProps> = ({
  aiStatus,
  aiIncidents,
  onApprove,
  isApproving,
}) => {
  const [selectedIncident, setSelectedIncident] = useState<AIIncident | null>(null);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Page Title */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.4rem',
              padding: '0.15rem 0.5rem',
              backgroundColor: '#131922',
              border: '1px solid #1f2838',
              borderRadius: '2px',
              fontSize: '0.625rem',
              fontFamily: 'var(--font-mono)',
              color: '#38bdf8',
              fontWeight: 600,
              marginBottom: '0.4rem',
            }}
          >
            AUTONOMOUS REASONING ARCHITECTURE
          </div>
          <h1 style={{ fontSize: '1.45rem', fontWeight: 800, letterSpacing: '-0.02em', color: '#f8fafc' }}>
            AI Multi-Agent Reasoning Subsystem
          </h1>
          <p style={{ fontSize: '0.775rem', color: '#94a3b8', marginTop: '0.2rem' }}>
            Structured, deterministic agent graph utilizing Google Vertex AI Gemini, hybrid vector retrieval, and contextual memory.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <span className="noc-badge noc-badge-ok">
            ● BACKEND: {aiStatus?.llm_backend || 'HEURISTIC (OFFLINE)'}
          </span>
        </div>
      </div>

      {/* Engineering Pipeline Topology Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.75rem' }}>
        {/* Card 1: LLM Engine */}
        <div className="noc-card" style={{ padding: '0.85rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <span style={{ fontSize: '0.6875rem', color: '#94a3b8' }}>LLM Backend</span>
            <Cpu size={14} style={{ color: '#38bdf8' }} />
          </div>
          <div style={{ fontSize: '1.15rem', fontWeight: 800, color: '#f1f5f9', fontFamily: 'var(--font-mono)', margin: '0.2rem 0' }}>
            {aiStatus?.uses_llm ? 'Vertex AI Gemini' : 'Heuristic Engine'}
          </div>
          <div style={{ fontSize: '0.6875rem', color: '#64748b' }}>
            {aiStatus?.vertex_model || 'Deterministic offline reasoner'}
          </div>
        </div>

        {/* Card 2: Hybrid Retrieval */}
        <div className="noc-card" style={{ padding: '0.85rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <span style={{ fontSize: '0.6875rem', color: '#94a3b8' }}>Vector Retrieval</span>
            <Database size={14} style={{ color: '#10b981' }} />
          </div>
          <div style={{ fontSize: '1.15rem', fontWeight: 800, color: '#10b981', fontFamily: 'var(--font-mono)', margin: '0.2rem 0' }}>
            {aiStatus?.retriever_backend === 'chromadb' ? 'ChromaDB' : 'Numpy Cosine Store'}
          </div>
          <div style={{ fontSize: '0.6875rem', color: '#64748b' }}>
            Runbooks & Hardware Errata Indexed
          </div>
        </div>

        {/* Card 3: Memory Store */}
        <div className="noc-card" style={{ padding: '0.85rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <span style={{ fontSize: '0.6875rem', color: '#94a3b8' }}>Persistent Memory</span>
            <Server size={14} style={{ color: '#f59e0b' }} />
          </div>
          <div style={{ fontSize: '1.15rem', fontWeight: 800, color: '#f59e0b', fontFamily: 'var(--font-mono)', margin: '0.2rem 0' }}>
            {aiStatus?.memory?.incidents || 106} Incidents
          </div>
          <div style={{ fontSize: '0.6875rem', color: '#64748b' }}>
            {aiStatus?.memory?.hosts_tracked || 11} Hosts • {aiStatus?.memory?.fault_domains || 3} Domains
          </div>
        </div>

        {/* Card 4: Orchestrator Graph */}
        <div className="noc-card" style={{ padding: '0.85rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <span style={{ fontSize: '0.6875rem', color: '#94a3b8' }}>Agent Graph</span>
            <Layers size={14} style={{ color: '#38bdf8' }} />
          </div>
          <div style={{ fontSize: '1.15rem', fontWeight: 800, color: '#38bdf8', fontFamily: 'var(--font-mono)', margin: '0.2rem 0' }}>
            8 Specialized Agents
          </div>
          <div style={{ fontSize: '0.6875rem', color: '#64748b' }}>
            ADK / LangGraph-style workflow
          </div>
        </div>
      </div>

      {/* Recent AI Incidents Table */}
      <div className="noc-card">
        <div className="noc-card-header">
          <div className="noc-card-title">
            <Cpu size={13} style={{ color: '#38bdf8' }} />
            Recent AI Multi-Agent Reasoning Incidents
          </div>
          <span style={{ fontSize: '0.6875rem', color: '#64748b', fontFamily: 'var(--font-mono)' }}>
            Total: {aiIncidents.length}
          </span>
        </div>

        <div className="noc-table-wrapper">
          <table className="noc-table">
            <thead>
              <tr>
                <th style={{ width: '80px' }}>TIME</th>
                <th style={{ width: '90px' }}>HOST</th>
                <th style={{ width: '130px' }}>FAULT DOMAIN</th>
                <th>ROOT CAUSE ANALYSIS</th>
                <th style={{ width: '75px' }}>CONF.</th>
                <th style={{ width: '140px' }}>PLAYBOOK</th>
                <th style={{ width: '75px' }}>RISK</th>
                <th style={{ width: '110px' }}>STATUS</th>
                <th style={{ width: '90px', textAlign: 'right' }}>ACTIONS</th>
              </tr>
            </thead>
            <tbody>
              {aiIncidents.length > 0 ? (
                aiIncidents.slice().reverse().map((inc) => {
                  const isPending = inc.status === 'pending_approval';
                  const riskColor = inc.risk === 'high' ? '#f43f5e' : inc.risk === 'medium' ? '#f59e0b' : '#10b981';

                  return (
                    <tr key={inc.incident_id}>
                      <td style={{ fontFamily: 'var(--font-mono)', color: '#94a3b8' }}>
                        {inc.ts ? inc.ts.slice(11, 19) : '--'}
                      </td>
                      <td style={{ fontWeight: 600, color: '#f1f5f9' }}>{inc.host || '--'}</td>
                      <td>
                        <span className="noc-badge noc-badge-med">
                          {inc.fault_domain || 'UNKNOWN'}
                        </span>
                      </td>
                      <td style={{ color: '#cbd5e1', fontSize: '0.725rem' }}>
                        {inc.root_cause || inc.explanation || 'Root cause correlation pending full telemetry convergence.'}
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: '#10b981' }}>
                        {inc.confidence != null ? Number(inc.confidence).toFixed(2) : '--'}
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', color: '#38bdf8', fontSize: '0.725rem' }}>
                        {inc.playbook || '--'}
                      </td>
                      <td>
                        <span style={{ color: riskColor, fontWeight: 700, fontFamily: 'var(--font-mono)', fontSize: '0.6875rem' }}>
                          {inc.risk || '--'}
                        </span>
                      </td>
                      <td>
                        <span
                          className="noc-badge"
                          style={{
                            backgroundColor: isPending ? 'rgba(245, 158, 11, 0.15)' : 'rgba(16, 185, 129, 0.15)',
                            color: isPending ? '#f59e0b' : '#10b981',
                            borderColor: isPending ? '#f59e0b' : '#10b981',
                          }}
                        >
                          {inc.status || '--'}
                        </span>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <button
                          onClick={() => setSelectedIncident(inc)}
                          className="noc-btn noc-btn-outline"
                          style={{ padding: '0.2rem 0.5rem', fontSize: '0.625rem' }}
                        >
                          <Terminal size={11} /> Trace
                        </button>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={9} style={{ textAlign: 'center', padding: '2rem', color: '#64748b' }}>
                    No AI multi-agent incidents recorded. Trigger event injection to execute the reasoning pipeline.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Detail Trace Inspector Modal */}
      {selectedIncident && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(5, 7, 10, 0.8)',
            backdropFilter: 'blur(3px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
          }}
        >
          <div
            className="noc-card"
            style={{ width: '640px', maxHeight: '80vh', display: 'flex', flexDirection: 'column' }}
          >
            <div className="noc-card-header">
              <div className="noc-card-title">
                <Terminal size={14} style={{ color: '#38bdf8' }} />
                AGENT EXECUTION TRACE: {selectedIncident.incident_id}
              </div>
              <button
                onClick={() => setSelectedIncident(null)}
                style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer' }}
              >
                <X size={15} />
              </button>
            </div>
            <div
              style={{
                padding: '1rem',
                backgroundColor: '#090c10',
                overflowY: 'auto',
                fontFamily: 'var(--font-mono)',
                fontSize: '0.725rem',
                color: '#38bdf8',
                whiteSpace: 'pre-wrap',
                flex: 1,
              }}
            >
              {JSON.stringify(selectedIncident, null, 2)}
            </div>
            <div
              style={{
                padding: '0.65rem 1rem',
                borderTop: '1px solid #1c222e',
                display: 'flex',
                justifyContent: 'flex-end',
                gap: '0.5rem',
              }}
            >
              <button onClick={() => setSelectedIncident(null)} className="noc-btn noc-btn-outline">
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
