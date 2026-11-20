<<<<<<< HEAD
# NetResolve AI — Intelligent Network Operations & Human-Approved Remediation Platform

## Project Overview

NetResolve AI is an enterprise network operations, bug triage, and human-authorized remediation platform for multi-VM and GPU/RDMA cluster environments. It combines deterministic telemetry analysis, XGBoost machine-learning triage, LangGraph multi-agent root-cause analysis (Google Vertex AI Gemini with offline heuristic fallback), a bounded conversational Voice Operations agent, and a policy-enforced human-approval remediation pipeline.

## End-to-End Operational Flow

`Telemetry Agent → Kafka / FastAPI Ingestion → Controller Processor → Deterministic Rules + XGBoost Triage → Evidence & Topology Correlation → Multi-Agent AI RCA + Hybrid RAG → RemediationPolicy Proposal & Preview → Explicit Human Authorization → Controlled Execution (Simulated / Opt-in Ansible) → Deterministic Post-Check Verification → Redacted Audit Trail`

## Architecture

### 1. Telemetry Agent (`agent/`)
- **Purpose**: Collects host-level network and kernel telemetry from cluster nodes.
- **Key Features**:
  - Periodic collection of kernel logs (`dmesg` tail), interface counters (`psutil`: `rx_bytes`, `tx_bytes`, `errin`, `errout`, `mtu`), RDMA queue-pair counters (`rdma-core`), and optional packet sampling (eBPF).
  - Apache Kafka publishing with local file-based buffering and retry reliability.
  - YAML-driven configuration (`agent/config.yaml`) and systemd service packaging (`agent/service/`).

### 2. Controller, AI, Voice & Remediation Core (`controller/`)
- **Core Triage Pipeline**:
  - `processor.py`: Orchestrates event normalization, per-host baseline tracking, rules, ML scoring, evidence generation, and AI escalation.
  - `rules_engine.py`: Deterministic threshold checks (e.g., interface error spikes, RDMA QP errors).
  - `nlp_parser.py` & `log_anomaly.py`: Kernel log classification and anomaly scoring.
  - `triage_model.py`: XGBoost priority and fault-domain localization classifier.
  - `topology.py` & `evidence.py`: Compares observed telemetry against approved topology intent (e.g., expected MTU `9000` vs. observed `1500`), computes counter deltas, and records change correlations (explicitly distinguished from causation).
  - `demo_scenarios.py`: Deterministic, repeatable `demo:mtu-two-host` synthetic fixture (`gpu-a ↔ leaf-1 ↔ gpu-b`) with `pass`, `fail`, and `inconclusive` post-check variants.
- **Multi-Agent AI & RAG (`controller/ai/`)**:
  - `orchestrator.py` & `agents.py`: LangGraph `StateGraph` multi-agent reasoning pipeline (planner, RCA, remediation advisor, validator).
  - `llm.py`: Unified `LLMClient` supporting Google Vertex AI Gemini (`ChatVertexAI` / `vertexai` SDK) with automatic, honest `HeuristicBackend` fallback when offline.
  - `retriever.py`, `knowledge_base.py`, `vector_store.py`, `memory.py`: Hybrid vector + keyword retrieval over Markdown runbooks (`controller/ai/knowledge/`) and persistent incident memory.
  - `adk_integration.py`, `evaluation.py`, `monitoring.py`: Google ADK integration, evaluation helpers, and pipeline latency/counter metrics.
- **Bounded Conversational Voice Operations Agent (`controller/voice/`)**:
  - `agent.py`: `ConversationalOpsAgent` combining Vertex Gemini structured tool routing (when online) with deterministic conversational NLU fallback (when offline). Strictly bound to `ALL_ALLOWED_INTENTS`.
  - `engine.py`: Multi-step host investigation, platform health synthesis, contextual follow-ups, and two-step readback/confirmation workflow.
  - `conversation.py`: Per-user, session-isolated `ConversationStore` tracking active host, incident, proposal, investigation stage, and walkthrough step.
  - `knowledge.py`: Application awareness and interactive 12-stage NetResolve AI walkthrough (including anonymous-safe `POST /api/voice/walkthrough`).
  - `auth.py`, `security.py`, `audit.py`: Token authentication, RBAC (`viewer`, `operator`, `senior_approver`), per-host scoping, step-up / second-approver verification, secret redaction, prompt-injection neutralization, and redacted audit logging.
- **Central Remediation Policy (`controller/remediation/`)**:
  - `policy.py`: Single authoritative `RemediationPolicy` boundary (`propose`, `decide`, `verify`) with SHA-256 preview digests, approval TTL expiry, idempotency, and strict target/playbook validation.
  - `catalog.py` & `candidates.py`: Allowlisted actions (`set_mtu`, `restart_driver`, `collect_forensics`), driver allowlists, and inventory validation.
  - `executors.py`: Simulated dry-run executor (default) and strictly gated Ansible executor.
  - `verification.py`: Deterministic post-remediation checks returning `VERIFIED RESOLVED` (`passed`), `VERIFICATION FAILED` (`failed`), or `VERIFICATION INCONCLUSIVE` (`inconclusive`).
  - `store.py`: Persistent proposal and audit storage.

### 3. API Layer (`main.py`, `api/`, `schemas.py`, `app.py`)
- **FastAPI Primary Backend (`main.py`)**:
  - `api/routes.py`: `/api/auth`, `/api/status`, `/api/events`, `/api/inject`, `/api/process`, `/api/load_sample_events`, `/api/decisions`, `/api/audit`, `/api/ai/*`, `/api/remediations/*`, `/api/demo/mtu-two-host/*`, `/api/topology/{id}`, `/api/train`, `/api/models`, `/api/clear`.
  - `api/voice_routes.py`: `/api/voice/config`, `/api/voice/walkthrough`, `/api/voice/demo-session`, `/api/voice/me`, `/api/voice/query`, `/api/voice/confirm`, `/api/voice/conversation`, `/api/voice/conversation/clear`, `/api/voice/audit`.
- **Legacy Compatibility (`app.py`)**: Preserved Flask compatibility layer.

### 4. Frontend Console (`frontend/`)
- **Stack**: React 19, TypeScript, Vite, hash-based routing (`frontend/src/lib/routes.ts`), Lucide icons, centralized `api.ts` client.
- **Design System**: Warm Swiss Industrial palette (`#F6F5F1` paper canvas, `#FFFFFF` cards, `#E2DFD7` hairlines, `#171614` ink, semantic vermilion/ochre/olive-sage pigments, IBM Plex Sans + Space Mono, `0px` corners).
- **Screens**:
  - **Operations**: Incident Cockpit (`OverviewPage`), Two-Host MTU Demo (`DemoPage`), Voice Operations (`VoiceAssistantPage`), Incident Queue & RCA (`IncidentsPage` / `IncidentDetailPage`), Remediation Gate (`RemediationPage`).
  - **Pipeline & Records**: Telemetry Events (`EventsPage`), Triage Decisions (`DecisionsPage`), Multi-Agent Analysis (`AiAnalysisPage`), Execution & Audit Log (`AuditTrailPage`).
  - **Global Assistant**: Persistent `FloatingVoiceAssistant` drawer accessible across all operational pages with page-context awareness, browser Web Speech push-to-talk STT, `SpeechSynthesis` TTS, and inline confirmation cards.

### 5. Infrastructure Layer (`infra/`)
- Ansible playbooks (`infra/playbooks/`), roles (`infra/roles/`), `inventory.ini`, and VM provisioning (`create-vm.sh`, `provision.yml`, `site.yml`).

## Project Structure

```text
.
├── agent/                 # Host telemetry collector & systemd service
├── api/                   # FastAPI routes, auth, service facade & voice routes
├── controller/
│   ├── ai/                # LangGraph agents, Vertex Gemini LLM, RAG & memory
│   ├── remediation/       # RemediationPolicy, catalog, executors, verification
│   ├── voice/             # ConversationalOpsAgent, session memory, RBAC, security, audit
│   ├── evidence.py        # Deterministic evidence & change correlation
│   ├── processor.py       # Main event processing pipeline
│   ├── rules_engine.py    # Deterministic threshold rules
│   ├── topology.py        # Topology registry & path/intent lookup
│   └── triage_model.py    # XGBoost classifier
├── data/                  # Sample events, topology fixtures & eval datasets
├── docs/                  # Architecture, topology, Ansible & voice docs
├── frontend/              # React 19 + TypeScript Warm Swiss Industrial console
├── infra/                 # Ansible playbooks, inventory & VM provisioning
├── scripts/               # Backend & frontend startup scripts
├── tests/                 # Unit, integration, policy, AI & voice agent tests
├── main.py                # Primary FastAPI entry point
├── app.py                 # Legacy Flask compatibility entry point
├── schemas.py             # Pydantic v1/v2 request/response contracts
└── .env.example           # Environment configuration template
=======
# Network Bug Triage & Remediation Platform

## Project Overview

This platform is an automated system for detecting, correlating, and remediating network issues across a multi-VM environment. It combines network telemetry with AI/ML techniques to provide intelligent monitoring and automated remediation of network problems.

## Architecture

### 1. Agent Component (`agent/`)
- **Purpose**: Collects telemetry data from individual VMs
- **Key Features**:
  - Periodic collection of:
    - Kernel logs (dmesg tail)
    - Interface statistics (via psutil)
    - RDMA counters (from rdma-core)
    - Optional packet sampling (via eBPF)
  - Kafka integration for event publishing
  - Local file-based buffering for reliability
  - Configurable via YAML
  - Runs as a systemd service

### 2. Controller Component (`controller/`)
- **Purpose**: Central processing and decision-making unit
- **Modules**:
  - `processor.py`: Main event processing pipeline
  - `rules_engine.py`: Rule-based triage system
  - `nlp_parser.py`: Log analysis using NLP
  - `triage_model.py`: ML-based issue classification
  - `ansible_runner.py`: Remediation execution
- **Features**:
  - Kafka event consumption
  - Multi-stage triage (rules + ML)
  - Cross-VM correlation
  - Automated remediation orchestration

### 3. Infrastructure Layer (`infra/`)
- **Components**:
  - Ansible playbooks for remediation
  - VM provisioning scripts
  - Network topology setup
- **Remediation Actions**:
  - MTU mismatches
  - Driver issues
  - RDMA problems
  - Network configuration

## Technical Stack

### Core Technologies
- **Language**: Python 3.x
- **Message Queue**: Apache Kafka
- **Automation**: Ansible
- **ML/AI**:
  - XGBoost for classification
  - Sentence Transformers for log analysis
  - scikit-learn for ML pipeline

### Dependencies
- **Core Runtime**:
  - psutil
  - pyyaml
  - kafka-python
  - python-dateutil
- **ML/AI**:
  - numpy
  - pandas
  - scikit-learn
  - xgboost
  - joblib
  - sentence-transformers
- **Optional**:
  - bcc (for eBPF packet sampling)
  - pyverbs (for RDMA integration)

## Key Features

### 1. Telemetry Collection
- Network interface statistics
- Kernel log monitoring
- RDMA counter tracking
- Optional packet sampling

### 2. Intelligent Analysis
- Rule-based triage
- Machine learning classification
- Natural language processing for log analysis
- Cross-VM issue correlation

### 3. Automated Remediation
- Canary-first deployment
- Rollback capabilities
- MTU configuration fixes
- Driver restart procedures
- Forensic data collection

### 4. Reliability Features
- Local event buffering
- Kafka retry mechanisms
- Systemd service integration
- Error logging and auditing

## Project Structure

```
.
├── agent/                 # Agent component
│   ├── agent.py          # Main agent implementation
│   ├── config.yaml       # Agent configuration
│   └── service/          # Systemd service files
├── controller/           # Central control system
│   ├── processor.py     # Main event processing
│   ├── rules_engine.py  # Rule-based triage
│   ├── nlp_parser.py    # Log analysis
│   ├── triage_model.py  # ML classification
│   └── model/           # ML model training
├── infra/               # Infrastructure management
│   ├── playbooks/      # Ansible remediation playbooks
│   ├── create-vm.sh    # VM provisioning
│   └── provision.yml   # Environment setup
├── data/               # Data storage
│   ├── logs/          # System logs
│   └── metrics/       # Performance metrics
├── tests/             # Testing suite
├── docs/              # Documentation
└── requirements.txt   # Python dependencies
```

## Usage Scenarios

### 1. Normal Operation
1. Agents collect telemetry from VMs
2. Data is published to Kafka topic
3. Controller processes events
4. Issues are detected and classified
5. Automated remediation is triggered

### 2. Network Issue Detection
1. Agent detects anomalies (e.g., MTU mismatch)
2. Controller correlates across VMs
3. ML model classifies severity
4. Appropriate remediation playbook is selected
5. Canary-first deployment of fix

### 3. Offline Operation
1. Agent buffers events locally
2. Reconnects to Kafka when available
3. Cached events are processed
4. System maintains operation history

## Development and Testing

### Local Development
1. Use Docker Compose for Kafka setup
2. Create test VMs with Vagrant
3. Deploy agent in dry-run mode
4. Test remediation in isolated environment

### Testing Tools
- Fault injection scripts
- Pipeline validation
- Synthetic event generation
- Forensic data collection

## Deployment Requirements

### System Requirements
- Python 3.x environment
- Kafka cluster
- Ansible control node
- Target VMs with:
  - Python 3.x
  - systemd
  - RDMA support (optional)

### Network Requirements
- Kafka connectivity
- SSH access for Ansible
- RDMA network (optional)
- Management network

## Security Considerations

### Agent Security
- Runs as root for network access
- Configurable logging
- Local file permissions

### Controller Security
- Ansible inventory management
- Kafka authentication
- Remediation authorization

### Network Security
- Secure Kafka communication
- SSH key management
- RDMA security (if enabled)

## Monitoring and Maintenance

### Logging
- Agent logs
- Controller audit logs
- Remediation history
- Performance metrics

### Health Checks
- Agent heartbeat
- Kafka connectivity
- ML model performance
- Remediation success rate

## Future Enhancements

### Planned Features
- Enhanced ML models
- Additional remediation strategies
- Expanded telemetry collection
- Improved correlation algorithms

### Integration Options
- Additional messaging systems
- Cloud provider integration
- Extended monitoring capabilities
- Custom remediation actions
>>>>>>> ff89564813fe8c100cd1118813d53af4264c93d6
