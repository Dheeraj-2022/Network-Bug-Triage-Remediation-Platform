import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertOctagon,
  Activity,
  ChevronDown,
  Cpu,
  Database,
  Pause,
  Play,
  RefreshCw,
  Server,
  Trash2,
  Zap,
} from 'lucide-react';
import { Incident } from '../lib/incidents';
import { relativeTime } from '../lib/format';
import { TelemetryEvent } from '../types';

interface TopbarProps {
  incidents: Incident[];
  events: TelemetryEvent[];
  onOpenIncident: (key: string) => void;
  onOpenEvent: (eventId: string) => void;
  onOpenHost: (host: string) => void;
  onInject: () => void;
  onLoadSamples: () => void;
  onTrainModel: () => void;
  onClearState: () => void;
  onRefresh: () => void;
  isInjecting: boolean;
  isLoadingSamples: boolean;
  isTraining: boolean;
  isRefreshing: boolean;
  isLive: boolean;
  setIsLive: (val: boolean) => void;
  lastUpdated: number | null;
  connection: 'connecting' | 'online' | 'offline';
}

type Result = { kind: 'incident' | 'host' | 'event'; id: string; label: string; meta: string };

function useNow(intervalMs = 1000) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(t);
  }, [intervalMs]);
  return now;
}

const GlobalSearch: React.FC<Pick<TopbarProps, 'incidents' | 'events' | 'onOpenIncident' | 'onOpenEvent' | 'onOpenHost'>> = ({
  incidents,
  events,
  onOpenIncident,
  onOpenEvent,
  onOpenHost,
}) => {
  const [q, setQ] = useState('');
  const [open, setOpen] = useState(false);
  const [cursor, setCursor] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (e.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(t.tagName)) {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    const onClick = (e: MouseEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('mousedown', onClick);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('mousedown', onClick);
    };
  }, []);

  const results = useMemo<Result[]>(() => {
    const term = q.trim().toLowerCase();
    if (!term) return [];
    const inc: Result[] = incidents
      .filter((i) => [i.key, i.host, i.title, i.faultDomain, i.playbook ?? ''].some((s) => s.toLowerCase().includes(term)))
      .slice(0, 6)
      .map((i) => ({ kind: 'incident', id: i.key, label: i.title, meta: i.key }));
    const hostSet = new Set<string>();
    for (const e of events) if (e.host && e.host.toLowerCase().includes(term)) hostSet.add(e.host);
    const hosts: Result[] = [...hostSet].slice(0, 5).map((h) => ({ kind: 'host', id: h, label: h, meta: 'Filter telemetry by host' }));
    const evs: Result[] = events
      .filter((e) => e.event_id?.toLowerCase().includes(term) || (e.dmesg_tail || '').toLowerCase().includes(term))
      .slice(-6)
      .reverse()
      .map((e) => ({ kind: 'event', id: e.event_id, label: e.event_id, meta: `${e.host} · ${e.dmesg_tail || ''}` }));
    return [...inc, ...hosts, ...evs];
  }, [q, incidents, events]);

  useEffect(() => setCursor(0), [q]);

  const choose = (r: Result) => {
    setOpen(false);
    setQ('');
    inputRef.current?.blur();
    if (r.kind === 'incident') onOpenIncident(r.id);
    else if (r.kind === 'host') onOpenHost(r.id);
    else onOpenEvent(r.id);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setCursor((c) => Math.min(results.length - 1, c + 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setCursor((c) => Math.max(0, c - 1));
    } else if (e.key === 'Enter' && results[cursor]) {
      e.preventDefault();
      choose(results[cursor]);
    } else if (e.key === 'Escape') {
      setOpen(false);
      inputRef.current?.blur();
    }
  };

  const groups: { kind: Result['kind']; label: string; icon: React.ReactNode }[] = [
    { kind: 'incident', label: 'Incidents', icon: <AlertOctagon size={14} /> },
    { kind: 'host', label: 'Hosts', icon: <Server size={14} /> },
    { kind: 'event', label: 'Telemetry events', icon: <Activity size={14} /> },
  ];

  return (
    <div ref={wrapRef} style={{ position: 'relative', width: 'min(420px, 40vw)' }}>
      <div className="input-icon">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
          <circle cx="11" cy="11" r="7" />
          <path d="m20 20-3.5-3.5" />
        </svg>
        <input
          ref={inputRef}
          className="input"
          type="search"
          value={q}
          placeholder="Search incidents, hosts, event IDs"
          aria-label="Search incidents, hosts and events"
          role="combobox"
          aria-expanded={open && !!q}
          aria-controls="global-search-results"
          onChange={(e) => {
            setQ(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          style={{ paddingRight: 28, background: 'var(--surface-2)' }}
        />
        {!q && (
          <span className="kbd hide-sm" style={{ position: 'absolute', right: 8 }} aria-hidden>
            /
          </span>
        )}
      </div>
      {open && q.trim() && (
        <div className="search-pop" id="global-search-results" role="listbox">
          {results.length === 0 && <div className="search-empty">No incidents, hosts or events match “{q}”.</div>}
          {groups.map((g) => {
            const items = results.map((r, idx) => ({ r, idx })).filter((x) => x.r.kind === g.kind);
            if (!items.length) return null;
            return (
              <div key={g.kind}>
                <div className="search-group">{g.label}</div>
                {items.map(({ r, idx }) => (
                  <button
                    key={`${r.kind}-${r.id}`}
                    className="search-result"
                    role="option"
                    aria-selected={idx === cursor}
                    onMouseEnter={() => setCursor(idx)}
                    onClick={() => choose(r)}
                  >
                    <span className="subtle">{g.icon}</span>
                    <span className="truncate" style={{ flex: 1 }}>
                      {r.kind === 'event' ? <span className="mono">{r.label}</span> : r.label}
                    </span>
                    <span className="subtle truncate mono" style={{ maxWidth: 200, fontSize: 11 }}>
                      {r.meta}
                    </span>
                  </button>
                ))}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

const ActionsMenu: React.FC<Pick<TopbarProps, 'onInject' | 'onLoadSamples' | 'onTrainModel' | 'onClearState' | 'isInjecting' | 'isLoadingSamples' | 'isTraining'>> = ({
  onInject,
  onLoadSamples,
  onTrainModel,
  onClearState,
  isInjecting,
  isLoadingSamples,
  isTraining,
}) => {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const busy = isInjecting || isLoadingSamples || isTraining;

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        const items = Array.from(ref.current?.querySelectorAll<HTMLButtonElement>('.menu-item:not(:disabled)') ?? []);
        const i = items.indexOf(document.activeElement as HTMLButtonElement);
        const next = e.key === 'ArrowDown' ? (i + 1) % items.length : (i - 1 + items.length) % items.length;
        items[next]?.focus();
      }
    };
    document.addEventListener('mousedown', onClick);
    document.addEventListener('keydown', onKey);
    ref.current?.querySelector<HTMLButtonElement>('.menu-item')?.focus();
    return () => {
      document.removeEventListener('mousedown', onClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const run = (fn: () => void) => () => {
    setOpen(false);
    fn();
  };

  return (
    <div className="menu-anchor" ref={ref}>
      <button className="btn" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        {busy ? <RefreshCw size={14} className="spin" /> : <Database size={14} />}
        <span className="hide-sm">{isInjecting ? 'Injecting…' : isLoadingSamples ? 'Loading…' : isTraining ? 'Training…' : 'Data'}</span>
        <ChevronDown size={14} />
      </button>
      {open && (
        <div className="menu" role="menu">
          <div className="menu-label">Ingest</div>
          <button className="menu-item" role="menuitem" onClick={run(onInject)} disabled={isInjecting}>
            <Zap size={14} />
            <span>
              Inject synthetic events…
              <div className="desc">Generate host telemetry, optionally with faults</div>
            </span>
          </button>
          <button className="menu-item" role="menuitem" onClick={run(onLoadSamples)} disabled={isLoadingSamples}>
            <Database size={14} />
            <span>
              Load sample fixtures
              <div className="desc">Replay up to 20 events from data/sample_events.json</div>
            </span>
          </button>
          <div className="menu-sep" />
          <div className="menu-label">Model</div>
          <button className="menu-item" role="menuitem" onClick={run(onTrainModel)} disabled={isTraining}>
            <Cpu size={14} />
            <span>
              Train triage model
              <div className="desc">Retrain the XGBoost priority classifier</div>
            </span>
          </button>
          <div className="menu-sep" />
          <button className="menu-item danger" role="menuitem" onClick={run(onClearState)}>
            <Trash2 size={14} />
            <span>Reset platform state…</span>
          </button>
        </div>
      )}
    </div>
  );
};

export const Topbar: React.FC<TopbarProps> = (props) => {
  const { onRefresh, isRefreshing, isLive, setIsLive, lastUpdated, connection } = props;
  const now = useNow();

  return (
    <header className="topbar">
      <GlobalSearch {...props} />
      <div className="topbar-spacer" />

      <span className="muted hide-md" style={{ fontSize: 12 }} aria-live="off">
        {connection === 'offline' ? (
          <span style={{ color: 'var(--crit)' }}>Controller unreachable</span>
        ) : lastUpdated ? (
          <>Updated {relativeTime(new Date(lastUpdated).toISOString(), now)}</>
        ) : (
          'Connecting…'
        )}
      </span>

      <div className="segmented" role="group" aria-label="Auto-refresh">
        <button
          type="button"
          aria-pressed={isLive}
          onClick={() => setIsLive(!isLive)}
          title={isLive ? 'Pause auto-refresh' : 'Resume auto-refresh (every 5 s)'}
        >
          {isLive ? <Pause size={12} /> : <Play size={12} />}
          <span className="hide-sm">{isLive ? 'Live · 5s' : 'Paused'}</span>
        </button>
        <button type="button" onClick={onRefresh} title="Refresh now" aria-label="Refresh now">
          <RefreshCw size={12} className={isRefreshing ? 'spin' : undefined} />
        </button>
      </div>

      <div className="topbar-divider" />
      <ActionsMenu {...props} />
    </header>
  );
};
