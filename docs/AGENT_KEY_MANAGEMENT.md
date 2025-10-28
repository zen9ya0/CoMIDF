# Edge Agent 密钥管理系统

## 概述

CoMIDF 提供了完整的 Edge Agent 密钥管理机制，允许从 Cloud Platform 生成专属的 Edge Agent 凭证，实现安全的设备认证和通信。

## 架构

```
┌─────────────────────────────────────────┐
│     Cloud Platform (Key Manager)        │
│  ┌──────────────────────────────────┐   │
│  │  /api/v1/agents/register        │   │  <- 生成新凭证
│  │  /api/v1/agents/<id>/credentials │   │  <- 获取凭证
│  │  /api/v1/agents/<id>/rotate      │   │  <- 轮换密钥
│  └──────────────────────────────────┘   │
└─────────────────────────────────────────┘
                    ↓
        生成凭证包 (JSON)
    ┌───────────────────────┐
    │ - agent_id            │
    │ - tenant_id           │
    │ - api_token           │
    │ - mTLS certs (可选)    │
    │ - config_template     │
    └───────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│     Edge Agent 安装                      │
│  ┌──────────────────────────────────┐   │
│  │ ./bin/install_with_key.sh        │   │
│  │ └─ 解析凭证                       │   │
│  │ └─ 生成配置文件                   │   │
│  │ └─ 安装证书                       │   │
│  │ └─ 启动服务                       │   │
│  └──────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

## 密钥组成

### 1. API Token

- **用途**: 身份验证和授权
- **格式**: 64 字节 URL-safe Base64 字符串
- **存储**: 
  - Cloud: SHA-256 哈希存储
  - Edge: 明文存储在配置文件（受文件权限保护）
- **轮换**: 支持密钥轮换，旧密钥失效

### 2. mTLS 证书 (可选)

- **用途**: 双向 TLS 认证
- **类型**: 客户端证书
- **包含**:
  - 客户端证书 (agent.pem)
  - 私钥 (agent.key)
  - CA 证书 (ca.pem)

### 3. Agent ID

- **格式**: `{tenant_id}-{site}-{random}`
- **示例**: `TENANT-12345-beijing-a1b2c3d4`
- **唯一性**: 全局唯一

### 4. 配置模板

自动生成的 `agent.yaml` 模板，包含：
- Tenant 和 Site 信息
- API Token
- mTLS 配置
- 默认阈值和设置

## 使用流程

### 步骤 1: 从 Cloud Platform 生成凭证

```bash
cd cloud-platform/bin
./create_agent_key.sh

# 或直接调用 API
curl -X POST http://localhost:9090/api/v1/agents/register \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "TENANT-12345",
    "site": "beijing",
    "name": "Site-01 Agent"
  }'
```

**返回示例**:
```json
{
  "status": "registered",
  "agent_id": "TENANT-12345-beijing-a1b2c3d4",
  "credentials": {
    "agent_id": "TENANT-12345-beijing-a1b2c3d4",
    "tenant_id": "TENANT-12345",
    "site": "beijing",
    "api_token": "example-token-value",
    "api_token_hash": "sha256-hash",
    "timestamp": "2025-01-01T00:00:00Z",
    "expires_at": "2026-01-01T00:00:00Z",
    "mTLS": {
      "enabled": true,
      "certificate": "-----BEGIN CERTIFICATE-----\n...",
      "private_key": "-----BEGIN PRIVATE KEY-----\n...",
      "ca_cert": "-----BEGIN CERTIFICATE-----\n..."
    }
  },
  "config_template": {
    "agent": {
      "id": "TENANT-12345-beijing-a1b2c3d4",
      "tenant_id": "TENANT-12345",
      "site": "beijing"
    },
    "uplink": {
      "mssp_url": "https://your-cloud.example.com",
      "token": "example-token-value"
    }
  }
}
```

### 步骤 2: 下载凭证到 Edge Agent

```bash
# 保存凭证到文件
curl -X POST http://your-cloud/api/v1/agents/register \
  -H "Content-Type: application/json" \
  -d '{"tenant_id":"TENANT","site":"site"}' \
  | jq -r '.credentials' > /tmp/agent_credentials.json

# 传输到 Edge Agent
scp /tmp/agent_credentials.json user@edge-agent:/tmp/
```

### 步骤 3: 在 Edge Agent 上安装

```bash
# 在 Edge Agent 服务器上
cd /opt/CoMIDF/edge-agent

# 使用凭证安装
./bin/install_with_key.sh /tmp/agent_credentials.json
```

**安装脚本将自动**:
1. ✅ 解析凭证文件
2. ✅ 提取 agent_id, tenant_id, token
3. ✅ 生成 agent.yaml 配置文件
4. ✅ 写入 mTLS 证书（如果有）
5. ✅ 设置文件权限
6. ✅ 安装 Python 依赖
7. ✅ 创建 systemd 服务
8. ✅ 启动并验证服务

## API 端点

### POST /api/v1/agents/register

注册新 Edge Agent 并生成凭证。

**请求**:
```json
{
  "tenant_id": "TENANT-12345",
  "site": "beijing",
  "name": "Agent Name"
}
```

**响应**:
```json
{
  "status": "registered",
  "agent_id": "...",
  "credentials": {...},
  "config_template": {...}
}
```

### GET /api/v1/agents/<agent_id>/credentials

获取现有 agent 的凭证（用于重新安装或恢复）。

**请求**:
```bash
GET /api/v1/agents/TENANT-12345-beijing-a1b2c3d4/credentials
Authorization: Bearer <admin-token>
```

**响应**:
```json
{
  "agent_id": "...",
  "tenant_id": "...",
  "status": "active",
  "created_at": "...",
  "last_seen": "..."
}
```

### POST /api/v1/agents/<agent_id>/rotate

轮换 agent 的 API token。

**请求**:
```bash
POST /api/v1/agents/TENANT-12345-beijing-a1b2c3d4/rotate
Authorization: Bearer <admin-token>
```

**响应**:
```json
{
  "status": "rotated",
  "agent_id": "...",
  "new_token": "...",
  "rotate_at": "...",
  "old_token_expires_at": "..."
}
```

## 安全特性

### 1. Token 安全性

- ✅ Token 使用 `secrets.token_urlsafe()` 生成
- ✅ 存储时使用 SHA-256 哈希
- ✅ 支持密钥轮换
- ✅ 到期时间管理（默认 1 年）

### 2. mTLS 安全

- ✅ 双向 TLS 认证
- ✅ 证书由私有 CA 签发
- ✅ 证书存储在受保护的位置（600 权限）
- ✅ 定期轮换支持

### 3. 凭证传输

- ✅ 凭证文件在传输后立即删除
- ✅ 支持加密传输（SCP/HTTPS）
- ✅ 凭证文件临时存储
- ✅ 不在日志中记录敏感信息

### 4. 访问控制

- ✅ Agent ID 与 Tenant ID 绑定
- ✅ API Token 验证
- ✅ mTLS 证书验证
- ✅ 支持撤销清单

## 配置示例

### 完整的 agent.yaml

```yaml
agent:
  id: "TENANT-12345-beijing-a1b2c3d4"
  tenant_id: "TENANT-12345"
  site: "beijing"
  timezone: "Asia/Shanghai"

uplink:
  mssp_url: "https://cloud.example.com"
  fal_endpoint: "/api/fal/uer"
  token: "generated-api-token-here"
  tls:
    mtls: true
    ca_cert: "/etc/comidf/agent/ca.pem"
    cert: "/etc/comidf/agent/agent.pem"
    key: "/etc/comidf/agent/agent.key"
  retry:
    backoff_ms: [200, 500, 1000, 2000]
    max_retries: 8

buffer:
  backend: sqlite
  path: /var/lib/comidf/agent/buffer.db
  max_mb: 2048
  flush_batch: 500

privacy:
  id_salt: "SALT-ROTATE-2025Q4"
  strip_fields: ["usernames", "urls", "payload"]

agents:
  http:
    enabled: true
    thresholds:
      score_alert: 0.7
  mqtt:
    enabled: true
    thresholds:
      score_alert: 0.65

metrics:
  prometheus_port: 9108

logging:
  level: info
  json: true
```

## 密钥轮换

### 自动轮换策略

- 定期轮换：每 90 天自动轮换
- 手动轮换：管理员触发
- 紧急轮换：检测到泄露时

### 轮换流程

```bash
# 1. 在 Cloud Platform 上轮换密钥
curl -X POST http://cloud/api/v1/agents/AGENT-ID/rotate

# 2. 下载新凭证
# (同上)

# 3. 在 Edge Agent 上更新配置
./bin/install_with_key.sh new_credentials.json
systemctl restart comidf-edge
```

## 故障排除

### 问题：凭证验证失败

**症状**: Edge Agent 返回 401 Unauthorized

**检查**:
```bash
# 1. 验证 token
grep token /etc/comidf/agent/agent.yaml

# 2. 检查 token 是否过期
# 在 Cloud Platform 上查看凭证到期时间

# 3. 轮换密钥
# 重新生成凭证并更新配置
```

### 问题：mTLS 证书错误

**症状**: SSL handshake failed

**检查**:
```bash
# 1. 检查证书文件
ls -la /etc/comidf/agent/*.pem

# 2. 验证证书
openssl x509 -in /etc/comidf/agent/agent.pem -text

# 3. 检查 CA 证书
openssl verify -CAfile /etc/comidf/agent/ca.pem \
  /etc/comidf/agent/agent.pem
```

### 问题：Agent ID 冲突

**症状**: Agent registration failed

**解决**:
- Agent ID 自动生成，冲突概率极低
- 如遇冲突，重新运行注册

## 最佳实践

1. **凭证保管**
   - 凭证文件保存后立即删除
   - 不在代码仓库中提交凭证
   - 使用安全传输（SCP/HTTPS）

2. **密钥轮换**
   - 定期轮换（建议每 90 天）
   - 检测到异常时立即轮换
   - 保留旧密钥 24 小时作为缓冲

3. **权限控制**
   - 配置文件权限 600
   - 仅 comidf 用户可访问
   - 密钥文件不可读

4. **监控和告警**
   - 监控 agent 心跳
   - 检测异常访问模式
   - 记录所有轮换事件

---

**参考**:
- [部署指南](./DEPLOYMENT.md)
- [使用手册](./USAGE.md)

