import React, { useState } from 'react';
import { ActivityBucket } from '../lib/incidents';

const pad = (n: number) => String(n).padStart(2, '0');
const hhmm = (t: number) => {
  const d = new Date(t);
  return `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
};

/** Decisions processed per minute, flagged-for-remediation stacked on top. */
export const ActivityChart: React.FC<{ buckets: ActivityBucket[]; height?: number }> = ({ buckets, height = 148 }) => {
  const [hover, setHover] = useState<number | null>(null);
  const width = 720;
  const padL = 30;
  const padB = 20;
  const padT = 10;
  const innerW = width - padL;
  const innerH = height - padB - padT;
  const max = Math.max(1, ...buckets.map((b) => b.total));
  const niceMax = max <= 4 ? max : Math.ceil(max / 4) * 4;
  const bw = innerW / buckets.length;
  const y = (v: number) => padT + innerH - (v / niceMax) * innerH;
  const ticks = niceMax <= 4 ? Array.from({ length: niceMax + 1 }, (_, i) => i) : [0, niceMax / 4, niceMax / 2, (3 * niceMax) / 4, niceMax];
  const hb = hover !== null ? buckets[hover] : null;

  return (
    <div style={{ position: 'relative' }}>
      <svg
        className="chart"
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        style={{ height }}
        role="img"
        aria-label={`Decisions per minute over the last ${buckets.length} minutes`}
        onMouseLeave={() => setHover(null)}
      >
        {ticks.map((t) => (
          <g key={t}>
            <line x1={padL} x2={width} y1={y(t)} y2={y(t)} stroke="#e6e3db" strokeWidth={1} strokeDasharray={t === 0 ? undefined : '2 2'} />
            <text x={padL - 7} y={y(t) + 3} textAnchor="end" fontSize={10} fill="#76736b" fontFamily="var(--font-mono)">
              {t}
            </text>
          </g>
        ))}
        {buckets.map((b, i) => {
          const x = padL + i * bw + 1.5;
          const w = Math.max(1, bw - 3);
          const okCount = b.total - b.flagged;
          return (
            <g key={b.start} onMouseEnter={() => setHover(i)}>
              <rect x={padL + i * bw} y={padT} width={bw} height={innerH} fill={hover === i ? '#efeeea' : 'transparent'} />
              {okCount > 0 && <rect x={x} y={y(b.total)} width={w} height={y(b.flagged) - y(b.total)} rx={1.5} fill="#cfc9be" />}
              {b.flagged > 0 && <rect x={x} y={y(b.flagged)} width={w} height={y(0) - y(b.flagged)} rx={1.5} fill="#b83b2a" />}
            </g>
          );
        })}
        {buckets.map((b, i) =>
          i % 5 === 0 || i === buckets.length - 1 ? (
            <text key={`l${b.start}`} x={padL + i * bw + bw / 2} y={height - 4} textAnchor="middle" fontSize={10} fill="#76736b" fontFamily="var(--font-mono)">
              {hhmm(b.start)}
            </text>
          ) : null,
        )}
      </svg>
      {hb && (
        <div
          style={{
            position: 'absolute',
            top: 4,
            left: `calc(${((padL + (hover! + 0.5) * bw) / width) * 100}% + 8px)`,
            background: 'var(--surface)',
            border: '1px solid var(--border-strong)',
            borderRadius: 'var(--radius)',
            boxShadow: 'var(--shadow-pop)',
            padding: '7px 10px',
            fontSize: 12,
            pointerEvents: 'none',
            whiteSpace: 'nowrap',
            zIndex: 10,
            transform: hover! > buckets.length * 0.7 ? 'translateX(calc(-100% - 16px))' : undefined,
          }}
        >
          <div className="mono strong" style={{ fontSize: 11, marginBottom: 2 }}>{hhmm(hb.start)} UTC</div>
          <div className="num">{hb.total} decisions</div>
          <div className="num" style={{ color: 'var(--crit)', fontWeight: 500 }}>{hb.flagged} flagged for remediation</div>
        </div>
      )}
    </div>
  );
};

export const BarList: React.FC<{
  items: { key: string; label: React.ReactNode; count: number; color?: string }[];
  emptyText?: string;
}> = ({ items, emptyText = 'No data' }) => {
  if (!items.length) return <div className="muted" style={{ fontSize: 12 }}>{emptyText}</div>;
  const max = Math.max(...items.map((i) => i.count));
  return (
    <div className="barlist">
      {items.map((i) => (
        <div className="barlist-row" key={i.key}>
          <span className="truncate" title={typeof i.label === 'string' ? i.label : i.key}>
            {i.label}
          </span>
          <span className="barlist-track">
            <span className="barlist-fill" style={{ width: `${(i.count / max) * 100}%`, display: 'block', background: i.color }} />
          </span>
          <span className="num right mono" style={{ textAlign: 'right', fontSize: 11, color: 'var(--text-2)' }}>
            {i.count}
          </span>
        </div>
      ))}
    </div>
  );
};
