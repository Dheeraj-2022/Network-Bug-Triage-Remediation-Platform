import React, { useMemo } from 'react';
import { RefreshCw } from 'lucide-react';
import { Badge, Banner, EmptyState, PageHeader, Panel, StatusDot } from '../components/ui';
import { countBy, Incident } from '../lib/incidents';
import { domainLabel, formatNumber, formatPct, formatSeconds } from '../lib/format';
import { AIStatus, SystemStatus } from '../types';
import { CommonPageProps } from './common';

interface Props extends CommonPageProps {
  aiStatus: AIStatus | null;
  status: SystemStatus | null;
  incidents: Incident[];
  onTrainModel: () => void;
  isTraining: boolean;
}

export const AiAnalysisPage: React.FC<Props> = ({ aiStatus, status, incidents, onTrainModel, isTraining, loaded }) => {
  const analysed = useMemo(() => incidents.filter((i) => i.aiId), [incidents]);
  const domains = useMemo(() => countBy(analysed, (i) => i.faultDomain), [analysed]);
  const avgConfidence = useMemo(() => {
    const vals = analysed.map((i) => i.confidence).filter((c): c is number => typeof c === 'number');
    return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : undefined;
  }, [analysed]);
  const confidenceByDomain = useMemo(() => {
    const m = new Map<string, number[]>();
    for (const i of analysed) {
      if (typeof i.confidence !== 'number') continue;
      m.set(i.faultDomain, [...(m.get(i.faultDomain) || []), i.confidence]);
    }
    return m;
  }, [analysed]);

  const latency = Object.entries(aiStatus?.metrics?.avg_latency_seconds || {}).sort((a, b) => b[1] - a[1]);
  const counters = Object.entries(aiStatus?.metrics?.counters || {}).sort((a, b) => a[0].localeCompare(b[0]));
  const maxLatency = Math.max(0, ...latency.map(([, v]) => v));
  const modelMsg = (status?.model_status as any)?.message as string | undefined;
  const mem = aiStatus?.memory;

  return (
    <>
      <PageHeader
        title="Analysis engine"
        description="Configuration and runtime metrics for the ML triage model and the multi-agent root-cause workflow."
      />

      {aiStatus && !aiStatus.enabled && (
        <Banner tone={aiStatus.error ? 'crit' : 'warn'} title="Multi-agent analysis is disabled">
          {aiStatus.error || aiStatus.reason || 'The orchestrator is not available.'} Incidents are raised by the rules engine and ML
          triage only; no root-cause analysis or approval gate is applied.
        </Banner>
      )}

      <div className="grid-2">
        <Panel
          title="Triage model"
          actions={
            <button className="btn btn-sm" onClick={onTrainModel} disabled={isTraining}>
              <RefreshCw size={14} className={isTraining ? 'spin' : undefined} />
              {isTraining ? 'Training…' : status?.model_trained ? 'Retrain' : 'Train model'}
            </button>
          }
        >
          <dl className="kv">
            <dt>State</dt>
            <dd>
              {!status ? (
                '—'
              ) : status.model_trained ? (
                <StatusDot tone="ok" label="Trained" />
              ) : (
                <StatusDot tone="warn" label="Not trained — heuristic fallback in use" />
              )}
            </dd>
            <dt>Model</dt>
            <dd>XGBoost priority classifier</dd>
            <dt>Flag threshold</dt>
            <dd className="num">priority ≥ 0.85</dd>
            {modelMsg && (
              <>
                <dt>Last message</dt>
                <dd className="muted">{modelMsg}</dd>
              </>
            )}
            <dt>Decisions</dt>
            <dd className="num">{formatNumber(status?.total_decisions)}</dd>
          </dl>
        </Panel>

        <Panel title="Orchestrator">
          {!aiStatus ? (
            loaded ? <EmptyState compact title="Status unavailable" /> : <div className="skeleton" style={{ width: '60%' }} />
          ) : (
            <dl className="kv">
              <dt>State</dt>
              <dd>{aiStatus.enabled ? <StatusDot tone="ok" label="Enabled" /> : <StatusDot tone="neutral" label="Disabled" />}</dd>
              <dt>LLM backend</dt>
              <dd className="mono">
                {aiStatus.llm_backend || '—'}
                {aiStatus.llm_impl ? ` (${aiStatus.llm_impl})` : ''}
              </dd>
              {aiStatus.vertex_model && (
                <>
                  <dt>Model</dt>
                  <dd className="mono">{aiStatus.vertex_model}</dd>
                </>
              )}
              <dt>Uses LLM</dt>
              <dd>{aiStatus.uses_llm === undefined ? '—' : aiStatus.uses_llm ? 'Yes' : 'No — deterministic reasoning'}</dd>
              <dt>Retriever</dt>
              <dd className="mono">{aiStatus.retriever_backend || '—'}</dd>
              <dt>Executor</dt>
              <dd className="mono">{aiStatus.executor || '—'}</dd>
              <dt>Approval policy</dt>
              <dd>{aiStatus.require_human_approval ? 'All plans' : 'Medium / high risk only'}</dd>
              <dt>Prometheus</dt>
              <dd>{aiStatus.metrics?.prometheus ? 'Exporting' : 'Not configured'}</dd>
            </dl>
          )}
        </Panel>
      </div>

      <div className="stat-strip">
        <div className="stat">
          <div className="stat-label">Incidents analysed</div>
          <div className="stat-value">{formatNumber(status?.ai_incidents ?? analysed.length)}</div>
        </div>
        <div className="stat">
          <div className="stat-label">Mean RCA confidence</div>
          <div className="stat-value">{formatPct(avgConfidence)}</div>
          <div className="stat-meta">Across incidents in current window</div>
        </div>
        <div className="stat">
          <div className="stat-label">Hosts tracked</div>
          <div className="stat-value">{formatNumber(mem?.hosts_tracked)}</div>
          <div className="stat-meta">Incident memory</div>
        </div>
        <div className="stat">
          <div className="stat-label">Fault domains seen</div>
          <div className="stat-value">{formatNumber(mem?.fault_domains)}</div>
        </div>
        <div className="stat">
          <div className="stat-label">Stored incidents</div>
          <div className="stat-value">{formatNumber(mem?.incidents)}</div>
          <div className="stat-meta">{formatNumber(mem?.conversations)} conversations</div>
        </div>
      </div>

      <div className="grid-2">
        <Panel title="Root cause by fault domain" sub="Incidents analysed in the current window" flush>
          {domains.length === 0 ? (
            <EmptyState compact title="No analysed incidents" />
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Fault domain</th>
                  <th className="right" style={{ width: 80 }}>
                    Incidents
                  </th>
                  <th className="right" style={{ width: 130 }}>
                    Mean confidence
                  </th>
                </tr>
              </thead>
              <tbody>
                {domains.map((d) => {
                  const vals = confidenceByDomain.get(d.key) || [];
                  const mean = vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : undefined;
                  return (
                    <tr key={d.key}>
                      <td>{domainLabel(d.key)}</td>
                      <td className="right num">{d.count}</td>
                      <td className="right num">{formatPct(mean)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </Panel>

        <Panel title="Agent latency" sub="Mean wall-clock time per agent step">
          {latency.length === 0 ? (
            <EmptyState compact title="No latency samples yet" />
          ) : (
            <div className="barlist">
              {latency.map(([k, v]) => (
                <div className="barlist-row wide-value" key={k}>
                  <span className="mono truncate" title={k}>
                    {k}
                  </span>
                  <span className="barlist-track">
                    <span className="barlist-fill" style={{ width: `${maxLatency ? (v / maxLatency) * 100 : 0}%`, display: 'block' }} />
                  </span>
                  <span className="num" style={{ textAlign: 'right' }}>
                    {formatSeconds(v)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>

      {counters.length > 0 && (
        <Panel title="Counters" flush>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Metric</th>
                  <th className="right" style={{ width: 120 }}>
                    Value
                  </th>
                </tr>
              </thead>
              <tbody>
                {counters.map(([k, v]) => (
                  <tr key={k}>
                    <td className="mono">{k}</td>
                    <td className="right num">
                      {formatNumber(v)}
                      {/error|fail/i.test(k) && v > 0 && (
                        <>
                          {' '}
                          <Badge tone="crit">!</Badge>
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
    </>
  );
};
