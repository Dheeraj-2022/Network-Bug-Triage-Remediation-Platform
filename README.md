# Network Bug Triage & Remediation Platform

## 📌 Overview
This platform automates **detection, correlation, and remediation** of network issues across a multi-VM environment.  
It integrates **network telemetry (kernel logs, NIC stats, RDMA counters)** with **AI/ML (XGBoost, NLP log parsing)** to:
- Detect kernel, driver, and RDMA errors
- Correlate across a multi-VM topology
- Apply safe remediation (MTU fixes, driver restarts, config rollbacks) via **Ansible**

## 🏗️ Architecture
- **Agent (per VM)**: Collects telemetry → pushes JSON events to Kafka  
- **Controller**: Consumes events → applies rule-based + ML triage → triggers remediation playbooks  
- **Infra**: Multi-VM setup with Vagrant/libvirt + Soft-RoCE for RDMA  
- **ML/NLP**: XGBoost classifier + transformer-based log embeddings

=======
## 🏗️ System Architecture

![Network Bug Triage & Remediation Platform Architecture](docs/network_bug_architecture.png)

## 🤖 AI Multi-Agent Layer

On top of the deterministic stack (rules + XGBoost + NLP + Ansible) the platform
runs a **multi-agent, LLM-powered reasoning pipeline** built around Google
Vertex AI Gemini, a hybrid retrieval pipeline, a knowledge base and persistent
memory. The XGBoost classifier remains the **fast first-pass classifier**; the
LLM performs the deeper reasoning (root-cause analysis, explanation, remediation
planning and risk analysis).

```
Telemetry Agent → Kafka → Orchestrator (ADK/LangGraph-style)
   → Planner Agent → Telemetry Analysis Agent → Retriever Agent
   → Vector DB + Knowledge Base → Vertex AI Gemini
   → Root Cause Analysis Agent → Remediation Planner
   → Human Approval → Ansible Execution → Validation Agent → Dashboard
```

### Agents (`controller/ai/agents.py`)
| Agent | Responsibility |
|-------|----------------|
| Planner | Decides analysis depth based on ML priority + rule signals |
| Telemetry Analysis | Extracts structured signals (counters, MTU anomalies) |
| Retriever | Hybrid vector + keyword + incident-history retrieval |
| Knowledge Base | Selects the authoritative runbook |
| Root Cause Analysis | Gemini-grounded RCA over retrieved context |
| Remediation | Gemini remediation planning + risk analysis (guardrailed to real playbooks) |
| Validation | Post-remediation before/after validation |
| Audit | Persists incident + remediation to memory |

### Key properties
- **Graceful degradation** — with no cloud/optional deps installed, the layer
  runs a deterministic offline reasoner + numpy cosine retrieval, so the whole
  platform still works air-gapped. Install the extras in `requirements.txt`
  (Vertex AI, LangChain/LangGraph, ADK, Chroma) to enable full LLM reasoning.
- **Non-invasive** — the legacy rule/ML/Ansible path is untouched; the AI layer
  augments the decision and is fully optional (toggle via `NBT_AI_ENABLED`).
- **Human approval** — AI-generated remediations are held `pending_approval`
  and executed only after approval via the dashboard/API.
- **Hybrid retrieval** — vector search + keyword search + incident history over
  runbooks, RDMA docs, kernel-log patterns and past remediation records.
- **Memory** — conversation, incident, host-history, remediation-history and
  failure-pattern memory persisted under `controller/ai/store/`.

### Configuration
AI settings live in `controller/ai/ai_config.yaml` and are overridable via
environment variables:

| Variable | Purpose |
|----------|---------|
| `NBT_AI_ENABLED` | Master on/off for the AI layer |
| `NBT_AI_REQUIRE_APPROVAL` | Require human approval before remediation |
| `GOOGLE_CLOUD_PROJECT` / `NBT_VERTEX_PROJECT` | Enables Vertex AI Gemini |
| `NBT_VERTEX_LOCATION`, `NBT_VERTEX_MODEL` | Vertex region / model |
| `GOOGLE_APPLICATION_CREDENTIALS` | Service-account JSON for Vertex |

### API endpoints (Flask)
| Endpoint | Description |
|----------|-------------|
| `GET /api/ai/status` | LLM backend, retrieval, memory & metrics |
| `GET /api/ai/incidents` | Recent multi-agent incidents (RCA + plans) |
| `GET /api/ai/incident/<id>` | Full agent trace for one incident |
| `POST /api/ai/approve` | Approve/reject a pending remediation |

### Evaluation
A reproducible harness measures fault-localization and fault-domain accuracy:

```bash
python -m controller.ai.evaluation --dataset data/eval_labeled.json
```

## ▶️ Running
```bash
pip install -r requirements.txt
python app.py          # dashboard at http://127.0.0.1:5000
# or the pipeline consumer:
python controller/processor.py --dry-run
```
