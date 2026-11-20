import React, { useMemo, useState } from 'react';
import { Database, Zap } from 'lucide-react';
import { IncidentTable } from '../components/IncidentTable';
import { EmptyState, PageHeader, Pagination, Panel, SearchInput, Segmented, usePageClamp } from '../components/ui';
import { compareIncidents, Incident, SEVERITY_ORDER, STATE_META } from '../lib/incidents';
import { domainLabel, parseTs } from '../lib/format';
import { CommonPageProps } from './common';

type View = 'action' | 'active' | 'closed' | 'all';
type Sort = 'queue' | 'newest' | 'priority' | 'confidence';
const PAGE_SIZE = 25;

interface IncidentsPageProps extends CommonPageProps {
  incidents: Incident[];
  query: URLSearchParams;
}

export const IncidentsPage: React.FC<IncidentsPageProps> = ({ incidents, query, navigate, loaded, onInject, onLoadSamples, isLoadingSamples }) => {
  const [view, setView] = useState<View>((query.get('view') as View) || 'all');
  const [search, setSearch] = useState(query.get('q') || '');
  const [host, setHost] = useState(query.get('host') || '');
  const [domain, setDomain] = useState('');
  const [sev, setSev] = useState('');
  const [sort, setSort] = useState<Sort>('queue');
  const [page, setPage] = useState(0);

  const hosts = useMemo(() => [...new Set(incidents.map((i) => i.host))].sort(), [incidents]);
  const domains = useMemo(() => [...new Set(incidents.map((i) => i.faultDomain))].sort(), [incidents]);

  const counts = useMemo(() => {
    const c = { action: 0, active: 0, closed: 0, all: incidents.length };
    for (const i of incidents) c[STATE_META[i.state].group] += 1;
    return c;
  }, [incidents]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    const list = incidents.filter((i) => {
      if (view !== 'all' && STATE_META[i.state].group !== view) return false;
      if (host && i.host !== host) return false;
      if (domain && i.faultDomain !== domain) return false;
      if (sev && i.severity !== sev) return false;
      if (q) {
        const hay = [i.key, i.title, i.host, i.playbook, i.ruleReason, i.rootCause, i.eventId].filter(Boolean).join(' ').toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
    const t = (i: Incident) => parseTs(i.ts)?.getTime() ?? 0;
    switch (sort) {
      case 'newest':
        return list.sort((a, b) => t(b) - t(a));
      case 'priority':
        return list.sort((a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity] || b.mlPriority - a.mlPriority);
      case 'confidence':
        return list.sort((a, b) => (b.confidence ?? b.mlPriority) - (a.confidence ?? a.mlPriority));
      default:
        return list.sort(compareIncidents);
    }
  }, [incidents, view, host, domain, sev, search, sort]);

  usePageClamp(page, setPage, filtered.length, PAGE_SIZE);
  const pageItems = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const filtersActive = !!(search || host || domain || sev || view !== 'all');

  const reset = () => {
    setSearch('');
    setHost('');
    setDomain('');
    setSev('');
    setView('all');
  };

  return (
    <>
      <PageHeader
        title="Incident Queue & RCA"
        description="Events that breached a rule threshold or were escalated by the analysis engine, with their remediation state."
      />

      <Panel
        flush
        toolbar={
          <>
            <Segmented<View>
              label="Incident state"
              value={view}
              onChange={(v) => {
                setView(v);
                setPage(0);
              }}
              options={[
                { value: 'all', label: 'All', count: counts.all },
                { value: 'action', label: 'Needs action', count: counts.action },
                { value: 'active', label: 'Remediating', count: counts.active },
                { value: 'closed', label: 'Rejected', count: counts.closed },
              ]}
            />
            <select className="select" value={sev} onChange={(e) => setSev(e.target.value)} aria-label="Priority">
              <option value="">All priorities</option>
              {['P1', 'P2', 'P3', 'P4'].map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
            <select className="select" value={host} onChange={(e) => setHost(e.target.value)} aria-label="Host">
              <option value="">All hosts</option>
              {hosts.map((h) => (
                <option key={h} value={h}>
                  {h}
                </option>
              ))}
            </select>
            <select className="select" value={domain} onChange={(e) => setDomain(e.target.value)} aria-label="Fault domain">
              <option value="">All fault domains</option>
              {domains.map((d) => (
                <option key={d} value={d}>
                  {domainLabel(d)}
                </option>
              ))}
            </select>
            <div style={{ flex: 1 }} />
            <select className="select" value={sort} onChange={(e) => setSort(e.target.value as Sort)} aria-label="Sort by">
              <option value="queue">Sort: queue order</option>
              <option value="newest">Sort: newest</option>
              <option value="priority">Sort: priority</option>
              <option value="confidence">Sort: confidence</option>
            </select>
            <SearchInput value={search} onChange={setSearch} placeholder="Filter by ID, host, playbook" width={240} />
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
                <span />
              )}
              <div className="row">
                <Pagination page={page} pageSize={PAGE_SIZE} total={filtered.length} onPage={setPage} />
              </div>
            </>
          ) : undefined
        }
      >
        <IncidentTable
          incidents={pageItems}
          navigate={navigate}
          loading={!loaded}
          columns={['severity', 'incident', 'host', 'state', 'confidence', 'playbook', 'detected']}
          empty={
            incidents.length === 0 ? (
              <EmptyState
                title="No incidents"
                description="Incidents are opened when an event breaches a rule threshold, the ML priority score is ≥ 0.85, or the analysis engine escalates it."
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
                title="No incidents match these filters"
                actions={
                  <button className="btn btn-sm" onClick={reset}>
                    Clear filters
                  </button>
                }
              />
            )
          }
        />
      </Panel>
    </>
  );
};
