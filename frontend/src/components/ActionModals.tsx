import React, { useState } from 'react';
import { Modal } from './ui';
import { Incident } from '../lib/incidents';

export const ClearConfirmModal: React.FC<{
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  isLoading: boolean;
}> = ({ isOpen, onClose, onConfirm, isLoading }) => (
  <Modal
    open={isOpen}
    onClose={onClose}
    title="Reset platform state"
    footer={
      <>
        <button className="btn" onClick={onClose}>
          Cancel
        </button>
        <button className="btn btn-danger-solid" onClick={onConfirm} disabled={isLoading}>
          {isLoading ? 'Resetting…' : 'Reset state'}
        </button>
      </>
    }
  >
    <p>
      Removes all in-memory telemetry events, triage decisions, remediation audit entries and AI incidents from the
      controller.
    </p>
    <p className="muted">This cannot be undone. The trained model on disk is not affected.</p>
  </Modal>
);

export const InjectModal: React.FC<{
  isOpen: boolean;
  onClose: () => void;
  onInject: (count: number, injectErrors: boolean) => void;
  isLoading: boolean;
}> = ({ isOpen, onClose, onInject, isLoading }) => {
  const [count, setCount] = useState(5);
  const [injectErrors, setInjectErrors] = useState(true);
  const valid = Number.isInteger(count) && count >= 1 && count <= 100;

  return (
    <Modal
      open={isOpen}
      onClose={onClose}
      title="Inject synthetic telemetry"
      footer={
        <>
          <button className="btn" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={() => onInject(count, injectErrors)} disabled={isLoading || !valid}>
            {isLoading ? 'Injecting…' : `Inject ${valid ? count : ''} events`}
          </button>
        </>
      }
    >
      <p className="muted">
        Generates host events for <span className="mono">node1–node5</span> and runs each through the rules engine, log
        classifier, ML triage model and, if enabled, the multi-agent analysis workflow.
      </p>
      <div className="field">
        <label className="field-label" htmlFor="inject-count">
          Number of events
        </label>
        <input
          id="inject-count"
          className="input num"
          type="number"
          min={1}
          max={100}
          value={Number.isNaN(count) ? '' : count}
          onChange={(e) => setCount(parseInt(e.target.value, 10))}
          style={{ width: 120 }}
        />
        <span className="field-help">1–100 events per request.</span>
      </div>
      <label className="checkbox-row">
        <input type="checkbox" checked={injectErrors} onChange={(e) => setInjectErrors(e.target.checked)} />
        <span>
          <span className="strong">Include faults</span>
          <span className="field-help" style={{ display: 'block' }}>
            Every other event carries one of: MTU mismatch, interface TX errors, RDMA QP errors, or a driver oops in dmesg.
          </span>
        </span>
      </label>
    </Modal>
  );
};

export const ApprovalModal: React.FC<{
  incident: Incident | null;
  approve: boolean;
  onClose: () => void;
  onConfirm: () => void;
  isLoading: boolean;
}> = ({ incident, approve, onClose, onConfirm, isLoading }) => (
  <Modal
    open={!!incident}
    onClose={onClose}
    title={approve ? 'Approve remediation' : 'Reject remediation'}
    footer={
      <>
        <button className="btn" onClick={onClose}>
          Cancel
        </button>
        <button className={approve ? 'btn btn-primary' : 'btn btn-danger-solid'} onClick={onConfirm} disabled={isLoading}>
          {isLoading ? 'Submitting…' : approve ? 'Approve plan' : 'Reject plan'}
        </button>
      </>
    }
  >
    {incident && (
      <>
        <dl className="kv">
          <dt>Incident</dt>
          <dd className="mono">{incident.key}</dd>
          <dt>Host</dt>
          <dd className="mono">{incident.host}</dd>
          <dt>Fault</dt>
          <dd>{incident.title}</dd>
          <dt>Playbook</dt>
          <dd className="mono">{incident.playbook || '—'}</dd>
          <dt>Risk</dt>
          <dd>{incident.risk || '—'}</dd>
        </dl>
        <p className="muted">
          {approve
            ? 'Approval is recorded and the orchestrator resumes the workflow: the validation agent checks the outcome and the audit agent records the incident.'
            : 'The plan will be marked as rejected. No playbook will run.'}
        </p>
      </>
    )}
  </Modal>
);
