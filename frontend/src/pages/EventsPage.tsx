import React, { useMemo, useState } from 'react';
import { Database, X, Zap } from 'lucide-react';
import { Badge, EmptyState, PageHeader, Pagination, Panel, SearchInput, Segmented, SkeletonRows, StatusDot, Tone, cx, usePageClamp } from '../components/ui';
import { eventErrorCount, eventMtuAnomaly, eventSignal, Incident } from '../lib/incidents';
import { formatDateTime, formatNumber, formatTime, parseTs } from '../lib/format';
import { hrefFor } from '../lib/routes';
import { Decision, TelemetryEvent } from '../types';
import { CommonPageProps } from './common';
import { EventEvidence } from './IncidentDetailPage';

interface Props extends CommonPageProps {
  events: TelemetryEvent[];
  decisions: Decision[];
  incidents: Incident[];
  query: URLSearchParams;
}

type Signal = 'all' | 'crit' | 'warn' | 'ok';
const PAGE_SIZE = 30;
const SIGNAL_LABEL: Record<Exclude<Signal, 'all'>, string> = { crit: 'Threshold breach', warn: 'Anomaly', ok: 'Nominal' };

function mtuSummary(ev: TelemetryEvent): string {
  const mtus = [...new Set(Object.values(ev.ifaces || {}).map((s) => s.mtu).filter((m): m is number => m !== undefined))];
  return mtus.length ? mtus.join(' / ') : '—';
}

export const EventsPage: React.FC<Props> = ({ events, decisions, incidents, query, loaded, onInject, onLoadSamples, isLoadingSamples }) => {
  const [host, setHost] = useState(query.get('host') || '');
  const [signal, setSignal] = useState<Signal>('all');
  const [search, setSearch] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(query.get('event'));
  const [page, setPage] = useState(0);

  const decisionByEvent = useMemo(() => new Map(decisions.filter((d) => d.event_id).map((d) => [d.event_id!, d])), [decisions]);
  const incidentByEvent = useMemo(() => new Map(incidents.filter((i) => i.eventId).map((i) => [i.eventId!, i])), [incidents]);
  const hosts = useMemo(() => [...new Set(events.map((e) => e.host).filter(Boolean))].sort(), [events]);

  const sorted = useMemo(
    () => [...events].sort((a, b) => (parseTs(b.ts)?.getTime() ?? 0) - (parseTs(a.ts)?.getTime() ?? 0)),
    [events],
  );

  const scoped = useMemo(() => sorted.filter((e) => !host || e.host === host), [sorted, host]);
  const counts = useMemo(() => {
    const c = { all: scoped.length, crit: 0, warn: 0, ok: 0 };
    for (const e of scoped) c[eventSignal(e)] += 1;
    return c;
  }, [scoped]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return scoped.filter((e) => {
      if (signal !== 'all' && eventSignal(e) !== signal) return false;
      if (q) {
        const hay = [e.event_id, e.host, e.dmesg_tail, ...Object.keys(e.ifaces || {})].filter(Boolean).join(' ').toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [scoped, signal, search]);

  usePageClamp(page, setPage, filtered.length, PAGE_SIZE);
  const pageItems = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const selected = selectedId ? events.find((e) => e.event_id === selectedId) : undefined;
  const selDecision = selected ? decisionByEvent.get(selected.event_id) : undefined;
  const selIncident = selected ? incidentByEvent.get(selected.event_id) : undefined;
  const filtersActive = !!(host || search || signal !== 'all');

  const reset = () => {
    setHost('');
    setSearch('');
    setSignal('all');
  };

  const table = (
    <Panel
      flush
      toolbar={
        <>
          <Segmented<Signal>
            label="Signal"
            value={signal}
            onChange={(v) => {
              setSignal(v);
              setPage(0);
            }}
            options={[
              { value: 'all', label: 'All', count: counts.all },
              { value: 'crit', label: 'Breach', count: counts.crit },
              { value: 'warn', label: 'Anomaly', count: counts.warn },
              { value: 'ok', label: 'Nominal', count: counts.ok },
            ]}
          />
          <select
            className="select"
            value={host}
            onChange={(e) => {
              setHost(e.target.value);
              setPage(0);
            }}
            aria-label="Host"
          >
            <option value="">All hosts</option>
            {hosts.map((h) => (
              <option key={h} value={h}>
                {h}
              </option>
            ))}
          </select>
          <div style={{ flex: 1 }} />
          <SearchInput value={search} onChange={setSearch} placeholder="Event ID, interface, dmesg text" width={240} />
        </>
      }
      footer={
        filtered.length > 0 ? (
          <>
            {filtersActive ? (
              <button className="btn-link" onClick={reset}>
                Clear filters
              </button>
            ) : (
              <span>Newest first · last {events.length} events held by the controller</span>
            )}
            <div className="row">
              <Pagination page={page} pageSize={PAGE_SIZE} total={filtered.length} onPage={setPage} />
            </div>
          </>
        ) : undefined
      }
    >
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th style={{ width: 84 }}>Time</th>
              <th style={{ width: 110 }}>Host</th>
              <th>Event</th>
              <th className="right" style={{ width: 80 }} title="Sum of errin + errout across interfaces">
                Iface err
              </th>
              <th className="right" style={{ width: 90 }}>
                MTU
              </th>
              <th className="right" style={{ width: 70 }} title="RDMA queue-pair errors">
                QP err
              </th>
              <th style={{ width: 150 }}>Outcome</th>
            </tr>
          </thead>
          {!loaded ? (
            <SkeletonRows rows={8} cols={7} />
          ) : pageItems.length === 0 ? (
            <tbody>
              <tr>
                <td colSpan={7} style={{ padding: 0 }}>
                  {events.length === 0 ? (
                    <EmptyState
                      title="No telemetry received"
                      description="Agents post host snapshots (interface counters, RDMA stats, dmesg) to the controller. Load fixtures or inject synthetic events to populate this view."
                      actions={
                        <>
                          <button className="btn" onClick={onLoadSamples} disabled={isLoadingSamples}>
                            <Database size={14} /> Load sample fixtures
                          </button>
                          <button className="btn" onClick={onInject}>
                            <Zap size={14} /> Inject synthetic events
                          </button>
                        </>
                      }
                    />
                  ) : (
                    <EmptyState
                      compact
                      title="No events match these filters"
                      actions={
                        <button className="btn btn-sm" onClick={reset}>
                          Clear filters
                        </button>
                      }
                    />
                  )}
                </td>
              </tr>
            </tbody>
          ) : (
            <tbody>
              {pageItems.map((e) => {
                const sig = eventSignal(e);
                const errs = eventErrorCount(e);
                const qp = Number(e.rdma?.qp_errors) || 0;
                const d = decisionByEvent.get(e.event_id);
                const inc = incidentByEvent.get(e.event_id);
                const isSel = selectedId === e.event_id;
                return (
                  <tr
                    key={e.event_id}
                    className={cx('clickable', isSel && 'selected')}
                    onClick={(ev) => {
                      if ((ev.target as HTMLElement).closest('a')) return;
                      setSelectedId(isSel ? null : e.event_id);
                    }}
                    onKeyDown={(ev) => {
                      if (ev.key === 'Enter' || ev.key === ' ') {
                        ev.preventDefault();
                        setSelectedId(isSel ? null : e.event_id);
                      }
                    }}
                    tabIndex={0}
                    aria-selected={isSel}
                  >
                    <td className="num muted nowrap" title={formatDateTime(e.ts)}>
                      {formatTime(e.ts)}
                    </td>
                    <td className="mono nowrap">{e.host}</td>
                    <td style={{ maxWidth: 0, width: '100%' }}>
                      <div className="row" style={{ gap: 6 }}>
                        <StatusDot tone={sig} title={SIGNAL_LABEL[sig]} />
                        <span className="mono truncate">{e.event_id}</span>
                      </div>
                      {e.dmesg_tail && (
                        <div className="cell-secondary truncate mono" title={e.dmesg_tail}>
                          {e.dmesg_tail}
                        </div>
                      )}
                    </td>
                    <td className="right num" style={{ color: errs >= 5 ? 'var(--crit)' : errs > 0 ? 'var(--warn)' : undefined }}>
                      {formatNumber(errs)}
                    </td>
                    <td className="right num" style={{ color: eventMtuAnomaly(e) ? 'var(--warn)' : undefined }}>
                      {mtuSummary(e)}
                    </td>
                    <td className="right num" style={{ color: qp > 0 ? 'var(--crit)' : undefined }}>
                      {e.rdma ? formatNumber(qp) : '—'}
                    </td>
                    <td className="nowrap">
                      {inc ? (
                        <a href={hrefFor('incident-detail', inc.key)}>Incident · {inc.severity}</a>
                      ) : d ? (
                        <span className="muted">No action</span>
                      ) : (
                        <span className="subtle">Not triaged</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          )}
        </table>
      </div>
    </Panel>
  );

  return (
    <>
      <PageHeader
        title="Telemetry"
        description="Raw host snapshots received from agents: interface counters, RDMA queue-pair stats and kernel log tail."
      />

      <div className={selected ? 'layout-aside-wide' : undefined}>
        {table}
        {selected && (
          <div className="detail-pane">
            <Panel
              title="Event detail"
              actions={
                <button className="btn btn-ghost btn-sm btn-icon" onClick={() => setSelectedId(null)} aria-label="Close event detail">
                  <X size={14} />
                </button>
              }
            >
              <div className="stack">
                <div className="row wrap">
                  <SignalBadge tone={eventSignal(selected)} />
                  {selIncident ? (
                    <a className="btn btn-sm" href={hrefFor('incident-detail', selIncident.key)}>
                      Open incident
                    </a>
                  ) : selDecision ? (
                    <Badge>Triaged · no action</Badge>
                  ) : null}
                </div>
                {selDecision && (
                  <dl className="kv">
                    <dt>Rule</dt>
                    <dd className="mono">
                      {selDecision.rule_action} · {selDecision.rule_reason}
                    </dd>
                    <dt>Log class</dt>
                    <dd className="mono">{selDecision.log_class || '—'}</dd>
                    <dt>ML priority</dt>
                    <dd className="num">{selDecision.ml_priority?.toFixed(2) ?? '—'}</dd>
                    <dt>Playbook</dt>
                    <dd className="mono">{selDecision.playbook || '—'}</dd>
                  </dl>
                )}
                <EventEvidence event={selected} />
              </div>
            </Panel>
          </div>
        )}
      </div>
    </>
  );
};

const SignalBadge: React.FC<{ tone: Exclude<Tone, 'info' | 'neutral'> }> = ({ tone }) => (
  <Badge tone={tone}>{SIGNAL_LABEL[tone]}</Badge>
);
