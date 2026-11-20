import React, { useMemo, useState } from 'react';
import { Badge, Banner, EmptyState, PageHeader, Pagination, Panel, SearchInput, SkeletonRows, usePageClamp } from '../components/ui';
import { Incident } from '../lib/incidents';
import { formatDateTime, parseTs } from '../lib/format';
import { hrefFor } from '../lib/routes';
import { AuditEntry } from '../types';
import { CommonPageProps } from './common';

interface Props extends CommonPageProps {
  auditLog: AuditEntry[];
  incidents: Incident[];
}

const PAGE_SIZE = 30;

export const AuditTrailPage: React.FC<Props> = ({ auditLog, incidents, loaded }) => {
  const [host, setHost] = useState('');
  const [playbook, setPlaybook] = useState('');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);

  const incidentByEvent = useMemo(() => new Map(incidents.filter((i) => i.eventId).map((i) => [i.eventId!, i])), [incidents]);
  const hosts = useMemo(() => [...new Set(auditLog.map((a) => a.host).filter((h): h is string => !!h))].sort(), [auditLog]);
  const playbooks = useMemo(() => [...new Set(auditLog.map((a) => a.playbook).filter((p): p is string => !!p))].sort(), [auditLog]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return [...auditLog]
      .sort((a, b) => (parseTs(b.ts)?.getTime() ?? 0) - (parseTs(a.ts)?.getTime() ?? 0))
      .filter((a) => {
        if (host && a.host !== host) return false;
        if (playbook && a.playbook !== playbook) return false;
        if (q && ![a.event_id, a.host, a.playbook, a.reason, a.status].filter(Boolean).join(' ').toLowerCase().includes(q)) return false;
        return true;
      });
  }, [auditLog, host, playbook, search]);

  usePageClamp(page, setPage, filtered.length, PAGE_SIZE);
  const pageItems = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const filtersActive = !!(host || playbook || search);
  const dryRun = auditLog.some((a) => /dry/i.test(a.status || ''));
  const reset = () => {
    setHost('');
    setPlaybook('');
    setSearch('');
  };

  return (
    <>
      <PageHeader
        title="Execution & Audit Log"
        description="Append-only record of every playbook the controller triggered, with the reason and the originating event."
      />

      {dryRun && (
        <Banner title="Playbooks run in dry-run mode">
          The API controller records playbook triggers without applying changes to hosts. Use{' '}
          <span className="mono">ansible-playbook</span> against <span className="mono">infra/inventory.ini</span> to execute for real.
        </Banner>
      )}

      <Panel
        flush
        toolbar={
          <>
            <select className="select" value={host} onChange={(e) => setHost(e.target.value)} aria-label="Host">
              <option value="">All hosts</option>
              {hosts.map((h) => (
                <option key={h} value={h}>
                  {h}
                </option>
              ))}
            </select>
            <select className="select" value={playbook} onChange={(e) => setPlaybook(e.target.value)} aria-label="Playbook">
              <option value="">All playbooks</option>
              {playbooks.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
            <div style={{ flex: 1 }} />
            <SearchInput value={search} onChange={setSearch} placeholder="Event, reason, status" width={240} />
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
                <th style={{ width: 200 }}>Timestamp (UTC)</th>
                <th style={{ width: 110 }}>Host</th>
                <th style={{ width: 200 }}>Playbook</th>
                <th>Trigger reason</th>
                <th style={{ width: 150 }}>Status</th>
                <th style={{ width: 120 }}>Incident</th>
              </tr>
            </thead>
            {!loaded ? (
              <SkeletonRows rows={8} cols={6} />
            ) : pageItems.length === 0 ? (
              <tbody>
                <tr>
                  <td colSpan={6} style={{ padding: 0 }}>
                    {auditLog.length === 0 ? (
                      <EmptyState title="No playbooks have been triggered" description="Entries are written when a triage decision selects a remediation playbook." />
                    ) : (
                      <EmptyState
                        compact
                        title="No entries match these filters"
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
                {pageItems.map((a, idx) => {
                  const inc = a.event_id ? incidentByEvent.get(a.event_id) : undefined;
                  return (
                    <tr key={`${a.ts}-${idx}`}>
                      <td className="num nowrap muted">{formatDateTime(a.ts).replace(' UTC', '')}</td>
                      <td className="mono nowrap">{a.host || '—'}</td>
                      <td className="mono nowrap">{a.playbook || '—'}</td>
                      <td style={{ maxWidth: 0 }}>
                        <div className="mono truncate" title={a.reason}>
                          {a.reason || '—'}
                        </div>
                        {a.event_id && (
                          <a className="cell-secondary mono truncate" style={{ display: 'block' }} href={hrefFor('events', undefined, { event: a.event_id })}>
                            {a.event_id}
                          </a>
                        )}
                      </td>
                      <td className="nowrap">
                        <Badge tone={/fail|error/i.test(a.status || '') ? 'crit' : /complete|success|ok/i.test(a.status || '') ? 'ok' : 'info'}>
                          {a.status || 'recorded'}
                        </Badge>
                      </td>
                      <td className="nowrap">
                        {inc ? <a href={hrefFor('incident-detail', inc.key)}>View · {inc.severity}</a> : <span className="subtle">—</span>}
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
