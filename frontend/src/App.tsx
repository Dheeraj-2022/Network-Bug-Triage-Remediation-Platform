import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ApprovalModal, ClearConfirmModal, InjectModal } from './components/ActionModals';
import { Sidebar } from './components/Sidebar';
import { ToastContainer, ToastMessage } from './components/Toast';
import { Topbar } from './components/Topbar';
import { Banner } from './components/ui';
import { AiAnalysisPage } from './pages/AiAnalysisPage';
import { AuditTrailPage } from './pages/AuditTrailPage';
import { DecisionsPage } from './pages/DecisionsPage';
import { EventsPage } from './pages/EventsPage';
import { IncidentDetailPage } from './pages/IncidentDetailPage';
import { IncidentsPage } from './pages/IncidentsPage';
import { OverviewPage } from './pages/OverviewPage';
import { RemediationPage } from './pages/RemediationPage';
import { Navigate } from './pages/common';
import { api, API_BASE_URL } from './services/api';
import { buildHostHealth, buildIncidents, Incident, STATE_META } from './lib/incidents';
import { hrefFor, parseHash, Route } from './lib/routes';
import { AIIncident, AIStatus, AuditEntry, Decision, SystemStatus, TelemetryEvent } from './types';

// Hash routing keeps deep links and back/forward without a router dependency.
const FETCH_LIMIT = 200;

export const App: React.FC = () => {
  const [route, setRoute] = useState<Route>(() => parseHash(window.location.hash));

  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [events, setEvents] = useState<TelemetryEvent[]>([]);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [auditLog, setAuditLog] = useState<AuditEntry[]>([]);
  const [aiStatus, setAiStatus] = useState<AIStatus | null>(null);
  const [aiIncidents, setAiIncidents] = useState<AIIncident[]>([]);

  const [connection, setConnection] = useState<'connecting' | 'online' | 'offline'>('connecting');
  const [loaded, setLoaded] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<number | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const [isInjecting, setIsInjecting] = useState(false);
  const [isLoadingSamples, setIsLoadingSamples] = useState(false);
  const [isTraining, setIsTraining] = useState(false);
  const [isClearing, setIsClearing] = useState(false);
  const [isApproving, setIsApproving] = useState(false);

  const [isClearModalOpen, setIsClearModalOpen] = useState(false);
  const [isInjectModalOpen, setIsInjectModalOpen] = useState(false);
  const [approval, setApproval] = useState<{ incident: Incident; approve: boolean } | null>(null);
  const [isLive, setIsLive] = useState(true);

  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const mainRef = useRef<HTMLElement>(null);

  const removeToast = useCallback((id: string) => setToasts((prev) => prev.filter((t) => t.id !== id)), []);
  const addToast = useCallback(
    (type: ToastMessage['type'], title: string, message?: string) => {
      const id = `${Date.now()}-${Math.random()}`;
      setToasts((prev) => [...prev.slice(-3), { id, type, title, message }]);
      setTimeout(() => removeToast(id), type === 'error' ? 8000 : 4500);
    },
    [removeToast],
  );

  useEffect(() => {
    const onHash = () => {
      setRoute(parseHash(window.location.hash));
      mainRef.current?.scrollTo({ top: 0 });
    };
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  const navigate: Navigate = useCallback((page, param, query) => {
    window.location.hash = hrefFor(page, param, query);
  }, []);

  const refreshAll = useCallback(async () => {
    setIsRefreshing(true);
    const [s, evs, decs, aud, aiS, aiIncs] = await Promise.allSettled([
      api.getStatus(),
      api.getEvents(FETCH_LIMIT),
      api.getDecisions(FETCH_LIMIT),
      api.getAudit(FETCH_LIMIT),
      api.getAiStatus(),
      api.getAiIncidents(FETCH_LIMIT),
    ]);
    if (s.status === 'fulfilled') setStatus(s.value);
    if (evs.status === 'fulfilled') setEvents(evs.value);
    if (decs.status === 'fulfilled') setDecisions(decs.value);
    if (aud.status === 'fulfilled') setAuditLog(aud.value);
    if (aiS.status === 'fulfilled') setAiStatus(aiS.value);
    if (aiIncs.status === 'fulfilled') setAiIncidents(aiIncs.value);
    setConnection(s.status === 'fulfilled' ? 'online' : 'offline');
    if (s.status === 'fulfilled') setLastUpdated(Date.now());
    setLoaded(true);
    setIsRefreshing(false);
  }, []);

  useEffect(() => {
    refreshAll();
  }, [refreshAll]);

  useEffect(() => {
    if (!isLive) return;
    const interval = setInterval(refreshAll, 5000);
    return () => clearInterval(interval);
  }, [isLive, refreshAll]);

  const incidents = useMemo(() => buildIncidents(decisions, aiIncidents), [decisions, aiIncidents]);
  const hostHealth = useMemo(() => buildHostHealth(events, incidents), [events, incidents]);
  const awaitingApproval = incidents.filter((i) => i.state === 'awaiting_approval');
  const openIncidents = incidents.filter((i) => STATE_META[i.state].group === 'action');

  // ---------------------------------------------------------------------------
  // Actions
  // ---------------------------------------------------------------------------
  const handleInject = async (count: number, injectErrors: boolean) => {
    setIsInjecting(true);
    try {
      const res = await api.injectEvents(count, injectErrors);
      const flagged = res.decisions.filter((d) => d.remediate).length;
      addToast('success', `Injected ${res.injected} events`, `${flagged} flagged for remediation by the triage pipeline.`);
      setIsInjectModalOpen(false);
      await refreshAll();
    } catch (err: any) {
      addToast('error', 'Injection failed', err.message);
    } finally {
      setIsInjecting(false);
    }
  };

  const handleLoadSamples = async () => {
    setIsLoadingSamples(true);
    try {
      const res = await api.loadSampleEvents();
      const flagged = res.decisions.filter((d) => d.remediate).length;
      addToast('success', `Loaded ${res.loaded} sample events`, `${flagged} flagged for remediation.`);
      await refreshAll();
    } catch (err: any) {
      addToast('error', 'Could not load sample events', err.message);
    } finally {
      setIsLoadingSamples(false);
    }
  };

  const handleTrainModel = async () => {
    setIsTraining(true);
    addToast('info', 'Training triage model', 'This can take a while on the first run.');
    try {
      const res = await api.trainModel();
      if (res.ok) addToast('success', 'Model trained', res.message);
      else addToast('error', 'Training failed', res.error || 'See controller logs.');
      await refreshAll();
    } catch (err: any) {
      addToast('error', 'Training failed', err.message);
    } finally {
      setIsTraining(false);
    }
  };

  const handleClearState = async () => {
    setIsClearing(true);
    try {
      await api.clearState();
      addToast('info', 'Platform state reset', 'Events, decisions, audit entries and AI incidents were cleared.');
      setIsClearModalOpen(false);
      await refreshAll();
    } catch (err: any) {
      addToast('error', 'Reset failed', err.message);
    } finally {
      setIsClearing(false);
    }
  };

  const requestApproval = (incident: Incident, approve: boolean) => setApproval({ incident, approve });

  const confirmApproval = async () => {
    if (!approval?.incident.aiId) return;
    const { incident, approve } = approval;
    setIsApproving(true);
    try {
      const res = await api.approveAiIncident(incident.aiId!, approve);
      addToast(
        approve ? 'success' : 'info',
        approve ? 'Remediation approved' : 'Remediation rejected',
        `${incident.title} — status: ${res.status}.`,
      );
      setApproval(null);
      await refreshAll();
    } catch (err: any) {
      addToast('error', 'Approval was not recorded', err.message);
    } finally {
      setIsApproving(false);
    }
  };

  const openInject = () => setIsInjectModalOpen(true);

  const empty = loaded && connection === 'online' && events.length === 0 && decisions.length === 0;
  const common = { loaded, connection, navigate, onInject: openInject, onLoadSamples: handleLoadSamples, isLoadingSamples };

  let page: React.ReactNode = null;
  switch (route.page) {
    case 'overview':
      page = (
        <OverviewPage
          {...common}
          status={status}
          events={events}
          decisions={decisions}
          incidents={incidents}
          hostHealth={hostHealth}
          auditLog={auditLog}
          aiStatus={aiStatus}
          empty={empty}
          onRequestApproval={requestApproval}
        />
      );
      break;
    case 'incidents':
      page = <IncidentsPage {...common} key={route.query.toString()} incidents={incidents} query={route.query} />;
      break;
    case 'incident-detail':
      page = (
        <IncidentDetailPage
          {...common}
          key={route.param}
          incidentKey={route.param!}
          incidents={incidents}
          events={events}
          auditLog={auditLog}
          aiStatus={aiStatus}
          onRequestApproval={requestApproval}
        />
      );
      break;
    case 'remediation':
      page = (
        <RemediationPage
          {...common}
          incidents={incidents}
          aiStatus={aiStatus}
          auditLog={auditLog}
          onRequestApproval={requestApproval}
        />
      );
      break;
    case 'events':
      page = <EventsPage {...common} key={route.query.toString()} events={events} decisions={decisions} incidents={incidents} query={route.query} />;
      break;
    case 'decisions':
      page = <DecisionsPage {...common} key={route.query.toString()} decisions={decisions} incidents={incidents} query={route.query} />;
      break;
    case 'ai-analysis':
      page = <AiAnalysisPage {...common} aiStatus={aiStatus} status={status} incidents={incidents} onTrainModel={handleTrainModel} isTraining={isTraining} />;
      break;
    case 'audit-trail':
      page = <AuditTrailPage {...common} auditLog={auditLog} incidents={incidents} />;
      break;
  }

  return (
    <div className="app">
      <Sidebar
        currentPage={route.page}
        onNavigate={(p) => navigate(p)}
        counts={{
          openIncidents: openIncidents.length,
          awaitingApproval: awaitingApproval.length,
          events: status?.total_events ?? events.length,
          decisions: status?.total_decisions ?? decisions.length,
          executions: auditLog.length,
        }}
        connection={connection}
        modelTrained={status?.model_trained}
        aiBackend={aiStatus?.enabled ? aiStatus.llm_backend : null}
      />

      <div className="main">
        <Topbar
          incidents={incidents}
          events={events}
          onOpenIncident={(key) => navigate('incident-detail', key)}
          onOpenEvent={(id) => navigate('events', undefined, { event: id })}
          onOpenHost={(host) => navigate('events', undefined, { host })}
          onInject={openInject}
          onLoadSamples={handleLoadSamples}
          onTrainModel={handleTrainModel}
          onClearState={() => setIsClearModalOpen(true)}
          onRefresh={refreshAll}
          isInjecting={isInjecting}
          isLoadingSamples={isLoadingSamples}
          isTraining={isTraining}
          isRefreshing={isRefreshing}
          isLive={isLive}
          setIsLive={setIsLive}
          lastUpdated={lastUpdated}
          connection={connection}
        />

        <main className="content" ref={mainRef} id="main">
          <div className="page">
            {connection === 'offline' && (
              <Banner
                tone="crit"
                title="Cannot reach the triage controller"
                actions={
                  <button className="btn btn-sm" onClick={refreshAll}>
                    Retry
                  </button>
                }
              >
                Requests to <span className="mono">{API_BASE_URL}</span> are failing. Start the API with{' '}
                <span className="mono">python main.py</span> or set <span className="mono">VITE_API_BASE_URL</span>.
                {lastUpdated ? ' Data shown below is from the last successful refresh.' : ''}
              </Banner>
            )}
            {page}
          </div>
        </main>
      </div>

      <ClearConfirmModal isOpen={isClearModalOpen} onClose={() => setIsClearModalOpen(false)} onConfirm={handleClearState} isLoading={isClearing} />
      <InjectModal isOpen={isInjectModalOpen} onClose={() => setIsInjectModalOpen(false)} onInject={handleInject} isLoading={isInjecting} />
      <ApprovalModal
        incident={approval?.incident ?? null}
        approve={approval?.approve ?? true}
        onClose={() => setApproval(null)}
        onConfirm={confirmApproval}
        isLoading={isApproving}
      />
      <ToastContainer toasts={toasts} onDismiss={removeToast} />
    </div>
  );
};

export default App;
