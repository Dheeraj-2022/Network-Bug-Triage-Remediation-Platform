export function parseTs(ts?: string | null): Date | null {
  if (!ts) return null;
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? null : d;
}

const pad = (n: number) => String(n).padStart(2, '0');

/** HH:MM:SS in UTC — backend timestamps are UTC. */
export function formatTime(ts?: string | null): string {
  const d = parseTs(ts);
  if (!d) return '—';
  return `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}`;
}

export function formatDateTime(ts?: string | null): string {
  const d = parseTs(ts);
  if (!d) return '—';
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())} ${formatTime(ts)} UTC`;
}

export function relativeTime(ts?: string | null, now: number = Date.now()): string {
  const d = parseTs(ts);
  if (!d) return '—';
  const s = Math.round((now - d.getTime()) / 1000);
  if (s < 0) return 'just now';
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 48) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export function formatNumber(n?: number | null): string {
  if (n === undefined || n === null || Number.isNaN(n)) return '—';
  return n.toLocaleString('en-US');
}

export function formatPct(v?: number | null, digits = 0): string {
  if (v === undefined || v === null || Number.isNaN(v)) return '—';
  return `${(v * 100).toFixed(digits)}%`;
}

export function formatBytes(n?: number | null): string {
  if (n === undefined || n === null) return '—';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KiB`;
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MiB`;
  return `${(n / 1024 / 1024 / 1024).toFixed(2)} GiB`;
}

export function formatSeconds(s?: number | null): string {
  if (s === undefined || s === null) return '—';
  if (s < 1) return `${Math.round(s * 1000)} ms`;
  return `${s.toFixed(2)} s`;
}

const DOMAIN_LABELS: Record<string, string> = {
  MTU_MISMATCH: 'MTU mismatch',
  RDMA_ERROR: 'RDMA error',
  DRIVER_FAULT: 'Driver fault',
  LINK_FLAP: 'Link flap',
  CONGESTION: 'Congestion',
  KERNEL_PANIC: 'Kernel panic',
  UNKNOWN: 'Unclassified',
};

export function domainLabel(code?: string | null): string {
  if (!code) return 'Unclassified';
  return DOMAIN_LABELS[code] ?? code.replace(/_/g, ' ').toLowerCase().replace(/^\w/, (c) => c.toUpperCase());
}

export function shortId(id?: string | null, max = 28): string {
  if (!id) return '—';
  return id.length > max ? `${id.slice(0, max - 1)}…` : id;
}
