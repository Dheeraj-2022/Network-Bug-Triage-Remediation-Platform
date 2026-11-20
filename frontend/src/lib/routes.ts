import { PageId } from '../types';

const PATHS: Record<Exclude<PageId, 'incident-detail'>, string> = {
  overview: 'overview',
  demo: 'demo',
  incidents: 'incidents',
  remediation: 'remediation',
  events: 'telemetry',
  decisions: 'decisions',
  'ai-analysis': 'analysis',
  'audit-trail': 'executions',
};

export interface Route {
  page: PageId;
  param?: string;
  query: URLSearchParams;
}

export function parseHash(hash: string): Route {
  const [pathPart, queryPart] = hash.replace(/^#\/?/, '').split('?');
  const segs = pathPart.split('/').filter(Boolean).map(decodeURIComponent);
  const query = new URLSearchParams(queryPart || '');
  if (segs[0] === 'incidents' && segs[1]) return { page: 'incident-detail', param: segs[1], query };
  const page = (Object.keys(PATHS) as (keyof typeof PATHS)[]).find((k) => PATHS[k] === segs[0]);
  return { page: page ?? 'overview', query };
}

export function hrefFor(page: PageId, param?: string, query?: Record<string, string>): string {
  const base = page === 'incident-detail' ? `#/incidents/${encodeURIComponent(param ?? '')}` : `#/${PATHS[page]}`;
  const qs = query ? new URLSearchParams(query).toString() : '';
  return qs ? `${base}?${qs}` : base;
}
