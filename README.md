# CoMIDF: Collaborative Multi-Protocol Intrusion Detection Framework

## 项目概述

CoMIDF 是一个多协议协同入侵检测框架，支持 HTTP(S)、MQTT、CoAP、Zigbee、BLE、Modbus/TCP、QUIC 等异构网络环境。

### 核心特性

- 🔍 **多协议检测** - 统一检测 HTTP、MQTT、CoAP 等多种协议
- 🧠 **智能融合** - Bayesian + Dempster-Shafer 证据融合引擎
- 🔄 **主动反馈** - AFL 机制动态调整检测阈值
- 🔐 **隐私保护** - 设备 ID 匿名化，不传输 payload 数据
- ☁️ **云端融合** - MSSP 多租户平台集中分析
- 🔋 **轻量边缘** - Edge Agent 支持离线运行

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                     Edge Layer                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │ HTTP PA  │  │ MQTT PA   │  │ CoAP PA  │             │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘             │
│       │             │             │                     │
│       └─────────────┴─────────────┘                     │
│                      ↓                                    │
│              ┌──────────────┐                            │
│              │  FAL (UER)   │                            │
│              └──────┬───────┘                            │
│                     ↓                                     │
│              Secure Connector (mTLS)                      │
└────────────────────┬─────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────┐
│                   Cloud Platform                         │
│  ┌──────────────────────────────────────────┐           │
│  │   Ingress → Kafka → GC → PR → AFL       │           │
│  └──────────────────────────────────────────┘           │
│                                                           │
│  - Global Correlator (Bayesian Fusion)                   │
│  - Policy & Response (Alert Generation)                  │
│  - Active Feedback Loop (Dynamic Tuning)                  │
│  - Multi-Tenant Dashboard & Reports                     │
└─────────────────────────────────────────────────────────┘
```

## 项目结构

```
CoMIDF/
├── edge-agent/              # Edge Agent 实现
│   ├── agents/              # Protocol Agents
│   │   ├── base_agent.py    # 基础 Agent 类
│   │   ├── http_agent.py    # HTTP/TLS Agent
│   │   ├── mqtt_agent.py    # MQTT Agent
│   │   └── coap_agent.py    # CoAP Agent
│   ├── core/                # 核心模块
│   │   ├── uer.py           # Unified Event Record
│   │   ├── fal.py           # Feature Abstraction Layer
│   │   ├── connector.py     # Secure Connector
│   │   ├── storage.py       # Local Buffer (SQLite)
│   │   └── feedback.py      # AFL Handler
│   ├── api/                 # 本地 API
│   │   └── local_api.py    # REST API (/health, /metrics, /feedback)
│   ├── cmd/agentd/          # Daemon
│   │   └── main.py         # 主程序入口
│   ├── bin/agentctl        # CLI 工具
│   ├── agent.yaml           # 配置文件
│   ├── requirements.txt     # Python 依赖
│   ├── Dockerfile           # Docker 镜像
│   └── README.md            # Edge 文档
│
├── cloud-platform/          # Cloud Platform
│   ├── services/            # Cloud 服务
│   │   ├── ingress.py      # Ingress Gateway
│   │   ├── gc.py            # Global Correlator
│   │   ├── pr.py            # Policy & Response
│   │   └── afl.py           # Active Feedback Loop
│   ├── cloud_platform.yaml  # Cloud 配置
│   ├── requirements.txt     # Python 依赖
│   ├── docker-compose.yml   # Docker Compose
│   └── Dockerfile           # Docker 镜像
│
├── tests/                  # 单元测试
│   ├── test_uer.py          # UER 测试
│   └── test_fal.py          # FAL 测试
│
├── docs/                    # 文档
│   ├── collaborative_ids_framework.md              # 论文
│   ├── co_midf_edge_agent_開發指南.md           # Edge 开发指南
│   ├── co_midf_mssp_雲端平台開發指南.md         # Cloud 开发指南
│   └── co_midf_產品開發規格指南.md             # 产品规格
│
├── USAGE.md                 # 使用指南
└── README.md                # 本文件
```

## 快速开始

### 1. Edge Agent

```bash
cd edge-agent

# 安装依赖
pip install -r requirements.txt

# 配置
cp agent.yaml agent-local.yaml
# 编辑 agent-local.yaml

# 运行
python cmd/agentd/main.py --config agent-local.yaml

# Docker 运行
docker build -t comidf-edge .
docker run -d -p 8600:8600 comidf-edge
```

### 2. Cloud Platform

```bash
cd cloud-platform

# Docker Compose 启动
docker-compose up -d

# 查看日志
docker-compose logs -f
```

## 核心组件说明

### Edge Agent

- **Protocol Agents (PA)** - 协议特定检测器
- **Feature Abstraction Layer (FAL)** - 特征抽象与标准化
- **Secure Connector** - 安全上传（mTLS + JWT）
- **Local Buffer** - 离线缓存（SQLite）
- **Feedback Handler** - 接收 AFL 策略

### Cloud Platform

- **Ingress** - 接收 UER，验证与去重
- **Global Correlator (GC)** - 证据融合引擎
- **Policy & Response (PR)** - 告警与响应
- **Active Feedback Loop (AFL)** - 动态调优

## UER Schema

统一事件记录格式：

```json
{
  "uid": "sha256_hash",
  "ts": "2025-04-21T13:10:00Z",
  "src": {
    "ip": "10.0.0.5",
    "device_id": "hashed_device_id",
    "port": 54321
  },
  "dst": {
    "ip": "10.0.0.100",
    "port": 1883
  },
  "proto": {"l7": "MQTT"},
  "stats": {
    "len_mean": 142,
    "iat_mean": 22,
    "pkt": 8
  },
  "detector": {
    "score": 0.78,
    "conf": 0.86,
    "model": "mqtt-v1"
  },
  "entities": ["device_id", "topic"],
  "attck_hint": ["T1041"],
  "tenant": "TENANT-12345",
  "site": "hq-taipei"
}
```

## 工作流程

1. **Edge**: Protocol Agent 采集并检测 → FAL 标准化 → UER 封装
2. **Upload**: Secure Connector 通过 mTLS 上传 UER 到 Cloud
3. **Cloud**: Ingress 接收并验证 → Kafka 存储 → GC 融合
4. **Decision**: PR 生成告警/行动 → AFL 计算策略
5. **Feedback**: AFL 下发策略到 Edge，动态调整阈值

## 实验性能

根据论文实验：

- **召回率**: 提升 12% (vs 单协议检测)
- **误报率**: 降低 9%
- **延迟**: < 100ms @ 10k events/s
- **资源**: Edge 2 vCPU, 4GB RAM

## 安全特性

- ✅ Mutual TLS (mTLS)
- ✅ JWT Bearer Tokens
- ✅ SHA-256 设备 ID 匿名化
- ✅ 不传输 payload 数据
- ✅ 时间戳对齐与去重
- ✅ Audit Trail 审计日志

## 文档

- [论文](./collaborative_ids_framework.md)
- [Edge 开发指南](./co_midf_edge_agent_開發指南.md)
- [Cloud 开发指南](./co_midf_mssp_雲端平台開發指南（與_edge_agent_完美整合版）.md)
- [产品规格](./co_midf_產品開發規格指南.md)
- [使用指南](./USAGE.md)

## 技术栈

### Edge Agent
- Python 3.11
- Flask (REST API)
- SQLite (Local Buffer)
- Requests (HTTP Client)

### Cloud Platform
- Python 3.11
- FastAPI / Flask (REST API)
- Kafka (Message Queue)
- PostgreSQL (Metadata)
- Redis (Idempotency Cache)
- Elasticsearch (Search)

### Infrastructure
- Docker & Docker Compose
- Kubernetes (生产部署)
- Prometheus & Grafana (监控)
- mTLS + JWT (安全)

## 测试

```bash
# Edge Agent 测试
cd edge-agent
python tests/test_uer.py
python tests/test_fal.py

# 集成测试
cd ..
python -m pytest tests/
```

## 贡献

项目遵循以下规范：

- 代码: English only
- 文档: 繁体中文
- 风格: Black + isort + flake8
- 测试: 覆盖率 ≥ 80%

## 许可证

[待定]

## 联系方式

[待定]

---

**CoMIDF** - A Collaborative Multi-Protocol Intrusion Detection Framework

