import React, { useState } from 'react';
import { AlertTriangle, CheckCircle2, Sliders, Trash2, X, Zap } from 'lucide-react';

interface ClearConfirmModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  isLoading: boolean;
}

export const ClearConfirmModal: React.FC<ClearConfirmModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  isLoading,
}) => {
  if (!isOpen) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(5, 7, 10, 0.75)',
        backdropFilter: 'blur(2px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 100,
      }}
    >
      <div
        className="noc-card"
        style={{
          width: '420px',
          borderColor: '#f43f5e',
          boxShadow: '0 12px 32px rgba(0, 0, 0, 0.7)',
        }}
      >
        <div className="noc-card-header" style={{ borderColor: 'rgba(244, 63, 94, 0.3)' }}>
          <div className="noc-card-title" style={{ color: '#f43f5e' }}>
            <AlertTriangle size={15} />
            CONFIRM STATE PURGE
          </div>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer' }}
          >
            <X size={15} />
          </button>
        </div>
        <div style={{ padding: '1.25rem' }}>
          <p style={{ fontSize: '0.8125rem', color: '#cbd5e1', marginBottom: '0.75rem' }}>
            This will purge all ingested in-memory telemetry, triage decisions, audit records, and AI incidents from the live platform.
          </p>
          <div
            style={{
              padding: '0.5rem 0.75rem',
              backgroundColor: 'rgba(244, 63, 94, 0.08)',
              border: '1px solid rgba(244, 63, 94, 0.25)',
              borderRadius: '3px',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.6875rem',
              color: '#f43f5e',
              marginBottom: '1.25rem',
            }}
          >
            Action cannot be undone. Trained ML model weights on disk will remain preserved.
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
            <button onClick={onClose} className="noc-btn noc-btn-outline">
              Cancel
            </button>
            <button
              onClick={onConfirm}
              disabled={isLoading}
              className="noc-btn noc-btn-danger"
            >
              <Trash2 size={13} />
              {isLoading ? 'Purging...' : 'Purge All State'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

interface InjectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onInject: (count: number, injectErrors: boolean) => void;
  isLoading: boolean;
}

export const InjectModal: React.FC<InjectModalProps> = ({
  isOpen,
  onClose,
  onInject,
  isLoading,
}) => {
  const [count, setCount] = useState(5);
  const [injectErrors, setInjectErrors] = useState(true);

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(5, 7, 10, 0.75)',
        backdropFilter: 'blur(2px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 100,
      }}
    >
      <div
        className="noc-card"
        style={{
          width: '440px',
          borderColor: '#232a38',
          boxShadow: '0 12px 32px rgba(0, 0, 0, 0.7)',
        }}
      >
        <div className="noc-card-header">
          <div className="noc-card-title">
            <Zap size={14} style={{ color: '#38bdf8' }} />
            INJECT SYNTHETIC TELEMETRY
          </div>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer' }}
          >
            <X size={15} />
          </button>
        </div>
        <div style={{ padding: '1.25rem' }}>
          <div style={{ marginBottom: '1rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.4rem', fontSize: '0.75rem' }}>
              <span style={{ color: '#94a3b8' }}>Telemetry Events Count:</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: '#38bdf8' }}>{count}</span>
            </div>
            <input
              type="range"
              min={1}
              max={20}
              value={count}
              onChange={(e) => setCount(parseInt(e.target.value))}
              style={{ width: '100%', accentColor: '#38bdf8' }}
            />
          </div>

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              padding: '0.75rem',
              backgroundColor: '#12161f',
              border: '1px solid #1e2532',
              borderRadius: '3px',
              marginBottom: '1.25rem',
              cursor: 'pointer',
            }}
            onClick={() => setInjectErrors(!injectErrors)}
          >
            <input
              type="checkbox"
              checked={injectErrors}
              onChange={(e) => setInjectErrors(e.target.checked)}
              style={{ accentColor: '#38bdf8' }}
            />
            <div>
              <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#e2e8f0' }}>
                Simulate Hardware & Protocol Faults
              </div>
              <div style={{ fontSize: '0.6875rem', color: '#64748b' }}>
                Randomly introduces MTU mismatches, RDMA QP resets, and iface driver drops
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
            <button onClick={onClose} className="noc-btn noc-btn-outline">
              Cancel
            </button>
            <button
              onClick={() => onInject(count, injectErrors)}
              disabled={isLoading}
              className="noc-btn noc-btn-primary"
            >
              <Zap size={13} />
              {isLoading ? 'Injecting...' : `Dispatch ${count} Events`}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
