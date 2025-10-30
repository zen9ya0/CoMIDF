# CoMIDF 快速参考卡片

## 🚀 快速部署（5分钟）

```bash
# 1. 安装依赖
./install.sh

# 2. 配置
nano edge-agent/agent.yaml
nano cloud-platform/.env

# 3. 一键部署
./deploy.sh

# 4. 验证
curl http://localhost:8600/health
curl http://localhost:8080/health
```

## 📋 系统要求

### Edge Agent
- 2 vCPU, 4GB RAM, 10GB Disk
- Ubuntu 20.04+, CentOS 7+, Debian 10+

### Cloud Platform
- 4 vCPU, 8GB RAM, 50GB Disk
- Docker 20.10+, Docker Compose 1.29+

## 📦 安装步骤

### Ubuntu/Debian

```bash
sudo apt update
sudo apt install -y python3.11 docker.io docker-compose git
```

### CentOS/RHEL

```bash
sudo yum install -y python3 docker docker-compose git
sudo systemctl start docker
```

## 🔧 配置清单

### 1. Edge Agent (`agent.yaml`)

```yaml
agent:
  id: "edge-ap01"
  tenant_id: "YOUR-TENANT"
  site: "your-site"

uplink:
  mssp_url: "https://your-cloud.com"
  token: "YOUR-TOKEN"
```

### 2. Cloud Platform (`.env`)

```bash
POSTGRES_PASSWORD=secure-password
KAFKA_BROKERS=kafka:9092
LOG_LEVEL=INFO
```

## 🧪 测试命令

### 健康检查

```bash
# Edge Agent
curl http://localhost:8600/health | jq

# Cloud Platform
curl http://localhost:8080/health | jq

# Metrics
curl http://localhost:8600/metrics
```

### 发送测试数据

```bash
curl -X POST http://localhost:8080/api/fal/uer \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: TEST" \
  -H "X-Agent-ID: test" \
  -d '{
    "ts": "2025-01-01T00:00:00Z",
    "src": {"ip": "192.168.1.1"},
    "dst": {"ip": "10.0.0.100", "port": 1883},
    "proto": {"l7": "MQTT"},
    "detector": {"score": 0.75, "conf": 0.85, "model": "mqtt-v1"}
  }'
```

## 📊 监控命令

### 查看日志

```bash
# Edge Agent
docker logs comidf-edge -f

# Cloud Platform
docker-compose -f cloud-platform/docker-compose.yml logs -f

# 所有服务
docker ps
```

### 查看状态

```bash
# 服务状态
docker ps --filter "name=comidf"

# 端口占用
lsof -i :8080
lsof -i :8600

# 资源使用
docker stats
```

## 🔍 故障排除

### Edge Agent 无法连接

```bash
# 1. 检查网络
curl -v https://your-cloud.com/health

# 2. 检查 Token
grep token edge-agent/agent.yaml

# 3. 查看日志
docker logs comidf-edge
```

### Cloud Platform 无响应

```bash
# 1. 检查服务
docker-compose -f cloud-platform/docker-compose.yml ps

# 2. 重启服务
docker-compose -f cloud-platform/docker-compose.yml restart

# 3. 查看日志
docker-compose -f cloud-platform/docker-compose.yml logs
```

### 磁盘空间不足

```bash
# 1. 检查空间
df -h

# 2. 清理旧数据
docker system prune

# 3. 增加 buffer
nano edge-agent/agent.yaml  # 修改 max_mb: 4096
```

## 🛑 停止服务

```bash
# 停止 Edge Agent
docker stop comidf-edge

# 停止 Cloud Platform
docker-compose -f cloud-platform/docker-compose.yml down

# 完全清理
docker rm comidf-edge
docker-compose -f cloud-platform/docker-compose.yml down -v
```

## 📚 重要文件

| 文件 | 说明 |
|------|------|
| `DEPLOYMENT.md` | 详细部署指南 |
| `USAGE.md` | 使用手册 |
| `TEST_SETUP.md` | 测试指南 |
| `edge-agent/agent.yaml` | Edge 配置 |
| `cloud-platform/.env` | Cloud 配置 |

## 🎯 常用端口

| 服务 | 端口 | 说明 |
|------|------|------|
| Edge Agent | 8600 | Local API |
| Cloud Ingress | 8080 | API Gateway |
| Kafka | 9092 | Message Queue |
| Redis | 6379 | Cache |
| PostgreSQL | 5432 | Database |

## 🚨 快速诊断

```bash
# 检查所有服务
./deploy.sh && curl http://localhost:8600/health && curl http://localhost:8080/health

# 重启所有服务
docker stop comidf-edge && docker-compose -f cloud-platform/docker-compose.yml restart && docker start comidf-edge

# 查看所有日志
docker logs comidf-edge -f & docker-compose -f cloud-platform/docker-compose.yml logs -f
```

---

**提示**: 保存此卡片供快速参考！

