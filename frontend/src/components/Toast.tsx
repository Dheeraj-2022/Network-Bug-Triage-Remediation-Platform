import React from 'react';
import { AlertCircle, CheckCircle2, Info, X } from 'lucide-react';

export interface ToastMessage {
  id: string;
  type: 'success' | 'error' | 'info';
  title: string;
  message?: string;
}

const ICONS = {
  success: <CheckCircle2 size={16} />,
  error: <AlertCircle size={16} />,
  info: <Info size={16} />,
};

export const ToastContainer: React.FC<{ toasts: ToastMessage[]; onDismiss: (id: string) => void }> = ({ toasts, onDismiss }) => (
  <div className="toast-stack" aria-live="polite" aria-atomic="false">
    {toasts.map((t) => (
      <div key={t.id} className={`toast toast-${t.type}`} role={t.type === 'error' ? 'alert' : 'status'}>
        {ICONS[t.type]}
        <div style={{ minWidth: 0 }}>
          <div className="toast-title">{t.title}</div>
          {t.message && <div className="toast-msg">{t.message}</div>}
        </div>
        <button className="toast-close" onClick={() => onDismiss(t.id)} aria-label="Dismiss notification">
          <X size={14} />
        </button>
      </div>
    ))}
  </div>
);
