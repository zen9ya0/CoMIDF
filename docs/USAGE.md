# CoMIDF 使用指南

## 项目结构

```
CoMIDF/
├── edge-agent/              # Edge Agent 实现
│   ├── agents/              # Protocol Agents (HTTP, MQTT, CoAP)
│   ├── core/                # 核心模块 (UER, FAL, Connector, Storage)
│   ├── api/                 # 本地 REST API
│   ├── cmd/agentd/          # Agent daemon 主程序
│   ├── bin/agentctl         # CLI 工具
│   ├── agent.yaml           # 配置文件
│   ├── requirements.txt      # Python 依赖
│   └── Dockerfile           # Docker 镜像
├── cloud-platform/          # Cloud Platform 实现
│   ├── services/             # Cloud 服务 (Ingress, GC, PR, AFL)
│   ├── cloud_platform.yaml  # Cloud 配置
│   ├── requirements.txt      # Python 依赖
│   ├── Dockerfile           # Docker 镜像
│   └── docker-compose.yml    # Docker Compose
├── tests/                   # 单元测试
└── docs/                    # 文档
```

## Edge Agent 快速开始

### 1. 本地开发

```bash
cd edge-agent

# 安装依赖
pip install -r requirements.txt

# 配置 agent.yaml
cp agent.yaml agent-local.yaml
# 编辑 agent-local.yaml 设置 tenant_id, token, etc.

# 运行 Agent
python cmd/agentd/main.py --config agent-local.yaml
```

### 2. Docker 部署

```bash
# 构建镜像
docker build -t comidf-edge-agent edge-agent/

# 运行容器
docker run -d \
  --name edge-agent \
  -v $(pwd)/edge-agent/agent.yaml:/etc/agent/agent.yaml \
  -p 8600:8600 \
  comidf-edge-agent
```

### 3. 使用 CLI 工具

```bash
# 检查状态
./edge-agent/bin/agentctl status

# 查看 metrics
./edge-agent/bin/agentctl metrics

# 查看配置
./edge-agent/bin/agentctl config

# 应用反馈策略
./edge-agent/bin/agentctl feedback policy.json
```

## Cloud Platform 快速开始

### 1. 使用 Docker Compose

```bash
cd cloud-platform

# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f ingress

# 停止服务
docker-compose down
```

### 2. 单独启动服务

```bash
# 启动 Ingress
python services/ingress.py

# 启动 GC
python services/gc.py

# 启动 PR
python services/pr.py

# 启动 AFL
python services/afl.py
```

## 测试

### Edge Agent 测试

```bash
cd edge-agent

# 运行单元测试
python -m pytest tests/

# 运行特定测试
python tests/test_uer.py
python tests/test_fal.py
```

### 集成测试

```bash
# 启动 Cloud Platform
cd cloud-platform
docker-compose up -d

# 启动 Edge Agent
cd edge-agent
python cmd/agentd/main.py --config agent.yaml

# 发送测试请求
curl http://localhost:8600/health
curl http://localhost:8080/health
```

## 配置说明

### Edge Agent 配置 (agent.yaml)

```yaml
agent:
  id: "edge-ap01"           # Agent 唯一标识
  tenant_id: "TENANT-12345" # 租户 ID
  site: "hq-taipei"          # 站点名称

uplink:
  mssp_url: "https://mssp.example.com"  # Cloud URL
  fal_endpoint: "/api/fal/uer"          # 上传端点
  token: "<API_TOKEN>"                  # API Token
  tls:
    mtls: true                           # 启用 mTLS
    cert: "/etc/agent/agent.pem"        # 客户端证书
    key: "/etc/agent/agent.key"          # 私钥

agents:
  http:
    enabled: true              # 启用 HTTP Agent
    pcap: "/dev/net/tap0"      # 网络接口
    thresholds:
      score_alert: 0.7         # 告警阈值

  mqtt:
    enabled: true              # 启用 MQTT Agent
    source: "tcp://127.0.0.1:1883"
    thresholds:
      score_alert: 0.65
```

### Cloud Platform 配置 (cloud_platform.yaml)

```yaml
ingress:
  port: 8080                   # Ingress 端口
  mtsl: true                   # mTLS
  rate_limit:
    per_agent: 3000           # 每 Agent 速率限制
    burst: 5000

gc:
  window_size_sec: 5          # 时间窗口
  trust_alpha: 0.9             # 信任衰减系数

pr:
  thresholds:
    alert: 0.6                 # 告警阈值
    action: 0.85                # 行动阈值

afl:
  update_interval_sec: 300     # 更新间隔
```

## API 端点

### Edge Agent API (端口 8600)

- `GET /health` - 健康检查
- `GET /metrics` - Prometheus metrics
- `GET /config` - 当前配置
- `POST /feedback` - 接收 AFL 策略

### Cloud Platform Ingress (端口 8080)

- `POST /api/fal/uer` - 单个 UER 上传
- `POST /api/fal/uer/_bulk` - 批量 UER 上传 (NDJSON)
- `GET /health` - 健康检查

## 示例策略文件 (policy.json)

```json
{
  "agent": "mqtt",
  "thresholds": {"score_alert": 0.72},
  "sampling": {"rate": 0.8},
  "trust": {"w": 0.93, "decay": 0.9},
  "ts": "2025-10-28T02:00:00Z"
}
```

## 故障排除

### Edge Agent 无法连接到 Cloud

1. 检查 agent.yaml 中的 mssp_url
2. 验证 Token 是否正确
3. 检查证书路径
4. 查看日志: `docker logs edge-agent`

### Cloud Ingress 返回 401

1. 检查 Token 是否有效
2. 验证 X-Tenant-ID 和 X-Agent-ID headers
3. 检查 mTLS 证书

### Buffer 队列满

1. 增加 buffer.max_mb
2. 检查网络连接
3. 查看 connector 日志

## 开发指南

### 添加新的 Protocol Agent

```python
# agents/my_protocol_agent.py
from agents.base_agent import BaseAgent

class MyProtocolAgent(BaseAgent):
    def collect(self) -> Dict:
        # 收集协议数据
        pass
    
    def detect(self, raw: Dict) -> Dict:
        # 检测异常
        return {
            "score": 0.5,
            "conf": 0.8,
            "model": "my-protocol-v1"
        }
```

### 扩展 GC 融合算法

修改 `cloud-platform/services/gc.py` 中的 `fuse_evidences()` 方法。

## 安全最佳实践

1. **使用 mTLS** - 所有通信使用 mutual TLS
2. **Token 轮换** - 定期更新 API Token
3. **设备 ID 匿名化** - 使用 SHA-256 + salt
4. **不传输 payload** - 只传输统计特征
5. **审计日志** - 记录所有操作

## 性能调优

### Edge Agent

- 调整 `flush_batch` 大小
- 优化 Protocol Agents 采集间隔
- 使用 RocksDB 替代 SQLite (高负载场景)

### Cloud Platform

- 增加 Kafka partition 数量
- 调整 GC window_size_sec
- 使用多个 GC workers

## 更多资源

- 论文: `collaborative_ids_framework.md`
- Edge 开发指南: `co_midf_edge_agent_開發指南.md`
- Cloud 开发指南: `co_midf_mssp_雲端平台開發指南.md`
- 产品规格: `co_midf_產品開發規格指南.md`

