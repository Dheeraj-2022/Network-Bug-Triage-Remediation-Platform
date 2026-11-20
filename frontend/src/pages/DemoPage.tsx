import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle2, FlaskConical, RotateCcw, ShieldCheck, Trash2 } from 'lucide-react';
import { AuditTimeline, EvidencePanel, RemediationPanel } from '../components/EvidenceViews';
import { Badge, Banner, EmptyState, Panel, Segmented, cx } from '../components/ui';
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

function latestErrin(events: TelemetryEvent[], host?: string, iface?: string): number | undefined {
  const ev = [...events].reverse().find((e) => e.host === host && e.ifaces?.[iface ?? '']);
  return ev?.ifaces?.[iface ?? '']?.errin;
}

const PhysicalFabricGraph: React.FC<{ demo: DemoState }> = ({ demo }) => {
  const topo = demo.topology;
  const nodes = useMemo(() => new Map((topo?.nodes ?? []).map((n) => [n.id, n] as [string, TopologyNode])), [topo]);
  if (!topo) return <EmptyState compact title="Topology not available" />;

  const hostNodes = topo.nodes.filter((n) => n.kind === 'host');
  const switchNodes = topo.nodes.filter((n) => n.kind === 'switch');
  const ifacesFor = (hostName: string) => topo.nodes.filter((n) => n.kind === 'interface' && n.host === hostName);

  const leftHost = hostNodes[0];
  const rightHost = hostNodes[1];
  const sw = switchNodes[0];

  const renderHostCard = (hostNode: TopologyNode | undefined) => {
    if (!hostNode) return null;
    const itf = ifacesFor(hostNode.name)[0];
    const observed = itf ? latestMtu(demo.events, hostNode.name, itf.name) : undefined;
    const errs = itf ? latestErrin(demo.events, hostNode.name, itf.name) : undefined;
    const mismatch = observed !== undefined && itf?.intended_mtu !== undefined && observed !== itf.intended_mtu;
    return (
      <div className={cx('nr-topo-node', mismatch && 'fault')}>
        <div className="row" style={{ justifyContent: 'space-between', marginBottom: 4 }}>
          <span className="mono strong" style={{ fontSize: 13 }}>{hostNode.name}</span>
          <Badge tone={mismatch ? 'crit' : 'ok'}>{mismatch ? 'FAULT DOMAIN' : 'NORMAL'}</Badge>
        </div>
        <div className="nr-topo-kv">
          <span>Interface:</span>
          <strong className="mono">{itf?.name || '—'}</strong>
        </div>
        <div className="nr-topo-kv">
          <span>Observed MTU:</span>
          <strong className="mono" style={{ color: mismatch ? 'var(--crit)' : 'var(--ok)' }}>
            {observed !== undefined ? `${observed}${observed === 9000 ? ' (Jumbo)' : ' (Standard)'}` : '—'}
          </strong>
        </div>
        <div className="nr-topo-kv">
          <span>Intended MTU:</span>
          <strong className="mono">{itf?.intended_mtu ?? '—'}</strong>
        </div>
        <div className="nr-topo-kv">
          <span>rx_errors:</span>
          <strong className="mono" style={{ color: errs && errs > 0 ? 'var(--crit)' : undefined }}>
            {errs ?? 0}
          </strong>
        </div>
      </div>
    );
  };

  const path = topo.paths[0];

  return (
    <div className="stack">
      <div className="nr-topo-graph">
        {renderHostCard(leftHost)}

        <div className="nr-topo-node" style={{ background: '#ffffff' }}>
          <div className="row" style={{ justifyContent: 'space-between', marginBottom: 4 }}>
            <span className="mono strong" style={{ fontSize: 13 }}>{sw?.name || 'leaf-1'} (Switch)</span>
            <Badge tone="warn">{sw?.shared ? 'SHARED' : 'FABRIC'}</Badge>
          </div>
          <div className="nr-topo-kv">
            <span>Path ID:</span>
            <strong className="mono">{path?.id || '—'}</strong>
          </div>
          <div className="nr-topo-kv">
            <span>Required MTU:</span>
            <strong className="mono">{path?.required_mtu ?? 9000} B</strong>
          </div>
          <div className="nr-topo-kv">
            <span>Purpose:</span>
            <strong className="mono truncate" style={{ maxWidth: 160 }}>{path?.purpose || 'RDMA Fabric'}</strong>
          </div>
          <div style={{ marginTop: 6, paddingTop: 6, borderTop: '1px solid var(--border)', fontSize: 11, color: 'var(--text-2)' }}>
            Switch ports reflect configured topology intent — not modified by host remediation.
          </div>
        </div>

        {renderHostCard(rightHost)}
      </div>

      <div className="muted mono" style={{ fontSize: 11 }}>
        Topology source: {topo.source} {topo.simulated ? '· SIMULATED FIXTURE (not discovered live)' : ''}
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
    { num: 'STEP 01', name: 'Load Fixture', state: demo?.loaded ? 'done' : 'current', meta: demo?.loaded ? `post-check: ${demo.post_check_variant ?? '—'}` : 'Not loaded' },
    { num: 'STEP 02', name: 'Topology & Fault', state: evidence ? 'done' : 'pending', meta: evidence ? `${evidence.mtu_checks[0]?.observed} vs ${evidence.mtu_checks[0]?.expected}` : 'Pending' },
    { num: 'STEP 03', name: 'Evidence & RCA', state: evidence ? 'done' : 'pending', meta: evidence ? `${evidence.inference.fault_domain} · ${evidence.confidence.level}` : 'Pending' },
    {
      num: 'STEP 04',
      name: 'Preview & Approve',
      state: !proposal ? 'pending' : st === 'pending_approval' ? 'current' : st === 'rejected' || st === 'blocked' || st === 'expired' ? 'failed' : 'done',
      meta: st === 'pending_approval' ? 'Awaiting Approval' : proposal?.decision ? `${proposal.decision.approved ? 'Approved' : 'Rejected'} by ${proposal.decision.approver}` : (st || 'Pending'),
    },
    {
      num: 'STEP 05',
      name: 'Post-Check & Audit',
      state: st === 'resolved' ? 'done' : st === 'verification_failed' || st === 'execution_failed' ? 'failed' : st === 'verification_inconclusive' ? 'current' : st === 'rejected' ? 'skipped' : 'pending',
      meta: proposal?.verification ? `Outcome: ${proposal.verification.outcome}` : 'Pending',
    },
  ];

  const mtuCheck = evidence?.mtu_checks?.[0];
  const changes = evidence?.change_correlation?.items ?? demo?.changes ?? [];

  return (
    <>
      <div className="page-header">
        <div>
          <div className="eyebrow">INTERACTIVE SCENARIO · SIMULATED FIXTURE</div>
          <h1 className="page-title">Two-Host MTU Mismatch Scenario</h1>
          <div className="row" style={{ gap: 8, marginTop: 6 }}>
            <Badge tone="warn">SIMULATED FIXTURE</Badge>
            <span className="mono" style={{ fontSize: 11, color: 'var(--text-3)' }}>
              {demo?.scenario_id || 'demo:mtu-two-host'}
            </span>
          </div>
        </div>
        <div className="page-actions" style={{ alignItems: 'center' }}>
          <Segmented<Variant>
            label="Scripted post-check outcome"
            value={variant}
            onChange={setVariant}
            options={[
              { value: 'pass', label: 'PASSES' },
              { value: 'fail', label: 'FAILS' },
              { value: 'inconclusive', label: 'INCONCLUSIVE' },
            ]}
          />
          <button className="btn btn-primary" onClick={load} disabled={!!busy}>
            <RotateCcw size={13} /> {busy === 'load' ? 'LOADING…' : demo?.loaded ? 'RESET & REPLAY DEMO' : 'LOAD DEMO'}
          </button>
          <button className="btn" onClick={reset} disabled={!!busy || !demo?.loaded}>
            <Trash2 size={13} /> REMOVE FIXTURE
          </button>
        </div>
      </div>

      <Banner tone="warn" title="Simulated fixture data — not live infrastructure">
        {demo?.disclaimer ??
          'Telemetry, log lines, change records and post-remediation samples are scripted synthetic fixtures. Remediation runs strictly through RemediationPolicy in deterministic simulated mode.'}
      </Banner>

      {error && (
        <Banner tone="crit" title="Demo request failed" actions={<button className="btn btn-sm" onClick={refresh}>Retry</button>}>
          {error}
        </Banner>
      )}

      {/* 5-Step Incident Lifecycle */}
      <ol className="steps" aria-label="Demo lifecycle">
        {steps.map((s) => (
          <li key={s.name} className={cx('step', s.state)}>
            <span className="step-icon" aria-hidden />
            <span style={{ minWidth: 0 }}>
              <span className="mono" style={{ fontSize: 10, color: 'var(--text-3)', display: 'block' }}>{s.num}</span>
              <span className="step-name" style={{ display: 'block', fontWeight: 600 }}>{s.name}</span>
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
            description="Loading replays three scripted telemetry samples (gpu-a healthy, gpu-b MTU 1500 mismatch) through the real triage pipeline, evidence builder, and RemediationPolicy. Unrelated records are never modified."
            actions={<button className="btn btn-primary" onClick={load} disabled={!!busy}>LOAD TWO-HOST MTU DEMO</button>}
          />
          {demo && (
            <ul style={{ paddingLeft: 18 }} className="muted">
              {demo.story.map((s, i) => <li key={i}>{s}</li>)}
            </ul>
          )}
        </Panel>
      ) : (
        <div className="stack">
          {/* Physical Layer Graph */}
          <Panel
            title="Deterministic Fabric Topology"
            sub={`PHYSICAL LAYER GRAPH · Scenario clock ${demo.scenario_clock}`}
            actions={
              <div className="row" style={{ gap: 10, fontSize: 11 }}>
                <span className="status"><span className="dot dot-ok" />Line Rate OK</span>
                <span className="status"><span className="dot dot-crit" />MTU Truncation Violation</span>
              </div>
            }
          >
            <PhysicalFabricGraph demo={demo} />
          </Panel>

          {/* Split Row: Telemetry Samples + Root Cause Identification & Change Correlation */}
          <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.35fr) minmax(0, 1fr)', gap: 16 }} className="activity-grid">
            <Panel title="Triaged Telemetry Samples" count={demo.events.length} sub="INGRESS TELEMETRY STREAM (SIMULATED)" flush>
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Event ID</th>
                      <th>Timestamp</th>
                      <th>Host / Dev</th>
                      <th>MTU</th>
                      <th>RX Errs</th>
                      <th>QP Errs</th>
                      <th>Role</th>
                    </tr>
                  </thead>
                  <tbody>
                    {demo.events.map((e) => {
                      const [iface, stats] = Object.entries(e.ifaces ?? {})[0] ?? ['', {} as IfaceStats];
                      const badMtu = stats.mtu !== undefined && stats.mtu < 9000;
                      return (
                        <tr key={e.event_id}>
                          <td className="mono" style={{ color: badMtu ? 'var(--crit)' : undefined }}>{e.event_id}</td>
                          <td className="mono num">{formatTime(e.ts)}</td>
                          <td className="mono">{e.host}:{iface}</td>
                          <td className="mono num" style={{ color: badMtu ? 'var(--crit)' : undefined, fontWeight: badMtu ? 700 : 400 }}>{stats.mtu ?? '—'}</td>
                          <td className="mono num" style={{ color: (stats.errin ?? 0) > 0 ? 'var(--crit)' : undefined }}>{stats.errin ?? 0}</td>
                          <td className="mono num">{e.rdma?.qp_errors ?? 0}</td>
                          <td><Badge tone={badMtu ? 'crit' : 'ok'}>{e.role || 'sample'}</Badge></td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Panel>

            <div className="stack">
              <Panel
                title="Root Cause Identification"
                actions={
                  evidence && (
                    <Badge tone="crit">
                      {evidence.confidence.level.toUpperCase()} · {evidence.confidence.supporting_checks}/{evidence.confidence.total_checks} CHECKS
                    </Badge>
                  )
                }
              >
                {evidence ? (
                  <div className="stack">
                    <div style={{ fontSize: 15, fontWeight: 700, color: '#171614' }}>
                      {evidence.inference.fault_domain.replace(/_/g, ' ')}
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--text-2)' }}>{evidence.inference.statement}</div>
                    {mtuCheck && (
                      <div className="nr-compare-grid" style={{ marginBottom: 0 }}>
                        <div className="nr-compare-box">
                          <div className="eyebrow">EXPECTED MTU</div>
                          <div className="mono strong" style={{ fontSize: 18 }}>{mtuCheck.expected ?? '—'}</div>
                        </div>
                        <div className="nr-compare-box fault">
                          <div className="eyebrow" style={{ color: 'var(--crit)' }}>OBSERVED MTU</div>
                          <div className="mono strong" style={{ fontSize: 18, color: 'var(--crit)' }}>{mtuCheck.observed ?? '—'}</div>
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <EmptyState compact title="No evidence recorded" />
                )}
              </Panel>

              <Panel title="Change Ledger Correlation" count={changes.length}>
                {changes.length === 0 ? (
                  <EmptyState compact title="No correlated changes" />
                ) : (
                  <div className="stack" style={{ gap: 8 }}>
                    {changes.map((ch: any, idx: number) => (
                      <div
                        key={ch.change_id || idx}
                        style={{
                          padding: '8px 10px',
                          background: ch.relevance === 'relevant' ? 'var(--warn-bg)' : 'var(--bg)',
                          border: `1px solid ${ch.relevance === 'relevant' ? 'var(--warn-border)' : 'var(--border)'}`,
                        }}
                      >
                        <div className="row" style={{ justifyContent: 'space-between', marginBottom: 2 }}>
                          <span className="mono strong" style={{ fontSize: 11 }}>{ch.change_id}</span>
                          <Badge tone={ch.relevance === 'relevant' ? 'warn' : 'neutral'}>
                            {(ch.relevance || 'recorded').toUpperCase()}
                          </Badge>
                        </div>
                        <div style={{ fontSize: 12, color: 'var(--text-2)' }}>{ch.summary || `${ch.attribute} on ${ch.entity}`}</div>
                      </div>
                    ))}
                    <div className="mono" style={{ fontSize: 10, color: 'var(--text-3)', textAlign: 'center', padding: '6px 8px', background: 'var(--bg)', border: '1px solid var(--border)' }}>
                      CORRELATION ONLY — NOT PROOF OF CAUSATION. VERIFICATION GATE ENFORCED.
                    </div>
                  </div>
                )}
              </Panel>
            </div>
          </div>

          {/* Controlled Safety Gate: Remediation Preview, Approval & Verification */}
          <Panel
            title="Remediation Gate & Post-Check Verification"
            sub="CONTROLLED SAFETY GATE · SHARED REMEDIATION POLICY"
            actions={
              proposal && (
                <span className="mono" style={{ fontSize: 11, color: 'var(--text-2)' }}>
                  {proposal.id} · TARGET: {proposal.host}
                </span>
              )
            }
          >
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

          {evidence && (
            <Panel title="Full Deterministic Evidence & Reasoning">
              <EvidencePanel evidence={evidence} />
            </Panel>
          )}

          <Panel title="Persistent Demo Audit Trail" count={demo.audit.length}>
            <AuditTimeline entries={demo.audit} />
          </Panel>
        </div>
      )}
    </>
  );
};
