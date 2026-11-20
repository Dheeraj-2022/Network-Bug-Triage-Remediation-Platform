import React from 'react';
import { Incident } from '../lib/incidents';
import { formatDateTime, relativeTime } from '../lib/format';
import { hrefFor } from '../lib/routes';
import { Navigate } from '../pages/common';
import { Meter, SeverityTag, SkeletonRows, StateBadge } from './ui';

export type IncidentColumn = 'severity' | 'incident' | 'host' | 'state' | 'confidence' | 'playbook' | 'risk' | 'detected';

interface Props {
  incidents: Incident[];
  navigate: Navigate;
  columns?: IncidentColumn[];
  loading?: boolean;
  actions?: (i: Incident) => React.ReactNode;
  empty?: React.ReactNode;
}

const HEAD: Record<IncidentColumn, { label: string; width?: number; title?: string }> = {
  severity: { label: 'Pri', width: 56 },
  incident: { label: 'Incident' },
  host: { label: 'Host', width: 120 },
  state: { label: 'State', width: 160 },
  confidence: { label: 'Confidence', width: 130, title: 'Root-cause confidence from the analysis engine; ML priority score when no RCA is available.' },
  playbook: { label: 'Playbook', width: 170 },
  risk: { label: 'Risk', width: 90 },
  detected: { label: 'Detected', width: 96 },
};

const DEFAULT_COLS: IncidentColumn[] = ['severity', 'incident', 'host', 'state', 'confidence', 'detected'];

export const IncidentTable: React.FC<Props> = ({ incidents, navigate, columns = DEFAULT_COLS, loading, actions, empty }) => {
  const open = (i: Incident) => navigate('incident-detail', i.key);
  const colCount = columns.length + (actions ? 1 : 0);

  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c} style={{ width: HEAD[c].width }} title={HEAD[c].title}>
                {HEAD[c].label}
              </th>
            ))}
            {actions && <th className="right" style={{ width: 1 }}><span className="sr-only">Actions</span></th>}
          </tr>
        </thead>
        {loading ? (
          <SkeletonRows rows={4} cols={colCount} />
        ) : incidents.length === 0 ? (
          <tbody>
            <tr>
              <td colSpan={colCount} style={{ padding: 0 }}>
                {empty}
              </td>
            </tr>
          </tbody>
        ) : (
          <tbody>
            {incidents.map((i) => (
              <tr
                key={i.key}
                className="clickable"
                onClick={(e) => {
                  if ((e.target as HTMLElement).closest('a,button')) return;
                  open(i);
                }}
              >
                {columns.map((c) => {
                  switch (c) {
                    case 'severity':
                      return (
                        <td key={c}>
                          <SeverityTag severity={i.severity} />
                        </td>
                      );
                    case 'incident':
                      return (
                        <td key={c} style={{ maxWidth: 0, width: '100%' }}>
                          <a href={hrefFor('incident-detail', i.key)} className="cell-primary truncate" style={{ display: 'block', color: 'var(--text)' }}>
                            {i.title}
                          </a>
                          <div className="cell-secondary truncate" title={i.ruleReason || undefined}>
                            <span className="mono">{i.key}</span>
                            {i.ruleReason && i.ruleReason !== 'no rule triggered' ? ` · ${i.ruleReason}` : ''}
                          </div>
                        </td>
                      );
                    case 'host':
                      return (
                        <td key={c} className="mono nowrap">
                          {i.host}
                        </td>
                      );
                    case 'state':
                      return (
                        <td key={c} className="nowrap">
                          <StateBadge state={i.state} />
                        </td>
                      );
                    case 'confidence':
                      return (
                        <td key={c}>
                          <Meter
                            value={i.confidence ?? i.mlPriority}
                            title={i.confidence !== undefined ? 'RCA confidence' : 'ML priority score'}
                          />
                        </td>
                      );
                    case 'playbook':
                      return (
                        <td key={c} className="mono nowrap">
                          {i.playbook || <span className="subtle">none</span>}
                        </td>
                      );
                    case 'risk':
                      return (
                        <td key={c} className="nowrap" style={{ textTransform: 'capitalize' }}>
                          {i.risk || <span className="subtle">—</span>}
                        </td>
                      );
                    case 'detected':
                      return (
                        <td key={c} className="nowrap muted num" title={formatDateTime(i.ts)}>
                          {relativeTime(i.ts)}
                        </td>
                      );
                    default:
                      return null;
                  }
                })}
                {actions && (
                  <td className="right nowrap">
                    <div className="row" style={{ justifyContent: 'flex-end' }}>
                      {actions(i)}
                    </div>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        )}
      </table>
    </div>
  );
};
