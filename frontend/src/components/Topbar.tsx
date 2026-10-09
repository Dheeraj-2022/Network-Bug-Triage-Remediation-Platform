import React from 'react';
import {
  Bell,
  Cpu,
  Database,
  Flame,
  Radio,
  RefreshCw,
  Search,
  Sparkles,
  Trash2,
  Zap,
} from 'lucide-react';

interface TopbarProps {
  onInject: () => void;
  onLoadSamples: () => void;
  onTrainModel: () => void;
  onClearState: () => void;
  onRefresh: () => void;
  isInjecting: boolean;
  isLoadingSamples: boolean;
  isTraining: boolean;
  isClearing: boolean;
  isLive: boolean;
  setIsLive: (val: boolean) => void;
  searchQuery: string;
  setSearchQuery: (val: string) => void;
}

export const Topbar: React.FC<TopbarProps> = ({
  onInject,
  onLoadSamples,
  onTrainModel,
  onClearState,
  onRefresh,
  isInjecting,
  isLoadingSamples,
  isTraining,
  isClearing,
  isLive,
  setIsLive,
  searchQuery,
  setSearchQuery,
}) => {
  return (
    <header
      style={{
        height: '52px',
        backgroundColor: '#0d1117',
        borderBottom: '1px solid #1c222e',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 1.25rem',
        flexShrink: 0,
        zIndex: 20,
      }}
    >
      {/* Left: Environment & Cluster metadata */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.45rem',
            padding: '0.25rem 0.65rem',
            backgroundColor: '#121720',
            border: '1px solid #1e2634',
            borderRadius: '3px',
            fontFamily: 'var(--font-mono)',
            fontSize: '0.6875rem',
            fontWeight: 600,
          }}
        >
          <span className="status-pulse-dot pulse-green" />
          <span style={{ color: '#94a3b8' }}>US-EAST-1</span>
          <span style={{ color: '#475569' }}>/</span>
          <span style={{ color: '#10b981' }}>PRODUCTION</span>
        </div>

        {/* Search input */}
        <div style={{ position: 'relative', width: '380px' }}>
          <Search
            size={13}
            style={{
              position: 'absolute',
              left: '10px',
              top: '50%',
              transform: 'translateY(-50%)',
              color: '#64748b',
            }}
          />
          <input
            type="text"
            className="noc-input"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search telemetry, IP (e.g. 10.240.12.4), INC-ID..."
            style={{
              width: '100%',
              paddingLeft: '30px',
              paddingRight: '12px',
              fontSize: '0.75rem',
              height: '30px',
              backgroundColor: '#090c10',
              borderColor: '#1e2432',
            }}
          />
        </div>
      </div>

      {/* Right: Quick Operational Control Actions */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.55rem' }}>
        {/* Engine Operational Pill */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.4rem',
            padding: '0.25rem 0.6rem',
            backgroundColor: 'rgba(16, 185, 129, 0.08)',
            border: '1px solid rgba(16, 185, 129, 0.25)',
            borderRadius: '3px',
            fontSize: '0.6875rem',
            fontFamily: 'var(--font-mono)',
            color: '#10b981',
            fontWeight: 600,
          }}
        >
          <span className="status-pulse-dot pulse-green" />
          Engine: Operational
        </div>

        {/* Live streaming toggle */}
        <button
          onClick={() => setIsLive(!isLive)}
          className="noc-btn noc-btn-outline"
          style={{
            height: '28px',
            fontSize: '0.6875rem',
            padding: '0 0.6rem',
            color: isLive ? '#38bdf8' : '#64748b',
            borderColor: isLive ? '#0284c7' : '#1e2430',
          }}
          title={isLive ? 'Pause auto-polling (5s)' : 'Resume auto-polling'}
        >
          <Radio size={12} className={isLive ? 'animate-pulse' : ''} />
          {isLive ? '5x Live' : 'Paused'}
        </button>

        {/* Inject Synthetic Telemetry */}
        <button
          onClick={onInject}
          disabled={isInjecting}
          className="noc-btn noc-btn-cyan-outline"
          style={{ height: '28px', fontSize: '0.6875rem', padding: '0 0.65rem' }}
          title="Inject synthetic telemetry events through the triage pipeline"
        >
          <Zap size={12} />
          {isInjecting ? 'Injecting...' : 'Inject Event'}
        </button>

        {/* Load Fixtures */}
        <button
          onClick={onLoadSamples}
          disabled={isLoadingSamples}
          className="noc-btn noc-btn-outline"
          style={{ height: '28px', fontSize: '0.6875rem', padding: '0 0.65rem' }}
          title="Load 20 pre-recorded telemetry fixtures"
        >
          <Database size={12} />
          {isLoadingSamples ? 'Loading...' : 'Load Samples'}
        </button>

        {/* Train XGBoost Model */}
        <button
          onClick={onTrainModel}
          disabled={isTraining}
          className="noc-btn noc-btn-outline"
          style={{ height: '28px', fontSize: '0.6875rem', padding: '0 0.65rem' }}
          title="Train ML XGBoost triage classifier inline"
        >
          <Cpu size={12} />
          {isTraining ? 'Training...' : 'Train Model'}
        </button>

        {/* Clear State */}
        <button
          onClick={onClearState}
          disabled={isClearing}
          className="noc-btn noc-btn-outline"
          style={{ height: '28px', fontSize: '0.6875rem', padding: '0 0.55rem', color: '#f43f5e' }}
          title="Reset in-memory platform state"
        >
          <Trash2 size={12} />
        </button>

        {/* Manual Refresh */}
        <button
          onClick={onRefresh}
          className="noc-btn noc-btn-outline"
          style={{ height: '28px', width: '28px', padding: 0 }}
          title="Manual refresh"
        >
          <RefreshCw size={12} />
        </button>

        <div style={{ width: '1px', height: '18px', backgroundColor: '#1e2430', margin: '0 0.2rem' }} />

        {/* Notification indicator */}
        <button
          className="noc-btn noc-btn-outline"
          style={{ height: '28px', width: '28px', padding: 0, position: 'relative' }}
          title="Alerts and notifications"
        >
          <Bell size={13} />
          <span
            style={{
              position: 'absolute',
              top: '4px',
              right: '4px',
              width: '6px',
              height: '6px',
              backgroundColor: '#f43f5e',
              borderRadius: '50%',
            }}
          />
        </button>
      </div>
    </header>
  );
};
