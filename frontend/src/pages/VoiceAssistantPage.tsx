import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  Code2,
  Download,
  KeyRound,
  LogOut,
  Mic,
  MicOff,
  Send,
  Shield,
  Square,
  Trash2,
  Volume2,
  VolumeX,
  X,
} from 'lucide-react';
import { Badge, Banner, EmptyState, Panel, cx } from '../components/ui';
import { formatTime } from '../lib/format';
import { api, ApiError, voiceToken } from '../services/api';
import {
  PageId,
  VoiceAuditEntry,
  VoiceConfig,
  VoiceConfirmation,
  VoiceConversationContext,
  VoicePrincipal,
  VoiceQueryResponse,
  VoiceWalkthroughResponse,
} from '../types';
import { CommonPageProps } from './common';

interface Props extends CommonPageProps {
  currentPage?: PageId;
  onChanged: () => void;
  onToast: (type: 'success' | 'error' | 'info', title: string, message?: string) => void;
}

type DemoProfileId = 'viewer-gpu' | 'operator-gpu' | 'operator-lab' | 'senior-approver';

const CONVERSATIONAL_PROMPTS = [
  'Explain what NetResolve AI does',
  'Is everything running smoothly?',
  'Load the MTU demo',
  'Which host has the most serious issue?',
  'Investigate why gpu-b is experiencing packet loss',
  'Show me the logs for that host',
  'Can you fix this issue?',
  'Proceed with this fix',
];

function getSpeechRecognitionCtor(): any {
  const w = window as any;
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

export const VoiceAssistantPage: React.FC<Props> = ({ currentPage, navigate, onChanged, onToast }) => {
  const [config, setConfig] = useState<VoiceConfig | null>(null);
  const [principal, setPrincipal] = useState<VoicePrincipal | null>(null);
  const [stepUpHint, setStepUpHint] = useState<string | null>(null);
  const [manualToken, setManualToken] = useState('');
  const [selectedProfile, setSelectedProfile] = useState<DemoProfileId>('operator-gpu');
  const [authBusy, setAuthBusy] = useState(false);

  // Anonymous walkthrough state
  const [walkthroughRes, setWalkthroughRes] = useState<VoiceWalkthroughResponse | null>(null);
  const [walkthroughStep, setWalkthroughStep] = useState<number>(0);
  const [walkthroughBusy, setWalkthroughBusy] = useState(false);

  // Conversational operations state
  const [transcript, setTranscript] = useState('');
  const [busy, setBusy] = useState(false);
  const [listening, setListening] = useState(false);
  const [ttsEnabled, setTtsEnabled] = useState(true);
  const [speaking, setSpeaking] = useState(false);
  const [responses, setResponses] = useState<VoiceQueryResponse[]>([]);
  const [convContext, setConvContext] = useState<VoiceConversationContext | null>(null);
  const [expandedJson, setExpandedJson] = useState<Record<number, boolean>>({});
  const [pendingConfirm, setPendingConfirm] = useState<VoiceConfirmation | null>(null);
  const [confirmPhrase, setConfirmPhrase] = useState('yes confirm');
  const [stepUpCode, setStepUpCode] = useState('');
  const [secondApproverToken, setSecondApproverToken] = useState('');
  const [audit, setAudit] = useState<VoiceAuditEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  const recognitionRef = useRef<any>(null);
  const speechSupported = Boolean(getSpeechRecognitionCtor());

  const stopSpeaking = useCallback(() => {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    setSpeaking(false);
  }, []);

  const speak = useCallback(
    (text: string) => {
      if (!ttsEnabled || !text || !('speechSynthesis' in window)) return;
      try {
        window.speechSynthesis.cancel();
        const utter = new SpeechSynthesisUtterance(text);
        utter.rate = 1.02;
        utter.onstart = () => setSpeaking(true);
        utter.onend = () => setSpeaking(false);
        utter.onerror = () => setSpeaking(false);
        window.speechSynthesis.speak(utter);
      } catch {
        setSpeaking(false);
      }
    },
    [ttsEnabled],
  );

  const refreshAuditAndContext = useCallback(async () => {
    if (!voiceToken.get()) return;
    try {
      const [aud, conv] = await Promise.all([api.getVoiceAudit(40), api.getVoiceConversation()]);
      setAudit(aud);
      setConvContext(conv.context);
    } catch {
      // ignore if session expired
    }
  }, []);

  const loadConfigAndSession = useCallback(async () => {
    try {
      const cfg = await api.getVoiceConfig();
      setConfig(cfg);
      if (voiceToken.get()) {
        try {
          const me = await api.getVoiceMe();
          setPrincipal(me.principal);
          await refreshAuditAndContext();
        } catch {
          voiceToken.set('');
          setPrincipal(null);
        }
      }
    } catch (e: any) {
      setError(e.message);
    }
  }, [refreshAuditAndContext]);

  useEffect(() => {
    loadConfigAndSession();
    return () => {
      recognitionRef.current?.abort?.();
      stopSpeaking();
    };
  }, [loadConfigAndSession, stopSpeaking]);

  // Anonymous walkthrough
  const runWalkthrough = async (opts?: { transcript?: string; step?: number }) => {
    setWalkthroughBusy(true);
    try {
      const res = await api.voiceWalkthrough({
        transcript: opts?.transcript,
        step: opts?.step,
        current_page: currentPage || 'voice',
      });
      setWalkthroughRes(res);
      if (res.stage?.step) setWalkthroughStep(res.stage.step);
      speak(res.spoken_summary);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setWalkthroughBusy(false);
    }
  };

  // Auth actions
  const startDemoSession = async (profile: DemoProfileId) => {
    setAuthBusy(true);
    setError(null);
    try {
      const res = await api.createVoiceDemoSession(profile);
      voiceToken.set(res.token);
      setPrincipal(res.principal);
      setStepUpHint(res.step_up_code || null);
      if (res.step_up_code) setStepUpCode(res.step_up_code);
      setPendingConfirm(null);
      setResponses([]);
      onToast('success', 'Voice session started', `Authenticated as ${res.principal.display_name} (${res.principal.role}).`);
      await refreshAuditAndContext();
    } catch (e: any) {
      setError(e.message);
      onToast('error', 'Could not start voice session', e.message);
    } finally {
      setAuthBusy(false);
    }
  };

  const authenticateManualToken = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!manualToken.trim()) return;
    setAuthBusy(true);
    setError(null);
    try {
      voiceToken.set(manualToken.trim());
      const me = await api.getVoiceMe();
      setPrincipal(me.principal);
      setManualToken('');
      setStepUpHint(null);
      onToast('success', 'Voice token verified', `Authenticated as ${me.principal.display_name}.`);
      await refreshAuditAndContext();
    } catch (e: any) {
      voiceToken.set('');
      setPrincipal(null);
      setError(e.message);
    } finally {
      setAuthBusy(false);
    }
  };

  const revokeSession = () => {
    stopSpeaking();
    recognitionRef.current?.abort?.();
    setListening(false);
    voiceToken.set('');
    setPrincipal(null);
    setStepUpHint(null);
    setPendingConfirm(null);
    setConvContext(null);
    setResponses([]);
    setAudit([]);
    onToast('info', 'Voice session ended', 'Ephemeral session token removed from this tab.');
  };

  const handleClearConversation = async () => {
    try {
      await api.clearVoiceConversation();
      setResponses([]);
      setPendingConfirm(null);
      await refreshAuditAndContext();
      onToast('info', 'Conversation cleared', 'Session context and message history were reset.');
    } catch (e: any) {
      setError(e.message);
    }
  };

  // Query submission
  const submitQuery = async (text: string, inputMode: 'voice' | 'text') => {
    const clean = text.trim();
    if (!clean) return;
    if (!principal) {
      await runWalkthrough({ transcript: clean });
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await api.voiceQuery({
        transcript: clean,
        input_mode: inputMode,
        current_page: currentPage || 'voice',
      });
      setResponses((prev) => [res, ...prev.slice(0, 29)]);
      if (res.conversation_context) setConvContext(res.conversation_context);
      if (res.confirmation) {
        setPendingConfirm(res.confirmation);
        setConfirmPhrase('yes confirm');
      } else if (['verified_resolved', 'verification_failed', 'verification_inconclusive', 'cancelled', 'expired'].includes(res.status)) {
        setPendingConfirm(null);
      }
      speak(res.spoken_summary);
      setTranscript('');
      await refreshAuditAndContext();
      if (['demo_load', 'demo_reset', 'approve_remediation'].includes(res.interpreted?.intent || '')) {
        onChanged();
      }
    } catch (err: any) {
      if (err instanceof ApiError && err.body && typeof err.body === 'object' && 'spoken_summary' in err.body) {
        const res = err.body as VoiceQueryResponse;
        setResponses((prev) => [res, ...prev.slice(0, 29)]);
        if (res.conversation_context) setConvContext(res.conversation_context);
        speak(res.spoken_summary);
        await refreshAuditAndContext();
      } else {
        setError(err.message);
      }
    } finally {
      setBusy(false);
    }
  };

  const handleConfirmDecision = async (confirm: boolean) => {
    if (!pendingConfirm) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.voiceConfirm({
        confirmation_id: pendingConfirm.confirmation_id,
        confirm,
        confirmation_phrase: confirm ? confirmPhrase : 'cancel',
        step_up_code: pendingConfirm.requires_step_up && stepUpCode.trim() ? stepUpCode.trim() : undefined,
        second_approver_token:
          pendingConfirm.requires_step_up && secondApproverToken.trim() ? secondApproverToken.trim() : undefined,
      });
      setResponses((prev) => [res, ...prev.slice(0, 29)]);
      if (res.conversation_context) setConvContext(res.conversation_context);
      setPendingConfirm(null);
      speak(res.spoken_summary);
      await refreshAuditAndContext();
      onChanged();
    } catch (err: any) {
      if (err instanceof ApiError && err.body && typeof err.body === 'object' && 'spoken_summary' in err.body) {
        const res = err.body as VoiceQueryResponse;
        setResponses((prev) => [res, ...prev.slice(0, 29)]);
        speak(res.spoken_summary);
        if (err.status === 409) setPendingConfirm(null);
        await refreshAuditAndContext();
      } else {
        setError(err.message);
      }
    } finally {
      setBusy(false);
    }
  };

  const togglePushToTalk = () => {
    if (listening) {
      recognitionRef.current?.stop?.();
      setListening(false);
      return;
    }
    const Ctor = getSpeechRecognitionCtor();
    if (!Ctor) {
      onToast('info', 'Browser speech recognition unavailable', 'Use the text input fallback below.');
      return;
    }
    stopSpeaking();
    const rec = new Ctor();
    rec.lang = 'en-US';
    rec.interimResults = true;
    rec.continuous = false;
    rec.maxAlternatives = 1;
    let finalText = '';
    rec.onstart = () => setListening(true);
    rec.onresult = (event: any) => {
      let interim = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const chunk = event.results[i][0]?.transcript || '';
        if (event.results[i].isFinal) finalText += chunk;
        else interim += chunk;
      }
      setTranscript((finalText || interim).trim());
    };
    rec.onerror = (e: any) => {
      setListening(false);
      if (e.error !== 'aborted') {
        setError(`Speech recognition error: ${e.error}. Use the text input fallback.`);
      }
    };
    rec.onend = () => {
      setListening(false);
      if (finalText.trim()) {
        submitQuery(finalText.trim(), 'voice');
      }
    };
    recognitionRef.current = rec;
    rec.start();
  };

  const exportAuditCsv = () => {
    if (!audit.length) return;
    const header = ['seq', 'ts', 'user_id', 'role', 'intent', 'target_host', 'authorized', 'outcome', 'redacted_transcript'];
    const rows = audit.map((a) =>
      [
        a.seq,
        a.ts,
        a.user_id,
        a.role,
        a.intent || '',
        a.target_host || '',
        a.authorized ? 'ALLOWED' : 'DENIED',
        a.outcome,
        `"${(a.redacted_transcript || '').replace(/"/g, '""')}"`,
      ].join(','),
    );
    const blob = new Blob([[header.join(','), ...rows].join('\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'netresolve-voice-audit.csv';
    link.click();
    URL.revokeObjectURL(url);
  };

  const statusTone = (st: string) => {
    if (['verified_resolved', 'ok'].includes(st)) return 'ok';
    if (['confirmation_required', 'clarification_needed', 'verification_inconclusive', 'cancelled'].includes(st)) return 'warn';
    return 'crit';
  };

  return (
    <>
      {/* Header */}
      <div className="page-header">
        <div>
          <div className="eyebrow">SUBSYSTEM: AI-VOCAL-INGRESS · ENCLAVE-ISOLATED</div>
          <h1 className="page-title">Voice Operations Assistant</h1>
          <p className="page-desc">
            Intelligent conversational operations agent connected to live telemetry, multi-step incident investigation,
            and human-approved RemediationPolicy workflows.
          </p>
        </div>
        <div className="page-actions" style={{ alignItems: 'center' }}>
          <span className={`status-chip ${listening ? 'crit' : busy ? 'warn' : ''}`}>
            <span className={`dot ${listening ? 'dot-crit' : busy ? 'dot-warn' : 'dot-neutral'}`} />
            {listening ? 'LISTENING' : busy ? 'PROCESSING' : 'IDLE'}
          </span>
          <span className={`status-chip ${config?.uses_llm ? 'ok' : 'warn'}`}>
            {config?.uses_llm ? `AI: ${(config.llm_backend || 'GEMINI').toUpperCase()}` : 'AI: DETERMINISTIC OFFLINE'}
          </span>
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => {
              if (ttsEnabled) stopSpeaking();
              setTtsEnabled((v) => !v);
            }}
          >
            {ttsEnabled ? <Volume2 size={13} /> : <VolumeX size={13} />}
            {ttsEnabled ? 'TTS ON' : 'MUTED'}
          </button>
          {speaking && (
            <button type="button" className="btn btn-sm btn-danger" onClick={stopSpeaking}>
              <Square size={12} /> STOP SPEAKING
            </button>
          )}
        </div>
      </div>

      {/* Security & Speech Privacy Boundary */}
      <Banner tone="info" title="SECURITY & SPEECH PRIVACY BOUNDARY">
        {config?.speech_privacy_note ||
          'Browser speech recognition is opt-in (push-to-talk only) and may use your browser vendor’s speech service. The backend receives only text transcripts, never stores raw audio, enforces RBAC and per-host scope, redacts secrets, and routes every state change through RemediationPolicy with explicit readback.'}
      </Banner>

      {error && (
        <Banner tone="crit" title="Voice Operations Error" actions={<button className="btn btn-sm" onClick={() => setError(null)}>Dismiss</button>}>
          {error}
        </Banner>
      )}

      {/* Operator Principal / Auth Panel */}
      {!principal ? (
        <div className="stack" style={{ marginBottom: 16 }}>
          <Panel
            title="Operator Authentication Required for Infrastructure Access"
            sub="Voice recognition is never treated as identity verification. Start an ephemeral demo session or provide a configured voice token."
          >
            <div className="stack" style={{ gap: 14 }}>
              {config?.demo_sessions_enabled && (
                <div className="row wrap" style={{ gap: 10, alignItems: 'center' }}>
                  <select
                    className="input"
                    style={{ width: 260, maxWidth: '100%' }}
                    value={selectedProfile}
                    onChange={(e) => setSelectedProfile(e.target.value as DemoProfileId)}
                    aria-label="Select local demo operator profile"
                  >
                    {(config.demo_profiles || []).map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.display_name} — {p.role}
                      </option>
                    ))}
                  </select>
                  <button className="btn btn-primary" onClick={() => startDemoSession(selectedProfile)} disabled={authBusy}>
                    <KeyRound size={13} /> {authBusy ? 'STARTING…' : 'START DEMO SESSION'}
                  </button>
                </div>
              )}

              <form onSubmit={authenticateManualToken} className="row wrap" style={{ gap: 8 }}>
                <input
                  className="input mono"
                  type="password"
                  style={{ width: 320, maxWidth: '100%' }}
                  value={manualToken}
                  onChange={(e) => setManualToken(e.target.value)}
                  placeholder="Or paste configured X-Voice-Token..."
                  aria-label="Configured voice token"
                />
                <button className="btn" type="submit" disabled={authBusy || !manualToken.trim()}>
                  AUTHENTICATE TOKEN
                </button>
              </form>
            </div>
          </Panel>

          {/* Anonymous-safe introductory walkthrough */}
          <Panel
            title="New to NetResolve AI? Interactive Application Walkthrough (Anonymous-Safe)"
            sub="Explore the 12-stage architecture without accessing protected infrastructure data."
            actions={
              <div className="row" style={{ gap: 6 }}>
                <button className="btn btn-sm btn-primary" onClick={() => runWalkthrough({ transcript: 'Explain what NetResolve AI does' })} disabled={walkthroughBusy}>
                  <BookOpen size={13} /> EXPLAIN NETRESOLVE AI
                </button>
                <button
                  className="btn btn-sm"
                  onClick={() => runWalkthrough({ step: Math.min(12, walkthroughStep + 1) })}
                  disabled={walkthroughBusy}
                >
                  {walkthroughStep === 0 ? 'START 12-STEP TOUR' : `NEXT STEP (${Math.min(12, walkthroughStep + 1)}/12)`}
                </button>
              </div>
            }
          >
            {walkthroughRes ? (
              <div className="stack" style={{ gap: 8 }}>
                <div style={{ fontSize: 13, color: '#171614' }}>{walkthroughRes.visible_summary}</div>
                {walkthroughRes.note && <div className="mono muted" style={{ fontSize: 11 }}>{walkthroughRes.note}</div>}
                {walkthroughRes.navigate_to && (
                  <div>
                    <button className="btn btn-sm" onClick={() => navigate(walkthroughRes.navigate_to as PageId)}>
                      OPEN {walkthroughRes.stage?.route_label?.toUpperCase() || walkthroughRes.navigate_to.toUpperCase()} <ArrowRight size={12} />
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <div className="muted" style={{ fontSize: 12 }}>
                Click <strong>Explain NetResolve AI</strong> or <strong>Start 12-Step Tour</strong> to learn how telemetry ingestion,
                deterministic rules, XGBoost triage, multi-agent RCA, and human-approved remediation work together.
              </div>
            )}
          </Panel>
        </div>
      ) : (
        <>
          {/* Authenticated Operator Principal Header Card */}
          <Panel className="mb-4" bodyClassName="stack">
            <div className="row wrap" style={{ justifyContent: 'space-between', gap: 12, paddingBottom: 12, borderBottom: '1px solid var(--border)' }}>
              <div>
                <div className="eyebrow">OPERATOR PRINCIPAL</div>
                <div className="row" style={{ gap: 10 }}>
                  <span style={{ fontSize: 16, fontWeight: 700, color: '#171614' }}>{principal.display_name}</span>
                  <Badge tone="neutral">{principal.demo_session ? 'LOCAL DEMO SESSION (EPHEMERAL)' : 'CONFIGURED PRINCIPAL'}</Badge>
                </div>
              </div>
              <div className="row wrap" style={{ gap: 8 }}>
                {stepUpHint && (
                  <span className="status-chip warn">
                    STEP-UP CODE: <strong>{stepUpHint}</strong>
                  </span>
                )}
                {config?.demo_sessions_enabled && (
                  <select
                    className="input"
                    style={{ height: 30, fontSize: 11, width: 170 }}
                    value={selectedProfile}
                    onChange={(e) => {
                      const next = e.target.value as DemoProfileId;
                      setSelectedProfile(next);
                      startDemoSession(next);
                    }}
                    aria-label="Switch demo profile"
                  >
                    {(config.demo_profiles || []).map((p) => (
                      <option key={p.id} value={p.id}>
                        Switch: {p.id}
                      </option>
                    ))}
                  </select>
                )}
                <button className="btn btn-sm" onClick={handleClearConversation} title="Clear conversation memory">
                  <Trash2 size={12} /> CLEAR CHAT
                </button>
                <button className="btn btn-sm btn-danger" onClick={revokeSession}>
                  <LogOut size={12} /> REVOKE
                </button>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 12 }} className="activity-grid">
              <div>
                <div className="eyebrow">RBAC ASSIGNED ROLE</div>
                <div className="mono strong" style={{ fontSize: 12 }}>● {principal.role}</div>
              </div>
              <div>
                <div className="eyebrow">PERMITTED HOST SCOPE</div>
                <div className="row wrap" style={{ gap: 4 }}>
                  {principal.allowed_hosts.map((h) => (
                    <Badge key={h} mono>{h}</Badge>
                  ))}
                </div>
              </div>
              <div>
                <div className="eyebrow">REMEDIATION POLICY</div>
                <div className="mono" style={{ fontSize: 12 }}>
                  {(config?.remediation_mode || 'simulate').toUpperCase()} · Explicit Readback
                </div>
              </div>
              <div>
                <div className="eyebrow">CONVERSATION CONTEXT</div>
                <div className="mono" style={{ fontSize: 11, color: 'var(--text-2)' }}>
                  Host: <strong>{convContext?.selected_host || 'none'}</strong> · Stage: <strong>{convContext?.investigation_stage || 'idle'}</strong>
                </div>
              </div>
            </div>
          </Panel>

          {/* Explicit Confirmation Readback Card */}
          {pendingConfirm && (
            <div className="nr-confirm-card" role="alert">
              <div className="row wrap" style={{ justifyContent: 'space-between', gap: 8, marginBottom: 10 }}>
                <div className="row wrap" style={{ gap: 8 }}>
                  <span style={{ background: '#171614', color: '#f6f5f1', padding: '2px 8px', fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700 }}>
                    ACTION REQUIRES EXPLICIT CONFIRMATION
                  </span>
                  {pendingConfirm.proposal_id && <Badge mono>proposal: {pendingConfirm.proposal_id}</Badge>}
                  {pendingConfirm.preview_digest && <Badge mono>digest: {pendingConfirm.preview_digest}</Badge>}
                  {pendingConfirm.mode && <Badge tone={pendingConfirm.mode === 'ansible' ? 'crit' : 'warn'}>MODE: {pendingConfirm.mode.toUpperCase()}</Badge>}
                  {pendingConfirm.risk && <Badge tone={pendingConfirm.risk === 'high' ? 'crit' : 'warn'}>RISK: {pendingConfirm.risk.toUpperCase()}</Badge>}
                </div>
                <span className="mono muted" style={{ fontSize: 11 }}>Expires {formatTime(pendingConfirm.expires_at)}</span>
              </div>

              <div className="eyebrow">TARGET READBACK VERIFICATION</div>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#171614', marginBottom: 10 }}>
                {pendingConfirm.readback}
              </div>

              {pendingConfirm.requires_step_up && (
                <div className="row wrap" style={{ gap: 8, marginBottom: 10 }}>
                  <input
                    className="input mono"
                    style={{ width: 200, maxWidth: '100%' }}
                    value={stepUpCode}
                    onChange={(e) => setStepUpCode(e.target.value)}
                    placeholder="Senior step-up code"
                    aria-label="Senior approver step-up code"
                  />
                  <input
                    className="input mono"
                    style={{ width: 240, maxWidth: '100%' }}
                    type="password"
                    value={secondApproverToken}
                    onChange={(e) => setSecondApproverToken(e.target.value)}
                    placeholder="Or second senior_approver token"
                    aria-label="Second senior approver token"
                  />
                </div>
              )}

              <div className="row wrap" style={{ gap: 8 }}>
                <input
                  className="input mono"
                  style={{ width: 200, maxWidth: '100%' }}
                  value={confirmPhrase}
                  onChange={(e) => setConfirmPhrase(e.target.value)}
                  placeholder="Type 'yes confirm'"
                  aria-label="Explicit confirmation phrase"
                />
                <button className="btn btn-primary" onClick={() => handleConfirmDecision(true)} disabled={busy}>
                  <CheckCircle2 size={13} /> CONFIRM
                </button>
                <button className="btn btn-danger" onClick={() => handleConfirmDecision(false)} disabled={busy}>
                  <X size={13} /> CANCEL
                </button>
              </div>
            </div>
          )}

          {/* Main Split Grid: Ingress Console + Feed (Left) / Enclave & Topology Context (Right) */}
          <div className="nr-voice-grid" style={{ marginBottom: 16 }}>
            <div className="stack">
              <Panel
                title="Real-Time Ingress Console"
                actions={
                  <span className="mono muted" style={{ fontSize: 10 }}>
                    STT: {speechSupported ? 'WebSpeech (Push-to-Talk)' : 'Text Fallback Only'}
                  </span>
                }
              >
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    submitQuery(transcript, 'text');
                  }}
                  className="row"
                  style={{ gap: 8, marginBottom: 12 }}
                >
                  <button
                    type="button"
                    className={`btn ${listening ? 'btn-danger' : 'btn-primary'}`}
                    onClick={togglePushToTalk}
                    disabled={busy}
                    style={{ minWidth: 100 }}
                  >
                    {listening ? <MicOff size={14} /> : <Mic size={14} />}
                    {listening ? 'STOP' : 'SPEAK'}
                  </button>
                  <input
                    className="input mono"
                    style={{ flex: 1 }}
                    value={transcript}
                    onChange={(e) => setTranscript(e.target.value)}
                    placeholder="> Ask naturally: e.g., Is everything running smoothly? or Investigate gpu-b..."
                    aria-label="Conversational operations input"
                    disabled={busy}
                  />
                  <button type="submit" className="btn btn-primary" disabled={busy || !transcript.trim()} aria-label="Send message">
                    <Send size={13} />
                  </button>
                </form>

                <div className="row wrap" style={{ gap: 6, alignItems: 'center' }}>
                  <span className="eyebrow" style={{ marginBottom: 0, marginRight: 4 }}>TRY ASKING:</span>
                  {CONVERSATIONAL_PROMPTS.map((p) => (
                    <button
                      key={p}
                      type="button"
                      className="btn btn-sm"
                      style={{ fontSize: 11, fontFamily: 'var(--font-mono)', background: 'var(--bg)' }}
                      onClick={() => submitQuery(p, 'text')}
                      disabled={busy}
                    >
                      {p}
                    </button>
                  ))}
                </div>
              </Panel>

              {/* Structured Voice Responses & Conversation Feed */}
              <Panel
                title="Conversational Operations Feed"
                count={responses.length}
                flush
              >
                {responses.length === 0 ? (
                  <EmptyState
                    compact
                    title="Ready for voice or text operations"
                    description="Start talking or click any prompt above to inspect infrastructure health, investigate incidents, walk through NetResolve AI, or preview a remediation."
                  />
                ) : (
                  <div className="nr-chat-stream">
                    {responses.map((r, idx) => {
                      const tone = statusTone(r.status);
                      const isOpen = !!expandedJson[idx];
                      return (
                        <div key={`${r.audit_seq}-${idx}`} className={cx('nr-chat-msg assistant', tone === 'warn' && 'warn', tone === 'crit' && 'crit')}>
                          <div className="row wrap" style={{ justifyContent: 'space-between', gap: 6, marginBottom: 6 }}>
                            <div className="row wrap" style={{ gap: 6 }}>
                              <Badge tone={tone}>{r.status.toUpperCase()}</Badge>
                              {r.interpreted?.intent && <Badge mono>intent: {r.interpreted.intent}</Badge>}
                              {r.evidence_meta?.simulated && <Badge tone="warn">simulated</Badge>}
                              {r.ai_backend && <Badge mono>{r.ai_backend}</Badge>}
                              {r.injection_flagged && <Badge tone="crit">INJECTION NEUTRALIZED</Badge>}
                            </div>
                            <span className="mono muted" style={{ fontSize: 10 }}>{formatTime(r.ts)}</span>
                          </div>

                          <div
                            className="mono"
                            style={{
                              fontSize: 11,
                              padding: '6px 10px',
                              background: 'var(--bg)',
                              border: '1px solid var(--border)',
                              marginBottom: 8,
                              color: 'var(--text-2)',
                            }}
                          >
                            &gt; &ldquo;{r.recognized_transcript}&rdquo;
                          </div>

                          <div style={{ fontSize: 13, color: '#171614', lineHeight: 1.5, marginBottom: 8 }}>
                            {r.visible_summary}
                          </div>

                          {/* Suggested Follow-Ups & Navigation */}
                          <div className="row wrap" style={{ justifyContent: 'space-between', gap: 8, paddingTop: 8, borderTop: '1px solid var(--border)' }}>
                            <div className="row wrap" style={{ gap: 6 }}>
                              {(r.suggested_actions || []).map((act) => (
                                <button
                                  key={act}
                                  type="button"
                                  className="btn btn-sm"
                                  style={{ fontSize: 11 }}
                                  onClick={() => submitQuery(act, 'text')}
                                  disabled={busy}
                                >
                                  {act}
                                </button>
                              ))}
                              {r.navigate_to && (
                                <button
                                  type="button"
                                  className="btn btn-sm btn-primary"
                                  style={{ fontSize: 11 }}
                                  onClick={() => navigate(r.navigate_to as PageId)}
                                >
                                  OPEN {r.navigate_to.toUpperCase()} <ArrowRight size={11} />
                                </button>
                              )}
                            </div>

                            <button
                              type="button"
                              className="btn btn-sm btn-ghost mono"
                              style={{ fontSize: 10 }}
                              onClick={() => setExpandedJson((prev) => ({ ...prev, [idx]: !prev[idx] }))}
                            >
                              <Code2 size={11} /> {isOpen ? 'HIDE JSON' : 'INSPECT JSON'}
                            </button>
                          </div>

                          {isOpen && (
                            <pre
                              className="mono"
                              style={{
                                marginTop: 8,
                                padding: 10,
                                background: '#171614',
                                color: '#f6f5f1',
                                fontSize: 11,
                                overflowX: 'auto',
                                maxHeight: 260,
                              }}
                            >
                              {JSON.stringify(r.data ?? r, null, 2)}
                            </pre>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </Panel>
            </div>

            {/* Right Rail: Runtime Voice Enclave Rules & Topology Context */}
            <div className="stack">
              <Panel title="Runtime Voice Enclave Rules" actions={<Shield size={13} />}>
                <div className="stack" style={{ gap: 8, fontSize: 12 }}>
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <span>Arbitrary Shell / SQL Exec</span>
                    <Badge tone="crit">BLOCKED</Badge>
                  </div>
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <span>Cross-Tenant Host Scope</span>
                    <Badge tone="crit">BLOCKED</Badge>
                  </div>
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <span>Automated Secret Redaction</span>
                    <Badge tone="ok">ACTIVE</Badge>
                  </div>
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <span>Prompt-Injection Guard</span>
                    <Badge tone="ok">ENFORCED</Badge>
                  </div>
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <span>Live Ansible Over Voice</span>
                    <Badge tone={config?.voice_allow_ansible ? 'warn' : 'neutral'}>
                      {config?.voice_allow_ansible ? 'OPT-IN + STEP-UP' : 'DISABLED'}
                    </Badge>
                  </div>
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <span>Raw Audio Retention</span>
                    <Badge tone="ok">NONE</Badge>
                  </div>
                </div>
              </Panel>

              <Panel title="Active Session Memory">
                <div className="stack" style={{ gap: 6, fontSize: 12 }}>
                  <div className="nr-topo-kv">
                    <span>Active Topic:</span>
                    <strong>{convContext?.active_topic || 'none'}</strong>
                  </div>
                  <div className="nr-topo-kv">
                    <span>Selected Host:</span>
                    <strong>{convContext?.selected_host || 'none'}</strong>
                  </div>
                  <div className="nr-topo-kv">
                    <span>Selected Proposal:</span>
                    <strong>{convContext?.selected_proposal_id || 'none'}</strong>
                  </div>
                  <div className="nr-topo-kv">
                    <span>Stage:</span>
                    <strong>{convContext?.investigation_stage || 'idle'}</strong>
                  </div>
                  <div className="nr-topo-kv">
                    <span>Turns Recorded:</span>
                    <strong>{convContext?.turn_count ?? 0}</strong>
                  </div>
                </div>
              </Panel>

              <Panel title="Authorized Host Scope" count={principal.allowed_hosts.length}>
                <div className="stack" style={{ gap: 6 }}>
                  {principal.allowed_hosts.map((h) => (
                    <div
                      key={h}
                      className="row"
                      style={{
                        justifyContent: 'space-between',
                        padding: '6px 8px',
                        background: convContext?.selected_host === h ? 'var(--warn-bg)' : 'var(--bg)',
                        border: '1px solid var(--border)',
                      }}
                    >
                      <span className="mono strong" style={{ fontSize: 12 }}>{h}</span>
                      <button
                        type="button"
                        className="btn btn-sm"
                        style={{ fontSize: 10 }}
                        onClick={() => submitQuery(`Investigate ${h}`, 'text')}
                        disabled={busy || h === '*'}
                      >
                        INVESTIGATE
                      </button>
                    </div>
                  ))}
                </div>
              </Panel>
            </div>
          </div>

          {/* Redacted Voice Audit Trail */}
          <Panel
            title="Redacted Voice Audit Trail"
            sub="Immutable record of recognized transcripts, policy checks, and confirmation outcomes."
            count={audit.length}
            actions={
              <button className="btn btn-sm" onClick={exportAuditCsv} disabled={!audit.length}>
                <Download size={12} /> EXPORT CSV
              </button>
            }
            flush
          >
            {audit.length === 0 ? (
              <EmptyState compact title="No voice audit records yet" />
            ) : (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th># Seq</th>
                      <th>Operator / Role</th>
                      <th>Intent</th>
                      <th>Target Host</th>
                      <th>Auth Status</th>
                      <th>Outcome</th>
                      <th>Redacted Transcript</th>
                    </tr>
                  </thead>
                  <tbody>
                    {audit.map((a) => (
                      <tr key={a.seq}>
                        <td className="mono">#{a.seq}</td>
                        <td>
                          <div className="strong" style={{ fontSize: 12 }}>{a.user_id}</div>
                          <div className="mono muted" style={{ fontSize: 10 }}>{a.role}</div>
                        </td>
                        <td className="mono">{a.intent || '—'}</td>
                        <td className="mono">{a.target_host || '—'}</td>
                        <td>
                          <Badge tone={a.authorized ? 'ok' : 'crit'}>{a.authorized ? 'ALLOWED' : 'DENIED'}</Badge>
                        </td>
                        <td>
                          <Badge tone={statusTone(a.outcome)}>{a.outcome.toUpperCase()}</Badge>
                        </td>
                        <td className="mono" style={{ fontSize: 11, maxWidth: 320 }}>{a.redacted_transcript}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </>
      )}
    </>
  );
};
