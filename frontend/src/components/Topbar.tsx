import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertOctagon,
  Activity,
  ChevronDown,
  Cpu,
  Database,
  Mic,
  Pause,
  Play,
  RefreshCw,
  Server,
  Trash2,
  Zap,
} from 'lucide-react';
import { Incident } from '../lib/incidents';
import { AIStatus, PageId, TelemetryEvent } from '../types';

interface TopbarProps {
  incidents: Incident[];
  events: TelemetryEvent[];
  onOpenIncident: (key: string) => void;
  onOpenEvent: (eventId: string) => void;
  onOpenHost: (host: string) => void;
  onNavigate: (page: PageId) => void;
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
  remediationMode?: string;
  aiStatus?: AIStatus | null;
}

type Result = { kind: 'incident' | 'host' | 'event'; id: string; label: string; meta: string };

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
      if ((e.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(t.tagName)) || ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k')) {
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
    <div ref={wrapRef} style={{ position: 'relative', width: 'min(260px, 28vw)' }}>
      <div className="input-icon">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
          <circle cx="11" cy="11" r="7" />
          <path d="m20 20-3.5-3.5" />
        </svg>
        <input
          ref={inputRef}
          className="input"
          type="search"
          value={q}
          placeholder="Cmd+K search..."
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
          style={{ paddingRight: 42, background: 'var(--bg)', height: 30, fontSize: 12 }}
        />
        {!q && (
          <span className="kbd hide-sm" style={{ position: 'absolute', right: 6, fontSize: 10 }} aria-hidden>
            ⌘K
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
                    <span className="subtle truncate mono" style={{ maxWidth: 160, fontSize: 11 }}>
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
    };
    document.addEventListener('mousedown', onClick);
    document.addEventListener('keydown', onKey);
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
      <button className="btn btn-sm" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((o) => !o)} style={{ height: 30 }}>
        {busy ? <RefreshCw size={13} className="spin" /> : <Database size={13} />}
        <span className="hide-sm">{isInjecting ? 'INJECTING' : isLoadingSamples ? 'LOADING' : isTraining ? 'TRAINING' : 'OPS'}</span>
        <ChevronDown size={13} />
      </button>
      {open && (
        <div className="menu" role="menu">
          <div className="menu-label">Telemetry &amp; Fixtures</div>
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
          <div className="menu-label">Triage Model</div>
          <button className="menu-item" role="menuitem" onClick={run(onTrainModel)} disabled={isTraining}>
            <Cpu size={14} />
            <span>
              Train XGBoost triage model
              <div className="desc">Retrain priority &amp; localization classifier</div>
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
  const { onNavigate, onRefresh, isRefreshing, isLive, setIsLive, connection, remediationMode, aiStatus } = props;

  const modeLabel = (remediationMode || 'simulate').toUpperCase();
  const aiLabel = !aiStatus
    ? 'AI: CHECKING'
    : aiStatus.uses_llm
      ? `GEMINI: ${(aiStatus.vertex_model || 'VERTEX').toUpperCase()}`
      : aiStatus.enabled
        ? 'HEURISTIC: LOCAL OFFLINE'
        : 'AI: DISABLED';

  return (
    <header className="topbar">
      <div className="row" style={{ gap: 8, flexWrap: 'nowrap' }}>
        <span className={`status-chip ${connection === 'online' ? 'ok' : connection === 'offline' ? 'crit' : ''}`}>
          <span className={`dot ${connection === 'online' ? 'dot-ok' : connection === 'offline' ? 'dot-crit' : 'dot-neutral'}`} />
          {connection === 'online' ? 'API CONNECTED' : connection === 'offline' ? 'API OFFLINE' : 'CONNECTING'}
        </span>

        <span className={`status-chip hide-md ${modeLabel === 'ANSIBLE' ? 'crit' : 'warn'}`}>
          <span className={`dot ${modeLabel === 'ANSIBLE' ? 'dot-crit' : 'dot-warn'}`} />
          MODE: {modeLabel === 'SIMULATE' ? 'SIMULATED' : modeLabel}
        </span>

        <span className="status-chip hide-md" title={aiStatus?.reason || aiStatus?.llm_backend || 'AI engine status'}>
          <Cpu size={11} />
          {aiLabel}
        </span>
      </div>

      <div className="topbar-spacer" />

      <GlobalSearch {...props} />

      <button
        type="button"
        className="btn btn-sm"
        onClick={() => onNavigate('voice')}
        style={{ height: 30, textTransform: 'uppercase', letterSpacing: '0.04em' }}
        title="Open Voice Operations Assistant"
      >
        <Mic size={13} />
        <span className="hide-sm">Voice Ops</span>
      </button>

      <div className="segmented" role="group" aria-label="Auto-refresh">
        <button
          type="button"
          aria-pressed={isLive}
          onClick={() => setIsLive(!isLive)}
          title={isLive ? 'Pause auto-refresh' : 'Resume auto-refresh (5s)'}
          style={{ height: 28 }}
        >
          {isLive ? <Pause size={11} /> : <Play size={11} />}
          <span className="hide-sm mono" style={{ fontSize: 10 }}>{isLive ? '5S' : 'PAUSED'}</span>
        </button>
        <button type="button" onClick={onRefresh} title="Refresh now" aria-label="Refresh now" style={{ height: 28 }}>
          <RefreshCw size={11} className={isRefreshing ? 'spin' : undefined} />
        </button>
      </div>

      <ActionsMenu {...props} />

      <button
        type="button"
        className="btn btn-sm btn-primary"
        onClick={() => onNavigate('demo')}
        style={{ height: 30, textTransform: 'uppercase', letterSpacing: '0.05em' }}
      >
        <Play size={11} />
        <span className="hide-sm">Load MTU Demo</span>
      </button>
    </header>
  );
};
