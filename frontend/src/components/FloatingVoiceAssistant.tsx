import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  ArrowRight,
  CheckCircle2,
  KeyRound,
  Maximize2,
  Mic,
  MicOff,
  Send,
  Volume2,
  VolumeX,
  X,
} from 'lucide-react';
import { Badge } from './ui';
import { api, ApiError, voiceToken } from '../services/api';
import {
  PageId,
  VoiceConfirmation,
  VoiceConversationContext,
  VoicePrincipal,
  VoiceQueryResponse,
} from '../types';

interface FloatingVoiceAssistantProps {
  currentPage: PageId;
  onNavigate: (page: PageId, param?: string) => void;
  onChanged: () => void;
  onToast: (type: 'success' | 'error' | 'info', title: string, message?: string) => void;
}

function getSpeechCtor(): any {
  const w = window as any;
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

export const FloatingVoiceAssistant: React.FC<FloatingVoiceAssistantProps> = ({
  currentPage,
  onNavigate,
  onChanged,
  onToast,
}) => {
  const [open, setOpen] = useState(false);
  const [principal, setPrincipal] = useState<VoicePrincipal | null>(null);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [listening, setListening] = useState(false);
  const [ttsOn, setTtsOn] = useState(true);
  const [messages, setMessages] = useState<VoiceQueryResponse[]>([]);
  const [ctx, setCtx] = useState<VoiceConversationContext | null>(null);
  const [pendingConfirm, setPendingConfirm] = useState<VoiceConfirmation | null>(null);
  const [confirmPhrase, setConfirmPhrase] = useState('yes confirm');
  const [error, setError] = useState<string | null>(null);
  const recRef = useRef<any>(null);

  const speak = useCallback(
    (text: string) => {
      if (!ttsOn || !text || !('speechSynthesis' in window)) return;
      try {
        window.speechSynthesis.cancel();
        window.speechSynthesis.speak(new SpeechSynthesisUtterance(text));
      } catch {
        // ignore speech synthesis errors
      }
    },
    [ttsOn],
  );

  const syncSession = useCallback(async () => {
    if (!voiceToken.get()) {
      setPrincipal(null);
      return;
    }
    try {
      const me = await api.getVoiceMe();
      setPrincipal(me.principal);
      const conv = await api.getVoiceConversation();
      setCtx(conv.context);
    } catch {
      setPrincipal(null);
    }
  }, []);

  useEffect(() => {
    if (open) syncSession();
  }, [open, syncSession]);

  // Hide floating widget on the dedicated full Voice Operations page to avoid duplication
  if (currentPage === 'voice') return null;

  const quickDemoLogin = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await api.createVoiceDemoSession('operator-gpu');
      voiceToken.set(res.token);
      setPrincipal(res.principal);
      onToast('success', 'Voice Ops connected', `Signed in as ${res.principal.display_name}.`);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const sendQuery = async (text: string, mode: 'voice' | 'text') => {
    const clean = text.trim();
    if (!clean) return;
    setBusy(true);
    setError(null);
    try {
      if (!principal) {
        const wt = await api.voiceWalkthrough({ transcript: clean, current_page: currentPage });
        speak(wt.spoken_summary);
        setMessages((prev) => [
          {
            status: wt.status,
            recognized_transcript: clean,
            spoken_summary: wt.spoken_summary,
            visible_summary: wt.visible_summary,
            injection_flagged: Boolean(wt.injection_flagged),
            audit_seq: Date.now(),
            ts: new Date().toISOString(),
            principal: {
              user_id: 'anonymous',
              display_name: 'Visitor',
              role: 'viewer',
              allowed_hosts: [],
              demo_session: true,
              can_write: false,
              can_step_up: false,
            },
            navigate_to: wt.navigate_to || null,
            suggested_actions: ['Explain what NetResolve AI does'],
          },
          ...prev.slice(0, 14),
        ]);
        setInput('');
        return;
      }
      const res = await api.voiceQuery({
        transcript: clean,
        input_mode: mode,
        current_page: currentPage,
      });
      setMessages((prev) => [res, ...prev.slice(0, 14)]);
      if (res.conversation_context) setCtx(res.conversation_context);
      if (res.confirmation) {
        setPendingConfirm(res.confirmation);
        setConfirmPhrase('yes confirm');
      } else if (['verified_resolved', 'verification_failed', 'verification_inconclusive', 'cancelled'].includes(res.status)) {
        setPendingConfirm(null);
      }
      speak(res.spoken_summary);
      setInput('');
      if (['demo_load', 'demo_reset', 'approve_remediation'].includes(res.interpreted?.intent || '')) {
        onChanged();
      }
    } catch (err: any) {
      if (err instanceof ApiError && err.body?.spoken_summary) {
        setMessages((prev) => [err.body as VoiceQueryResponse, ...prev.slice(0, 14)]);
        speak(err.body.spoken_summary);
      } else {
        setError(err.message);
      }
    } finally {
      setBusy(false);
    }
  };

  const decideConfirm = async (confirm: boolean) => {
    if (!pendingConfirm) return;
    setBusy(true);
    try {
      const res = await api.voiceConfirm({
        confirmation_id: pendingConfirm.confirmation_id,
        confirm,
        confirmation_phrase: confirm ? confirmPhrase : 'cancel',
      });
      setMessages((prev) => [res, ...prev.slice(0, 14)]);
      setPendingConfirm(null);
      speak(res.spoken_summary);
      onChanged();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const toggleMic = () => {
    if (listening) {
      recRef.current?.stop?.();
      setListening(false);
      return;
    }
    const Ctor = getSpeechCtor();
    if (!Ctor) {
      onToast('info', 'Web Speech unavailable', 'Type your question in the text input.');
      return;
    }
    const rec = new Ctor();
    rec.lang = 'en-US';
    rec.interimResults = false;
    rec.continuous = false;
    let finalText = '';
    rec.onstart = () => setListening(true);
    rec.onresult = (ev: any) => {
      finalText = ev.results?.[0]?.[0]?.transcript || '';
      setInput(finalText);
    };
    rec.onerror = () => setListening(false);
    rec.onend = () => {
      setListening(false);
      if (finalText.trim()) sendQuery(finalText.trim(), 'voice');
    };
    recRef.current = rec;
    rec.start();
  };

  if (!open) {
    return (
      <button
        type="button"
        className="nr-floating-trigger"
        onClick={() => setOpen(true)}
        aria-label="Open Voice Operations Assistant"
      >
        <Mic size={14} />
        <span>VOICE OPS</span>
      </button>
    );
  }

  return (
    <aside className="nr-floating-drawer" aria-label="Floating Voice Operations Assistant">
      <div className="nr-floating-head">
        <div>
          <div className="eyebrow" style={{ color: '#8a877e', marginBottom: 2 }}>
            NETRESOLVE VOICE OPS · PAGE: {currentPage.toUpperCase()}
          </div>
          <div style={{ fontWeight: 700, fontSize: 13 }}>
            {principal ? `${principal.display_name} (${principal.role})` : 'Anonymous Walkthrough Mode'}
          </div>
        </div>
        <div className="row" style={{ gap: 4 }}>
          <button type="button" className="btn btn-sm" onClick={() => setTtsOn((v) => !v)} title={ttsOn ? 'Mute TTS' : 'Enable TTS'}>
            {ttsOn ? <Volume2 size={12} /> : <VolumeX size={12} />}
          </button>
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => {
              setOpen(false);
              onNavigate('voice');
            }}
            title="Open full Voice Operations screen"
          >
            <Maximize2 size={12} />
          </button>
          <button type="button" className="btn btn-sm" onClick={() => setOpen(false)} aria-label="Close assistant">
            <X size={12} />
          </button>
        </div>
      </div>

      {!principal && (
        <div style={{ padding: '8px 12px', background: 'var(--warn-bg)', borderBottom: '1px solid var(--warn-border)', fontSize: 11 }}>
          <div className="row" style={{ justifyContent: 'space-between', gap: 8 }}>
            <span>Sign in to inspect hosts &amp; incidents.</span>
            <button type="button" className="btn btn-sm btn-primary" onClick={quickDemoLogin} disabled={busy}>
              <KeyRound size={11} /> DEMO LOGIN
            </button>
          </div>
        </div>
      )}

      {ctx && (ctx.selected_host || ctx.selected_proposal_id) && (
        <div style={{ padding: '6px 12px', background: 'var(--bg)', borderBottom: '1px solid var(--border)', fontSize: 10 }} className="mono">
          CTX: host={ctx.selected_host || '—'} · proposal={ctx.selected_proposal_id || '—'} · stage={ctx.investigation_stage}
        </div>
      )}

      {error && (
        <div style={{ padding: '8px 12px', background: 'var(--crit-bg)', color: 'var(--crit)', fontSize: 11, borderBottom: '1px solid var(--crit-border)' }}>
          {error}
        </div>
      )}

      {pendingConfirm && (
        <div style={{ padding: 10, background: 'var(--warn-bg)', borderBottom: '1px solid #171614' }}>
          <div className="mono strong" style={{ fontSize: 10, marginBottom: 4 }}>CONFIRMATION REQUIRED</div>
          <div style={{ fontSize: 11, marginBottom: 6 }}>{pendingConfirm.readback}</div>
          <div className="row" style={{ gap: 6 }}>
            <input
              className="input mono"
              style={{ flex: 1, height: 26, fontSize: 11 }}
              value={confirmPhrase}
              onChange={(e) => setConfirmPhrase(e.target.value)}
              aria-label="Confirmation phrase"
            />
            <button type="button" className="btn btn-sm btn-primary" onClick={() => decideConfirm(true)} disabled={busy}>
              <CheckCircle2 size={11} /> CONFIRM
            </button>
            <button type="button" className="btn btn-sm btn-danger" onClick={() => decideConfirm(false)} disabled={busy}>
              CANCEL
            </button>
          </div>
        </div>
      )}

      <div className="nr-floating-body">
        {messages.length === 0 ? (
          <div className="stack" style={{ gap: 6 }}>
            <div className="muted" style={{ fontSize: 12 }}>
              Ask about infrastructure health, investigate a host, or request a guided walkthrough.
            </div>
            {['Is everything running smoothly?', 'Which host has the most serious issue?', 'Explain what NetResolve AI does'].map((q) => (
              <button
                key={q}
                type="button"
                className="btn btn-sm"
                style={{ justifyContent: 'flex-start', fontFamily: 'var(--font-mono)', fontSize: 11 }}
                onClick={() => sendQuery(q, 'text')}
                disabled={busy}
              >
                &gt; {q}
              </button>
            ))}
          </div>
        ) : (
          messages.map((m, i) => (
            <div key={`${m.audit_seq}-${i}`} className="nr-chat-msg assistant" style={{ padding: '8px 10px' }}>
              <div className="row" style={{ justifyContent: 'space-between', marginBottom: 4 }}>
                <Badge tone={m.status === 'ok' || m.status === 'verified_resolved' ? 'ok' : m.status === 'confirmation_required' ? 'warn' : 'crit'}>
                  {m.status.toUpperCase()}
                </Badge>
                {m.navigate_to && (
                  <button type="button" className="btn btn-sm btn-ghost" style={{ fontSize: 10 }} onClick={() => onNavigate(m.navigate_to as PageId)}>
                    OPEN {m.navigate_to.toUpperCase()} <ArrowRight size={10} />
                  </button>
                )}
              </div>
              <div className="mono muted" style={{ fontSize: 10, marginBottom: 4 }}>&gt; {m.recognized_transcript}</div>
              <div style={{ fontSize: 12, color: '#171614' }}>{m.visible_summary}</div>
            </div>
          ))
        )}
      </div>

      <form
        className="nr-floating-foot"
        onSubmit={(e) => {
          e.preventDefault();
          sendQuery(input, 'text');
        }}
      >
        <button type="button" className={`btn btn-sm ${listening ? 'btn-danger' : 'btn-primary'}`} onClick={toggleMic} disabled={busy} aria-label="Push to talk">
          {listening ? <MicOff size={13} /> : <Mic size={13} />}
        </button>
        <input
          className="input mono"
          style={{ flex: 1, height: 30, fontSize: 11 }}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask NetResolve AI..."
          disabled={busy}
        />
        <button type="submit" className="btn btn-sm btn-primary" disabled={busy || !input.trim()} aria-label="Send">
          <Send size={12} />
        </button>
      </form>
    </aside>
  );
};
