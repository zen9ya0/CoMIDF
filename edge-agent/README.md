# CoMIDF Edge Agent

Edge Agent implementation for CoMIDF collaborative intrusion detection framework.

## Architecture

```
Packets → Protocol Agents (HTTP/MQTT/CoAP) → FAL → Connector → Cloud MSSP
                                                    ↓
                                                  Buffer (SQLite)
```

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Run agent
python cmd/agentd/main.py --config agent.yaml
```

## Docker

```bash
# Build
docker build -t comidf-edge-agent .

# Run
docker run -d \
  -v $(pwd)/agent.yaml:/etc/agent/agent.yaml \
  -p 8600:8600 \
  comidf-edge-agent
```

## Configuration

Edit `agent.yaml`:

```yaml
agent:
  id: "edge-ap01"
  tenant_id: "TENANT-12345"
  site: "hq-taipei"

uplink:
  mssp_url: "https://mssp.example.com"
  token: "<API_TOKEN>"

agents:
  mqtt:
    enabled: true
  http:
    enabled: true
```

## Local API

- `GET /health` - Health check
- `GET /metrics` - Prometheus metrics
- `GET /config` - Agent configuration
- `POST /feedback` - Apply AFL policy

## Usage

```bash
# Check status
./bin/agentctl status

# View metrics
./bin/agentctl metrics

# Apply feedback
./bin/agentctl feedback policy.json
```

## Protocol Agents

- **HTTP Agent**: Monitors HTTP/TLS traffic
- **MQTT Agent**: Monitors MQTT pub/sub
- **CoAP Agent**: Monitors CoAP IoT traffic

## Security

- mTLS for uplink
- JWT Bearer tokens
- SHA-256 anonymization of device IDs
- No payload data transmitted

