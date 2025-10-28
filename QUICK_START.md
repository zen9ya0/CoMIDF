# CoMIDF Quick Start Guide

## Overview

CoMIDF is a Collaborative Multi-Protocol Intrusion Detection Framework for IoT and industrial environments.

## Installation

### Prerequisites

- Python 3.8+
- Linux-based OS (for packet capture)
- Root/sudo access (for libpcap)

### Step 1: Install Dependencies

```bash
cd /opt/CoMIDF
pip install -r requirements.txt
```

### Step 2: Install Cloud Platform

```bash
sudo ./scripts/install_cloud.sh
```

During installation:
1. Select management interface (UI/API/SSH)
2. Select data interface (Kafka/UER Gateway)
3. Provide IP addresses or auto-detect

### Step 3: Install Edge Agent

```bash
sudo ./scripts/install_agent.sh
```

During installation:
1. Select management interface (TLS/registration)
2. Select packet capture interface
3. Enter Cloud Platform endpoint
4. Enter Tenant ID and Agent ID

### Step 4: Start Services

**Cloud Platform:**
```bash
cd /opt/CoMIDF
python -m cloud_platform.uer_gateway.receiver
```

**Edge Agent:**
```bash
cd /opt/CoMIDF
python edge_agent/main.py
```

## Configuration Files

### Cloud Platform
- Network config: `/etc/comidf/cloud_net_config.yaml`
- Platform config: `/etc/comidf/cloud_config.yaml`

### Edge Agent
- Network config: `/etc/comidf/agent_net_config.yaml`
- Agent config: `/etc/comidf/agent_config.yaml`

## Architecture

```
┌─────────────┐     UER (gRPC/TLS)     ┌──────────────┐
│ Edge Agent  │───────────────────────→│Cloud Platform│
│             │                        │              │
│ • Protocol  │                        │ • GC         │
│   Agents    │                        │ • PR         │
│ • FAL       │                        │ • CTI        │
│ • Secure    │←────── Reports ───────│ • LLM        │
│   Connector │                        │ • AFL        │
└─────────────┘                        └──────────────┘
```

## Key Features

### Edge Agent
- **Protocol Support**: MQTT, HTTP, DNS, QUIC
- **Feature Extraction**: Flow analysis, entropy calculation
- **Secure Communication**: JWT + mTLS
- **Local Analysis**: Risk scoring before upload

### Cloud Platform
- **AI Fusion**: Bayesian + Dempster-Shafer
- **CTI Integration**: IOC matching
- **LLM Reports**: Natural language descriptions
- **Active Learning**: Adaptive thresholds

## Testing

### Test UER Creation

```python
from shared.models.uer_schema import UnifiedEventReport
from datetime import datetime

uer = UnifiedEventReport(
    event_id="test-001",
    agent_id="agent-001",
    tenant_id="tenant-abc",
    timestamp=datetime.now(),
    source_ip="192.168.1.100",
    destination_ip="10.0.0.5",
    source_port=12345,
    destination_port=1883,
    protocol_info=...,
    flow_features=...,
    protocol_features=...,
    edge_agent_risk_score=0.8,
    edge_agent_anomaly_flags=["high_entropy"]
)
```

### Test Cloud Processing

```python
from cloud_platform.gc.global_credibility import GlobalCredibility

gc = GlobalCredibility(config={})
result = await gc.process_uer(uer)
print(f"Credibility: {result['global_credibility']}")
```

## Troubleshooting

### Edge Agent Issues

**Problem**: Cannot capture packets
- **Solution**: Ensure running as root, check interface permissions

**Problem**: Cannot connect to Cloud Platform
- **Solution**: Verify network config, check firewall rules

### Cloud Platform Issues

**Problem**: UER Gateway not receiving data
- **Solution**: Check port 9092, verify firewall, check logs

**Problem**: High CPU usage
- **Solution**: Adjust packet buffer size in config

## Logs

- Edge Agent: `/var/log/comidf/edge_agent.log`
- UER Gateway: `/var/log/comidf/uer_gateway.log`
- GC: `/var/log/comidf/global_credibility.log`
- CTI: `/var/log/comidf/cti.log`
- LLM: `/var/log/comidf/llm_engine.log`

## Next Steps

1. Implement additional protocol agents (CoAP, Modbus, Zigbee, gRPC, NetFlow)
2. Add database persistence (PostgreSQL)
3. Integrate real CTI feeds (OpenCTI, MISP, OTX)
4. Connect LLM API (OpenAI, local models)
5. Build management UI (React)
6. Add monitoring (Prometheus/Grafana)

## Documentation

- Full specification: `# CoMIDF 全產品開發規格指南（Product Development S.ini`
- Project summary: `PROJECT_SUMMARY.md`
- Main README: `README.md`

## Support

For issues and questions, refer to the development specification guide.

