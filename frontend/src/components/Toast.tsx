import React from 'react';
import { AlertCircle, CheckCircle2, Info, X } from 'lucide-react';

export interface ToastMessage {
  id: string;
  type: 'success' | 'error' | 'info';
  title: string;
  message?: string;
}

interface ToastProps {
  toasts: ToastMessage[];
  onDismiss: (id: string) => void;
}

export const ToastContainer: React.FC<ToastProps> = ({ toasts, onDismiss }) => {
  if (!toasts.length) return null;

  return (
    <div
      style={{
        position: 'fixed',
        bottom: '1.25rem',
        right: '1.25rem',
        zIndex: 9999,
        display: 'flex',
        flexDirection: 'column',
        gap: '0.5rem',
        maxWidth: '380px',
      }}
    >
      {toasts.map((toast) => {
        const isSuccess = toast.type === 'success';
        const isError = toast.type === 'error';

        const borderColor = isSuccess ? '#10b981' : isError ? '#f43f5e' : '#38bdf8';
        const bgColor = '#10141b';
        const textColor = isSuccess ? '#10b981' : isError ? '#f43f5e' : '#38bdf8';

        return (
          <div
            key={toast.id}
            style={{
              backgroundColor: bgColor,
              border: `1px solid ${borderColor}`,
              borderLeft: `4px solid ${borderColor}`,
              borderRadius: '4px',
              padding: '0.65rem 0.85rem',
              boxShadow: '0 8px 24px rgba(0, 0, 0, 0.6)',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '0.65rem',
            }}
          >
            <div style={{ color: textColor, marginTop: '2px', flexShrink: 0 }}>
              {isSuccess && <CheckCircle2 size={15} />}
              {isError && <AlertCircle size={15} />}
              {!isSuccess && !isError && <Info size={15} />}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#f1f5f9' }}>
                {toast.title}
              </div>
              {toast.message && (
                <div style={{ fontSize: '0.6875rem', color: '#94a3b8', marginTop: '2px' }}>
                  {toast.message}
                </div>
              )}
            </div>
            <button
              onClick={() => onDismiss(toast.id)}
              style={{
                background: 'none',
                border: 'none',
                color: '#64748b',
                cursor: 'pointer',
                padding: '0',
                marginLeft: '0.25rem',
              }}
            >
              <X size={13} />
            </button>
          </div>
        );
      })}
    </div>
  );
};
