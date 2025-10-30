# CoMIDF MSSP 雲端平台開發指南（與 Edge Agent 完美整合版）

> 目標：本指南提供 **MSSP Cloud** 端完整的開發規格，保證與《CoMIDF Edge Agent 開發指南》無縫整合。
> - 語言慣例：**程式碼、API 名稱、結構欄位皆為 English**；說明以繁體中文撰寫。
> - 版本：Integration Contract **v1.1**（本文件定義）。
> - 對應 Edge 端：需配合 Edge Guide 之 `uer-v1.1` schema、idempotency、rate limit 與 feedback 流程。

---

## 1. 整體架構與資料流（Cloud）
```
Internet (mTLS) → API Gateway (Ingress) → Kafka (per-tenant topics) → GC (fusion) → PR (actions) → AFL (policies)
                                                                             ↓
                                                                 Portal / Dashboard / Reports
```
- **Ingress**：驗證租戶，驗證 mTLS 與 Bearer Token，做基本結構檢查與 idempotency 檢查，然後投遞 Kafka。
- **GC**（Global Correlator）：以 Bayesian + Dempster–Shafer 融合多協定證據，輸出 posterior 與 uncertainty。
- **PR**（Policy & Response）：依 posterior 產生 alert / action，並同步儲存以便報表與查詢。
- **AFL**（Active Feedback Loop）：彙總 per-tenant 與 per-agent 近期表現，輸出 trust/threshold/sampling 策略。

---

## 2. 多租戶（Multi-Tenancy）模型
- **Tenant identity**：HTTP Header `X-Tenant-ID` 必填，亦寫入 Kafka topic 名稱與 DB schema。
- **Per-tenant resources**：
  - Kafka topics：`uer.ingest.<tenant>`, `uer.deadletter.<tenant>`, `afl.feedback.<tenant>`
  - DB schemas：`tenant_<id>`（PostgreSQL / Timescale），ES index：`uer-<tenant>-YYYY.MM.DD`
  - Secrets：每租戶獨立 mTLS 憑證與 JWT 客戶端金鑰（Cloud 以 JWKS 驗證）
- **RBAC**：Portal 僅能檢視本租戶資料；MSSP Operator 具跨租戶只讀權限。

---

## 3. API Gateway（Ingress）規格
### 3.1 Endpoints
- `POST /api/fal/uer` — **single UER ingest**（Edge 端預設使用）
- `POST /api/fal/uer/_bulk` — **NDJSON bulk ingest**（建議 Edge 端批次上傳時使用）

### 3.2 Headers（必填）
- `Authorization: Bearer <JWT>`（RS256；Cloud 驗證）
- `X-Tenant-ID: <tenant>`
- `X-Agent-ID: <edge-agent-id>`
- `X-Schema-Version: uer-v1.1`

### 3.3 Security
- TLS 1.3、**mutual TLS**（客戶端憑證 CN=AgentID）；
- JWT 驗證：`iss`, `aud`, `exp` 檢查，並以租戶綁定 token；
- **Idempotency**：Body 欄位 `uid`（若缺少，Gateway 代為生成），以 Redis 7（或 Postgres upsert）做 24h 去重。

### 3.4 Rate Limit（per-agent）
- 基礎：`R = 3000 events/s`，burst 5000/s（60 秒平滑窗）；
- 超額：`429 Too Many Requests`，Edge 端依回退策略重試；
- 觀測：`X-RateLimit-Remaining`、`X-RateLimit-Reset` 回傳。

### 3.5 驗證與拒收條件
- 缺 header 或 JWT 無效 → 401；
- Schema 版本不相容 → 400 + 描述；
- `ts` 超過 24 小時 → 接收但標示 `late=true`；
- Payload 大於 256KB → 413，建議改 bulk。

---

## 4. UER Schema（`uer-v1.1`）
> 相容 Edge Guide（v1.1）；`tenant`、`site` 改由 Gateway 注入、Edge 端可填可不填。
```json
{
  "uid": "sha256(ts+src.ip+dst.ip+model+nonce)",
  "ts": "2025-04-21T13:10:00Z",
  "src": {"ip": "10.0.0.5", "device_id": "<hashed>", "port": 54321},
  "dst": {"ip": "10.0.0.100", "port": 1883},
  "proto": {"l7": "MQTT"},
  "stats": {"len_mean": 142, "iat_mean": 22, "pkt": 8},
  "detector": {"score": 0.78, "conf": 0.86, "model": "mqtt-v1"},
  "entities": ["device_id", "topic"],
  "attck_hint": ["T1041"],
  "tenant": "TENANT-12345",
  "site": "hq-taipei",
  "late": false
}
```
- **注意**：`src.device_id` 必為 Edge 端已匿名化（SHA256+salt）。Cloud 不接收明文識別。

---

## 5. Kafka Topic 與訊息格式
- `uer.ingest.<tenant>`：key=`uid`，value=`UER JSON`；
- `uer.deadletter.<tenant>`：不可解析或 4xx 錯誤之 UER；
- Partition 建議：`max(12, agents*2)`；保留 7 天；壓縮 `lz4`。

---

## 6. Global Correlator（GC）服務
### 6.1 功能
- 以時間窗（sliding window，如 5s/10s）聚合同一會話或主體之 UER；
- 機率融合：Bayesian 乘法（依信任權重 `w_i`）+ DS 證據理論處理衝突；
- 產生 `posterior`、`uncertainty` 與 `explain`（貢獻度、top features）。

### 6.2 介面
- Consumer：subscribe `uer.ingest.<tenant>`；
- Producer：`gc.posterior.<tenant>`（供 PR/AFL 後續處理）；
- REST（可選）：`GET /api/gc/health`、`GET /api/gc/metrics`。

### 6.3 效能要求
- 延遲（p95）< 100ms；
- 單節點 20k UER/s；
- 水平擴展：stateless workers + Kafka partitions。

---

## 7. Policy & Response（PR）
### 7.1 規則
- 預設動作：`posterior >= 0.6 → ALERT`、`>= 0.85 → ACTION (isolate/quarantine)`（二步驗證可開關）；
- Enrich：IOC/ATT&CK 對應，查 CTI（OpenCTI/MISP）。

### 7.2 介面
- Input：`gc.posterior.<tenant>` topic；
- Output：`/api/alerts`（Portal 用）、Webhooks、Email、Syslog、SOAR connectors。

### 7.3 審計
- 事件寫入 Postgres（metadata）與 ES（全文索引）；
- 生成週報/月報（PDF, CSV, JSON API）。

---

## 8. Active Feedback Loop（AFL）
### 8.1 功能
- 計算 per-tenant、per-agent 近期精準度（Precision/Recall/FPR）；
- 產出策略：`trust.w`, `thresholds.score_alert`, `sampling.rate`；
- 發送：
  - **Push**：POST `https://edge:8600/feedback`（mTLS）
  - **Pull**：提供 `GET /api/afl/policies?tenant=...&agent=...`（Edge 端週期拉取）

### 8.2 策略格式（v1.1）
```json
{
  "agent": "mqtt",
  "thresholds": {"score_alert": 0.72},
  "sampling": {"rate": 0.8},
  "trust": {"w": 0.93, "decay": 0.9},
  "ts": "2025-10-28T02:00:00Z",
  "schema": "afl-v1.1"
}
```

---

## 9. Portal / Dashboard
- 多租戶登入（Keycloak / OIDC）；
- 視覺化：事件時間線、posterior 分布、Agent trust 曲線、Top protocols；
- 查詢：以 ES 查 UER 與 Alert；
- 報表：PDF 匯出，API 提供 JSON 原始資料。

---

## 10. 資料庫設計（簡要）
### 10.1 PostgreSQL（metadata）
- `tenants(id, name, status, created_at)`
- `agents(id, tenant_id, site, status, last_seen)`
- `alerts(id, tenant_id, agent_id, ts, posterior, action, severity, rule_id)`
- `policies(id, tenant_id, agent, payload_json, ts)`

### 10.2 Elasticsearch（document）
- Index pattern：`uer-<tenant>-*`、`alerts-<tenant>-*`
- Mappings：`ts`（date）、`posterior`（scaled_float）、`proto.l7`（keyword）

---

## 11. 安全性與合規
- 僅接收匿名化識別（哈希）；
- 雙向 TLS + JWT，憑證/金鑰輪替（90 天）；
- Audit trail：Ingress/GC/PR/AFL 全鏈路；
- 資料主權：支援 region pinning（資料不跨區）。

---

## 12. Observability（可觀察性）
- Prometheus metrics：
  - Ingress：`ingress_requests_total`, `ingress_reject_total`, `ingress_latency_ms`
  - GC：`gc_fusion_latency_ms`, `gc_throughput_eps`, `gc_agent_trust_avg`
  - PR：`pr_alerts_total`, `pr_actions_total`
  - AFL：`afl_policies_issued_total`, `afl_push_fail_total`
- Logs：JSON，集中到 ES；
- Tracing：OpenTelemetry（Ingress→Kafka→GC→PR→AFL）。

---

## 13. 部署與擴展
- Kubernetes：
  - `ingress-gw`（HPA, mTLS termination）
  - `kafka-cluster`（3–5 brokers, 3 zookeepers 或 KRaft）
  - `gc-deployment`（stateless workers, HPA by QPS）
  - `pr-deployment`, `afl-deployment`
  - `postgres`, `elasticsearch`, `redis`, `minio`
- CI/CD：GitHub Actions + ArgoCD；
- 秘密：KMS/Sealed Secrets 管理。

---

## 14. 測試與驗收（Cloud 端）
| 類別 | 測試內容 | 驗收標準 |
|------|----------|----------|
| Ingress | mTLS+JWT 驗證、Rate limit、Idempotency | 100% 通過；重放不重複入列 |
| GC | 20k UER/s 吞吐；p95 < 100ms | 通過 |
| PR | 規則命中與二步動作 | 正確觸發、審計完整 |
| AFL | Push/Pull 雙模式策略下發 | Edge 收到並套用；Portal 顯示變更 |
| 故障 | Kafka 宕機、DB 延遲、跨區降級 | 自動緩衝與告警、不中斷 Ingress |

---

## 15. OpenAPI 摘要（Cloud 端）
```yaml
openapi: 3.0.0
info:
  title: CoMIDF Cloud Ingress & AFL API
  version: 1.1
paths:
  /api/fal/uer:
    post:
      summary: Ingest single UER
      parameters:
        - in: header
          name: X-Tenant-ID
          required: true
          schema: {type: string}
        - in: header
          name: X-Agent-ID
          required: true
          schema: {type: string}
        - in: header
          name: X-Schema-Version
          required: true
          schema: {type: string}
      requestBody:
        required: true
        content:
          application/json:
            schema: {$ref: '#/components/schemas/UER'}
      responses:
        '200': {description: OK}
        '400': {description: Bad Request}
        '401': {description: Unauthorized}
        '413': {description: Payload Too Large}
        '429': {description: Too Many Requests}
  /api/fal/uer/_bulk:
    post:
      summary: Ingest UER in NDJSON bulk format
      responses:
        '200': {description: OK}
  /api/afl/policies:
    get:
      summary: Get AFL policies for an agent
      parameters:
        - in: query
          name: tenant
          required: true
          schema: {type: string}
        - in: query
          name: agent
          required: true
          schema: {type: string}
      responses:
        '200': {description: OK}
components:
  schemas:
    UER:
      type: object
      required: [ts, src, dst, proto, detector]
      properties:
        uid: {type: string}
        ts: {type: string, format: date-time}
        src:
          type: object
          properties: {ip: {type: string}, device_id: {type: string}, port: {type: integer}}
        dst:
            type: object
            properties: {ip: {type: string}, port: {type: integer}}
        proto:
          type: object
          properties: {l7: {type: string}}
        stats:
          type: object
          additionalProperties: {type: number}
        detector:
          type: object
          properties: {score: {type: number}, conf: {type: number}, model: {type: string}}
        entities:
          type: array
          items: {type: string}
        attck_hint:
          type: array
          items: {type: string}
        tenant: {type: string}
        site: {type: string}
```

---

## 16. 版本政策（Versioning）
- Schema 版本：`X-Schema-Version: uer-vMAJOR.MINOR`；本版為 **uer-v1.1**；
- 回溯相容：MINOR 版本維持欄位相容；MAJOR 版本另行公告遷移。

---

## 17. 與 Edge Agent 的整合要點（Check List）
- [ ] Edge 端以 `uer-v1.1` 出版欄位；
- [ ] 送入 `POST /api/fal/uer` 或 `_bulk`；
- [ ] Headers 齊全、mTLS 與 JWT 驗證通過；
- [ ] 支援 `429` 回退重試；
- [ ] `uid` 去重 24h；
- [ ] 可 Pull `GET /api/afl/policies` 或接受 Push `/feedback`；
- [ ] Portal 能看到 Edge Agent 狀態與版本。

---

> 完成本指南後，Cloud 與 Edge 可依 **Integration Contract v1.1** 直接對接；任何契約更新請同步更新 Edge 指南與此文件。



---

## 20. Integration Contract v1.1（Edge ⇄ Cloud 同步補充）
**此節為與《MSSP 雲端平台開發指南》一致的契約更新，Edge 端需遵循：**

### 20.1 Schema 與 Headers
- `X-Schema-Version: uer-v1.1`
- `X-Tenant-ID: <tenant>`、`X-Agent-ID: <edge-agent-id>`
- 仍使用 **mTLS + Bearer JWT**（RS256），Cloud 會同時驗證兩者。

### 20.2 UER 變更（v1.1）
- 新增／強化欄位：`uid`（建議 Edge 端先生成，若缺 Cloud 將代生成）、`late`（可不送，Cloud 會自動判定遲到標記）。
- `tenant`、`site` 可留空，Cloud Gateway 會依 header 注入（Edge 端保留填寫亦可）。

### 20.3 上行端點與批次
- 單筆：`POST {mssp_url}/api/fal/uer`
- 批次：`POST {mssp_url}/api/fal/uer/_bulk`（**NDJSON**，每行一筆 UER），建議大流量改用批次以降低開銷。

### 20.4 回退與速率限制
- 速率：每 Agent 基準 `3000 eps`（burst 5000/s，60 秒窗）。
- 收到 `429` 時：依 `agent.yaml` 的 backoff 設定重試；
- `408/5xx`：重試；`4xx(≠429)`：寫入 DLQ 並產生告警。

### 20.5 Idempotency 去重
- Edge 端請以 `uid = sha256(ts + src.ip + dst.ip + detector.model + nonce)` 生成；
- 同一 `uid` 在 24h 內不應重複被處理；Cloud 將以 Redis/Postgres upsert 保障去重。

### 20.6 Feedback 對接
- Pull：`GET {mssp_url}/api/afl/policies?tenant=<>&agent=<>`，回傳 `afl-v1.1`；
- Push（可選）：Cloud → `https://edge:8600/feedback`（mTLS）；
- Edge 端需將策略 **持久化** 並 **熱套用**（不重啟）。

> 本節屬必要同步；Edge 端實作完成後，即與 Cloud 端的《Integration Contract v1.1》完全一致。

