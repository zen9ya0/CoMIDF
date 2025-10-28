# CoMIDF 安装指南

## 📋 目录

1. [系统要求](#系统要求)
2. [快速开始](#快速开始)
3. [详细安装步骤](#详细安装步骤)
4. [配置说明](#配置说明)
5. [验证安装](#验证安装)

---

## 系统要求

### 最低配置

#### Cloud Platform
- **CPU**: 4 vCPU
- **RAM**: 8GB
- **Disk**: 50GB
- **OS**: Ubuntu 20.04+, CentOS 7+, Debian 10+
- **软件**: Docker 20.10+, Docker Compose 1.29+

#### Edge Agent
- **CPU**: 2 vCPU
- **RAM**: 4GB
- **Disk**: 10GB
- **网络**: 可访问 Cloud Platform (HTTPS 443)

---

## 快速开始

### 一键安装（推荐）

```bash
# 1. 克隆项目
git clone <repo-url> CoMIDF
cd CoMIDF

# 2. 安装依赖
./install.sh

# 3. 配置
# 编辑 cloud-platform/.env
# 编辑 edge-agent/agent_production.yaml

# 4. 部署
./deploy.sh

# 5. 验证
curl https://your-cloud.com/health
```

---

## 详细安装步骤

### 步骤 1: 安装系统依赖

#### Ubuntu/Debian

```bash
sudo apt update
sudo apt install -y python3.11 docker.io docker-compose git curl jq
```

#### CentOS/RHEL

```bash
sudo yum install -y python3 docker docker-compose git curl jq
sudo systemctl start docker
sudo systemctl enable docker
```

#### 验证安装

```bash
docker --version      # 应该显示 Docker 20.10+
docker-compose --version  # 应该显示 1.29+
python3 --version     # 应该显示 Python 3.9+
```

### 步骤 2: 克隆项目

```bash
git clone <your-repo-url> CoMIDF
cd CoMIDF
```

### 步骤 3: 设置 SSL 证书 (Cloud Platform)

```bash
cd nginx
chmod +x setup_ssl.sh
./setup_ssl.sh
```

选择证书类型：
- **[1]** Let's Encrypt (生产环境推荐)
- **[2]** 自签名证书 (测试环境)
- **[3]** 使用现有证书

### 步骤 4: 配置 Cloud Platform

```bash
cd ../cloud-platform

# 创建环境变量文件
cat > .env << EOF
# Database
POSTGRES_PASSWORD=$(openssl rand -base64 32)

# Kafka
KAFKA_BROKERS=kafka:9092

# Redis
REDIS_PASSWORD=$(openssl rand -base64 32)

# Ingress
INGRESS_HOST=0.0.0.0
INGRESS_PORT=8080

# Logging
LOG_LEVEL=INFO
EOF
```

### 步骤 5: 启动 Cloud Platform

```bash
# 开发环境 (推荐先测试)
docker-compose up -d

# 或生产环境
docker-compose -f docker-compose.prod.yml up -d

# 查看日志
docker-compose logs -f
```

**验证 Cloud Platform**:
```bash
curl http://localhost:8080/health
# 或 HTTPS
curl https://your-cloud.com/health
```

### 步骤 6: 配置 Edge Agent

```bash
cd ../edge-agent

# 复制生产配置
cp agent_production.yaml agent.yaml

# 编辑配置
nano agent.yaml
```

**关键配置**:
```yaml
agent:
  id: "edge-ap01"                    # 唯一标识
  tenant_id: "YOUR-TENANT-ID"         # 从 Cloud 获取
  site: "hq-beijing"                  # 站点名称

uplink:
  mssp_url: "https://your-cloud.com"  # Cloud URL (HTTPS!)
  fal_endpoint: "/api/fal/uer"
  token: "YOUR-API-TOKEN"             # 从 Cloud 生成
  tls:
    mtls: false  # 通过 Nginx，不需要 mTLS
    verify: true  # 验证 SSL 证书
```

### 步骤 7: 安装 Edge Agent

#### 方式 1: Docker (推荐)

```bash
cd edge-agent

# 构建镜像
docker build -t comidf-edge:latest .

# 运行容器
docker run -d \
  --name comidf-edge \
  --restart unless-stopped \
  -v $(pwd)/agent.yaml:/etc/agent/agent.yaml \
  -p 8600:8600 \
  comidf-edge:latest
```

#### 方式 2: 使用密钥自动安装

```bash
# 1. 从 Cloud Platform 生成凭证
cd ../cloud-platform/bin
./create_agent_key.sh

# 2. 下载凭证到 Edge Agent
scp /tmp/comidf_credentials.json user@edge-host:/tmp/

# 3. 在 Edge Agent 上安装
ssh edge-host
cd /opt/CoMIDF/edge-agent
./bin/install_with_key.sh /tmp/comidf_credentials.json
```

#### 方式 3: Systemd 服务

```bash
# 1. 安装 Python 依赖
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. 创建 systemd 服务
sudo tee /etc/systemd/system/comidf-edge.service > /dev/null << EOF
[Unit]
Description=CoMIDF Edge Agent
After=network-online.target

[Service]
Type=simple
ExecStart=$(pwd)/venv/bin/python cmd/agentd/main.py --config agent.yaml
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# 3. 启动服务
sudo systemctl enable comidf-edge
sudo systemctl start comidf-edge
```

### 步骤 8: 验证 Edge Agent

```bash
# 健康检查
curl http://localhost:8600/health

# 查看日志
docker logs comidf-edge
# 或
journalctl -u comidf-edge -f
```

---

## 配置说明

### Cloud Platform 配置

#### 环境变量 (.env)

```bash
# Database
POSTGRES_PASSWORD=secure_password_here
POSTGRES_USER=comidf
POSTGRES_DB=comidf

# Kafka
KAFKA_BROKERS=kafka:9092

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=secure_redis_password

# Ingress
INGRESS_HOST=0.0.0.0
INGRESS_PORT=8080

# Logging
LOG_LEVEL=INFO
```

#### Nginx 配置

编辑 `nginx/nginx.conf`:
- 修改 `server_name` 为您的域名
- 确保证书路径正确

### Edge Agent 配置

#### agent.yaml

```yaml
agent:
  id: "edge-ap01"              # 唯一标识
  tenant_id: "TENANT-12345"    # 租户 ID
  site: "hq-beijing"           # 站点名

uplink:
  mssp_url: "https://cloud.example.com"  # HTTPS URL
  fal_endpoint: "/api/fal/uer"
  token: "your-api-token"
  tls:
    mtls: false  # 不需要 mTLS
    verify: true  # 验证 SSL

agents:
  http:
    enabled: true
    thresholds:
      score_alert: 0.7
  mqtt:
    enabled: true
    thresholds:
      score_alert: 0.65
```

---

## 验证安装

### 1. 健康检查

```bash
# Cloud Platform
curl https://your-cloud.com/health
# 应该返回: {"status": "ok"}

# Edge Agent
curl http://localhost:8600/health
# 应该返回: {"status": "ok", "uptime_sec": ...}
```

### 2. 发送测试 UER

```bash
curl -X POST https://your-cloud.com/api/fal/uer \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: TEST" \
  -H "X-Agent-ID: test-agent" \
  -d '{
    "ts": "2025-01-01T00:00:00Z",
    "src": {"ip": "192.168.1.1"},
    "dst": {"ip": "10.0.0.100", "port": 1883},
    "proto": {"l7": "MQTT"},
    "stats": {"len_mean": 150},
    "detector": {"score": 0.75, "conf": 0.85, "model": "mqtt-v1"}
  }'
```

### 3. 查看统计

```bash
# Cloud Platform
curl https://your-cloud.com/api/v1/stats

# Edge Agent
curl http://localhost:8600/metrics
```

---

## 故障排除

### 问题 1: Edge Agent 无法连接 Cloud

**症状**: 返回 Connection Refused

**检查**:
```bash
# 检查 Cloud 是否运行
curl https://your-cloud.com/health

# 检查 DNS
nslookup your-cloud.com

# 检查网络
ping your-cloud.com
```

**解决**:
```bash
# 确认 URL 和端口
grep mssp_url edge-agent/agent.yaml

# 测试连接
curl -v https://your-cloud.com/api/fal/uer
```

### 问题 2: SSL 证书错误

**症状**: SSL certificate verification failed

**检查**:
```bash
# 查看证书
openssl s_client -connect your-cloud.com:443

# 检查证书有效期
certbot certificates
```

**解决**:
```bash
# 更新证书
certbot renew
docker restart comidf-nginx
```

### 问题 3: 401 Unauthorized

**症状**: 返回 401

**检查**:
```bash
# 验证 Token
grep token edge-agent/agent.yaml

# 检查 Headers
curl -v https://your-cloud.com/api/fal/uer \
  -H "X-Tenant-ID: YOUR-TENANT"
```

**解决**:
```bash
# 重新生成凭证
./cloud-platform/bin/create_agent_key.sh

# 更新配置
nano edge-agent/agent.yaml
```

---

## 生产环境部署

### 推荐架构

```
Load Balancer (443)
    ↓
Nginx (SSL Termination)
    ↓
[Ingress → Kafka → GC → PR → AFL]
    ↓
Database + Cache + Storage
```

### 高可用配置

```bash
# 使用 docker-compose.prod.yml
cd cloud-platform
docker-compose -f docker-compose.prod.yml up -d

# 启用负载均衡
# 部署多个 Ingress 实例
# 使用 Nginx upstream 配置
```

---

## 下一步

安装完成后：

1. **配置监控**: 设置 Prometheus + Grafana
2. **设置告警**: 配置告警规则
3. **优化性能**: 根据流量调整配置
4. **文档阅读**: 查看 USAGE.md 和 README.md

---

**需要帮助?**
- 文档: README.md
- 快速参考: QUICK_REFERENCE.md
- 使用指南: USAGE.md


