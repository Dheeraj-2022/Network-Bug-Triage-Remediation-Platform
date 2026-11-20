import React, { useMemo, useState } from 'react';
import { Badge, EmptyState, Meter, PageHeader, Pagination, Panel, SearchInput, Segmented, SkeletonRows, usePageClamp } from '../components/ui';
import { Incident } from '../lib/incidents';
import { formatDateTime, formatTime, parseTs } from '../lib/format';
import { hrefFor } from '../lib/routes';
import { Decision } from '../types';
import { CommonPageProps } from './common';

interface Props extends CommonPageProps {
  decisions: Decision[];
  incidents: Incident[];
  query: URLSearchParams;
}

type Outcome = 'all' | 'remediate' | 'none';
const PAGE_SIZE = 30;

export const DecisionsPage: React.FC<Props> = ({ decisions, incidents, query, loaded, navigate }) => {
  const [outcome, setOutcome] = useState<Outcome>((query.get('outcome') as Outcome) || 'all');
  const [host, setHost] = useState(query.get('host') || '');
  const [logClass, setLogClass] = useState('');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);

  const incidentByEvent = useMemo(() => new Map(incidents.filter((i) => i.eventId).map((i) => [i.eventId!, i])), [incidents]);
  const hosts = useMemo(() => [...new Set(decisions.map((d) => d.host).filter((h): h is string => !!h))].sort(), [decisions]);
  const classes = useMemo(() => [...new Set(decisions.map((d) => d.log_class).filter((c): c is string => !!c))].sort(), [decisions]);

  const sorted = useMemo(
    () => [...decisions].sort((a, b) => (parseTs(b.ts)?.getTime() ?? 0) - (parseTs(a.ts)?.getTime() ?? 0)),
    [decisions],
  );

  const counts = useMemo(() => {
    const c = { all: decisions.length, remediate: 0, none: 0 };
    for (const d of decisions) c[d.remediate ? 'remediate' : 'none'] += 1;
    return c;
  }, [decisions]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return sorted.filter((d) => {
      if (outcome === 'remediate' && !d.remediate) return false;
      if (outcome === 'none' && d.remediate) return false;
      if (host && d.host !== host) return false;
      if (logClass && d.log_class !== logClass) return false;
      if (q) {
        const hay = [d.event_id, d.host, d.rule_reason, d.playbook, d.ml_localization, d.ai?.root_cause].filter(Boolean).join(' ').toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [sorted, outcome, host, logClass, search]);

  usePageClamp(page, setPage, filtered.length, PAGE_SIZE);
  const pageItems = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const filtersActive = !!(host || logClass || search || outcome !== 'all');
  const reset = () => {
    setOutcome('all');
    setHost('');
    setLogClass('');
    setSearch('');
  };

  return (
    <>
      <PageHeader
        title="Triage Decisions"
        description="Per-event output of the rules engine, log classifier and XGBoost priority model. An event is flagged when a rule threshold is breached or the priority score is ≥ 0.85."
      />

      <Panel
        flush
        toolbar={
          <>
            <Segmented<Outcome>
              label="Outcome"
              value={outcome}
              onChange={(v) => {
                setOutcome(v);
                setPage(0);
              }}
              options={[
                { value: 'all', label: 'All', count: counts.all },
                { value: 'remediate', label: 'Flagged', count: counts.remediate },
                { value: 'none', label: 'No action', count: counts.none },
              ]}
            />
            <select className="select" value={host} onChange={(e) => setHost(e.target.value)} aria-label="Host">
              <option value="">All hosts</option>
              {hosts.map((h) => (
                <option key={h} value={h}>
                  {h}
                </option>
              ))}
            </select>
            <select className="select" value={logClass} onChange={(e) => setLogClass(e.target.value)} aria-label="Log class">
              <option value="">All log classes</option>
              {classes.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
            <div style={{ flex: 1 }} />
            <SearchInput value={search} onChange={setSearch} placeholder="Event, rule reason, playbook" width={240} />
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
                <span>Newest first</span>
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
                <th style={{ width: 100 }}>Host</th>
                <th>Rule engine</th>
                <th style={{ width: 130 }}>Log class</th>
                <th style={{ width: 130 }} title="XGBoost priority score">
                  ML priority
                </th>
                <th style={{ width: 130 }}>Localization</th>
                <th style={{ width: 170 }}>Outcome</th>
              </tr>
            </thead>
            {!loaded ? (
              <SkeletonRows rows={8} cols={7} />
            ) : pageItems.length === 0 ? (
              <tbody>
                <tr>
                  <td colSpan={7} style={{ padding: 0 }}>
                    {decisions.length === 0 ? (
                      <EmptyState title="No triage decisions yet" description="Each ingested event produces one decision." />
                    ) : (
                      <EmptyState
                        compact
                        title="No decisions match these filters"
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
                {pageItems.map((d, idx) => {
                  const inc = d.event_id ? incidentByEvent.get(d.event_id) : undefined;
                  return (
                    <tr key={`${d.event_id ?? d.ts}-${idx}`}>
                      <td className="num muted nowrap" title={formatDateTime(d.ts)}>
                        {formatTime(d.ts)}
                      </td>
                      <td className="mono nowrap">{d.host || '—'}</td>
                      <td style={{ maxWidth: 0, width: '100%' }}>
                        <div className="row" style={{ gap: 6 }}>
                          {d.rule_action === 'remediate' ? <Badge tone="crit">breach</Badge> : <Badge>ok</Badge>}
                          <span className="mono truncate" title={d.rule_reason}>
                            {d.rule_reason || '—'}
                          </span>
                        </div>
                        {d.event_id && (
                          <a className="cell-secondary mono truncate" style={{ display: 'block' }} href={hrefFor('events', undefined, { event: d.event_id })}>
                            {d.event_id}
                          </a>
                        )}
                      </td>
                      <td className="mono nowrap">{d.log_class || '—'}</td>
                      <td>
                        <Meter value={d.ml_priority} />
                      </td>
                      <td className="mono nowrap">{d.ml_localization || '—'}</td>
                      <td className="nowrap">
                        {d.remediate || inc ? (
                          <div>
                            {inc ? (
                              <button className="btn-link" onClick={() => navigate('incident-detail', inc.key)}>
                                Incident · {inc.severity}
                              </button>
                            ) : (
                              <span>Flagged</span>
                            )}
                            <div className="cell-secondary mono truncate" style={{ maxWidth: 170 }}>
                              {d.ai?.ai_playbook || d.playbook || 'no playbook'}
                            </div>
                          </div>
                        ) : (
                          <span className="muted">No action</span>
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
    </>
  );
};
