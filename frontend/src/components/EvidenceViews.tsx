import React, { useState } from 'react';
import { ApiError, api } from '../services/api';
import { domainLabel, formatDateTime, formatTime } from '../lib/format';
import { Evidence, RemediationAudit, RemediationProposal, RemediationStatus } from '../types';
import { ApproverField } from './ActionModals';
import { useApprover } from '../hooks/useApprover';
import { Badge, Banner, EmptyState, Tone } from './ui';

const show = (v: unknown) => (v === null || v === undefined || v === '' ? '—' : typeof v === 'object' ? JSON.stringify(v) : String(v));

const LEVEL_TONE: Record<string, Tone> = { high: 'ok', medium: 'warn', low: 'crit' };
const RELEVANCE_TONE: Record<string, Tone> = { relevant: 'warn', possibly_related: 'info', unrelated: 'neutral', unknown: 'neutral' };

const FactRefs: React.FC<{ ids: string[] }> = ({ ids }) => (
  <span className="row wrap" style={{ gap: 4, display: 'inline-flex' }}>
    {ids.map((id) => (
      <a key={id} href={`#fact-${id}`} className="badge badge-mono" onClick={(e) => {
        e.preventDefault();
        document.getElementById(`fact-${id}`)?.scrollIntoView({ block: 'center' });
      }}>
        {id}
      </a>
    ))}
  </span>
);

const Section: React.FC<{ title: string; sub?: React.ReactNode; children: React.ReactNode }> = ({ title, sub, children }) => (
  <div>
    <div className="section-label">{title}</div>
    {sub && <p className="muted" style={{ marginBottom: 'var(--sp-2)' }}>{sub}</p>}
    {children}
  </div>
);

// ---------------------------------------------------------------------------
// Evidence
// ---------------------------------------------------------------------------
export const EvidencePanel: React.FC<{ evidence: Evidence }> = ({ evidence: ev }) => {
  const loc = ev.localization;
  const conf = ev.confidence;
  return (
    <div className="stack">
      <div className="row wrap">
        {ev.simulated && <Badge tone="warn">SIMULATED evidence</Badge>}
        <Badge tone={loc.status === 'resolved' ? 'ok' : loc.status === 'unresolved' ? 'crit' : 'warn'}>Localization: {loc.status}</Badge>
        <Badge tone={LEVEL_TONE[conf.level]} title={conf.note}>
          Evidence strength: {conf.level} ({conf.supporting_checks}/{conf.total_checks} checks)
        </Badge>
      </div>

      <Section title="Inference (deterministic rules)">
        <p style={{ fontSize: 'var(--fs-lg)' }}>
          <span className="strong">{domainLabel(ev.inference.fault_domain)}</span>{' '}
          <Badge tone={ev.inference.status === 'confirmed' ? 'ok' : 'warn'}>{ev.inference.status}</Badge>
        </p>
        <p>{ev.inference.statement}</p>
        {ev.inference.reasoning.length > 0 && (
          <ol style={{ paddingLeft: 18, display: 'grid', gap: 4, marginTop: 'var(--sp-2)' }}>
            {ev.inference.reasoning.map((r, i) => (
              <li key={i}>
                {r.step} <span className="muted">because</span> <FactRefs ids={r.because} />
              </li>
            ))}
          </ol>
        )}
      </Section>

      <Section title="Confidence and limitations" sub={conf.note}>
        <ul style={{ listStyle: 'none', display: 'grid', gap: 2 }}>
          {conf.checks.map((c) => (
            <li key={c.name}>
              <Badge tone={c.passed ? 'ok' : 'neutral'}>{c.passed ? 'pass' : 'no'}</Badge> <span className="mono">{c.name}</span>{' '}
              <span className="muted">— {c.detail}</span>
            </li>
          ))}
        </ul>
        {conf.limitations.length > 0 && (
          <ul style={{ paddingLeft: 18, marginTop: 'var(--sp-2)' }}>
            {conf.limitations.map((l, i) => (
              <li key={i} className="muted">{l}</li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Localization">
        <dl className="kv">
          <dt>Host</dt>
          <dd>
            <span className="mono">{loc.host.name || '—'}</span>{' '}
            {loc.host.resolved ? (
              <span className="muted">
                {loc.host.entity_id} · topology <span className="mono">{loc.host.topology_id}</span>
                {loc.host.simulated_topology ? ' (simulated fixture)' : ''}
              </span>
            ) : (
              <Badge tone="crit">not in topology</Badge>
            )}
          </dd>
          {loc.interfaces.map((i) => (
            <React.Fragment key={i.name}>
              <dt>Interface</dt>
              <dd>
                <span className="mono">{i.name}</span> {i.driver && <span className="muted">driver {i.driver}</span>}{' '}
                {!i.resolved && <Badge tone="crit">unresolved</Badge>}
              </dd>
              <dt>Peer</dt>
              <dd>
                {i.peer.resolved ? (
                  <>
                    <span className="mono">
                      {i.peer.device} {i.peer.port}
                    </span>{' '}
                    <span className="muted">
                      configured MTU {show(i.peer.configured_mtu)} ({i.peer.note})
                    </span>
                  </>
                ) : (
                  <span className="muted">Unavailable: {i.peer.reason}</span>
                )}
              </dd>
            </React.Fragment>
          ))}
        </dl>
        {loc.paths.map((p) => (
          <div key={p.id} style={{ marginTop: 'var(--sp-2)' }}>
            <div className="muted">
              Known path <span className="mono">{p.id}</span> · required MTU {show(p.required_mtu)} {p.purpose ? `· ${p.purpose}` : ''}
            </div>
            <div className="row wrap" style={{ gap: 4 }}>
              {p.hops.map((h, idx) => (
                <React.Fragment key={h.entity_id}>
                  {idx > 0 && <span className="subtle">→</span>}
                  <Badge mono>{h.device && h.kind !== 'host' ? `${h.device}:${h.name}` : h.name}</Badge>
                </React.Fragment>
              ))}
            </div>
          </div>
        ))}
      </Section>

      <Section title="Expected vs observed MTU">
        {ev.mtu_checks.length === 0 ? (
          <span className="muted">No interface was localized.</span>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr><th>Interface</th><th>Expected (topology)</th><th>Observed (telemetry)</th><th>Result</th><th>Facts</th></tr>
              </thead>
              <tbody>
                {ev.mtu_checks.map((m) => (
                  <tr key={m.iface}>
                    <td className="mono">{m.host}/{m.iface}</td>
                    <td className="num">{show(m.expected)}</td>
                    <td className="num">{show(m.observed)}</td>
                    <td>
                      <Badge tone={m.status === 'mismatch' ? 'crit' : m.status === 'match' ? 'ok' : 'neutral'}>{m.status}</Badge>{' '}
                      <span className="muted">{m.reason}</span>
                    </td>
                    <td><FactRefs ids={m.facts} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      {ev.counters.length > 0 && (
        <Section title="Counters">
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr><th>Entity</th><th>Counter</th><th>Before</th><th>After</th><th>Delta</th><th>Window</th><th>Fact</th></tr>
              </thead>
              <tbody>
                {ev.counters.map((c, i) => (
                  <tr key={i}>
                    <td className="mono">{c.entity}</td>
                    <td className="mono">{c.counter}</td>
                    <td className="num">{show(c.before)}</td>
                    <td className="num">{show(c.after)}</td>
                    <td className="num">{c.delta === null ? 'unknown' : c.delta > 0 ? `+${c.delta}` : c.delta}</td>
                    <td className="num">{c.window_s ? `${c.window_s}s` : '—'}</td>
                    <td><FactRefs ids={[c.fact]} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}

      {ev.log_lines.length > 0 && (
        <Section title="Matching kernel log lines (exact)">
          {ev.log_lines.map((l) => (
            <div key={l.line_no} className="log-line">
              <span className="subtle">{l.fact} · line {l.line_no} · {l.tags.join(', ')}</span>
              <div>{l.text}</div>
            </div>
          ))}
        </Section>
      )}

      <Section title="Affected scope">
        <div className="grid-2">
          <div>
            <div className="strong">Directly affected</div>
            <ul style={{ paddingLeft: 18 }}>
              {ev.scope.direct.map((s) => (
                <li key={s.entity_id}><span className="mono">{s.label}</span> <span className="muted">— {s.reason}</span></li>
              ))}
              {ev.scope.direct.length === 0 && <li className="muted">None localized</li>}
            </ul>
          </div>
          <div>
            <div className="strong">Broader blast radius</div>
            <ul style={{ paddingLeft: 18 }}>
              {ev.scope.blast_radius.map((s) => (
                <li key={s.entity_id}><span className="mono">{s.label}</span> <span className="muted">— {s.reason}</span></li>
              ))}
              {ev.scope.blast_radius.length === 0 && <li className="muted">Unknown (no topology path)</li>}
            </ul>
          </div>
        </div>
      </Section>

      <Section title="Change correlation" sub={ev.change_correlation.note}>
        {ev.change_correlation.items.length === 0 ? (
          <span className="muted">No change records in the correlation window.</span>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr><th>Change</th><th>When</th><th>Entity / attribute</th><th>Assessment</th><th title="Heuristic 0–1; not a probability">Relevance score</th></tr>
              </thead>
              <tbody>
                {ev.change_correlation.items.map((c) => (
                  <tr key={c.change_id}>
                    <td>
                      <div className="mono">{c.change_id}</div>
                      <div className="muted">{c.summary}</div>
                    </td>
                    <td className="num">{formatDateTime(c.ts)}</td>
                    <td>
                      <span className="mono">{c.entity}</span> · <span className="mono">{c.attribute}</span>{' '}
                      <span className="muted">{show(c.old_value)} → {show(c.new_value)}</span>
                    </td>
                    <td>
                      <Badge tone={RELEVANCE_TONE[c.relevance]}>{c.relevance.replace('_', ' ')}</Badge>
                      <ul style={{ paddingLeft: 16 }} className="muted">
                        {c.factors.map((f, i) => <li key={i}>{f}</li>)}
                      </ul>
                    </td>
                    <td className="num">{c.relevance_score.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      <Section title={`Observed facts (${ev.observed_facts.length})`}>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr><th>ID</th><th>Kind</th><th>Statement</th><th>Source</th></tr>
            </thead>
            <tbody>
              {ev.observed_facts.map((f) => (
                <tr key={f.id} id={`fact-${f.id}`}>
                  <td className="mono">{f.id}</td>
                  <td>{f.kind}</td>
                  <td className={f.kind === 'log' ? 'mono' : undefined}>{f.statement}</td>
                  <td className="mono" style={{ fontSize: 'var(--fs-sm)' }}>
                    {f.source.type}:{f.source.ref ?? '—'}
                    {f.source.compared_with ? ` vs ${f.source.compared_with}` : ''}
                    {f.source.simulated ? ' · simulated' : ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      {(ev.model_signals ?? []).map((s, i) => (
        <Banner key={i} tone={s.flagged ? 'warn' : 'info'} title={`Model-generated log anomaly score: ${s.max_score.toFixed(2)} (${s.model}, trained on ${s.trained_on})`}>
          <div className="mono">{s.top_line}</div>
          <p className="muted">{s.note}</p>
        </Banner>
      ))}

      {ev.model_explanation && (
        <Banner title={`Model-generated explanation (${ev.model_explanation.backend || 'AI layer'})`}>
          <p>{ev.model_explanation.explanation || ev.model_explanation.root_cause}</p>
          <p className="muted">
            {ev.model_explanation.note} Model-reported confidence {show(ev.model_explanation.model_reported_confidence)} is not
            calibrated and is not used by the remediation policy.
          </p>
        </Banner>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Remediation (shared policy)
// ---------------------------------------------------------------------------
const STATUS_BANNER: Record<RemediationStatus, { tone: Tone; title: string }> = {
  pending_approval: { tone: 'warn', title: 'Approval required before anything runs' },
  blocked: { tone: 'crit', title: 'Blocked by the remediation policy — manual triage required' },
  rejected: { tone: 'neutral', title: 'Rejected — nothing was executed' },
  expired: { tone: 'neutral', title: 'Approval window expired — re-run triage for a fresh preview' },
  approved: { tone: 'info', title: 'Approved' },
  executing: { tone: 'info', title: 'Executing' },
  verifying: { tone: 'info', title: 'Awaiting post-check' },
  execution_failed: { tone: 'crit', title: 'Execution failed — not resolved. No automatic retry or rollback was attempted.' },
  verification_failed: { tone: 'crit', title: 'Post-check FAILED — the incident is not resolved' },
  verification_inconclusive: { tone: 'warn', title: 'Post-check inconclusive — the incident is not marked resolved' },
  resolved: { tone: 'ok', title: 'Resolved — verified by the post-check' },
  completed: { tone: 'ok', title: 'Completed (diagnostic action)' },
};

export const AuditTimeline: React.FC<{ entries: RemediationAudit[] }> = ({ entries }) =>
  entries.length === 0 ? (
    <EmptyState compact title="No audit records yet" />
  ) : (
    <ol className="timeline">
      {entries.map((a) => {
        const bad = a.kind === 'blocked' || a.kind === 'rejected' || (a.kind === 'post_check' && a.detail.outcome !== 'passed');
        return (
          <li key={a.seq} className={`timeline-item ${bad ? 'crit' : 'ok'}`}>
            <span className="timeline-marker" aria-hidden />
            <div style={{ minWidth: 0 }}>
              <div className="timeline-head">
                <span className="timeline-agent">{a.kind}</span>
                <span className="timeline-time">{formatTime(a.ts)} UTC</span>
              </div>
              <div className="timeline-msg">
                {a.actor && <>by <span className="mono">{a.actor}</span> · </>}
                {a.kind === 'previewed' && <>action {a.detail.action} · mode {a.detail.mode} · digest <span className="mono">{a.detail.preview_digest}</span></>}
                {a.kind === 'blocked' && a.detail.reason}
                {(a.kind === 'simulated' || a.kind === 'executed') && a.detail.detail}
                {a.kind === 'post_check' && <>outcome {a.detail.outcome}</>}
                {a.kind === 'recommended' && <>from {a.detail.source}: {a.detail.diagnosis?.statement}</>}
                {(a.kind === 'approved' || a.kind === 'rejected') && a.detail.reason}
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );

export const RemediationPanel: React.FC<{
  proposal: RemediationProposal;
  onChanged: (p: RemediationProposal) => void;
  onError?: (msg: string) => void;
}> = ({ proposal: p, onChanged, onError }) => {
  const [approver, setApprover, valid] = useApprover();
  const [busy, setBusy] = useState<null | 'approve' | 'reject' | 'verify'>(null);
  const [error, setError] = useState<string | null>(null);
  const prev = p.preview;
  const banner = STATUS_BANNER[p.status];

  const act = async (kind: 'approve' | 'reject' | 'verify') => {
    setBusy(kind);
    setError(null);
    try {
      const res =
        kind === 'verify'
          ? await api.verifyRemediation(p.id)
          : await api.decideRemediation(p.id, { approved: kind === 'approve', approver, preview_digest: p.preview_digest });
      onChanged(res);
    } catch (e: any) {
      const msg = e instanceof ApiError && e.status === 409 ? `Refused: ${e.message}` : e.message;
      setError(msg);
      onError?.(msg);
      if (e instanceof ApiError && e.body?.proposal) onChanged(e.body.proposal);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="stack">
      <Banner tone={banner.tone} title={banner.title}>
        {p.status === 'blocked' && <span className="mono">{p.block_reason}</span>}
        {p.verification && <>{p.verification.summary} {p.verification.note}</>}
        {p.execution && !p.execution.ok && <span className="mono">{p.execution.detail}</span>}
      </Banner>
      {error && <Banner tone="crit" title="Request failed">{error}</Banner>}

      {prev && (
        <div>
          <div className="section-label">Preview (exact action)</div>
          <dl className="kv">
            <dt>Action</dt>
            <dd><span className="mono">{prev.action}</span> — {prev.description}</dd>
            <dt>Playbook</dt>
            <dd className="mono">infra/playbooks/{prev.playbook}</dd>
            <dt>Mode</dt>
            <dd>
              {prev.simulated ? <Badge tone="info">SIMULATION — no infrastructure change</Badge> : <Badge tone="crit">REAL Ansible execution</Badge>}
            </dd>
            <dt>Targets</dt>
            <dd className="mono">{prev.targets.map((t) => Object.values(t).join('/')).join(', ')}</dd>
            <dt>Variables</dt>
            <dd className="mono">{JSON.stringify(prev.extra_vars)}</dd>
            <dt>Risk</dt>
            <dd><Badge tone={prev.risk === 'high' ? 'crit' : prev.risk === 'medium' ? 'warn' : 'ok'}>{prev.risk}</Badge> {prev.risk_rationale}</dd>
            <dt>Blast radius</dt>
            <dd>{prev.blast_radius.length ? prev.blast_radius.map((b) => b.label).join(', ') : 'unknown'}</dd>
            <dt>Rollback</dt>
            <dd>{prev.rollback}</dd>
            <dt>Post-check</dt>
            <dd>{prev.post_check}</dd>
            {prev.ignored_inputs.length > 0 && (
              <>
                <dt>Ignored inputs</dt>
                <dd className="muted">Recommender-supplied {prev.ignored_inputs.join(', ')} ignored; variables are derived by the policy.</dd>
              </>
            )}
            <dt>Preview digest</dt>
            <dd className="mono">{p.preview_digest}</dd>
            <dt>Expires</dt>
            <dd className="num">{formatDateTime(p.expires_at)}</dd>
          </dl>
          <pre className="code" style={{ marginTop: 'var(--sp-2)', whiteSpace: 'pre-wrap' }}>{prev.command_preview}</pre>
        </div>
      )}

      {p.status === 'pending_approval' && (
        <div>
          <ApproverField id={`approver-${p.id}`} value={approver} onChange={setApprover} valid={valid} />
          <div className="row">
            <button className="btn btn-danger" disabled={!valid || !!busy} onClick={() => act('reject')}>
              {busy === 'reject' ? 'Rejecting…' : 'Reject'}
            </button>
            <button className="btn btn-primary" disabled={!valid || !!busy} onClick={() => act('approve')}>
              {busy === 'approve' ? 'Approving…' : prev?.simulated ? 'Approve (simulate) and verify' : 'Approve and execute'}
            </button>
          </div>
        </div>
      )}

      <div>
        <div className="section-label">Candidates considered</div>
        <ul style={{ listStyle: 'none', display: 'grid', gap: 2 }}>
          {p.candidates_considered.map((c, i) => (
            <li key={i}>
              <Badge tone={c.accepted ? 'ok' : 'neutral'}>{c.accepted ? 'accepted' : 'rejected'}</Badge>{' '}
              <span className="mono">{c.recommender}</span> → <span className="mono">{c.requested}</span> <span className="muted">— {c.reason}</span>
            </li>
          ))}
        </ul>
      </div>

      {p.decision && (
        <dl className="kv">
          <dt>Decision</dt>
          <dd>
            {p.decision.approved ? 'Approved' : 'Rejected'} by <span className="mono">{p.decision.approver}</span> at {formatDateTime(p.decision.ts)}
          </dd>
          {p.execution && (
            <>
              <dt>Execution</dt>
              <dd>{p.execution.detail}</dd>
            </>
          )}
        </dl>
      )}

      {p.verification && (
        <div>
          <div className="section-label">Before / after verification</div>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr><th>Check</th><th>Target</th><th>Expected</th><th>Observed</th><th>Result</th><th>Samples</th></tr>
              </thead>
              <tbody>
                {p.verification.checks.map((c, i) => (
                  <tr key={i}>
                    <td className="mono">{c.name}</td>
                    <td className="mono">{c.target}</td>
                    <td>{show(c.expected)}</td>
                    <td>{show(c.observed)}</td>
                    <td><Badge tone={c.status === 'pass' ? 'ok' : c.status === 'fail' ? 'crit' : 'warn'}>{c.status}</Badge></td>
                    <td className="mono" style={{ fontSize: 'var(--fs-sm)' }}>{c.sources.join(', ')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {(p.status === 'verification_inconclusive' || p.status === 'verification_failed') && (
        <div>
          <button className="btn" disabled={!!busy} onClick={() => act('verify')}>
            {busy === 'verify' ? 'Checking…' : 'Re-run post-check with latest telemetry'}
          </button>
        </div>
      )}
    </div>
  );
};
