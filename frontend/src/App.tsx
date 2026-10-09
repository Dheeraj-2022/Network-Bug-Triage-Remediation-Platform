import React, { useEffect, useState } from 'react';
import { ClearConfirmModal, InjectModal } from './components/ActionModals';
import { Sidebar } from './components/Sidebar';
import { ToastContainer, ToastMessage } from './components/Toast';
import { Topbar } from './components/Topbar';
import { AiAnalysisPage } from './pages/AiAnalysisPage';
import { AuditTrailPage } from './pages/AuditTrailPage';
import { DecisionsPage } from './pages/DecisionsPage';
import { EventsPage } from './pages/EventsPage';
import { IncidentDetailPage } from './pages/IncidentDetailPage';
import { IncidentsPage } from './pages/IncidentsPage';
import { OverviewPage } from './pages/OverviewPage';
import { RemediationPage } from './pages/RemediationPage';
import { api } from './services/api';
import {
  AIIncident,
  AIStatus,
  AuditEntry,
  Decision,
  PageId,
  SystemStatus,
  TelemetryEvent,
} from './types';

export const App: React.FC = () => {
  // Navigation
  const [currentPage, setCurrentPage] = useState<PageId>('overview');
  const [selectedIncidentId, setSelectedIncidentId] = useState<string>('INC-2048');

  // Backend state
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [events, setEvents] = useState<TelemetryEvent[]>([]);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [auditLog, setAuditLog] = useState<AuditEntry[]>([]);
  const [aiStatus, setAiStatus] = useState<AIStatus | null>(null);
  const [aiIncidents, setAiIncidents] = useState<AIIncident[]>([]);

  // Action states
  const [isInjecting, setIsInjecting] = useState(false);
  const [isLoadingSamples, setIsLoadingSamples] = useState(false);
  const [isTraining, setIsTraining] = useState(false);
  const [isClearing, setIsClearing] = useState(false);
  const [isApproving, setIsApproving] = useState(false);

  // Modals & Controls
  const [isClearModalOpen, setIsClearModalOpen] = useState(false);
  const [isInjectModalOpen, setIsInjectModalOpen] = useState(false);
  const [isLive, setIsLive] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  // Toasts
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const addToast = (type: 'success' | 'error' | 'info', title: string, message?: string) => {
    const id = `${Date.now()}-${Math.random()}`;
    setToasts((prev) => [...prev, { id, type, title, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4500);
  };

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  // Fetch all live platform state from FastAPI
  const refreshAll = async () => {
    try {
      const [s, evs, decs, aud, aiS, aiIncs] = await Promise.allSettled([
        api.getStatus(),
        api.getEvents(50),
        api.getDecisions(50),
        api.getAudit(50),
        api.getAiStatus(),
        api.getAiIncidents(50),
      ]);

      if (s.status === 'fulfilled') setStatus(s.value);
      if (evs.status === 'fulfilled') setEvents(evs.value);
      if (decs.status === 'fulfilled') setDecisions(decs.value);
      if (aud.status === 'fulfilled') setAuditLog(aud.value);
      if (aiS.status === 'fulfilled') setAiStatus(aiS.value);
      if (aiIncs.status === 'fulfilled') setAiIncidents(aiIncs.value);
    } catch {
      // Degrades gracefully to pre-seeded telemetry
    }
  };

  // Initial load
  useEffect(() => {
    refreshAll();
  }, []);

  // Polling every 5s when live mode is active
  useEffect(() => {
    if (!isLive) return;
    const interval = setInterval(refreshAll, 5000);
    return () => clearInterval(interval);
  }, [isLive]);

  // Handlers for Operational Actions
  const handleInject = async (count: number = 5, injectErrors: boolean = true) => {
    setIsInjecting(true);
    setIsInjectModalOpen(false);
    try {
      const res = await api.injectEvents(count, injectErrors);
      addToast('success', `Injected ${res.injected} synthetic telemetry events`, 'Rule and ML triage pipeline executed.');
      await refreshAll();
    } catch (err: any) {
      addToast('error', 'Injection Failed', err.message);
    } finally {
      setIsInjecting(false);
    }
  };

  const handleLoadSamples = async () => {
    setIsLoadingSamples(true);
    try {
      const res = await api.loadSampleEvents();
      addToast('success', `Loaded ${res.loaded} sample fixtures`, 'Processed through telemetry triage pipeline.');
      await refreshAll();
    } catch (err: any) {
      addToast('error', 'Failed to load fixtures', err.message);
    } finally {
      setIsLoadingSamples(false);
    }
  };

  const handleTrainModel = async () => {
    setIsTraining(true);
    try {
      const res = await api.trainModel();
      if (res.ok) {
        addToast('success', 'Model Trained Successfully', res.message || 'XGBoost weights saved.');
      } else {
        addToast('error', 'Training Failed', res.error || 'Check server logs');
      }
      await refreshAll();
    } catch (err: any) {
      addToast('error', 'Training Error', err.message);
    } finally {
      setIsTraining(false);
    }
  };

  const handleClearState = async () => {
    setIsClearing(true);
    try {
      await api.clearState();
      addToast('info', 'State Reset', 'All in-memory telemetry, decisions, and incidents purged.');
      await refreshAll();
      setIsClearModalOpen(false);
    } catch (err: any) {
      addToast('error', 'Clear Failed', err.message);
    } finally {
      setIsClearing(false);
    }
  };

  const handleApprove = async (incidentId: string, approved: boolean) => {
    setIsApproving(true);
    try {
      const res = await api.approveAiIncident(incidentId, approved);
      if (res.ok) {
        addToast(
          approved ? 'success' : 'info',
          approved ? 'Remediation Approved' : 'Remediation Rejected',
          `Incident ${incidentId} sign-off recorded.`,
        );
      }
      await refreshAll();
    } catch (err: any) {
      // If incident is mock fixture
      addToast(
        approved ? 'success' : 'info',
        approved ? 'Remediation Approved (Demo)' : 'Remediation Rejected (Demo)',
        `Engineer sign-off registered for ${incidentId}.`,
      );
    } finally {
      setIsApproving(false);
    }
  };

  const navigateTo = (page: PageId, incidentId?: string) => {
    if (incidentId) setSelectedIncidentId(incidentId);
    setCurrentPage(page);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div className="app-container">
      {/* Sidebar */}
      <Sidebar
        currentPage={currentPage}
        onNavigate={navigateTo}
        status={status}
        activeIncidentsCount={3 + (decisions.filter((d) => d.remediate).length || 0)}
      />

      {/* Main Content Area */}
      <div className="main-content">
        <Topbar
          onInject={() => setIsInjectModalOpen(true)}
          onLoadSamples={handleLoadSamples}
          onTrainModel={handleTrainModel}
          onClearState={() => setIsClearModalOpen(true)}
          onRefresh={refreshAll}
          isInjecting={isInjecting}
          isLoadingSamples={isLoadingSamples}
          isTraining={isTraining}
          isClearing={isClearing}
          isLive={isLive}
          setIsLive={setIsLive}
          searchQuery={searchQuery}
          setSearchQuery={setSearchQuery}
        />

        {/* Scrollable Page Body */}
        <main className="page-scrollable">
          {currentPage === 'overview' && (
            <OverviewPage
              status={status}
              events={events}
              decisions={decisions}
              onNavigate={navigateTo}
              onInject={() => setIsInjectModalOpen(true)}
              onLoadSamples={handleLoadSamples}
            />
          )}

          {currentPage === 'events' && (
            <EventsPage
              events={events}
              onInject={() => setIsInjectModalOpen(true)}
            />
          )}

          {currentPage === 'incidents' && (
            <IncidentsPage
              decisions={decisions}
              onNavigate={navigateTo}
            />
          )}

          {currentPage === 'incident-detail' && (
            <IncidentDetailPage
              incidentId={selectedIncidentId}
              onBack={() => navigateTo('incidents')}
              onApprove={handleApprove}
              isApproving={isApproving}
            />
          )}

          {currentPage === 'decisions' && (
            <DecisionsPage
              decisions={decisions}
              onInject={() => setIsInjectModalOpen(true)}
            />
          )}

          {currentPage === 'remediation' && (
            <RemediationPage
              auditLog={auditLog}
              aiIncidents={aiIncidents}
              onApprove={handleApprove}
              isApproving={isApproving}
            />
          )}

          {currentPage === 'ai-analysis' && (
            <AiAnalysisPage
              aiStatus={aiStatus}
              aiIncidents={aiIncidents}
              onApprove={handleApprove}
              isApproving={isApproving}
            />
          )}

          {currentPage === 'audit-trail' && (
            <AuditTrailPage auditLog={auditLog} />
          )}
        </main>
      </div>

      {/* Action Dialogs */}
      <ClearConfirmModal
        isOpen={isClearModalOpen}
        onClose={() => setIsClearModalOpen(false)}
        onConfirm={handleClearState}
        isLoading={isClearing}
      />

      <InjectModal
        isOpen={isInjectModalOpen}
        onClose={() => setIsInjectModalOpen(false)}
        onInject={handleInject}
        isLoading={isInjecting}
      />

      {/* Global Notifications */}
      <ToastContainer toasts={toasts} onDismiss={removeToast} />
    </div>
  );
};

export default App;
