# CoMIDF 快速部署指南

## 📋 目录

1. [系统要求](#系统要求)
2. [快速开始 (Docker)](#快速开始-docker)
3. [手动部署](#手动部署)
4. [配置说明](#配置说明)
5. [验证部署](#验证部署)
6. [故障排除](#故障排除)

---

## 系统要求

### 最低配置

#### Edge Agent
- **CPU**: 2 vCPU
- **RAM**: 4GB
- **Disk**: 10GB
- **OS**: Ubuntu 20.04+, CentOS 7+, Debian 10+
- **Network**: 稳定的网络连接

#### Cloud Platform
- **CPU**: 4 vCPU (推荐 8+)
- **RAM**: 8GB (推荐 16GB+)
- **Disk**: 50GB+ (取决于数据保留)
- **OS**: Ubuntu 20.04+, Kubernetes 1.20+
- **Network**: 公网IP或负载均衡器

### 软件依赖

#### 必须
- Python 3.11+ (或 3.9+)
- Docker 20.10+
- Docker Compose 1.29+

#### 可选
- Kubernetes 1.20+ (生产环境)
- Kafka 2.8+ (如需独立 Kafka)
- PostgreSQL 13+ (如需独立数据库)
- Prometheus + Grafana (监控)

---

## 快速开始 (Docker)

### 一键部署

```bash
# 1. 克隆或下载项目
cd /opt
git clone <your-repo> CoMIDF
cd CoMIDF

# 2. 配置 Edge Agent
cp edge-agent/agent.yaml edge-agent/agent-production.yaml
# 编辑 agent-production.yaml 设置 tenant_id, token, mssp_url

# 3. 配置 Cloud Platform
cp cloud-platform/cloud_platform.yaml cloud-platform/cloud-production.yaml
# 编辑 cloud-production.yaml 设置数据库、Kafka 配置

# 4. 启动所有服务
docker-compose -f cloud-platform/docker-compose.yml up -d

# 5. 构建并启动 Edge Agent
cd edge-agent
docker build -t comidf-edge:latest .
docker run -d \
  --name edge-agent \
  -v $(pwd)/agent-production.yaml:/etc/agent/agent.yaml \
  -p 8600:8600 \
  comidf-edge:latest
```

### 验证部署

```bash
# 检查 Edge Agent
curl http://localhost:8600/health

# 检查 Cloud Platform
curl http://localhost:8080/health

# 查看日志
docker logs edge-agent
docker-compose -f cloud-platform/docker-compose.yml logs
```

---

## 手动部署

### 步骤 1: 安装系统依赖

#### Ubuntu/Debian

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装 Python 和依赖
sudo apt install -y python3.11 python3.11-venv python3-pip git curl

# 安装 Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# 安装 Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 重新登录以使 Docker 组生效
newgrp docker
```

#### CentOS/RHEL

```bash
# 更新系统
sudo yum update -y

# 安装依赖
sudo yum install -y python39 python3-pip git curl

# 安装 Docker
sudo yum install -y yum-utils
sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo yum install -y docker-ce docker-ce-cli containerd.io
sudo systemctl start docker
sudo systemctl enable docker

# 安装 Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 步骤 2: 部署 Cloud Platform

```bash
cd /opt/CoMIDF/cloud-platform

# 安装 Python 依赖
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 配置环境变量
cat > .env << EOF
# Database
POSTGRES_PASSWORD=comidf_pass_$(openssl rand -hex 8)

# Kafka
KAFKA_BROKERS=localhost:9092

# Redis
REDIS_PASSWORD=$(openssl rand -hex 16)

# Ingress
INGRESS_HOST=0.0.0.0
INGRESS_PORT=8080

# Logging
LOG_LEVEL=INFO
EOF

# 使用 Docker Compose 启动
docker-compose up -d

# 检查服务状态
docker-compose ps
docker-compose logs -f ingress
```

### 步骤 3: 部署 Edge Agent

```bash
cd /opt/CoMIDF/edge-agent

# 安装依赖
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 创建配置目录
sudo mkdir -p /etc/comidf/agent
sudo mkdir -p /var/lib/comidf/agent

# 复制配置文件
sudo cp agent.yaml /etc/comidf/agent/agent-production.yaml

# 编辑配置
sudo nano /etc/comidf/agent/agent-production.yaml
```

**关键配置**：
```yaml
agent:
  id: "edge-ap01"
  tenant_id: "YOUR-TENANT-ID"  # 从云平台获取
  site: "your-site-name"

uplink:
  mssp_url: "https://your-cloud.example.com"  # Cloud Platform URL
  token: "YOUR-API-TOKEN"  # 从云平台获取
```

### 步骤 4: 配置 Systemd 服务

```bash
sudo tee /etc/systemd/system/comidf-edge.service > /dev/null << 'EOF'
[Unit]
Description=CoMIDF Edge Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=comidf
WorkingDirectory=/opt/CoMIDF/edge-agent
Environment="PYTHONPATH=/opt/CoMIDF/edge-agent"
ExecStart=/opt/CoMIDF/edge-agent/venv/bin/python \
  cmd/agentd/main.py \
  --config /etc/comidf/agent/agent-production.yaml
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 创建用户
sudo useradd -r -s /bin/false comidf
sudo chown -R comidf:comidf /opt/CoMIDF
sudo chown -R comidf:comidf /var/lib/comidf

# 启动服务
sudo systemctl daemon-reload
sudo systemctl enable comidf-edge
sudo systemctl start comidf-edge
sudo systemctl status comidf-edge
```

---

## 配置说明

### Cloud Platform 配置

编辑 `cloud-platform/cloud_platform.yaml`:

```yaml
ingress:
  port: 8080
  mtsl: true
  rate_limit:
    per_agent: 3000
    burst: 5000

kafka:
  brokers: ["kafka:9092"]
  topics:
    ingest: "uer.ingest"
    deadletter: "uer.deadletter"
    posterior: "gc.posterior"
    feedback: "afl.feedback"

database:
  postgres:
    host: "postgres"
    port: 5432
    database: "comidf"
```

### Edge Agent 配置

编辑 `edge-agent/agent.yaml`:

```yaml
agent:
  id: "edge-ap01"
  tenant_id: "TENANT-12345"
  site: "hq-beijing"

uplink:
  mssp_url: "https://cloud.example.com"
  fal_endpoint: "/api/fal/uer"
  token: "<API_TOKEN>"
  tls:
    mtls: true
    ca_cert: "/etc/comidf/ca.pem"
    cert: "/etc/comidf/agent.pem"
    key: "/etc/comidf/agent.key"
  retry:
    backoff_ms: [200, 500, 1000, 2000]
    max_retries: 8

buffer:
  backend: "sqlite"
  path: "/var/lib/comidf/agent/buffer.db"
  max_mb: 2048
  flush_batch: 500

agents:
  http:
    enabled: true
    pcap: "/dev/net/tap0"
    thresholds:
      score_alert: 0.7
  mqtt:
    enabled: true
    source: "tcp://127.0.0.1:1883"
    thresholds:
      score_alert: 0.65
```

---

## 验证部署

### 1. 健康检查

```bash
# Edge Agent
curl http://localhost:8600/health | jq
# 应该返回: {"status": "ok", "uptime_sec": ...}

# Cloud Platform
curl http://localhost:8080/health | jq
# 应该返回: {"status": "ok", "timestamp": ...}
```

### 2. Metrics 检查

```bash
# Edge Agent metrics
curl http://localhost:8600/metrics

# 应该看到:
# agent_buffer_pending
# agent_uplink_success_total
```

### 3. 发送测试 UER

```bash
curl -X POST http://localhost:8080/api/fal/uer \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: TEST" \
  -H "X-Agent-ID: test-agent" \
  -d '{
    "uid": "test-001",
    "ts": "2025-01-01T00:00:00Z",
    "src": {"ip": "192.168.1.1"},
    "dst": {"ip": "10.0.0.100", "port": 1883},
    "proto": {"l7": "MQTT"},
    "stats": {"len_mean": 150},
    "detector": {"score": 0.75, "conf": 0.85, "model": "mqtt-v1"}
  }'

# 检查是否接收
curl http://localhost:8080/stats | jq
```

### 4. 查看日志

```bash
# Edge Agent
docker logs edge-agent
# 或
journalctl -u comidf-edge -f

# Cloud Platform
docker-compose -f cloud-platform/docker-compose.yml logs -f ingress

# Kafka
docker-compose -f cloud-platform/docker-compose.yml logs -f kafka
```

---

## 故障排除

### 问题 1: Edge Agent 无法连接 Cloud

**症状**: 不断重试连接

**检查**:
```bash
# 1. 检查网络连接
curl -v https://your-cloud.example.com/health

# 2. 检查 Token
grep token /etc/comidf/agent/agent-production.yaml

# 3. 检查证书
ls -la /etc/comidf/*.pem

# 4. 查看详细日志
docker logs edge-agent -f
```

**解决**:
```bash
# 更新 Token
# 从云平台获取新的 API Token
# 编辑配置文件
sudo nano /etc/comidf/agent/agent-production.yaml

# 重启服务
sudo systemctl restart comidf-edge
```

### 问题 2: Cloud Platform 返回 503

**症状**: `/health` 返回 503

**检查**:
```bash
# 检查所有服务
docker-compose -f cloud-platform/docker-compose.yml ps

# 检查 Kafka
docker-compose -f cloud-platform/docker-compose.yml logs kafka

# 检查 PostgreSQL
docker-compose -f cloud-platform/docker-compose.yml logs postgres
```

**解决**:
```bash
# 重启服务
docker-compose -f cloud-platform/docker-compose.yml restart

# 重建容器
docker-compose -f cloud-platform/docker-compose.yml up -d --force-recreate
```

### 问题 3: 磁盘空间不足

**症状**: Buffer 队列满

**检查**:
```bash
df -h
du -sh /var/lib/comidf/agent/*
```

**解决**:
```bash
# 增加 buffer 大小 (编辑配置)
max_mb: 4096  # 从 2048 增加到 4096

# 或清理旧数据
python -c "
import sqlite3
conn = sqlite3.connect('/var/lib/comidf/agent/buffer.db')
cur = conn.cursor()
# 删除 7 天前的数据
cur.execute('DELETE FROM queue WHERE created_at < datetime(\"now\", \"-7 days\")')
conn.commit()
"

# 重启服务
sudo systemctl restart comidf-edge
```

---

## 生产环境建议

### 1. 使用 Kubernetes

```bash
# 部署 Helm Chart
helm install comidf ./charts/comidf \
  --set ingress.host=cloud.example.com \
  --set database.password=secure-password

# 查看状态
kubectl get pods -n comidf
kubectl logs -f -l app=edge-agent -n comidf
```

### 2. 配置 SSL/TLS

```bash
# 使用 Let's Encrypt
certbot certonly --standalone -d cloud.example.com

# 配置 Ingress
# 在 docker-compose.yml 或 Kubernetes 中启用 TLS
```

### 3. 监控与告警

```bash
# 部署 Prometheus + Grafana
docker-compose -f monitoring/docker-compose.yml up -d

# 配置告警规则
# 在 Prometheus 中配置 alerts
```

### 4. 备份策略

```bash
# 备份数据库 (每天)
0 2 * * * pg_dump -h localhost comidf > /backup/comidf-$(date +\%Y\%m\%d).sql

# 备份 Kafka (每 3 小时)
0 */3 * * * kafka-console-consumer --bootstrap-server localhost:9092 --topic uer.ingest --from-beginning > /backup/uers-$(date +\%Y\%m\%d-%H).jsonl
```

---

## 快速部署脚本

我建议创建一个自动化部署脚本：

```bash
#!/bin/bash
# quick_deploy.sh

set -e

echo "╔════════════════════════════════════════╗"
echo "║   CoMIDF 快速部署脚本                   ║"
echo "╚════════════════════════════════════════╝"

# 1. 检查依赖
echo "→ 检查依赖..."
command -v docker >/dev/null 2>&1 || { echo "需要安装 Docker"; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo "需要安装 Docker Compose"; exit 1; }

# 2. 启动 Cloud Platform
echo "→ 启动 Cloud Platform..."
cd cloud-platform
docker-compose up -d

# 3. 构建 Edge Agent
echo "→ 构建 Edge Agent..."
cd ../edge-agent
docker build -t comidf-edge:latest .

# 4. 启动 Edge Agent
echo "→ 启动 Edge Agent..."
docker run -d \
  --name comidf-edge \
  -v $(pwd)/agent.yaml:/etc/agent/agent.yaml \
  -p 8600:8600 \
  comidf-edge:latest

# 5. 验证
echo "→ 验证部署..."
sleep 5
curl http://localhost:8600/health && echo "✓ Edge Agent 运行中"
curl http://localhost:8080/health && echo "✓ Cloud Platform 运行中"

echo "✓ 部署完成！"
```

---

## 更多资源

- [使用指南](./USAGE.md)
- [测试指南](./TEST_SETUP.md)
- [架构文档](./collaborative_ids_framework.md)

---

**下一步**: 部署完成后，请运行完整测试验证系统功能。

