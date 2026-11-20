import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { FlaskConical, RotateCcw, Trash2 } from 'lucide-react';
import { AuditTimeline, EvidencePanel, RemediationPanel } from '../components/EvidenceViews';
import { Badge, Banner, EmptyState, PageHeader, Panel, Segmented, cx } from '../components/ui';
import { formatTime } from '../lib/format';
import { api } from '../services/api';
import { DemoState, IfaceStats, TelemetryEvent, TopologyNode } from '../types';
import { CommonPageProps } from './common';

type Variant = 'pass' | 'fail' | 'inconclusive';

interface Props extends CommonPageProps {
  onChanged: () => void;
  onToast: (type: 'success' | 'error' | 'info', title: string, message?: string) => void;
}

function latestMtu(events: TelemetryEvent[], host?: string, iface?: string): number | undefined {
  const ev = [...events].reverse().find((e) => e.host === host && e.ifaces?.[iface ?? '']);
  return ev?.ifaces?.[iface ?? '']?.mtu;
}

const TopologyPathView: React.FC<{ demo: DemoState }> = ({ demo }) => {
  const topo = demo.topology;
  const nodes = useMemo(() => new Map((topo?.nodes ?? []).map((n) => [n.id, n] as [string, TopologyNode])), [topo]);
  const path = topo?.paths[0];
  if (!topo || !path) return <EmptyState compact title="Topology not available" />;
  return (
    <div className="stack">
      <div className="muted">
        <span className="mono">{path.id}</span> · required MTU {path.required_mtu} · {path.purpose}
      </div>
      <div className="row wrap" style={{ gap: 6, alignItems: 'stretch' }}>
        {path.hops.map((id, idx) => {
          const n = nodes.get(id);
          if (!n) return null;
          const observed = n.kind === 'interface' ? latestMtu(demo.events, n.host, n.name) : undefined;
          const mismatch = observed !== undefined && n.intended_mtu !== undefined && observed !== n.intended_mtu;
          return (
            <React.Fragment key={id}>
              {idx > 0 && <span className="subtle" style={{ alignSelf: 'center' }}>—</span>}
              <div
                className={cx('panel')}
                style={{ padding: '6px 10px', minWidth: 110, borderColor: mismatch ? 'var(--crit, #d33)' : undefined }}
                title={id}
              >
                <div className="subtle" style={{ fontSize: 'var(--fs-sm)' }}>{n.kind.replace('_', ' ')}</div>
                <div className="mono strong">{n.kind === 'switch_port' ? `${n.switch}:${n.name}` : n.kind === 'interface' ? `${n.host}:${n.name}` : n.name}</div>
                {n.intended_mtu !== undefined && (
                  <div style={{ fontSize: 'var(--fs-sm)' }}>
                    intent {n.intended_mtu}
                    {observed !== undefined && (
                      <>
                        {' · '}observed <span className={mismatch ? 'strong' : undefined}>{observed}</span>
                      </>
                    )}
                  </div>
                )}
                {n.kind === 'switch' && n.shared && <Badge tone="warn">shared</Badge>}
                {mismatch && <Badge tone="crit">MTU mismatch</Badge>}
              </div>
            </React.Fragment>
          );
        })}
      </div>
      <div className="muted" style={{ fontSize: 'var(--fs-sm)' }}>
        Topology source: <span className="mono">{topo.source}</span> {topo.simulated ? '(simulated fixture, not discovered)' : ''}. Switch
        values are configured intent from the topology record, not observed telemetry.
      </div>
    </div>
  );
};

export const DemoPage: React.FC<Props> = ({ onChanged, onToast }) => {
  const [demo, setDemo] = useState<DemoState | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<null | 'load' | 'reset'>(null);
  const [error, setError] = useState<string | null>(null);
  const [variant, setVariant] = useState<Variant>('pass');

  const refresh = useCallback(async () => {
    try {
      const d = await api.getDemo();
      setDemo(d);
      if (d.post_check_variant) setVariant(d.post_check_variant);
      setError(null);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const load = async () => {
    setBusy('load');
    try {
      const d = await api.loadDemo(variant);
      setDemo(d);
      setError(null);
      onToast('success', 'Demo fixture loaded', `Scripted post-check: ${variant}. Only demo records were replaced.`);
      onChanged();
    } catch (e: any) {
      setError(e.message);
      onToast('error', 'Could not load demo', e.message);
    } finally {
      setBusy(null);
    }
  };

  const reset = async () => {
    setBusy('reset');
    try {
      await api.resetDemo();
      await refresh();
      onToast('info', 'Demo records removed', 'Other events, decisions and proposals were not touched.');
      onChanged();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(null);
    }
  };

  const proposal = demo?.proposal ?? null;
  const evidence = demo?.decision?.evidence ?? null;
  const st = proposal?.status;
  const steps = [
    { name: '1. Load fixture', state: demo?.loaded ? 'done' : 'current', meta: demo?.loaded ? `post-check: ${demo.post_check_variant ?? '—'}` : 'Not loaded' },
    { name: '2. Topology & fault', state: evidence ? 'done' : 'pending', meta: evidence ? `${evidence.mtu_checks[0]?.observed} vs ${evidence.mtu_checks[0]?.expected}` : undefined },
    { name: '3. Diagnosis', state: evidence ? 'done' : 'pending', meta: evidence ? `${evidence.inference.fault_domain} · ${evidence.confidence.level}` : undefined },
    {
      name: '4. Preview & approve',
      state: !proposal ? 'pending' : st === 'pending_approval' ? 'current' : st === 'rejected' || st === 'blocked' || st === 'expired' ? 'failed' : 'done',
      meta: st === 'pending_approval' ? 'Waiting for you' : proposal?.decision ? `${proposal.decision.approved ? 'approved' : 'rejected'} by ${proposal.decision.approver}` : st,
    },
    {
      name: '5. Verify & audit',
      state: st === 'resolved' ? 'done' : st === 'verification_failed' || st === 'execution_failed' ? 'failed' : st === 'verification_inconclusive' ? 'current' : st === 'rejected' ? 'skipped' : 'pending',
      meta: proposal?.verification ? `post-check ${proposal.verification.outcome}` : undefined,
    },
  ];

  return (
    <>
      <PageHeader
        title={
          <span className="row" style={{ gap: 8 }}>
            <FlaskConical size={18} /> Two-host MTU mismatch demo <Badge tone="warn">SIMULATED</Badge>
          </span>
        }
        description={demo?.title ?? 'Deterministic, repeatable scenario: gpu-a ↔ leaf-1 ↔ gpu-b'}
        actions={
          <>
            <Segmented<Variant>
              label="Scripted post-check outcome"
              value={variant}
              onChange={setVariant}
              options={[
                { value: 'pass', label: 'Post-check passes' },
                { value: 'fail', label: 'Fails' },
                { value: 'inconclusive', label: 'Inconclusive' },
              ]}
            />
            <button className="btn btn-primary" onClick={load} disabled={!!busy}>
              <RotateCcw size={14} /> {busy === 'load' ? 'Loading…' : demo?.loaded ? 'Reset & replay' : 'Load demo'}
            </button>
            <button className="btn btn-ghost" onClick={reset} disabled={!!busy || !demo?.loaded}>
              <Trash2 size={14} /> Remove demo data
            </button>
          </>
        }
      />

      <Banner tone="warn" title="Simulated data — not live telemetry">
        {demo?.disclaimer ??
          'Telemetry, log lines, change records and post-remediation samples are scripted fixtures. Remediation runs in simulation mode and changes no infrastructure.'}
      </Banner>

      {error && (
        <Banner tone="crit" title="Demo request failed" actions={<button className="btn btn-sm" onClick={refresh}>Retry</button>}>
          {error}
        </Banner>
      )}

      <ol className="steps" aria-label="Demo progress">
        {steps.map((s) => (
          <li key={s.name} className={cx('step', s.state)}>
            <span className="step-icon" aria-hidden />
            <span style={{ minWidth: 0 }}>
              <span className="step-name" style={{ display: 'block' }}>{s.name}</span>
              {s.meta && <span className="step-meta truncate" style={{ display: 'block' }}>{s.meta}</span>}
            </span>
          </li>
        ))}
      </ol>

      {loading ? (
        <Panel>
          <div className="stack">
            <div className="skeleton" style={{ width: '40%' }} />
            <div className="skeleton" style={{ width: '70%' }} />
          </div>
        </Panel>
      ) : !demo?.loaded ? (
        <Panel>
          <EmptyState
            icon={<FlaskConical size={28} />}
            title="Demo fixture not loaded"
            description="Loading replays three scripted telemetry samples through the real triage pipeline (rules, log classifier, ML fallback, topology evidence, shared remediation policy). It replaces only records tagged demo:mtu-two-host."
            actions={<button className="btn btn-primary" onClick={load} disabled={!!busy}>Load demo</button>}
          />
          {demo && (
            <ul style={{ paddingLeft: 18 }} className="muted">
              {demo.story.map((s, i) => <li key={i}>{s}</li>)}
            </ul>
          )}
        </Panel>
      ) : (
        <div className="stack">
          <Panel title="2. Topology and fault" sub={`Scenario clock ${demo.scenario_clock}`}>
            <TopologyPathView demo={demo} />
            <div className="section-label" style={{ marginTop: 'var(--sp-4)' }}>Story</div>
            <ul style={{ paddingLeft: 18 }} className="muted">
              {demo.story.map((s, i) => <li key={i}>{s}</li>)}
            </ul>
            <div className="section-label" style={{ marginTop: 'var(--sp-4)' }}>Telemetry samples triaged ({demo.events.length})</div>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr><th>Event</th><th>Time (scenario)</th><th>Host</th><th>MTU</th><th>rx errors</th><th>qp_errors</th><th>Role</th></tr>
                </thead>
                <tbody>
                  {demo.events.map((e) => {
                    const [iface, st] = Object.entries(e.ifaces ?? {})[0] ?? ['', {} as IfaceStats];
                    return (
                      <tr key={e.event_id}>
                        <td className="mono">{e.event_id}</td>
                        <td className="num">{formatTime(e.ts)}</td>
                        <td className="mono">{e.host}/{iface}</td>
                        <td className="num">{st.mtu ?? '—'}</td>
                        <td className="num">{st.errin ?? '—'}</td>
                        <td className="num">{e.rdma?.qp_errors ?? '—'}</td>
                        <td>{e.role}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Panel>

          <Panel title="3. Evidence-backed diagnosis">
            {evidence ? <EvidencePanel evidence={evidence} /> : <EmptyState compact title="No evidence recorded for the trigger event" />}
          </Panel>

          <Panel title="4–5. Remediation preview, approval and verification">
            {proposal ? (
              <RemediationPanel
                proposal={proposal}
                onChanged={() => {
                  refresh();
                  onChanged();
                }}
              />
            ) : (
              <EmptyState compact title="No remediation proposal" description="The triage pipeline did not produce a candidate for the trigger event." />
            )}
          </Panel>

          <Panel title="Audit trail (persistent, demo-scoped)" count={demo.audit.length}>
            <AuditTimeline entries={demo.audit} />
          </Panel>
        </div>
      )}
    </>
  );
};
