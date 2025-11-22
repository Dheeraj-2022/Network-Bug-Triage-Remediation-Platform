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