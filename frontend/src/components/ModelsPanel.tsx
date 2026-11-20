import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { ModelInfo, ModelsResponse } from '../types';
import { Badge, Banner, EmptyState, Panel } from './ui';

const TITLES: Record<string, string> = {
  host_triage: 'Host triage (XGBoost)',
  log_anomaly: 'Log-line anomaly (XGBoost, BGL)',
  oran_fault: 'DeepORAN backhaul impairment (XGBoost)',
};

const pct = (v?: number | null) => (v === null || v === undefined ? '—' : v.toFixed(3));

const ModelCard: React.FC<{ id: string; info: ModelInfo }> = ({ id, info }) => {
  const c = info.card;
  const metrics = Object.entries(c?.metrics ?? {}).filter(([, m]) => m && typeof m === 'object' && 'f1' in m) as [string, any][];
  return (
    <div className="stack" style={{ borderTop: '1px solid var(--border, #e5e5e5)', paddingTop: 'var(--sp-3)' }}>
      <div className="row wrap">
        <span className="strong">{TITLES[id] ?? id}</span>
        <Badge tone={info.runtime_status === 'loaded' ? 'ok' : info.runtime_status === 'offline' ? 'info' : 'warn'}>{info.runtime_status}</Badge>
        <Badge>{info.used_at_runtime ? 'used at runtime' : 'offline evaluation only'}</Badge>
        {c?.data?.type === 'synthetic' && <Badge tone="warn">synthetic training data</Badge>}
      </div>
      {!c ? (
        <span className="muted">Not trained. See README “Models”.</span>
      ) : (
        <>
          <div className="muted">
            {c.task} · data: {c.data?.dataset ?? c.data?.type} · trained {c.trained_at?.slice(0, 19).replace('T', ' ')} UTC
          </div>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr><th>Evaluation set</th><th>n</th><th>Positives</th><th>Precision</th><th>Recall</th><th>F1</th><th>ROC-AUC</th></tr>
              </thead>
              <tbody>
                {metrics.map(([name, m]) => (
                  <tr key={name}>
                    <td className="mono">{name}</td>
                    <td className="num">{m.n}</td>
                    <td className="num">{m.positives}</td>
                    <td className="num">{pct(m.precision)}</td>
                    <td className="num">{pct(m.recall)}</td>
                    <td className="num">{pct(m.f1)}</td>
                    <td className="num">{pct(m.roc_auc)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ul style={{ paddingLeft: 18 }} className="muted">
            {(c.caveats ?? []).map((x: string, i: number) => <li key={i}>{x}</li>)}
          </ul>
        </>
      )}
    </div>
  );
};

export const ModelsPanel: React.FC = () => {
  const [models, setModels] = useState<ModelsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api.getModels().then(setModels).catch((e: Error) => setError(e.message));
  }, []);
  return (
    <Panel title="Trained models" sub="Metrics are from each model's own held-out split; see caveats before relying on them.">
      {error && <Banner tone="crit" title="Could not load model status">{error}</Banner>}
      {!models && !error && <EmptyState compact title="Loading…" />}
      {models && (
        <div className="stack">
          {Object.entries(models).map(([id, info]) => <ModelCard key={id} id={id} info={info} />)}
        </div>
      )}
    </Panel>
  );
};
