import React, { useEffect, useRef } from 'react';
import { AlertTriangle, CheckCircle2, ChevronLeft, ChevronRight, Info, Search, X, XCircle } from 'lucide-react';
import { Incident, IncidentState, Severity, SEVERITY_HELP, STATE_META } from '../lib/incidents';

export type Tone = 'crit' | 'warn' | 'ok' | 'info' | 'neutral';

const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(' ');

export const Badge: React.FC<{ tone?: Tone; mono?: boolean; title?: string; children: React.ReactNode }> = ({
  tone = 'neutral',
  mono,
  title,
  children,
}) => (
  <span className={cx('badge', tone !== 'neutral' && `badge-${tone}`, mono && 'badge-mono')} title={title}>
    {children}
  </span>
);

export const StatusDot: React.FC<{ tone: Tone; label?: React.ReactNode; live?: boolean; title?: string }> = ({
  tone,
  label,
  live,
  title,
}) => (
  <span className="status" title={title}>
    <span className={cx('dot', `dot-${tone}`, live && 'dot-live')} aria-hidden />
    {label}
  </span>
);

export const SeverityTag: React.FC<{ severity: Severity }> = ({ severity }) => (
  <span className={`sev sev-${severity.toLowerCase()}`} title={SEVERITY_HELP}>
    <span className="sev-bar" aria-hidden />
    {severity}
  </span>
);

export const StateBadge: React.FC<{ state: IncidentState }> = ({ state }) => {
  const m = STATE_META[state];
  return <StatusDot tone={m.tone} label={m.label} />;
};

export const RiskBadge: React.FC<{ risk?: string }> = ({ risk }) => {
  if (!risk) return <span className="subtle">—</span>;
  const tone: Tone = risk === 'high' ? 'crit' : risk === 'medium' ? 'warn' : 'ok';
  return <Badge tone={tone}>{risk.charAt(0).toUpperCase() + risk.slice(1)} risk</Badge>;
};

export const Meter: React.FC<{ value?: number; title?: string }> = ({ value, title }) => {
  if (value === undefined || value === null) return <span className="subtle">—</span>;
  const v = Math.max(0, Math.min(1, value));
  const level = v >= 0.85 ? 'high' : v >= 0.6 ? 'mid' : 'low';
  return (
    <span className="meter" title={title}>
      <span className="meter-track">
        <span className={`meter-fill ${level}`} style={{ width: `${v * 100}%`, display: 'block' }} />
      </span>
      <span className="meter-value">{v.toFixed(2)}</span>
    </span>
  );
};

export const PageHeader: React.FC<{
  title: React.ReactNode;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  breadcrumb?: React.ReactNode;
}> = ({ title, description, actions, breadcrumb }) => (
  <div className="page-header">
    <div style={{ minWidth: 0 }}>
      {breadcrumb && <nav className="breadcrumb" aria-label="Breadcrumb">{breadcrumb}</nav>}
      <h1 className="page-title">{title}</h1>
      {description && <p className="page-desc">{description}</p>}
    </div>
    {actions && <div className="page-actions">{actions}</div>}
  </div>
);

export const Panel: React.FC<{
  title?: React.ReactNode;
  count?: number;
  sub?: React.ReactNode;
  actions?: React.ReactNode;
  footer?: React.ReactNode;
  toolbar?: React.ReactNode;
  className?: string;
  bodyClassName?: string;
  flush?: boolean;
  id?: string;
  children?: React.ReactNode;
}> = ({ title, count, sub, actions, footer, toolbar, className, bodyClassName, flush, id, children }) => (
  <section className={cx('panel', className)} aria-labelledby={id}>
    {(title || actions) && (
      <header className="panel-header">
        <div style={{ minWidth: 0 }}>
          {title && (
            <h2 className="panel-title" id={id}>
              {title}
              {count !== undefined && <span className="count">{count}</span>}
            </h2>
          )}
          {sub && <div className="panel-sub">{sub}</div>}
        </div>
        {actions && <div className="row">{actions}</div>}
      </header>
    )}
    {toolbar && <div className="toolbar">{toolbar}</div>}
    {flush ? children : <div className={cx('panel-body', bodyClassName)}>{children}</div>}
    {footer && <footer className="panel-footer">{footer}</footer>}
  </section>
);

export const EmptyState: React.FC<{
  icon?: React.ReactNode;
  title: React.ReactNode;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  compact?: boolean;
}> = ({ icon, title, description, actions, compact }) => (
  <div className={cx('empty', compact && 'compact')}>
    {icon && <div style={{ color: 'var(--text-4)' }}>{icon}</div>}
    <div className="empty-title">{title}</div>
    {description && <div className="empty-desc">{description}</div>}
    {actions && <div className="empty-actions">{actions}</div>}
  </div>
);

const BANNER_ICON: Record<Tone, React.ReactNode> = {
  crit: <XCircle size={16} />,
  warn: <AlertTriangle size={16} />,
  ok: <CheckCircle2 size={16} />,
  info: <Info size={16} />,
  neutral: <Info size={16} />,
};

export const Banner: React.FC<{
  tone?: Tone;
  title?: React.ReactNode;
  actions?: React.ReactNode;
  children?: React.ReactNode;
}> = ({ tone = 'info', title, actions, children }) => (
  <div className={cx('banner', tone !== 'info' && tone !== 'neutral' && `banner-${tone}`)} role={tone === 'crit' ? 'alert' : 'status'}>
    {BANNER_ICON[tone]}
    <div style={{ minWidth: 0 }}>
      {title && <div className="banner-title">{title}</div>}
      {children && <div className="muted" style={{ color: 'var(--text-2)' }}>{children}</div>}
    </div>
    {actions && <div className="banner-actions">{actions}</div>}
  </div>
);

export interface SegOption<T extends string> {
  value: T;
  label: React.ReactNode;
  count?: number;
}

export function Segmented<T extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: SegOption<T>[];
  value: T;
  onChange: (v: T) => void;
  label: string;
}) {
  return (
    <div className="segmented" role="group" aria-label={label}>
      {options.map((o) => (
        <button key={o.value} type="button" aria-pressed={value === o.value} onClick={() => onChange(o.value)}>
          {o.label}
          {o.count !== undefined && <span className="seg-count">{o.count}</span>}
        </button>
      ))}
    </div>
  );
}

export const SearchInput: React.FC<{
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  width?: number | string;
  label?: string;
}> = ({ value, onChange, placeholder, width = 260, label }) => (
  <div className="input-icon" style={{ width }}>
    <Search size={14} />
    <input
      className="input"
      type="search"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      aria-label={label || placeholder}
    />
  </div>
);

export const SkeletonRows: React.FC<{ rows?: number; cols?: number }> = ({ rows = 5, cols = 5 }) => (
  <tbody aria-busy="true">
    {Array.from({ length: rows }).map((_, r) => (
      <tr key={r}>
        {Array.from({ length: cols }).map((__, c) => (
          <td key={c}>
            <div className="skeleton" style={{ width: `${50 + ((r * 7 + c * 13) % 45)}%` }} />
          </td>
        ))}
      </tr>
    ))}
  </tbody>
);

export const Pagination: React.FC<{
  page: number;
  pageSize: number;
  total: number;
  onPage: (p: number) => void;
}> = ({ page, pageSize, total, onPage }) => {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : page * pageSize + 1;
  const to = Math.min(total, (page + 1) * pageSize);
  return (
    <>
      <span className="num">
        {from}–{to} of {total}
      </span>
      <div className="pagination">
        <button className="btn btn-sm btn-icon" onClick={() => onPage(page - 1)} disabled={page <= 0} aria-label="Previous page">
          <ChevronLeft size={14} />
        </button>
        <span className="num muted">
          {page + 1} / {pages}
        </span>
        <button className="btn btn-sm btn-icon" onClick={() => onPage(page + 1)} disabled={page >= pages - 1} aria-label="Next page">
          <ChevronRight size={14} />
        </button>
      </div>
    </>
  );
};

/** Clamp a page index when the underlying list shrinks. */
export function usePageClamp(page: number, setPage: (p: number) => void, total: number, pageSize: number) {
  useEffect(() => {
    const max = Math.max(0, Math.ceil(total / pageSize) - 1);
    if (page > max) setPage(max);
  }, [page, total, pageSize, setPage]);
}

export const Modal: React.FC<{
  open: boolean;
  onClose: () => void;
  title: React.ReactNode;
  footer?: React.ReactNode;
  width?: number;
  children?: React.ReactNode;
}> = ({ open, onClose, title, footer, width, children }) => {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const node = ref.current;
    const focusables = () =>
      Array.from(
        node?.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])') ?? [],
      );
    (focusables()[1] ?? focusables()[0])?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
      } else if (e.key === 'Tab') {
        const els = focusables();
        if (!els.length) return;
        const first = els[0];
        const last = els[els.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      previouslyFocused?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={typeof title === 'string' ? title : undefined} ref={ref} style={width ? { width: `min(${width}px, calc(100vw - 32px))` } : undefined}>
        <div className="modal-header">
          <h2 className="modal-title">{title}</h2>
          <button className="btn btn-ghost btn-sm btn-icon" onClick={onClose} aria-label="Close dialog">
            <X size={16} />
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>
  );
};

/** Compact incident identifier: host-level ids from the orchestrator are long. */
export const IncidentRef: React.FC<{ incident: Incident }> = ({ incident }) => (
  <span className="mono subtle truncate" title={incident.key} style={{ display: 'block', maxWidth: 260 }}>
    {incident.key}
  </span>
);

export { cx };
