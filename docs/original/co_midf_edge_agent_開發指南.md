# CoMIDF Edge Agent 開發指南（可被 Vibe Coding AI 直接執行的規格）

> 說明（Must‑Read）：
> - 本指南定位：讓工程師與 Vibe Coding AI 能 **直接依規格開發** 地端代理程式（Edge Agent），與雲端 MSSP 之 CoMIDF 平台串接。
> - 語言慣例：**程式碼、設定、API 名稱與註解一律使用 English**；**敘述文字採繁體中文**。
> - 目標架構對應論文：CoMIDF（PA → FAL → Secure Connector → GC/PR/AFL）。
> - 交付檢核：見「§13 驗收與測試標準」。

---

## 1. 系統概觀（Edge Agent 職責）
Edge Agent 於客戶端（地端）運行，負責：
1. **收集與解析**：擷取網路封包或協定事件（mirror port / span / tap / broker hooks）。
2. **本地偵測**：以 **Protocol Agents (PA)** 執行 signature/ML 初判，產生 evidence 分數與信心值。
3. **正規化封裝**：透過 **Feature Abstraction Layer (FAL)** 將事件轉為 **UER (Unified Event Record)**。
4. **安全上傳**：由 **Secure Connector** 進行租戶認證、mutual TLS、安全傳輸到雲端 GC/PR。
5. **接收回饋**：接收 AFL 的 threshold/trust/sampling 調整，套用於本地 PAs。

> 關鍵原則：地端不上傳原始封包，只上傳 UER（統計/側信道特徵），滿足隱私法規。

---

## 2. 目標系統需求（Non‑Functional Requirements）
- **性能**：單節點 ≥ 3k UER/s（burst 5k/s，持續 60s 不丟失），平均處理延遲 ≤ 50ms。
- **資源**：2 vCPU、4GB RAM、10GB Disk（含本地 buffer）。
- **可靠性**：網路中斷時可本地緩存（≥ 24h），連線恢復後自動補送（exactly‑once 目標為 at‑least‑once + 去重）。
- **安全**：TLS 1.3、mutual TLS、API token、時間同步（NTP），UER 中敏感識別以 SHA‑256+salt 匿名化。
- **可觀察性**：/health、/metrics（Prometheus）、結構化日誌（JSON）。
- **升級**：支援 OTA（auto‑update，可關閉）、回滾。

---

## 3. 元件分層與資料流
```
Packets/Telem  →  Protocol Agents (PA-*): http, mqtt, coap, zigbee, quic, modbus
                          │  (local detect: score/conf/features)
                          ▼
                Feature Abstraction Layer (FAL): normalize → UER
                          ▼
                Secure Connector: auth, mTLS, retry, buffer
                          ▼
               Cloud (MSSP): GC/PR/AFL
                          ▲
                       Feedback (AFL)
```

---

## 4. 專案目錄與模組（建議樣板）
```
edge-agent/
├── agent.yaml                  # Global config (tenant, endpoints, tls, buffers)
├── bin/
│   └── agentctl               # CLI wrapper (start/stop/status/register)
├── cmd/
│   └── agentd/main.py         # daemon entry
├── core/
│   ├── fal.py                 # FAL normalize & anonymize
│   ├── uer.py                 # UER dataclass/schema
│   ├── connector.py           # Secure Connector (HTTP/gRPC, retry, buffer)
│   ├── feedback.py            # AFL feedback handler (apply thresholds/trust)
│   └── storage.py             # local buffer (sqlite/rocksdb)
├── agents/
│   ├── http_agent.py          # HTTP/TLS PA
│   ├── mqtt_agent.py          # MQTT PA
│   ├── coap_agent.py          # CoAP PA
│   ├── modbus_agent.py        # Modbus/TCP PA
│   └── zigbee_agent.py        # Zigbee/BLE PA
├── api/
│   └── local_api.py           # local REST: /health /metrics /config /feedback
├── pkg/
│   ├── crypto.py              # tls certs, signing helpers
│   ├── util.py                # common helpers
│   └── log.py                 # structured logging
├── tests/                     # unit & integration tests
└── Dockerfile
```

---

## 5. 設定檔（`agent.yaml`）
> **English‑only keys**；以範例為準：
```yaml
agent:
  id: "edge-ap01"
  tenant_id: "TENANT-12345"
  site: "hq-taipei"
  timezone: "Asia/Taipei"

uplink:
  mssp_url: "https://mssp.example.com"
  fal_endpoint: "/api/fal/uer"        # Cloud FAL ingress or GC ingress
  token: "<API_TOKEN>"
  tls:
    mtls: true
    ca_cert: "/etc/agent/ca.pem"
    cert: "/etc/agent/agent.pem"
    key: "/etc/agent/agent.key"
  retry:
    backoff_ms: [200, 500, 1000, 2000]
    max_retries: 8

buffer:
  backend: "sqlite"                    # sqlite | rocksdb
  path: "/var/lib/edge-agent/buffer.db"
  max_mb: 2048
  flush_batch: 500

privacy:
  id_salt: "SALT-ROTATE-2025Q4"
  strip_fields: ["usernames", "urls", "payload"]

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
  coap:
    enabled: false

metrics:
  prometheus_port: 9108

logging:
  level: "info"                         # debug|info|warn|error
  json: true
```

---

## 6. UER 統一事件結構（Edge 端輸出 → Cloud）
> **Schema（English keys）**：
```json
{
  "ts": "2025-04-21T13:10:00Z",
  "src": {"ip": "10.0.0.5", "device_id": "edge-ap01", "port": 54321},
  "dst": {"ip": "10.0.0.100", "port": 1883},
  "proto": {"l7": "MQTT"},
  "stats": {"len_mean": 142, "iat_mean": 22, "pkt": 8},
  "detector": {"score": 0.78, "conf": 0.86, "model": "mqtt-v1"},
  "entities": ["device_id", "topic"],
  "attck_hint": ["T1041"],
  "tenant": "TENANT-12345",
  "site": "hq-taipei"
}
```
**必填欄位**：`ts, src.ip, dst.ip, proto.l7, detector.score, detector.conf`。
**隱私**：`src.device_id` 上傳前以 `SHA256(device_id + id_salt)` 匿名化。

---

## 7. Local Detect（PA）最小實作規格
每個 `agents/*_agent.py` 必須實作下列介面：
```python
class BaseAgent:
    name: str  # e.g., "mqtt"
    def start(self): ...       # begin capture/subscribe loop
    def stop(self): ...
    def collect(self) -> dict: ...   # return raw feature dict or packet view
    def detect(self, raw: dict) -> dict: ...
    # detect() returns: {"score": float[0..1], "conf": float[0..1], "features": {...}}
```
**偵測策略**：
- Signature engine（rules）或 ML（ONNX/PyTorch）皆可；
- `score` 代表惡意可能性；`conf` 為模型校準信心；
- Features 僅包含 side‑channel、統計欄位（避免原文 payload）。

---

## 8. FAL 規格（Normalize → Uplink）
**職責**：
- 將不同 PA 的 `features` 統一映射到 `stats`；
- 補齊時間、租戶、站點欄位；
- 匿名化 `device_id`；
- 呼叫 Secure Connector 送往雲端；
- 異常時寫入本地 buffer，待日後 flush。

**關鍵函式**：
```python
class FAL:
    def __init__(self, cfg): ...
    def normalize(self, pa_name: str, raw: dict, det: dict) -> dict: ...  # -> UER dict
    def anonymize(self, uer: dict) -> dict: ...
    def publish(self, uer: dict) -> None: ...   # use connector.send(uer)
```

---

## 9. Secure Connector（上行通道）
**HTTP/gRPC 要求**：
- HTTPS (TLS 1.3) + **mutual TLS**（client cert）；
- `Authorization: Bearer <API_TOKEN>`；
- Header：`X-Tenant-ID`, `X-Agent-ID`, `X-Schema-Version`。

**端點（Cloud 側預設）**：
```
POST {mssp_url}{fal_endpoint}
Content-Type: application/json
```
**請求 Body**：單筆 UER JSON；批次可改為 NDJSON。

**重試與緩存**：
- Exponential backoff（見 config）；
- HTTP 408/429/5xx 時重試；
- 永久錯誤（4xx except 429）→ 丟入 dead‑letter，並告警。

**去重 Idempotency**：
- UER 附 `uid = sha256(ts + src.ip + dst.ip + model + rand)`；
- 伺服端以 `uid` 做去重。

---

## 10. Feedback 通道（AFL → Edge）
**拉/推模式**：
- Pull：Edge 週期呼叫 `{mssp_url}/api/afl/policies?tenant=...&agent=...` 取得更新；
- Push（可選）：Webhook（需 mTLS）觸發 Edge `/feedback` 本地端點。

**策略格式**：
```json
{
  "agent": "mqtt",
  "thresholds": {"score_alert": 0.72},
  "sampling": {"rate": 0.8},
  "trust": {"w": 0.93, "decay": 0.9},
  "ts": "2025-10-28T02:00:00Z"
}
```
Edge 需將策略持久化並熱套用。

---

## 11. 本地 API（Edge 提供）
**Port**：預設 8600（僅本機或管理 VLAN 可存取）。

- `GET /health` → `{status:"ok", time:"...", queues:{buffer:123}}`
- `GET /metrics` → Prometheus 格式（如：`agent_buffer_pending 123`、`uplink_fail_total 5`）
- `GET /config` → 目前運行之合併設定（含版本/來源）
- `POST /feedback` → 套用策略（同 §10 格式）
- `POST /register` → 首次註冊（送 `tenant_id`, `site`, `pubkey`），回 `API_TOKEN` 與 mTLS 憑證路徑

> 建議以 FastAPI/Flask（Python）或 Go 實作；務必加上簡易 auth（local token / mTLS）。

---

## 12. 程式碼範例（Skeleton）
> 僅示意核心流程；實作時請依目錄結構拆檔。

```python
# core/uer.py
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List

@dataclass
class Endpoint:
    ip: str
    device_id: str | None = None
    port: int | None = None

@dataclass
class Detector:
    score: float
    conf: float
    model: str | None = None

@dataclass
class UER:
    ts: datetime
    src: Endpoint
    dst: Endpoint
    proto: str
    stats: Dict[str, float]
    detector: Detector
    entities: List[str]
    attck_hint: List[str]
    tenant: str
    site: str
```

```python
# core/fal.py
import hashlib, json, time
from core.uer import UER, Endpoint, Detector

class FAL:
    def __init__(self, cfg, connector):
        self.cfg = cfg
        self.connector = connector

    def _anonymize(self, device_id: str) -> str:
        salt = self.cfg["privacy"]["id_salt"]
        return hashlib.sha256(f"{device_id}{salt}".encode()).hexdigest()

    def normalize(self, pa_name: str, raw: dict, det: dict) -> dict:
        src = Endpoint(ip=raw["src_ip"], device_id=raw.get("device_id"))
        dst = Endpoint(ip=raw["dst_ip"], port=raw.get("dst_port"))
        if src.device_id:
            src.device_id = self._anonymize(src.device_id)
        uer = {
            "ts": raw["ts"],
            "src": src.__dict__,
            "dst": dst.__dict__,
            "proto": {"l7": pa_name.upper()},
            "stats": raw.get("features", {}),
            "detector": {"score": det["score"], "conf": det["conf"], "model": det.get("model", f"{pa_name}-v1")},
            "entities": ["device_id"],
            "attck_hint": det.get("attck_hint", []),
            "tenant": self.cfg["agent"]["tenant_id"],
            "site": self.cfg["agent"]["site"]
        }
        return uer

    def publish(self, uer: dict):
        self.connector.send(uer)
```

```python
# core/connector.py
import json, time, requests
from typing import List

class SecureConnector:
    def __init__(self, cfg, buffer_store):
        self.cfg = cfg
        self.store = buffer_store
        self.base = cfg["uplink"]["mssp_url"].rstrip('/')
        self.path = cfg["uplink"]["fal_endpoint"]
        self.token = cfg["uplink"]["token"]
        self.tls = cfg["uplink"]["tls"]
        self.backoff = cfg["uplink"]["retry"]["backoff_ms"]
        self.max_retries = cfg["uplink"]["retry"]["max_retries"]

    def _post(self, uer: dict):
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "X-Tenant-ID": uer["tenant"],
            "X-Agent-ID": self.cfg["agent"]["id"],
            "X-Schema-Version": "uer-v1"
        }
        cert = (self.tls["cert"], self.tls["key"]) if self.tls.get("mtls") else None
        resp = requests.post(self.base + self.path, headers=headers, json=uer, timeout=5,
                             verify=self.tls.get("ca_cert"), cert=cert)
        return resp

    def send(self, uer: dict):
        # try live send
        for i, ms in enumerate(self.backoff + [self.backoff[-1]] * (self.max_retries - len(self.backoff))):
            try:
                r = self._post(uer)
                if r.status_code < 300:
                    return
                if r.status_code in (408, 429) or r.status_code >= 500:
                    raise RuntimeError(f"retryable: {r.status_code}")
                # non-retryable
                self.store.dead_letter(uer, reason=f"HTTP {r.status_code}")
                return
            except Exception as e:
                time.sleep(ms / 1000.0)
        # persist for later flush
        self.store.enqueue(uer)
```

```python
# core/storage.py
import sqlite3, json, time

class SqliteBuffer:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.execute("CREATE TABLE IF NOT EXISTS q (id INTEGER PRIMARY KEY, uer TEXT)")
        self.conn.execute("CREATE TABLE IF NOT EXISTS dlq (id INTEGER PRIMARY KEY, uer TEXT, reason TEXT)")
        self.conn.commit()

    def enqueue(self, uer: dict):
        self.conn.execute("INSERT INTO q (uer) VALUES (?)", (json.dumps(uer),))
        self.conn.commit()

    def dequeue_batch(self, n=500):
        cur = self.conn.execute("SELECT id, uer FROM q ORDER BY id ASC LIMIT ?", (n,))
        rows = cur.fetchall()
        ids = [r[0] for r in rows]
        uers = [json.loads(r[1]) for r in rows]
        if ids:
            self.conn.execute(f"DELETE FROM q WHERE id IN ({','.join('?'*len(ids))})", ids)
            self.conn.commit()
        return uers

    def dead_letter(self, uer: dict, reason: str):
        self.conn.execute("INSERT INTO dlq (uer, reason) VALUES (?, ?)", (json.dumps(uer), reason))
        self.conn.commit()
```

---

## 13. 驗收與測試標準（Acceptance & Tests）
**功能測試**：
1. 產生 10k 筆模擬事件（各協定各 3k，混合 burst），Edge 應回報成功（200/OK）或入 queue 待送；
2. 中斷外網 10 分鐘，恢復後 5 分鐘內補送完畢，無遺失（以 uid 去重）。

**性能測試**：
- 單機 2 vCPU/4GB → 穩定 3k UER/s；平均 uplink 延遲 < 50ms；99p < 150ms。

**安全測試**：
- 必須檢查：未配置 token 或 憑證錯誤 → 一律失敗且寫 log；
- `device_id` 必為 SHA‑256 之匿名值；不得外洩原始識別子。

**API 測試**：
- `/health` 回 `ok`；`/metrics` 曝露 buffer 深度、uplink 成功率；`/feedback` 可動態改 `score_alert`。

**回歸（Regression）**：
- 提供最少 10 個單元測試（agents 偵測、FAL 匿名化、connector 重試、buffer flush）。

---

## 14. 部署與運維
**Docker**（建議）：
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV TZ=Asia/Taipei PYTHONUNBUFFERED=1
EXPOSE 8600
CMD ["python","cmd/agentd/main.py","--config","/etc/agent/agent.yaml"]
```

**Systemd**（可選）:
```
[Unit]
Description=CoMIDF Edge Agent
After=network-online.target

[Service]
ExecStart=/usr/bin/python /opt/edge-agent/cmd/agentd/main.py --config /etc/agent/agent.yaml
Restart=always
User=agent

[Install]
WantedBy=multi-user.target
```

**滾動更新（OTA）**：
- 預設每日凌晨 03:00 查詢版本；
- 有新版本 → 下載鏡像 → 健康檢查 → 切換 → 失敗即回滾。

---

## 15. 安全與合規最佳實務
- **最小化資料**：不上傳 payload；僅上傳側信道/統計特徵；
- **匿名化**：所有可識別資訊（device_id, hostname）均 hash+salt；
- **時間同步**：NTP；
- **密鑰輪替**：API token 與 salt 皆需定期更新（預設 90 天）。

---

## 16. 開發規範（Coding Standards）
- **語言**：Python 3.11+；type hints 強制；
- **風格**：Black + isort + flake8；
- **日誌**：JSON 結構，含 `tenant`, `agent_id`, `event_uid`；
- **錯誤碼**：上行失敗需分類（4xx 非重試；408/429/5xx 重試）；
- **重試策略**：指數退避 + 抖動；
- **測試覆蓋**：關鍵模組 ≥ 80%。

---

## 17. 開發任務 Checklist（給 Vibe Coding AI）
- [ ] 生成專案樣板與 `agent.yaml` 解析器
- [ ] 實作 `SqliteBuffer` 與 flush worker（background thread）
- [ ] 完成 `SecureConnector.send()`（含 mTLS、retry、DLQ）
- [ ] 完成 `FAL.normalize()/publish()`（含 anonymize）
- [ ] 實作 `mqtt_agent.py` 與 `http_agent.py` 的 `detect()`（rule 或 mock ML）
- [ ] 起本地 API：`/health /metrics /feedback /config`（FastAPI）
- [ ] 單元測試 10+；整合測試（模擬雲端 endpoint）
- [ ] Dockerfile + Compose（本地起跑）
- [ ] 性能與穩定性測試，達到 §2 指標

---

## 18. 參考 API 合約（Edge → Cloud）
**OpenAPI snippet（供雲端端點參考）**：
```yaml
openapi: 3.0.0
info:
  title: CoMIDF FAL Ingress API
  version: "1.0"
paths:
  /api/fal/uer:
    post:
      summary: Ingest single UER
      security:
        - bearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/UER'
      responses:
        '200': {description: OK}
        '400': {description: Bad Request}
        '401': {description: Unauthorized}
        '429': {description: Too Many Requests}
        '500': {description: Server Error}
components:
  schemas:
    UER:
      type: object
      required: [ts, src, dst, proto, detector]
      properties:
        ts: {type: string, format: date-time}
        src:
          type: object
          properties:
            ip: {type: string}
            device_id: {type: string}
            port: {type: integer}
        dst:
          type: object
          properties:
            ip: {type: string}
            port: {type: integer}
        proto:
          type: object
          properties:
            l7: {type: string}
        stats:
          type: object
          additionalProperties: {type: number}
        detector:
          type: object
          required: [score, conf]
          properties:
            score: {type: number}
            conf: {type: number}
            model: {type: string}
        entities:
          type: array
          items: {type: string}
        attck_hint:
          type: array
          items: {type: string}
        tenant: {type: string}
        site: {type: string}
securitySchemes:
  bearerAuth:
    type: http
    scheme: bearer
    bearerFormat: JWT
```

---

## 19. 常見錯誤與處置
- **401 Unauthorized**：檢查 token 與 mTLS 憑證；
- **429 Too Many Requests**：降低 `flush_batch` 或上傳速率；
- **Buffer 滿**：提升 `max_mb` 或縮短 flush 週期；
- **時鐘飄移**：確認 NTP；過期事件應標示並仍可送出（由雲端決策）。

---

### 附錄 A：指令操作範例
```bash
# Start agent
python cmd/agentd/main.py --config /etc/agent/agent.yaml

# Query health
curl -s http://127.0.0.1:8600/health | jq

# Apply feedback
curl -s -X POST http://127.0.0.1:8600/feedback -d '{"agent":"mqtt","thresholds":{"score_alert":0.72}}' -H 'Content-Type: application/json'
```

### 附錄 B：Metrics 指標（Prometheus）
```
agent_buffer_pending  
agent_uplink_success_total  
agent_uplink_fail_total  
agent_feedback_applied_total  
agent_event_rate_per_sec  
```

---

> **完成本規格即足以讓 Vibe Coding AI 與工程團隊開始實作 Edge Agent**。若需，我們可再補上 Kafka/NDJSON 批次上傳、時窗聚合與更完整的 OTA 機制細節。

